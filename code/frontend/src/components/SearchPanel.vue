<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { searchPlaces } from '../api'
import type { PlaceSummary, SearchResult } from '../types'

const emit = defineEmits<{
  (e: 'pick', item: PlaceSummary): void
  (e: 'hover', item: PlaceSummary | null): void
}>()

const keyword = ref('')
const yearInput = ref<string>('')
const page = ref(1)
const size = 20

const result = ref<SearchResult | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)
const activeId = ref<number | null>(null)

let ctrl: AbortController | null = null

const yearValue = computed<number | null>(() => {
  const raw = yearInput.value.trim()
  if (!raw) return null
  if (!/^-?\d+$/.test(raw)) return null
  return Number(raw)
})
const yearInvalid = computed(
  () => yearInput.value.trim().length > 0 && yearValue.value === null,
)

const totalText = computed(() => {
  if (!result.value) return ''
  return `${result.value.total.toLocaleString()} 条`
})

const emptyHint = computed(() => {
  if (loading.value || !result.value) return ''
  if (result.value.total === 0) {
    return yearValue.value !== null
      ? '该关键词在此年代无有效名称，可清空年代限制再试'
      : '无匹配地点'
  }
  return ''
})

async function run(resetPage = false) {
  if (resetPage) page.value = 1
  if (yearInvalid.value) {
    error.value = '年代需为整数（公元前用负数，如 -200）'
    return
  }
  ctrl?.abort()
  ctrl = new AbortController()
  loading.value = true
  error.value = null
  try {
    result.value = await searchPlaces(
      {
        keyword: keyword.value.trim() || undefined,
        year: yearValue.value,
        page: page.value,
        size,
      },
      ctrl.signal,
    )
  } catch (e) {
    if ((e as Error).name === 'AbortError') return
    error.value = (e as Error).message
    result.value = null
  } finally {
    loading.value = false
  }
}

function pick(item: PlaceSummary) {
  activeId.value = item.placeId
  emit('pick', item)
}

function goto(delta: number) {
  if (!result.value) return
  const next = page.value + delta
  if (next < 1 || next > result.value.totalPages) return
  page.value = next
  run()
}

function onEnter() {
  run(true)
}

function fmtYear(y: number | null): string {
  if (y === null) return '—'
  // 天文纪年：内部为整数，1 BCE = 0，2 BCE = -1；界面显示公元 1 年之前不出现 0 年
  return y <= 0 ? `前 ${1 - y} ` : `${y} `
}

function yearRange(item: PlaceSummary): string {
  if (!item.timeKnown) return '纪年未知'
  return `${fmtYear(item.validFromYear)}– ${fmtYear(item.validToYear)}`
}

const typeLabel: Record<string, string> = {
  admin_center_province: '省级治所',
  admin_center_prefecture: '府级治所',
  admin_center_county: '县级治所',
}

function typeText(t: string | null): string {
  if (!t) return '类型未定'
  return typeLabel[t] ?? t
}

watch(
  () => [keyword.value, yearInput.value],
  () => {
    if (keyword.value.trim() === '' && yearInput.value.trim() === '') {
      result.value = null
      page.value = 1
    }
  },
)

onBeforeUnmount(() => ctrl?.abort())
</script>

