# M4-3 R1.1 · 变更记录与只读复核

日期：2026-11-04
分支：`m4-3-pleiades-gis`
性质：**数量核算修正 + 承载矩阵修正 + 方案文档统一**。未改业务代码、未改数据库、未执行 Migration、未导入。

---

## 一、三项决策已固化（OWNER CONFIRMED）

| # | 决策 | 落地后的数字 |
|---|---|---|
| 1 | 代表点 **A2**：合成 3,317 条独立 Point 位置行 | 位置 **35,691**；source_record 增量 **127,829**；总量 **157,220** |
| 2 | `attested_form` **不补**名称行（10,297 条） | 名称行 37,055、source_record 127,829 **不增加** |
| 3 | `place_without_geometry` **不写台账**（7,200 只作验收查询） | 台账可预测合计 **7,960**；V9 只加 **3** 种类型（共 23） |

---

## 二、本轮修正清单

### 2.1 核算脚本与 JSON

| 项 | R1 | R1.1 |
|---|---:|---:|
| `source_record_delta.total` | 124,512（A1） | **127,829（A2，采纳）** |
| `expected_total` | 153,903 | **157,220** |
| 对照口径 | 无 | 保留 A1（124,512 / 153,903）作 reference |
| 台账预估 | 无结构 | 新增 `ledger_estimate`（含 7 项可预测 + 代码依据） |
| 决策标记 | 无 | 新增 `decisions` 三项，标注 OWNER CONFIRMED |

`import_counts.json` 现含：`decisions` / `sets` / `place_precision` / `names` / `locations` /
`coverage` / `connections` / `place_types` / `languages` / `placement_accuracy` /
`rep_point_materialisation` / `geometry_invalid` / `source_record_delta` / `ledger_estimate`。

### 2.2 connections 逐条核实（新增脚本）

新增 `code/ops/m4-3/connections_audit.py` → `connections_audit.json`，输出**互斥**分类与全部记录 ID：

| 类别 | 记录数 |
|---|---:|
| A 两端可解析 | 13,575 |
| ├ A1 真实自环 `1001909 → 1001909` | 1 |
| └ A2 正常对 | 13,574 |
| B 至少一端悬空 | 28 |
| ├ B1 整行空（第 4498 行 `,,,,,,,,,,,,`） | 1 |
| ├ B2 单端悬空（含 3 条 `/errata/` 目标） | 27 |
| └ B3 两端都悬空 | 0 |
| **合计** | **13,603** |

端点侧数 29（`connects_to` 28 + `place_id` 1）。

**R1 的矛盾已消除**："29 = 端点侧数"、"28 = 记录数"、"2 = 字面 a==b（含空行）"、"1 = 真实自环"，
四个数字各自有明确归属，不再混用。

候选：13,574 − 21（按 `uq_candidate_match_c09` 有序对去重）= **13,553**（未调整口径）。

### 2.3 承载矩阵

| 项 | R1 | R1.1 |
|---|---|---|
| 分类 | 6 入库 / 2 派生 / 3 源记录 / 8 归档 | **6 入库 / 2 派生 / 11 归档** |
| 三个词表（`archaeological_remains`、`transcription_accuracy`、`transcription_completeness`） | 描述为"由 source_record 承载" | 明确为**词表文件本身不入库**；只有其**值**随业务行进 `raw_payload` |
| `places_place_types` 48,030 条关系 | 只说"汇总文本" | 明确：**无逐行 source_record、不在 raw_payload、只在归档**，因此无法逐行追溯、无法按类型筛选 |
| 可查询性 | 笼统 | 区分"有列可查" vs "仅 jsonb 表达式可取" vs "完全不可查" |

### 2.4 V9

| 项 | R1 | R1.1 |
|---|---|---|
| 新 `issue_type` | 4 个（共 24） | **3 个（共 23）** |
| `place_without_geometry` | 在 CHECK 中 | **从 CHECK 删除**，只保留验收 SQL |
| 其余 | — | `LineString` 值域、四个数量、校验/回滚 SQL 均保留 |

### 2.5 台账规则（本轮重点核实）

R1 写 `unknown_time_bound_type ≥7,546`（名称 2,986 + 位置 1,977 + 地点 2,583）——**错误，已撤销**。

代码依据：

- `normalize.py:615` `rule_basis_available = date_rules.loaded`（CHGIS 的 date-rule 工作簿）
- `normalize.py:621` `for record in chgis_records:`（该开票逻辑在 **CHGIS 循环内**）
- `normalize.py:1509-1523` 仅当 `rule_basis_available` + `BEG_RULE/END_RULE` 未登记 +
  `time_bound_type == "unknown"` 时才开票

