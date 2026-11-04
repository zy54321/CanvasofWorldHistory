<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'
import maplibregl, { type Map as MlMap, type MapMouseEvent } from 'maplibre-gl'
import { fetchEventMap, fetchMap } from '../api'
import type { EventFeatureCollection, PlaceFeatureCollection } from '../types'
import {
  HAS_BASEMAP,
  REGION_PRESETS,
  STYLE_OPTIONS,
  fallbackStyle,
  styleUrl,
  type StyleId,
} from '../map/basemaps'

const props = defineProps<{
  selectedId: number | null
  /** 当前时间窗口（天文学纪年整数，端点包含） */
  timeFrom: number
  timeTo: number
  /** 图层开关：事件 / 地点 */
  showEvents: boolean
  showPlaces: boolean
  /** 是否显示"无名地点"（占位名且无别名的记录，默认不显示） */
  showUnnamed: boolean
}>()
const emit = defineEmits<{
  (e: 'select', placeId: number): void
  (e: 'overlap', payload: { x: number; y: number; items: { placeId: number; name: string; geomType: string }[] }): void
  (e: 'clear'): void
  (e: 'event-select', eventId: number): void
  (e: 'meta', payload: { returned: number; totalInBbox: number; truncated: boolean }): void
  (e: 'event-meta', payload: { returned: number; totalInWindow: number; truncated: boolean }): void
}>()

const container = ref<HTMLDivElement | null>(null)
const map = shallowRef<MlMap | null>(null)
const currentStyle = ref<StyleId>('outdoor')
const activeRegion = ref<string>('world')
const loading = ref(false)
const mapError = ref<string | null>(null)
const styleSwitching = ref(false)

const PLACES = 'places'          // 面 / 线（真实几何，不聚合）
const PLACES_PTS = 'places-pts'  // 点（低缩放聚合）
const EVENTS = 'events'
const SELECTED = 'selected-place'
const MAP_LIMIT = 400
const EVENT_LIMIT = 1200

let fetchAbort: AbortController | null = null
let eventAbort: AbortController | null = null
let moveTimer: number | undefined

let lastShapes: PlaceFeatureCollection | null = null
let lastPoints: PlaceFeatureCollection | null = null
let lastEvents: EventFeatureCollection | null = null

function emptyFC(): GeoJSON.FeatureCollection {
  return { type: 'FeatureCollection', features: [] }
}

