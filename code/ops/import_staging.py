#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""阶段三：七张暂存 CSV → PostgreSQL 导入器（V2.1.1 规则实现）。

设计依据（逐条落在下面的函数里）：
  CORE_DATA_MODEL_V2.1.1   §4.2 五段键 / §4.3 ordinal / §4.4 content_hash / §5.2.4 数据集取值
                           §5.4.2 record_scope 判定表 / §5.5.3 grain_key / §5.5.4 锚点
                           §5.9.1 台账 dataset_id 两条派生链 / §9.2 N01–N18
  IMPORT_RULES_V2.1.1      §3 先算完再写 / §4 建点白名单 / §5 重复隔离 / §6 判定表 / §9 MCGD 按组
  FIELD_MAPPING_V2.1.1     列级映射与 dropped / discarded 判定

执行纪律：
  · 全程单事务：任一派生失败 ⇒ 整批 rollback（CORE §5.3 status=failed，"一行都不许落库"）
  · 不修改 CSV / Migration / 设计文件；不为凑数插改数据
  · 可重复执行：五段键 / (dataset,grain_key) / C07 / C08 / C09 / issue_fingerprint 六处去重

用法：
  PYTHONPATH=./ops/.deps python ops/import_staging.py --db canvas_history_stage3
  PYTHONPATH=./ops/.deps python ops/import_staging.py --db canvas_history_stage3 --dry-run
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import io
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import psycopg2
from psycopg2.extras import Json, execute_values

CODE_ROOT = Path(__file__).resolve().parent.parent
STAGING = CODE_ROOT / "data" / "staging"
DERIVATION_VERSION = "v2.1.1"

CSV_FILES = {
    "data_datasets": "data_datasets.csv",
    "source_records": "source_records.csv",
    "historical_places": "historical_places.csv",
    "historical_place_names": "historical_place_names.csv",
    "historical_place_locations": "historical_place_locations.csv",
    "candidate_matches": "candidate_matches.csv",
    "data_quality_issues": "data_quality_issues.csv",
}

# ---------------------------------------------------------------- 数据源（CORE §5.1）
SOURCES = [
    ("chgis", "China Historical GIS", "https://sites.fas.harvard.edu/~chgis/",
     "CHGIS V6 时间点层（府级 / 县级）。来源文件为随包 DBF + sidecar。"),
    ("mcgd", "MCGD (Modern China Geospatial Database)", "https://doi.org/10.5281/zenodo.22094815",
     "MCGD 2026-08-25 前 960 行切片（Zenodo 22094815）。"),
    ("pleiades", "Pleiades", "https://pleiades.stoa.org/",
     "Pleiades GIS 4.1 切片：places / names / locations / connections 四个 CSV。"),
    ("whg", "World Historical Gazetteer", "https://whgazetteer.org/",
     "WHG API 抽样：geoname / getty tgn / hgis de las indias 三套。"),
]

# ---------------------------------------------------------------- 数据集（CORE §5.2.4 / §9.3）
DATASETS = {
    "chgis_v6_prefecture_points": dict(
        source_id="chgis", display_name="CHGIS V6 time_pref_pts (prefecture-level point layer)",
        dataset_version="v6", record_scopes=["place"], place_grain="per_record",
        location_grain="per_record", occurrence_key_rule="none", external_id_nature="source_declared",
        grain_evidence="5,226 条 source_record 的 record_scope 全为 place（external_id_type=chgis_sys_id）；"
                       "1 条记录 = 1 个 SYS_ID = 1 个地点 ⇒ per_record。"),
    "chgis_v6_county_points": dict(
        source_id="chgis", display_name="CHGIS V6 time_cnty_pts (county-level point layer)",
        dataset_version="v6", record_scopes=["place"], place_grain="per_record",
        location_grain="per_record", occurrence_key_rule="none", external_id_nature="source_declared",
        grain_evidence="10,522 条 source_record 的 record_scope 全为 place（external_id_type=chgis_sys_id）；"
                       "1 条记录 = 1 个 SYS_ID = 1 个地点 ⇒ per_record。"),
    "mcgd_zenodo_22094815_head960": dict(
        source_id="mcgd", display_name="MCGD (Modern China Geospatial Database) 2026-08-25, first 960 rows",
        dataset_version="2026_08_25", record_scopes=["name"], place_grain="per_parent_external_id",
        location_grain="per_parent_external_id", occurrence_key_rule="parent_ordinal",
        external_id_nature="source_declared",
        grain_evidence="960 条 record_scope=name（external_id_type=mcgd_nameid，NameID），"
                       "按 raw_payload.LocID 成组后为 643 组 ⇒ 960 → 643 个地点，故 place_grain=per_parent_external_id。"),
    "pleiades_gis_4_1_slice": dict(
        source_id="pleiades", display_name="Pleiades GIS 4.1 slice (places / names / locations / connections)",
        dataset_version="4.1", record_scopes=["place", "name", "location", "edge"],
        place_grain="per_record", location_grain="per_record", occurrence_key_rule="parent_ordinal",
        external_id_nature="source_declared",
        grain_evidence="12,445 条 = place 2,643 + name 4,579 + location 2,460 + edge 2,763；"
                       "仅 place 记录建点（2,643），name/location 经 raw_payload.place_id 挂到已存在地点 ⇒ per_record。"),
    "whg_geoname_s_gn_sample": dict(
        source_id="whg", display_name="WHG geonames sample",
        dataset_version=None, record_scopes=["place", "name", "location"], place_grain="per_record",
        location_grain="per_record", occurrence_key_rule="none", external_id_nature="pipeline_composed",
        grain_evidence="209 条 = place 4 + name 201 + location 4（external_id 由抽取管线拼装）⇒ 4 个地点，per_record。"),
    "whg_getty_tgn_sample": dict(
        source_id="whg", display_name="WHG Getty TGN sample",
        dataset_version=None, record_scopes=["place", "name", "location"], place_grain="per_record",
        location_grain="per_record", occurrence_key_rule="none", external_id_nature="pipeline_composed",
        grain_evidence="21 条 = place 1 + name 19 + location 1 ⇒ 1 个地点，per_record。"),
    "whg_hgis_de_las_indias_sample": dict(
        source_id="whg", display_name="WHG HGIS de las Indias sample",
        dataset_version=None, record_scopes=["place", "name", "location"], place_grain="per_record",
        location_grain="per_record", occurrence_key_rule="none", external_id_nature="pipeline_composed",
        grain_evidence="8 条 = place 2 + name 3 + location 3 ⇒ 2 个地点，per_record。"),
}

# ---------------------------------------------------------------- record_scope 判定表（CORE §5.4.2，11 种 external_id_type）
SCOPE_MAP = {
    ("chgis_v6_prefecture_points", "chgis_sys_id"): "place",
    ("chgis_v6_county_points", "chgis_sys_id"): "place",
    ("mcgd_zenodo_22094815_head960", "mcgd_nameid"): "name",
    ("pleiades_gis_4_1_slice", "pleiades_place_id"): "place",
    ("pleiades_gis_4_1_slice", "pleiades_name_id"): "name",
    ("pleiades_gis_4_1_slice", "pleiades_location_id"): "location",
    ("pleiades_gis_4_1_slice", "pleiades_connection_id"): "edge",
    ("whg_geoname_s_gn_sample", "whg_source_id"): "place",
    ("whg_geoname_s_gn_sample", "whg_place_name_index"): "name",
    ("whg_geoname_s_gn_sample", "whg_geometry"): "location",
    ("whg_getty_tgn_sample", "whg_source_id"): "place",
    ("whg_getty_tgn_sample", "whg_place_name_index"): "name",
    ("whg_getty_tgn_sample", "whg_geometry"): "location",
    ("whg_hgis_de_las_indias_sample", "whg_place_id"): "place",
    ("whg_hgis_de_las_indias_sample", "whg_place_name_index"): "name",
    ("whg_hgis_de_las_indias_sample", "whg_geom_index"): "location",
}

