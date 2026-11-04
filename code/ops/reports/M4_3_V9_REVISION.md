# M4-3 R1 · V9 Migration 修订说明（只设计，不执行）

日期：2026-11-04
状态：**设计稿**。本轮未执行、未在正式库或测试库应用任何 Migration。
授权范围：Owner 已批准 V9，但**仅允许在隔离测试数据库执行**；正式库 `canvas_history` 维持 V5。

---

## 一、V9 要做两件事

| # | 变更 | 为什么必须 |
|---|---|---|
| 1 | `historical_place_location.geom_type` 值域增加 `LineString` | 5,265 条线（本轮新增 4,893）无法入库：`ck_hpl_geom_type` 只允许 `Point / Polygon / MultiPolygon` |
| 2 | `data_quality_issue.issue_type` 值域增加 4 个值 | 本轮产生 4 类新事实，现有 20 个值里没有对应的合法类型 |

**不改**：列类型（`geom` 已是 `geometry(Geometry,4326)`，能存线）、索引、其他任何约束、任何表结构。

---

## 二、现状核对（实测，非推测）

```sql
-- 位置表
ck_hpl_geom_type:        CHECK (geom_type = ANY (ARRAY['Point','Polygon','MultiPolygon']))
ck_hpl_geom_matches_type:CHECK ((geom IS NULL) OR (st_geometrytype(geom) = ('ST_'::text || geom_type)))
ck_hpl_location_precision CHECK (location_precision = ANY (ARRAY['precise','approximate','rough','unknown']))
ck_hpl_c15:              CHECK ((geom IS NOT NULL) OR (record_status <> 'published'))
ck_hpl_c07:              UNIQUE (source_record_id) WHERE source_record_id IS NOT NULL

-- 台账表：20 个 issue_type（V8 后）
beg_gt_end, beg_eq_end, missing_coordinate, coordinate_out_of_range,
coordinate_outside_china_bbox, year_out_of_range, duplicate_external_id, duplicate_sysid,
unknown_crs, unknown_time_bound_type, nonstandard_field_name, empty_name,
parent_place_not_in_sample, truncated_slice_tail, cross_layer_coordinate_conflict,
manual_edit_conflict, import_row_error, derived_value_mismatch, rollback_conflict,
attribution_missing
```

关键点：

- `ck_hpl_geom_matches_type` 用 `'ST_' || geom_type` 与 `ST_GeometryType()` 比，**`LineString` 天然成立**
  （`ST_GeometryType('LINESTRING(...)')` = `ST_LineString`），所以只需放行值域，不用改这条约束。
- `ck_hpl_location_precision` 已含 `rough`，**不需要**为精度做任何改动。
- `ck_hpl_c15` 只要求 published 有几何；staging 允许 NULL，7,200 个无坐标地点可以正常入库。

---

## 三、几何值域：允许哪些值

| 值 | 本轮是否产生 | 说明 |
|---|---|---|
| `Point` | 是（26,684，含 3,317 条代表点） | 现有 |
| `Polygon` | 是（4,114） | 现有 |
| `MultiPolygon` | 可能（仅当 `ST_MakeValid` 把无效面拆成多面） | 现有 |
| **`LineString`** | **是（4,893）** | **新增** |
| `MultiLineString` | **否**（v4.1 线文件 100% 是 `LineString`，已逐行判定） | **不加**——不为没出现过的类型扩值域 |
| `GeometryCollection` | 否 | 禁止：`ST_MakeValid` 结果若为集合，用 `ST_CollectionExtract(...,3)` 取面，取不到就跳过并记账 |

---

## 四、四类新台账：精确数量与定义

| `issue_type` | 本轮数量 | 定义 | 数据来源 |
|---|---:|---|---|
| `geometry_invalid_repaired` | **4** | 源 WKT 的 `ST_IsValid=false`，入库前经 `ST_MakeValid` + `ST_CollectionExtract(...,3)` 修复成功 | `location_polygons.csv`；整包 5 条，其中 1 条属旧切片地点（本轮跳过） |
| `connection_endpoint_missing` | **28** | 连接的 `place_id` 或 `connects_to` 解析后不在 `places.csv` 中，**不生成候选关系** | `connections.csv`；29 个悬空端点分属 28 条记录（1 条两端都悬空） |
| `accuracy_unknown_sentinel` | **728** | `places_accuracy.min_accuracy_meters = -1`（"未知"哨兵），转 NULL，不得当米数 | 仅统计"有代表点但无 location 行"的 3,317 个地点中 728 个 rough 者 |
| `place_without_geometry` | **7,200** | 既无任何 location 行，也无代表点、无 bbox（口径③） | NEW 集合；不随是否合成代表点漂移 |

