package com.canvasofworldhistory.api.service;

import com.canvasofworldhistory.api.dto.Dtos;
import com.canvasofworldhistory.api.dto.PolityDtos;
import com.canvasofworldhistory.api.dto.Requests;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.namedparam.MapSqlParameterSource;
import org.springframework.jdbc.core.namedparam.NamedParameterJdbcTemplate;
import org.springframework.jdbc.support.GeneratedKeyHolder;
import org.springframework.jdbc.support.KeyHolder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 历史政权（展示用最小模型）读写。
 *
 * <p>定位：矩阵的行维度。这里只做「起个名字、归一个展示地区、可选存在区间」，
 * 不做疆域、不做继承、不按事件名称或坐标自动推断归属。
 */
@Service
public class PolityService {

    /** 展示地区：固定 10 个，顺序即界面展示顺序。 */
    public static final List<PolityDtos.Region> REGIONS = List.of(
            new PolityDtos.Region("east_asia", "东亚", 1),
            new PolityDtos.Region("central_asia", "中亚", 2),
            new PolityDtos.Region("south_asia", "南亚", 3),
            new PolityDtos.Region("southeast_asia", "东南亚", 4),
            new PolityDtos.Region("middle_east", "中东", 5),
            new PolityDtos.Region("europe", "欧洲", 6),
            new PolityDtos.Region("africa", "非洲", 7),
            new PolityDtos.Region("north_america", "北美洲", 8),
            new PolityDtos.Region("south_america", "南美洲", 9),
            new PolityDtos.Region("oceania", "大洋洲", 10));

    private static final Map<String, String> REGION_LABEL = new LinkedHashMap<>();
    private static final Map<String, Integer> REGION_ORDER = new LinkedHashMap<>();

    static {
        for (PolityDtos.Region r : REGIONS) {
            REGION_LABEL.put(r.code(), r.label());
            REGION_ORDER.put(r.code(), r.sortOrder());
        }
    }

    /** 状态枚举：requireEnum 的允许值写法与其余服务一致（SQL 列表形式，不能传逗号串）。 */
    private static final String RECORD_STATUS_SQL = "('staging','published','rejected')";
    private static final int MAX_PAGE_SIZE = 100;

    private final NamedParameterJdbcTemplate jdbc;

