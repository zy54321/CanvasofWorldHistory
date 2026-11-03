<script setup lang="ts">
/**
 * 人物编辑器：主表 + 名称（八类）+ 关联事件 + 活动地点。
 * 生卒年份允许全部留空（资料残缺可保存）。
 */
import { computed, ref, watch } from 'vue'
import AstroYear from './AstroYear.vue'
import ObjectPicker, { type PickedItem } from './ObjectPicker.vue'
import { personApi } from '../../api'
import type { PersonDetail, PersonEventRow, PersonPlaceRow, PersonNameRow } from '../../types'
import { PRECISIONS, formatRange, formatYear, precisionLabel } from '../../time'

const props = defineProps<{ entityId: number | null }>()
const emit = defineEmits<{
  (e: 'saved', id: number): void
  (e: 'deleted'): void
  (e: 'changed'): void
  (e: 'locate', lon: number, lat: number): void
}>()

const NAME_TYPES = [
  { v: 'primary', t: '正名' },
  { v: 'alternate', t: '别名' },
  { v: 'transliteration', t: '转写' },
  { v: 'historical', t: '旧称' },
  { v: 'courtesy', t: '字' },
  { v: 'art', t: '号' },
  { v: 'posthumous', t: '谥号' },
  { v: 'pseudonym', t: '化名' },
]

const detail = ref<PersonDetail | null>(null)
const loading = ref(false)
const saving = ref(false)
const err = ref<string | null>(null)
const msg = ref<string | null>(null)

const form = ref({
  canonicalName: '',
  canonicalNameLang: 'zh',
  description: '',
  birth: null as number | null,
  birthPrecision: 'unknown',
  birthOriginalText: '',
  death: null as number | null,
  deathPrecision: 'unknown',
  deathOriginalText: '',
  notes: '',
  recordStatus: 'staging',
})

const names = computed<PersonNameRow[]>(() => detail.value?.names ?? [])
const events = computed<PersonEventRow[]>(() => detail.value?.events ?? [])
const places = computed<PersonPlaceRow[]>(() => detail.value?.places ?? [])

// ---- 名称 ----
const nameOpen = ref(false)
const nameForm = ref({
  id: null as number | null,
  nameText: '',
  nameLang: 'zh',
  nameType: 'alternate',
  transliterationScheme: '',
  notes: '',
})

// ---- 关联事件 ----
const evOpen = ref(false)
const pickerEvent = ref(false)
const evForm = ref({
  linkId: null as number | null,
  eventId: null as number | null,
  eventTitle: '',
  role: 'participant',
  validFrom: null as number | null,
  validTo: null as number | null,
  note: '',
})

// ---- 活动地点 ----
const plOpen = ref(false)
const pickerPlace = ref(false)
const plForm = ref({
  linkId: null as number | null,
  placeId: null as number | null,
  placeName: '',
  relationType: 'activity',
  start: null as number | null,
  end: null as number | null,
  timePrecision: 'unknown',
  sequenceOrder: '' as string,
  note: '',
})

