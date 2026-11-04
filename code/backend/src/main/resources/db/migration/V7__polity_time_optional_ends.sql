-- ==========================================================================
-- V7：历史政权存在区间改为「任意端点可选」
--
-- 背景（M3 封存轮）：V6 的 ck_polity_time_pair 要求起始年与结束年**同时填写或
-- 同时留空**。实际录入时大量政权只知道建国年（如「秦，前 221 年」）或只知道
-- 灭亡年（如「新巴比伦，前 539 年亡」），强制成对填写会逼出假数据。
--
-- 本迁移只做一件事：放开「必须成对」，保留「都填时必须 start <= end」。
--   允许：只填起始年 / 只填结束年 / 两者都空 / 两者都填；
--   禁止：两者都填且 start > end。
--
-- 边界：
--   1. 不修改 V6 及 V1～V5 的任何脚本，只在其上叠加约束变更；
--   2. 不改列类型、不改数据、不加新列、不动矩阵过滤逻辑（矩阵只看事件时间）；
--   3. 只在测试库执行；正式库保持 V5，本轮不迁移。
-- 注：Flyway 已在事务中执行本脚本，故不再显式 BEGIN/COMMIT。
-- ==========================================================================

ALTER TABLE historical_polity
    DROP CONSTRAINT IF EXISTS ck_polity_time_pair;

-- 旧约束的表达式在「只有一端」时求值为 NULL（CHECK 视为通过），但语义上仍写成
-- 「成对」条件，容易误导后来者。这里显式重建为「缺失即跳过比较」的写法。
ALTER TABLE historical_polity
    DROP CONSTRAINT IF EXISTS ck_polity_time_order;

ALTER TABLE historical_polity
    ADD CONSTRAINT ck_polity_time_order CHECK (
        start_year_astro IS NULL
        OR end_year_astro IS NULL
        OR start_year_astro <= end_year_astro);

COMMENT ON COLUMN historical_polity.start_year_astro IS
    '可选的存在起始年（天文学纪年）；可只填起始年，也可两端都空；不与结束年强制配对';
COMMENT ON COLUMN historical_polity.end_year_astro IS
    '可选的存在结束年（天文学纪年）；可只填结束年；两端都填时必须 start <= end';
COMMENT ON CONSTRAINT ck_polity_time_order ON historical_polity IS
    '存在区间顺序：任一端为空时不比较；两端都填时 start_year_astro <= end_year_astro';
