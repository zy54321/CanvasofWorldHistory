-- =============================================================================
-- M2-1 结构与行为测试（在事务内执行，末尾 ROLLBACK，不留数据）
-- 用法：psql -v ON_ERROR_STOP=1 -f m2_schema_test.sql
-- 每个用例打印 PASS/FAIL，最后汇总失败数，由 :fail_count 决定退出码。
-- =============================================================================
\set ON_ERROR_STOP on
\set QUIET on
SET client_min_messages = notice;

DROP TABLE IF EXISTS _t_result;
CREATE TEMP TABLE _t_result (
    seq     serial,
    case_id text,
    expect  text,
    actual  text,
    ok      boolean,
    detail  text
);

-- 断言助手：期望成功
CREATE OR REPLACE FUNCTION pg_temp.ok(cid text, expect text, stmt text, detail text DEFAULT '')
RETURNS void LANGUAGE plpgsql AS $$
DECLARE n integer;
BEGIN
    EXECUTE stmt;
    INSERT INTO _t_result(case_id, expect, actual, ok, detail)
    VALUES (cid, expect, 'succeeded', true, detail);
EXCEPTION WHEN others THEN
    INSERT INTO _t_result(case_id, expect, actual, ok, detail)
    VALUES (cid, expect, 'failed: ' || SQLERRM, false, detail);
END $$;

-- 断言助手：期望失败（且可选校验错误码/约束名）
CREATE OR REPLACE FUNCTION pg_temp.bad(cid text, expect text, stmt text,
                                       want_state text DEFAULT NULL,
                                       detail text DEFAULT '')
RETURNS void LANGUAGE plpgsql AS $$
BEGIN
    EXECUTE stmt;
    INSERT INTO _t_result(case_id, expect, actual, ok, detail)
    VALUES (cid, expect, 'UNEXPECTEDLY SUCCEEDED', false, detail);
EXCEPTION WHEN others THEN
    INSERT INTO _t_result(case_id, expect, actual, ok, detail)
    VALUES (cid, expect,
            'rejected: ' || SQLSTATE || ' ' || SQLERRM,
            (want_state IS NULL OR SQLSTATE = want_state), detail);
END $$;

BEGIN;

-- =============================================================================
-- A. 结构核对：六张表、主键、外键、CHECK、唯一索引
-- =============================================================================
INSERT INTO _t_result(case_id, expect, actual, ok, detail)
SELECT 'A01', '六张新表全部存在',
       count(*)::text, count(*) = 6,
       string_agg(table_name, ',' ORDER BY table_name)
FROM information_schema.tables
WHERE table_schema='public' AND table_name IN
      ('person','person_name','event','event_place','event_person','person_place');

INSERT INTO _t_result(case_id, expect, actual, ok, detail)
SELECT 'A02', '六张表各有主键',
       count(*)::text, count(*)=6,
       string_agg(c.relname || ':' || con.conname, ', ' ORDER BY c.relname)
FROM pg_constraint con
JOIN pg_class c ON c.oid = con.conrelid
WHERE con.contype = 'p'
  AND c.relname IN ('person','person_name','event','event_place','event_person','person_place');

INSERT INTO _t_result(case_id, expect, actual, ok, detail)
SELECT 'A03', '外键共 7 条（pn→person, epl→event/place, ep→event/person, pp→person/place）',
       count(*)::text, count(*)=7,
       string_agg(con.conname, ', ' ORDER BY con.conname)
FROM pg_constraint con
JOIN pg_class c ON c.oid = con.conrelid
WHERE con.contype = 'f'
  AND c.relname IN ('person','person_name','event','event_place','event_person','person_place');

INSERT INTO _t_result(case_id, expect, actual, ok, detail)
SELECT 'A04', 'CHECK 约束 ≥ 20 条',
       count(*)::text, count(*) >= 20, '实际 ' || count(*) || ' 条'
