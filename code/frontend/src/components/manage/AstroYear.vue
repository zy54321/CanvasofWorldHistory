<script setup lang="ts">
/**
 * 单个年份输入：界面用「公元前/公元后 + 正整数」，内部换算成天文学纪年整数。
 * 绝不显示「公元 0 年」：BCE 1 对应的内部 0 会原样回填为 BCE 1。
 */
import { computed, ref, watch } from 'vue'
import { fromAstro, toAstro, type Era } from '../../time'

const props = defineProps<{
  modelValue: number | null
  placeholder?: string
  disabled?: boolean
}>()
const emit = defineEmits<{ (e: 'update:modelValue', v: number | null): void }>()

const era = ref<Era>('CE')
const yearText = ref<string>('')

function syncFromModel(v: number | null) {
  if (v === null || v === undefined) {
    yearText.value = ''
    return
  }
  const p = fromAstro(v)
  era.value = p.era
  yearText.value = String(p.year)
}

watch(() => props.modelValue, syncFromModel, { immediate: true })

function commit() {
  const t = yearText.value.trim()
  if (!t) {
    emit('update:modelValue', null)
    return
  }
  if (!/^\d+$/.test(t) || Number(t) < 1) {
    // 非法输入不静默改成 0，保持原地等待修正
    return
  }
  emit('update:modelValue', toAstro(era.value, Number(t)))
}

function onEraChange() {
  commit()
}

const preview = computed(() => {
  if (props.modelValue === null || props.modelValue === undefined) return '未填写 = 时间未知'
  const p = fromAstro(props.modelValue)
  const label = p.era === 'BCE' ? `公元前 ${p.year} 年` : `公元 ${p.year} 年`
  return `${label}（内部整数 ${props.modelValue}）`
})
</script>

<template>
  <div class="astro-year">
    <div class="row">
      <select v-model="era" :disabled="disabled" @change="onEraChange">
        <option value="BCE">公元前</option>
        <option value="CE">公元</option>
      </select>
      <input
        v-model="yearText"
        type="text"
        inputmode="numeric"
        :placeholder="placeholder ?? '年份，如 551'"
        :disabled="disabled"
        @input="commit"
        @blur="commit"
      />
      <button
        v-if="yearText"
        type="button"
        class="clear"
        :disabled="disabled"
        title="清空（= 时间未知）"
        @click="((yearText = ''), emit('update:modelValue', null))"
      >
        ✕
      </button>
    </div>
    <p class="hint">{{ preview }}</p>
  </div>
</template>

<style scoped>
.astro-year { display: flex; flex-direction: column; gap: 3px; }
.row { display: flex; gap: 5px; align-items: center; }
select, input {
  font: inherit;
  font-size: 13px;
  border: 1px solid var(--line);
  border-radius: 7px;
  padding: 6px 8px;
  background: #fff;
  color: var(--ink);
}
select { flex: 0 0 86px; }
input { flex: 1; min-width: 0; }
.clear {
  border: 1px solid var(--line);
  background: #fff;
  border-radius: 6px;
  padding: 4px 7px;
  font-size: 11px;
  color: var(--ink-3);
}
.hint { margin: 0; font-size: 10.5px; color: var(--ink-3); }
</style>
