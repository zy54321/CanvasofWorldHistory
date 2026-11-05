<script setup lang="ts">
/**
 * M2 管理面板：地点 / 人物 / 事件 三个页签，左侧列表 + 右侧编辑器。
 * 地图本体仍由 MapView 负责，这里只发「定位」事件让地图飞过去。
 *
 * V1.0 内容管理专项（只在地点页签生效）：
 *  · 两层筛选：几何类型 × 名称质量，AND 组合；任一变化回到第 1 页。
 *  · 列表逐条显示展示名、名称质量、点/线/面数量、位置总数、名称数、数据集。
 *  · 分页支持直接跳页（校验范围），翻页保留筛选。
 *  · 请求进行中禁用所有翻页/跳页控件，并丢弃过期响应（防止慢请求覆盖新结果）。
 */
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import PlaceEditor from './PlaceEditor.vue'
import PersonEditor from './PersonEditor.vue'
import EventEditor from './EventEditor.vue'
import { eventApi, personApi, placeAdmin } from '../../api'
import type { PlaceAdminFilter } from '../../api'
import { formatRange, formatYear } from '../../time'

const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{
  (e: 'close'): void
  (e: 'locate', lon: number, lat: number): void
}>()

type Tab = 'place' | 'person' | 'event'
const TABS: { v: Tab; t: string }[] = [
  { v: 'place', t: '地点' },
  { v: 'person', t: '人物' },
  { v: 'event', t: '事件' },
]

const GEOM_OPTIONS: { v: NonNullable<PlaceAdminFilter['geomType']>; t: string }[] = [
  { v: 'all', t: '全部几何' },
  { v: 'point', t: '有点' },
  { v: 'line', t: '有线' },
  { v: 'polygon', t: '有面' },
  { v: 'none', t: '无几何' },
]

const QUALITY_OPTIONS: { v: NonNullable<PlaceAdminFilter['nameQuality']>; t: string }[] = [
  { v: 'all', t: '全部名称' },
  { v: 'valid', t: '有效名称' },
  { v: 'alias_only', t: '仅别名有效' },
  { v: 'placeholder', t: '占位无名' },
  { v: 'no_name', t: '完全无名称' },
]

const QUALITY_LABEL: Record<string, string> = {
  valid: '有效名称',
  alias_only: '仅别名有效',
  placeholder: '占位无名',
  no_name: '完全无名称',
}

const tab = ref<Tab>('place')
const keyword = ref('')
const geomType = ref<NonNullable<PlaceAdminFilter['geomType']>>('all')
const nameQuality = ref<NonNullable<PlaceAdminFilter['nameQuality']>>('all')
const page = ref(1)
const pageSize = 20
const list = ref<{ id: number; name: string; sub: string; tag?: string; noName?: boolean }[]>([])
const total = ref(0)
const totalPages = ref(1)
const loading = ref(false)
const err = ref<string | null>(null)
const selectedId = ref<number | null>(null)
const creating = ref(false)
const jumpTo = ref('')

let ctrl: AbortController | null = null
/** 请求序号：只有最后一次请求的响应才允许写回列表 */
let seq = 0

function placeSub(x: {
  nameCount: number
  locationCount: number
  geomLocationCount: number
  pointCount: number
  lineCount: number
  polygonCount: number
  datasetName: string | null
  datasetId: string
}): string {
  const parts: string[] = []
  if (x.geomLocationCount === 0) {
    parts.push('无几何')
  } else {
    const g: string[] = []
    if (x.pointCount) g.push(`点 ${x.pointCount}`)
    if (x.lineCount) g.push(`线 ${x.lineCount}`)
    if (x.polygonCount) g.push(`面 ${x.polygonCount}`)
    parts.push(g.join(' / '))
  }
  parts.push(`位置 ${x.locationCount}`, `名称 ${x.nameCount}`)
  parts.push(x.datasetName || x.datasetId)
  return parts.join(' · ')
}