### 4.1 为什么 `accuracy_unknown_sentinel` 只有 728，不是 11,438

`places_accuracy.csv` 里 NEW 集合有 11,438 行是 `-1`。但本方案**不整表导入**该文件，只把
`min_accuracy_meters` 用作"代表点合成行"的 `uncertainty_m` 来源。而这 3,317 个地点中：

- 2,589 个 precise → 值为正（5–9,310 m，中位 930 m）→ 直接写 `uncertainty_m`
- 728 个 rough → 值为 `-1` → 写 NULL + 记 728 条台账

其余 10,710 条 `-1` 不对应任何入库字段，因此**不产生台账行**（若将来导入 `places_accuracy` 整表，
再按新的口径重算，不得沿用 728 这个数）。

### 4.2 为什么 `place_without_geometry` 是 7,200，不是 7,509 或 10,517

| 定义 | 整包 | NEW |
|---|---:|---:|
| 无 location 行 | 10,974 | 10,517 |
| 无代表点 | 7,509 | 7,200 |
| **无 location 行且无代表点且无 bbox（采用）** | **7,509** | **7,200** |

用口径③的理由：它在"合成代表点 / 不合成"两种方案下都是 7,200，不会因实现选择而变；语义也最干净
（"这个地点没有任何坐标线索"）。7,509 是整包数字，10,517 是"NEW 里没有 location 行"的数字，
两者都**不得**直接写进验收指标。

---

## 五、Migration 内容（设计稿）

文件名：`V9__geometry_linestring_and_issue_types.sql`

```sql
-- M4-3 / R1：放行 LineString 几何，并补齐四类新台账类型。
-- 只改两个 CHECK 值域；不改列类型、不改索引、不改其他约束、不动任何数据。

BEGIN;

-- 1) 几何类型：Point / Polygon / MultiPolygon → + LineString
ALTER TABLE historical_place_location
    DROP CONSTRAINT ck_hpl_geom_type;

ALTER TABLE historical_place_location
    ADD CONSTRAINT ck_hpl_geom_type
    CHECK (geom_type = ANY (ARRAY['Point', 'Polygon', 'MultiPolygon', 'LineString']));

-- 2) 台账类型：20 → 24
ALTER TABLE data_quality_issue
    DROP CONSTRAINT ck_data_quality_issue_issue_type;

ALTER TABLE data_quality_issue
    ADD CONSTRAINT ck_data_quality_issue_issue_type
    CHECK (issue_type = ANY (ARRAY[
        'beg_gt_end', 'beg_eq_end', 'missing_coordinate', 'coordinate_out_of_range',
        'coordinate_outside_china_bbox', 'year_out_of_range', 'duplicate_external_id',
        'duplicate_sysid', 'unknown_crs', 'unknown_time_bound_type', 'nonstandard_field_name',
        'empty_name', 'parent_place_not_in_sample', 'truncated_slice_tail',
        'cross_layer_coordinate_conflict', 'manual_edit_conflict', 'import_row_error',
        'derived_value_mismatch', 'rollback_conflict', 'attribution_missing',
        -- M4-3 新增
        'geometry_invalid_repaired', 'connection_endpoint_missing',
        'accuracy_unknown_sentinel', 'place_without_geometry'
    ]));

COMMIT;
```

### 5.1 为什么不用 `NOT VALID` + `VALIDATE`

`NOT VALID` 用于"加约束但不校验存量"，适合大表。这里两张表分别是 1.8 万与 1.3 万行，
`CHECK` 重新校验是秒级；用一次性 `ADD CONSTRAINT` 更简单，也避免留下"未校验"的中间态。
**如果 M4-4 导入后表已到 5 万行仍感觉慢，再改 `NOT VALID` 不迟。**

### 5.2 锁与影响

