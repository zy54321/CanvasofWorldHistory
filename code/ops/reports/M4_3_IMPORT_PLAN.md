# M4-3 导入方案 · Pleiades GIS 4.1（`pleiades_gis_4_1`）

编制日期：2026-11-04
前置：`M4_3_PLEIADES_GIS_ACQUISITION_REPORT.md`（数据已下载并核验，41,480 地点全部核实）
**本文只是方案，未执行任何导入。数据库仍为 V5 / 测试库 V8。**

---

## 0. 原则

1. **增量补全，不整包覆盖。** 现库切片来自比 v4.1 更新的快照（87 个地点创建于 v4.1 发布后），整包覆盖会退化 104 个地点的值、丢掉 91 个地点。
2. **不降级。** 同一 Pleiades 地点若已有更新数据，v4.1 的值不得覆盖它；冲突逐条入账，不静默取胜。
3. **不合并、不推断。** `connections` 只是关联关系，不是同一地点的证据；同名 + 近距离只出候选。
4. **来源与授权不设门禁**（M4-2 决策延续）：`attribution` 只作字符串留痕，不参与任何判断。
5. **可追溯。** 每条入库行都能回到 `dataset → 文件 → 行号 → 原始 payload`。
6. **人工修改优先。** `created_by='manual'` / `locked` / `manual_edited_fields` 三档保护原样生效。

---

## 1. 数据集登记

| 字段 | 值 |
|---|---|
| `dataset_id` | `pleiades_gis_4_1`（新建，**不改** `pleiades_gis_4_1_slice`） |
| `source_id` | `pleiades` |
| `dataset_version` | `4.1` |
| `dataset_name` | `Pleiades Datasets v4.1 — GIS CSV` |
| `homepage` | `https://doi.org/10.5281/zenodo.15540082` |
| `record_count` | 41,480（place 作用域行数，与官方口径一致） |
| `local_path` | `code/data/raw/pleiades_gis_4_1/gis/` |
| `acquisition_method` | Zenodo fixed-version archive（`isawnyu/pleiades.datasets-v4.1.zip`，size 286,621,469，MD5 `ad339c92c6b895f0eb9a52228da498c4`） |
| `evidence` | `code/ops/m4-3/audit.json`（19 个文件逐一 SHA256 + 全部计数） |
| `notes` | 只提取 `data/gis/`；未用 latest 代替 v4.1 |

---

## 2. 候选策略比较

| 方案 | 做法 | 结果 | 评价 |
|---|---|---|---|
| **A · 增量补全（推荐）** | 新建 dataset；只导入 v4.1 有、库里没有的 38,928 个地点；已存在的 2,643 个保持原值并留痕 | 地点 +38,928 → 57,967；无重复 | 无数据退化、无合并决策、可回滚 |
| B · 整包重建 | 全量 41,480 建到新 dataset，旧切片 2,643 行标失效 | 地点 +41,480，但产生 2,643 组"同源双行" | 需 2,643 次合并裁决，违反"禁止自动合并"；且 104 个地点退化 |
| C · 原地扩写 | 把 v4.1 数据写进现有 `_slice` dataset | 单数据集、无重复 | 会改写既有验收基线（M4-2 的 12,833 口径失效），不可取 |

**推荐 A**，并额外建一张**同源别名表**（见 §3.3）用于把连接的旧快照端点接到既有 `place_id`，使 13,574 条连接中"一端是旧切片地点"的 1,730 条不丢。

---

## 3. 识别规则（新增 / 已存在 / 跳过）

### 3.1 地点键

- **稳定键用 `uri`**，导入时归一成尾段 id：`https://pleiades.stoa.org/places/433032` → `433032`。
- 落库唯一键沿用既有约束：`uq_historical_place_c04 (dataset_id, grain_key)`，`grain_key = 'pleiades:' || id`。
- `id` 只在各 CSV 内唯一，**不能**跨表当全局键（`names.id` 有 slug 形式，如 `gallia`）。

### 3.2 三分类判定

