# M4-3 导入方案（R1.1 · 最终版）· Pleiades GIS 4.1 → `pleiades_gis_4_1`

日期：2026-11-04
状态：**方案定稿，等待 Owner 审查；未执行任何导入或 Migration。**
配套文件：

| 文件 | 内容 |
|---|---|
| `M4_3_IMPORT_COUNT_RECONCILIATION.md` | 数量重算（本文件所有数字的推导过程） |
| `M4_3_FILE_BEARING_MATRIX.md` | 19 个文件的承载矩阵 |
| `M4_3_V9_REVISION.md` | V9 最终设计稿 |
| `M4_3_R1_1_CHANGELOG.md` | 本轮变更与只读复核 |
| `ops/m4-3/import_counts.json` | 机器可读的数量结果 |
| `ops/m4-3/connections_audit.json` | 13,603 条连接的逐条分类与 ID |

---

## 1. 三项决策（OWNER CONFIRMED，不再讨论）

| # | 决策 | 落地口径 |
|---|---|---|
| 1 | **代表点采用 A2** | 3,317 个代表点合成独立 `Point` 位置行；位置 **35,691**；source_record 增量 **127,829**，总量 **157,220** |
| 2 | **`attested_form` 不补名称行** | 10,297 条原文只保留在原始数据与 `raw_payload`；名称行与 source_record **不增加** |
| 3 | **`place_without_geometry` 不写台账** | 7,200 作为独立验收指标，用 SQL 查询验证；V9 只加 3 种类型（共 23 种） |

---

## 2. 数据集登记

| 字段 | 值 |
|---|---|
| `dataset_id` | `pleiades_gis_4_1`（新建，不改 `pleiades_gis_4_1_slice`） |
| `source_id` / 版本 | `pleiades` / `4.1` |
| `dataset_name` | `Pleiades Datasets v4.1 — GIS CSV` |
| `homepage` | `https://doi.org/10.5281/zenodo.15540082` |
| `record_count` | 41,480（place 作用域） |
| `local_path` | `code/data/raw/pleiades_gis_4_1/gis/` |
| `evidence` | `code/ops/m4-3/audit.json`（19 文件 SHA256 + 全量计数） |

---

## 3. 集合与识别

| 项 | 值 |
|---|---:|
| v4.1 地点 | 41,480 |
| 现库切片地点 | 2,643 |
| 交集 | 2,552 |
| 仅切片有 | 91 |
| **NEW（导入对象）** | **38,928** |

```
alias = 既有 source_record(dataset_id='pleiades_gis_4_1_slice', record_scope='place', is_active)
for place in places.csv:
    if place.id in alias → SKIP（写 is_active=false 源记录，reason='superseded_by_newer_snapshot'）
    else                 → NEW（建地点）
```

- 稳定键：`uri` 尾段（`/places/433032` → `433032`）；`id` 只在单文件内唯一。
- 唯一性：`uq_historical_place_c04 (dataset_id, grain_key)`，`grain_key='pleiades:'||id`。
- 91 个"仅切片有"的地点保持原样，不删不改。
- **别名映射**在导入器内存构造（`source_record` 无 `place_id` 列），零结构改动：
  用于把 1,358 条"一端是旧切片地点"+ 373 条"两端都是旧切片"的连接解析到既有 `place_id`。

---

## 4. 名称 / 位置 / 连接

| 对象 | 导入量 | 规则 |
|---|---:|---|
| 名称 | 37,055 | 父地点 ∈ NEW 才导；`association_certainty` 直入列；`language_tag` 空 → `und`；`geographic→primary`，其余 `alternate` |
| 位置 — 真实 | 32,374 | 点 23,367 / 面 4,114 / 线 4,893 |
| 位置 — 代表点合成 | 3,317 | 见 §5 |
| 连接（源记录） | 13,603 | 全量保留，含悬空 28、自环 1、空行 1 |
| 连接（候选） | **13,553** | 两端可解析、非自环，按有序对去重 |

### 4.1 连接的分类（互斥，已逐条核实）

| 类别 | 记录数 |
|---|---:|
| A 两端可解析 | **13,575** |
| ├ A1 真实自环（`1001909 → 1001909`） | 1 |
| └ A2 正常对 | 13,574 |
| B 至少一端悬空 | **28** |
| ├ B1 整行空（`connections.csv` 第 4498 行） | 1 |
| ├ B2 单端悬空（其中 3 条指向 `/errata/`） | 27 |
| └ B3 两端都悬空 | 0 |
| **合计** | **13,603** |

端点侧数 **29**（`connects_to` 28 + `place_id` 1）。"29 侧 / 28 记录 / 2 条字面 a==b / 1 条真实自环"
四个数各有所指，不矛盾。

候选：13,574 − 21（同有序对重复，按 `uq_candidate_match_c09`）= **13,553**。
1 条真实自环被 `ck_candidate_match_distinct_places` 拒绝，空行被"悬空"排除。

---

## 5. 代表点合成（A2）

### 5.1 为什么必须做

