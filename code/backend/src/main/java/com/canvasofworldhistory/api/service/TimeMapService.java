package com.canvasofworldhistory.api.service;

import com.canvasofworldhistory.api.dto.PolityDtos;
import org.springframework.dao.DataAccessException;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.namedparam.MapSqlParameterSource;
import org.springframework.jdbc.core.namedparam.NamedParameterJdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * M3 时间—地图联动查询。
 *
 * <p>两条查询共用**同一套时间规则**（这里只有一份实现）：
 * <ul>
 *   <li>事件时间用天文学纪年整数，区间端点包含式；</li>
 *   <li>事件与窗口相交 = {@code start <= windowEnd && coalesce(end, start) >= windowStart}；</li>
 *   <li>只知起点（end 为空）的事件按「起点单年」参与窗口匹配，<b>不</b>向未来无限延伸，
 *       否则一个「始于前 500 年」的事件会出现在此后每一个窗口里；</li>
 *   <li>起点未知的事件不进入任何具体时间窗口（地图与矩阵都不显示），但仍保留在内容管理中。</li>
 * </ul>
 */
@Service
public class TimeMapService {

    private static final int MAX_MAP_LIMIT = 3000;
    private static final int DEFAULT_MAP_LIMIT = 1200;
    private static final int MAX_COLUMNS = 40;
    private static final int MATRIX_ROW_LIMIT = 6000;

    private final NamedParameterJdbcTemplate jdbc;