→ Pleiades 不在 `chgis_records`，**永远不产生该类型**；3,317 条合成位置行的
`time_bound_type='unknown'` **不触发**任何台账。

重新计算的可预测台账：

| 类型 | 数量 |
|---|---:|
| `missing_coordinate` | 7,200 |
| `geometry_invalid_repaired` | 4 |
| `connection_endpoint_missing` | 28 |
| `accuracy_unknown_sentinel` | 728 |
| `coordinate_out_of_range` / `parent_place_not_in_sample` / `truncated_slice_tail` / `unknown_time_bound_type` | 0 |
| **合计** | **7,960** |

另外确认：子行（名称/位置）的 `empty_name` / `missing_coordinate` / `z_ordinate_discarded`
**不单独开票**——`normalize.py:1683-1695` 只遍历 `group.primary.quality_flags`，唯一例外是
`parent_place_not_in_sample`（`normalize.py:1704-1720`）。

### 2.6 文档统一

- `M4_3_IMPORT_PLAN.md` 成为唯一主文件，全部数字切到 A2；
- 三份配套（数量、矩阵、V9）与主文件口径一致；
- `M4_3_R1_CHANGELOG.md` 顶部标注**已被本文件取代**；
- 待决事项：**0 项**（模型扩展事项单列为"不阻塞"）。

---

## 三、三类数字的边界（本轮反复强调）

| 类别 | 例子 | 状态 |
|---|---|---|
| **源数据验证** | 41,480 地点；2,552 交集；35,691 位置；13,553 候选；27,418/11,510 精度；7,200 无坐标 | 可直接作验收值 |
| **按设计推算** | 127,829 source_record（= 各项之和）；157,220 总量；7,960 可预测台账 | 依赖实现与规则，导入后逐项核对 |
| **必须 M4-4a 实测** | `duplicate_external_id` / `derived_value_mismatch` / `manual_edit_conflict` / 台账总增量 / 类型总数 | **不得**现在写死 |

---

## 四、只读复核结果

### 4.1 原始数据（未变）

| 项 | 值 |
|---|---|
| zip SHA256 | `94c5c337d27a07f1a5fa231b6513e40e6d3cf7d5ad7b8c010f8e8bfd9159cd85` |
| zip 字节 | 286,621,469 |
| 19 个文件（csv+README+howto）清单指纹 | `df030b8b9c29220e863ad7e6c3bd5c296ef54b767cc1203977bbffe51e9b4073` |

> 清单指纹算法：`sha256sum gis/*.csv gis/README.md gis/howto.txt | sha256sum`（按 glob 顺序）；
> 与 R0 的逐文件哈希（`audit.json`）一致。

### 4.2 staging（未变）

```
candidate_matches.csv            4e29c2ec64ebe263…    historical_place_names.csv       80674c0ded553241…
data_datasets.csv                4b530673373005cc…    historical_places.csv            bfddd91c6fb2a502…
data_quality_issues.csv          7b9020ee41a1ad14…    source_records.csv               83bd11626964a21d…
historical_place_locations.csv   9e987ba578e933ed…
```

### 4.3 数据库（未变）

| 库 | Flyway | source_record | place | name | location | candidate | issue |
|---|---:|---:|---:|---:|---:|---:|---:|
| `canvas_history` | **5** | 29,391 | 19,039 | 47,499 | 18,101 | 53,131 | 12,831 |
| `canvas_history_m2check` | 8 | 29,398 | 19,091 | 47,534 | 18,136 | 53,131 | 12,833 |

本轮执行的 SQL 仅 `SELECT` / `\d` / `pg_get_constraintdef`；未建库、未删库、未加约束、未写入。

### 4.4 Git（本轮开工 → 收工）

| 项 | 值 |
|---|---|
| 开工 HEAD | `232e79abf4e68fe32104b44e564f005d41d8abfb` |
| 本轮改动 | 6 个文件修改 + 2 个文件新增（均在 `code/ops/`） |
| 业务代码 | **0 改动** |
| 未跟踪 | 仅 `汇报/`（交付目录） |

---

## 五、待决事项

**0 项。** 三项决策已由 Owner 确认；`places_place_types` 多值关联表等 4 项模型扩展已登记为
"不阻塞 M4-4 的后续事项"。

---

## 六、本地未做的事

1. 未写 V9 迁移文件（只在报告里给设计稿）；
2. 未在任何库执行 Migration（正式库 V5、测试库 V8）；
3. 未导入数据、未建新库；
4. 未改 `code/p0/**` 与 `code/ops/import_staging.py`；
5. 未覆盖 `code/data/staging`、未改原始 zip 与提取件；
6. 未做任何跨源合并。
