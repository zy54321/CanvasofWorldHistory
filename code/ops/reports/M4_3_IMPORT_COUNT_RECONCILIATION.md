# M4-3 R1 · 导入数量重新核算报告

日期：2026-11-04
依据：`code/ops/m4-3/import_counts.py` 的实测输出 `code/ops/m4-3/import_counts.json`
边界：只读。未写任何库、未执行 Migration、未改 staging、未改原始数据。

> 本报告推翻了 R0 方案里的三类数字：① `overlap` 曾恒为 0（把 `new ∩ slice` 当重叠，正确应为 `all ∩ slice`）；
> ② 自环/悬空口径把"侧数"当"记录数"；③ 精度直接用了整包分布，没有按 NEW 集合过滤。
> 以下全部为重新计算结果。

---

## 一、集合

| 项 | 数值 | 说明 |
|---|---:|---|
| v4.1 地点总数 | 41,480 | `places.csv` 行数 |
| 现库切片地点（`pleiades_gis_4_1_slice`，place 作用域，active） | 2,643 | 来自 `source_records.csv` |
| 交集（同源重叠） | **2,552** | 两边都有 |
| 仅切片有 | **91** | v4.1 没有（快照更新造成） |
| **NEW（v4.1 有、库中无）** | **38,928** | 41,480 − 2,552 |

校验：38,928 + 2,552 = 41,480 ✓；2,643 − 2,552 = 91 ✓

---

## 二、source_record 增量

| 组成 | 数量 | 依据 |
|---|---:|---|
| 新地点（place 作用域） | 38,928 | NEW 集合 |
| 新名称（name 作用域） | 37,055 | `names.csv` 中父地点 ∈ NEW 的行 |
| 新位置（location 作用域，仅三个 location 文件） | 32,374 | 点 23,367 + 面 4,114 + 线 4,893 |
| 连接（connection 作用域） | **13,603** | **全部保留源记录**，含 28 条悬空、1 条自环、9 条重复三元组 |
| 重叠地点 inactive 记录 | **2,552** | `is_active=false`，`inactive_reason='superseded_by_newer_snapshot'` |
| **合计** | **124,512** | 与 Owner 给定算式逐项一致 |

`29,391 + 124,512 = 153,903`

> 与 R0 的差异：R0 写 121,931（漏了 2,552 条 inactive 记录，且连接按 13,574 计）。现更正为 124,512 / 153,903。

**连接为什么 13,603 全留源记录**：导入器的 `_build_connection` 对每一行都产出 `ExtraRecord`，
源记录写入不以"两端可解析"为前提——现库台账里 `parent_place_not_in_sample` 有 4,810 行（其中 1,549 是连接）
就是证据：不可关联的连接**仍然**有源记录。所以源记录按 13,603 计。

---

## 三、连接与候选关系（两者分开核算）

| 分类 | 记录数 | 说明 |
|---|---:|---|
| `connections.csv` 总行数 | 13,603 | — |
| 两端都可解析（且非自环） | **13,574** | 进入候选计算 |
| └ 两端都在 NEW | 11,843 | 纯新对 |
| └ 一端 NEW、一端旧切片（走别名） | 1,358 | 需 §3.3 别名映射 |
| └ 两端都在旧切片 | 373 | 仍可映射到既有 `place_id` |
| 自环（两端同点） | **1** | 保留源记录，不生成候选 |
| 端点悬空 | **28 条记录 / 29 个端点** | 其中 1 条两端都悬空（= 29 侧 / 28 记录） |

候选去重（按实际约束 `uq_candidate_match_c09 UNIQUE (relation_type, place_id_a, place_id_b)`）：

| 步骤 | 数量 |
|---|---:|
| 可解析非自环记录 | 13,574 |
| 减去"同一有序对"重复（21 条，来自不同 `connection_type` 或完全重复） | −21 |
| **最终候选行** | **13,553** |

说明：

- 导入器的 C09 收敛键是 `(relation_type, place_id_a, place_id_b)`，**与 `connection_type` 无关**，
  因此 9 条"同三元组重复"里的 9 条会全部被并进同一对；另有 12 条是同对但不同类型，也一并合并 →
  共减 21 条。
- `ck_candidate_match_distinct_places` 要求 `place_id_a <> place_id_b`，所以自环 1 条**不可能**入库。
- 候选写入后按现有规则把 `pleiades_connection` 改写为 `status='confirmed'`、
  `reviewer='system:source_attested'`（满足 `ck_candidate_match_confirmed_edge_reviewer`）。

**结论：`candidate_match` 增量 = 13,553，不是 13,572，也不是 13,603。**
（53,131 + 13,553 = **66,684**）

---

## 四、两级精度（只统计 NEW 集合）

### 4.1 A 级：`historical_place`（地点级，来自 `places.csv.location_precision`）

