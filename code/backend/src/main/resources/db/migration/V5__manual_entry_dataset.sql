-- =============================================================================
-- V5：人工录入地点的溯源落点 + 人工名称去重
--
-- 背景（M2 收尾施工时发现的真实缺口，不是为前端方便而放宽约束）：
--   historical_place.dataset_id 是 NOT NULL 外键，而 data_dataset 里只有 7 个
--   导入数据集；data_source 的 CHECK 又把 source_id 限死为 chgis/pleiades/whg/mcgd。
--   也就是说：**M2 要求的「新增历史地点」在现有模型下无处安放**——
--   硬塞进 chgis 等数据集会把人工录入误标成第三方来源，属伪造溯源。
--
--   因此新增第 5 个数据源 'manual'（人工录入）与一个固定数据集
--   'manual_entry'，让人工地点有诚实的归属。这是模型补全，不是放宽既有校验：
--   四个原有 source_id 的约束语义完全不变，仍不可写入未知取值。
--
-- 另加一条部分唯一索引：人工录入的名称行（source_record_id IS NULL）不允许
-- 同一地点下「同类型 + 同文本 + 同语言」重复。既有 47,499 行全部有
-- source_record_id，不受影响（WHERE 子句把它们排除在外）。
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. data_source 增加 'manual'
-- -----------------------------------------------------------------------------
ALTER TABLE data_source DROP CONSTRAINT ck_data_source_source_id;
ALTER TABLE data_source ADD CONSTRAINT ck_data_source_source_id
    CHECK (source_id IN ('chgis', 'pleiades', 'whg', 'mcgd', 'manual'));

COMMENT ON CONSTRAINT ck_data_source_source_id ON data_source IS
    'V5 起允许 manual（人工录入）。原有四个导入源语义不变。';

INSERT INTO data_source (source_id, display_name, homepage_url, display_priority, notes)
VALUES ('manual', '人工录入', NULL, 0,
        'M2 起通过管理界面新增/编辑的地点归入此来源。不含任何第三方数据，不得与导入数据混淆。')
ON CONFLICT (source_id) DO NOTHING;

-- -----------------------------------------------------------------------------
-- 2. 人工录入数据集
-- -----------------------------------------------------------------------------
INSERT INTO data_dataset (dataset_id, source_id, display_name, dataset_version,
                          record_scopes, place_grain, location_grain,
                          grain_evidence, occurrence_key_rule, external_id_nature,
                          record_count, is_active, notes, created_at, updated_at)
VALUES ('manual_entry', 'manual', '人工录入地点', 'v1',
        ARRAY['place', 'name', 'location'], 'per_record', 'per_record',
        '人工逐条录入，无外部批量来源；粒度即「一条记录一个地点」。',
        'none', 'source_declared',
        0, true,
        'M2 管理界面的写入落点。grain_key 由服务端生成（manual-<place_id>），保证 C04 唯一。',
        now(), now())
ON CONFLICT (dataset_id) DO NOTHING;

COMMENT ON TABLE data_dataset IS
    '七个导入数据集 + V5 起的 manual_entry（人工录入）。自然键 text 主键。';

-- -----------------------------------------------------------------------------
-- 3. 人工名称去重（不影响既有导入数据）
-- -----------------------------------------------------------------------------
CREATE UNIQUE INDEX uq_hpn_manual_name
    ON historical_place_name (place_id, name_type, name_text, coalesce(name_lang, ''))
    WHERE source_record_id IS NULL;

COMMENT ON INDEX uq_hpn_manual_name IS
    'M2 人工录入名称的去重。既有导入行 source_record_id 非空，全部落在 WHERE 之外。';
