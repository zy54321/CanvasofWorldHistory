#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""M4-4c 测试夹具：从隔离库里挑出可复现的样本，写成 fixtures.json。

为什么要单独生成夹具
--------------------
E2E 里的"面/线地点""多位置混合精度""无坐标地点""时间轴样本"都不能靠随机取，
否则每次跑出来的结论不可比。这里用**确定性规则**（固定 bbox、固定排序键、
固定排除集合）选出样本，并把"期望值"一并写出，测试脚本只做断言。

已知遗留的处理（施工指令 §五）
------------------------------
M4-4b 已知 629 个地点存在 `derived_value_mismatch`（地点级时间包络口径分歧）。
时间轴样本**优先排除**这些地点；如果排除后凑不够 10 个，脚本会如实报出实际样本数，
不凑数、不用别的口径顶替。

用法：
    cd code
    PYTHONPATH=ops/.deps python ops/m4-4c/make_fixtures.py --db canvas_history_m4_4b \
        --json ops/reports/m4-4c/fixtures.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

CODE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(CODE_ROOT / "ops"))

P4 = "pleiades_gis_4_1"

#: 罗马老城 bbox（west,south,east,north）。固定值，便于复跑比对。
ROME_BBOX = (12.30, 41.70, 12.60, 42.00)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    parser.add_argument("--json", default=str(CODE_ROOT / "ops" / "reports" / "m4-4c" / "fixtures.json"))
    args = parser.parse_args()

    import psycopg2  # noqa: PLC0415
    import import_staging as importer  # noqa: PLC0415

    env = importer.load_env()
    conn = psycopg2.connect(host="127.0.0.1", port=int(env.get("DB_HOST_PORT", "15432")),
                            dbname=args.db, user=env["POSTGRES_USER"],
                            password=env["POSTGRES_PASSWORD"])
    conn.set_session(readonly=True, autocommit=True)
    cur = conn.cursor()

    def rows(sql: str, params: tuple = ()) -> List[tuple]:
        cur.execute(sql, params)
        return cur.fetchall()

    fixtures: Dict[str, Any] = {
        "db": args.db,
        "rome_bbox": list(ROME_BBOX),
        "selection_rules": {
            "rome_bbox": "固定 12.30,41.70,12.60,42.00",
            "geometry_samples": "v4.1 数据集中 geom 与 bbox 相交、按 place_id 升序取前 3 个 Polygon / 3 个 LineString",
            "multi_location": "v4.1 中位置数≥3 且同时含 precise 与 rough、按位置数降序取前 2",
            "timeline": "v4.1 中只有 1 条名称、该名称有完整纪年、且不在 derived_value_mismatch 集合内、"
                        "有可用几何；按 md5(place_id) 排序取前 10（单名保证年份过滤无歧义）",
        },
    }

    # ---- 1. 罗马 bbox 内按几何分类的样本 ----------------------------------
    cur.execute("""
        SELECT 'Polygon' AS kind, p.place_id, p.canonical_name, l.geom_type,
               l.representative_lon, l.representative_lat, l.location_precision
          FROM historical_place p
          JOIN LATERAL (SELECT * FROM historical_place_location x
                         WHERE x.place_id = p.place_id AND x.geom IS NOT NULL
                         ORDER BY x.location_id LIMIT 1) l ON TRUE
         WHERE p.dataset_id = %s AND l.geom_type IN ('Polygon','MultiPolygon')
           AND EXISTS (SELECT 1 FROM historical_place_location y
                        WHERE y.place_id = p.place_id AND y.geom IS NOT NULL
                          AND ST_Intersects(y.geom, ST_MakeEnvelope(%s,%s,%s,%s,4326)))
         ORDER BY p.place_id LIMIT 3
        """, (P4,) + ROME_BBOX)
    poly = cur.fetchall()
    cur.execute("""
        SELECT 'LineString' AS kind, p.place_id, p.canonical_name, l.geom_type,
               l.representative_lon, l.representative_lat, l.location_precision
          FROM historical_place p
          JOIN LATERAL (SELECT * FROM historical_place_location x
                         WHERE x.place_id = p.place_id AND x.geom IS NOT NULL
                         ORDER BY x.location_id LIMIT 1) l ON TRUE
         WHERE p.dataset_id = %s AND l.geom_type = 'LineString'
           AND EXISTS (SELECT 1 FROM historical_place_location y
                        WHERE y.place_id = p.place_id AND y.geom IS NOT NULL
                          AND ST_Intersects(y.geom, ST_MakeEnvelope(%s,%s,%s,%s,4326)))
         ORDER BY p.place_id LIMIT 3
        """, (P4,) + ROME_BBOX)
    line = cur.fetchall()
    fixtures["geometry_samples"] = [
        {"kind": r[0], "place_id": r[1], "name": r[2], "geom_type": r[3],
         "rep_lon": float(r[4]), "rep_lat": float(r[5]), "precision": r[6]}
        for r in list(poly) + list(line)
    ]

    # ---- 2. 罗马 bbox 内的类型计数（用于地图断言） ------------------------
    cur.execute("""
        SELECT l.geom_type, count(DISTINCT p.place_id)
          FROM historical_place p JOIN historical_place_location l USING (place_id)
         WHERE p.dataset_id = %s AND l.geom IS NOT NULL
           AND ST_Intersects(l.geom, ST_MakeEnvelope(%s,%s,%s,%s,4326))
         GROUP BY 1 ORDER BY 1
        """, (P4,) + ROME_BBOX)
    fixtures["rome_geom_counts"] = {k: v for k, v in cur.fetchall()}

    # ---- 3. 雅典 / 庞贝 搜索与多位置 --------------------------------------
    cur.execute("""
        SELECT p.place_id, p.canonical_name, n.name_text, n.name_lang,
               (SELECT count(*) FROM historical_place_location l WHERE l.place_id=p.place_id)
          FROM historical_place p JOIN historical_place_name n USING (place_id)
         WHERE p.dataset_id = %s AND lower(n.name_text) = 'athens' AND n.name_lang = 'en'
         ORDER BY p.place_id LIMIT 1
        """, (P4,))
    row = cur.fetchone()
    fixtures["athens"] = ({"place_id": row[0], "canonical_name": row[1],
                           "name_text": row[2], "name_lang": row[3], "location_count": row[4]}
                          if row else None)

    cur.execute("""
        SELECT p.place_id, p.canonical_name,
               (SELECT count(*) FROM historical_place_location l WHERE l.place_id=p.place_id)
          FROM historical_place p
         WHERE p.dataset_id = %s AND p.canonical_name = 'Pompeii' LIMIT 1
        """, (P4,))
    row = cur.fetchone()
    fixtures["pompeii"] = ({"place_id": row[0], "canonical_name": row[1],
                            "location_count": row[2]} if row else None)

    cur.execute("""
        SELECT p.place_id, p.canonical_name, count(l.*) AS n,
               count(*) FILTER (WHERE l.location_precision='precise') AS precise,
               count(*) FILTER (WHERE l.location_precision='rough') AS rough,
               string_agg(DISTINCT l.geom_type, '/') AS types
          FROM historical_place p JOIN historical_place_location l USING (place_id)
         WHERE p.dataset_id = %s
         GROUP BY p.place_id, p.canonical_name
        HAVING count(*) >= 3
           AND count(*) FILTER (WHERE l.location_precision='rough') > 0
           AND count(*) FILTER (WHERE l.location_precision='precise') > 0
         ORDER BY count(l.*) DESC, p.place_id LIMIT 2
        """, (P4,))
    fixtures["multi_location"] = [
        {"place_id": r[0], "name": r[1], "location_count": r[2],
         "precise": r[3], "rough": r[4], "geom_types": r[5]}
        for r in cur.fetchall()
    ]

    # ---- 4. 无坐标地点（7,200 个之一） -----------------------------------
    # 必须能被"名称搜索"命中：搜索走的是 historical_place_name.name_text，
    # 不是 place.canonical_name，所以这里连名字表一起挑，避免夹具选到搜不到的地点。
    cur.execute("""
        SELECT p.place_id, p.canonical_name, n.name_text
          FROM historical_place p
          JOIN historical_place_name n ON n.place_id = p.place_id
         WHERE p.dataset_id = %s
           AND NOT EXISTS (SELECT 1 FROM historical_place_location l WHERE l.place_id=p.place_id)
           AND n.name_text ~ '^[A-Za-z][A-Za-z ]{6,}$'
           AND n.name_type = 'primary'
         ORDER BY length(n.name_text), p.place_id LIMIT 3
        """, (P4,))
    fixtures["no_geometry"] = [
        {"place_id": r[0], "canonical_name": r[1], "name_text": r[2]}
        for r in cur.fetchall()
    ]

    # ---- 5. 时间轴样本（排除 820 条已知冲突涉及的地点） -------------------
    cur.execute("""
        WITH mism AS (
            SELECT DISTINCT place_id FROM data_quality_issue
             WHERE issue_type='derived_value_mismatch' AND place_id IS NOT NULL
        )
        SELECT * FROM (
            -- 一个地点可能有多条 primary 名称（不同语种），先按 place 去重再抽样，
            -- 否则 10 条样本可能只覆盖 5 个地点。
            SELECT DISTINCT ON (p.place_id)
                   p.place_id, p.canonical_name, n.name_text,
                   n.valid_from_year_astro, n.valid_to_year_astro, n.time_bound_type
              FROM historical_place p
              JOIN historical_place_name n ON n.place_id = p.place_id
             WHERE p.dataset_id = %s
               AND n.name_type = 'primary'
               AND n.valid_from_year_astro IS NOT NULL
               AND n.valid_to_year_astro IS NOT NULL
               AND n.valid_to_year_astro > n.valid_from_year_astro
               AND p.place_id NOT IN (SELECT place_id FROM mism)
               AND EXISTS (SELECT 1 FROM historical_place_location l
                            WHERE l.place_id = p.place_id AND l.geom IS NOT NULL)
               -- 只取"整条记录只有 1 个名称"的地点：这样按年份过滤时
               -- 不会因为另一条名称的时间窗覆盖该年而出现"应排除却仍命中"的歧义
               AND (SELECT count(*) FROM historical_place_name n2
                     WHERE n2.place_id = p.place_id) = 1
             ORDER BY p.place_id, n.name_id
        ) u
         ORDER BY md5(place_id::text) LIMIT 10
        """, (P4,))
    timeline = cur.fetchall()
    fixtures["timeline_samples"] = [
        {"place_id": r[0], "canonical_name": r[1], "name_text": r[2],
         "valid_from": r[3], "valid_to": r[4], "time_bound_type": r[5],
         "inside_year": r[3], "outside_year": r[4] + 1, "single_name": True,
         "ui_from_label": f"前 {1 - r[3]}" if r[3] <= 0 else str(r[3])}
        for r in timeline
    ]
    cur.execute("""
        WITH mism AS (
            SELECT DISTINCT place_id FROM data_quality_issue
             WHERE issue_type='derived_value_mismatch' AND place_id IS NOT NULL
        )
        SELECT count(*) FROM (
            SELECT p.place_id FROM historical_place p
              JOIN historical_place_name n ON n.place_id = p.place_id
             WHERE p.dataset_id = %s AND n.name_type='primary'
               AND n.valid_from_year_astro IS NOT NULL AND n.valid_to_year_astro IS NOT NULL
               AND n.valid_to_year_astro > n.valid_from_year_astro
               AND p.place_id NOT IN (SELECT place_id FROM mism)
        ) t
        """, (P4,))
    fixtures["timeline_pool_size"] = cur.fetchone()[0]

    conn.close()

    out = Path(args.json)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(fixtures, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"夹具 → {out}")
    print(f"  罗马 bbox 几何计数      {fixtures['rome_geom_counts']}")
    print(f"  几何样本               {len(fixtures['geometry_samples'])} 条")
    print(f"  雅典 / 庞贝            {fixtures['athens']} / {fixtures['pompeii']}")
    print(f"  多位置混合精度          {[m['place_id'] for m in fixtures['multi_location']]}")
    print(f"  无坐标地点              {[n['place_id'] for n in fixtures['no_geometry']]}")
    print(f"  时间轴样本              {len(fixtures['timeline_samples'])} 条"
          f"（候选池 {fixtures['timeline_pool_size']:,}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
