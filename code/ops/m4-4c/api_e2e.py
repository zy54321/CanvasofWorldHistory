#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""M4-4c API 级 E2E：地图 / 搜索 / 详情 / 时间轴。

只调用隔离库上的只读 API（默认 127.0.0.1:8089，连 canvas_history_m4_4b），
并用 psycopg2 直接查同一个库交叉验证"接口返回的坐标/类型"与"库里存的几何"是否一致。

判据分组（对应施工指令 §三 / §四 / §五）：
  E1 地图：罗马 bbox 返回面/线来源的地点，HTTP 200，meta 自洽
  E2 几何：坐标合法，且与库里 representative 坐标一致；类型与库里 geom_type 一致
  E3 面/线详情：详情能打开，位置行带 geomType、hasGeom、精度
  E4 无坐标地点：名称可搜到、详情可打开、位置为空（没有坐标就不该有坐标）
  E5 搜索：雅典 / 庞贝 命中新增 Pleiades 地点
  E6 多位置 + 精度：4 条位置、precise/rough 混排，不出现整体 unknown 降级
  E7 溯源：数据集为 pleiades_gis_4_1，sourceRecords 带 rawFile
  E8 时间轴：10 个样本在有效年内命中、有效年外不命中，纪年与库里一致
  E9 地图-时间轴联动：被年份过滤命中的地点，其坐标能在对应 bbox 的地图查询里找到

用法：
    cd code
    PYTHONPATH=ops/.deps python ops/m4-4c/api_e2e.py \
        --db canvas_history_m4_4b --api http://127.0.0.1:8089 \
        --fixtures ops/reports/m4-4c/fixtures.json --json ops/reports/m4-4c/api_e2e.json
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

CODE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(CODE_ROOT / "ops"))


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


