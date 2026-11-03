package com.canvasofworldhistory.api.web;

import com.canvasofworldhistory.api.dto.Dtos;
import com.canvasofworldhistory.api.service.PlaceQueryService;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

import java.util.Map;

@RestController
@RequestMapping("/api/v1/places")
public class PlaceController {

    private final PlaceQueryService service;

    public PlaceController(PlaceQueryService service) {
        this.service = service;
    }

    /** 地点搜索：keyword 必填；year 可选（按名称有效期筛选）。 */
    @GetMapping(produces = MediaType.APPLICATION_JSON_VALUE)
    public Dtos.Page<Dtos.PlaceHit> search(
            @RequestParam(name = "keyword", required = false) String keyword,
            @RequestParam(name = "year", required = false) Integer year,
            @RequestParam(name = "page", defaultValue = "1") int page,
            @RequestParam(name = "size", defaultValue = "20") int size) {
        if (keyword == null || keyword.trim().isEmpty()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "keyword 不能为空");
        }
        if (keyword.trim().length() < 1) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "keyword 至少 1 个字符");
        }
        return service.search(keyword, year, page, size);
    }

    /** 地图视野查询：bbox=west,south,east,north（WGS84 / EPSG:4326），返回 GeoJSON。 */
    @GetMapping(value = "/map", produces = MediaType.APPLICATION_JSON_VALUE)
    public Map<String, Object> map(
            @RequestParam(name = "bbox") String bbox,
            @RequestParam(name = "limit", defaultValue = "1000") int limit) {
        double[] b = parseBbox(bbox);
        return service.mapFeatures(b[0], b[1], b[2], b[3], limit);
    }

    /** 地点详情。 */
    @GetMapping(value = "/{id}", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<Dtos.PlaceDetail> detail(@PathVariable("id") long id) {
        return service.detail(id)
                .map(ResponseEntity::ok)
                .orElseGet(() -> ResponseEntity.notFound().build());
    }

    private static double[] parseBbox(String raw) {
        String[] parts = raw.split(",");
        if (parts.length != 4) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST,
                    "bbox 必须是 west,south,east,north 四个数字");
        }
        double[] v = new double[4];
        try {
            for (int i = 0; i < 4; i++) {
                v[i] = Double.parseDouble(parts[i].trim());
            }
        } catch (NumberFormatException e) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "bbox 含非数字");
        }
        double w = v[0], s = v[1], e = v[2], n = v[3];
        if (!(-180 <= w && w <= 180 && -180 <= e && e <= 180 && -90 <= s && s <= 90 && -90 <= n && n <= 90)) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "bbox 超出经纬度范围");
        }
        if (w >= e || s >= n) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "bbox 需满足 west<east 且 south<north");
        }
        return v;
    }
}
