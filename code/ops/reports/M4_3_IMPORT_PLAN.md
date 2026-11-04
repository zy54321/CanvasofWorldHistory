# M4-3 导入方案（修订 R1）· Pleiades GIS 4.1 → `pleiades_gis_4_1`

日期：2026-11-04
基线：`M4_3_IMPORT_COUNT_RECONCILIATION.md`（数量）、`M4_3_FILE_BEARING_MATRIX.md`（19 文件）、`M4_3_V9_REVISION.md`（Migration）
状态：**方案修订完成，未执行任何导入或 Migration。**

---

## 0. 本轮修订了什么（与 R0 的差异）

| # | R0 的问题 | R1 的处理 |
|---|---|---|
| 1 | `overlap` 恒为 0（把 `new ∩ slice` 当交集） | 改为 `all ∩ slice` = **2,552** |
| 2 | source_record 增量 121,931，漏了 inactive 记录 | **124,512**（含 2,552），总量 **153,903** |
| 3 | candidate 写成 13,572 / 13,574 | 按 `uq_candidate_match_c09` 有序对去重 = **13,553** |
| 4 | 新增地点精度直接用整包 29,396 / 12,084 | 按 NEW 过滤 = **27,418 / 11,510**；另补位置级精度 |
| 5 | `-1` 哨兵用整包 12,007 | NEW 11,438；**实际入账仅 728** |
| 6 | 未识别"有代表点但无 location 行" | **3,317（NEW）**，给出 A1/A2 两套口径 |
| 7 | 7,509 与 10,974 混用 | 三种口径分层，验收采用 **7,200** |
| 8 | 19 个文件未逐一交代 | 见承载矩阵（6 入库 / 2 派生 / 3 仅源记录 / 8 归档） |
| 9 | 验收指标含不可核实数字 | 拆成"可冻结"与"须 M4-4a 实测后冻结"两类 |

---

## 1. 已锁定决策（不再讨论）

1. **方案 A：增量补全**，保留现有 `pleiades_gis_4_1_slice` 不动。
2. 2,552 条重叠地点写 `source_record`，`is_active=false`、`inactive_reason='superseded_by_newer_snapshot'`，**不创建重复地点**。
3. **V9 已批准，但只在隔离测试库执行**；正式库维持 V5，未单独授权不得迁移或写入。

---

## 2. 数据集登记

| 字段 | 值 |
|---|---|
| `dataset_id` | `pleiades_gis_4_1`（新建，**不改** `pleiades_gis_4_1_slice`） |
| `source_id` | `pleiades` |
| `dataset_version` | `4.1` |
| `dataset_name` | `Pleiades Datasets v4.1 — GIS CSV` |
| `homepage` | `https://doi.org/10.5281/zenodo.15540082` |
| `record_count` | 41,480（place 作用域行数） |
| `local_path` | `code/data/raw/pleiades_gis_4_1/gis/` |
| `acquisition_method` | Zenodo 固定版本归档（286,621,469 B，MD5 `ad339c92c6b895f0eb9a52228da498c4`） |
| `evidence` | `code/ops/m4-3/audit.json`（19 文件 SHA256 + 全部计数） |

---

## 3. 集合与识别规则

| 项 | 值 |
|---|---:|
| v4.1 地点 | 41,480 |
| 现库切片地点 | 2,643 |
| 交集 | 2,552 |
| 仅切片有 | 91 |
| **NEW（导入对象）** | **38,928** |

判定：

```
alias = 既有 source_record(dataset_id='pleiades_gis_4_1_slice', record_scope='place', is_active)
for place in places.csv:
    if place.id in alias → SKIP（写 inactive 源记录，不建地点）
    else                 → NEW（建地点）
```

- 稳定键：`uri` 尾段（`/places/433032` → `433032`）；`id` 只在单文件内唯一，不能当跨表键。
- 落库唯一性：`uq_historical_place_c04 (dataset_id, grain_key)`，`grain_key='pleiades:'||id`。
- 91 个"仅切片有"的地点**保持原样**，不删不改。

