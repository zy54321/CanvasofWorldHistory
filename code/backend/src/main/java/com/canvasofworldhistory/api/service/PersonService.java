package com.canvasofworldhistory.api.service;

import com.canvasofworldhistory.api.dto.PersonDtos;
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
import java.util.Optional;

/**
 * 人物相关读写。
 *
 * 口径：
 *  - 时间字段全部是天文学纪年整数，原样存取，不做 BCE/CE 标签换算。
 *  - 校验以数据库 V4 约束为准（33 条 CHECK + 唯一索引），服务层只做「能给出更清楚报错」的前置校验；
 *    最终仍由数据库兜底，避免两套规则漂移。
 *  - 人物被删时，名称 / 事件关联 / 地点关联由数据库 ON DELETE CASCADE 清除；地点本体不受影响。
 */
@Service
public class PersonService {

    private static final int MAX_PAGE_SIZE = 100;
    private static final int MAX_CHILD_ROWS = 500;

    private static final String PRECISIONS = "('exact','approximate','range','unknown')";
    private static final String NAME_TYPES =
            "('primary','alternate','transliteration','historical','courtesy','art','posthumous','pseudonym')";
    private static final String RECORD_STATUS = "('staging','published','rejected')";

    private final NamedParameterJdbcTemplate jdbc;

