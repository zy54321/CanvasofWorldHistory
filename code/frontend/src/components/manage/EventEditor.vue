<script setup lang="ts">
/**
 * 事件编辑器：主表 + 关联政权 + 关联人物 + 关联地点。
 * 时间允许完全未知；也允许只知起点的开放区间。
 *
 * 政权关联（M3）只做「搜索选择 + 添加 + 解除 + 必要时新建政权」，
 * 建政权的入口放在这里而不是另建一套政权管理平台。
 */
import { computed, ref, watch } from 'vue'
import AstroYear from './AstroYear.vue'
import ObjectPicker, { type PickedItem } from './ObjectPicker.vue'
import { eventApi, polityApi } from '../../api'
import type {
  EventDetail,
  EventPersonRow,
  EventPlaceRow,
  EventPolityRow,
  PolityRegion,
  PolityStatus,
} from '../../types'
import { PRECISIONS, formatRange } from '../../time'

const props = defineProps<{ entityId: number | null }>()
const emit = defineEmits<{
  (e: 'saved', id: number): void
  (e: 'deleted'): void
  (e: 'changed'): void
  (e: 'locate', lon: number, lat: number): void
}>()

const detail = ref<EventDetail | null>(null)
const loading = ref(false)
const saving = ref(false)
const err = ref<string | null>(null)
const msg = ref<string | null>(null)

const form = ref({
  title: '',
  summary: '',
  description: '',
  start: null as number | null,
  end: null as number | null,
  timePrecision: 'unknown',
  timeOriginalText: '',
  timeNote: '',
  eventType: 'unknown',
  notes: '',
  recordStatus: 'staging',
})

const persons = computed<EventPersonRow[]>(() => detail.value?.persons ?? [])
const places = computed<EventPlaceRow[]>(() => detail.value?.places ?? [])
const polities = computed<EventPolityRow[]>(() => detail.value?.polities ?? [])

// 关联政权（M3）
const poOpen = ref(false)
const pickerPolity = ref(false)
const poForm = ref({
  polityId: null as number | null,
  polityName: '',
  role: '',
  note: '',
})
const newPoOpen = ref(false)
const regions = ref<PolityRegion[]>([])
const newPo = ref({
  name: '',
  regionCode: 'east_asia',
  start: null as number | null,
  end: null as number | null,
  recordStatus: 'staging' as PolityStatus,
})

/** 状态文案：只做识别，不做审核流 */
const POLITY_STATUS: { value: PolityStatus; label: string; hint: string }[] = [
  { value: 'staging', label: '暂存', hint: '进矩阵（本系统所有录入默认状态）' },
  { value: 'published', label: '已发布', hint: '进矩阵' },
  { value: 'rejected', label: '已否决', hint: '不进矩阵；事件与关联都保留' },
]

function statusLabel(s: PolityStatus): string {
  return POLITY_STATUS.find((x) => x.value === s)?.label ?? s
}

/** 改状态：只影响矩阵是否显示该政权行，不删事件、不删关联 */
async function changePoStatus(r: EventPolityRow, value: string) {
  err.value = null
  try {
    await polityApi.updateStatus(r.polityId, value)
    await load(props.entityId as number)
    emit('changed')
  } catch (e) {
    err.value = (e as Error).message
  }
}

async function ensureRegions() {
  if (regions.value.length) return
  try {
    regions.value = await polityApi.regions()
    if (!regions.value.some((r) => r.code === newPo.value.regionCode) && regions.value.length) {
      newPo.value.regionCode = regions.value[0].code
    }
  } catch (e) {
    err.value = `政权地区列表加载失败：${(e as Error).message}`
  }
}

function openPo() {
  err.value = null
  poOpen.value = true
  poForm.value = { polityId: null, polityName: '', role: '', note: '' }
  void ensureRegions()
}

function onPickPolity(it: PickedItem) {
  poForm.value.polityId = it.id
  poForm.value.polityName = it.name
  pickerPolity.value = false
}

async function savePo() {
  if (props.entityId === null) return
  err.value = null
  if (poForm.value.polityId === null) {
    err.value = '请先选择要关联的历史政权'
    return
  }
  try {
    await polityApi.link(props.entityId, {
      polityId: poForm.value.polityId,
      role: poForm.value.role || null,
      note: poForm.value.note || null,
    })
    poOpen.value = false
    await load(props.entityId)
    emit('changed')
  } catch (e) {
    err.value = (e as Error).message
  }
}

