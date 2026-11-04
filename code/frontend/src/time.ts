/**
 * 天文纪年（Astronomical Year Numbering）工具。
 *
 * 后端只存整数，绝不解析「公元前 384 年」这类文本；换算只在这一处做，
 * 避免前端各处各写一套导致漂移。
 *
 *   公元前 n 年 → 1 - n      （BCE 1 → 0）
 *   公元后 n 年 → n          （CE 1   → 1）
 *
 * 界面规则：不显示「公元 0 年」——内部 0 一律显示为「公元前 1 年」。
 */

export type Era = 'BCE' | 'CE'
export type Precision = 'exact' | 'approximate' | 'range' | 'unknown'

export interface YearParts {
  era: Era
  year: number
}

export const PRECISIONS: { value: Precision; label: string }[] = [
  { value: 'exact', label: '确切' },
  { value: 'approximate', label: '约' },
  { value: 'range', label: '区间/范围' },
  { value: 'unknown', label: '未知' },
]

export function precisionLabel(p: string | null | undefined): string {
  return PRECISIONS.find((x) => x.value === p)?.label ?? p ?? '未知'
}

/** 界面年份 → 内部整数 */
export function toAstro(era: Era, year: number): number {
  return era === 'BCE' ? 1 - year : year
}

/** 内部整数 → 界面年份（永不给 0 年） */
export function fromAstro(astro: number): YearParts {
  if (astro <= 0) {
    return { era: 'BCE', year: 1 - astro }
  }
  return { era: 'CE', year: astro }
}

/** 单个年份显示；null 显示为「—」 */
export function formatYear(astro: number | null | undefined): string {
  if (astro === null || astro === undefined) return '—'
  const p = fromAstro(astro)
  return p.era === 'BCE' ? `公元前 ${p.year} 年` : `公元 ${p.year} 年`
}

/** 紧凑显示（列表里用） */
export function formatYearShort(astro: number | null | undefined): string {
  if (astro === null || astro === undefined) return '—'
  const p = fromAstro(astro)
  return p.era === 'BCE' ? `前${p.year}` : `${p.year}`
}

/**
 * 区间显示。端点包含式：start === end 表示单年。
 * 结束年为空表示「只知起点」的开放区间。
 */
export function formatRange(
  start: number | null | undefined,
  end: number | null | undefined,
  precision?: string | null,
): string {
  if (start === null || start === undefined) {
    if (end === null || end === undefined) return '时间未知'
    return `至 ${formatYearShort(end)}`
  }
  const head = precision === 'approximate' ? '约 ' : ''
  if (end === null || end === undefined) return `${head}${formatYearShort(start)} 起（终点未知）`
  if (start === end) return `${head}${formatYearShort(start)}`
  return `${head}${formatYearShort(start)} – ${formatYearShort(end)}`
}

/** 解析用户在「年份」输入框里敲的内容，只接受正整数 */
export function parseYearInput(raw: string): { ok: true; year: number } | { ok: false; reason: string } {
  const t = raw.trim()
  if (!t) return { ok: false, reason: '请填写年份数字' }
  if (!/^\d+$/.test(t)) return { ok: false, reason: '年份必须是正整数（公元前请选 BCE 并填正数）' }
  const n = Number(t)
  if (n < 1) return { ok: false, reason: '年份从 1 起算（没有公元前 0 年）' }
  if (n > 99999) return { ok: false, reason: '年份过大' }
  return { ok: true, year: n }
}

// ==========================================================================
// M3 时间轴：窗口与跨度
// 所有运算都在天文学纪年整数上做，显示时才转成「公元前/公元」。
// 区间一律端点包含式：跨度 10 年、起点 -499（前500）→ 覆盖 -499..-490（前500–前491）。
// ==========================================================================

export type Span = 1 | 10 | 100

export const SPANS: { value: Span; label: string }[] = [
  { value: 1, label: '1 年' },
  { value: 10, label: '10 年' },
  { value: 100, label: '100 年' },
]

/** 允许的时间边界（内部整数）：前3000年 ~ 公元2100年。 */
export const MIN_ASTRO = -2999
export const MAX_ASTRO = 2100

export function clampFrom(from: number, span: number): number {
  const lo = MIN_ASTRO
  const hi = MAX_ASTRO - span + 1
  return Math.min(Math.max(from, lo), Math.max(lo, hi))
}

/** 窗口结束年（包含式） */
export function windowEnd(from: number, span: number): number {
  return from + span - 1
}

/** 按跨度整数倍平移（dir 为正向右=未来） */
export function shiftFrom(from: number, span: number, steps: number): number {
  return clampFrom(from + steps * span, span)
}

/** 「公元前 500 年」 / 「公元前 500 年 – 前 491 年」 / 「公元前 5 年 – 公元 5 年」 */
export function formatWindow(from: number, span: number): string {
  if (span <= 1) return formatYear(from)
  const end = windowEnd(from, span)
  const a = fromAstro(from)
  const b = fromAstro(end)
  // 跨公元前后：两端都写全，避免「前 5 – 5 年」这种歧义
  if (a.era !== b.era) return `${formatYear(from)} – ${formatYear(end)}`
  return a.era === 'BCE'
    ? `公元前 ${a.year} 年 – 前 ${b.year} 年`
    : `公元 ${a.year} 年 – ${b.year} 年`
}

/** 刻度用的极短标签：前500 / 500 */
export function shortYear(astro: number): string {
  return astro <= 0 ? `前${1 - astro}` : String(astro)
}

/** 时刻标签（矩阵列表头用，紧凑） */
export function columnLabel(astro: number): string {
  return formatYearShort(astro)
}