```
existing_alias = {uris/pids from source_record where dataset_id='pleiades_gis_4_1_slice'
                                    and record_scope='place' and is_active}
for each place in places.csv:
    if id in existing_alias:  → SKIP（skipped_same_source_newer_snapshot）
    else:                     → NEW
```

判定结果（本轮实测）：

| 分类 | 数量 |
|---|---:|
| NEW（v4.1 有、库中无） | **38,928** |
| SKIP（同源，库中版本更新或等值） | **2,552** |
| 库中有、v4.1 无（保持不动） | **91** |

SKIP 的 2,552 条**不静默丢弃**：为每条写一条 `source_record`，`is_active=false`、`inactive_reason='superseded_by_newer_snapshot'`，payload 保留 v4.1 原行。这样"v4.1 里也有这个地点"这件事可查、可复核，但不参与展示。

### 3.3 同源别名映射（供连接使用，不改动现有数据）

`source_record` 表**没有** `place_id` 列——`place` 行与 `historical_place` 行的对应关系由导入器内部的
`place_keys[(dataset, external_id)]` 维护，落库后只能通过"同批次 + 同 external_id"间接看出。
因此别名不建视图、不建表，**在导入器内存里构造**：

```python
# 导入器启动时（读取既有数据，不写库）
alias = {                        # pleiades place id -> 既有 historical_place.place_id
    ext: pid
    for (ds, ext), pid in existing_place_keys.items()
    if ds == 'pleiades_gis_4_1_slice'
}
# connections 两端解析顺序：先 new 集，再 alias
def resolve(pid: str) -> int | None:
    return new_place_ids.get(pid) or alias.get(pid)
```

这样：

- 13,574 条可导连接里，"一端是旧切片地点"的 **1,730 条**不会丢；
- 不新增表、不改现有数据、不需要 Migration；
- 别名只在本次导入进程内有效，导入结束即消失，不产生第二套真相。

> 若 Owner 希望别名长期可查（例如后续按 Pleiades id 反查），再考虑新增 `place_source_key(place_id, source_id, external_id)`——
> 属结构变更，需单独授权，本轮不做。

## 4. 名称、位置、连接的关联规则

| 对象 | 核心行 | 父键 | 关联方式 | 本轮导入量 |
|---|---|---|---:|---:|
| 地点 | `places.csv` | — | 自身即锚点 | 38,928 |
| 名称 | `names.csv` | `place_id` | 父地点在 NEW 集才导；孤儿（父不存在）直接入账不导 | 37,055 |
| 位置 | `location_points/polygons/linestrings.csv` | `place_id` | 同上 | 32,374（点 23,367 / 面 4,114 / 线 4,893） |
| 连接 | `connections.csv` | `place_id` + `connects_to`（URI） | 两端都必须能解析到 `place_id`（含别名） | 13,574（→ `candidate_match`） |

细节：

- **名称唯一性**：`uq_hpn_c08 (source_record_id, name_type, name_text, name_lang)`。v4.1 里 651 条"同地点同名同类"由不同 `id` 区分，因此各有自己的 `source_record`，不冲突。
- **语言**：`language_tag` 空 → `und`（23,221 条，59.8%）。有值的 90 种原样保留。
- **名称类型映射**：`geographic → primary`；`label / ethnic / associated_modern / undefined / unknown → alternate`（沿用 `pleiades_extract._NAME_TYPE_MAP`）。
- **连接**：两端解析不到时**不写入** `candidate_match`，改记 `connection_endpoint_missing`（29 条），源记录仍保留；自环 2 条丢弃并记账。
- **连接的 `connects_to` 必须归一**（去 `https://pleiades.stoa.org/places/` 前缀），否则会造 13,603 条假孤儿。

---

## 5. Polygon / LineString 的承载方案

### 5.1 结论：模型基本够用，只差一个值域

