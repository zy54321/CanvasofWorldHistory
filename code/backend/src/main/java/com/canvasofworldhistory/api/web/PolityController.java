package com.canvasofworldhistory.api.web;

import com.canvasofworldhistory.api.dto.Dtos;
import com.canvasofworldhistory.api.dto.PolityDtos;
import com.canvasofworldhistory.api.dto.Requests;
import com.canvasofworldhistory.api.service.PolityService;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/**
 * 历史政权 API（M3）。
 *
 * <p>只做矩阵需要的最小能力：列地区、搜政权、建政权。
 * 不建独立政权管理平台；关联维护挂在 {@code /api/v1/events/{id}/polities}。
 */
@RestController
@RequestMapping("/api/v1/polities")
public class PolityController {

    private final PolityService service;

    public PolityController(PolityService service) {
        this.service = service;
    }

    /** 展示地区（10 个固定值，含中文标签）；前端不维护第二份清单。 */
    @GetMapping(value = "/regions", produces = MediaType.APPLICATION_JSON_VALUE)
    public List<PolityDtos.Region> regions() {
        return service.regions();
    }

    @GetMapping(produces = MediaType.APPLICATION_JSON_VALUE)
    public Dtos.Page<PolityDtos.PolityHit> list(
            @RequestParam(name = "keyword", required = false) String keyword,
            @RequestParam(name = "region", required = false) String region,
            @RequestParam(name = "page", defaultValue = "1") int page,
            @RequestParam(name = "size", defaultValue = "20") int size) {
        return service.list(keyword, region, page, size);
    }

    @PostMapping(consumes = MediaType.APPLICATION_JSON_VALUE, produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<PolityDtos.PolityHit> create(@RequestBody Requests.PolityUpsert req) {
        return ResponseEntity.status(HttpStatus.CREATED).body(service.create(req));
    }

    /**
     * 政权状态变更（staging / published / rejected）。
     *
     * <p>只有状态一个字段：不做审核流、不记录审批人。rejected 之后该政权不再进入矩阵，
     * 但事件本体、事件—政权关联、地图标记都保留，随时可以改回来。
     */
    @PatchMapping(value = "/{id}/status",
            consumes = MediaType.APPLICATION_JSON_VALUE, produces = MediaType.APPLICATION_JSON_VALUE)
    public PolityDtos.PolityHit updateStatus(@PathVariable long id, @RequestBody Requests.PolityStatus req) {
        return service.updateStatus(id, req == null ? null : req.recordStatus());
    }
}