function ensureLayers(m: MlMap) {
  // ---------------- 面 / 线：真实几何（M4-4b 起库里就有 Polygon / MultiPolygon / LineString）
  if (!m.getSource(PLACES)) {
    m.addSource(PLACES, {
      type: 'geojson',
      data: (lastShapes ?? emptyFC()) as unknown as GeoJSON.FeatureCollection,
    })
  }
  if (!m.getLayer('places-fill')) {
    m.addLayer({
      id: 'places-fill',
      type: 'fill',
      source: PLACES,
      filter: ['in', ['geometry-type'], ['literal', ['Polygon', 'MultiPolygon']]],
      paint: {
        // 面：暖赭色半透明填充 —— 与点的浅底棕环、事件的实心红点区分开
        'fill-color': '#d9a463',
        // 大区域（如 Italia 22 万 km²）在小比例尺下会盖住底图：
        // 填充随缩放加深、但上限压低，轮廓另有一层，形状仍然清楚可辨
        'fill-opacity': ['interpolate', ['linear'], ['zoom'], 2, 0.08, 6, 0.14, 10, 0.22],
      },
    })
  }
  if (!m.getLayer('places-outline')) {
    m.addLayer({
      id: 'places-outline',
      type: 'line',
      source: PLACES,
      filter: ['in', ['geometry-type'], ['literal', ['Polygon', 'MultiPolygon']]],
      paint: { 'line-color': '#8c5a2b', 'line-width': ['interpolate', ['linear'], ['zoom'], 2, 0.6, 8, 1.6] },
    })
  }
  if (!m.getLayer('places-line')) {
    m.addLayer({
      id: 'places-line',
      type: 'line',
      source: PLACES,
      filter: ['==', ['geometry-type'], 'LineString'],
      paint: {
        // 线：青蓝色虚线，与面、点、事件都不同色系
        'line-color': '#1f6f8b',
        'line-width': ['interpolate', ['linear'], ['zoom'], 2, 1, 8, 2.6],
        'line-dasharray': [2, 1.4],
      },
    })
  }
  // 面/线的"加宽命中层"：真实几何很细，直接点几乎点不中
  if (!m.getLayer('places-shape-hit')) {
    m.addLayer({
      id: 'places-shape-hit',
      type: 'line',
      source: PLACES,
      paint: { 'line-color': 'rgba(0,0,0,0)', 'line-width': 14 },
    })
  }

  // ---------------- 点：低缩放聚合
  if (!m.getSource(PLACES_PTS)) {
    m.addSource(PLACES_PTS, {
      type: 'geojson',
      data: (lastPoints ?? emptyFC()) as unknown as GeoJSON.FeatureCollection,
      cluster: true,
      clusterRadius: 44,
      clusterMaxZoom: 5,
    } as never)
  }
  if (!m.getLayer('places-cluster')) {
    m.addLayer({
      id: 'places-cluster',
      type: 'circle',
      source: PLACES_PTS,
      filter: ['has', 'point_count'],
      paint: {
        'circle-radius': ['step', ['get', 'point_count'], 12, 20, 16, 100, 21, 500, 26],
        'circle-color': '#8c5a2b',
        'circle-opacity': 0.85,
        'circle-stroke-color': '#ffffff',
        'circle-stroke-width': 1.6,
      },
    })
  }
  if (!m.getLayer('places-cluster-count')) {
    m.addLayer({
      id: 'places-cluster-count',
      type: 'symbol',
      source: PLACES_PTS,
      filter: ['has', 'point_count'],
      layout: {
        'text-field': ['get', 'point_count_abbreviated'],
        'text-size': 11,
        'text-font': ['Noto Sans Regular'],
        'text-allow-overlap': true,
      },
      paint: { 'text-color': '#ffffff' },
    })
  }
  if (!m.getLayer('places-halo')) {
    m.addLayer({
      id: 'places-halo',
      type: 'circle',
      source: PLACES_PTS,
      filter: ['!', ['has', 'point_count']],
      paint: {
        'circle-radius': ['interpolate', ['linear'], ['zoom'], 0, 4, 4, 7, 8, 11],
        'circle-color': '#8c5a2b',
        'circle-opacity': 0.12,
      },
    })
  }
  if (!m.getLayer('places-dot')) {
    m.addLayer({
      id: 'places-dot',
      type: 'circle',
      source: PLACES_PTS,
      filter: ['!', ['has', 'point_count']],
      paint: {
        'circle-radius': ['interpolate', ['linear'], ['zoom'], 0, 2.2, 4, 4, 8, 6.5],
        // 浅色填充 + 棕色描边 = 「地名点」；事件是实心红点，缩小时也不会混淆
        'circle-color': '#f7eddd',
        'circle-stroke-color': '#8c5a2b',
        'circle-stroke-width': ['interpolate', ['linear'], ['zoom'], 0, 1.1, 6, 1.8],
      },
    })
  }

  // ---------------- 地名标签：只在看得清的时候出现
  if (!m.getLayer('places-label')) {
    m.addLayer({
      id: 'places-label',
      type: 'symbol',
      source: PLACES_PTS,
      minzoom: 6,
      filter: ['all', ['!', ['has', 'point_count']], ['!=', ['get', 'unnamed'], true]],
      layout: {
        'text-field': ['get', 'name'],
        'text-size': ['interpolate', ['linear'], ['zoom'], 6, 10, 10, 13],
        'text-font': ['Noto Sans Regular'],
        'text-offset': [0, 1.1],
        'text-anchor': 'top',
        'text-allow-overlap': false,
        'text-ignore-placement': false,
        'text-padding': 3,
      },
      paint: { 'text-color': '#4a3520', 'text-halo-color': 'rgba(255,255,255,0.9)', 'text-halo-width': 1.4 },
    })
  }

  // ---------------- 事件（M3，带聚合）
  if (!m.getSource(EVENTS)) {
    m.addSource(EVENTS, {
      type: 'geojson',
      data: (lastEvents ?? emptyFC()) as unknown as GeoJSON.FeatureCollection,
      cluster: true,
      clusterRadius: 46,
      clusterMaxZoom: 6,
    } as never)
  }
  if (!m.getLayer('events-cluster')) {
    m.addLayer({
      id: 'events-cluster',
      type: 'circle',
      source: EVENTS,
      filter: ['has', 'point_count'],
      paint: {
        'circle-radius': ['step', ['get', 'point_count'], 11, 5, 14, 20, 18, 50, 22],
        'circle-color': '#b3261e',
        'circle-opacity': 0.85,
        'circle-stroke-color': '#ffffff',
        'circle-stroke-width': 1.6,
      },
    })
  }
  if (!m.getLayer('events-point')) {
    m.addLayer({
      id: 'events-point',
      type: 'circle',
      source: EVENTS,
      filter: ['!', ['has', 'point_count']],
      paint: {
        'circle-radius': ['interpolate', ['linear'], ['zoom'], 0, 4, 4, 6, 8, 8.5],
        'circle-color': '#b3261e',
        'circle-stroke-color': '#ffffff',
        'circle-stroke-width': 1.4,
      },
    })
  }

  // ---------------- 选中环
  if (!m.getSource(SELECTED)) {
    m.addSource(SELECTED, { type: 'geojson', data: emptyFC() as never })
  }
  if (!m.getLayer('selected-ring')) {
    m.addLayer({
      id: 'selected-ring',
      type: 'circle',
      source: SELECTED,
      paint: {
        'circle-radius': ['interpolate', ['linear'], ['zoom'], 0, 9, 6, 16],
        'circle-color': 'rgba(0,0,0,0)',
        'circle-stroke-color': '#1f6feb',
        'circle-stroke-width': 2.4,
      },
    })
  }

  applyVisibility(m)
}