| 检查项 | 现状 | 结论 |
|---|---|---|
| `geom` 列类型 | `geometry(Geometry,4326)` | **通用类型，能存面与线** |
| `geom_type` 值域 | `Point / Polygon / MultiPolygon` | **缺 `LineString`** → 需 Migration |
| 一致性约束 | `st_geometrytype(geom) = 'ST_' || geom_type` | 命名兼容（`ST_LineString`） |
| 地图取点 | 取 `location_id` 最小的有效行，要求 `representative_lon/lat` 非空 | 面/线**必须补代表点**，否则上看不到 |

### 5.2 落库映射

| 源文件 | `geom_type` | `geom` | `representative_lon/lat` | `location_precision` |
|---|---|---|---|---|
| `location_points.csv` | `Point` | `POINT(x y)` | WKT 的 x/y | 源值（全部 `precise`） |
| `location_polygons.csv` | `Polygon` | WKT 原样（无效的先 `ST_MakeValid`） | **质心**（`ST_PointOnSurface`，保证落在面内） | 源值（rough 3,942 / precise 443） |
| `location_linestrings.csv` | `LineString` | WKT 原样 | **线上中点**（`ST_LineInterpolatePoint(geom, 0.5)`） | 源值（全部 `precise`） |

- 面/线的原始 WKT 必须整串保留在 `source_record.raw_payload`，**不允许"压缩成代表点后丢弃几何"**。
- 插入顺序固定 **点 → 线 → 面**，让地图的 `ORDER BY location_id LIMIT 1` 优先取到精确点，而不是粗框质心。
- `is_preferred`：每个地点把第一条**点**行置 `true`（当前查询未使用，但语义正确、为后续留口）。

### 5.3 无效几何处理

5 条 OGC 无效多边形（4 条 ring self-intersection + 1 条蝴蝶结）。规则：

```sql
geom = CASE WHEN ST_IsValid(g) THEN g
            ELSE ST_CollectionExtract(ST_MakeValid(g), 3) END
```

`ST_MakeValid` 可能返回 `GeometryCollection` 或 `MultiPolygon`：取 `ST_CollectionExtract(...,3)` 后若得到 `MultiPolygon`，`geom_type` 写 `MultiPolygon`（值域已允许）；仍为空则整行不入库、记 `geometry_invalid_repaired`。原始 WKT 保留在 `source_record`。

---

## 6. 多位置与精度

| 场景 | 处理 |
|---|---|
| 一个地点多个位置（3,588 个地点，最多 27 条） | 每条位置一行，全部入库；`uq_hpl_c07` 保证一条源记录一行 |
| 地图显示哪个点 | 按 `location_id` 最小（=先插入的点）；不需要新逻辑 |
| `location_precision` | **直接映射源值**：`precise → precise`、`rough → rough`。**不得**像现在这样把非 `precise` 一律写成 `unknown` |
| `accuracy_radius`（米） | → `uncertainty_m`（取整）；缺失留 NULL |
| `places_accuracy.max/min_accuracy_meters` 的 **−1 哨兵**（12,007 行） | **转 NULL**，并记 `accuracy_unknown_sentinel`；绝不把 −1 当米数 |
| `accuracy_assessment_uri` | 写入 `notes` 的来源串（可追溯），不新建列 |
| `places_accuracy.accuracy_hull`（80 MB） | **不入库**（PostGIS 可随时由位置重算）；只在 `raw_payload` 保留 |
| CRS | 全部 `original_crs='EPSG:4326'`、`crs_confidence='confirmed'`、`axis_order_verified=true`（WKT 的 X=经度，README 与样本一致） |

---

## 7. 时间字段转换

| 源字段 | 落库 |
|---|---|
| `year_after_which`（TPQ，无公元 0） | `parse_signed_year()` → `valid_from_year_astro`；`source_beg_rule` 记原文 |
| `year_before_which`（TAQ） | → `valid_to_year_astro`；`source_end_rule` 记原文 |
| 两端都有 | `time_bound_type='tpq_taq'`（子对象）/ `'derived_tpq_taq'`（地点级包络） |
| 只有一端 | `tpq_taq` + 单侧 NULL（现有 CHECK 允许） |
| 都没有 | `time_bound_type='unknown'` |
| 地点级 | **由 name+location 子行取包络**（min 起 / max 止），`places.csv` 自身无时间列；**不得**把子行时间上提覆盖地点 |