- `ALTER TABLE ... DROP/ADD CONSTRAINT` 取 `ACCESS EXCLUSIVE`，表小、耗时毫秒级。
- 不重写表（只改约束定义）。
- 不改 `geom` 列，不触碰 PostGIS 索引。

---

## 六、执行前后的校验 SQL

### 6.1 执行前（确认现状与预期一致）

```sql
-- 现有几何类型分布：应只有 Point
SELECT geom_type, count(*) FROM historical_place_location GROUP BY 1 ORDER BY 2 DESC;

-- 现有台账类型数：应为 20
SELECT count(DISTINCT issue_type) FROM data_quality_issue;

-- 约束原文
SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint
 WHERE conname IN ('ck_hpl_geom_type','ck_data_quality_issue_issue_type');
```

### 6.2 执行后（应全部通过）

```sql
-- 1) 两个约束已含新值
SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname='ck_hpl_geom_type';
--    期望包含 'LineString'
SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname='ck_data_quality_issue_issue_type';
--    期望包含 'geometry_invalid_repaired' 等 4 个

-- 2) 存量数据未变（执行前后 count 必须相等）
SELECT count(*) AS locations FROM historical_place_location;
SELECT count(*) AS issues FROM data_quality_issue;

-- 3) 没有越界值混入
SELECT count(*) FROM historical_place_location
 WHERE geom_type NOT IN ('Point','Polygon','MultiPolygon','LineString');
--    期望 0

-- 4) 一致性约束仍成立（几何与类型匹配）
SELECT count(*) FROM historical_place_location
 WHERE geom IS NOT NULL AND st_geometrytype(geom) <> ('ST_' || geom_type);
--    期望 0
```

### 6.3 回滚

```sql
-- 前提：表中不存在 geom_type='LineString' 的行（若已导入，先处理数据再回滚）
BEGIN;
ALTER TABLE historical_place_location DROP CONSTRAINT ck_hpl_geom_type;
ALTER TABLE historical_place_location ADD CONSTRAINT ck_hpl_geom_type
  CHECK (geom_type = ANY (ARRAY['Point','Polygon','MultiPolygon']));
ALTER TABLE data_quality_issue DROP CONSTRAINT ck_data_quality_issue_issue_type;
ALTER TABLE data_quality_issue ADD CONSTRAINT ck_data_quality_issue_issue_type
  CHECK (issue_type = ANY (ARRAY[ ... 原 20 值 ... ]));
COMMIT;
```

回滚前必须确认：`SELECT count(*) FROM historical_place_location WHERE geom_type='LineString'` = 0，
且台账中不存在 4 个新类型；否则会因存量违规而失败——这是**正确**的失败，不能强推。

---

## 七、执行边界（本轮与下一轮）

| 项 | 本轮（R1） | M4-4 |
|---|---|---|
| 写 V9 文件 | **不写**（本文只是设计稿） | 写入 `db/migration/V9__…sql` |
| 在测试库执行 | **不执行** | 在**隔离测试库**执行（建议新建 `canvas_history_m4_3`，不复用 `_m2check`） |
| 在正式库执行 | **永不** | 需单独授权 |
| 校验 SQL | 只写好备用 | 执行后逐条跑，结果入报告 |

> 建议 M4-4 新建独立测试库 `canvas_history_m4_3` 而不是复用 `canvas_history_m2check`：
> 后者已有 M3 演示数据与 M4-2 的 12,833 台账基线，混入 Pleiades 全量后
> "行数验收"会与既有基线纠缠。独立库可以干净地跑"空库 → V9 → 完整导入 → 核验"。

---

## 八、V9 之外的模型问题（本轮不解决，登记在案）

| # | 问题 | 现状 | 建议 |
|---|---|---|---|
| 1 | `place_type` 只有 5 值 | `places_place_types` 48,030 行无表可落 | 类型串进 `place_type_basis_note`；需要按类型筛选时再建关联表 |
| 2 | 名称无 `attested_form` 列 | 10,297 条原文只在 raw_payload | 见承载矩阵待决 1 |
| 3 | 位置无 `archaeological_remains` 列 | 32,374 行只在 raw_payload | 与 1 同类：需要筛选时再扩 |
| 4 | 无 `accuracy_m` 语义列 | `uncertainty_m` 已够用 | 不新增 |
| 5 | `source_record` 无 `external_uri` | `uri` 只在 raw_payload | 可选；不加也能追溯 |
