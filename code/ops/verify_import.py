#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""阶段三：独立验证库导入结果的只读核验（V1–V9 + V12 + V13）。

原则（R1 修订，R1.2 收尾）：
  · 只读：不写入任何行、不改 DDL
  · 每一项的判据必须来自**本次实际执行**的查询或文件读取；没有执行 ⇒ 不得 PASS
  · 行数、指纹一律现场读取，不得把原始数量写死在输出文本里
  · 无法验证的显式标记 UNVERIFIED（例如无数据走到的更新路径）

用法：
  PYTHONPATH=./ops/.deps python ops/verify_import.py --db canvas_history_stage3_r12
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import sys
from pathlib import Path

import psycopg2

CODE_ROOT = Path(__file__).resolve().parent.parent
STAGING = CODE_ROOT / "data" / "staging"
REPORTS = CODE_ROOT / "ops" / "reports"

CSV_FILES = [
    "data_datasets.csv", "source_records.csv", "historical_places.csv",
    "historical_place_names.csv", "historical_place_locations.csv",
    "candidate_matches.csv", "data_quality_issues.csv",
]

# 开工前数据基线（设计资料/V2.1.1_正式交付/_build/STAGING_FIELD_BASELINE.md 行 29–35）
BASELINE_SHA256 = {
    "data_datasets.csv": "fa44197e54b4da4a8af78b589d10a63a668184397f63dbdf842b5051a2ef636f",
    "source_records.csv": "30fed0e40ba124960ba008b030948394398a418a9cc58b333095614469771c5d",
    "historical_places.csv": "86db3ce6b94f9e31036a3785a55510d48eb43bd4ce998aaa5cad2f59b068533f",
    "historical_place_names.csv": "80674c0ded553241c6f4745db0d6957d4dd6617acdfa7918d503128c1690ebbd",
    "historical_place_locations.csv": "9e987ba578e933ed9bdb11564487125783b22623abf348b9201a74d562d637a2",
    "candidate_matches.csv": "4e29c2ec64ebe263c325bab5f0eb70dc922116dd737542cf234373d86c98ab12",
    "data_quality_issues.csv": "7a8ab3916e00dcb04308d89c816c7c8771c6f71ec598ee3e4188c6b643263602",
}

RESULTS: list[tuple[str, str, str]] = []

# 台账口径基线（Owner R1.1 明确）：暂存原始 12,631 行 → 目标 12,831 行
LEDGER_STAGED = 12631          # 暂存原始行数（必须与现场读到的 CSV 行数相等）
LEDGER_DROPPED = 2             # licence_unconfirmed 两条明确剔除，不重归类
LEDGER_SYNTH_DUP = 5           # duplicate_external_id 合成
LEDGER_SYNTH_MIS = 197         # derived_value_mismatch 合成
LEDGER_TARGET = LEDGER_STAGED - LEDGER_DROPPED + LEDGER_SYNTH_DUP + LEDGER_SYNTH_MIS   # 12,831
MISMATCH_PLACES = 130          # derived_value_mismatch 涉及的地点个数（字段级台账，非地点数）


def record(no: str, status: str, msg: str) -> None:
    RESULTS.append((no, status, msg))
    icon = {"PASS": "✓", "FAIL": "✗", "UNVERIFIED": "?", "INFO": "·"}[status]
    print(f"  {icon} [{no}] {msg}")


def head(title: str) -> None:
    print(f"\n{'=' * 78}\n{title}\n{'=' * 78}")


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    for raw in (CODE_ROOT / ".env").read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


def one(cur, sql, args=None):
    cur.execute(sql, args or ())
    return cur.fetchone()


def val(cur, sql, args=None):
    r = one(cur, sql, args)
    return r[0] if r else None


