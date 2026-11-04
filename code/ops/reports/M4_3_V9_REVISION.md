# M4-3 R1.1 · V9 Migration 最终设计稿（只设计，不执行）

日期：2026-11-04
状态：**设计稿**。本轮未写迁移文件、未执行、未在正式库或测试库应用任何 Migration。
授权：Owner 已批准 V9，**仅允许在隔离测试数据库执行**；正式库 `canvas_history` 维持 V5。

---

## 一、V9 只做两件事

| # | 变更 | 为什么必须 |
|---|---|---|
| 1 | `historical_place_location.geom_type` 值域增加 `LineString` | 4,893 条线无法入库：现值域只允许 `Point / Polygon / MultiPolygon` |
| 2 | `data_quality_issue.issue_type` 值域增加 **3** 个值 | 本轮产生 3 类新事实，现有 20 个值里没有合法类型 |

**不改**：列类型（`geom` 已是 `geometry(Geometry,4326)`）、索引、其他约束、任何表结构、任何数据。

### 1.1 `place_without_geometry` 已从 V9 移除

R1 曾把它列为第 4 个新值。**OWNER 已确认：该指标不写入质量台账**，7,200 作为独立验收指标用 SQL 查询验证。
因此：

- `ck_data_quality_issue_issue_type` **不**增加该值（保持 23 种，不是 24 种）；
- 验收侧保留 `place_without_geometry` 的 SQL 查询（见 §六）；
- 理由：7,200 个地点已经各自有一条 `missing_coordinate`，再写 7,200 行是同一事实的重复登记。

---

## 二、现状核对（实测）

```sql
ck_hpl_geom_type:        CHECK (geom_type = ANY (ARRAY['Point','Polygon','MultiPolygon']))
ck_hpl_geom_matches_type:CHECK ((geom IS NULL) OR (st_geometrytype(geom) = ('ST_'::text || geom_type)))
ck_hpl_location_precision CHECK (location_precision = ANY (ARRAY['precise','approximate','rough','unknown']))
ck_hpl_c15:              CHECK ((geom IS NOT NULL) OR (record_status <> 'published'))
ck_hpl_c07:              UNIQUE (source_record_id) WHERE source_record_id IS NOT NULL

-- 台账：20 种（V8 之后）
beg_gt_end, beg_eq_end, missing_coordinate, coordinate_out_of_range,
coordinate_outside_china_bbox, year_out_of_range, duplicate_external_id, duplicate_sysid,
unknown_crs, unknown_time_bound_type, nonstandard_field_name, empty_name,
parent_place_not_in_sample, truncated_slice_tail, cross_layer_coordinate_conflict,
manual_edit_conflict, import_row_error, derived_value_mismatch, rollback_conflict,
attribution_missing
```

- `ck_hpl_geom_matches_type` 用 `'ST_' || geom_type` 比较，`LineString` 天然成立（`ST_GeometryType` = `ST_LineString`），**不需要改这条**。
- `ck_hpl_location_precision` 已含 `rough`，精度**不需要**任何迁移。
- `ck_hpl_c15` 只要求 published 有几何；staging 允许 NULL，7,200 个无坐标地点可正常入库。

---

## 三、几何值域

| 值 | 本轮产生量 | 说明 |
|---|---:|---|
| `Point` | 26,684 | 23,367 真实点 + 3,317 代表点 |
| `Polygon` | 4,114 | 4 条先修复 |
| `MultiPolygon` | 0（可能由修复产生） | 值域已有 |
| **`LineString`** | **4,893** | **新增** |
| `MultiLineString` | 0 | **不加**：v4.1 线文件逐行判定 100% 为 `LineString` |
| `GeometryCollection` | 0 | 禁止：修复结果若为集合，用 `ST_CollectionExtract(...,3)` 取面，取不到则跳过并记账 |

---

## 四、三个新台账类型：数量与定义

| `issue_type` | 数量 | 定义 | 数据来源 |
|---|---:|---|---|
| `geometry_invalid_repaired` | **4** | 源 WKT `ST_IsValid=false`，入库前经 `ST_MakeValid` + `ST_CollectionExtract(...,3)` 修复成功 | `location_polygons.csv`：整包 5 条，NEW 里 4 条 |
| `connection_endpoint_missing` | **28** | 连接至少一端解析不到 `place_id`，不生成候选关系 | `connections.csv`：24 条指向不存在的 place + 3 条指向 `/errata/` + 1 条整行空 |
| `accuracy_unknown_sentinel` | **728** | `places_accuracy.min_accuracy_meters = -1`（"未知"哨兵）转 NULL | 只统计"有代表点无 location 行"的 3,317 个地点中 728 个 rough 者 |

### 4.1 为什么 `accuracy_unknown_sentinel` 是 728

`places_accuracy.csv` 在 NEW 集合里有 11,438 行是 `-1`。但本方案**不整表导入**该文件，
只把 `min_accuracy_meters` 用作 3,317 条代表点合成行的 `uncertainty_m` 来源：

- 2,589 个 precise → 值为正（5–9,310 m，中位 930 m）→ 直接写 `uncertainty_m`
- 728 个 rough → 值为 `-1` → 写 NULL + 记 728 条台账
- 其余 10,710 条 `-1` 不对应任何入库字段，**不产生台账行**

若将来导入 `places_accuracy` 整表，必须按新口径重算，不得沿用 728。

### 4.2 `connection_endpoint_missing` 的 28 条构成（逐条可查）

| 子类 | 数量 | 例 |
|---|---:|---|
| 指向不存在的 place | 24 | `999238742 → 368305523`（near） |
| 指向 `/errata/<id>`（本就不是地点） | 3 | `1001914 → /errata/991384`（succeeds） |
| 整行字段全空（`connections.csv` 第 4498 行 `,,,,,,,,,,,,`） | 1 | id/两端/类型全空 |

