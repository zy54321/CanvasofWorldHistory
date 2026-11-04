package com.canvasofworldhistory.api.service;

import com.canvasofworldhistory.api.dto.Dtos;
import org.springframework.jdbc.core.namedparam.MapSqlParameterSource;
import org.springframework.jdbc.core.namedparam.NamedParameterJdbcTemplate;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

/**
 * M1 只读查询：地点搜索 / 地点详情 / 地图 bbox 查询 / 概览统计。
 *
 * 口径（全部沿用既有数据模型，不另立规则）：
 *  · 只有 record_status &lt;&gt; 'rejected' 的行参与展示。**来源不是准入条件**（M4-2）：
 *    有 source_record 时要求它 is_active（失效来源的衍生行不展示），
 *    没有 source_record（人工录入）时照常展示 —— 因此关联一律 LEFT JOIN，
 *    不得因为 source_record_id 为空把地点或名称排除在外；
 *  · 未知坐标系（crs_confidence = 'unknown'）的坐标行**不作为可信位置**输出（地图不返回、详情里标注）；
 *  · 每个地点在地图上只画一个点：坐标行按 location_id 定序取首行（与 v_place_evidence 的"有效证据优先"同思路）；
 *  · 名称检索覆盖 primary / alternate（别名）/ transliteration 三种 name_type，同名不同地点**不合并**。
 */
@Service
public class PlaceQueryService {

    public static final int MAX_PAGE_SIZE = 100;
    public static final int DEFAULT_PAGE_SIZE = 20;
    public static final int MAX_MAP_FEATURES = 2000;

    /** 每个地点的"代表坐标行"：有 geom、CRS 已确认、未被驳回；按 location_id 定序取第一行。 */
    private static final String PREFERRED_LOCATION = """
            LEFT JOIN LATERAL (
                SELECT l.location_id, l.representative_lon, l.representative_lat,
                       l.location_precision, l.uncertainty_m, l.crs_confidence
                  FROM historical_place_location l
                 WHERE l.place_id = p.place_id
                   AND l.geom IS NOT NULL
                   AND l.representative_lon IS NOT NULL
                   AND l.representative_lat IS NOT NULL
                   AND l.crs_confidence <> 'unknown'
                   AND l.record_status <> 'rejected'
                 ORDER BY l.location_id
                 LIMIT 1) loc ON TRUE
            """;

    private static final String SEARCH_CTE = """
            WITH param AS (SELECT :kw::text AS kw, :yr::int AS yr),
            name_hit AS (
                SELECT n.place_id,
                       n.name_text,
                       n.name_type,
                       n.name_lang,
                       n.valid_from_year_astro,
                       n.valid_to_year_astro,
                       n.time_bound_type,
                       CASE WHEN lower(n.name_text) = lower(p.kw) THEN 0
                            WHEN n.name_text ILIKE p.kw || '%' THEN 1
                            ELSE 2 END AS hit_rank
                  FROM historical_place_name n
                  JOIN historical_place pl ON pl.place_id = n.place_id
                                         AND pl.merged_into_place_id IS NULL
                  LEFT JOIN source_record sr ON sr.source_record_id = n.source_record_id
                  CROSS JOIN param p
                 WHERE n.record_status <> 'rejected'
                   AND (sr.source_record_id IS NULL OR sr.is_active)
                   AND n.name_text ILIKE '%' || p.kw || '%'
                   AND (p.yr IS NULL
                        OR ((n.valid_from_year_astro IS NULL OR n.valid_from_year_astro <= p.yr)
                            AND (n.valid_to_year_astro IS NULL OR n.valid_to_year_astro >= p.yr)))
            ),
            canon_hit AS (
                -- 仅在未指定年代时补 canonical_name 命中（指定年代时必须以名称有效期为准，不能绕过）
                SELECT pl.place_id,
                       pl.canonical_name AS name_text,
                       'canonical'::text  AS name_type,
                       pl.canonical_name_lang AS name_lang,
                       NULL::int AS valid_from_year_astro,
                       NULL::int AS valid_to_year_astro,
                       'unknown'::text AS time_bound_type,
                       3 AS hit_rank
                  FROM historical_place pl
                  CROSS JOIN param p
                 WHERE p.yr IS NULL
                   AND pl.merged_into_place_id IS NULL
                   AND pl.canonical_name ILIKE '%' || p.kw || '%'
                   AND NOT EXISTS (SELECT 1 FROM name_hit h WHERE h.place_id = pl.place_id)
            ),
            best AS (
                SELECT DISTINCT ON (place_id) *
                  FROM (SELECT * FROM name_hit UNION ALL SELECT * FROM canon_hit) u
                 ORDER BY place_id, hit_rank
            )
            """;

