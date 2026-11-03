<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { fetchPlace } from '../api'
import type { PlaceDetail } from '../types'

const props = defineProps<{ placeId: number | null }>()
const emit = defineEmits<{
  (e: 'close'): void
  (e: 'locate', lon: number, lat: number): void
}>()

const detail = ref<PlaceDetail | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)
const tab = ref<'names' | 'location' | 'source' | 'issues'>('names')

let ctrl: AbortController | null = null

async function load(id: number) {
  ctrl?.abort()
  ctrl = new AbortController()
  loading.value = true
  error.value = null
  detail.value = null
  try {
    detail.value = await fetchPlace(id, ctrl.signal)
  } catch (e) {
    if ((e as Error).name === 'AbortError') return
    error.value = (e as Error).message
  } finally {
    loading.value = false
  }
}

watch(
  () => props.placeId,
  (id) => {
    if (id === null) {
      detail.value = null
      return
    }
    tab.value = 'names'
    load(id)
  },
  { immediate: true },
)

const primaryLocation = computed(() => {
  const d = detail.value
  if (!d) return null
  return d.locations.find((l) => l.hasGeom && l.lon !== null && l.lat !== null) ?? null
})

const coords = computed(() => {
  const l = primaryLocation.value
  return l ? `${l.lon!.toFixed(5)}, ${l.lat!.toFixed(5)}` : null
})

const precisionText = computed(() => {
  const l = primaryLocation.value
  if (!l) return '无代表坐标'
  const base = l.locationPrecision ?? 'unknown'
  return l.uncertaintyM != null ? `${base} · ±${l.uncertaintyM} m` : base
})

const crsWarning = computed(() => {
  const d = detail.value
  if (!d) return null
  if (d.locations.length === 0) return '该地点暂无位置记录'
  const noGeom = d.locations.filter((l) => !l.hasGeom).length
  const unknown = d.locations.filter((l) => l.crsConfidence === 'unknown' || l.crsConfidence === null).length
  const parts: string[] = []
  if (noGeom) parts.push(`${noGeom} 条位置无可用几何（坐标缺失或越界）`)
  if (unknown) parts.push(`${unknown} 条坐标系置信度 unknown，不作为可信位置显示`)
  if (!primaryLocation.value) parts.push('无可展示的代表坐标')
  return parts.length ? parts.join('；') : null
})

const recordStatusText = computed(() => {
  const s = detail.value?.recordStatus
  if (s === 'published') return '已发布'
  if (s === 'staging') return '暂存（staging）'
  if (s === 'confirmed') return '已确认'
  return s ?? '—'
})

function fmtYear(y: number | null): string {
  if (y === null) return '—'
  return y <= 0 ? `前 ${1 - y}` : `${y}`
}

function span(a: number | null, b: number | null): string {
  if (a === null && b === null) return '纪年未知'
  return `${fmtYear(a)} – ${fmtYear(b)}`
}

const nameTypeLabel: Record<string, string> = {
  primary: '正名',
  alternate: '别名',
  transliteration: '转写',
  variant: '异写',
  historical: '旧称',
}

const severityLabel: Record<string, string> = {
  info: '提示',
  warning: '警告',
  error: '错误',
  blocking: '阻断',
}

function locate() {
  const l = primaryLocation.value
  if (l) emit('locate', l.lon!, l.lat!)
}
</script>

