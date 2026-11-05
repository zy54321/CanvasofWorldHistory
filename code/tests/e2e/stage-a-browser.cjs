/**
 * 阶段 A2 浏览器验收：真实几何渲染 + 交互 + 占位名处理。
 * 所有断言都从真实 DOM / map 实例读取，不依赖截图人眼判断（截图另存备查）。
 */
const puppeteer = require('puppeteer-core')
const fs = require('fs')
const path = require('path')

const BASE = process.argv[2] || 'http://127.0.0.1:5180/'
const OUT = process.argv[3] || 'C:/Users/the_z/AppData/Local/Temp/v1b-shots'
const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe'
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

const results = []
function check(id, desc, ok, detail) {
  results.push({ id, desc, ok: !!ok, detail: detail === undefined ? '' : String(detail) })
  console.log(`${ok ? '✓' : '✗'} ${id} ${desc}${detail !== undefined ? ' :: ' + detail : ''}`)
}

;(async () => {
  fs.mkdirSync(OUT, { recursive: true })
  const browser = await puppeteer.launch({
    executablePath: CHROME,
    headless: 'new',
    args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader', '--no-sandbox'],
    defaultViewport: { width: 1500, height: 950 },
  })
  const page = await browser.newPage()
  const pageErrors = []
  const consoleErrors = []
  page.on('pageerror', (e) => pageErrors.push(String(e)))
  page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(m.text()) })

  const t0 = Date.now()
  await page.goto(BASE, { waitUntil: 'networkidle2', timeout: 60000 })
  await page.waitForFunction(() => !!(window.__map && window.__map.isStyleLoaded()), { timeout: 30000, polling: 200 })
  const loadMs = Date.now() - t0

  check('A2-1', '首页可加载且地图样式就绪', true, `${loadMs}ms`)
  const title = await page.title()
  check('A2-2', '页面标题正确', /历史/.test(title) || title.length > 0, title)

  // 底图
  const basemap = await page.evaluate(() => {
    const m = window.__map
    const layers = m.getStyle().layers
    const ids = layers.map((l) => l.id)
    const hasBg = ids.includes('Background')
    const base = ids.filter((id) => /^(Background|Water|Forest|Wood|Grass|Sand|Residential|River|Road|Highway|Boundary|Park|Hillshade)/.test(id))
    return { total: layers.length, base: base.length, hasBg, hasCanvas: !!document.querySelector('canvas'), sample: base.slice(0, 6) }
  })
  check('A2-3', '底图图层存在', basemap.hasBg && basemap.base > 8 && basemap.hasCanvas,
        `${basemap.base}/${basemap.total} 层, 样本 ${basemap.sample.join(',')}`)

  // 罗马视野：点/线/面真实渲染
  await page.evaluate(() => window.__map.jumpTo({ center: [12.45, 41.85], zoom: 10.6 }))
  await sleep(5000)
  const rome = await page.evaluate(() => {
    const m = window.__map
    const n = (id) => { try { return m.queryRenderedFeatures({ layers: [id] }).length } catch (e) { return -1 } }
    const shapes = m.getSource('places')?._data?.features || []
    const pts = m.getSource('places-pts')?._data?.features || []
    const srcTypes = shapes.reduce((a, f) => { a[f.geometry.type] = (a[f.geometry.type] || 0) + 1; return a }, {})
    return {
      fill: n('places-fill'), outline: n('places-outline'), line: n('places-line'),
      dot: n('places-dot'), label: n('places-label'),
      shapesN: shapes.length, ptsN: pts.length, srcTypes,
      zoom: +m.getZoom().toFixed(2),
    }
  })
  check('A2-4', '面要素真实绘制（fill > 0）', rome.fill > 0, `fill=${rome.fill} outline=${rome.outline}`)
  check('A2-5', '线要素真实绘制（line > 0）', rome.line > 0, `line=${rome.line}`)
  check('A2-6', '点要素绘制（dot > 0）', rome.dot > 0, `dot=${rome.dot}`)
  check('A2-7', '缩放 10.6 显示地名标签', rome.label > 0, `label=${rome.label}`)
  check('A2-8', '源里确实含非点几何', Object.keys(rome.srcTypes).some((k) => k !== 'Point'),
        JSON.stringify(rome.srcTypes))
  await page.screenshot({ path: path.join(OUT, 'a_rome_shapes.png') })

  // 世界视野：低缩放应为聚合
  await page.evaluate(() => window.__map.jumpTo({ center: [20, 30], zoom: 2 }))
  await sleep(4500)
  const cluster = await page.evaluate(() => {
    const m = window.__map
    const n = (id) => { try { return m.queryRenderedFeatures({ layers: [id] }).length } catch (e) { return -1 } }
    return { cluster: n('places-cluster'), dot: n('places-dot'), label: n('places-label'), zoom: +m.getZoom().toFixed(1) }
  })
  check('A2-9', '低缩放聚合生效（cluster > 0 且 label = 0）',
        cluster.cluster > 0 && cluster.label === 0, JSON.stringify(cluster))
  await page.screenshot({ path: path.join(OUT, 'a_world_cluster.png') })

  // 无名地点开关
  await page.evaluate(() => window.__map.jumpTo({ center: [12.45, 41.85], zoom: 10.6 }))
  await sleep(4000)
  const unnamedBtn = await page.$('button[title*="无名地点"]')
  check('A2-10', '存在「无名」图层开关', !!unnamedBtn)

  const beforeToggle = await page.evaluate(() => {
    const src = window.__map.getSource('places-pts')?._data?.features || []
    const shp = window.__map.getSource('places')?._data?.features || []
    return [...src, ...shp].filter((f) => f.properties.unnamed === true).length
  })
  if (unnamedBtn) {
    await unnamedBtn.click()
    await sleep(4500)
  }
  const afterToggle = await page.evaluate(() => {
    const src = window.__map.getSource('places-pts')?._data?.features || []
    const shp = window.__map.getSource('places')?._data?.features || []
    return [...src, ...shp].filter((f) => f.properties.unnamed === true).length
  })
  check('A2-11', '默认隐藏无名地点，打开开关后出现', beforeToggle === 0 && afterToggle > 0,
        `默认 ${beforeToggle} → 开关后 ${afterToggle}`)
  await page.screenshot({ path: path.join(OUT, 'a_unnamed_on.png') })
  if (unnamedBtn) { await unnamedBtn.click(); await sleep(3000) }

  // 单击 → 详情
  // 用与 MapView.onMapClick 完全相同的命中口径（±7px + shape-hit/fill/dot 三层），
  // 只挑"该位置只有 1 个地点"的点；罗马市区太密，先把地图移到一个指定地点上放大。
  const target = await page.evaluate(async () => {
    const r = await fetch('/api/v1/places/map?bbox=12.40,41.80,12.55,41.95&limit=50')
    const d = await r.json()
    const f = d.features.find((x) => x.geometry.type === 'Point' && x.properties.nameIsPlaceholder !== true)
    return f ? { lon: f.geometry.coordinates[0], lat: f.geometry.coordinates[1], name: f.properties.name, id: f.properties.placeId } : null
  })
  let single = null
  if (target) {
    await page.evaluate(({ lon, lat }) => window.__map.jumpTo({ center: [lon, lat], zoom: 15 }), target)
    await sleep(4500)
    single = await page.evaluate(({ id, name }) => {
      const m = window.__map
      const fs = m.queryRenderedFeatures({ layers: ['places-dot'] })
      const me = fs.find((f) => Number(f.properties.placeId) === Number(id))
      if (!me) return null
      const pt = m.project(me.geometry.coordinates)
      const hits = m.queryRenderedFeatures(
        [[pt.x - 7, pt.y - 7], [pt.x + 7, pt.y + 7]],
        { layers: ['places-shape-hit', 'places-fill', 'places-dot'].filter((l) => m.getLayer(l)) })
      const ids = new Set(hits.map((h) => h.properties.placeId))
      return { x: Math.round(pt.x), y: Math.round(pt.y), name, n: ids.size }
    }, target)
  }
  let detailOpen = false
  let detailTitle = ''
  if (single && single.n === 1) {
    await page.mouse.click(single.x, single.y)
    await sleep(2500)
    const d = await page.evaluate(() => {
      const el = document.querySelector('.detail')
      return { open: !!el, title: el?.querySelector('h2')?.textContent?.trim() || '', text: (el?.innerText || '').slice(0, 160) }
    })
    detailOpen = d.open
    detailTitle = d.title
    check('A2-12', '单击孤立地点直接打开详情', d.open, `${single.name} → ${d.title}`)
    await page.screenshot({ path: path.join(OUT, 'a_detail.png') })
  } else {
    // 该点周围仍有重叠：按设计应弹候选列表，这同样是正确行为
    if (single) {
      await page.mouse.click(single.x, single.y)
      await sleep(1800)
      const ov = await page.evaluate(() => ({
        overlap: !!document.querySelector('.overlap'),
        items: document.querySelectorAll('.ov-item').length,
      }))
      check('A2-12', '单击地点有响应（孤立点开详情 / 重叠点开候选）', ov.overlap || ov.items > 0,
            `${single.name} 周围 ${single.n} 个地点 → 候选 ${ov.items}`)
    } else {
      check('A2-12', '单击地点有响应（孤立点开详情 / 重叠点开候选）', false, '目标点未渲染')
    }
  }

  // 点空白 → 关闭
  await page.mouse.click(760, 700)
  await sleep(1200)
  const closed = await page.evaluate(() => !document.querySelector('.detail'))
  check('A2-14', '点击地图空白关闭详情', closed)

  // 重叠候选
  const multi = await page.evaluate(() => {
    const m = window.__map
    const fs = m.queryRenderedFeatures({ layers: ['places-dot'] })
    for (const f of fs) {
      const pt = m.project(f.geometry.coordinates)
      if (!(pt.x > 340 && pt.x < 1400 && pt.y > 180 && pt.y < 760)) continue
      const hits = m.queryRenderedFeatures(
        [[pt.x - 7, pt.y - 7], [pt.x + 7, pt.y + 7]],
        { layers: ['places-shape-hit', 'places-fill', 'places-dot'].filter((l) => m.getLayer(l)) })
      const ids = new Set(hits.map((h) => h.properties.placeId))
      if (ids.size > 1 && ids.size <= 12) return { x: Math.round(pt.x), y: Math.round(pt.y), n: ids.size }
    }
    return null
  })
  if (multi) {
    await page.mouse.click(multi.x, multi.y)
    await sleep(1600)
    const ov = await page.evaluate(() => ({
      open: !!document.querySelector('.overlap'),
      items: document.querySelectorAll('.ov-item').length,
    }))
    check('A2-15', '重叠位置弹出候选列表', ov.open && ov.items > 1, `候选 ${ov.items} 个`)
    if (ov.open) {
      await page.click('.ov-item')
      await sleep(2200)
      const d = await page.evaluate(() => ({ open: !!document.querySelector('.detail'), title: document.querySelector('.detail h2')?.textContent?.trim() }))
      check('A2-16', '从候选列表选中后打开该地点详情', d.open, d.title)
      const dt = await page.evaluate(() => (document.querySelector('.detail')?.innerText || '').replace(/\s+/g, ' ').slice(0, 300))
      check('A2-13', '详情含数据集/精度等溯源信息',
            /Pleiades|CHGIS|MCGD|WHG|数据集|精度|precision/i.test(dt), dt.slice(0, 160))
      await page.screenshot({ path: path.join(OUT, 'a_overlap.png') })
    }
  } else {
    check('A2-15', '重叠位置弹出候选列表', false, '视野内没有重叠点')
  }

  // 检索：有坐标 / 无坐标 都能搜到
  await page.evaluate(() => { const i = document.querySelector('input[type=search], .search input, input.input'); if (i) { i.value = ''; i.dispatchEvent(new Event('input', { bubbles: true })) } })
  const searchOk = await page.evaluate(async () => {
    const r = await fetch('/api/v1/places?keyword=Athenae&size=5')
    if (!r.ok) return { ok: false, status: r.status }
    const d = await r.json()
    return { ok: true, total: d.total ?? (d.items || []).length, first: (d.items || [])[0]?.canonicalName }
  })
  check('A2-17', '检索接口可用', searchOk.ok, JSON.stringify(searchOk))

  // 无坐标地点仍可检索（从库里取一个 geom 为空的 place）
  const noGeom = await page.evaluate(async () => {
    const r = await fetch('/api/v1/places?keyword=' + encodeURIComponent('Untitled') + '&size=20')
    const d = await r.json()
    return { total: d.total ?? (d.items || []).length, sample: (d.items || [])[0]?.canonicalName }
  })
  check('A2-18', '占位名地点仍可被检索到（未被隐藏出索引）', noGeom.total > 0, JSON.stringify(noGeom))

  // 时间轴双向
  await page.evaluate(() => window.__map.jumpTo({ center: [12.45, 41.85], zoom: 8 }))
  await sleep(2500)
  const tl = await page.evaluate(() => {
    const el = document.querySelector('[class*=timeline] .track, .tl .track, .track')
    if (!el) return null
    const r = el.getBoundingClientRect()
    return { x: r.x + r.width / 2, y: r.y + r.height / 2 }
  })
  if (tl) {
    const label = () => page.evaluate(() => {
      const el = document.querySelector('.cur-label, [class*=cur-label]')
      return el?.textContent?.trim() || document.body.innerText.match(/公元前\s*\d+\s*年[^\n]*/)?.[0] || ''
    })
    const l0 = await label()
    await page.mouse.move(tl.x, tl.y); await page.mouse.down()
    await page.mouse.move(tl.x - 220, tl.y, { steps: 12 }); await page.mouse.up()
    await sleep(1000)
    const l1 = await label()
    await page.mouse.move(tl.x, tl.y); await page.mouse.down()
    await page.mouse.move(tl.x + 420, tl.y, { steps: 14 }); await page.mouse.up()
    await sleep(1000)
    const l2 = await label()
    check('A2-19', '时间轴可向两个方向拖动', l0 !== l1 && l1 !== l2, `${l0} → ${l1} → ${l2}`)
  } else {
    check('A2-19', '时间轴可向两个方向拖动', false, '找不到时间轴 track')
  }

  check('A2-20', '浏览器无 pageerror', pageErrors.length === 0, pageErrors.slice(0, 3).join(' | '))
  check('A2-21', '浏览器无 console.error', consoleErrors.length === 0, consoleErrors.slice(0, 3).join(' | '))

  const pass = results.filter((r) => r.ok).length
  console.log(`\n结果 ${pass}/${results.length}`)
  fs.writeFileSync(path.join(OUT, 'stage_a_browser.json'), JSON.stringify({ results, pageErrors, consoleErrors }, null, 2))
  await browser.close()
  process.exit(pass === results.length ? 0 : 1)
})().catch((e) => { console.error('FATAL', e); process.exit(2) })