    private final NamedParameterJdbcTemplate jdbc;

    public PlaceQueryService(NamedParameterJdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    // ------------------------------------------------------------------ 搜索
    public Dtos.Page<Dtos.PlaceHit> search(String keyword, Integer year, int page, int size) {
        int p = Math.max(1, page);
        int s = Math.min(Math.max(1, size), MAX_PAGE_SIZE);
        MapSqlParameterSource prm = new MapSqlParameterSource()
                .addValue("kw", keyword.trim())
                .addValue("yr", year)
                .addValue("limit", s)
                .addValue("offset", (p - 1) * s);

        Long total = jdbc.queryForObject(SEARCH_CTE + "SELECT count(*) FROM best", prm, Long.class);
        long n = total == null ? 0 : total;
        if (n == 0) {
            return Dtos.Page.of(List.of(), p, s, 0);
        }

        String pageSql = SEARCH_CTE + """
                SELECT b.place_id, b.name_text, b.name_type, b.name_lang,
                       b.valid_from_year_astro, b.valid_to_year_astro, b.time_bound_type,
                       p.canonical_name, p.canonical_name_lang, p.place_type, p.dataset_id,
                       d.display_name AS dataset_name, p.record_status,
                       loc.representative_lon, loc.representative_lat,
                       loc.location_precision, loc.uncertainty_m,
                       (SELECT count(*) FROM historical_place_name n2
                         WHERE n2.place_id = b.place_id AND n2.record_status <> 'rejected') AS name_count,
                       (SELECT count(*) FROM historical_place_location l2
                         WHERE l2.place_id = b.place_id AND l2.geom IS NOT NULL) AS location_count
                  FROM (SELECT * FROM best
                         ORDER BY hit_rank, name_text, place_id
                         LIMIT :limit OFFSET :offset) b
                  JOIN historical_place p ON p.place_id = b.place_id
                  JOIN data_dataset d ON d.dataset_id = p.dataset_id
                  %s
                 ORDER BY b.hit_rank, b.name_text, b.place_id
                """.formatted(PREFERRED_LOCATION);

        List<Dtos.PlaceHit> items = jdbc.query(pageSql, prm, (rs, i) -> {
            Integer vf = (Integer) rs.getObject("valid_from_year_astro");
            Integer vt = (Integer) rs.getObject("valid_to_year_astro");
            String tbt = rs.getString("time_bound_type");
            boolean timeKnown = vf != null || vt != null;
            return new Dtos.PlaceHit(
                    rs.getLong("place_id"),
                    rs.getString("canonical_name"),
                    rs.getString("canonical_name_lang"),
                    rs.getString("place_type"),
                    rs.getString("dataset_id"),
                    rs.getString("dataset_name"),
                    rs.getString("record_status"),
                    rs.getString("name_text"),
                    rs.getString("name_type"),
                    rs.getString("name_lang"),
                    vf, vt, tbt, timeKnown,
                    (Double) rs.getObject("representative_lon"),
                    (Double) rs.getObject("representative_lat"),
                    rs.getString("location_precision"),
                    (Integer) rs.getObject("uncertainty_m"),
                    rs.getInt("name_count"),
                    rs.getInt("location_count"));
        });
        return Dtos.Page.of(items, p, s, n);
    }

    // ------------------------------------------------------------------ 详情
    public Optional<Dtos.PlaceDetail> detail(long placeId) {
        MapSqlParameterSource prm = new MapSqlParameterSource("id", placeId);

        List<Map<String, Object>> head = jdbc.query("""
                SELECT p.place_id, p.canonical_name, p.canonical_name_lang, p.place_type,
                       p.place_type_source, p.place_type_basis_note, p.description, p.notes,
                       p.record_status, p.merged_into_place_id, p.dataset_id,
                       d.display_name AS dataset_name, d.dataset_version, d.source_id,
                       s.display_name AS source_name, s.homepage_url AS source_homepage,
                       s.notes AS source_note,
                       v.liveness
                  FROM historical_place p
                  JOIN data_dataset d ON d.dataset_id = p.dataset_id
                  LEFT JOIN data_source s ON s.source_id = d.source_id
                  LEFT JOIN v_place_liveness v ON v.place_id = p.place_id
                 WHERE p.place_id = :id
                """, prm, (rs, i) -> {
            Map<String, Object> m = new LinkedHashMap<>();
            m.put("placeId", rs.getLong("place_id"));
            m.put("canonicalName", rs.getString("canonical_name"));
            m.put("canonicalNameLang", rs.getString("canonical_name_lang"));
            m.put("placeType", rs.getString("place_type"));
            m.put("placeTypeSource", rs.getString("place_type_source"));
            m.put("placeTypeBasisNote", rs.getString("place_type_basis_note"));
            m.put("description", rs.getString("description"));
            m.put("notes", rs.getString("notes"));
            m.put("recordStatus", rs.getString("record_status"));
            m.put("liveness", rs.getString("liveness"));
            m.put("mergedIntoPlaceId", rs.getObject("merged_into_place_id"));
            m.put("datasetId", rs.getString("dataset_id"));
            m.put("datasetName", rs.getString("dataset_name"));
            m.put("datasetVersion", rs.getString("dataset_version"));
            m.put("sourceId", rs.getString("source_id"));
            m.put("sourceName", rs.getString("source_name"));
            m.put("sourceHomepage", rs.getString("source_homepage"));
            m.put("sourceNote", rs.getString("source_note"));
            return m;
        });
        if (head.isEmpty()) {
            return Optional.empty();
        }
        Map<String, Object> h = head.get(0);

        List<Dtos.NameRow> names = jdbc.query("""
                SELECT name_id, name_text, name_lang, name_type, transliteration_scheme,
                       association_certainty, valid_from_year_astro, valid_to_year_astro,
                       time_bound_type, time_note, record_status
                  FROM historical_place_name
                 WHERE place_id = :id
                 ORDER BY CASE name_type WHEN 'primary' THEN 0 WHEN 'alternate' THEN 1 ELSE 2 END,
                          name_id
                """, prm, (rs, i) -> new Dtos.NameRow(
                rs.getLong("name_id"), rs.getString("name_text"), rs.getString("name_lang"),
                rs.getString("name_type"), rs.getString("transliteration_scheme"),
                rs.getString("association_certainty"),
                (Integer) rs.getObject("valid_from_year_astro"),
                (Integer) rs.getObject("valid_to_year_astro"),
                rs.getString("time_bound_type"), rs.getString("time_note"),
                rs.getString("record_status")));

        List<Dtos.LocationRow> locations = jdbc.query("""
                SELECT location_id, representative_lon, representative_lat, geom_type,
                       location_precision, uncertainty_m, uncertainty_source, original_crs,
                       crs_confidence, original_x, original_y,
                       valid_from_year_astro, valid_to_year_astro, time_bound_type,
                       record_status, conflict_status, (geom IS NOT NULL) AS has_geom
                  FROM historical_place_location
                 WHERE place_id = :id
                 ORDER BY CASE WHEN crs_confidence = 'unknown' THEN 1 ELSE 0 END, location_id
                """, prm, (rs, i) -> new Dtos.LocationRow(
                rs.getLong("location_id"),
                (Double) rs.getObject("representative_lon"),
                (Double) rs.getObject("representative_lat"),
                rs.getString("geom_type"), rs.getString("location_precision"),
                (Integer) rs.getObject("uncertainty_m"), rs.getString("uncertainty_source"),
                rs.getString("original_crs"), rs.getString("crs_confidence"),
                rs.getString("original_x"), rs.getString("original_y"),
                (Integer) rs.getObject("valid_from_year_astro"),
                (Integer) rs.getObject("valid_to_year_astro"),
                rs.getString("time_bound_type"), rs.getString("record_status"),
                rs.getString("conflict_status"), rs.getBoolean("has_geom")));

        List<Dtos.SourceRecordRow> records = jdbc.query("""
                WITH ids AS (
                    SELECT created_from_source_record_id AS id FROM historical_place WHERE place_id = :id
                    UNION SELECT source_record_id FROM historical_place_name WHERE place_id = :id
                    UNION SELECT source_record_id FROM historical_place_location WHERE place_id = :id
                )
                SELECT sr.source_record_id, sr.dataset_id, sr.record_scope, sr.external_id,
                       sr.duplicate_ordinal, sr.raw_file, sr.is_active, sr.inactive_reason
                  FROM source_record sr
                 WHERE sr.source_record_id IN (SELECT id FROM ids WHERE id IS NOT NULL)
                 ORDER BY sr.record_scope, sr.external_id
                 LIMIT 50
                """, prm, (rs, i) -> new Dtos.SourceRecordRow(
                rs.getLong("source_record_id"), rs.getString("dataset_id"),
                rs.getString("record_scope"), rs.getString("external_id"),
                (Integer) rs.getObject("duplicate_ordinal"), rs.getString("raw_file"),
                rs.getBoolean("is_active"), rs.getString("inactive_reason")));

        int issueLimit = 50;
        List<Dtos.IssueRow> issues = jdbc.query("""
                WITH ids AS (
                    SELECT created_from_source_record_id AS id FROM historical_place WHERE place_id = :id
                    UNION SELECT source_record_id FROM historical_place_name WHERE place_id = :id
                    UNION SELECT source_record_id FROM historical_place_location WHERE place_id = :id
                )
                SELECT issue_id, issue_type, severity, field_name, observed_value,
                       action_taken, resolution_note
                  FROM data_quality_issue
                 WHERE place_id = :id
                    OR source_record_id IN (SELECT id FROM ids WHERE id IS NOT NULL)
                 ORDER BY CASE severity WHEN 'blocking' THEN 0 WHEN 'warning' THEN 1 ELSE 2 END,
                          issue_type, issue_id
                 LIMIT :lim
                """, prm.addValue("lim", issueLimit + 1), (rs, i) -> new Dtos.IssueRow(
                rs.getLong("issue_id"), rs.getString("issue_type"), rs.getString("severity"),
                rs.getString("field_name"), rs.getString("observed_value"),
                rs.getString("action_taken"), rs.getString("resolution_note")));
        boolean truncated = issues.size() > issueLimit;
        if (truncated) {
            issues = new ArrayList<>(issues.subList(0, issueLimit));
        }

        return Optional.of(new Dtos.PlaceDetail(
                (Long) h.get("placeId"),
                (String) h.get("canonicalName"),
                (String) h.get("canonicalNameLang"),
                (String) h.get("placeType"),
                (String) h.get("placeTypeSource"),
                (String) h.get("placeTypeBasisNote"),
                (String) h.get("description"),
                (String) h.get("notes"),
                (String) h.get("recordStatus"),
                (String) h.get("liveness"),
                (Long) h.get("mergedIntoPlaceId"),
                (String) h.get("datasetId"),
                (String) h.get("datasetName"),
                (String) h.get("datasetVersion"),
                (String) h.get("sourceId"),
                (String) h.get("sourceName"),
                (String) h.get("sourceHomepage"),
                (String) h.get("sourceNote"),
                names, locations, records, issues, truncated));
    }

    // ------------------------------------------------------------------ 地图
    public Map<String, Object> mapFeatures(double west, double south, double east, double north, int limit) {
        int lim = Math.min(Math.max(1, limit), MAX_MAP_FEATURES);
        MapSqlParameterSource prm = new MapSqlParameterSource()
                .addValue("w", west).addValue("s", south)
                .addValue("e", east).addValue("n", north)
                .addValue("lim", lim);

        Long total = jdbc.queryForObject("""
                SELECT count(DISTINCT l.place_id)
                  FROM historical_place_location l
                  LEFT JOIN source_record sr ON sr.source_record_id = l.source_record_id
                 WHERE l.geom IS NOT NULL
                   AND l.crs_confidence <> 'unknown'
                   AND l.record_status <> 'rejected'
                   AND (sr.source_record_id IS NULL OR sr.is_active)
                   AND ST_Intersects(l.geom, ST_MakeEnvelope(:w, :s, :e, :n, 4326))
                """, prm, Long.class);
        long n = total == null ? 0 : total;

        List<Map<String, Object>> features = jdbc.query("""
                WITH cand AS (
                    SELECT DISTINCT ON (l.place_id)
                           l.place_id, l.location_id, l.representative_lon, l.representative_lat,
                           l.location_precision, l.uncertainty_m, l.crs_confidence,
                           l.valid_from_year_astro, l.valid_to_year_astro, l.time_bound_type
                      FROM historical_place_location l
                      LEFT JOIN source_record sr ON sr.source_record_id = l.source_record_id
                     WHERE l.geom IS NOT NULL
                       AND l.crs_confidence <> 'unknown'
                       AND l.record_status <> 'rejected'
                       AND (sr.source_record_id IS NULL OR sr.is_active)
                       AND ST_Intersects(l.geom, ST_MakeEnvelope(:w, :s, :e, :n, 4326))
                     ORDER BY l.place_id, l.location_id
                )
                SELECT c.place_id, c.location_id, c.representative_lon, c.representative_lat,
                       c.location_precision, c.uncertainty_m, c.crs_confidence,
                       c.valid_from_year_astro, c.valid_to_year_astro, c.time_bound_type,
                       p.canonical_name, p.canonical_name_lang, p.place_type, p.dataset_id,
                       d.display_name AS dataset_name, p.record_status
                  FROM cand c
                  JOIN historical_place p ON p.place_id = c.place_id
                  JOIN data_dataset d ON d.dataset_id = p.dataset_id
                 WHERE p.merged_into_place_id IS NULL
                 -- 截断时用 id 的确定性哈希排序，使有限采样在空间上分散，
                 -- 避免按 id 顺序取前 N 个导致所有点挤在数据集的首个地理片区
                 ORDER BY md5(c.place_id::text)
                 LIMIT :lim
                """, prm, (rs, i) -> {
            Map<String, Object> props = new LinkedHashMap<>();
            props.put("placeId", rs.getLong("place_id"));
            props.put("name", rs.getString("canonical_name"));
            props.put("nameLang", rs.getString("canonical_name_lang"));
            props.put("placeType", rs.getString("place_type"));
            props.put("datasetId", rs.getString("dataset_id"));
            props.put("datasetName", rs.getString("dataset_name"));
            props.put("recordStatus", rs.getString("record_status"));
            props.put("locationId", rs.getLong("location_id"));
            props.put("locationPrecision", rs.getString("location_precision"));
            props.put("uncertaintyM", rs.getObject("uncertainty_m"));
            props.put("crsConfidence", rs.getString("crs_confidence"));
            props.put("validFromYear", rs.getObject("valid_from_year_astro"));
            props.put("validToYear", rs.getObject("valid_to_year_astro"));
            props.put("timeBoundType", rs.getString("time_bound_type"));

            Map<String, Object> geom = new LinkedHashMap<>();
            geom.put("type", "Point");
            geom.put("coordinates", List.of(
                    ((Number) rs.getObject("representative_lon")).doubleValue(),
                    ((Number) rs.getObject("representative_lat")).doubleValue()));

            Map<String, Object> f = new LinkedHashMap<>();
            f.put("type", "Feature");
            f.put("id", rs.getLong("place_id"));
            f.put("geometry", geom);
            f.put("properties", props);
            return f;
        });

        Map<String, Object> meta = new LinkedHashMap<>();
        meta.put("bbox", List.of(west, south, east, north));
        meta.put("totalInBbox", n);
        meta.put("returned", features.size());
        meta.put("limit", lim);
        meta.put("truncated", n > features.size());

        Map<String, Object> fc = new LinkedHashMap<>();
        fc.put("type", "FeatureCollection");
        fc.put("features", features);
        fc.put("meta", meta);
        return fc;
    }

    // ------------------------------------------------------------------ 概览
    public Dtos.Stats stats() {
        Map<String, Object> r = jdbc.queryForMap("""
                SELECT (SELECT count(*) FROM historical_place) AS places,
                       (SELECT count(*) FROM historical_place_name) AS names,
                       (SELECT count(*) FROM historical_place_location) AS locations,
                       (SELECT count(*) FROM historical_place_location WHERE geom IS NOT NULL) AS with_geom,
                       (SELECT count(*) FROM historical_place_location WHERE crs_confidence = 'unknown') AS unknown_crs,
                       (SELECT count(*) FROM data_dataset) AS datasets,
                       (SELECT count(*) FROM data_source) AS sources,
                       (SELECT count(*) FROM data_quality_issue) AS ledger,
                       (SELECT count(*) FROM historical_place WHERE record_status = 'published') AS published
                """, new MapSqlParameterSource());
        long published = ((Number) r.get("published")).longValue();
        String status = published == 0 ? "staging" : "published";
        return new Dtos.Stats(
                ((Number) r.get("places")).longValue(),
                ((Number) r.get("names")).longValue(),
                ((Number) r.get("locations")).longValue(),
                ((Number) r.get("with_geom")).longValue(),
                ((Number) r.get("unknown_crs")).longValue(),
                ((Number) r.get("datasets")).longValue(),
                ((Number) r.get("sources")).longValue(),
                ((Number) r.get("ledger")).longValue(),
                status);
    }
}