<template>
  <aside v-if="placeId !== null" class="detail panel">
    <header class="hd">
      <div class="titles">
        <h2 v-if="detail">{{ detail.canonicalName }}</h2>
        <h2 v-else-if="loading" class="dim">加载中…</h2>
        <h2 v-else class="dim">#{{ placeId }}</h2>
        <p v-if="detail" class="tiny dim">
          {{ detail.placeType ?? '类型未定' }} · {{ recordStatusText }} · #{{ detail.placeId }}
        </p>
      </div>
      <button class="x" title="关闭" @click="emit('close')">✕</button>
    </header>

    <p v-if="error" class="body err">加载失败：{{ error }}</p>

    <div v-if="detail" class="body scroll">
      <!-- 概览 -->
      <div class="kicker">
        <div class="kv">
          <span class="k">坐标</span>
          <span class="v mono">{{ coords ?? '—' }}</span>
        </div>
        <div class="kv">
          <span class="k">定位精度</span>
          <span class="v">{{ precisionText }}</span>
        </div>
        <div class="kv">
          <span class="k">数据集</span>
          <span class="v">{{ detail.datasetName ?? detail.datasetId }}</span>
        </div>
        <div class="kv">
          <span class="k">来源</span>
          <span class="v">
            <a v-if="detail.sourceHomepage" :href="detail.sourceHomepage" target="_blank" rel="noreferrer noopener">
              {{ detail.sourceName ?? detail.sourceId }}
            </a>
            <template v-else>{{ detail.sourceName ?? detail.sourceId ?? '—' }}</template>
          </span>
        </div>
      </div>

      <div class="actions">
        <button :disabled="!primaryLocation" @click="locate">在地图上定位</button>
        <span v-if="detail.notes" class="tiny dim" :title="detail.notes">原始备注可见于数据集记录</span>
      </div>

      <p v-if="crsWarning" class="warn tiny">{{ crsWarning }}</p>

      <!-- 选项卡 -->
      <nav class="tabs">
        <button :class="{ active: tab === 'names' }" @click="tab = 'names'">
          名称 <span class="cnt">{{ detail.names.length }}</span>
        </button>
        <button :class="{ active: tab === 'location' }" @click="tab = 'location'">
          位置 <span class="cnt">{{ detail.locations.length }}</span>
        </button>
        <button :class="{ active: tab === 'source' }" @click="tab = 'source'">
          来源记录 <span class="cnt">{{ detail.sourceRecords.length }}</span>
        </button>
        <button :class="{ active: tab === 'issues' }" @click="tab = 'issues'">
          质量提示 <span class="cnt">{{ detail.issues.length }}</span>
        </button>
      </nav>

      <!-- 名称 -->
      <section v-if="tab === 'names'" class="pane">
        <p v-if="detail.names.length === 0" class="tiny dim">无名称记录</p>
        <table v-else class="tbl">
          <thead>
            <tr><th>名称</th><th>类型</th><th>语言</th><th>有效期</th></tr>
          </thead>
          <tbody>
            <tr v-for="n in detail.names" :key="n.nameId">
              <td>{{ n.nameText }}</td>
              <td>{{ nameTypeLabel[n.nameType ?? ''] ?? n.nameType ?? '—' }}</td>
              <td class="mono tiny">{{ n.nameLang ?? '—' }}</td>
              <td class="tiny" :class="{ dim: !n.timeBoundType }">{{ span(n.validFromYear, n.validToYear) }}</td>
            </tr>
          </tbody>
        </table>
      </section>

      <!-- 位置 -->
      <section v-if="tab === 'location'" class="pane">
        <p v-if="detail.locations.length === 0" class="tiny dim">无位置记录</p>
        <div v-for="l in detail.locations" :key="l.locationId" class="loc">
          <div class="loc-hd">
            <span class="mono tiny">{{ l.lon?.toFixed(5) ?? '—' }}, {{ l.lat?.toFixed(5) ?? '—' }}</span>
            <span class="tag" :class="l.hasGeom ? 'ok' : 'bad'">{{ l.hasGeom ? '可用几何' : '无几何' }}</span>
          </div>
          <dl class="mini">
            <div><dt>定位精度</dt><dd>{{ l.locationPrecision ?? '—' }}<template v-if="l.uncertaintyM != null"> · ±{{ l.uncertaintyM }} m</template></dd></div>
            <div><dt>原始坐标系</dt><dd class="mono">{{ l.originalCrs ?? '—' }}</dd></div>
            <div><dt>坐标系置信</dt><dd :class="{ bad: l.crsConfidence === 'unknown' || !l.crsConfidence }">{{ l.crsConfidence ?? '—' }}</dd></div>
            <div v-if="l.originalX"><dt>原始坐标</dt><dd class="mono tiny">{{ l.originalX }}, {{ l.originalY }}</dd></div>
            <div><dt>有效期</dt><dd>{{ span(l.validFromYear, l.validToYear) }}</dd></div>
            <div><dt>记录状态</dt><dd>{{ l.recordStatus }}</dd></div>
          </dl>
        </div>
      </section>

      <!-- 来源 -->
      <section v-if="tab === 'source'" class="pane">
        <div class="srcline tiny">
          <span class="dim">来源</span>
          <strong>{{ detail.sourceName ?? detail.sourceId ?? '—' }}</strong>
          <span v-if="detail.datasetVersion" class="dim">· 版本 {{ detail.datasetVersion }}</span>
        </div>
        <p v-if="detail.sourceLicenseNote" class="tiny dim lic">{{ detail.sourceLicenseNote }}</p>
        <table v-if="detail.sourceRecords.length" class="tbl">
          <thead>
            <tr><th>外部 ID</th><th>作用域</th><th>原始文件</th><th>状态</th></tr>
          </thead>
          <tbody>
            <tr v-for="r in detail.sourceRecords" :key="r.sourceRecordId">
              <td class="mono tiny">{{ r.externalId }}</td>
              <td class="tiny">{{ r.recordScope }}</td>
              <td class="tiny dim">{{ (r.rawFile ?? '—').split('/').pop() }}</td>
              <td class="tiny">
                <span v-if="r.active" class="tag ok">活动</span>
                <span v-else class="tag bad" :title="r.inactiveReason ?? ''">已隔离</span>
              </td>
            </tr>
          </tbody>
        </table>
        <p v-else class="tiny dim">无来源记录</p>
      </section>

      <!-- 质量提示 -->
      <section v-if="tab === 'issues'" class="pane">
        <p v-if="detail.issues.length === 0" class="tiny dim">该地点无质量台账条目</p>
        <template v-else>
          <p v-if="detail.issueListTruncated" class="tiny dim trunc">
            台账条目过多，仅显示前 {{ detail.issues.length }} 条（按严重程度排序）
          </p>
          <ul class="issues">
            <li v-for="i in detail.issues" :key="i.issueId">
              <div class="ih">
                <span class="tag" :class="i.severity === 'blocking' || i.severity === 'error' ? 'bad' : 'warn-tag'">
                  {{ severityLabel[i.severity ?? ''] ?? i.severity ?? '—' }}
                </span>
                <span class="tiny mono">{{ i.issueType }}</span>
                <span v-if="i.fieldName" class="tiny dim">· {{ i.fieldName }}</span>
              </div>
              <div v-if="i.observedValue" class="tiny ov">观测值：{{ i.observedValue }}</div>
              <div v-if="i.actionTaken" class="tiny dim">处置：{{ i.actionTaken }}</div>
              <div v-if="i.resolutionNote" class="tiny dim note">{{ i.resolutionNote }}</div>
            </li>
          </ul>
        </template>
      </section>
    </div>
  </aside>
