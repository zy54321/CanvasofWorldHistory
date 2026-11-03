<script setup lang="ts">
/**
 * 对象选择器：搜索并选择已有地点 / 人物 / 事件。
 * 关联关系一律走这个选择器，不允许手填 ID。
 */
import { onBeforeUnmount, ref, watch } from 'vue'
import { eventApi, personApi, placeAdmin } from '../../api'

export interface PickedItem {
  id: number
  name: string
  sub?: string
}

const props = defineProps<{
  open: boolean
  kind: 'place' | 'person' | 'event'
  title: string
  /** 已关联的对象 id，用于标灰避免重复选 */
  excludeIds?: number[]
}>()
const emit = defineEmits<{
  (e: 'close'): void
  (e: 'pick', item: PickedItem): void
}>()

const keyword = ref('')
const items = ref<PickedItem[]>([])
const loading = ref(false)
const error = ref<string | null>(null)
let ctrl: AbortController | null = null

const used = () => new Set(props.excludeIds ?? [])

async function load() {
  ctrl?.abort()
  ctrl = new AbortController()
  loading.value = true
  error.value = null
  try {
    if (props.kind === 'place') {
      const r = await placeAdmin.list(keyword.value, 1, 20, ctrl.signal)
      items.value = r.items.map((x) => ({
        id: x.placeId,
        name: x.canonicalName,
        sub: [x.placeType, x.hasGeom && x.lon !== null ? `${x.lon.toFixed(2)}, ${x.lat?.toFixed(2)}` : '无坐标']
          .filter(Boolean)
          .join(' · '),
      }))
    } else if (props.kind === 'person') {
      const r = await personApi.list(keyword.value, 1, 20, ctrl.signal)
      items.value = r.items.map((x) => ({
        id: x.personId,
        name: x.canonicalName,
        sub: [x.birthYearAstro !== null || x.deathYearAstro !== null ? '生卒已录' : '生卒未知',
              `${x.nameCount} 名`].join(' · '),
      }))
    } else {
      const r = await eventApi.list(keyword.value, 1, 20, ctrl.signal)
      items.value = r.items.map((x) => ({
        id: x.eventId,
        name: x.title,
        sub: [x.eventType, x.timePrecision === 'unknown' ? '时间未知' : '有时间'].join(' · '),
      }))
    }
  } catch (e) {
    if ((e as Error).name === 'AbortError') return
    error.value = (e as Error).message
    items.value = []
  } finally {
    loading.value = false
  }
}

watch(
  () => [props.open, props.kind],
  ([o]) => {
    if (o) {
      keyword.value = ''
      load()
    }
  },
)

onBeforeUnmount(() => ctrl?.abort())

function pick(it: PickedItem) {
  if (used().has(it.id)) return
  emit('pick', it)
}
</script>

<template>
  <div v-if="open" class="mask" @click.self="emit('close')">
    <section class="picker panel">
      <header>
        <strong>{{ title }}</strong>
        <button class="x" @click="emit('close')">✕</button>
      </header>
      <div class="search">
        <input
          v-model="keyword"
          type="text"
          :placeholder="
            kind === 'place' ? '搜索地点名称或别名（留空列出全部）' : kind === 'person' ? '搜索人物姓名或别名' : '搜索事件标题'
          "
          @keyup.enter="load"
        />
        <button @click="load">搜索</button>
      </div>

      <div class="list scroll">
        <p v-if="loading" class="tiny dim pad">查询中…</p>
        <p v-else-if="error" class="tiny err pad">{{ error }}</p>
        <p v-else-if="items.length === 0" class="tiny dim pad">
          没有匹配结果。{{ kind === 'place' ? '可先在「地点」页签新建。' : '' }}
        </p>
        <button
          v-for="it in items"
          :key="it.id"
          class="item"
          :class="{ used: used().has(it.id) }"
          :disabled="used().has(it.id)"
          @click="pick(it)"
        >
          <span class="nm">{{ it.name }}</span>
          <span class="sub tiny dim">{{ it.sub }}</span>
          <span v-if="used().has(it.id)" class="tiny dim">已关联</span>
          <span v-else class="mono tiny dim">#{{ it.id }}</span>
        </button>
      </div>
    </section>
  </div>
</template>

<style scoped>
.mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 26, 42, 0.28);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 60;
}
.picker { width: 520px; max-height: 70vh; display: flex; flex-direction: column; overflow: hidden; }
header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 11px 14px;
  border-bottom: 1px solid var(--line);
  font-size: 13px;
}
.x { border: none; background: transparent; color: var(--ink-3); }
.search { display: flex; gap: 6px; padding: 10px 14px; }
.search input {
  flex: 1;
  font: inherit;
  font-size: 13px;
  padding: 7px 9px;
  border: 1px solid var(--line);
  border-radius: 7px;
}
.list { flex: 1; min-height: 120px; }
.pad { padding: 16px 14px; margin: 0; }
.err { color: #b3261e; }
.item {
  display: flex;
  align-items: baseline;
  gap: 8px;
  width: 100%;
  text-align: left;
  border: none;
  border-bottom: 1px solid #f1f4f7;
  border-radius: 0;
  background: #fff;
  padding: 9px 14px;
}
.item:hover:not(:disabled) { background: #f7f9fb; }
.item.used { opacity: 0.45; }
.nm { font-size: 13.5px; font-weight: 600; }
.sub { flex: 1; }
.mono { font-size: 10.5px; }
</style>
