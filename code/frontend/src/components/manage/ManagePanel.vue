<script setup lang="ts">
/**
 * M2 管理面板：地点 / 人物 / 事件 三个页签，左侧列表 + 右侧编辑器。
 * 地图本体仍由 MapView 负责，这里只发「定位」事件让地图飞过去。
 */
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import PlaceEditor from './PlaceEditor.vue'
import PersonEditor from './PersonEditor.vue'
import EventEditor from './EventEditor.vue'
import { eventApi, personApi, placeAdmin } from '../../api'
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

const tab = ref<Tab>('place')
const keyword = ref('')
const page = ref(1)
const list = ref<{ id: number; name: string; sub: string }[]>([])
const total = ref(0)
const totalPages = ref(1)
const loading = ref(false)
const err = ref<string | null>(null)
const selectedId = ref<number | null>(null)
const creating = ref(false)

let ctrl: AbortController | null = null

async function load() {
  ctrl?.abort()
  ctrl = new AbortController()
  loading.value = true
  err.value = null
  try {
    if (tab.value === 'place') {
      const r = await placeAdmin.list(keyword.value, page.value, 20, ctrl.signal)
      list.value = r.items.map((x) => ({
        id: x.placeId,
        name: x.canonicalName,
        sub: [
          x.placeType ?? '类型未定',
          x.hasGeom && x.lon !== null ? '有坐标' : '无坐标',
          `${x.nameCount} 名`,
        ].join(' · '),
      }))
      total.value = r.total
      totalPages.value = r.totalPages
    } else if (tab.value === 'person') {
      const r = await personApi.list(keyword.value, page.value, 20, ctrl.signal)
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
      totalPages.value = r.totalPages
    } else {
      const r = await eventApi.list(keyword.value, page.value, 20, ctrl.signal)
      list.value = r.items.map((x) => ({
        id: x.eventId,
        name: x.title,
        sub: [
          formatRange(x.startYearAstro, x.endYearAstro, x.timePrecision),
          `${x.personCount} 人 · ${x.placeCount} 地`,
        ].join(' · '),
      }))
      total.value = r.total
      totalPages.value = r.totalPages
    }
  } catch (e) {
    if ((e as Error).name === 'AbortError') return
    err.value = (e as Error).message
    list.value = []
  } finally {
    loading.value = false
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
  page.value = 1
  selectedId.value = null
  creating.value = false
}

function search() {
  page.value = 1
  load()
}

function goto(delta: number) {
  const next = page.value + delta
  if (next < 1 || next > totalPages.value) return
  page.value = next
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
            <button class="m2-btn" @click="search">搜索</button>
          </div>
          <button class="m2-btn primary new" @click="startCreate">
            + 新建{{ tab === 'place' ? '地点' : tab === 'person' ? '人物' : '事件' }}
          </button>

          <div class="items scroll">
            <p v-if="loading" class="m2-empty">加载中…</p>
            <p v-else-if="err" class="m2-alert">{{ err }}</p>
            <p v-else-if="list.length === 0" class="m2-empty">
              暂无数据{{ keyword ? '（换个关键词试试）' : '' }}
            </p>
            <button
              v-for="it in list"
              :key="it.id"
              class="item"
              :class="{ active: !creating && selectedId === it.id }"
              @click="pick(it.id)"
            >
              <span class="nm">{{ it.name }}</span>
              <span class="sub tiny dim">{{ it.sub }}</span>
            </button>
          </div>

          <footer v-if="totalPages > 1" class="pager">
            <button class="m2-btn sm" :disabled="page <= 1" @click="goto(-1)">上一页</button>
            <span class="tiny dim">{{ page }} / {{ totalPages }}</span>
            <button class="m2-btn sm" :disabled="page >= totalPages" @click="goto(1)">下一页</button>
          </footer>
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
  flex: 0 0 322px;
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
.new { margin: 2px 12px 8px; }
.items { flex: 1; min-height: 80px; }
.item {
  display: flex;
  flex-direction: column;
  gap: 1px;
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
.pager {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  padding: 7px 12px;
  border-top: 1px solid var(--line);
}
.main { flex: 1; min-width: 0; padding: 12px 14px; overflow: hidden; }
.center { text-align: center; padding-top: 80px; }
</style>