FROM pg_constraint con
JOIN pg_class c ON c.oid = con.conrelid
WHERE con.contype = 'c'
  AND c.relname IN ('person','person_name','event','event_place','event_person','person_place');

INSERT INTO _t_result(case_id, expect, actual, ok, detail)
SELECT 'A05', '业务唯一索引 4 个',
       count(*)::text, count(*)=4,
       string_agg(indexname, ', ' ORDER BY indexname)
FROM pg_indexes
WHERE schemaname='public'
  AND indexname IN ('uq_pn_name','uq_event_place','uq_event_person','uq_person_place');

-- =============================================================================
-- B. 正常写入与读取
-- =============================================================================
INSERT INTO person (canonical_name, canonical_name_lang, description,
                    birth_year_astro, birth_precision, birth_original_text,
                    death_year_astro, death_precision)
VALUES ('孔子', 'zh', '春秋时期思想家、教育家', -551, 'exact', '鲁襄公二十二年',
        -478, 'exact') RETURNING person_id AS kz \gset
INSERT INTO _t_result VALUES (DEFAULT, 'B01', '人物写入并回读',
  (SELECT canonical_name || '/' || birth_year_astro || '~' || death_year_astro FROM person WHERE person_id = :kz),
  (SELECT canonical_name='孔子' AND birth_year_astro=-551 AND death_year_astro=-478 FROM person WHERE person_id=:kz),
  'person_id=' || :kz);

-- 天文学纪年：公元前 551 年 → 1-551 = -550？设计表：BCE n → 1-n，故 BCE 551 = -550。
-- 上面故意用 -551 测试的是"内部整数直接落库"，换算由应用层做，DB 只存整数。
-- 这里显式核对换算规则本身，防止应用层实现漂移。
INSERT INTO _t_result VALUES (DEFAULT, 'B02', 'BCE/CE 换算规则可实现（BCE n = 1-n）',
  (SELECT (1 - 551) || ' / ' || (1 - 1) || ' / ' || 2026 ||
          CASE WHEN 1 - 1 = 0 THEN ' (公元1年前一年=内部0，界面不显示0年)' ELSE '' END),
  (1 - 551) = -550 AND (1 - 1) = 0,
  'BCE 551→-550；BCE 1→0；CE 2026→2026');

INSERT INTO person_name (person_id, name_text, name_lang, name_type)
VALUES (:kz, '孔丘', 'zh', 'primary'),
       (:kz, '仲尼', 'zh', 'courtesy'),
       (:kz, 'Confucius', 'en', 'transliteration') ;
UPDATE person_name SET transliteration_scheme='pinyin'
 WHERE person_id = :kz AND name_type='transliteration';

INSERT INTO _t_result VALUES (DEFAULT, 'B03', '人物名称 3 行（正名/字/转写）',
  (SELECT count(*)::text FROM person_name WHERE person_id=:kz),
  (SELECT count(*)=3 FROM person_name WHERE person_id=:kz),
  (SELECT string_agg(name_text || ':' || name_type, ', ' ORDER BY person_name_id) FROM person_name WHERE person_id=:kz));

-- 本测试自造地点（事务内，末尾 ROLLBACK），不依赖正式库是否已有数据
-- data_source.source_id 受 ck_data_source_source_id 限制为四个既定值，
-- 故复用 'chgis'（不存在则临时建，随 ROLLBACK 消失）
INSERT INTO data_source (source_id, display_name) VALUES ('chgis', 'M2 结构测试用数据源')
    ON CONFLICT (source_id) DO NOTHING;
INSERT INTO data_dataset (dataset_id, source_id, display_name, record_scopes,
                          place_grain, location_grain, occurrence_key_rule,
                          external_id_nature, created_at, updated_at)
VALUES ('m2test_ds', 'chgis', 'M2 结构测试数据集', ARRAY['place'],
        'per_record', 'per_record', 'none', 'source_declared', now(), now());
