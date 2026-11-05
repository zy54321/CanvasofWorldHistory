/**
 * 阶段 A3：前端渲染耗时分离测量。
 * 只测"地图视野变化 → 本应用图层数据到位并可渲染"这一段，
 * 不含底图瓦片（那是第三方 CDN，受网络影响，不能算进业务性能）。
 */
const puppeteer = require('puppeteer-core')
const fs = require('fs')

const BASE = process.argv[2] || 'http://127.0.0.1:5180/'
const OUT = process.argv[3] || 'C:/Users/the_z/AppData/Local/Temp/v1b-shots'
const N = 30
const VIEWS = {
  rome: [12.45, 41.85, 10.6],
  world: [20, 30, 2],
  beijing: [116.5, 39.75, 10],
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

;(async () => {
  fs.mkdirSync(OUT, { recursive: true })
  const browser = await puppeteer.launch({
    executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe',
    headless: 'new',
    args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader', '--no-sandbox'],
    defaultViewport: { width: 1500, height: 950 },
  })
  const page = await browser.newPage()
  await page.goto(BASE, { waitUntil: 'networkidle2', timeout: 60000 })
  await page.waitForFunction(() => !!(window.__map && window.__map.isStyleLoaded()), { timeout: 30000, polling: 200 })
  await sleep(3000)

  const out = {}
  for (const [name, [lon, lat, zoom]] of Object.entries(VIEWS)) {
    const samples = []
    for (let i = 0; i < N + 3; i++) {
      const ms = await page.evaluate(async ({ lon, lat, zoom, flip }) => {
        const m = window.__map
        // 用 setData 的「数据对象引用」判断数据是否已刷新 —— 比要素条数可靠：
        // 同一 bbox 反复跳转时条数可能完全相同，引用则每次 setData 必然换新。
        const src = m.getSource('places')
        const ptx = m.getSource('places-pts')
        const d0 = src?._data
        const p0 = ptx?._data
        const t0 = performance.now()
        m.jumpTo({ center: [lon + (flip ? 0.02 : -0.02), lat], zoom })
        await new Promise((resolve) => {
          const deadline = performance.now() + 8000
          const tick = () => {
            if (src?._data !== d0 || ptx?._data !== p0) {
              requestAnimationFrame(() => requestAnimationFrame(resolve))
            } else if (performance.now() > deadline) resolve()
            else setTimeout(tick, 16)
          }
          tick()
        })
        return performance.now() - t0
      }, { lon, lat, zoom, flip: i % 2 === 1 })
      if (i >= 3) samples.push(ms)
    }
    samples.sort((a, b) => a - b)
    const pick = (p) => samples[Math.min(samples.length - 1, Math.floor((samples.length - 1) * p))]
    const DEBOUNCE = 260  // MapView.scheduleLoad 固定 260ms
    out[name] = {
      n: samples.length,
      p50_ms: +pick(0.5).toFixed(1), p95_ms: +pick(0.95).toFixed(1), max_ms: +samples[samples.length - 1].toFixed(1),
      p50_net_ms: +Math.max(0, pick(0.5) - DEBOUNCE).toFixed(1),
      p95_net_ms: +Math.max(0, pick(0.95) - DEBOUNCE).toFixed(1),
      note: 'front p50/p95 含 scheduleLoad 的 260ms 防抖；*_net 为扣除后净耗时',
    }
    console.log(`${name.padEnd(9)} 前端(含防抖) P50=${out[name].p50_ms}ms P95=${out[name].p95_ms}ms | 净 P50=${out[name].p50_net_ms}ms P95=${out[name].p95_net_ms}ms`)
  }

  fs.writeFileSync(`${OUT}/bench_front.json`, JSON.stringify(out, null, 2))
  await browser.close()
})().catch((e) => { console.error('FATAL', e); process.exit(2) })