    public TimeMapService(NamedParameterJdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public static void requireWindow(Integer from, Integer to) {
        if (from == null || to == null) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "from / to 必填（天文学纪年整数）");
        }
        if (from > to) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST,
                    "from 不得晚于 to（天文学纪年整数比较，公元前为 0 或负数）");
        }
    }

    /** 时间窗口的简短标签：公元前为「前500」，公元后为「500」。 */
    static String shortYear(int astro) {
        return astro <= 0 ? "前" + (1 - astro) : String.valueOf(astro);
    }

    // ================================================================ 地图
    /**
     * 按「时间窗口 ∩ 地图视野」查询事件标记，一个（事件 × 地点）一条。
     *
     * <p>坐标约束沿用 M1：geom 非空、坐标系置信度不为 unknown、地点与位置均未被否决、
     * 地点未被合并。未知坐标不生成假点。
     */
    public Map<String, Object> mapFeatures(double west, double south, double east, double north,
                                           int from, int to, Integer limit) {
        if (!(west < east) || !(south < north)) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "bbox 非法：需要 west<east 且 south<north");
        }
        int lim = limit == null ? DEFAULT_MAP_LIMIT : Math.min(Math.max(1, limit), MAX_MAP_LIMIT);

        MapSqlParameterSource prm = new MapSqlParameterSource()
                .addValue("w", west).addValue("s", south).addValue("e", east).addValue("n", north)
                .addValue("from", from).addValue("to", to).addValue("lim", lim);

        String cte = """
                WITH hit AS (
                    SELECT e.event_id, e.title, e.start_year_astro, e.end_year_astro, e.time_precision,
                           e.event_type, pl.place_id, pl.canonical_name AS place_name,
                           epl.location_role, l.location_id,
                           ST_X(l.geom) AS lon, ST_Y(l.geom) AS lat,
                           row_number() OVER (PARTITION BY e.event_id, pl.place_id
                                              ORDER BY l.location_id) AS rn
                      FROM event e
                      JOIN event_place epl ON epl.event_id = e.event_id
                      JOIN historical_place pl ON pl.place_id = epl.place_id
                      JOIN historical_place_location l ON l.place_id = pl.place_id
                      LEFT JOIN source_record sr ON sr.source_record_id = l.source_record_id
                     WHERE e.record_status <> 'rejected'
                       AND pl.record_status <> 'rejected'
                       AND pl.merged_into_place_id IS NULL
                       AND l.record_status <> 'rejected'
                       AND l.geom IS NOT NULL
                       AND l.crs_confidence <> 'unknown'
                       AND (sr.source_record_id IS NULL OR sr.is_active)
                       AND e.start_year_astro IS NOT NULL
                       AND e.start_year_astro <= :to
                       AND COALESCE(e.end_year_astro, e.start_year_astro) >= :from
                       AND l.geom && ST_MakeEnvelope(:w, :s, :e, :n, 4326)
                )
                """;

        Long total = jdbc.queryForObject(cte + "SELECT count(*) FROM hit WHERE rn = 1", prm, Long.class);
        int n = total == null ? 0 : total.intValue();

        List<Map<String, Object>> rows = jdbc.query(cte + """
                SELECT event_id, title, start_year_astro, end_year_astro, time_precision, event_type,
                       place_id, place_name, location_role, lon, lat
                  FROM hit WHERE rn = 1
                 ORDER BY md5(event_id::text || ':' || place_id::text)
                 LIMIT :lim
                """, prm, (rs, i) -> {
            Map<String, Object> p = new LinkedHashMap<>();
            p.put("eventId", rs.getLong("event_id"));
            p.put("title", rs.getString("title"));
            p.put("startYearAstro", rs.getObject("start_year_astro"));
            p.put("endYearAstro", rs.getObject("end_year_astro"));
            p.put("timePrecision", rs.getString("time_precision"));
            p.put("eventType", rs.getString("event_type"));
            p.put("placeId", rs.getLong("place_id"));
            p.put("placeName", rs.getString("place_name"));
            p.put("locationRole", rs.getString("location_role"));
            Map<String, Object> f = new LinkedHashMap<>();
            f.put("type", "Feature");
            f.put("properties", p);
            f.put("geometry", Map.of("type", "Point",
                    "coordinates", List.of(rs.getDouble("lon"), rs.getDouble("lat"))));
            return f;
        });

        Integer unknownTime = jdbc.queryForObject(
                "SELECT count(*) FROM event WHERE record_status <> 'rejected' AND start_year_astro IS NULL",
                new MapSqlParameterSource(), Integer.class);

        Map<String, Object> fc = new LinkedHashMap<>();
        fc.put("type", "FeatureCollection");
        fc.put("features", rows);
        fc.put("meta", new PolityDtos.EventMapMeta(
                from, to, rows.size(), n, lim, n > rows.size(),
                unknownTime == null ? 0 : unknownTime,
                "只含时间窗口内的已关联地点事件；坐标系未知或已被否决的位置不生成标记"));
        return fc;
    }

    // ================================================================ 矩阵
    /**
     * 历史时空矩阵：按地区 → 政权 → 时间段分组。
     *
     * @param from   第一列起始年（天文学纪年）
     * @param step   每列年数（1 / 10 / 100）
     * @param count  本次返回的列数
     * @param offset 从 from 起跳过的列数（横向滚动加载更多时使用）
     */
    public PolityDtos.MatrixResponse matrix(int from, int step, int count, int offset, String region) {
        if (!List.of(1, 10, 100).contains(step)) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "step 只允许 1 / 10 / 100");
        }
        int c = Math.min(Math.max(1, count), MAX_COLUMNS);
        int off = Math.max(0, offset);
        int winFrom = from + off * step;
        int winTo = winFrom + c * step - 1;

        try {
            return matrix0(from, step, c, off, winFrom, winTo, region);
        } catch (DataAccessException ex) {
            // 该库还没执行 V6（政权模型未建）：不抛 500，返回空矩阵并说明原因，
            // 让只读的正式实例（当前停在 V5）仍能正常打开界面。
            if (isMissingPolityTable(ex)) {
                return emptyMatrix(from, step, off, c, winFrom, region,
                        "本库尚未执行 V6 迁移（historical_polity 不存在），矩阵暂无数据；"
                                + "请在该库执行 Flyway migrate 后重试");
            }
            throw ex;
        }
    }

    private static boolean isMissingPolityTable(Throwable ex) {
        for (Throwable t = ex; t != null; t = t.getCause()) {
            if (t instanceof java.sql.SQLException sql
                    && ("42P01".equals(sql.getSQLState()) || "42703".equals(sql.getSQLState()))) {
                String msg = String.valueOf(sql.getMessage());
                return msg.contains("historical_polity") || msg.contains("event_polity");
            }
        }
        return false;
    }

    /** 没有政权模型时的空矩阵（结构与正常响应一致，前端无需特判）。 */
    private PolityDtos.MatrixResponse emptyMatrix(int from, int step, int off, int c,
                                                  int winFrom, String region, String note) {
        List<PolityDtos.MatrixColumn> columns = new java.util.ArrayList<>(c);
        for (int i = 0; i < c; i++) {
            int s = winFrom + i * step;
            columns.add(new PolityDtos.MatrixColumn(off + i, s, s + step - 1, shortYear(s)));
        }
        List<PolityDtos.MatrixRegion> regions = new java.util.ArrayList<>();
        for (PolityDtos.Region rg : PolityService.REGIONS) {
            if (region != null && !region.isBlank() && !region.trim().equals(rg.code())) {
                continue;
            }
            regions.add(new PolityDtos.MatrixRegion(rg.code(), rg.label(), rg.sortOrder(),
                    0, 0, List.of()));
        }
        return new PolityDtos.MatrixResponse(from, step, off, c, columns, regions,
                0, 0, false, note);
    }

    private PolityDtos.MatrixResponse matrix0(int from, int step, int c, int off,
                                              int winFrom, int winTo, String region) {

        // 列索引用**绝对列号**（off + i）：前端横向滚动追加分页时，新旧列的索引天然连续
        List<PolityDtos.MatrixColumn> columns = new ArrayList<>(c);
        for (int i = 0; i < c; i++) {
            int s = winFrom + i * step;
            columns.add(new PolityDtos.MatrixColumn(off + i, s, s + step - 1, shortYear(s)));
        }

        MapSqlParameterSource prm = new MapSqlParameterSource()
                .addValue("winFrom", winFrom).addValue("winTo", winTo)
                .addValue("lim", MATRIX_ROW_LIMIT);

        // 一个（事件 × 政权）一行；同一事件关联多个政权时自然出现在多行
        List<Map<String, Object>> rows = jdbc.query("""
                SELECT e.event_id, e.title, e.start_year_astro, e.end_year_astro, e.time_precision,
                       e.event_type, po.polity_id, po.name, po.region_code,
                       po.start_year_astro AS po_start, po.end_year_astro AS po_end
                  FROM event e
                  JOIN event_polity ep ON ep.event_id = e.event_id
                  JOIN historical_polity po ON po.polity_id = ep.polity_id
                 WHERE e.record_status <> 'rejected'
                   AND po.record_status <> 'rejected'
                   AND e.start_year_astro IS NOT NULL
                   AND e.start_year_astro <= :winTo
                   AND COALESCE(e.end_year_astro, e.start_year_astro) >= :winFrom
                 ORDER BY po.region_code, po.name, e.start_year_astro, e.event_id
                 LIMIT :lim
                """, prm, (rs, i) -> {
            Map<String, Object> m = new LinkedHashMap<>();
            m.put("eventId", rs.getLong("event_id"));
            m.put("title", rs.getString("title"));
            m.put("start", rs.getObject("start_year_astro"));
            m.put("end", rs.getObject("end_year_astro"));
            m.put("precision", rs.getString("time_precision"));
            m.put("type", rs.getString("event_type"));
            m.put("polityId", rs.getLong("polity_id"));
            m.put("polityName", rs.getString("name"));
            m.put("region", rs.getString("region_code"));
            m.put("poStart", rs.getObject("po_start"));
            m.put("poEnd", rs.getObject("po_end"));
            return m;
        });

        // 政权 → 列 → 事件（LinkedHashMap 保持稳定顺序）
        Map<Long, PolityDtos.MatrixPolity> polityRows = new LinkedHashMap<>();
        Map<Long, Map<Integer, List<PolityDtos.MatrixEvent>>> cellMap = new LinkedHashMap<>();
        Map<Long, Integer> polityEventCount = new LinkedHashMap<>();
        Map<Long, String> polityRegion = new LinkedHashMap<>();
        for (Map<String, Object> r : rows) {
            long pid = ((Number) r.get("polityId")).longValue();
            int start = ((Number) r.get("start")).intValue();
            Integer endObj = (Integer) r.get("end");
            int effEnd = endObj == null ? start : endObj;

            polityRegion.putIfAbsent(pid, (String) r.get("region"));
            polityRows.computeIfAbsent(pid, k -> new PolityDtos.MatrixPolity(
                    pid, (String) r.get("polityName"), (Integer) r.get("poStart"),
                    (Integer) r.get("poEnd"), 0, new ArrayList<>()));

            for (PolityDtos.MatrixColumn col : columns) {
                if (start <= col.endYearAstro() && effEnd >= col.startYearAstro()) {
                    cellMap.computeIfAbsent(pid, k -> new LinkedHashMap<>())
                            .computeIfAbsent(col.index(), k -> new ArrayList<>())
                            .add(new PolityDtos.MatrixEvent(
                                    ((Number) r.get("eventId")).longValue(),
                                    (String) r.get("title"),
                                    start, endObj,
                                    (String) r.get("precision"),
                                    (String) r.get("type")));
                    polityEventCount.merge(pid, 1, Integer::sum);
                }
            }
        }

        // 组装地区（固定 10 个，无内容的地区 polities 为空）
        Map<String, List<PolityDtos.MatrixPolity>> byRegion = new LinkedHashMap<>();
        for (Map.Entry<Long, PolityDtos.MatrixPolity> e : polityRows.entrySet()) {
            long pid = e.getKey();
            String regionCode = polityRegion.get(pid);
            Map<Integer, List<PolityDtos.MatrixEvent>> cells = cellMap.getOrDefault(pid, Map.of());
            List<PolityDtos.MatrixCell> cellList = new ArrayList<>();
            cells.entrySet().stream().sorted(Map.Entry.comparingByKey())
                    .forEach(x -> cellList.add(new PolityDtos.MatrixCell(x.getKey(), x.getValue())));
            PolityDtos.MatrixPolity base = e.getValue();
            PolityDtos.MatrixPolity withCells = new PolityDtos.MatrixPolity(
                    base.polityId(), base.name(), base.startYearAstro(), base.endYearAstro(),
                    polityEventCount.getOrDefault(pid, 0), cellList);
            byRegion.computeIfAbsent(regionCode == null ? "east_asia" : regionCode,
                    k -> new ArrayList<>()).add(withCells);
        }

        List<String> regionFilter = region == null || region.isBlank()
                ? List.of() : List.of(region.trim());
        List<PolityDtos.MatrixRegion> regions = new ArrayList<>();
        for (PolityDtos.Region rg : PolityService.REGIONS) {
            if (!regionFilter.isEmpty() && !regionFilter.contains(rg.code())) {
                continue;
            }
            // 注意：byRegion 的默认值是 List.of()（不可变），必须复制后再排序
            List<PolityDtos.MatrixPolity> list =
                    new ArrayList<>(byRegion.getOrDefault(rg.code(), List.of()));
            list.sort(Comparator.comparing(PolityDtos.MatrixPolity::name));
            int ev = list.stream().mapToInt(PolityDtos.MatrixPolity::eventCount).sum();
            regions.add(new PolityDtos.MatrixRegion(rg.code(), rg.label(), rg.sortOrder(),
                    list.size(), ev, list));
        }

        int eventsInWindow = countEvents(winFrom, winTo, false);
        int unlinked = countEvents(winFrom, winTo, true);

        return new PolityDtos.MatrixResponse(
                from, step, off, c, columns, regions, eventsInWindow, unlinked,
                rows.size() >= MATRIX_ROW_LIMIT,
                "只显示当前窗口内有事件的政权；未知时间事件不进入矩阵");
    }

    /** 统计窗口内事件数；onlyUnlinked=true 时只统计没有任何政权关联的事件。 */
    private int countEvents(int winFrom, int winTo, boolean onlyUnlinked) {
        String sql = """
                SELECT count(*) FROM event e
                 WHERE e.record_status <> 'rejected'
                   AND e.start_year_astro IS NOT NULL
                   AND e.start_year_astro <= :winTo
                   AND COALESCE(e.end_year_astro, e.start_year_astro) >= :winFrom
                """ + (onlyUnlinked
                ? " AND NOT EXISTS (SELECT 1 FROM event_polity ep WHERE ep.event_id = e.event_id)"
                : "");
        Integer v = jdbc.queryForObject(sql, new MapSqlParameterSource()
                .addValue("winFrom", winFrom).addValue("winTo", winTo), Integer.class);
        return v == null ? 0 : v;
    }
}
