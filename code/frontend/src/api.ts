import type {
  AdminPlaceRow,
  EventDetail,
  EventHit,
  EventPersonRow,
  EventPlaceRow,
  MapStats,
  PersonDetail,
  PersonEventRow,
  PersonHit,
  PersonNameRow,
  PersonPlaceRow,
  EventFeatureCollection,
  EventPolityRow,
  MatrixResponse,
  PolityHit,
  PolityRegion,
  PlaceDetail,
  PlaceFeatureCollection,
  PlaceOptions,
  SearchResult,
} from './types'

const BASE = '/api/v1'

async function getJson<T>(url: string, signal?: AbortSignal): Promise<T> {
  const res = await fetch(url, { signal, headers: { Accept: 'application/json' } })
  if (!res.ok) {
    let msg = `${res.status} ${res.statusText}`
    try {
      const body = await res.json()
      if (body?.message) msg = body.message
    } catch {
      /* 非 JSON 错误体 */
    }
    throw new Error(msg)
  }
  return (await res.json()) as T
}

export function searchPlaces(
  params: { keyword?: string; year?: number | null; page?: number; size?: number },
  signal?: AbortSignal,
): Promise<SearchResult> {
  const q = new URLSearchParams()
  if (params.keyword) q.set('keyword', params.keyword)
  if (params.year !== null && params.year !== undefined) q.set('year', String(params.year))
  q.set('page', String(params.page ?? 1))
  q.set('size', String(params.size ?? 20))
  return getJson<SearchResult>(`${BASE}/places?${q.toString()}`, signal)
}

export function fetchPlace(id: number, signal?: AbortSignal): Promise<PlaceDetail> {
  return getJson<PlaceDetail>(`${BASE}/places/${id}`, signal)
}

export function fetchMap(
  bbox: [number, number, number, number],
  limit = 400,
  signal?: AbortSignal,
): Promise<PlaceFeatureCollection> {
  const q = new URLSearchParams({ bbox: bbox.map((n) => n.toFixed(5)).join(','), limit: String(limit) })
  return getJson<PlaceFeatureCollection>(`${BASE}/places/map?${q.toString()}`, signal)
}

export function fetchStats(signal?: AbortSignal): Promise<MapStats> {
  return getJson<MapStats>(`${BASE}/meta/stats`, signal)
}
// ==========================================================================
// M2 写接口
// 说明：错误统一由后端返回 {status, error, message, constraint?}，
// 这里把 message 抛出去，界面直接展示，不吞成「操作失败」。
// ==========================================================================

export class ApiError extends Error {
  status: number
  constraint?: string
  constructor(status: number, message: string, constraint?: string) {
    super(message)
    this.status = status
    this.constraint = constraint
  }
}

