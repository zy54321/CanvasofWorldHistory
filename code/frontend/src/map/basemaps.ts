import type { StyleSpecification } from 'maplibre-gl'

export type StyleId = 'outdoor' | 'streets' | 'satellite' | 'hybrid'

export interface StyleOption {
  id: StyleId
  label: string
  /** MapTiler 官方式名 */
  maptiler: string
}

export const STYLE_OPTIONS: StyleOption[] = [
  { id: 'outdoor', label: 'Outdoor', maptiler: 'outdoor-v2' },
  { id: 'streets', label: 'Streets', maptiler: 'streets-v2' },
  { id: 'satellite', label: 'Satellite', maptiler: 'satellite' },
  { id: 'hybrid', label: 'Hybrid', maptiler: 'hybrid' },
]

/**
 * MapTiler key 的取值顺序：
 *   1. 运行时注入：部署时由 config.js 提供 window.__ENV__.MAPTILER_KEY
 *      —— 正式 Release 包不含任何密钥，部署后放一个 config.js 即可。
 *   2. 构建期内联：开发态（vite dev）从 .env.dev 注入 __MAPTILER_KEY__。
 *   3. 空字符串 → 走无底图降级，界面明确提示，不伪装成功。
 */
function resolveMapTilerKey(): string {
  const runtime = (window as unknown as { __ENV__?: { MAPTILER_KEY?: string } }).__ENV__
  if (runtime && typeof runtime.MAPTILER_KEY === 'string' && runtime.MAPTILER_KEY.length > 0) {
    return runtime.MAPTILER_KEY
  }
  return typeof __MAPTILER_KEY__ === 'string' ? __MAPTILER_KEY__ : ''
}

export const MAPTILER_KEY: string = resolveMapTilerKey()

export const HAS_BASEMAP = MAPTILER_KEY.length > 0

export function styleUrl(id: StyleId): string {
  const opt = STYLE_OPTIONS.find((s) => s.id === id) ?? STYLE_OPTIONS[0]
  return `https://api.maptiler.com/maps/${opt.maptiler}/style.json?key=${encodeURIComponent(MAPTILER_KEY)}`
}

/**
 * 无 API Key 时的降级底图：纯色背景 + 经纬网。
 * 目的不是替代正式底图，而是让「地点图层 + 交互 + 空间查询」仍可验证，
 * 并在界面上明确标注底图不可用，绝不伪装成加载成功。
 *
 * 四种样式各有不同的底色与网格密度，以便在离线状态下仍能验证
 * 「样式切换 + 视野保持」这条交互链路本身。
 */
const FALLBACK_PALETTE: Record<StyleId, { bg: string; line: string; step: number }> = {
  outdoor: { bg: '#e9eef3', line: '#a9b8c7', step: 30 },
  streets: { bg: '#f2ede4', line: '#c0b2a0', step: 15 },
  satellite: { bg: '#2b3138', line: '#5a6672', step: 30 },
  hybrid: { bg: '#1d2228', line: '#4b5b69', step: 10 },
}

export function fallbackStyle(id: StyleId = 'outdoor'): StyleSpecification {
  const pal = FALLBACK_PALETTE[id] ?? FALLBACK_PALETTE.outdoor
  const meridians: [number, number][][] = []
  const parallels: [number, number][][] = []
  for (let lon = -180; lon <= 180; lon += pal.step) {
    const line: [number, number][] = []
    for (let lat = -85; lat <= 85; lat += 5) line.push([lon, lat])
    meridians.push(line)
  }
  for (let lat = -90 + pal.step; lat < 90; lat += pal.step) {
    const line: [number, number][] = []
    for (let lon = -180; lon <= 180; lon += 5) line.push([lon, lat])
    parallels.push(line)
  }
  const features = [
    ...meridians.map((c) => ({
      type: 'Feature' as const,
      properties: { kind: 'meridian' },
      geometry: { type: 'LineString' as const, coordinates: c },
    })),
    ...parallels.map((c) => ({
      type: 'Feature' as const,
      properties: { kind: 'parallel' },
      geometry: { type: 'LineString' as const, coordinates: c },
    })),
  ]

  return {
    version: 8,
    name: 'offline-graticule',
    sources: {
      graticule: {
        type: 'geojson',
        data: { type: 'FeatureCollection', features } as never,
      },
    },
    layers: [
      { id: 'bg', type: 'background', paint: { 'background-color': pal.bg } },
      {
        id: 'grat',
        type: 'line',
        source: 'graticule',
        paint: { 'line-color': pal.line, 'line-width': 1 },
      },
    ],
  } as unknown as StyleSpecification
}

export interface RegionPreset {
  id: string
  label: string
  center: [number, number]
  zoom: number
}

export const REGION_PRESETS: RegionPreset[] = [
  { id: 'world', label: '全球', center: [20, 20], zoom: 1.4 },
  { id: 'china', label: '中国', center: [108, 32], zoom: 3.8 },
  { id: 'europe', label: '欧洲', center: [14, 49], zoom: 3.9 },
  { id: 'namerica', label: '北美', center: [-98, 42], zoom: 3.2 },
  { id: 'mideast', label: '中东', center: [45, 29], zoom: 4.2 },
]