def csv_rows(name: str) -> list[dict[str, str]]:
    with io.open(STAGING / name, encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def sha256_of(name: str) -> str:
    h = hashlib.sha256()
    with open(STAGING / name, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ------------------------------------------------------------------ V1
def v1_files(cur) -> None:
    head("V1  七张暂存 CSV 指纹与开工前基线逐一核对（SHA256 全字节）+ 批次逐条核对")
    bad, rows = [], {}
    for f in CSV_FILES:
        digest = sha256_of(f)
        n = len(csv_rows(f))
        rows[f] = n
        match = digest == BASELINE_SHA256[f]
        if not match:
            bad.append(f)
        print(f"    {f:32s} {n:>7,} 行  {digest}  {'= 基线' if match else '≠ 基线 ✗'}")

    # ---- 批次逐条核对（R1.1）：不得 DISTINCT + fetchone() 只看第一行。
    #      每一个批次都必须与其 input_file 的基线哈希相等，NULL 亦判失败。
    cur.execute("""SELECT batch_id, dataset_id, input_file, input_sha256
                     FROM import_batch ORDER BY batch_id""")
    batches = cur.fetchall()
    print(f"\n    import_batch 共 {len(batches)} 个批次（逐条核对，不取 DISTINCT 首行）")
    if not batches:
        bad.append("import_batch 为空，批次指纹无从核对")
    b_bad, b_null, b_nokey = [], [], []
    for bid, ds, fname, sha in batches:
        if sha is None:
            b_null.append(bid)
            mark = "NULL ✗"
        elif fname not in BASELINE_SHA256:
            b_nokey.append(f"{bid}:{fname}")
            mark = f"input_file {fname} 无基线 ✗"
        elif sha == BASELINE_SHA256[fname]:
            mark = f"= 基线 {fname}"
        else:
            b_bad.append(bid)
            mark = f"≠ 基线（{fname}）✗"
        print(f"      batch {bid:>3}  {ds:32s}  {fname:24s}  {str(sha)[:16]}…  {mark}")

    distinct_sha = len({b[3] for b in batches})
    print(f"    指纹集合：{distinct_sha} 种；NULL {len(b_null)} 条；无基线 input_file {len(b_nokey)} 条；"
          f"与基线不符 {len(b_bad)} 条")

    if not bad and not b_bad and not b_null and not b_nokey:
        record("V1", "PASS",
               f"7/7 文件指纹与基线逐字节相等；import_batch {len(batches)} 个批次逐条核对，"
               f"全部 input_sha256 = 其 input_file 的基线值（NULL 0 条、不符 0 条）")
    else:
        record("V1", "FAIL",
               f"文件不符 {bad}；批次不符 {b_bad}、NULL {b_null}、无基线 {b_nokey}"
               f"{'；' + str(bad) if bad else ''}")


# ------------------------------------------------------------------ V2
def v2_counts(cur, run_dir: Path) -> None:
    head("V2  原始 / 入库 / 排除 / 转换行数可逐层解释（行数现场读取，不写死）")
    src = {f: len(csv_rows(f)) for f in CSV_FILES}

    def n(table):
        return val(cur, f"SELECT count(*) FROM {table}")

    sr, hp = n("source_record"), n("historical_place")
    nm, lc = n("historical_place_name"), n("historical_place_location")
    cm, dq = n("candidate_match"), n("data_quality_issue")
    inact = val(cur, "SELECT count(*) FROM source_record WHERE NOT is_active")
    # 被隔离的源记录**从未入库**（name/location 行同样未写），所以只能从 CSV 侧比对。
    # 隔离清单取自第 1 轮导入的执行快照，并与库中 is_active=false 的行数交叉核对。
    s1 = run_dir / "run1_summary.json"
    qids = set(json.loads(s1.read_text(encoding="utf-8")).get("quarantine_ids") or []) if s1.exists() else set()
    nm_skip = sum(1 for r in csv_rows("historical_place_names.csv") if r["source_record_id"] in qids)
    lc_skip = sum(1 for r in csv_rows("historical_place_locations.csv") if r["source_record_id"] in qids)
    ex_file = None
    if s1.exists():
        p = json.loads(s1.read_text(encoding="utf-8")).get("excluded_csv") or ""
        if p and Path(p).exists():
            ex_file = Path(p)
    if ex_file is None:
        for cand in (run_dir / "stage3_excluded_rows.csv", REPORTS / "stage3_excluded_rows.csv"):
            if cand.exists():
                ex_file = cand
                break
    n_ex = len(list(csv.DictReader(io.open(ex_file, encoding="utf-8")))) if ex_file else None
    n_lic = val(cur, "SELECT count(*) FROM data_quality_issue WHERE issue_type='licence_unconfirmed'")

    print(f"    source_records.csv          {src['source_records.csv']:>7,} → source_record          {sr:>7,}")
    print(f"    historical_places.csv       {src['historical_places.csv']:>7,} → historical_place       {hp:>7,}")
    print(f"    historical_place_names.csv  {src['historical_place_names.csv']:>7,} → historical_place_name  "
          f"{nm:>7,}（− 隔离源 {nm_skip}）")
    print(f"    ..._locations.csv           {src['historical_place_locations.csv']:>7,} → ..._location  "
          f"{lc:>7,}（− 隔离源 {lc_skip}）")
    print(f"    candidate_matches.csv       {src['candidate_matches.csv']:>7,} → candidate_match        {cm:>7,}"
          f"（− 排除留痕 {n_ex}）")
    print(f"    data_quality_issues.csv     {src['data_quality_issues.csv']:>7,} → data_quality_issue     {dq:>7,}")
    print(f"    source_record 隔离行（保留未删）{inact}；隔离源记录 {sorted(qids)}")
    print(f"    引用隔离源的暂存行：name {nm_skip} / location {lc_skip}"
          + ("" if len(qids) == inact else f"  ⚠ 隔离清单 {len(qids)} ≠ 库中失效行 {inact}"))

    checks = [
        ("source_record", sr, src["source_records.csv"]),
        ("historical_place", hp, src["historical_places.csv"]),
        ("historical_place_name", nm, src["historical_place_names.csv"] - (nm_skip or 0)),
        ("historical_place_location", lc, src["historical_place_locations.csv"] - (lc_skip or 0)),
        ("candidate_match", cm, src["candidate_matches.csv"] - (n_ex or 0)),
        # 台账：暂存 12,631 − 2(licence 剔除) + 5(duplicate_external_id) + 197(derived_value_mismatch)
        ("data_quality_issue", dq,
         src["data_quality_issues.csv"] - LEDGER_DROPPED + LEDGER_SYNTH_DUP + LEDGER_SYNTH_MIS),
    ]
    bad = [(t, a, e) for t, a, e in checks if a != e]
    print("    逐项等式：")
    for t, a, e in checks:
        print(f"      {t:26s} 实际 {a:>7,}  期望 {e:>7,}  {'✓' if a == e else '✗'}")
    print(f"    台账口径：暂存原始 {src['data_quality_issues.csv']:,}（基线 {LEDGER_STAGED:,}）"
          f" − {LEDGER_DROPPED} + {LEDGER_SYNTH_DUP} + {LEDGER_SYNTH_MIS} = {LEDGER_TARGET:,}；"
          f"实际入库 {dq:,}")
    if bad or src["data_quality_issues.csv"] != LEDGER_STAGED or dq != LEDGER_TARGET or len(qids) != inact:
        record("V2", "FAIL",
               f"行数链不成立：{bad}；台账原始行 {src['data_quality_issues.csv']}（应为 {LEDGER_STAGED:,}）；"
               f"入库 {dq}（应为 {LEDGER_TARGET:,}）；隔离清单 {len(qids)} vs 库中失效 {inact}")
    else:
        record("V2", "PASS",
               f"六张目标表行数全部等于「暂存行 − 结构性排除」的实际算式；台账 {src['data_quality_issues.csv']:,} "
               f"− {LEDGER_DROPPED} + {LEDGER_SYNTH_DUP} + {LEDGER_SYNTH_MIS} = {dq:,}"
               f"（目标 {LEDGER_TARGET:,}）；隔离 {inact} 行保留未删")


# ------------------------------------------------------------------ V3
def v3_fk(cur) -> None:
    head("V3  外键无孤儿行（全库 FK 逐条 LEFT JOIN 扫描，非抽样）")
    cur.execute("""
        SELECT c.conname, c.conrelid::regclass::text, c.confrelid::regclass::text,
               (SELECT string_agg(a.attname, ',' ORDER BY u.ord)
                  FROM unnest(c.conkey) WITH ORDINALITY u(attnum, ord)
                  JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = u.attnum) AS child_cols,
               (SELECT string_agg(a.attname, ',' ORDER BY u.ord)
                  FROM unnest(c.confkey) WITH ORDINALITY u(attnum, ord)
                  JOIN pg_attribute a ON a.attrelid = c.confrelid AND a.attnum = u.attnum) AS parent_cols,
               (SELECT string_agg('c.' || a.attname, ' IS NOT NULL AND ' ORDER BY u.ord)
                  FROM unnest(c.conkey) WITH ORDINALITY u(attnum, ord)
                  JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = u.attnum) AS notnull
          FROM pg_constraint c
         WHERE c.contype = 'f'
           AND c.conrelid::regclass::text IN ('source_record','historical_place','historical_place_name',
               'historical_place_location','candidate_match','data_quality_issue','import_batch','data_dataset')
         ORDER BY 2, 1""")
    rows = cur.fetchall()
    total, worst = 0, []
    for conname, child, parent, ccols, pcols, notnull in rows:
        sql = f"""SELECT count(*) FROM {child} c
                   WHERE {notnull} IS NOT NULL
                     AND NOT EXISTS (SELECT 1 FROM {parent} p
                                      WHERE ({','.join('p.' + x for x in pcols.split(','))})
                                          = ({','.join('c.' + x for x in ccols.split(','))}))"""
        o = val(cur, sql)
        total += o
        if o:
            worst.append((conname, o))
        print(f"    {conname:44s} {child:26s}→{parent:18s} 孤儿 {o}")
    if total == 0:
        record("V3", "PASS", f"{len(rows)} 条外键全部 0 孤儿（全表扫描，非抽样）")
    else:
        record("V3", "FAIL", f"存在孤儿行：{worst}")


# ------------------------------------------------------------------ V4
def v4_unique(cur) -> None:
    head("V4  业务唯一键无冲突（C01 / C04 / C08 / C09 / C10）")
    tests = [
        ("C01 五段键", """SELECT count(*) FROM (SELECT 1 FROM source_record
              GROUP BY dataset_id, record_scope, parent_external_id, external_id, duplicate_ordinal
              HAVING count(*) > 1) t"""),
        ("C04 地点 (dataset,grain_key)", """SELECT count(*) FROM (SELECT 1 FROM historical_place
              GROUP BY dataset_id, grain_key HAVING count(*) > 1) t"""),
        ("C08 名称四段", """SELECT count(*) FROM (SELECT 1 FROM historical_place_name
              GROUP BY source_record_id, name_type, name_text, name_lang HAVING count(*) > 1) t"""),
        ("C09 候选三段", """SELECT count(*) FROM (SELECT 1 FROM candidate_match
              GROUP BY relation_type, place_id_a, place_id_b HAVING count(*) > 1) t"""),
        ("C10 台账指纹", """SELECT count(*) FROM (SELECT 1 FROM data_quality_issue
              GROUP BY issue_fingerprint HAVING count(*) > 1) t"""),
    ]
    bad = []
    for name, sql in tests:
        n = val(cur, sql)
        print(f"    {name:30s} 重复组 {n}")
        if n:
            bad.append((name, n))
    if bad:
        record("V4", "FAIL", f"唯一键冲突：{bad}")
    else:
        record("V4", "PASS", "5 组业务唯一键全部 0 冲突")


# ------------------------------------------------------------------ V5
def v5_geom(cur) -> None:
    head("V5  坐标与 SRID（NULL 安全比较；无 geom 行逐条归因；越界坐标核对台账与等级）")
    cur.execute("""
        SELECT count(*)                                                       AS n_total,
               count(*) FILTER (WHERE geom IS NOT NULL)                       AS n_geom,
               count(*) FILTER (WHERE representative_lon IS NOT NULL
                                  AND representative_lat IS NOT NULL)         AS n_coord,
               count(*) FILTER (WHERE geom IS NOT NULL AND ST_SRID(geom) = 4326)          AS n_srid,
               count(*) FILTER (WHERE geom IS NOT NULL AND ST_GeometryType(geom) = 'ST_Point') AS n_ispt,
               count(*) FILTER (WHERE geom IS NOT NULL AND geom_type = 'Point')           AS n_gtype,
               -- NULL 安全：任一侧为 NULL 都算"不一致"（IS DISTINCT FROM 不会像 <> 那样吞掉 NULL）
               count(*) FILTER (WHERE ST_X(geom) IS DISTINCT FROM representative_lon
                                  OR ST_Y(geom) IS DISTINCT FROM representative_lat)      AS n_mismatch,
               count(*) FILTER (WHERE geom IS NOT NULL
                                  AND (representative_lon IS NULL OR representative_lat IS NULL)) AS n_geom_nocoord,
               count(*) FILTER (WHERE geom IS NULL
                                  AND representative_lon IS NOT NULL
                                  AND representative_lat IS NOT NULL)         AS n_coord_nogeom,
               count(*) FILTER (WHERE representative_lon IS NOT NULL
                                  AND representative_lat IS NOT NULL
                                  AND (representative_lon NOT BETWEEN -180 AND 180
                                       OR representative_lat NOT BETWEEN -90 AND 90)) AS n_outrange,
               -- 单侧 NULL 必须双向都查：只查一个方向会漏掉另一半
               count(*) FILTER (WHERE representative_lon IS NULL
                                  AND representative_lat IS NOT NULL)          AS n_lon_null,
               count(*) FILTER (WHERE representative_lat IS NULL
                                  AND representative_lon IS NOT NULL)          AS n_lat_null,
               count(*) FILTER (WHERE geom IS NULL
                                  AND coalesce(btrim(notes), '') = '')         AS n_nogeom_nonotes
          FROM historical_place_location""")
    (n_total, n_geom, n_coord, n_srid, n_ispt, n_gtype,
     n_mismatch, n_geom_nocoord, n_coord_nogeom, n_outrange,
     n_lon_null, n_lat_null, n_nogeom_nonotes) = cur.fetchone()
    n_partial_null = n_lon_null + n_lat_null
    print(f"    共 {n_total:,} 行坐标行：有 geom {n_geom:,} / 有 lon+lat {n_coord:,}")
    print(f"    SRID=4326 {n_srid:,} / ST_Point {n_ispt:,} / geom_type='Point' {n_gtype:,}"
          f"  {'✓' if n_srid == n_ispt == n_gtype == n_geom else '✗'}")
    print(f"    geom 与 representative_lon/lat 不一致（IS DISTINCT FROM，含单侧 NULL）{n_mismatch}"
          f"  {'✓' if n_mismatch == 0 else '✗'}")
    print(f"    有 geom 但缺坐标 {n_geom_nocoord}；有坐标但无 geom {n_coord_nogeom}")
    print(f"    坐标越界 {n_outrange}；lon/lat 单侧为 NULL {n_partial_null}"
          f"（lon 空 {n_lon_null} / lat 空 {n_lat_null}，双向分别统计）")

    # ---- 无 geom 行：逐条归因，并核实状态（C15 只拦 published）
    cur.execute("""SELECT record_status, crs_confidence, count(*),
                          count(*) FILTER (WHERE coalesce(notes,'') = '')
                     FROM historical_place_location WHERE geom IS NULL
                    GROUP BY 1,2 ORDER BY 3 DESC""")
    nog_rows = cur.fetchall()
    print("\n    无 geom 行的状态分布（record_status / crs_confidence / 行数 / notes 为空的行数）：")
    for st, cc, c, nempty in nog_rows:
        print(f"      {st:12s} {cc:12s} {c:>3} 行   notes 空 {nempty}")
    nog_pub = val(cur, """SELECT count(*) FROM historical_place_location
                           WHERE geom IS NULL AND record_status = 'published'""")
    nog_unknown_crs = val(cur, """SELECT count(*) FROM historical_place_location
                                   WHERE geom IS NULL AND crs_confidence = 'unknown'""")
    print(f"    其中 published {nog_pub}（C14/C15 拦截口径）；crs_confidence='unknown' {nog_unknown_crs}")
    # 无坐标原因说明：notes 必须逐行载明，且必须有 missing_coordinate 台账兜底（覆盖率 100%）
    print(f"    无 geom 行 notes 为空 {n_nogeom_nonotes}（PASS 判据：必须为 0）")
    n_nog_ledger = val(cur, """SELECT count(*) FROM historical_place_location l
                                WHERE l.geom IS NULL
                                  AND NOT EXISTS (SELECT 1 FROM data_quality_issue d
                                                   WHERE d.source_record_id = l.source_record_id
                                                     AND d.issue_type = 'missing_coordinate')""")
    print(f"    无 geom 行中缺少 missing_coordinate 台账登记 {n_nog_ledger}（PASS 判据：必须为 0）")

    # ---- C14/C15：published 行不得缺 geom 或 CRS 未知
    pub_nogeom = val(cur, """SELECT count(*) FROM historical_place_location
                              WHERE (geom IS NULL OR crs_confidence = 'unknown')
                                AND record_status = 'published'""")
    print(f"    C14/C15 违例（published 且 geom 空或 CRS 未知）{pub_nogeom}")

    # ---- 越界坐标：核对地点、台账类型、severity 等级、处置动作、源记录一致性
    cur.execute("""SELECT l.location_id, l.source_record_id, l.place_id, p.canonical_name,
                          p.dataset_id, l.representative_lon, l.representative_lat,
                          l.record_status, l.crs_confidence, l.geom_type
                     FROM historical_place_location l JOIN historical_place p USING (place_id)
                    WHERE l.representative_lon IS NOT NULL
                      AND l.representative_lat IS NOT NULL
                      AND (l.representative_lon NOT BETWEEN -180 AND 180
                           OR l.representative_lat NOT BETWEEN -90 AND 90)
                    ORDER BY l.location_id""")
    oob = cur.fetchall()
    oob_bad = []
    print("\n    越界坐标逐条核对：")
    for (loc_id, srid, place_id, name, ds, lon, lat, st, cc, gtype) in oob:
        cur.execute("""SELECT issue_id, issue_type, severity, field_name, action_taken, place_id
                         FROM data_quality_issue
                        WHERE source_record_id = %s AND observed_value = %s
                        ORDER BY issue_id""", (srid, f"lon={lon},lat={lat}"))
        led = cur.fetchall()
        hit = [x for x in led if x[1] == "coordinate_out_of_range"]
        sev = hit[0][2] if hit else None
        act = hit[0][4] if hit else None
        ok = bool(hit) and sev == "blocking" and act == "preserved_and_flagged"
        if not ok:
            oob_bad.append(loc_id)
        print(f"      location {loc_id}  place {place_id}「{name}」({ds})  "
              f"lon={lon} lat={lat}  status={st}  crs={cc}  geom_type={gtype}")
        print(f"        → 台账 {[(x[0], x[1], x[2], x[3], x[4]) for x in led] or '无'}  "
              f"{'✓ 类型/等级/处置相符' if ok else '✗ 未登记或等级不符'}")
        if hit:
            print(f"        → 台账 place_id={hit[0][5]}（暂存台账未回填地点，可经 source_record_id="
                  f"{srid} 反查得 place {place_id}，与坐标行归属一致）")

    geom_ok = (n_geom > 0 and n_srid == n_geom and n_ispt == n_geom and n_gtype == n_geom
               and n_mismatch == 0 and n_geom_nocoord == 0
               and n_coord_nogeom == 0
               and n_lon_null == 0 and n_lat_null == 0
               and n_nogeom_nonotes == 0 and n_nog_ledger == 0
               and n_geom == n_coord - n_coord_nogeom
               and pub_nogeom == 0 and nog_pub == 0)
    if geom_ok and not oob_bad:
        record("V5", "PASS",
               f"{n_geom:,} 行几何全部 SRID=4326 / Point，且 ST_X/ST_Y 与 representative_lon/lat "
               f"NULL 安全逐位相等（IS DISTINCT FROM 0 行）；lon/lat 单侧 NULL 双向均为 0"
               f"（lon 空 {n_lon_null} / lat 空 {n_lat_null}）；有 geom 缺坐标 0、有坐标缺 geom 0；"
               f"无 geom {n_total - n_geom} 行全部非 published（published {nog_pub}，C14/C15 违例 {pub_nogeom}），"
               f"notes 空 0 行且 missing_coordinate 台账覆盖率 100%；"
               f"{len(oob)} 行越界坐标原样保留，台账 coordinate_out_of_range / severity=blocking / "
               f"preserved_and_flagged 逐条相符")
    else:
        record("V5", "FAIL",
               f"geom={n_geom}/{n_total} srid={n_srid} point={n_ispt} type={n_gtype} "
               f"mismatch={n_mismatch}(NULL安全) 有geom缺坐标={n_geom_nocoord} "
               f"有坐标缺geom={n_coord_nogeom} 单侧NULL(lon空/ lat空)={n_lon_null}/{n_lat_null} "
               f"无geom缺notes={n_nogeom_nonotes} 无geom缺台账={n_nog_ledger} "
               f"c14c15={pub_nogeom} nogeom_published={nog_pub} "
               f"越界未登记/等级不符={oob_bad}")


# ------------------------------------------------------------------ V6
def v6_views(cur) -> None:
    head("V6  三个派生视图：列数 + 行数 + 语义对应（证据行与子表双向恒等、时间跨度独立重算）")
    places = val(cur, "SELECT count(*) FROM historical_place")
    n_name = val(cur, "SELECT count(*) FROM historical_place_name")
    n_loc = val(cur, "SELECT count(*) FROM historical_place_location")
    bad = []

    # ---- 6.1 列数
    spec = {"v_place_evidence": 11, "v_place_liveness": 7, "v_place_time_span": 10}
    ncol = {}
    for view, exp in spec.items():
        n = val(cur, """SELECT count(*) FROM information_schema.columns
                         WHERE table_name = %s AND table_schema = current_schema()""", (view,))
        ncol[view] = n
        if n != exp:
            bad.append(f"{view} 列数 {n}≠{exp}")
        print(f"    {view:22s} {n:>2} 列 {'✓' if n == exp else '✗'}（期望 {exp}）")

    # ---- 6.2 行数
    n_ev_all = val(cur, "SELECT count(*) FROM v_place_evidence")
    n_ev_canon = val(cur, "SELECT count(*) FROM v_place_evidence WHERE is_canonical_row")
    n_live = val(cur, "SELECT count(*) FROM v_place_liveness")
    n_span = val(cur, "SELECT count(*) FROM v_place_time_span")
    for view, n, exp, note in (
            ("v_place_liveness", n_live, places, "地点级"),
            ("v_place_time_span", n_span, places, "地点级"),
            ("v_place_evidence", n_ev_all, None, "证据行级")):
        ok = (n == exp) if exp is not None else (n >= places)
        if not ok:
            bad.append(f"{view} 行数 {n}≠{exp or '≥' + str(places)}")
        print(f"    {view:22s} {n:>7,} 行 {'✓' if ok else '✗'}（{note}，"
              f"{'期望 = 地点数 ' + format(places, ',') if exp is not None else '期望 ≥ 地点数'}）")

    # ---- 6.3 证据视图：canonical 每地点唯一覆盖
    n_canon_dup = val(cur, """SELECT count(*) FROM (SELECT place_id FROM v_place_evidence
                                GROUP BY 1 HAVING count(*) FILTER (WHERE is_canonical_row) <> 1) t""")
    n_cover = val(cur, "SELECT count(DISTINCT place_id) FROM v_place_evidence")
    n_place_only = val(cur, """SELECT count(*) FROM historical_place p
                                WHERE NOT EXISTS (SELECT 1 FROM v_place_evidence e
                                                   WHERE e.place_id = p.place_id)""")
    print(f"\n    6.3 canonical 覆盖：canonical 行 {n_ev_canon:,}；canonical≠1 的地点 {n_canon_dup}；"
          f"视图覆盖地点 {n_cover:,}/{places:,}；无任何证据行的地点 {n_place_only}")
    for k, v in (("canonical≠1", n_canon_dup), ("覆盖不足", places - n_cover),
                 ("无证据地点", n_place_only), ("canonical≠地点数", n_ev_canon - places)):
        if v:
            bad.append(f"证据视图 {k}={v}")

    # ---- 6.4 证据行与底层子表双向恒等（不是抽样；四列同时比对：place / source_record / 角色表 / 子行）
    pairs = [
        ("name", "historical_place_name", "name_id"),
        ("location", "historical_place_location", "location_id"),
    ]
    print("\n    6.4 证据行 ↔ 子表双向恒等（EXCEPT 双向，place_id + source_record_id + child_table + child_row_id）：")
    for role, table, key in pairs:
        fwd = val(cur, f"""SELECT count(*) FROM (
                    SELECT place_id, source_record_id, child_table, child_row_id
                      FROM v_place_evidence WHERE evidence_role = '{role}'
                    EXCEPT
                    SELECT place_id, source_record_id, '{role}', {key} FROM {table}) t""")
        bwd = val(cur, f"""SELECT count(*) FROM (
                    SELECT place_id, source_record_id, '{role}'::text, {key} FROM {table}
                    EXCEPT
                    SELECT place_id, source_record_id, child_table, child_row_id
                      FROM v_place_evidence WHERE evidence_role = '{role}') t""")
        n_tab = val(cur, f"SELECT count(*) FROM {table}")
        n_view = val(cur, f"SELECT count(*) FROM v_place_evidence WHERE evidence_role = '{role}'")
        ok = (fwd == 0 and bwd == 0 and n_view == n_tab)
        print(f"      {role:9s} 视图 {n_view:>6,} 行 / 子表 {n_tab:>6,} 行；"
              f"视图→表差集 {fwd}、表→视图差集 {bwd}  {'✓' if ok else '✗'}")
        if not ok:
            bad.append(f"{role} 双向恒等 fwd={fwd} bwd={bwd} {n_view}≠{n_tab}")
        # 子行状态 / 驳回人必须与子表一致
        nm = (f"""LEFT JOIN {table} c
                    ON e.evidence_role = '{role}' AND c.{key} = e.child_row_id""")
        n_st = val(cur, f"""SELECT count(*) FROM v_place_evidence e {nm}
                             WHERE e.evidence_role = '{role}'
                               AND (c.record_status IS DISTINCT FROM e.child_record_status
                                    OR c.rejected_by IS DISTINCT FROM e.child_rejected_by)""")
        print(f"      {'':9s} child_record_status / child_rejected_by 与子表不一致 {n_st}")
        if n_st:
            bad.append(f"{role} 子行状态不一致 {n_st}")

    # ---- 6.5 creator 角色 + evidence_role 基本完整性
    n_cr = val(cur, "SELECT count(*) FROM v_place_evidence WHERE evidence_role = 'creator'")
    n_cr_child = val(cur, """SELECT count(*) FROM v_place_evidence
                              WHERE evidence_role = 'creator'
                                AND (child_row_id IS NOT NULL OR child_table IS NOT NULL
                                     OR child_record_status IS NOT NULL)""")
    n_cr_nosr = val(cur, """SELECT count(*) FROM v_place_evidence
                             WHERE evidence_role = 'creator' AND source_record_id IS NULL""")
    n_role_bad = val(cur, """SELECT count(*) FROM v_place_evidence
                              WHERE evidence_role NOT IN ('creator', 'name', 'location')""")
    n_ct_bad = val(cur, """SELECT count(*) FROM v_place_evidence
                            WHERE (evidence_role IN ('name', 'location')
                                   AND (child_table IS DISTINCT FROM evidence_role
                                        OR child_row_id IS NULL))
                               OR (evidence_role = 'creator' AND child_table IS NOT NULL)""")
    n_place_nocr = val(cur, """SELECT count(*) FROM historical_place p
                                WHERE NOT EXISTS (SELECT 1 FROM v_place_evidence e
                                                   WHERE e.place_id = p.place_id
                                                     AND e.evidence_role = 'creator')""")
    n_anchor_dup = val(cur, """SELECT count(*) FROM (SELECT place_id FROM v_place_evidence
                                GROUP BY 1 HAVING count(*) FILTER (WHERE is_anchor) <> 1) t""")
    n_anchor_wrong = val(cur, """SELECT count(*) FROM v_place_evidence e
                                  JOIN historical_place p USING (place_id)
                                 WHERE e.is_anchor
                                   AND e.source_record_id IS DISTINCT FROM p.created_from_source_record_id""")
    n_noncr_anchor = val(cur, """SELECT count(*) FROM v_place_evidence
                                  WHERE is_anchor AND evidence_role <> 'creator'""")
    print(f"\n    6.5 creator 角色：{n_cr:,} 行；child_row_id/table/status 非空 {n_cr_child}；"
          f"source_record_id 为空 {n_cr_nosr}；无 creator 行的地点 {n_place_nocr}；"
          f"evidence_role 越界 {n_role_bad}；child_table 与角色不符 {n_ct_bad}")
    print(f"        is_anchor≠1 的地点 {n_anchor_dup}；is_anchor 与 created_from 不符 {n_anchor_wrong}；"
          f"非 creator 行标 anchor {n_noncr_anchor}")
    for k, v in (("creator 子行字段非空", n_cr_child), ("creator 缺源记录", n_cr_nosr),
                 ("无 creator 行", n_place_nocr), ("role 越界", n_role_bad),
                 ("child_table 不符", n_ct_bad),
                 ("anchor≠1", n_anchor_dup),
                 ("anchor 与 created_from 不符", n_anchor_wrong), ("非creator标anchor", n_noncr_anchor)):
        if v:
            bad.append(f"{k}={v}")

    # ---- 6.6 source_is_active / inactive_reason 必须忠实于 source_record
    n_src = val(cur, """SELECT count(*) FROM v_place_evidence e
                          JOIN source_record sr USING (source_record_id)
                         WHERE e.source_is_active IS DISTINCT FROM sr.is_active
                            OR e.source_inactive_reason IS DISTINCT FROM sr.inactive_reason""")
    n_orphan = val(cur, """SELECT count(*) FROM v_place_evidence e
                            LEFT JOIN source_record sr USING (source_record_id)
                           WHERE sr.source_record_id IS NULL""")
    print(f"    6.6 source_is_active/reason 与 source_record 不一致 {n_src}；无对应源记录 {n_orphan}")
    if n_src or n_orphan:
        bad.append(f"源状态 {n_src} / 无源 {n_orphan}")

    # ---- 6.7 时间跨度：独立重算全部 9 个派生列（不只看 valid_child_rows > 0）
    n_span_bad = val(cur, """
        WITH child AS (
          SELECT place_id, source_record_id, valid_from_year_astro f,
                 valid_to_year_astro t, record_status
            FROM historical_place_name
          UNION ALL
          SELECT place_id, source_record_id, valid_from_year_astro, valid_to_year_astro, record_status
            FROM historical_place_location),
        eff AS (
          SELECT c.* FROM child c JOIN source_record sr USING (source_record_id)
           WHERE c.record_status <> 'rejected' AND sr.is_active),
        agg AS (
          SELECT p.place_id,
                 min(e.f) FILTER (WHERE e.f IS NOT NULL)          AS sf,
                 max(e.t) FILTER (WHERE e.t IS NOT NULL)          AS st,
                 count(*) FILTER (WHERE e.f IS NOT NULL)          AS nf,
                 count(*) FILTER (WHERE e.t IS NOT NULL)          AS nt,
                 count(*) FILTER (WHERE e.record_status = 'staging') AS ns,
                 count(*) FILTER (WHERE e.f IS NOT NULL OR e.t IS NOT NULL) AS nn,
                 count(e.place_id)                                AS vc
            FROM historical_place p LEFT JOIN eff e ON e.place_id = p.place_id
           GROUP BY p.place_id),
        tot AS (SELECT place_id, count(*) ct FROM child GROUP BY 1)
        SELECT count(*) FROM agg JOIN v_place_time_span v USING (place_id)
          LEFT JOIN tot ON tot.place_id = agg.place_id
         WHERE agg.sf IS DISTINCT FROM v.span_from_astro
            OR agg.st IS DISTINCT FROM v.span_to_astro
            OR agg.nf IS DISTINCT FROM v.from_evidence_rows
            OR agg.nt IS DISTINCT FROM v.to_evidence_rows
            OR agg.ns IS DISTINCT FROM v.staging_evidence_rows
            OR agg.vc IS DISTINCT FROM v.valid_child_rows
            OR coalesce(tot.ct, 0) IS DISTINCT FROM v.child_rows_total
            OR v.derivation_kind IS DISTINCT FROM
               CASE WHEN agg.nn = 0 THEN 'no_evidence'
                    WHEN agg.sf IS NOT NULL AND agg.st IS NOT NULL AND agg.sf = agg.st
                         THEN 'single_point'
                    ELSE 'envelope_of_name_and_location_rows' END
            OR v.all_children_rejected IS DISTINCT FROM
               (coalesce(tot.ct, 0) > 0 AND agg.vc = 0)""")
    print(f"\n    6.7 时间跨度独立重算（9 个派生列 + 3 值 derivation_kind + all_children_rejected）"
          f"不一致地点 {n_span_bad}")
    if n_span_bad:
        bad.append(f"时间跨度重算不一致 {n_span_bad}")

    cur.execute("""SELECT derivation_kind, count(*),
                          count(*) FILTER (WHERE span_from_astro IS NULL),
                          count(*) FILTER (WHERE span_from_astro = span_to_astro)
                     FROM v_place_time_span GROUP BY 1 ORDER BY 2 DESC""")
    kinds = cur.fetchall()
    print("    derivation_kind 分布（行数 / span_from 为 NULL / 两端相等）：")
    for k, c, nnull, neq in kinds:
        print(f"      {k:34s} {c:>7,}   NULL {nnull:>7,}   两端相等 {neq:>7,}")
    # 语义自洽：no_evidence 必须两列全 NULL；single_point 必须两端相等且非空
    k_noev, k_single = 0, 0
    for k, c, nnull, neq in kinds:
        if k == "no_evidence":
            k_noev = c
            if nnull != c:
                bad.append(f"no_evidence 中 span_from 非 NULL {c - nnull}")
        if k == "single_point":
            k_single = c
            if neq != c:
                bad.append(f"single_point 中两端不等 {c - neq}")
    n_tot = sum(c for _k, c, _n, _e in kinds)
    m_null = val(cur, "SELECT count(*) FROM v_place_time_span WHERE span_from_astro IS NULL")
    print(f"    合计 {n_tot:,} 行；span_from 为 NULL {m_null:,}（= no_evidence {k_noev:,} + "
          f"仅有 to 端 {m_null - k_noev:,}）；single_point {k_single:,}")
    n_span_rows = val(cur, """SELECT count(*) FROM v_place_time_span
                               WHERE span_from_astro IS NOT NULL AND valid_child_rows > 0""")
    print(f"    有实际派生结果（span_from 非空且 valid_child_rows>0）{n_span_rows:,} 行")
    if n_span_rows == 0:
        bad.append("时间跨度视图无任何实际派生结果（空壳）")

    # ---- 6.8 liveness 分布
    print("\n    6.8 v_place_liveness 分布：")
    cur.execute("SELECT liveness, count(*) FROM v_place_liveness GROUP BY 1 ORDER BY 2 DESC")
    for lv, c in cur.fetchall():
        print(f"      {lv:24s} {c:>7,}")

    if bad:
        record("V6", "FAIL", f"{bad}")
    else:
        record("V6", "PASS",
               f"列数 11/7/10 命中；两地点级视图各 {places:,} 行 = 地点数；canonical 每地点恰 1 行（{n_ev_canon:,}）；"
               f"证据行 {n_ev_all:,} = creator {n_cr:,} + name {n_name:,} + location {n_loc:,}，"
               f"name/location 与子表按 place_id+source_record_id+child_table+child_row_id 四列双向差集均为 0；"
               f"evidence_role 仅 creator/name/location 三类、child_table 与角色一一对应、每地点均有 creator 行、"
               f"creator 均带源记录；时间跨度 9 列独立重算 0 不一致，"
               f"实际派生结果 {n_span_rows:,} 行（no_evidence {k_noev:,} / single_point {k_single:,}）")


def v12_c27_c28(cur) -> None:
    head("V12  C27 / C28 断言级真值表（非 SQL CHECK，必须用数据实测）")
    places = val(cur, "SELECT count(*) FROM historical_place")
    r4 = {
        "R4a rejected 但 liveness 不在失败集":
            """SELECT count(*) FROM v_place_liveness
                WHERE record_status = 'rejected'
                  AND liveness NOT IN ('all_sources_absent','all_sources_rolled_back',
                                       'quarantined_only','mixed_inactive')""",
        "R4b 失败集 liveness 但 status<>rejected":
            """SELECT count(*) FROM v_place_liveness
                WHERE liveness IN ('all_sources_absent','all_sources_rolled_back',
                                   'quarantined_only','mixed_inactive')
                  AND record_status <> 'rejected'""",
        "R4c (active, rejected) 不可达":
            """SELECT count(*) FROM v_place_liveness
                WHERE liveness = 'active' AND record_status = 'rejected'""",
        "R4d (manual, rejected) 不可达":
            """SELECT count(*) FROM v_place_liveness
                WHERE liveness = 'manual' AND record_status = 'rejected'""",
        "R4e merged 行必须 record_status='merged'":
            """SELECT count(*) FROM v_place_liveness
                WHERE liveness = 'merged' AND record_status <> 'merged'""",
        "R4f orphaned 必须为 0":
            """SELECT count(*) FROM v_place_liveness WHERE liveness = 'orphaned'""",
    }
    bad = []
    for name, sql in r4.items():
        n = val(cur, sql)
        print(f"    {name:44s} {n}")
        if n:
            bad.append((name, n))

    n_cells = val(cur, """SELECT count(*) FROM (SELECT DISTINCT liveness, record_status
                            FROM v_place_liveness) t""")
    n_lv = val(cur, "SELECT count(DISTINCT liveness) FROM v_place_liveness")
    print(f"    实际出现的 (liveness, record_status) 组合 {n_cells} 个 / 出现 {n_lv} 种 liveness")
    n_mismatch = val(cur, """
        WITH recomputed AS (
          SELECT p.place_id, p.record_status,
                 CASE
                   WHEN p.record_status = 'merged' THEN 'merged'
                   WHEN p.created_by = 'manual'    THEN 'manual'
                   WHEN EXISTS (SELECT 1 FROM v_place_evidence e
                                 WHERE e.place_id = p.place_id
                                   AND e.source_is_active IS TRUE
                                   AND e.child_record_status IS DISTINCT FROM 'rejected')
                        THEN 'active'
                   ELSE 'orphaned'
                 END AS expect_liveness
            FROM historical_place p)
        SELECT count(*) FROM recomputed r JOIN v_place_liveness v USING (place_id)
         WHERE v.liveness <> r.expect_liveness""")
    print(f"    按优先级独立重算 liveness 与视图不一致的行 {n_mismatch}")

    if not bad and n_mismatch == 0 and n_cells > 0:
        record("V12", "PASS",
               f"C27：6 条 R4a–R4f 全 0；出现 {n_lv} 种 liveness、{n_cells} 个合法格。"
               f"C28：{places:,} 行按优先级重算 0 不一致")
    else:
        record("V12", "FAIL", f"{bad or ''} 重算不一致 {n_mismatch}")

    if n_lv < 8:
        print(f"\n    ⚠ 真值表为 8 种 liveness × 3 种 record_status，本库数据只触发 {n_lv} 种。")
        record("V12b", "INFO",
               f"真值表穷尽性**不能**由本库数据证明（仅 {n_cells}/{7} 个合法格出现）；"
               f"穷尽性由 verify_rollback_and_protection.py 的构造夹具 T 段落实测，见其日志")


# ------------------------------------------------------------------ V7
def v7_ledger(cur) -> None:
    head("V7  质量台账逐项核对（总数 / 类型数 / 偏差条数与地点数 / licence 为 0）")
    staged_types = {r["issue_type"] for r in csv_rows("data_quality_issues.csv")}
    n_staged = len(csv_rows("data_quality_issues.csv"))
    # 期望类型数现场推算：暂存类型 − licence_unconfirmed + 2 个导入器合成类型
    exp_types = len(staged_types - {"licence_unconfirmed"}) + 2
    cur.execute("""SELECT issue_type, count(*) FROM data_quality_issue GROUP BY 1 ORDER BY 2 DESC""")
    rows = cur.fetchall()
    tot = sum(c for _t, c in rows)
    for it, c in rows:
        print(f"    {it:34s} {c:>6,}")
    n_type = len(rows)
    print(f"    {'合计':34s} {tot:>6,}   类型数 {n_type}")
    print(f"    类型数来源：暂存 {len(staged_types)} 种 − licence_unconfirmed 1 种 "
          f"+ 导入器合成（duplicate_external_id / derived_value_mismatch）2 种 = {exp_types}")
    lic = val(cur, "SELECT count(*) FROM data_quality_issue WHERE issue_type='licence_unconfirmed'")
    mis = val(cur, "SELECT count(*) FROM data_quality_issue WHERE issue_type='derived_value_mismatch'")
    mis_p = val(cur, """SELECT count(DISTINCT place_id) FROM data_quality_issue
                         WHERE issue_type='derived_value_mismatch'""")
    dup = val(cur, "SELECT count(*) FROM data_quality_issue WHERE issue_type='duplicate_external_id'")
    print(f"    licence_unconfirmed {lic}（应为 0）；derived_value_mismatch {mis} 条 / {mis_p} 个地点；"
          f"duplicate_external_id {dup} 条")
    checks = [("总数", tot, LEDGER_TARGET), ("类型数", n_type, exp_types), ("licence", lic, 0),
              ("偏差条数", mis, LEDGER_SYNTH_MIS), ("偏差地点", mis_p, MISMATCH_PLACES),
              ("duplicate_external_id", dup, LEDGER_SYNTH_DUP)]
    bad = [(k, a, e) for k, a, e in checks if a != e]
    print("    逐项判据：" + "；".join(f"{k} {a:,} vs {e:,} {'✓' if a == e else '✗'}" for k, a, e in checks))
    if bad:
        record("V7", "FAIL", f"台账不符：{bad}")
    else:
        record("V7", "PASS",
               f"{tot:,} 行（目标 {LEDGER_TARGET:,}）/ {n_type} 种 issue_type"
               f"（暂存 {len(staged_types)} 种 − licence + 合成 2 = {exp_types}）/ "
               f"derived_value_mismatch {mis} 条落在 {mis_p} 个地点 / duplicate_external_id {dup} / "
               f"licence_unconfirmed 0")


# ------------------------------------------------------------------ V8
# 必备键 = 核验里**实际读取**的每一个键（含 dry_run / inject_fault，缺一个就不能判 PASS）
SUMMARY_REQUIRED = ("db", "run_at", "dry_run", "inject_fault", "exit_code", "committed",
                    "counts_before", "counts_after", "assert_ok", "staging_rows",
                    "source_stat", "candidate_stat", "table_delta_inserted")
SOURCE_STAT_REQUIRED = ("inserted", "updated", "touched", "held")
CAND_STAT_REQUIRED = ("staging", "inserted")
ALL_TABLES = ("source_record", "historical_place", "historical_place_name",
              "historical_place_location", "candidate_match", "data_quality_issue",
              "import_batch", "data_dataset", "data_source")
DATA_TABLES = ALL_TABLES[:6]


def _is_int(x) -> bool:
    return isinstance(x, int) and not isinstance(x, bool)


def _load_summary(path: Path, label: str, bad: list[str]) -> dict | None:
    """读取执行快照并做完整性校验：缺字段一律 FAIL，**不得默认成 0**。"""
    if not path.exists():
        bad.append(f"{label} 快照不存在：{path.name}")
        return None
    try:
        s = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:                                  # noqa: BLE001
        bad.append(f"{label} 快照解析失败：{exc}")
        return None
    if not isinstance(s, dict):
        bad.append(f"{label} 快照不是 JSON 对象")
        return None
    # 键必须存在；除 inject_fault（正常轮次本就为 null）外，值还必须非空
    miss = [k for k in SUMMARY_REQUIRED if k not in s]
    if miss:
        bad.append(f"{label} 快照缺字段 {miss}")
    null_keys = [k for k in SUMMARY_REQUIRED
                 if k != "inject_fault" and k not in miss and s.get(k) is None]
    if null_keys:
        bad.append(f"{label} 快照字段为空值 {null_keys}")
    for key in ("counts_before", "counts_after", "table_delta_inserted"):
        d = s.get(key)
        if not isinstance(d, dict):
            bad.append(f"{label}.{key} 不是对象")
            continue
        miss_t = [t for t in ALL_TABLES if t not in d or not _is_int(d[t])]
        if miss_t:
            bad.append(f"{label}.{key} 缺表字段或类型非整数 {miss_t}")
    # source_stat / candidate_stat 的子字段是核验实际使用的判据 ⇒ 逐个查，缺一个就 FAIL
    for key, need in (("source_stat", SOURCE_STAT_REQUIRED),
                      ("candidate_stat", CAND_STAT_REQUIRED)):
        d = s.get(key)
        if not isinstance(d, dict):
            bad.append(f"{label}.{key} 不是对象")
            continue
        miss_sub = [k for k in need if k not in d or not _is_int(d[k])]
        if miss_sub:
            bad.append(f"{label}.{key} 缺子字段或类型非整数 {miss_sub}")
    for key in ("dry_run", "inject_fault", "assert_ok", "committed"):
        if key in s and not isinstance(s[key], (bool, type(None))):
            bad.append(f"{label}.{key} 类型不是布尔")
    return s


def v8_idempotent(cur, dbname: str, run_dir: Path) -> None:
    head("V8  幂等：两轮真实执行快照独立复算（缺字段不默认 0，逐步核对增量）")
    f1, f2 = run_dir / "run1_summary.json", run_dir / "run2_summary.json"
    bad: list[str] = []
    s1 = _load_summary(f1, "run1", bad)
    s2 = _load_summary(f2, "run2", bad)
    print(f"    快照：{f1.name} / {f2.name}（{run_dir}）")
    if bad:
        for b in bad:
            print(f"      ✗ {b}")
        record("V8", "FAIL", f"执行快照不完整，幂等性无可靠证据：{bad}")
        return

    ok_meta = True
    for label, s in (("第 1 轮", s1), ("第 2 轮", s2)):
        # 全部走 .get()：即使上游校验漏了某项也只输出 FAIL，不会抛 KeyError
        good = (s.get("db") == dbname and s.get("exit_code") == 0
                and s.get("committed") is True and s.get("assert_ok") is True
                and s.get("dry_run") is False and not s.get("inject_fault"))
        ok_meta &= bool(good)
        print(f"    {label} {s.get('run_at')}  db={s.get('db')}  exit={s.get('exit_code')}  "
              f"committed={s.get('committed')}  assert_ok={s.get('assert_ok')}  "
              f"dry_run={s.get('dry_run')}  inject_fault={s.get('inject_fault')}  {'✓' if good else '✗'}")

    # ---- 独立复算增量：Δ = after − before（不读程序自报的 table_delta_inserted 作为依据）
    print("\n    独立复算 Δ = counts_after − counts_before（并与程序自报的 table_delta_inserted 交叉核对）：")
    recomputed, selfbad = {}, []
    for label, s in (("run1", s1), ("run2", s2)):
        b, a, t = s["counts_before"], s["counts_after"], s["table_delta_inserted"]
        recomputed[label] = {tb: a[tb] - b[tb] for tb in ALL_TABLES}
        diff = {tb: (recomputed[label][tb], t.get(tb)) for tb in ALL_TABLES
                if recomputed[label][tb] != t.get(tb)}
        if diff:
            selfbad.append((label, diff))
        print(f"      {label}: " + "  ".join(
            f"{tb.replace('historical_', '')[:12]}Δ{recomputed[label][tb]:+d}" for tb in ALL_TABLES))
        if diff:
            print(f"        ✗ 与自报 table_delta_inserted 不符：{diff}")

    # ---- 首轮必须全部净增；次轮数据表净增必须全 0
    r1, r2 = recomputed["run1"], recomputed["run2"]
    zero_r1 = [t for t in DATA_TABLES if r1[t] <= 0]
    grow_r2 = [t for t in DATA_TABLES if r2[t] != 0]
    print(f"\n    首轮数据表净增为 0 或负的表：{zero_r1 or '无'}")
    print(f"    次轮数据表净增非 0 的表：{grow_r2 or '无'}")
    print(f"    次轮 import_batch 净增 {r2['import_batch']:+d}（每轮新建 7 批，属预期）")

    # ---- 链条连续性：第 1 轮 after 必须逐表等于第 2 轮 before
    chain = {tb: (s1["counts_after"][tb], s2["counts_before"][tb]) for tb in ALL_TABLES
             if s1["counts_after"][tb] != s2["counts_before"][tb]}
    print(f"    两轮衔接（run1.after == run2.before）不一致的表：{chain or '无'}")

    # ---- 独立于快照：用当前库实际行数核对第 2 轮 after
    live = {}
    for tb in ALL_TABLES:
        live[tb] = val(cur, f"SELECT count(*) FROM {tb}")
    live_diff = {tb: (live[tb], s2["counts_after"][tb]) for tb in ALL_TABLES
                 if live[tb] != s2["counts_after"][tb]}
    print(f"    当前库实际行数 vs run2.counts_after 不一致的表：{live_diff or '无'}")
    print("      " + "  ".join(f"{tb}={live[tb]:,}" for tb in ALL_TABLES))

    st = s2["source_stat"]
    no_insert = st.get("inserted") == 0 and st.get("updated") == 0
    print(f"    次轮 source_stat：{st}  ⇒ 新增 {st.get('inserted')} / 内容变更 {st.get('updated')} / "
          f"仅推进批次 {st.get('touched')} / 隔离保持 {st.get('held')}  {'✓' if no_insert else '✗'}")
    # 四类处置必须覆盖全部源记录（与当前库实际行数对账，不只看自报值）
    st_sum = sum(st.get(k, 0) for k in SOURCE_STAT_REQUIRED)
    st_ok = (st_sum == live["source_record"])
    print(f"    source_stat 四类之和 {st_sum:,} vs 库中 source_record {live['source_record']:,}"
          f"  {'✓' if st_ok else '✗'}")
    cand = s2["candidate_stat"]
    cand_ok = cand.get("inserted") == 0
    print(f"    次轮 candidate_stat：{cand}  ⇒ 新增 {cand.get('inserted')}  {'✓' if cand_ok else '✗'}")

    if not (ok_meta and not selfbad and not zero_r1 and not grow_r2 and not chain
            and not live_diff and no_insert and st_ok and cand_ok):
        record("V8", "FAIL",
               f"元数据={ok_meta} 自报不符={selfbad} 首轮无净增={zero_r1} 次轮有净增={grow_r2} "
               f"两轮断链={chain} 与库不符={live_diff} 源记录={no_insert} "
               f"源记录四类和={st_ok}({st_sum}≠{live['source_record']}) 候选={cand.get('inserted')}")
        return
    record("V8", "PASS",
           f"两轮真实执行快照字段完整（{len(SUMMARY_REQUIRED)} 个必备键 + 9 表逐表计数 + "
           f"source_stat {len(SOURCE_STAT_REQUIRED)} 个子字段 + candidate_stat {len(CAND_STAT_REQUIRED)} 个子字段齐备）；"
           f"独立复算首轮六表全净增、次轮六表净增全 0；run1.after 逐表等于 run2.before；"
           f"run2 快照与当前库实际行数逐表相等；次轮新增 0 / 内容变更 0 / 候选新增 0；"
           f"source_stat 新增+变更+推进+隔离 = {st_sum:,} = 库中源记录数")


# ------------------------------------------------------------------ V9
def v9_batch_update(cur, run_dir: Path) -> None:
    head("V9  不同批次的更新规则（last_batch_id / first_batch_id / occurrence_count）")
    cur.execute("""
        WITH latest AS (SELECT dataset_id, max(batch_id) AS bid FROM import_batch GROUP BY 1)
        SELECT count(*) FILTER (WHERE sr.last_batch_id = l.bid), count(*)
          FROM source_record sr JOIN latest l USING (dataset_id)""")
    same, tot = cur.fetchone()
    print(f"    last_batch_id 指向本数据集最新批 {same:,}/{tot:,}")
    n_gt = val(cur, "SELECT count(*) FROM source_record WHERE first_batch_id > last_batch_id")
    n_lt = val(cur, "SELECT count(*) FROM source_record WHERE first_batch_id < last_batch_id")
    n_occ = val(cur, "SELECT count(*) FROM data_quality_issue WHERE occurrence_count > 1")
    n_diff = val(cur, "SELECT count(*) FROM data_quality_issue WHERE first_batch_id <> last_batch_id")
    print(f"    first_batch_id > last_batch_id {n_gt}；first_batch_id < last_batch_id {n_lt:,}（重跑不改首见批）")
    print(f"    occurrence_count > 1 的台账行 {n_occ:,}；first_batch_id <> last_batch_id {n_diff}")

    st = {}
    f2 = run_dir / "run2_summary.json"
    if f2.exists():
        st = json.loads(f2.read_text(encoding="utf-8")).get("source_stat") or {}
    print(f"    内容更新路径（content_hash 变化 ⇒ UPDATE raw_payload）：本轮 updated = {st.get('updated')}")
    if same == tot and n_gt == 0:
        record("V9", "PASS",
               f"{tot:,} 行 last_batch_id 均指向本数据集最新批；first_batch_id 未被重跑改写")
    else:
        record("V9", "FAIL", f"仅 {same:,}/{tot:,} 指向最新批；first>last {n_gt}")
    record("V9b", "UNVERIFIED",
           f"「内容变更 ⇒ UPDATE 而非 INSERT」的更新路径**本次未走到**（两轮输入完全相同，"
           f"updated={st.get('updated')}）；需构造 content_hash 变化的第三轮才能实测，本轮不做")


# ------------------------------------------------------------------ V13
def v13_candidate_trace(cur, run_dir: Path) -> None:
    head("V13  candidate_match 排除追溯（逐条可回溯到原始 CSV 行）")
    # 优先用第 1 轮快照里登记的实际留痕路径，避免误读其他轮次的文件
    f = None
    s1 = run_dir / "run1_summary.json"
    if s1.exists():
        p = json.loads(s1.read_text(encoding="utf-8")).get("excluded_csv") or ""
        if p and Path(p).exists():
            f = Path(p)
    if f is None:
        for cand in (run_dir / "stage3_excluded_rows.csv",
                     REPORTS / "stage3_excluded_rows.csv"):
            if cand.exists():
                f = cand
                break
    if f is None:
        record("V13", "FAIL", "排除留痕文件不存在")
        return
    print(f"    留痕文件：{f}")
    trace = list(csv.DictReader(io.open(f, encoding="utf-8")))
    orig = csv_rows("candidate_matches.csv")
    print(f"    留痕 {len(trace)} 行；原始 {len(orig):,} 行")
    orig_cols = list(orig[0].keys())
    bad = []
    reasons = {}
    # ---- 留痕文件必须完整保留原始每一列（不能"缺列就当无事发生"）
    miss_cols = [c for c in orig_cols if trace and c not in trace[0]]
    print(f"    原始 {len(orig_cols)} 列在留痕中的缺失情况：{miss_cols or '无（全部保留）'}")
    if miss_cols:
        bad.append(f"留痕缺原始列 {miss_cols}")
    print(f"    留痕附加列：{[c for c in trace[0] if c not in orig_cols]}")

    # ---- 行号 / candidate_id 不得重复
    row_nos = [t.get("staging_row_no", "") for t in trace]
    ids = [t.get("candidate_id", "") for t in trace]
    dup_row = sorted({x for x in row_nos if row_nos.count(x) > 1})
    dup_id = sorted({x for x in ids if ids.count(x) > 1})
    print(f"    staging_row_no 重复 {len(dup_row)} 个 {dup_row[:5]}；candidate_id 重复 {len(dup_id)} 个 {dup_id[:5]}")
    if dup_row or dup_id:
        bad.append(f"重复 staging_row_no {dup_row[:5]} / candidate_id {dup_id[:5]}")

    orig_by_id = {r["candidate_id"]: r for r in orig}
    for t in trace:
        try:
            ln = int(t["staging_row_no"])
        except (TypeError, ValueError):
            bad.append(("staging_row_no 非法", t.get("candidate_id")))
            continue
        if not (1 <= ln <= len(orig)):
            bad.append(("行号越界", ln))
            continue
        src = orig[ln - 1]
        # 原始 19 列逐字比对（缺列已在上方整体检查，这里只看值）
        diff = [k for k in orig_cols if src[k] != t.get(k)]
        if diff:
            bad.append((t["candidate_id"], f"字段与原始行不符 {diff[:3]}"))
        if src["candidate_id"] != t["candidate_id"]:
            bad.append((t["candidate_id"], f"行号指向的候选是 {src['candidate_id']}"))
        # 收敛目标：必须能在原始 CSV 里找到，且键与被收敛行一致
        tgt = t.get("converged_to_candidate_id", "")
        reason = t.get("exclusion_reason", "")
        if reason.startswith("c09"):
            if not tgt:
                bad.append((t["candidate_id"], "c09 收敛缺少目标"))
            elif tgt not in orig_by_id:
                bad.append((t["candidate_id"], f"收敛目标 {tgt} 不在原始 CSV"))
            else:
                o = orig_by_id[tgt]
                key_self = (src["relation_type"], src["place_id_a"], src["place_id_b"])
                key_tgt = (o["relation_type"], o["place_id_a"], o["place_id_b"])
                if key_self != key_tgt:
                    bad.append((t["candidate_id"], f"收敛目标键不一致 {key_tgt}"))
        elif reason.startswith("self_reference") and tgt:
            bad.append((t["candidate_id"], f"自指行不应有收敛目标 {tgt}"))
        reasons[reason.split(":")[0]] = reasons.get(reason.split(":")[0], 0) + 1
        print(f"    #{ln:<6} {t['candidate_id']}  {t['relation_type']:26s} "
              f"{t['place_id_a']}→{t['place_id_b']}  {t['exclusion_reason']}"
              + (f"  ⇒ {tgt}" if tgt else ""))

    # ---- 收敛目标必须真的在库里（按 relation_type + 两个地点唯一键）
    n_tgt_ok = n_tgt_miss = 0
    for t in trace:
        tgt = t.get("converged_to_candidate_id", "")
        if not tgt or tgt not in orig_by_id:
            continue
        db_a, db_b = t.get("db_place_id_a"), t.get("db_place_id_b")
        hit = val(cur, """SELECT count(*) FROM candidate_match
                           WHERE relation_type = %s AND place_id_a = %s AND place_id_b = %s""",
                  (t["relation_type"], int(db_a), int(db_b))) if db_a and db_b else 0
        if hit:
            n_tgt_ok += 1
        else:
            n_tgt_miss += 1
            bad.append((t["candidate_id"], f"收敛目标 {tgt} 在库中不存在对应保留行"))
    print(f"    收敛目标在库中可定位 {n_tgt_ok} 条；定位不到 {n_tgt_miss} 条")

    n_db = val(cur, "SELECT count(*) FROM candidate_match")
    n_self = sum(1 for t in trace if t["exclusion_reason"].startswith("self_reference"))
    n_c09 = sum(1 for t in trace if t["exclusion_reason"].startswith("c09"))
    print(f"    原因分布 {reasons}；入库 {n_db:,} + 留痕 {len(trace)} = {n_db + len(trace):,}"
          f"（原始 {len(orig):,}）")
    if bad:
        record("V13", "FAIL", f"留痕与原始行对不上：{bad[:5]}")
    elif n_db + len(trace) != len(orig) or n_self != 2 or n_c09 != 4:
        record("V13", "FAIL",
               f"恒等式 {n_db}+{len(trace)}≠{len(orig)}，或自指 {n_self}≠2 / C09 {n_c09}≠4")
    else:
        record("V13", "PASS",
               f"{len(orig):,} 行 = 入库 {n_db:,} + 留痕 {len(trace)}（自指 {n_self} + C09 收敛 {n_c09}）；"
               f"留痕完整保留原始全部 {len(orig_cols)} 列且逐字相符；staging_row_no / candidate_id 均无重复；"
               f"{n_c09} 条 C09 收敛目标全部存在于原始 CSV 且在库中有对应保留行")


# ------------------------------------------------------------------ main
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--run-dir", default="",
                    help="本轮执行快照目录（run1_summary.json / run2_summary.json / 排除留痕）；"
                         "默认 ops/reports/r1_2")
    args = ap.parse_args()
    run_dir = Path(args.run_dir) if args.run_dir else (REPORTS / "r1_2")
    env = load_env()
    conn = psycopg2.connect(host="127.0.0.1", port=int(env.get("DB_HOST_PORT", "55432")),
                            dbname=args.db, user=env["POSTGRES_USER"], password=env["POSTGRES_PASSWORD"])
    conn.autocommit = True
    cur = conn.cursor()
    print(f"### 阶段三导入结果核验（R1.2）  db={args.db}  run_dir={run_dir}")
    try:
        v1_files(cur)
        v2_counts(cur, run_dir)
        v3_fk(cur)
        v4_unique(cur)
        v5_geom(cur)
        v6_views(cur)
        v7_ledger(cur)
        v8_idempotent(cur, args.db, run_dir)
        v9_batch_update(cur, run_dir)
        v12_c27_c28(cur)
        v13_candidate_trace(cur, run_dir)
    finally:
        conn.close()

    head("汇总")
    for no, st, msg in RESULTS:
        icon = {"PASS": "✓", "FAIL": "✗", "UNVERIFIED": "?", "INFO": "·"}[st]
        print(f"  {icon} {no:5s} {st:10s} {msg}")
    fails = [r for r in RESULTS if r[1] == "FAIL"]
    unv = [r for r in RESULTS if r[1] == "UNVERIFIED"]
    print(f"\n  合计 {len(RESULTS)} 项：PASS {sum(1 for r in RESULTS if r[1] == 'PASS')}"
          f" / FAIL {len(fails)} / UNVERIFIED {len(unv)}")
    return 0 if not fails else 1


if __name__ == "__main__":
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
