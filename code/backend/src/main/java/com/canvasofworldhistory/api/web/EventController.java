package com.canvasofworldhistory.api.web;

import com.canvasofworldhistory.api.dto.Dtos;
import com.canvasofworldhistory.api.dto.EventDtos;
import com.canvasofworldhistory.api.dto.PolityDtos;
import com.canvasofworldhistory.api.dto.Requests;
import com.canvasofworldhistory.api.service.EventService;
import com.canvasofworldhistory.api.service.PolityService;
import com.canvasofworldhistory.api.service.TimeMapService;
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

import java.util.List;
import java.util.Map;

/**
 * 事件 API（M2-2A）。
 * 时间字段一律天文学纪年整数（公元前 1 年 = 0），接口不做 BCE/CE 标签换算。
 */
@RestController
@RequestMapping("/api/v1/events")
public class EventController {

    private final EventService service;
    private final TimeMapService timeMap;
    private final PolityService polities;

    public EventController(EventService service, TimeMapService timeMap, PolityService polities) {
        this.service = service;
        this.timeMap = timeMap;
        this.polities = polities;
    }

    /** 列表 / 关键词搜索（标题与摘要）。keyword 为空则返回全部。 */
    @GetMapping(produces = MediaType.APPLICATION_JSON_VALUE)
    public Dtos.Page<EventDtos.EventHit> list(
            @RequestParam(name = "keyword", required = false) String keyword,
            @RequestParam(name = "page", defaultValue = "1") int page,
            @RequestParam(name = "size", defaultValue = "20") int size) {
        return service.search(keyword, page, size);
    }

    /**
     * 地图事件标记（M3）：时间窗口 ∩ 视野，一个（事件 × 地点）一条，GeoJSON。
     * bbox 顺序为 west,south,east,north；from / to 为天文学纪年整数且端点包含。
     */
    @GetMapping(value = "/map", produces = MediaType.APPLICATION_JSON_VALUE)
    public Map<String, Object> map(
            @RequestParam("bbox") String bbox,
            @RequestParam("from") int from,
            @RequestParam("to") int to,
            @RequestParam(name = "limit", required = false) Integer limit) {
        TimeMapService.requireWindow(from, to);
        String[] parts = bbox.split(",");
        if (parts.length != 4) {
            throw new org.springframework.web.server.ResponseStatusException(
                    HttpStatus.BAD_REQUEST, "bbox 需要 4 个数字：west,south,east,north");
        }
        double w, s, e, n;
        try {
            w = Double.parseDouble(parts[0].trim());
            s = Double.parseDouble(parts[1].trim());
            e = Double.parseDouble(parts[2].trim());
            n = Double.parseDouble(parts[3].trim());
        } catch (NumberFormatException ex) {
            throw new org.springframework.web.server.ResponseStatusException(
                    HttpStatus.BAD_REQUEST, "bbox 含非数字：" + bbox);
        }
        return timeMap.mapFeatures(w, s, e, n, from, to, limit);
    }

    /**
     * 历史时空矩阵（M3）：地区 → 政权 → 时间段 → 事件。
     * step 只允许 1 / 10 / 100；offset 为跳过的列数（横向滚动加载更多）。
     */
    @GetMapping(value = "/matrix", produces = MediaType.APPLICATION_JSON_VALUE)
    public PolityDtos.MatrixResponse matrix(
            @RequestParam("from") int from,
            @RequestParam(name = "step", defaultValue = "10") int step,
            @RequestParam(name = "count", defaultValue = "12") int count,
            @RequestParam(name = "offset", defaultValue = "0") int offset,
            @RequestParam(name = "region", required = false) String region) {
        return timeMap.matrix(from, step, count, offset, region);
    }

    /** 事件的政权关联（M3）。 */
    @GetMapping(value = "/{id}/polities", produces = MediaType.APPLICATION_JSON_VALUE)
    public List<PolityDtos.EventPolityRow> eventPolities(@PathVariable("id") long id) {
        return polities.byEvent(id);
    }

