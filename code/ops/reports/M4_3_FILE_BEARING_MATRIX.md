# M4-3 R1.1 · 19 个 GIS 文件的数据承载矩阵

日期：2026-11-04
依据：`code/data/raw/pleiades_gis_4_1/gis/`（v4.1 实提取）、`code/ops/m4-3/audit.json`、数据库实际表结构
原则：**不用"文件已归档"当作"数据已承载"**；也不为塞数据而新增业务表。

---

## 一、三个层次必须先分清

| 层次 | 含义 | 能否被接口/地图使用 | 能否按行追溯 |
|---|---|---|---|
| **业务入库** | 落到业务表并有专用列 | 能 | 能（`source_record_id`） |
| **派生** | 不整表入库，但被解析成某个字段/台账/文本 | 部分（取决于落到哪个字段） | 部分 |
| **仅归档** | 只在原始文件里；数据库里没有它 | 不能 | **不能** |

词表文件（`place_types` / `connection_types` / `languages_and_scripts` / `name_types` /
`association_certainty` / `archaeological_remains` / `transcription_accuracy` / `transcription_completeness`）
属于**仅归档**：它们本身是"取值字典"，不进任何表。

需要特别区分两件常被混为一谈的事：

- **词表文件是否入库**：否。
- **业务行里的那个属性值是否保留**：是——但它保留在**该业务行的 `raw_payload`（jsonb）**里，
  不是"词表文件被 source_record 承载"。

`raw_payload` 是 jsonb，所以用 SQL 的 `raw_payload->>'archaeological_remains'` **能取到值**，
但没有专用列、没有索引、接口层不返回——这叫"可追溯"，不叫"关系化承载"。

---

## 二、分类合计：6 + 2 + 11 = 19

| 分类 | 数量 | 文件 |
|---|---:|---|
| 业务入库 | **6** | `places`、`names`、`location_points`、`location_polygons`、`location_linestrings`、`connections` |
| 派生 | **2** | `places_accuracy`、`places_place_types` |
| 仅归档 | **11** | `place_types`、`connection_types`、`languages_and_scripts`、`name_types`、`association_certainty`、`archaeological_remains`、`transcription_accuracy`、`transcription_completeness`、`time_periods`、`README.md`、`howto.txt` |

---

## 三、总表

| # | 文件 | 规模 | 用途 | 分类 | 落点 / 处理 | 属性值在哪 | 能否结构化查询 |
|---:|---|---:|---|---|---|---|---|
| 1 | `places.csv` | 41,480 行 / 16.0 MB | 地点主表 | **业务入库** | `historical_place` 38,928；`representative_lat/lon` 另落 3,317 条 Point 位置行 | `uri / created / description / details / provenance / bounding_box_wkt` 在该 place 的 `raw_payload` | 仅 `place_type`/`canonical_name` 等有列；其余 jsonb |
| 2 | `names.csv` | 38,862 行 / 8.5 MB | 名称 | **业务入库** | `historical_place_name` 37,055 | `attested_form`(10,297)、`romanized_form_1/2/3`、`transcription_*` 在该名称行 `raw_payload` | `name_text/name_lang/name_type/association_certainty` 有列；其余 jsonb |
| 3 | `location_points.csv` | 25,038 行 / 9.4 MB | 点几何 | **业务入库** | `historical_place_location` 23,367（`geom_type='Point'`） | `accuracy_assessment_uri`、`archaeological_remains`、`association_certainty` 在该位置行 `raw_payload` | `geom/precision/uncertainty_m` 有列；其余 jsonb |
| 4 | `location_polygons.csv` | 4,385 行 / 1.4 MB | 面几何 | **业务入库** | 同上 4,114（`Polygon`，4 条先修复） | 同上 | 同上 |
| 5 | `location_linestrings.csv` | 5,265 行 / 9.2 MB | 线几何 | **业务入库（需 V9）** | 同上 4,893（`LineString`） | 同上 | 同上 |
| 6 | `connections.csv` | 13,603 行 / 2.5 MB | 地点间关联 | **业务入库** | `source_record` 13,603 + `candidate_match` 13,553 | `association_certainty`、时间两列在该连接行 `raw_payload` | 连接类型在 `evidence` 文本；jsonb 可取原值 |
| 7 | `places_accuracy.csv` | 41,480 行 / 80.6 MB | 地点级精度汇总 | **派生** | 只取 `location_precision` 交叉校验、`min_accuracy_meters` 作 3,317 条代表点行的 `uncertainty_m` | 不并入任何 `raw_payload` | 否（`accuracy_hull` 不入库） |
| 8 | `places_place_types.csv` | 51,009 行 / 0.9 MB | 地点→类型（多值） | **派生（仅汇总文本）** | 类型串写入 `historical_place.place_type_basis_note`；`place_type` 只取 `settlement`/`unknown` | **该文件的 48,030 条 NEW 关系没有逐行 source_record，也不在 raw_payload 里** | **否**（详见 §四） |
| 9 | `place_types.csv` | 192 行 | 类型词表 | **仅归档** | 供 #8 的标签解析（与旧词表 236 键取并集） | — | 否 |
| 10 | `connection_types.csv` | 40 种 | 连接类型词表 | **仅归档** | 供 #6 写人类可读类型名 | — | 否 |
| 11 | `languages_and_scripts.csv` | 103 代码 | 语言/文字词表 | **仅归档** | 供 #2 校验 `name_lang`/`name_script` | — | 否 |
| 12 | `name_types.csv` | 6 行 | 名称类型词表 | **仅归档** | 映射到 `primary`/`alternate` | — | 否 |
| 13 | `association_certainty.csv` | 3 行 | 关联确定性词表 | **仅归档** | 值直写 `historical_place_name.association_certainty`（文本列） | — | 值可查，词表本身不查 |
| 14 | `archaeological_remains.csv` | 5 行 | 考古遗迹程度词表 | **仅归档** | 文件不入库 | **值**在 32,374 条位置行的 `raw_payload` | 仅 jsonb 表达式，无列无索引 |
| 15 | `transcription_accuracy.csv` | 4 行 | 转写准确度词表 | **仅归档** | 文件不入库 | **值**在名称行 `raw_payload` | 仅 jsonb 表达式 |
| 16 | `transcription_completeness.csv` | 3 行 | 转写完整度词表 | **仅归档** | 文件不入库 | 同上 | 仅 jsonb 表达式 |
| 17 | `time_periods.csv` | 204 行 | 时间周期词表 | **仅归档** | 无业务表；与现库 220 行副本版本不同，**不覆盖** | — | 否 |
| 18 | `README.md` | 18.5 KB | 官方说明 | **仅归档** | 文档 | — | 否 |
| 19 | `howto.txt` | 117 B | 使用提示 | **仅归档** | 文档 | — | 否 |

