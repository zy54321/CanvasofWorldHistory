"""M4-3 R1.1 · 逐条核实 connections 的分类与交集（只读）。

R1 里自环与悬空的口径出现过矛盾：一次报"孤儿 29、自环 2"，另一次报"悬空 28、自环 1"。
原因是两者的判定顺序不同（先判悬空再判自环，还是反过来），以及"侧数"与"记录数"混用。

本脚本不做算术倒推，而是把每条记录都归到一个**互斥**的类别里，并额外输出各集合的交集，
让"29 / 28 / 2 / 1"这些数字各自有明确归属。

类别（互斥）：
  A. both_ends_ok     两端都在 places.csv
     A1. self_loop     其中 a == b（可解析自环）
     A2. pair          正常对（进入候选去重）
  B. dangling         至少一端不在 places.csv（按"为什么悬空"再分）
     B1. blank_row     整行字段全空（a == b == ''，不是真自环）
     B2. errata_target connects_to 指向 /errata/<id>，本来就不是地点
     B3. place_missing 指向的 place id 不在 places.csv


输出：JSON（含全部记录 ID）+ 控制台摘要。
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

CODE = Path(__file__).resolve().parents[2]
GIS = CODE / "data" / "raw" / "pleiades_gis_4_1" / "gis"
URI_RE = re.compile(r"/places/([^/?#]+)")


def rows(path: Path):
    with io.open(path, encoding="utf-8-sig", newline="") as f:
        yield from csv.DictReader(f)


def key(v: str) -> str:
    v = (v or "").strip()
    m = URI_RE.search(v)
    return m.group(1) if m else v


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=str(CODE / "ops" / "m4-3" / "connections_audit.json"))
    args = ap.parse_args()

    place_ids = {(r["id"] or "").strip() for r in rows(GIS / "places.csv")}

    total = 0
    both_ok_self = []       # A1 可解析自环
    both_ok_pairs = []      # A2
    blank = []              # B1 整行空
    dang_one = []           # B2 单端悬空（含 errata）
    dang_both = []           # B3 两端悬空
    dangling_sides = Counter()

    for r in rows(GIS / "connections.csv"):
        total += 1
        cid = (r.get("id") or "").strip()
        uri = (r.get("uri") or "").strip()
        a = key(r.get("place_id"))
        b = key(r.get("connects_to"))
        ctype = (r.get("connection_type") or "").strip()
        rec = {"connection_id": cid, "uri": uri, "place_id": a, "connects_to": b,
               "connection_type": ctype}
        ok_a, ok_b = a in place_ids, b in place_ids
        if not ok_a:
            dangling_sides["place_id"] += 1
        if not ok_b:
            dangling_sides["connects_to"] += 1
        if ok_a and ok_b:
            (both_ok_self if a == b else both_ok_pairs).append(rec)
        else:
            raw_target = (r.get("connects_to") or "").strip()
            if not a and not b:
                blank.append(dict(rec, sides="both"))
            elif "errata" in raw_target:
                dang_one.append(dict(rec, sides="a" if not ok_a else "b",
                                     target_kind="errata"))
            elif not ok_a and not ok_b:
                dang_both.append(dict(rec, sides="both", target_kind="place_missing"))
            else:
                dang_one.append(dict(rec, sides="a" if not ok_a else "b",
                                     target_kind="place_missing"))

    # 有序对去重（与 uq_candidate_match_c09 一致）
    pair_count = Counter((r["place_id"], r["connects_to"]) for r in both_ok_pairs)
    dup_pairs = {f"{a}->{b}": c for (a, b), c in pair_count.items() if c > 1}
    # 找出重复对里被合并掉的那些记录（保留首条）
    kept, dropped = [], []
    seen = set()
    for r in both_ok_pairs:
        k = (r["place_id"], r["connects_to"])
        if k in seen:
            dropped.append(r)
        else:
            seen.add(k)
            kept.append(r)

    # 三元组重复（同 a,b,type）
    triple_count = Counter((r["place_id"], r["connects_to"], r["connection_type"])
                           for r in both_ok_pairs)
    dup_triples = {f"{a}->{b}|{t}": c for (a, b, t), c in triple_count.items() if c > 1}

    out = {
        "source_rows": total,
        "place_ids": len(place_ids),
        "classes": {
            "A_both_ends_ok": len(both_ok_self) + len(both_ok_pairs),
            "A1_resolvable_self_loop": len(both_ok_self),
            "A2_normal_pairs": len(both_ok_pairs),
            "B_dangling": len(blank) + len(dang_one) + len(dang_both),
            "B1_blank_row": len(blank),
            "B2_one_side_dangling": len(dang_one),
            "B2a_of_which_errata_target": sum(1 for x in dang_one if x.get("target_kind") == "errata"),
            "B3_both_sides_dangling": len(dang_both),
        },
        "self_loops_real": len(both_ok_self),
        "self_loops_counted_by_equality": len(both_ok_self) + len(blank),
        "dangling_records_total": len(blank) + len(dang_one) + len(dang_both),
        "dangling_endpoint_sides": dict(dangling_sides),
        "dangling_sides_sum": sum(dangling_sides.values()),
        "candidate": {
            "pairs_before_dedup": len(both_ok_pairs),
            "distinct_ordered_pairs": len(pair_count),
            "dropped_by_pair_dedup": len(dropped),
            "duplicate_pairs": dup_pairs,
            "duplicate_triples": dup_triples,
            "final_rows": len(pair_count),
            "unique_key": "uq_candidate_match_c09 (relation_type, place_id_a, place_id_b)",
            "excluded_by_check": "ck_candidate_match_distinct_places 拒绝 a = b",
        },
        "ids": {
            "A1_resolvable_self_loop": both_ok_self,
            "B1_blank_row": blank,
            "B2_one_side_dangling": dang_one,
            "B3_both_sides_dangling": dang_both,
            "dropped_by_pair_dedup": dropped,
        },
    }
    Path(args.json).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    print("== 总行数 ==", total)
    print("== 互斥分类 ==")
    for k, v in out["classes"].items():
        print(f"  {k:32s} {v:,}")
    print(f"  真实自环（可解析，A1）         {out['self_loops_real']}")
    print(f"  字面 a==b（含空行）            {out['self_loops_counted_by_equality']}")
    print(f"  悬空记录（B1+B2+B3）           {out['dangling_records_total']}")
    print(f"  悬空端点侧数                   {out['dangling_sides_sum']}  {out['dangling_endpoint_sides']}")
    print("== 候选 ==")
    for k, v in out["candidate"].items():
        if k in ("duplicate_pairs", "duplicate_triples"):
            print(f"  {k:32s} {len(v)} 组")
        elif k not in ("unique_key", "excluded_by_check"):
            print(f"  {k:32s} {v:,}")
    print("\n== 记录 ID 清单 ==")
    for k, v in out["ids"].items():
        print(f"  {k}（{len(v)}）:")
        for r in v[:40]:
            print(f"    {r['connection_id']:>14s}  {r['place_id']:>12s} -> {r['connects_to']:<12s}"
                  f"  {r['connection_type']}")
    print(f"\nJSON -> {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
