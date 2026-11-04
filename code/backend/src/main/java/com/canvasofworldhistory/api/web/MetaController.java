package com.canvasofworldhistory.api.web;

import com.canvasofworldhistory.api.config.WriteGuard;
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
    private final WriteGuard writeGuard;

    public MetaController(PlaceQueryService service, NamedParameterJdbcTemplate jdbc,
                          WriteGuard writeGuard) {
        this.service = service;
        this.jdbc = jdbc;
        this.writeGuard = writeGuard;
    }

    /** 写保护状态（只读接口）：前端/运维用它确认这个实例到底能不能写。 */
    @GetMapping("/write-policy")
    public Map<String, Object> writePolicy() {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("database", writeGuard.getDatabaseName() == null ? "(未识别)" : writeGuard.getDatabaseName());
        m.put("allowedDatabases", writeGuard.getAllowedDatabases());
        m.put("writeAllowed", writeGuard.isWriteAllowed());
        m.put("configProblems", writeGuard.getConfigProblems());
        m.put("note", writeGuard.isWriteAllowed()
                ? "本实例允许写入（POST/PUT/PATCH/DELETE）"
                : "本实例只读：写操作将返回 403；GET 不受影响");
        return m;
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