---

## 四、`places_place_types` 必须说清的一件事

| 问题 | 答案 |
|---|---|
| 51,009 行关系是否入表？ | **否**。现有模型没有多值类型表，`historical_place.place_type` 只有 5 个允许值 |
| 是否生成了逐行 `source_record`？ | **否**。该文件的行不是任何业务行的来源，导入器不会为它建记录 |
| 是否在某个 `raw_payload` 里？ | **否**。`raw_payload` 存的是 place 行（`places.csv`），不是这个关系文件的行 |
| 那 48,030 条关系现在在哪？ | **只在原始文件归档里**（`code/data/raw/pleiades_gis_4_1/gis/places_place_types.csv`） |
| 业务上还能看到什么？ | 每个地点一个**汇总文本**：`place_type_basis_note = 'pleiades_place_types=settlement,villa'`；`place_type` 取 `settlement` 或 `unknown`（NEW 里 12,545 个地点含 settlement） |
| 能按类型筛选吗？ | **不能**。要支持就得建关联表 `place_type_link(place_id, type_key)`，属模型扩展 |

**本轮不建关联表**，登记为后续扩展事项（不阻塞 M4-4）。

---

## 五、未入库数据的实际影响（不许含糊）

| 数据 | 量 | 现在会怎样 | 影响 |
|---|---:|---|---|
| 类型多值关系 | 48,030 行 / 38,926 地点 | 只有汇总文本；无逐行记录 | **无法按类型筛选**，也无法回溯"这个类型来自哪一行" |
| `archaeological_remains` | 32,374 行（100%） | 值在 `raw_payload` | 无法按"有遗迹/无遗迹"过滤；可用 SQL jsonb 取 |
| `attested_form` | 10,297 条 | 值在 `raw_payload`（OWNER 已确认不补名称行） | 详情页不显示原文；可 JSON 取 |
| `romanized_form_1/2/3` | 37,055 行有 `romanized_form_1` | 在 `raw_payload` | 主名通常是罗马化形式，检索以 `name_text` 为准 |
| `transcription_accuracy / completeness` | 名称行 | 在 `raw_payload` | 无法判断转写质量 |
| `accuracy_hull` | 12,085 行 | 不入库 | 无"大概范围"多边形；可由位置重算 |
| `max/min_accuracy_meters` | 41,480 行 | 仅 3,317 条代表点行用到 | 其余地点的精度半径未使用 |

---

## 六、与 R1 的差异

| 项 | R1 | R1.1 | 原因 |
|---|---|---|---|
| 分类 | 6 入库 / 2 派生 / 3 源记录 / 8 归档 | **6 入库 / 2 派生 / 11 归档** | 三个 `transcription_*`/`archaeological_remains` 是**词表**，说成"由 source_record 承载"不成立；它们是归档文件，只有其**值**随业务行进了 `raw_payload` |
| `places_place_types` | 列为"派生"，未说明追溯性 | 明确：**无逐行记录、不在 raw_payload、只在归档** | 原表述容易被误读为"已入库" |

---

## 七、后续模型扩展（不阻塞本轮）

| # | 事项 | 触发条件 |
|---|---|---|
| 1 | `place_type_link(place_id, type_key)` 多值类型表 | 需要"按类型筛选/统计"时 |
| 2 | 名称 `attested_form` 列 | 需要在详情页展示原文时（Owner 已确认本轮不做） |
| 3 | 位置 `archaeological_remains` 列 | 需要按遗迹程度筛选时 |
| 4 | `source_record.external_uri` 列 | 需要按 Pleiades URI 反查时 |
