<script setup lang="ts">
/**
 * 地点编辑器：主表 + 历史名称（多行）+ 位置（多行，允许无坐标）。
 * entityId 为 null 表示新建。
 */
import { computed, ref, watch } from 'vue'
import AstroYear from './AstroYear.vue'
import { placeAdmin } from '../../api'
import type { PlaceDetail, PlaceLocation, PlaceName } from '../../types'

const props = defineProps<{ entityId: number | null }>()
const emit = defineEmits<{
  (e: 'saved', id: number): void
  (e: 'deleted'): void
  (e: 'changed'): void
  (e: 'locate', lon: number, lat: number): void
}>()

const PLACE_TYPES = [
  { v: 'settlement', t: '聚落' },
  { v: 'admin_center_prefecture', t: '府级治所' },
  { v: 'admin_center_county', t: '县级治所' },
  { v: 'admin_center_other', t: '其他治所' },
  { v: 'unknown', t: '未定' },
]
const NAME_TYPES = [
  { v: 'primary', t: '正名' },
  { v: 'alternate', t: '别名' },
  { v: 'transliteration', t: '转写' },
  { v: 'historical', t: '旧称' },
  { v: 'colloquial', t: '俗名' },
]
const TBTS = [
  { v: 'unknown', t: '未知' },
  { v: 'exact', t: '确切' },
  { v: 'bounded', t: '有界' },
  { v: 'exact_or_bounded', t: '确切或有界' },
  { v: 'tpq_taq', t: '最早/最晚' },
  { v: 'derived_tpq_taq', t: '推导最早/最晚' },
  { v: 'snapshot', t: '快照' },
]
const PRECISIONS = [
  { v: 'unknown', t: '未知' },
  { v: 'precise', t: '精确' },
  { v: 'approximate', t: '近似' },
  { v: 'rough', t: '粗略' },
]
const CRS_CONF = [
  { v: 'inferred', t: '推定（人工录入默认）' },
  { v: 'confirmed', t: '已确认' },
  { v: 'unknown', t: '未知（不作可信位置）' },
]

const detail = ref<PlaceDetail | null>(null)
const loading = ref(false)
const saving = ref(false)
const err = ref<string | null>(null)
const msg = ref<string | null>(null)

const form = ref({
  canonicalName: '',
  canonicalNameLang: 'zh',
  placeType: 'settlement',
  description: '',
  notes: '',
  recordStatus: 'staging',
})

const names = computed<PlaceName[]>(() => detail.value?.names ?? [])
const locs = computed<PlaceLocation[]>(() => detail.value?.locations ?? [])

// ---- 名称编辑 ----
const nameForm = ref({
  id: null as number | null,
  nameText: '',
  nameLang: 'zh',
  nameType: 'alternate',
  transliterationScheme: '',
  validFrom: null as number | null,
  validTo: null as number | null,
  timeBoundType: 'unknown',
  timeNote: '',
})
const nameFormOpen = ref(false)

// ---- 位置编辑 ----
const locForm = ref({
  id: null as number | null,
  lon: '',
  lat: '',
  locationPrecision: 'unknown',
  uncertaintyM: '',
  crsConfidence: 'inferred',
  recordStatus: 'staging',
  notes: '',
})
const locFormOpen = ref(false)

async function load(id: number) {
  loading.value = true
  err.value = null
  try {
    const r = await fetch(`/api/v1/places/${id}`, { headers: { Accept: 'application/json' } })
    if (!r.ok) throw new Error(`${r.status} ${r.statusText}`)
    const d = (await r.json()) as PlaceDetail
    detail.value = d
    form.value = {
      canonicalName: d.canonicalName,
      canonicalNameLang: d.canonicalNameLang ?? '',
      placeType: d.placeType ?? 'unknown',
      description: d.description ?? '',
      notes: d.notes ?? '',
      recordStatus: d.recordStatus === 'rejected' ? 'rejected' : 'staging',
    }
  } catch (e) {
    err.value = (e as Error).message
    detail.value = null
  } finally {
    loading.value = false
  }
}

