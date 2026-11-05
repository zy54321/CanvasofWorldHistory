"""阶段 A3：地图视野与列表的真实耗时测量。

三件事必须分开测，否则"快了 165 倍"这种结论站不住：
  1. 数据库侧（psql EXPLAIN ANALYZE 之外的纯执行时间）—— 用 psycopg2 直接跑同一条 SQL；
  2. HTTP 侧（API 序列化 + 网络）—— 用 urllib 计时；
  3. 前端渲染 —— 由 bench_front.mjs 在真实 Chrome 里测。

每项先预热 3 次再测 30 次，输出 P50/P95/max，不用单次最快值。
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, List

CODE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(CODE / "ops" / ".deps"))
sys.path.insert(0, str(CODE / "ops"))

import psycopg2  # noqa: E402
from import_staging import load_env  # noqa: E402

VIEWS = {
    "rome": (12.30, 41.70, 12.60, 42.00),
    "world": (-180.0, -74.0, 180.0, 82.0),
    "beijing": (116.0, 39.0, 117.0, 40.5),
}

MAP_PATH = "/api/v1/places/map?bbox={w},{s},{e},{n}&limit=400"

# 与 PlaceQueryService.mapFeatures 现在执行的同一条 SQL（搬过来只为测量，不参与业务）
MAP_SQL = """
WITH cand AS (
    SELECT DISTINCT ON (l.place_id)
           l.place_id, l.location_id, l.representative_lon, l.representative_lat,
           l.location_precision, l.uncertainty_m, l.crs_confidence,
           l.valid_from_year_astro, l.valid_to_year_astro, l.time_bound_type,
           l.geom_type
      FROM historical_place_location l
      LEFT JOIN source_record sr ON sr.source_record_id = l.source_record_id
     WHERE l.geom IS NOT NULL
       AND l.crs_confidence <> 'unknown'
       AND l.record_status <> 'rejected'
       AND (sr.source_record_id IS NULL OR sr.is_active)
       AND ST_Intersects(l.geom, ST_MakeEnvelope(%(w)s, %(s)s, %(e)s, %(n)s, 4326))
     ORDER BY l.place_id,
              CASE l.geom_type
                   WHEN 'Polygon' THEN 0 WHEN 'MultiPolygon' THEN 0
                   WHEN 'LineString' THEN 1 ELSE 2 END,
              l.location_id
), picked AS (
    SELECT c.place_id, c.location_id, c.representative_lon, c.representative_lat,
           c.location_precision, c.uncertainty_m, c.crs_confidence,
           c.valid_from_year_astro, c.valid_to_year_astro, c.time_bound_type,
           c.geom_type,
           p.canonical_name, p.canonical_name_lang, p.place_type, p.dataset_id,
           d.display_name AS dataset_name, p.record_status
      FROM cand c
      JOIN historical_place p ON p.place_id = c.place_id
      JOIN data_dataset d ON d.dataset_id = p.dataset_id
     WHERE p.merged_into_place_id IS NULL
     ORDER BY md5(c.place_id::text)
     LIMIT %(lim)s
)
SELECT k.place_id, alt.alt_name, alt.alt_lang, ST_AsGeoJSON(l.geom) AS geojson
  FROM picked k
  JOIN historical_place_location l ON l.location_id = k.location_id
  LEFT JOIN LATERAL (
        SELECT n.name_text AS alt_name, n.name_lang AS alt_lang
          FROM historical_place_name n
         WHERE n.place_id = k.place_id
           AND btrim(coalesce(n.name_text, '')) <> ''
         ORDER BY CASE n.name_type WHEN 'primary' THEN 0 ELSE 1 END, n.name_id
         LIMIT 1
  ) alt ON true
 ORDER BY md5(k.place_id::text)
"""

LIST_PATH = "/api/v1/places/admin?page={page}&size=50"


def pct(vals: List[float], p: float) -> float:
    if not vals:
        return float("nan")
    s = sorted(vals)
    k = (len(s) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def summarise(vals: List[float]) -> Dict[str, Any]:
    return {
        "n": len(vals),
        "p50_ms": round(pct(vals, 0.50) * 1000, 2),
        "p95_ms": round(pct(vals, 0.95) * 1000, 2),
        "max_ms": round(max(vals) * 1000, 2),
        "min_ms": round(min(vals) * 1000, 2),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="canvas_history")
    ap.add_argument("--api", default="http://127.0.0.1:8088")
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--warmup", type=int, default=3)
    ap.add_argument("--json", default="ops/reports/v1b/bench_views.json")
    args = ap.parse_args()

    env = load_env()
    conn = psycopg2.connect(
        host="127.0.0.1",
        port=int(env.get("DB_HOST_PORT", "55432")),
        dbname=args.db,
        user=env["POSTGRES_USER"],
        password=env["POSTGRES_PASSWORD"],
    )
    conn.autocommit = True
    cur = conn.cursor()

    out: Dict[str, Any] = {"db": args.db, "n": args.n, "views": {}, "list": {}}

    for name, (w, s, e, n) in VIEWS.items():
        params = {"w": w, "s": s, "e": e, "n": n, "lim": 400}
        sql_t: List[float] = []
        http_t: List[float] = []
        body = None
        for i in range(args.warmup + args.n):
            t0 = time.perf_counter()
            cur.execute(MAP_SQL, params)
            rows = cur.fetchall()
            t1 = time.perf_counter()

            url = args.api + MAP_PATH.format(w=w, s=s, e=e, n=n)
            t2 = time.perf_counter()
            with urllib.request.urlopen(url, timeout=120) as r:
                body = r.read()
            t3 = time.perf_counter()
            if i >= args.warmup:
                sql_t.append(t1 - t0)
                http_t.append(t3 - t2)

        feats = json.loads(body)["features"]
        out["views"][name] = {
            "bbox": [w, s, e, n],
            "rows": len(rows),
            "features": len(feats),
            "bytes": len(body),
            "db": summarise(sql_t),
            "http": summarise(http_t),
        }
        print(f"{name:9s} rows={len(rows):>4d} features={len(feats):>4d} "
              f"db P50={out['views'][name]['db']['p50_ms']:>8.2f}ms "
              f"P95={out['views'][name]['db']['p95_ms']:>8.2f}ms | "
              f"http P50={out['views'][name]['http']['p50_ms']:>8.2f}ms "
              f"P95={out['views'][name]['http']['p95_ms']:>8.2f}ms")

    # 内容管理的列表接口（阶段 B 的目标）
    for page in (1, 500, 1200):
        path = LIST_PATH.format(page=page)
        ts: List[float] = []
        code = None
        for i in range(args.warmup + args.n):
            t0 = time.perf_counter()
            try:
                with urllib.request.urlopen(args.api + path, timeout=60) as r:
                    code = r.status
                    r.read()
            except Exception as ex:  # noqa: BLE001
                code = getattr(ex, "code", str(ex))
                break
            ts.append(time.perf_counter() - t0)
        if ts:
            out["list"][f"page{page}"] = {"status": code, **summarise(ts)}
            print(f"list page={page:<5d} status={code} "
                  f"P50={out['list'][f'page{page}']['p50_ms']:>8.2f}ms "
                  f"P95={out['list'][f'page{page}']['p95_ms']:>8.2f}ms")
        else:
            out["list"][f"page{page}"] = {"status": code}
            print(f"list page={page:<5d} status={code} (不可用)")

    dest = CODE / args.json
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n写入 {dest}")


if __name__ == "__main__":
    main()
