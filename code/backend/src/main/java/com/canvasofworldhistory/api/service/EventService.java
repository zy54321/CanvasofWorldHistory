package com.canvasofworldhistory.api.service;

import com.canvasofworldhistory.api.dto.Dtos;
import com.canvasofworldhistory.api.dto.EventDtos;
import com.canvasofworldhistory.api.dto.Requests;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.namedparam.MapSqlParameterSource;
import org.springframework.jdbc.core.namedparam.NamedParameterJdbcTemplate;
import org.springframework.jdbc.support.GeneratedKeyHolder;
import org.springframework.jdbc.support.KeyHolder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

import java.util.List;
import java.util.Optional;

/**
 * 事件相关读写。口径同 {@link PersonService}：
 * 时间为天文学纪年整数；校验以 V4 数据库约束为准，服务层只补更清楚的报错；
 * 删除事件时 event_place / event_person 由数据库 ON DELETE CASCADE 清除，人物与地点本体不受影响。
 */
@Service
public class EventService {

    private static final int MAX_PAGE_SIZE = 100;
    private static final int MAX_CHILD_ROWS = 500;
    private static final String RECORD_STATUS = "('staging','published','rejected')";

    private final NamedParameterJdbcTemplate jdbc;

    public EventService(NamedParameterJdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    // ================================================================ 列表 / 搜索
    public Dtos.Page<EventDtos.EventHit> search(String keyword, int page, int size) {
        int p = Math.max(1, page);
        int s = Math.min(Math.max(1, size), MAX_PAGE_SIZE);
        String kw = keyword == null ? "" : keyword.trim();
        String like = kw.isEmpty() ? null : "%" + kw + "%";

        MapSqlParameterSource prm = new MapSqlParameterSource()
                .addValue("like", like)
                .addValue("limit", s)
                .addValue("offset", (p - 1) * s);

        String where = like == null ? "" : """
                 WHERE e.title ILIKE :like
                    OR coalesce(e.summary, '') ILIKE :like
                """;

        Long total = jdbc.queryForObject("SELECT count(*) FROM event e" + where, prm, Long.class);
        long n = total == null ? 0 : total;
        if (n == 0) {
            return Dtos.Page.of(List.of(), p, s, 0);
        }

        String sql = """
                SELECT e.event_id, e.title, e.summary, e.start_year_astro, e.end_year_astro,
                       e.time_precision, e.event_type, e.record_status,
                       (SELECT count(*) FROM event_person ep WHERE ep.event_id = e.event_id) AS person_count,
                       (SELECT count(*) FROM event_place epl WHERE epl.event_id = e.event_id) AS place_count
                  FROM event e
                """ + where + """
                 ORDER BY (e.title ILIKE coalesce(:like, '')) DESC,
                          e.start_year_astro NULLS LAST, e.event_id
                 LIMIT :limit OFFSET :offset
                """;

        List<EventDtos.EventHit> items = jdbc.query(sql, prm, (rs, i) -> new EventDtos.EventHit(
                rs.getLong("event_id"),
                rs.getString("title"),
                rs.getString("summary"),
                (Integer) rs.getObject("start_year_astro"),
                (Integer) rs.getObject("end_year_astro"),
                rs.getString("time_precision"),
                rs.getString("event_type"),
                rs.getString("record_status"),
                rs.getInt("person_count"),
                rs.getInt("place_count")));

        return Dtos.Page.of(items, p, s, n);
    }

    // ================================================================ 详情
    public Optional<EventDtos.EventDetail> detail(long eventId) {
        List<EventDtos.EventDetail> rows = jdbc.query("""
                SELECT event_id, title, summary, description, start_year_astro, end_year_astro,
                       time_precision, time_original_text, time_note, event_type, notes,
                       record_status, created_by, locked
                  FROM event WHERE event_id = :id
                """, new MapSqlParameterSource("id", eventId), (rs, i) -> {
            List<EventDtos.EventPersonRow> persons = persons(eventId, MAX_CHILD_ROWS + 1);
            List<EventDtos.EventPlaceRow> places = places(eventId, MAX_CHILD_ROWS + 1);
            boolean truncated = persons.size() > MAX_CHILD_ROWS || places.size() > MAX_CHILD_ROWS;
            return new EventDtos.EventDetail(
                    rs.getLong("event_id"),
                    rs.getString("title"),
                    rs.getString("summary"),
                    rs.getString("description"),
                    (Integer) rs.getObject("start_year_astro"),
                    (Integer) rs.getObject("end_year_astro"),
                    rs.getString("time_precision"),
                    rs.getString("time_original_text"),
                    rs.getString("time_note"),
                    rs.getString("event_type"),
                    rs.getString("notes"),
                    rs.getString("record_status"),
                    rs.getString("created_by"),
                    rs.getBoolean("locked"),
                    persons.size() > MAX_CHILD_ROWS ? persons.subList(0, MAX_CHILD_ROWS) : persons,
                    places.size() > MAX_CHILD_ROWS ? places.subList(0, MAX_CHILD_ROWS) : places,
                    truncated);
        });
        return rows.stream().findFirst();
    }

    // ================================================================ 增删改
    @Transactional
    public EventDtos.EventDetail create(Requests.EventUpsert req) {
        PersonService.validateRange(req.startYearAstro(), req.endYearAstro(), req.timePrecision(), "event");
        String status = req.recordStatus() == null
                ? "staging" : PersonService.requireEnum(req.recordStatus(), RECORD_STATUS, "recordStatus");

        MapSqlParameterSource prm = new MapSqlParameterSource()
                .addValue("title", PersonService.requireText(req.title(), "title"))
                .addValue("summary", PersonService.blankToNull(req.summary()))
                .addValue("desc", PersonService.blankToNull(req.description()))
                .addValue("s", req.startYearAstro())
                .addValue("e", req.endYearAstro())
                .addValue("tp", req.timePrecision() == null ? "unknown" : req.timePrecision())
                .addValue("tot", PersonService.blankToNull(req.timeOriginalText()))
                .addValue("tn", PersonService.blankToNull(req.timeNote()))
                .addValue("type", req.eventType() == null || req.eventType().isBlank()
                        ? "unknown" : req.eventType().trim())
                .addValue("notes", PersonService.blankToNull(req.notes()))
                .addValue("status", status);

        KeyHolder keys = new GeneratedKeyHolder();
        jdbc.update("""
                INSERT INTO event (title, summary, description, start_year_astro, end_year_astro,
                                   time_precision, time_original_text, time_note, event_type,
                                   notes, record_status, created_by)
                VALUES (:title, :summary, :desc, :s, :e, :tp, :tot, :tn, :type,
                        :notes, :status, 'manual')
                """, prm, keys, new String[]{"event_id"});

        long id = keys.getKey() == null ? -1L : keys.getKey().longValue();
        return detail(id).orElseThrow(() -> new ResponseStatusException(
                HttpStatus.INTERNAL_SERVER_ERROR, "事件创建后无法回读"));
    }

    @Transactional
    public EventDtos.EventDetail update(long eventId, Requests.EventUpsert req) {
        EventDtos.EventDetail before = detail(eventId)
                .orElseThrow(() -> PersonService.notFound("事件", eventId));
        if (before.locked()) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "事件已锁定，不允许修改");
        }
        PersonService.validateRange(req.startYearAstro(), req.endYearAstro(), req.timePrecision(), "event");
        String status = req.recordStatus() == null
                ? before.recordStatus()
                : PersonService.requireEnum(req.recordStatus(), RECORD_STATUS, "recordStatus");