/** 图层开关（不改数据，只改可见性） */
function applyVisibility(m: MlMap) {
  const set = (id: string, v: boolean) => {
    if (m.getLayer(id)) m.setLayoutProperty(id, 'visibility', v ? 'visible' : 'none')
  }
  for (const id of ['places-fill', 'places-outline', 'places-line', 'places-shape-hit',
                    'places-cluster', 'places-cluster-count', 'places-halo', 'places-dot',
                    'places-label']) {
    set(id, props.showPlaces)
  }
  set('events-cluster', props.showEvents)
  set('events-point', props.showEvents)
}

function bboxOf(m: MlMap): [number, number, number, number] | null {
  const b = m.getBounds()
  const bbox: [number, number, number, number] = [
    Math.max(-180, b.getWest()),
    Math.max(-85, b.getSouth()),
    Math.min(180, b.getEast()),
    Math.min(85, b.getNorth()),
  ]
  if (!(bbox[0] < bbox[2]) || !(bbox[1] < bbox[3])) return null
  return bbox
}

async function loadPlaces() {
  const m = map.value
  if (!m || !props.showPlaces) return
  const bbox = bboxOf(m)
  if (!bbox) return
  fetchAbort?.abort()
  fetchAbort = new AbortController()
  try {
    const fc = await fetchMap(bbox, MAP_LIMIT, fetchAbort.signal)
    // 后端返回的是**真实几何**（Point / Polygon / MultiPolygon / LineString）。
    // 面线走非聚合源（要保留形状），点走聚合源（低缩放正确聚合）。
    // 无名地点（源标题是 Untitled / Unnamed Place 且没有别名）默认不进图层：
    // 它们不是地名，混在地名里只会误导；用「无名地点」开关单独查看。
    const feats = props.showUnnamed
      ? fc.features
      : fc.features.filter((f) => f.properties?.unnamed !== true)
    const shapes = feats.filter((f) => f.geometry.type !== 'Point')
    const points = feats.filter((f) => f.geometry.type === 'Point')
    lastShapes = { ...fc, features: shapes }
    lastPoints = { ...fc, features: points }
    ;(m.getSource(PLACES) as maplibregl.GeoJSONSource | undefined)
      ?.setData(lastShapes as unknown as GeoJSON.FeatureCollection)
    ;(m.getSource(PLACES_PTS) as maplibregl.GeoJSONSource | undefined)
      ?.setData(lastPoints as unknown as GeoJSON.FeatureCollection)
    emit('meta', {
      returned: fc.meta.returned,
      totalInBbox: fc.meta.totalInBbox,
      truncated: fc.meta.truncated,
    })
  } catch (err) {
    if ((err as Error).name === 'AbortError') return
    mapError.value = `地点图层加载失败：${(err as Error).message}`
  }
}

