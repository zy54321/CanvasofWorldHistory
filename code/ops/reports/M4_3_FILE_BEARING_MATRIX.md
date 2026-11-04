# M4-3 R1 · 19 个 GIS 文件的数据承载矩阵

日期：2026-11-04
依据：`code/data/raw/pleiades_gis_4_1/gis/`（v4.1 实提取）、`code/ops/m4-3/audit.json`、数据库实际表结构
原则：**不用"文件已归档"当作"数据已承载"**；也不为塞数据而新增业务表。

图例：
- **入库** = 落到业务表，可被接口/地图/搜索使用
- **派生** = 不整表入库，但被解析成某个字段/台账
- **留存** = 只进 `source_record.raw_payload`（仍可按行追溯，但不可查询）
- **归档** = 只在原始文件里，不进入数据库任何形态

---

## 一、总表（19 个文件）

| # | 文件 | 规模 | 用途 | 是否入库 | 落点 | 合并进已有对象 | 只留 raw_payload | 只留归档 | 本轮不导入的原因 / 后续 |
|---:|---|---:|---|---|---|---|---|---|---|
| 1 | `places.csv` | 41,480 行 / 16.0 MB | 地点主表（title、uri、代表点、bbox、精度） | **是** | `historical_place`（38,928 新增）+ `historical_place_location`（3,317 条代表点，见方案 A2） | 否 | `uri / created / description / details / provenance / bounding_box_wkt` 留在 place 的源记录里 | — | 7,200 个地点无任何坐标，只入 `historical_place`，不建位置行 |
| 2 | `names.csv` | 38,862 行 / 8.5 MB | 名称（含类型、语言、原文、罗马化、时间） | **是** | `historical_place_name`（37,055 新增） | 否 | `attested_form`（10,297）、`romanized_form_2/3`、`transcription_accuracy/completeness` | — | `attested_form` 无对应列，暂不建列（见 §三·待决 1） |
| 3 | `location_points.csv` | 25,038 行 / 9.4 MB | 点的几何与精度 | **是** | `historical_place_location`（23,367 新增，`geom_type='Point'`） | 否 | `accuracy_assessment_uri`、`archaeological_remains`、`association_certainty` | — | 无 |
| 4 | `location_polygons.csv` | 4,385 行 / 1.4 MB | 面的几何与精度 | **是** | 同上（4,114 新增，`geom_type='Polygon'`；4 条先 `ST_MakeValid`） | 否 | 同上 | — | 1 条无效面属旧切片地点，本轮跳过 |
| 5 | `location_linestrings.csv` | 5,265 行 / 9.2 MB | 线的几何与精度 | **是（需 V9）** | 同上（4,893 新增，`geom_type='LineString'`） | 否 | 同上 | — | 值域缺 `LineString`，必须 V9 |
| 6 | `connections.csv` | 13,603 行 / 2.5 MB | 地点间关联（40 种类型） | **是** | `source_record`（13,603）+ `candidate_match`（13,553，`relation_type='pleiades_connection'`） | 否（**绝不合并**） | `association_certainty`、时间两列 | — | 28 条悬空 + 1 条自环不入候选，但保留源记录 |
| 7 | `places_accuracy.csv` | 41,480 行 / 80.6 MB | 地点级精度汇总（hull、max/min 米、hull 依据） | **派生**（不整表入库） | 取 `location_precision` 做交叉校验；`min_accuracy_meters` 作为 3,317 条代表点行的 `uncertainty_m` 来源 | — | 否（该文件的列并入 place 的源记录会造成一份 payload 两处来源，故不并入） | — | 不入库原因：`accuracy_hull` 80 MB 且可由位置重算；`-1` 哨兵 11,438 行需清洗 |
| 8 | `places_place_types.csv` | 51,009 行 / 0.9 MB | 地点 → 类型（多值） | **否**（无业务表） | 仅派生：把类型串写入 `historical_place.place_type_basis_note`（文本） | 部分（汇总成一行文本） | 是（源记录里保留 place 行，不含本文件行） | 是 | 现有模型只有 5 值 `place_type`，无多值表；不为它新建表 |
| 9 | `place_types.csv` | 192 行 / 30 KB | 类型词表 | **否** | 供 #8 的标签解析（与旧词表 236 键取并集） | — | — | 是 | 参考词表，不进业务表 |
| 10 | `connection_types.csv` | 40 种 / 2.7 KB | 连接类型词表 | **否** | 供 #6 的 `evidence` 文本写人类可读类型 | — | — | 是 | 同上 |
| 11 | `languages_and_scripts.csv` | 103 代码 / 8.8 KB | 语言与文字代码表 | **否** | 供 #2 的 `name_lang` / `name_script` 校验 | — | — | 是 | 同上；NEW 用到 87 种，3 种不在表内 |
| 12 | `name_types.csv` | 6 行 / 0.8 KB | 名称类型词表 | **否** | 映射到 `primary / alternate` | — | — | 是 | 现有名称类型只有 3 值 |
| 13 | `association_certainty.csv` | 3 行 / 0.5 KB | 关联确定性词表 | **否** | 值直接写入 `historical_place_name.association_certainty`（文本列，无需词表） | — | — | 是 | 词表本身不入库 |
| 14 | `archaeological_remains.csv` | 5 行 / 172 B | 考古遗迹程度词表 | **否** | — | — | 位置行的该字段值随行留在 raw_payload | 是 | 位置表无对应列 |
| 15 | `transcription_accuracy.csv` | 4 行 / 457 B | 转写准确度词表 | **否** | — | — | 名称行该字段随行留在 raw_payload | 是 | 名称表无对应列 |
| 16 | `transcription_completeness.csv` | 3 行 / 586 B | 转写完整度词表 | **否** | — | — | 同上 | 是 | 同上 |
| 17 | `time_periods.csv` | 204 行 / 38 KB | 时间周期词表 | **否** | — | — | — | 是 | 无业务表；且与现库 220 行副本版本不同，**不覆盖** |
| 18 | `README.md` | 18.5 KB | 官方说明（CRS、精度语义、字段定义） | **否** | — | — | — | 是 | 文档；其"文件清单"与实际不符（无 `locations.csv`） |
| 19 | `howto.txt` | 117 B | 使用提示 | **否** | — | — | — | 是 | 文档 |

