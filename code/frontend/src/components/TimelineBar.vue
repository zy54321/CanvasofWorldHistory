<script setup lang="ts">
/**
 * 收起状态的时间轴（M3）。
 *
 * 只有一条横向轴：中间是当前时间段，两侧是按当前跨度等距的相邻段。
 * 左右按钮与拖动都按「跨度」为步长移动 —— 1 年跨度一次走 1 年，100 年跨度一次走 100 年。
 * 所有数值都是天文学纪年整数，显示时才转「公元前/公元」。
 */
import { computed, ref } from 'vue'
import { SPANS, formatWindow, shiftFrom, shortYear, type Span } from '../time'

const props = defineProps<{
  from: number
  span: Span
  /** 当前窗口内事件数（地图实际返回） */
  eventCount: number | null
  /** 事件总数里被截断时的提示 */
  truncated?: boolean
}>()
const emit = defineEmits<{
  (e: 'update:from', v: number): void
  (e: 'update:span', v: Span): void
  (e: 'expand'): void
}>()

const TICK_COUNT = 7
const trackEl = ref<HTMLDivElement | null>(null)

const label = computed(() => formatWindow(props.from, props.span))

/** 中心两侧各 3 段 */
const ticks = computed(() => {
  const half = (TICK_COUNT - 1) / 2
  const out: { offset: number; from: number; label: string; current: boolean }[] = []
  for (let i = -half; i <= half; i++) {
    const f = props.from + i * props.span
    out.push({ offset: i, from: f, label: shortYear(f), current: i === 0 })
  }
  return out
})

function move(steps: number) {
  emit('update:from', shiftFrom(props.from, props.span, steps))
}

function setSpan(v: Span) {
  if (v === props.span) return
  emit('update:span', v)
}

// ---- 拖动：向右拖 = 回到更早（内容跟着手走）----
const drag = ref<{ x0: number; from0: number } | null>(null)
const PX_PER_SPAN = 68

function onPointerDown(e: PointerEvent) {
  if (e.button !== 0) return
  drag.value = { x0: e.clientX, from0: props.from }
  ;(e.currentTarget as HTMLElement).setPointerCapture(e.pointerId)
  e.preventDefault()
}

function onPointerMove(e: PointerEvent) {
  if (!drag.value) return
  const dx = e.clientX - drag.value.x0
  const steps = Math.round(-dx / PX_PER_SPAN)
  const next = shiftFrom(drag.value.from0, props.span, steps)
  if (next !== props.from) emit('update:from', next)
}

function onPointerUp(e: PointerEvent) {
  if (!drag.value) return
  drag.value = null
  try {
    ;(e.currentTarget as HTMLElement).releasePointerCapture(e.pointerId)
  } catch {
    /* 指针已释放 */
  }
}

function jump(i: number) {
  emit('update:from', ticks.value[i + (TICK_COUNT - 1) / 2].from)
}
</script>

<template>
  <div class="tl panel">
    <button class="nav" title="向早移动一个跨度" @click="move(-1)">‹</button>

    <div
      ref="trackEl"
      class="track"
      title="按住左右拖动时间轴"
      @pointerdown="onPointerDown"
      @pointermove="onPointerMove"
      @pointerup="onPointerUp"
      @pointercancel="onPointerUp"
    >
      <div class="ruler">
        <button
          v-for="(t, i) in ticks"
          :key="t.offset"
          class="tick"
          :class="{ cur: t.current }"
          :title="`跳到 ${t.label}`"
          @click="jump(i)"
        >
          <span class="lab">{{ t.label }}</span>
          <span class="bar" />
        </button>
      </div>
    </div>

    <button class="nav" title="向晚移动一个跨度" @click="move(1)">›</button>

    <div class="now">
      <span class="cur-label">{{ label }}</span>
      <span class="tiny dim count">
        <template v-if="eventCount === null">读取中…</template>
        <template v-else>{{ eventCount }} 个事件<template v-if="truncated">（已截断）</template></template>
      </span>
    </div>

    <div class="spans">
      <button
        v-for="s in SPANS"
        :key="s.value"
        :class="{ active: span === s.value }"
        :title="`时间跨度 ${s.label}（左右移动步长同步）`"
        @click="setSpan(s.value as Span)"
      >
        {{ s.label }}
      </button>
    </div>

    <button class="expand" title="展开历史时空矩阵" @click="emit('expand')">展开 ▴</button>
  </div>
</template>

<style scoped>
.tl {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  height: 62px;
  pointer-events: auto;
  user-select: none;
}

.nav {
  width: 26px;
  height: 34px;
  padding: 0;
  font-size: 17px;
  line-height: 1;
  color: var(--ink-2);
  flex: none;
}

.track {
  position: relative;
  width: clamp(220px, 34vw, 460px);
  height: 44px;
  overflow: hidden;
  cursor: grab;
  flex: none;
  touch-action: none;
}
.track:active { cursor: grabbing; }

.ruler {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  height: 100%;
  align-items: end;
}

.tick {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-end;
  gap: 3px;
  height: 100%;
  padding: 0 1px 2px;
  border: none;
  background: transparent;
  color: var(--ink-3);
  border-radius: 0;
}
.tick:hover { background: rgba(140, 90, 43, 0.06); }
.tick .lab {
  font-size: 10px;
  white-space: nowrap;
  transform: scale(0.92);
  opacity: 0.75;
}
.tick .bar {
  width: 1px;
  height: 9px;
  background: #cfd6de;
}
.tick.cur { color: var(--accent); }
.tick.cur .lab { font-size: 11px; font-weight: 700; opacity: 1; }
.tick.cur .bar { height: 14px; width: 2px; background: var(--accent); }

.now {
  display: flex;
  flex-direction: column;
  gap: 1px;
  min-width: 132px;
  padding-left: 4px;
  border-left: 1px solid var(--line);
  flex: none;
}
.cur-label { font-size: 13.5px; font-weight: 700; letter-spacing: 0.01em; }
.count { white-space: nowrap; }

.spans { display: flex; gap: 2px; flex: none; }
.spans button { font-size: 11.5px; padding: 4px 7px; }

.expand {
  margin-left: 4px;
  font-size: 12px;
  font-weight: 600;
  color: var(--accent);
  border-color: #e6d5c2;
  background: #fdfaf6;
  flex: none;
}
.expand:hover { background: var(--accent-soft); }
</style>
