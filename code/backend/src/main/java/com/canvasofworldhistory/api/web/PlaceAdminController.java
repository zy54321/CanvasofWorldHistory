package com.canvasofworldhistory.api.web;

import com.canvasofworldhistory.api.dto.Dtos;
import com.canvasofworldhistory.api.dto.PlaceAdminDtos;
import com.canvasofworldhistory.api.dto.Requests;
import com.canvasofworldhistory.api.service.PlaceAdminService;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

/**
 * 地点管理写入接口（M2 收尾补齐）。
 *
 * 与 M1 只读接口的分工：
 *  - 列表：/places/admin（keyword 可空，供管理界面浏览）
 *  - 详情：沿用 M1 的 GET /places/{id}（已含 names / locations，不重复实现）
 *  - 写入：本控制器
 *
 * 删除被事件或人物引用的地点时，数据库 RESTRICT 会拒绝，由 ApiExceptionHandler 返回 409。
 */
@RestController
@RequestMapping("/api/v1/places")
public class PlaceAdminController {

    private final PlaceAdminService service;

    public PlaceAdminController(PlaceAdminService service) {
        this.service = service;
    }

    @GetMapping(value = "/admin", produces = MediaType.APPLICATION_JSON_VALUE)
    public Dtos.Page<PlaceAdminDtos.PlaceAdminRow> list(
            @RequestParam(name = "keyword", required = false) String keyword,
            @RequestParam(name = "page", defaultValue = "1") int page,
            @RequestParam(name = "size", defaultValue = "20") int size) {
        return service.list(keyword, page, size);
    }

    @GetMapping(value = "/admin/options", produces = MediaType.APPLICATION_JSON_VALUE)
    public PlaceAdminDtos.PlaceOptions options() {
        return service.options();
    }

    @PostMapping(consumes = MediaType.APPLICATION_JSON_VALUE, produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<Map<String, Object>> create(@RequestBody Requests.PlaceUpsert req) {
        long id = service.create(req);
        return ResponseEntity.status(HttpStatus.CREATED)
                .body(Map.of("placeId", id, "created", true));
    }

    @PutMapping(value = "/{id}", consumes = MediaType.APPLICATION_JSON_VALUE,
            produces = MediaType.APPLICATION_JSON_VALUE)
    public Map<String, Object> update(@PathVariable("id") long id,
                                      @RequestBody Requests.PlaceUpsert req) {
        service.update(id, req);
        return Map.of("placeId", id, "updated", true);
    }

    @DeleteMapping(value = "/{id}", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<PlaceAdminDtos.Deleted> delete(@PathVariable("id") long id) {
        int n = service.delete(id);
        if (n == 0) {
            return ResponseEntity.notFound().build();
        }
        return ResponseEntity.ok(new PlaceAdminDtos.Deleted(id, n));
    }

    // ---------------------------------------------------------------- 名称
    @PostMapping(value = "/{id}/names", consumes = MediaType.APPLICATION_JSON_VALUE,
            produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<Map<String, Object>> addName(@PathVariable("id") long id,
                                                       @RequestBody Requests.PlaceNameUpsert req) {
        long nameId = service.addName(id, req);
        return ResponseEntity.status(HttpStatus.CREATED).body(Map.of("nameId", nameId, "created", true));
    }

    @PutMapping(value = "/{id}/names/{nameId}", consumes = MediaType.APPLICATION_JSON_VALUE,
            produces = MediaType.APPLICATION_JSON_VALUE)
    public Map<String, Object> updateName(@PathVariable("id") long id,
                                          @PathVariable("nameId") long nameId,
                                          @RequestBody Requests.PlaceNameUpsert req) {
        service.updateName(id, nameId, req);
        return Map.of("nameId", nameId, "updated", true);
    }

    @DeleteMapping(value = "/{id}/names/{nameId}", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<PlaceAdminDtos.Deleted> deleteName(@PathVariable("id") long id,
                                                             @PathVariable("nameId") long nameId) {
        int n = service.deleteName(id, nameId);
        if (n == 0) {
            return ResponseEntity.notFound().build();
        }
        return ResponseEntity.ok(new PlaceAdminDtos.Deleted(nameId, n));
    }

    // ---------------------------------------------------------------- 位置
    @PostMapping(value = "/{id}/locations", consumes = MediaType.APPLICATION_JSON_VALUE,
            produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<Map<String, Object>> addLocation(@PathVariable("id") long id,
                                                           @RequestBody Requests.PlaceLocationUpsert req) {
        long locationId = service.addLocation(id, req);
        return ResponseEntity.status(HttpStatus.CREATED)
                .body(Map.of("locationId", locationId, "created", true));
    }

    @PutMapping(value = "/{id}/locations/{locationId}", consumes = MediaType.APPLICATION_JSON_VALUE,
            produces = MediaType.APPLICATION_JSON_VALUE)
    public Map<String, Object> updateLocation(@PathVariable("id") long id,
                                              @PathVariable("locationId") long locationId,
                                              @RequestBody Requests.PlaceLocationUpsert req) {
        service.updateLocation(id, locationId, req);
        return Map.of("locationId", locationId, "updated", true);
    }

    @DeleteMapping(value = "/{id}/locations/{locationId}", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<PlaceAdminDtos.Deleted> deleteLocation(@PathVariable("id") long id,
                                                                 @PathVariable("locationId") long locationId) {
        int n = service.deleteLocation(id, locationId);
        if (n == 0) {
            return ResponseEntity.notFound().build();
        }
        return ResponseEntity.ok(new PlaceAdminDtos.Deleted(locationId, n));
    }
}
