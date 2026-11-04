<script setup lang="ts">
/**
 * 历史时空矩阵（M3 展开态）。
 *
 * 结构：顶部时间刻度 + 10 个地区折叠面板 → 展开后是「政权 × 时间段」矩阵。
 *
 * 关键实现：**刻度与矩阵内容在同一个横向滚动容器里**（一个 scroller，不是两个容器互相同步），
 * 所以刻度列与事件列永远对齐；左侧「地区 / 政权」列用 position: sticky 常驻可见，
 * 表头用 sticky top 常驻可见。纵向只在矩阵内部滚动，页面本身不滚动。
 */
import { computed, nextTick, ref, watch } from 'vue'
import { fetchMatrix } from '../api'
import { formatRange } from '../time'
import type { MatrixColumn, MatrixEvent, MatrixPolity, MatrixRegion } from '../types'

const props = defineProps<{
  open: boolean
  from: number
  step: number
  eventCount: number | null
}>()
const emit = defineEmits<{
  (e: 'close'): void
  (e: 'select-window', from: number, to: number): void
  (e: 'event-select', eventId: number): void
}>()

const MAX_COLUMNS = 72
const LEFT_W = 190

const anchor = ref(props.from)
const columns = ref<MatrixColumn[]>([])
const regions = ref<MatrixRegion[]>([])
const expanded = ref<Set<string>>(new Set())
const selected = ref<number>(0)
const loading = ref(false)
const loadingMore = ref(false)
const error = ref<string | null>(null)
const note = ref('')
const unlinked = ref(0)
const truncated = ref(false)
const scrollEl = ref<HTMLDivElement | null>(null)
let ctrl: AbortController | null = null

const colW = computed(() => (props.step >= 100 ? 108 : props.step >= 10 ? 98 : 76))

/** 一页至少铺满视口再多 6 列，否则内容不足一屏就没有横向滚动条，"滑到更多"无法触发 */
function pageSize(): number {
  const w = window.innerWidth || 1440
  return Math.min(48, Math.max(14, Math.ceil((w - LEFT_W) / colW.value) + 6))
}
const colsW = computed(() => columns.value.length * colW.value)
const totalW = computed(() => LEFT_W + colsW.value)
const hasMore = computed(() => columns.value.length > 0 && columns.value.length < MAX_COLUMNS)

const label = computed(() => formatRange(anchor.value, anchor.value + props.step - 1))
/** 后端说明里带 V6 时代表该库还没有政权表（降级），需要给出显式提示，不能只是空白矩阵 */
const degraded = computed(() => note.value.includes('V6'))

/** 首屏：从 anchor 重新加载 */
async function reload() {
  ctrl?.abort()
  ctrl = new AbortController()
  loading.value = true
  error.value = null
  columns.value = []
  regions.value = []
  try {
    const r = await fetchMatrix(anchor.value, props.step, pageSize(), 0, ctrl.signal)
    applyPage(r, true)
    // 默认选中包含 anchor 的那一列
    selected.value = r.columns.find((c) => anchor.value >= c.startYearAstro && anchor.value <= c.endYearAstro)?.index ?? 0
    await nextTick()
    if (scrollEl.value) scrollEl.value.scrollLeft = 0
  } catch (e) {
    if ((e as Error).name === 'AbortError') return
    error.value = (e as Error).message
  } finally {
    loading.value = false
  }
}

/** 追加一页（横向滚动到底部时触发） */
async function loadMore() {
  if (loadingMore.value || loading.value || !hasMore.value) return
  loadingMore.value = true
  try {
    const r = await fetchMatrix(anchor.value, props.step, pageSize(), columns.value.length)
    applyPage(r, false)
  } catch (e) {
    if ((e as Error).name !== 'AbortError') error.value = (e as Error).message
  } finally {
    loadingMore.value = false
  }
}

interface ServerResp {
  columns: MatrixColumn[]
  regions: MatrixRegion[]
  unlinkedEventsInWindow: number
  truncated: boolean
  note: string
}

