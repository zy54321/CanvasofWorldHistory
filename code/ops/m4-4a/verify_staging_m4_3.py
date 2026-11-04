#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""M4-4a 交付核验：逐条核对 ``code/data/staging_m4_3`` 的七张 CSV。

不连数据库。所有判据要么来自**源数据现场重算**，要么来自 Owner 给的对照基线；
任何"期望值"都标明它属于哪一类，避免把"基线"当成"必须凑到的数"。

判据分组（与施工指令 §五 的 10 项测试要求一一对应）：
  S1 表头 / 行数 / 基线增量
  S2 主键唯一性 + 外键可解析 + 地点键 1:1
  S3 几何（类型分布 / WKT 非空 / 面线代表点 / 无效面已修）
  S4 精度（源值直传）
  S5 时间（天文纪年 / 无公元 0 / 顺序 / 七值域）
  S6 坐标（经纬度范围）
  S7 A2 代表点合成（3,317 条逐条比对 places.csv 原值）
  S8 重叠地点（2,552 条 inactive）
  S9 连接（13,603 源记录 / 13,553 唯一有序对 / 与切片的 373 条重复）
  S10 质量台账（7,960 的构成与"未开票"项）
  S11 既有四源零漂移（与 code/data/staging 逐行比对，仅忽略时间戳列）

用法：
    cd code
    python ops/m4-4a/verify_staging_m4_3.py
    python ops/m4-4a/verify_staging_m4_3.py --json ops/m4-4a/verify_report.json

退出码：0 全部通过；1 有任一判据失败（每条失败都会打印明细）。
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
NEW = CODE_ROOT / "data" / "staging_m4_3"
OLD = CODE_ROOT / "data" / "staging"
GIS = CODE_ROOT / "data" / "raw" / "pleiades_gis_4_1" / "gis"

P4 = "pleiades_gis_4_1"
SLICE = "pleiades_gis_4_1_slice"

#: 施工指令 §四 的对照基线（增量，不是总量）。
BASELINE: Dict[str, int] = {
    "new_places": 38_928,
    "new_names": 37_055,
    "raw_locations": 32_374,
    "synthetic_points": 3_317,
    "locations_total": 35_691,
    "connections_source_records": 13_603,
    "inactive_overlap": 2_552,
    "source_record_delta": 127_829,
    "source_record_total": 157_220,
    "candidate_distinct_pairs": 13_553,
    "point": 26_684,
    "polygon_plus_multipolygon": 4_114,
    "linestring": 4_893,
    "geometry_total": 35_691,
    "place_precise": 27_418,
    "place_rough": 11_510,
    "location_precise": 31_223,
    "location_rough": 4_468,
    "missing_coordinate": 7_200,
    "geometry_invalid_repaired": 4,
    "connection_endpoint_missing": 28,
    "accuracy_unknown_sentinel": 728,
    "predicted_issue_rows": 7_960,
}

TABLE_FILES = {
    "historical_places": "historical_places.csv",
    "historical_place_names": "historical_place_names.csv",
    "historical_place_locations": "historical_place_locations.csv",
    "source_records": "source_records.csv",
    "data_quality_issues": "data_quality_issues.csv",
    "candidate_matches": "candidate_matches.csv",
    "data_datasets": "data_datasets.csv",
}

#: 时间戳列：旧暂存用 2026-11-02，本轮用 2026-11-04，比对时忽略。
VOLATILE_COLUMNS = {"ingested_at", "created_at"}

TIME_BOUND_TYPES = {"exact", "bounded", "exact_or_bounded", "tpq_taq",
                    "derived_tpq_taq", "snapshot", "unknown"}


class Report:
    """Collect pass/fail results so one run produces both console and JSON."""

    def __init__(self) -> None:
        self.items: List[Dict[str, Any]] = []

    def check(self, section: str, name: str, ok: bool, detail: str = "") -> bool:
        self.items.append({"section": section, "name": name, "ok": bool(ok), "detail": detail})
        flag = "✓" if ok else "✗"
        print(f"  {flag} [{section}] {name}" + (f"  — {detail}" if detail else ""))
        return ok

    def expect(self, section: str, name: str, actual: Any, expected: Any) -> bool:
        ok = actual == expected
        return self.check(section, name, ok, f"实际={actual} 期望={expected}")

    @property
    def ok(self) -> bool:
        return all(item["ok"] for item in self.items)

    @property
    def failures(self) -> List[Dict[str, Any]]:
        return [item for item in self.items if not item["ok"]]


