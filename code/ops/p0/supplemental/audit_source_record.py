#!/usr/bin/env python
"""P0 补充审计 · source_record 指纹口径与逐字段核验（只读）

要回答的问题：
  1. 原有 29,391 条是否全部保留？
  2. 日志说 29,388 条"更新了 last_batch_id"，究竟改了哪些字段？
  3. 现有 SHA256 不变证明了什么？"逐字节不变"这个说法准不准？

做法：把基线库（正式库 `canvas_history`，未被修改）与演练库（`canvas_history_p0_rehearsal`）
的 29,391 条原有行按 `source_record_id` 一一对齐，**逐列**比较 16 个字段。

同时算三种指纹，把"变了/没变"讲清楚：
  A. 整行指纹（包含 last_batch_id）        —— 会被导入维护动作打破
  B. 业务内容指纹（排除 last_batch_id）    —— 这才是"数据没变"的证据
  C. 核心内容指纹（再排除 content_hash 之外的维护列）—— 与 B 相同，表上无其他维护列

用法：
    python ops/p0/supplemental/audit_source_record.py
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

CODE_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(CODE_ROOT / "ops" / ".deps"))
sys.path.insert(0, str(CODE_ROOT / "ops"))

import psycopg2  # noqa: E402

from import_staging import load_env  # noqa: E402

OUT = CODE_ROOT / "ops" / "reports" / "p0" / "supplemental_audit"

COLUMNS = [
    "source_record_id", "dataset_id", "record_scope", "external_id",
    "parent_external_id", "duplicate_ordinal", "raw_file", "raw_record_index",
    "raw_payload", "content_hash", "first_batch_id", "last_batch_id",
    "is_active", "inactive_reason", "inactive_at", "inactive_in_batch_id",
    "ingested_at",
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


def normalize(value: Any) -> Any:
    """Make a column value comparable across databases."""
    if isinstance(value, memoryview):
        return bytes(value).hex()
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).hex()
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value


def load(db: str, only_before: str = "pleiades_gis_4_1") -> List[Dict[str, Any]]:
    """Load the *pre-existing* rows (everything except the new dataset)."""
    conn = connect(db)
    cur = conn.cursor()
    cur.execute(
        f"SELECT {', '.join(COLUMNS)} FROM source_record WHERE dataset_id <> %s "
        f"ORDER BY source_record_id", (only_before,)
    )
    rows = [dict(zip(COLUMNS, r)) for r in cur.fetchall()]
    conn.close()
    for row in rows:
        for key in row:
            row[key] = normalize(row[key])
        for key in ("inactive_at", "ingested_at"):
            if row[key] is not None:
                row[key] = str(row[key])
    return rows


def fingerprint(rows: List[Dict[str, Any]], drop: tuple = ()) -> str:
    """Ordered SHA256 over the selected columns."""
    cols = [c for c in COLUMNS if c not in drop]
    h = hashlib.sha256()
    for row in rows:
        h.update(("|".join(str(row[c]) for c in cols) + "\n").encode("utf-8"))
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="source_record 逐字段核验")
    parser.add_argument("--baseline", default="canvas_history")
    parser.add_argument("--after", default="canvas_history_p0_rehearsal")
    args = parser.parse_args()

    base = load(args.baseline)
    aft = load(args.after)
    base_by_id = {r["source_record_id"]: r for r in base}
    aft_by_id = {r["source_record_id"]: r for r in aft}

    print("=" * 84)
    print(f"source_record 逐字段核验：{args.baseline} → {args.after}")
    print("=" * 84)
    print(f"基线原有行 {len(base):,}；导入后原有行 {len(aft):,}")
    print(f"编号区间：{min(base_by_id)}–{max(base_by_id)} / {min(aft_by_id) if aft_by_id else '-'}–{max(aft_by_id) if aft_by_id else '-'}")

    missing = [i for i in base_by_id if i not in aft_by_id]
    extra = [i for i in aft_by_id if i not in base_by_id]
    print(f"缺失 {len(missing)}；多出 {len(extra)}")

    col_changes: Counter = Counter()
    changed_rows: List[Dict[str, Any]] = []
    for sid, old in base_by_id.items():
        new = aft_by_id.get(sid)
        if new is None:
            continue
        diff = [c for c in COLUMNS if old[c] != new[c]]
        if diff:
            for c in diff:
                col_changes[c] += 1
            changed_rows.append({"source_record_id": sid, "columns": diff,
                                 "old": {c: old[c] for c in diff},
                                 "new": {c: new[c] for c in diff}})
    print(f"\n发生变化的行：{len(changed_rows):,} / {len(base):,}")
    print(f"按列统计：{dict(col_changes)}")

    # 三种指纹
    fp_full_base = fingerprint(base)
    fp_full_aft = fingerprint(aft)
    fp_biz_base = fingerprint(base, drop=("last_batch_id",))
    fp_biz_aft = fingerprint(aft, drop=("last_batch_id",))
    print("\n指纹：")
    print(f"  A 整行（含 last_batch_id）：基线 {fp_full_base[:16]}…  导入后 {fp_full_aft[:16]}…  "
          f"{'相同' if fp_full_base == fp_full_aft else '不同'}")
    print(f"  B 业务内容（不含 last_batch_id）：基线 {fp_biz_base[:16]}…  导入后 {fp_biz_aft[:16]}…  "
          f"{'相同' if fp_biz_base == fp_biz_aft else '不同'}")

    # last_batch_id 的具体走向
    lb = Counter((r["old"].get("last_batch_id"), r["new"].get("last_batch_id"))
                 for r in changed_rows if r["columns"] == ["last_batch_id"])
    print(f"\n仅 last_batch_id 变化的行：{sum(lb.values()):,}")
    print(f"  取值迁移（前 6 组）：{dict(list(sorted(lb.items(), key=lambda kv: -kv[1]))[:6])}")
    others = [r for r in changed_rows if r["columns"] != ["last_batch_id"]]
    print(f"除 last_batch_id 外还有其他列变化的行：{len(others)}")
    for r in others[:5]:
        print(f"  {r['source_record_id']} {r['columns']} {r['old']} → {r['new']}")

    # 3 条"隔离记录保持不变"是哪 3 条
    unchanged = [sid for sid in base_by_id
                 if sid in aft_by_id and not any(base_by_id[sid][c] != aft_by_id[sid][c] for c in COLUMNS)]
    print(f"\n完全未变的行：{len(unchanged)} → {unchanged[:6]}")
    if unchanged:
        conn = connect(args.after)
        cur = conn.cursor()
        cur.execute(
            "SELECT source_record_id, dataset_id, record_scope, external_id, is_active, inactive_reason "
            "FROM source_record WHERE source_record_id = ANY(%s) ORDER BY 1", (unchanged,))
        for row in cur.fetchall():
            print(f"    {row[0]} {row[1]} / {row[2]} / {row[3]} active={row[4]} reason={row[5]}")
        conn.close()

    # CSV
    OUT.mkdir(parents=True, exist_ok=True)
    out_csv = OUT / "04_source_record_diff.csv"
    with io.open(out_csv, "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["source_record_id", "changed_columns", "column",
                         "before", "after"])
        for item in changed_rows:
            for c in item["columns"]:
                writer.writerow([item["source_record_id"], ",".join(item["columns"]),
                                 c, item["old"][c], item["new"][c]])
    print(f"\n明细 CSV → {out_csv}（{sum(len(r['columns']) for r in changed_rows):,} 行）")

    summary = {
        "baseline_rows": len(base),
        "after_rows": len(aft),
        "missing": len(missing),
        "extra": len(extra),
        "changed_rows": len(changed_rows),
        "column_changes": dict(col_changes),
        "unchanged_rows": len(unchanged),
        "unchanged_ids": unchanged,
        "fingerprint_full_before": fp_full_base,
        "fingerprint_full_after": fp_full_aft,
        "fingerprint_business_before": fp_biz_base,
        "fingerprint_business_after": fp_biz_aft,
        "last_batch_transitions": {f"{k[0]}->{k[1]}": v for k, v in
                                   sorted(lb.items(), key=lambda kv: -kv[1])[:10]},
        "rows_with_other_changes": len(others),
        "other_change_detail": others[:20],
    }
    with io.open(OUT / "04_source_record_audit.json", "w", encoding="utf-8", newline="\n") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)
    print(f"汇总 JSON → {OUT / '04_source_record_audit.json'}")
    return 0 if not missing and not others else 1


if __name__ == "__main__":
    raise SystemExit(main())