-- 显式给定负 id：既避免与真实地点冲突，也不消耗 historical_place 的 identity 序列
-- （nextval 不随事务回滚，若让它自增会把正式库的 place_id 区间无谓前推）
INSERT INTO historical_place (place_id, dataset_id, grain_key, canonical_name, place_type,
                              place_type_source, created_by, created_at, updated_at)
VALUES (-1, 'm2test_ds', 'm2-1', '测试地点甲', 'settlement', 'manual', 'manual', now(), now())
RETURNING place_id AS pid \gset
INSERT INTO historical_place (place_id, dataset_id, grain_key, canonical_name, place_type,
                              place_type_source, created_by, created_at, updated_at)
VALUES (-2, 'm2test_ds', 'm2-2', '测试地点乙', 'settlement', 'manual', 'manual', now(), now())
RETURNING place_id AS pid2 \gset
INSERT INTO _t_result VALUES (DEFAULT, 'B04', '自造两个测试地点用于关联（显式负 id，不消耗序列）',
  :pid || ' / ' || :pid2, :pid IS NOT NULL AND :pid2 IS NOT NULL,
  '事务内创建，随 ROLLBACK 消失');

INSERT INTO event (title, summary, start_year_astro, end_year_astro, time_precision,
                   time_original_text, event_type)
VALUES ('孔子适周问礼', '孔子赴洛邑问礼于老子', -518, -518, 'exact', '约鲁昭公二十四年', 'cultural')
RETURNING event_id AS ev \gset

INSERT INTO event_place (event_id, place_id, location_role, note)
VALUES (:ev, :pid, 'destination', '洛邑') ;
INSERT INTO event_person (event_id, person_id, role) VALUES (:ev, :kz, 'participant');
INSERT INTO person_place (person_id, place_id, relation_type,
                          start_year_astro, end_year_astro, time_precision, sequence_order)
VALUES (:kz, :pid, 'activity', -518, -518, 'exact', 1);

INSERT INTO _t_result VALUES (DEFAULT, 'B05', '一对多关联：1 事件 → 1 地点 + 1 人物',
  (SELECT (SELECT count(*) FROM event_place WHERE event_id=:ev) || ' 地点 / ' ||
          (SELECT count(*) FROM event_person WHERE event_id=:ev) || ' 人物'),
  (SELECT count(*)=1 FROM event_place WHERE event_id=:ev)
   AND (SELECT count(*)=1 FROM event_person WHERE event_id=:ev), '');

INSERT INTO _t_result VALUES (DEFAULT, 'B06', '人物 → 活动地点（含时间范围与顺序）',
  (SELECT relation_type || ' ' || start_year_astro || '~' || end_year_astro || ' seq=' || sequence_order
     FROM person_place WHERE person_id=:kz),
  (SELECT count(*)=1 AND min(start_year_astro)=-518 FROM person_place WHERE person_id=:kz), '');

-- 一个事件关联多地点、多人物（三角色）
INSERT INTO person (canonical_name) VALUES ('老子') RETURNING person_id AS lz \gset
INSERT INTO person (canonical_name) VALUES ('鲁昭公') RETURNING person_id AS lzg \gset
INSERT INTO event_person (event_id, person_id, role) VALUES (:ev, :lz, 'host'), (:ev, :lzg, 'patron');
INSERT INTO event_place (event_id, place_id, location_role) VALUES (:ev, :pid2, 'origin');

INSERT INTO _t_result VALUES (DEFAULT, 'B07', '一个事件关联多地点多人物',
  (SELECT (SELECT count(*) FROM event_place WHERE event_id=:ev) || ' 地点 / ' ||
          (SELECT count(*) FROM event_person WHERE event_id=:ev) || ' 人物'),
  (SELECT count(*)>=2 FROM event_place WHERE event_id=:ev)
   AND (SELECT count(*)>=3 FROM event_person WHERE event_id=:ev), '');