<template>
  <section class="search panel">
    <header>
      <h1>地点检索</h1>
      <p class="tiny dim">按名称、别名或年代查找</p>
    </header>

    <div class="controls">
      <div class="row">
        <input
          v-model="keyword"
          type="text"
          placeholder="搜索历史地名、别名（如 桂林 / 长安）"
          @keyup.enter="onEnter"
        />
        <button class="primary" :disabled="loading" @click="onEnter">
          {{ loading ? '…' : '搜索' }}
        </button>
      </div>
      <div class="row">
        <input
          v-model="yearInput"
          type="text"
          inputmode="numeric"
          placeholder="年代（可空，公元前用负数，如 -200）"
          :class="{ invalid: yearInvalid }"
          @keyup.enter="onEnter"
        />
        <button v-if="yearInput || keyword" class="ghost" @click="((keyword = ''), (yearInput = ''), (result = null))">
          清空
        </button>
      </div>
      <p v-if="yearInvalid" class="tiny err">年代必须是整数，公元前用负数</p>
    </div>

    <div class="result-head tiny">
      <span v-if="error" class="err">查询失败：{{ error }}</span>
      <span v-else-if="result">
        共 <strong>{{ totalText }}</strong>
        <span class="dim">· 第 {{ result.page }} / {{ result.totalPages }} 页</span>
      </span>
      <span v-else class="dim">输入关键词开始检索</span>
    </div>

    <div class="list scroll">
      <p v-if="emptyHint" class="empty tiny dim">{{ emptyHint }}</p>
      <article
        v-for="item in result?.items ?? []"
        :key="item.placeId"
        class="item"
        :class="{ active: activeId === item.placeId }"
        @click="pick(item)"
        @mouseenter="emit('hover', item)"
        @mouseleave="emit('hover', null)"
      >
        <div class="line1">
          <span class="nm" :class="{ unnamed: !item.displayName }">
            {{ item.displayName ?? `未命名地点 · #${item.placeId}` }}
          </span>
          <span v-if="item.matchedNameType && item.matchedNameType !== 'primary'" class="badge">
            {{ item.matchedNameType === 'alternate' ? '别名' : item.matchedNameType === 'transliteration' ? '转写' : item.matchedNameType }}
          </span>
          <span class="id mono tiny dim">#{{ item.placeId }}</span>
        </div>
        <div class="line2 tiny">
          <span
            v-if="item.matchedName !== item.canonicalName && item.matchedName !== item.displayName"
            class="dim"
          >
            正名 {{ item.canonicalName }} · 匹配 {{ item.matchedName }} ·
          </span>
          <span class="dim">{{ typeText(item.placeType) }}</span>
          <span class="dim"> · {{ yearRange(item) }}</span>
        </div>
        <div class="line3 tiny dim">
          <!-- M4-4c：接口用 non_null 序列化，无代表坐标的地点**不带**这两个字段，
               取到的是 undefined 而不是 null。原来的 `!== null` 判断放过了 undefined，
               下面再调 .toFixed() 就会抛 "Cannot read properties of undefined"，
               整个搜索结果列表随之渲染失败（Pleiades 4.1 有 7,200 个这样的地点）。
               改成 `!= null` 同时挡住 null 与 undefined，走下面的“无代表坐标”分支。 -->
          <span v-if="item.lon != null && item.lat != null" class="mono">
            {{ item.lon.toFixed(3) }}, {{ item.lat.toFixed(3) }}
          </span>
          <span v-else>无代表坐标</span>
          <span v-if="item.locationPrecision"> · 精度 {{ item.locationPrecision }}</span>
        </div>
      </article>
    </div>

    <footer v-if="result && result.totalPages > 1" class="pager">
      <button :disabled="page <= 1 || loading" @click="goto(-1)">上一页</button>
      <span class="tiny dim">{{ page }} / {{ result.totalPages }}</span>
      <button :disabled="page >= result.totalPages || loading" @click="goto(1)">下一页</button>
    </footer>
  </section>
</template>

<style scoped>
.search {
  display: flex;
  flex-direction: column;
  width: 344px;
  max-height: calc(100vh - 96px);
  overflow: hidden;
}
header { padding: 13px 15px 8px; }
h1 {
  margin: 0;
  font-size: 16px;
  font-weight: 650;
  letter-spacing: 0.02em;
}
header p { margin: 3px 0 0; }

.controls { padding: 4px 15px 8px; display: flex; flex-direction: column; gap: 7px; }
.row { display: flex; gap: 6px; }
.row input { flex: 1; min-width: 0; }
button.primary { background: var(--accent); border-color: var(--accent); color: #fff; padding: 6px 14px; }
button.primary:hover { background: #7a4d23; }
button.ghost { padding: 6px 10px; color: var(--ink-2); }
.invalid { border-color: #b3261e; }

.result-head {
  padding: 6px 15px;
  border-top: 1px solid var(--line);
  border-bottom: 1px solid var(--line);
  background: rgba(246, 247, 249, 0.75);
}
.err { color: #b3261e; }

.list { flex: 1; min-height: 120px; }
.empty { padding: 18px 15px; margin: 0; }

.item {
  padding: 9px 15px;
  border-bottom: 1px solid #eef1f5;
  cursor: pointer;
}
.item:hover { background: #f7f9fb; }
.item.active { background: var(--accent-soft); box-shadow: inset 3px 0 0 var(--accent); }

.line1 { display: flex; align-items: baseline; gap: 6px; }
.nm { font-size: 14px; font-weight: 600; }
.badge {
  font-size: 10px;
  padding: 1px 5px;
  border-radius: 4px;
  background: var(--accent-soft);
  color: var(--accent);
  border: 1px solid #e4d0b6;
}
.id { margin-left: auto; }
.line2, .line3 { margin-top: 2px; line-height: 1.5; }
.line3 .mono { font-size: 10.5px; }

.pager {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 8px 15px;
  border-top: 1px solid var(--line);
}
.nm.unnamed { color: var(--ink-3); font-style: italic; font-weight: 500; }
</style>