    @PostMapping(value = "/{id}/polities", consumes = MediaType.APPLICATION_JSON_VALUE,
            produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<PolityDtos.EventPolityRow> linkPolity(
            @PathVariable("id") long id, @RequestBody Requests.EventPolityLink req) {
        return ResponseEntity.status(HttpStatus.CREATED).body(polities.link(id, req));
    }

    @DeleteMapping(value = "/{id}/polities/{linkId}", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<Requests.Deleted> unlinkPolity(
            @PathVariable("id") long id, @PathVariable("linkId") long linkId) {
        return ResponseEntity.ok(new Requests.Deleted(linkId, polities.unlink(id, linkId)));
    }

    @GetMapping(value = "/{id}", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<EventDtos.EventDetail> detail(@PathVariable("id") long id) {
        return service.detail(id).map(ResponseEntity::ok)
                .orElseGet(() -> ResponseEntity.notFound().build());
    }

    @PostMapping(consumes = MediaType.APPLICATION_JSON_VALUE, produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<EventDtos.EventDetail> create(@RequestBody Requests.EventUpsert req) {
        return ResponseEntity.status(HttpStatus.CREATED).body(service.create(req));
    }

    @PutMapping(value = "/{id}", consumes = MediaType.APPLICATION_JSON_VALUE,
            produces = MediaType.APPLICATION_JSON_VALUE)
    public EventDtos.EventDetail update(@PathVariable("id") long id,
                                        @RequestBody Requests.EventUpsert req) {
        return service.update(id, req);
    }

    @DeleteMapping(value = "/{id}", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<Requests.Deleted> delete(@PathVariable("id") long id) {
        int n = service.delete(id);
        if (n == 0) {
            return ResponseEntity.notFound().build();
        }
        return ResponseEntity.ok(new Requests.Deleted(id, n));
    }

    // ---------------------------------------------------------------- 关联人物
    @GetMapping(value = "/{id}/persons", produces = MediaType.APPLICATION_JSON_VALUE)
    public List<EventDtos.EventPersonRow> persons(@PathVariable("id") long id) {
        return service.persons(id, 500);
    }

    @PostMapping(value = "/{id}/persons", consumes = MediaType.APPLICATION_JSON_VALUE,
            produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<EventDtos.EventPersonRow> linkPerson(@PathVariable("id") long id,
                                                               @RequestBody Requests.PersonEventLink req) {
        return ResponseEntity.status(HttpStatus.CREATED).body(service.linkPerson(id, req));
    }

    @PutMapping(value = "/{id}/persons/{linkId}", consumes = MediaType.APPLICATION_JSON_VALUE,
            produces = MediaType.APPLICATION_JSON_VALUE)
    public EventDtos.EventPersonRow updatePersonLink(@PathVariable("id") long id,
                                                     @PathVariable("linkId") long linkId,
                                                     @RequestBody Requests.PersonEventLink req) {
        return service.updatePersonLink(id, linkId, req);
    }

    @DeleteMapping(value = "/{id}/persons/{linkId}", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<Requests.Deleted> unlinkPerson(@PathVariable("id") long id,
                                                         @PathVariable("linkId") long linkId) {
        int n = service.unlinkPerson(id, linkId);
        if (n == 0) {
            return ResponseEntity.notFound().build();
        }
        return ResponseEntity.ok(new Requests.Deleted(linkId, n));
    }

    // ---------------------------------------------------------------- 关联地点
    @GetMapping(value = "/{id}/places", produces = MediaType.APPLICATION_JSON_VALUE)
    public List<EventDtos.EventPlaceRow> places(@PathVariable("id") long id) {
        return service.places(id, 500);
    }

    @PostMapping(value = "/{id}/places", consumes = MediaType.APPLICATION_JSON_VALUE,
            produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<EventDtos.EventPlaceRow> linkPlace(@PathVariable("id") long id,
                                                             @RequestBody Requests.EventPlaceLink req) {
        return ResponseEntity.status(HttpStatus.CREATED).body(service.linkPlace(id, req));
    }

    @PutMapping(value = "/{id}/places/{linkId}", consumes = MediaType.APPLICATION_JSON_VALUE,
            produces = MediaType.APPLICATION_JSON_VALUE)
    public EventDtos.EventPlaceRow updatePlaceLink(@PathVariable("id") long id,
                                                   @PathVariable("linkId") long linkId,
                                                   @RequestBody Requests.EventPlaceLink req) {
        return service.updatePlaceLink(id, linkId, req);
    }

    @DeleteMapping(value = "/{id}/places/{linkId}", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<Requests.Deleted> unlinkPlace(@PathVariable("id") long id,
                                                        @PathVariable("linkId") long linkId) {
        int n = service.unlinkPlace(id, linkId);
        if (n == 0) {
            return ResponseEntity.notFound().build();
        }
        return ResponseEntity.ok(new Requests.Deleted(linkId, n));
    }
}
