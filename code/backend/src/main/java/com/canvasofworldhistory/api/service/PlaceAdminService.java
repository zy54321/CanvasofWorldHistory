package com.canvasofworldhistory.api.service;

import com.canvasofworldhistory.api.dto.Dtos;
import com.canvasofworldhistory.api.dto.PlaceAdminDtos;
import com.canvasofworldhistory.api.dto.Requests;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.namedparam.MapSqlParameterSource;
import org.springframework.jdbc.core.namedparam.NamedParameterJdbcTemplate;
import org.springframework.jdbc.support.GeneratedKeyHolder;
import org.springframework.jdbc.support.KeyHolder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/**
 * 地点管理写入（M2 收尾补齐）。
 *
 * 为什么需要新写接口：M1 只交付了只读查询，而 M2 要求地点可新增/编辑/删除。
 *
 * 关键约束（都以 V2/V5 数据库规则为准，服务层只做更清楚的报错）：
 *  - historical_place.dataset_id 非空外键：人工录入统一落到 V5 新增的
 *    data_source='manual' / data_dataset='manual_entry'，**不冒用第三方来源**。
 *  - C05：created_by='manual' 时 created_from_source_record_id 可为空。
 *  - C14/C15：坐标系 unknown 或几何为空的地点不得置为 published —— 本表 record_status
 *    值域只有 staging/rejected/merged，服务端只接受 staging/rejected。
 *  - 坐标未知时 geom 为空、geom_type 为空，落一条「未定位」记录，不填假坐标。
 */
@Service
public class PlaceAdminService {

    private static final int MAX_PAGE_SIZE = 100;

    private static final String MANUAL_DATASET = "manual_entry";

    private static final List<String> PLACE_TYPES = List.of(
            "admin_center_prefecture", "admin_center_county", "admin_center_other",
            "settlement", "unknown");
    private static final List<String> PLACE_RECORD_STATUS = List.of("staging", "rejected");
    private static final String NAME_TYPES =
            "('primary','alternate','transliteration','historical','colloquial')";
    private static final String TIME_BOUND_TYPES =
            "('exact','bounded','exact_or_bounded','tpq_taq','derived_tpq_taq','snapshot','unknown')";
    private static final String LOCATION_PRECISIONS = "('precise','approximate','rough','unknown')";
    private static final String CRS_CONFIDENCES = "('confirmed','inferred','unknown')";
    private static final String CHILD_STATUS = "('staging','published','rejected')";

    // ---- 几何筛选：按"是否存在这类带 geom 的位置行"判断（存在性，不是代表点）----
    private static final String GEOM_POINT = """
            EXISTS (SELECT 1 FROM historical_place_location l
                     WHERE l.place_id = p.place_id AND l.geom IS NOT NULL AND l.geom_type = 'Point')""";
    private static final String GEOM_LINE = """
            EXISTS (SELECT 1 FROM historical_place_location l
                     WHERE l.place_id = p.place_id AND l.geom IS NOT NULL AND l.geom_type = 'LineString')""";
    private static final String GEOM_POLYGON = """
            EXISTS (SELECT 1 FROM historical_place_location l
                     WHERE l.place_id = p.place_id AND l.geom IS NOT NULL
                       AND l.geom_type IN ('Polygon','MultiPolygon'))""";
    private static final String GEOM_NONE = """
            NOT EXISTS (SELECT 1 FROM historical_place_location l
                         WHERE l.place_id = p.place_id AND l.geom IS NOT NULL)""";

    // ---- 名称质量四分类：与 PlaceNames.quality() 必须逐条等价 ----
    private static final String NOT_PLACEHOLDER = """
            btrim(coalesce(p.canonical_name, '')) <> ''
              AND lower(btrim(p.canonical_name)) NOT IN """ + PlaceNames.PLACEHOLDER_SQL_LIST;
    private static final String IS_PLACEHOLDER = """
            lower(btrim(coalesce(p.canonical_name, ''))) IN """ + PlaceNames.PLACEHOLDER_SQL_LIST;
    private static final String HAS_ALT = """
            EXISTS (SELECT 1 FROM historical_place_name n
                     WHERE n.place_id = p.place_id AND btrim(coalesce(n.name_text, '')) <> '')""";