本轮已核验：名称/位置/连接 **TPQ > TAQ 倒挂 = 0**，因此不需要"倒挂不交换、只标记"的分支；但保留该检查以防未来快照。

`time_periods.csv`（204 行）作为**引用词表**入库到 `data_dataset` 之外的文件层面即可，不建业务表；与现有 220 行副本**不互相覆盖**，差异已记录在获取报告 §3.3。

---

## 8. 追溯关系

每条入库行都满足"三跳可回"：

```
historical_place / _name / _location / candidate_match
   → source_record_id
      → dataset_id='pleiades_gis_4_1'
      → raw_file='places.csv' / 'names.csv' / ...
      → raw_record_index=N
      → raw_payload（整行 JSON，含 uri / created / provenance）
      → content_hash（SHA256 of canonical payload）
      → first_batch_id / last_batch_id（批次可查）
```

- `external_id` = 源 `id`；`parent_external_id` = 子行的 `place_id`（地点行为空串）。
- 归一化产物另存一份 `code/data/staging_m4_3/`（**不覆盖** `code/data/staging`），其 7 张 CSV 与本次导入一一对应，便于逐行复核。
- 可选增强（**非必需**）：给 `source_record` 加 `external_uri text` 列，让 `uri` 可索引查询。属结构变更，需单独授权；不加也不影响追溯（在 `raw_payload` 里）。

---

## 9. 与 CHGIS / MCGD / WHG 的重复候选

只出候选，**一条都不合并**：

| 对比 | 实测候选 | 处理 |
|---|---|---|
| CHGIS ↔ Pleiades | 50 km 内各 1 例 | 忽略（地理不相交，非重复） |
| MCGD ↔ Pleiades | 1 km 内 1 · 10 km 内 2 · 50 km 内 43 | 写 `candidate_match(relation_type='cross_source_same_place_candidate', status='candidate')`，人工裁决 |
| WHG ↔ Pleiades | 1 km 内 36 · 10 km 内 525 · 50 km 内 704 | 同上，优先处理 ≤1 km 的 36 条 |
| 名称相等 | 仅 3 对（跨文字系统不可用） | **不作为判据**，只在 evidence 里附注 |

约束：

- `connections` 的 `same_as`（68 条）**也不能**当合并依据，只作候选证据。
- 任何自动合并都不在本轮授权内；候选表只写 `status='candidate'`。

---

## 10. 人工修改保护

沿用 M4-2 已验证的三档（`import_staging.write_places`）：

| 保护位 | 行为 |
|---|---|
| `created_by='manual'` | 该地点整体不覆盖，记 `manual_edit_conflict` |
| `locked=true` | 同上 |
| `manual_edited_fields` 非空 | 只保护列出的字段，其余字段可更新 |
| 未受保护 | 按内容哈希决定 UPDATE / NOOP |

本轮补充要求：

- 保护判定必须在"地点级"，且**不得**复用源记录级 `cnt_blocked`（M4-2 已踩过：会导致 G1 恒等式多 1 整批回滚）。地点级用独立的 `cnt_place_blocked`。
- 导入后必须复核：`SELECT count(*) FROM historical_place WHERE created_by='manual'` 与导入前一致，且这些行的 `updated_at` 不变。

---

## 11. 预期行数与验收指标

### 11.1 行数（方案 A，含别名映射）

| 表 | 导入前 | 增量 | 导入后 |
|---|---:|---:|---:|
| `source_record` | 29,391 | **+121,931** | **151,322** |
| `historical_place` | 19,039 | **+38,928** | **57,967** |
| `historical_place_name` | 47,499 | **+37,055** | **84,554** |
| `historical_place_location` | 18,101 | **+32,374** | **50,475** |
| `candidate_match` | 53,131 | **+13,574** | **66,705** |
| `import_batch` | 7 | +1 | 8 |