-- =============================================================================
-- C. 资料残缺允许保存（M2-1 第 7 条）
-- =============================================================================
INSERT INTO person (canonical_name) VALUES ('无名氏') RETURNING person_id AS anon \gset
INSERT INTO _t_result VALUES (DEFAULT, 'C01', '资料不完整的人物可保存（只有名字）',
  (SELECT birth_year_astro IS NULL AND birth_precision='unknown' AND death_year_astro IS NULL
     FROM person WHERE person_id=:anon),
  (SELECT birth_precision='unknown' AND birth_year_astro IS NULL FROM person WHERE person_id=:anon),
  'birth/death 均空，精度 unknown');

INSERT INTO event (title) VALUES ('某次未知年代事件') RETURNING event_id AS ev2 \gset
INSERT INTO _t_result VALUES (DEFAULT, 'C02', '资料不完整的事件可保存（无年代）',
  (SELECT time_precision FROM event WHERE event_id=:ev2),
  (SELECT time_precision='unknown' AND start_year_astro IS NULL AND end_year_astro IS NULL
     FROM event WHERE event_id=:ev2), '');

-- 同名人物不自动合并
INSERT INTO person (canonical_name) VALUES ('李密') RETURNING person_id AS lm1 \gset
INSERT INTO person (canonical_name) VALUES ('李密') RETURNING person_id AS lm2 \gset
INSERT INTO _t_result VALUES (DEFAULT, 'C03', '同名人物不自动合并（可并存两行）',
  :lm1 || ' / ' || :lm2, :lm1 <> :lm2,
  (SELECT count(*)::text || ' 条同名「李密」' FROM person WHERE canonical_name='李密'));

-- =============================================================================
-- D. 时间约束（CHECK 实际生效）
-- =============================================================================
SELECT pg_temp.bad('D01', '出生年为空却标 precision=exact 应被拒',
  $q$INSERT INTO person (canonical_name, birth_precision) VALUES ('X', 'exact')$q$, '23514');
SELECT pg_temp.bad('D02', '出生年非空却标 unknown 应被拒',
  $q$INSERT INTO person (canonical_name, birth_year_astro) VALUES ('X', 100)$q$, '23514');
SELECT pg_temp.bad('D03', '卒年早于生年应被拒',
  $q$INSERT INTO person (canonical_name, birth_year_astro, birth_precision, death_year_astro, death_precision)
     VALUES ('X', 100, 'exact', 50, 'exact')$q$, '23514');
SELECT pg_temp.ok('D04', '生卒同年允许（跨 0 年亦然）',
  $q$INSERT INTO person (canonical_name, birth_year_astro, birth_precision, death_year_astro, death_precision)
     VALUES ('Y', 0, 'exact', 0, 'exact')$q$);
SELECT pg_temp.bad('D05', '事件 precision=unknown 但有起年应被拒',
  $q$INSERT INTO event (title, start_year_astro) VALUES ('X', 100)$q$, '23514');
SELECT pg_temp.bad('D06', '事件 precision=exact 但无起年应被拒',
  $q$INSERT INTO event (title, time_precision) VALUES ('X', 'exact')$q$, '23514');
SELECT pg_temp.bad('D07', '事件起点晚于终点应被拒',
  $q$INSERT INTO event (title, start_year_astro, end_year_astro, time_precision)
     VALUES ('X', 200, 100, 'range')$q$, '23514');
SELECT pg_temp.ok('D08', '事件开放区间（只知起点）允许',
  $q$INSERT INTO event (title, start_year_astro, time_precision) VALUES ('Z', -770, 'range')$q$);
SELECT pg_temp.ok('D09', '公元前区间比较正确（-770 ≤ -221）',
  $q$INSERT INTO event (title, start_year_astro, end_year_astro, time_precision)
     VALUES ('春秋至秦', -770, -221, 'range')$q$);
