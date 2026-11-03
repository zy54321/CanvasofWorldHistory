-- =============================================================================
-- V3：三个正式派生视图
-- 权威依据：CORE_DATA_MODEL_V2.1.1.md §5.10（逐字落地，不改语义）
--   §5.10.1 v_place_evidence（11 列，canonical 由外层窗口定序实际计算）
--   §5.10.2 v_place_liveness（对外 7 列，liveness 8 值）
--   §5.10.3 v_place_time_span（10 列，过滤 record_status <> 'rejected' AND sr.is_active）
--
-- ⛔ 施工纪律：
--   - 时间视图的过滤条件是 <> 'rejected'，不是 = 'published'；
--     照 V2.1 旧口径施工会让 19,039 个地点的时间跨度全部为 NULL（§5.10.3 修正说明）。
--   - v_place_evidence 的定序键 duplicate_ordinal / external_id 必须回连 source_record，
--     它们不是该视图的列（§5.10.4，F-11 原缺陷）。
-- =============================================================================

-- -----------------------------------------------------------------------------
-- §5.10.1 v_place_evidence（11 列）
-- -----------------------------------------------------------------------------
CREATE VIEW v_place_evidence AS
SELECT u.place_id,
       u.source_record_id,
       u.evidence_role,
       u.source_is_active,
       u.source_inactive_reason,
       u.child_table,
       u.child_row_id,
       u.child_record_status,
       u.child_rejected_by,
       u.is_anchor,
       (row_number() OVER (
          PARTITION BY u.place_id
          ORDER BY (u.source_is_active IS TRUE
                    AND u.child_record_status IS DISTINCT FROM 'rejected') DESC,  -- ⓿ 有效证据优先
                   (u.evidence_role = 'creator') DESC,                            -- ① 创建记录优先
                   sr.duplicate_ordinal ASC NULLS LAST,                           -- ②
                   sr.external_id       ASC NULLS LAST,                           -- ③（MCGD 即 NameID 最小）
                   u.source_record_id   ASC,                                      -- ④
                   coalesce(u.child_row_id, 0) ASC                                -- ⑤
        ) = 1) AS is_canonical_row
FROM (
    -- ① 创建证据（白名单见 §5.5.5）
    SELECT p.place_id,
           sr.source_record_id,
           'creator'::text              AS evidence_role,
           sr.is_active                 AS source_is_active,
           sr.inactive_reason           AS source_inactive_reason,
           NULL::text                   AS child_table,
           NULL::bigint                 AS child_row_id,
           NULL::text                   AS child_record_status,
           NULL::text                   AS child_rejected_by,
           (sr.source_record_id = p.created_from_source_record_id) AS is_anchor
    FROM historical_place p
    JOIN source_record sr
      ON sr.dataset_id = p.dataset_id
     AND (   (p.grain_key = sr.external_id        AND sr.record_scope = 'place')
          OR (p.grain_key = sr.parent_external_id
              AND sr.record_scope IN ('name', 'location')
              AND sr.dataset_id IN (SELECT dataset_id FROM data_dataset
                                    WHERE place_grain = 'per_parent_external_id')) )
    UNION ALL
    -- ② 名称行
    SELECT n.place_id, n.source_record_id, 'name',
           sr.is_active, sr.inactive_reason,
           'name', n.name_id, n.record_status, n.rejected_by,
           FALSE
    FROM historical_place_name n LEFT JOIN source_record sr USING (source_record_id)
    UNION ALL
    -- ③ 位置行
    SELECT l.place_id, l.source_record_id, 'location',
           sr.is_active, sr.inactive_reason,
           'location', l.location_id, l.record_status, l.rejected_by,
           FALSE
    FROM historical_place_location l LEFT JOIN source_record sr USING (source_record_id)
) u
LEFT JOIN source_record sr ON sr.source_record_id = u.source_record_id;

COMMENT ON VIEW v_place_evidence IS '地点证据展开（11 列）。有效证据 ⇔ source_is_active IS TRUE AND child_record_status IS DISTINCT FROM ''rejected''。is_canonical_row 为定序第一行，仅用于追溯，不代表该行有效。';