    public PersonService(NamedParameterJdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    // ================================================================ 列表 / 搜索
    public com.canvasofworldhistory.api.dto.Dtos.Page<PersonDtos.PersonHit> search(
            String keyword, int page, int size) {
        int p = Math.max(1, page);
        int s = Math.min(Math.max(1, size), MAX_PAGE_SIZE);
        String kw = keyword == null ? "" : keyword.trim();
        String like = kw.isEmpty() ? null : "%" + kw + "%";

        MapSqlParameterSource prm = new MapSqlParameterSource()
                .addValue("like", like)
                .addValue("limit", s)
                .addValue("offset", (p - 1) * s);

        String where = like == null ? "" : """
                 WHERE p.canonical_name ILIKE :like
                    OR EXISTS (SELECT 1 FROM person_name n
                                WHERE n.person_id = p.person_id AND n.name_text ILIKE :like)
                """;

        Long total = jdbc.queryForObject("SELECT count(*) FROM person p" + where, prm, Long.class);
        long n = total == null ? 0 : total;
        if (n == 0) {
            return com.canvasofworldhistory.api.dto.Dtos.Page.of(List.of(), p, s, 0);
        }

        String sql = """
                SELECT p.person_id, p.canonical_name, p.canonical_name_lang, p.description,
                       p.birth_year_astro, p.birth_precision, p.death_year_astro, p.death_precision,
                       p.record_status,
                       (SELECT count(*) FROM person_name n WHERE n.person_id = p.person_id) AS name_count,
                       (SELECT count(*) FROM event_person ep WHERE ep.person_id = p.person_id) AS event_count,
                       (SELECT count(*) FROM person_place pp WHERE pp.person_id = p.person_id) AS place_count
                  FROM person p
                """ + where + """
                 ORDER BY (p.canonical_name ILIKE coalesce(:like, '')) DESC,
                          p.canonical_name, p.person_id
                 LIMIT :limit OFFSET :offset
                """;

        List<PersonDtos.PersonHit> items = jdbc.query(sql, prm, (rs, i) -> new PersonDtos.PersonHit(
                rs.getLong("person_id"),
                rs.getString("canonical_name"),
                rs.getString("canonical_name_lang"),
                rs.getString("description"),
                (Integer) rs.getObject("birth_year_astro"),
                rs.getString("birth_precision"),
                (Integer) rs.getObject("death_year_astro"),
                rs.getString("death_precision"),
                rs.getString("record_status"),
                rs.getInt("name_count"),
                rs.getInt("event_count"),
                rs.getInt("place_count")));

        return com.canvasofworldhistory.api.dto.Dtos.Page.of(items, p, s, n);
    }

    // ================================================================ 详情
    public Optional<PersonDtos.PersonDetail> detail(long personId) {
        MapSqlParameterSource prm = new MapSqlParameterSource("id", personId);
        List<PersonDtos.PersonDetail> rows = jdbc.query("""
                SELECT person_id, canonical_name, canonical_name_lang, description,
                       birth_year_astro, birth_precision, birth_original_text,
                       death_year_astro, death_precision, death_original_text,
                       notes, record_status, created_by, locked
                  FROM person WHERE person_id = :id
                """, prm, (rs, i) -> {
            List<PersonDtos.PersonNameRow> names = names(personId);
            List<PersonDtos.PersonEventRow> events = events(personId, MAX_CHILD_ROWS + 1);
            List<PersonDtos.PersonPlaceRow> places = places(personId, MAX_CHILD_ROWS + 1);
            boolean truncated = events.size() > MAX_CHILD_ROWS || places.size() > MAX_CHILD_ROWS;
            return new PersonDtos.PersonDetail(
                    rs.getLong("person_id"),
                    rs.getString("canonical_name"),
                    rs.getString("canonical_name_lang"),
                    rs.getString("description"),
                    (Integer) rs.getObject("birth_year_astro"),
                    rs.getString("birth_precision"),
                    rs.getString("birth_original_text"),
                    (Integer) rs.getObject("death_year_astro"),
                    rs.getString("death_precision"),
                    rs.getString("death_original_text"),
                    rs.getString("notes"),
                    rs.getString("record_status"),
                    rs.getString("created_by"),
                    rs.getBoolean("locked"),
                    names,
                    events.size() > MAX_CHILD_ROWS ? events.subList(0, MAX_CHILD_ROWS) : events,
                    places.size() > MAX_CHILD_ROWS ? places.subList(0, MAX_CHILD_ROWS) : places,
                    truncated);
        });
        return rows.stream().findFirst();
    }

    // ================================================================ 增删改
    @Transactional
    public PersonDtos.PersonDetail create(Requests.PersonUpsert req) {
        validatePersonTime(req.birthYearAstro(), req.birthPrecision(), "birth");
        validatePersonTime(req.deathYearAstro(), req.deathPrecision(), "death");
        String name = requireText(req.canonicalName(), "canonicalName");
        String status = req.recordStatus() == null ? "staging" : requireEnum(req.recordStatus(), RECORD_STATUS, "recordStatus");

        MapSqlParameterSource prm = new MapSqlParameterSource()
                .addValue("name", name)
                .addValue("lang", blankToNull(req.canonicalNameLang()))
                .addValue("desc", blankToNull(req.description()))
                .addValue("b", req.birthYearAstro())
                .addValue("bp", req.birthPrecision() == null ? "unknown" : req.birthPrecision())
                .addValue("bot", blankToNull(req.birthOriginalText()))
                .addValue("d", req.deathYearAstro())
                .addValue("dp", req.deathPrecision() == null ? "unknown" : req.deathPrecision())
                .addValue("dot", blankToNull(req.deathOriginalText()))
                .addValue("notes", blankToNull(req.notes()))
                .addValue("status", status);

        KeyHolder keys = new GeneratedKeyHolder();
        jdbc.update("""
                INSERT INTO person (canonical_name, canonical_name_lang, description,
                                    birth_year_astro, birth_precision, birth_original_text,
                                    death_year_astro, death_precision, death_original_text,
                                    notes, record_status, created_by)
                VALUES (:name, :lang, :desc, :b, :bp, :bot, :d, :dp, :dot, :notes, :status, 'manual')
                """, prm, keys, new String[]{"person_id"});

        long id = keys.getKey() == null ? -1L : keys.getKey().longValue();
        return detail(id).orElseThrow(() -> new ResponseStatusException(
                HttpStatus.INTERNAL_SERVER_ERROR, "人物创建后无法回读"));
    }

    @Transactional
    public PersonDtos.PersonDetail update(long personId, Requests.PersonUpsert req) {
        PersonDtos.PersonDetail before = detail(personId).orElseThrow(() -> notFound("人物", personId));
        if (before.locked()) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "人物已锁定，不允许修改");
        }
        validatePersonTime(req.birthYearAstro(), req.birthPrecision(), "birth");
        validatePersonTime(req.deathYearAstro(), req.deathPrecision(), "death");
        String name = requireText(req.canonicalName(), "canonicalName");
        String status = req.recordStatus() == null
                ? before.recordStatus()
                : requireEnum(req.recordStatus(), RECORD_STATUS, "recordStatus");

