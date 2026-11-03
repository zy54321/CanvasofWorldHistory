#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
V2.1.1 映射差异预判的实测支撑脚本 (Task B 支撑)

目的：对 V0.2.2 定式中「必须失效/改写」的字段，逐条核实它在暂存 CSV 里的真实来源
（存在 → 给来源列；不存在 → 说明派生规则并标 derived）。

所有结论均为「①原始 CSV 逐行实算」层级。严格只读。
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

# V2.1 映射行 44 声明的 4 值域
VALID_SCOPE = {"place", "name", "location", "edge"}


def read_rows(name):
    """只读逐行生成 dict。"""
    path = os.path.join(SRC_DIR, name + ".csv")
    with open(path, "r", encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            yield row


def report(title, lines):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)
    for ln in lines:
        print(ln)


def main():
    # ---------------------------------------------------------------
    # 1) external_id_type 全域 & 与 record_scope 的对应
    # ---------------------------------------------------------------
    idt_counter = Counter()
    idt_by_dataset = defaultdict(set)
    for r in read_rows("source_records"):
        idt_counter[r["external_id_type"]] += 1
        idt_by_dataset[r["external_id_type"]].add(r["dataset_id"])
    report("① external_id_type 全域（V2.1 映射行 35 称『16 种取值』）", [
        "实测种类数：%d（V2.1 映射行 35 写 16 种）" % len(idt_counter),
    ])
    for k, v in idt_counter.most_common():
        ds = sorted(idt_by_dataset[k])
        print("  %-26s %7d  dataset=%s" % (k, v, ",".join(ds)))

    # ---------------------------------------------------------------
    # 2) raw_payload_json 顶层键（验证 parent_external_id 的派生可行性）
    # ---------------------------------------------------------------
    keys_by_dataset = defaultdict(Counter)
    parent_probe = defaultdict(Counter)
    n_sr = 0
    for r in read_rows("source_records"):
        n_sr += 1
        ds = r["dataset_id"]
        try:
            payload = ast.literal_eval(r["raw_payload_json"])
        except Exception:
            parent_probe[ds]["<解析失败>"] += 1
            continue
        if isinstance(payload, dict):
            for k in payload.keys():
                keys_by_dataset[ds][k] += 1
        # parent_external_id 候选源：place_id / LocID
        for cand in ("place_id", "LocID", "LOCID", "loc_id"):
            if isinstance(payload, dict) and cand in payload:
                parent_probe[ds][cand] += 1

    report("② parent_external_id 的暂存来源探测（V0.2.2 C29 定为五段键必需段）", [
        "source_records 实测列：source_record_id / source_id / source_dataset / "
        "dataset_id / external_id / external_id_type / raw_file / "
        "raw_record_index / raw_payload_json / license_status / "
        "redistributable / attribution_text / ingested_at / pipeline_version",
        "⇒ 暂存 CSV **无** parent_external_id 列，只能由 raw_payload_json 派生。",
    ])
    for ds in sorted(parent_probe):
        print("  %-34s %s" % (ds, dict(parent_probe[ds])))

    print("\n  各 dataset 的 raw_payload_json 顶层键（前 12 个）：")
    for ds in sorted(keys_by_dataset):
        kk = [k for k, _ in keys_by_dataset[ds].most_common(12)]
        print("    %-34s %s" % (ds, ", ".join(kk)))

    # ---------------------------------------------------------------
    # 3) record_scope 四值域的实测可达性（按 external_id_type 归类）
    # ---------------------------------------------------------------
    scope_guess = {}
    for idt in idt_counter:
        low = idt.lower()
        if "connection" in low:
            scope_guess[idt] = "edge"
        elif "place" in low:
            scope_guess[idt] = "place"
        elif "name" in low:
            scope_guess[idt] = "name"
        elif "location" in low or "coord" in low:
            scope_guess[idt] = "location"
        else:
            scope_guess[idt] = "??未归类"
    report("③ external_id_type → record_scope 归类（QA 试归类，非权威）",
           ["  %-26s %10s  → %s" % (k, idt_counter[k], scope_guess[k])
            for k in idt_counter])
    out_of_domain = [k for k, v in scope_guess.items() if v not in VALID_SCOPE]
    print("\n  落在 4 值域之外（V0.2.2 A12 要求出现第五种 ⇒ 整批 failed）：%s"
          % (out_of_domain if out_of_domain else "无"))

    # ---------------------------------------------------------------
    # 4) 七张表是否含 V0.2.2 新增列
    # ---------------------------------------------------------------
    expect_new = {
        "source_records": ["parent_external_id", "duplicate_ordinal",
                           "inactive_at", "inactive_in_batch_id"],
        "historical_places": ["dataset_id", "grain_key"],
        "historical_place_names": ["rejected_by"],
        "historical_place_locations": ["rejected_by"],
        "data_quality_issues": ["first_batch_id", "last_batch_id",
                                "occurrence_count", "issue_fingerprint"],
    }
    report("④ V0.2.2 新增列在暂存 CSV 中的存在性核查", [])
    for tbl, cols in expect_new.items():
        with open(os.path.join(SRC_DIR, tbl + ".csv"), "r",
                  encoding="utf-8-sig", newline="") as fh:
            header = next(csv.reader(fh))
        print("\n  [%s] 暂存 %d 列：%s" % (tbl, len(header), ",".join(header)))
        for c in cols:
            print("      %-22s %s" % (c, "存在" if c in header else "**不存在（derived）**"))

    # ---------------------------------------------------------------
    # 5) data_quality_issues 的指纹构成要素（issue_fingerprint 只能派生）
    # ---------------------------------------------------------------
    dqi_keys = Counter()
    n_dqi = 0
    for r in read_rows("data_quality_issues"):
        n_dqi += 1
        dqi_keys[(r["issue_type"], r["severity"], r["action_taken"])] += 1
    report("⑤ data_quality_issues 构成（%d 行）" % n_dqi, [
        "  暂存 11 列，无 issue_fingerprint / first_batch_id / last_batch_id / occurrence_count",
        "  issue_type 种类：%d" % len(set(k[0] for k in dqi_keys)),
        "  action_taken 种类：%d" % len(set(k[2] for k in dqi_keys)),
    ])

    # ---------------------------------------------------------------
    # 6) data_datasets 的许可相关列（待删除的 9 列目标）
    # ---------------------------------------------------------------
    with open(os.path.join(SRC_DIR, "data_datasets.csv"), "r",
              encoding="utf-8-sig", newline="") as fh:
        dd = list(csv.DictReader(fh))
    report("⑥ data_datasets 暂存列（V2.1 目标表 9 列许可列的源头）", [
        "  暂存 %d 列：%s" % (len(dd[0]), ",".join(dd[0].keys())),
        "  行数：%d" % len(dd),
    ])
    for k in dd[0].keys():
        vals = [r[k] for r in dd]
        nonempty = sum(1 for v in vals if v != "")
        print("      %-22s 非空 %d/%d 唯一 %d" % (k, nonempty, len(dd),
                                                  len(set(vals))))

    print("\n完成。source_records 行数 = %d" % n_sr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
