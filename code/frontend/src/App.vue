<script setup lang="ts">
import { onMounted, ref } from 'vue'
import MapView from './components/MapView.vue'
import SearchPanel from './components/SearchPanel.vue'
import DetailPanel from './components/DetailPanel.vue'
import ManagePanel from './components/manage/ManagePanel.vue'
import { fetchStats } from './api'
import type { MapStats, PlaceSummary } from './types'

const mapRef = ref<InstanceType<typeof MapView> | null>(null)
const selectedId = ref<number | null>(null)
const viewport = ref<{ returned: number; totalInBbox: number; truncated: boolean } | null>(null)
const stats = ref<MapStats | null>(null)
const apiDown = ref(false)
const manageOpen = ref(false)

onMounted(async () => {
  try {
    stats.value = await fetchStats()
  } catch {
    apiDown.value = true
  }
})

function onPick(item: PlaceSummary) {
  selectedId.value = item.placeId
  if (item.lon !== null && item.lat !== null) {
    mapRef.value?.flyToPlace(item.lon, item.lat)
  }
}

function onSelect(placeId: number) {
  selectedId.value = placeId
}

function onLocate(lon: number, lat: number) {
  mapRef.value?.flyToPlace(lon, lat)
}

function closeDetail() {
  selectedId.value = null
  mapRef.value?.clearHighlight()
}

/** 管理面板里点「看地图」——把地图飞到该坐标，并关闭管理面板 */
function onManageLocate(lon: number, lat: number) {
  manageOpen.value = false
  mapRef.value?.flyToPlace(lon, lat)
}
</script>

<template>
  <div class="shell">
    <MapView ref="mapRef" :selected-id="selectedId" @select="onSelect" @meta="viewport = $event" />

    <!-- 左侧：检索 -->
    <div class="left">
      <SearchPanel @pick="onPick" />
      <button class="manage-entry panel" @click="manageOpen = true">内容管理</button>
    </div>

    <!-- 右侧：详情 -->
    <transition name="slide">
      <div v-if="selectedId !== null" class="right">
        <DetailPanel :place-id="selectedId" @close="closeDetail" @locate="onLocate" />
      </div>
    </transition>

    <ManagePanel :open="manageOpen" @close="manageOpen = false" @locate="onManageLocate" />

    <!-- 底部左侧：数据状况 -->
    <div class="data-note panel tiny">
      <template v-if="stats">
        <span><strong>{{ stats.places.toLocaleString() }}</strong> 个历史地点</span>
        <span class="sep">·</span>
        <span>{{ stats.names.toLocaleString() }} 个名称</span>
        <span class="sep">·</span>
        <span>{{ stats.locationsWithGeom.toLocaleString() }} 条可用坐标</span>
        <span class="sep">·</span>
        <span class="dim">{{ stats.datasetCount }} 数据集 / {{ stats.sourceCount }} 来源</span>
      </template>
      <span v-else-if="apiDown" class="err">后端 API 未连接（/api/v1 不可达）</span>
      <span v-else class="dim">读取数据统计…</span>
      <template v-if="viewport">
        <span class="sep">｜</span>
        <span v-if="viewport.returned === 0" class="dim">
          当前视野内无可信坐标的历史地点（坐标系未知的不会显示）
        </span>
        <span v-else class="dim">
          当前视野 {{ viewport.returned.toLocaleString() }}
          <template v-if="viewport.totalInBbox > viewport.returned">
            / {{ viewport.totalInBbox.toLocaleString() }}（已达上限，请放大）
          </template>
        </span>
      </template>
    </div>
  </div>
</template>

<style scoped>
.shell { position: absolute; inset: 0; }

.left {
  position: absolute;
  top: 14px;
  left: 14px;
  z-index: 10;
}

.right {
  position: absolute;
  top: 14px;
  right: 14px;
  z-index: 10;
}

.manage-entry {
  display: block;
  width: 100%;
  margin-top: 8px;
  padding: 8px 12px;
  font-size: 12.5px;
  font-weight: 600;
  color: var(--accent);
  text-align: left;
}
.manage-entry:hover { background: var(--accent-soft); }

.data-note {
  position: absolute;
  left: 14px;
  bottom: 14px;
  z-index: 10;
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 5px 10px;
  max-width: 62vw;
  flex-wrap: wrap;
  line-height: 1.5;
}
.sep { color: #cfd6de; }
.err { color: #b3261e; }

.slide-enter-active, .slide-leave-active { transition: transform 0.2s ease, opacity 0.2s ease; }
.slide-enter-from, .slide-leave-to { transform: translateX(12px); opacity: 0; }
</style>