async function load() {
  ctrl?.abort()
  ctrl = new AbortController()
  const my = ++seq
  loading.value = true
  err.value = null
  try {
    if (tab.value === 'place') {
      const r = await placeAdmin.list(
        { keyword: keyword.value, geomType: geomType.value, nameQuality: nameQuality.value },
        page.value,
        pageSize,
        ctrl.signal,
      )
      if (my !== seq) return // 过期响应：直接丢弃，不覆盖新结果
      list.value = r.items.map((x) => ({
        id: x.placeId,
        name: x.displayName ?? `未命名地点 · #${x.placeId}`,
        noName: !x.displayName,
        tag: QUALITY_LABEL[x.nameQuality] ?? x.nameQuality,
        sub: placeSub(x),
      }))
      total.value = r.total
      totalPages.value = Math.max(1, r.totalPages)
    } else if (tab.value === 'person') {
      const r = await personApi.list(keyword.value, page.value, 20, ctrl.signal)
      if (my !== seq) return
      list.value = r.items.map((x) => ({
        id: x.personId,
        name: x.canonicalName,
        sub: [
          x.birthYearAstro === null && x.deathYearAstro === null
            ? '生卒未知'
            : `${formatYear(x.birthYearAstro)} – ${formatYear(x.deathYearAstro)}`,
          `${x.eventCount} 事件 · ${x.placeCount} 地点`,
        ].join(' · '),
      }))
      total.value = r.total
      totalPages.value = Math.max(1, r.totalPages)
    } else {
      const r = await eventApi.list(keyword.value, page.value, 20, ctrl.signal)
      if (my !== seq) return
      list.value = r.items.map((x) => ({
        id: x.eventId,
        name: x.title,
        sub: [
          formatRange(x.startYearAstro, x.endYearAstro, x.timePrecision),
          `${x.personCount} 人 · ${x.placeCount} 地`,
        ].join(' · '),
      }))
      total.value = r.total
      totalPages.value = Math.max(1, r.totalPages)
    }
  } catch (e) {
    if ((e as Error).name === 'AbortError') return
    if (my !== seq) return
    err.value = (e as Error).message
    list.value = []
  } finally {
    if (my === seq) loading.value = false
  }
}

watch(
  () => [props.open, tab.value],
  ([o]) => {
    if (o) {
      page.value = 1
      selectedId.value = null
      creating.value = false
      load()
    }
  },
  { immediate: true },
)

function switchTab(t: Tab) {
  tab.value = t
  keyword.value = ''
  geomType.value = 'all'
  nameQuality.value = 'all'
  page.value = 1
  jumpTo.value = ''
  selectedId.value = null
  creating.value = false
}

/** 任何筛选变化都必须回到第 1 页，否则会停在超出范围的页码上 */
function applyFilter() {
  page.value = 1
  jumpTo.value = ''
  load()
}

function search() {
  applyFilter()
}

function goto(delta: number) {
  if (loading.value) return
  const next = page.value + delta
  if (next < 1 || next > totalPages.value) return
  page.value = next
  jumpTo.value = ''
  load()
}

/** 直接跳页：非法输入给出提示且不发请求，合法则夹在 [1, totalPages] 内 */
function jump() {
  if (loading.value) return
  const raw = jumpTo.value.trim()
  if (!raw) return
  if (!/^\d+$/.test(raw)) {
    err.value = '页码必须是正整数'
    return
  }
  const n = Number(raw)
  if (n < 1 || n > totalPages.value) {
    err.value = `页码超出范围（1 – ${totalPages.value}）`
    return
  }
  err.value = null
  page.value = n
  jumpTo.value = ''
  load()
}

function pick(id: number) {
  creating.value = false
  selectedId.value = id
}

function startCreate() {
  selectedId.value = null
  creating.value = true
}

function onSaved(id: number) {
  creating.value = false
  selectedId.value = id
  load()
}

function onDeleted() {
  selectedId.value = null
  creating.value = false
  load()
}

const editorKey = computed(() =>
  creating.value ? `new-${tab.value}` : `${tab.value}-${selectedId.value ?? 'none'}`,
)