### 3.1 别名映射（供连接使用，零结构改动）

`source_record` 没有 `place_id` 列，别名在**导入器内存**里构造：

```python
alias = {ext: pid for (ds, ext), pid in existing_place_keys.items()
         if ds == 'pleiades_gis_4_1_slice'}
resolve = lambda pid: new_place_ids.get(pid) or alias.get(pid)
```

作用：让"一端是旧切片地点"的 **1,358 条**连接、以及"两端都是旧切片"的 **373 条**连接仍能落到既有 `place_id`。

---

## 4. 名称 / 位置 / 连接

| 对象 | 导入量 | 关键规则 |
|---|---:|---|
| 名称 | **37,055** | 父地点 ∈ NEW 才导；`association_certainty` 直接入列（100% 有值）；`language_tag` 空 → `und`；类型 `geographic→primary`，其余 `alternate` |
| 位置 | **32,374**（A1）/ **35,691**（A2） | 见 §6、§7 |
| 连接（源记录） | **13,603** | 全部保留源记录，含悬空 28、自环 1、重复 9 |
| 连接（候选） | **13,553** | 两端可解析且非自环，按有序对去重；`status='confirmed'`、`reviewer='system:source_attested'` |

连接的三类例外（都保留源记录，只是不生成候选）：

| 例外 | 数量 | 处理 |
|---|---:|---|
| 端点悬空 | 28 条记录 / 29 个端点 | 台账 `connection_endpoint_missing` |
| 自环 | 1 | `ck_candidate_match_distinct_places` 不允许，跳过 |
| 重复（同有序对） | 21 条（9 条同三元组 + 12 条同对异类型） | 按 `(relation_type, place_id_a, place_id_b)` 合并 |

---

## 5. 代表点：本轮最关键的待决项

### 5.1 事实

- `historical_place` **没有任何坐标列**（已核对表结构）。
- 地图/搜索取点（`PlaceQueryService.PREFERRED_LOCATION`）只认 `historical_place_location` 的
  `representative_lon/lat`，且要求 `geom IS NOT NULL`、`crs_confidence <> 'unknown'`。
- v4.1 里 **3,317 个 NEW 地点有代表点（且 bbox），却没有任何 location 行**。

→ 不处理的话，这 3,317 个地点入库后**在地图上完全不可见**（名称搜索仍可用）。

### 5.2 两个方案

| | A1 · 不合成 | **A2 · 合成（推荐）** |
|---|---|---|
| 做法 | 只导 32,374 条真实 location 行 | 额外把 3,317 个代表点写成 `geom_type='Point'` 的位置行 |
| 位置行 | 32,374 | **35,691** |
| source_record 增量 | 124,512 | **127,829** |
| source_record 总量 | 153,903 | **157,220** |
| 可见性 | 3,317 个地点不可见 | 除 7,200 个真无坐标者外全部可见 |

A2 不是"造点"：坐标取自 `places.csv` 自己的 `representative_longitude/latitude`，是**源数据声明的代表点**。
写入时带完整出处：`notes`、独立源记录、`raw_file='places.csv'`、`raw_record_index`。

### 5.3 A2 的字段取值

| 字段 | 值 |
|---|---|
| `geom` / `geom_type` | `POINT(lon lat)` / `Point` |
| `representative_lon/lat` | 同坐标 |
| `original_x / original_y` | CSV 原文字符串 |
| `original_crs` / `crs_confidence` / `axis_order_verified` | `EPSG:4326` / `confirmed` / `true` |
| `location_precision` | 源值：**2,589 precise / 728 rough** |
| `uncertainty_m` | `places_accuracy.min_accuracy_meters` 为正时取整（5–9,310 m）；`-1` → NULL + 台账 |
| `time_bound_type` | `unknown` |
| 源记录 | `record_scope='location'`、`external_id='<pid>-representative'`、`parent_external_id=<pid>`、`raw_file='places.csv'` |

