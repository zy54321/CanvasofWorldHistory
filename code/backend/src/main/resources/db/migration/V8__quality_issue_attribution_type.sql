-- V8 · M4-2：质量台账新增 attribution_missing 类型
--
-- 背景：Owner 取消许可门禁后，数据授权由 Owner 负责，系统不再判断许可、审核许可或检查许可完整性。
--   WHG 扁平记录（HGIS de las Indias）缺 attribution 块这件事，原本以 licence_unconfirmed 记录，
--   在 V2 中该类型已从 19 值域删除，导入器当时靠“直接剔除 2 行”绕过。
--   本轮取消剔除，这 2 行必须入库，且不能再用“许可未确认”这种以许可为准入条件的命名。
--
-- 处理：只把真实观察到的类型补进值域（19 → 20），不放宽其他约束、不改语义、不动既有列。
--   被补入的类型有真实数据支撑：2 行，severity=info，action_taken=preserved_and_flagged。
--
-- 影响面：仅 data_quality_issue.issue_type 的 CHECK 值域。不新增表/列/索引，不回填历史数据。
-- 执行范围：只在测试库 canvas_history_m2check 执行；正式库保持 V5，不执行 V6/V7/V8。

ALTER TABLE data_quality_issue
    DROP CONSTRAINT ck_data_quality_issue_issue_type;

ALTER TABLE data_quality_issue
    ADD CONSTRAINT ck_data_quality_issue_issue_type
        CHECK (issue_type IN ('beg_gt_end', 'beg_eq_end', 'missing_coordinate', 'coordinate_out_of_range',
                              'coordinate_outside_china_bbox', 'year_out_of_range', 'duplicate_external_id',
                              'duplicate_sysid', 'unknown_crs', 'unknown_time_bound_type', 'nonstandard_field_name',
                              'empty_name', 'parent_place_not_in_sample', 'truncated_slice_tail',
                              'cross_layer_coordinate_conflict', 'manual_edit_conflict', 'import_row_error',
                              'derived_value_mismatch', 'rollback_conflict',
                              -- M4-2 新增：来源元数据（attribution）缺失，非阻断
                              'attribution_missing'));

COMMENT ON CONSTRAINT ck_data_quality_issue_issue_type ON data_quality_issue IS
    'issue_type 值域（M4-2 起 20 值）：原 19 值 + attribution_missing。'
    'attribution_missing 记录“来源载荷没有 attribution 块”，severity=info，不参与任何准入判定。';
