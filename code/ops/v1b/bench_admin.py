"""阶段 B 内容管理性能测量：常规翻页、深翻页、各筛选组合。

目标：常规本地地点列表翻页 P95 ≤ 300ms。
测法与前一轮一致：预热 3 次，再测 30 次，取 P50/P95；不用单次最快值。
"""
from __future__ import annotations

import argparse
import json
import statistics
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List

CODE = Path(__file__).resolve().parents[2]

CASES = [
    ("all_p1", {"page": 1}),
    ("all_p50", {"page": 50}),
    ("all_p500", {"page": 500}),
    ("all_deep", {"page": 1200}),
    ("point_p1", {"page": 1, "geomType": "point"}),
    ("line_p1", {"page": 1, "geomType": "line"}),
    ("polygon_p1", {"page": 1, "geomType": "polygon"}),
    ("none_p1", {"page": 1, "geomType": "none"}),
    ("name_placeholder_p1", {"page": 1, "nameQuality": "placeholder"}),
    ("name_alias_p1", {"page": 1, "nameQuality": "alias_only"}),
    ("combo_valid_polygon", {"page": 1, "geomType": "polygon", "nameQuality": "valid"}),
    ("combo_placeholder_line", {"page": 1, "geomType": "line", "nameQuality": "placeholder"}),
    ("keyword_athens", {"page": 1, "keyword": "Athens"}),
    ("keyword_none_geom", {"page": 1, "keyword": "Untitled", "geomType": "none"}),
]


def pct(vals: List[float], p: float) -> float:
    s = sorted(vals)
    k = (len(s) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://127.0.0.1:8088")
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--warmup", type=int, default=3)
    ap.add_argument("--size", type=int, default=20)
    ap.add_argument("--json", default="ops/reports/v1b/bench_admin.json")
    args = ap.parse_args()

    out: Dict[str, Any] = {"api": args.api, "n": args.n, "size": args.size, "cases": {}}
    worst_p95 = 0.0
    worst_case = ""

    for name, params in CASES:
        q = {"size": args.size, **{k: str(v) for k, v in params.items()}}
        url = f"{args.api}/api/v1/places/admin?{urllib.parse.urlencode(q)}"
        ts: List[float] = []
        body: Dict[str, Any] = {}
        for i in range(args.warmup + args.n):
            t0 = time.perf_counter()
            with urllib.request.urlopen(url, timeout=60) as r:
                body = json.load(r)
            ts.append(time.perf_counter() - t0)
        measured = ts[args.warmup:]
        rec = {
            "params": params,
            "total": body.get("total"),
            "items": len(body.get("items") or []),
            "p50_ms": round(pct(measured, 0.50) * 1000, 1),
            "p95_ms": round(pct(measured, 0.95) * 1000, 1),
            "max_ms": round(max(measured) * 1000, 1),
        }
        out["cases"][name] = rec
        if rec["p95_ms"] > worst_p95:
            worst_p95, worst_case = rec["p95_ms"], name
        print(f"{name:24s} total={str(rec['total']):>7s} items={rec['items']:>2d} "
              f"P50={rec['p50_ms']:>6.1f}ms P95={rec['p95_ms']:>6.1f}ms")

    out["worst"] = {"case": worst_case, "p95_ms": worst_p95}
    out["target_ms"] = 300
    out["meets_target"] = worst_p95 <= 300
    dest = CODE / args.json
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n最差 P95 = {worst_p95:.1f}ms ({worst_case})，目标 300ms → "
          f"{'达标' if out['meets_target'] else '未达标'}")
    print(f"写入 {dest}")


if __name__ == "__main__":
    main()
