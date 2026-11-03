package com.canvasofworldhistory.api.dto;

import java.util.List;

/** M1 只读接口的响应载体（record，避免无意义的分层）。 */
public final class Dtos {

    private Dtos() {
    }

    /** 搜索结果中的一条：一个 place（同名不同地点是不同 place_id）。 */
    public record PlaceHit(
            long placeId,
            String canonicalName,
            String canonicalNameLang,
            String placeType,
            String datasetId,
            String datasetName,
            String recordStatus,
            String matchedName,
            String matchedNameType,
            String matchedNameLang,
            Integer validFromYear,
            Integer validToYear,
            String timeBoundType,
            boolean timeKnown,
            Double lon,
            Double lat,
            String locationPrecision,
            Integer uncertaintyM,
            Integer nameCount,
            Integer locationCount) {
    }

    public record Page<T>(List<T> items, int page, int size, long total, int totalPages) {
        public static <T> Page<T> of(List<T> items, int page, int size, long total) {
            int pages = size <= 0 ? 0 : (int) ((total + size - 1) / size);
            return new Page<>(items, page, size, total, pages);
        }
    }

    public record NameRow(
            long nameId,
            String nameText,
            String nameLang,
            String nameType,
            String transliterationScheme,
            String associationCertainty,
            Integer validFromYear,
            Integer validToYear,
            String timeBoundType,
            String timeNote,
            String recordStatus) {
    }

    public record LocationRow(
            long locationId,
            Double lon,
            Double lat,
            String geomType,
            String locationPrecision,
            Integer uncertaintyM,
            String uncertaintySource,
            String originalCrs,
            String crsConfidence,
            String originalX,
            String originalY,
            Integer validFromYear,
            Integer validToYear,
            String timeBoundType,
            String recordStatus,
            String conflictStatus,
            boolean hasGeom) {
    }

    public record SourceRecordRow(
            long sourceRecordId,
            String datasetId,
            String recordScope,
            String externalId,
            Integer duplicateOrdinal,
            String rawFile,
            boolean active,
            String inactiveReason) {
    }

    public record IssueRow(
            long issueId,
            String issueType,
            String severity,
            String fieldName,
            String observedValue,
            String actionTaken,
            String resolutionNote) {
    }

    public record PlaceDetail(
            long placeId,
            String canonicalName,
            String canonicalNameLang,
            String placeType,
            String placeTypeSource,
            String placeTypeBasisNote,
            String description,
            String notes,
            String recordStatus,
            String liveness,
            Long mergedIntoPlaceId,
            String datasetId,
            String datasetName,
            String datasetVersion,
            String sourceId,
            String sourceName,
            String sourceHomepage,
            String sourceLicenseNote,
            List<NameRow> names,
            List<LocationRow> locations,
            List<SourceRecordRow> sourceRecords,
            List<IssueRow> issues,
            boolean issueListTruncated) {
    }

    public record Stats(
            long places,
            long names,
            long locations,
            long locationsWithGeom,
            long locationsUnknownCrs,
            long datasetCount,
            long sourceCount,
            long ledgerEntries,
            String dataStatus) {
    }
}