        jdbc.update("""
                UPDATE event SET title = :title, summary = :summary, description = :desc,
                                 start_year_astro = :s, end_year_astro = :e,
                                 time_precision = :tp, time_original_text = :tot, time_note = :tn,
                                 event_type = :type, notes = :notes, record_status = :status
                 WHERE event_id = :id
                """, new MapSqlParameterSource()
                .addValue("id", eventId)
                .addValue("title", PersonService.requireText(req.title(), "title"))
                .addValue("summary", PersonService.blankToNull(req.summary()))
                .addValue("desc", PersonService.blankToNull(req.description()))
                .addValue("s", req.startYearAstro())
                .addValue("e", req.endYearAstro())
                .addValue("tp", req.timePrecision() == null ? "unknown" : req.timePrecision())
                .addValue("tot", PersonService.blankToNull(req.timeOriginalText()))
                .addValue("tn", PersonService.blankToNull(req.timeNote()))
                .addValue("type", req.eventType() == null || req.eventType().isBlank()
                        ? "unknown" : req.eventType().trim())
                .addValue("notes", PersonService.blankToNull(req.notes()))
                .addValue("status", status));

        return detail(eventId).orElseThrow(() -> PersonService.notFound("事件", eventId));
    }

    @Transactional
    public int delete(long eventId) {
        return jdbc.update("DELETE FROM event WHERE event_id = :id",
                new MapSqlParameterSource("id", eventId));
    }

    // ================================================================ 事件 ↔ 人物
    public List<EventDtos.EventPersonRow> persons(long eventId, int limit) {
        return jdbc.query("""
                SELECT ep.event_person_id, ep.person_id, ep.role,
                       ep.valid_from_year_astro, ep.valid_to_year_astro, ep.note,
                       p.canonical_name
                  FROM event_person ep
                  JOIN person p ON p.person_id = ep.person_id
                 WHERE ep.event_id = :id
                 ORDER BY ep.event_person_id
                 LIMIT :lim
                """, new MapSqlParameterSource("id", eventId).addValue("lim", limit),
                (rs, i) -> new EventDtos.EventPersonRow(
                        rs.getLong("event_person_id"),
                        rs.getLong("person_id"),
                        rs.getString("canonical_name"),
                        rs.getString("role"),
                        (Integer) rs.getObject("valid_from_year_astro"),
                        (Integer) rs.getObject("valid_to_year_astro"),
                        rs.getString("note")));
    }

    @Transactional
    public EventDtos.EventPersonRow linkPerson(long eventId, Requests.PersonEventLink req) {
        requireEventExists(eventId);
        long personId = req.personId() == null ? -1L : req.personId();
        requirePersonExists(personId);

        KeyHolder keys = new GeneratedKeyHolder();
        jdbc.update("""
                INSERT INTO event_person (event_id, person_id, role,
                                          valid_from_year_astro, valid_to_year_astro, note)
                VALUES (:eid, :pid, :role, :vf, :vt, :note)
                """, new MapSqlParameterSource()
                .addValue("eid", eventId)
                .addValue("pid", personId)
                .addValue("role", req.role() == null || req.role().isBlank() ? "unknown" : req.role().trim())
                .addValue("vf", req.validFromYearAstro())
                .addValue("vt", req.validToYearAstro())
                .addValue("note", PersonService.blankToNull(req.note())),
                keys, new String[]{"event_person_id"});

        long id = keys.getKey() == null ? -1L : keys.getKey().longValue();
        return persons(eventId, MAX_CHILD_ROWS).stream()
                .filter(r -> r.linkId() == id).findFirst()
                .orElseThrow(() -> new ResponseStatusException(
                        HttpStatus.INTERNAL_SERVER_ERROR, "关联创建后无法回读"));
    }

    @Transactional
    public EventDtos.EventPersonRow updatePersonLink(long eventId, long linkId, Requests.PersonEventLink req) {
        Integer ok = jdbc.query("SELECT 1 FROM event_person WHERE event_person_id = :id AND event_id = :eid",
                new MapSqlParameterSource("id", linkId).addValue("eid", eventId),
                rs -> rs.next() ? 1 : null);
        if (ok == null) {
            throw PersonService.notFound("事件人物关联", linkId);
        }
        jdbc.update("""
                UPDATE event_person SET role = :role, valid_from_year_astro = :vf,
                                        valid_to_year_astro = :vt, note = :note
                 WHERE event_person_id = :id AND event_id = :eid
                """, new MapSqlParameterSource()
                .addValue("id", linkId)
                .addValue("eid", eventId)
                .addValue("role", req.role() == null || req.role().isBlank() ? "unknown" : req.role().trim())
                .addValue("vf", req.validFromYearAstro())
                .addValue("vt", req.validToYearAstro())
                .addValue("note", PersonService.blankToNull(req.note())));

        return persons(eventId, MAX_CHILD_ROWS).stream()
                .filter(r -> r.linkId() == linkId).findFirst()
                .orElseThrow(() -> new ResponseStatusException(
                        HttpStatus.INTERNAL_SERVER_ERROR, "关联更新后无法回读"));
    }

    @Transactional
    public int unlinkPerson(long eventId, long linkId) {
        return jdbc.update("DELETE FROM event_person WHERE event_person_id = :id AND event_id = :eid",
                new MapSqlParameterSource("id", linkId).addValue("eid", eventId));
    }

    // ================================================================ 事件 ↔ 地点
    public List<EventDtos.EventPlaceRow> places(long eventId, int limit) {
        return jdbc.query("""
                SELECT epl.event_place_id, epl.place_id, epl.location_role,
                       epl.valid_from_year_astro, epl.valid_to_year_astro, epl.note,
                       p.canonical_name AS place_name, p.place_type,
                       loc.representative_lon, loc.representative_lat
                  FROM event_place epl
                  JOIN historical_place p ON p.place_id = epl.place_id
                  LEFT JOIN LATERAL (
                       SELECT l.representative_lon, l.representative_lat
                         FROM historical_place_location l
                        WHERE l.place_id = p.place_id AND l.geom IS NOT NULL
                          AND l.crs_confidence <> 'unknown'
                        ORDER BY l.location_id LIMIT 1) loc ON TRUE
                 WHERE epl.event_id = :id
                 ORDER BY epl.event_place_id
                 LIMIT :lim
                """, new MapSqlParameterSource("id", eventId).addValue("lim", limit),
                (rs, i) -> new EventDtos.EventPlaceRow(
                        rs.getLong("event_place_id"),
                        rs.getLong("place_id"),
                        rs.getString("place_name"),
                        rs.getString("place_type"),
                        rs.getString("location_role"),
                        (Integer) rs.getObject("valid_from_year_astro"),
                        (Integer) rs.getObject("valid_to_year_astro"),
                        rs.getString("note"),
                        (Double) rs.getObject("representative_lon"),
                        (Double) rs.getObject("representative_lat")));
    }

    @Transactional
    public EventDtos.EventPlaceRow linkPlace(long eventId, Requests.EventPlaceLink req) {
        requireEventExists(eventId);
        long placeId = req.placeId() == null ? -1L : req.placeId();
        requirePlaceExists(placeId);

        KeyHolder keys = new GeneratedKeyHolder();
        jdbc.update("""
                INSERT INTO event_place (event_id, place_id, location_role,
                                         valid_from_year_astro, valid_to_year_astro, note)
                VALUES (:eid, :plid, :role, :vf, :vt, :note)
                """, new MapSqlParameterSource()
                .addValue("eid", eventId)
                .addValue("plid", placeId)
                .addValue("role", req.locationRole() == null || req.locationRole().isBlank()
                        ? "unknown" : req.locationRole().trim())
                .addValue("vf", req.validFromYearAstro())
                .addValue("vt", req.validToYearAstro())
                .addValue("note", PersonService.blankToNull(req.note())),
                keys, new String[]{"event_place_id"});

        long id = keys.getKey() == null ? -1L : keys.getKey().longValue();
        return places(eventId, MAX_CHILD_ROWS).stream()
                .filter(r -> r.linkId() == id).findFirst()
                .orElseThrow(() -> new ResponseStatusException(
                        HttpStatus.INTERNAL_SERVER_ERROR, "关联创建后无法回读"));
    }

    @Transactional
    public EventDtos.EventPlaceRow updatePlaceLink(long eventId, long linkId, Requests.EventPlaceLink req) {
        Integer ok = jdbc.query("SELECT 1 FROM event_place WHERE event_place_id = :id AND event_id = :eid",
                new MapSqlParameterSource("id", linkId).addValue("eid", eventId),
                rs -> rs.next() ? 1 : null);
        if (ok == null) {
            throw PersonService.notFound("事件地点关联", linkId);
        }
        long placeId = req.placeId() == null ? -1L : req.placeId();
        requirePlaceExists(placeId);

        jdbc.update("""
                UPDATE event_place SET place_id = :plid, location_role = :role,
                                       valid_from_year_astro = :vf, valid_to_year_astro = :vt,
                                       note = :note
                 WHERE event_place_id = :id AND event_id = :eid
                """, new MapSqlParameterSource()
                .addValue("id", linkId)
                .addValue("eid", eventId)
                .addValue("plid", placeId)
                .addValue("role", req.locationRole() == null || req.locationRole().isBlank()
                        ? "unknown" : req.locationRole().trim())
                .addValue("vf", req.validFromYearAstro())
                .addValue("vt", req.validToYearAstro())
                .addValue("note", PersonService.blankToNull(req.note())));

        return places(eventId, MAX_CHILD_ROWS).stream()
                .filter(r -> r.linkId() == linkId).findFirst()
                .orElseThrow(() -> new ResponseStatusException(
                        HttpStatus.INTERNAL_SERVER_ERROR, "关联更新后无法回读"));
    }

    @Transactional
    public int unlinkPlace(long eventId, long linkId) {
        return jdbc.update("DELETE FROM event_place WHERE event_place_id = :id AND event_id = :eid",
                new MapSqlParameterSource("id", linkId).addValue("eid", eventId));
    }

    // ================================================================ 内部
    private void requireEventExists(long eventId) {
        Integer ok = jdbc.query("SELECT 1 FROM event WHERE event_id = :id",
                new MapSqlParameterSource("id", eventId), rs -> rs.next() ? 1 : null);
        if (ok == null) {
            throw PersonService.notFound("事件", eventId);
        }
    }

    private void requirePersonExists(long personId) {
        Integer ok = jdbc.query("SELECT 1 FROM person WHERE person_id = :id",
                new MapSqlParameterSource("id", personId), rs -> rs.next() ? 1 : null);
        if (ok == null) {
            throw PersonService.notFound("人物", personId);
        }
    }

    private void requirePlaceExists(long placeId) {
        Integer ok = jdbc.query("SELECT 1 FROM historical_place WHERE place_id = :id",
                new MapSqlParameterSource("id", placeId), rs -> rs.next() ? 1 : null);
        if (ok == null) {
            throw PersonService.notFound("地点", placeId);
        }
    }
}