async function send<T>(method: string, url: string, body?: unknown): Promise<T> {
  const res = await fetch(url, {
    method,
    headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  const text = await res.text()
  let data: unknown = null
  if (text) {
    try {
      data = JSON.parse(text)
    } catch {
      data = text
    }
  }
  if (!res.ok) {
    const d = data as { message?: string; constraint?: string } | null
    throw new ApiError(res.status, d?.message || `${res.status} ${res.statusText}`, d?.constraint)
  }
  return data as T
}

interface Paged<T> {
  items: T[]
  page: number
  size: number
  total: number
  totalPages: number
}

/** 关键词查询串；空关键词不传，交给后端返回全部 */
function kw(keyword: string, page: number, size: number): string {
  const q = new URLSearchParams({ page: String(page), size: String(size) })
  if (keyword.trim()) q.set('keyword', keyword.trim())
  return q.toString()
}

// ------------------------------------------------------------------ 地点
export const placeAdmin = {
  options: (signal?: AbortSignal) => getJson<PlaceOptions>('/api/v1/places/admin/options', signal),
  list: (keyword: string, page = 1, size = 20, signal?: AbortSignal) =>
    getJson<Paged<AdminPlaceRow>>(`/api/v1/places/admin?${kw(keyword, page, size)}`, signal),
  create: (body: unknown) => send<{ placeId: number }>('POST', '/api/v1/places', body),
  update: (id: number, body: unknown) => send<unknown>('PUT', `/api/v1/places/${id}`, body),
  remove: (id: number) => send<unknown>('DELETE', `/api/v1/places/${id}`),
  addName: (id: number, body: unknown) => send<{ nameId: number }>('POST', `/api/v1/places/${id}/names`, body),
  updateName: (id: number, nameId: number, body: unknown) =>
    send<unknown>('PUT', `/api/v1/places/${id}/names/${nameId}`, body),
  removeName: (id: number, nameId: number) => send<unknown>('DELETE', `/api/v1/places/${id}/names/${nameId}`),
  addLocation: (id: number, body: unknown) =>
    send<{ locationId: number }>('POST', `/api/v1/places/${id}/locations`, body),
  updateLocation: (id: number, locationId: number, body: unknown) =>
    send<unknown>('PUT', `/api/v1/places/${id}/locations/${locationId}`, body),
  removeLocation: (id: number, locationId: number) =>
    send<unknown>('DELETE', `/api/v1/places/${id}/locations/${locationId}`),
}

// ------------------------------------------------------------------ 人物
export const personApi = {
  list: (keyword: string, page = 1, size = 20, signal?: AbortSignal) =>
    getJson<Paged<PersonHit>>(`/api/v1/persons?${kw(keyword, page, size)}`, signal),
  detail: (id: number, signal?: AbortSignal) => getJson<PersonDetail>(`/api/v1/persons/${id}`, signal),
  create: (body: unknown) => send<PersonDetail>('POST', '/api/v1/persons', body),
  update: (id: number, body: unknown) => send<PersonDetail>('PUT', `/api/v1/persons/${id}`, body),
  remove: (id: number) => send<unknown>('DELETE', `/api/v1/persons/${id}`),
  names: (id: number) => getJson<PersonNameRow[]>(`/api/v1/persons/${id}/names`),
  addName: (id: number, body: unknown) => send<PersonNameRow>('POST', `/api/v1/persons/${id}/names`, body),
  updateName: (id: number, nameId: number, body: unknown) =>
    send<PersonNameRow>('PUT', `/api/v1/persons/${id}/names/${nameId}`, body),
  removeName: (id: number, nameId: number) => send<unknown>('DELETE', `/api/v1/persons/${id}/names/${nameId}`),
  events: (id: number) => getJson<PersonEventRow[]>(`/api/v1/persons/${id}/events`),
  linkEvent: (id: number, body: unknown) => send<PersonEventRow>('POST', `/api/v1/persons/${id}/events`, body),
  updateEventLink: (id: number, linkId: number, body: unknown) =>
    send<PersonEventRow>('PUT', `/api/v1/persons/${id}/events/${linkId}`, body),
  unlinkEvent: (id: number, linkId: number) => send<unknown>('DELETE', `/api/v1/persons/${id}/events/${linkId}`),
  places: (id: number) => getJson<PersonPlaceRow[]>(`/api/v1/persons/${id}/places`),
  linkPlace: (id: number, body: unknown) => send<PersonPlaceRow>('POST', `/api/v1/persons/${id}/places`, body),
  updatePlaceLink: (id: number, linkId: number, body: unknown) =>
    send<PersonPlaceRow>('PUT', `/api/v1/persons/${id}/places/${linkId}`, body),
  unlinkPlace: (id: number, linkId: number) => send<unknown>('DELETE', `/api/v1/persons/${id}/places/${linkId}`),
}

// ------------------------------------------------------------------ 事件
export const eventApi = {
  list: (keyword: string, page = 1, size = 20, signal?: AbortSignal) =>
    getJson<Paged<EventHit>>(`/api/v1/events?${kw(keyword, page, size)}`, signal),
  detail: (id: number, signal?: AbortSignal) => getJson<EventDetail>(`/api/v1/events/${id}`, signal),
  create: (body: unknown) => send<EventDetail>('POST', '/api/v1/events', body),
  update: (id: number, body: unknown) => send<EventDetail>('PUT', `/api/v1/events/${id}`, body),
  remove: (id: number) => send<unknown>('DELETE', `/api/v1/events/${id}`),
  persons: (id: number) => getJson<EventPersonRow[]>(`/api/v1/events/${id}/persons`),
  linkPerson: (id: number, body: unknown) => send<EventPersonRow>('POST', `/api/v1/events/${id}/persons`, body),
  updatePersonLink: (id: number, linkId: number, body: unknown) =>
    send<EventPersonRow>('PUT', `/api/v1/events/${id}/persons/${linkId}`, body),
  unlinkPerson: (id: number, linkId: number) => send<unknown>('DELETE', `/api/v1/events/${id}/persons/${linkId}`),
  places: (id: number) => getJson<EventPlaceRow[]>(`/api/v1/events/${id}/places`),
  linkPlace: (id: number, body: unknown) => send<EventPlaceRow>('POST', `/api/v1/events/${id}/places`, body),
  updatePlaceLink: (id: number, linkId: number, body: unknown) =>
    send<EventPlaceRow>('PUT', `/api/v1/events/${id}/places/${linkId}`, body),
  unlinkPlace: (id: number, linkId: number) => send<unknown>('DELETE', `/api/v1/events/${id}/places/${linkId}`),
}

// ==========================================================================
// M3：时间—地图联动
// 时间一律天文学纪年整数；区间端点包含式。
// ==========================================================================

/** 地图事件标记：时间窗口 ∩ 视野，返回 GeoJSON FeatureCollection。 */
export function fetchEventMap(
  bbox: [number, number, number, number],
  from: number,
  to: number,
  limit = 1200,
  signal?: AbortSignal,
): Promise<EventFeatureCollection> {
  const q = new URLSearchParams({
    bbox: bbox.map((n) => n.toFixed(5)).join(','),
    from: String(from),
    to: String(to),
    limit: String(limit),
  })
  return getJson<EventFeatureCollection>(`${BASE}/events/map?${q.toString()}`, signal)
}

/** 历史时空矩阵：地区 → 政权 → 时间段 → 事件。 */
export function fetchMatrix(
  from: number,
  step: number,
  count = 12,
  offset = 0,
  signal?: AbortSignal,
): Promise<MatrixResponse> {
  const q = new URLSearchParams({
    from: String(from),
    step: String(step),
    count: String(count),
    offset: String(offset),
  })
  return getJson<MatrixResponse>(`${BASE}/events/matrix?${q.toString()}`, signal)
}

/** 事件详情（含政权关联）。 */
export function fetchEvent(id: number, signal?: AbortSignal): Promise<EventDetail> {
  return getJson<EventDetail>(`${BASE}/events/${id}`, signal)
}

export const polityApi = {
  regions: (signal?: AbortSignal) => getJson<PolityRegion[]>(`${BASE}/polities/regions`, signal),
  list: (keyword: string, region = '', size = 20, signal?: AbortSignal) => {
    const q = new URLSearchParams({ size: String(size) })
    if (keyword.trim()) q.set('keyword', keyword.trim())
    if (region) q.set('region', region)
    return getJson<Paged<PolityHit>>(`${BASE}/polities?${q.toString()}`, signal)
  },
  create: (body: unknown) => send<PolityHit>('POST', `${BASE}/polities`, body),
  byEvent: (eventId: number, signal?: AbortSignal) =>
    getJson<EventPolityRow[]>(`${BASE}/events/${eventId}/polities`, signal),
  link: (eventId: number, body: unknown) =>
    send<EventPolityRow>('POST', `${BASE}/events/${eventId}/polities`, body),
  unlink: (eventId: number, linkId: number) =>
    send<unknown>('DELETE', `${BASE}/events/${eventId}/polities/${linkId}`),
}