def read_rows(path: Path) -> Iterable[Dict[str, str]]:
    with io.open(path, encoding="utf-8-sig", newline="") as handle:
        yield from csv.DictReader(handle)


def header_of(path: Path) -> List[str]:
    with io.open(path, encoding="utf-8-sig", newline="") as handle:
        return next(csv.reader(handle))


def count_rows(path: Path) -> int:
    if not path.is_file():
        return 0
    with io.open(path, encoding="utf-8-sig", newline="") as handle:
        return max(0, sum(1 for _ in handle) - 1)


def to_float(text: str) -> Optional[float]:
    value = (text or "").strip()
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def to_int(text: str) -> Optional[int]:
    value = (text or "").strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def load_source_index(path: Path) -> Tuple[Dict[str, Dict[str, str]], Dict[str, int]]:
    """Stream ``source_records.csv`` into a compact index.

    The file is ~145 MB, so only the columns the checks need are kept, plus the
    payload of the representative-point rows (3,317) which are compared against
    ``places.csv`` coordinate by coordinate.

    Returns:
      ``(by_sid, per_dataset_counts)``.
    """
    by_sid: Dict[str, Dict[str, str]] = {}
    per_dataset: Counter = Counter()
    for row in read_rows(path):
        sid = row["source_record_id"]
        per_dataset[row["dataset_id"]] += 1
        keep = {
            "dataset_id": row["dataset_id"],
            "external_id": row["external_id"],
            "external_id_type": row["external_id_type"],
            "raw_file": row["raw_file"],
            "raw_record_index": row["raw_record_index"],
        }
        if row["external_id_type"] == "pleiades_representative_point":
            keep["raw_payload_json"] = row["raw_payload_json"]
        by_sid[sid] = keep
    return by_sid, dict(per_dataset)


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify the M4-4a staging deliverables.")
    parser.add_argument("--json", default="")
    args = parser.parse_args()

    report = Report()
    print("M4-4a 交付核验：code/data/staging_m4_3")
    print()

    # ---------------------------------------------------------------- S1
    print("S1 表头 / 行数 / 基线增量")
    old_counts = {name: count_rows(OLD / file) for name, file in TABLE_FILES.items()}
    new_counts = {name: count_rows(NEW / file) for name, file in TABLE_FILES.items()}
    for name, file in TABLE_FILES.items():
        report.check(
            "S1", f"{file} 表头与既有暂存一致",
            header_of(NEW / file) == header_of(OLD / file),
            f"{len(header_of(NEW / file))} 列",
        )

    deltas = {
        "places": new_counts["historical_places"] - old_counts["historical_places"],
        "names": new_counts["historical_place_names"] - old_counts["historical_place_names"],
        "locations": (new_counts["historical_place_locations"]
                      - old_counts["historical_place_locations"]),
        "source_records": new_counts["source_records"] - old_counts["source_records"],
        "issues": (new_counts["data_quality_issues"] - old_counts["data_quality_issues"]),
        "candidates": new_counts["candidate_matches"] - old_counts["candidate_matches"],
        "datasets": new_counts["data_datasets"] - old_counts["data_datasets"],
    }
    report.expect("S1", "地点净增", deltas["places"], BASELINE["new_places"])
    report.expect("S1", "名称净增", deltas["names"], BASELINE["new_names"])
    report.expect("S1", "位置净增", deltas["locations"], BASELINE["locations_total"])
    report.expect("S1", "source_record 净增", deltas["source_records"],
                  BASELINE["source_record_delta"])
    report.expect("S1", "source_record 总量", new_counts["source_records"],
                  BASELINE["source_record_total"])
    report.expect("S1", "data_datasets 净增", deltas["datasets"], 1)
    print(f"    旧/新行数：" + "；".join(
        f"{name} {old_counts[name]:,}→{new_counts[name]:,}" for name in TABLE_FILES))

    # ---------------------------------------------------------------- S2
    print("\nS2 主键唯一性 / 外键 / 地点键")
    place_ids: Dict[str, str] = {}
    place_keys: set = set()
    dataset_of_place: Dict[str, str] = {}
    dup_place_key = 0
    dup_place_id = 0
    for row in read_rows(NEW / TABLE_FILES["historical_places"]):
        pid = row["place_id"]
        if pid in place_ids:
            dup_place_id += 1
        place_ids[pid] = row["source_dataset"]
        dataset_of_place[pid] = row["source_dataset"]
        key = (row["source_dataset"], row["primary_external_id"])
        if key in place_keys:
            dup_place_key += 1
        place_keys.add(key)
    report.expect("S2", "historical_places 行数 = 唯一 place_id 数",
                  len(place_ids), new_counts["historical_places"])
    report.expect("S2", "place_id 重复", dup_place_id, 0)
    report.expect("S2", "(source_dataset, primary_external_id) 重复", dup_place_key, 0)

    name_ids: set = set()
    name_sr: set = set()
    name_place_missing = 0
    dup_name = 0
    for row in read_rows(NEW / TABLE_FILES["historical_place_names"]):
        if row["name_id"] in name_ids:
            dup_name += 1
        name_ids.add(row["name_id"])
        name_sr.add(row["source_record_id"])
        if row["place_id"] not in place_ids:
            name_place_missing += 1
    report.expect("S2", "name_id 重复", dup_name, 0)
    report.expect("S2", "名称行 place_id 全部可解析", name_place_missing, 0)

    loc_ids: set = set()
    loc_sr: set = set()
    loc_place_missing = 0
    dup_loc = 0
    dup_loc_sr = 0
    for row in read_rows(NEW / TABLE_FILES["historical_place_locations"]):
        if row["location_id"] in loc_ids:
            dup_loc += 1
        loc_ids.add(row["location_id"])
        sid = row["source_record_id"]
        if sid in loc_sr:
            dup_loc_sr += 1
        loc_sr.add(sid)
        if row["place_id"] not in place_ids:
            loc_place_missing += 1
    report.expect("S2", "location_id 重复", dup_loc, 0)
    report.expect("S2", "location.source_record_id 重复（C07）", dup_loc_sr, 0)
    report.expect("S2", "位置行 place_id 全部可解析", loc_place_missing, 0)

    by_sid, per_dataset = load_source_index(NEW / TABLE_FILES["source_records"])
    report.expect("S2", "source_record_id 唯一", len(by_sid), new_counts["source_records"])
    report.expect("S2", "source_records 中 pleiades_gis_4_1 行数",
                  per_dataset.get(P4, 0), BASELINE["source_record_delta"])
    print(f"    各数据集源记录：" + "；".join(
        f"{k} {v:,}" for k, v in sorted(per_dataset.items())))

    missing_sr = sum(1 for sid in name_sr if sid not in by_sid)
    missing_sr += sum(1 for sid in loc_sr if sid not in by_sid)
    report.expect("S2", "名称/位置行 source_record_id 全部可解析", missing_sr, 0)

    # ---------------------------------------------------------------- S3
    print("\nS3 几何")
    geom_counts: Counter = Counter()
    geom_by_dataset: Dict[str, Counter] = defaultdict(Counter)
    empty_wkt = 0
    shape_without_rep = 0
    p4_locations = 0
    for row in read_rows(NEW / TABLE_FILES["historical_place_locations"]):
        gtype = (row["geom_type"] or "").strip()
        geom_counts[gtype] += 1
        if not (row["geom_wkt"] or "").strip():
            empty_wkt += 1
        if gtype != "Point" and (
            to_float(row["representative_lon"]) is None
            or to_float(row["representative_lat"]) is None
        ):
            shape_without_rep += 1
        dataset = place_ids.get(row["place_id"], "")
        geom_by_dataset[dataset][gtype] += 1
        if dataset == P4:
            p4_locations += 1
    p4_geom = geom_by_dataset[P4]
    report.expect("S3", "v4.1 几何总数", sum(p4_geom.values()), BASELINE["geometry_total"])
    report.expect("S3", "v4.1 Point（含 3,317 合成）", p4_geom["Point"], BASELINE["point"])
    report.expect("S3", "v4.1 Polygon + MultiPolygon",
                  p4_geom["Polygon"] + p4_geom["MultiPolygon"],
                  BASELINE["polygon_plus_multipolygon"])
    report.expect("S3", "v4.1 LineString", p4_geom["LineString"], BASELINE["linestring"])
    # 全表 10 行空 WKT 是 CHGIS 的 DBF 溢出标记行（X_COOR=**********），属既有行为
    report.expect("S3", "全表 geom_wkt 为空的行（应为既有 CHGIS 10 行）", empty_wkt, 10)
    report.expect("S3", "面/线缺代表点", shape_without_rep, 0)
    report.expect("S3", "v4.1 位置行数", p4_locations, BASELINE["locations_total"])
    print(f"    几何明细：{dict(sorted(geom_counts.items()))}")
    print(f"    v4.1 几何明细：{dict(sorted(geom_by_dataset[P4].items()))}")

    # 无效面是否真的修好了：源文件重新判定一次
    # 用流水线自己的判定函数把 polygons.csv 重判一遍，确认"4 条无效"不是抄来的数字
    try:
        sys.path.insert(0, str(CODE_ROOT / "p0" / "wb-002-normalize"))
        from pleiades_extract import _location_geometry  # noqa: PLC0415

        repaired_rows = []
        for index, row in enumerate(read_rows(GIS / "location_polygons.csv"), start=1):
            result = _location_geometry(row.get("geometry_wkt", ""), "Polygon")
            if "geometry_invalid_repaired" in result["flags"]:
                repaired_rows.append((index, row["id"], result["geom_type"]))
        report.expect("S3", "源文件重判：整包无效面", len(repaired_rows), 5)
        report.expect("S3", "源文件重判：修复后仍为面/多面",
                      sorted(gt for _i, _id, gt in repaired_rows),
                      ["MultiPolygon", "MultiPolygon", "Polygon", "Polygon", "Polygon"])
    except Exception as exc:  # noqa: BLE001
        report.check("S3", "重判无效面", False, f"{type(exc).__name__}: {exc}")
    issue_rows = list(read_rows(NEW / TABLE_FILES["data_quality_issues"]))
    repaired_logged = [r for r in issue_rows if r["issue_type"] == "geometry_invalid_repaired"]
    report.expect("S3", "台账 geometry_invalid_repaired", len(repaired_logged),
                  BASELINE["geometry_invalid_repaired"])
    repaired_detail = Counter()
    for row in repaired_logged:
        sid = row["source_record_id"]
        dataset = by_sid.get(sid, {}).get("dataset_id", "")
        repaired_detail[dataset] += 1
    report.expect("S3", "修复行全部属于 v4.1", repaired_detail.get(P4, 0),
                  BASELINE["geometry_invalid_repaired"])

    # ---------------------------------------------------------------- S4
    print("\nS4 精度（源值直传）")
    loc_precision: Counter = Counter()
    p4_loc_precision: Counter = Counter()
    for row in read_rows(NEW / TABLE_FILES["historical_place_locations"]):
        value = (row["location_precision"] or "").strip()
        loc_precision[value] += 1
        if place_ids.get(row["place_id"]) == P4:
            p4_loc_precision[value] += 1
    report.expect("S4", "v4.1 位置 precise", p4_loc_precision["precise"],
                  BASELINE["location_precise"])
    report.expect("S4", "v4.1 位置 rough", p4_loc_precision["rough"],
                  BASELINE["location_rough"])
    report.expect("S4", "v4.1 位置精度取值全在四值域",
                  set(p4_loc_precision) <= {"precise", "approximate", "rough", "unknown"},
                  True)
    print(f"    全表精度分布：{dict(sorted(loc_precision.items()))}")

    place_precision: Counter = Counter()
    for row in read_rows(NEW / TABLE_FILES["historical_places"]):
        if row["source_dataset"] != P4:
            continue
        found = ""
        for part in (row["notes"] or "").split(";"):
            if part.strip().startswith("location_precision="):
                found = part.strip().split("=", 1)[1]
        place_precision[found] += 1
    report.expect("S4", "v4.1 地点级 precise", place_precision["precise"],
                  BASELINE["place_precise"])
    report.expect("S4", "v4.1 地点级 rough", place_precision["rough"],
                  BASELINE["place_rough"])

    # ---------------------------------------------------------------- S5
    print("\nS5 时间")
    year_zero = 0
    inverted = 0
    bad_bound_type = 0
    p4_time = Counter()
    for table in ("historical_place_names", "historical_place_locations"):
        for row in read_rows(NEW / TABLE_FILES[table]):
            f, t = to_int(row["valid_from_year_astro"]), to_int(row["valid_to_year_astro"])
            if f is not None and t is not None and f > t:
                inverted += 1
            if (row["time_bound_type"] or "") not in TIME_BOUND_TYPES:
                bad_bound_type += 1
            # 天文纪年没有公元 0：值 0 是"公元前 1 年"，合法；只要不是被 +1/-1 平移即可。
            if f == 0 or t == 0:
                year_zero += 1
            if place_ids.get(row["place_id"]) == P4:
                p4_time[row["time_bound_type"]] += 1
    report.expect("S5", "time_bound_type 越出七值域", bad_bound_type, 0)
    report.expect("S5", "valid_from > valid_to", inverted, 0)
    print(f"    v4.1 子行时间类型：{dict(sorted(p4_time.items()))}")
    report.check("S5", "v4.1 不含 exact 之外的越界类型",
                 set(p4_time) <= TIME_BOUND_TYPES, str(sorted(p4_time)))

    # ---------------------------------------------------------------- S6
    print("\nS6 坐标")
    out_of_range = Counter()
    missing_coord_rows = Counter()
    for row in read_rows(NEW / TABLE_FILES["historical_place_locations"]):
        dataset = place_ids.get(row["place_id"], "")
        lon, lat = to_float(row["representative_lon"]), to_float(row["representative_lat"])
        if lon is None or lat is None:
            missing_coord_rows[dataset] += 1
            continue
        if not (-180.0 <= lon <= 180.0) or not (-90.0 <= lat <= 90.0):
            out_of_range[dataset] += 1
    report.expect("S6", "v4.1 经纬度越界", out_of_range.get(P4, 0), 0)
    report.expect("S6", "v4.1 位置行缺代表坐标", missing_coord_rows.get(P4, 0), 0)
    # 既有行里的例外必须点名，不能"因为不是本轮数据就忽略"：
    #   CHGIS 10 行坐标被 DBF 溢出标记吞掉 ⇒ 无代表坐标（M2 已记账）
    #   MCGD  1 行 LONG=881.41 ⇒ 数值越界（M2 已记账）
    report.expect("S6", "全表缺代表坐标（应为既有 CHGIS 10 行）",
                  sum(missing_coord_rows.values()), 10)
    report.expect("S6", "全表越界（应为既有 MCGD 1 行）", sum(out_of_range.values()), 1)

    # ---------------------------------------------------------------- S7
    print("\nS7 A2 代表点合成")
    places_coord: Dict[str, Tuple[Optional[float], Optional[float], str]] = {}
    for row in read_rows(GIS / "places.csv"):
        places_coord[(row.get("id") or "").strip()] = (
            to_float(row.get("representative_longitude", "")),
            to_float(row.get("representative_latitude", "")),
            (row.get("location_precision") or "").strip(),
        )
    rep_rows = 0
    rep_mismatch: List[str] = []
    rep_precision: Counter = Counter()
    rep_null_uncertainty = 0
    rep_wrong_file = 0
    for row in read_rows(NEW / TABLE_FILES["historical_place_locations"]):
        sid = row["source_record_id"]
        meta = by_sid.get(sid)
        if not meta or meta["external_id_type"] != "pleiades_representative_point":
            continue
        rep_rows += 1
        pid = meta["external_id"].rsplit("-representative", 1)[0]
        if meta["raw_file"] != "places.csv":
            rep_wrong_file += 1
        exp_lon, exp_lat, exp_precision = places_coord.get(pid, (None, None, ""))
        got_lon, got_lat = to_float(row["representative_lon"]), to_float(row["representative_lat"])
        if (exp_lon is None or got_lon is None
                or abs(exp_lon - got_lon) > 1e-9 or abs(exp_lat - got_lat) > 1e-9):
            rep_mismatch.append(pid)
        rep_precision[(row["location_precision"] or "").strip()] += 1
        if not (row["uncertainty_m"] or "").strip():
            rep_null_uncertainty += 1
        payload = json.loads(meta.get("raw_payload_json") or "{}")
        if payload.get("place_id") != pid:
            rep_mismatch.append(f"{pid}:payload")
    report.expect("S7", "合成代表点行数", rep_rows, BASELINE["synthetic_points"])
    report.expect("S7", "代表点坐标与 places.csv 不一致", len(rep_mismatch), 0)
    report.expect("S7", "合成行 raw_file 不是 places.csv", rep_wrong_file, 0)
    report.expect("S7", "合成行 precise", rep_precision["precise"], 2_589)
    report.expect("S7", "合成行 rough", rep_precision["rough"], 728)
    report.expect("S7", "合成行 uncertainty_m 为空（-1 哨兵）", rep_null_uncertainty, 728)

    # ---------------------------------------------------------------- S8
    print("\nS8 重叠地点（inactive）")
    v41_place_ext: set = set()
    slice_place_ext: set = set()
    v41_place_sids: Dict[str, str] = {}
    for sid, meta in by_sid.items():
        if meta["external_id_type"] != "pleiades_place_id":
            continue
        if meta["dataset_id"] == P4:
            v41_place_ext.add(meta["external_id"])
            v41_place_sids[meta["external_id"]] = sid
        elif meta["dataset_id"] == SLICE:
            slice_place_ext.add(meta["external_id"])
    overlap = v41_place_ext & slice_place_ext
    report.expect("S8", "v4.1 地点源记录", len(v41_place_ext), 41_480)
    report.expect("S8", "切片地点源记录", len(slice_place_ext), 2_643)
    report.expect("S8", "重叠集合大小", len(overlap), BASELINE["inactive_overlap"])
    report.expect("S8", "非重叠（新建地点）", len(v41_place_ext) - len(overlap),
                  BASELINE["new_places"])

    # 导入器侧：用真实 Importer 重算一遍（无数据库，build() 只读 CSV）
    try:
        sys.path.insert(0, str(CODE_ROOT / "ops"))
        import import_staging as importer  # noqa: PLC0415

        class _Cur:
            def execute(self, *_a, **_k):
                raise AssertionError("build() 不应执行 SQL")

        class _Conn:
            def cursor(self):
                return _Cur()

        importer.STAGING = NEW
        built = importer.Importer(_Conn(), "m4-4a-verify", "verify")
        import contextlib
        with contextlib.redirect_stdout(io.StringIO()):
            built.build()
        report.expect("S8", "导入器判定为重叠的源记录数", len(built.superseded_sids),
                      BASELINE["inactive_overlap"])
        report.expect("S8", "导入器地点键数（应等于暂存 places 行数）",
                      len(built.place_keys), new_counts["historical_places"])
    except Exception as exc:  # noqa: BLE001
        report.check("S8", "导入器前置派生", False, f"{type(exc).__name__}: {exc}")

    # ---------------------------------------------------------------- S9
    print("\nS9 连接")
    conn_records = sum(
        1 for meta in by_sid.values()
        if meta["dataset_id"] == P4 and meta["external_id_type"] == "pleiades_connection_id"
    )
    report.expect("S9", "v4.1 连接源记录", conn_records, BASELINE["connections_source_records"])

    p4_rows = 0
    slice_rows = 0
    p4_pairs: set = set()
    slice_pairs: set = set()
    for row in read_rows(NEW / TABLE_FILES["candidate_matches"]):
        if row["relation_type"] != "pleiades_connection":
            continue
        evidence = row["evidence"]
        a = evidence.split("pleiades_place_id_a=")[1].split(";")[0].strip()
        b = evidence.split("pleiades_place_id_b=")[1].split(";")[0].strip()
        ds_a = by_sid.get(row["source_record_id_a"], {}).get("dataset_id", "")
        if ds_a == SLICE:
            slice_rows += 1
            slice_pairs.add((a, b))
        elif ds_a == P4:
            p4_rows += 1
            p4_pairs.add((a, b))
    collisions = p4_pairs & slice_pairs
    report.expect("S9", "切片连接候选行", slice_rows, 390)
    report.expect("S9", "v4.1 连接候选行（按记录）", p4_rows, 13_574)
    report.expect("S9", "v4.1 唯一有序对", len(p4_pairs), BASELINE["candidate_distinct_pairs"])
    report.expect("S9", "与切片候选同有序对（入库按 C09 收敛）", len(collisions), 373)
    print(f"    候选行 {slice_rows + p4_rows:,} = 切片 {slice_rows} + v4.1 {p4_rows:,}；"
          f"v4.1 去重后 {len(p4_pairs):,} 个有序对，其中 {len(collisions)} 个与既有切片候选"
          f"同对 ⇒ 入库净增 {len(p4_pairs) - len(collisions):,}")

    # ---------------------------------------------------------------- S10
    print("\nS10 质量台账")
    issue_by_type: Counter = Counter()
    issue_by_dataset: Counter = Counter()
    for row in issue_rows:
        issue_by_type[row["issue_type"]] += 1
        sid = row["source_record_id"]
        issue_by_dataset[by_sid.get(sid, {}).get("dataset_id", "")] += 1
    delta_by_type = {
        "missing_coordinate": issue_by_type["missing_coordinate"]
        - sum(1 for r in read_rows(OLD / TABLE_FILES["data_quality_issues"])
              if r["issue_type"] == "missing_coordinate"),
        "geometry_invalid_repaired": issue_by_type["geometry_invalid_repaired"],
        "connection_endpoint_missing": issue_by_type["connection_endpoint_missing"],
        "accuracy_unknown_sentinel": issue_by_type["accuracy_unknown_sentinel"],
    }
    for name, expected_key in (
        ("missing_coordinate", "missing_coordinate"),
        ("geometry_invalid_repaired", "geometry_invalid_repaired"),
        ("connection_endpoint_missing", "connection_endpoint_missing"),
        ("accuracy_unknown_sentinel", "accuracy_unknown_sentinel"),
    ):
        report.expect("S10", f"{name} 净增", delta_by_type[name], BASELINE[expected_key])
    report.expect("S10", "可预测台账合计", sum(delta_by_type.values()),
                  BASELINE["predicted_issue_rows"])
    report.expect("S10", "台账总净增", deltas["issues"], BASELINE["predicted_issue_rows"])
    report.expect("S10", "v4.1 台账行数", issue_by_dataset.get(P4, 0),
                  BASELINE["predicted_issue_rows"])
    appended = issue_rows[-BASELINE["predicted_issue_rows"]:]
    report.check("S10", "7,960 行全部追加在既有 12,631 行之后（既有 dq_ 编号不移位）",
                 all(by_sid.get(r["source_record_id"], {}).get("dataset_id") == P4
                     for r in appended),
                 f"追加段数据集 {dict(Counter(by_sid.get(r['source_record_id'], {}).get('dataset_id', '') for r in appended))}")
    print(f"    台账类型分布（全表）：{dict(sorted(issue_by_type.items()))}")

    # ---------------------------------------------------------------- S11
    print("\nS11 既有四源零漂移")
    for name, file in TABLE_FILES.items():
        old_path, new_path = OLD / file, NEW / file
        limit = old_counts[name]
        diffs = 0
        first: Optional[Tuple[int, str]] = None
        with io.open(old_path, encoding="utf-8-sig", newline="") as fh_old, \
                io.open(new_path, encoding="utf-8-sig", newline="") as fh_new:
            reader_old, reader_new = csv.DictReader(fh_old), csv.DictReader(fh_new)
            for index, (a, b) in enumerate(zip(reader_old, reader_new)):
                if index >= limit:
                    break
                for column in a:
                    if column in VOLATILE_COLUMNS:
                        continue
                    if a[column] != b[column]:
                        diffs += 1
                        if first is None:
                            first = (index, column)
                        break
        report.check("S11", f"{file} 前 {limit:,} 行与旧暂存一致（忽略时间戳列）",
                     diffs == 0, f"差异 {diffs}" + (f"，首个 {first}" if first else ""))

    # ---------------------------------------------------------------- 汇总
    print("\n" + "=" * 72)
    print(f"判据 {len(report.items)} 条：通过 {len(report.items) - len(report.failures)}，"
          f"失败 {len(report.failures)}")
    if report.failures:
        print("\n失败明细：")
        for item in report.failures:
            print(f"  ✗ [{item['section']}] {item['name']} — {item['detail']}")

    payload = {
        "generated_at": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc).isoformat(timespec="seconds"),
        "ok": report.ok,
        "checks": len(report.items),
        "failures": len(report.failures),
        "counts": {"old": old_counts, "new": new_counts, "delta": deltas},
        "items": report.items,
    }
    if args.json:
        out = Path(args.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n报告 → {out}")
    return 0 if report.ok else 1


if __name__ == "__main__":
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
