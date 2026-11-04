<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import MapView from './components/MapView.vue'
import SearchPanel from './components/SearchPanel.vue'
import DetailPanel from './components/DetailPanel.vue'
import EventDetailPanel from './components/EventDetailPanel.vue'
import TimelineBar from './components/TimelineBar.vue'
import MatrixView from './components/MatrixView.vue'
import ManagePanel from './components/manage/ManagePanel.vue'
import { fetchStats } from './api'
import { clampFrom, formatWindow, windowEnd, type Span } from './time'
import type { MapStats, PlaceSummary } from './types'

const mapRef = ref<InstanceType<typeof MapView> | null>(null)
const selectedPlaceId = ref<number | null>(null)
const selectedEventId = ref<number | null>(null)
/** 从矩阵点开事件时自动定位；从地图标记点开时不重复飞过去 */
const autoLocate = ref(true)

const viewport = ref<{ returned: number; totalInBbox: number; truncated: boolean } | null>(null)
const eventMeta = ref<{ returned: number; totalInWindow: number; truncated: boolean } | null>(null)
const stats = ref<MapStats | null>(null)
const apiDown = ref(false)
const manageOpen = ref(false)
const matrixOpen = ref(false)

// 两个图层默认都开：M1 的历史地点（古代地名）是地图的基本内容，
// M3 的事件标记叠加在它上面；互不关闭、互不覆盖。
const showEvents = ref(true)
const showPlaces = ref(true)

// ---- 时间状态：天文学纪年整数；默认公元前 500 年、10 年跨度（前500–前491）
const timeFrom = ref(-499)
const span = ref<Span>(10)
const timeTo = computed(() => windowEnd(timeFrom.value, span.value))
const currentLabel = computed(() => formatWindow(timeFrom.value, span.value))

onMounted(async () => {
  try {
    stats.value = await fetchStats()
  } catch {
    apiDown.value = true
  }
})

function onPick(item: PlaceSummary) {
  selectedEventId.value = null
  selectedPlaceId.value = item.placeId
  // M4-4c：接口 non_null 序列化，无代表坐标的地点不带 lon/lat（取到 undefined）。
  // 原来的 `!== null` 会放过 undefined，于是 flyToPlace(undefined, undefined)
  // 让 MapLibre 抛 "Invalid LngLat object: (NaN, NaN)"。
  // 用 `!= null` 同时挡住 null 与 undefined：没有坐标就不飞，详情照常打开。
  if (item.lon != null && item.lat != null) {
    mapRef.value?.flyToPlace(item.lon, item.lat)
  }
}

function onPlaceSelect(placeId: number) {
  selectedEventId.value = null
  selectedPlaceId.value = placeId
}

/** 地图标记 → 详情（已在该位置，不再自动飞） */
function onMapEvent(eventId: number) {
  autoLocate.value = false
  selectedPlaceId.value = null
  selectedEventId.value = eventId
}

/**
 * 矩阵事件 → 收起矩阵 + 详情 + 自动定位到实际地点。
 * 必须先收起：矩阵是覆盖层，详情面板与地图都在它下面，不收起用户看不到定位结果。
 */
function onMatrixEvent(eventId: number) {
  matrixOpen.value = false
  autoLocate.value = true
  selectedPlaceId.value = null
  selectedEventId.value = eventId
}

function onEventLocate(lon: number, lat: number) {
  mapRef.value?.flyToPlace(lon, lat)
}

function closeDetail() {
  selectedPlaceId.value = null
  selectedEventId.value = null
  mapRef.value?.clearHighlight()
}

function setFrom(v: number) {
  timeFrom.value = clampFrom(v, span.value)
}

function setSpan(v: Span) {
  span.value = v
  timeFrom.value = clampFrom(timeFrom.value, v)
}

function onSelectWindow(from: number, to: number) {
  span.value = (to - from + 1) as Span
  timeFrom.value = clampFrom(from, span.value)
  // 不关闭矩阵：地图在覆盖层下方同步刷新，收起矩阵即可看到该时间段的事件
}

function closeMatrix() {
  matrixOpen.value = false
  // 矩阵只是覆盖层：地图从未重建，收起后保留当前中心、缩放与选中的时间
  mapRef.value?.loadEvents()
}

function onManageLocate(lon: number, lat: number) {
  manageOpen.value = false
  mapRef.value?.flyToPlace(lon, lat)
}
</script>

