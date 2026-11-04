package com.canvasofworldhistory.api.dto;

import com.fasterxml.jackson.annotation.JsonInclude;

import java.util.List;

/**
 * M3 时间—地图联动相关 DTO。
 *
 * <p>时间口径与 M2 一致：全部为天文学纪年整数（公元前 1 年 = 0），
 * 接口不做「公元前/公元」文本解析，也不返回「公元 0 年」这种显示。
 * 区间均为<b>端点包含式</b>：单年即 start == end。
 */
public final class PolityDtos {

    private PolityDtos() {
    }

    /** 展示地区（固定 10 个，仅作分组，不代表历史疆域）。 */
    @JsonInclude(JsonInclude.Include.ALWAYS)
    public record Region(String code, String label, int sortOrder) {
    }

    /**
     * 政权列表行。
     *
     * <p>存在区间两端**各自可选**（V7）：只填起始年或只填结束年都是合法状态，
     * 因此这里两个字段都可能为 null，前端不得假定成对出现。
     */
    @JsonInclude(JsonInclude.Include.ALWAYS)
    public record PolityHit(
            long polityId,
            String name,
            String regionCode,
            String regionLabel,
            Integer startYearAstro,
            Integer endYearAstro,
            String description,
            String recordStatus,
            int eventCount) {
    }

    /** 事件详情里的政权关联行（带状态，管理界面据此区分是否进入矩阵）。 */
    @JsonInclude(JsonInclude.Include.ALWAYS)
    public record EventPolityRow(
            long linkId,
            long polityId,
            String polityName,
            String regionCode,
            String regionLabel,
            String recordStatus,
            String role,
            String note) {
    }

    // ---------------------------------------------------------------- 地图
    /** 地图查询元信息（放在 GeoJSON 的 meta 里，前端用它显示计数与截断提示）。 */
    @JsonInclude(JsonInclude.Include.ALWAYS)
    public record EventMapMeta(
            int fromYearAstro,
            int toYearAstro,
            int returned,
            int totalInWindow,
            int limit,
            boolean truncated,
            int unknownTimeEvents,
            String note) {
    }

    // ---------------------------------------------------------------- 矩阵
    /** 矩阵的一列（一个时间段）。 */
    @JsonInclude(JsonInclude.Include.ALWAYS)
    public record MatrixColumn(int index, int startYearAstro, int endYearAstro, String label) {
    }

    /** 单元格里的一个事件（只带展示所需的最小字段）。 */
    @JsonInclude(JsonInclude.Include.ALWAYS)
    public record MatrixEvent(
            long eventId,
            String title,
            Integer startYearAstro,
            Integer endYearAstro,
            String timePrecision,
            String eventType) {
    }

    /** 某政权在某列的事件集合；无事件的列不返回，避免空对象。 */
    @JsonInclude(JsonInclude.Include.ALWAYS)
    public record MatrixCell(int columnIndex, List<MatrixEvent> events) {
    }

    /** 矩阵行：一个历史政权。 */
    @JsonInclude(JsonInclude.Include.ALWAYS)
    public record MatrixPolity(
            long polityId,
            String name,
            Integer startYearAstro,
            Integer endYearAstro,
            int eventCount,
            List<MatrixCell> cells) {
    }

    /** 矩阵里的一个地区（10 个固定返回，无内容时 polities 为空数组）。 */
    @JsonInclude(JsonInclude.Include.ALWAYS)
    public record MatrixRegion(
            String code,
            String label,
            int sortOrder,
            int polityCount,
            int eventCount,
            List<MatrixPolity> polities) {
    }

    /** 矩阵整体响应。 */
    @JsonInclude(JsonInclude.Include.ALWAYS)
    public record MatrixResponse(
            int fromYearAstro,
            int step,
            int offset,
            int count,
            List<MatrixColumn> columns,
            List<MatrixRegion> regions,
            int eventsInWindow,
            int unlinkedEventsInWindow,
            boolean truncated,
            String note) {
    }
}