function applyPage(r: ServerResp, first: boolean) {
  note.value = r.note
  truncated.value = r.truncated
  unlinked.value = first ? r.unlinkedEventsInWindow : unlinked.value
  columns.value = first ? [...r.columns] : [...columns.value, ...r.columns]

  if (first) {
    regions.value = r.regions.map((x) => ({ ...x, polities: [], polityCount: 0, eventCount: 0 }))
  }
  for (const rg of r.regions) {
    const target = regions.value.find((x) => x.code === rg.code)
    if (!target) continue
    for (const p of rg.polities) {
      let row = target.polities.find((x) => x.polityId === p.polityId)
      if (!row) {
        row = { ...p, cells: [] }
        target.polities.push(row)
      }
      for (const c of p.cells) row.cells.push(c)
      recompute(row)
    }
    target.polities.sort((a, b) => a.name.localeCompare(b.name, 'zh-Hans-CN'))
    target.polityCount = target.polities.length
    target.eventCount = target.polities.reduce((n, p) => n + p.eventCount, 0)
  }
}

/** 行上的计数按「去重后的事件数」算，避免跨列重复计数 */
function recompute(row: MatrixPolity) {
  const ids = new Set<number>()
  for (const c of row.cells) for (const e of c.events) ids.add(e.eventId)
  row.eventCount = ids.size
}

function cellEvents(row: MatrixPolity, col: number): MatrixEvent[] {
  return row.cells.find((c) => c.columnIndex === col)?.events ?? []
}

function toggle(code: string) {
  const next = new Set(expanded.value)
  if (next.has(code)) next.delete(code)
  else next.add(code)
  expanded.value = next
}

function pickColumn(c: MatrixColumn) {
  selected.value = c.index
  emit('select-window', c.startYearAstro, c.endYearAstro)
}

/**
 * 点事件：先把当前时间段切到它所在的列，再打开详情。
 * 否则会出现「详情说这是前490年的事，但地图窗口还是前500」的错位。
 */
function pickEvent(e: MatrixEvent, colIndex: number) {
  const col = columns.value.find((c) => c.index === colIndex)
  if (col) pickColumn(col)
  emit('event-select', e.eventId)
}

function onScroll() {
  const el = scrollEl.value
  if (!el) return
  if (el.scrollLeft + el.clientWidth >= el.scrollWidth - 240) void loadMore()
}

watch(
  () => props.open,
  (open) => {
    if (open) {
      anchor.value = props.from
      void reload()
    }
  },
)
watch(
  () => [props.step, props.from] as const,
  ([step, from], old) => {
    // 只在打开状态下响应「跨度变化」；from 由本组件自己通过点击列驱动，不触发重载（否则会跳列）
    if (!props.open) return
    if (step !== old?.[0]) {
      anchor.value = from
      void reload()
    }
  },
)

defineExpose({ reload })
</script>

