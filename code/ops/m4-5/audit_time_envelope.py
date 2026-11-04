#!/usr/bin/env python
"""M4-5 · 地点级时间包络逐条审计（只读，不改任何文件）

背景
----
M4-4b 导入后发现 820 条 ``derived_value_mismatch``（629 个地点）：

* 197 条 / 130 个地点属于 ``pleiades_gis_4_1_slice``（M4-2 时代就存在）；
* 623 条 / 499 个地点属于 ``pleiades_gis_4_1``（M4-4b 新增）。

导入器给出的规则是"地点级时间 = 仅 name+location 子行包络（排除 edge/connection）"，
而 :func:`normalize._place_time_bounds` 收到的 ``children`` 里**包含 connection 记录**
（``normalize.py`` 第 711 行把 ``name`` / ``location`` / ``connection`` 一起塞进
``extra_children``）。本脚本要做的不是"相信这个结论"，而是把三个候选口径各算一遍，
看哪一种能逐条解释暂存里已有的值。

三个口径
--------
``E_all``      name + location，**所有**带数字年份的子行（= 导入器现行规则）
``E_bound``    name + location，只取 ``time_bound_type ∈ {tpq_taq, bounded}``
               （= 归一化在**排除 connection 之后**的口径）
``E_bound_conn``  ``E_bound`` 再加上 connection（= 归一化**当前实际**口径）

判读方式
--------
对暂存里每个 ``(place, field)``：

1. 若 ``staged == E_all``，一致，不计入差异；
2. 否则这是一条差异。再看 ``staged`` 等于哪个候选口径、以及三个口径谁高谁低，
   把差异归到下面几类之一：

   ``connection_extreme``   connection 行提供了更早的 TPQ 或更晚的 TAQ，
                            使 ``E_bound_conn`` 比 ``E_all`` 更宽，暂存正是这个更宽的值
   ``bound_type_filter``    name/location 里有带年份但 ``time_bound_type=unknown`` 的行，
                            归一化跳过、导入器纳入，暂存 = ``E_bound(+conn)``
   ``both``                 两者同时发生
   ``unexplained``          以上都解释不了 —— 这一类的数量必须是 0，否则说明还有别的成因

输出
----
``--json`` 写一份完整明细（每条差异 + 驱动记录），``--csv`` 写同一份明细的表格版；
标准输出只打印汇总，便于日志留档。
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

CODE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(CODE_ROOT / "p0" / "wb-002-normalize"))

from quality_checks import astro_year  # noqa: E402
from time_semantics import parse_signed_year  # noqa: E402

#: 归一化在 Pleiades 分支里认可的"有确定区间"的 bound type。
BOUNDED_TYPES = ("tpq_taq", "bounded")


def read_rows(path: Path) -> List[Dict[str, str]]:
    """Read a staging CSV as a list of dicts (BOM-tolerant)."""
    with io.open(path, encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def to_int(value: Any) -> Optional[int]:
    """Parse an already-rendered astro year."""
    text = ("" if value is None else str(value)).strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def widen(current: List[Optional[int]], low: Optional[int], high: Optional[int]) -> None:
    """Extend ``current = [min, max]`` in place."""
    if low is not None:
        current[0] = low if current[0] is None else min(current[0], low)
    if high is not None:
        current[1] = high if current[1] is None else max(current[1], high)


def place_key(value: str) -> str:
    """Bare id from either a bare id or an absolute URI."""
    text = (value or "").strip()
    return text.rstrip("/").rsplit("/", 1)[-1] if "/" in text else text


def main() -> int:
    parser = argparse.ArgumentParser(description="M4-5 时间包络逐条审计")
    parser.add_argument("--staging", default="data/staging_m4_3", help="暂存目录")
    parser.add_argument("--gis", default="data/raw/pleiades_gis_4_1/gis", help="4.1 GIS 目录")
    parser.add_argument("--json", help="明细 JSON 输出路径")
    parser.add_argument("--csv", help="明细 CSV 输出路径")
    args = parser.parse_args()

    staging = (CODE_ROOT / args.staging).resolve()
    gis = (CODE_ROOT / args.gis).resolve()

    places = read_rows(staging / "historical_places.csv")
    names = read_rows(staging / "historical_place_names.csv")
    locations = read_rows(staging / "historical_place_locations.csv")

    # ------------------------------------------------------------------ 索引
    # 每条子行三件事要记：是否有数字年份、bound_type、source_record_id（用于溯源）
    name_by_place: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    for row in names:
        name_by_place[row["place_id"]].append(row)
    loc_by_place: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    for row in locations:
        loc_by_place[row["place_id"]].append(row)

    # 暂存里的 place_id -> (dataset, external_id)，用来把 4.1 的连接映射回来
    place_meta = {
        row["place_id"]: (row["source_dataset"], row["primary_external_id"])
        for row in places
    }
    by_ext: Dict[Tuple[str, str], str] = {v: k for k, v in place_meta.items()}

    # 连接记录一律从**暂存的 source_records.csv** 取，而不是读原始 connections.csv。
    # 两个理由：
    #   1. 切片快照（M4-2）与 4.1 全量（M4-4b）各自只含自己那一份连接子集，
    #      读同一个原始 CSV 会让切片地点被"多算"它当年没见过的连接；
    #   2. 暂存才是归一化的输入，也是这条链路的唯一事实源，可复算。
    # 每条连接记录的 raw_payload_json 保留了原行（含 place_id / 年份），
    # 因此不需要再回头找 candidate_matches 的 evidence 反推。
    conn_by_ext: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    conn_ds: Dict[str, str] = {}
    n_conn_rows = 0
    for row in read_rows(staging / "source_records.csv"):
        if row["external_id_type"] != "pleiades_connection_id":
            continue
        n_conn_rows += 1
        payload = json.loads(row["raw_payload_json"] or "{}")
        pid = place_key(payload.get("place_id", ""))
        tp = parse_signed_year(payload.get("year_after_which", ""))
        tq = parse_signed_year(payload.get("year_before_which", ""))
        # 同名地点在两个数据集里各有一份，按 (dataset, place) 分组避免串味
        conn_ds[row["dataset_id"]] = row["dataset_id"]
        conn_by_ext[pid].append(
            {
                "dataset_id": row["dataset_id"],
                "source_record_id": row["source_record_id"],
                "connection_id": row["external_id"],
                "raw_file": row["raw_file"],
                "raw_record_index": int(row["raw_record_index"] or 0),
                "connects_to": place_key(payload.get("connects_to", "")),
                "connection_type": (payload.get("connection_type") or "").strip(),
                "from_astro": astro_year(tp) if tp is not None else None,
                "to_astro": astro_year(tq) if tq is not None else None,
            }
        )

    # ------------------------------------------------------- 三个口径逐点重算
    e_all: Dict[str, List[Optional[int]]] = defaultdict(lambda: [None, None])
    e_bound: Dict[str, List[Optional[int]]] = defaultdict(lambda: [None, None])
    skipped_by_filter: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    per_field_rows: Dict[str, List[Dict[str, str]]] = defaultdict(list)

    for bucket, rows in (("name", names), ("location", locations)):
        for row in rows:
            pid = row["place_id"]
            frm = to_int(row["valid_from_year_astro"])
            to = to_int(row["valid_to_year_astro"])
            per_field_rows[pid].append(row)
            widen(e_all[pid], frm, to)
            if row["time_bound_type"] in BOUNDED_TYPES:
                widen(e_bound[pid], frm, to)
            elif frm is not None or to is not None:
                skipped_by_filter[pid].append(
                    {
                        "kind": bucket,
                        "row_id": row.get("name_id") or row.get("location_id"),
                        "time_bound_type": row["time_bound_type"],
                        "from_astro": frm,
                        "to_astro": to,
                        "source_record_id": row.get("source_record_id", ""),
                    }
                )

    def conns_of(dataset: str, external_id: str) -> List[Dict[str, Any]]:
        """Connections that belong to one (dataset, place) pair."""
        return [c for c in conn_by_ext.get(external_id, []) if c["dataset_id"] == dataset]

    e_bound_conn: Dict[str, List[Optional[int]]] = {}
    for pid in place_meta:
        base = list(e_bound.get(pid, [None, None]))
        ds, ext = place_meta[pid]
        for rec in conns_of(ds, ext):
            widen(base, rec["from_astro"], rec["to_astro"])
        e_bound_conn[pid] = base

    # ----------------------------------------------------------- 逐条比对归类
    details: List[Dict[str, Any]] = []
    by_dataset = Counter()
    places_by_dataset: Dict[str, set] = defaultdict(set)
    kind_counter = Counter()
    field_counter = Counter()

    for place in places:
        pid = place["place_id"]
        ds = place["source_dataset"]
        ext = place["primary_external_id"]
        staged = [to_int(place["valid_from_year_astro"]), to_int(place["valid_to_year_astro"])]
        rebuilt = e_all.get(pid, [None, None])
        if staged == rebuilt:
            continue

        for slot, field in ((0, "valid_from_year_astro"), (1, "valid_to_year_astro")):
            if staged[slot] == rebuilt[slot]:
                continue
            bound = e_bound.get(pid, [None, None])[slot]
            with_conn = e_bound_conn.get(pid, [None, None])[slot]
            filtered = skipped_by_filter.get(pid, [])
            conn_effect = bound != with_conn
            filter_effect = bound != rebuilt[slot]

            if conn_effect and filter_effect:
                kind = "both"
            elif conn_effect:
                kind = "connection_extreme"
            elif filter_effect:
                kind = "bound_type_filter"
            else:
                kind = "unexplained"

            # 找出提供极值的那条 connection（只对该字段方向相关的那一端）
            driver: Dict[str, Any] = {}
            if conn_effect:
                conns = conns_of(ds, ext)
                key = "from_astro" if slot == 0 else "to_astro"
                picker = min if slot == 0 else max
                candidates = [c for c in conns if c.get(key) is not None]
                if candidates:
                    best = picker(candidates, key=lambda c: c[key])
                    driver = {
                        "kind": "connection",
                        "connection_id": best["connection_id"],
                        "connects_to": best["connects_to"],
                        "connection_type": best["connection_type"],
                        "raw_file": best["raw_file"],
                        "raw_record_index": best["raw_record_index"],
                        "value": best[key],
                    }
            if filter_effect and not driver:
                picker = min if slot == 0 else max
                key = "from_astro" if slot == 0 else "to_astro"
                cand = [f for f in filtered if f.get(key) is not None]
                if cand:
                    best = picker(cand, key=lambda f: f[key])
                    driver = {
                        "kind": "child_row_outside_bound_types",
                        "row_id": best["row_id"],
                        "row_kind": best["kind"],
                        "time_bound_type": best["time_bound_type"],
                        "source_record_id": best["source_record_id"],
                        "value": best[key],
                    }

            details.append(
                {
                    "place_id": pid,
                    "source_dataset": ds,
                    "primary_external_id": ext,
                    "canonical_name": place["canonical_name"],
                    "field": field,
                    "staged": staged[slot],
                    "recomputed_importer": rebuilt[slot],
                    "recomputed_name_loc_bound_only": bound,
                    "recomputed_name_loc_conn": with_conn,
                    "place_time_bound_type": place["time_bound_type"],
                    "place_time_derivation": place["time_derivation"],
                    "classification": kind,
                    "driver": driver,
                    "n_names": len(name_by_place.get(pid, [])),
                    "n_locations": len(loc_by_place.get(pid, [])),
                    "n_connections": len(conns_of(ds, ext)),
                }
            )
            by_dataset[ds] += 1
            places_by_dataset[ds].add(pid)
            kind_counter[(ds, kind)] += 1
            field_counter[field] += 1

    # --------------------------------------------------------------- 汇总打印
    total = len(details)
    print("=" * 78)
    print("M4-5 时间包络审计：暂存值 vs 导入器重算值（仅 name+location）")
    print("=" * 78)
    print(f"暂存地点 {len(places):,}；差异 {total:,} 条 / "
          f"{sum(len(v) for v in places_by_dataset.values()):,} 个地点")
    for ds in sorted(by_dataset):
        print(f"  {ds:26s} {by_dataset[ds]:>5,} 条 / {len(places_by_dataset[ds]):>4,} 个地点")
    print("\n分类：")
    for (ds, kind), n in sorted(kind_counter.items()):
        print(f"  {ds:26s} {kind:22s} {n:>5,}")
    print("\n受影响字段：", dict(sorted(field_counter.items())))

    unexplained = [d for d in details if d["classification"] == "unexplained"]
    both = [d for d in details if d["classification"] == "both"]
    filtered_only = [d for d in details if d["classification"] == "bound_type_filter"]

    # 关键判据 1：暂存值是否等于"name+loc+conn"口径（证明成因就是 connection）
    matched_with_conn = sum(
        1
        for d in details
        if d["staged"] == d["recomputed_name_loc_conn"]
    )
    print(f"\n暂存值 == name+loc+conn 口径的条数：{matched_with_conn:,} / {total:,}")
    print(f"其中 bound_type 过滤也参与的（both）：{len(both)}")
    print(f"纯 bound_type 过滤（与该问题无关的第二类成因）：{len(filtered_only)}")
    print(f"无法解释：{len(unexplained)}")

    if both or filtered_only or unexplained:
        print("\n非 connection 成因的样本（最多 5 条）：")
        for d in (both + filtered_only + unexplained)[:5]:
            print(f"  place={d['place_id']} {d['field']} staged={d['staged']} "
                  f"importer={d['recomputed_importer']} bound={d['recomputed_name_loc_bound_only']} "
                  f"conn={d['recomputed_name_loc_conn']} driver={d['driver']}")

    summary = {
        "staging_dir": str(staging),
        "places_total": len(places),
        "mismatch_rows": total,
        "mismatch_places": sum(len(v) for v in places_by_dataset.values()),
        "by_dataset": dict(sorted(by_dataset.items())),
        "places_by_dataset": {k: len(v) for k, v in sorted(places_by_dataset.items())},
        "by_classification": {
            f"{ds}:{kind}": n for (ds, kind), n in sorted(kind_counter.items())
        },
        "by_field": dict(sorted(field_counter.items())),
        "staged_equals_name_loc_conn": matched_with_conn,
        "connection_only": sum(1 for d in details if d["classification"] == "connection_extreme"),
        "both_connection_and_filter": len(both),
        "bound_type_filter_only": len(filtered_only),
        "unexplained": len(unexplained),
    }

    if args.json:
        out = Path(args.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        payload = {"summary": summary, "details": details}
        with io.open(out, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        print(f"\n明细 JSON：{out}（{out.stat().st_size:,} B）")

    if args.csv:
        out = Path(args.csv)
        out.parent.mkdir(parents=True, exist_ok=True)
        cols = [
            "place_id", "source_dataset", "primary_external_id", "canonical_name",
            "field", "staged", "recomputed_importer", "recomputed_name_loc_bound_only",
            "recomputed_name_loc_conn", "classification", "place_time_bound_type",
            "place_time_derivation", "n_names", "n_locations", "n_connections",
            "driver_kind", "driver_id", "driver_value", "driver_detail",
        ]
        with io.open(out, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=cols)
            writer.writeheader()
            for d in details:
                drv = d["driver"] or {}
                writer.writerow(
                    {
                        **{k: d[k] for k in cols if k in d},
                        "driver_kind": drv.get("kind", ""),
                        "driver_id": drv.get("connection_id") or drv.get("row_id", ""),
                        "driver_value": drv.get("value", ""),
                        "driver_detail": json.dumps(
                            {k: v for k, v in drv.items() if k not in ("kind", "value")},
                            ensure_ascii=False,
                        ),
                    }
                )
        print(f"明细 CSV：{out}（{out.stat().st_size:,} B）")

    return 0 if not unexplained else 2


if __name__ == "__main__":
    raise SystemExit(main())