    private static final String QUALITY_VALID = "(" + NOT_PLACEHOLDER + ")";
    private static final String QUALITY_ALIAS = "(NOT (" + NOT_PLACEHOLDER + ") AND " + HAS_ALT + ")";
    private static final String QUALITY_PLACEHOLDER =
            "(NOT (" + NOT_PLACEHOLDER + ") AND NOT " + HAS_ALT + " AND " + IS_PLACEHOLDER + ")";
    private static final String QUALITY_NO_NAME =
            "(NOT (" + NOT_PLACEHOLDER + ") AND NOT " + HAS_ALT + " AND NOT " + IS_PLACEHOLDER + ")";

    private final NamedParameterJdbcTemplate jdbc;

    public PlaceAdminService(NamedParameterJdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    // ================================================================ 选项
    public PlaceAdminDtos.PlaceOptions options() {
        return new PlaceAdminDtos.PlaceOptions(
                PLACE_TYPES, List.of("manual", "unknown"), PLACE_RECORD_STATUS,
                List.of("primary", "alternate", "transliteration", "historical", "colloquial"),
                List.of("exact", "bounded", "exact_or_bounded", "tpq_taq",
                        "derived_tpq_taq", "snapshot", "unknown"),
                List.of("precise", "approximate", "rough", "unknown"),
                List.of("confirmed", "inferred", "unknown"));
    }

    // ================================================================ 列表
    /**
     * 列表查询（V1.0 内容管理专项）。
     *
     * 三个口径必须说清楚，否则"筛选"和"显示的条数"会自相矛盾：
     *  1) 几何筛选按**关联位置记录的存在性**判断，不是按代表点：一个地点可能同时有
     *     点、线、面，于是它会同时出现在 point / line / polygon 三个筛选里 —— 这是对的。
     *     "无几何"= 一条带 geom 的位置记录都没有（不是"没有代表点"）。
     *  2) 名称质量四分类互斥且穷尽，与 PlaceNames.quality() 同口径：
     *     占位词清单直接取 PlaceNames.PLACEHOLDER_SQL_LIST，避免两处漂移。
     *  3) 逐类几何数量用一次 LATERAL 聚合取，**不对每行发额外查询**（无 N+1）。
     */
    public Dtos.Page<PlaceAdminDtos.PlaceAdminRow> list(String keyword, String geomType,
                                                        String nameQuality, int page, int size) {
        int p = Math.max(1, page);
        int s = Math.min(Math.max(1, size), MAX_PAGE_SIZE);
        String kw = keyword == null ? "" : keyword.trim();
        String like = kw.isEmpty() ? null : "%" + kw + "%";
        String geom = geomType == null ? "" : geomType.trim().toLowerCase(Locale.ROOT);
        String quality = nameQuality == null ? "" : nameQuality.trim().toLowerCase(Locale.ROOT);

        MapSqlParameterSource prm = new MapSqlParameterSource()
                .addValue("like", like)
                .addValue("limit", s)
                .addValue("offset", (p - 1) * s);

        List<String> conds = new ArrayList<>();
        if (like != null) {
            conds.add("""
                    (p.canonical_name ILIKE :like
                     OR p.place_id IN (SELECT n.place_id FROM historical_place_name n
                                        WHERE n.name_text ILIKE :like))""");
        }
        switch (geom) {
            case "point" -> conds.add(GEOM_POINT);
            case "line" -> conds.add(GEOM_LINE);
            case "polygon", "poly" -> conds.add(GEOM_POLYGON);
            case "none" -> conds.add(GEOM_NONE);
            case "", "all" -> { }
            default -> throw new ResponseStatusException(HttpStatus.BAD_REQUEST,
                    "geomType 只接受 point/line/polygon/none/all");
        }
        switch (quality) {
            case "valid" -> conds.add(QUALITY_VALID);
            case "alias_only" -> conds.add(QUALITY_ALIAS);
            case "placeholder" -> conds.add(QUALITY_PLACEHOLDER);
            case "no_name" -> conds.add(QUALITY_NO_NAME);
            case "", "all" -> { }
            default -> throw new ResponseStatusException(HttpStatus.BAD_REQUEST,
                    "nameQuality 只接受 valid/alias_only/placeholder/no_name/all");
        }
        String where = conds.isEmpty() ? "" : " WHERE " + String.join(" AND ", conds);

        // 排序：有可展示地名的排前面 → 最近更新 → id 倒序。
        // 起因：Pleiades 切片有 3,856 条占位名，纯按 updated_at 排会让首页 20 行
        // 全是"未命名地点"，列表看起来像坏了。加名称桶后首页即可读。
        // 代价实测：深翻页 SQL 25ms → 42ms（仍远低于 300ms 目标，报告已记录）。
        // 布尔表达式 DESC 即 true 在前，比 CASE WHEN 更短且同样走排序键。
        String orderBy = " ORDER BY (" + NOT_PLACEHOLDER + ") DESC, "
                + "p.updated_at DESC NULLS LAST, p.place_id DESC ";

        Long total = jdbc.queryForObject("SELECT count(*) FROM historical_place p" + where, prm, Long.class);
        long n = total == null ? 0 : total;
        if (n == 0) {
            return Dtos.Page.of(List.of(), p, s, 0);
        }

        // 先只把"当前页这 20 个 place_id"取出来（走 pk 索引，深翻页也是毫秒级），
        // 再对这 20 行做计数/别名/坐标的三次 LATERAL。
        // 反过来写（把 LATERAL 放在带 LIMIT 的外层）会让 PG 先给 5.8 万行都算一遍
        // 聚合再排序截断 —— 实测深翻页 369ms，改成本形状后 25ms。
        String sql = """
                WITH page_ids AS (
                    SELECT p.place_id
                      FROM historical_place p
                """ + where + """
        """ + orderBy + """
                     LIMIT :limit OFFSET :offset
                )
                SELECT p.place_id, p.canonical_name, p.canonical_name_lang, p.place_type,
                       p.description, p.record_status, p.dataset_id,
                       d.display_name AS dataset_name,
                       (SELECT count(*) FROM historical_place_name n WHERE n.place_id = p.place_id) AS name_count,
                       gc.loc_total, gc.geom_total, gc.points, gc.lines, gc.polys,
                       loc.representative_lon, loc.representative_lat, (loc.geom IS NOT NULL) AS has_geom,
                       alt.alt_name
                  FROM page_ids k
                  JOIN historical_place p ON p.place_id = k.place_id
                  JOIN data_dataset d ON d.dataset_id = p.dataset_id
                  LEFT JOIN LATERAL (
                       -- 一次聚合拿到四类计数，避免"每个地点一条 SQL"的 N+1
                       SELECT count(*) AS loc_total,
                              count(*) FILTER (WHERE l.geom IS NOT NULL) AS geom_total,
                              count(*) FILTER (WHERE l.geom IS NOT NULL AND l.geom_type = 'Point') AS points,
                              count(*) FILTER (WHERE l.geom IS NOT NULL AND l.geom_type = 'LineString') AS lines,
                              count(*) FILTER (WHERE l.geom IS NOT NULL
                                                 AND l.geom_type IN ('Polygon','MultiPolygon')) AS polys
                         FROM historical_place_location l
                        WHERE l.place_id = p.place_id) gc ON TRUE
                  LEFT JOIN LATERAL (
                       SELECT n.name_text AS alt_name
                         FROM historical_place_name n
                        WHERE n.place_id = p.place_id
                          AND btrim(coalesce(n.name_text, '')) <> ''
                        ORDER BY CASE n.name_type WHEN 'primary' THEN 0 ELSE 1 END, n.name_id
                        LIMIT 1) alt ON TRUE
                  LEFT JOIN LATERAL (
                       SELECT l.representative_lon, l.representative_lat, l.geom
                         FROM historical_place_location l
                        WHERE l.place_id = p.place_id AND l.geom IS NOT NULL
                          AND l.crs_confidence <> 'unknown'
                        ORDER BY l.location_id LIMIT 1) loc ON TRUE
                 ORDER BY p.updated_at DESC NULLS LAST, p.place_id DESC
                """;

        List<PlaceAdminDtos.PlaceAdminRow> items = jdbc.query(sql, prm,
                (rs, i) -> {
                    String canonical = rs.getString("canonical_name");
                    String altName = rs.getString("alt_name");
                    boolean hasAlt = altName != null && !altName.trim().isEmpty();
                    return new PlaceAdminDtos.PlaceAdminRow(
                            rs.getLong("place_id"),
                            canonical,
                            rs.getString("canonical_name_lang"),
                            rs.getString("place_type"),
                            rs.getString("description"),
                            rs.getString("record_status"),
                            rs.getString("dataset_id"),
                            rs.getInt("name_count"),
                            rs.getInt("loc_total"),
                            (Double) rs.getObject("representative_lon"),
                            (Double) rs.getObject("representative_lat"),
                            rs.getInt("geom_total") > 0,
                            PlaceNames.displayName(canonical, altName),
                            PlaceNames.quality(canonical, hasAlt),
                            rs.getString("dataset_name"),
                            rs.getInt("points"),
                            rs.getInt("lines"),
                            rs.getInt("polys"),
                            rs.getInt("geom_total"));
                });

        return Dtos.Page.of(items, p, s, n);
    }

    // ================================================================ 增删改
    @Transactional
    public long create(Requests.PlaceUpsert req) {
        String name = PersonService.requireText(req.canonicalName(), "canonicalName");
        String type = req.placeType() == null || req.placeType().isBlank()
                ? "unknown" : req.placeType().trim();
        if (!PLACE_TYPES.contains(type)) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST,
                    "placeType 非法：" + type + "，允许值 " + PLACE_TYPES);
        }
        String status = req.recordStatus() == null
                ? "staging" : enumOf(req.recordStatus(), PLACE_RECORD_STATUS, "recordStatus");

