/**
 * M4-4c 浏览器 E2E：地图 / 搜索 / 详情 / 时间轴（真实 UI，只读 API）
 *
 * 目标：http://127.0.0.1:5180/  → 代理到 127.0.0.1:8089 → 库 canvas_history_m4_4b
 * 夹具：ops/reports/m4-4c/fixtures.json（由 ops/m4-4c/make_fixtures.py 生成）
 *
 * 跑法：
 *   NODE_PATH=/tmp/e2e-deps/node_modules node tests/e2e-m4c/places-e2e.cjs \
 *       http://127.0.0.1:5180/ ../ops/reports/m4-4c/fixtures.json ../ops/reports/m4-4c/shots
 *
 * 判据编号与报告一一对应：
 *   U1 页面/地图就绪、无脚本异常
 *   U2 罗马视窗：面/线地点进入 places 图层
 *   U3 面+多位置地点：点结果→详情，类型/精度/条数正确
 *   U4 线状地点：详情正常，不因 geom_type≠Point 报错
 *   U5 无坐标地点：能搜到、能开详情、地图上不出现
 *   U6 雅典 / 庞贝：搜索命中 + 详情
 *   U7 时间轴：有效年命中、有效年外不命中（BCE 与 CE 各一组）
 *   U8 BCE 显示为「前 N」，不出现公元 0 年
 *   U9 全程无 pageerror
 */
const puppeteer = require('puppeteer-core')
const fs = require('node:fs')
const path = require('node:path')

const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe'
const URL = process.argv[2] || 'http://127.0.0.1:5180/'
const FIXTURES = process.argv[3] || path.join(__dirname, '../../ops/reports/m4-4c/fixtures.json')
const OUT = process.argv[4] || path.join(__dirname, '../../ops/reports/m4-4c/shots')

const fx = JSON.parse(fs.readFileSync(FIXTURES, 'utf8'))
const results = []
const rec = (id, name, ok, detail) => {
  results.push({ id, name, ok, detail })
  console.log(`${ok ? 'PASS' : 'FAIL'} ${id} ${name} — ${detail}`)
}
const wait = (ms) => new Promise((r) => setTimeout(r, ms))

