package com.canvasofworldhistory.api.dto;

/**
 * M2-2A 写入请求体。
 *
 * 约定：
 *  - 时间字段一律天文学纪年整数（公元前 1 年 = 0），接口不做 BCE/CE 标签解析。
 *  - PUT 为整体替换：可选字段传 null 表示清空（recordStatus 例外，null 表示保持不变）。
 *  - recordStatus 允许 staging / published / rejected。
 */
public final class Requests {

    private Requests() {
    }

    /** 人物创建 / 整体更新。 */
    public record PersonUpsert(
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
            String recordStatus) {
    }

    /** 人物名称创建 / 更新。 */
    public record PersonNameUpsert(
            String nameText,
            String nameLang,
            String nameType,
            String transliterationScheme,
            String notes,
            String recordStatus) {
    }

    /** 人物 ↔ 事件 关联（也用于事件侧挂人物）。 */
    public record PersonEventLink(
            Long personId,
            Long eventId,
            String role,
            Integer validFromYearAstro,
            Integer validToYearAstro,
            String note) {
    }

    /** 人物 ↔ 地点 关联。 */
    public record PersonPlaceLink(
            Long personId,
            Long placeId,
            String relationType,
            Integer startYearAstro,
            Integer endYearAstro,
            String timePrecision,
            Integer sequenceOrder,
            String note) {
    }

    /** 事件创建 / 整体更新。 */
    public record EventUpsert(
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
            String recordStatus) {
    }

    /** 事件 ↔ 地点 关联。 */
    public record EventPlaceLink(
            Long eventId,
            Long placeId,
            String locationRole,
            Integer validFromYearAstro,
            Integer validToYearAstro,
            String note) {
    }

    /** 历史政权创建（M3）。regionCode 必须是后端给出的 10 个展示地区之一。 */
    public record PolityUpsert(
            String name,
            String nameLang,
            String regionCode,
            Integer startYearAstro,
            Integer endYearAstro,
            String description,
            String notes,
            String recordStatus) {
    }

    /** 事件—政权关联（M3）。role 为自由文本，不做枚举约束。 */
    public record EventPolityLink(
            Long polityId,
            String role,
            String note) {
    }

    /** 简单确认响应。 */
    public record Deleted(long id, int affected) {
    }

    // ------------------------------------------------------------------ 地点（M2 收尾新增）

    /** 地点创建 / 整体更新。经纬度可空 —— 坐标未知时保存为未定位记录，不伪造坐标。 */
    public record PlaceUpsert(
            String canonicalName,
            String canonicalNameLang,
            String placeType,
            String placeTypeBasisNote,
            String description,
            String notes,
            String recordStatus) {
    }

    /** 地点历史名称 / 别名。有效期可空（未知即 unknown）。 */
    public record PlaceNameUpsert(
            String nameText,
            String nameLang,
            String nameType,
            String transliterationScheme,
            Integer validFromYearAstro,
            Integer validToYearAstro,
            String timeBoundType,
            String timeNote,
            String notes,
            String recordStatus) {
    }

    /** 地点位置：经纬度可空；给出经纬度时存为 EPSG:4326 的 Point。 */
    public record PlaceLocationUpsert(
            Double lon,
            Double lat,
            String locationPrecision,
            Integer uncertaintyM,
            String crsConfidence,
            Integer validFromYearAstro,
            Integer validToYearAstro,
            String timeBoundType,
            String notes,
            String recordStatus) {
    }
}