| 范围 | precise | rough | 合计 |
|---|---:|---:|---:|
| 整包 41,480 | 29,396 | 12,084 | 41,480 |
| **NEW 38,928** | **27,418** | **11,510** | 38,928 |
| 切片 2,552（不导入） | 1,978 | 574 | 2,552 |

> R0 把 29,396 / 12,084 直接当成新增验收值，**错误**。正确值：**27,418 / 11,510**。

### 4.2 B 级：`historical_place_location`（位置级，三个文件各自）

| 几何 | 新增行 | precise | rough | accuracy_radius 有值 | NULL |
|---|---:|---:|---:|---:|---:|
| Point | 23,367 | 23,367 | 0 | 23,366 | 1 |
| Polygon | 4,114 | 374 | 3,740 | 441 | 3,673 |
| LineString | 4,893 | 4,893 | 0 | 4,893 | 0 |
| **合计** | **32,374** | 28,634 | 3,740 | 28,700 | 3,674 |

- `accuracy_radius` 里**没有** 0 值、也没有负值；只有"有值"与"空"。空 3,674 条集中在多边形（3,673）。
- R0 里说的"占位/哨兵"是 `places_accuracy.csv` 的 `max/min_accuracy_meters = -1`，不是位置表的 `accuracy_radius`。
  两处必须分开写，这与 Owner 指出的问题一致。

---

## 五、`-1` 哨兵的真实分布

| 范围 | 行数 |
|---|---:|
| `places_accuracy.csv` 总行数 | 41,480 |
| `max/min_accuracy_meters` 含 `-1` 的行（整包） | 12,007 |
| 上述中属于 NEW 集合 | **11,438** |
| 上述中属于"有代表点但无 location 行"的 3,317 个地点 | **728** |

为什么只关心 728：本方案**不导入 `places_accuracy` 整表**（见承载矩阵），只在为"有代表点但无 location 行"
的地点合成位置行时，用 `min_accuracy_meters` 填 `uncertainty_m`。这 3,317 个地点里：

- 2,589 个 precise → `min_accuracy_meters` 为正（5 – 9,310 m，中位 930 m），可直接作 `uncertainty_m`；
- **728 个 rough → `-1` 哨兵** → `uncertainty_m` 置 NULL，并记 728 条 `accuracy_unknown_sentinel`。

其余 10,710 条 NEW 的 `-1` 因为整表不入库，不产生台账行。

---

## 六、代表点覆盖（本轮新增的关键事实）

| 口径 | 整包 | NEW |
|---|---:|---:|
| 地点数 | 41,480 | 38,928 |
| 有代表点（`representative_latitude/longitude` 均非空） | 33,971 | **31,728** |
| 有 `bounding_box_wkt` | 33,971 | 31,728 |
| 有任意 location 行（点/线/面） | 30,506 | 28,411 |
| **有代表点、但没有任何 location 行** | 3,465 | **3,317** |
| 有 bbox、但没有任何 location 行 | 3,465 | 3,317 |
| 三者全无（无代表点、无 bbox、无 location） | 7,509 | **7,200** |
| 有 location 行、但无代表点 | 0 | 0 |

**这意味着什么：**

- `historical_place` **没有任何坐标列**（已核对表结构：只有 `canonical_name / place_type / …`，无 lon/lat）。
- 地图与搜索的取点逻辑（`PlaceQueryService.PREFERRED_LOCATION`）只从
  `historical_place_location` 取 `representative_lon/lat`，且要求 `geom IS NOT NULL`。
- 所以：**一个地点若只有 `places.csv` 的代表点而没有 location 行，它入库后在地图上完全不可见**（仍可被名称搜索到）。

→ 要么丢弃这 3,317 个坐标（Owner 已明确不允许），要么把它们落成位置行。

### 6.1 建议：把 3,317 个代表点落成"来源声明的代表点"位置行

不是"凭空造点"：坐标取自 v4.1 `places.csv` 自己的 `representative_longitude/latitude`，
是源数据声明的代表点，只是 v4.1 没有为它单独导出一条 `location_*` 记录。

| 字段 | 取值 |
|---|---|
| `geom` | `ST_SetSRID(ST_MakePoint(lon, lat), 4326)` |
| `geom_type` | `Point` |
| `representative_lon/lat` | 同坐标 |
| `original_x / original_y` | CSV 原文字符串（不重排） |
| `original_crs` | `EPSG:4326` |
| `crs_confidence` | `confirmed`（README 明确 WGS-84 十进制度） |
| `axis_order_verified` | `true`（列名已标明 lat/lon，非 WKT） |
| `location_precision` | 取 `places.csv` 的值（2,589 precise / 728 rough） |
| `uncertainty_m` | 取 `places_accuracy.min_accuracy_meters`（仅正数）；`-1` → NULL + 台账 |
| `time_bound_type` | `unknown`（这些地点无子行时间） |
| `notes` | `representative point declared by places.csv (no location_* row in v4.1)` |
| 源记录 | 新增一条 `record_scope='location'`、`external_id='<place_id>-representative'`、`parent_external_id=<place_id>`、`raw_file='places.csv'`、`raw_record_index=<行号>`、payload 保存该 place 整行 |