> **未冻结**：位置总数与 source_record 总数取决于 Owner 选 A1 还是 A2，其余指标不受影响。

---

## 6. 几何承载

| 类型 | 数量（A2） | `geom` | 代表点来源 |
|---|---:|---|---|
| Point | 26,684 | `POINT(x y)` | 自身（23,367 真实点 + 3,317 代表点） |
| Polygon | 4,114 | WKT 原样；无效者先修 | `ST_PointOnSurface`（保证落在面内） |
| LineString | 4,893 | WKT 原样 | `ST_LineInterpolatePoint(geom, 0.5)` |

- 插入顺序固定 **点 → 线 → 面**，让 `ORDER BY location_id LIMIT 1` 优先取到精确点。
- 面/线必须补 `representative_lon/lat`，否则地图不显示。
- 无效面整包 5 条、NEW **4** 条：`ST_MakeValid` → `ST_CollectionExtract(...,3)`；若得 `MultiPolygon`（值域已允许）
  则按 `MultiPolygon` 写；仍为空则整行不入库并记账。原始 WKT 留在 `raw_payload`。
- `is_preferred`：每地点第一条点行置 `true`（当前查询未用，为后续留口）。

---

## 7. 精度：两级分开，只算 NEW

### A 级 · 地点级（来自 `places.csv.location_precision`）

| 范围 | precise | rough |
|---|---:|---:|
| 整包 | 29,396 | 12,084 |
| **NEW** | **27,418** | **11,510** |

说明：`historical_place` **没有**精度列，地点级精度只在子行与 `places_accuracy` 中体现，
因此不单独入库，只在验收时按子行分布核对。

### B 级 · 位置级（`historical_place_location.location_precision`）

| 几何 | 新增 | precise | rough | `accuracy_radius` 有值 / 空 |
|---|---:|---:|---:|---:|
| Point（真实） | 23,367 | 23,367 | 0 | 23,366 / 1 |
| Point（代表点合成，A2） | 3,317 | 2,589 | 728 | 2,589 / 728 |
| Polygon | 4,114 | 374 | 3,740 | 441 / 3,673 |
| LineString | 4,893 | 4,893 | 0 | 4,893 / 0 |
| **合计（A2）** | **35,691** | 31,223 | 4,468 | 31,289 / 4,402 |

**硬约束**：不得像现库那样把非 `precise` 一律写 `unknown`（现库 16,399 条位置因此全成 `unknown`）。
本方案要求源值直传（`ck_hpl_location_precision` 已允许 `precise/approximate/rough/unknown`）。

---

## 8. 时间

| 源 | 落库 |
|---|---|
| `year_after_which`（TPQ，无公元 0） | → `valid_from_year_astro`，`source_beg_rule` 记原文 |
| `year_before_which`（TAQ） | → `valid_to_year_astro`，`source_end_rule` 记原文 |
| 两端有 | `tpq_taq`；地点级 `derived_tpq_taq`（子行包络） |
| 单端 | `tpq_taq` + 另一侧 NULL |
| 都无 | `unknown` |

- NEW 无时间：名称 **2,986** / 位置 **1,977** / 地点（无任何带时间子行）**2,583**。
- 倒挂 0，无需"不交换只标记"分支。
- 地点级时间只能由子行聚合，不得上提覆盖。

---

## 9. 追溯

`row → source_record_id → (dataset_id, raw_file, raw_record_index) → raw_payload → content_hash → first/last_batch_id`

- 归一化产物另存 `code/data/staging_m4_3/`（**不覆盖** `code/data/staging`）。
- `uri` 只在 `raw_payload`（不加列，见 V9 文档 §八）。

---

## 10. 跨源候选（只出候选，不合并）