LAYER_MAP = {
    "chgis_pref": "chgis_v6_prefecture_points",
    "chgis_cnty": "chgis_v6_county_points",
    "mcgd_zenodo_22094815_head960": "mcgd_zenodo_22094815_head960",
    "pleiades_gis_4_1_slice": "pleiades_gis_4_1_slice",
}

VALID_SCOPES = {"place", "name", "location", "edge"}
SENTINEL_PARENT = "-"
RELATION_TYPES = {"same_coord_diff_entity", "homonym_diff_place", "same_entity_same_seat",
                  "location_migration_candidate", "pleiades_connection",
                  "true_duplicate_suspected", "cross_layer_disagreement"}


# ============================================================ 工具
def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    for raw in (CODE_ROOT / ".env").read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


def read_csv(name: str) -> list[dict[str, str]]:
    with io.open(STAGING / name, encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def file_sha256(name: str) -> str:
    h = hashlib.sha256()
    with open(STAGING / name, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_json(payload) -> str:
    """CORE §4.4 逐字实现：sort_keys=True, ensure_ascii=False, separators=(',',':')。"""
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def to_int(v):
    if v is None:
        return None
    v = str(v).strip()
    return int(v) if v else None


def to_float(v):
    if v is None:
        return None
    v = str(v).strip()
    return float(v) if v else None


def to_bool(v) -> bool:
    return str(v).strip().lower() in ("true", "1", "t", "yes")


BCP47 = re.compile(r"^[A-Za-z]{2,3}(-[A-Za-z0-9]{2,8})*$")


def sanitize_lang(v):
    """CORE §5.7.1 / FIELD_MAPPING sanitize：'None' ⇒ NULL；非 BCP-47 ⇒ 'und'。"""
    if v is None:
        return None, "null"
    v = str(v).strip()
    if v == "":
        return None, "empty_to_null"
    if v == "None":
        return None, "literal_None_to_null"
    if v == "und" or BCP47.match(v):
        return v, "ok"
    return "und", "non_bcp47_to_und"


def split_time_rule_code(code):
    """time_rule_code：命名时间列 ⇒ 列掩码（C13 要求此时数字规则必须为空）；数字码 ⇒ 两个 smallint。"""
    code = (code or "").strip()
    if code == "":
        return "", None, None
    if "year_after_which" in code or "year_before_which" in code:
        return code, None, None
    parts = code.split("|")
    beg = int(parts[0]) if parts[0].strip().isdigit() else None
    end = int(parts[1]) if len(parts) > 1 and parts[1].strip().isdigit() else None
    return "", beg, end


TIME_BOUND_TYPES = {"exact", "bounded", "exact_or_bounded", "tpq_taq",
                    "derived_tpq_taq", "snapshot", "unknown"}
MASK_RULE = "year_after_which|year_before_which"


def derive_time_bound_type(rule_code, from_year, to_year, staged):
    """CORE §6.1 七值域的三分支映射（V2.1.1 CHANGELOG §B.6 决策 6）。

    ① mask 分支（``time_rule_code = 'year_after_which|year_before_which'``）：
       两端相等 ⇒ 不确定性区间塌缩成点 ⇒ ``snapshot``；两端不等 ⇒ 保留暂存值
       （Pleiades 的 ``tpq_taq`` / ``bounded`` 源词汇已由暂存判定，本函数不改写）。
    ② numeric 分支（CHGIS ``'3|3'`` 一类数字码）：走 ``chgis_time_bound_type()`` 既有 7 值域
       契约，``from == to`` 是**真实零长区间**，保持 ``bounded``，不得改判。
    ③ 空码分支（源未声明）：按字段映射 ``direct`` 照抄。

    返回 (入库值, 分支标签)。分支标签只用于统计与逐行核验，不落库。
    """
    code = (rule_code or "").strip()
    f, t = to_int(from_year), to_int(to_year)
    if code == MASK_RULE:
        if f is not None and f == t:
            return "snapshot", "mask_collapse_to_snapshot"
        return staged, "mask_keep"
    if code == "":
        return staged, "empty_direct"
    return staged, "numeric_direct"


class DerivationError(Exception):
    """前置校验失败 ⇒ 整批不得落库。"""


class AssertionFailure(Exception):
    """写入后断言不成立 ⇒ 必须回滚，import_batch 不得残留 succeeded。"""


# ============================================================ 导入器
class Importer:
    def __init__(self, conn, dbname: str, operator: str, dry_run: bool = False,
                 inject_fault: str | None = None, excluded_csv: str | None = None):
        self.conn = conn
        self.cur = conn.cursor()
        self.dbname = dbname
        self.operator = operator
        self.dry_run = dry_run
        self.inject_fault = inject_fault
        self.excluded_csv = excluded_csv or str(CODE_ROOT / "ops" / "reports" / "stage3_excluded_rows.csv")
        self.warnings: list[str] = []
        self.excluded: list[dict] = []
        # IMPORT_RULES §3.2.1 / G1 恒等式所需的逐数据集计数
        self.cnt_inserted: Counter = Counter()
        self.cnt_updated: Counter = Counter()
        self.cnt_noop: Counter = Counter()
        self.cnt_blocked: Counter = Counter()
        self.updated_ids: dict[str, list[int]] = {}
        self.manual_blocks: list[tuple] = []      # (ds, sr_id, place_id, fields)
        # write_places 的四类处置计数（供 P2 人工保护断言使用，只记账、不改处理语义）
        self.place_stat: dict[str, int] = dict(inserted=0, updated=0, noop=0,
                                               protected=0, blocked=0, total=0)

    # ------------------------------------------------------------ 1. 读取 + 派生（写库前算完）
    def check_import_required(self) -> None:
        """导入级必填（IMPORT_VALIDATION_RULES.md I-01 / I-02）。

        数据库列可空 ≠ 允许空。规则在导入器里强制，写库前一次性查完，
        失败抛 DerivationError ⇒ 整批 rollback，一行不落库。
        """
        print("\n## 1b. 导入级必填校验（数据库不强制、导入器强制）")
        bad = [(r["name_id"], r["source_record_id"]) for r in self.name_rows
               if not (r.get("notes") or "").strip()]
        if bad:
            raise DerivationError(
                f"I-01 historical_place_name.notes 为空 {len(bad)} 行（示例 {bad[:5]}）⇒ 整批中止")
        print(f"  I-01 name.notes 非空：{len(self.name_rows):,}/{len(self.name_rows):,} ✓")

        bad_ds = [ds for ds, d in DATASETS.items() if not (d.get("grain_evidence") or "").strip()]
        if bad_ds:
            raise DerivationError(f"I-02 data_dataset.grain_evidence 为空：{bad_ds} ⇒ 整批中止")
        print(f"  I-02 dataset.grain_evidence 非空：{len(DATASETS)}/{len(DATASETS)} ✓")

    def build(self) -> None:
        print("## 1. 读取暂存 CSV 与实际文件指纹")
        self.sha = {}
        for _, fname in CSV_FILES.items():
            self.sha[fname] = file_sha256(fname)
            print(f"  {fname:34s} {self.sha[fname]}")

        self.ds_rows = read_csv(CSV_FILES["data_datasets"])
        self.src_rows = read_csv(CSV_FILES["source_records"])
        self.place_rows = read_csv(CSV_FILES["historical_places"])
        self.name_rows = read_csv(CSV_FILES["historical_place_names"])
        self.loc_rows = read_csv(CSV_FILES["historical_place_locations"])
        self.cand_rows = read_csv(CSV_FILES["candidate_matches"])
        self.dq_rows = read_csv(CSV_FILES["data_quality_issues"])
        self.input_counts = {
            "data_datasets": len(self.ds_rows), "source_records": len(self.src_rows),
            "historical_places": len(self.place_rows), "historical_place_names": len(self.name_rows),
            "historical_place_locations": len(self.loc_rows),
            "candidate_matches": len(self.cand_rows), "data_quality_issues": len(self.dq_rows),
        }
        print("\n  暂存原始行数：" + " / ".join(f"{k}={v:,}" for k, v in self.input_counts.items()))
        self.check_import_required()

        print("\n## 2. 派生：record_scope / parent_external_id / content_hash / duplicate_ordinal")
        self.records: list[dict] = []
        bad_scope = set()
        for r in self.src_rows:
            scope = SCOPE_MAP.get((r["dataset_id"], r["external_id_type"]))
            if scope not in VALID_SCOPES:
                bad_scope.add((r["dataset_id"], r["external_id_type"]))
                continue
            payload = json.loads(r["raw_payload_json"])
            if scope == "place":
                parent = SENTINEL_PARENT
            else:
                p = payload.get("place_id") or payload.get("LocID")
                parent = str(p) if p not in (None, "") else SENTINEL_PARENT
            canon = canonical_json(payload).encode("utf-8")
            h = hashlib.sha256(canon).digest()
            self.records.append(dict(
                sid=r["source_record_id"], ds=r["dataset_id"], scope=scope, ext=r["external_id"],
                parent=parent, idx=to_int(r["raw_record_index"]), payload=payload,
                raw_file=r["raw_file"], ingested_at=r["ingested_at"], hash=h,
                bytewise_ok=(h.hex() == hashlib.sha256(r["raw_payload_json"].encode("utf-8")).hexdigest()),
            ))
        if bad_scope:
            raise DerivationError(f"record_scope 出现未声明组合：{sorted(bad_scope)[:5]}（A12 ⇒ 整批 failed）")
        self.rec_by_sid = {x["sid"]: x for x in self.records}

        n_sent = sum(1 for x in self.records if x["parent"] == SENTINEL_PARENT)
        bytewise = sum(1 for x in self.records if x["bytewise_ok"])
        print(f"  record_scope：{len(self.records):,} 行全部命中 4 值（无第五种）")
        print(f"  parent_external_id：可派生 {len(self.records) - n_sent:,} / 落哨兵 {n_sent:,}")
        print(f"  content_hash：规范化式与逐字节式相等 {bytewise:,}/{len(self.records):,}"
              + ("  ✓" if bytewise == len(self.records) else "  ✗ H1 约定被破坏"))
        if bytewise != len(self.records):
            self.warnings.append("content_hash 规范化式与逐字节式不等，需回归 normalize.py:306")

        groups = defaultdict(list)
        for x in self.records:
            groups[(x["ds"], x["scope"], x["parent"], x["ext"])].append(x)
        for g in groups.values():
            g.sort(key=lambda x: (x["hash"], x["idx"] or 0))
            if len(g) == 1:
                g[0]["ord"] = 0
            else:
                for i, x in enumerate(g, 1):
                    x["ord"] = i
        self.multi_groups = {k: v for k, v in groups.items() if len(v) > 1}
        self.quarantine: dict[str, dict] = {}
        for g in self.multi_groups.values():
            seen = set()
            for x in g:
                if x["hash"] in seen:
                    self.quarantine[x["sid"]] = x
                else:
                    seen.add(x["hash"])
        print(f"  duplicate_ordinal：0 的 {sum(1 for x in self.records if x['ord'] == 0):,} 行；"
              f"重复组 {len(self.multi_groups)} 组 / {sum(len(v) for v in self.multi_groups.values())} 行")
        print(f"  隔离 {len(self.quarantine)} 条：{', '.join(sorted(self.quarantine))}")

        # 地点装配键（CORE §5.5.3 / §5.5.4）
        self.place_keys: dict[tuple, dict] = {}
        for x in self.records:
            if x["sid"] in self.quarantine:
                continue
            if x["scope"] == "place":
                self.place_keys[(x["ds"], x["ext"])] = x
            elif x["scope"] in ("name", "location") and \
                    DATASETS[x["ds"]]["place_grain"] == "per_parent_external_id":
                pk = (x["ds"], x["parent"])
                cur = self.place_keys.get(pk)
                if cur is None or x["ext"] < cur["ext"]:
                    self.place_keys[pk] = x            # MCGD：NameID 字典序最小者为锚点
        print(f"  grain_key：{len(self.place_keys):,} 个地点键")

        hp2key = {}
        for r in self.place_rows:
            ds = LAYER_MAP.get(r["source_dataset"])
            if ds is None:
                m = re.search(r"dataset_id=([^;]+)", r["notes"])
                ds = m.group(1).strip() if m else None
            if ds is None:
                raise DerivationError(f"places.csv {r['place_id']} 无法确定 dataset_id")
            hp2key[r["place_id"]] = (ds, r["primary_external_id"])
        derived, staged = set(self.place_keys), set(hp2key.values())
        if derived != staged:
            raise DerivationError(
                f"地点装配键不一致：派生多 {len(derived - staged)} 个 {sorted(derived - staged)[:3]}；"
                f"暂存多 {len(staged - derived)} 个 {sorted(staged - derived)[:3]}（CORE §8 校验 5/6 ⇒ 整批 failed）")
        self.hp2key = hp2key
        print(f"  暂存 places {len(hp2key):,} 行与派生键 1:1 匹配  ✓")

        # 时间类型映射（CORE §6.1 七值域 + CHANGELOG §B.6 决策 6 的三分支）
        print("\n## 2b. time_bound_type 三分支映射（mask 分支两端相等 ⇒ snapshot）")
        self.time_map: dict[tuple[str, str], tuple[str, str]] = {}
        tstat, changed = Counter(), []
        for table, rows, idcol in (("name", self.name_rows, "name_id"),
                                   ("location", self.loc_rows, "location_id")):
            for r in rows:
                val, branch = derive_time_bound_type(
                    r["time_rule_code"], r["valid_from_year_astro"],
                    r["valid_to_year_astro"], r["time_bound_type"])
                if val not in TIME_BOUND_TYPES:
                    raise DerivationError(f"time_bound_type 越出七值域：{val}（{idcol}={r[idcol]}）")
                self.time_map[(table, r[idcol])] = (val, branch)
                tstat[f"{table}|{branch}"] += 1
                if val != r["time_bound_type"]:
                    changed.append((table, r[idcol], r["time_bound_type"], val,
                                    r["valid_from_year_astro"], r["valid_to_year_astro"]))
        for k in sorted(tstat):
            print(f"  {k:34s} {tstat[k]:>7,}")
        print(f"  改判行 {len(changed)}：" + ("; ".join(
            f"{t}/{i}: {a}→{b}（{f}={t2}）" for t, i, a, b, f, t2 in changed) or "无"))
        self.time_changed = changed
        self.time_stat = dict(tstat)
        if len(changed) != 2 or {c[1] for c in changed} != {"nm_0045996", "nm_0046197"}:
            raise DerivationError(
                f"时间类型改判行与权威期望不符（期望恰 nm_0045996 / nm_0046197 两行）⇒ 整批中止：{changed}")

        # 台账 dataset_id（CORE §5.9.1：① 源记录 ② 图层键映射）
        self.dq_v2, self.dropped_licence = [], []
        for r in self.dq_rows:
            if r["issue_type"] == "licence_unconfirmed":
                self.dropped_licence.append(r["issue_id"])
                continue
            sid = (r["source_record_id"] or "").strip() or None
            ds = self.rec_by_sid[sid]["ds"] if sid else LAYER_MAP.get(r["source_dataset"])
            if ds is None:
                raise DerivationError(f"台账 {r['issue_id']} 无法派生 dataset_id（source_dataset={r['source_dataset']}）")
            self.dq_v2.append((r, ds, sid))
        print(f"  台账：{len(self.dq_rows):,} → 剔除 licence_unconfirmed {len(self.dropped_licence)} 行"
              f"（{', '.join(self.dropped_licence)}）→ 保留 {len(self.dq_v2):,} 行")

    # ------------------------------------------------------------ 2. 写库
    TABLES = ("source_record", "historical_place", "historical_place_name",
              "historical_place_location", "candidate_match", "data_quality_issue",
              "import_batch", "data_dataset", "data_source")

    def table_counts(self) -> dict[str, int]:
        out = {}
        for t in self.TABLES:
            self.cur.execute(f"SELECT count(*) FROM {t}")
            out[t] = self.cur.fetchone()[0]
        return out

    def run(self) -> None:
        started = dt.datetime.now(dt.timezone.utc)
        print(f"\n## 3. 写库（单事务）  started_at={started.isoformat(timespec='seconds')}")
        self.started = started
        self.before = self.table_counts()
        self.upsert_reference(started)
        self.create_batches(started)
        self.write_source_records(started)
        self.write_places(started)
        self.write_names(started)
        self.write_locations(started)
        self.write_candidates(started)
        self.write_ledger(started)
        self.finish_batches()
        self.assertions()
        self.write_exclusion_trace()
        self.after = self.table_counts()
        print("\n### 3.12 本事务内行数变化（提交前快照）")
        for t in self.TABLES:
            d = self.after[t] - self.before[t]
            print(f"  {t:26s} {self.before[t]:>7,} → {self.after[t]:>7,}  (Δ{d:+d})")
        if self.dry_run:
            self.conn.rollback()
            print("\n!! --dry-run：已回滚，未落库")
        else:
            self.conn.commit()
            print("\n✓ 事务已提交")

    def upsert_reference(self, started) -> None:
        print("\n### 3.1 data_source / data_dataset（幂等初始化）")
        for sid, name, homepage, notes in SOURCES:
            self.cur.execute(
                """INSERT INTO data_source (source_id, display_name, homepage_url, display_priority, notes, created_at)
                   VALUES (%s,%s,%s,0,%s,%s)
                   ON CONFLICT (source_id) DO UPDATE
                     SET display_name=EXCLUDED.display_name, homepage_url=EXCLUDED.homepage_url,
                         notes=EXCLUDED.notes""", (sid, name, homepage, notes, started))
        for ds, d in DATASETS.items():
            raw_files = sorted({x["raw_file"] for x in self.records if x["ds"] == ds})
            n_rec = sum(1 for x in self.records if x["ds"] == ds)
            self.cur.execute(
                """INSERT INTO data_dataset
                     (dataset_id, source_id, display_name, dataset_version, record_scopes,
                      place_grain, location_grain, grain_evidence, occurrence_key_rule,
                      external_id_nature, content_sha256, local_path, record_count,
                      is_active, notes, created_at, updated_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NULL,%s,%s,true,%s,%s,%s)
                   ON CONFLICT (dataset_id) DO UPDATE
                     SET display_name=EXCLUDED.display_name, dataset_version=EXCLUDED.dataset_version,
                         record_scopes=EXCLUDED.record_scopes, place_grain=EXCLUDED.place_grain,
                         location_grain=EXCLUDED.location_grain, grain_evidence=EXCLUDED.grain_evidence,
                         occurrence_key_rule=EXCLUDED.occurrence_key_rule,
                         external_id_nature=EXCLUDED.external_id_nature,
                         local_path=EXCLUDED.local_path, record_count=EXCLUDED.record_count,
                         updated_at=EXCLUDED.updated_at""",
                (ds, d["source_id"], d["display_name"], d["dataset_version"], d["record_scopes"],
                 d["place_grain"], d["location_grain"], d["grain_evidence"], d["occurrence_key_rule"],
                 d["external_id_nature"], " | ".join(raw_files), n_rec,
                 "content_sha256 留空：本轮只有归一化暂存 CSV，无按数据集切分的原始输入文件；"
                 "批次级 input_sha256 记录 source_records.csv 的实际哈希。local_path 逐字取自 "
                 "source_records.raw_file，未改写。", started, started))
        self.cur.execute("SELECT (SELECT count(*) FROM data_source), (SELECT count(*) FROM data_dataset)")
        a, b = self.cur.fetchone()
        print(f"  data_source {a} 行（期望 4） / data_dataset {b} 行（期望 7）")

    def create_batches(self, started) -> None:
        print("\n### 3.2 import_batch（每数据集 1 批，status=running）")
        self.batch_ids: dict[str, int] = {}
        sha = self.sha["source_records.csv"]
        for ds, d in DATASETS.items():
            n = sum(1 for x in self.records if x["ds"] == ds)
            self.cur.execute(
                """INSERT INTO import_batch
                     (dataset_id, dataset_version, derivation_version, status, input_file,
                      input_sha256, input_row_count, started_at, operator, notes)
                   VALUES (%s,%s,%s,'running','source_records.csv',%s,%s,%s,%s,%s)
                   RETURNING batch_id""",
                (ds, d["dataset_version"], DERIVATION_VERSION, sha, n, started, self.operator,
                 f"阶段三：record_scope / parent_external_id / duplicate_ordinal / content_hash 按 {DERIVATION_VERSION} 派生"))
            self.batch_ids[ds] = self.cur.fetchone()[0]
            print(f"  batch {self.batch_ids[ds]:>2}  {ds:34s} input_row_count={n:,}")

    def write_source_records(self, started) -> None:
        print("\n### 3.3 source_record（五段键；隔离不删行）")
        self.cur.execute(
            """SELECT dataset_id, record_scope, parent_external_id, external_id, duplicate_ordinal,
                      source_record_id, encode(content_hash,'hex'), is_active, inactive_reason
               FROM source_record""")
        existing = {r[:5]: r[5:] for r in self.cur.fetchall()}
        print(f"  库中已存在 {len(existing):,} 行")

        to_insert, upd, touch, hold = [], 0, 0, 0
        for x in self.records:
            key = (x["ds"], x["scope"], x["parent"], x["ext"], x["ord"])
            quarantined = x["sid"] in self.quarantine
            if key in existing:
                db_id, db_hash, db_active, db_reason = existing[key]
                if quarantined and not db_active and db_reason == "duplicate_quarantine":
                    # 隔离结论不重判，但"最近一次被看到"仍应推进（last_batch_id 语义）
                    self.cur.execute("UPDATE source_record SET last_batch_id=%s WHERE source_record_id=%s",
                                     (self.batch_ids[x["ds"]], db_id))
                    self.cnt_blocked[x["ds"]] += 1      # §3.2.1 成因 4：quarantine_hold（不落台账）
                    hold += 1
                    continue
                if db_hash == x["hash"].hex():
                    self.cur.execute("UPDATE source_record SET last_batch_id=%s WHERE source_record_id=%s",
                                     (self.batch_ids[x["ds"]], db_id))
                    self.cnt_noop[x["ds"]] += 1
                    touch += 1
                else:
                    self.cur.execute(
                        """UPDATE source_record SET raw_payload=%s, content_hash=%s,
                               last_batch_id=%s, ingested_at=%s WHERE source_record_id=%s""",
                        (Json(x["payload"]), x["hash"], self.batch_ids[x["ds"]], x["ingested_at"], db_id))
                    self.cnt_updated[x["ds"]] += 1
                    self.updated_ids.setdefault(x["ds"], []).append(db_id)
                    upd += 1
                continue
            to_insert.append(x)

        rows = []
        for x in to_insert:
            bid = self.batch_ids[x["ds"]]
            q = x["sid"] in self.quarantine
            rows.append((x["ds"], x["scope"], x["ext"], x["parent"], x["ord"], x["raw_file"], x["idx"],
                         Json(x["payload"]), x["hash"], bid, bid, not q,
                         "duplicate_quarantine" if q else None, started if q else None,
                         bid if q else None, x["ingested_at"]))
        if rows:
            execute_values(self.cur,
                """INSERT INTO source_record
                     (dataset_id, record_scope, external_id, parent_external_id, duplicate_ordinal,
                      raw_file, raw_record_index, raw_payload, content_hash,
                      first_batch_id, last_batch_id, is_active,
                      inactive_reason, inactive_at, inactive_in_batch_id, ingested_at)
                   VALUES %s""", rows, page_size=2000)
        for r in rows:
            self.cnt_inserted[r[0]] += 1
        self.cur.execute(
            """SELECT dataset_id, record_scope, parent_external_id, external_id, duplicate_ordinal,
                      source_record_id FROM source_record""")
        self.sr_map = {r[:5]: r[5] for r in self.cur.fetchall()}
        self.src_stat = dict(inserted=len(rows), updated=upd, touched=touch, held=hold)
        print(f"  新增 {len(rows):,} / 内容变更 {upd} / 仅触 last_batch_id {touch:,} / 隔离保持 {hold}；"
              f"库中合计 {len(self.sr_map):,}")

    def _anchor_id(self, x) -> int:
        return self.sr_map[(x["ds"], x["scope"], x["parent"], x["ext"], x["ord"])]

    def _sr_id(self, sid):
        if not sid:
            return None
        x = self.rec_by_sid.get(sid)
        return self._anchor_id(x) if x else None

    def write_places(self, started) -> None:
        print("\n### 3.4 historical_place（每地点恰好 1 条锚点）")
        self.cur.execute("""SELECT place_id, dataset_id, grain_key, canonical_name, locked,
                                   created_by, merged_into_place_id, manual_edited_fields
                             FROM historical_place""")
        existing = {r[1:3]: r for r in self.cur.fetchall()}
        rows, upd, skip, n_block = [], 0, 0, 0
        for r in self.place_rows:
            ds, grain = self.hp2key[r["place_id"]]
            anchor = self._anchor_id(self.place_keys[(ds, grain)])
            m = re.search(r"place_type_basis=([^;]+)", r["notes"])
            basis = m.group(1).strip() if m else None
            if ds.startswith("chgis"):
                pts = "lev_rank_unmapped" if basis == "lev_rank_unmapped" else "lev_rank"
                note = basis
            elif ds.startswith("mcgd"):
                pts, note = "source_code_unconfirmed", "code_meaning_unconfirmed"
            else:
                pts, note = "unknown", None
            if (ds, grain) in existing:
                db = existing[(ds, grain)]
                fields = list(db[7] or [])
                # IMPORT_RULES §3.2.1 成因 1/2/3：created_by=manual / locked / manual_edited_fields
                if db[5] == "manual" or db[4] or fields or db[6] is not None:
                    if db[3] != r["canonical_name"]:
                        why = []
                        if db[5] == "manual":
                            why.append("created_by=manual")
                        if db[4]:
                            why.append("locked")
                        if fields:
                            why.append("manual_edited_fields=" + ",".join(fields))
                        if db[6] is not None:
                            why.append("merged")
                        anc = self.place_keys.get((ds, grain))
                        self.manual_blocks.append(
                            (ds, self._anchor_id(anc) if anc else None, db[0],
                             "|".join(why) or "manual_edited_fields",
                             db[3], r["canonical_name"]))
                        self.cnt_blocked[ds] += 1
                        n_block += 1
                    skip += 1
                    continue
                if db[3] != r["canonical_name"]:
                    self.cur.execute(
                        """UPDATE historical_place SET canonical_name=%s, canonical_name_lang=%s,
                               place_type=%s, place_type_source=%s, place_type_basis_note=%s,
                               notes=%s, updated_at=%s WHERE place_id=%s""",
                        (r["canonical_name"], r["canonical_name_lang"] or None, r["place_type"],
                         pts, note, r["notes"], started, db[0]))
                    upd += 1
                continue
            rows.append((ds, grain, r["canonical_name"], r["canonical_name_lang"] or None,
                         r["place_type"], pts, note, r["record_status"], anchor, "import",
                         to_bool(r["locked"]), "{}", r["created_at"], r["created_at"], r["notes"]))
        if rows:
            execute_values(self.cur,
                """INSERT INTO historical_place
                     (dataset_id, grain_key, canonical_name, canonical_name_lang, place_type,
                      place_type_source, place_type_basis_note, record_status,
                      created_from_source_record_id, created_by, locked, manual_edited_fields,
                      created_at, updated_at, notes)
                   VALUES %s""", rows, page_size=2000)
        self.cur.execute("SELECT place_id, dataset_id, grain_key FROM historical_place")
        self.place_map = {(r[1], r[2]): r[0] for r in self.cur.fetchall()}
        self.hp2place = {hp: self.place_map[k] for hp, k in self.hp2key.items()}
        self.place_stat = dict(inserted=len(rows), updated=upd, protected=skip, blocked=n_block,
                               total=len(self.place_rows),
                               noop=len(self.place_rows) - len(rows) - upd - skip)
        print(f"  新增 {len(rows):,} / 内容变更 {upd} / 无变化 {self.place_stat['noop']:,} / "
              f"人工保护跳过 {skip}（其中名称冲突登记台账 {n_block}）；库中合计 {len(self.place_map):,}")

    def write_names(self, started) -> None:
        print("\n### 3.5 historical_place_name")
        # 去重键必须用库内自增主键（C08 四段），不能用暂存的 sr_xxx 业务标识
        self.cur.execute("SELECT source_record_id, name_type, name_text, name_lang FROM historical_place_name")
        have = set(self.cur.fetchall())
        rows, fix, skip = [], Counter(), 0
        for r in self.name_rows:
            if r["source_record_id"] in self.quarantine:
                skip += 1
                continue
            lang, how = sanitize_lang(r["name_lang"])
            fix[how] += 1
            rec = self.rec_by_sid[r["source_record_id"]]
            anchor = self._anchor_id(rec)
            if (anchor, r["name_type"], r["name"], lang) in have:
                continue
            mask, _b, _e = split_time_rule_code(r["time_rule_code"])
            cert = rec["payload"].get("association_certainty")
            ttype, _branch = self.time_map[("name", r["name_id"])]
            notes = (r.get("notes") or "").strip()
            if not notes:
                raise DerivationError(f"I-01 写入前复检失败：name_id={r['name_id']} notes 为空")
            rows.append((self.hp2place[r["place_id"]], anchor, r["name"], lang,
                         r["name_script"] or None, r["name_type"], r["transliteration_scheme"] or None,
                         to_int(r["valid_from_year_astro"]), to_int(r["valid_to_year_astro"]),
                         ttype, cert if cert in ("certain", "less-certain", "uncertain") else None,
                         mask, notes, started, started))
        if rows:
            execute_values(self.cur,
                """INSERT INTO historical_place_name
                     (place_id, source_record_id, name_text, name_lang, name_script, name_type,
                      transliteration_scheme, valid_from_year_astro, valid_to_year_astro,
                      time_bound_type, association_certainty, source_time_columns, notes,
                      created_at, updated_at)
                   VALUES %s""", rows, page_size=2000)
        print(f"  新增 {len(rows):,}；隔离源跳过 {skip}；name_lang 处置 {dict(fix)}")

    def write_locations(self, started) -> None:
        print("\n### 3.6 historical_place_location")
        self.cur.execute("SELECT source_record_id FROM historical_place_location WHERE source_record_id IS NOT NULL")
        have = {r[0] for r in self.cur.fetchall()}
        rows, skip, crs_fix = [], 0, Counter()
        for r in self.loc_rows:
            if r["source_record_id"] in self.quarantine:
                skip += 1
                continue
            rec = self.rec_by_sid[r["source_record_id"]]
            srid = self._anchor_id(rec)
            if srid in have:
                continue
            lon, lat = to_float(r["lon"]), to_float(r["lat"])
            oc = (r["original_crs"] or "").strip()
            derived = "confirmed" if oc == "EPSG:4326" else "unknown"
            if derived != r["crs_confidence"]:
                crs_fix[f"{r['crs_confidence']}→{derived}"] += 1
            mask, beg, end = split_time_rule_code(r["time_rule_code"])
            unc = to_float(r["uncertainty_m"])
            ttype, _branch = self.time_map[("location", r["location_id"])]
            rows.append((self.hp2place[r["place_id"]], srid, lon, lat, r["original_x"], r["original_y"],
                         oc or None, derived, to_bool(r["axis_order_verified"]),
                         "precise" if r["location_precision"] == "precise" else "unknown",
                         int(round(unc)) if unc is not None else None,
                         to_int(r["valid_from_year_astro"]), to_int(r["valid_to_year_astro"]),
                         ttype, beg, end, mask, r["notes"], started, started))
        if rows:
            execute_values(self.cur,
                """INSERT INTO historical_place_location
                     (place_id, source_record_id, representative_lon, representative_lat,
                      original_x, original_y, original_crs, crs_confidence, axis_order_verified,
                      location_precision, uncertainty_m, valid_from_year_astro, valid_to_year_astro,
                      time_bound_type, source_beg_rule, source_end_rule, source_time_columns,
                      notes, created_at, updated_at)
                   VALUES %s""", rows, page_size=1000)
            self.cur.execute(
                """UPDATE historical_place_location
                      SET geom=ST_SetSRID(ST_MakePoint(representative_lon, representative_lat),4326),
                          geom_type='Point'
                    WHERE geom IS NULL AND representative_lon IS NOT NULL
                      AND representative_lat IS NOT NULL AND source_record_id IS NOT NULL""")
        print(f"  新增 {len(rows):,}；隔离源跳过 {skip}；crs_confidence 由 original_crs 重派 {dict(crs_fix)}")

    def write_candidates(self, started) -> None:
        print("\n### 3.7 candidate_match")
        # C09 收敛：同一 (relation_type, place_id_a, place_id_b) 在**暂存文件内**重复出现。
        # 先按文件内定序算出"保留首行、其余收敛"，跑第几轮都与库状态无关 ⇒ 留痕可复现。
        seen_csv: dict[tuple, str] = {}
        c09_ids: dict[str, str] = {}
        for i, r in enumerate(self.cand_rows, 1):
            k = (r["relation_type"], r["place_id_a"], r["place_id_b"])
            if k in seen_csv:
                c09_ids[r["candidate_id"]] = seen_csv[k]
            else:
                seen_csv[k] = r["candidate_id"]
        del seen_csv

        self.cur.execute("SELECT relation_type, place_id_a, place_id_b FROM candidate_match")
        have = set(self.cur.fetchall())
        have_before = bool(have)
        rows, rewritten, excluded = [], Counter(), []
        self_ref = c09 = 0
        for i, r in enumerate(self.cand_rows, 1):
            rt = r["relation_type"]
            if rt not in RELATION_TYPES:
                raise DerivationError(f"candidate_match relation_type 越界：{rt}")
            a, b = self.hp2place[r["place_id_a"]], self.hp2place[r["place_id_b"]]
            # CORE §5.8 表级 CHECK (place_id_a <> place_id_b)：同一 SYS_ID 内部重复无法表达为
            # 两个不同地点 ---- 该事实已由 duplicate_sysid 台账 + duplicate_ordinal 隔离承载。
            if a == b:
                self_ref += 1
                excluded.append(dict(r, staging_row_no=i,
                                     exclusion_reason="self_reference:place_id_a==place_id_b",
                                     db_place_id_a=a, db_place_id_b=b, converged_to_candidate_id=""))
                continue
            if r["candidate_id"] in c09_ids:
                c09 += 1
                excluded.append(dict(r, staging_row_no=i,
                                     exclusion_reason="c09_converged:同(relation_type,place_id_a,place_id_b)已有保留行",
                                     db_place_id_a=a, db_place_id_b=b,
                                     converged_to_candidate_id=c09_ids[r["candidate_id"]]))
                continue
            if (rt, a, b) in have:
                # 上一轮已入库（同库重跑）⇒ 不是本轮排除，不进留痕文件
                continue
            have.add((rt, a, b))
            status, reviewer, reviewed_at = r["status"], None, None
            if rt == "pleiades_connection":
                status = "confirmed"
                reviewer = "system:source_attested"
                ra = self.rec_by_sid.get(r["source_record_id_a"])
                reviewed_at = ra["ingested_at"] if ra else None
                rewritten[f"{r['status']}→confirmed"] += 1
            evidence = {
                "source_text": r["evidence"],
                "name_a": r["name_a"], "lon_a": to_float(r["lon_a"]), "lat_a": to_float(r["lat_a"]),
                "name_b": r["name_b"], "lon_b": to_float(r["lon_b"]), "lat_b": to_float(r["lat_b"]),
                "same_name": to_bool(r["same_name"]),
            }
            rows.append((rt, a, self._sr_id(r["source_record_id_a"]), b,
                         self._sr_id(r["source_record_id_b"]), to_float(r["distance_m"]), Json(evidence),
                         r["confidence"], status, reviewer, reviewed_at, "none", started, started))
        if rows:
            execute_values(self.cur,
                """INSERT INTO candidate_match
                     (relation_type, place_id_a, source_record_id_a, place_id_b, source_record_id_b,
                      distance_m, evidence, confidence, status, reviewer, reviewed_at, direction,
                      created_at, updated_at)
                   VALUES %s""", rows, page_size=1000)
        self.cand_stat = dict(staging=len(self.cand_rows), inserted=len(rows),
                              self_ref=self_ref, c09=c09)
        self.dump_excluded(excluded)
        print(f"  暂存 {len(self.cand_rows):,} 行 → 本轮入库 {len(rows):,}"
              f"（不按 U18 过滤）；自指跳过 {self_ref} / CSV 内 C09 收敛 {c09}"
              f"（= {len(excluded)} 行留痕）；status 改写 {dict(rewritten) or '无'}")
        self.cur.execute("SELECT count(*) FROM candidate_match")
        n_db = self.cur.fetchone()[0]
        print(f"  库中 candidate_match {n_db:,} 行；恒等式 {len(self.cand_rows):,} − {len(excluded)} = "
              f"{len(self.cand_rows) - len(excluded):,}")
        if not have_before and len(rows) != len(self.cand_rows) - len(excluded):
            raise AssertionError(
                f"候选表恒等式不成立（空库首轮）：入库 {len(rows)} ≠ {len(self.cand_rows)} − {len(excluded)}")

    def dump_excluded(self, skipped: list[dict]) -> None:
        """被判据挡下的暂存行逐字留痕，不静默丢弃。"""
        self.excluded.extend(skipped)

    def write_exclusion_trace(self) -> None:
        if not self.excluded:
            return
        out = Path(self.excluded_csv)
        out.parent.mkdir(parents=True, exist_ok=True)
        cols = list(self.excluded[0].keys())
        with io.open(out, "w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=cols)
            w.writeheader()
            w.writerows(self.excluded)
        print(f"\n### 3.11 未入库暂存行留痕 → {self.excluded_csv}（{len(self.excluded)} 行）")

    def write_ledger(self, started) -> None:
        print("\n### 3.8 data_quality_issue")
        rows = []
        for r, ds, sid in self.dq_v2:
            bid = self.batch_ids[ds]
            rows.append((ds, self._sr_id(sid), None, r["issue_type"], r["severity"],
                         r["field_name"] or "", r["observed_value"] or None,
                         r["expected_rule"] or None, r["action_taken"],
                         bid, bid, bid, 1, started, r["notes"] or None))
        n_staging = len(rows)

        # +5：多行组中"暂存尚无 duplicate_sysid"的组 ⇒ 1 组 1 行 duplicate_external_id
        dup_sysid = {r["observed_value"] for r, _d, _s in self.dq_v2 if r["issue_type"] == "duplicate_sysid"}
        n_dup = 0
        for (ds, scope, parent, ext), g in self.multi_groups.items():
            if ext in dup_sysid:
                continue
            x = g[-1]
            bid = self.batch_ids[ds]
            identical = len({y["hash"] for y in g}) == 1
            rows.append((ds, self._anchor_id(x), self._place_of(x), "duplicate_external_id", "warning",
                         "external_id",
                         f"external_id={ext}|parent={parent}|n={len(g)}|"
                         f"content={'identical' if identical else 'divergent'}",
                         "同一四段前缀组出现多行；同 hash 子组仅保留最小 ordinal，其余置 duplicate_quarantine",
                         "preserved_and_flagged", bid, bid, bid, 1, started,
                         f"按 IMPORT_RULES {DERIVATION_VERSION} §5.1 重复隔离算法产生；不删除任何源记录"))
            n_dup += 1

        # +197：地点级时间重算 vs 暂存值（只聚合 name+location，排除 edge）
        agg = defaultdict(lambda: [None, None])
        for r in self.name_rows + self.loc_rows:
            if r["source_record_id"] in self.quarantine:
                continue
            a = agg[r["place_id"]]
            for i, c in ((0, "valid_from_year_astro"), (1, "valid_to_year_astro")):
                v = to_int(r[c])
                if v is None:
                    continue
                a[i] = v if a[i] is None else (min(a[i], v) if i == 0 else max(a[i], v))
        n_mis, mis_places = 0, set()
        for r in self.place_rows:
            a = agg.get(r["place_id"], [None, None])
            for i, c in ((0, "valid_from_year_astro"), (1, "valid_to_year_astro")):
                sv = to_int(r[c])
                if sv == a[i]:
                    continue
                ds = self.hp2key[r["place_id"]][0]
                bid = self.batch_ids[ds]
                rows.append((ds, None, self.hp2place[r["place_id"]], "derived_value_mismatch", "warning",
                             c, str(sv) if sv is not None else None,
                             "地点级时间 = 仅 name+location 子行包络（排除 edge/connection；过滤 rejected 与失效源）",
                             "preserved_and_flagged", bid, bid, bid, 1, started,
                             f"重算值={a[i]}; 暂存值={sv}"))
                n_mis += 1
                mis_places.add(r["place_id"])

        # +N：人工保护位挡住的地点（IMPORT_RULES §3.2.1 成因 1/2/3 ⇒ 一行一条 manual_edit_conflict）
        for ds, srid_, pid, why, old, new in self.manual_blocks:
            bid = self.batch_ids[ds]
            rows.append((ds, srid_, pid, "manual_edit_conflict", "warning", "",
                         f"staged={new}",
                         "locked / created_by=manual / 已合并的行不得被机器覆盖（人工保护位优先）",
                         "preserved_and_flagged", bid, bid, bid, 1, started,
                         f"保护原因={why}; 库中现值={old}; 导入值={new}"))

        execute_values(self.cur,
            """INSERT INTO data_quality_issue
                 (dataset_id, source_record_id, place_id, issue_type, severity, field_name,
                  observed_value, expected_rule, action_taken, batch_id, first_batch_id, last_batch_id,
                  occurrence_count, created_at, resolution_note)
               VALUES %s
               ON CONFLICT (issue_fingerprint) DO UPDATE
                 SET last_batch_id = EXCLUDED.last_batch_id,
                     occurrence_count = data_quality_issue.occurrence_count + 1""",
            rows, page_size=1000)
        self.dq_stat = dict(staging=n_staging, dup=n_dup, mismatch=n_mis, places=len(mis_places),
                            manual=len(self.manual_blocks))
        print(f"  暂存 {n_staging:,} + duplicate_external_id {n_dup} + derived_value_mismatch {n_mis}"
              f"（{len(mis_places)} 个地点）+ manual_edit_conflict {len(self.manual_blocks)}"
              f" = {n_staging + n_dup + n_mis + len(self.manual_blocks):,}")
        self.cur.execute("SELECT count(*), count(DISTINCT issue_fingerprint) FROM data_quality_issue")
        t, u = self.cur.fetchone()
        print(f"  库中 {t:,} 行 / 唯一指纹 {u:,}" + ("  ✓" if t == u else "  ✗ 指纹冲突"))

    def _place_of(self, x):
        if x["scope"] == "place":
            return self.place_map.get((x["ds"], x["ext"]))
        if x["scope"] in ("name", "location"):
            return self.place_map.get((x["ds"], x["parent"]))
        return None

    def assertions(self) -> None:
        print("\n### 3.9 幂等断言 A1–A9（IMPORT_RULES §1.3）+ G1 恒等式（ROLLBACK §3.2）")
        all_ok = True
        for ds, bid in self.batch_ids.items():
            c = self.cur
            c.execute("""SELECT input_row_count, coalesce(failed_count,0), quarantined_count,
                                coalesce(skipped_count,0), coalesce(blocked_count,0),
                                coalesce(array_length(updated_source_record_ids,1),0),
                                coalesce(array_length(inserted_source_record_ids,1),0)
                           FROM import_batch WHERE batch_id=%s""", (bid,))
            n_in, n_fail, n_quar, n_noop, n_block, n_upd, n_ins_arr = c.fetchone()
            c.execute("SELECT count(*) FROM source_record WHERE first_batch_id=%s", (bid,))
            a1 = c.fetchone()[0]
            c.execute("SELECT count(*) FROM source_record WHERE first_batch_id=%s AND is_active", (bid,))
            n_ins = c.fetchone()[0]
            c.execute("""SELECT count(*) FILTER (WHERE is_active), count(*) FILTER (WHERE NOT is_active)
                           FROM source_record WHERE dataset_id=%s""", (ds,))
            act, inact = c.fetchone()
            c.execute("""SELECT count(*) FROM (SELECT 1 FROM source_record WHERE dataset_id=%s
                          GROUP BY dataset_id, record_scope, parent_external_id, external_id, duplicate_ordinal
                          HAVING count(*)>1) t""", (ds,))
            a3 = c.fetchone()[0]
            c.execute("""SELECT count(*) FROM source_record WHERE dataset_id=%s AND
                          (parent_external_id IS NULL OR parent_external_id='' OR duplicate_ordinal IS NULL)""", (ds,))
            a789 = c.fetchone()[0]
            c.execute("""SELECT count(*) FROM data_quality_issue WHERE batch_id=%s AND issue_type='import_row_error'""", (bid,))
            a5 = c.fetchone()[0]
            c.execute("SELECT count(*) FROM source_record WHERE first_batch_id=%s AND NOT is_active", (bid,))
            a6 = c.fetchone()[0]
            ok = (a3 == 0 and a789 == 0 and a5 == n_fail and act + inact == n_in and a1 <= n_in)
            # G1：input_row_count = N_fail_import + N_quar + N_inserted + N_updated + N_noop + N_blocked
            g1_rhs = n_fail + n_quar + n_ins + n_upd + n_noop + n_block
            g1 = g1_rhs == n_in
            a1v = a1 == n_ins_arr          # A1：数组长度 == 该批落库行数
            ok = ok and g1 and a1v
            all_ok &= ok
            print(f"  {'✓' if ok else '✗'} {ds:34s} A1 {a1:>6,}/{n_in:<6,}"
                  f" G1 {n_in:,} = 失败{n_fail} + 隔离{n_quar} + 新增{n_ins:,} + 更新{n_upd}"
                  f" + 无变化{n_noop:,} + 跳过{n_block}"
                  f" → {'平衡' if g1 else f'不平衡({g1_rhs})'}"
                  f"{'' if a1v else ' ✗A1数组'}")
            if a3 or a789:
                print(f"      重键={a3} 缺段={a789}  ✗")
        c = self.cur
        c.execute("SELECT count(*), count(*) FILTER (WHERE NOT is_active), count(*) FILTER (WHERE duplicate_ordinal=0) FROM source_record")
        t, ina, z = c.fetchone()
        print(f"  合计 source_record {t:,}（活性 {t - ina:,} / 隔离 {ina}）；duplicate_ordinal=0 {z:,}")
        src_ok = all_ok
        if self.inject_fault:
            print(f"\n  ⚠ 受控故障注入 --inject-fault={self.inject_fault}：强制断言失败（仅用于回滚路径验证）")
            src_ok = False

        time_ok = self.assert_time_types()
        self.assert_ok = src_ok and time_ok
        print(f"\n  批次断言 {'✓ 通过' if src_ok else '✗ 失败'}"
              f"；时间类型断言 {'✓ 通过' if time_ok else '✗ 失败'}")
        if not self.assert_ok:
            raise AssertionFailure(
                f"断言未全部通过（批次={src_ok}, 时间类型={time_ok}）⇒ 整批回滚，不得提交")

    def _name_of(self, name_id: str) -> str:
        for r in self.name_rows:
            if r["name_id"] == name_id:
                return r["name"]
        raise DerivationError(f"暂存中无 name_id={name_id}")

    def assert_time_types(self) -> bool:
        """A10：时间类型映射（七值域 / 三分支 / 分布 / 逐行核验）。"""
        print("\n### 3.9b 时间类型断言 A10（CORE §6.1 + CHANGELOG §B.6 决策 6）")
        c = self.cur
        ok = True
        q = [
            ("F17a mask 分支两端相等却非 snapshot",
             "SELECT count(*) FROM historical_place_name WHERE source_time_columns = %s"
             " AND valid_from_year_astro = valid_to_year_astro AND time_bound_type <> 'snapshot'",
             (MASK_RULE,)),
            ("F17a' mask 分支两端不等却是 snapshot",
             "SELECT count(*) FROM historical_place_name WHERE source_time_columns = %s"
             " AND valid_from_year_astro <> valid_to_year_astro AND time_bound_type = 'snapshot'",
             (MASK_RULE,)),
            ("F17b 数字分支两端相等仍 bounded（期望 17）",
             "SELECT count(*) FROM historical_place_name WHERE source_time_columns = ''"
             " AND valid_from_year_astro = valid_to_year_astro"
             " AND time_bound_type = 'bounded'", ()),
            ("location 七值域外",
             "SELECT count(*) FROM historical_place_location WHERE time_bound_type NOT IN"
             " ('exact','bounded','exact_or_bounded','tpq_taq','derived_tpq_taq','snapshot','unknown')", ()),
            ("name 七值域外",
             "SELECT count(*) FROM historical_place_name WHERE time_bound_type NOT IN"
             " ('exact','bounded','exact_or_bounded','tpq_taq','derived_tpq_taq','snapshot','unknown')", ()),
        ]
        for label, sql, args in q:
            c.execute(sql, args)
            n = c.fetchone()[0]
            print(f"  {label:40s} {n}")
            if label.startswith("F17b"):
                ok &= (n == 17)
            elif n:
                ok = False

        # 分布逐类型比对：期望值由「暂存行 − 隔离行」经映射算出，不写死数字
        for table, rows, idcol, tb in (
                ("historical_place_name", self.name_rows, "name_id", "name"),
                ("historical_place_location", self.loc_rows, "location_id", "location")):
            exp = Counter()
            for r in rows:
                if r["source_record_id"] in self.quarantine:
                    continue
                exp[self.time_map[(tb, r[idcol])][0]] += 1
            c.execute(f"SELECT time_bound_type, count(*) FROM {table} GROUP BY 1")
            db = dict(c.fetchall())
            diff = {k: (db.get(k, 0), exp.get(k, 0)) for k in set(db) | set(exp)
                    if db.get(k, 0) != exp.get(k, 0)}
            fmt = lambda d: " ".join(f"{k}={v:,}" for k, v in sorted(d.items(), key=lambda x: -x[1]))
            print(f"  {table:24s} 期望 {fmt(exp)}")
            print(f"  {'':24s} 实际 {fmt(db)}" + ("  ✓" if not diff else f"  ✗ 差异 {diff}"))
            if diff:
                ok = False

        # 逐行核验两条改判记录
        for nid, tail in (("nm_0045996", "Boxar"), ("nm_0046197", "Catife")):
            c.execute("""SELECT n.name_text, p.canonical_name, n.valid_from_year_astro,
                                n.valid_to_year_astro, n.time_bound_type, n.source_time_columns, n.notes
                           FROM historical_place_name n JOIN historical_place p USING (place_id)
                          WHERE n.name_text = %s AND n.source_time_columns = %s""",
                      (self._name_of(nid), MASK_RULE))
            r = c.fetchone()
            if not r:
                print(f"  ✗ 逐行核验 {nid}：库中查无此行")
                ok = False
                continue
            nm, canon, f, t2, ttype, mask, notes = r
            good = (ttype == "snapshot" and f == 1500 and t2 == 1500
                    and mask == MASK_RULE and bool((notes or "").strip()))
            print(f"  {'✓' if good else '✗'} 逐行核验 {nid}「{nm}」({canon}) "
                  f"{f}–{t2} → time_bound_type={ttype} source_time_columns={mask} "
                  f"notes={'非空' if notes else '空'}")
            ok = bool(ok) and bool(good)
        return bool(ok)

    def finish_batches(self) -> None:
        print("\n### 3.10 批次收尾（六列计数按 G1 各集合独立取数）")
        for ds, bid in self.batch_ids.items():
            self.cur.execute("SELECT count(*) FILTER (WHERE NOT is_active), array_agg(source_record_id) "
                             "FROM source_record WHERE first_batch_id=%s", (bid,))
            quar, ids = self.cur.fetchone()
            self.cur.execute(
                """UPDATE import_batch SET status='succeeded', finished_at=now(),
                       inserted_source_record_ids=%s, updated_source_record_ids=%s,
                       quarantined_count=%s, skipped_count=%s, failed_count=0, blocked_count=%s
                     WHERE batch_id=%s""",
                (ids or [], self.updated_ids.get(ds) or None, quar or 0,
                 self.cnt_noop[ds], self.cnt_blocked[ds], bid))
            print(f"  batch {bid:>2} {ds:34s} succeeded  inserted={len(ids or []):,}"
                  f" updated={len(self.updated_ids.get(ds) or [])} quarantined={quar or 0}"
                  f" noop={self.cnt_noop[ds]:,} blocked={self.cnt_blocked[ds]}")


# ============================================================ main
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--operator", default="ops/import_staging.py")
    ap.add_argument("--inject-fault", default="",
                    help="受控故障注入（仅用于验证断言失败→回滚路径；正常导入不得使用）")
    ap.add_argument("--summary-json", default="",
                    help="把本次事务前后行数快照写入 JSON（供幂等性取证）")
    ap.add_argument("--excluded-csv", default="",
                    help="未入库暂存行的逐条留痕路径（默认 ops/reports/stage3_excluded_rows.csv）")
    args = ap.parse_args()

    env = load_env()
    conn = psycopg2.connect(host="127.0.0.1", port=int(env.get("DB_HOST_PORT", "55432")),
                            dbname=args.db, user=env["POSTGRES_USER"], password=env["POSTGRES_PASSWORD"])
    conn.autocommit = False
    print(f"### 阶段三导入  db={args.db}  derivation_version={DERIVATION_VERSION}"
          + (f"  [DRY-RUN]" if args.dry_run else "")
          + (f"  [INJECT-FAULT={args.inject_fault}]" if args.inject_fault else ""))
    imp = Importer(conn, args.db, args.operator, args.dry_run, args.inject_fault or None,
                   args.excluded_csv or None)
    code = 0
    try:
        imp.build()
        imp.run()
    except DerivationError as exc:
        conn.rollback()
        print(f"\n✗ 前置校验失败，整批回滚（一行未落库）：{exc}")
        code = 2
    except AssertionFailure as exc:
        conn.rollback()
        print(f"\n✗ 断言失败，整批回滚（import_batch 未残留 succeeded）：{exc}")
        code = 3
    except Exception:
        conn.rollback()
        print("\n✗ 异常，已回滚")
        raise
    finally:
        conn.close()
    if imp.warnings:
        print("\n警告：")
        for w in imp.warnings:
            print(f"  - {w}")

    if args.summary_json:
        out = Path(args.summary_json)
        out.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "db": args.db,
            "run_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "derivation_version": DERIVATION_VERSION,
            "dry_run": args.dry_run,
            "inject_fault": args.inject_fault or None,
            "exit_code": code,
            "committed": code == 0 and not args.dry_run,
            "counts_before": getattr(imp, "before", None),
            "counts_after": getattr(imp, "after", None),
            "assert_ok": getattr(imp, "assert_ok", None),
            "staging_rows": imp.input_counts,
            "excluded_csv": imp.excluded_csv,
            "quarantine_ids": sorted(getattr(imp, "quarantine", {})),
            "source_stat": getattr(imp, "src_stat", None),
            "candidate_stat": getattr(imp, "cand_stat", None),
            "ledger_stat": getattr(imp, "dq_stat", None),
            "time_changed": [list(x) for x in getattr(imp, "time_changed", [])],
            "table_delta_inserted": (
                {t: imp.after[t] - imp.before[t] for t in Importer.TABLES}
                if getattr(imp, "after", None) and getattr(imp, "before", None) else None),
        }
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n取证快照 → {args.summary_json}")
    return code


if __name__ == "__main__":
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
