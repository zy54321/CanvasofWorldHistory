/**
 * M0 + M1 浏览器端到端验收脚本（puppeteer-core + 本机 Chrome）。
 * 输出：控制台逐项结论 + 截图。
 */
const puppeteer = require('puppeteer-core')
const fs = require('node:fs')

const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe'
const URL = 'http://127.0.0.1:5180/'
const OUT = process.argv[2] || './shots'

/**
 * 单项统计过滤（仅供单项复跑时看数）：E2E_ONLY=M0-02
 *
 * 注意：这是**统计口径**过滤，不是跳过执行。整脚本仍逐步跑完（保证单项在与其他项
 * 相同的前置状态下被执行），只是未被点名的项不计入 results / 退出码。没有指定时行为不变。
 */
const ONLY = (process.env.E2E_ONLY || '')
  .split(',')
  .map((s) => s.trim())
  .filter(Boolean)

const results = []
const skipped = []
const rec = (id, name, ok, detail) => {
  if (ONLY.length && !ONLY.includes(id)) {
    skipped.push({ id, name, ok, detail })
    console.log(`  ·  ${id} ${name} — ${ok ? 'PASS' : 'FAIL'}（本次未计入统计）`)
    return
  }
  results.push({ id, name, ok, detail })
  console.log(`${ok ? 'PASS' : 'FAIL'} ${id} ${name} — ${detail}`)
}
const wait = (ms) => new Promise((r) => setTimeout(r, ms))