async function load(id: number) {
  loading.value = true
  err.value = null
  try {
    const d = await personApi.detail(id)
    detail.value = d
    form.value = {
      canonicalName: d.canonicalName,
      canonicalNameLang: d.canonicalNameLang ?? '',
      description: d.description ?? '',
      birth: d.birthYearAstro,
      birthPrecision: d.birthPrecision,
      birthOriginalText: d.birthOriginalText ?? '',
      death: d.deathYearAstro,
      deathPrecision: d.deathPrecision,
      deathOriginalText: d.deathOriginalText ?? '',
      notes: d.notes ?? '',
      recordStatus: d.recordStatus,
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
    nameOpen.value = false
    evOpen.value = false
    plOpen.value = false
    if (id === null) {
      detail.value = null
      form.value = {
        canonicalName: '', canonicalNameLang: 'zh', description: '',
        birth: null, birthPrecision: 'unknown', birthOriginalText: '',
        death: null, deathPrecision: 'unknown', deathOriginalText: '',
        notes: '', recordStatus: 'staging',
      }
    } else {
      load(id)
    }
  },
  { immediate: true },
)

/** 前端只做「年份与精度成对」的提示，最终以后端 CHECK 为准 */
function timeIssue(year: number | null, precision: string): string | null {
  if (year === null && precision !== 'unknown') return '未填年份时精度应为「未知」'
  if (year !== null && precision === 'unknown') return '已填年份，请选择确切/约/区间精度'
  return null
}

async function save() {
  err.value = null
  msg.value = null
  if (!form.value.canonicalName.trim()) {
    err.value = '人物规范姓名不能为空'
    return
  }
  const bi = timeIssue(form.value.birth, form.value.birthPrecision)
  const di = timeIssue(form.value.death, form.value.deathPrecision)
  if (bi || di) {
    err.value = `生卒时间：${bi ?? di}`
    return
  }
  if (
    form.value.birth !== null &&
    form.value.death !== null &&
    form.value.birth > form.value.death
  ) {
    err.value = '卒年不得早于生年'
    return
  }
  saving.value = true
  try {
    const body = {
      canonicalName: form.value.canonicalName.trim(),
      canonicalNameLang: form.value.canonicalNameLang || null,
      description: form.value.description || null,
      birthYearAstro: form.value.birth,
      birthPrecision: form.value.birthPrecision,
      birthOriginalText: form.value.birthOriginalText || null,
      deathYearAstro: form.value.death,
      deathPrecision: form.value.deathPrecision,
      deathOriginalText: form.value.deathOriginalText || null,
      notes: form.value.notes || null,
      recordStatus: form.value.recordStatus,
    }
    if (props.entityId === null) {
      const r = await personApi.create(body)
      emit('saved', r.personId)
    } else {
      await personApi.update(props.entityId, body)
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

async function removePerson() {
  if (props.entityId === null) return
  if (!window.confirm(`确认删除人物「${form.value.canonicalName}」？其名称、事件关联与活动地点关联会一并删除，事件与地点本体不受影响。`)) return
  err.value = null
  try {
    await personApi.remove(props.entityId)
    emit('deleted')
  } catch (e) {
    err.value = (e as Error).message
  }
}

// ---------------------------------------------------------------- 名称
function openName(n?: PersonNameRow) {
  err.value = null
  nameOpen.value = true
  nameForm.value = n
    ? { id: n.personNameId, nameText: n.nameText, nameLang: n.nameLang ?? '', nameType: n.nameType,
        transliterationScheme: n.transliterationScheme ?? '', notes: n.notes ?? '' }
    : { id: null, nameText: '', nameLang: 'zh', nameType: 'alternate', transliterationScheme: '', notes: '' }
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
    notes: f.notes || null,
    recordStatus: 'staging',
  }
  try {
    if (f.id === null) await personApi.addName(props.entityId, body)
    else await personApi.updateName(props.entityId, f.id, body)
    nameOpen.value = false
    await load(props.entityId)
    emit('changed')
  } catch (e) {
    err.value = (e as Error).message
  }
}

async function removeName(n: PersonNameRow) {
  if (props.entityId === null) return
  if (!window.confirm(`确认删除名称「${n.nameText}」？`)) return
  try {
    await personApi.removeName(props.entityId, n.personNameId)
    await load(props.entityId)
    emit('changed')
  } catch (e) {
    err.value = (e as Error).message
  }
}

// ---------------------------------------------------------------- 关联事件
function openEv(r?: PersonEventRow) {
  err.value = null
  evOpen.value = true
  evForm.value = r
    ? { linkId: r.linkId, eventId: r.eventId, eventTitle: r.title, role: r.role,
        validFrom: r.validFromYearAstro, validTo: r.validToYearAstro, note: r.note ?? '' }
    : { linkId: null, eventId: null, eventTitle: '', role: 'participant',
        validFrom: null, validTo: null, note: '' }
}

function onPickEvent(it: PickedItem) {
  evForm.value.eventId = it.id
  evForm.value.eventTitle = it.name
  pickerEvent.value = false
}

async function saveEv() {
  if (props.entityId === null) return
  err.value = null
  if (evForm.value.eventId === null) {
    err.value = '请先选择要关联的事件'
    return
  }
  if (!evForm.value.role.trim()) {
    err.value = '请填写人物在该事件中的角色（可用 unknown）'
    return
  }
  const body = {
    eventId: evForm.value.eventId,
    role: evForm.value.role.trim(),
    validFromYearAstro: evForm.value.validFrom,
    validToYearAstro: evForm.value.validTo,
    note: evForm.value.note || null,
  }
  try {
    if (evForm.value.linkId === null) await personApi.linkEvent(props.entityId, body)
    else await personApi.updateEventLink(props.entityId, evForm.value.linkId, body)
    evOpen.value = false
    await load(props.entityId)
    emit('changed')
  } catch (e) {
    err.value = (e as Error).message
  }
}

async function removeEv(r: PersonEventRow) {
  if (props.entityId === null) return
  if (!window.confirm(`确认解除与事件「${r.title}」的关联？（不会删除事件本体）`)) return
  try {
    await personApi.unlinkEvent(props.entityId, r.linkId)
    await load(props.entityId)
    emit('changed')
  } catch (e) {
    err.value = (e as Error).message
  }
}

// ---------------------------------------------------------------- 活动地点
function openPl(r?: PersonPlaceRow) {
  err.value = null
  plOpen.value = true
  plForm.value = r
    ? { linkId: r.linkId, placeId: r.placeId, placeName: r.placeName, relationType: r.relationType,
        start: r.startYearAstro, end: r.endYearAstro, timePrecision: r.timePrecision,
        sequenceOrder: r.sequenceOrder === null ? '' : String(r.sequenceOrder), note: r.note ?? '' }
    : { linkId: null, placeId: null, placeName: '', relationType: 'activity',
        start: null, end: null, timePrecision: 'unknown', sequenceOrder: '', note: '' }
}

function onPickPlace(it: PickedItem) {
  plForm.value.placeId = it.id
  plForm.value.placeName = it.name
  pickerPlace.value = false
}

async function savePl() {
  if (props.entityId === null) return
  err.value = null
  if (plForm.value.placeId === null) {
    err.value = '请先选择要关联的地点'
    return
  }
  if (!plForm.value.relationType.trim()) {
    err.value = '请填写关系类型（如 residence / activity / birthplace）'
    return
  }
  const p = plForm.value.timePrecision
  if (p === 'unknown' && (plForm.value.start !== null || plForm.value.end !== null)) {
    err.value = '时间判定为「未知」时不应填写年份'
    return
  }
  if (p !== 'unknown' && plForm.value.start === null) {
    err.value = '时间判定非「未知」时必须填写起始年份'
    return
  }
  if (plForm.value.start !== null && plForm.value.end !== null && plForm.value.start > plForm.value.end) {
    err.value = '起始年不得晚于结束年'
    return
  }
  const body = {
    placeId: plForm.value.placeId,
    relationType: plForm.value.relationType.trim(),
    startYearAstro: plForm.value.start,
    endYearAstro: plForm.value.end,
    timePrecision: plForm.value.timePrecision,
    sequenceOrder: plForm.value.sequenceOrder.trim() === '' ? null : Number(plForm.value.sequenceOrder),
    note: plForm.value.note || null,
  }
  try {
    if (plForm.value.linkId === null) await personApi.linkPlace(props.entityId, body)
    else await personApi.updatePlaceLink(props.entityId, plForm.value.linkId, body)
    plOpen.value = false
    await load(props.entityId)
    emit('changed')
  } catch (e) {
    err.value = (e as Error).message
  }
}

async function removePl(r: PersonPlaceRow) {
  if (props.entityId === null) return
  if (!window.confirm(`确认解除与地点「${r.placeName}」的关联？（不会删除地点本体）`)) return
  try {
    await personApi.unlinkPlace(props.entityId, r.linkId)
    await load(props.entityId)
    emit('changed')
  } catch (e) {
    err.value = (e as Error).message
  }
}
</script>

<template>
  <div class="editor">
    <div v-if="loading" class="m2-empty">加载中…</div>
    <template v-else>
      <h3 class="title">
        {{ entityId === null ? '新增历史人物' : `人物 #${entityId}` }}
        <span v-if="detail" class="tiny dim">{{ detail.recordStatus }}</span>
      </h3>

      <p v-if="err" class="m2-alert">{{ err }}</p>
      <p v-if="msg" class="tiny" style="color: #256b3a">{{ msg }}</p>

      <div class="m2-grid2">
        <div class="m2-field">
          <label>规范姓名 <span class="req">*</span></label>
          <input v-model="form.canonicalName" type="text" placeholder="如 孔丘" />
        </div>
        <div class="m2-field">
          <label>语言</label>
          <input v-model="form.canonicalNameLang" type="text" placeholder="zh" />
        </div>
      </div>
      <div class="m2-field">
        <label>简介</label>
        <textarea v-model="form.description" />
      </div>

      <div class="m2-sub">生卒时间（可留空）</div>
      <div class="m2-grid2">
        <div class="m2-field">
          <label>出生年</label>
          <AstroYear v-model="form.birth" />
        </div>
        <div class="m2-field">
          <label>出生精度</label>
          <select v-model="form.birthPrecision">
            <option v-for="p in PRECISIONS" :key="p.value" :value="p.value">{{ p.label }}</option>
          </select>
        </div>
      </div>
      <div class="m2-field">
        <label>生年原始表述</label>
        <input v-model="form.birthOriginalText" type="text" placeholder="如 鲁襄公二十二年（照原文，不改写）" />
      </div>
      <div class="m2-grid2">
        <div class="m2-field">
          <label>去世年</label>
          <AstroYear v-model="form.death" />
        </div>
        <div class="m2-field">
          <label>去世精度</label>
          <select v-model="form.deathPrecision">
            <option v-for="p in PRECISIONS" :key="p.value" :value="p.value">{{ p.label }}</option>
          </select>
        </div>
      </div>
      <div class="m2-field">
        <label>卒年原始表述</label>
        <input v-model="form.deathOriginalText" type="text" />
      </div>

      <div class="m2-grid2">
        <div class="m2-field">
          <label>记录状态</label>
          <select v-model="form.recordStatus">
            <option value="staging">暂存</option>
            <option value="published">已发布</option>
            <option value="rejected">已否决</option>
          </select>
        </div>
        <div class="m2-field">
          <label>备注</label>
          <input v-model="form.notes" type="text" />
        </div>
      </div>

      <div class="actions">
        <button class="m2-btn primary" :disabled="saving" @click="save">
          {{ saving ? '保存中…' : entityId === null ? '创建人物' : '保存修改' }}
        </button>
        <button v-if="entityId !== null" class="m2-btn danger" @click="removePerson">删除人物</button>
      </div>

      <!-- 名称 -->
      <div v-if="entityId !== null" class="m2-sub">
        姓名 / 别名 / 异体名 <span class="tiny dim">{{ names.length }} 条</span>
        <span class="spacer" />
        <button class="m2-btn sm" @click="openName()">+ 添加名称</button>
      </div>
      <div v-if="entityId !== null">
        <p v-if="names.length === 0 && !nameOpen" class="m2-empty">还没有名称行（规范姓名已在主表）</p>
        <div v-for="n in names" :key="n.personNameId" class="m2-row">
          <span class="grow">
            <strong>{{ n.nameText }}</strong>
            <span class="tiny dim">
              · {{ NAME_TYPES.find((t) => t.v === n.nameType)?.t ?? n.nameType }}
              · {{ n.nameLang || '语言未填' }}
              <template v-if="n.transliterationScheme"> · {{ n.transliterationScheme }}</template>
            </span>
          </span>
          <span class="acts">
            <button class="m2-btn sm" @click="openName(n)">编辑</button>
            <button class="m2-btn sm danger" @click="removeName(n)">删除</button>
          </span>
        </div>
        <div v-if="nameOpen" class="subform">
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
            <div v-if="nameForm.nameType === 'transliteration'" class="m2-field">
              <label>转写方案</label>
              <input v-model="nameForm.transliterationScheme" type="text" placeholder="pinyin" />
            </div>
          </div>
          <div class="actions">
            <button class="m2-btn primary" @click="saveName">保存名称</button>
            <button class="m2-btn" @click="nameOpen = false">取消</button>
          </div>
        </div>
      </div>

      <!-- 关联事件 -->
      <div v-if="entityId !== null" class="m2-sub">
        相关事件 <span class="tiny dim">{{ events.length }} 条</span>
        <span class="spacer" />
        <button class="m2-btn sm" @click="openEv()">+ 关联事件</button>
      </div>
      <div v-if="entityId !== null">
        <p v-if="events.length === 0 && !evOpen" class="m2-empty">还没有关联事件</p>
        <div v-for="r in events" :key="r.linkId" class="m2-row">
          <span class="grow">
            <strong>{{ r.title }}</strong>
            <span class="tiny dim">
              · 角色 {{ r.role }} · {{ formatRange(r.startYearAstro, r.endYearAstro, r.timePrecision) }}
              <template v-if="r.validFromYearAstro !== null || r.validToYearAstro !== null">
                · 关系期 {{ formatRange(r.validFromYearAstro, r.validToYearAstro) }}
              </template>
            </span>
          </span>
          <span class="acts">
            <button class="m2-btn sm" @click="openEv(r)">编辑</button>
            <button class="m2-btn sm danger" @click="removeEv(r)">解除</button>
          </span>
        </div>
        <div v-if="evOpen" class="subform">
          <div class="m2-field">
            <label>关联事件 <span class="req">*</span></label>
            <div class="pickrow">
              <input :value="evForm.eventTitle" type="text" readonly placeholder="点击选择事件" />
              <button class="m2-btn" @click="pickerEvent = true">选择事件</button>
            </div>
          </div>
          <div class="m2-field">
            <label>人物在事件中的角色 <span class="req">*</span></label>
            <input v-model="evForm.role" type="text" placeholder="如 participant / commander / host" />
          </div>
          <div class="m2-grid2">
            <div class="m2-field">
              <label>关系有效期起（可空）</label>
              <AstroYear v-model="evForm.validFrom" />
            </div>
            <div class="m2-field">
              <label>关系有效期止（可空）</label>
              <AstroYear v-model="evForm.validTo" />
            </div>
          </div>
          <div class="m2-field">
            <label>说明</label>
            <input v-model="evForm.note" type="text" />
          </div>
          <div class="actions">
            <button class="m2-btn primary" @click="saveEv">保存关联</button>
            <button class="m2-btn" @click="evOpen = false">取消</button>
          </div>
        </div>
      </div>

      <!-- 活动地点 -->
      <div v-if="entityId !== null" class="m2-sub">
        活动地点 <span class="tiny dim">{{ places.length }} 条</span>
        <span class="spacer" />
        <button class="m2-btn sm" @click="openPl()">+ 关联地点</button>
      </div>
      <div v-if="entityId !== null">
        <p v-if="places.length === 0 && !plOpen" class="m2-empty">还没有活动地点</p>
        <div v-for="r in places" :key="r.linkId" class="m2-row">
          <span class="grow">
            <strong>{{ r.placeName }}</strong>
            <span class="tiny dim">
              · {{ r.relationType }}
              · {{ formatRange(r.startYearAstro, r.endYearAstro, r.timePrecision) }}
              <template v-if="r.sequenceOrder !== null"> · 序 {{ r.sequenceOrder }}</template>
            </span>
          </span>
          <span class="acts">
            <button
              v-if="r.lon !== null && r.lat !== null"
              class="m2-btn sm"
              @click="emit('locate', r.lon!, r.lat!)"
            >
              看地图
            </button>
            <button class="m2-btn sm" @click="openPl(r)">编辑</button>
            <button class="m2-btn sm danger" @click="removePl(r)">解除</button>
          </span>
        </div>
        <div v-if="plOpen" class="subform">
          <div class="m2-field">
            <label>关联地点 <span class="req">*</span></label>
            <div class="pickrow">
              <input :value="plForm.placeName" type="text" readonly placeholder="点击选择地点" />
              <button class="m2-btn" @click="pickerPlace = true">选择地点</button>
            </div>
          </div>
          <div class="m2-grid2">
            <div class="m2-field">
              <label>关系类型 <span class="req">*</span></label>
              <input v-model="plForm.relationType" type="text" placeholder="birthplace / residence / activity" />
            </div>
            <div class="m2-field">
              <label>时间判定</label>
              <select v-model="plForm.timePrecision">
                <option v-for="p in PRECISIONS" :key="p.value" :value="p.value">{{ p.label }}</option>
              </select>
            </div>
          </div>
          <div v-if="plForm.timePrecision !== 'unknown'" class="m2-grid2">
            <div class="m2-field">
              <label>活动起始年</label>
              <AstroYear v-model="plForm.start" />
            </div>
            <div class="m2-field">
              <label>活动结束年（可空 = 开放区间）</label>
              <AstroYear v-model="plForm.end" />
            </div>
          </div>
          <div class="m2-grid2">
            <div class="m2-field">
              <label>顺序（可空）</label>
              <input v-model="plForm.sequenceOrder" type="text" placeholder="1, 2, 3…" />
            </div>
            <div class="m2-field">
              <label>说明</label>
              <input v-model="plForm.note" type="text" />
            </div>
          </div>
          <div class="actions">
            <button class="m2-btn primary" @click="savePl">保存关联</button>
            <button class="m2-btn" @click="plOpen = false">取消</button>
          </div>
        </div>
      </div>

      <p v-if="entityId === null" class="m2-hint">保存后即可添加别名、关联事件与活动地点。</p>

      <ObjectPicker
        :open="pickerEvent"
        kind="event"
        title="选择事件"
        :exclude-ids="evForm.linkId === null ? events.map((e) => e.eventId) : []"
        @close="pickerEvent = false"
        @pick="onPickEvent"
      />
      <ObjectPicker
        :open="pickerPlace"
        kind="place"
        title="选择活动地点"
        @close="pickerPlace = false"
        @pick="onPickPlace"
      />
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
.pickrow { display: flex; gap: 6px; }
.pickrow input { flex: 1; }
</style>