<template>
  <div v-if="open" class="mx">
    <div ref="scrollEl" class="mx-scroll" @scroll.passive="onScroll">
      <div class="mx-grid" :style="{ width: totalW + 'px' }">
        <!-- 时间刻度（sticky top，与内容同一个横向滚动容器） -->
        <div class="mx-head">
          <div class="mx-corner" :style="{ width: LEFT_W + 'px' }">
            <span class="tiny dim">地区 / 政权</span>
          </div>
          <button
            v-for="c in columns"
            :key="c.index"
            class="mx-hcol"
            :class="{ sel: c.index === selected }"
            :style="{ width: colW + 'px' }"
            :title="`选中 ${c.label}（${formatRange(c.startYearAstro, c.endYearAstro)}）`"
            @click="pickColumn(c)"
          >
            {{ c.label }}
          </button>
          <span v-if="loadingMore" class="mx-more tiny">加载…</span>
        </div>

        <p v-if="degraded" class="mx-degraded">
          {{ note }}
        </p>

        <!-- 地区折叠列表（默认收起） -->
        <div v-for="r in regions" :key="r.code" class="mx-region">
          <button class="mx-rrow" @click="toggle(r.code)">
            <span class="mx-rname" :style="{ width: LEFT_W + 'px' }">
              <span class="caret">{{ expanded.has(r.code) ? '▾' : '▸' }}</span>
              <span class="rlabel">{{ r.label }}</span>
              <span class="tiny dim rc">{{ r.polityCount }} 政权 · {{ r.eventCount }} 事件</span>
            </span>
            <span class="mx-rfill" :style="{ width: colsW + 'px' }" />
          </button>

          <template v-if="expanded.has(r.code)">
            <p v-if="r.polities.length === 0" class="mx-empty" :style="{ paddingLeft: LEFT_W + 12 + 'px' }">
              该时段此地区没有已关联历史政权的事件
            </p>
            <div v-for="p in r.polities" :key="p.polityId" class="mx-prow">
              <div class="mx-pname" :style="{ width: LEFT_W + 'px' }" :title="p.name">
                <span class="pn">{{ p.name }}</span>
                <span v-if="p.startYearAstro !== null" class="tiny dim py">
                  {{ formatRange(p.startYearAstro, p.endYearAstro) }}
                </span>
              </div>
              <div
                v-for="c in columns"
                :key="c.index"
                class="mx-cell"
                :class="{ sel: c.index === selected, has: cellEvents(p, c.index).length > 0 }"
                :style="{ width: colW + 'px' }"
              >
                <template v-if="cellEvents(p, c.index).length">
                  <button
                    v-for="e in cellEvents(p, c.index).slice(0, 2)"
                    :key="e.eventId"
                    class="ev"
                    :title="`${e.title}（${formatRange(e.startYearAstro, e.endYearAstro)}）`"
                    @click.stop="pickEvent(e, c.index)"
                  >
                    {{ e.title }}
                  </button>
                  <button
                    v-if="cellEvents(p, c.index).length > 2"
                    class="more"
                    :title="
                      cellEvents(p, c.index)
                        .slice(2)
                        .map((x) => x.title)
                        .join('、')
                    "
                    @click.stop="pickEvent(cellEvents(p, c.index)[2], c.index)"
                  >
                    +{{ cellEvents(p, c.index).length - 2 }}
                  </button>
                </template>
              </div>
            </div>
          </template>
        </div>

        <div class="mx-tail" :style="{ height: '26px' }" />
      </div>
    </div>

    <!-- 右上角：状态 + 收起（不占额外版面） -->
    <div class="mx-hud">
      <span v-if="unlinked > 0" class="hud-chip" title="这些事件没有关联任何历史政权，因此不进入矩阵">
        未关联政权 {{ unlinked }} 条
      </span>
      <span v-if="truncated" class="hud-chip">数据量过大，已截断</span>
      <span class="hud-chip mono">{{ label }} · {{ step }} 年/列</span>
      <button class="hud-close" title="收起矩阵（保留当前时间）" @click="emit('close')">收起 ▾</button>
    </div>

    <p v-if="error" class="mx-err panel">{{ error }}</p>
    <p v-else-if="note && !loading && columns.length === 0" class="mx-err panel">{{ note }}</p>
  </div>
</template>

