export interface PlaceSummary {
  placeId: number
  canonicalName: string
  canonicalNameLang: string | null
  placeType: string | null
  datasetId: string
  datasetName: string | null
  recordStatus: string
  matchedName: string
  matchedNameType: string | null
  matchedNameLang: string | null
  validFromYear: number | null
  validToYear: number | null
  timeBoundType: string | null
  timeKnown: boolean
  lon: number | null
  lat: number | null
  locationPrecision: string | null
  nameCount: number
  locationCount: number
}

export interface SearchResult {
  items: PlaceSummary[]
  page: number
  size: number
  total: number
  totalPages: number
}

export interface PlaceName {
  nameId: number
  nameText: string
  nameLang: string | null
  nameType: string | null
  transliterationScheme?: string | null
  validFromYear: number | null
  validToYear: number | null
  timeBoundType: string | null
  recordStatus: string
}

export interface PlaceLocation {
  locationId: number
  lon: number | null
  lat: number | null
  geomType: string | null
  locationPrecision: string | null
  uncertaintyM?: number | null
  originalCrs: string | null
  crsConfidence: string | null
  originalX: string | null
  originalY: string | null
  validFromYear: number | null
  validToYear: number | null
  timeBoundType: string | null
  recordStatus: string
  conflictStatus: string | null
  hasGeom: boolean
}

export interface SourceRecordRef {
  sourceRecordId: number
  externalId: string
  recordScope: string
  parentExternalId?: string | null
  duplicateOrdinal?: number
  rawFile: string | null
  active: boolean
  inactiveReason?: string | null
}

export interface IssueRef {
  issueId: number
  issueType: string
  severity: string | null
  fieldName: string | null
  observedValue: string | null
  actionTaken: string | null
  resolutionNote: string | null
}

export interface PlaceDetail {
  placeId: number
  canonicalName: string
  canonicalNameLang: string | null
  placeType: string | null
  placeTypeSource: string | null
  placeTypeBasisNote: string | null
  description: string | null
  notes: string | null
  recordStatus: string
  liveness: string | null
  datasetId: string
  datasetName: string | null
  datasetVersion: string | null
  sourceId: string | null
  sourceName: string | null
  sourceHomepage: string | null
  sourceLicenseNote: string | null
  names: PlaceName[]
  locations: PlaceLocation[]
  sourceRecords: SourceRecordRef[]
  issues: IssueRef[]
  issueListTruncated?: boolean
}

export interface PlaceFeatureProps {
  placeId: number
  name: string
  nameLang: string | null
  placeType: string | null
  datasetId: string
  datasetName: string | null
  recordStatus: string
  locationId: number
  locationPrecision: string | null
  crsConfidence: string | null
  validFromYear: number | null
  validToYear: number | null
  timeBoundType: string | null
}

export interface PlaceFeature {
  type: 'Feature'
  id: number
  geometry: { type: 'Point'; coordinates: [number, number] }
  properties: PlaceFeatureProps
}

export interface PlaceFeatureCollection {
  type: 'FeatureCollection'
  features: PlaceFeature[]
  meta: {
    bbox: [number, number, number, number]
    totalInBbox: number
    returned: number
    limit: number
    truncated: boolean
    recordStatus?: string
  }
}

export interface MapStats {
  places: number
  names: number
  locations: number
  locationsWithGeom: number
  locationsUnknownCrs: number
  datasetCount: number
  sourceCount: number
  ledgerEntries: number
  dataStatus: string
}
// ==========================================================================
// M2 人物 / 事件 / 地点管理
// 时间字段一律天文学纪年整数（公元前 1 年 = 0）。
// ==========================================================================

export interface PersonHit {
  personId: number
  canonicalName: string
  canonicalNameLang: string | null
  description: string | null
  birthYearAstro: number | null
  birthPrecision: string
  deathYearAstro: number | null
  deathPrecision: string
  recordStatus: string
  nameCount: number
  eventCount: number
  placeCount: number
}

export interface PersonNameRow {
  personNameId: number
  personId: number
  nameText: string
  nameLang: string | null
  nameType: string
  transliterationScheme: string | null
  notes: string | null
  recordStatus: string
}

export interface PersonEventRow {
  linkId: number
  eventId: number
  title: string
  startYearAstro: number | null
  endYearAstro: number | null
  timePrecision: string
  eventType: string
  role: string
  validFromYearAstro: number | null
  validToYearAstro: number | null
  note: string | null
}

export interface PersonPlaceRow {
  linkId: number
  placeId: number
  placeName: string
  placeType: string | null
  relationType: string
  startYearAstro: number | null
  endYearAstro: number | null
  timePrecision: string
  sequenceOrder: number | null
  note: string | null
  lon: number | null
  lat: number | null
}

