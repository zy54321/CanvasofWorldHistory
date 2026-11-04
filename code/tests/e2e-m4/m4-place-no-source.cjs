/**
 * M4-2 · 无来源手工地点上图 E2E。
 *
 * 目的：证明「人工录入、没有任何 source_record 的地点，只要坐标有效就能出现在 M1 地图上」，
 * 并且这件事不受图层开关影响。全程真实浏览器 + 真实 HTTP。
 *
 * 用法：
 *   node tests/e2e-m4/m4-place-no-source.cjs http://127.0.0.1:5181/ http://127.0.0.1:8089 ./out
 */
const puppeteer = require('puppeteer-core')

const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe'
const URL = process.argv[2] || 'http://127.0.0.1:5181/'
const API = (process.argv[3] || 'http://127.0.0.1:8089').replace(/\/$/, '')
const OUT = process.argv[4] || './shots'
const wait = (ms) => new Promise((r) => setTimeout(r, ms))

const RESULTS = []
const rec = (id, desc, ok, expect, actual) => {
  RESULTS.push(ok)
  console.log(`${ok ? 'PASS' : 'FAIL'} ${id.padEnd(5)} ${desc} | 期望 ${expect} | 实际 ${actual}`)
}

async function api(method, path, body) {
  const r = await fetch(API + path, {
    method,
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  })
  const txt = await r.text()
  let j = null
  try { j = txt ? JSON.parse(txt) : null } catch { /* 非 JSON */ }
  return { status: r.status, body: j }
}

;(async () => {
  const tag = 'M4二-E2E-' + Date.now()
  // 选一个周围没有导入点的位置，保证点击命中的就是本用例创建的地点
  const lon = 87.6168
  const lat = 43.8256

  // ---------- 1. 用 API 建一个完全没有来源的地点 + 坐标
  const p = await api('POST', '/api/v1/places', {
    canonicalName: tag, placeType: 'settlement', notes: 'M4-2 E2E 无来源地点',
  })
  const pid = p.body && p.body.placeId
  rec('E01', '创建无来源地点', p.status === 201 && !!pid, '201 + placeId', `${p.status} ${pid}`)
  if (!pid) { process.exit(1) }

  const l = await api('POST', `/api/v1/places/${pid}/locations`, {
    lon, lat, locationPrecision: 'approximate',
  })
  rec('E02', '添加坐标（无来源）', l.status === 201, '201', l.status)

  const detail = await api('GET', `/api/v1/places/${pid}`)
  rec('E03', '详情可直接读取（sourceRecords 为空不算错）',
    detail.status === 200 && Array.isArray(detail.body.sourceRecords) && detail.body.sourceRecords.length === 0,
    '200 + []', `${detail.status} ${(detail.body.sourceRecords || []).length}`)

  // ---------- 2. 浏览器里看它是否真的画在地图上
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

  // 地图飞到该点附近，触发 bbox 重查
  await page.evaluate(([x, y]) => window.__map.easeTo({ center: [x, y], zoom: 8, duration: 900 }), [lon, lat])
  await wait(3000)

  const probe = () =>
    page.evaluate((id) => {
      const m = window.__map
      const data = m.getSource('places') && m.getSource('places')._data
      const feats = (data && data.features) || []
      const hit = feats.find((f) => f.properties && f.properties.placeId === id)
      return {
        hasSource: !!m.getSource('places'),
        visible: m.getLayer('places-dot') ? m.getLayoutProperty('places-dot', 'visibility') || 'visible' : 'missing',
        count: feats.length,
        hit: !!hit,
        props: hit ? { name: hit.properties.canonicalName, ds: hit.properties.datasetId } : null,
      }
    }, pid)

  const s1 = await probe()
  rec('E04', '无来源地点出现在地图 places 数据源里', s1.hit === true,
    `要素含 ${pid}`, `count=${s1.count} hit=${s1.hit} ${JSON.stringify(s1.props)}`)
  rec('E05', '地点图层默认可见', s1.visible === 'visible', 'visible', s1.visible)
  await page.screenshot({ path: `${OUT}/40_no_source_place_on_map.png` })

  // ---------- 3. 图层开关来回切，仍能恢复
  await page.evaluate(() => {
    const b = [...document.querySelectorAll('.layer-switch button')].find((x) => x.textContent.includes('地点'))
    b && b.click()
  })
  await wait(1200)
  const s2 = await probe()
  await page.evaluate(() => {
    const b = [...document.querySelectorAll('.layer-switch button')].find((x) => x.textContent.includes('地点'))
    b && b.click()
  })
  await wait(1200)
  const s3 = await probe()
  rec('E06', '关闭再打开地点图层后标记恢复',
    s2.visible === 'none' && s3.visible === 'visible' && s3.hit === true,
    'hidden → visible + 有要素', `${s2.visible} → ${s3.visible} hit=${s3.hit}`)

  // ---------- 4. 点一下该标记，看详情面板能不能开
  const clicked = await page.evaluate(() => {
    const m = window.__map
    const canvas = m.getCanvas()
    const r = canvas.getBoundingClientRect()
    const pt = m.project([87.6168, 43.8256])
    return { x: r.left + pt.x, y: r.top + pt.y }
  })
  await page.mouse.click(clicked.x, clicked.y)
  await wait(1500)
  const panel = await page.evaluate(() => {
    const el = document.querySelector('aside.detail.panel') || document.querySelector('aside.detail')
    return el ? el.textContent.replace(/\s+/g, ' ').trim().slice(0, 160) : null
  })
  rec('E07', '点击无来源标记能打开它自己的详情（不报“缺少来源”）',
    panel !== null && panel.includes(tag) && !/缺少来源|加载失败/.test(panel),
    `面板含 ${tag}`, (panel || '(未打开)').slice(0, 70))
  await page.screenshot({ path: `${OUT}/41_no_source_place_detail.png` })

  rec('E08', '全程无 JS 错误', errors.length === 0, '0', errors.slice(0, 2).join(' | ') || '0')

  await browser.close()

  // ---------- 5. 清理
  const del = await api('DELETE', `/api/v1/places/${pid}`)
  rec('E09', '清理：删除 E2E 地点', del.status === 200 || del.status === 204, '200/204', del.status)

  const pass = RESULTS.filter(Boolean).length
  console.log(`\n=== M4-2 无来源地点上图：PASS ${pass} / ${RESULTS.length} ===`)
  process.exit(pass === RESULTS.length ? 0 : 1)
})()