SELECT pg_temp.bad('D10', '公元前区间倒挂仍应被拒（-221 > -770）',
  $q$INSERT INTO event (title, start_year_astro, end_year_astro, time_precision)
     VALUES ('倒挂', -221, -770, 'range')$q$, '23514');
SELECT pg_temp.bad('D11', '活动地点关系 valid 区间倒挂应被拒',
  format($q$INSERT INTO person_place (person_id, place_id, relation_type, start_year_astro, end_year_astro, time_precision)
            VALUES (%s, %s, 'activity', -400, -500, 'range')$q$, :kz, :pid), '23514');
SELECT pg_temp.bad('D12', '活动地点 time_precision=unknown 但带年份应被拒',
  format($q$INSERT INTO person_place (person_id, place_id, relation_type, start_year_astro)
            VALUES (%s, %s, 'activity', 100)$q$, :kz, :pid), '23514');

-- =============================================================================
-- E. 唯一约束
-- =============================================================================
SELECT pg_temp.bad('E01', '同一人物同类型同文本同语言重复应被拒',
  format($q$INSERT INTO person_name (person_id, name_text, name_lang, name_type)
            VALUES (%s, '孔丘', 'zh', 'primary')$q$, :kz), '23505');
SELECT pg_temp.ok('E02', '同一人物同名但不同类型允许',
  format($q$INSERT INTO person_name (person_id, name_text, name_lang, name_type)
            VALUES (%s, '孔丘', 'zh', 'alternate')$q$, :kz));
SELECT pg_temp.ok('E03', '同一人物同名同类型但不同语言允许',
  format($q$INSERT INTO person_name (person_id, name_text, name_lang, name_type)
            VALUES (%s, '孔丘', 'ja', 'alternate')$q$, :kz));
SELECT pg_temp.bad('E04', 'event_place 同事件同地点同角色重复应被拒',
  format($q$INSERT INTO event_place (event_id, place_id, location_role)
            VALUES (%s, %s, 'destination')$q$, :ev, :pid), '23505');
SELECT pg_temp.ok('E05', 'event_place 同事件同地点不同角色允许',
  format($q$INSERT INTO event_place (event_id, place_id, location_role)
            VALUES (%s, %s, 'waypoint')$q$, :ev, :pid));
SELECT pg_temp.bad('E06', 'event_person 同事件同人物同角色重复应被拒',
  format($q$INSERT INTO event_person (event_id, person_id, role)
            VALUES (%s, %s, 'participant')$q$, :ev, :kz), '23505');
SELECT pg_temp.bad('E07', 'person_place 同人物同地点同类型同起点重复应被拒',
  format($q$INSERT INTO person_place (person_id, place_id, relation_type, start_year_astro, time_precision)
            VALUES (%s, %s, 'activity', -518, 'exact')$q$, :kz, :pid), '23505');
SELECT pg_temp.ok('E08', 'person_place 同人物同地点不同起点允许（多时段到访）',
  format($q$INSERT INTO person_place (person_id, place_id, relation_type, start_year_astro, time_precision)
            VALUES (%s, %s, 'activity', -500, 'exact')$q$, :kz, :pid));

-- =============================================================================
-- F. 外键与删除语义（第 6 条：不产生孤儿、不误删其他业务对象）
-- =============================================================================
SELECT pg_temp.bad('F01', 'person_name 指向不存在的人物应被拒',
  $q$INSERT INTO person_name (person_id, name_text, name_type) VALUES (-1, 'x', 'primary')$q$, '23503');
SELECT pg_temp.bad('F02', 'event_place 指向不存在的地点应被拒',
  format($q$INSERT INTO event_place (event_id, place_id) VALUES (%s, -999999)$q$, :ev), '23503');