onBeforeUnmount(() => ctrl?.abort())
</script>

<template>
  <div v-if="open" class="manage-mask">
    <section class="manage panel">
      <header class="hd">
        <strong>内容管理</strong>
        <nav class="tabs">
          <button
            v-for="t in TABS"
            :key="t.v"
            :class="{ active: tab === t.v }"
            @click="switchTab(t.v)"
          >
            {{ t.t }}
          </button>
        </nav>
        <span class="grow" />
        <span class="tiny dim">共 {{ total }} 条</span>
        <button class="x" title="关闭" @click="emit('close')">✕</button>
      </header>

      <div class="body">
        <!-- 左：列表 -->
        <aside class="side">
          <div class="search">
            <input
              v-model="keyword"
              type="text"
              :placeholder="
                tab === 'place'
                  ? '搜索地点名称/别名'
                  : tab === 'person'
                    ? '搜索人物姓名/别名'
                    : '搜索事件标题/摘要'
              "
              @keyup.enter="search"
            />
            <button class="m2-btn" :disabled="loading" @click="search">搜索</button>
          </div>

          <!-- 两层筛选：几何类型 × 名称质量（AND）。只对地点页签生效。 -->
          <div v-if="tab === 'place'" class="filters">
            <label>
              <span class="tiny dim">几何</span>
              <select v-model="geomType" :disabled="loading" @change="applyFilter">
                <option v-for="g in GEOM_OPTIONS" :key="g.v" :value="g.v">{{ g.t }}</option>
              </select>
            </label>
            <label>
              <span class="tiny dim">名称</span>
              <select v-model="nameQuality" :disabled="loading" @change="applyFilter">
                <option v-for="q in QUALITY_OPTIONS" :key="q.v" :value="q.v">{{ q.t }}</option>
              </select>
            </label>
          </div>

          <button class="m2-btn primary new" @click="startCreate">
            + 新建{{ tab === 'place' ? '地点' : tab === 'person' ? '人物' : '事件' }}
          </button>

          <div class="items scroll" :class="{ busy: loading }">
            <p v-if="loading && list.length === 0" class="m2-empty">加载中…</p>
            <p v-else-if="err" class="m2-alert">{{ err }}</p>
            <p v-else-if="list.length === 0" class="m2-empty">
              暂无数据{{
                keyword || geomType !== 'all' || nameQuality !== 'all' ? '（换个条件试试）' : ''
              }}
            </p>
            <button
              v-for="it in list"
              :key="it.id"
              class="item"
              :class="{ active: !creating && selectedId === it.id }"
              @click="pick(it.id)"
            >
              <span class="nm" :class="{ unnamed: it.noName }">{{ it.name }}</span>
              <span v-if="it.tag" class="tag" :class="'q-' + (it.noName ? 'none' : 'ok')">
                {{ it.tag }}
              </span>
              <span class="sub tiny dim">{{ it.sub }}</span>
            </button>
          </div>

          <footer v-if="totalPages > 1 || loading" class="pager">
            <button class="m2-btn sm" :disabled="loading || page <= 1" @click="goto(-1)">上一页</button>
            <span class="tiny dim">{{ page }} / {{ totalPages }}</span>
            <button
              class="m2-btn sm"
              :disabled="loading || page >= totalPages"
              @click="goto(1)"
            >
              下一页
            </button>
            <span class="jump">
              <input
                v-model="jumpTo"
                type="text"
                inputmode="numeric"
                placeholder="页码"
                :disabled="loading"
                @keyup.enter="jump"
              />
              <button class="m2-btn sm" :disabled="loading" @click="jump">跳转</button>
            </span>
          </footer>
          <p v-if="loading" class="loading-hint tiny dim">正在加载第 {{ page }} 页…</p>
        </aside>

        <!-- 右：编辑器 -->
        <main class="main">
          <p v-if="!creating && selectedId === null" class="m2-empty center">
            从左侧选择一条记录，或点击「新建」。
          </p>
          <PlaceEditor
            v-else-if="tab === 'place'"
            :key="editorKey"
            :entity-id="creating ? null : selectedId"
            @saved="onSaved"
            @deleted="onDeleted"
            @changed="load"
            @locate="(lon: number, lat: number) => emit('locate', lon, lat)"
          />
          <PersonEditor
            v-else-if="tab === 'person'"
            :key="editorKey"
            :entity-id="creating ? null : selectedId"
            @saved="onSaved"
            @deleted="onDeleted"
            @changed="load"
            @locate="(lon: number, lat: number) => emit('locate', lon, lat)"
          />
          <EventEditor
            v-else
            :key="editorKey"
            :entity-id="creating ? null : selectedId"
            @saved="onSaved"
            @deleted="onDeleted"
            @changed="load"
            @locate="(lon: number, lat: number) => emit('locate', lon, lat)"
          />
        </main>
      </div>
    </section>
  </div>