</template>

<style scoped>
.detail {
  display: flex;
  flex-direction: column;
  width: 400px;
  max-height: calc(100vh - 96px);
  overflow: hidden;
}
.hd {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 13px 14px 10px;
  border-bottom: 1px solid var(--line);
}
.titles { flex: 1; min-width: 0; }
h2 { margin: 0; font-size: 17px; font-weight: 650; }
.hd p { margin: 3px 0 0; }
.x {
  border: none;
  background: transparent;
  color: var(--ink-3);
  padding: 2px 6px;
  font-size: 14px;
}
.x:hover { background: #eef1f5; color: var(--ink); }

.body { padding: 0 14px 14px; flex: 1; }
.body.err { padding: 14px; color: #b3261e; font-size: 13px; }

.kicker {
  display: grid;
  gap: 5px;
  padding: 10px 0;
  border-bottom: 1px dashed var(--line);
}
.kv { display: flex; gap: 8px; font-size: 12.5px; line-height: 1.5; }
.kv .k { color: var(--ink-3); flex: 0 0 62px; }
.kv .v { flex: 1; min-width: 0; word-break: break-word; }
.kv a { color: var(--accent); }

.actions {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 0 4px;
}

.warn {
  margin: 6px 0 0;
  padding: 7px 9px;
  background: var(--warn-bg);
  border-left: 3px solid var(--warn-line);
  border-radius: 4px;
  color: #7a5212;
  line-height: 1.55;
}

.tabs {
  display: flex;
  gap: 4px;
  margin: 12px 0 8px;
  border-bottom: 1px solid var(--line);
}
.tabs button {
  border: none;
  border-bottom: 2px solid transparent;
  border-radius: 0;
  background: transparent;
  padding: 6px 8px 7px;
  font-size: 12.5px;
  color: var(--ink-2);
}
.tabs button.active { color: var(--accent); border-bottom-color: var(--accent); font-weight: 600; }
.cnt { font-size: 10.5px; color: var(--ink-3); }

.pane { padding-top: 2px; }

.tbl { width: 100%; border-collapse: collapse; font-size: 12px; }
.tbl th {
  text-align: left;
  font-weight: 500;
  color: var(--ink-3);
  font-size: 11px;
  padding: 4px 6px 4px 0;
  border-bottom: 1px solid var(--line);
}
.tbl td { padding: 5px 6px 5px 0; border-bottom: 1px solid #f1f4f7; vertical-align: top; }

.loc { padding: 9px 0; border-bottom: 1px solid #f1f4f7; }
.loc-hd { display: flex; align-items: center; gap: 8px; }
.loc-hd .mono { font-size: 11.5px; }
.mini { margin: 6px 0 0; display: grid; gap: 3px; }
.mini > div { display: flex; gap: 8px; font-size: 11.5px; }
.mini dt { color: var(--ink-3); flex: 0 0 74px; margin: 0; }
.mini dd { margin: 0; flex: 1; }
.mini dd.bad { color: #b3261e; }

.tag {
  font-size: 10px;
  padding: 1px 5px;
  border-radius: 4px;
  border: 1px solid;
  white-space: nowrap;
}
.tag.ok { color: #256b3a; border-color: #b6ddc3; background: #eef8f1; }
.tag.bad { color: #a3241b; border-color: #f0c2bd; background: #fdf0ee; }
.tag.warn-tag { color: #8a5b14; border-color: #e8d0a4; background: #fdf6e9; }

.srcline { display: flex; gap: 6px; align-items: baseline; padding-bottom: 4px; }
.lic { margin: 4px 0 8px; line-height: 1.5; }

.issues { list-style: none; margin: 0; padding: 0; display: grid; gap: 8px; }
.issues li { border: 1px solid var(--line); border-radius: 8px; padding: 8px 10px; background: #fcfdfe; }
.ih { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.ov { margin-top: 4px; color: var(--ink-2); word-break: break-word; }
.note { margin-top: 2px; line-height: 1.45; }
</style>