增量拆分：

```
source_record = 38,928(place) + 37,055(name) + 32,374(location) + 13,574(connection)
              = 121,931
location 明细  = 23,367(Point) + 4,893(LineString) + 4,114(Polygon) = 32,374
```

### 11.2 验收指标（必须全绿才算导入成功）

| # | 指标 | 期望 |
|---|---|---|
| 1 | `historical_place` 净增 | 38,928 |
| 2 | `historical_place_location` 按 `geom_type` | Point 23,367 / LineString 4,893 / Polygon 4,114 |
| 3 | `geom` 非空率（三条新几何） | Point 100% / LineString 100% / Polygon 100%（5 条先修复） |
| 4 | `representative_lon/lat` 非空（面/线） | 100%（否则不上图） |
| 5 | `location_precision` 分布 | precise 29,396 量级 / rough 12,084 量级（**不得全是 unknown**） |
| 6 | `source_record` 行数 | 151,322 ± 0 |
| 7 | 每个 `source_record` 的 `content_hash` | 与重算一致（V1 检查复用） |
| 8 | 孤儿 | `parent_place_not_in_sample` 新增 **0**；`connection_endpoint_missing` = 29 |
| 9 | 重复 | 同一 `(dataset, uri)` 仅 1 行；`uq_historical_place_c04` 无冲突 |
| 10 | 人工数据 | `created_by='manual'` 计数与 `updated_at` 不变 |
| 11 | 幂等 | 连跑两次，第二次数值全 0 增量（除 `last_batch_id` 按设计推进） |
| 12 | 地图 | `/api/v1/places/map` 在罗马/雅典 bbox 内出现 Polygon/LineString 来源地点，且不报错 |
| 13 | 搜索 | 按 `Pompeii` / `Athens` 命中，详情页显示多条位置且精度不是 unknown |
| 14 | 正式库 | 全程只读，V5 不变 |

---

## 12. 需要的 Migration 与代码改造（最小集）

### 12.1 Migration（**仅在测试库执行**）

| 版本 | 内容 | 理由 |
|---|---|---|
| `V9__geometry_linestring_and_issue_types.sql` | ① `ck_hpl_geom_type` 增加 `LineString`；② `ck_data_quality_issue_issue_type` 增加 4 个值：`geometry_invalid_repaired`、`connection_endpoint_missing`、`accuracy_unknown_sentinel`、`place_without_geometry` | 线无法入库；台账新事实没有合法类型 |
| ~~V10~~ | 暂不需要 | `external_uri` 可从 `raw_payload` 取 |

> 建议把 V9 与 M4-4 的导入放在同一轮，避免"迁移已上、数据未到"的中间态。

### 12.2 脚本改造（3 处，不重构）

| 文件 | 改动 | 规模 |
|---|---|---|
| `p0/wb-002-normalize/pleiades_extract.py` | ① 输入目录与文件表参数化（`SLICE_FILES` → `build_file_table(root)`）；② 新增 `parse_wkt_geometry()` 支持 `POINT/POLYGON/LINESTRING`（含 `Z`），返回 `(geom_type, wkt, rep_lon, rep_lat)`；③ `_build_location` 按文件给出 `geom_type` 与精度 | ~120 行 |
| `p0/wb-002-normalize/normalize.py` | ① `EXTRA_SOURCE_DATASETS` / `DATASET_ORDER` 增加 `pleiades_gis_4_1`；② `location_precision` 直传源值（`precise/rough`），不再写 `point`；③ 地点级时间包络不变 | ~40 行 |
| `ops/import_staging.py` | ① INSERT 带上 `geom`、`geom_type`（`ST_GeomFromText(wkt,4326)`），不再统一 `ST_MakePoint`；② `location_precision` 直传；③ 地点键加跨数据集别名映射；④ 输出目录参数化 | ~150 行 |