`historical_place` **没有坐标列**；地图取点（`PlaceQueryService.PREFERRED_LOCATION`）只认
`historical_place_location` 的 `representative_lon/lat`，且要求 `geom IS NOT NULL`。
v4.1 里 3,317 个 NEW 地点有代表点与 bbox，却没有任何 location 行 → 不合成则**在地图上不可见**。

### 5.2 字段取值

| 字段 | 值 |
|---|---|
| `geom` / `geom_type` | `POINT(lon lat)` / `Point` |
| `original_x / y` | CSV 原文字符串 |
| `original_crs` / `crs_confidence` / `axis_order_verified` | `EPSG:4326` / `confirmed` / `true` |
| `location_precision` | 源值：2,589 precise / 728 rough |
| `uncertainty_m` | `places_accuracy.min_accuracy_meters`（正数，5–9,310 m）；`-1` → NULL + 台账 728 条 |
| `time_bound_type` | `unknown`（**不会**产生台账，见 §7.2） |
| 源记录 | `record_scope='location'`、`external_id='<pid>-representative'`、`parent_external_id=<pid>`、`raw_file='places.csv'`、`raw_record_index=<行号>` |

---

## 6. 几何承载

| 类型 | 数量 | `geom` | 代表点 |
|---|---:|---|---|
| Point | 26,684 | `POINT(x y)` | 自身 |
| Polygon | 4,114 | WKT 原样；4 条先修 | `ST_PointOnSurface` |
| LineString | 4,893 | WKT 原样 | `ST_LineInterpolatePoint(geom, 0.5)` |

- 插入顺序固定 **点 → 线 → 面**，让 `ORDER BY location_id LIMIT 1` 先取到精确点。
- 面/线必须补 `representative_lon/lat`，否则地图不显示。
- 无效面修复：`ST_MakeValid` → `ST_CollectionExtract(...,3)`；得 `MultiPolygon` 则按 `MultiPolygon`
  写（值域已允许）；仍为空则跳过并记 `geometry_invalid_repaired`。原始 WKT 留在 `raw_payload`。
- `is_preferred`：每地点第一条点行置 `true`（当前查询未用，为后续留口）。

---

## 7. 精度与时间

### 7.1 精度（两级，只算 NEW）

| 级别 | 数值 |
|---|---|
| 地点级（`places.csv`） | **precise 27,418 / rough 11,510** |
| 位置级（A2 合计 35,691） | **precise 31,223 / rough 4,468** |

细分：Point 真实 23,367（全 precise）· Point 合成 2,589 precise + 728 rough · Polygon 374 precise +
3,740 rough · LineString 4,893（全 precise）。
**源值直传**，不得把非 precise 一律写 `unknown`。

### 7.2 时间

`year_after_which`/`year_before_which` → 天文纪年（无公元 0）；两端有 `tpq_taq`；单端单侧 NULL；
都无 `unknown`；地点级由子行包络取 `derived_tpq_taq`，不得上提覆盖。

**NEW 无时间**：名称 2,986 · 位置 1,977 · 地点 2,583。**这些都不产生台账**——
`unknown_time_bound_type` 只在 CHGIS 分支开票（`normalize.py:615/621/1509-1523`），Pleiades 恒为 0。

---

## 8. 追溯

`row → source_record_id → (dataset_id, raw_file, raw_record_index) → raw_payload(jsonb) → content_hash → first/last_batch_id`

- 归一化产物另存 `code/data/staging_m4_3/`，**不覆盖** `code/data/staging`。
- `uri` 只在 `raw_payload`（不加列）。
- **例外（必须知道）**：`places_place_types` 的 48,030 条关系**没有逐行记录**，只在原始归档里，
  业务上只有一个汇总文本（见承载矩阵 §四）。

---

## 9. 跨源候选（只出候选，不合并）

| 对比 | ≤1 km | ≤10 km | ≤50 km | 处理 |
|---|---:|---:|---:|---|
| CHGIS | 0 | 0 | 各 1 | 忽略（地理不相交） |
| MCGD | 1 | 2 | 43 | 写候选，人工裁决 |
| WHG 样本 | 36 | 525 | 704 | 优先 ≤1 km 的 36 条 |

名称匹配仅 3 对（跨文字系统），不作判据；`connections.same_as`（68 条）也不作合并依据。

---

## 10. 人工保护

`created_by='manual'` / `locked` / `manual_edited_fields` 三档沿用；地点级计数用独立的
`cnt_place_blocked`（不得复用源记录级 `cnt_blocked`，M4-2 曾因此触发 G1 恒等式失败）。
导入前后核对人工地点计数与 `updated_at` 不变。

---

## 11. 验收指标

### 11.1 可冻结（源数据已验证）