watch(
  () => props.entityId,
  (id) => {
    msg.value = null
    nameFormOpen.value = false
    locFormOpen.value = false
    if (id === null) {
      detail.value = null
      form.value = {
        canonicalName: '',
        canonicalNameLang: 'zh',
        placeType: 'settlement',
        description: '',
        notes: '',
        recordStatus: 'staging',
      }
    } else {
      load(id)
    }
  },
  { immediate: true },
)

async function save() {
  err.value = null
  msg.value = null
  if (!form.value.canonicalName.trim()) {
    err.value = '地点规范名称不能为空'
    return
  }
  saving.value = true
  try {
    const body = {
      canonicalName: form.value.canonicalName.trim(),
      canonicalNameLang: form.value.canonicalNameLang || null,
      placeType: form.value.placeType,
      description: form.value.description || null,
      notes: form.value.notes || null,
      recordStatus: form.value.recordStatus,
    }
    if (props.entityId === null) {
      const r = await placeAdmin.create(body)
      emit('saved', r.placeId)
    } else {
      await placeAdmin.update(props.entityId, body)
      await load(props.entityId)
      msg.value = '已保存'
      emit('changed')
    }
  } catch (e) {
    err.value = (e as Error).message
  } finally {
    saving.value = false
  }
}

async function removePlace() {
  if (props.entityId === null) return
  if (!window.confirm(`确认删除地点「${form.value.canonicalName}」？其名称与位置行会一并删除；若仍被事件或人物引用，数据库会拒绝并提示。`)) return
  err.value = null
  try {
    await placeAdmin.remove(props.entityId)
    emit('deleted')
  } catch (e) {
    err.value = (e as Error).message
  }
}

// ---------------------------------------------------------------- 名称
function openNameForm(n?: PlaceName) {
  nameFormOpen.value = true
  err.value = null
  if (n) {
    nameForm.value = {
      id: n.nameId,
      nameText: n.nameText,
      nameLang: n.nameLang ?? '',
      nameType: n.nameType ?? 'alternate',
      transliterationScheme: n.transliterationScheme ?? '',
      validFrom: n.validFromYear ?? null,
      validTo: n.validToYear ?? null,
      timeBoundType: n.timeBoundType ?? 'unknown',
      timeNote: '',
    }
  } else {
    nameForm.value = {
      id: null,
      nameText: '',
      nameLang: 'zh',
      nameType: 'alternate',
      transliterationScheme: '',
      validFrom: null,
      validTo: null,
      timeBoundType: 'unknown',
      timeNote: '',
    }
  }
}

async function saveName() {
  if (props.entityId === null) return
  err.value = null
  if (!nameForm.value.nameText.trim()) {
    err.value = '名称内容不能为空'
    return
  }
  const f = nameForm.value
  const body = {
    nameText: f.nameText.trim(),
    nameLang: f.nameLang || null,
    nameType: f.nameType,
    transliterationScheme: f.nameType === 'transliteration' ? f.transliterationScheme || null : null,
    validFromYearAstro: f.validFrom,
    validToYearAstro: f.validTo,
    timeBoundType: f.timeBoundType,
    timeNote: f.timeNote || null,
    recordStatus: 'staging',
  }
  try {
    if (f.id === null) {
      await placeAdmin.addName(props.entityId, body)
    } else {
      await placeAdmin.updateName(props.entityId, f.id, body)
    }
    nameFormOpen.value = false
    await load(props.entityId)
    emit('changed')
  } catch (e) {
    err.value = (e as Error).message
  }
}

async function removeName(n: PlaceName) {
  if (props.entityId === null) return
  if (!window.confirm(`确认删除名称「${n.nameText}」？`)) return
  try {
    await placeAdmin.removeName(props.entityId, n.nameId)
    await load(props.entityId)
    emit('changed')
  } catch (e) {
    err.value = (e as Error).message
  }
}