-- -----------------------------------------------------------------------------
-- §5.10.2 v_place_liveness（对外 7 列；liveness 8 值）
-- -----------------------------------------------------------------------------
CREATE VIEW v_place_liveness AS
WITH ev AS (
  SELECT e.place_id,
         bool_or(e.source_is_active IS TRUE
                 AND e.child_record_status IS DISTINCT FROM 'rejected')          AS has_valid,
         count(*) FILTER (WHERE e.child_rejected_by = 'manual')                  AS manual_rejected_rows,
         count(DISTINCT e.source_inactive_reason)
           FILTER (WHERE NOT e.source_is_active)                                 AS distinct_inactive_reasons,
         -- ⚠️ 施工修正（唯一一处对设计 SQL 字面的改动，语义不变）：
         --   设计原文写 (array_agg(...) ... END) ) FILTER (WHERE ...)
         --   —— 外层括号在 FILTER 之前已闭合，PG 报 syntax error at or near "FILTER"（SQLSTATE 42601）。
         --   FILTER 是函数调用的限定子句，必须写在括号内。此处把 FILTER 移入括号，
         --   聚合、定序键、过滤条件三者与设计逐字一致，仅调整括号位置以使其可执行。
         (array_agg(e.source_inactive_reason ORDER BY
              sr.inactive_at DESC NULLS LAST, sr.inactive_in_batch_id DESC NULLS LAST,
              CASE e.source_inactive_reason WHEN 'batch_rolled_back'    THEN 1
                                            WHEN 'duplicate_quarantine' THEN 2
                                            WHEN 'source_absent'        THEN 3 END)
          FILTER (WHERE NOT e.source_is_active))                                 AS reasons
  FROM v_place_evidence e
   LEFT JOIN source_record sr ON sr.source_record_id = e.source_record_id
  GROUP BY e.place_id
)
SELECT p.place_id, p.dataset_id, p.grain_key, p.record_status,
       coalesce(ev.manual_rejected_rows, 0)       AS manual_rejected_rows,
       coalesce(ev.distinct_inactive_reasons, 0)  AS distinct_inactive_reasons,
       CASE
         WHEN p.record_status = 'merged'                     THEN 'merged'
         WHEN p.created_by    = 'manual'                     THEN 'manual'
         WHEN coalesce(ev.has_valid, false)                  THEN 'active'
         WHEN coalesce(ev.distinct_inactive_reasons, 0) > 1  THEN 'mixed_inactive'
         WHEN coalesce(ev.distinct_inactive_reasons, 0) = 1  THEN
              CASE ev.reasons[1] WHEN 'source_absent'        THEN 'all_sources_absent'
                                 WHEN 'batch_rolled_back'    THEN 'all_sources_rolled_back'
                                 WHEN 'duplicate_quarantine' THEN 'quarantined_only' END
         ELSE 'orphaned'
       END AS liveness
FROM historical_place p LEFT JOIN ev ON ev.place_id = p.place_id;

COMMENT ON VIEW v_place_liveness IS '存活判定（对外 7 列）。liveness 8 值：merged/manual/active/mixed_inactive/all_sources_absent/all_sources_rolled_back/quarantined_only/orphaned。rejected ⟺ liveness ∈ {all_sources_absent, all_sources_rolled_back, quarantined_only, mixed_inactive}。has_valid / reasons 是 CTE 中间量，不对外。';

-- -----------------------------------------------------------------------------
-- §5.10.3 v_place_time_span（10 列）
-- -----------------------------------------------------------------------------
CREATE VIEW v_place_time_span AS
WITH child AS (
    SELECT place_id, source_record_id,
           valid_from_year_astro AS f, valid_to_year_astro AS t, record_status
      FROM historical_place_name
    UNION ALL
    SELECT place_id, source_record_id,
           valid_from_year_astro,     valid_to_year_astro,      record_status
      FROM historical_place_location
    -- 刻意不 UNION 任何 edge/connection 来源：connection 的年份是两个地点之间关系的存续期，
    -- 不是该地点存在到 X 年（§6.3 四条证据链）。
), eff AS (
    SELECT c.*, sr.is_active
      FROM child c
      JOIN source_record sr ON sr.source_record_id = c.source_record_id
     WHERE c.record_status <> 'rejected'
       AND sr.is_active
)
SELECT p.place_id,
       MIN(e.f) FILTER (WHERE e.f IS NOT NULL)                    AS span_from_astro,
       MAX(e.t) FILTER (WHERE e.t IS NOT NULL)                    AS span_to_astro,
       count(*) FILTER (WHERE e.f IS NOT NULL)                    AS from_evidence_rows,
       count(*) FILTER (WHERE e.t IS NOT NULL)                    AS to_evidence_rows,
       count(*) FILTER (WHERE e.record_status = 'staging')        AS staging_evidence_rows,
       count(e.place_id)                                          AS valid_child_rows,
       (SELECT count(*) FROM child c2 WHERE c2.place_id = p.place_id)
                                                                  AS child_rows_total,
       CASE
         WHEN count(*) FILTER (WHERE (e.f IS NOT NULL OR e.t IS NOT NULL)) = 0
              THEN 'no_evidence'
         WHEN MIN(e.f) IS NOT NULL AND MAX(e.t) IS NOT NULL AND MIN(e.f) = MAX(e.t)
              THEN 'single_point'
         ELSE 'envelope_of_name_and_location_rows'
       END                                                        AS derivation_kind,
       (   (SELECT count(*) FROM child c3 WHERE c3.place_id = p.place_id) > 0
       AND count(e.place_id) = 0 )                                AS all_children_rejected
FROM historical_place p
LEFT JOIN eff e ON e.place_id = p.place_id
GROUP BY p.place_id;

COMMENT ON VIEW v_place_time_span IS '地点时间跨度（10 列），只聚合 name + location 有效子行。valid_child_rows 用 count(e.place_id) 而非裸 count(*)：LEFT JOIN 无匹配时裸 count(*) 恒为 1，会让 all_children_rejected 永不为真（A-2 修正）。';