        MapSqlParameterSource prm = new MapSqlParameterSource()
                .addValue("id", personId)
                .addValue("name", name)
                .addValue("lang", blankToNull(req.canonicalNameLang()))
                .addValue("desc", blankToNull(req.description()))
                .addValue("b", req.birthYearAstro())
                .addValue("bp", req.birthPrecision() == null ? "unknown" : req.birthPrecision())
                .addValue("bot", blankToNull(req.birthOriginalText()))
                .addValue("d", req.deathYearAstro())
                .addValue("dp", req.deathPrecision() == null ? "unknown" : req.deathPrecision())
                .addValue("dot", blankToNull(req.deathOriginalText()))
                .addValue("notes", blankToNull(req.notes()))
                .addValue("status", status);

        jdbc.update("""
                UPDATE person SET canonical_name = :name, canonical_name_lang = :lang,
                                  description = :desc,
                                  birth_year_astro = :b, birth_precision = :bp,
                                  birth_original_text = :bot,
                                  death_year_astro = :d, death_precision = :dp,
                                  death_original_text = :dot,
                                  notes = :notes, record_status = :status
                 WHERE person_id = :id
                """, prm);
        return detail(personId).orElseThrow(() -> notFound("人物", personId));
    }

    @Transactional
    public int delete(long personId) {
        return jdbc.update("DELETE FROM person WHERE person_id = :id",
                new MapSqlParameterSource("id", personId));
    }

    // ================================================================ 名称
    public List<PersonDtos.PersonNameRow> names(long personId) {
        return jdbc.query("""
                SELECT person_name_id, person_id, name_text, name_lang, name_type,
                       transliteration_scheme, notes, record_status
                  FROM person_name WHERE person_id = :id
                 ORDER BY CASE name_type WHEN 'primary' THEN 0 WHEN 'courtesy' THEN 1
                                         WHEN 'alternate' THEN 2 ELSE 3 END,
                          person_name_id
                """, new MapSqlParameterSource("id", personId),
                (rs, i) -> new PersonDtos.PersonNameRow(
                        rs.getLong("person_name_id"),
                        rs.getLong("person_id"),
                        rs.getString("name_text"),
                        rs.getString("name_lang"),
                        rs.getString("name_type"),
                        rs.getString("transliteration_scheme"),
                        rs.getString("notes"),
                        rs.getString("record_status")));
    }

    @Transactional
    public PersonDtos.PersonNameRow addName(long personId, Requests.PersonNameUpsert req) {
        requirePersonExists(personId);
        MapSqlParameterSource prm = nameParams(req)
                .addValue("pid", personId)
                .addValue("status", req.recordStatus() == null
                        ? "staging" : requireEnum(req.recordStatus(), RECORD_STATUS, "recordStatus"));

        KeyHolder keys = new GeneratedKeyHolder();
        jdbc.update("""
                INSERT INTO person_name (person_id, name_text, name_lang, name_type,
                                         transliteration_scheme, notes, record_status, created_by)
                VALUES (:pid, :text, :lang, :type, :scheme, :notes, :status, 'manual')
                """, prm, keys, new String[]{"person_name_id"});

        long id = keys.getKey() == null ? -1L : keys.getKey().longValue();
        return nameRow(id).orElseThrow(() -> new ResponseStatusException(
                HttpStatus.INTERNAL_SERVER_ERROR, "名称创建后无法回读"));
    }

    @Transactional
    public PersonDtos.PersonNameRow updateName(long personId, long nameId, Requests.PersonNameUpsert req) {
        nameRow(nameId, personId).orElseThrow(() -> notFound("人物名称", nameId));
        MapSqlParameterSource prm = nameParams(req)
                .addValue("id", nameId)
                .addValue("pid", personId)
                .addValue("status", req.recordStatus() == null
                        ? "staging" : requireEnum(req.recordStatus(), RECORD_STATUS, "recordStatus"));
        jdbc.update("""
                UPDATE person_name SET name_text = :text, name_lang = :lang, name_type = :type,
                                      transliteration_scheme = :scheme, notes = :notes,
                                      record_status = :status
                 WHERE person_name_id = :id AND person_id = :pid
                """, prm);
        return nameRow(nameId).orElseThrow(() -> notFound("人物名称", nameId));
    }

    @Transactional
    public int deleteName(long personId, long nameId) {
        return jdbc.update("DELETE FROM person_name WHERE person_name_id = :id AND person_id = :pid",
                new MapSqlParameterSource("id", nameId).addValue("pid", personId));
    }

    // ================================================================ 人物 ↔ 事件
    public List<PersonDtos.PersonEventRow> events(long personId, int limit) {
        return jdbc.query("""
                SELECT ep.event_person_id, ep.event_id, ep.role,
                       ep.valid_from_year_astro, ep.valid_to_year_astro, ep.note,
                       e.title, e.start_year_astro, e.end_year_astro, e.time_precision, e.event_type
                  FROM event_person ep
                  JOIN event e ON e.event_id = ep.event_id
                 WHERE ep.person_id = :id
                 ORDER BY e.start_year_astro NULLS LAST, e.event_id
                 LIMIT :lim
                """, new MapSqlParameterSource("id", personId).addValue("lim", limit),
                (rs, i) -> new PersonDtos.PersonEventRow(
                        rs.getLong("event_person_id"),
                        rs.getLong("event_id"),
                        rs.getString("title"),
                        (Integer) rs.getObject("start_year_astro"),
                        (Integer) rs.getObject("end_year_astro"),
                        rs.getString("time_precision"),
                        rs.getString("event_type"),
                        rs.getString("role"),
                        (Integer) rs.getObject("valid_from_year_astro"),
                        (Integer) rs.getObject("valid_to_year_astro"),
                        rs.getString("note")));
    }

    @Transactional
    public PersonDtos.PersonEventRow linkEvent(long personId, Requests.PersonEventLink req) {
        requirePersonExists(personId);
        long eventId = req.eventId() == null ? -1L : req.eventId();
        requireEventExists(eventId);
        MapSqlParameterSource prm = new MapSqlParameterSource()
                .addValue("pid", personId)
                .addValue("eid", eventId)
                .addValue("role", req.role() == null || req.role().isBlank() ? "unknown" : req.role().trim())
                .addValue("vf", req.validFromYearAstro())
                .addValue("vt", req.validToYearAstro())
                .addValue("note", blankToNull(req.note()));

        KeyHolder keys = new GeneratedKeyHolder();
        jdbc.update("""
                INSERT INTO event_person (event_id, person_id, role,
                                          valid_from_year_astro, valid_to_year_astro, note)
                VALUES (:eid, :pid, :role, :vf, :vt, :note)
                """, prm, keys, new String[]{"event_person_id"});
        long id = keys.getKey() == null ? -1L : keys.getKey().longValue();
        return events(personId, MAX_CHILD_ROWS).stream()
                .filter(r -> r.linkId() == id)
                .findFirst()
                .orElseThrow(() -> new ResponseStatusException(
                        HttpStatus.INTERNAL_SERVER_ERROR, "关联创建后无法回读"));
    }

    @Transactional
    public PersonDtos.PersonEventRow updateEventLink(long personId, long linkId, Requests.PersonEventLink req) {
        Integer ok = jdbc.query("SELECT 1 FROM event_person WHERE event_person_id = :id AND person_id = :pid",
                new MapSqlParameterSource("id", linkId).addValue("pid", personId),
                rs -> rs.next() ? 1 : null);
        if (ok == null) {
            throw notFound("人物事件关联", linkId);
        }
        jdbc.update("""
                UPDATE event_person SET role = :role, valid_from_year_astro = :vf,
                                        valid_to_year_astro = :vt, note = :note
                 WHERE event_person_id = :id AND person_id = :pid
                """, new MapSqlParameterSource()
                .addValue("id", linkId)
                .addValue("pid", personId)
                .addValue("role", req.role() == null || req.role().isBlank() ? "unknown" : req.role().trim())
                .addValue("vf", req.validFromYearAstro())
                .addValue("vt", req.validToYearAstro())
                .addValue("note", blankToNull(req.note())));
        return events(personId, MAX_CHILD_ROWS).stream()
                .filter(r -> r.linkId() == linkId).findFirst()
                .orElseThrow(() -> new ResponseStatusException(
                        HttpStatus.INTERNAL_SERVER_ERROR, "关联更新后无法回读"));
    }

    @Transactional
    public int unlinkEvent(long personId, long linkId) {
        return jdbc.update("DELETE FROM event_person WHERE event_person_id = :id AND person_id = :pid",
                new MapSqlParameterSource("id", linkId).addValue("pid", personId));
    }

    // ================================================================ 人物 ↔ 地点
    public List<PersonDtos.PersonPlaceRow> places(long personId, int limit) {
        return jdbc.query("""
                SELECT pp.person_place_id, pp.place_id, pp.relation_type,
                       pp.start_year_astro, pp.end_year_astro, pp.time_precision,
                       pp.sequence_order, pp.note,
                       p.canonical_name AS place_name, p.place_type,
                       loc.representative_lon, loc.representative_lat
                  FROM person_place pp
                  JOIN historical_place p ON p.place_id = pp.place_id
                  LEFT JOIN LATERAL (
                       SELECT l.representative_lon, l.representative_lat
                         FROM historical_place_location l
                        WHERE l.place_id = p.place_id AND l.geom IS NOT NULL
                          AND l.crs_confidence <> 'unknown'
                        ORDER BY l.location_id LIMIT 1) loc ON TRUE
                 WHERE pp.person_id = :id
                 ORDER BY pp.sequence_order NULLS LAST, pp.start_year_astro NULLS LAST, pp.person_place_id
                 LIMIT :lim
                """, new MapSqlParameterSource("id", personId).addValue("lim", limit),
                (rs, i) -> new PersonDtos.PersonPlaceRow(
                        rs.getLong("person_place_id"),
                        rs.getLong("place_id"),
                        rs.getString("place_name"),
                        rs.getString("place_type"),
                        rs.getString("relation_type"),
                        (Integer) rs.getObject("start_year_astro"),
                        (Integer) rs.getObject("end_year_astro"),
                        rs.getString("time_precision"),
                        (Integer) rs.getObject("sequence_order"),
                        rs.getString("note"),
                        (Double) rs.getObject("representative_lon"),
                        (Double) rs.getObject("representative_lat")));
    }

    @Transactional
    public PersonDtos.PersonPlaceRow linkPlace(long personId, Requests.PersonPlaceLink req) {
        requirePersonExists(personId);
        long placeId = req.placeId() == null ? -1L : req.placeId();
        requirePlaceExists(placeId);
        validateRange(req.startYearAstro(), req.endYearAstro(), req.timePrecision(), "person_place");

        MapSqlParameterSource prm = new MapSqlParameterSource()
                .addValue("pid", personId)
                .addValue("plid", placeId)
                .addValue("type", requireText(req.relationType(), "relationType"))
                .addValue("s", req.startYearAstro())
                .addValue("e", req.endYearAstro())
                .addValue("tp", req.timePrecision() == null ? "unknown" : req.timePrecision())
                .addValue("seq", req.sequenceOrder())
                .addValue("note", blankToNull(req.note()));

        KeyHolder keys = new GeneratedKeyHolder();
        jdbc.update("""
                INSERT INTO person_place (person_id, place_id, relation_type,
                                          start_year_astro, end_year_astro, time_precision,
                                          sequence_order, note)
                VALUES (:pid, :plid, :type, :s, :e, :tp, :seq, :note)
                """, prm, keys, new String[]{"person_place_id"});
        long id = keys.getKey() == null ? -1L : keys.getKey().longValue();
        return places(personId, MAX_CHILD_ROWS).stream()
                .filter(r -> r.linkId() == id)
                .findFirst()
                .orElseThrow(() -> new ResponseStatusException(
                        HttpStatus.INTERNAL_SERVER_ERROR, "关联创建后无法回读"));
    }

    @Transactional
    public PersonDtos.PersonPlaceRow updatePlaceLink(long personId, long linkId, Requests.PersonPlaceLink req) {
        Integer existing = jdbc.query("SELECT 1 FROM person_place WHERE person_place_id = :id AND person_id = :pid",
                new MapSqlParameterSource("id", linkId).addValue("pid", personId),
                rs -> rs.next() ? 1 : null);
        if (existing == null) {
            throw notFound("人物地点关联", linkId);
        }
        long placeId = req.placeId() == null ? -1L : req.placeId();
        requirePlaceExists(placeId);
        validateRange(req.startYearAstro(), req.endYearAstro(), req.timePrecision(), "person_place");

        jdbc.update("""
                UPDATE person_place SET place_id = :plid, relation_type = :type,
                                        start_year_astro = :s, end_year_astro = :e,
                                        time_precision = :tp, sequence_order = :seq, note = :note
                 WHERE person_place_id = :id AND person_id = :pid
                """, new MapSqlParameterSource()
                .addValue("id", linkId)
                .addValue("pid", personId)
                .addValue("plid", placeId)
                .addValue("type", requireText(req.relationType(), "relationType"))
                .addValue("s", req.startYearAstro())
                .addValue("e", req.endYearAstro())
                .addValue("tp", req.timePrecision() == null ? "unknown" : req.timePrecision())
                .addValue("seq", req.sequenceOrder())
                .addValue("note", blankToNull(req.note())));

        return places(personId, MAX_CHILD_ROWS).stream()
                .filter(r -> r.linkId() == linkId)
                .findFirst()
                .orElseThrow(() -> new ResponseStatusException(
                        HttpStatus.INTERNAL_SERVER_ERROR, "关联更新后无法回读"));
    }

    @Transactional
    public int unlinkPlace(long personId, long linkId) {
        return jdbc.update("DELETE FROM person_place WHERE person_place_id = :id AND person_id = :pid",
                new MapSqlParameterSource("id", linkId).addValue("pid", personId));
    }

    // ================================================================ 内部工具
    private MapSqlParameterSource nameParams(Requests.PersonNameUpsert req) {
        String type = requireEnum(requireText(req.nameType(), "nameType"), NAME_TYPES, "nameType");
        String scheme = blankToNull(req.transliterationScheme());
        if (scheme != null && !"transliteration".equals(type)) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST,
                    "transliterationScheme 仅在 nameType=transliteration 时可用");
        }
        return new MapSqlParameterSource()
                .addValue("text", requireText(req.nameText(), "nameText"))
                .addValue("lang", blankToNull(req.nameLang()))
                .addValue("type", type)
                .addValue("scheme", scheme)
                .addValue("notes", blankToNull(req.notes()));
    }

    private Optional<PersonDtos.PersonNameRow> nameRow(long nameId) {
        List<PersonDtos.PersonNameRow> r = jdbc.query("""
                SELECT person_name_id, person_id, name_text, name_lang, name_type,
                       transliteration_scheme, notes, record_status
                  FROM person_name WHERE person_name_id = :id
                """, new MapSqlParameterSource("id", nameId),
                (rs, i) -> new PersonDtos.PersonNameRow(
                        rs.getLong("person_name_id"), rs.getLong("person_id"),
                        rs.getString("name_text"), rs.getString("name_lang"),
                        rs.getString("name_type"), rs.getString("transliteration_scheme"),
                        rs.getString("notes"), rs.getString("record_status")));
        return r.stream().findFirst();
    }

    private Optional<PersonDtos.PersonNameRow> nameRow(long nameId, long personId) {
        return nameRow(nameId).filter(r -> r.personId() == personId);
    }

    private void requirePersonExists(long personId) {
        Integer ok = jdbc.query("SELECT 1 FROM person WHERE person_id = :id",
                new MapSqlParameterSource("id", personId), rs -> rs.next() ? 1 : null);
        if (ok == null) {
            throw notFound("人物", personId);
        }
    }

    private void requireEventExists(long eventId) {
        Integer ok = jdbc.query("SELECT 1 FROM event WHERE event_id = :id",
                new MapSqlParameterSource("id", eventId), rs -> rs.next() ? 1 : null);
        if (ok == null) {
            throw notFound("事件", eventId);
        }
    }

    private void requirePlaceExists(long placeId) {
        Integer ok = jdbc.query("SELECT 1 FROM historical_place WHERE place_id = :id",
                new MapSqlParameterSource("id", placeId), rs -> rs.next() ? 1 : null);
        if (ok == null) {
            throw notFound("地点", placeId);
        }
    }

    /** 人物生卒：年份与精度必须成对（与 ck_person_birth/death_time_pair 同口径，但报错更明确）。 */
    static void validatePersonTime(Integer year, String precision, String field) {
        String p = precision == null ? (year == null ? "unknown" : null) : precision;
        if (p == null) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST,
                    field + "Precision 在给定 " + field + "YearAstro 时必填（exact/approximate/range）");
        }
        if (!List.of("exact", "approximate", "range", "unknown").contains(p)) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST,
                    field + "Precision 非法：" + p + "（仅 exact/approximate/range/unknown）");
        }
        if ((year == null) != "unknown".equals(p)) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST,
                    year == null
                            ? field + "YearAstro 为空时 " + field + "Precision 必须为 unknown"
                            : field + "Precision=unknown 时不得给出 " + field + "YearAstro");
        }
    }

    /** 区间：unknown 时两端皆空；非 unknown 时起点必填；起 ≤ 止。 */
    static void validateRange(Integer start, Integer end, String precision, String what) {
        String p = precision == null ? (start == null ? "unknown" : null) : precision;
        if (p == null) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST,
                    what + ".timePrecision 在给定 startYearAstro 时必填");
        }
        if (!List.of("exact", "approximate", "range", "unknown").contains(p)) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST,
                    what + ".timePrecision 非法：" + p);
        }
        if ("unknown".equals(p)) {
            if (start != null || end != null) {
                throw new ResponseStatusException(HttpStatus.BAD_REQUEST,
                        what + ".timePrecision=unknown 时起止年必须都为空");
            }
            return;
        }
        if (start == null) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST,
                    what + ".startYearAstro 在 timePrecision≠unknown 时必填");
        }
        if (end != null && start > end) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST,
                    what + ".startYearAstro 不得晚于 endYearAstro（天文纪年整数比较）");
        }
    }

    static String requireText(String v, String field) {
        if (v == null || v.isBlank()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, field + " 不能为空");
        }
        return v.trim();
    }

    static String requireEnum(String v, String allowed, String field) {
        String t = requireText(v, field);
        if (!allowed.contains("'" + t + "'")) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST,
                    field + " 非法：" + t + "，允许值 " + allowed);
        }
        return t;
    }

    static String blankToNull(String v) {
        return v == null || v.isBlank() ? null : v.trim();
    }

    static ResponseStatusException notFound(String what, long id) {
        return new ResponseStatusException(HttpStatus.NOT_FOUND, what + " 不存在：" + id);
    }

    /** 供 Controller 复用的错误体结构。 */
    public static Map<String, Object> errorBody(HttpStatus status, String message) {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("status", status.value());
        m.put("error", status.getReasonPhrase());
        m.put("message", message);
        return m;
    }
}