**对行数的影响（两套口径，必须由 Owner 选一个）：**

| 方案 | 位置行 | 位置合计 | source_record 增量 | source_record 总量 | 可见性 |
|---|---:|---:|---:|---:|---|
| **A1（最小）**：不合成 | 32,374 | 50,475 | 124,512 | 153,903 | 3,317 个地点不可见 |
| **A2（推荐）**：合成代表点 | **35,691** | **53,792** | **127,829** | **157,220** | 除 7,200 个真无坐标者外全部可见 |

A2 的几何拆分：Point 26,684（23,367 + 3,317）· Polygon 4,114 · LineString 4,893。
A2 多出的 3,317 条源记录同样计入 `data_quality_issue` 之外的正常来源链，不产生额外台账（provenance 写在 `notes`）。

---

## 七、"无几何"的三种口径（不得混用）

| 口径 | 定义 | 整包 | NEW | A1 后 | A2 后 |
|---|---|---:|---:|---:|---:|
| **① 无 location 行** | 三个 location 文件都没有它 | 10,974 | 10,517 | 10,517 | **7,200** |
| **② 无代表点** | `representative_lat/lon` 有空 | 7,509 | 7,200 | 7,200 | 7,200 |
| **③ 无任何几何信息**（= ①∩②） | 既无 location 行，也无代表点、无 bbox | 7,509 | **7,200** | 7,200 | 7,200 |

- **7,509 是整包数字，10,974 是"整包无 location 行"，两者不是一回事**（7,509 里全都没有 location；
  10,974 里还包含 3,465 个"有代表点但无 location"的）。
- NEW 集合对应值是 7,200 与 10,517。
- 台账 `place_without_geometry` 建议采用**口径 ③ = 7,200**：它在 A1/A2 下都稳定，且语义明确
  （"既没有位置行，也没有任何坐标线索"），不会随是否合成代表点而漂移。

---

## 八、其它可直接入库的字段覆盖（供承载矩阵引用）

| 项 | 数值 |
|---|---:|
| NEW 名称行 | 37,055 |
| └ 有 `association_certainty` | 37,055（100%，→ 列 `historical_place_name.association_certainty`） |
| └ 有 `romanized_form_1` | 37,055（100%，**无对应列**） |
| └ 有 `attested_form` | 10,297（**无对应列**） |
| NEW 位置行 | 32,374（A1） |
| └ 有 `archaeological_remains` | 32,374（100%，**无对应列**） |
| └ 有 `association_certainty` | 32,374（100%，**无对应列**） |
| NEW 地点类型行 | 48,030；覆盖 38,926 个地点（2 个地点无类型） |
| └ 其中含 `settlement` | 12,545 个地点 |
| 类型词表 | 192 键；被引用 206 键；**29 键未定义** |
| 语言词表 | 103 个代码；NEW 用到 87 种；3 个不在词表（`bn`、`egy-leidentr`、`si`） |
| 无效多边形（需修复） | 整包 5，NEW **4** |
| 连接类型（可导部分） | 39 种 |

---

## 九、可复核性

每个数字都能用一条命令复现：

```bash
cd code && PYTHONPATH=./ops/.deps python ops/m4-3/import_counts.py
# 输出 ops/m4-3/import_counts.json（本报告全部数字的机器可读版本）
```

脚本只读 `code/data/raw/pleiades_gis_4_1/gis/*.csv` 与 `code/data/staging/source_records.csv`，
不查数据库、不写任何文件（除 JSON 输出）。

---

## 十、与 R0 的差异清单

| 项 | R0 | R1 实测 | 原因 |
|---|---:|---:|---|
| source_record 增量 | 121,931 | **124,512** | 补 2,552 条 inactive 记录；连接按全量 13,603 |
| source_record 总量 | 151,322 | **153,903** | 同上 |
| candidate_match 增量 | 13,572 / 13,574 | **13,553** | 按 `uq_candidate_match_c09` 有序对去重 |
| 新增地点精度 | 29,396 / 12,084 | **27,418 / 11,510** | 未按 NEW 过滤 |
| 位置级精度 | 未分 | **precise 28,634 / rough 3,740** | 新算 |
| `-1` 哨兵 | 12,007（整包） | **11,438（NEW）/ 728（实际入账）** | 口径细化 |
| 代表点无 location | 未识别 | **3,317（NEW）** | 本轮新发现 |
| 无几何口径 | 7,509 与 10,974 混用 | **7,200（口径③）** | 定义分层 |
| 重叠地点 | 0（脚本 bug） | **2,552** | `new ∩ slice` → `all ∩ slice` |