明细见 `code/ops/m4-3/connections_audit.json` 的 `ids.B2_one_side_dangling` / `ids.B1_blank_row`。

---

## 五、Migration 内容（设计稿）

文件名：`V9__geometry_linestring_and_issue_types.sql`

```sql
-- M4-3 / R1.1：放行 LineString 几何，并补齐 3 类新台账类型。
-- 只改两个 CHECK 值域；不改列类型、不改索引、不改其他约束、不动任何数据。

BEGIN;

-- 1) 几何类型：Point / Polygon / MultiPolygon → + LineString
ALTER TABLE historical_place_location
    DROP CONSTRAINT ck_hpl_geom_type;

ALTER TABLE historical_place_location
    ADD CONSTRAINT ck_hpl_geom_type
    CHECK (geom_type = ANY (ARRAY['Point', 'Polygon', 'MultiPolygon', 'LineString']));

-- 2) 台账类型：20 → 23（place_without_geometry 按 OWNER 决策不加）
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
        -- M4-3 新增（3 个）
        'geometry_invalid_repaired', 'connection_endpoint_missing',
        'accuracy_unknown_sentinel'
    ]));

COMMIT;
```

### 5.1 为什么不用 `NOT VALID` + `VALIDATE`

两表 1.8 万 / 1.3 万行，`CHECK` 重校验秒级。一次性 `ADD CONSTRAINT` 更简单，也避免"未校验"中间态。
若 M4-4 导入后表到 5 万行仍觉得慢，再改 `NOT VALID` 不迟。

### 5.2 锁与影响

`ACCESS EXCLUSIVE` 毫秒级；不重写表；不触碰 PostGIS 索引。

---

## 六、执行前后校验 SQL

### 6.1 执行前

```sql
SELECT geom_type, count(*) FROM historical_place_location GROUP BY 1 ORDER BY 2 DESC;  -- 应只有 Point
SELECT count(DISTINCT issue_type) FROM data_quality_issue;                              -- 应为 20
SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint
 WHERE conname IN ('ck_hpl_geom_type','ck_data_quality_issue_issue_type');
```

### 6.2 执行后（应全部通过）

```sql
-- 1) 两个约束已含新值
SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname='ck_hpl_geom_type';
--    期望包含 'LineString'
SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname='ck_data_quality_issue_issue_type';
--    期望包含 3 个新值、且**不含** 'place_without_geometry'

-- 2) 存量未变（前后 count 必须相等）
SELECT count(*) FROM historical_place_location;
SELECT count(*) FROM data_quality_issue;

-- 3) 无越界值
SELECT count(*) FROM historical_place_location
 WHERE geom_type NOT IN ('Point','Polygon','MultiPolygon','LineString');   -- 期望 0

-- 4) 几何与类型仍一致
SELECT count(*) FROM historical_place_location
 WHERE geom IS NOT NULL AND st_geometrytype(geom) <> ('ST_' || geom_type); -- 期望 0
```

### 6.3 验收用查询（不写台账，OWNER 已确认）

```sql
-- place_without_geometry：既无任何 location 行、又无代表点/bbox 的地点
-- 期望（导入后）：7,200
SELECT count(*) FROM historical_place p
 WHERE p.dataset_id = 'pleiades_gis_4_1'
   AND NOT EXISTS (SELECT 1 FROM historical_place_location l WHERE l.place_id = p.place_id)
   AND p.place_type_basis_note LIKE '%has_representative_point=false%';
-- 注：落地时用一个显式标记（notes 或 basis_note 中的固定串）表达"该 place 无坐标线索"，
--     避免依赖 jsonb 之外的隐式规则。
```

### 6.4 回滚

```sql
-- 前提：不存在 geom_type='LineString' 的行，且台账中无 3 个新类型
BEGIN;
ALTER TABLE historical_place_location DROP CONSTRAINT ck_hpl_geom_type;
ALTER TABLE historical_place_location ADD CONSTRAINT ck_hpl_geom_type
  CHECK (geom_type = ANY (ARRAY['Point','Polygon','MultiPolygon']));
ALTER TABLE data_quality_issue DROP CONSTRAINT ck_data_quality_issue_issue_type;
ALTER TABLE data_quality_issue ADD CONSTRAINT ck_data_quality_issue_issue_type
  CHECK (issue_type = ANY (ARRAY[ ... 原 20 值 ... ]));
COMMIT;
```

回滚前必须确认 `SELECT count(*) FROM historical_place_location WHERE geom_type='LineString'` = 0，
否则会因存量违规而失败——这是**正确**的失败，不能强推。

---

## 七、执行边界

| 项 | 本轮（R1.1） | M4-4 |
|---|---|---|
| 写 V9 文件 | **不写**（本文只是设计稿） | 写入 `code/backend/src/main/resources/db/migration/V9__…sql` |
| 在测试库执行 | **不执行** | 在**隔离测试库**执行（建议新建 `canvas_history_m4_3`，不复用 `_m2check`） |
| 在正式库执行 | **永不** | 需单独授权 |

---

## 八、V9 之外的模型问题（登记，不阻塞）

| # | 问题 | 现状 | 建议 |
|---|---|---|---|
| 1 | `place_type` 只有 5 值 | 48,030 条类型关系只在归档 + 汇总文本 | 需要按类型筛选时再建 `place_type_link` |
| 2 | 名称无 `attested_form` 列 | 10,297 条只在 raw_payload | OWNER 已确认本轮不补 |
| 3 | 位置无 `archaeological_remains` 列 | 32,374 行只在 raw_payload | 需要筛选时再扩 |
| 4 | `source_record` 无 `external_uri` | uri 只在 raw_payload | 可选 |