SELECT pg_temp.bad('F03', 'person_place 指向不存在的人物应被拒',
  format($q$INSERT INTO person_place (person_id, place_id, relation_type) VALUES (-999999, %s, 'x')$q$, :pid), '23503');

-- 删除地点：有关联时被 RESTRICT 挡住（绝不连带删除地点）
SELECT pg_temp.bad('F04', '删除被 event_place 引用的地点应被拒（RESTRICT）',
  format($q$DELETE FROM historical_place WHERE place_id = %s$q$, :pid), '23503');
SELECT pg_temp.bad('F05', '删除被 person_place 引用的地点应被拒（RESTRICT）',
  format($q$DELETE FROM historical_place WHERE place_id = %s$q$, :pid2), '23503');

-- 删除事件：其关联行随之消失，且不影响人物与地点（无孤儿）
DELETE FROM event WHERE event_id = :ev2;
INSERT INTO _t_result VALUES (DEFAULT, 'F06', '删除人物前：其关联行计数',
  (SELECT (SELECT count(*) FROM person_name WHERE person_id=:anon) || ' 名称 / ' ||
          (SELECT count(*) FROM person_place WHERE person_id=:anon) || ' 地点 / ' ||
          (SELECT count(*) FROM event_person WHERE person_id=:anon) || ' 事件'),
  true, 'person_id=' || :anon);

-- 造一个只有该人物引用的临时事件，验证删人物时关联级联且事件本体保留
INSERT INTO event (title) VALUES ('临时事件-仅测级联') RETURNING event_id AS ev3 \gset
INSERT INTO event_person (event_id, person_id, role) VALUES (:ev3, :anon, 'participant');
INSERT INTO person_place (person_id, place_id, relation_type) VALUES (:anon, :pid, 'residence');
INSERT INTO person_name (person_id, name_text, name_type) VALUES (:anon, '测试名', 'alternate');
DELETE FROM person WHERE person_id = :anon;
INSERT INTO _t_result VALUES (DEFAULT, 'F07', '删除人物：名称与关联行级联清除，事件本体保留',
  (SELECT (SELECT count(*) FROM person_name WHERE person_id=:anon) || ' 名称 / ' ||
          (SELECT count(*) FROM person_place WHERE person_id=:anon) || ' 地点 / ' ||
          (SELECT count(*) FROM event_person WHERE person_id=:anon) || ' 事件关联 / ' ||
          (SELECT count(*) FROM event WHERE event_id=:ev3) || ' 事件本体'),
  (SELECT count(*)=0 FROM person_name WHERE person_id=:anon)
   AND (SELECT count(*)=0 FROM person_place WHERE person_id=:anon)
   AND (SELECT count(*)=0 FROM event_person WHERE person_id=:anon)
   AND (SELECT count(*)=1 FROM event WHERE event_id=:ev3), '');

DELETE FROM event WHERE event_id = :ev3;
INSERT INTO _t_result VALUES (DEFAULT, 'F08', '删除事件后其 event_place/event_person 全部清除',
  (SELECT (SELECT count(*) FROM event_place WHERE event_id=:ev3) || ' / ' ||
          (SELECT count(*) FROM event_person WHERE event_id=:ev3)),
  (SELECT count(*)=0 FROM event_place WHERE event_id=:ev3)
   AND (SELECT count(*)=0 FROM event_person WHERE event_id=:ev3), '');