</template>

<style scoped>
.manage-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 26, 42, 0.30);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 50;
}
.manage {
  width: min(1120px, 94vw);
  height: min(760px, 90vh);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.hd {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  border-bottom: 1px solid var(--line);
}
.hd strong { font-size: 14px; }
.tabs { display: flex; gap: 4px; }
.tabs button {
  border: none;
  border-bottom: 2px solid transparent;
  border-radius: 0;
  background: transparent;
  padding: 5px 10px;
  font-size: 12.5px;
  color: var(--ink-2);
}
.tabs button.active { color: var(--accent); border-bottom-color: var(--accent); font-weight: 600; }
.grow { flex: 1; }
.x { border: none; background: transparent; color: var(--ink-3); font-size: 14px; }

.body { flex: 1; display: flex; min-height: 0; }
.side {
  flex: 0 0 352px;
  border-right: 1px solid var(--line);
  display: flex;
  flex-direction: column;
  min-height: 0;
}
.search { display: flex; gap: 6px; padding: 10px 12px 6px; }
.search input {
  flex: 1;
  font: inherit;
  font-size: 12.5px;
  padding: 6px 8px;
  border: 1px solid var(--line);
  border-radius: 7px;
}
.filters { display: flex; gap: 8px; padding: 0 12px 6px; }
.filters label { display: flex; align-items: center; gap: 4px; flex: 1; }
.filters select {
  flex: 1;
  font: inherit;
  font-size: 12px;
  padding: 4px 5px;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: #fff;
}
.new { margin: 2px 12px 8px; }
.items { flex: 1; min-height: 80px; }
.items.busy { opacity: 0.55; }
.item {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 6px;
  width: 100%;
  text-align: left;
  border: none;
  border-bottom: 1px solid #f1f4f7;
  border-radius: 0;
  background: #fff;
  padding: 8px 12px;
}
.item:hover { background: #f7f9fb; }
.item.active { background: var(--accent-soft); box-shadow: inset 3px 0 0 var(--accent); }
.nm { font-size: 13px; font-weight: 600; }
.nm.unnamed { font-weight: 500; color: var(--ink-3); font-style: italic; }
.tag {
  font-size: 10.5px;
  line-height: 1.5;
  padding: 0 5px;
  border-radius: 999px;
  border: 1px solid var(--line);
  color: var(--ink-3);
  background: #fafbfc;
}
.tag.q-none { color: #8a6d3b; border-color: #e6d3ae; background: #fdf7ea; }
.sub { width: 100%; }
.pager {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  padding: 7px 12px;
  border-top: 1px solid var(--line);
  flex-wrap: wrap;
}
.jump { display: flex; align-items: center; gap: 4px; }
.jump input {
  width: 52px;
  font: inherit;
  font-size: 12px;
  padding: 3px 5px;
  border: 1px solid var(--line);
  border-radius: 6px;
  text-align: center;
}
.loading-hint { padding: 0 12px 6px; }
.main { flex: 1; min-width: 0; padding: 12px 14px; overflow: hidden; }
.center { text-align: center; padding-top: 80px; }
</style>