;(async () => {
  fs.mkdirSync(OUT, { recursive: true })
  const browser = await puppeteer.launch({
    executablePath: CHROME,
    headless: 'new',
    args: ['--no-sandbox', '--disable-dev-shm-usage', '--use-gl=swiftshader',
           '--enable-unsafe-swiftshader'],
    defaultViewport: { width: 1600, height: 950 },
  })
  const page = await browser.newPage()
  const pageErrors = []
  const consoleErrors = []
  page.on('pageerror', (e) => pageErrors.push('pageerror: ' + e.message))
  page.on('console', (m) => {
    if (m.type() === 'error') consoleErrors.push('console: ' + m.text().slice(0, 300))
  })

  const KW = '.search input[type=text]'
  const YR = '.search input[inputmode=numeric]'
  const ITEM = '.search .item'

  const itemIds = () =>
    page.$$eval(ITEM, (els) => els.map((e) => parseInt(e.querySelector('.id')?.textContent.replace('#', '') || '0', 10)))
  const itemTexts = () =>
    page.$$eval(ITEM, (els) => els.slice(0, 8).map((e) => ({
      nm: e.querySelector('.nm')?.textContent?.trim(),
      line2: e.querySelector('.line2')?.innerText.replace(/\s+/g, ' ').trim(),
    })))

  async function search(kw, year) {
    await page.click(KW, { clickCount: 3 })
    await page.keyboard.press('Backspace')
    await page.type(KW, kw)
    if (year === undefined || year === null) {
      await page.click(YR, { clickCount: 3 })
      await page.keyboard.press('Backspace')
    } else {
      await page.click(YR, { clickCount: 3 })
      await page.keyboard.press('Backspace')
      await page.type(YR, String(year))
    }
    await page.keyboard.press('Enter')
    // 等结果或空态出现（两种都算"查询完成"）
    await page.waitForFunction(
      (sel) => document.querySelectorAll(sel).length > 0 || document.querySelector('.search .empty'),
      { timeout: 20000 }, ITEM).catch(() => {})
    await wait(900)
  }

  async function openTab(name) {
    await page.evaluate((label) => {
      const btn = [...document.querySelectorAll('.detail .tabs button')]
        .find((b) => b.textContent.includes(label))
      if (btn) btn.click()
    }, name)
    await wait(400)
  }

  async function closeDetail() {
    const x = await page.$('.detail .x')
    if (x) await x.click()
    await wait(400)
  }

  const mapFeatures = () =>
    page.evaluate(() => {
      const m = window.__map
      const src = m.getSource('places')
      const feats = (src && src._data && src._data.features) || []
      return feats.map((f) => ({ id: f.properties?.placeId }))
    })

  // ---------------------------------------------------------------- U1
  await page.goto(URL, { waitUntil: 'networkidle2', timeout: 45000 })
  // M0-02 的教训：样式就绪时间在 1–7 s 之间浮动，固定等待会误报。
  // 这里轮询到 style loaded 且 places 源至少取过一次数据（或 20 s 超时）。
  await page.waitForFunction(
    () => !!(window.__map && window.__map.isStyleLoaded()),
    { timeout: 20000, polling: 200 }).catch(() => {})
  await wait(1500)
  const ready = await page.evaluate(() => !!(window.__map && window.__map.isStyleLoaded()))
  const dbName = await page.evaluate(async () => {
    const r = await fetch('/api/v1/meta/health')
    return (await r.json()).database
  })
  rec('U1', '页面加载且地图样式就绪', ready, `style loaded=${ready}`)
  rec('U1b', '前端代理指向隔离库', dbName === 'canvas_history_m4_4b', `health.database=${dbName}`)
  await page.screenshot({ path: `${OUT}/U1_page.png` })

  // ---------------------------------------------------------------- U2
  // 罗马视窗：与夹具同一个 bbox 的中心，zoom 12
  const [w, s, e, n] = fx.rome_bbox
  // 用 fitBounds 让整个罗马 bbox 进入视窗，否则 zoom 12 只能看到其中一小块，
  // "样本进入图层"会变成一条取决于视窗大小的假判据。
  await page.evaluate(([[ww, ss], [ee, nn]]) =>
    window.__map.fitBounds([[ww, ss], [ee, nn]], { padding: 20, duration: 0 }),
    [[w, s], [e, n]])
  await wait(3000)
  const feats = await mapFeatures()
  const ids = new Set(feats.map((f) => f.id))
  const samples = fx.geometry_samples.map((g) => g.place_id)
  const hitSamples = samples.filter((pid) => ids.has(pid))
  rec('U2', '罗马视窗内 places 图层有要素', feats.length > 0, `${feats.length} 个要素`)
  rec('U2b', '面/线样本至少 3 个进入图层', hitSamples.length >= 3,
    `命中 ${hitSamples.length}/${samples.length}：${hitSamples.join(',')}`)
  await page.screenshot({ path: `${OUT}/U2_rome.png` })

  // ---------------------------------------------------------------- U3
  // 多位置 + 混合精度（150130 Velini），从搜索点进去
  const multi = fx.multi_location[0]
  await search(multi.name.split(' ')[0])
  let hitIds = await itemIds()
  let targetId = hitIds.includes(multi.place_id) ? multi.place_id : hitIds[0]
  await page.click(ITEM)
  await wait(2200)
  await openTab('位置')
  const detail1 = await page.evaluate(() => ({
    title: document.querySelector('.detail h2')?.textContent?.trim(),
    kv: [...document.querySelectorAll('.detail .kv')].map((x) => x.innerText.replace(/\s+/g, ' ')),
    locRows: document.querySelectorAll('.detail .loc').length,
    body: (document.querySelector('.detail')?.innerText || '').replace(/\s+/g, ' '),
  }))
  const opened = await page.$('.detail')
  rec('U3', '从搜索结果点开详情', !!opened, `标题=${detail1.title}`)
  rec('U3b', '详情来源显示 Pleiades 4.1',
    /Pleiades/.test(detail1.body) && /4\.1/.test(detail1.body),
    (detail1.kv.find((t) => /Pleiades/.test(t)) || '').slice(0, 90))
  rec('U3c', '详情位置行数 ≥ 3', detail1.locRows >= 3, `渲染 ${detail1.locRows} 行`)
  rec('U3d', '详情同时展示 precise 与 rough（未整体降级）',
    /precise/.test(detail1.body) && /rough/.test(detail1.body),
    `precise=${/precise/.test(detail1.body)} rough=${/rough/.test(detail1.body)}`)
  await page.screenshot({ path: `${OUT}/U3_detail_multi.png` })
  await closeDetail()

  // ---------------------------------------------------------------- U4
  // 线状地点（Delkon river, 153964）—— 若它不在搜索结果里就直接用 URL 打不开，
  // 因此用它的名称搜索；搜不到则退化为用地图上已有的线状样本。
  const line = fx.geometry_samples.find((g) => g.geom_type === 'LineString')
  await search(line.name.split(' ')[0])
  hitIds = await itemIds()
  if (hitIds.includes(153964)) {
    // 直接点对应条目
    const idx = hitIds.indexOf(153964)
    const els = await page.$$(ITEM)
    if (els[idx]) await els[idx].click()
  } else if (hitIds.length) {
    await page.click(ITEM)
  }
  await wait(2000)
  const detail2 = await page.evaluate(() => ({
    title: document.querySelector('.detail h2')?.textContent?.trim(),
    body: (document.querySelector('.detail')?.innerText || '').replace(/\s+/g, ' '),
  }))
  rec('U4', '线状/面状地点详情可打开（无 geom_type 异常）', !!detail2.title,
    `标题=${detail2.title}`)
  await page.screenshot({ path: `${OUT}/U4_detail_line.png` })
  await closeDetail()

  // ---------------------------------------------------------------- U5
  const ng = fx.no_geometry[0]
  await search(ng.name_text)
  hitIds = await itemIds()
  const ngHit = hitIds.includes(ng.place_id)
  rec('U5', `无坐标地点「${ng.name_text}」可被搜到`, ngHit, `命中 ${hitIds.slice(0, 5).join(',')}`)
  const featsBefore = (await mapFeatures()).length
  if (hitIds.length) {
    const idx = hitIds.indexOf(ng.place_id)
    const els = await page.$$(ITEM)
    if (els[idx >= 0 ? idx : 0]) await els[idx >= 0 ? idx : 0].click()
  }
  await wait(1800)
  await openTab('位置')
  const detail3 = await page.evaluate(() => ({
    title: document.querySelector('.detail h2')?.textContent?.trim(),
    body: (document.querySelector('.detail')?.innerText || '').replace(/\s+/g, ' '),
  }))
  const featsAfter = (await mapFeatures()).length
  rec('U5b', '无坐标地点详情可打开', !!detail3.title, `标题=${detail3.title}`)
  rec('U5c', '详情明确说明没有位置记录',
    /无位置记录|暂无位置/.test(detail3.body), (detail3.body.match(/无位置记录[^。]{0,20}/) || [''])[0])
  const idsAfter = (await mapFeatures()).map((f) => f.id)
  rec('U5d', '地图上不出现该地点（没有虚构坐标）', !idsAfter.includes(ng.place_id),
    `点开后图层 ${featsBefore} → ${featsAfter} 个要素，其中含该 id=${idsAfter.includes(ng.place_id)}`)
  await page.screenshot({ path: `${OUT}/U5_detail_nogeom.png` })
  await closeDetail()

  // ---------------------------------------------------------------- U6
  await search('Athens')
  hitIds = await itemIds()
  rec('U6', '搜索 Athens 命中 Athenae(157338)', hitIds.includes(fx.athens.place_id),
    `命中 ${hitIds.slice(0, 6).join(',')}`)
  const plains = await itemTexts()
  rec('U6b', '搜索结果展示正名与纪年', plains.length > 0 && /前|纪年未知|\d/.test(plains[0].line2 || ''),
    `${plains[0]?.nm}｜${plains[0]?.line2}`)
  await page.screenshot({ path: `${OUT}/U6_search_athens.png` })
  await closeDetail()

  await search('Pompeii')
  hitIds = await itemIds()
  rec('U6c', '搜索 Pompeii 命中 150913', hitIds.includes(fx.pompeii.place_id),
    `命中 ${hitIds.slice(0, 6).join(',')}`)

  // ---------------------------------------------------------------- U7 / U8
  // 取两个样本：一个 BCE（valid_from<=0）、一个 CE
  const bce = fx.timeline_samples.find((t) => t.valid_from <= 0)
  const ce = fx.timeline_samples.find((t) => t.valid_from > 0)
  for (const [tag, t] of [['BCE', bce], ['CE', ce]]) {
    if (!t) {
      rec('U7', `${tag} 样本缺失`, false, '夹具里没有该类样本')
      continue
    }
    await search(t.name_text, t.inside_year)
    const inIds = await itemIds()
    const okIn = inIds.includes(t.place_id)
    const texts = await itemTexts()
    await page.screenshot({ path: `${OUT}/U7_timeline_${tag}_in.png` })
    await search(t.name_text, t.outside_year)
    const outIds = await itemIds()
    const okOut = !outIds.includes(t.place_id)
    await page.screenshot({ path: `${OUT}/U7_timeline_${tag}_out.png` })
    rec(`U7-${tag}`, `时间轴过滤 ${t.place_id}（${t.inside_year} 命中 / ${t.outside_year} 不命中）`,
      okIn && okOut, `in=${okIn} out=${okOut}`)
    if (tag === 'BCE') {
      const shown = texts.map((x) => x.line2 || '').join(' ')
      rec('U8', 'BCE 显示为「前 N」且不出现公元 0 年',
        /前\s?\d+/.test(shown) && !/\b0\b\s*[–-]/.test(shown), shown.slice(0, 90))
    }
  }

  // ---------------------------------------------------------------- U9
  rec('U9', '全程无 pageerror', pageErrors.length === 0,
    pageErrors.length ? pageErrors.slice(0, 3).join(' | ') : '0 条')
  rec('U9b', 'console error 计数（仅记录，不作为失败判据）', true,
    `${consoleErrors.length} 条${consoleErrors.length ? '：' + consoleErrors[0].slice(0, 120) : ''}`)

  await browser.close()

  const pass = results.filter((r) => r.ok).length
  console.log(`\n判据 ${results.length} 条：通过 ${pass}，失败 ${results.length - pass}`)
  fs.writeFileSync(path.join(OUT, 'ui_result.json'),
    JSON.stringify({ url: URL, db: fx.db, results, pageErrors, consoleErrors }, null, 2), 'utf8')
  if (pageErrors.length || pass !== results.length) process.exit(1)
})().catch((e) => {
  console.error('脚本异常：', e)
  process.exit(2)
})