async function loadEvents() {
  const m = map.value
  if (!m || !props.showEvents) return
  const bbox = bboxOf(m)
  if (!bbox) return
  eventAbort?.abort()
  eventAbort = new AbortController()
  loading.value = true
  try {
    const fc = await fetchEventMap(bbox, props.timeFrom, props.timeTo, EVENT_LIMIT, eventAbort.signal)
    lastEvents = fc
    const src = m.getSource(EVENTS) as maplibregl.GeoJSONSource | undefined
    src?.setData(fc as unknown as GeoJSON.FeatureCollection)
    emit('event-meta', {
      returned: fc.meta.returned,
      totalInWindow: fc.meta.totalInWindow,
      truncated: fc.meta.truncated,
    })
    mapError.value = null
  } catch (err) {
    if ((err as Error).name === 'AbortError') return
    mapError.value = `事件图层加载失败：${(err as Error).message}`
  } finally {
    loading.value = false
  }
}

function scheduleLoad() {
  window.clearTimeout(moveTimer)
  moveTimer = window.setTimeout(() => {
    void loadPlaces()
    void loadEvents()
  }, 260)
}

function baseStyle() {
  return HAS_BASEMAP ? styleUrl(currentStyle.value) : fallbackStyle(currentStyle.value)
}

/** 命中判定的容差（像素）：点太小、线太细，按 0 像素判定几乎点不中 */
const HIT_PAD = 7

function onMapClick(e: MapMouseEvent) {
  const m = map.value
  if (!m) return
  const pt = e.point

  // 1) 事件聚合：放大到能看清具体标记
  const cl = m.queryRenderedFeatures(pt, { layers: ['events-cluster'] })
  if (cl.length > 0) {
    const cid = cl[0].properties?.cluster_id
    const src = m.getSource(EVENTS) as maplibregl.GeoJSONSource
    src.getClusterExpansionZoom(cid).then((z) => {
      const geom = (cl[0].geometry as GeoJSON.Point).coordinates as [number, number]
      m.easeTo({ center: geom, zoom: Math.min(z + 0.4, 12), duration: 600 })
    })
    return
  }
  // 2) 事件点
  const ev = m.queryRenderedFeatures(pt, { layers: ['events-point'] })
  if (ev.length > 0) {
    const id = Number(ev[0].properties?.eventId)
    if (Number.isFinite(id)) emit('event-select', id)
    return
  }
  // 3) 地点聚合：放大地图
  const pcl = m.queryRenderedFeatures(pt, { layers: ['places-cluster'] })
  if (pcl.length > 0) {
    const cid = pcl[0].properties?.cluster_id
    const src = m.getSource(PLACES_PTS) as maplibregl.GeoJSONSource
    src.getClusterExpansionZoom(cid).then((z) => {
      const geom = (pcl[0].geometry as GeoJSON.Point).coordinates as [number, number]
      m.easeTo({ center: geom, zoom: Math.min(z + 0.3, 12), duration: 600 })
    })
    return
  }

  // 4) 地点：带容差命中，并且把同一位置的所有地点都收集起来
  const box: [maplibregl.PointLike, maplibregl.PointLike] = [
    [pt.x - HIT_PAD, pt.y - HIT_PAD],
    [pt.x + HIT_PAD, pt.y + HIT_PAD],
  ]
  const hitLayers = ['places-shape-hit', 'places-fill', 'places-dot'].filter((l) => m.getLayer(l))
  const hits = m.queryRenderedFeatures(box, { layers: hitLayers })
  if (hits.length > 0) {
    const seen = new Set<number>()
    const items: { placeId: number; name: string; geomType: string }[] = []
    for (const f of hits) {
      const id = Number(f.properties?.placeId)
      if (!Number.isFinite(id) || seen.has(id)) continue
      seen.add(id)
      items.push({
        placeId: id,
        name: String(f.properties?.name ?? ''),
        geomType: String(f.properties?.geomType ?? ''),
      })
    }
    if (items.length === 1) {
      emit('select', items[0].placeId)
    } else if (items.length > 1) {
      // 重叠：把候选列出来，而不是随便挑一个
      emit('overlap', { x: pt.x, y: pt.y, items })
    }
    return
  }
  // 5) 点空白：关闭当前弹窗
  emit('clear')
}