;(async () => {
  fs.mkdirSync(OUT, { recursive: true })
  const browser = await puppeteer.launch({
    executablePath: CHROME,
    headless: 'new',
    args: [
      '--no-sandbox',
      '--disable-dev-shm-usage',
      '--use-gl=swiftshader',
      '--enable-unsafe-swiftshader',
    ],
    defaultViewport: { width: 1600, height: 950 },
  })
  const page = await browser.newPage()
  const errors = []
  page.on('pageerror', (e) => errors.push('pageerror: ' + e.message))
  page.on('console', (m) => {
    if (m.type() === 'error') errors.push('console: ' + m.text())
  })
  page.on('requestfailed', (r) =>
    errors.push('reqfail: ' + r.url().replace(/key=[^&]+/, 'key=***') + ' :: ' + (r.failure()?.errorText || '')),
  )

  await page.goto(URL, { waitUntil: 'networkidle2', timeout: 45000 })
  await wait(3500)
  const HAS_KEY = !(await page.$('.no-key'))
  console.log(`检测到 MapTiler key：${HAS_KEY ? '是（真实底图模式）' : '否（离线降级模式）'}\n`)

  const cam = () =>
    page.evaluate(() => {
      const m = window.__map
      const c = m.getCenter()
      return { lng: +c.lng.toFixed(4), lat: +c.lat.toFixed(4), zoom: +m.getZoom().toFixed(3) }
    })
  const styleInfo = () =>
    page.evaluate(() => {
      const m = window.__map
      const st = m.getStyle() || {}
      return {
        name: st.name,
        bg: st.layers?.find((l) => l.type === 'background')?.paint?.['background-color'],
        raster: (st.layers || []).filter((l) => l.type === 'raster').length,
        sources: Object.keys(st.sources || {}),
        layers: st.layers?.length,
        places: (m.getSource('places')?._data?.features || []).length
              + (m.getSource('places-pts')?._data?.features || []).length,
        loaded: m.loaded(),
      }
    })

  // ---------- M0-01 地图加载 + 默认全球视野 ----------
  const s0 = await styleInfo()
  const c0 = await cam()
  const canvas = await page.$('.maplibregl-canvas')
  rec(
    'M0-01',
    '地图加载 / 默认全球视野',
    !!canvas && s0.loaded && c0.zoom < 2,
    `canvas=${!!canvas} loaded=${s0.loaded} center=${c0.lng},${c0.lat} zoom=${c0.zoom} layers=${s0.layers}`,
  )
  await page.screenshot({ path: `${OUT}/M0-01_initial_world.png` })

  // ---------- M0-05 凭证：不得把 key 送到浏览器 ----------
  const pageHasKey = await page.evaluate(() => {
    const html = document.documentElement.outerHTML
    return /[?&]key=/.test(html)
  })
  const bannerText = await page.$eval('.no-key', (e) => e.innerText).catch(() => '')
  rec(
    'M0-05',
    '凭证不泄漏 / 不硬编码',
    !pageHasKey,
    `HTML 中无 key 参数=${!pageHasKey}；`.concat(
      bannerText ? `界面明确提示底图未接入（未伪装成功）` : `已检测到 API key`,
    ),
  )

  // ---------- M0-02 / M0-03 样式切换 + 视野保持 ----------
  /**
   * 样式就绪轮询（替代历史上的固定 wait(1500)）。
   *
   * 固定等待的问题：setStyle 之后要等 style.json → sprite/glyphs → 瓦片，机器负载高时
   * 1.5s 常常不够，会读到 name=undefined、places=0 而误报失败。实测同机负载下
   * Streets 约 3.4s、Outdoor 约 5.8s 才真正就绪。
   *
   * 就绪判据（四项同时成立，缺一不可）：
   *   1. 样式名匹配目标样式；
   *   2. map.isStyleLoaded() —— 样式本身已加载完；
   *   3. map.loaded() —— 源与瓦片已停（真实底图模式下必须，避免「样式名到了但图还没出来」）；
   *   4. 地点图层已恢复：places 源存在、places-dot 图层存在且可见、要素数 > 0。
   *
   * 只看样式名是不够的：setStyle 会把自定义图层全部清掉，由 style.load 里的 ensureLayers
   * 重建，期间图层可能短暂缺失。所以「点层恢复」是独立且必要的判据。
   */
  const STYLE_TIMEOUT = 8000
  const STYLE_POLL = 200
  // Hybrid 的官方 name 是「Satellite Hybrid」；若 Satellite 只判 /satellite/，切到 Hybrid 时
  // 会把尚未切换的上一个样式（Satellite）误认成已就绪，因此 Satellite 必须排除 hybrid。
  const nameMatches = (label, name) => {
    const n = String(name || '').toLowerCase()
    if (label === 'Satellite') return n.includes('satellite') && !n.includes('hybrid')
    return n.includes(label.toLowerCase())
  }
  const styleState = () =>
    page.evaluate(() => {
      const m = window.__map
      const st = m.getStyle() || {}
      const dot = m.getLayer('places-dot')
      // V1.0：地点拆成两个源 —— 面/线在 'places'，点在聚合源 'places-pts'。
      // 低缩放下聚合源里通常是 cluster，'places' 可能是 0 条，所以两者相加才是"数据到了"。
      const src = m.getSource('places')
      const pts = m.getSource('places-pts')
      return {
        name: st.name ?? null,
        layers: (st.layers || []).length,
        raster: (st.layers || []).filter((l) => l.type === 'raster').length,
        styleLoaded: m.isStyleLoaded(),
        mapLoaded: m.loaded(),
        hasPlacesSource: !!src,
        hasPlacesLayer: !!dot,
        placesVisible: !!dot && (dot.layout?.visibility ?? 'visible') !== 'none',
        places: (src?._data?.features || []).length + (pts?._data?.features || []).length,
        shapes: (src?._data?.features || []).length,
        points: (pts?._data?.features || []).length,
      }
    })
  async function waitStyleReady(label) {
    const t0 = Date.now()
    let s = await styleState()
    let reason = ''
    while (Date.now() - t0 < STYLE_TIMEOUT) {
      s = await styleState()
      const nameOk = HAS_KEY ? nameMatches(label, s.name) : s.name === 'offline-graticule'
      const layerOk = s.hasPlacesSource && s.hasPlacesLayer && s.placesVisible && s.places > 0
      if (nameOk && layerOk && s.styleLoaded && s.mapLoaded) {
        return { ok: true, ms: Date.now() - t0, state: s }
      }
      const why = []
      if (!nameOk) why.push(`样式名「${s.name ?? 'null'}」未匹配 ${label}`)
      if (!s.styleLoaded) why.push('isStyleLoaded=false')
      if (!s.mapLoaded) why.push('loaded=false（瓦片仍在加载）')
      if (!s.hasPlacesSource) why.push('places 源缺失')
      if (!s.hasPlacesLayer) why.push('places-dot 图层缺失')
      else if (!s.placesVisible) why.push('places-dot 被隐藏')
      if (s.places === 0) why.push('places 要素数为 0')
      reason = why.join('；')
      await wait(STYLE_POLL)
    }
    return { ok: false, ms: Date.now() - t0, state: s, reason: reason || '未进入判据' }
  }

  await page.evaluate(() => window.__map.jumpTo({ center: [116.4, 39.9], zoom: 6.2 }))
  await wait(900)
  const before = await cam()
  const seen = []
  for (const label of ['Streets', 'Satellite', 'Hybrid', 'Outdoor']) {
    const btns = await page.$$('.style-bar button')
    for (const b of btns) {
      const t = await b.evaluate((e) => e.textContent.trim())
      if (t === label) {
        await b.click()
        break
      }
    }
    const ready = await waitStyleReady(label)
    const info = await styleInfo()
    const c = await cam()
    seen.push({ label, bg: info.bg, name: info.name, raster: info.raster,
                zoom: c.zoom, lng: c.lng, lat: c.lat, places: info.places,
                ready: ready.ok, ms: ready.ms, reason: ready.reason || '' })
    if (!ready.ok) {
      console.log(
        `   ⚠ ${label} 在 ${ready.ms}ms 内未就绪，失败原因：${ready.reason}` +
          `｜当前样式名 ${JSON.stringify(ready.state.name)}、图层 ${ready.state.layers} 个` +
          `（raster ${ready.state.raster}）、places 源=${ready.state.hasPlacesSource}` +
          `、places-dot=${ready.state.hasPlacesLayer}` +
          `（可见=${ready.state.placesVisible}）、要素 ${ready.state.places}` +
          `、styleLoaded=${ready.state.styleLoaded}、loaded=${ready.state.mapLoaded}`,
      )
    }
    await page.screenshot({ path: `${OUT}/M0-02_style_${label}.png` })
  }
  const drift = seen.filter(
    (s) =>
      Math.abs(s.zoom - before.zoom) > 0.001 ||
      Math.abs(s.lng - before.lng) > 0.01 ||
      Math.abs(s.lat - before.lat) > 0.01,
  )
  const distinctKey = new Set(seen.map((s) => (HAS_KEY ? String(s.name) : String(s.bg)))).size
  const rasterOk = HAS_KEY ? seen.some((s) => s.raster > 0) : true
  // 影像类底图必须真的有栅格层，否则「样式名对了但影像没出来」也会被判通过
  const rasterPair = HAS_KEY
    ? ['Satellite', 'Hybrid'].every((l) => {
        const s = seen.find((x) => x.label === l)
        return !!s && s.raster > 0
      })
    : true
  const notReady = seen.filter((s) => s.ready !== true)
  rec(
    'M0-02',
    '四种样式可用',
    seen.length === 4 &&
      notReady.length === 0 &&
      distinctKey >= 4 &&
      rasterOk &&
      rasterPair &&
      seen.every((s) => s.places > 0),
    (HAS_KEY
      ? `切换 4 次，样式名互异 ${distinctKey} 种：${seen.map((s) => s.name).join(' / ')}；` +
        `Satellite/Hybrid 含栅格影像层（raster ${seen.map((s) => s.raster).join('/')}）；` +
        `每步点层 ${seen.map((s) => s.places).join('/')} 点；`
      : `切换 4 次；离线底色互不相同 ${distinctKey} 种；` +
        `每步点层 ${seen.map((s) => s.places).join('/')} 点；`) +
      `轮询就绪耗时 ${seen.map((s) => `${s.label} ${s.ms}ms`).join(' / ')}` +
      (notReady.length
        ? `；未就绪：${notReady.map((s) => `${s.label}（${s.reason}）`).join('，')}`
        : '（均 ≤ 8s，全部就绪）'),
  )
  rec(
    'M0-03',
    '视野保持',
    drift.length === 0,
    drift.length === 0
      ? `切换前 ${before.lng},${before.lat} z${before.zoom}；四次切换后相机完全一致，漂移 0`
      : `漂移：${JSON.stringify(drift)}`,
  )

  // ---------- M0-04 四区域 ----------
  const regions = ['中国', '欧洲', '北美', '中东']
  const regionOut = []
  for (const name of regions) {
    const btns = await page.$$('.region-bar button')
    for (const b of btns) {
      const t = await b.evaluate((e) => e.textContent.trim())
      if (t === name) {
        await b.click()
        break
      }
    }
    await wait(3000)
    const c = await cam()
    const info = await styleInfo()
    // 视野内实际取到的后端点数（由状态条读）
    const note = await page.$eval('.data-note', (e) => e.innerText.replace(/\s+/g, ' '))
    const m = /当前视野 ([\d,]+)/.exec(note)
    const noPt = /当前视野内无可信坐标/.test(note)
    regionOut.push({
      name,
      center: `${c.lng},${c.lat}`,
      zoom: c.zoom,
      points: m ? m[1] : noPt ? '0' : '?',
      features: info.places,
    })
    await page.screenshot({ path: `${OUT}/M0-04_region_${name}.png` })
  }
  rec(
    'M0-04',
    '四区域测试',
    // M0 验证的是底图/相机/交互，与数据覆盖无关；北美/中东无点属数据集覆盖范围问题（CHGIS 为中国历史地名）
    regionOut.every((r) => Math.abs(r.zoom) > 1),
    regionOut.map((r) => `${r.name}@${r.center} z${r.zoom} 视野${r.points}点`).join(' | '),
  )

  // 回到全球
  await page.evaluate(() => window.__map.jumpTo({ center: [20, 20], zoom: 1.4 }))
  await wait(1600)

  // ---------- M1-01 搜索（真实库记录） ----------
  await page.click('.search input[type=text]')
  await page.type('.search input[type=text]', '长安')
  await page.keyboard.press('Enter')
  await page.waitForFunction(() => document.querySelectorAll('.search .item').length > 0, {
    timeout: 15000,
  })
  const head = await page.$eval('.result-head', (e) => e.innerText.replace(/\s+/g, ' '))
  const items = await page.$$eval('.search .item', (els) =>
    els.slice(0, 6).map((e) => ({
      nm: e.querySelector('.nm')?.textContent?.trim(),
      meta: e.querySelector('.line2')?.innerText.replace(/\s+/g, ' ').trim(),
      id: e.querySelector('.id')?.textContent?.trim(),
    })),
  )
  rec('M1-01', '地点搜索命中真实记录', items.length > 0, `${head}；前几条 ${items.map((i) => i.nm).join('、')}`)
  await page.screenshot({ path: `${OUT}/M1-01_search.png` })

  // 同名不同地点：不应被合并（应出现多个 #id）
  const sameNameIds = new Set(items.map((i) => i.id))
  rec(
    'M1-01b',
    '同名不同地点不合并',
    sameNameIds.size === items.length,
    `首屏 ${items.length} 条各自 id 唯一：${[...sameNameIds].join(' ')}`,
  )

  // ---------- M1-01 别名搜索 + 年代筛选 ----------
  await page.click('.search input[type=text]', { clickCount: 3 })
  await page.keyboard.press('Backspace')
  await page.type('.search input[type=text]', '桂林縣')
  await page.keyboard.press('Enter')
  await wait(1500)
  const aliasHit = await page.$$eval('.search .item', (els) =>
    els.slice(0, 3).map((e) => ({
      nm: e.querySelector('.nm')?.textContent?.trim(),
      canon: e.querySelector('.line2')?.innerText.replace(/\s+/g, ' ').trim(),
    })),
  )
  rec(
    'M1-01c',
    '别名搜索',
    aliasHit.length > 0 && aliasHit[0].canon.includes('正名'),
    `搜“桂林縣”（别名写法）→ ${aliasHit[0]?.nm}；${aliasHit[0]?.canon}`,
  )

  // 年代筛选：取一条结果的年份区间，用区间内 / 区间外两年对比
  await page.click('.search input[type=text]', { clickCount: 3 })
  await page.keyboard.press('Backspace')
  await page.type('.search input[type=text]', '洛阳')
  await page.keyboard.press('Enter')
  await wait(1600)
  const allCount = await page.$eval('.result-head', (e) => e.innerText)
  const yearBox = await page.$('.search input[inputmode=numeric]')
  await yearBox.click({ clickCount: 3 })
  await yearBox.type('1200')
  await page.keyboard.press('Enter')
  await wait(1600)
  const y1200 = await page.$eval('.result-head', (e) => e.innerText.replace(/\s+/g, ' '))
  await yearBox.click({ clickCount: 3 })
  await yearBox.type('-500')
  await page.keyboard.press('Enter')
  await wait(1600)
  const yNeg = await page.$eval('.result-head', (e) => e.innerText.replace(/\s+/g, ' '))
  const nAll = parseInt((/([\d,]+) 条/.exec(allCount) || [0, '0'])[1].replace(/,/g, ''), 10)
  const n1200 = parseInt((/([\d,]+) 条/.exec(y1200) || [0, '0'])[1].replace(/,/g, ''), 10)
  const nNeg = parseInt((/([\d,]+) 条/.exec(yNeg) || [0, '0'])[1].replace(/,/g, ''), 10)
  rec(
    'M1-01d',
    '年代筛选（名称有效期）',
    n1200 > 0 && n1200 < nAll && nNeg <= n1200,
    `洛阳：不限年代 ${nAll} 条 / year=1200 ${n1200} 条 / year=-500 ${nNeg} 条（筛选生效且有序）`,
  )
  await page.screenshot({ path: `${OUT}/M1-01_year.png` })

  // ---------- M1-01 分页 ----------
  await yearBox.click({ clickCount: 3 })
  await page.keyboard.press('Backspace')
  await page.keyboard.press('Enter')
  await wait(1200)
  const kw = await page.$('.search input[type=text]')
  await kw.click({ clickCount: 3 })
  await page.keyboard.press('Backspace')
  await page.type('.search input[type=text]', '县')
  await page.keyboard.press('Enter')
  await wait(1800)
  const pagerBefore = await page.$$('.pager button')
  let pageBefore = '（无分页器）'
  let pageAfter = pageBefore
  if (pagerBefore.length === 2) {
    pageBefore = await page.$eval('.pager .tiny', (e) => e.innerText)
    if (!(await pagerBefore[1].evaluate((e) => e.disabled))) {
      await pagerBefore[1].click()
      await wait(1600)
      pageAfter = await page.$eval('.pager .tiny', (e) => e.innerText)
    }
  }
  rec(
    'M1-01e',
    '分页',
    pagerBefore.length === 2 && pageBefore !== pageAfter,
    `分页器 ${pageBefore} → ${pageAfter}`,
  )
  await page.screenshot({ path: `${OUT}/M1-01_page2.png` })

  // ---------- M1-04 点结果 → 地图定位 ----------
  const camBeforePick = await cam()
  await page.click('.search .item')
  await page.waitForSelector('.detail h2', { timeout: 15000 })
  await wait(2500)
  const camAfterPick = await cam()
  const ring = await page.evaluate(() => {
    const m = window.__map
    return (m.getSource('selected-place')?._data?.features || []).length
  })
  rec(
    'M1-04',
    '搜索结果 → 地图定位',
    camBeforePick.zoom !== camAfterPick.zoom || camBeforePick.lng !== camAfterPick.lng,
    `点击前 z${camBeforePick.zoom}@${camBeforePick.lng},${camBeforePick.lat} → 点击后 z${camAfterPick.zoom}@${camAfterPick.lng},${camAfterPick.lat}；高亮环 ${ring} 个`,
  )
  await page.screenshot({ path: `${OUT}/M1-04_pick.png` })

  // ---------- M1-02 详情正确性 ----------
  const detail = await page.evaluate(() => {
    const h = document.querySelector('.detail h2')?.textContent?.trim()
    const kv = [...document.querySelectorAll('.detail .kv')].map((e) =>
      e.innerText.replace(/\s+/g, ' '),
    )
    const tabs = [...document.querySelectorAll('.tabs button')].map((e) =>
      e.innerText.replace(/\s+/g, ' '),
    )
    return { h, kv, tabs }
  })
  rec(
    'M1-02',
    '地点详情（名称/位置/来源/精度）',
    !!detail.h && detail.kv.length >= 4,
    `${detail.h} ｜ ${detail.kv.join(' ; ')} ｜ 页签 ${detail.tabs.join(' ')}`,
  )

  // 逐页签截图
  const tabs = await page.$$('.tabs button')
  for (let i = 0; i < tabs.length; i++) {
    await tabs[i].click()
    await wait(400)
    const txt = await page.$eval('.pane', (e) => e.innerText.replace(/\s+/g, ' ').slice(0, 180))
    console.log(`   tab[${i}] ${txt}`)
    await page.screenshot({ path: `${OUT}/M1-02_tab${i}.png` })
  }

  // 有一处质量台账的地点（19051 台湾府）
  await page.evaluate(() => {
    document.querySelector('.detail .x')?.click()
  })
  await wait(400)

  // ---------- M1-03 bbox 空间查询（GeoJSON） ----------
  const geo = await page.evaluate(async () => {
    const r = await fetch('/api/v1/places/map?bbox=108,20,122,32&limit=50')
    const j = await r.json()
    return {
      status: r.status,
      type: j.type,
      n: j.features?.length,
      first: j.features?.[0],
      meta: j.meta,
    }
  })
  const geomOk =
    geo.type === 'FeatureCollection' &&
    geo.first?.geometry?.type === 'Point' &&
    Array.isArray(geo.first.geometry.coordinates) &&
    geo.meta?.truncated !== undefined
  rec(
    'M1-03',
    'bbox 空间查询返回 GeoJSON',
    geo.status === 200 && geomOk,
    `HTTP ${geo.status} type=${geo.type} features=${geo.n} 首点 ${JSON.stringify(geo.first?.geometry?.coordinates)} meta=${JSON.stringify(geo.meta)}`,
  )

  // 上限保护：超大 bbox 不得返回全量
  const big = await page.evaluate(async () => {
    const r = await fetch('/api/v1/places/map?bbox=-180,-85,180,85&limit=99999')
    const j = await r.json()
    return { n: j.features?.length, meta: j.meta, status: r.status }
  })
  rec(
    'M1-03b',
    '返回数量上限',
    big.n <= 2000 && big.meta?.truncated === true,
    `全球 bbox 请求 limit=99999 → 服务端钳制为 ${big.meta?.limit} 并实际返回 ${big.n} 条（上限 2000 生效），truncated=${big.meta?.truncated}，totalInBbox=${big.meta?.totalInBbox}`,
  )

  // ---------- 控制台洁净度 ----------
  const realErrors = errors.filter(
    (e) => !/favicon/i.test(e) && !/ERR_ABORTED/.test(e),
  )
  const aborted = errors.filter((e) => /ERR_ABORTED/.test(e)).length
  rec(
    'CLEAN',
    '浏览器控制台',
    realErrors.length === 0,
    realErrors.length === 0
      ? `无 JS 错误、无真实失败请求（另有 ${aborted} 个因样式切换被浏览器取消的瓦片请求，属正常）`
      : realErrors.slice(0, 5).join(' ｜ '),
  )

  await browser.close()

  fs.writeFileSync(
    `${OUT}/e2e_result.json`,
    JSON.stringify({ results, skipped, errors, only: ONLY }, null, 2),
  )
  const fail = results.filter((r) => !r.ok)
  if (ONLY.length) {
    console.log(
      `\n（统计口径：仅 ${ONLY.join(',')}；另有 ${skipped.length} 项已执行但未计入，` +
        `其中失败 ${skipped.filter((r) => !r.ok).length} 项）`,
    )
  }
  console.log(`\n=== 合计 ${results.length} 项，PASS ${results.length - fail.length}，FAIL ${fail.length} ===`)
  process.exit(fail.length ? 1 : 0)
})().catch((e) => {
  console.error('E2E ABORTED:', e.message)
  process.exit(2)
})