**WKT 解析不要引入 shapely**：归一化脚本现行零依赖、可离线复跑（M4-1 已证明），引入 shapely 会破坏这一点。多边形质心用"环上点的平均 + 落在面内校验"或直接交由 PostGIS 在 SQL 里算（推荐：SQL 侧 `ST_PointOnSurface`，Python 侧只解析几何类型与坐标串）。**shapely 仅用于本轮审计脚本，不进流水线**。

### 12.3 接口

无需新增接口。地图/搜索/详情都从现表读，`geom_type` 与精度已经是既有字段；`PlaceQueryService` 的 `ST_Intersects` 对 Point/Polygon/LineString 通用。

唯一要验证的是**详情页是否会因 `geom_type != 'Point'` 报错**（当前前端把 `crsConfidence`、`lon/lat` 直接展示，未依赖类型）——列入 M4-4 的 E2E。

---

## 13. 风险清单

| # | 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|---|
| 1 | 整包覆盖导致 104 个地点退化、91 个消失 | 中（若不用方案 A） | 数据正确性 | 强制 SKIP 规则 + 导入前快照对比 |
| 2 | 面/线未补代表点 → 上看不到 | 高（若漏做） | 地图少 4,114+4,893 个点 | 验收指标 #4 卡死 |
| 3 | `ST_MakeValid` 产出 GeometryCollection 违反 `geom_matches_type` | 中 | 该行入库失败 | `ST_CollectionExtract(...,3)` + 兜底跳过并记账 |
| 4 | 精度被压成 unknown（沿用旧映射） | 高（若不改） | 12,084 个 rough 全变 unknown，违反"不得把粗略当精确" | 验收指标 #5 卡死 |
| 5 | 连接 URI 未归一 → 13 万级假孤儿 | 中 | 台账爆炸 | 单测 + 指标 #8 |
| 6 | 导入顺序错（面先于点）→ 代表点取到粗框质心 | 中 | 位置展示偏差数百米 | 固定 点→线→面 顺序 |
| 7 | 7,509 个无几何地点被误判为"导入失败" | 中 | 误报 | 台账 `place_without_geometry`，不算失败 |
| 8 | 10,974 个地点无位置 → 地图看不到 | 高（客观） | 观感 | 明确说明：这是源数据事实，不是缺陷 |
| 9 | `place_types` 29 个键未定义 | 中 | 类型标签退化 | 字典取旧词表 ∪ v4.1，缺的回退 key |
| 10 | 迁移锁表 | 低 | 短暂阻塞 | 表仅 1.8 万→5 万行，秒级 |

---

## 14. 工作量与阶段划分（建议）

| 阶段 | 内容 | 产出 |
|---|---|---|
| M4-4a | V9 迁移（测试库） + 3 处脚本改造 + 归一化预览（输出到 `staging_m4_3/`） | 7 张 CSV，行数与 §11.1 对齐 |
| M4-4b | 测试库完整导入 + 幂等复跑 + 14 项验收指标 | 导入日志、核对表 |
| M4-4c | 地图/搜索/详情 E2E（含面/线渲染）+ 人工保护回归 + M0–M3 回归 | E2E 报告 |
| M4-5 | 正式库迁移 + 导入（需单独授权） | 正式数据 |

预计：M4-4a 1 轮、M4-4b 1 轮、M4-4c 1 轮；风险主要在脚本改造（WKT 与几何类型）与"不降级"规则的实现。

---

## 15. 待 Owner 决策（3 项）

1. **是否采纳方案 A（增量）**，以及"91 个库中有、v4.1 无"的地点是否需要在 M4-4 里补做一次同源核对（它们来自更新的快照，v4.1 没有，属正常）。
2. **是否为 SKIP 的 2,552 条写 `is_active=false` 的 source_record**（推荐：写，可追溯；不写则"v4.1 也有这些地点"不可查）。
3. **是否允许 V9 迁移**（`LineString` + 4 个台账类型）。不迁移就只能导点与面，5,265 条线无法入库。

---

**M4-3 — DATA ACQUISITION & AUDIT COMPLETED / READY FOR IMPORT PLAN ACCEPTANCE**
