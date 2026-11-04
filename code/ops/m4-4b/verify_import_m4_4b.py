#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""M4-4b 数据库验收：逐条核对导入后的隔离库。

只读。所有判据分两类，报告里必须分开：
  · **从 staging 反查数据库**（"暂存里的 X 是否都落库了"）—— 证明没有丢行；
  · **从数据库正查**（"库里的 X 是否符合业务规则"）—— 证明没有写坏。

用法：
    cd code
    PYTHONPATH=ops/.deps python ops/m4-4b/verify_import_m4_4b.py \
        --db canvas_history_m4_4b --json ops/reports/m4-4b/verify_m4_4b.json

退出码：0 全部通过；1 有失败项。
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

CODE_ROOT = Path(__file__).resolve().parents[2]
STAGING = CODE_ROOT / "data" / "staging_m4_3"
GIS = CODE_ROOT / "data" / "raw" / "pleiades_gis_4_1" / "gis"
sys.path.insert(0, str(CODE_ROOT / "ops"))

P4 = "pleiades_gis_4_1"
SLICE = "pleiades_gis_4_1_slice"

#: 施工指令 §七 的预期值。
EXPECT = {
    "new_places": 38_928,
    "new_names": 37_055,
    "new_locations": 35_691,
    "new_source_records": 127_829,
    "source_records_total": 157_220,
    "superseded": 2_552,
    "point": 26_684,
    "polygon": 4_112,
    "multipolygon": 2,
    "linestring": 4_893,
    "geometry_total": 35_691,
    "loc_precise": 31_223,
    "loc_rough": 4_468,
    "place_precise": 27_418,
    "place_rough": 11_510,
    "candidate_total": 66_311,
    "candidate_delta": 13_180,
    "pairs_4_1": 13_553,
    "repaired": 4,
    "no_geometry_places": 7_200,
    "staging_issues": 7_960,
}


class Report:
    def __init__(self) -> None:
        self.items: List[Dict[str, Any]] = []

    def check(self, section: str, name: str, ok: bool, detail: str = "") -> bool:
        self.items.append({"section": section, "name": name, "ok": bool(ok), "detail": detail})
        print(f"  {'✓' if ok else '✗'} [{section}] {name}" + (f"  — {detail}" if detail else ""))
        return ok

    def expect(self, section: str, name: str, actual: Any, expected: Any) -> bool:
        return self.check(section, name, actual == expected, f"实际={actual} 期望={expected}")

    @property
    def ok(self) -> bool:
        return all(i["ok"] for i in self.items)

    @property
    def failures(self) -> List[Dict[str, Any]]:
        return [i for i in self.items if not i["ok"]]


def read_rows(path: Path) -> Iterable[Dict[str, str]]:
    with io.open(path, encoding="utf-8-sig", newline="") as handle:
        yield from csv.DictReader(handle)


def ti(text: str) -> Optional[int]:
    value = (text or "").strip()
    return int(value) if value else None


