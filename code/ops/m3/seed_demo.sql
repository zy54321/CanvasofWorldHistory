-- ==========================================================================
-- M3 演示数据（**仅测试库 canvas_history_m2check**，正式库禁止执行）
--
-- 目的：让时间轴 / 地图标记 / 时空矩阵可被真实观察与测试。
-- 说明：这些是**演示用最小数据**，不是史料整理成果；事件与政权的关联全部人工指定，
--       没有任何"按名称或坐标自动推断政权"的逻辑。
-- 幂等：先按标题前缀「演示：」清理，再插入。
-- ==========================================================================

-- ---------------------------------------------------------------- 清理旧演示数据
DELETE FROM event_polity
 WHERE event_id IN (SELECT event_id FROM event WHERE title LIKE '演示：%');
DELETE FROM event_place
 WHERE event_id IN (SELECT event_id FROM event WHERE title LIKE '演示：%');
DELETE FROM event WHERE title LIKE '演示：%';
DELETE FROM historical_polity WHERE name IN
    ('波斯帝国', '新巴比伦', '希腊城邦', '马其顿王国', '罗马共和国', '孔雀王朝', '秦', '汉');

-- ---------------------------------------------------------------- 演示地点（负 id，不消耗序列）
INSERT INTO data_source (source_id, display_name) VALUES ('chgis', '演示数据源')
    ON CONFLICT (source_id) DO NOTHING;
INSERT INTO data_dataset (dataset_id, source_id, display_name, record_scopes, place_grain,
                          location_grain, occurrence_key_rule, external_id_nature, created_at, updated_at)
VALUES ('m3_demo_ds', 'chgis', 'M3 演示数据集', ARRAY['place'], 'per_record', 'per_record',
        'none', 'source_declared', now(), now())
    ON CONFLICT (dataset_id) DO NOTHING;

INSERT INTO historical_place (place_id, dataset_id, grain_key, canonical_name, place_type,
                              place_type_source, created_by, record_status, created_at, updated_at)
VALUES (-101, 'm3_demo_ds', 'demo-marathon', '马拉松', 'settlement', 'manual', 'manual', 'staging', now(), now()),
       (-102, 'm3_demo_ds', 'demo-thermopylae', '温泉关', 'settlement', 'manual', 'manual', 'staging', now(), now()),
       (-103, 'm3_demo_ds', 'demo-babylon', '巴比伦', 'settlement', 'manual', 'manual', 'staging', now(), now()),
       (-104, 'm3_demo_ds', 'demo-persepolis', '波斯波利斯', 'settlement', 'manual', 'manual', 'staging', now(), now()),
       (-105, 'm3_demo_ds', 'demo-xianyang', '咸阳', 'settlement', 'manual', 'manual', 'staging', now(), now()),
       (-106, 'm3_demo_ds', 'demo-pataliputra', '华氏城', 'settlement', 'manual', 'manual', 'staging', now(), now()),
       (-107, 'm3_demo_ds', 'demo-alexandria', '亚历山大港', 'settlement', 'manual', 'manual', 'staging', now(), now())
    ON CONFLICT (place_id) DO NOTHING;

INSERT INTO historical_place_location (place_id, geom, geom_type, representative_lon, representative_lat,
                                       crs_confidence, axis_order_verified, location_precision,
                                       record_status, created_by, created_at, updated_at)