function setCursor(on: boolean) {
  const m = map.value
  if (m) m.getCanvas().style.cursor = on ? 'pointer' : ''
}

onMounted(() => {
  if (!container.value) return
  const m = new maplibregl.Map({
    container: container.value,
    style: baseStyle() as never,
    center: [20, 20],
    zoom: 1.4,
    minZoom: 0.4,
    maxZoom: 14,
    attributionControl: false,
    dragRotate: false,
  })
  map.value = m
  // 便于本地/自动化验收时读取相机与图层状态
  ;(window as unknown as Record<string, unknown>).__map = m

  m.addControl(new maplibregl.NavigationControl({ visualizePitch: false }), 'bottom-right')
  m.addControl(new maplibregl.ScaleControl({ maxWidth: 110, unit: 'metric' }), 'bottom-left')
  m.addControl(
    new maplibregl.AttributionControl({
      compact: true,
      customAttribution: HAS_BASEMAP
        ? '历史地名数据：CHGIS / Pleiades / MCGD / WHG'
        : '无底图（缺 MapTiler API Key）｜ 历史地名数据：CHGIS / Pleiades / MCGD / WHG',
    }),
    'bottom-right',
  )

  m.on('load', () => {
    ensureLayers(m)
    void loadPlaces()
    void loadEvents()
  })

  m.on('moveend', () => {
    if (styleSwitching.value) return
    activeRegion.value = ''
    scheduleLoad()
  })

  m.on('mousemove', (e) => {
    const hits = m.queryRenderedFeatures(e.point, {
      layers: ['events-point', 'events-cluster', 'places-dot', 'places-cluster',
               'places-fill', 'places-shape-hit'].filter((l) => m.getLayer(l)),
    })
    setCursor(hits.length > 0)
  })

  m.on('click', onMapClick)

  m.on('error', (e) => {
    const msg = (e as unknown as { error?: Error }).error?.message ?? '未知地图错误'
    if (/style|key|unauthor|forbidden|403|401/i.test(msg)) {
      mapError.value = `底图错误：${msg}`
    }
  })

  window.addEventListener('resize', resize)
})

function resize() {
  map.value?.resize()
}

onBeforeUnmount(() => {
  window.clearTimeout(moveTimer)
  fetchAbort?.abort()
  eventAbort?.abort()
  window.removeEventListener('resize', resize)
  map.value?.remove()
  map.value = null
})

function switchStyle(id: StyleId) {
  const m = map.value
  if (!m || id === currentStyle.value) return
  currentStyle.value = id
  styleSwitching.value = true
  const center = m.getCenter()
  const zoom = m.getZoom()
  const bearing = m.getBearing()
  m.setStyle(baseStyle() as never, { diff: false })
  m.once('style.load', () => {
    ensureLayers(m)
    // setStyle 已保留相机，这里显式再设一次以消除个别底图的跳变
    m.jumpTo({ center, zoom, bearing })
    styleSwitching.value = false
    void loadPlaces()
    void loadEvents()
  })
}

function goRegion(id: string) {
  const m = map.value
  const preset = REGION_PRESETS.find((r) => r.id === id)
  if (!m || !preset) return
  activeRegion.value = id
  m.flyTo({ center: preset.center, zoom: preset.zoom, duration: 900, essential: true })
}

/** 供父组件定位到某地点 */
function flyToPlace(lon: number, lat: number, zoom = 7) {
  const m = map.value
  if (!m) return
  m.flyTo({ center: [lon, lat], zoom: Math.max(m.getZoom(), zoom), duration: 1100, essential: true })
  highlight(lon, lat)
}

function highlight(lon: number, lat: number) {
  const m = map.value
  if (!m) return
  const src = m.getSource(SELECTED) as maplibregl.GeoJSONSource | undefined
  src?.setData({
    type: 'FeatureCollection',
    features: [
      { type: 'Feature', properties: {}, geometry: { type: 'Point', coordinates: [lon, lat] } },
    ],
  } as never)
}

