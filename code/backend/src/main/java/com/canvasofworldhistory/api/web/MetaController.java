package com.canvasofworldhistory.api.web;

import com.canvasofworldhistory.api.dto.Dtos;
import com.canvasofworldhistory.api.service.PlaceQueryService;
import org.springframework.jdbc.core.namedparam.NamedParameterJdbcTemplate;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.time.OffsetDateTime;
import java.util.LinkedHashMap;
import java.util.Map;

/** 概览与健康检查（前端页头用，也用于确认后端连的是哪个库）。 */
@RestController
@RequestMapping("/api/v1/meta")
public class MetaController {

    private final PlaceQueryService service;
    private final NamedParameterJdbcTemplate jdbc;

    public MetaController(PlaceQueryService service, NamedParameterJdbcTemplate jdbc) {
        this.service = service;
        this.jdbc = jdbc;
    }

    @GetMapping("/stats")
    public Dtos.Stats stats() {
        return service.stats();
    }

    @GetMapping("/health")
    public Map<String, Object> health() {
        Map<String, Object> m = new LinkedHashMap<>();
        Map<String, Object> db = jdbc.queryForMap(
                "select current_database() as db, current_user as usr, version() as ver",
                new org.springframework.jdbc.core.namedparam.MapSqlParameterSource());
        m.put("status", "ok");
        m.put("database", db.get("db"));
        m.put("user", db.get("usr"));
        m.put("postgres", String.valueOf(db.get("ver")).split(" ")[1]);
        m.put("time", OffsetDateTime.now().toString());
        return m;
    }
}
