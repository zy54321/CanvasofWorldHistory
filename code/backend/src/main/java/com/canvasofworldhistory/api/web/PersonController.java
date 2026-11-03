package com.canvasofworldhistory.api.web;

import com.canvasofworldhistory.api.dto.Dtos;
import com.canvasofworldhistory.api.dto.PersonDtos;
import com.canvasofworldhistory.api.dto.Requests;
import com.canvasofworldhistory.api.service.PersonService;
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

/**
 * 人物 API（M2-2A）。
 *
 * 时间字段一律天文学纪年整数：公元前 1 年 = 0，公元 1 年 = 1；接口不做 BCE/CE 标签换算。
 */
@RestController
@RequestMapping("/api/v1/persons")
public class PersonController {

    private final PersonService service;

    public PersonController(PersonService service) {
        this.service = service;
    }

    /** 列表 / 关键词搜索（匹配规范名与全部别名）。keyword 为空则返回全部。 */
    @GetMapping(produces = MediaType.APPLICATION_JSON_VALUE)
    public Dtos.Page<PersonDtos.PersonHit> list(
            @RequestParam(name = "keyword", required = false) String keyword,
            @RequestParam(name = "page", defaultValue = "1") int page,
            @RequestParam(name = "size", defaultValue = "20") int size) {
        return service.search(keyword, page, size);
    }

    /** 详情：主表 + 名称 / 关联事件 / 活动地点。 */
    @GetMapping(value = "/{id}", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<PersonDtos.PersonDetail> detail(@PathVariable("id") long id) {
        return service.detail(id).map(ResponseEntity::ok)
                .orElseGet(() -> ResponseEntity.notFound().build());
    }

    @PostMapping(consumes = MediaType.APPLICATION_JSON_VALUE, produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<PersonDtos.PersonDetail> create(@RequestBody Requests.PersonUpsert req) {
        return ResponseEntity.status(HttpStatus.CREATED).body(service.create(req));
    }

    @PutMapping(value = "/{id}", consumes = MediaType.APPLICATION_JSON_VALUE,
            produces = MediaType.APPLICATION_JSON_VALUE)
    public PersonDtos.PersonDetail update(@PathVariable("id") long id,
                                          @RequestBody Requests.PersonUpsert req) {
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

    // ---------------------------------------------------------------- 名称
    @GetMapping(value = "/{id}/names", produces = MediaType.APPLICATION_JSON_VALUE)
    public List<PersonDtos.PersonNameRow> names(@PathVariable("id") long id) {
        return service.names(id);
    }

    @PostMapping(value = "/{id}/names", consumes = MediaType.APPLICATION_JSON_VALUE,
            produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<PersonDtos.PersonNameRow> addName(@PathVariable("id") long id,
                                                            @RequestBody Requests.PersonNameUpsert req) {
        return ResponseEntity.status(HttpStatus.CREATED).body(service.addName(id, req));
    }

    @PutMapping(value = "/{id}/names/{nameId}", consumes = MediaType.APPLICATION_JSON_VALUE,
            produces = MediaType.APPLICATION_JSON_VALUE)
    public PersonDtos.PersonNameRow updateName(@PathVariable("id") long id,
                                               @PathVariable("nameId") long nameId,
                                               @RequestBody Requests.PersonNameUpsert req) {
        return service.updateName(id, nameId, req);
    }

    @DeleteMapping(value = "/{id}/names/{nameId}", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<Requests.Deleted> deleteName(@PathVariable("id") long id,
                                                       @PathVariable("nameId") long nameId) {
        int n = service.deleteName(id, nameId);
        if (n == 0) {
            return ResponseEntity.notFound().build();
        }
        return ResponseEntity.ok(new Requests.Deleted(nameId, n));
    }

    // ---------------------------------------------------------------- 关联事件
    @GetMapping(value = "/{id}/events", produces = MediaType.APPLICATION_JSON_VALUE)
    public List<PersonDtos.PersonEventRow> events(@PathVariable("id") long id) {
        return service.events(id, 500);
    }

    @PostMapping(value = "/{id}/events", consumes = MediaType.APPLICATION_JSON_VALUE,
            produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<PersonDtos.PersonEventRow> linkEvent(@PathVariable("id") long id,
                                                               @RequestBody Requests.PersonEventLink req) {
        return ResponseEntity.status(HttpStatus.CREATED).body(service.linkEvent(id, req));
    }

    @PutMapping(value = "/{id}/events/{linkId}", consumes = MediaType.APPLICATION_JSON_VALUE,
            produces = MediaType.APPLICATION_JSON_VALUE)
    public PersonDtos.PersonEventRow updateEventLink(@PathVariable("id") long id,
                                                     @PathVariable("linkId") long linkId,
                                                     @RequestBody Requests.PersonEventLink req) {
        return service.updateEventLink(id, linkId, req);
    }

    @DeleteMapping(value = "/{id}/events/{linkId}", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<Requests.Deleted> unlinkEvent(@PathVariable("id") long id,
                                                        @PathVariable("linkId") long linkId) {
        int n = service.unlinkEvent(id, linkId);
        if (n == 0) {
            return ResponseEntity.notFound().build();
        }
        return ResponseEntity.ok(new Requests.Deleted(linkId, n));
    }

    // ---------------------------------------------------------------- 关联地点
    @GetMapping(value = "/{id}/places", produces = MediaType.APPLICATION_JSON_VALUE)
    public List<PersonDtos.PersonPlaceRow> places(@PathVariable("id") long id) {
        return service.places(id, 500);
    }

    @PostMapping(value = "/{id}/places", consumes = MediaType.APPLICATION_JSON_VALUE,
            produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<PersonDtos.PersonPlaceRow> linkPlace(@PathVariable("id") long id,
                                                               @RequestBody Requests.PersonPlaceLink req) {
        return ResponseEntity.status(HttpStatus.CREATED).body(service.linkPlace(id, req));
    }

    @PutMapping(value = "/{id}/places/{linkId}", consumes = MediaType.APPLICATION_JSON_VALUE,
            produces = MediaType.APPLICATION_JSON_VALUE)
    public PersonDtos.PersonPlaceRow updatePlaceLink(@PathVariable("id") long id,
                                                     @PathVariable("linkId") long linkId,
                                                     @RequestBody Requests.PersonPlaceLink req) {
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