function clearHighlight() {
  const m = map.value
  if (!m) return
  const src = m.getSource(SELECTED) as maplibregl.GeoJSONSource | undefined
  src?.setData(emptyFC() as never)
}

defineExpose({ flyToPlace, highlight, clearHighlight, loadPlaces, loadEvents, switchStyle, goRegion })

watch(
  () => props.selectedId,
  (id) => {
    if (id === null) clearHighlight()
  },
)

// 时间窗口变化 → 只重查事件；相机与底图不变
watch(
  () => [props.timeFrom, props.timeTo] as const,
  () => {
    void loadEvents()
  },
)

watch(
  () => props.showUnnamed,
  () => {
    void loadPlaces()
  },
)

watch(
  () => [props.showEvents, props.showPlaces] as const,
  () => {
    const m = map.value
    if (!m) return
    applyVisibility(m)
    if (props.showPlaces) void loadPlaces()
    if (props.showEvents) void loadEvents()
  },
)
</script>

<template>
  <div class="map-wrap">
    <div ref="container" class="map-canvas" />

    <!-- 样式切换 -->
    <div class="style-bar panel">
      <button
        v-for="s in STYLE_OPTIONS"
        :key="s.id"
        :class="{ active: currentStyle === s.id }"
        :title="HAS_BASEMAP ? `切换到 ${s.label}` : `离线预览底色（未接入 MapTiler）`"
        @click="switchStyle(s.id)"
      >
        {{ s.label }}
      </button>
    </div>

    <!-- 区域预设 -->
    <div class="region-bar panel">
      <span class="tiny dim">区域</span>
      <button
        v-for="r in REGION_PRESETS"
        :key="r.id"
        :class="{ active: activeRegion === r.id }"
        @click="goRegion(r.id)"
      >
        {{ r.label }}
      </button>
    </div>

    <!-- 状态条 -->
    <div class="map-status panel tiny">
      <span v-if="loading">查询当前时间段的事件…</span>
      <span v-else-if="mapError" class="err">{{ mapError }}</span>
      <span v-else class="dim">拖动或缩放地图，按当前时间段查询历史事件</span>
    </div>

    <div v-if="!HAS_BASEMAP" class="no-key panel">
      <strong>底图未接入 MapTiler</strong>
      <p>
        未检测到 <code>VITE_MAPTILER_API_KEY</code>。当前为离线降级视图：只有底色与经纬网，
        <b>不带任何地图瓦片</b>。右上角样式按钮仅切换离线预览底色，不代表 Outdoor / Streets /
        Satellite / Hybrid 底图可用。
      </p>
      <p>事件图层、地点图层、检索、详情等数据能力不受影响，均为真实数据库结果。</p>
      <p class="tiny dim">
        在 <code>code/.env</code> 中填入 MapTiler <em>API key</em>（非 Service Token）后重启前端即可加载真实底图。
      </p>
    </div>
  </div>
</template>

<style scoped>
.map-wrap { position: absolute; inset: 0; }
.map-canvas { position: absolute; inset: 0; }

.style-bar {
  position: absolute;
  /* 顶部有全局标题栏，控件下移避免遮挡 */
  top: 66px;
  right: 14px;
  display: flex;
  gap: 4px;
  padding: 5px;
  z-index: 5;
}

.region-bar {
  position: absolute;
  top: 66px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 5px 8px;
  z-index: 5;
}
.region-bar .tiny { margin-right: 2px; }

.map-status {
  position: absolute;
  /* 让出底部时间轴的位置 */
  bottom: 92px;
  left: 50%;
  transform: translateX(-50%);
  padding: 5px 12px;
  z-index: 5;
  max-width: 60vw;
}
.err { color: #b3261e; }

.no-key {
  position: absolute;
  top: 112px;
  left: 14px;
  width: 320px;
  padding: 12px 14px;
  z-index: 6;
  border-left: 3px solid var(--warn-line);
  background: var(--warn-bg);
}
.no-key strong { color: var(--warn-ink); font-size: 13px; }
.no-key p { margin: 6px 0 0; font-size: 12px; line-height: 1.55; color: #6b4a12; }
.no-key code { background: rgba(0, 0, 0, 0.06); padding: 1px 4px; border-radius: 3px; }
</style>
