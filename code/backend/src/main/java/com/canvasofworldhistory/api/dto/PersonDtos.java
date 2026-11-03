package com.canvasofworldhistory.api.dto;

import com.fasterxml.jackson.annotation.JsonInclude;

import java.util.List;

/**
 * M2-2A 人物相关 DTO。
 *
 * 时间口径：所有 *_astro 字段都是**天文学纪年整数**（公元前 1 年 = 0，公元 1 年 = 1）。
 * 接口只透传整数，不做任何 BCE/CE 标签换算，避免后端与前端各写一套换算而漂移。
 */
public final class PersonDtos {

    private PersonDtos() {
    }

    /** 列表项：够列表展示，不含子集合。 */
    @JsonInclude(JsonInclude.Include.ALWAYS)
    public record PersonHit(
            long personId,
            String canonicalName,
            String canonicalNameLang,
            String description,
            Integer birthYearAstro,
            String birthPrecision,
            Integer deathYearAstro,
            String deathPrecision,
            String recordStatus,
            int nameCount,
            int eventCount,
            int placeCount) {
    }

    /** 人物名称行。 */
    @JsonInclude(JsonInclude.Include.ALWAYS)
    public record PersonNameRow(
            long personNameId,
            long personId,
            String nameText,
            String nameLang,
            String nameType,
            String transliterationScheme,
            String notes,
            String recordStatus) {
    }

    /** 人物关联的事件（含该人在此事件中的角色）。 */
    @JsonInclude(JsonInclude.Include.ALWAYS)
    public record PersonEventRow(
            long linkId,
            long eventId,
            String title,
            Integer startYearAstro,
            Integer endYearAstro,
            String timePrecision,
            String eventType,
            String role,
            Integer validFromYearAstro,
            Integer validToYearAstro,
            String note) {
    }

    /** 人物关联的活动地点。 */
    @JsonInclude(JsonInclude.Include.ALWAYS)
    public record PersonPlaceRow(
            long linkId,
            long placeId,
            String placeName,
            String placeType,
            String relationType,
            Integer startYearAstro,
            Integer endYearAstro,
            String timePrecision,
            Integer sequenceOrder,
            String note,
            Double lon,
            Double lat) {
    }

    /** 人物详情：主表字段 + 名称 / 事件 / 地点三组子集合。 */
    @JsonInclude(JsonInclude.Include.ALWAYS)
    public record PersonDetail(
            long personId,
            String canonicalName,
            String canonicalNameLang,
            String description,
            Integer birthYearAstro,
            String birthPrecision,
            String birthOriginalText,
            Integer deathYearAstro,
            String deathPrecision,
            String deathOriginalText,
            String notes,
            String recordStatus,
            String createdBy,
            boolean locked,
            List<PersonNameRow> names,
            List<PersonEventRow> events,
            List<PersonPlaceRow> places,
            boolean truncated) {
    }
}