分类合计（6 + 2 + 3 + 8 = 19）：

- **入库 6 个**：`places`、`names`、`location_points`、`location_polygons`、`location_linestrings`、
  `connections`（→ `source_record` + `candidate_match`）
- **派生 2 个**：`places_accuracy`（只取精度与 `uncertainty_m` 来源）、`places_place_types`（汇总成文本）
- **仅由源记录承载 3 个**：`archaeological_remains`、`transcription_accuracy`、`transcription_completeness`
  （值随所在行进入 `raw_payload`，词表本身不入业务表）
- **仅归档 8 个**：`place_types`、`connection_types`、`languages_and_scripts`、`name_types`、
  `association_certainty`、`time_periods`、`README.md`、`howto.txt`

> 说明：`places_accuracy` 的 `accuracy_hull` 列属于"归档级"（不入库、不派生），但文件本身算"派生"，
> 不重复计数。

---

## 二、未入库数据的具体影响（不许含糊）

| 数据 | 量 | 现在会怎样 | 影响 |
|---|---:|---|---|
| `places_place_types` 多值类型 | 48,030 行 / 38,926 地点 | 只有 `settlement` 映射到 `place_type`；其余落 `unknown`，全量类型串写进 `place_type_basis_note` | 无法按类型筛选（如"只看神庙/道路"）；文本可读但不可查询 |
| `archaeological_remains` | 32,374 行（100% 有值） | 只在 raw_payload | 无法按"有遗迹/无遗迹"过滤 |
| `attested_form`（原文） | 10,297 条 | 只在 raw_payload | 详情页看不到希腊文/楔形文字原文 |
| `romanized_form_2/3` | 未单列，随行 | 只在 raw_payload | 少量别名检索不到 |
| `transcription_accuracy / completeness` | 名称行 | 只在 raw_payload | 无法判断转写质量 |
| `accuracy_hull` | 12,085 行（其中 NEW 11,511） | 不入库 | 无"大概范围"多边形；可用位置重算 |
| `max/min_accuracy_meters` | 41,480 行，11,438 行 NEW 为 `-1` | 仅 3,317 条代表点行用到，其余不用 | 大量地点的精度半径信息未使用 |
| `time_periods` | 204 行 | 只归档 | 无影响（当前没有按时段分类的功能） |

**结论（必须让 Owner 看到）**：v4.1 里约 **13 万条字段级事实**（类型/遗迹/原文/转写质量）本轮只做到
"可追溯（raw_payload）"，**做不到"可查询"**。这是现有模型的边界，不是导入实现的问题。

---

## 三、待决事项（2 项，都需要 Owner 拍板）

### 待决 1：`attested_form` 是否补成名称行？

- 现状：10,297 条有原文形式（希腊文、拉丁文、阿卡德语等），模型没有对应列。
- 选项 A（推荐）：不动。原文留在 raw_payload，详情页显示"原始形式未入库"。
- 选项 B：把它们作为 `name_type='alternate'`、`name_text=attested_form`、`name_script` 按语言填的**额外名称行**导入
  → 名称行 +10,297，源记录 +10,297（总计 source 167,517 / name 94,851）。
- 代价：会与"罗马化名"形成同义重复，且 `uq_hpn_c08` 需保证不撞键（`name_type+name_text+lang` 组合可达）。

### 待决 2：`places_place_types` 是否需要多值承载？

- 选项 A（推荐，零结构变更）：类型串进 `place_type_basis_note`（文本），`place_type` 只取 `settlement`/`unknown`。
- 选项 B（需新表）：新建 `place_type_link(place_id, type_key)`，48,030 行 → 需要 Migration 与新接口，
  属模型扩建，建议留到真正需要"按类型筛选"时再做。