def http_json(url: str) -> Tuple[int, Any]:
    """GET one URL and return ``(status, parsed_json_or_text)``."""
    try:
        with urllib.request.urlopen(url, timeout=20) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, json.loads(body) if body else None
    except urllib.error.HTTPError as exc:  # type: ignore[attr-defined]
        return exc.code, exc.read().decode("utf-8", "replace")
    except Exception as exc:  # noqa: BLE001
        return 0, str(exc)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    parser.add_argument("--api", default="http://127.0.0.1:8089")
    parser.add_argument("--fixtures", default=str(CODE_ROOT / "ops" / "reports" / "m4-4c" / "fixtures.json"))
    parser.add_argument("--json", default=str(CODE_ROOT / "ops" / "reports" / "m4-4c" / "api_e2e.json"))
    args = parser.parse_args()

    import psycopg2  # noqa: PLC0415
    import import_staging as importer  # noqa: PLC0415

    fx = json.loads(Path(args.fixtures).read_text(encoding="utf-8"))
    env = importer.load_env()
    conn = psycopg2.connect(host="127.0.0.1", port=int(env.get("DB_HOST_PORT", "15432")),
                            dbname=args.db, user=env["POSTGRES_USER"],
                            password=env["POSTGRES_PASSWORD"])
    conn.set_session(readonly=True, autocommit=True)
    cur = conn.cursor()
    api = args.api.rstrip("/")
    report = Report()

    def one(sql: str, params: tuple = ()) -> Any:
        cur.execute(sql, params)
        return cur.fetchone()[0]

    print(f"M4-4c API E2E  db={args.db}  api={api}")
    print()

    # =============================================================== E1
    print("E1 地图：罗马 bbox")
    bbox = fx["rome_bbox"]
    bbox_str = ",".join(f"{v}" for v in bbox)
    status, fc = http_json(f"{api}/api/v1/places/map?bbox={bbox_str}&limit=2000")
    report.expect("E1", "HTTP 状态", status, 200)
    report.check("E1", "返回 FeatureCollection",
                 isinstance(fc, dict) and fc.get("type") == "FeatureCollection",
                 str(type(fc).__name__))
    feats = (fc or {}).get("features") or []
    meta = (fc or {}).get("meta") or {}
    report.check("E1", "有要素", len(feats) > 0, f"{len(feats)} 条")
    report.expect("E1", "meta.returned == features 长度", meta.get("returned"), len(feats))

    db_total = one("""
        SELECT count(DISTINCT l.place_id)
          FROM historical_place_location l
          LEFT JOIN source_record sr ON sr.source_record_id = l.source_record_id
         WHERE l.geom IS NOT NULL AND l.crs_confidence <> 'unknown'
           AND l.record_status <> 'rejected'
           AND (sr.source_record_id IS NULL OR sr.is_active)
           AND ST_Intersects(l.geom, ST_MakeEnvelope(%s,%s,%s,%s,4326))
        """, tuple(bbox))
    report.expect("E1", "meta.totalInBbox 与库内计数一致", meta.get("totalInBbox"), db_total)

    by_id = {f["id"]: f for f in feats}
    sample_ids = [g["place_id"] for g in fx["geometry_samples"]]
    missing = [pid for pid in sample_ids if pid not in by_id]
    report.check("E1", "面/线样本出现在 bbox 结果中", not missing,
                 f"缺失 {missing}" if missing else f"{len(sample_ids)} 个全部命中")

    # =============================================================== E2
    print("\nE2 几何：坐标与类型")
    bad_range = [f["id"] for f in feats
                 if not (isinstance(f["geometry"]["coordinates"], list)
                         and len(f["geometry"]["coordinates"]) == 2
                         and -180 <= f["geometry"]["coordinates"][0] <= 180
                         and -90 <= f["geometry"]["coordinates"][1] <= 90)]
    report.check("E2", "全部要素坐标在合法经纬度范围", not bad_range, f"越界 {bad_range[:5]}")
    report.check("E2", "全部要素 geometry.type = Point",
                 all(f["geometry"]["type"] == "Point" for f in feats), "")

    # 与库里的 representative 坐标逐点比对（类型不同的地点用代表点，这是产品的既定口径）
    coord_bad = []
    type_bad = []
    for g in fx["geometry_samples"]:
        f = by_id.get(g["place_id"])
        if not f:
            continue
        lon, lat = f["geometry"]["coordinates"]
        if abs(lon - g["rep_lon"]) > 1e-9 or abs(lat - g["rep_lat"]) > 1e-9:
            coord_bad.append((g["place_id"], (lon, lat), (g["rep_lon"], g["rep_lat"])))
        db_type = one("""SELECT l.geom_type FROM historical_place_location l
                          WHERE l.place_id=%s AND l.geom IS NOT NULL
                          ORDER BY l.location_id LIMIT 1""", (g["place_id"],))
        if db_type != g["geom_type"]:
            type_bad.append((g["place_id"], db_type, g["geom_type"]))
    report.check("E2", "面/线地点：地图坐标 = 库内代表坐标", not coord_bad, str(coord_bad[:3]))
    report.check("E2", "面/线地点：库内 geom_type 与夹具一致", not type_bad, str(type_bad[:3]))
    report.check("E2", "样本中确实含 Polygon 与 LineString",
                 {g["geom_type"] for g in fx["geometry_samples"]} >= {"Polygon", "LineString"},
                 str(sorted({g['geom_type'] for g in fx['geometry_samples']})))

    # =============================================================== E3
    print("\nE3 面/线详情")
    for g in fx["geometry_samples"]:
        st, d = http_json(f"{api}/api/v1/places/{g['place_id']}")
        locs = (d or {}).get("locations") or []
        types = {l["geomType"] for l in locs}
        ok = (st == 200 and locs and g["geom_type"] in types
              and all(l["hasGeom"] for l in locs)
              and all((l["locationPrecision"] or "") != "" for l in locs))
        report.check("E3", f"place {g['place_id']}（{g['name'][:18]}，{g['geom_type']}）",
                     ok, f"HTTP {st} 位置 {len(locs)} 类型 {sorted(types)}")

    # =============================================================== E4
    print("\nE4 无坐标地点")
    ng = fx["no_geometry"][0]
    st, page = http_json(
        f"{api}/api/v1/places?keyword={urllib.parse.quote(ng['name_text'])}&size=50")
    hits = (page or {}).get("items") or []
    hit = next((h for h in hits if h["placeId"] == ng["place_id"]), None)
    report.expect("E4", f"名称「{ng['name_text']}」能搜到 place {ng['place_id']}", hit is not None, True)
    report.check("E4", "该命中没有代表坐标（前端据此不上图）",
                 hit is not None and hit.get("representativeLon") is None
                 and hit.get("representativeLat") is None,
                 f"lon={hit.get('representativeLon') if hit else None}")
    st, d = http_json(f"{api}/api/v1/places/{ng['place_id']}")
    report.expect("E4", "详情 HTTP", st, 200)
    report.expect("E4", "详情位置数为 0", len(((d or {}).get("locations") or [])), 0)
    report.expect("E4", "库里也确实没有任何位置行",
                  one("SELECT count(*) FROM historical_place_location WHERE place_id=%s",
                      (ng["place_id"],)), 0)
    # 用它的名字所在纬度带做一个 bbox 查询，确认地图接口不会凭空造出这个点
    st, fc2 = http_json(f"{api}/api/v1/places/map?bbox=-180,-90,180,90&limit=2000")
    all_ids = {f["id"] for f in (fc2 or {}).get("features") or []}
    report.check("E4", "全球 bbox 采样里也不含该地点（无坐标即不入图）",
                 ng["place_id"] not in all_ids, f"采样 {len(all_ids)} 条")

    # =============================================================== E5
    print("\nE5 雅典 / 庞贝 搜索")
    for label, key in (("雅典", "athens"), ("庞贝", "pompeii")):
        target = fx[key]
        kw = target["name_text"] if key == "athens" else target["canonical_name"]
        st, page = http_json(f"{api}/api/v1/places?keyword={urllib.parse.quote(kw)}&size=50")
        items = (page or {}).get("items") or []
        ids = [i["placeId"] for i in items]
        report.check("E5", f"{label}：关键词「{kw}」命中 {target['place_id']}",
                     target["place_id"] in ids, f"HTTP {st}，命中 {len(items)} 条")
        st2, d = http_json(f"{api}/api/v1/places/{target['place_id']}")
        report.expect("E5", f"{label}：详情 HTTP", st2, 200)
        report.expect("E5", f"{label}：详情位置数", len(((d or {}).get("locations") or [])),
                      target["location_count"])

    # =============================================================== E6
    print("\nE6 多位置与精度")
    for m in fx["multi_location"]:
        st, d = http_json(f"{api}/api/v1/places/{m['place_id']}")
        locs = (d or {}).get("locations") or []
        prec = [l["locationPrecision"] for l in locs]
        report.expect("E6", f"place {m['place_id']} 位置数", len(locs), m["location_count"])
        report.expect("E6", f"place {m['place_id']} precise 条数", prec.count("precise"), m["precise"])
        report.expect("E6", f"place {m['place_id']} rough 条数", prec.count("rough"), m["rough"])
        report.check("E6", f"place {m['place_id']} 没有把精度整体降级为 unknown",
                     "unknown" not in prec, str(sorted(set(prec))))
        geoms = {l["geomType"] for l in locs}
        report.check("E6", f"place {m['place_id']} 位置类型多样（{sorted(geoms)}）",
                     len(geoms) >= 2, str(sorted(geoms)))

    # =============================================================== E7
    print("\nE7 来源溯源")
    st, d = http_json(f"{api}/api/v1/places/150913")
    report.expect("E7", "datasetId", (d or {}).get("datasetId"), "pleiades_gis_4_1")
    report.check("E7", "datasetName 显示 Pleiades 4.1",
                 "Pleiades" in ((d or {}).get("datasetName") or "")
                 and "4.1" in ((d or {}).get("datasetName") or ""),
                 (d or {}).get("datasetName"))
    report.expect("E7", "datasetVersion", (d or {}).get("datasetVersion"), "4.1")
    report.expect("E7", "sourceId", (d or {}).get("sourceId"), "pleiades")
    srs = (d or {}).get("sourceRecords") or []
    report.check("E7", "sourceRecords 非空且带 rawFile",
                 bool(srs) and all(s.get("rawFile") for s in srs),
                 f"{len(srs)} 条，示例 {srs[0]['rawFile'] if srs else None}")
    known = {"places.csv", "names.csv", "location_points.csv", "location_linestrings.csv",
             "location_polygons.csv", "connections.csv"}
    report.check("E7", "sourceRecords.rawFile 都是 v4.1 的已知文件",
                 all(s["rawFile"] in known for s in srs),
                 str(sorted({s["rawFile"] for s in srs})))

    # =============================================================== E8
    print("\nE8 时间轴（10 个样本，均为单名地点，已排除 derived_value_mismatch 集合）")
    timeline_rows = []
    for t in fx["timeline_samples"]:
        kw = urllib.parse.quote(t["name_text"])
        st_in, page_in = http_json(f"{api}/api/v1/places?keyword={kw}&year={t['inside_year']}&size=50")
        st_out, page_out = http_json(f"{api}/api/v1/places?keyword={kw}&year={t['outside_year']}&size=50")
        ids_in = [i["placeId"] for i in ((page_in or {}).get("items") or [])]
        ids_out = [i["placeId"] for i in ((page_out or {}).get("items") or [])]
        hit = next((i for i in ((page_in or {}).get("items") or [])
                    if i["placeId"] == t["place_id"]), None)
        ok_in = t["place_id"] in ids_in
        ok_out = t["place_id"] not in ids_out
        ok_years = (hit is not None
                    and hit.get("validFromYear") == t["valid_from"]
                    and hit.get("validToYear") == t["valid_to"])
        report.check("E8", f"{t['place_id']} {t['name_text'][:18]}：{t['inside_year']} 命中 / "
                           f"{t['outside_year']} 不命中 / 纪年一致",
                     ok_in and ok_out and ok_years,
                     f"in={ok_in} out={ok_out} years={ok_years}"
                     f"（{hit.get('validFromYear') if hit else '-'}..{hit.get('validToYear') if hit else '-'}）")
        timeline_rows.append({"place_id": t["place_id"], "name": t["name_text"],
                              "inside_year": t["inside_year"], "outside_year": t["outside_year"],
                              "hit_inside": ok_in, "hit_outside": ok_out, "years_match": ok_years})

    bce = [t for t in fx["timeline_samples"] if t["valid_from"] <= 0]
    ce = [t for t in fx["timeline_samples"] if t["valid_from"] > 0]
    report.check("E8", "样本覆盖 BCE 与 CE 两侧", bool(bce) and bool(ce),
                 f"BCE {len(bce)} 条 / CE {len(ce)} 条")

    # =============================================================== E9
    print("\nE9 地图-时间轴联动（命中地点的坐标可在地图上查到）")
    for t in fx["timeline_samples"][:5]:
        cur.execute("""SELECT l.representative_lon, l.representative_lat
                         FROM historical_place_location l
                        WHERE l.place_id=%s AND l.geom IS NOT NULL
                        ORDER BY l.location_id LIMIT 1""", (t["place_id"],))
        lon, lat = cur.fetchone()
        pad = 0.05
        bb = f"{lon-pad},{lat-pad},{lon+pad},{lat+pad}"
        st, fc3 = http_json(f"{api}/api/v1/places/map?bbox={bb}&limit=200")
        ids = {f["id"] for f in (fc3 or {}).get("features") or []}
        report.check("E9", f"{t['place_id']} 在自身坐标 bbox 内可查得", t["place_id"] in ids,
                     f"bbox={bb} HTTP {st} 返回 {len(ids)} 条")

    conn.close()

    # =============================================================== 汇总
    print("\n" + "=" * 72)
    print(f"判据 {len(report.items)} 条：通过 {len(report.items)-len(report.failures)}，"
          f"失败 {len(report.failures)}")
    for item in report.failures:
        print(f"  ✗ [{item['section']}] {item['name']} — {item['detail']}")

    payload = {
        "db": args.db,
        "api": api,
        "ok": report.ok,
        "checks": len(report.items),
        "failures": len(report.failures),
        "rome_bbox": bbox,
        "rome_features": len(feats),
        "timeline": timeline_rows,
        "items": report.items,
    }
    Path(args.json).parent.mkdir(parents=True, exist_ok=True)
    Path(args.json).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n报告 → {args.json}")
    return 0 if report.ok else 1


if __name__ == "__main__":
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
