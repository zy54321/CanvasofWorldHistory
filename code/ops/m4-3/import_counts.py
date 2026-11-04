"""M4-3 R1 · 导入数量与承载能力核算（只读）。

回答四件事，全部从源 CSV 与现有 staging 现场计算，不引用任何预设行数：
  1. NEW 集合（v4.1 有、库中无）的地点/名称/位置/连接/来源记录精确增量；
  2. 地点级与位置级两级精度分布，且只统计 NEW 集合；
  3. places.csv 代表点与三类 location 文件的覆盖关系（含"有代表点但无 location 行"）；
  4. V9 需要用到的四类台账计数，以及"无几何"的三种口径。

用法：python ops/m4-3/import_counts.py [--json ops/m4-3/import_counts.json]
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path

CODE = Path(__file__).resolve().parents[2]
GIS = CODE / "data" / "raw" / "pleiades_gis_4_1" / "gis"
STAGING = CODE / "data" / "staging"

URI_RE = re.compile(r"/places/([^/?#]+)")
LOC_FILES = (
    ("location_points.csv", "Point"),
    ("location_polygons.csv", "Polygon"),
    ("location_linestrings.csv", "LineString"),
)


def rows(path: Path):
    with io.open(path, encoding="utf-8-sig", newline="") as f:
        yield from csv.DictReader(f)


def key(v: str) -> str:
    """URI 或裸 id -> 地点 id。"""
    v = (v or "").strip()
    m = URI_RE.search(v)
    return m.group(1) if m else v


def load_slice_place_ids() -> set[str]:
    out = set()
    for r in rows(STAGING / "source_records.csv"):
        if (r["dataset_id"] == "pleiades_gis_4_1_slice"
                and r["external_id_type"] == "pleiades_place_id"
                and str(r.get("is_active", "true")).lower() != "false"):
            out.add((r["external_id"] or "").strip())
    return out


def num(v):
    try:
        s = (v or "").strip()
        return float(s) if s else None
    except ValueError:
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=str(CODE / "ops" / "m4-3" / "import_counts.json"))
    args = ap.parse_args()

    slice_ids = load_slice_place_ids()
    places = {}
    for r in rows(GIS / "places.csv"):
        pid = (r["id"] or "").strip()
        lon, lat = num(r.get("representative_longitude")), num(r.get("representative_latitude"))
        places[pid] = {
            "title": (r.get("title") or "").strip(),
            "precision": (r.get("location_precision") or "").strip() or "(empty)",
            "lon": lon, "lat": lat,
            "has_rep": lon is not None and lat is not None,
            "has_bbox": bool((r.get("bounding_box_wkt") or "").strip()),
        }
    all_ids = set(places)
    new_ids = all_ids - slice_ids

    # ---------- 名称 / 位置按 NEW 过滤 ----------
    names_total = names_new = 0
    name_types_new = Counter()
    for r in rows(GIS / "names.csv"):
        names_total += 1
        if key(r.get("place_id")) in new_ids:
            names_new += 1
            name_types_new[(r.get("name_type") or "").strip() or "(empty)"] += 1

    loc = {}
    for fname, gtype in LOC_FILES:
        total = new = 0
        prec_new = Counter()
        radius_new = Counter()
        places_with = set()
        places_with_new = set()
        for r in rows(GIS / fname):
            total += 1
            pid = key(r.get("place_id"))
            places_with.add(pid)
            if pid not in new_ids:
                continue
            new += 1
            places_with_new.add(pid)
            prec_new[(r.get("location_precision") or "").strip() or "(empty)"] += 1
            rad = num(r.get("accuracy_radius"))
            if rad is None:
                radius_new["null"] += 1
            elif rad < 0:
                radius_new["negative_sentinel"] += 1
            elif rad == 0:
                radius_new["zero"] += 1
            else:
                radius_new["positive"] += 1
        loc[gtype] = {
            "file": fname, "rows_total": total, "rows_new": new,
            "precision_new": dict(prec_new.most_common()),
            "accuracy_radius_new": dict(radius_new.most_common()),
            "places_with_any_row": len(places_with),
            "places_with_row_new": len(places_with_new),
            "_places_with": places_with,
            "_places_with_new": places_with_new,
        }

    # ---------- 代表点 vs location 覆盖 ----------
    def coverage(ids: set) -> dict:
        has_rep = {i for i in ids if places[i]["has_rep"]}
        has_bbox = {i for i in ids if places[i]["has_bbox"]}
        has_loc = set()
        for g in loc.values():
            has_loc |= g["_places_with"]
        has_loc &= ids
        return {
            "places": len(ids),
            "with_rep_point": len(has_rep),
            "with_bbox": len(has_bbox),
            "with_location_rows": len(has_loc),
            "rep_but_no_location": len(has_rep - has_loc),
            "bbox_but_no_location": len(has_bbox - has_loc),
            "rep_and_bbox_but_no_location": len(has_rep & has_bbox - has_loc),
            "no_rep_no_bbox_no_location": len(ids - has_rep - has_bbox - has_loc),
            "no_rep_but_location": len(has_loc - has_rep),
            "no_rep_no_bbox_but_location": len(has_loc - has_rep - has_bbox),
            "_rep_but_no_location_ids": sorted(has_rep - has_loc)[:5],
        }

    cov_all = coverage(all_ids)
    cov_new = coverage(new_ids)
    # 有代表点但无 location 行的地点：precision 分布（决定合成位置行的精度口径）
    rep_only_ids = set()
    _loc_any = set()
    for g in loc.values():
        _loc_any |= g["_places_with"]
    for i in new_ids:
        if places[i]["has_rep"] and i not in _loc_any:
            rep_only_ids.add(i)
    rep_only_prec = Counter(places[i]["precision"] for i in rep_only_ids)

    # ---------- 连接 ----------
    conn_total = 0
    both_all = both_new = self_loop = dangling = 0
    pairs = set()
    triples = Counter()
    one_side_alias = 0
    dangling_examples = []
    for r in rows(GIS / "connections.csv"):
        conn_total += 1
        a, b = key(r.get("place_id")), key(r.get("connects_to"))
        ok_a, ok_b = a in all_ids, b in all_ids
        if not (ok_a and ok_b):
            dangling += 1
            if len(dangling_examples) < 5:
                dangling_examples.append({"place_id": a, "connects_to": b,
                                          "a_ok": ok_a, "b_ok": ok_b})
            continue
        if a == b:
            self_loop += 1
            continue
        both_all += 1
        pairs.add((a, b))
        triples[(a, b, (r.get("connection_type") or "").strip())] += 1
        if a in new_ids and b in new_ids:
            both_new += 1
        elif (a in new_ids) != (b in new_ids):
            one_side_alias += 1

    dup_triples = sum(v - 1 for v in triples.values() if v > 1)
    # 候选行：导入器按 (relation_type, place_id_a, place_id_b) 去重（C09），
    # 与 connection_type 无关，因此行数 = 可解析且非自环的"有序对"数。
    candidate_rows = len(pairs)
    pair_dedup_extra = both_all - candidate_rows

    # ---------- places_accuracy ----------
    acc_rows = acc_neg_total = acc_neg_new = 0
    acc_hull_empty_new = 0
    for r in rows(GIS / "places_accuracy.csv"):
        acc_rows += 1
        pid = key(r.get("place_id"))
        mx, mn = num(r.get("max_accuracy_meters")), num(r.get("min_accuracy_meters"))
        neg = (mx is not None and mx < 0) or (mn is not None and mn < 0)
        if neg:
            acc_neg_total += 1
            if pid in new_ids:
                acc_neg_new += 1
        if pid in new_ids and not (r.get("accuracy_hull") or "").strip():
            acc_hull_empty_new += 1

    # ---------- 无效几何（需修复） ----------
    from shapely import wkt as shapely_wkt
    from shapely.errors import GEOSException

    invalid_total = invalid_new = 0
    invalid_list = []
    for r in rows(GIS / "location_polygons.csv"):
        w = (r.get("geometry_wkt") or "").strip()
        if not w:
            continue
        try:
            g = shapely_wkt.loads(w)
        except (GEOSException, ValueError):
            g = None
        if g is None or not g.is_valid:
            invalid_total += 1
            pid = key(r.get("place_id"))
            if pid in new_ids:
                invalid_new += 1
            if len(invalid_list) < 8:
                invalid_list.append({"place_id": pid, "in_new": pid in new_ids,
                                     "wkt": w[:70]})

    # ---------- 地点级精度（NEW） ----------
    place_prec_new = Counter(places[i]["precision"] for i in new_ids)
    place_prec_all = Counter(places[i]["precision"] for i in all_ids)

    # ---------- 类型附表 ----------
    ppt_rows = ppt_new = 0
    ppt_places_new = set()
    type_hits_new = Counter()
    vocab_label = {}
    for r in rows(GIS / "place_types.csv"):
        vocab_label[(r.get("key") or "").strip()] = (r.get("term") or "").strip()
    for r in rows(GIS / "places_place_types.csv"):
        ppt_rows += 1
        pid = key(r.get("place_id"))
        k = (r.get("place_type") or "").strip()
        if pid in new_ids:
            ppt_new += 1
            ppt_places_new.add(pid)
            type_hits_new[vocab_label.get(k, k) or "(empty)"] += 1
    vocab_keys = set(vocab_label)
    used_keys = set()
    for r in rows(GIS / "places_place_types.csv"):
        used_keys.add((r.get("place_type") or "").strip())

    # 语言标签是否都在语言表里
    lang_codes = set()
    for r in rows(GIS / "languages_and_scripts.csv"):
        for col in ("code", "key", "tag", "id"):
            if r.get(col):
                lang_codes.add(r[col].strip())
                break
    used_langs = Counter()
    for r in rows(GIS / "names.csv"):
        if key(r.get("place_id")) in new_ids:
            t = (r.get("language_tag") or "").strip()
            if t:
                used_langs[t] += 1
    lang_missing = sorted({t for t in used_langs if t not in lang_codes})[:10]

    # ---------- 汇总 ----------
    loc_new_rows = sum(g["rows_new"] for g in loc.values())
    overlap = len(all_ids & slice_ids)
    source_delta = len(new_ids) + names_new + loc_new_rows + conn_total + overlap

    out = {
        "sets": {
            "places_all": len(all_ids),
            "slice_places": len(slice_ids),
            "new_places": len(new_ids),
            "overlap_places": len(all_ids & slice_ids),
            "slice_only_places": len(slice_ids - all_ids),
        },
        "place_precision": {
            "all": dict(place_prec_all.most_common()),
            "new": dict(place_prec_new.most_common()),
        },
        "names": {"rows_total": names_total, "rows_new": names_new,
                  "name_types_new": dict(name_types_new.most_common())},
        "locations": {g: {k: v for k, v in d.items() if not k.startswith("_")}
                      for g, d in loc.items()},
        "locations_total_new_rows": loc_new_rows,
        "coverage": {"all": {k: v for k, v in cov_all.items() if not k.startswith("_")},
                     "new": {k: v for k, v in cov_new.items() if not k.startswith("_")},
                     "new_examples": cov_new["_rep_but_no_location_ids"]},
        "connections": {
            "rows_total": conn_total,
            "resolvable_both_ends": both_all,
            "both_ends_in_new": both_new,
            "one_end_alias_to_slice": one_side_alias,
            "self_loop": self_loop,
            "dangling_endpoint": dangling,
            "dangling_examples": dangling_examples,
            "duplicate_triples_extra_rows": dup_triples,
            "pair_dedup_extra_rows": pair_dedup_extra,
            "distinct_pairs_candidate_rows": candidate_rows,
        },
        "placement_accuracy": {
            "rows": acc_rows,
            "negative_sentinel_total": acc_neg_total,
            "negative_sentinel_new": acc_neg_new,
            "empty_hull_new": acc_hull_empty_new,
        },
        "geometry_invalid": {"total": invalid_total, "in_new": invalid_new,
                             "examples": invalid_list},
        "place_types": {
            "rows_total": ppt_rows,
            "rows_new": ppt_new,
            "places_with_type_new": len(ppt_places_new),
            "places_without_type_new": len(new_ids) - len(ppt_places_new),
            "vocab_keys": len(vocab_keys),
            "used_keys": len(used_keys),
            "used_not_defined": len(used_keys - vocab_keys),
            "top_types_new": dict(type_hits_new.most_common(10)),
        },
        "languages": {
            "vocab_codes": len(lang_codes),
            "distinct_used_new": len(used_langs),
            "used_not_in_vocab": lang_missing,
        },
        "rep_point_materialisation": {
            "new_places_rep_only": len(rep_only_ids),
            "precision": dict(rep_only_prec.most_common()),
            "location_rows_if_materialised": loc_new_rows + len(rep_only_ids),
            "source_delta_if_materialised": (len(new_ids) + names_new
                                             + loc_new_rows + len(rep_only_ids)
                                             + conn_total + len(all_ids & slice_ids)),
            "expected_source_total": 29391 + (len(new_ids) + names_new + loc_new_rows
                                              + conn_total + len(all_ids & slice_ids)),
        },
        "source_record_delta": {
            "places": len(new_ids),
            "names": names_new,
            "locations": loc_new_rows,
            "connections": conn_total,
            "inactive_overlap_places": overlap,
            "total": source_delta,
        },
    }

    Path(args.json).parent.mkdir(parents=True, exist_ok=True)
    Path(args.json).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---- 控制台
    print("== 集合 ==")
    for k, v in out["sets"].items():
        print(f"  {k:22s} {v:,}")
    print("== 地点级精度 ==")
    print("  全部", out["place_precision"]["all"])
    print("  NEW ", out["place_precision"]["new"])
    print("== 名称 / 位置 ==")
    print(f"  names total {names_total:,}  new {names_new:,}")
    for g, d in loc.items():
        print(f"  {g:10s} total {d['rows_total']:,}  new {d['rows_new']:,}"
              f"  prec {d['precision_new']}  radius {d['accuracy_radius_new']}")
    print(f"  新增位置合计 {loc_new_rows:,}")
    print("== 覆盖（代表点 vs location）==")
    for scope in ("all", "new"):
        c = out["coverage"][scope]
        print(f"  {scope:3s} places {c['places']:,} rep {c['with_rep_point']:,}"
              f" bbox {c['with_bbox']:,} loc {c['with_location_rows']:,}"
              f" | rep-无loc {c['rep_but_no_location']:,}"
              f" bbox-无loc {c['bbox_but_no_location']:,}"
              f" 全无 {c['no_rep_no_bbox_no_location']:,}"
              f" | loc-无rep {c['no_rep_but_location']:,}")
    print("== 代表点无 location（NEW）==")
    rpm = out["rep_point_materialisation"]
    print(f"  {rpm['new_places_rep_only']:,} 个，精度 {rpm['precision']}；"
          f"若补位置行 → {rpm['location_rows_if_materialised']:,} 条位置、"
          f"source_record 增量 {rpm['source_delta_if_materialised']:,}")
    print("== 连接 ==")
    for k, v in out["connections"].items():
        if k.endswith("examples"):
            continue
        print(f"  {k:32s} {v:,}")
    print("== 类型附表 ==")
    pt = out["place_types"]
    print(f"  rows {pt['rows_total']:,} new {pt['rows_new']:,}"
          f"  places-with-type(new) {pt['places_with_type_new']:,}"
          f"  无类型 {pt['places_without_type_new']:,}"
          f"  词表 {pt['vocab_keys']} 键 / 被引用 {pt['used_keys']} / 未定义 {pt['used_not_defined']}")
    print(f"  语言：词表 {out['languages']['vocab_codes']} 个代码，NEW 用到 "
          f"{out['languages']['distinct_used_new']} 种，不在词表 {out['languages']['used_not_in_vocab']}")
    print("== 精度哨兵 ==", out["placement_accuracy"])
    print("== 无效多边形 ==", {k: v for k, v in out["geometry_invalid"].items() if k != "examples"})
    print("== source_record 增量 ==")
    for k, v in out["source_record_delta"].items():
        print(f"  {k:26s} {v:,}")
    print(f"\nJSON -> {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