VALUES (-101, ST_SetSRID(ST_MakePoint(23.97, 38.15), 4326), 'Point', 23.97, 38.15, 'confirmed', true, 'approximate', 'staging', 'manual', now(), now()),
       (-102, ST_SetSRID(ST_MakePoint(22.53, 38.80), 4326), 'Point', 22.53, 38.80, 'confirmed', true, 'approximate', 'staging', 'manual', now(), now()),
       (-103, ST_SetSRID(ST_MakePoint(44.42, 32.54), 4326), 'Point', 44.42, 32.54, 'confirmed', true, 'approximate', 'staging', 'manual', now(), now()),
       (-104, ST_SetSRID(ST_MakePoint(52.89, 29.93), 4326), 'Point', 52.89, 29.93, 'confirmed', true, 'approximate', 'staging', 'manual', now(), now()),
       (-105, ST_SetSRID(ST_MakePoint(108.70, 34.33), 4326), 'Point', 108.70, 34.33, 'confirmed', true, 'approximate', 'staging', 'manual', now(), now()),
       (-106, ST_SetSRID(ST_MakePoint(85.13, 25.60), 4326), 'Point', 85.13, 25.60, 'confirmed', true, 'approximate', 'staging', 'manual', now(), now()),
       (-107, ST_SetSRID(ST_MakePoint(29.92, 31.20), 4326), 'Point', 29.92, 31.20, 'confirmed', true, 'approximate', 'staging', 'manual', now(), now())
    ON CONFLICT DO NOTHING;

-- ---------------------------------------------------------------- 演示政权（展示地区为人工指定）
INSERT INTO historical_polity (name, region_code, start_year_astro, end_year_astro, description, record_status)
VALUES ('波斯帝国',   'middle_east', -549, -330, '阿契美尼德王朝（演示用区间）', 'staging'),
       ('新巴比伦',   'middle_east', -625, -538, '迦勒底王朝（演示用区间）', 'staging'),
       ('希腊城邦',   'europe',      -799, -145, '古典时期希腊诸城邦（演示用区间）', 'staging'),
       ('马其顿王国', 'europe',      -808, -167, '阿吉德王朝至安提柯王朝（演示用区间）', 'staging'),
       ('罗马共和国', 'europe',      -508,  -26, '罗马共和国（演示用区间）', 'staging'),
       ('孔雀王朝',   'south_asia',  -321, -184, '孔雀王朝（演示用区间）', 'staging'),
       ('秦',         'east_asia',   -220, -206, '秦朝（演示用区间）', 'staging'),
       ('汉',         'east_asia',   -201,  220, '西汉至东汉（演示用区间）', 'staging')
    ON CONFLICT (name, region_code) DO NOTHING;

-- ---------------------------------------------------------------- 演示事件
WITH ins AS (
    INSERT INTO event (title, summary, description, start_year_astro, end_year_astro, time_precision,
                       event_type, record_status, created_by, created_at, updated_at)
    VALUES
      ('演示：马拉松战役', '公元前 490 年', '希波战争中的一场战役（演示数据，非正式史料条目）',
       -489, -489, 'exact', 'battle', 'staging', 'manual', now(), now()),
      ('演示：温泉关战役', '公元前 480 年', '希波战争中的隘口战（演示数据）',
       -479, -479, 'exact', 'battle', 'staging', 'manual', now(), now()),
      ('演示：巴比伦之囚', '公元前 586 年起', '新巴比伦时期犹太人被掳（演示数据，跨多年）',
       -585, -537, 'range', 'political', 'staging', 'manual', now(), now()),
      ('演示：波斯攻克巴比伦', '公元前 539 年', '居鲁士入巴比伦（演示数据，同时关联两个政权）',
       -538, -538, 'exact', 'political', 'staging', 'manual', now(), now()),
      ('演示：秦灭六国', '公元前 230—前 221 年', '秦统一战争（演示数据，跨 10 年）',
       -229, -220, 'range', 'military', 'staging', 'manual', now(), now()),
      ('演示：汉高祖称帝', '公元前 202 年', '刘邦称帝（演示数据）',
       -201, -201, 'exact', 'political', 'staging', 'manual', now(), now()),
      ('演示：亚历山大东征', '公元前 334—前 323 年', '亚历山大远征（演示数据，跨 12 年）',
       -333, -322, 'range', 'military', 'staging', 'manual', now(), now()),
      ('演示：孔雀王朝立国', '公元前 322 年', '旃陀罗笈多建立孔雀王朝（演示数据）',
       -321, -321, 'exact', 'political', 'staging', 'manual', now(), now()),
      ('演示：布匿战争', '公元前 264—前 146 年', '罗马与迦太基的长期冲突（演示数据，跨百年）',
       -263, -145, 'range', 'military', 'staging', 'manual', now(), now()),
      ('演示：跨公元前后的事件', '公元前 10 年至公元 10 年', '用于验证 BCE/CE 衔接（演示数据）',
       -9, 10, 'range', 'other', 'staging', 'manual', now(), now()),
      ('演示：未归属政权的祭祀事件', '公元前 500 年', '故意不关联任何政权，用于统计未归属数量',
       -499, -499, 'exact', 'religious', 'staging', 'manual', now(), now()),
      ('演示：时间未知的传说', '时间不详', '故意留空时间，验证未知时间事件不进入矩阵与地图',
       NULL, NULL, 'unknown', 'other', 'staging', 'manual', now(), now())
    RETURNING event_id, title
)
SELECT 1;

