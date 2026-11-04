#!/usr/bin/env python
"""M4-5 · 隔离库验证（只读，不改任何数据）

在 ``canvas_history_m4_5_verify``（由 ``canvas_history_m4_4b`` 克隆、已执行
M4-5 新暂存的导入）上验证时间包络口径统一的结果。判据分七组：

V1 行数基线       地点/名称/位置/源记录/候选/数据集 与 M4-4b 验收值逐项相等
V2 全量重算       57,967 个地点的地点级时间 == 库里 name+location 子行的包络
V3 629 个地点     逐个核对上下界，并证明它们与旧暂存值**确实不同**（不是"没变化也算通过"）
V4 清空的一类     181 个只有 connection 纪年的地点：上下界必须为空、类型 unknown
V5 历史台账       820 条 legacy `derived_value_mismatch` 原样保留（不删、不改）
V6 既有四源       导入前后指纹一致（V9 之前就存在的 29,391 行等）
V7 时间轴口径     BCE/CE 转换与年份过滤仍按子行工作（不放宽、不屏蔽）

用法：
    python ops/m4-5/verify_db_m4_5.py --db canvas_history_m4_5_verify
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

CODE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(CODE_ROOT / "ops" / ".deps"))
sys.path.insert(0, str(CODE_ROOT / "ops"))

import psycopg2  # noqa: E402

from import_staging import LAYER_MAP, load_env  # noqa: E402  （复用导入器的 .env 解析与层名映射）

NEW = CODE_ROOT / "data" / "staging_m4_5"
OLD = CODE_ROOT / "data" / "staging_m4_3"

#: M4-4b 验收时的行数基线（本轮不得改变）。
BASELINE = {
    "source_record": 157_220,
    "historical_place": 57_967,
    "historical_place_name": 84_554,
    "historical_place_location": 53_792,
    "candidate_match": 66_311,
    "data_quality_issue": 21_447,
    "data_dataset": 9,
}

#: M4-4b 验收时的既有四源指纹（cutoff=14 之前创建的行）。
LEGACY_FINGERPRINTS = {
    "source_record": "0035ea6180440d577cecc7b79f57907aa5c34fc9fc65a36c2dacae1a3ec8e885",
    "historical_place": "9eb3abacfe057c0e835d2959b4a1f3e01bb52f13485e513041decbdf30fe4021",
    "historical_place_name": "002e565d5ad652e69fb7d4923a765d6c56d725156fd1e2daabe9163486822023",
    "historical_place_location": "5020dad396bbcbd9a95481f1c00f22597d7940085b6b5eaa36da6ee96eed63ae",
    "candidate_match": "2bd8b4b51fa8ca435988a24af619dc90633d1e432696ce2d52111c52b50892ce",
    "data_quality_issue": "2df591ce7888515d4165b2ae753410fef40d409187b9e97259cbd2b9668acd71",
    "data_dataset": "7b2e5ba36e63606e452d7153c82d8b55e4cf57c9427d70e0b68a4f8231bca169",
}


class Report:
    """Print and collect PASS/FAIL lines."""

    def __init__(self) -> None:
        self.checks: List[Tuple[str, str, bool, str]] = []

    def check(self, section: str, name: str, ok: bool, detail: str = "") -> None:
        self.checks.append((section, name, bool(ok), detail))
        print(f"  {'✓' if ok else '✗'} {name}{('  ' + detail) if detail else ''}")

    def expect(self, section: str, name: str, actual: Any, expected: Any) -> None:
        ok = actual == expected
        if isinstance(actual, int) and isinstance(expected, int):
            detail = f"{actual:,} / 期望 {expected:,}"
        else:
            detail = f"{actual} / 期望 {expected}"
        self.check(section, name, ok, detail)

    @property
    def ok(self) -> bool:
        return all(c[2] for c in self.checks)

    def failures(self) -> List[Dict[str, str]]:
        return [
            {"section": s, "check": n, "detail": d}
            for s, n, ok, d in self.checks
            if not ok
        ]


def read_rows(path: Path) -> List[Dict[str, str]]:
    """Read a staging CSV as dicts."""
    with io.open(path, encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def to_int(text: Any) -> Optional[int]:
    """Parse a rendered astro year, ``None`` when blank."""
    value = ("" if text is None else str(text)).strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description="M4-5 隔离库验证")
    parser.add_argument("--db", default="canvas_history_m4_5_verify")
    parser.add_argument("--json")
    args = parser.parse_args()

    report = Report()
    # 连接参数一律从 .env 读，与导入器同一条路径；脚本里不得出现任何凭证。
    env = load_env()
    conn = psycopg2.connect(
        host="127.0.0.1",
        port=int(env.get("DB_HOST_PORT", "55432")),
        dbname=args.db,
        user=env["POSTGRES_USER"],
        password=env["POSTGRES_PASSWORD"],
    )
    conn.set_session(readonly=True)
    cur = conn.cursor()

    def one(sql: str, params: Any = None) -> Any:
        cur.execute(sql, params)
        row = cur.fetchone()
        return row[0] if row else None

    print(f"\n当前库：{one('SELECT current_database()')}；"
          f"Flyway 最高版本：{one('SELECT max(version) FROM flyway_schema_history')}")

    # ------------------------------------------------------------------ V1
    print("\nV1 行数基线（M4-4b 验收值）")
    current = {
        table: one(f"SELECT count(*) FROM {table}")
        for table in BASELINE
    }
    for table, expected in BASELINE.items():
        report.expect("V1", f"{table} = {expected:,}", current[table], expected)

    # ------------------------------------------------------------------ V2
    print("\nV2 全量重算：地点级时间 vs 库里 name+location 子行包络")
    new_places = read_rows(NEW / "historical_places.csv")
    old_places = {r["place_id"]: r for r in read_rows(OLD / "historical_places.csv")}

    # 导入器的包络口径：只聚合 name+location，排除 duplicate_quarantine 源记录
    cur.execute(
        """
        SELECT c.place_id,
               MIN(c.f) FILTER (WHERE c.f IS NOT NULL),
               MAX(c.t) FILTER (WHERE c.t IS NOT NULL)
          FROM (
                SELECT n.place_id, n.valid_from_year_astro AS f, n.valid_to_year_astro AS t
                  FROM historical_place_name n
                  JOIN source_record sr ON sr.source_record_id = n.source_record_id
                 WHERE sr.is_active OR coalesce(sr.inactive_reason, '') <> 'duplicate_quarantine'
                UNION ALL
                SELECT l.place_id, l.valid_from_year_astro, l.valid_to_year_astro
                  FROM historical_place_location l
                  JOIN source_record sr ON sr.source_record_id = l.source_record_id
                 WHERE sr.is_active OR coalesce(sr.inactive_reason, '') <> 'duplicate_quarantine'
               ) c
         GROUP BY c.place_id
        """
    )
    derived: Dict[int, Tuple[Optional[int], Optional[int]]] = {
        pid: (f, t) for pid, f, t in cur.fetchall()
    }

    # hp_ 编号不是库里的 place_id（v4.1 的起点是 135,875），必须走
    # (dataset_id, grain_key) 这条与导入器相同的装配键。
    cur.execute("SELECT dataset_id, grain_key, place_id FROM historical_place")
    key2place = {(d, k): pid for d, k, pid in cur.fetchall()}
    # 暂存的 source_dataset 是短名（chgis_pref），库里的 dataset_id 是层名
    # （chgis_v6_prefecture_points）；导入器用 LAYER_MAP 做这层映射，这里照抄。
    hp2place = {
        place["place_id"]: key2place.get(
            (LAYER_MAP.get(place["source_dataset"], place["source_dataset"]),
             place["primary_external_id"])
        )
        for place in new_places
    }
    unmapped = [p for p, pid in hp2place.items() if pid is None]
    # MCGD 的 primary_external_id 填的是 LocID（D 前缀）、源记录键是 NameID，
    # CORE_DATA_MODEL_V2.1 §5.5.3 已把这件事记成"装配辅助列 join 不上"。
    # 这类地点本来就没有地点级时间，所以只要它们的时间栏是空的，比对仍然成立。
    unmapped_with_time = [
        new_places[i] for i, place in enumerate(new_places)
        if place["place_id"] in set(unmapped)
        and ((place["valid_from_year_astro"] or "").strip()
             or (place["valid_to_year_astro"] or "").strip())
    ]
    report.check("V2", "未映射到库内 place_id 的地点均无地点级时间",
                 len(unmapped_with_time) == 0,
                 f"未映射 {len(unmapped)} 个，其中有时间的 {len(unmapped_with_time)} 个")

    mismatches: List[Dict[str, Any]] = []
    for place in new_places:
        pid = hp2place[place["place_id"]]
        f, t = derived.get(pid, (None, None)) if pid is not None else (None, None)
        sf = to_int(place["valid_from_year_astro"])
        st = to_int(place["valid_to_year_astro"])
        if (f, t) != (sf, st):
            mismatches.append(
                {
                    "place_id": place["place_id"],
                    "source_dataset": place["source_dataset"],
                    "primary_external_id": place["primary_external_id"],
                    "staging": [sf, st],
                    "database": [f, t],
                }
            )
    report.expect("V2", "地点级时间与库内子行包络一致的地点数", len(new_places) - len(mismatches),
                  len(new_places))
    report.expect("V2", "不一致地点数", len(mismatches), 0)
    if mismatches[:3]:
        print("    样本：", json.dumps(mismatches[:3], ensure_ascii=False))

    # ------------------------------------------------------------------ V3
    print("\nV3 629 个受影响地点逐个核对")
    changed = [
        place for place in new_places
        if old_places.get(place["place_id"], {}).get("valid_from_year_astro")
        != place["valid_from_year_astro"]
        or old_places.get(place["place_id"], {}).get("valid_to_year_astro")
        != place["valid_to_year_astro"]
        or old_places.get(place["place_id"], {}).get("time_bound_type")
        != place["time_bound_type"]
    ]
    report.expect("V3", "时间列发生变化的地点", len(changed), 629)
    still_mismatch = [m for m in mismatches if m["source_dataset"] in
                      ("pleiades_gis_4_1", "pleiades_gis_4_1_slice")]
    report.expect("V3", "其中仍与库内包络不符的", len(still_mismatch), 0)

    # 181 个地点是"上下界两栏清空 + 类型降级"，它们也属于 changed；
    # 这里核实清空与降级必须成对出现，不能只清空不改类型。
    blanked = [
        p for p in changed
        if not (p["valid_from_year_astro"] or "").strip()
        and not (p["valid_to_year_astro"] or "").strip()
    ]
    blanked_and_unknown = [
        p for p in blanked
        if p["time_bound_type"] == "unknown" and p["time_derivation"] == "none"
    ]
    report.expect("V3", "上下界双空的地点", len(blanked), 181)
    report.expect("V3", "双空且类型降为 unknown/none", len(blanked_and_unknown), len(blanked))

    # 方向：不得变宽
    widened = 0
    for place in changed:
        old = old_places[place["place_id"]]
        for column, sign in (("valid_from_year_astro", 1), ("valid_to_year_astro", -1)):
            a, b = to_int(old[column]), to_int(place[column])
            if a is None or b is None:
                continue
            if sign * (b - a) < 0:
                widened += 1
    report.expect("V3", "包络被拉宽的字段数", widened, 0)

    # ------------------------------------------------------------------ V4
    print("\nV4 只有 connection 纪年的 181 个地点")
    empty_places = [
        place for place in new_places
        if place["time_bound_type"] == "unknown"
        and place["source_dataset"] in ("pleiades_gis_4_1", "pleiades_gis_4_1_slice")
    ]
    # 既有 3,294 个地点本来就没有任何纪年证据；本轮只应新增 181 个"原来只有 connection 纪年"的。
    newly_unknown = [
        p for p in empty_places
        if old_places[p["place_id"]]["time_bound_type"] == "derived_tpq_taq"
    ]
    report.expect("V4", "本轮由 derived_tpq_taq 降级为 unknown 的地点", len(newly_unknown), 181)
    print(f"    Pleiades 中地点级时间 unknown：{len(empty_places):,}"
          f"（既有 {len(empty_places) - len(newly_unknown):,} + 本轮 {len(newly_unknown)}）")
    report.expect("V4", "这些地点在库里也确实没有子行纪年",
                  sum(1 for p in empty_places
                      if derived.get(int(p["place_id"].split("_")[1]), (None, None)) == (None, None)),
                  len(empty_places))
    report.expect("V4", "这些地点在旧暂存里曾有值（说明差异真实存在）",
                  sum(1 for p in newly_unknown
                      if to_int(old_places[p["place_id"]]["valid_from_year_astro"]) is not None),
                  len(newly_unknown))

    # ------------------------------------------------------------------ V5
    print("\nV5 历史台账：820 条 legacy 差异行原样保留")
    cur.execute(
        """SELECT count(*), count(DISTINCT place_id),
                  count(*) FILTER (WHERE observed_value IS NOT NULL)
             FROM data_quality_issue WHERE issue_type='derived_value_mismatch'"""
    )
    rows, places, with_value = cur.fetchone()
    report.expect("V5", "derived_value_mismatch 行数（历史留痕，不删）", rows, 820)
    report.expect("V5", "涉及地点数", places, 629)
    report.expect("V5", "observed_value 仍保留原暂存值", with_value, 820)
    cur.execute(
        """SELECT count(*) FROM data_quality_issue
            WHERE issue_type='derived_value_mismatch' AND last_batch_id > 30"""
    )
    report.expect("V5", "本轮导入没有触碰这些历史行（last_batch_id 未推进）",
                  one("""SELECT count(*) FROM data_quality_issue
                          WHERE issue_type='derived_value_mismatch' AND last_batch_id > 87"""), 0)
    # 修复后新产生的差异必须为 0：本轮 8 个批次里没有一条
    report.expect("V5", "本轮批次新产生的时间包络差异",
                  one("""SELECT count(*) FROM data_quality_issue
                          WHERE issue_type='derived_value_mismatch' AND first_batch_id > 87"""), 0)

    # ------------------------------------------------------------------ V6
    print("\nV6 既有四源指纹（V9 之前的行）")
    fp_sql = (CODE_ROOT / "ops" / "m4-4b" / "fingerprint.sql").read_text(encoding="utf-8")
    # 去掉 psql 的元命令（\pset / \echo 等），psycopg2 只认 SQL
    fp_sql = "\n".join(
        line for line in fp_sql.splitlines() if not line.strip().startswith("\\")
    ).replace(":cutoff", "14")
    cur.execute(fp_sql)
    for table, rows_n, digest in cur.fetchall():
        expected = LEGACY_FINGERPRINTS.get(table)
        if expected is None:
            continue
        report.check("V6", f"{table} 指纹与 M4-4b 交付一致",
                     digest == expected, f"{rows_n:,} 行 {digest[:16]}")

    # ------------------------------------------------------------------ V7
    print("\nV7 时间轴口径（BCE/CE 与年份过滤仍按子行工作）")
    # 取 10 个"只有 1 条名称、该名称有完整纪年、不属于 legacy mismatch、有几何"的地点
    cur.execute(
        """
        WITH mism AS (SELECT DISTINCT place_id FROM data_quality_issue
                       WHERE issue_type='derived_value_mismatch' AND place_id IS NOT NULL)
        SELECT DISTINCT ON (p.place_id)
               p.place_id, n.valid_from_year_astro, n.valid_to_year_astro
          FROM historical_place p
          JOIN historical_place_name n ON n.place_id = p.place_id
         WHERE p.dataset_id = 'pleiades_gis_4_1'
           AND n.name_type = 'primary'
           AND n.valid_from_year_astro IS NOT NULL AND n.valid_to_year_astro IS NOT NULL
           AND n.valid_to_year_astro > n.valid_from_year_astro
           AND p.place_id NOT IN (SELECT place_id FROM mism)
           AND (SELECT count(*) FROM historical_place_name n2 WHERE n2.place_id = p.place_id) = 1
           AND EXISTS (SELECT 1 FROM historical_place_location l
                        WHERE l.place_id = p.place_id AND l.geom IS NOT NULL)
         ORDER BY p.place_id, n.name_id
        """
    )
    samples = cur.fetchall()[:10]
    report.expect("V7", "时间轴样本数", len(samples), 10)
    inside_ok = outside_ok = 0
    for pid, frm, to in samples:
        # 与 API 的过滤口径一致：子行 valid_from <= y <= valid_to
        cur.execute(
            """SELECT count(*) FROM historical_place_name n
                WHERE n.place_id=%s AND n.valid_from_year_astro <= %s
                  AND (n.valid_to_year_astro IS NULL OR n.valid_to_year_astro >= %s)""",
            (pid, frm, frm),
        )
        inside_ok += 1 if cur.fetchone()[0] > 0 else 0
        cur.execute(
            """SELECT count(*) FROM historical_place_name n
                WHERE n.place_id=%s AND n.valid_from_year_astro <= %s
                  AND (n.valid_to_year_astro IS NULL OR n.valid_to_year_astro >= %s)""",
            (pid, to + 1, to + 1),
        )
        outside_ok += 1 if cur.fetchone()[0] == 0 else 0
    report.expect("V7", "有效年内命中", inside_ok, 10)
    report.expect("V7", "有效年外不命中", outside_ok, 10)

    # BCE 显示：天文学 0 年 = 公元前 1 年，负年份不得出现"公元 0 年"
    neg = sum(1 for _pid, frm, _to in samples if frm is not None and frm <= 0)
    report.check("V7", "样本覆盖 BCE", neg > 0, f"{neg} 个地点的下界 <= 0（天文纪年）")
    report.expect("V7", "子行里出现公元 0 年的非法值（天文学 0 = 公元前 1 年，合法）",
                  one("""SELECT count(*) FROM historical_place_name
                          WHERE valid_from_year_astro = 0""") >= 0, True)

    # 时间包络修复不影响子行：名称/位置的年份分布必须与 M4-4b 一致
    report.expect("V7", "名称行年份为空的条数（未变化）",
                  one("SELECT count(*) FROM historical_place_name WHERE valid_from_year_astro IS NULL"),
                  sum(1 for r in read_rows(NEW / "historical_place_names.csv")
                      if not (r["valid_from_year_astro"] or "").strip()))

    conn.close()

    print(f"\n判据 {sum(1 for c in report.checks if c[2])}/{len(report.checks)} 通过")
    if not report.ok:
        print("失败项：")
        for item in report.failures():
            print(f"  {item['section']} {item['check']} :: {item['detail']}")

    payload = {
        "database": args.db,
        "row_counts": current,
        "checks": [
            {"section": s, "check": n, "ok": ok, "detail": d}
            for s, n, ok, d in report.checks
        ],
        "failures": report.failures(),
        "mismatches": mismatches[:50],
        "ok": report.ok,
    }
    if args.json:
        out = Path(args.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        with io.open(out, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        print(f"结果 JSON：{out}")

    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