<template>
  <div class="shell">
    <MapView
      ref="mapRef"
      :selected-id="selectedPlaceId"
      :time-from="timeFrom"
      :time-to="timeTo"
      :show-events="showEvents"
      :show-places="showPlaces"
      @select="onPlaceSelect"
      @event-select="onMapEvent"
      @meta="viewport = $event"
      @event-meta="eventMeta = $event"
    />

    <!-- 顶部：标题 + 入口 -->
    <header class="topbar panel">
      <div class="brand">
        <span class="brand-name">世界历史时空画布</span>
        <span class="brand-sub tiny dim">时间 × 空间</span>
      </div>
      <div class="tb-right">
        <button :class="{ active: matrixOpen }" title="打开历史时空矩阵" @click="matrixOpen = true">
          时间观察
        </button>
        <button class="reserved" disabled title="M3 不实现；保留入口">
          空间反查 <span class="badge">预留</span>
        </button>
        <button title="打开地点 / 人物 / 事件管理" @click="manageOpen = true">内容管理</button>
      </div>
    </header>

    <!-- 左侧：地点检索 + 数据状况 -->
    <div class="left">
      <SearchPanel @pick="onPick" />
      <div class="data-note panel tiny">
        <template v-if="stats">
          <span><strong>{{ stats.places.toLocaleString() }}</strong> 个历史地点</span>
          <span class="sep">·</span>
          <span>{{ stats.locationsWithGeom.toLocaleString() }} 条可用坐标</span>
        </template>
        <span v-else-if="apiDown" class="err">后端 API 未连接（/api/v1 不可达）</span>
        <span v-else class="dim">读取数据统计…</span>
        <template v-if="viewport">
          <span class="sep">｜</span>
          <span v-if="viewport.returned === 0" class="dim">当前视野无可信坐标地点</span>
          <span v-else class="dim">
            当前视野 {{ viewport.returned.toLocaleString() }}
            <template v-if="viewport.totalInBbox > viewport.returned">/ {{ viewport.totalInBbox.toLocaleString() }}</template>
          </span>
        </template>
      </div>
    </div>

    <!-- 右侧：事件 / 地点详情 -->
    <transition name="slide">
      <div v-if="selectedEventId !== null || selectedPlaceId !== null" class="right">
        <EventDetailPanel
          v-if="selectedEventId !== null"
          :key="'ev' + selectedEventId"
          :event-id="selectedEventId"
          :auto-locate="autoLocate"
          @close="closeDetail"
          @locate="onEventLocate"
        />
        <DetailPanel
          v-else-if="selectedPlaceId !== null"
          :key="'pl' + selectedPlaceId"
          :place-id="selectedPlaceId"
          @close="closeDetail"
          @locate="onEventLocate"
        />
      </div>
    </transition>

    <!-- 图层开关 -->
    <div class="layer-switch panel tiny">
      <span class="dim">图层</span>
      <button
        :class="{ active: showEvents }"
        title="历史事件标记（当前时间段）"
        @click="showEvents = !showEvents"
      >
        <span class="dot ev" />事件
      </button>
      <button
        :class="{ active: showPlaces }"
        title="历史地点（M1 图层：古代地名与历史地点）"
        @click="showPlaces = !showPlaces"
      >
        <span class="dot pl" />地点
      </button>
    </div>

    <!-- 底部：时间轴（收起态） -->
    <div class="timeline-dock">
      <TimelineBar
        :from="timeFrom"
        :span="span"
        :event-count="eventMeta ? eventMeta.returned : null"
        :truncated="eventMeta?.truncated ?? false"
        @update:from="setFrom"
        @update:span="setSpan"
        @expand="matrixOpen = true"
      />
    </div>

    <!-- 展开态：历史时空矩阵（覆盖层，地图不重建） -->
    <MatrixView
      :open="matrixOpen"
      :from="timeFrom"
      :step="span"
      :event-count="eventMeta ? eventMeta.returned : null"
      @close="closeMatrix"
      @select-window="onSelectWindow"
      @event-select="onMatrixEvent"
    />

    <ManagePanel :open="manageOpen" @close="manageOpen = false" @locate="onManageLocate" />
  </div>
</template>

<style scoped>
.shell { position: absolute; inset: 0; overflow: hidden; }

.topbar {
  position: absolute;
  top: 12px;
  left: 14px;
  right: 14px;
  height: 44px;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 12px;
  z-index: 20;
}
.brand { display: flex; align-items: baseline; gap: 8px; }
.brand-name { font-size: 15px; font-weight: 700; letter-spacing: 0.01em; }
.brand-sub { font-size: 10.5px; }
.tb-right { margin-left: auto; display: flex; gap: 6px; align-items: center; }
.tb-right button { font-size: 12px; padding: 5px 10px; }
.reserved { color: var(--ink-3); }
.badge {
  font-size: 9.5px;
  padding: 0 4px;
  margin-left: 2px;
  border-radius: 3px;
  background: #eef0f3;
  color: var(--ink-3);
}

.left {
  position: absolute;
  top: 66px;
  left: 14px;
  width: 330px;
  z-index: 12;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.data-note {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 5px 10px;
  flex-wrap: wrap;
  line-height: 1.5;
}
.sep { color: #cfd6de; }
.err { color: #b3261e; }

.right {
  position: absolute;
  top: 66px;
  right: 14px;
  z-index: 14;
}

.layer-switch {
  position: absolute;
  right: 14px;
  bottom: 16px;
  z-index: 12;
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
}
.layer-switch button { font-size: 11.5px; padding: 3px 8px; display: inline-flex; align-items: center; gap: 4px; }
.dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
.dot.ev { background: #b3261e; }
.dot.pl { background: #f6ead8; border: 1.4px solid #8c5a2b; }

.timeline-dock {
  position: absolute;
  left: 50%;
  bottom: 14px;
  transform: translateX(-50%);
  z-index: 13;
}

.slide-enter-active, .slide-leave-active { transition: transform 0.2s ease, opacity 0.2s ease; }
.slide-enter-from, .slide-leave-to { transform: translateX(12px); opacity: 0; }
</style>
