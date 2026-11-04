-- V9 执行前后校验 + 完整可执行回滚（M4-4a 交付物，本阶段不执行）
--
-- 用法（M4-4b 起，仅隔离测试库）：
--   psql -h 127.0.0.1 -p 15432 -U canvas_app -d canvas_history_m4_3 -f V9_checks.sql
--   -- 前两步为只读校验，第三段回滚需要显式取消注释
--
-- 本阶段（M4-4a）边界：不连接数据库执行任何语句；此文件只作为交付物随 V9 一起审查。

-- ===========================================================================
-- 一、执行前校验（期望值见注释；任何一条不符即停止，不得执行 V9）
-- ===========================================================================

-- 1.1 几何类型分布：V9 执行前应只有 Point
SELECT geom_type, count(*) AS rows
  FROM historical_place_location
 GROUP BY 1
 ORDER BY 2 DESC;

-- 1.2 台账值域 vs 实际用到的类型 —— 两件事必须分开看
--     （a）CHECK 允许多少值：V9 执行前应恰为 20（从约束定义里数，不数数据）
--     （b）库里实际出现过多少种：由数据决定，**不要求**等于 20；
--         没出现过的合法类型不算缺失，只是这批数据没碰到。
SELECT length(pg_get_constraintdef(oid))
       - length(replace(pg_get_constraintdef(oid), ''',''', '')) + 1 AS allowed_values_in_check
  FROM pg_constraint
 WHERE conname = 'ck_data_quality_issue_issue_type';

SELECT count(DISTINCT issue_type) AS observed_types,
       string_agg(DISTINCT issue_type, ', ' ORDER BY issue_type) AS observed_list
  FROM data_quality_issue;

-- 1.2b 实际出现的类型必须全部落在允许值域内（越界即为数据问题，不是值域问题）
SELECT count(*) AS out_of_vocabulary
  FROM data_quality_issue
 WHERE issue_type NOT IN ('beg_gt_end', 'beg_eq_end', 'missing_coordinate',
        'coordinate_out_of_range', 'coordinate_outside_china_bbox', 'year_out_of_range',
        'duplicate_external_id', 'duplicate_sysid', 'unknown_crs', 'unknown_time_bound_type',
        'nonstandard_field_name', 'empty_name', 'parent_place_not_in_sample',
        'truncated_slice_tail', 'cross_layer_coordinate_conflict', 'manual_edit_conflict',
        'import_row_error', 'derived_value_mismatch', 'rollback_conflict',
        'attribution_missing');

-- 1.3 三个待改约束的当前定义（应分别不含 LineString / 新 3 值 / 新失效原因）
SELECT conname, pg_get_constraintdef(oid) AS definition
  FROM pg_constraint
 WHERE conname IN ('ck_hpl_geom_type',
                   'ck_data_quality_issue_issue_type',
                   'ck_source_record_c19');

-- 1.4 存量基线（记录下来，执行后必须完全相等）
SELECT 'historical_place_location' AS table_name, count(*) FROM historical_place_location
UNION ALL SELECT 'data_quality_issue', count(*) FROM data_quality_issue
UNION ALL SELECT 'source_record', count(*) FROM source_record;

-- ===========================================================================
-- 二、执行后校验（应全部通过）
-- ===========================================================================

-- 2.1 约束已含新值
SELECT conname, pg_get_constraintdef(oid) LIKE '%LineString%'                AS has_linestring,
       pg_get_constraintdef(oid) LIKE '%accuracy_unknown_sentinel%'          AS has_sentinel_type,
       pg_get_constraintdef(oid) LIKE '%superseded_by_newer_snapshot%'       AS has_superseded
  FROM pg_constraint
 WHERE conname IN ('ck_hpl_geom_type',
                   'ck_data_quality_issue_issue_type',
                   'ck_source_record_c19');

-- 2.2 台账值域恰为 23 个，且不含 place_without_geometry
SELECT pg_get_constraintdef(oid) LIKE '%place_without_geometry%' AS must_be_false
  FROM pg_constraint
 WHERE conname = 'ck_data_quality_issue_issue_type';

-- 2.3 存量未变（与 1.4 逐项相等）
SELECT 'historical_place_location' AS table_name, count(*) FROM historical_place_location
UNION ALL SELECT 'data_quality_issue', count(*) FROM data_quality_issue
UNION ALL SELECT 'source_record', count(*) FROM source_record;

-- 2.4 无越界几何类型
SELECT count(*) AS out_of_range
  FROM historical_place_location
 WHERE geom_type NOT IN ('Point', 'Polygon', 'MultiPolygon', 'LineString');

