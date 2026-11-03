#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
parent_external_id 派生覆盖率精确交叉表（Task B 支撑，来源层级①）

V0.2.2 §2.5.0 C29 把 parent_external_id 定为五段自然键的**必需段**，
禁止 NULL / 空串。本脚本按 (dataset_id, external_id_type) 交叉统计：
  · 该组总行数
  · raw_payload_json 中能取到候选父级字段（place_id / LocID）的行数
  · 取不到的行数 ⇒ V2.1.1 必须为这部分显式补一条规则（哨兵或其它派生式）

严格只读。
"""

from __future__ import annotations

import ast
import csv
import os
import sys
from collections import Counter, defaultdict

SRC_DIR = (
    r"E:\01_Work\01_PersonalProjects\014-CanvasofWorldHistory"
    r"\设计资料\P0收敛\WB-002\normalized"
)

csv.field_size_limit(10 ** 9)

# V2.1 映射行 46 声明的派生来源；V0.2.2 C29 ② 追加 CHGIS place → 哨兵 '-'
CANDIDATE_KEYS = ("place_id", "LocID")

# V0.2.2 §2.7.2 定式：external_id_type → record_scope（用于交叉核对）
SCOPE_BY_IDT = {
    "chgis_sys_id": "place",
    "pleiades_place_id": "place",
    "whg_place_id": "place",
    "whg_source_id": "place",
    "pleiades_name_id": "name",
    "mcgd_nameid": "name",
    "whg_place_name_index": "name",
    "pleiades_location_id": "location",
    "whg_geometry": "location",
    "whg_geom_index": "location",
    "pleiades_connection_id": "edge",
}


def main():
    total = Counter()
    hit = Counter()
    hitkey = defaultdict(Counter)
    parse_fail = Counter()

    with open(os.path.join(SRC_DIR, "source_records.csv"), "r",
              encoding="utf-8-sig", newline="") as fh:
        for r in csv.DictReader(fh):
            grp = (r["dataset_id"], r["external_id_type"])
            total[grp] += 1
            try:
                payload = ast.literal_eval(r["raw_payload_json"])
            except Exception:
                parse_fail[grp] += 1
                continue
            if not isinstance(payload, dict):
                parse_fail[grp] += 1
                continue
            for k in CANDIDATE_KEYS:
                if k in payload and str(payload[k]).strip() != "":
                    hit[grp] += 1
                    hitkey[grp][k] += 1
                    break

    print("=" * 100)
    print("parent_external_id 派生覆盖率交叉表（① 原始 CSV 逐行实算）")
    print("=" * 100)
    print("%-34s %-24s %-9s %8s %8s %8s  %s" % (
        "dataset_id", "external_id_type", "scope", "总行", "可取到", "取不到", "命中键"))
    print("-" * 100)

    grand_t = grand_h = 0
    rows = []
    for grp in sorted(total, key=lambda g: (g[0], -total[g])):
        ds, idt = grp
        t, h = total[grp], hit[grp]
        miss = t - h - parse_fail[grp]
        grand_t += t
        grand_h += h
        rows.append((ds, idt, SCOPE_BY_IDT.get(idt, "??"), t, h, miss,
                     ",".join(sorted(hitkey[grp])) or "—"))
        print("%-34s %-24s %-9s %8d %8d %8d  %s" % (
            ds, idt, SCOPE_BY_IDT.get(idt, "??"), t, h, miss,
            ",".join(sorted(hitkey[grp])) or "—"))
    print("-" * 100)
    print("%-34s %-24s %-9s %8d %8d %8d" % ("合计", "", "", grand_t, grand_h,
                                            grand_t - grand_h))

    # 按 scope 汇总
    print("\n按 record_scope 汇总：")
    st, sh = Counter(), Counter()
    for ds, idt, sc, t, h, m, _k in rows:
        st[sc] += t
        sh[sc] += h
    for sc in ("place", "name", "location", "edge", "??"):
        if st[sc]:
            print("  %-10s 总 %6d  可取到 %6d  取不到 %6d"
                  % (sc, st[sc], sh[sc], st[sc] - sh[sc]))

    print("\n**必须显式补规则的组（取不到 = 100%%）**：")
    for ds, idt, sc, t, h, m, _k in rows:
        if h == 0:
            print("  %-34s %-24s scope=%-9s 行数 %d  ⇒ V0.2.2 C29② 只写了 "
                  "『CHGIS place → 哨兵 -』，本组未覆盖" % (ds, idt, sc, t))
    return 0


if __name__ == "__main__":
    sys.exit(main())
