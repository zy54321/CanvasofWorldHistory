package com.canvasofworldhistory.api.dto;

import com.fasterxml.jackson.annotation.JsonInclude;

import java.util.List;

/**
 * 地点管理 DTO（M2 收尾：为地点 CRUD 与名称/位置维护提供列表与写入视角）。
 *
 * 与 M1 只读视角的区别：这里的列表允许 keyword 为空（管理界面要能翻页浏览），
 * 详情沿用 M1 的 /places/{id}（其 names/locations 已含编辑所需字段），不另造一套。
 */
public final class PlaceAdminDtos {

    private PlaceAdminDtos() {
    }

    @JsonInclude(JsonInclude.Include.ALWAYS)
    public record PlaceAdminRow(
            long placeId,
            String canonicalName,
            String canonicalNameLang,
            String placeType,
            String description,
            String recordStatus,
            String datasetId,
            int nameCount,
            int locationCount,
            Double lon,
            Double lat,
            boolean hasGeom,
            // V1.0 内容管理：展示名与名称质量（读取侧计算，不改数据）
            String displayName,
            String nameQuality,
            String datasetName,
            // 逐类几何数量：同一地点可能同时有点/线/面，所以三个数可以并存
            int pointCount,
            int lineCount,
            int polygonCount,
            int geomLocationCount) {
    }

    @JsonInclude(JsonInclude.Include.ALWAYS)
    public record Deleted(long id, int affected) {
    }

    /** 供管理界面判断哪些值可选（与数据库 CHECK 一致，不额外发明）。 */
    @JsonInclude(JsonInclude.Include.ALWAYS)
    public record PlaceOptions(
            List<String> placeTypes,
            List<String> placeTypeSources,
            List<String> recordStatuses,
            List<String> nameTypes,
            List<String> timeBoundTypes,
            List<String> locationPrecisions,
            List<String> crsConfidences) {
    }
}
