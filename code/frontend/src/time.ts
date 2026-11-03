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
