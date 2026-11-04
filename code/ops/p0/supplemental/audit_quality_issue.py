#!/usr/bin/env python
"""P0 补充审计 · data_quality_issue 全量行级核验（只读）

以**未被修改的正式库** `canvas_history` 作为导入前基线，与演练库
`canvas_history_p0_rehearsal`（V9 + staging_m4_5 导入后）逐行比对。

比对键怎么选，必须先说清楚：

* 表上 `issue_id` 是 identity 主键，但导入时新行会重新取号，**跨库不可比**；
* 真正决定"是不是同一条质量事实"的是生成列 `issue_fingerprint`
  = `fn_issue_fingerprint(source_record_id, dataset_id, place_id, issue_type, field_name, observed_value)`，
  表上还有 `uq_data_quality_issue_c10 UNIQUE(issue_fingerprint)`，导入器也正是拿它做
  `ON CONFLICT` 目标。所以**指纹是唯一的业务键**。

由此推出两条判据：

1. 原有 12,831 条的指纹必须**全部仍在**；
2. 原有行允许变化的列只有两列 —— `last_batch_id`（设计如此）与 `occurrence_count`
   （每次重复命中 +1）。其余列若变了，就是"内容被改写"，必须逐条列出。

用法：
    python ops/p0/supplemental/audit_quality_issue.py \
        --baseline canvas_history --after canvas_history_p0_rehearsal
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List

CODE_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(CODE_ROOT / "ops" / ".deps"))
sys.path.insert(0, str(CODE_ROOT / "ops"))

import psycopg2  # noqa: E402

from import_staging import load_env  # noqa: E402

OUT = CODE_ROOT / "ops" / "reports" / "p0" / "supplemental_audit"

#: 原有行允许变化的列（其余列一旦变化即为"内容被改写"）。
MUTABLE = {"last_batch_id", "occurrence_count"}

COLUMNS = [
    "issue_id", "issue_fingerprint", "dataset_id", "source_record_id", "place_id",
    "batch_id", "issue_type", "severity", "field_name", "observed_value",
    "expected_rule", "action_taken", "first_batch_id", "last_batch_id",
    "occurrence_count", "created_at", "resolution_note",
]


def connect(db: str):
    """Read-only connection."""
    env = load_env()
    conn = psycopg2.connect(
        host="127.0.0.1", port=int(env.get("DB_HOST_PORT", "55432")),
        dbname=db, user=env["POSTGRES_USER"], password=env["POSTGRES_PASSWORD"],
    )
    conn.set_session(readonly=True)
    return conn


def load(db: str) -> List[Dict[str, Any]]:
    """All quality-issue rows as dicts."""
    conn = connect(db)
    cur = conn.cursor()
    cur.execute(f"SELECT {', '.join(COLUMNS)} FROM data_quality_issue")
    rows = [dict(zip(COLUMNS, r)) for r in cur.fetchall()]
    conn.close()
    for row in rows:
        row["created_at"] = str(row["created_at"])
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="data_quality_issue 行级核验")
    parser.add_argument("--baseline", default="canvas_history")
    parser.add_argument("--after", default="canvas_history_p0_rehearsal")
    args = parser.parse_args()

    base = load(args.baseline)
    aft = load(args.after)
    base_by_fp = {r["issue_fingerprint"]: r for r in base}
    aft_by_fp = {r["issue_fingerprint"]: r for r in aft}

    print("=" * 84)
    print(f"data_quality_issue 行级核验：{args.baseline} → {args.after}")
    print("=" * 84)
    print(f"基线 {len(base):,} 行（唯一指纹 {len(base_by_fp):,}）；"
          f"导入后 {len(aft):,} 行（唯一指纹 {len(aft_by_fp):,}）")

    # ---------------------------------------------------------- 1. 原有行是否都在
    missing = [fp for fp in base_by_fp if fp not in aft_by_fp]
    print(f"\n原有行仍在：{len(base_by_fp) - len(missing):,} / {len(base_by_fp):,}；"
          f"丢失 {len(missing)}")

    # ---------------------------------------------------------- 2. 原有行字段是否被改
    changed: List[Dict[str, Any]] = []
    occ_changed = 0
    last_batch_changed = 0
    for fp, old in base_by_fp.items():
        new = aft_by_fp.get(fp)
        if new is None:
            continue
        diff_cols = [c for c in COLUMNS if c not in MUTABLE and old[c] != new[c]]
        if diff_cols:
            changed.append({"fingerprint": fp, "issue_id": old["issue_id"],
                            "columns": diff_cols,
                            "old": {c: old[c] for c in diff_cols},
                            "new": {c: new[c] for c in diff_cols}})
        if old["occurrence_count"] != new["occurrence_count"]:
            occ_changed += 1
        if old["last_batch_id"] != new["last_batch_id"]:
            last_batch_changed += 1
    print(f"原有行内容被改写（排除 {sorted(MUTABLE)}）：{len(changed)} 行")
    print(f"  occurrence_count 变化：{occ_changed:,} 行")
    print(f"  last_batch_id 变化：{last_batch_changed:,} 行")

    # ---------------------------------------------------------- 3. 新增行
    new_rows = [r for fp, r in aft_by_fp.items() if fp not in base_by_fp]
    print(f"\n新增行：{len(new_rows):,}")
    print(f"  按 first_batch_id：{dict(sorted(Counter(r['first_batch_id'] for r in new_rows).items()))}")
    print(f"  按 issue_type：{dict(sorted(Counter(r['issue_type'] for r in new_rows).items(), key=lambda kv: -kv[1]))}")
    print(f"  按 dataset_id：{dict(sorted(Counter(r['dataset_id'] for r in new_rows).items()))}")

    # 新增行里，是否存在"除了 dataset_id 之外与某条基线完全相同"的疑似重复
    sig = lambda r: (r["source_record_id"], r["place_id"], r["issue_type"],  # noqa: E731
                     r["field_name"], r["observed_value"])
    base_sig = defaultdict(list)
    for r in base:
        base_sig[sig(r)].append(r)
    dup_suspects = [r for r in new_rows if sig(r) in base_sig]
    print(f"  其中与既有行除 dataset_id 外完全相同的疑似重复：{len(dup_suspects)}")

    # ---------------------------------------------------------- 4. 197 条专项
    dvm_base = [r for r in base if r["issue_type"] == "derived_value_mismatch"]
    dvm_aft = [r for r in aft if r["issue_type"] == "derived_value_mismatch"]
    dvm_new = [r for r in dvm_aft if r["issue_fingerprint"] not in base_by_fp]
    print(f"\nderived_value_mismatch：基线 {len(dvm_base)} → 导入后 {len(dvm_aft)}；"
          f"新增 {len(dvm_new)}")
    by_ds = Counter(r["dataset_id"] for r in dvm_aft)
    print(f"  按数据集：{dict(by_ds)}")
    by_field = Counter(r["field_name"] for r in dvm_aft)
    print(f"  按字段：{dict(by_field)}")
    obs = Counter((r["observed_value"], r["resolution_note"]) for r in dvm_aft)
    print(f"  观察值/重算值组合：{len(obs)} 种")

    # ---------------------------------------------------------- 5. action_taken 改写
    mapped = [r for r in new_rows if r["resolution_note"]
              and "action_taken 原值=" in r["resolution_note"]]
    verbs = Counter()
    for r in mapped:
        note = r["resolution_note"]
        verb = note.split("action_taken 原值=")[1].split("（")[0]
        verbs[verb] += 1
    all_mapped_ok = all(r["action_taken"] == "preserved_and_flagged" for r in mapped)
    print(f"\naction_taken 越界映射行：{len(mapped):,}（原动词：{dict(verbs)}）")
    print(f"  全部落库为 preserved_and_flagged：{all_mapped_ok}")
    print(f"  原始动词全部保留在 resolution_note：{len(mapped) == sum(verbs.values())}")

    # ---------------------------------------------------------- CSV 明细
    OUT.mkdir(parents=True, exist_ok=True)
    diff_csv = OUT / "02_quality_issue_diff.csv"
    with io.open(diff_csv, "w", encoding="utf-8", newline="") as handle:
        fieldnames = ["kind", "issue_fingerprint", "issue_id", "dataset_id", "issue_type",
                      "field_name", "observed_value", "action_taken", "first_batch_id",
                      "last_batch_id", "occurrence_count", "detail"]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for fp in missing:
            r = base_by_fp[fp]
            writer.writerow({**{k: r.get(k) for k in fieldnames if k in r},
                             "kind": "baseline_missing", "detail": "基线行在导入后不存在"})
        for item in changed:
            r = base_by_fp[item["fingerprint"]]
            writer.writerow({**{k: r.get(k) for k in fieldnames if k in r},
                             "kind": "baseline_field_changed",
                             "detail": f"{item['columns']}: {item['old']} → {item['new']}"})
        for r in new_rows:
            writer.writerow({**{k: r.get(k) for k in fieldnames if k in r},
                             "kind": "new_row",
                             "detail": ("action_taken 原值=" +
                                        r["resolution_note"].split("action_taken 原值=")[1].split("（")[0])
                             if r in mapped else ""})
    print(f"\n明细 CSV → {diff_csv}（{len(missing) + len(changed) + len(new_rows):,} 行）")

    summary = {
        "baseline": {"db": args.baseline, "rows": len(base), "fingerprints": len(base_by_fp)},
        "after": {"db": args.after, "rows": len(aft), "fingerprints": len(aft_by_fp)},
        "baseline_present": len(base_by_fp) - len(missing),
        "baseline_missing": len(missing),
        "baseline_field_changed": len(changed),
        "occurrence_count_changed": occ_changed,
        "last_batch_id_changed": last_batch_changed,
        "new_rows": len(new_rows),
        "new_by_batch": dict(sorted(Counter(r["first_batch_id"] for r in new_rows).items())),
        "new_by_type": dict(sorted(Counter(r["issue_type"] for r in new_rows).items(),
                                   key=lambda kv: -kv[1])),
        "new_by_dataset": dict(sorted(Counter(r["dataset_id"] for r in new_rows).items())),
        "duplicate_suspects": len(dup_suspects),
        "derived_value_mismatch": {
            "baseline": len(dvm_base), "after": len(dvm_aft), "new": len(dvm_new),
            "by_dataset": dict(by_ds), "by_field": dict(by_field),
        },
        "action_taken_mapped": len(mapped),
        "action_taken_verbs": dict(verbs),
        "action_taken_all_preserved_and_flagged": all_mapped_ok,
        "changed_detail": changed[:50],
        "missing_detail": missing[:50],
    }
    with io.open(OUT / "02_quality_issue_audit.json", "w", encoding="utf-8", newline="\n") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)
    print(f"汇总 JSON → {OUT / '02_quality_issue_audit.json'}")
    return 0 if not missing and not changed else 1


if __name__ == "__main__":
    raise SystemExit(main())
