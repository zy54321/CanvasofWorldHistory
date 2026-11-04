-- V10：补齐两处"按 place_id 取子行"的缺失索引
--
-- 证据（P0/V1.0 施工时用 EXPLAIN ANALYZE 实测，2026-11-04）：
--   · historical_place_name 上**没有** place_id 的完整索引：
--     唯一的 uq_hpn_manual_name 是 `WHERE source_record_id IS NULL` 的部分索引，
--     只能覆盖人工录入行，导入的 84,554 条名称完全用不上；
--     于是"地图上给 400 个地点各取一个别名"变成 400 次全表扫描，
--     /places/map 在罗马视野从 ~40 ms 涨到 1.4 s。
--   · historical_place_location 同样没有 place_id 索引：
--     详情页、v_place_time_span、以及任何"按地点取位置"的查询都走顺序扫。
--
-- 这两个索引不改变任何业务语义，只补访问路径；不新增表、列或约束。
-- 名称的检索（ILIKE）另有 ivfflat/pg_trgm 方案，本轮不动 —— 没有证据表明它是瓶颈。

CREATE INDEX IF NOT EXISTS ix_hpn_place
    ON historical_place_name (place_id);

CREATE INDEX IF NOT EXISTS ix_hpl_place
    ON historical_place_location (place_id);

COMMENT ON INDEX ix_hpn_place IS
    'V10：按地点取名称子行。缺它时地图别名回退与详情名称列表退化为全表扫描（实测 400 次 seq scan / 1.4 s）。';
COMMENT ON INDEX ix_hpl_place IS
    'V10：按地点取位置子行。详情页与 v_place_time_span 的常用路径。';