-- 2.5 几何与类型仍一致（LineString 也必须成立）
SELECT count(*) AS geom_type_mismatch
  FROM historical_place_location
 WHERE geom IS NOT NULL
   AND st_geometrytype(geom) <> ('ST_' || geom_type);

-- ===========================================================================
-- 三、回滚（完整可执行；默认注释，需要时手工取消注释）
--     前提：库里不存在 geom_type='LineString' 的位置行，也不存在 3 个新台账类型
--           与新失效原因的行。不满足时 ALTER 会失败 —— 这是**正确**的失败，
--           不得用 DELETE 业务数据来强推回滚。
-- ===========================================================================
/*
BEGIN;

-- 3.0 回滚前提自检（任一非 0 则 COMMIT 前应 ROLLBACK）
SELECT 'linestring_locations' AS check_name, count(*) AS blocking_rows
  FROM historical_place_location WHERE geom_type = 'LineString'
UNION ALL
SELECT 'new_issue_types', count(*)
  FROM data_quality_issue
 WHERE issue_type IN ('geometry_invalid_repaired',
                      'connection_endpoint_missing',
                      'accuracy_unknown_sentinel')
UNION ALL
SELECT 'superseded_source_records', count(*)
  FROM source_record WHERE inactive_reason = 'superseded_by_newer_snapshot';

-- 3.1 geom_type 回到 3 值
ALTER TABLE historical_place_location DROP CONSTRAINT IF EXISTS ck_hpl_geom_type;
ALTER TABLE historical_place_location
    ADD CONSTRAINT ck_hpl_geom_type
    CHECK (geom_type = ANY (ARRAY['Point', 'Polygon', 'MultiPolygon']));

-- 3.2 issue_type 回到 V8 的 20 值
ALTER TABLE data_quality_issue DROP CONSTRAINT IF EXISTS ck_data_quality_issue_issue_type;
ALTER TABLE data_quality_issue
    ADD CONSTRAINT ck_data_quality_issue_issue_type
    CHECK (issue_type = ANY (ARRAY[
        'beg_gt_end', 'beg_eq_end', 'missing_coordinate', 'coordinate_out_of_range',
        'coordinate_outside_china_bbox', 'year_out_of_range', 'duplicate_external_id',
        'duplicate_sysid', 'unknown_crs', 'unknown_time_bound_type',
        'nonstandard_field_name', 'empty_name', 'parent_place_not_in_sample',
        'truncated_slice_tail', 'cross_layer_coordinate_conflict',
        'manual_edit_conflict', 'import_row_error', 'derived_value_mismatch',
        'rollback_conflict', 'attribution_missing']));

-- 3.3 inactive_reason 回到 V2 的 3 值
ALTER TABLE source_record DROP CONSTRAINT IF EXISTS ck_source_record_c19;
ALTER TABLE source_record
    ADD CONSTRAINT ck_source_record_c19
    CHECK (inactive_reason IS NULL
        OR inactive_reason IN ('source_absent', 'batch_rolled_back', 'duplicate_quarantine'));

COMMIT;
*/

-- ===========================================================================
-- 四、验收查询（按 Owner 决策：place_without_geometry 不写台账，只查）
--     这是 M4-4b 导入完成后才有的指标；此处保留查询定义，供验收直接使用。
-- ===========================================================================
/*
-- 4.1 无任何位置行的 Pleiades 4.1 地点（A2 合成后期望 7,200）
SELECT count(*) AS place_without_geometry
  FROM historical_place p
 WHERE p.dataset_id = 'pleiades_gis_4_1'
   AND NOT EXISTS (SELECT 1 FROM historical_place_location l WHERE l.place_id = p.place_id);

-- 4.2 几何类型分布（导入后期望 Point 26,684 / Polygon 4,112 /
--     MultiPolygon 2 / LineString 4,893，合计 35,691）
SELECT geom_type, count(*) FROM historical_place_location GROUP BY 1 ORDER BY 2 DESC;

-- 4.3 位置级精度（导入后期望 precise 31,223 / rough 4,468）
SELECT location_precision, count(*) FROM historical_place_location GROUP BY 1 ORDER BY 2 DESC;

-- 4.4 面/线必须有代表点，否则地图不显示
SELECT count(*) AS missing_representative
  FROM historical_place_location
 WHERE geom_type <> 'Point'
   AND (representative_lon IS NULL OR representative_lat IS NULL);
*/