export interface PersonDetail {
  personId: number
  canonicalName: string
  canonicalNameLang: string | null
  description: string | null
  birthYearAstro: number | null
  birthPrecision: string
  birthOriginalText: string | null
  deathYearAstro: number | null
  deathPrecision: string
  deathOriginalText: string | null
  notes: string | null
  recordStatus: string
  createdBy: string
  locked: boolean
  names: PersonNameRow[]
  events: PersonEventRow[]
  places: PersonPlaceRow[]
  truncated: boolean
}

export interface EventHit {
  eventId: number
  title: string
  summary: string | null
  startYearAstro: number | null
  endYearAstro: number | null
  timePrecision: string
  eventType: string
  recordStatus: string
  personCount: number
  placeCount: number
}

export interface EventPersonRow {
  linkId: number
  personId: number
  personName: string
  role: string
  validFromYearAstro: number | null
  validToYearAstro: number | null
  note: string | null
}

export interface EventPlaceRow {
  linkId: number
  placeId: number
  placeName: string
  placeType: string | null
  locationRole: string
  validFromYearAstro: number | null
  validToYearAstro: number | null
  note: string | null
  lon: number | null
  lat: number | null
}

export interface EventDetail {
  eventId: number
  title: string
  summary: string | null
  description: string | null
  startYearAstro: number | null
  endYearAstro: number | null
  timePrecision: string
  timeOriginalText: string | null
  timeNote: string | null
  eventType: string
  notes: string | null
  recordStatus: string
  createdBy: string
  locked: boolean
  persons: EventPersonRow[]
  places: EventPlaceRow[]
  polities: EventPolityRow[]
  truncated: boolean
}

export interface AdminPlaceRow {
  placeId: number
  canonicalName: string
  canonicalNameLang: string | null
  placeType: string | null
  description: string | null
  recordStatus: string
  datasetId: string
  nameCount: number
  locationCount: number
  lon: number | null
  lat: number | null
  hasGeom: boolean
}

/** GET /api/v1/places/admin/options 的返回：取值与数据库 CHECK 约束一致 */
export interface PlaceOptions {
  placeTypes: string[]
  placeTypeSources: string[]
  recordStatuses: string[]
  nameTypes: string[]
  timeBoundTypes: string[]
  locationPrecisions: string[]
  crsConfidences: string[]
}

// ==========================================================================
// M3 时间—地图联动
// ==========================================================================

/** 地图事件标记（一个「事件 × 地点」一个要素） */
export interface EventMarkerProps {
  eventId: number
  title: string
  startYearAstro: number | null
  endYearAstro: number | null
  timePrecision: string
  eventType: string
  placeId: number
  placeName: string
  locationRole: string | null
  /** MapLibre 聚合专用字段 */
  cluster?: boolean
  cluster_id?: number
  point_count?: number
}

export interface EventFeature {
  type: 'Feature'
  geometry: { type: 'Point'; coordinates: [number, number] }
  properties: EventMarkerProps
}

export interface EventMapMeta {
  fromYearAstro: number
  toYearAstro: number
  returned: number
  totalInWindow: number
  limit: number
  truncated: boolean
  unknownTimeEvents: number
  note: string
}

export interface EventFeatureCollection {
  type: 'FeatureCollection'
  features: EventFeature[]
  meta: EventMapMeta
}

export interface MatrixColumn {
  index: number
  startYearAstro: number
  endYearAstro: number
  label: string
}

export interface MatrixEvent {
  eventId: number
  title: string
  startYearAstro: number | null
  endYearAstro: number | null
  timePrecision: string
  eventType: string
}

export interface MatrixCell {
  columnIndex: number
  events: MatrixEvent[]
}

export interface MatrixPolity {
  polityId: number
  name: string
  startYearAstro: number | null
  endYearAstro: number | null
  eventCount: number
  cells: MatrixCell[]
}

export interface MatrixRegion {
  code: string
  label: string
  sortOrder: number
  polityCount: number
  eventCount: number
  polities: MatrixPolity[]
}

export interface MatrixResponse {
  fromYearAstro: number
  step: number
  offset: number
  count: number
  columns: MatrixColumn[]
  regions: MatrixRegion[]
  eventsInWindow: number
  unlinkedEventsInWindow: number
  truncated: boolean
  note: string
}

/** 政权（展示用最小模型） */
export interface PolityHit {
  polityId: number
  name: string
  regionCode: string
  regionLabel: string
  startYearAstro: number | null
  endYearAstro: number | null
  description: string | null
  eventCount: number
}

export interface PolityRegion {
  code: string
  label: string
  sortOrder: number
}

export interface EventPolityRow {
  linkId: number
  polityId: number
  polityName: string
  regionCode: string
  regionLabel: string
  role: string | null
  note: string | null
}
