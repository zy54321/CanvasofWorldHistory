"""M4-3 · Pleiades GIS 4.1 完整包只读审计。

只做三件事：
  1. 校验归档（字节数 / MD5 / SHA256 / ZIP 完整性）；
  2. 逐文件解析 GIS 目录，给出地点、名称、位置（点/线/面）、连接、精度、时间统计；
  3. 与现有切片、CHGIS / MCGD / WHG 做覆盖与重复**候选**分析。

不写数据库、不改 staging、不合并任何数据。所有数字都来自本次真实解析。

用法：
    python ops/m4-3/pleiades_audit.py --json ops/m4-3/audit.json
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import re
import sys
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

CODE = Path(__file__).resolve().parents[2]
ROOT = CODE.parent
RAW = CODE / "data" / "raw" / "pleiades_gis_4_1"
GIS = RAW / "gis"
STAGING = CODE / "data" / "staging"
SLICE_DIR = ROOT / "设计资料" / "P0收敛" / "WB-002" / "sample_data_pleiades"

EXPECT_SIZE = 286_621_469
EXPECT_MD5 = "ad339c92c6b895f0eb9a52228da498c4"

#: 目标地点数（v4.1 官方口径）
EXPECT_PLACES = 41_480


def rows(name: str):
    """逐行读取 gis 目录下的 CSV（UTF-8 BOM）。"""
    with io.open(GIS / name, encoding="utf-8-sig", newline="") as f:
        yield from csv.DictReader(f)


def rows_from(path: Path):
    with io.open(path, encoding="utf-8-sig", newline="") as f:
        yield from csv.DictReader(f)


def to_float(v):
    try:
        s = (v or "").strip()
        return float(s) if s else None
    except ValueError:
        return None


def to_int(v):
    try:
        s = (v or "").strip()
        return int(s) if s else None
    except ValueError:
        return None


def md5_of(p: Path) -> str:
    h = hashlib.md5()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_of(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


_PLACE_URI_RE = re.compile(r"/places/([^/?#]+)")


def place_key(value: str) -> str:
    """把 ``connects_to`` 这类 URI 归一成地点 id。

    v4.1 的 ``connections.connects_to`` 存的是完整 URI
    （``https://pleiades.stoa.org/places/433032``），``place_id`` 则是裸 id。
    两侧必须对齐，否则会得到 100% 的假孤儿。
    """
    v = (value or "").strip()
    if not v:
        return ""
    m = _PLACE_URI_RE.search(v)
    if m:
        return m.group(1)
    return v.rstrip("/").rsplit("/", 1)[-1]


def haversine_km(lon1, lat1, lon2, lat2) -> float:
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


# ---------------------------------------------------------------- 归档校验
def verify_archive(zip_path: Path) -> dict:
    out = {
        "path": str(zip_path.relative_to(ROOT)).replace("\\", "/"),
        "size_bytes": zip_path.stat().st_size,
        "size_expected": EXPECT_SIZE,
        "size_ok": zip_path.stat().st_size == EXPECT_SIZE,
        "md5": md5_of(zip_path),
        "md5_expected": EXPECT_MD5,
    }
    out["md5_ok"] = out["md5"] == EXPECT_MD5
    out["sha256"] = sha256_of(zip_path)
    with zipfile.ZipFile(zip_path) as z:
        bad = z.testzip()
        names = z.namelist()
    out["zip_test"] = "ok" if bad is None else f"corrupt:{bad}"
    out["zip_entries"] = len(names)
    tops = sorted({n.split("/")[0] for n in names if n})
    out["zip_top_level"] = tops
    return out


# ---------------------------------------------------------------- 地点
def audit_places() -> tuple[dict, dict]:
    total = 0
    ids, uris = Counter(), Counter()
    precision = Counter()
    no_coord = no_bbox = no_title = 0
    lon_range = [None, None]
    lat_range = [None, None]
    geoms: dict[str, dict] = {}   # id -> 摘要，供子表关联判定
    for r in rows("places.csv"):
        total += 1
        pid = (r.get("id") or "").strip()
        ids[pid] += 1
        uris[(r.get("uri") or "").strip()] += 1
        precision[(r.get("location_precision") or "").strip() or "(empty)"] += 1
        if not (r.get("title") or "").strip():
            no_title += 1
        lon = to_float(r.get("representative_longitude"))
        lat = to_float(r.get("representative_latitude"))
        if lon is None or lat is None:
            no_coord += 1
        else:
            for i, v in ((0, lon), (1, lat)):
                pass
            lon_range[0] = lon if lon_range[0] is None else min(lon_range[0], lon)
            lon_range[1] = lon if lon_range[1] is None else max(lon_range[1], lon)
            lat_range[0] = lat if lat_range[0] is None else min(lat_range[0], lat)
            lat_range[1] = lat if lat_range[1] is None else max(lat_range[1], lat)
        if not (r.get("bounding_box_wkt") or "").strip():
            no_bbox += 1
        geoms[pid] = {
            "uri": (r.get("uri") or "").strip(),
            "title": (r.get("title") or "").strip(),
            "precision": (r.get("location_precision") or "").strip(),
            "lon": lon,
            "lat": lat,
        }
    dup_ids = {k: v for k, v in ids.items() if v > 1}
    dup_uris = {k: v for k, v in uris.items() if v > 1}
    summary = {
        "rows": total,
        "expected_rows": EXPECT_PLACES,
        "matches_expected": total == EXPECT_PLACES,
        "unique_ids": len(ids),
        "duplicate_ids": len(dup_ids),
        "duplicate_id_examples": list(dup_ids.items())[:5],
        "unique_uris": len(uris),
        "duplicate_uris": len(dup_uris),
        "duplicate_uri_examples": list(dup_uris.items())[:5],
        "empty_uris": uris.get("", 0),
        "empty_titles": no_title,
        "missing_representative_point": no_coord,
        "missing_bounding_box_wkt": no_bbox,
        "location_precision": dict(precision.most_common()),
        "lon_range": lon_range,
        "lat_range": lat_range,
    }
    return summary, geoms


# ---------------------------------------------------------------- 名称
def audit_names(place_ids: set) -> dict:
    total = 0
    types = Counter()
    langs = Counter()
    orphan = 0
    orphan_examples = []
    dup_key = Counter()
    no_title = 0
    time_rows = 0
    time_inv = 0
    for r in rows("names.csv"):
        total += 1
        pid = (r.get("place_id") or "").strip()
        title = (r.get("title") or "").strip()
        t = (r.get("name_type") or "").strip() or "(empty)"
        types[t] += 1
        lang = (r.get("language_tag") or "").strip()
        if lang:
            langs[lang] += 1
        if not title:
            no_title += 1
        if pid not in place_ids:
            orphan += 1
            if len(orphan_examples) < 5:
                orphan_examples.append({"id": r.get("id"), "place_id": pid, "title": title})
        dup_key[(pid, title, t)] += 1
        tpq, taq = to_int(r.get("year_after_which")), to_int(r.get("year_before_which"))
        if tpq is not None or taq is not None:
            time_rows += 1
            if tpq is not None and taq is not None and tpq > taq:
                time_inv += 1
    dup_exact = {k: v for k, v in dup_key.items() if v > 1}
    return {
        "rows": total,
        "empty_titles": no_title,
        "name_types": dict(types.most_common()),
        "language_tags_top": dict(langs.most_common(12)),
        "distinct_language_tags": len(langs),
        "orphan_parent_missing": orphan,
        "orphan_examples": orphan_examples,
        "exact_duplicate_rows": sum(v - 1 for v in dup_exact.values()),
        "exact_duplicate_groups": len(dup_exact),
        "with_time_bounds": time_rows,
        "time_inversions_tpq_gt_taq": time_inv,
    }


# ---------------------------------------------------------------- 位置（点/线/面）
def audit_locations(place_ids: set) -> dict:
    from shapely import wkt as shapely_wkt, is_valid_reason
    from shapely.errors import GEOSException

    def one(fname: str, kind: str) -> dict:
        total = 0
        parsed = invalid = empty = out_of_range = orphan = 0
        precision = Counter()
        radius = {"zero": 0, "unknown": 0, "gt0": 0}
        time_rows = time_inv = 0
        geom_types = Counter()
        dup = Counter()
        invalid_examples = []
        for r in rows(fname):
            total += 1
            pid = (r.get("place_id") or "").strip()
            precision[(r.get("location_precision") or "").strip() or "(empty)"] += 1
            rad = to_float(r.get("accuracy_radius"))
            if rad is None:
                radius["unknown"] += 1
            elif rad == 0:
                radius["zero"] += 1
            else:
                radius["gt0"] += 1
            tpq, taq = to_int(r.get("year_after_which")), to_int(r.get("year_before_which"))
            if tpq is not None or taq is not None:
                time_rows += 1
                if tpq is not None and taq is not None and tpq > taq:
                    time_inv += 1
            if pid not in place_ids:
                orphan += 1
            w = (r.get("geometry_wkt") or "").strip()
            dup[(pid, w)] += 1
            if not w:
                empty += 1
                continue
            try:
                g = shapely_wkt.loads(w)
            except (GEOSException, ValueError):
                invalid += 1
                if len(invalid_examples) < 5:
                    invalid_examples.append({"id": r.get("id"), "place_id": pid,
                                             "wkt": w[:90]})
                continue
            parsed += 1
            geom_types[g.geom_type] += 1
            if g.is_empty:
                empty += 1
                continue
            minx, miny, maxx, maxy = g.bounds
            if not (-180 <= minx <= 180 and -180 <= maxx <= 180
                    and -90 <= miny <= 90 and -90 <= maxy <= 90):
                out_of_range += 1
            if not g.is_valid:
                invalid += 1
                if len(invalid_examples) < 5:
                    invalid_examples.append({"id": r.get("id"), "place_id": pid,
                                             "wkt": w[:90], "reason": is_valid_reason(g)})
        dup_rows = sum(v - 1 for v in dup.values() if v > 1)
        return {
            "file": fname,
            "geometry_kind": kind,
            "rows": total,
            "parsed": parsed,
            "empty_geometry": empty,
            "invalid_geometry": invalid,
            "invalid_examples": invalid_examples,
            "out_of_range": out_of_range,
            "orphan_parent_missing": orphan,
            "geom_types": dict(geom_types.most_common()),
            "location_precision": dict(precision.most_common()),
            "accuracy_radius": radius,
            "with_time_bounds": time_rows,
            "time_inversions_tpq_gt_taq": time_inv,
            "duplicate_rows_same_place_and_wkt": dup_rows,
        }

    points = one("location_points.csv", "Point")
    polys = one("location_polygons.csv", "Polygon")
    lines = one("location_linestrings.csv", "LineString")
    tot_rows = points["rows"] + polys["rows"] + lines["rows"]
    return {
        "points": points,
        "polygons": polys,
        "linestrings": lines,
        "total_rows": tot_rows,
        "orphan_total": (points["orphan_parent_missing"] + polys["orphan_parent_missing"]
                         + lines["orphan_parent_missing"]),
        "invalid_total": (points["invalid_geometry"] + polys["invalid_geometry"]
                          + lines["invalid_geometry"]),
        "out_of_range_total": (points["out_of_range"] + polys["out_of_range"]
                               + lines["out_of_range"]),
    }


# ---------------------------------------------------------------- 连接
def audit_connections(place_ids: set) -> dict:
    total = 0
    types = Counter()
    certainty = Counter()
    orphan_from = orphan_to = 0
    self_loop = 0
    dup = Counter()
    orphan_examples = []
    time_rows = time_inv = 0
    for r in rows("connections.csv"):
        total += 1
        a = place_key(r.get("place_id"))
        b = place_key(r.get("connects_to"))
        types[(r.get("connection_type") or "").strip() or "(empty)"] += 1
        certainty[(r.get("association_certainty") or "").strip() or "(empty)"] += 1
        if a not in place_ids:
            orphan_from += 1
            if len(orphan_examples) < 5:
                orphan_examples.append({"side": "place_id", "id": a, "other": b})
        if b not in place_ids:
            orphan_to += 1
            if len(orphan_examples) < 5:
                orphan_examples.append({"side": "connects_to", "id": b, "other": a})
        if a == b:
            self_loop += 1
        dup[(a, b, (r.get("connection_type") or "").strip())] += 1
        tpq, taq = to_int(r.get("year_after_which")), to_int(r.get("year_before_which"))
        if tpq is not None or taq is not None:
            time_rows += 1
            if tpq is not None and taq is not None and tpq > taq:
                time_inv += 1
    return {
        "rows": total,
        "connection_types": dict(types.most_common()),
        "association_certainty": dict(certainty.most_common()),
        "orphan_place_id": orphan_from,
        "orphan_connects_to": orphan_to,
        "orphan_total": orphan_from + orphan_to,
        "orphan_examples": orphan_examples,
        "self_loops": self_loop,
        "duplicate_rows_same_triple": sum(v - 1 for v in dup.values() if v > 1),
        "with_time_bounds": time_rows,
        "time_inversions_tpq_gt_taq": time_inv,
    }


# ---------------------------------------------------------------- 精度与类型附表
def audit_accuracy(place_ids: set) -> dict:
    total = 0
    precision = Counter()
    hull_empty = 0
    max_acc = []
    min_acc = []
    orphan = 0
    for r in rows("places_accuracy.csv"):
        total += 1
        precision[(r.get("location_precision") or "").strip() or "(empty)"] += 1
        if not (r.get("accuracy_hull") or "").strip():
            hull_empty += 1
        for bucket, key in ((max_acc, "max_accuracy_meters"), (min_acc, "min_accuracy_meters")):
            v = to_float(r.get(key))
            if v is not None:
                bucket.append(v)
        if (r.get("place_id") or "").strip() not in place_ids:
            orphan += 1

    def q(vals):
        if not vals:
            return None
        vals = sorted(vals)
        n = len(vals)
        return {"n": n, "min": round(vals[0], 1), "p50": round(vals[n // 2], 1),
                "p95": round(vals[int(n * 0.95) - 1], 1) if n > 1 else round(vals[0], 1),
                "max": round(vals[-1], 1)}

    return {
        "rows": total,
        "location_precision": dict(precision.most_common()),
        "empty_accuracy_hull": hull_empty,
        "max_accuracy_meters": q(max_acc),
        "min_accuracy_meters": q(min_acc),
        "orphan_place_id": orphan,
    }


def audit_place_types(place_ids: set) -> dict:
    labels = {}
    for r in rows("place_types.csv"):
        labels[(r.get("key") or "").strip()] = (r.get("term") or "").strip()
    total = 0
    per_place = Counter()
    top = Counter()
    orphan = 0
    for r in rows("places_place_types.csv"):
        total += 1
        pid = (r.get("place_id") or "").strip()
        key = (r.get("place_type") or "").strip()
        per_place[pid] += 1
        top[labels.get(key, key) or "(empty)"] += 1
        if pid not in place_ids:
            orphan += 1
    return {
        "place_type_vocab": len(labels),
        "rows": total,
        "distinct_places": len(per_place),
        "places_without_type": 0,  # 由调用方用 places 总数补齐
        "rows_per_place": dict(Counter(per_place.values()).most_common(6)),
        "top_types": dict(top.most_common(15)),
        "orphan_place_id": orphan,
    }


def audit_time_periods() -> dict:
    total = 0
    lower_empty = upper_empty = 0
    for r in rows("time_periods.csv"):
        total += 1
        if (r.get("lower_bound") or "").strip() == "":
            lower_empty += 1
        if (r.get("upper_bound") or "").strip() == "":
            upper_empty += 1
    slice_file = SLICE_DIR / "time_periods.csv.range-0-999999"
    same = None
    if slice_file.exists():
        a = sha256_of(GIS / "time_periods.csv")
        b = sha256_of(slice_file)
        # 切片是 999,999 字节截断；完整文件 38 KB < 1 MB，理论上应完全相同
        same = a == b
    return {
        "rows": total,
        "lower_bound_empty": lower_empty,
        "upper_bound_empty": upper_empty,
        "slice_identical_sha256": same,
        "sha256": sha256_of(GIS / "time_periods.csv"),
    }


# ---------------------------------------------------------------- 与切片对照
def compare_with_slice(places: dict) -> dict:
    recs = STAGING / "source_records.csv"
    slice_ids = set()
    with io.open(recs, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            if (r["dataset_id"] == "pleiades_gis_4_1_slice"
                    and r["external_id_type"] == "pleiades_place_id"):
                slice_ids.add((r["external_id"] or "").strip())
    full_ids = set(places)
    only_slice = slice_ids - full_ids
    # 切片 CSV 里能读到的值（截断尾行丢弃）用于判断"值是否变化"
    slice_rows = {}
    p = SLICE_DIR / "places.csv.range-0-1048575"
    header = None
    with io.open(p, encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        header = next(reader)
        for row in reader:
            if len(row) != len(header):
                continue  # 截断尾行
            d = dict(zip(header, row))
            slice_rows[(d.get("id") or "").strip()] = d
    changed = []
    unchanged = 0
    for pid in sorted(slice_ids & full_ids):
        old = slice_rows.get(pid)
        if not old:
            continue
        new = places[pid]
        if (to_float(old.get("representative_longitude")) != new["lon"]
                or to_float(old.get("representative_latitude")) != new["lat"]
                or (old.get("location_precision") or "").strip() != new["precision"]):
            if len(changed) < 10:
                changed.append({
                    "id": pid,
                    "old": [to_float(old.get("representative_longitude")),
                            to_float(old.get("representative_latitude")),
                            (old.get("location_precision") or "").strip()],
                    "new": [new["lon"], new["lat"], new["precision"]],
                })
        else:
            unchanged += 1
    return {
        "slice_source_records": len(slice_ids),
        "full_places": len(full_ids),
        "in_both": len(slice_ids & full_ids),
        "only_in_slice": len(only_slice),
        "only_in_slice_examples": sorted(only_slice)[:5],
        "new_in_full": len(full_ids - slice_ids),
        "value_unchanged": unchanged,
        "value_changed": len(slice_ids & full_ids) - unchanged,
        "value_changed_examples": changed,
        "slice_csv_rows_parsed": len(slice_rows),
        "coverage_pct_of_full": round(len(slice_ids & full_ids) / len(full_ids) * 100, 2),
    }


# ---------------------------------------------------------------- 跨源候选
NORM_RE = re.compile(r"[\s·・,，.。'’\"()（）\[\]【】\-—_:：;；/]")


def norm_name(s: str) -> str:
    s = NORM_RE.sub("", (s or "").strip().lower())
    for a, b in (("縣", "县"), ("臺", "台"), ("廣", "广"), ("東", "东"), ("西", "西")):
        s = s.replace(a, b)
    return s


def load_staging_places() -> tuple[dict, dict]:
    """返回 (place_id -> {dataset,name,lon,lat}, dataset -> 名称集合)。"""
    meta, loc = {}, {}
    with io.open(STAGING / "historical_places.csv", encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            meta[r["place_id"]] = {
                "dataset": r["source_dataset"],
                "name": (r.get("canonical_name") or "").strip(),
            }
    with io.open(STAGING / "historical_place_locations.csv", encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            pid = r["place_id"]
            if pid in loc:
                continue
            lon, lat = to_float(r.get("representative_lon")), to_float(r.get("representative_lat"))
            if lon is not None and lat is not None:
                loc[pid] = (lon, lat)
    return meta, loc


def cross_source_candidates(places: dict) -> dict:
    """与 CHGIS / MCGD / WHG 的**候选**关系统计（只数，不合并）。

    两条独立判据，分开报，因为它们的可用性完全不同：

      · 名称归一化相等：Pleiades 是拉丁/希腊文，CHGIS 是汉文，MCGD 是汉文+拼音，
        跨文字系统基本命中不了 —— 这一栏的数字小是**事实**，不是算法失败。
      · 坐标邻近：按 0.1° 网格做邻域检索，给出 ≤1km / ≤10km / ≤50km 的最近距离分档，
        用来量化"地理上是否重叠"。这是真正能用的候选线索。
    """
    meta, loc = load_staging_places()
    by_name = defaultdict(list)
    for pid, m in meta.items():
        n = norm_name(m["name"])
        if not n:
            continue
        p = loc.get(pid)
        if p:
            by_name[n].append((pid, m["dataset"], p[0], p[1]))

    # 网格索引：cell(0.1°) -> [(dataset, lon, lat)]
    CELL = 0.1
    grid = defaultdict(list)
    for pid, m in meta.items():
        p = loc.get(pid)
        if not p:
            continue
        ds = m["dataset"]
        if ds in ("pleiades_gis_4_1_slice", "m2check_ds", "m3_demo_ds", "manual_entry"):
            continue
        grid[(int(math.floor(p[0] / CELL)), int(math.floor(p[1] / CELL)))].append(
            (ds, p[0], p[1]))

    ple = [(pid, v["lon"], v["lat"]) for pid, v in places.items()
           if v["lon"] is not None and v["lat"] is not None]
    ple_names = defaultdict(list)
    for pid, lon, lat in ple:
        n = norm_name(places[pid]["title"])
        if n:
            ple_names[n].append((pid, lon, lat))

    buckets = Counter()
    near_examples = []
    same_name_total = 0
    self_slice = Counter()
    for n, targets in ple_names.items():
        for (tpid, tds, tlon, tlat) in by_name.get(n, []):
            if tds == "pleiades_gis_4_1_slice":
                # 与已入库切片的重合：这是"同一来源不同快照"的一致性检查，
                # 不是跨源去重候选，必须分开统计。
                best = min(haversine_km(lon, lat, tlon, tlat) for _, lon, lat in targets)
                band = ("<=1km" if best <= 1 else "<=10km" if best <= 10
                        else "<=50km" if best <= 50 else ">50km")
                self_slice[band] += 1
                continue
            same_name_total += 1
            best = min(haversine_km(lon, lat, tlon, tlat) for _, lon, lat in targets)
            band = ("<=1km" if best <= 1 else "<=10km" if best <= 10
                    else "<=50km" if best <= 50 else ">50km")
            buckets[f"name|{tds}|{band}"] += 1
            if band != ">50km" and len(near_examples) < 12:
                near_examples.append({"name": n, "dataset": tds, "km": round(best, 2),
                                      "via": "name"})

    # 邻域半径：0.5° ≈ 55km（纬度），足以覆盖 50km 档；再远的点对不构成"同一地点"候选，
    # 只按"范围内无点"计入 none，避免用 3×3 格（≈±11km）把 >50km 档做成假 0。
    R = 5
    datasets = sorted({ds for cell in grid.values() for ds, _x, _y in cell})
    prox = Counter()
    prox_examples = []
    for pid, lon, lat in ple:
        cx, cy = int(math.floor(lon / CELL)), int(math.floor(lat / CELL))
        best = {}
        for dx in range(-R, R + 1):
            for dy in range(-R, R + 1):
                for (ds, olon, olat) in grid.get((cx + dx, cy + dy), ()):
                    d = haversine_km(lon, lat, olon, olat)
                    if d > 50:
                        continue
                    if ds not in best or d < best[ds]:
                        best[ds] = d
        for ds in datasets:
            if ds not in best:
                prox[f"coord|{ds}|none_within_50km"] += 1
                continue
            d = best[ds]
            band = "<=1km" if d <= 1 else "<=10km" if d <= 10 else "<=50km"
            prox[f"coord|{ds}|{band}"] += 1
            if band == "<=1km" and len(prox_examples) < 10:
                prox_examples.append({"pleiades": pid, "dataset": ds, "km": round(d, 3)})

    all_buckets = dict(sorted({**buckets, **prox}.items()))
    return {
        "self_slice_name_matches": dict(sorted(self_slice.items())),
        "same_name_pairs_excluding_pleiades_self": same_name_total,
        "name_match_by_dataset_and_distance": dict(sorted(buckets.items())),
        "coord_nearest_by_dataset_and_distance": dict(sorted(prox.items())),
        "coord_within_1km_examples": prox_examples,
        "all_buckets": all_buckets,
        "near_examples": near_examples,
        "method": ("名称归一化相等 + 网格(0.1°)最近邻 Haversine 距离分档；"
                   "仅候选，绝不合并"),
    }


# ---------------------------------------------------------------- 每地点覆盖度
def place_coverage(place_ids: set) -> dict:
    """每个地点带多少名称 / 位置，以及三类几何各自覆盖多少地点。"""
    names_per = Counter()
    loc_ids = {"point": set(), "polygon": set(), "linestring": set()}
    for r in rows("names.csv"):
        names_per[(r.get("place_id") or "").strip()] += 1
    for fname, key in (("location_points.csv", "point"),
                       ("location_polygons.csv", "polygon"),
                       ("location_linestrings.csv", "linestring")):
        for r in rows(fname):
            loc_ids[key].add((r.get("place_id") or "").strip())
    with_any = set()
    for v in loc_ids.values():
        with_any |= v
    return {
        "places_total": len(place_ids),
        "places_with_name": len(names_per),
        "places_with_any_location": len(with_any & place_ids),
        "places_with_point": len(loc_ids["point"] & place_ids),
        "places_with_polygon": len(loc_ids["polygon"] & place_ids),
        "places_with_linestring": len(loc_ids["linestring"] & place_ids),
        "places_without_name": len(place_ids - set(names_per)),
        "places_without_location": len(place_ids - with_any),
        "names_per_place": dict(Counter(names_per.values()).most_common(8)),
        "avg_names_per_place": round(sum(names_per.values()) / len(place_ids), 2),
        "total_names": sum(names_per.values()),
    }


# ---------------------------------------------------------------- 主流程
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=str(CODE / "ops" / "m4-3" / "audit.json"))
    ap.add_argument("--skip-archive", action="store_true")
    args = ap.parse_args()

    result = {"archive": None if args.skip_archive else verify_archive(
        RAW / "pleiades.datasets-v4.1.zip")}

    places, geoms = audit_places()
    place_ids = set(geoms)
    result["places"] = places
    result["names"] = audit_names(place_ids)
    result["locations"] = audit_locations(place_ids)
    result["connections"] = audit_connections(place_ids)
    result["accuracy"] = audit_accuracy(place_ids)
    result["place_types"] = audit_place_types(place_ids)
    types = result["place_types"]
    types["places_without_type"] = len(place_ids) - types["distinct_places"]
    result["time_periods"] = audit_time_periods()
    result["coverage"] = place_coverage(place_ids)
    result["vs_slice"] = compare_with_slice(geoms)
    result["cross_source"] = cross_source_candidates(geoms)

    # 文件清单
    files = []
    for p in sorted(GIS.iterdir()):
        if p.is_file():
            files.append({
                "file": p.name,
                "bytes": p.stat().st_size,
                "sha256": sha256_of(p),
            })
    result["files"] = files

    out = Path(args.json)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---- 控制台摘要
    lc = result["locations"]
    print("== 归档 ==")
    if result["archive"]:
        a = result["archive"]
        print(f"  size {a['size_bytes']:,} ok={a['size_ok']}  md5 {a['md5'][:12]}… ok={a['md5_ok']}  zip {a['zip_test']}")
    print("== 地点 ==")
    p = result["places"]
    print(f"  rows {p['rows']:,} (期望 {p['expected_rows']:,}, 命中={p['matches_expected']})"
          f"  unique id {p['unique_ids']:,}  dup id {p['duplicate_ids']}"
          f"  unique uri {p['unique_uris']:,}  dup uri {p['duplicate_uris']}")
    print(f"  precision {p['location_precision']}")
    print("== 名称 ==")
    n = result["names"]
    print(f"  rows {n['rows']:,}  orphan {n['orphan_parent_missing']:,}"
          f"  exact-dup rows {n['exact_duplicate_rows']:,}  time {n['with_time_bounds']:,}"
          f"  tp>taq {n['time_inversions_tpq_gt_taq']}")
    print(f"  types {n['name_types']}")
    print("== 位置 ==")
    for k, label in (("points", "Point"), ("polygons", "Polygon"), ("linestrings", "LineString")):
        d = lc[k]
        print(f"  {label:10s} rows {d['rows']:,}  parsed {d['parsed']:,}"
              f"  invalid {d['invalid_geometry']}  empty {d['empty_geometry']}"
              f"  oob {d['out_of_range']}  orphan {d['orphan_parent_missing']}"
              f"  precision {d['location_precision']}")
    print("== 连接 ==")
    c = result["connections"]
    print(f"  rows {c['rows']:,}  orphan {c['orphan_total']}  self {c['self_loops']}"
          f"  dup {c['duplicate_rows_same_triple']}  types {c['connection_types']}")
    print("== 每地点覆盖 ==")
    cov = result["coverage"]
    print(f"  places {cov['places_total']:,}  with-name {cov['places_with_name']:,}"
          f"  with-loc {cov['places_with_any_location']:,}"
          f"  point {cov['places_with_point']:,}  polygon {cov['places_with_polygon']:,}"
          f"  line {cov['places_with_linestring']:,}  no-loc {cov['places_without_location']:,}"
          f"  avg names {cov['avg_names_per_place']}")
    print("== 与切片对照 ==")
    v = result["vs_slice"]
    print(f"  slice {v['slice_source_records']:,}  both {v['in_both']:,}"
          f"  only-slice {v['only_in_slice']}  new {v['new_in_full']:,}"
          f"  changed {v['value_changed']}  unchanged {v['value_unchanged']:,}"
          f"  coverage {v['coverage_pct_of_full']}%")
    print("== 跨源候选 ==")
    g = result["cross_source"]
    print(f"  same-name pairs {g['same_name_pairs_excluding_pleiades_self']:,}")
    for k, v in g["coord_nearest_by_dataset_and_distance"].items():
        print(f"    {k:34s} {v:,}")
    print(f"\nJSON -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