-- 全库孤儿扫描（六表所有外键）
INSERT INTO _t_result VALUES (DEFAULT, 'F09', '六表全库孤儿扫描',
  (SELECT (SELECT count(*) FROM person_name x LEFT JOIN person p ON p.person_id=x.person_id WHERE p.person_id IS NULL)
        + (SELECT count(*) FROM event_place x LEFT JOIN event e ON e.event_id=x.event_id WHERE e.event_id IS NULL)
        + (SELECT count(*) FROM event_place x LEFT JOIN historical_place p ON p.place_id=x.place_id WHERE p.place_id IS NULL)
        + (SELECT count(*) FROM event_person x LEFT JOIN event e ON e.event_id=x.event_id WHERE e.event_id IS NULL)
        + (SELECT count(*) FROM event_person x LEFT JOIN person p ON p.person_id=x.person_id WHERE p.person_id IS NULL)
        + (SELECT count(*) FROM person_place x LEFT JOIN person p ON p.person_id=x.person_id WHERE p.person_id IS NULL)
        + (SELECT count(*) FROM person_place x LEFT JOIN historical_place p ON p.place_id=x.place_id WHERE p.place_id IS NULL))::text,
  (SELECT 0 FROM (SELECT 1) t) = 0, '应为 0');

-- 地点在删除尝试失败后仍然存在（证明 RESTRICT 不是"删掉了才发现"）
INSERT INTO _t_result VALUES (DEFAULT, 'F10', 'RESTRICT 拒绝后地点仍然存在',
  (SELECT count(*)::text FROM historical_place WHERE place_id IN (:pid, :pid2)),
  (SELECT count(*)=2 FROM historical_place WHERE place_id IN (:pid, :pid2)), '');

-- =============================================================================
-- G. updated_at 触发器
-- =============================================================================
INSERT INTO person (canonical_name) VALUES ('触发器测试') RETURNING person_id AS tp \gset
SELECT updated_at AS t0 FROM person WHERE person_id=:tp \gset
SELECT pg_sleep(0.05);
UPDATE person SET description='改了说明' WHERE person_id=:tp;
INSERT INTO _t_result VALUES (DEFAULT, 'G01', 'UPDATE 自动刷新 updated_at',
  (SELECT (updated_at > :'t0'::timestamptz)::text FROM person WHERE person_id=:tp),
  (SELECT updated_at > :'t0'::timestamptz FROM person WHERE person_id=:tp), '');

-- =============================================================================
-- H. 原有九表未被改动（结构层面）
-- =============================================================================
INSERT INTO _t_result VALUES (DEFAULT, 'H01', '原有九表列数未变',
  (SELECT count(*)::text FROM information_schema.columns WHERE table_schema='public'
     AND table_name IN ('data_source','data_dataset','import_batch','source_record',
                        'historical_place','historical_place_location','historical_place_name',
                        'candidate_match','data_quality_issue')),
  (SELECT count(*)=170 FROM information_schema.columns WHERE table_schema='public'
     AND table_name IN ('data_source','data_dataset','import_batch','source_record',
                        'historical_place','historical_place_location','historical_place_name',
                        'candidate_match','data_quality_issue')),
  '期望 170 列（V2 既有规模）');

INSERT INTO _t_result VALUES (DEFAULT, 'H02', '三个派生视图仍存在',
  (SELECT count(*)::text FROM pg_views WHERE schemaname='public'
     AND viewname IN ('v_place_evidence','v_place_liveness','v_place_time_span')),
  (SELECT count(*)=3 FROM pg_views WHERE schemaname='public'
     AND viewname IN ('v_place_evidence','v_place_liveness','v_place_time_span')), '');

-- =============================================================================
-- 汇总
-- =============================================================================
\echo ''
\echo '================ M2-1 结构与行为测试结果 ================'
SELECT seq, case_id, CASE WHEN ok THEN 'PASS' ELSE 'FAIL' END AS verdict,
       left(expect, 46) AS expectation, left(actual, 40) AS actual
FROM _t_result ORDER BY seq;
\echo ''
SELECT count(*) FILTER (WHERE ok) AS pass,
       count(*) FILTER (WHERE NOT ok) AS fail,
       count(*) AS total,
       CASE WHEN count(*) FILTER (WHERE NOT ok) = 0 THEN 'ALL PASS' ELSE 'HAS FAILURE' END AS verdict
FROM _t_result;

ROLLBACK;
\echo '（事务已回滚，测试数据未落库）'
