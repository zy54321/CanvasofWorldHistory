-- P0 · 数据永久性核验（只读）
--
-- 用法（psql）：
--   psql -v ts="'2026-11-04 20:46:01+08'" -f ops/p0/unification_check.sql
--
-- 目的：证明"升级前就存在的行"在 Migration + 导入之后**一个字节都没变**。
-- 做法：所有指纹都限定 created_at < :ts（升级开始时刻），因此新增的 Pleiades 行
-- 不会进入比对；剔除按设计会变的列（updated_at / last_batch_id / occurrence_count）。
-- 几何单独用 ST_AsEWKB 的十六进制参与比较，避免 WKB 文本表示的差异。

\pset pager off

SELECT '--- 全表行数 ---' AS section;
SELECT 'source_record' AS tbl, count(*) AS rows FROM source_record
UNION ALL SELECT 'historical_place', count(*) FROM historical_place
UNION ALL SELECT 'historical_place_name', count(*) FROM historical_place_name
UNION ALL SELECT 'historical_place_location', count(*) FROM historical_place_location
UNION ALL SELECT 'candidate_match', count(*) FROM candidate_match
UNION ALL SELECT 'data_quality_issue', count(*) FROM data_quality_issue
UNION ALL SELECT 'data_dataset', count(*) FROM data_dataset
ORDER BY 1;

SELECT '--- 升级前就存在的行：行数 + 指纹（created_at < :ts）---' AS section;
SELECT 'source_record' AS tbl, count(*) AS rows,
       encode(sha256(convert_to(coalesce(string_agg(j,'|' ORDER BY id),''),'UTF8')),'hex') AS sha256
  -- 注意：source_record 的 ingested_at 取自暂存 CSV 的固定构建时间，不是"入库时刻"，
  -- 用它区分新旧会失效。这里按数据集切分：Pleiades 4.1 是本轮唯一的新增数据集。
  FROM (SELECT source_record_id AS id, (row_to_json(s)::jsonb - 'last_batch_id')::text AS j
          FROM source_record s WHERE dataset_id <> 'pleiades_gis_4_1') q
UNION ALL
SELECT 'historical_place', count(*),
       encode(sha256(convert_to(coalesce(string_agg(j,'|' ORDER BY id),''),'UTF8')),'hex')
  FROM (SELECT place_id AS id, (row_to_json(p)::jsonb - 'updated_at')::text AS j
          FROM historical_place p WHERE dataset_id <> 'pleiades_gis_4_1') q
UNION ALL
SELECT 'historical_place_name', count(*),
       encode(sha256(convert_to(coalesce(string_agg(j,'|' ORDER BY id),''),'UTF8')),'hex')
  FROM (SELECT name_id AS id, (row_to_json(n)::jsonb - 'updated_at')::text AS j
          FROM historical_place_name n WHERE created_at < :ts) q
UNION ALL
SELECT 'historical_place_location', count(*),
       encode(sha256(convert_to(coalesce(string_agg(j,'|' ORDER BY id),''),'UTF8')),'hex')
  FROM (SELECT location_id AS id,
               (row_to_json(l)::jsonb - 'updated_at'
                 || jsonb_build_object('geom_ewkb', encode(ST_AsEWKB(l.geom),'hex')))::text AS j
          FROM historical_place_location l WHERE created_at < :ts) q
UNION ALL
SELECT 'candidate_match', count(*),
       encode(sha256(convert_to(coalesce(string_agg(j,'|' ORDER BY id),''),'UTF8')),'hex')
  FROM (SELECT candidate_id AS id, (row_to_json(c)::jsonb - 'updated_at')::text AS j
          FROM candidate_match c WHERE created_at < :ts) q
UNION ALL
SELECT 'data_dataset', count(*),
       encode(sha256(convert_to(coalesce(string_agg(j,'|' ORDER BY id),''),'UTF8')),'hex')
  FROM (SELECT dataset_id AS id, (row_to_json(d)::jsonb - 'updated_at')::text AS j
          FROM data_dataset d WHERE created_at < :ts) q
ORDER BY 1;
