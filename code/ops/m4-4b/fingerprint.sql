-- M4-4b · 关键数据指纹（可重复、可比对）
--
-- 目的：证明「既有四源数据在 V9 与导入之后一行未变」，而不是只看行数。
--
-- 用法：
--   psql -d canvas_history_m4_4b -v cutoff=14 -f code/ops/m4-4b/fingerprint.sql
--
-- cutoff = 导入前已有的 import_batch 最大 batch_id。既有行一律由
-- first_batch_id <= cutoff 定义（而不是按时间戳猜），因此重复执行结论稳定。
--
-- 为什么用 `- 'xxx'` 扣掉几列：
--   last_batch_id / updated_at / occurrence_count 是**按设计会被推进**的列
--   （"最近一次被看到"语义），把它们算进指纹会让"没有变化"永远不成立。
--   扣掉它们之后，剩下的每一个字节都必须与导入前相同。
--
-- 输出：每张表一行 {tbl, rows, sha256}。行数也一起比，避免"内容一样但多了一行"。

\pset pager off
\pset format aligned

WITH legacy_sr AS MATERIALIZED (
    SELECT source_record_id FROM source_record WHERE first_batch_id <= :cutoff
)
SELECT 'source_record' AS tbl, count(*) AS rows,
       encode(sha256(convert_to(coalesce(string_agg(j, '|' ORDER BY id), ''), 'UTF8')), 'hex') AS sha256
  FROM (SELECT sr.source_record_id AS id,
               (row_to_json(sr)::jsonb - 'last_batch_id')::text AS j
          FROM source_record sr WHERE sr.first_batch_id <= :cutoff) q
UNION ALL
SELECT 'historical_place', count(*),
       encode(sha256(convert_to(coalesce(string_agg(j, '|' ORDER BY id), ''), 'UTF8')), 'hex')
  FROM (SELECT p.place_id AS id, (row_to_json(p)::jsonb - 'updated_at')::text AS j
          FROM historical_place p
         WHERE p.created_from_source_record_id IN (SELECT source_record_id FROM legacy_sr)) q
UNION ALL
SELECT 'historical_place_name', count(*),
       encode(sha256(convert_to(coalesce(string_agg(j, '|' ORDER BY id), ''), 'UTF8')), 'hex')
  FROM (SELECT n.name_id AS id, (row_to_json(n)::jsonb - 'updated_at')::text AS j
          FROM historical_place_name n
         WHERE n.source_record_id IN (SELECT source_record_id FROM legacy_sr)) q
UNION ALL
SELECT 'historical_place_location', count(*),
       encode(sha256(convert_to(coalesce(string_agg(j, '|' ORDER BY id), ''), 'UTF8')), 'hex')
  FROM (SELECT l.location_id AS id,
               (row_to_json(l)::jsonb - 'updated_at'
                 -- geom 用 ST_AsEWKB 的十六进制参与比较；row_to_json 会把它变成 GeoJSON 文本
                 || jsonb_build_object('geom_ewkb', encode(ST_AsEWKB(l.geom), 'hex')))::text AS j
          FROM historical_place_location l
         WHERE l.source_record_id IN (SELECT source_record_id FROM legacy_sr)) q
UNION ALL
SELECT 'candidate_match', count(*),
       encode(sha256(convert_to(coalesce(string_agg(j, '|' ORDER BY id), ''), 'UTF8')), 'hex')
  FROM (SELECT c.candidate_id AS id, (row_to_json(c)::jsonb - 'updated_at')::text AS j
          FROM candidate_match c
         -- 既有候选没有 batch 列，用「旧批次最晚开始时间 + 1 分钟」作上界：
         -- 旧行必然在该窗口内落库，新行必然在之后，且不随重跑漂移。
         WHERE c.created_at <= (SELECT max(started_at) FROM import_batch WHERE batch_id <= :cutoff)
                               + interval '1 minute') q
UNION ALL
SELECT 'data_quality_issue', count(*),
       encode(sha256(convert_to(coalesce(string_agg(j, '|' ORDER BY id), ''), 'UTF8')), 'hex')
  FROM (SELECT d.issue_id AS id,
               (row_to_json(d)::jsonb - 'updated_at' - 'last_batch_id' - 'occurrence_count')::text AS j
          FROM data_quality_issue d
         WHERE d.first_batch_id <= :cutoff) q
UNION ALL
SELECT 'data_dataset', count(*),
       encode(sha256(convert_to(coalesce(string_agg(j, '|' ORDER BY id), ''), 'UTF8')), 'hex')
  FROM (SELECT ds.dataset_id AS id, (row_to_json(ds)::jsonb - 'updated_at')::text AS j
          FROM data_dataset ds
         WHERE ds.dataset_id <> 'pleiades_gis_4_1') q;