    public PolityService(NamedParameterJdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    static String label(String regionCode) {
        return REGION_LABEL.getOrDefault(regionCode, regionCode);
    }

    static int order(String regionCode) {
        return REGION_ORDER.getOrDefault(regionCode, 99);
    }

    static void requireRegion(String code) {
        if (code == null || !REGION_LABEL.containsKey(code)) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST,
                    "regionCode 非法（应为 " + String.join(" / ", REGION_LABEL.keySet()) + "）");
        }
    }

    // ================================================================ 查询
    public List<PolityDtos.Region> regions() {
        return REGIONS;
    }

    public Dtos.Page<PolityDtos.PolityHit> list(String keyword, String region, int page, int size) {
        int p = Math.max(1, page);
        int s = Math.min(Math.max(1, size), MAX_PAGE_SIZE);
        String kw = keyword == null ? "" : keyword.trim();
        String reg = region == null ? "" : region.trim();

        MapSqlParameterSource prm = new MapSqlParameterSource()
                .addValue("like", kw.isEmpty() ? null : "%" + kw + "%")
                .addValue("region", reg.isEmpty() ? null : reg)
                .addValue("limit", s)
                .addValue("offset", (p - 1) * s);

        // 注意：`:like IS NULL` / `:region IS NULL` 必须显式 CAST，否则 PostgreSQL 无法推断参数类型
        // （会报 "could not determine data type of parameter"）
        String where = """
                 WHERE (CAST(:like AS text) IS NULL OR po.name ILIKE :like)
                   AND (CAST(:region AS text) IS NULL OR po.region_code = :region)
                """;

        Long total = jdbc.queryForObject(
                "SELECT count(*) FROM historical_polity po" + where, prm, Long.class);
        long n = total == null ? 0 : total;
        if (n == 0) {
            return Dtos.Page.of(List.of(), p, s, 0);
        }

        List<PolityDtos.PolityHit> items = jdbc.query("""
                SELECT po.polity_id, po.name, po.region_code, po.start_year_astro, po.end_year_astro,
                       po.description, po.record_status,
                       (SELECT count(*) FROM event_polity ep WHERE ep.polity_id = po.polity_id) AS event_count
                  FROM historical_polity po
                """ + where + """
                 ORDER BY po.region_code, po.name, po.polity_id
                 LIMIT :limit OFFSET :offset
                """, prm, (rs, i) -> new PolityDtos.PolityHit(
                rs.getLong("polity_id"),
                rs.getString("name"),
                rs.getString("region_code"),
                label(rs.getString("region_code")),
                (Integer) rs.getObject("start_year_astro"),
                (Integer) rs.getObject("end_year_astro"),
                rs.getString("description"),
                rs.getString("record_status"),
                rs.getInt("event_count")));

        return Dtos.Page.of(items, p, s, n);
    }

    /** 单条读取（状态变更后回填用）。 */
    public PolityDtos.PolityHit get(long polityId) {
        return jdbc.query("""
                        SELECT po.polity_id, po.name, po.region_code, po.start_year_astro, po.end_year_astro,
                               po.description, po.record_status,
                               (SELECT count(*) FROM event_polity ep WHERE ep.polity_id = po.polity_id) AS event_count
                          FROM historical_polity po
                         WHERE po.polity_id = :id
                        """,
                new MapSqlParameterSource("id", polityId),
                (rs, i) -> new PolityDtos.PolityHit(
                        rs.getLong("polity_id"),
                        rs.getString("name"),
                        rs.getString("region_code"),
                        label(rs.getString("region_code")),
                        (Integer) rs.getObject("start_year_astro"),
                        (Integer) rs.getObject("end_year_astro"),
                        rs.getString("description"),
                        rs.getString("record_status"),
                        rs.getInt("event_count")))
                .stream().findFirst()
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "政权不存在：" + polityId));
    }

    // ================================================================ 创建
    @Transactional
    public PolityDtos.PolityHit create(Requests.PolityUpsert req) {
        String name = PersonService.requireText(req.name(), "name");
        String region = req.regionCode() == null ? "" : req.regionCode().trim();
        requireRegion(region);

        Integer start = req.startYearAstro();
        Integer end = req.endYearAstro();
        // V7：两端各自可选——只知起点或只知终点都是合法录入；都填时才校验顺序。
        if (start != null && end != null && start > end) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST,
                    "startYearAstro 不得晚于 endYearAstro（天文纪年整数比较）");
        }
        String status = req.recordStatus() == null
                ? "staging"
                : PersonService.requireEnum(req.recordStatus(), RECORD_STATUS_SQL, "recordStatus");

        MapSqlParameterSource prm = new MapSqlParameterSource()
                .addValue("name", name)
                .addValue("lang", PersonService.blankToNull(req.nameLang()))
                .addValue("region", region)
                .addValue("s", start)
                .addValue("e", end)
                .addValue("desc", PersonService.blankToNull(req.description()))
                .addValue("notes", PersonService.blankToNull(req.notes()))
                .addValue("status", status);

        KeyHolder keys = new GeneratedKeyHolder();
        jdbc.update("""
                INSERT INTO historical_polity
                       (name, name_lang, region_code, start_year_astro, end_year_astro,
                        description, notes, record_status, created_at, updated_at)
                VALUES (:name, :lang, :region, :s, :e, :desc, :notes, :status, now(), now())
                """, prm, keys, new String[]{"polity_id"});

        Number id = keys.getKey();
        if (id == null) {
            throw new ResponseStatusException(HttpStatus.INTERNAL_SERVER_ERROR, "政权创建失败：未取得主键");
        }
        return new PolityDtos.PolityHit(id.longValue(), name, region, label(region),
                start, end, PersonService.blankToNull(req.description()), status, 0);
    }

    // ================================================================ 状态
    /**
     * 变更政权状态（staging / published / rejected）。
     *
     * <p>规则：staging 与 published 都正常进入矩阵；rejected 只影响矩阵行，
     * 不删事件、不删关联、不影响地图与检索。这里不记录审核人，也不做审核流。
     */
    @Transactional
    public PolityDtos.PolityHit updateStatus(long polityId, String recordStatus) {
        if (recordStatus == null || recordStatus.isBlank()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "recordStatus 必填");
        }
        String status = PersonService.requireEnum(recordStatus.trim(),
                RECORD_STATUS_SQL, "recordStatus");
        int n = jdbc.update("""
                UPDATE historical_polity SET record_status = :s, updated_at = now()
                 WHERE polity_id = :id
                """, new MapSqlParameterSource().addValue("s", status).addValue("id", polityId));
        if (n == 0) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "政权不存在：" + polityId);
        }
        return get(polityId);
    }

    // ================================================================ 事件关联
    public List<PolityDtos.EventPolityRow> byEvent(long eventId) {
        requireEvent(eventId);
        return byEventUnchecked(eventId);
    }

    @Transactional
    public PolityDtos.EventPolityRow link(long eventId, Requests.EventPolityLink req) {
        requireEvent(eventId);
        if (req.polityId() == null) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "polityId 必填");
        }
        Map<String, Object> po = jdbc.query("""
                        SELECT name, region_code, record_status FROM historical_polity WHERE polity_id = :pid
                        """,
                new MapSqlParameterSource("pid", req.polityId()),
                (rs, i) -> {
                    Map<String, Object> m = new LinkedHashMap<>();
                    m.put("name", rs.getString("name"));
                    m.put("region", rs.getString("region_code"));
                    m.put("status", rs.getString("record_status"));
                    return m;
                })
                .stream().findFirst()
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.BAD_REQUEST, "政权不存在"));

        MapSqlParameterSource prm = new MapSqlParameterSource()
                .addValue("eid", eventId)
                .addValue("pid", req.polityId())
                .addValue("role", PersonService.blankToNull(req.role()))
                .addValue("note", PersonService.blankToNull(req.note()));

        KeyHolder keys = new GeneratedKeyHolder();
        jdbc.update("""
                INSERT INTO event_polity (event_id, polity_id, role, note, created_at, updated_at)
                VALUES (:eid, :pid, :role, :note, now(), now())
                """, prm, keys, new String[]{"event_polity_id"});
        Number id = keys.getKey();

        String region = String.valueOf(po.get("region"));
        return new PolityDtos.EventPolityRow(
                id == null ? 0 : id.longValue(), req.polityId(), String.valueOf(po.get("name")),
                region, label(region), String.valueOf(po.get("status")),
                PersonService.blankToNull(req.role()),
                PersonService.blankToNull(req.note()));
    }

    @Transactional
    public int unlink(long eventId, long linkId) {
        requireEvent(eventId);
        return jdbc.update("""
                DELETE FROM event_polity WHERE event_polity_id = :id AND event_id = :eid
                """, new MapSqlParameterSource().addValue("id", linkId).addValue("eid", eventId));
    }

    private void requireEvent(long eventId) {
        Integer ok = jdbc.query("SELECT 1 FROM event WHERE event_id = :id",
                new MapSqlParameterSource("id", eventId), rs -> rs.next() ? 1 : null);
        if (ok == null) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "事件不存在：" + eventId);
        }
    }

    /** 供事件详情内联使用（不重复做存在性检查）。 */
    List<PolityDtos.EventPolityRow> byEventUnchecked(long eventId) {
        return jdbc.query("""
                SELECT ep.event_polity_id, ep.polity_id, po.name, po.region_code, po.record_status,
                       ep.role, ep.note
                  FROM event_polity ep
                  JOIN historical_polity po ON po.polity_id = ep.polity_id
                 WHERE ep.event_id = :eid
                 ORDER BY po.region_code, po.name
                """, new MapSqlParameterSource("eid", eventId), (rs, i) -> new PolityDtos.EventPolityRow(
                rs.getLong("event_polity_id"),
                rs.getLong("polity_id"),
                rs.getString("name"),
                rs.getString("region_code"),
                label(rs.getString("region_code")),
                rs.getString("record_status"),
                rs.getString("role"),
                rs.getString("note")));
    }
}
