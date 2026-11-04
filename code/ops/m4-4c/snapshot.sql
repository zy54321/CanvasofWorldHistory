-- M4-4c · 验收库全量快照（逐表 sha256 + 行数），用于"测试前后一致"
-- 口径与 M4-4b 的 fingerprint.sql 相同：扣掉按设计会变的列（updated_at / last_batch_id /
-- occurrence_count），几何用 ST_AsEWKB 的十六进制参与比较。
\pset pager off
SELECT 'source_record' AS tbl, count(*) AS rows,
       encode(sha256(convert_to(coalesce(string_agg(j,'|' ORDER BY id),''),'UTF8')),'hex') AS sha256
  FROM (SELECT source_record_id AS id, (row_to_json(s)::jsonb - 'last_batch_id')::text AS j
          FROM source_record s) q
UNION ALL
SELECT 'historical_place', count(*), encode(sha256(convert_to(coalesce(string_agg(j,'|' ORDER BY id),''),'UTF8')),'hex')
  FROM (SELECT place_id AS id, (row_to_json(p)::jsonb - 'updated_at')::text AS j FROM historical_place p) q
UNION ALL
SELECT 'historical_place_name', count(*), encode(sha256(convert_to(coalesce(string_agg(j,'|' ORDER BY id),''),'UTF8')),'hex')
  FROM (SELECT name_id AS id, (row_to_json(n)::jsonb - 'updated_at')::text AS j FROM historical_place_name n) q
UNION ALL
SELECT 'historical_place_location', count(*), encode(sha256(convert_to(coalesce(string_agg(j,'|' ORDER BY id),''),'UTF8')),'hex')
  FROM (SELECT location_id AS id,
               (row_to_json(l)::jsonb - 'updated_at'
                 || jsonb_build_object('geom_ewkb', encode(ST_AsEWKB(l.geom),'hex')))::text AS j
          FROM historical_place_location l) q
UNION ALL
SELECT 'candidate_match', count(*), encode(sha256(convert_to(coalesce(string_agg(j,'|' ORDER BY id),''),'UTF8')),'hex')
  FROM (SELECT candidate_id AS id, (row_to_json(c)::jsonb - 'updated_at')::text AS j FROM candidate_match c) q
UNION ALL
SELECT 'data_quality_issue', count(*), encode(sha256(convert_to(coalesce(string_agg(j,'|' ORDER BY id),''),'UTF8')),'hex')
  FROM (SELECT issue_id AS id, (row_to_json(d)::jsonb - 'updated_at' - 'last_batch_id' - 'occurrence_count')::text AS j
          FROM data_quality_issue d) q
UNION ALL
SELECT 'data_dataset', count(*), encode(sha256(convert_to(coalesce(string_agg(j,'|' ORDER BY id),''),'UTF8')),'hex')
  FROM (SELECT dataset_id AS id, (row_to_json(ds)::jsonb - 'updated_at')::text AS j FROM data_dataset ds) q;