| # | 指标 | 期望 |
|---|---|---|
| 1 | `historical_place` 净增 | **38,928** |
| 2 | `historical_place_name` 净增 | **37,055** |
| 3 | `historical_place_location` 净增 | **35,691** |
| 4 | 几何拆分 | Point **26,684** · Polygon **4,114** · LineString **4,893** |
| 5 | `source_record` 净增 / 总量 | **127,829 / 157,220** |
| 6 | `candidate_match` 净增 | **13,553** |
| 7 | inactive 重叠记录 | **2,552**（`superseded_by_newer_snapshot`） |
| 8 | 位置级精度 | precise **31,223** / rough **4,468** |
| 9 | 地点级精度（子行核对） | precise 27,418 / rough 11,510 |
| 10 | `geom` 非空率 | 100% |
| 11 | 面/线 `representative_lon/lat` 非空 | 100% |
| 12 | 无坐标地点（验收查询，不写台账） | **7,200** |
| 13 | 人工地点计数 / `updated_at` | 不变 |
| 14 | 幂等 | 第二轮增量全 0（`last_batch_id` 按设计推进） |
| 15 | 正式库 | 全程 V5、行数不变 |

### 11.2 可预测台账（源数据 + 代码规则）

| 类型 | 期望 |
|---|---:|
| `missing_coordinate` | **7,200** |
| `geometry_invalid_repaired` | **4** |
| `connection_endpoint_missing` | **28** |
| `accuracy_unknown_sentinel` | **728** |
| 其余（`coordinate_out_of_range` / `parent_place_not_in_sample` / `truncated_slice_tail` / `unknown_time_bound_type`） | 0 |
| **可预测合计** | **7,960** |

### 11.3 必须 M4-4a 实测后才能冻结

| 项 | 原因 |
|---|---|
| `duplicate_external_id` / `derived_value_mismatch` / `manual_edit_conflict` | 导入器运行期合成，取决于多行组与保护位 |
| `data_quality_issue` 净增总量 | 上面三项为未知量 |
| 台账类型总数 | 若三项为 0，类型数会少 |

### 11.4 地图 / 搜索 / 详情（E2E）

| 场景 | 判据 |
|---|---|
| 罗马 bbox | 出现 Polygon/LineString 来源地点，HTTP 200，`geom_type` 正确 |
| 雅典/庞贝搜索 | 名称命中；详情页多条位置，精度不一刀切为 `unknown` |
| 无坐标地点 | 搜索命中（名称），地图不出现（预期，不报错） |
| 面/线地点 | 地图出现代表点；点击开详情不因 `geom_type != Point` 报错 |
| 时间轴 | 抽样 10 个新地点落入正确时段列 |

---

## 12. V9（详见 `M4_3_V9_REVISION.md`）

- `ck_hpl_geom_type` + `LineString`；
- `ck_data_quality_issue_issue_type` + **3** 值（20 → 23）：`geometry_invalid_repaired`、
  `connection_endpoint_missing`、`accuracy_unknown_sentinel`；**不含** `place_without_geometry`；
- 只在隔离测试库执行；建议新建 `canvas_history_m4_3`。

---

## 13. 风险

| # | 风险 | 缓解 |
|---|---|---|
| 1 | 整包覆盖导致 104 个地点退化 | SKIP 规则 + 导入前快照对比 |
| 2 | 代表点未合成 → 地点不可见 | A2 已定；指标 #3/#4 卡死 |
| 3 | 精度被压成 unknown | 源值直传 + 指标 #8 |
| 4 | `connects_to` 未归一 → 假孤儿 | 单测 + 指标 #6 |
| 5 | `ST_MakeValid` 产出集合体 | `ST_CollectionExtract` + 跳过记账 |
| 6 | 插入顺序错 → 代表点取到粗框质心 | 固定 点→线→面 |
| 7 | 台账无法预先冻结 | 指标 11.3 明确标"须实测" |
| 8 | 测试库混入既有基线 | 新建 `canvas_history_m4_3` |

---

## 14. 阶段划分

| 阶段 | 内容 | 出口 |
|---|---|---|
| M4-4a | 写 V9 + 3 处脚本改造 + 归一化到 `staging_m4_3/` | 7 张 CSV + **冻结台账实际行数** |
| M4-4b | 隔离库 V9 → 空库完整导入 → 幂等复跑 | §11.1 全部 + §11.2 实测值 |
| M4-4c | 地图/搜索/详情 E2E + 人工保护 + M0–M3 回归 | E2E 报告 |
| M4-5 | 正式库（需单独授权） | — |

---

## 15. 待决事项：0

三项决策已由 Owner 确认并写入 §1，本轮无遗留待决项。

不阻塞 M4-4 的**模型扩展**登记（需要时再做，不在本轮范围）：

| # | 事项 | 触发条件 |
|---|---|---|
| 1 | `place_type_link(place_id, type_key)` 多值类型表 | 需要按类型筛选/统计时 |
| 2 | 名称 `attested_form` 列 | 需要在详情页展示原文时 |
| 3 | 位置 `archaeological_remains` 列 | 需要按遗迹程度筛选时 |
| 4 | `source_record.external_uri` 列 | 需要按 Pleiades URI 反查时 |

---

**M4-3 R1.1 — IMPORT PLAN FINAL / READY FOR OWNER REVIEW（未启动 M4-4）**