        // grain_key 先给临时唯一值，插入后用 place_id 定稿，保证 C04(dataset_id,grain_key) 唯一且可读
        String tmpGrain = "manual-" + java.util.UUID.randomUUID();

        MapSqlParameterSource prm = new MapSqlParameterSource()
                .addValue("ds", MANUAL_DATASET)
                .addValue("grain", tmpGrain)
                .addValue("name", name)
                .addValue("lang", PersonService.blankToNull(req.canonicalNameLang()))
                .addValue("type", type)
                .addValue("basis", PersonService.blankToNull(req.placeTypeBasisNote()))
                .addValue("desc", PersonService.blankToNull(req.description()))
                .addValue("notes", PersonService.blankToNull(req.notes()))
                .addValue("status", status);

        KeyHolder keys = new GeneratedKeyHolder();
        jdbc.update("""
                INSERT INTO historical_place (dataset_id, grain_key, canonical_name, canonical_name_lang,
                                              place_type, place_type_source, place_type_basis_note,
                                              description, notes, record_status, created_by,
                                              created_at, updated_at)
                VALUES (:ds, :grain, :name, :lang, :type, 'manual', :basis,
                        :desc, :notes, :status, 'manual', now(), now())
                """, prm, keys, new String[]{"place_id"});

        long id = keys.getKey() == null ? -1L : keys.getKey().longValue();
        jdbc.update("UPDATE historical_place SET grain_key = :g WHERE place_id = :id",
                new MapSqlParameterSource("g", "manual-" + id).addValue("id", id));
        return id;
    }

    @Transactional
    public void update(long placeId, Requests.PlaceUpsert req) {
        requirePlace(placeId);
        String name = PersonService.requireText(req.canonicalName(), "canonicalName");
        String type = req.placeType() == null || req.placeType().isBlank()
                ? "unknown" : req.placeType().trim();
        if (!PLACE_TYPES.contains(type)) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST,
                    "placeType 非法：" + type + "，允许值 " + PLACE_TYPES);
        }
        if (req.recordStatus() != null) {
            enumOf(req.recordStatus(), PLACE_RECORD_STATUS, "recordStatus");
        }

        jdbc.update("""
                UPDATE historical_place
                   SET canonical_name = :name, canonical_name_lang = :lang,
                       place_type = :type, place_type_basis_note = :basis,
                       description = :desc, notes = :notes,
                       -- 管理界面列表按 updated_at 倒序，编辑必须推进它，否则排序名不副实
                       updated_at = now()
                       %s
                 WHERE place_id = :id
                """.formatted(req.recordStatus() == null ? "" : ", record_status = :status"),
                new MapSqlParameterSource()
                        .addValue("id", placeId)
                        .addValue("name", name)
                        .addValue("lang", PersonService.blankToNull(req.canonicalNameLang()))
                        .addValue("type", type)
                        .addValue("basis", PersonService.blankToNull(req.placeTypeBasisNote()))
                        .addValue("desc", PersonService.blankToNull(req.description()))
                        .addValue("notes", PersonService.blankToNull(req.notes()))
                        .addValue("status", req.recordStatus()));
    }

    @Transactional
    public int delete(long placeId) {
        // 删除语义（M3 前置收尾实测暴露的问题）：
        //  historical_place_name / historical_place_location 的 FK 没有 ON DELETE 级联，
        //  所以「删除一个加过别名的地点」会直接报 23503，界面上表现为莫名其妙的「仍被引用」。
        //  这两张表属于地点聚合内部，人工录入的场景应当连带删除。
        //
        //  但对导入数据集的地点不这么做——它们的名称/位置是导入证据，不能在管理界面里连带抹掉，
        //  要处理走数据治理流程。事件/人物/候选/台账对该地点的引用仍然交给数据库判定（RESTRICT
        //  或默认 NO ACTION），一律转成 409，绝不连带删除其他业务对象。
        List<Map<String, Object>> rows = jdbc.queryForList(
                "SELECT dataset_id FROM historical_place WHERE place_id = :id",
                new MapSqlParameterSource("id", placeId));
        if (rows.isEmpty()) {
            return 0;
        }
        Object ds = rows.get(0).get("dataset_id");
        if (!MANUAL_DATASET.equals(String.valueOf(ds))) {
            throw new ResponseStatusException(HttpStatus.CONFLICT,
                    "该地点属于导入数据集 " + ds + "，不允许在管理界面删除（其名称与位置是导入证据）");
        }
        MapSqlParameterSource prm = new MapSqlParameterSource("id", placeId);
        jdbc.update("DELETE FROM historical_place_name WHERE place_id = :id", prm);
        jdbc.update("DELETE FROM historical_place_location WHERE place_id = :id", prm);
        return jdbc.update("DELETE FROM historical_place WHERE place_id = :id", prm);
    }

    // ================================================================ 名称
    @Transactional
    public long addName(long placeId, Requests.PlaceNameUpsert req) {
        requirePlace(placeId);
        MapSqlParameterSource prm = nameParams(req).addValue("pid", placeId);
        KeyHolder keys = new GeneratedKeyHolder();
        jdbc.update("""
                INSERT INTO historical_place_name (place_id, name_text, name_lang, name_type,
                                                   transliteration_scheme,
                                                   valid_from_year_astro, valid_to_year_astro,
                                                   time_bound_type, time_note, notes,
                                                   record_status, created_by, created_at, updated_at)
                VALUES (:pid, :text, :lang, :type, :scheme, :vf, :vt, :tbt, :tn, :notes, :status, 'manual',
                        now(), now())
                """, prm, keys, new String[]{"name_id"});
        return keys.getKey() == null ? -1L : keys.getKey().longValue();
    }

    @Transactional
    public void updateName(long placeId, long nameId, Requests.PlaceNameUpsert req) {
        requireName(nameId, placeId);
        jdbc.update("""
                UPDATE historical_place_name
                   SET name_text = :text, name_lang = :lang, name_type = :type,
                       transliteration_scheme = :scheme,
                       valid_from_year_astro = :vf, valid_to_year_astro = :vt,
                       time_bound_type = :tbt, time_note = :tn, notes = :notes,
                       record_status = :status
                 WHERE name_id = :id AND place_id = :pid
                """, nameParams(req).addValue("id", nameId).addValue("pid", placeId));
    }

    @Transactional
    public int deleteName(long placeId, long nameId) {
        return jdbc.update("DELETE FROM historical_place_name WHERE name_id = :id AND place_id = :pid",
                new MapSqlParameterSource("id", nameId).addValue("pid", placeId));
    }

    // ================================================================ 位置
    @Transactional
    public long addLocation(long placeId, Requests.PlaceLocationUpsert req) {
        requirePlace(placeId);
        MapSqlParameterSource prm = locationParams(req).addValue("pid", placeId);
        KeyHolder keys = new GeneratedKeyHolder();
        jdbc.update("""
                INSERT INTO historical_place_location (
                        place_id, geom, geom_type, representative_lon, representative_lat,
                        original_x, original_y, original_crs, crs_confidence, axis_order_verified,
                        location_precision, uncertainty_m,
                        valid_from_year_astro, valid_to_year_astro, time_bound_type,
                        notes, record_status, created_by, created_at, updated_at)
                VALUES (:pid,
                        CASE WHEN :lon::double precision IS NULL OR :lat::double precision IS NULL
                             THEN NULL
                             ELSE ST_SetSRID(ST_MakePoint(:lon, :lat), 4326) END,
                        CASE WHEN :lon::double precision IS NULL OR :lat::double precision IS NULL
                             THEN NULL ELSE 'Point' END,
                        :lon, :lat,
                        CASE WHEN :lon::double precision IS NULL THEN NULL ELSE :lon::text END,
                        CASE WHEN :lat::double precision IS NULL THEN NULL ELSE :lat::text END,
                        CASE WHEN :lon::double precision IS NULL THEN NULL ELSE 'EPSG:4326' END,
                        :crs, false, :prec, :unc, :vf, :vt, :tbt, :notes, :status, 'manual', now(), now())
                """, prm, keys, new String[]{"location_id"});
        return keys.getKey() == null ? -1L : keys.getKey().longValue();
    }

    @Transactional
    public void updateLocation(long placeId, long locationId, Requests.PlaceLocationUpsert req) {
        requireLocation(locationId, placeId);
        jdbc.update("""
                UPDATE historical_place_location
                   SET geom = CASE WHEN :lon::double precision IS NULL OR :lat::double precision IS NULL
                                   THEN NULL
                                   ELSE ST_SetSRID(ST_MakePoint(:lon, :lat), 4326) END,
                       geom_type = CASE WHEN :lon::double precision IS NULL
                                        THEN NULL ELSE 'Point' END,
                       representative_lon = :lon, representative_lat = :lat,
                       original_x = CASE WHEN :lon::double precision IS NULL THEN NULL ELSE :lon::text END,
                       original_y = CASE WHEN :lat::double precision IS NULL THEN NULL ELSE :lat::text END,
                       original_crs = CASE WHEN :lon::double precision IS NULL THEN NULL ELSE 'EPSG:4326' END,
                       crs_confidence = :crs, location_precision = :prec, uncertainty_m = :unc,
                       valid_from_year_astro = :vf, valid_to_year_astro = :vt,
                       time_bound_type = :tbt, notes = :notes, record_status = :status
                 WHERE location_id = :id AND place_id = :pid
                """, locationParams(req).addValue("id", locationId).addValue("pid", placeId));
    }

    @Transactional
    public int deleteLocation(long placeId, long locationId) {
        return jdbc.update("DELETE FROM historical_place_location WHERE location_id = :id AND place_id = :pid",
                new MapSqlParameterSource("id", locationId).addValue("pid", placeId));
    }

    // ================================================================ 内部
    private MapSqlParameterSource nameParams(Requests.PlaceNameUpsert req) {
        String type = PersonService.requireEnum(
                PersonService.requireText(req.nameType(), "nameType"), NAME_TYPES, "nameType");
        String scheme = PersonService.blankToNull(req.transliterationScheme());
        if (scheme != null && !"transliteration".equals(type)) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST,
                    "transliterationScheme 仅在 nameType=transliteration 时可用");
        }
        String tbt = req.timeBoundType() == null || req.timeBoundType().isBlank()
                ? "unknown" : PersonService.requireEnum(req.timeBoundType(), TIME_BOUND_TYPES, "timeBoundType");
        if ("exact".equals(tbt) && (req.validFromYearAstro() == null || req.validToYearAstro() == null)) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST,
                    "timeBoundType=exact 时起止年都必须给出");
        }
        if ("unknown".equals(tbt) && req.validFromYearAstro() != null) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST,
                    "timeBoundType=unknown 时不得给出年份");
        }
        Integer vf = req.validFromYearAstro();
        Integer vt = req.validToYearAstro();
        if (vf != null && vt != null && vf > vt) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST,
                    "名称有效期起年不得晚于止年（天文纪年整数比较）");
        }
        return new MapSqlParameterSource()
                .addValue("text", PersonService.requireText(req.nameText(), "nameText"))
                .addValue("lang", PersonService.blankToNull(req.nameLang()))
                .addValue("type", type)
                .addValue("scheme", scheme)
                .addValue("vf", vf)
                .addValue("vt", vt)
                .addValue("tbt", tbt)
                .addValue("tn", PersonService.blankToNull(req.timeNote()))
                .addValue("notes", PersonService.blankToNull(req.notes()))
                .addValue("status", req.recordStatus() == null
                        ? "staging" : PersonService.requireEnum(req.recordStatus(), CHILD_STATUS, "recordStatus"));
    }

    private MapSqlParameterSource locationParams(Requests.PlaceLocationUpsert req) {
        Double lon = req.lon();
        Double lat = req.lat();
        if ((lon == null) != (lat == null)) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST,
                    "经度与纬度必须同时给出或同时为空（不允许单侧坐标）");
        }
        if (lon != null && (lon < -180 || lon > 180 || lat < -90 || lat > 90)) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST,
                    "经纬度越界：经度 -180~180，纬度 -90~90");
        }
        String prec = req.locationPrecision() == null || req.locationPrecision().isBlank()
                ? "unknown" : PersonService.requireEnum(req.locationPrecision(), LOCATION_PRECISIONS, "locationPrecision");
        String crs = req.crsConfidence() == null || req.crsConfidence().isBlank()
                ? (lon == null ? "unknown" : "inferred")
                : PersonService.requireEnum(req.crsConfidence(), CRS_CONFIDENCES, "crsConfidence");
        String tbt = req.timeBoundType() == null || req.timeBoundType().isBlank()
                ? "unknown" : PersonService.requireEnum(req.timeBoundType(), TIME_BOUND_TYPES, "timeBoundType");
        if ("exact".equals(tbt) && (req.validFromYearAstro() == null || req.validToYearAstro() == null)) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST,
                    "timeBoundType=exact 时起止年都必须给出");
        }
        String status = req.recordStatus() == null
                ? "staging" : PersonService.requireEnum(req.recordStatus(), CHILD_STATUS, "recordStatus");
        // C14/C15：坐标系 unknown 或几何为空不得 published
        if ("published".equals(status) && (lon == null || "unknown".equals(crs))) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST,
                    "坐标为未知或坐标系置信度为 unknown 时，位置行不允许置为 published（C14/C15）");
        }
        Integer vf = req.validFromYearAstro();
        Integer vt = req.validToYearAstro();
        if (vf != null && vt != null && vf > vt) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST,
                    "位置有效期起年不得晚于止年");
        }
        return new MapSqlParameterSource()
                .addValue("lon", lon)
                .addValue("lat", lat)
                .addValue("prec", prec)
                .addValue("unc", req.uncertaintyM())
                .addValue("crs", crs)
                .addValue("vf", vf)
                .addValue("vt", vt)
                .addValue("tbt", tbt)
                .addValue("notes", PersonService.blankToNull(req.notes()))
                .addValue("status", status);
    }

    private void requirePlace(long placeId) {
        Integer ok = jdbc.query("SELECT 1 FROM historical_place WHERE place_id = :id",
                new MapSqlParameterSource("id", placeId), rs -> rs.next() ? 1 : null);
        if (ok == null) {
            throw PersonService.notFound("地点", placeId);
        }
    }

    private void requireName(long nameId, long placeId) {
        Integer ok = jdbc.query("SELECT 1 FROM historical_place_name WHERE name_id = :id AND place_id = :pid",
                new MapSqlParameterSource("id", nameId).addValue("pid", placeId),
                rs -> rs.next() ? 1 : null);
        if (ok == null) {
            throw PersonService.notFound("地点名称", nameId);
        }
    }

    private void requireLocation(long locationId, long placeId) {
        Integer ok = jdbc.query("SELECT 1 FROM historical_place_location WHERE location_id = :id AND place_id = :pid",
                new MapSqlParameterSource("id", locationId).addValue("pid", placeId),
                rs -> rs.next() ? 1 : null);
        if (ok == null) {
            throw PersonService.notFound("地点位置", locationId);
        }
    }

    private static String enumOf(String v, List<String> allowed, String field) {
        String t = PersonService.requireText(v, field);
        if (!allowed.contains(t)) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST,
                    field + " 非法：" + t + "，允许值 " + allowed);
        }
        return t;
    }
}
