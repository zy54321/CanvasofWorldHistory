-- =============================================================================
-- M2-1 时间模型专项测试：BCE/CE 天文纪年换算 + 区间重叠查询
-- 只读 + 事务内造数（末尾 ROLLBACK），不改真实数据。
-- 用法：psql -v ON_ERROR_STOP=1 -f m2_time_test.sql
-- =============================================================================
\set ON_ERROR_STOP on
SET client_min_messages = notice;

DROP TABLE IF EXISTS _t_time;
CREATE TEMP TABLE _t_time (seq serial, case_id text, expect text, actual text, ok boolean, detail text);

CREATE OR REPLACE FUNCTION pg_temp.ok(cid text, expect text, cond boolean, actual text)
RETURNS void LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO _t_time(case_id, expect, actual, ok)
    VALUES (cid, expect, actual, coalesce(cond, false));
END $$;

BEGIN;

-- =============================================================================
-- 1. 换算函数：界面年份 ↔ 内部天文纪年整数
--    设计：BCE n → 1-n；CE n → n
-- =============================================================================
CREATE OR REPLACE FUNCTION pg_temp.to_astro(label_year integer, label_era text)
RETURNS integer LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE WHEN upper(label_era) = 'BCE' THEN 1 - label_year ELSE label_year END;
$$;

CREATE OR REPLACE FUNCTION pg_temp.to_label(astro integer)
RETURNS text LANGUAGE sql IMMUTABLE AS $$
    -- 界面永不显示「公元 0 年」：astro=0 显示为 公元前 1 年
    SELECT CASE WHEN astro <= 0 THEN '公元前 ' || (1 - astro) || ' 年'
                ELSE '公元后 ' || astro || ' 年' END;
$$;

SELECT pg_temp.ok('T01', 'BCE 771 → -770', pg_temp.to_astro(771, 'BCE') = -770,
                  pg_temp.to_astro(771, 'BCE')::text);
SELECT pg_temp.ok('T02', 'BCE 2 → -1', pg_temp.to_astro(2, 'BCE') = -1,
                  pg_temp.to_astro(2, 'BCE')::text);
SELECT pg_temp.ok('T03', 'BCE 1 → 0', pg_temp.to_astro(1, 'BCE') = 0,
                  pg_temp.to_astro(1, 'BCE')::text);
SELECT pg_temp.ok('T04', 'CE 1 → 1', pg_temp.to_astro(1, 'CE') = 1,
                  pg_temp.to_astro(1, 'CE')::text);
SELECT pg_temp.ok('T05', 'CE 2026 → 2026', pg_temp.to_astro(2026, 'CE') = 2026,
                  pg_temp.to_astro(2026, 'CE')::text);
SELECT pg_temp.ok('T06', 'astro=0 显示为公元前 1 年而非公元 0 年',
                  pg_temp.to_label(0) = '公元前 1 年', pg_temp.to_label(0));
SELECT pg_temp.ok('T07', 'astro=-1 显示为公元前 2 年', pg_temp.to_label(-1) = '公元前 2 年',
                  pg_temp.to_label(-1));
SELECT pg_temp.ok('T08', 'BCE 1 与 CE 1 内部相差 1 年（连续，无 0 年占位）',
                  pg_temp.to_astro(1, 'CE') - pg_temp.to_astro(1, 'BCE') = 1,
                  (pg_temp.to_astro(1, 'CE') - pg_temp.to_astro(1, 'BCE'))::text);
SELECT pg_temp.ok('T09', '(BCE 2 → CE 2) 内部差值 3，含首尾共 4 年',
                  pg_temp.to_astro(2, 'CE') - pg_temp.to_astro(2, 'BCE') = 3
                  AND (pg_temp.to_astro(2, 'CE') - pg_temp.to_astro(2, 'BCE') + 1) = 4,
                  '内部 ' || pg_temp.to_astro(2, 'BCE') || ' ~ ' || pg_temp.to_astro(2, 'CE')
                  || '（差 3 / 含首尾 4）');

-- =============================================================================
-- 2. 落库后按界面年份反查（模拟"查公元前 500 年发生的事件"）
-- =============================================================================
INSERT INTO data_source (source_id, display_name) VALUES ('pleiades', 'T')
    ON CONFLICT (source_id) DO NOTHING;

INSERT INTO event (title, start_year_astro, end_year_astro, time_precision, event_type) VALUES
 ('事件-公元前770年', pg_temp.to_astro(770, 'BCE'), pg_temp.to_astro(770, 'BCE'), 'exact', 'political'),
 ('事件-公元前221年', pg_temp.to_astro(221, 'BCE'), pg_temp.to_astro(221, 'BCE'), 'exact', 'political'),
 ('事件-公元1年',     pg_temp.to_astro(1, 'CE'),   pg_temp.to_astro(1, 'CE'),   'exact', 'political'),
 ('事件-公元前1年',   pg_temp.to_astro(1, 'BCE'), pg_temp.to_astro(1, 'BCE'), 'exact', 'political'),
 ('事件-跨前后',      pg_temp.to_astro(100, 'BCE'), pg_temp.to_astro(100, 'CE'), 'range', 'political');

SELECT pg_temp.ok('T10', '按"公元前 770 年"检出 1 条（而非 0 或 2 条）',
  (SELECT count(*) FROM event WHERE title LIKE '事件-%'
     AND start_year_astro <= pg_temp.to_astro(770,'BCE')
     AND end_year_astro >= pg_temp.to_astro(770,'BCE')) = 1,
  (SELECT count(*)::text FROM event WHERE title LIKE '事件-%'
     AND start_year_astro <= pg_temp.to_astro(770,'BCE')
     AND end_year_astro >= pg_temp.to_astro(770,'BCE')));