async function removePo(r: EventPolityRow) {
  if (props.entityId === null) return
  if (!window.confirm(`确认解除与政权「${r.polityName}」的关联？（不会删除政权或事件本体）`)) return
  try {
    await polityApi.unlink(props.entityId, r.linkId)
    await load(props.entityId)
    emit('changed')
  } catch (e) {
    err.value = (e as Error).message
  }
}

async function createPolity() {
  err.value = null
  if (!newPo.value.name.trim()) {
    err.value = '请填写政权名称'
    return
  }
  // V7：只填起始年或只填结束年都合法；两端都填时才要求顺序正确
  if (
    newPo.value.start !== null &&
    newPo.value.end !== null &&
    newPo.value.start > newPo.value.end
  ) {
    err.value = '存在起始年不得晚于结束年'
    return
  }
  try {
    const p = await polityApi.create({
      name: newPo.value.name.trim(),
      regionCode: newPo.value.regionCode,
      startYearAstro: newPo.value.start,
      endYearAstro: newPo.value.end,
      recordStatus: newPo.value.recordStatus,
    })
    poForm.value.polityId = p.polityId
    poForm.value.polityName = p.name
    newPoOpen.value = false
    // 新建即选中：直接把关联表单打开，省掉「再搜一次」的步骤
    poOpen.value = true
    newPo.value = {
      name: '',
      regionCode: newPo.value.regionCode,
      start: null,
      end: null,
      recordStatus: 'staging',
    }
    msg.value = `已新建政权「${p.name}」，可直接保存关联`
  } catch (e) {
    err.value = (e as Error).message
  }
}

// 关联人物
const pOpen = ref(false)
const pickerPerson = ref(false)
const pForm = ref({
  linkId: null as number | null,
  personId: null as number | null,
  personName: '',
  role: 'participant',
  validFrom: null as number | null,
  validTo: null as number | null,
  note: '',
})

// 关联地点
const lOpen = ref(false)
const pickerPlace = ref(false)
const lForm = ref({
  linkId: null as number | null,
  placeId: null as number | null,
  placeName: '',
  locationRole: 'unknown',
  validFrom: null as number | null,
  validTo: null as number | null,
  note: '',
})