| 对比 | ≤1 km | ≤10 km | ≤50 km | 处理 |
|---|---:|---:|---:|---|
| CHGIS（县/府） | 0 | 0 | 各 1 | 忽略（地理不相交） |
| MCGD | 1 | 2 | 43 | 写候选，人工裁决 |
| WHG 样本 | 36 | 525 | 704 | 优先处理 ≤1 km 的 36 条 |

- 名称匹配仅 3 对（跨文字系统），**不作判据**。
- `connections.same_as`（68 条）也不作合并依据。

---

## 11. 人工保护

`created_by='manual'` / `locked` / `manual_edited_fields` 三档沿用；地点级计数必须用独立的
`cnt_place_blocked`，**不得**复用源记录级 `cnt_blocked`（M4-2 曾因此触发 G1 恒等式失败）。
导入前后核对：人工地点计数不变、`updated_at` 不变。

---

## 12. 文件承载（详见 `M4_3_FILE_BEARING_MATRIX.md`）

| 分类 | 数量 | 文件 |
|---|---:|---|
| 入库 | 6 | places、names、location_points/polygons/linestrings、connections |
| 派生 | 2 | places_accuracy（精度 + uncertainty 来源）、places_place_types（汇总文本） |
| 仅源记录承载 | 3 | archaeological_remains、transcription_accuracy、transcription_completeness |
| 仅归档 | 8 | place_types、connection_types、languages_and_scripts、name_types、association_certainty、time_periods、README、howto |

**必须让 Owner 看到的边界**：类型多值（48,030 行）、考古遗迹（32,374 行）、名称原文（10,297 条）
本轮只做到"可追溯"，**不可查询**。

---

## 13. 验收指标（重建）

### 13.1 可冻结（数值由本轮实测确定）

| # | 指标 | 期望 | 来源 |
|---|---|---|---|
| 1 | `historical_place` 净增 | **38,928** | `import_counts.json` |
| 2 | `(dataset, grain_key)` 唯一 | 38,928 | `uq_historical_place_c04` |
| 3 | `historical_place_name` 净增 | **37,055** | 同上 |
| 4 | `historical_place_location` 净增 | 32,374（A1）/ **35,691（A2）** | 待定 |
| 5 | 几何拆分 | Point 23,367（A1）/ 26,684（A2）；Polygon 4,114；LineString 4,893 | 同上 |
| 6 | `source_record` 净增 | 124,512（A1）/ **127,829（A2）** | 同上 |
| 7 | `candidate_match` 净增 | **13,553** | 有序对去重 |
| 8 | inactive 重叠记录 | **2,552** | `inactive_reason='superseded_by_newer_snapshot'` |
| 9 | 位置级精度分布 | precise 28,634（A1）/ 31,223（A2）；rough 3,740 / 4,468 | §7 |
| 10 | `geom` 非空率 | 100% | 逐行构造 |
| 11 | 面/线 `representative_lon/lat` 非空 | 100% | `ST_PointOnSurface` / 线中点 |
| 12 | 人工地点计数与 `updated_at` | 不变 | 导入前后各查一次 |
| 13 | 幂等 | 第二轮增量全 0（`last_batch_id` 按设计推进） | 两轮对比 |
| 14 | 正式库 | 全程 V5、行数不变 | 开工/收工各查一次 |

### 13.2 须在 M4-4a 实测后才能冻结（**不得现在写死**）

| # | 指标 | 为什么不能冻结 |
|---|---|---|
| 15 | `data_quality_issue` 净增 | "归一化产出"部分（`missing_coordinate` / `unknown_time_bound_type` / `empty_name` / `year_out_of_range` / `beg_*`）取决于 normalize 实际判定 |
| 16 | `duplicate_external_id` / `derived_value_mismatch` / `manual_edit_conflict` | 导入器运行期合成，取决于多行组与地点级包络 |
| 17 | 台账类型总数 | 若 15/16 出现 0 行，类型数会少几个 |

### 13.3 台账可预测部分（"预估下界"，不是验收值）