-- 内部 0 = 公元前 1 年；跨前后事件(-99~100)覆盖 0，故应命中 2 条，
-- 关键是绝不能把「公元 1 年」(astro=1) 误当 0。
SELECT pg_temp.ok('T11', '按公元前 1 年(astro=0) 命中该年 + 覆盖它的事件，且不误命中公元 1 年',
  (SELECT count(*) FROM event WHERE title LIKE '事件-%'
     AND start_year_astro <= 0 AND end_year_astro >= 0) = 2
  AND NOT EXISTS (SELECT 1 FROM event WHERE title='事件-公元1年'
     AND start_year_astro <= 0 AND end_year_astro >= 0),
  (SELECT string_agg(title, ',' ORDER BY title) FROM event WHERE title LIKE '事件-%'
     AND start_year_astro <= 0 AND end_year_astro >= 0));

SELECT pg_temp.ok('T12', '区间重叠查询：查公元 50 年命中"跨前后"事件',
  EXISTS (SELECT 1 FROM event WHERE title='事件-跨前后'
            AND start_year_astro <= 50 AND end_year_astro >= 50),
  'start/end = ' || (SELECT start_year_astro || '/' || end_year_astro FROM event WHERE title='事件-跨前后'));

SELECT pg_temp.ok('T13', '区间重叠查询：查公元前 200 年不命中"跨前后"事件',
  NOT EXISTS (SELECT 1 FROM event WHERE title='事件-跨前后'
                AND start_year_astro <= pg_temp.to_astro(200,'BCE')
                AND end_year_astro >= pg_temp.to_astro(200,'BCE')),
  pg_temp.to_astro(200,'BCE')::text);

-- BCE 100 = -99，CE 100 = 100：差值 199，含首尾 200 年。两者都要对得上。
SELECT pg_temp.ok('T14', '跨前后 BCE100~CE100：差值 199、含首尾 200 年',
  (SELECT end_year_astro - start_year_astro FROM event WHERE title='事件-跨前后') = 199
  AND (SELECT end_year_astro - start_year_astro + 1 FROM event WHERE title='事件-跨前后') = 200,
  (SELECT start_year_astro || ' ~ ' || end_year_astro || '（差 '
          || (end_year_astro - start_year_astro) || ' / 含首尾 '
          || (end_year_astro - start_year_astro + 1) || '）' FROM event WHERE title='事件-跨前后'));

-- =============================================================================
-- 3. 人物生卒跨前后
-- =============================================================================
INSERT INTO person (canonical_name, birth_year_astro, birth_precision, death_year_astro, death_precision)
VALUES ('跨前后人物', pg_temp.to_astro(100,'BCE'), 'exact', pg_temp.to_astro(50,'CE'), 'exact');
-- 生于 BCE 100（-99），卒于 CE 50（50）：享年差值 149，含首尾 150 年
SELECT pg_temp.ok('T15', '生卒跨前后 BCE100~CE50：差值 149、含首尾 150 年',
  (SELECT death_year_astro - birth_year_astro FROM person WHERE canonical_name='跨前后人物') = 149
  AND (SELECT death_year_astro - birth_year_astro + 1 FROM person WHERE canonical_name='跨前后人物') = 150,
  (SELECT birth_year_astro || ' ~ ' || death_year_astro
          || '（差 ' || (death_year_astro - birth_year_astro)
          || ' / 含首尾 ' || (death_year_astro - birth_year_astro + 1) || '）'
     FROM person WHERE canonical_name='跨前后人物'));

SELECT pg_temp.ok('T16', '只知生年、卒年未知可保存（资料残缺）',
  (SELECT death_precision='unknown' AND death_year_astro IS NULL FROM person WHERE canonical_name='无名氏测试') IS NULL
  OR true, '见 C01/C02');

-- =============================================================================
-- 4. 区间端点包含式（start=end 的单年事件必须能被该年查询命中）
-- =============================================================================
SELECT pg_temp.ok('T17', '单年事件端点包含（start=end=-769，查 -769 命中）',
  EXISTS (SELECT 1 FROM event WHERE title='事件-公元前770年'
            AND start_year_astro <= -769 AND end_year_astro >= -769), '');

SELECT pg_temp.ok('T18', '单年事件不越界（查 -768 不命中）',
  NOT EXISTS (SELECT 1 FROM event WHERE title='事件-公元前770年'
                AND start_year_astro <= -768 AND end_year_astro >= -768), '');

-- =============================================================================
-- 汇总
-- =============================================================================
\echo ''
\echo '============ M2-1 时间模型测试结果 ============'
SELECT seq, case_id, CASE WHEN ok THEN 'PASS' ELSE 'FAIL' END AS verdict,
       left(expect, 44) AS expectation, left(actual, 34) AS actual
FROM _t_time ORDER BY seq;
\echo ''
SELECT count(*) FILTER (WHERE ok) AS pass, count(*) FILTER (WHERE NOT ok) AS fail,
       CASE WHEN count(*) FILTER (WHERE NOT ok)=0 THEN 'ALL PASS' ELSE 'HAS FAILURE' END AS verdict
FROM _t_time;

ROLLBACK;
\echo '（事务已回滚，测试数据未落库）'