// ---------------------------------------------------------------- 位置
function openLocForm(l?: PlaceLocation) {
  locFormOpen.value = true
  err.value = null
  if (l) {
    locForm.value = {
      id: l.locationId,
      lon: l.lon === null || l.lon === undefined ? '' : String(l.lon),
      lat: l.lat === null || l.lat === undefined ? '' : String(l.lat),
      locationPrecision: l.locationPrecision ?? 'unknown',
      uncertaintyM: l.uncertaintyM === null || l.uncertaintyM === undefined ? '' : String(l.uncertaintyM),
      crsConfidence: l.crsConfidence ?? 'inferred',
      recordStatus: l.recordStatus ?? 'staging',
      notes: '',
    }
  } else {
    locForm.value = {
      id: null,
      lon: '',
      lat: '',
      locationPrecision: 'unknown',
      uncertaintyM: '',
      crsConfidence: 'inferred',
      recordStatus: 'staging',
      notes: '',
    }
  }
}

async function saveLoc() {
  if (props.entityId === null) return
  err.value = null
  const f = locForm.value
  const hasLon = f.lon.trim() !== ''
  const hasLat = f.lat.trim() !== ''
  if (hasLon !== hasLat) {
    err.value = '经度与纬度必须同时填写，或都留空表示坐标未知'
    return
  }
  const lon = hasLon ? Number(f.lon) : null
  const lat = hasLat ? Number(f.lat) : null
  if (lon !== null && (Number.isNaN(lon) || lon < -180 || lon > 180)) {
    err.value = '经度需在 -180 ~ 180 之间'
    return
  }
  if (lat !== null && (Number.isNaN(lat) || lat < -90 || lat > 90)) {
    err.value = '纬度需在 -90 ~ 90 之间'
    return
  }
  const body = {
    lon,
    lat,
    locationPrecision: f.locationPrecision,
    uncertaintyM: f.uncertaintyM.trim() === '' ? null : Number(f.uncertaintyM),
    crsConfidence: f.crsConfidence,
    validFromYearAstro: null,
    validToYearAstro: null,
    timeBoundType: 'unknown',
    notes: f.notes || null,
    recordStatus: f.recordStatus,
  }
  try {
    if (f.id === null) {
      await placeAdmin.addLocation(props.entityId, body)
    } else {
      await placeAdmin.updateLocation(props.entityId, f.id, body)
    }
    locFormOpen.value = false
    await load(props.entityId)
    emit('changed')
  } catch (e) {
    err.value = (e as Error).message
  }
}

async function removeLoc(l: PlaceLocation) {
  if (props.entityId === null) return
  if (!window.confirm('确认删除这条位置记录？')) return
  try {
    await placeAdmin.removeLocation(props.entityId, l.locationId)
    await load(props.entityId)
    emit('changed')
  } catch (e) {
    err.value = (e as Error).message
  }
}

function fmtCoord(l: PlaceLocation): string {
  if (l.lon === null || l.lon === undefined) return '无坐标（未定位）'
  return `${l.lon.toFixed(5)}, ${l.lat?.toFixed(5)}`
}

function fmtNameRange(n: PlaceName): string {
  if (n.validFromYear === null && n.validToYear === null) return '有效期未知'
  const a = n.validFromYear
  const b = n.validToYear
  const f = (v: number | null) => (v === null ? '?' : v <= 0 ? `前${1 - v}` : `${v}`)
  if (a !== null && b !== null && a === b) return f(a)
  return `${f(a)} ~ ${f(b)}`
}
</script>