| 类型 | 预估 | 依据 |
|---|---:|---|
| `missing_coordinate` | ≥7,200 | 7,200 个地点无代表点；位置行无缺几何者 |
| `unknown_time_bound_type` | ≥7,546 | 名称 2,986 + 位置 1,977 + 地点 2,583 |
| `connection_endpoint_missing` | 28 | 悬空连接记录 |
| `geometry_invalid_repaired` | 4 | NEW 里无效多边形 |
| `accuracy_unknown_sentinel` | 728 | 代表点合成行里的 `-1` |
| `place_without_geometry` | 7,200 | 口径③；**建议不写入**（与 `missing_coordinate` 重复计数），只作验收查询 |

> 下界只能当下界：归一化可能对同一行开多条台账，也可能因规则细节少开。
> M4-4a 跑完归一化后，以 `staging_m4_3/data_quality_issues.csv` 实际行数为准重新冻结。

### 13.4 地图 / 搜索 / 详情（E2E）

| 场景 | 判据 |
|---|---|
| 罗马 bbox | 出现 Polygon/LineString 来源地点，HTTP 200，`geom_type` 正确 |
| 雅典/庞贝搜索 | 按名称命中；详情页多条位置，精度不一刀切为 `unknown` |
| 无坐标地点 | 搜索命中（名称），地图不出现（预期，不报错） |
| 面/线地点 | 地图出现代表点；点击开详情不因 `geom_type != Point` 报错 |
| 时间轴 | 抽样 10 个新地点落在正确时段列 |

---

## 14. V9（详见 `M4_3_V9_REVISION.md`）

- `ck_hpl_geom_type` 增加 `LineString`；
- `ck_data_quality_issue_issue_type` 增加 4 值；
- 只在**隔离测试库**执行；建议新建 `canvas_history_m4_3`，不复用 `_m2check`。

---

## 15. 风险

| # | 风险 | 缓解 |
|---|---|---|
| 1 | 整包覆盖导致 104 个地点退化 | SKIP 规则 + 导入前快照对比 |
| 2 | 3,317 个代表点未合成 → 地点不可见 | 选 A2；指标 #4/#5 卡死 |
| 3 | 精度被压成 unknown | 源值直传 + 指标 #9 卡死 |
| 4 | `connects_to` 未归一 → 假孤儿 | 单测 + 指标 #7 |
| 5 | `ST_MakeValid` 产出集合体 | `ST_CollectionExtract(...,3)` + 失败跳过并记账 |
| 6 | 插入顺序错 → 代表点取到粗框质心 | 固定 点→线→面 |
| 7 | 台账行数无法预先冻结 | 指标 15–17 明确标"须实测" |
| 8 | 测试库混入既有基线 | 新建 `canvas_history_m4_3` |

---

## 16. 阶段划分

| 阶段 | 内容 | 出口 |
|---|---|---|
| M4-4a | 写 V9 + 3 处脚本改造 + 归一化到 `staging_m4_3/` | 7 张 CSV + **冻结台账实际行数** |
| M4-4b | 隔离库 V9 → 空库完整导入 → 幂等复跑 | 13.1 全部指标 + 13.2 实测值 |
| M4-4c | 地图/搜索/详情 E2E + 人工保护 + M0–M3 回归 | E2E 报告 |
| M4-5 | 正式库（需单独授权） | — |

---

## 17. 待决事项（3 项）

| # | 事项 | 选项 | 影响 |
|---|---|---|---|
| 1 | 代表点合成 | **A2（推荐）** / A1 | 位置 +3,317、source_record +3,317；3,317 个地点能否上图 |
| 2 | `attested_form` 是否补成名称行 | 不补（推荐）/ 补 | 名称 +10,297、source_record +10,297 |
| 3 | `place_without_geometry` 是否写台账 | 不写、只作验收查询（推荐）/ 写 7,200 行 | 台账总量 ±7,200 |

---

**M4-3 R1 — IMPORT PLAN REVISED / AWAITING OWNER DECISION ON 3 ITEMS**