<style scoped>
.mx {
  position: absolute;
  /* 让出顶部导航：展开后导航仍固定可见，矩阵占满其余可视区域 */
  inset: 56px 0 0 0;
  background: #fbfcfd;
  z-index: 30;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.mx-scroll {
  position: absolute;
  inset: 0;
  overflow: auto;
  overscroll-behavior: contain;
}

.mx-grid { min-height: 100%; }

/* ---------------- 表头：随横向滚动移动，纵向常驻 ---------------- */
.mx-head {
  position: sticky;
  top: 0;
  z-index: 6;
  display: flex;
  align-items: stretch;
  height: 38px;
  background: #fff;
  border-bottom: 1px solid var(--line);
  box-shadow: 0 1px 4px rgba(15, 26, 42, 0.05);
}
.mx-corner {
  position: sticky;
  left: 0;
  z-index: 7;
  display: flex;
  align-items: center;
  padding: 0 12px;
  background: #fff;
  border-right: 1px solid var(--line);
  flex: none;
}
.mx-hcol {
  flex: none;
  border: none;
  border-right: 1px solid #f0f3f6;
  border-radius: 0;
  background: #fff;
  font-size: 11.5px;
  color: var(--ink-2);
  padding: 0 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.mx-hcol:hover { background: #f7f9fb; }
.mx-hcol.sel {
  background: var(--accent-soft);
  color: #6b3f16;
  font-weight: 700;
  box-shadow: inset 0 -2px 0 var(--accent);
}
.mx-more { align-self: center; padding: 0 8px; flex: none; }

/* ---------------- 地区行 ---------------- */
.mx-region { border-bottom: 1px solid #eef1f5; }

.mx-rrow {
  display: flex;
  align-items: stretch;
  width: 100%;
  padding: 0;
  border: none;
  border-radius: 0;
  background: #f6f8fa;
  text-align: left;
  min-height: 34px;
}
.mx-rrow:hover { background: #eef2f6; }
.mx-rname {
  position: sticky;
  left: 0;
  z-index: 3;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 0 12px;
  background: inherit;
  border-right: 1px solid var(--line);
  flex: none;
}
.caret { color: var(--ink-3); font-size: 10px; width: 10px; }
.rlabel { font-size: 13px; font-weight: 700; }
.rc { margin-left: auto; padding-left: 8px; }
.mx-rfill { flex: none; }

/* ---------------- 政权行 ---------------- */
.mx-prow {
  display: flex;
  align-items: stretch;
  border-top: 1px solid #f4f6f8;
  min-height: 34px;
}
.mx-pname {
  position: sticky;
  left: 0;
  z-index: 3;
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 2px 12px 2px 26px;
  background: #fff;
  border-right: 1px solid var(--line);
  flex: none;
  overflow: hidden;
}
.pn { font-size: 12.5px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.py { white-space: nowrap; font-size: 10px; }

.mx-cell {
  flex: none;
  border-right: 1px solid #f2f4f7;
  padding: 3px;
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.mx-cell.sel { background: #fdf7ef; }
.mx-cell.has { background: #fcfdff; }
.mx-cell.sel.has { background: #fbf1e4; }

.ev {
  font-size: 10.5px;
  line-height: 1.3;
  padding: 2px 5px;
  border-radius: 4px;
  border: 1px solid #e4d5c2;
  background: #fffaf4;
  color: #6b3f16;
  text-align: left;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.ev:hover { background: var(--accent-soft); }
.more {
  font-size: 10px;
  padding: 0 4px;
  border: none;
  background: transparent;
  color: var(--ink-3);
  align-self: flex-start;
}
.more:hover { color: var(--accent); background: transparent; }

.mx-degraded {
  position: sticky;
  left: 0;
  margin: 0;
  padding: 10px 14px;
  font-size: 12px;
  line-height: 1.6;
  color: #8a5b14;
  background: #fff8ea;
  border-bottom: 1px solid #f0e0c4;
}

.mx-empty {
  margin: 0;
  padding: 10px 12px;
  font-size: 12px;
  color: var(--ink-3);
  background: #fff;
}

/* ---------------- HUD ---------------- */
.mx-hud {
  position: absolute;
  top: 6px;
  right: 12px;
  z-index: 8;
  display: flex;
  align-items: center;
  gap: 6px;
}
.hud-chip {
  font-size: 10.5px;
  color: var(--ink-3);
  background: rgba(255, 255, 255, 0.95);
  border: 1px solid var(--line);
  border-radius: 999px;
  padding: 2px 8px;
}
.hud-close {
  font-size: 11.5px;
  font-weight: 600;
  color: var(--accent);
  border-color: #e6d5c2;
  background: #fff;
  padding: 3px 9px;
}

.mx-err {
  position: absolute;
  left: 50%;
  top: 46%;
  transform: translateX(-50%);
  padding: 10px 14px;
  font-size: 12.5px;
  max-width: 60vw;
  color: #8c1d16;
  background: #fdf0ee;
  border-left: 3px solid #e8a39b;
}
.mono { font-variant-numeric: tabular-nums; }
</style>