<template>
  <div class="editor">
    <div v-if="loading" class="m2-empty">加载中…</div>

    <template v-else>
      <h3 class="title">
        {{ entityId === null ? '新增历史地点' : `地点 #${entityId}` }}
        <span v-if="detail" class="tiny dim">{{ detail.recordStatus }}</span>
      </h3>

      <p v-if="err" class="m2-alert">{{ err }}</p>
      <p v-if="msg" class="tiny" style="color: #256b3a">{{ msg }}</p>

      <div class="m2-field">
        <label>规范名称 <span class="req">*</span></label>
        <input v-model="form.canonicalName" type="text" placeholder="如 洛邑" />
      </div>
      <div class="m2-grid3">
        <div class="m2-field">
          <label>语言</label>
          <input v-model="form.canonicalNameLang" type="text" placeholder="zh" />
        </div>
        <div class="m2-field">
          <label>地点类型</label>
          <select v-model="form.placeType">
            <option v-for="t in PLACE_TYPES" :key="t.v" :value="t.v">{{ t.t }}</option>
          </select>
        </div>
        <div class="m2-field">
          <label>记录状态</label>
          <select v-model="form.recordStatus">
            <option value="staging">暂存（staging）</option>
            <option value="rejected">已否决（rejected）</option>
          </select>
        </div>
      </div>
      <div class="m2-field">
        <label>简介</label>
        <textarea v-model="form.description" />
      </div>
      <div class="m2-field">
        <label>备注</label>
        <textarea v-model="form.notes" />
      </div>

      <div class="actions">
        <button class="m2-btn primary" :disabled="saving" @click="save">
          {{ saving ? '保存中…' : entityId === null ? '创建地点' : '保存修改' }}
        </button>
        <button v-if="entityId !== null" class="m2-btn danger" @click="removePlace">删除地点</button>
      </div>

      <!-- 名称 -->
      <div v-if="entityId !== null" class="m2-sub">
        历史名称 / 别名 <span class="tiny dim">{{ names.length }} 条</span>
        <span class="spacer" />
        <button class="m2-btn sm" @click="openNameForm()">+ 添加名称</button>
      </div>
      <div v-if="entityId !== null">
        <p v-if="names.length === 0 && !nameFormOpen" class="m2-empty">还没有名称行</p>
        <div v-for="n in names" :key="n.nameId" class="m2-row">
          <span class="grow">
            <strong>{{ n.nameText }}</strong>
            <span class="tiny dim">
              · {{ NAME_TYPES.find((t) => t.v === n.nameType)?.t ?? n.nameType }}
              · {{ n.nameLang || '语言未填' }} · {{ fmtNameRange(n) }}
            </span>
          </span>
          <span class="acts">
            <button class="m2-btn sm" @click="openNameForm(n)">编辑</button>
            <button class="m2-btn sm danger" @click="removeName(n)">删除</button>
          </span>
        </div>

        <div v-if="nameFormOpen" class="subform">
          <div class="m2-grid2">
            <div class="m2-field">
              <label>名称 <span class="req">*</span></label>
              <input v-model="nameForm.nameText" type="text" />
            </div>
            <div class="m2-field">
              <label>类型</label>
              <select v-model="nameForm.nameType">
                <option v-for="t in NAME_TYPES" :key="t.v" :value="t.v">{{ t.t }}</option>
              </select>
            </div>
          </div>
          <div class="m2-grid2">
            <div class="m2-field">
              <label>语言</label>
              <input v-model="nameForm.nameLang" type="text" placeholder="zh / zh-Latn / en" />
            </div>
            <div class="m2-field">
              <label>时间判定</label>
              <select v-model="nameForm.timeBoundType">
                <option v-for="t in TBTS" :key="t.v" :value="t.v">{{ t.t }}</option>
              </select>
            </div>
          </div>
          <div v-if="nameForm.nameType === 'transliteration'" class="m2-field">
            <label>转写方案</label>
            <input v-model="nameForm.transliterationScheme" type="text" placeholder="pinyin" />
          </div>
          <div v-if="nameForm.timeBoundType !== 'unknown'" class="m2-grid2">
            <div class="m2-field">
              <label>有效期起</label>
              <AstroYear v-model="nameForm.validFrom" />
            </div>
            <div class="m2-field">
              <label>有效期止</label>
              <AstroYear v-model="nameForm.validTo" />
            </div>
          </div>
          <p v-else class="m2-hint">时间判定为「未知」时不接受年份，避免编造。</p>
          <div class="actions">
            <button class="m2-btn primary" @click="saveName">保存名称</button>
            <button class="m2-btn" @click="nameFormOpen = false">取消</button>
          </div>
        </div>
      </div>

      <!-- 位置 -->
      <div v-if="entityId !== null" class="m2-sub">
        位置 / 坐标 <span class="tiny dim">{{ locs.length }} 条</span>
        <span class="spacer" />
        <button class="m2-btn sm" @click="openLocForm()">+ 添加位置</button>
      </div>
      <div v-if="entityId !== null">
        <p v-if="locs.length === 0 && !locFormOpen" class="m2-empty">
          还没有位置记录 —— 坐标未知时可以只保存地点本体，不伪造坐标。
        </p>
        <div v-for="l in locs" :key="l.locationId" class="m2-row">
          <span class="grow">
            <span class="mono">{{ fmtCoord(l) }}</span>
            <span class="tiny dim">
              · {{ PRECISIONS.find((p) => p.v === l.locationPrecision)?.t ?? l.locationPrecision }}
              <template v-if="l.uncertaintyM != null"> ±{{ l.uncertaintyM }}m</template>
              · {{ l.crsConfidence }}
            </span>
          </span>
          <span class="acts">
            <button
              v-if="l.hasGeom && l.lon !== null && l.lat !== null"
              class="m2-btn sm"
              @click="emit('locate', l.lon!, l.lat!)"
            >
              看地图
            </button>
            <button class="m2-btn sm" @click="openLocForm(l)">编辑</button>
            <button class="m2-btn sm danger" @click="removeLoc(l)">删除</button>
          </span>
        </div>

        <div v-if="locFormOpen" class="subform">
          <div class="m2-grid2">
            <div class="m2-field">
              <label>经度（WGS84）</label>
              <input v-model="locForm.lon" type="text" placeholder="留空 = 坐标未知" />
            </div>
            <div class="m2-field">
              <label>纬度（WGS84）</label>
              <input v-model="locForm.lat" type="text" placeholder="留空 = 坐标未知" />
            </div>
          </div>
          <div class="m2-grid3">
            <div class="m2-field">
              <label>定位精度</label>
              <select v-model="locForm.locationPrecision">
                <option v-for="p in PRECISIONS" :key="p.v" :value="p.v">{{ p.t }}</option>
              </select>
            </div>
            <div class="m2-field">
              <label>不确定度（米）</label>
              <input v-model="locForm.uncertaintyM" type="text" placeholder="无依据可留空" />
            </div>
            <div class="m2-field">
              <label>坐标系置信</label>
              <select v-model="locForm.crsConfidence">
                <option v-for="c in CRS_CONF" :key="c.v" :value="c.v">{{ c.t }}</option>
              </select>
            </div>
          </div>
          <div class="m2-field">
            <label>备注</label>
            <input v-model="locForm.notes" type="text" />
          </div>
          <p class="m2-hint">
            坐标留空即「未定位」，地图上不会显示；坐标系 unknown 的位置按规则不作为可信位置。
          </p>
          <div class="actions">
            <button class="m2-btn primary" @click="saveLoc">保存位置</button>
            <button class="m2-btn" @click="locFormOpen = false">取消</button>
          </div>
        </div>
      </div>

      <p v-if="entityId === null" class="m2-hint">保存后即可添加历史名称与位置。</p>
    </template>
  </div>
</template>

<style scoped>
.editor { height: 100%; overflow-y: auto; padding-right: 4px; }
.title { margin: 0 0 10px; font-size: 14px; font-weight: 650; display: flex; gap: 8px; align-items: baseline; }
.actions { display: flex; gap: 8px; margin: 10px 0 4px; }
.subform {
  margin: 8px 0 4px;
  padding: 10px 12px;
  background: #f8fafc;
  border: 1px solid var(--line);
  border-radius: 8px;
}
</style>
