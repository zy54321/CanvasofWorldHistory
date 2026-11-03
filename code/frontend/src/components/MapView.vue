<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'
import maplibregl, { type Map as MlMap, type MapMouseEvent } from 'maplibre-gl'
import { fetchMap } from '../api'
import type { PlaceFeatureCollection } from '../types'
import {
  HAS_BASEMAP,
  REGION_PRESETS,
  STYLE_OPTIONS,
  fallbackStyle,
  styleUrl,
  type StyleId,
} from '../map/basemaps'

const props = defineProps<{ selectedId: number | null }>()
const emit = defineEmits<{
  (e: 'select', placeId: number): void
  (e: 'meta', payload: { returned: number; totalInBbox: number; truncated: boolean }): void
}>()

const container = ref<HTMLDivElement | null>(null)
const map = shallowRef<MlMap | null>(null)
const currentStyle = ref<StyleId>('outdoor')
const activeRegion = ref<string>('world')
const loading = ref(false)
const mapError = ref<string | null>(null)
const styleSwitching = ref(false)

const SOURCE = 'places'
const SELECTED = 'selected-place'
const MAP_LIMIT = 400

let fetchAbort: AbortController | null = null
let moveTimer: number | undefined

/** 当前应该渲染的数据（样式切换后需重新灌入） */
let lastData: PlaceFeatureCollection | null = null

function emptyFC(): GeoJSON.FeatureCollection {
  return { type: 'FeatureCollection', features: [] }
}

function ensureLayers(m: MlMap) {
  if (!m.getSource(SOURCE)) {
    m.addSource(SOURCE, {
      type: 'geojson',
      data: (lastData ?? emptyFC()) as unknown as GeoJSON.FeatureCollection,
    })
  }
  if (!m.getLayer('places-halo')) {
    m.addLayer({
      id: 'places-halo',
      type: 'circle',
      source: SOURCE,
      paint: {
        'circle-radius': ['interpolate', ['linear'], ['zoom'], 0, 3, 4, 6, 8, 10],
        'circle-color': '#8c5a2b',
        'circle-opacity': 0.18,
      },
    })
  }
  if (!m.getLayer('places-dot')) {
    m.addLayer({
      id: 'places-dot',
      type: 'circle',
      source: SOURCE,
      paint: {
        'circle-radius': ['interpolate', ['linear'], ['zoom'], 0, 1.6, 4, 3.2, 8, 5.5],
        'circle-color': '#8c5a2b',
        'circle-stroke-color': '#ffffff',
        'circle-stroke-width': 0.8,
      },
    })
  }
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
}

async function loadViewport() {
  const m = map.value
  if (!m) return
  const b = m.getBounds()
  const bbox: [number, number, number, number] = [
    Math.max(-180, b.getWest()),
    Math.max(-85, b.getSouth()),
    Math.min(180, b.getEast()),
    Math.min(85, b.getNorth()),
  ]
  // 全球视野跳过反子午线跨界（west>east）的退化情况
  if (!(bbox[0] < bbox[2]) || !(bbox[1] < bbox[3])) return

  fetchAbort?.abort()
  fetchAbort = new AbortController()
  loading.value = true
  try {
    const fc = await fetchMap(bbox, MAP_LIMIT, fetchAbort.signal)
    lastData = fc
    const src = m.getSource(SOURCE) as maplibregl.GeoJSONSource | undefined
    src?.setData(fc as unknown as GeoJSON.FeatureCollection)
    emit('meta', {
      returned: fc.meta.returned,
      totalInBbox: fc.meta.totalInBbox,
      truncated: fc.meta.truncated,
    })
    mapError.value = null
  } catch (err) {
    if ((err as Error).name === 'AbortError') return
    mapError.value = `地点图层加载失败：${(err as Error).message}`
  } finally {
    loading.value = false
  }
}

function scheduleLoad() {
  window.clearTimeout(moveTimer)
  moveTimer = window.setTimeout(loadViewport, 260)
}

function baseStyle() {
  return HAS_BASEMAP ? styleUrl(currentStyle.value) : fallbackStyle(currentStyle.value)
}

function onMapClick(e: MapMouseEvent) {
  const m = map.value
  if (!m) return
  const hits = m.queryRenderedFeatures(e.point, { layers: ['places-dot'] })
  if (hits.length > 0) {
    const id = Number(hits[0].properties?.placeId)
    if (Number.isFinite(id)) emit('select', id)
  }
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
      // 有底图时版权由 MapTiler 样式自带，这里只补数据来源，避免重复；
      // 无底图时显式说明"无底图"，避免让人误以为已加载
      customAttribution: HAS_BASEMAP
        ? '历史地名数据：CHGIS / Pleiades / MCGD / WHG'
        : '无底图（缺 MapTiler API Key）｜ 历史地名数据：CHGIS / Pleiades / MCGD / WHG',
    }),
    'bottom-right',
  )

  m.on('load', () => {
    ensureLayers(m)
    loadViewport()
  })

  m.on('moveend', () => {
    if (styleSwitching.value) return
    activeRegion.value = ''
    scheduleLoad()
  })

  m.on('mousemove', (e) => {
    const hits = m.queryRenderedFeatures(e.point, { layers: ['places-dot'] })
    setCursor(hits.length > 0)
  })

  m.on('click', onMapClick)

  m.on('error', (e) => {
    const msg = (e as unknown as { error?: Error }).error?.message ?? '未知地图错误'
    // 瓦片 404 之类不阻断使用，只记录
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
    loadViewport()
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

defineExpose({ flyToPlace, highlight, clearHighlight, loadViewport, switchStyle, goRegion })

watch(
  () => props.selectedId,
  (id) => {
    if (id === null) clearHighlight()
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
      <span v-if="loading">加载地点…</span>
      <span v-else-if="mapError" class="err">{{ mapError }}</span>
      <span v-else class="dim">拖动或缩放地图以查询当前视野内的历史地点</span>
    </div>

    <div v-if="!HAS_BASEMAP" class="no-key panel">
      <strong>底图未接入 MapTiler</strong>
      <p>
        未检测到 <code>VITE_MAPTILER_API_KEY</code>。当前为离线降级视图：只有底色与经纬网，
        <b>不带任何地图瓦片</b>。右上角样式按钮仅切换离线预览底色，不代表 Outdoor / Streets /
        Satellite / Hybrid 底图可用。
      </p>
      <p>地点图层、检索、空间查询、详情等数据能力不受影响，均为真实数据库结果。</p>
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
  top: 14px;
  right: 14px;
  display: flex;
  gap: 4px;
  padding: 5px;
  z-index: 5;
}

.region-bar {
  position: absolute;
  top: 14px;
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
  bottom: 14px;
  left: 50%;
  transform: translateX(-50%);
  padding: 5px 12px;
  z-index: 5;
  max-width: 60vw;
}
.err { color: #b3261e; }

.no-key {
  position: absolute;
  top: 64px;
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