-- ---------------------------------------------------------------- 事件 ↔ 地点
-- 注意：event_place 没有 updated_at（V4 设计如此），只写 created_at
INSERT INTO event_place (event_id, place_id, location_role, created_at)
SELECT e.event_id, v.place_id, v.role, now()
  FROM (VALUES
        ('演示：马拉松战役', -101, 'battlefield'),
        ('演示：温泉关战役', -102, 'battlefield'),
        ('演示：巴比伦之囚', -103, 'location'),
        ('演示：波斯攻克巴比伦', -103, 'location'),
        ('演示：波斯攻克巴比伦', -104, 'capital'),
        ('演示：秦灭六国', -105, 'capital'),
        ('演示：亚历山大东征', -107, 'location'),
        ('演示：孔雀王朝立国', -106, 'capital'),
        ('演示：跨公元前后的事件', -107, 'location')
       ) AS v(title, place_id, role)
  JOIN event e ON e.title = v.title
 WHERE NOT EXISTS (SELECT 1 FROM event_place ep
                    WHERE ep.event_id = e.event_id AND ep.place_id = v.place_id);

-- ---------------------------------------------------------------- 事件 ↔ 政权（人工指定）
INSERT INTO event_polity (event_id, polity_id, role, note, created_at, updated_at)
SELECT e.event_id, p.polity_id, v.role, NULL, now(), now()
  FROM (VALUES
        ('演示：马拉松战役',       '希腊城邦',   'defender'),
        ('演示：温泉关战役',       '希腊城邦',   'defender'),
        ('演示：巴比伦之囚',       '新巴比伦',   'aggressor'),
        ('演示：波斯攻克巴比伦',   '波斯帝国',   'aggressor'),
        ('演示：波斯攻克巴比伦',   '新巴比伦',   'defeated'),
        ('演示：秦灭六国',         '秦',         'aggressor'),
        ('演示：汉高祖称帝',       '汉',         'founder'),
        ('演示：亚历山大东征',     '马其顿王国', 'aggressor'),
        ('演示：孔雀王朝立国',     '孔雀王朝',   'founder'),
        ('演示：布匿战争',         '罗马共和国', 'aggressor'),
        ('演示：跨公元前后的事件', '罗马共和国', 'participant'),
        ('演示：跨公元前后的事件', '汉',         'participant')
       ) AS v(title, polity_name, role)
  JOIN event e ON e.title = v.title
  JOIN historical_polity p ON p.name = v.polity_name
 WHERE NOT EXISTS (SELECT 1 FROM event_polity ep
                    WHERE ep.event_id = e.event_id AND ep.polity_id = p.polity_id);

SELECT '演示事件数=' || count(*) FROM event WHERE title LIKE '演示：%';
SELECT '演示政权数=' || count(*) FROM historical_polity;
SELECT '关联行数=' || count(*) FROM event_polity;
