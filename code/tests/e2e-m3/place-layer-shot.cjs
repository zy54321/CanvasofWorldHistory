/**
 * M3 封存轮 · 地图双图层取证截图。
 *
 * 用途：地点图层（M1）与事件图层（M3）同时开启时，两种标记是否真的画出来、
 * 视觉上能否区分、缩放后是否还正常。直接读 MapLibre 的图层状态与渲染命中数，
 * 并落两张截图（全球视角 + 区域视角）。
 *
 * 用法：
 *   node tests/e2e-m3/place-layer-shot.cjs http://127.0.0.1:5180/ ./out
 *   node tests/e2e-m3/place-layer-shot.cjs http://127.0.0.1:5181/ ./out
 */
const puppeteer = require('puppeteer-core')

const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe'
const URL = process.argv[2] || 'http://127.0.0.1:5181/'
const OUT = process.argv[3] || './shots'
const wait = (ms) => new Promise((r) => setTimeout(r, ms))

;(async () => {
  const browser = await puppeteer.launch({
    executablePath: CHROME,
    headless: 'new',
    args: ['--no-sandbox', '--use-gl=swiftshader', '--enable-unsafe-swiftshader'],
    defaultViewport: { width: 1600, height: 900 },
  })
  const page = await browser.newPage()
  const errors = []
  page.on('pageerror', (e) => errors.push(e.message.slice(0, 140)))
  await page.goto(URL, { waitUntil: 'networkidle2', timeout: 60000 })
  await wait(5000)

  const state = () =>
    page.evaluate(() => {
      const m = window.__map
      const vis = (l) => (m.getLayer(l) ? m.getLayoutProperty(l, 'visibility') || 'visible' : 'missing')
      const src = (s) => {
        try {
          return m.querySourceFeatures(s).length
        } catch {
          return -1
        }
      }
      return {
        places: { visible: vis('places-dot'), source: src('places'),
                  rendered: m.queryRenderedFeatures({ layers: ['places-dot'] }).length,
                  fill: m.getPaintProperty('places-dot', 'circle-color') },
        events: { visible: vis('events-point'), source: src('events'),
                  rendered: m.queryRenderedFeatures({ layers: ['events-point'] }).length,
                  fill: m.getPaintProperty('events-point', 'circle-color') },
        center: m.getCenter().toArray().map((n) => +n.toFixed(2)),
        zoom: +m.getZoom().toFixed(2),
      }
    })

  const world = await state()
  await page.screenshot({ path: `${OUT}/30_two_layers_world.png` })
  console.log('全球视角:', JSON.stringify(world))

  // 区域视角：地中海东岸（演示地点与事件都集中在这里）
  await page.evaluate(() => window.__map.easeTo({ center: [35, 34], zoom: 4.2, duration: 900 }))
  await wait(2200)
  const regional = await state()
  await page.screenshot({ path: `${OUT}/31_two_layers_regional.png` })
  console.log('区域视角:', JSON.stringify(regional))

  // 第三种视角：把时间前移一个跨度，让事件层与地点层同时出现在同一屏
  await page.evaluate(() => document.querySelectorAll('.tl .nav')[1].click())
  await wait(2200)
  await page.evaluate(() => window.__map.easeTo({ center: [24, 37.5], zoom: 5.2, duration: 900 }))
  await wait(2200)
  const both = await state()
  await page.screenshot({ path: `${OUT}/32_two_layers_event_and_place.png` })
  console.log('事件+地点同屏:', JSON.stringify(both))

  console.log('JS 错误:', errors.length ? errors.join(' | ') : '0')
  await browser.close()
  process.exit(0)
})()
