#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""M4-4a 质量台账实测：每种 issue_type 的实际行数、来源、生成规则、可追溯 ID。

只读 ``code/data/staging_m4_3/data_quality_issues.csv``，不连数据库。

输出 ``code/ops/m4-4a/ledger_audit.json``，结构分三段，对应施工指令 §五 要求区分的
三类台账：

  A. ``normalization``  归一化阶段（本阶段）真实生成的行 —— 这些数字是**已实测**的；
  B. ``importer_synthesized``  导入器运行期合成的行（duplicate_external_id /
     derived_value_mismatch / manual_edit_conflict）—— 本阶段**没有执行导入**，
     因此这里只有规则与在暂存上可静态预判的部分，绝不能写成"已验证"；
  C. ``not_opened``  明确不开票的事实（Z 序降维、place_without_geometry 等），
     写清为什么不开，避免下次被当成遗漏。

用法：
    cd code
    python ops/m4-4a/ledger_audit.py
"""

from __future__ import annotations

import csv
import io
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List

CODE_ROOT = Path(__file__).resolve().parents[2]
STAGING = CODE_ROOT / "data" / "staging_m4_3"
OUT = CODE_ROOT / "ops" / "m4-4a" / "ledger_audit.json"

#: 生成规则出处（文件:行号）—— 行号会随代码演进漂移，因此同时给出函数名与判据文字。
RULES: Dict[str, Dict[str, str]] = {
    "missing_coordinate": {
        "stage": "归一化",
        "where": "pleiades_extract.py: place 行 representative_latitude/longitude 缺失 ⇒ quality_flags",
        "rule": "places.csv 该行没有代表坐标 → place 记录带 missing_coordinate → normalize 逐 place 开票（1 place 1 行）",
    },
    "geometry_invalid_repaired": {
        "stage": "归一化",
        "where": "pleiades_extract._location_geometry",
        "rule": "GEOS 判定 ST_IsValid=false → shapely.make_valid + 只取面片 → 修好才开票；修不出面片则整行不入库",
    },
    "connection_endpoint_missing": {
        "stage": "归一化",
        "where": "pleiades_extract.extract_pleiades_full（connections 段）",
        "rule": "connects_to 归一为裸 id 后，任一端不在 places.csv（含 /errata/、整行空）→ 开票，不生成候选关系",
    },
    "accuracy_unknown_sentinel": {
        "stage": "归一化",
        "where": "pleiades_extract.extract_pleiades_full（A2 代表点段）",
        "rule": "places_accuracy.min_accuracy_meters = -1（未知哨兵）→ uncertainty_m 写 NULL 并开票；只对 3,317 条合成行判定",
    },
    "parent_place_not_in_sample": {
        "stage": "归一化",
        "where": "normalize.py 孤儿子行段",
        "rule": "子行的 parent_external_id 不在抽取范围内 → 保留源记录并开票；全量包无孤儿，故本批 0 条新增",
    },
    "unknown_time_bound_type": {
        "stage": "归一化（仅 CHGIS 分支）",
        "where": "normalize.py 只在 chgis_records 循环内开票",
        "rule": "BEG_RULE/END_RULE 不在 xtra_date_rules 且 time_bound_type=unknown；Pleiades 无此两列 ⇒ 恒 0",
    },
    "duplicate_external_id": {
        "stage": "导入器运行期",
        "where": "import_staging.write_ledger（+duplicate_sysid 排除）",
        "rule": "同一 (dataset, scope, parent, external_id) 出现多行且不是 duplicate_sysid 组 ⇒ 1 组 1 行；取决于运行期分组",
    },
    "derived_value_mismatch": {
        "stage": "导入器运行期",
        "where": "import_staging.write_ledger（地点级时间包络重算）",
        "rule": "地点级 valid_from/valid_to 与仅 name+location 子行包络不一致 ⇒ 1 处 1 行",
    },
    "manual_edit_conflict": {
        "stage": "导入器运行期（依赖库内人工保护位）",
        "where": "import_staging.write_places → manual_blocks",
        "rule": "目标地点 created_by=manual / locked / manual_edited_fields 非空且 canonical_name 不同 ⇒ 1 处 1 行",
    },
}

#: 明确不开票的事实，以及为什么。
NOT_OPENED: List[Dict[str, str]] = [
    {
        "fact": "place_without_geometry（7,200 个地点无任何坐标线索）",
        "why": "OWNER 决策：每个这样的地点已有一条 missing_coordinate，再写 7,200 行是同一事实重复登记；"
               "改为验收查询 historical_place ⋈ historical_place_location NOT EXISTS",
    },
    {
        "fact": "z_ordinate_discarded（8 POINT Z / 11 LINESTRING Z / 91 POLYGON Z）",
        "why": "表列是 geometry(Geometry,4326)，降维是表示层处理，不构成源数据缺陷；"
               "原始 WKT 带 Z 的事实保留在该行 raw_payload，quality_flag 也留了痕迹",
    },
    {
        "fact": "place_type 未映射（29,677 个地点 place_type=unknown，其中 NEW 26,383）",
        "why": "Pleiades 192 键类型词表无法映射到 5 值域；强行映射等于编造。多值关系写进 place_type_basis_note 汇总文本",
    },
    {
        "fact": "name_lang 非法 BCP-47（42 行：asyr/osar/cana/arbd/etruscan-in-latin-characters 等）",
        "why": "导入器 sanitize_lang 统一写 und，原值留在 raw_payload；这是既有的降级路径，不是新缺陷",
    },
    {
        "fact": "attested_form 未单独成名称行（10,297 条）",
        "why": "OWNER 决策：不补名称行，原文只在 raw_payload",
    },
]


def read_rows(path: Path):
    with io.open(path, encoding="utf-8-sig", newline="") as handle:
        yield from csv.DictReader(handle)


def main() -> int:
    issues = list(read_rows(STAGING / "data_quality_issues.csv"))
    sources: Dict[str, Dict[str, str]] = {}
    for row in read_rows(STAGING / "source_records.csv"):
        sources[row["source_record_id"]] = {
            "dataset_id": row["dataset_id"],
            "external_id": row["external_id"],
            "external_id_type": row["external_id_type"],
            "raw_file": row["raw_file"],
            "raw_record_index": row["raw_record_index"],
        }

    by_type: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    for row in issues:
        by_type[row["issue_type"]].append(row)

    # 既有暂存（M0–M3 已验收）的分布，用来区分"本轮新增"与"历史存量"
    legacy = Counter()
    legacy_path = CODE_ROOT / "data" / "staging" / "data_quality_issues.csv"
    if legacy_path.is_file():
        for row in read_rows(legacy_path):
            legacy[row["issue_type"]] += 1

    normalization: List[Dict[str, Any]] = []
    for issue_type in sorted(by_type):
        rows = by_type[issue_type]
        datasets = Counter(sources.get(r["source_record_id"], {}).get("dataset_id", "")
                           for r in rows)
        entry: Dict[str, Any] = {
            "issue_type": issue_type,
            "total_rows": len(rows),
            "legacy_rows": legacy.get(issue_type, 0),
            "delta_rows": len(rows) - legacy.get(issue_type, 0),
            "by_dataset": dict(sorted(datasets.items())),
            "severity": dict(sorted(Counter(r["severity"] for r in rows).items())),
            "action_taken": dict(sorted(Counter(r["action_taken"] for r in rows).items())),
            "rule": RULES.get(issue_type, {}),
        }
        # 可追溯：给出前 20 条 (issue_id, source_record_id, dataset, external_id, raw 定位)
        samples = []
        for row in rows[:20]:
            meta = sources.get(row["source_record_id"], {})
            samples.append({
                "issue_id": row["issue_id"],
                "source_record_id": row["source_record_id"],
                "dataset_id": meta.get("dataset_id", ""),
                "external_id": meta.get("external_id", ""),
                "raw_file": meta.get("raw_file", ""),
                "raw_record_index": meta.get("raw_record_index", ""),
                "observed_value": (row["observed_value"] or "")[:120],
            })
        entry["samples"] = samples
        if len(rows) <= 100:
            # 行数少的关键类型（修复 4 / 悬空 28）给全量 ID，便于逐条复核
            entry["all_keys"] = [
                {
                    "issue_id": row["issue_id"],
                    "source_record_id": row["source_record_id"],
                    "external_id": sources.get(row["source_record_id"], {}).get("external_id", ""),
                    "raw_file": sources.get(row["source_record_id"], {}).get("raw_file", ""),
                    "raw_record_index": sources.get(row["source_record_id"], {}).get(
                        "raw_record_index", ""),
                }
                for row in rows
            ]
        normalization.append(entry)

    new_types = ["missing_coordinate", "geometry_invalid_repaired",
                 "connection_endpoint_missing", "accuracy_unknown_sentinel"]
    delta_sum = sum(
        (len(by_type[t]) - legacy.get(t, 0)) if t in by_type else -legacy.get(t, 0)
        for t in new_types
    )

    payload = {
        "generated_from": str(STAGING / "data_quality_issues.csv"),
        "staging_rows_total": len(issues),
        "legacy_rows_total": sum(legacy.values()),
        "delta_total": len(issues) - sum(legacy.values()),
        "A_normalization": {
            "note": "本阶段真实生成，数字已由 verify_staging_m4_3.py 的 S10 组逐项核对",
            "predicted_7960_breakdown": {t: (len(by_type[t]) - legacy.get(t, 0))
                                         for t in new_types},
            "predicted_7960_sum": delta_sum,
            "types": normalization,
        },
        "B_importer_synthesized": {
            "note": ("本阶段**未执行导入**，因此这三类没有实测行数；"
                     "下面给出规则、在暂存上可静态预判的口径，以及为什么无法提前冻结"),
            "types": [
                {
                    "issue_type": "duplicate_external_id",
                    "verified": False,
                    "static_estimate": ("暂存里 38 个多行组 / 76 行，其中 2 组已有 duplicate_sysid，"
                                        "余下 36 组各 1 行 ⇒ 静态预判 36 行；"
                                        "实际以导入器运行期分组为准"),
                    "rule": RULES["duplicate_external_id"],
                },
                {
                    "issue_type": "derived_value_mismatch",
                    "verified": False,
                    "static_estimate": "取决于地点级时间包络与暂存值逐地点比对，本阶段不重算",
                    "rule": RULES["derived_value_mismatch"],
                },
                {
                    "issue_type": "manual_edit_conflict",
                    "verified": False,
                    "static_estimate": "取决于目标库里哪些地点带人工保护位；本阶段不查库",
                    "rule": RULES["manual_edit_conflict"],
                },
            ],
        },
        "C_not_opened": NOT_OPENED,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"台账实测 → {OUT}")
    print(f"暂存 {len(issues):,} 行 = 存量 {sum(legacy.values()):,} + 本轮 {len(issues) - sum(legacy.values()):,}")
    for dimension in new_types:
        if dimension in by_type:
            print(f"  {dimension:32s} 本轮 {(len(by_type[dimension]) - legacy.get(dimension, 0)):>6,}"
                  f"  累计 {len(by_type[dimension]):>6,}")
    print(f"  可预测合计 {delta_sum:,}")
    return 0 if delta_sum == 7_960 else 1


if __name__ == "__main__":
    raise SystemExit(main())