def tf(text: str) -> Optional[float]:
    value = (text or "").strip()
    return float(value) if value else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    parser.add_argument("--json", default="")
    args = parser.parse_args()

    import psycopg2  # noqa: PLC0415
    import import_staging as importer  # noqa: PLC0415

    env = importer.load_env()
    conn = psycopg2.connect(host="127.0.0.1", port=int(env.get("DB_HOST_PORT", "15432")),
                            dbname=args.db, user=env["POSTGRES_USER"],
                            password=env["POSTGRES_PASSWORD"])
    conn.set_session(readonly=True, autocommit=True)
    cur = conn.cursor()
    report = Report()

    def one(sql: str, params: Tuple = ()) -> Any:
        cur.execute(sql, params)
        return cur.fetchone()[0]

    print(f"M4-4b 数据库验收：{args.db}")
    print()

    # ================================================================= V1
    print("V1 库身份与 Migration 版本")
    report.expect("V1", "当前库", one("SELECT current_database()"), args.db)
    report.expect("V1", "Flyway 最高版本", one("SELECT max(version) FROM flyway_schema_history"), "9")
    report.expect("V1", "V9 成功", one(
        "SELECT success FROM flyway_schema_history WHERE version='9'"), True)
    report.expect("V1", "V1–V8 全部成功", one(
        "SELECT count(*) FROM flyway_schema_history WHERE success IS NOT TRUE OR version IS NULL"), 0)

    # ================================================================= V2
    print("\nV2 行数总账（导入前 → 导入后）")
    totals = {
        "source_record": one("SELECT count(*) FROM source_record"),
        "historical_place": one("SELECT count(*) FROM historical_place"),
        "historical_place_name": one("SELECT count(*) FROM historical_place_name"),
        "historical_place_location": one("SELECT count(*) FROM historical_place_location"),
        "candidate_match": one("SELECT count(*) FROM candidate_match"),
        "data_quality_issue": one("SELECT count(*) FROM data_quality_issue"),
        "data_dataset": one("SELECT count(*) FROM data_dataset"),
    }
    report.expect("V2", "source_record", totals["source_record"], EXPECT["source_records_total"])
    report.expect("V2", "historical_place", totals["historical_place"], 19_039 + EXPECT["new_places"])
    report.expect("V2", "historical_place_name", totals["historical_place_name"],
                  47_499 + EXPECT["new_names"])
    report.expect("V2", "historical_place_location",
                  totals["historical_place_location"], 18_101 + EXPECT["new_locations"])
    report.expect("V2", "candidate_match", totals["candidate_match"], EXPECT["candidate_total"])
    report.expect("V2", "data_dataset（8 + 新数据集；manual_entry 属 V5）",
                  totals["data_dataset"], 9)
    print(f"    合计：{totals}")

    # ================================================================= V3
    print("\nV3 新数据集与来源记录")
    report.expect("V3", "pleiades_gis_4_1 已登记",
                  one("SELECT count(*) FROM data_dataset WHERE dataset_id=%s", (P4,)), 1)
    report.expect("V3", "dataset.record_count",
                  one("SELECT record_count FROM data_dataset WHERE dataset_id=%s", (P4,)),
                  EXPECT["new_source_records"])
    cur.execute("SELECT dataset_id, count(*) FROM source_record GROUP BY 1 ORDER BY 1")
    ds_counts = dict(cur.fetchall())
    report.expect("V3", "v4.1 源记录", ds_counts.get(P4, 0), EXPECT["new_source_records"])
    report.expect("V3", "切片源记录未变", ds_counts.get(SLICE, 0), 12_445)
    print(f"    各数据集源记录：{ds_counts}")
    scope_counts = {}
    cur.execute("SELECT record_scope, count(*) FROM source_record WHERE dataset_id=%s GROUP BY 1", (P4,))
    scope_counts = dict(cur.fetchall())
    report.expect("V3", "v4.1 record_scope 分布",
                  scope_counts,
                  {"place": 41_480, "name": 37_055, "location": 35_691, "edge": 13_603})

    # ================================================================= V4
    print("\nV4 重叠地点（2,552 inactive）")
    report.expect("V4", "inactive_reason=superseded_by_newer_snapshot",
                  one("SELECT count(*) FROM source_record WHERE inactive_reason=%s",
                      ("superseded_by_newer_snapshot",)), EXPECT["superseded"])
    report.expect("V4", "这些行 is_active=false",
                  one("SELECT count(*) FROM source_record WHERE inactive_reason=%s AND is_active",
                      ("superseded_by_newer_snapshot",)), 0)
    report.expect("V4", "这些行 duplicate_ordinal=0",
                  one("SELECT count(*) FROM source_record WHERE inactive_reason=%s"
                      " AND duplicate_ordinal<>0", ("superseded_by_newer_snapshot",)), 0)
    report.expect("V4", "inactive_at / inactive_in_batch_id 均非空",
                  one("SELECT count(*) FROM source_record WHERE inactive_reason=%s"
                      " AND (inactive_at IS NULL OR inactive_in_batch_id IS NULL)",
                      ("superseded_by_newer_snapshot",)), 0)
    # 没有重复地点：同一 (grain_key) 只出现一次由 uq_c04 保证，这里核对"重叠集合没有建点"
    report.expect("V4", "v4.1 地点数 = 38,928（重叠未建点）",
                  one("SELECT count(*) FROM historical_place WHERE dataset_id=%s", (P4,)),
                  EXPECT["new_places"])
    report.expect("V4", "重叠地点的 grain_key 只由切片承载（v4.1 侧无对应 place）",
                  one("""
                      SELECT count(*) FROM source_record sr
                       WHERE sr.dataset_id=%s AND sr.record_scope='place'
                         AND sr.inactive_reason='superseded_by_newer_snapshot'
                         AND EXISTS (SELECT 1 FROM historical_place p
                                      WHERE p.dataset_id=%s AND p.grain_key=sr.external_id)
                      """, (P4, P4)), 0)

    # ================================================================= V5
    print("\nV5 几何")
    geom = {}
    cur.execute("SELECT geom_type, count(*) FROM historical_place_location"
                " WHERE place_id IN (SELECT place_id FROM historical_place WHERE dataset_id=%s)"
                " GROUP BY 1", (P4,))
    geom = {k: v for k, v in cur.fetchall()}
    report.expect("V5", "Point", geom.get("Point", 0), EXPECT["point"])
    report.expect("V5", "Polygon", geom.get("Polygon", 0), EXPECT["polygon"])
    report.expect("V5", "MultiPolygon", geom.get("MultiPolygon", 0), EXPECT["multipolygon"])
    report.expect("V5", "LineString", geom.get("LineString", 0), EXPECT["linestring"])
    report.expect("V5", "v4.1 位置合计", sum(geom.values()), EXPECT["geometry_total"])
    report.expect("V5", "全部几何 ST_IsValid",
                  one("SELECT count(*) FROM historical_place_location WHERE geom IS NOT NULL"
                      " AND NOT ST_IsValid(geom)"), 0)
    report.expect("V5", "geom_type 与真实类型一致",
                  one("SELECT count(*) FROM historical_place_location WHERE geom IS NOT NULL"
                      " AND ST_GeometryType(geom) <> 'ST_' || geom_type"), 0)
    report.expect("V5", "面/线缺代表点",
                  one("SELECT count(*) FROM historical_place_location WHERE geom_type IN"
                      " ('Polygon','MultiPolygon','LineString')"
                      " AND (representative_lon IS NULL OR representative_lat IS NULL)"), 0)
    report.expect("V5", "SRID 全为 4326",
                  one("SELECT count(*) FROM historical_place_location WHERE geom IS NOT NULL"
                      " AND ST_SRID(geom) <> 4326"), 0)
    # 修复的 4 条：geom 有效 + 有台账
    report.expect("V5", "修复台账 4 条",
                  one("SELECT count(*) FROM data_quality_issue WHERE issue_type='geometry_invalid_repaired'"),
                  EXPECT["repaired"])
    report.expect("V5", "4 条修复行的几何全部有效",
                  one("""SELECT count(*) FROM data_quality_issue d
                           JOIN historical_place_location l ON l.source_record_id=d.source_record_id
                          WHERE d.issue_type='geometry_invalid_repaired'
                            AND (l.geom IS NULL OR NOT ST_IsValid(l.geom))"""), 0)
    report.expect("V5", "4 条修复行类型为面/多面",
                  one("""SELECT count(*) FROM data_quality_issue d
                           JOIN historical_place_location l ON l.source_record_id=d.source_record_id
                          WHERE d.issue_type='geometry_invalid_repaired'
                            AND l.geom_type NOT IN ('Polygon','MultiPolygon')"""), 0)

    # 3,317 条合成代表点：坐标逐条与 places.csv 相同
    place_rep: Dict[str, Tuple[float, float]] = {}
    for row in read_rows(GIS / "places.csv"):
        lon, lat = tf(row.get("representative_longitude", "")), tf(row.get("representative_latitude", ""))
        if lon is not None and lat is not None:
            place_rep[(row.get("id") or "").strip()] = (lon, lat)
    cur.execute("""
        SELECT sr.external_id, l.representative_lon, l.representative_lat
          FROM source_record sr JOIN historical_place_location l USING (source_record_id)
         WHERE sr.dataset_id=%s AND sr.external_id LIKE '%%-representative'
        """, (P4,))
    rows = cur.fetchall()
    bad = 0
    for external_id, lon, lat in rows:
        pid = external_id.rsplit("-representative", 1)[0]
        exp = place_rep.get(pid)
        if exp is None or lon is None or lat is None or abs(exp[0] - lon) > 1e-9 or abs(exp[1] - lat) > 1e-9:
            bad += 1
    report.expect("V5", "合成代表点行数", len(rows), 3_317)
    report.expect("V5", "合成代表点坐标与 places.csv 不一致", bad, 0)

    # 7,200 个真正没有位置线索的地点：没有虚构坐标
    report.expect("V5", "无任何位置行的 v4.1 地点",
                  one("""SELECT count(*) FROM historical_place p WHERE p.dataset_id=%s
                          AND NOT EXISTS (SELECT 1 FROM historical_place_location l
                                           WHERE l.place_id=p.place_id)""", (P4,)),
                  EXPECT["no_geometry_places"])
    report.expect("V5", "这 7,200 个地点的 notes 标记 has_representative_point=false",
                  one("""SELECT count(*) FROM historical_place p WHERE p.dataset_id=%s
                          AND NOT EXISTS (SELECT 1 FROM historical_place_location l
                                           WHERE l.place_id=p.place_id)
                          AND p.notes LIKE '%%has_representative_point=false%%'""", (P4,)),
                  EXPECT["no_geometry_places"])

    # ================================================================= V6
    print("\nV6 精度")
    cur.execute("""
        SELECT l.location_precision, count(*) FROM historical_place_location l
          JOIN historical_place p USING (place_id)
         WHERE p.dataset_id=%s GROUP BY 1""", (P4,))
    prec = dict(cur.fetchall())
    report.expect("V6", "位置级 precise", prec.get("precise", 0), EXPECT["loc_precise"])
    report.expect("V6", "位置级 rough", prec.get("rough", 0), EXPECT["loc_rough"])
    report.expect("V6", "位置级只出现 precise/rough", set(prec) <= {"precise", "rough"}, True)
    report.expect("V6", "地点级 precise（notes 记录）",
                  one("""SELECT count(*) FROM historical_place WHERE dataset_id=%s
                          AND notes LIKE '%%location_precision=precise%%'""", (P4,)),
                  EXPECT["place_precise"])
    report.expect("V6", "地点级 rough（notes 记录）",
                  one("""SELECT count(*) FROM historical_place WHERE dataset_id=%s
                          AND notes LIKE '%%location_precision=rough%%'""", (P4,)),
                  EXPECT["place_rough"])

    # ================================================================= V7
    print("\nV7 候选关系")
    report.expect("V7", "candidate_match 总量", totals["candidate_match"], EXPECT["candidate_total"])
    conn_total = one("SELECT count(*) FROM candidate_match WHERE relation_type='pleiades_connection'")
    conn_slice = one("""SELECT count(*) FROM candidate_match c
                          JOIN source_record sr ON sr.source_record_id=c.source_record_id_a
                         WHERE c.relation_type='pleiades_connection'
                           AND sr.dataset_id=%s""", (SLICE,))
    conn_v41 = one("""SELECT count(*) FROM candidate_match c
                        JOIN source_record sr ON sr.source_record_id=c.source_record_id_a
                       WHERE c.relation_type='pleiades_connection'
                         AND sr.dataset_id=%s""", (P4,))
    report.expect("V7", "pleiades_connection 总行数", conn_total, 390 + EXPECT["candidate_delta"])
    report.expect("V7", "本轮新增（来源为 v4.1）", conn_v41, EXPECT["candidate_delta"])
    report.expect("V7", "既有切片承载的连接", conn_slice, 390)
    print(f"    pleiades_connection {conn_total:,} = 切片 {conn_slice} + v4.1 {conn_v41:,}")
    report.expect("V7", "无自环（place_id_a = place_id_b）",
                  one("SELECT count(*) FROM candidate_match WHERE place_id_a = place_id_b"), 0)
    report.expect("V7", "无重复三元组（uq_c09 之外再查一遍）",
                  one("""SELECT count(*) FROM (SELECT relation_type, place_id_a, place_id_b
                           FROM candidate_match GROUP BY 1,2,3 HAVING count(*)>1) t"""), 0)
    report.expect("V7", "confirmed 的 pleiades_connection 都有 system reviewer",
                  one("""SELECT count(*) FROM candidate_match WHERE relation_type='pleiades_connection'
                          AND status='confirmed' AND reviewer <> 'system:source_attested'"""), 0)

    # 13,553 个唯一有序对：从**原始 connections.csv** 出发重算一遍（含别名解析），
    # 再映射到库里的 place_id，逐对核对是否都在库。这样这个数字不依赖暂存 CSV 的行数。
    import re as _re  # noqa: PLC0415

    def place_key(value: str) -> str:
        text = (value or "").strip()
        return text.rstrip("/").rsplit("/", 1)[-1] if "/" in text else text

    hp_rows = list(read_rows(STAGING / "historical_places.csv"))
    key2place = {(r["source_dataset"], r["primary_external_id"]): pid
                 for r in hp_rows for pid in [r["place_id"]]}
    cur.execute("SELECT dataset_id, grain_key, place_id FROM historical_place")
    key2db = {(d, k): pid for d, k, pid in cur.fetchall()}
    pairs_source: set = set()
    dangling = 0
    with io.open(GIS / "connections.csv", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            ka = (P4, place_key(row.get("place_id")))
            kb = (P4, place_key(row.get("connects_to")))
            pa = key2db.get(ka) or key2db.get((SLICE, ka[1]))
            pb = key2db.get(kb) or key2db.get((SLICE, kb[1]))
            if pa is None or pb is None:
                dangling += 1
                continue
            if pa == pb:
                continue
            pairs_source.add((pa, pb))
    cur.execute("SELECT place_id_a, place_id_b FROM candidate_match"
                " WHERE relation_type='pleiades_connection'")
    pairs_db = set(cur.fetchall())
    report.expect("V7", "connections.csv 重算的唯一有序对", len(pairs_source), EXPECT["pairs_4_1"])
    report.expect("V7", "悬空端点（不生成候选）", dangling, 28)
    report.expect("V7", "这 13,553 对全部在库（差集）", len(pairs_source - pairs_db), 0)
    report.expect("V7", "库里的连接对没有来源之外的多余项（差集）",
                  len(pairs_db - pairs_source), 17)
    print(f"    库里 {len(pairs_db):,} 对 = v4.1 的 {len(pairs_source):,} 对"
          f" + 切片独有的 17 对（一端是仅切片有的地点）")

    # ================================================================= V8
    print("\nV8 质量台账")
    cur.execute("SELECT issue_type, count(*) FROM data_quality_issue GROUP BY 1 ORDER BY 1")
    issue = dict(cur.fetchall())
    print(f"    类型分布：{issue}")
    for name, expected in (("missing_coordinate", 7_200 + 337),
                           ("geometry_invalid_repaired", 4),
                           ("connection_endpoint_missing", 28),
                           ("accuracy_unknown_sentinel", 728)):
        report.expect("V8", f"{name} 累计行数", issue.get(name, 0), expected)
    report.expect("V8", "issue_fingerprint 唯一",
                  one("SELECT count(*)-count(DISTINCT issue_fingerprint) FROM data_quality_issue"), 0)
    synth = {
        "duplicate_external_id": issue.get("duplicate_external_id", 0),
        "derived_value_mismatch": issue.get("derived_value_mismatch", 0),
        "manual_edit_conflict": issue.get("manual_edit_conflict", 0),
    }
    print(f"    导入器合成：{synth}")
    baseline_total, baseline_staging, baseline_synth = 12_833, 12_631, 202
    synth_now = sum(synth.values())
    report.expect("V8", "台账总量（基线 + 暂存增量 + 合成增量）",
                  totals["data_quality_issue"],
                  baseline_total + EXPECT["staging_issues"] + (synth_now - baseline_synth))
    print(f"    {totals['data_quality_issue']:,} = 基线 {baseline_total:,}"
          f" + 暂存增量 {EXPECT['staging_issues']:,} + 合成增量 {synth_now - baseline_synth:,}")
    report.expect("V8", "台账 dataset 均非空",
                  one("SELECT count(*) FROM data_quality_issue WHERE dataset_id IS NULL"), 0)
    report.expect("V8", "action_taken 全在 6 值域",
                  one("""SELECT count(*) FROM data_quality_issue WHERE action_taken NOT IN
                          ('preserved_and_flagged','needs_manual_review','rejected',
                           'fixed_manually','ignored','discarded')"""), 0)
    report.expect("V8", "action_taken 原动词保留在 resolution_note（732 行）",
                  one("""SELECT count(*) FROM data_quality_issue
                          WHERE resolution_note LIKE '%%action_taken 原值=%%'"""), 732)

    # ================================================================= V9
    print("\nV9 完整性")
    report.expect("V9", "名称孤儿（place_id 无对应地点）",
                  one("""SELECT count(*) FROM historical_place_name n
                          WHERE NOT EXISTS (SELECT 1 FROM historical_place p WHERE p.place_id=n.place_id)"""), 0)
    report.expect("V9", "位置孤儿",
                  one("""SELECT count(*) FROM historical_place_location l
                          WHERE NOT EXISTS (SELECT 1 FROM historical_place p WHERE p.place_id=l.place_id)"""), 0)
    report.expect("V9", "名称 source_record 不可解析",
                  one("""SELECT count(*) FROM historical_place_name WHERE source_record_id IS NULL"""), 0)
    report.expect("V9", "位置 source_record 不可解析",
                  one("""SELECT count(*) FROM historical_place_location WHERE source_record_id IS NULL"""), 0)
    report.expect("V9", "v4.1 地点的锚点源记录指向本数据集",
                  one("""SELECT count(*) FROM historical_place p
                           JOIN source_record sr ON sr.source_record_id=p.created_from_source_record_id
                          WHERE p.dataset_id=%s AND sr.dataset_id<>%s""", (P4, P4)), 0)
    report.expect("V9", "raw_payload 全部非空",
                  one("SELECT count(*) FROM source_record WHERE raw_payload IS NULL"), 0)
    report.expect("V9", "v4.1 源记录 raw_file 全部以已知文件命名",
                  one("""SELECT count(*) FROM source_record WHERE dataset_id=%s
                          AND raw_file NOT IN ('places.csv','names.csv','location_points.csv',
                                               'location_linestrings.csv','location_polygons.csv',
                                               'connections.csv')""", (P4,)), 0)
    report.expect("V9", "v4.1 源记录 raw_record_index 非空",
                  one("SELECT count(*) FROM source_record WHERE dataset_id=%s"
                      " AND raw_record_index IS NULL", (P4,)), 0)
    report.expect("V9", "content_hash 唯一性（同五段键内）",
                  one("""SELECT count(*) FROM (SELECT dataset_id, record_scope, parent_external_id,
                             external_id, duplicate_ordinal, content_hash, count(*)
                           FROM source_record GROUP BY 1,2,3,4,5,6 HAVING count(*)>1) t"""), 0)

    # ================================================================= V10
    print("\nV10 批次（首轮导入 + 幂等复跑）")
    cur.execute("""SELECT batch_id, dataset_id, status, input_row_count, quarantined_count,
                          skipped_count, blocked_count,
                          coalesce(array_length(inserted_source_record_ids,1),0),
                          coalesce(array_length(updated_source_record_ids,1),0)
                     FROM import_batch WHERE batch_id > 14 ORDER BY batch_id""")
    batches = cur.fetchall()
    run1 = batches[:8]
    run2 = batches[8:]
    report.expect("V10", "新增批次数（两轮 × 8 数据集）", len(batches), 16)
    report.expect("V10", "首轮 8 批全部 succeeded",
                  sum(1 for b in run1 if b[2] == "succeeded"), 8)
    report.expect("V10", "复跑 8 批全部 succeeded",
                  sum(1 for b in run2 if b[2] == "succeeded"), 8)
    report.expect("V10", "首轮新增源记录合计", sum(b[7] for b in run1),
                  EXPECT["new_source_records"])
    report.expect("V10", "复跑新增源记录合计（必须 0）", sum(b[7] for b in run2), 0)
    report.expect("V10", "复跑内容变更合计（必须 0）", sum(b[8] for b in run2), 0)
    for b in batches:
        print(f"    batch {b[0]} {b[1]:34s} {b[2]:9s} in={b[3]:>7,} quar={b[4]:>4}"
              f" skip={b[5]:>5,} blocked={b[6]} ins={b[7]:>7,} upd={b[8]:>4}")

    # 幂等副作用：occurrence_count / last_batch_id 必须按设计推进，而不是"什么都没发生"
    report.expect("V10", "复跑后 occurrence_count=2 的台账行",
                  one("SELECT count(*) FROM data_quality_issue WHERE occurrence_count=2"),
                  EXPECT["staging_issues"] + 654)
    report.expect("V10", "全部源记录 last_batch_id 指向复跑批次",
                  one("""SELECT count(*) FROM source_record
                          WHERE last_batch_id < (SELECT max(batch_id) FROM import_batch) - 7"""),
                  0)

    conn.close()

    print("\n" + "=" * 72)
    print(f"判据 {len(report.items)} 条：通过 {len(report.items)-len(report.failures)}，"
          f"失败 {len(report.failures)}")
    for item in report.failures:
        print(f"  ✗ [{item['section']}] {item['name']} — {item['detail']}")

    payload = {
        "db": args.db,
        "ok": report.ok,
        "checks": len(report.items),
        "failures": len(report.failures),
        "totals": totals,
        "issue_types": issue,
        "importer_synthesized": synth,
        "batches": [list(b) for b in batches],
        "items": report.items,
    }
    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n报告 → {args.json}")
    return 0 if report.ok else 1


if __name__ == "__main__":
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
