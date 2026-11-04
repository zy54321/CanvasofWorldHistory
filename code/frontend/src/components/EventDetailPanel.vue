<script setup lang="ts">
/**
 * 事件详情面板（M3）：地图标记与矩阵事件共用同一详情。
 * 只读展示；不含编辑（编辑在「内容管理」里）。
 */
import { ref, watch } from 'vue'
import { fetchEvent } from '../api'
import { formatRange, precisionLabel } from '../time'
import type { EventDetail } from '../types'

const props = defineProps<{ eventId: number; autoLocate?: boolean }>()
const emit = defineEmits<{
  (e: 'close'): void
  (e: 'locate', lon: number, lat: number): void
}>()

const detail = ref<EventDetail | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)
let ctrl: AbortController | null = null

async function load(id: number) {
  ctrl?.abort()
  ctrl = new AbortController()
  loading.value = true
  error.value = null
  detail.value = null
  try {
    const d = await fetchEvent(id, ctrl.signal)
    detail.value = d
    // 有可靠坐标时才定位；无坐标的事件只展示详情，不做错误定位
    const place = d.places.find((p) => p.lon !== null && p.lat !== null)
    if (props.autoLocate !== false && place) {
      emit('locate', place.lon as number, place.lat as number)
    }
  } catch (e) {
    if ((e as Error).name === 'AbortError') return
    error.value = (e as Error).message
  } finally {
    loading.value = false
  }
}

watch(() => props.eventId, load, { immediate: true })

/** 有关键坐标的地点才允许定位；无坐标时按钮不出现，避免"点了没反应" */
function locatable(l: { lon: number | null; lat: number | null }) {
  return l.lon !== null && l.lat !== null
}
</script>

<template>
  <div class="ev panel">
    <div class="ev-head">
      <span class="tag">历史事件</span>
      <button class="x" title="关闭" @click="emit('close')">×</button>
    </div>

    <p v-if="loading" class="tiny dim">读取事件…</p>
    <p v-else-if="error" class="m2-alert">{{ error }}</p>

    <template v-else-if="detail">
      <h2 class="title">{{ detail.title }}</h2>

      <div class="meta">
        <span class="when">
          {{ formatRange(detail.startYearAstro, detail.endYearAstro, detail.timePrecision) }}
        </span>
        <span class="dim tiny">· {{ precisionLabel(detail.timePrecision) }}</span>
        <span v-if="detail.timeOriginalText" class="dim tiny">· 原文「{{ detail.timeOriginalText }}」</span>
      </div>
      <div class="chips">
        <span class="chip">{{ detail.eventType }}</span>
        <span class="chip ghost">{{ detail.recordStatus }}</span>
        <span v-if="detail.startYearAstro === null" class="chip ghost">时间未知 · 不进入时间轴</span>
      </div>

      <p v-if="detail.summary" class="summary">{{ detail.summary }}</p>
      <p v-if="detail.description" class="desc">{{ detail.description }}</p>

      <section>
        <h3>历史政权 <span class="n">{{ detail.polities.length }}</span></h3>
        <ul v-if="detail.polities.length" class="rows">
          <li v-for="p in detail.polities" :key="p.linkId">
            <span class="nm">{{ p.polityName }}</span>
            <span class="dim tiny">{{ p.regionLabel }}</span>
            <span v-if="p.role" class="role">{{ p.role }}</span>
          </li>
        </ul>
        <p v-else class="tiny dim">
          尚未关联历史政权 —— 该事件仍完整保留，只是不进入时空矩阵
        </p>
      </section>

      <section>
        <h3>关联人物 <span class="n">{{ detail.persons.length }}</span></h3>
        <ul v-if="detail.persons.length" class="rows">
          <li v-for="p in detail.persons" :key="p.linkId">
            <span class="nm">{{ p.personName }}</span>
            <span v-if="p.role" class="role">{{ p.role }}</span>
            <span v-if="p.validFromYearAstro !== null || p.validToYearAstro !== null" class="dim tiny">
              {{ formatRange(p.validFromYearAstro, p.validToYearAstro) }}
            </span>
          </li>
        </ul>
        <p v-else class="tiny dim">未关联人物</p>
      </section>

      <section>
        <h3>关联地点 <span class="n">{{ detail.places.length }}</span></h3>
        <ul v-if="detail.places.length" class="rows">
          <li v-for="l in detail.places" :key="l.linkId">
            <span class="nm">{{ l.placeName }}</span>
            <span v-if="l.locationRole" class="role">{{ l.locationRole }}</span>
            <button v-if="locatable(l)" class="mini" @click="emit('locate', l.lon as number, l.lat as number)">
              定位
            </button>
            <span v-else class="dim tiny">无坐标</span>
          </li>
        </ul>
        <p v-else class="tiny dim">未关联地点</p>
      </section>

      <p v-if="detail.timeNote" class="tiny dim note">时间说明：{{ detail.timeNote }}</p>
      <p class="tiny dim foot">
        来源：人工录入条目（{{ detail.createdBy }}）· 事件 #{{ detail.eventId }}
        <template v-if="detail.places.some((x) => x.lon !== null)">
          · 地图位置取自关联地点的代表坐标
        </template>
      </p>
      <p v-if="detail.truncated" class="tiny dim">关联过多，仅显示前 500 条</p>
    </template>
  </div>
</template>

<style scoped>
.ev {
  width: 340px;
  max-height: calc(100vh - 92px);
  overflow-y: auto;
  padding: 12px 14px 14px;
}
.ev-head { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.tag {
  font-size: 10.5px;
  letter-spacing: 0.04em;
  color: var(--accent);
  background: var(--accent-soft);
  border-radius: 4px;
  padding: 2px 6px;
}
.x {
  margin-left: auto;
  border: none;
  background: transparent;
  font-size: 18px;
  line-height: 1;
  color: var(--ink-3);
  padding: 0 4px;
}
.x:hover { background: transparent; color: var(--ink); }

.title { font-size: 17px; margin: 2px 0 6px; line-height: 1.35; }
.meta { font-size: 12.5px; color: var(--ink-2); display: flex; flex-wrap: wrap; gap: 4px; }
.when { font-weight: 600; }
.chips { display: flex; flex-wrap: wrap; gap: 5px; margin: 8px 0 4px; }
.chip {
  font-size: 11px;
  padding: 1.5px 7px;
  border-radius: 999px;
  background: #eef3fa;
  color: #2b4a72;
}
.chip.ghost { background: #f2f3f5; color: var(--ink-3); }
.summary { font-size: 13px; margin: 8px 0 2px; color: var(--ink); }
.desc { font-size: 12.5px; color: var(--ink-2); line-height: 1.6; margin: 4px 0 0; }

section { margin-top: 12px; border-top: 1px dashed var(--line); padding-top: 8px; }
h3 { font-size: 12px; margin: 0 0 5px; color: var(--ink-2); display: flex; gap: 6px; align-items: baseline; }
h3 .n { font-size: 11px; color: var(--ink-3); font-weight: 400; }
.rows { list-style: none; margin: 0; padding: 0; }
.rows li {
  display: flex;
  align-items: baseline;
  gap: 7px;
  padding: 3px 0;
  font-size: 12.5px;
}
.nm { color: var(--ink); }
.role {
  font-size: 10.5px;
  color: #6b5a3a;
  background: #f6efe3;
  border-radius: 4px;
  padding: 1px 5px;
}
.mini {
  margin-left: auto;
  font-size: 11px;
  padding: 1px 7px;
  border-radius: 5px;
}
.note { margin-top: 10px; }
.foot { margin-top: 10px; line-height: 1.5; }
</style>
