package com.canvasofworldhistory.api.dto;

import com.fasterxml.jackson.annotation.JsonInclude;

import java.util.List;

/**
 * M2-2A 事件相关 DTO。
 * 时间口径同 {@link PersonDtos}：全部为天文学纪年整数，不做标签换算。
 */
public final class EventDtos {

    private EventDtos() {
    }

    @JsonInclude(JsonInclude.Include.ALWAYS)
    public record EventHit(
            long eventId,
            String title,
            String summary,
            Integer startYearAstro,
            Integer endYearAstro,
            String timePrecision,
            String eventType,
            String recordStatus,
            int personCount,
            int placeCount) {
    }

    /** 事件关联的人物（含角色）。 */
    @JsonInclude(JsonInclude.Include.ALWAYS)
    public record EventPersonRow(
            long linkId,
            long personId,
            String personName,
            String role,
            Integer validFromYearAstro,
            Integer validToYearAstro,
            String note) {
    }

    /** 事件关联的地点（含地点角色）。 */
    @JsonInclude(JsonInclude.Include.ALWAYS)
    public record EventPlaceRow(
            long linkId,
            long placeId,
            String placeName,
            String placeType,
            String locationRole,
            Integer validFromYearAstro,
            Integer validToYearAstro,
            String note,
            Double lon,
            Double lat) {
    }

    @JsonInclude(JsonInclude.Include.ALWAYS)
    public record EventDetail(
            long eventId,
            String title,
            String summary,
            String description,
            Integer startYearAstro,
            Integer endYearAstro,
            String timePrecision,
            String timeOriginalText,
            String timeNote,
            String eventType,
            String notes,
            String recordStatus,
            String createdBy,
            boolean locked,
            List<EventPersonRow> persons,
            List<EventPlaceRow> places,
            boolean truncated) {
    }
}
