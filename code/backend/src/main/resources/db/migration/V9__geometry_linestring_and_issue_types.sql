-- V9 · M4-4a：放行 LineString 几何，并补齐 Pleiades 4.1 全量接入产生的 3 类台账类型
--
-- 依据：M4-3 R1.1《V9 Migration 最终设计稿》(code/ops/reports/M4_3_V9_REVISION.md)
-- 执行范围：**本文件只编写，不在任何数据库执行**。M4-4b 才可在隔离测试库执行；
--           正式库 canvas_history 维持 V5，不执行 V6/V7/V8/V9。
--
-- 三处值域变更（不改列类型、不加列、不改索引、不动任何数据）：
--   1) historical_place_location.geom_type  : Point / Polygon / MultiPolygon
--                                             → + LineString
--   2) data_quality_issue.issue_type        : 20 值 → 23 值
--                                             新增 geometry_invalid_repaired /
--                                                  connection_endpoint_missing /
--                                                  accuracy_unknown_sentinel
--     注意：按 Owner 决策，**不**新增 place_without_geometry（该指标只做验收查询）。
--   3) source_record.inactive_reason        : 3 值 → 4 值
--                                             新增 superseded_by_newer_snapshot
--
-- 关于第 3 项（V9-D1 增补，R1.1 设计稿遗漏，需 Owner 追认）：
--   冻结决策「2,552 条重叠地点保留 inactive source_record」要求把新快照的地点源记录写成
--   is_active=false。但 V2 的 ck_source_record_c19 只允许 source_absent /
--   batch_rolled_back / duplicate_quarantine 三种原因，且 C03/C18 规定
--   「NOT is_active ⇒ inactive_reason IS NOT NULL」、C20 规定 duplicate_quarantine 必须
--   duplicate_ordinal > 0。三个既有值没有一个能表达「同 grain_key 已由既有切片快照承载，
--   本行仅为追溯保留」，硬套会造成语义错误（源端并未消失，也不是组内重复行）。
--   因此这里只做一次最小枚举扩宽（+1 个值），不改变任何既有语义。
--   若 Owner 不追认，回退方案是改用 'source_absent'（合法但语义不准确），
--   对应代码常量见 code/ops/import_staging.py 的 SUPERSEDED_INACTIVE_REASON。
--
-- 幂等：三处变更都用 DO 块先判后改，重复执行不会报错，便于反复审查。
-- 事务：不写显式 BEGIN/COMMIT —— Flyway 在 PostgreSQL 上默认把单个 migration 放在一个
--       事务里执行，显式 BEGIN 只会产生「already a transaction in progress」告警。
--       回滚脚本见 code/ops/m4-4a/V9_rollback.sql（含执行前后校验）。

-- ---------------------------------------------------------------------------
-- 1) 几何类型：Point / Polygon / MultiPolygon → + LineString
--    ck_hpl_geom_matches_type 用 'ST_' || geom_type 比较，
--    ST_GeometryType(LineString) = 'ST_LineString'，因此该约束天然成立，无需修改。
-- ---------------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conname = 'ck_hpl_geom_type'
           AND pg_get_constraintdef(oid) LIKE '%LineString%'
    ) THEN
        ALTER TABLE historical_place_location
            DROP CONSTRAINT IF EXISTS ck_hpl_geom_type;

        ALTER TABLE historical_place_location
            ADD CONSTRAINT ck_hpl_geom_type
            CHECK (geom_type = ANY (ARRAY['Point', 'Polygon', 'MultiPolygon', 'LineString']));
    END IF;
END
$$;

COMMENT ON CONSTRAINT ck_hpl_geom_type ON historical_place_location IS
    '几何类型值域（M4-4a 起 4 值）：Point / Polygon / MultiPolygon / LineString。'
    'v4.1 的 location_linestrings 逐行判定 100% 为 LineString，故不预置 MultiLineString；'
    '修复后的无效面若含多个面片则写 MultiPolygon（本批 2 条）。';

-- ---------------------------------------------------------------------------
-- 2) 台账类型：20 → 23
--    完整保留 V8 的 20 个合法值，只追加 3 个。
-- ---------------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conname = 'ck_data_quality_issue_issue_type'
           AND pg_get_constraintdef(oid) LIKE '%accuracy_unknown_sentinel%'
    ) THEN
        ALTER TABLE data_quality_issue
            DROP CONSTRAINT IF EXISTS ck_data_quality_issue_issue_type;

        ALTER TABLE data_quality_issue
            ADD CONSTRAINT ck_data_quality_issue_issue_type
            CHECK (issue_type = ANY (ARRAY[
                -- V2 起 19 值（删除 licence_unconfirmed 后）
                'beg_gt_end', 'beg_eq_end', 'missing_coordinate', 'coordinate_out_of_range',
                'coordinate_outside_china_bbox', 'year_out_of_range', 'duplicate_external_id',
                'duplicate_sysid', 'unknown_crs', 'unknown_time_bound_type',
                'nonstandard_field_name', 'empty_name', 'parent_place_not_in_sample',
                'truncated_slice_tail', 'cross_layer_coordinate_conflict',
                'manual_edit_conflict', 'import_row_error', 'derived_value_mismatch',
                'rollback_conflict',
                -- V8 起第 20 值
                'attribution_missing',
                -- M4-4a 起新增 3 值（V9）
                'geometry_invalid_repaired',   -- 源 WKT 无效，入库前经 GEOS/ST_MakeValid 修复成功
                'connection_endpoint_missing', -- 连接至少一端解析不到 place_id，不生成候选关系
                'accuracy_unknown_sentinel'    -- places_accuracy.min_accuracy_meters = -1 转 NULL
                -- 按 Owner 决策：不新增 place_without_geometry（只做验收查询）
            ]));
    END IF;
END
$$;

COMMENT ON CONSTRAINT ck_data_quality_issue_issue_type ON data_quality_issue IS
    'issue_type 值域（M4-4a 起 23 值）：V2 的 19 值 + attribution_missing（V8）+ '
    'geometry_invalid_repaired / connection_endpoint_missing / accuracy_unknown_sentinel（V9）。'
    'place_without_geometry 按 Owner 决策不入台账。';

-- ---------------------------------------------------------------------------
-- 3) 源记录失效原因：3 → 4（V9-D1 增补，见文件头说明）
-- ---------------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conname = 'ck_source_record_c19'
           AND pg_get_constraintdef(oid) LIKE '%superseded_by_newer_snapshot%'
    ) THEN
        ALTER TABLE source_record
            DROP CONSTRAINT IF EXISTS ck_source_record_c19;

        ALTER TABLE source_record
            ADD CONSTRAINT ck_source_record_c19
            CHECK (inactive_reason IS NULL
                OR inactive_reason IN ('source_absent', 'batch_rolled_back',
                                       'duplicate_quarantine',
                                       'superseded_by_newer_snapshot'));
    END IF;
END
$$;

COMMENT ON CONSTRAINT ck_source_record_c19 ON source_record IS
    '失效原因值域（M4-4a 起 4 值）：source_absent / batch_rolled_back / duplicate_quarantine '
    '/ superseded_by_newer_snapshot。新增值语义：同一 grain_key 已由既有切片快照承载，'
    '本行来自更新的快照，仅为追溯保留，不派生业务行（is_active=false，duplicate_ordinal=0）。';