async function load(id: number) {
  loading.value = true
  err.value = null
  try {
    const d = await eventApi.detail(id)
    detail.value = d
    form.value = {
      title: d.title,
      summary: d.summary ?? '',
      description: d.description ?? '',
      start: d.startYearAstro,
      end: d.endYearAstro,
      timePrecision: d.timePrecision,
      timeOriginalText: d.timeOriginalText ?? '',
      timeNote: d.timeNote ?? '',
      eventType: d.eventType,
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
    pOpen.value = false
    lOpen.value = false
    if (id === null) {
      detail.value = null
      form.value = {
        title: '', summary: '', description: '',
        start: null, end: null, timePrecision: 'unknown',
        timeOriginalText: '', timeNote: '', eventType: 'unknown',
        notes: '', recordStatus: 'staging',
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
  if (!form.value.title.trim()) {
    err.value = '事件标题不能为空'
    return
  }
  const p = form.value.timePrecision
  if (p === 'unknown' && (form.value.start !== null || form.value.end !== null)) {
    err.value = '时间判定为「未知」时不应填写年份'
    return
  }
  if (p !== 'unknown' && form.value.start === null) {
    err.value = '时间判定非「未知」时必须填写开始年份'
    return
  }
  if (form.value.start !== null && form.value.end !== null && form.value.start > form.value.end) {
    err.value = '开始年不得晚于结束年'
    return
  }
  saving.value = true
  try {
    const body = {
      title: form.value.title.trim(),
      summary: form.value.summary || null,
      description: form.value.description || null,
      startYearAstro: form.value.start,
      endYearAstro: form.value.end,
      timePrecision: form.value.timePrecision,
      timeOriginalText: form.value.timeOriginalText || null,
      timeNote: form.value.timeNote || null,
      eventType: form.value.eventType.trim() || 'unknown',
      notes: form.value.notes || null,
      recordStatus: form.value.recordStatus,
    }
    if (props.entityId === null) {
      const r = await eventApi.create(body)
      emit('saved', r.eventId)
    } else {
      await eventApi.update(props.entityId, body)
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

async function removeEvent() {
  if (props.entityId === null) return
  if (!window.confirm(`确认删除事件「${form.value.title}」？其关联人物与关联地点记录会一并删除，人物与地点本体不受影响。`)) return
  err.value = null
  try {
    await eventApi.remove(props.entityId)
    emit('deleted')
  } catch (e) {
    err.value = (e as Error).message
  }
}

// ---------------------------------------------------------------- 关联人物
function openP(r?: EventPersonRow) {
  err.value = null
  pOpen.value = true
  pForm.value = r
    ? { linkId: r.linkId, personId: r.personId, personName: r.personName, role: r.role,
        validFrom: r.validFromYearAstro, validTo: r.validToYearAstro, note: r.note ?? '' }
    : { linkId: null, personId: null, personName: '', role: 'participant',
        validFrom: null, validTo: null, note: '' }
}

function onPickPerson(it: PickedItem) {
  pForm.value.personId = it.id
  pForm.value.personName = it.name
  pickerPerson.value = false
}

async function saveP() {
  if (props.entityId === null) return
  err.value = null
  if (pForm.value.personId === null) {
    err.value = '请先选择要关联的人物'
    return
  }
  if (!pForm.value.role.trim()) {
    err.value = '请填写人物在事件中的角色（可用 unknown）'
    return
  }
  const body = {
    personId: pForm.value.personId,
    role: pForm.value.role.trim(),
    validFromYearAstro: pForm.value.validFrom,
    validToYearAstro: pForm.value.validTo,
    note: pForm.value.note || null,
  }
  try {
    if (pForm.value.linkId === null) await eventApi.linkPerson(props.entityId, body)
    else await eventApi.updatePersonLink(props.entityId, pForm.value.linkId, body)
    pOpen.value = false
    await load(props.entityId)
    emit('changed')
  } catch (e) {
    err.value = (e as Error).message
  }
}

async function removeP(r: EventPersonRow) {
  if (props.entityId === null) return
  if (!window.confirm(`确认解除与人物「${r.personName}」的关联？（不会删除人物本体）`)) return
  try {
    await eventApi.unlinkPerson(props.entityId, r.linkId)
    await load(props.entityId)
    emit('changed')
  } catch (e) {
    err.value = (e as Error).message
  }
}

// ---------------------------------------------------------------- 关联地点
function openL(r?: EventPlaceRow) {
  err.value = null
  lOpen.value = true
  lForm.value = r
    ? { linkId: r.linkId, placeId: r.placeId, placeName: r.placeName, locationRole: r.locationRole,
        validFrom: r.validFromYearAstro, validTo: r.validToYearAstro, note: r.note ?? '' }
    : { linkId: null, placeId: null, placeName: '', locationRole: 'unknown',
        validFrom: null, validTo: null, note: '' }
}

function onPickPlace2(it: PickedItem) {
  lForm.value.placeId = it.id
  lForm.value.placeName = it.name
  pickerPlace.value = false
}

async function saveL() {
  if (props.entityId === null) return
  err.value = null
  if (lForm.value.placeId === null) {
    err.value = '请先选择要关联的地点'
    return
  }
  if (!lForm.value.locationRole.trim()) {
    err.value = '请填写地点在事件中的角色（可用 unknown）'
    return
  }
  const body = {
    placeId: lForm.value.placeId,
    locationRole: lForm.value.locationRole.trim(),
    validFromYearAstro: lForm.value.validFrom,
    validToYearAstro: lForm.value.validTo,
    note: lForm.value.note || null,
  }
  try {
    if (lForm.value.linkId === null) await eventApi.linkPlace(props.entityId, body)
    else await eventApi.updatePlaceLink(props.entityId, lForm.value.linkId, body)
    lOpen.value = false
    await load(props.entityId)
    emit('changed')
  } catch (e) {
    err.value = (e as Error).message
  }
}

async function removeL(r: EventPlaceRow) {
  if (props.entityId === null) return
  if (!window.confirm(`确认解除与地点「${r.placeName}」的关联？（不会删除地点本体）`)) return
  try {
    await eventApi.unlinkPlace(props.entityId, r.linkId)
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
        {{ entityId === null ? '新增历史事件' : `事件 #${entityId}` }}
        <span v-if="detail" class="tiny dim">{{ detail.recordStatus }}</span>
      </h3>

      <p v-if="err" class="m2-alert">{{ err }}</p>
      <p v-if="msg" class="tiny" style="color: #256b3a">{{ msg }}</p>

      <div class="m2-field">
        <label>标题 <span class="req">*</span></label>
        <input v-model="form.title" type="text" placeholder="如 孔子适周问礼" />
      </div>
      <div class="m2-field">
        <label>摘要</label>
        <input v-model="form.summary" type="text" />
      </div>
      <div class="m2-field">
        <label>详细描述</label>
        <textarea v-model="form.description" />
      </div>

      <div class="m2-sub">时间（可完全未知）</div>
      <div class="m2-field">
        <label>时间判定</label>
        <select v-model="form.timePrecision">
          <option v-for="p in PRECISIONS" :key="p.value" :value="p.value">{{ p.label }}</option>
        </select>
      </div>
      <div v-if="form.timePrecision !== 'unknown'" class="m2-grid2">
        <div class="m2-field">
          <label>开始年 <span class="req">*</span></label>
          <AstroYear v-model="form.start" />
        </div>
        <div class="m2-field">
          <label>结束年（可空 = 开放区间）</label>
          <AstroYear v-model="form.end" />
        </div>
      </div>
      <p v-else class="m2-hint">时间未知时不接受年份 —— 不为了填时间轴而编造。</p>
      <div class="m2-grid2">
        <div class="m2-field">
          <label>原始时间表述</label>
          <input v-model="form.timeOriginalText" type="text" placeholder="如 鲁昭公二十五年" />
        </div>
        <div class="m2-field">
          <label>时间备注</label>
          <input v-model="form.timeNote" type="text" />
        </div>
      </div>

      <div class="m2-grid2">
        <div class="m2-field">
          <label>事件类型（自由填写）</label>
          <input v-model="form.eventType" type="text" placeholder="political / military / cultural …" />
        </div>
        <div class="m2-field">
          <label>记录状态</label>
          <select v-model="form.recordStatus">
            <option value="staging">暂存</option>
            <option value="published">已发布</option>
            <option value="rejected">已否决</option>
          </select>
        </div>
      </div>
      <div class="m2-field">
        <label>备注</label>
        <input v-model="form.notes" type="text" />
      </div>

      <div class="actions">
        <button class="m2-btn primary" :disabled="saving" @click="save">
          {{ saving ? '保存中…' : entityId === null ? '创建事件' : '保存修改' }}
        </button>
        <button v-if="entityId !== null" class="m2-btn danger" @click="removeEvent">删除事件</button>
      </div>

      <!-- 关联政权（M3，决定事件在时空矩阵里出现在哪一行） -->
      <div v-if="entityId !== null" class="m2-sub">
        历史政权 <span class="tiny dim">{{ polities.length }} 个</span>
        <span class="spacer" />
        <button class="m2-btn sm" @click="openPo()">+ 关联政权</button>
        <button class="m2-btn sm" @click="newPoOpen = !newPoOpen; ensureRegions()">
          {{ newPoOpen ? '取消新建' : '新建政权' }}
        </button>
      </div>
      <div v-if="entityId !== null">
        <p v-if="polities.length === 0 && !poOpen" class="m2-empty">
          还没有关联政权 —— 该事件仍会保留在地图与检索中，但不会出现在时空矩阵
        </p>
        <div v-for="r in polities" :key="r.linkId" class="m2-row">
          <span class="grow">
            <strong>{{ r.polityName }}</strong>
            <span class="tiny dim">
              · {{ r.regionLabel }}
              <template v-if="r.role"> · {{ r.role }}</template>
            </span>
            <span class="po-status" :class="r.recordStatus" :title="POLITY_STATUS.find((x) => x.value === r.recordStatus)?.hint">
              {{ statusLabel(r.recordStatus) }}
            </span>
            <span v-if="r.recordStatus === 'rejected'" class="tiny warn-ink">本政权不进入矩阵</span>
          </span>
          <span class="acts">
            <select
              class="po-state-sel"
              :value="r.recordStatus"
              title="政权状态：暂存/已发布进矩阵，已否决不进矩阵"
              @change="changePoStatus(r, ($event.target as HTMLSelectElement).value)"
            >
              <option v-for="s in POLITY_STATUS" :key="s.value" :value="s.value">{{ s.label }}</option>
            </select>
            <button class="m2-btn sm danger" @click="removePo(r)">解除</button>
          </span>
        </div>

        <div v-if="poOpen" class="subform">
          <div class="m2-field">
            <label>选择历史政权 <span class="req">*</span></label>
            <div class="pickrow">
              <input :value="poForm.polityName" type="text" readonly placeholder="点击搜索并选择政权" />
              <button class="m2-btn" @click="pickerPolity = true">搜索政权</button>
            </div>
          </div>
          <div class="m2-field">
            <label>政权在事件中的角色（可空，自由文本）</label>
            <input v-model="poForm.role" type="text" placeholder="aggressor / defender / participant" />
          </div>
          <div class="m2-field">
            <label>说明</label>
            <input v-model="poForm.note" type="text" />
          </div>
          <div class="actions">
            <button class="m2-btn primary" @click="savePo">保存关联</button>
            <button class="m2-btn" @click="poOpen = false">取消</button>
          </div>
        </div>

        <!-- 新建政权：只有名称与展示地区必填；存在区间可空 -->
        <div v-if="newPoOpen" class="subform">
          <p class="m2-hint">
            政权只作「展示分组」：填名称与展示地区即可，不做疆域与继承关系。
          </p>
          <div class="m2-grid2">
            <div class="m2-field">
              <label>政权名称 <span class="req">*</span></label>
              <input v-model="newPo.name" type="text" placeholder="例如：波斯帝国" />
            </div>
            <div class="m2-field">
              <label>展示地区 <span class="req">*</span></label>
              <select v-model="newPo.regionCode">
                <option v-for="rg in regions" :key="rg.code" :value="rg.code">{{ rg.label }}</option>
              </select>
            </div>
          </div>
          <div class="m2-grid2">
            <div class="m2-field">
              <label>存在起始年（可空）</label>
              <AstroYear v-model="newPo.start" />
            </div>
            <div class="m2-field">
              <label>存在结束年（可空）</label>
              <AstroYear v-model="newPo.end" />
            </div>
          </div>
          <p class="m2-hint">起始年、结束年可以只填一个，也可以都留空；两端都填时必须起始不晚于结束。</p>
          <div class="m2-field">
            <label>状态</label>
            <select v-model="newPo.recordStatus">
              <option v-for="s in POLITY_STATUS" :key="s.value" :value="s.value">
                {{ s.label }} —— {{ s.hint }}
              </option>
            </select>
          </div>
          <div class="actions">
            <button class="m2-btn primary" @click="createPolity">新建并选用</button>
            <button class="m2-btn" @click="newPoOpen = false">取消</button>
          </div>
        </div>
      </div>

      <!-- 关联人物 -->
      <div v-if="entityId !== null" class="m2-sub">
        相关人物 <span class="tiny dim">{{ persons.length }} 人</span>
        <span class="spacer" />
        <button class="m2-btn sm" @click="openP()">+ 关联人物</button>
      </div>
      <div v-if="entityId !== null">
        <p v-if="persons.length === 0 && !pOpen" class="m2-empty">还没有关联人物</p>
        <div v-for="r in persons" :key="r.linkId" class="m2-row">
          <span class="grow">
            <strong>{{ r.personName }}</strong>
            <span class="tiny dim">
              · {{ r.role }}
              <template v-if="r.validFromYearAstro !== null || r.validToYearAstro !== null">
                · 关系期 {{ formatRange(r.validFromYearAstro, r.validToYearAstro) }}
              </template>
            </span>
          </span>
          <span class="acts">
            <button class="m2-btn sm" @click="openP(r)">编辑</button>
            <button class="m2-btn sm danger" @click="removeP(r)">解除</button>
          </span>
        </div>
        <div v-if="pOpen" class="subform">
          <div class="m2-field">
            <label>关联人物 <span class="req">*</span></label>
            <div class="pickrow">
              <input :value="pForm.personName" type="text" readonly placeholder="点击选择人物" />
              <button class="m2-btn" @click="pickerPerson = true">选择人物</button>
            </div>
          </div>
          <div class="m2-field">
            <label>人物在事件中的角色 <span class="req">*</span></label>
            <input v-model="pForm.role" type="text" placeholder="participant / commander / victim" />
          </div>
          <div class="m2-grid2">
            <div class="m2-field">
              <label>关系有效期起（可空）</label>
              <AstroYear v-model="pForm.validFrom" />
            </div>
            <div class="m2-field">
              <label>关系有效期止（可空）</label>
              <AstroYear v-model="pForm.validTo" />
            </div>
          </div>
          <div class="m2-field">
            <label>说明</label>
            <input v-model="pForm.note" type="text" />
          </div>
          <div class="actions">
            <button class="m2-btn primary" @click="saveP">保存关联</button>
            <button class="m2-btn" @click="pOpen = false">取消</button>
          </div>
        </div>
      </div>

      <!-- 关联地点 -->
      <div v-if="entityId !== null" class="m2-sub">
        相关地点 <span class="tiny dim">{{ places.length }} 处</span>
        <span class="spacer" />
        <button class="m2-btn sm" @click="openL()">+ 关联地点</button>
      </div>
      <div v-if="entityId !== null">
        <p v-if="places.length === 0 && !lOpen" class="m2-empty">还没有关联地点</p>
        <div v-for="r in places" :key="r.linkId" class="m2-row">
          <span class="grow">
            <strong>{{ r.placeName }}</strong>
            <span class="tiny dim">
              · {{ r.locationRole }}
              <template v-if="r.lon !== null"> · {{ r.lon.toFixed(2) }}, {{ r.lat?.toFixed(2) }}</template>
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
            <button class="m2-btn sm" @click="openL(r)">编辑</button>
            <button class="m2-btn sm danger" @click="removeL(r)">解除</button>
          </span>
        </div>
        <div v-if="lOpen" class="subform">
          <div class="m2-field">
            <label>关联地点 <span class="req">*</span></label>
            <div class="pickrow">
              <input :value="lForm.placeName" type="text" readonly placeholder="点击选择地点" />
              <button class="m2-btn" @click="pickerPlace = true">选择地点</button>
            </div>
          </div>
          <div class="m2-field">
            <label>地点在事件中的角色 <span class="req">*</span></label>
            <input v-model="lForm.locationRole" type="text" placeholder="origin / battlefield / destination" />
          </div>
          <div class="m2-grid2">
            <div class="m2-field">
              <label>关系有效期起（可空）</label>
              <AstroYear v-model="lForm.validFrom" />
            </div>
            <div class="m2-field">
              <label>关系有效期止（可空）</label>
              <AstroYear v-model="lForm.validTo" />
            </div>
          </div>
          <div class="m2-field">
            <label>说明</label>
            <input v-model="lForm.note" type="text" />
          </div>
          <div class="actions">
            <button class="m2-btn primary" @click="saveL">保存关联</button>
            <button class="m2-btn" @click="lOpen = false">取消</button>
          </div>
        </div>
      </div>

      <p v-if="entityId === null" class="m2-hint">保存后即可关联人物与地点。</p>

      <ObjectPicker
        :open="pickerPerson"
        kind="person"
        title="选择人物"
        @close="pickerPerson = false"
        @pick="onPickPerson"
      />
      <ObjectPicker
        :open="pickerPlace"
        kind="place"
        title="选择地点"
        @close="pickerPlace = false"
        @pick="onPickPlace2"
      />
      <ObjectPicker
        :open="pickerPolity"
        kind="polity"
        title="选择历史政权"
        :exclude-ids="polities.map((x) => x.polityId)"
        @close="pickerPolity = false"
        @pick="onPickPolity"
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

/* 政权状态：暂存/已发布/已否决（只做识别与切换，不做审核流） */
.po-status {
  margin-left: 6px;
  font-size: 10px;
  line-height: 1.4;
  padding: 0 5px;
  border-radius: 3px;
  border: 1px solid var(--line);
  background: #f4f6f8;
  color: var(--ink-3);
  vertical-align: 1px;
}
.po-status.staging { background: #f4f6f8; color: #4a5b6d; }
.po-status.published { background: #eaf3ea; color: #2f6b3a; border-color: #cfe3d2; }
.po-status.rejected { background: #fdf0ee; color: #8c1d16; border-color: #f0cfc9; }
.po-state-sel { font-size: 11px; padding: 2px 4px; height: 24px; }
.warn-ink { color: var(--warn-ink); }
</style>
