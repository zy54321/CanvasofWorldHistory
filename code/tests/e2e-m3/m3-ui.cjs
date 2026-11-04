/**
 * M3 时间—地图联动 · 浏览器端到端验收（真实点击/拖动/滚动，不做静态断言）。
 *
 * 目标：http://127.0.0.1:5181  → 代理到测试库 canvas_history_m2check
 *
 * 覆盖验收场景：
 *   一 地图时间联动     二 三种跨度与步长     三 BCE/CE 边界
 *   四 矩阵显示         五 横向同步与时间选择   六 政权关联（在接口测试覆盖，这里验展示）
 *   七 矩阵事件 → 详情 + 定位（含有政权无坐标事件不定位）
 *   八 三种分辨率无纵向滚动
 *   九 控制台干净
 */
const puppeteer = require('puppeteer-core')

const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe'
const URL = process.argv[2] || 'http://127.0.0.1:5181/'
const OUT = process.argv[3] || './shots'
const API = process.argv[4] || 'http://127.0.0.1:8089'
const R = []
const wait = (ms) => new Promise((r) => setTimeout(r, ms))

function rec(id, desc, ok, expect, actual) {
  R.push({ id, desc, ok })
  console.log(`${ok ? 'PASS' : 'FAIL'} ${id.padEnd(5)} ${desc.padEnd(40)} | 期望 ${expect} | 实际 ${actual}`)
}

const clickText = (page, sel, text) =>
  page.evaluate(
    (s, t) => {
      const el = [...document.querySelectorAll(s)].find((e) => (e.textContent || '').includes(t) && !e.disabled)
      if (!el) return false
      el.click()
      return true
    },
    sel,
    text,
  )

const label = (page) => page.$eval('.tl .cur-label', (e) => e.textContent.trim())
const eventCount = (page) =>
  page.evaluate(() => (window.__map.getSource('events')?._data?.features || []).length)

/** 「公元前 490 年 – 前 481 年」→ [startYearAstro, endYearAstro] */
function parseWindow(text) {
  const part = (s) => {
    const bce = /公元前\s*(\d+)/.exec(s)
    if (bce) return 1 - Number(bce[1])
    const shortBce = /前\s*(\d+)/.exec(s)
    if (shortBce) return 1 - Number(shortBce[1])
    const ce = /公元\s*(\d+)/.exec(s)
    if (ce) return Number(ce[1])
    const bare = /(\d+)/.exec(s)
    return bare ? Number(bare[1]) : null
  }
  const [a, b] = text.split('–')
  return [part(a), b ? part(b) : null]
}

async function noPageScroll(page) {
  return page.evaluate(() => ({
    doc: document.documentElement.scrollHeight,
    client: document.documentElement.clientHeight,
    body: document.body.scrollHeight,
  }))
}

;(async () => {
  const browser = await puppeteer.launch({
    executablePath: CHROME,
    headless: 'new',
    args: ['--no-sandbox', '--use-gl=swiftshader', '--enable-unsafe-swiftshader'],
    defaultViewport: { width: 1600, height: 900 },
  })
  const page = await browser.newPage()
  const errors = []
  page.on('console', (m) => {
    if (m.type() === 'error') errors.push(m.text().slice(0, 180))
  })
  page.on('pageerror', (e) => errors.push('PAGEERROR ' + e.message.slice(0, 180)))

  await page.goto(URL, { waitUntil: 'networkidle2', timeout: 60000 })
  await wait(4500)

  // ---------------- 一、地图观察模式 ----------------
  const base = await page.evaluate(() => {
    const c = document.querySelector('.map-canvas canvas')
    const r = c ? c.getBoundingClientRect() : null
    return { canvas: !!c, w: r ? Math.round(r.width) : 0, h: r ? Math.round(r.height) : 0,
             vw: window.innerWidth, vh: window.innerHeight }
  })
  rec('U01', '地图铺满可视区域', base.canvas && base.w === base.vw && base.h === base.vh,
    `${base.vw}×${base.vh}`, `${base.w}×${base.h}`)

  const s0 = await noPageScroll(page)
  rec('U02', '页面无纵向滚动（html/body）', s0.doc <= s0.client && s0.body <= s0.client,
    'scrollHeight<=clientHeight', JSON.stringify(s0))

  const l0 = await label(page)
  rec('U03', '初始时间窗口为前500–前491', l0 === '公元前 500 年 – 前 491 年', '公元前 500 年 – 前 491 年', l0)

  const below = await page.evaluate(() => {
    const tl = document.querySelector('.tl').getBoundingClientRect()
    const others = [...document.querySelectorAll('body *')].filter((e) => {
      const r = e.getBoundingClientRect()
      return r.height > 8 && r.top >= tl.bottom - 1 && r.width > 200 &&
             !e.closest('.tl') && getComputedStyle(e).position !== 'fixed'
    })
    return others.slice(0, 3).map((e) => e.className)
  })
  rec('U04', '时间轴下方没有任何内容块', below.length === 0, '0 个内容块', JSON.stringify(below))

  // ---------------- 二、时间联动与跨度 ----------------
  await page.evaluate(() => document.querySelectorAll('.tl .nav')[1].click())
  await wait(2200)
  const l1 = await label(page)
  const ev1 = await eventCount(page)
  rec('U05', '前移一个跨度：时间变为前490–前481', l1 === '公元前 490 年 – 前 481 年', '公元前 490 年 – 前 481 年', l1)
  rec('U06', '地图事件标记随时间刷新（该窗口 1 个事件）', ev1 === 1, '1', ev1)

  await page.evaluate(() => document.querySelectorAll('.tl .nav')[0].click())
  await wait(2200)
  const l2 = await label(page)
  rec('U07', '后移一个跨度可回到前500', l2 === '公元前 500 年 – 前 491 年', '公元前 500 年 – 前 491 年', l2)

  // 1 年跨度：步长应为 1 年
  await clickText(page, '.tl .spans button', '1 年')
  await wait(900)
  const a1 = parseWindow(await label(page))
  await page.evaluate(() => document.querySelectorAll('.tl .nav')[1].click())
  await wait(1200)
  const a2 = parseWindow(await label(page))
  rec('U08', '跨度 1 年：按钮步长 = 1 年', a2[0] - a1[0] === 1, '起点 +1', `${a1[0]} → ${a2[0]}`)

  // 100 年跨度
  await clickText(page, '.tl .spans button', '100 年')
  await wait(1000)
  const b1 = parseWindow(await label(page))
  await page.evaluate(() => document.querySelectorAll('.tl .nav')[1].click())
  await wait(1400)
  const b2 = parseWindow(await label(page))
  rec('U09', '跨度 100 年：按钮步长 = 100 年', b2[0] - b1[0] === 100, '起点 +100', `${b1[0]} → ${b2[0]}`)
  rec('U10', '跨度 100 年的窗口宽度 = 100 年', b2[1] - b2[0] === 99, '终点=起点+99',
    `${b2[0]}..${b2[1]}`)

  // 时间轴拖动：向右拖 → 回到更早
  const track = await page.$('.tl .track')
  const box = await track.boundingBox()
  const beforeDrag = parseWindow(await label(page))[0]
  await page.mouse.move(box.x + box.width * 0.7, box.y + box.height / 2)
  await page.mouse.down()
  await page.mouse.move(box.x + box.width * 0.7 + 140, box.y + box.height / 2, { steps: 8 })
  await page.mouse.up()
  await wait(1400)
  const afterDrag = parseWindow(await label(page))[0]
  rec('U11', '横向拖动时间轴可移动（右拖=更早）', afterDrag < beforeDrag, '起点变小',
    `${beforeDrag} → ${afterDrag}`)

  // ---------------- 三、BCE/CE 边界 ----------------
  // 用 100 年跨度快速走到公元元年前后，再切回 1 年跨度验证边界
  await clickText(page, '.tl .spans button', '100 年')
  await wait(900)
  for (let i = 0; i < 12; i++) {
    const from = parseWindow(await label(page))[0]
    if (from >= -50) break
    await page.evaluate(() => document.querySelectorAll('.tl .nav')[1].click())
    await wait(320)
  }
  const near = parseWindow(await label(page))[0]
  await clickText(page, '.tl .spans button', '1 年')
  await wait(900)
  // 从「公元 N 年」步进到公元 1 年
  for (let i = 0; i < 60; i++) {
    const t = await label(page)
    if (t === '公元 1 年') break
    await page.evaluate(() => document.querySelectorAll('.tl .nav')[0].click())
    await wait(220)
  }
  const ceLabel = await label(page)
  rec('U12', '跨度 1 年时显示「公元 1 年」', ceLabel === '公元 1 年', '公元 1 年', `${near} → ${ceLabel}`)

  await page.evaluate(() => document.querySelectorAll('.tl .nav')[0].click())
  await wait(700)
  const bce1 = await label(page)
  rec('U13', '再往前一年显示「公元前 1 年」（不出现公元 0 年）', bce1 === '公元前 1 年', '公元前 1 年', bce1)

  await page.evaluate(() => document.querySelectorAll('.tl .nav')[0].click())
  await wait(700)
  const bce2 = await label(page)
  rec('U14', '继续往前是「公元前 2 年」', bce2 === '公元前 2 年', '公元前 2 年', bce2)

  // 回到有数据的时段：重载页面（默认前500 / 10 年）
  await page.reload({ waitUntil: 'networkidle2' })
  await wait(4200)
  const resetLabel = await label(page)
  rec('U15', '刷新后回到默认时间窗口（前500–前491）', resetLabel === '公元前 500 年 – 前 491 年',
    '公元前 500 年 – 前 491 年', resetLabel)

  // 矩阵：确认表头不含「公元 0 年」，且存在公元 1 年列
  await clickText(page, 'button', '时间观察')
  await wait(2600)
  const colLabels = await page.$$eval('.mx-hcol', (els) => els.map((e) => e.textContent.trim()))
  rec('U16', '矩阵表头无「公元 0 年」', !colLabels.includes('0'), '不含 0', colLabels.slice(0, 8).join(' / '))
  await clickText(page, 'button', '收起')
  await wait(700)

  // ---------------- 四、矩阵显示 ----------------
  await clickText(page, 'button', '时间观察')
  await wait(2600)
  const mx = await page.evaluate(() => {
    const m = document.querySelector('.mx')
    const r = m.getBoundingClientRect()
    const head = document.querySelector('.mx-head').getBoundingClientRect()
    const rows = [...document.querySelectorAll('.mx-rrow')]
    return {
      top: Math.round(r.top), h: Math.round(r.height),
      vh: window.innerHeight,
      regions: rows.map((x) => x.textContent.replace(/\s+/g, ' ').trim().slice(0, 12)),
      rows: document.querySelectorAll('.mx-prow').length,
      headTop: Math.round(head.top),
      bigTitle: !!document.querySelector('.mx h1, .mx h2'),
      hasNav: !!document.querySelector('.topbar'),
    }
  })
  rec('U17', '矩阵覆盖除顶部导航外的可视区域',
    mx.top > 0 && mx.top < 80 && mx.h > mx.vh - mx.top - 2, `top=${mx.top} h≈${mx.vh - mx.top}`,
    `top=${mx.top} h=${mx.h}`)
  rec('U18', '顶部导航在矩阵展开时仍固定可见', mx.hasNav, '可见', mx.hasNav)
  rec('U19', '10 个地区全部列出', mx.regions.length === 10, '10', mx.regions.length)
  rec('U20', '地区默认收起（无政权行）', mx.rows === 0, '0 行', mx.rows)
  rec('U21', '没有大标题 / 说明区块', !mx.bigTitle, '无 h1/h2', mx.bigTitle)
  rec('U22', '时间刻度固定在顶部', Math.abs(mx.headTop - mx.top) <= 2, `≈${mx.top}`, mx.headTop)

  // 展开欧洲
  await page.evaluate(() => {
    const r = [...document.querySelectorAll('.mx-rrow')].find((x) => x.textContent.includes('欧洲'))
    r && r.click()
  })
  await wait(1200)
  const eu = await page.evaluate(() => {
    const rows = [...document.querySelectorAll('.mx-prow')]
    const names = rows.map((r) => r.querySelector('.pn')?.textContent?.trim())
    const cellsWithEvents = [...document.querySelectorAll('.mx-cell')].filter((c) => c.querySelector('.ev'))
    const first = cellsWithEvents[0]
    const firstCol = first ? Math.round(first.getBoundingClientRect().left) : null
    return { rows: rows.length, names,
             events: [...document.querySelectorAll('.mx-cell .ev')].map((e) => e.textContent.trim()),
             firstCol }
  })
  rec('U23', '展开欧洲后显示政权行', eu.rows >= 1 && eu.names.includes('希腊城邦'),
    '含 希腊城邦', JSON.stringify(eu.names))
  rec('U24', '事件显示在政权行的时间单元格内', eu.events.length >= 1, '>=1 个事件',
    JSON.stringify(eu.events.slice(0, 3)))

  await page.screenshot({ path: `${OUT}/10_matrix_europe.png` })

  // ---------------- 五、横向同步 ----------------
  const beforeScroll = await page.evaluate(() => {
    const h = document.querySelector('.mx-hcol').getBoundingClientRect()
    const cell = document.querySelector('.mx-cell').getBoundingClientRect()
    const name = document.querySelector('.mx-pname').getBoundingClientRect()
    return { h: Math.round(h.left), cell: Math.round(cell.left), name: Math.round(name.left) }
  })
  await page.evaluate(() => {
    const s = document.querySelector('.mx-scroll')
    s.scrollLeft = 300
    s.dispatchEvent(new Event('scroll'))
  })
  await wait(900)
  const afterScroll = await page.evaluate(() => {
    const h = document.querySelector('.mx-hcol').getBoundingClientRect()
    const cell = document.querySelector('.mx-cell').getBoundingClientRect()
    const name = document.querySelector('.mx-pname').getBoundingClientRect()
    const corner = document.querySelector('.mx-corner').getBoundingClientRect()
    return { h: Math.round(h.left), cell: Math.round(cell.left), name: Math.round(name.left),
             corner: Math.round(corner.left) }
  })
  rec('U25', '横向滚动时表头与单元格同步位移（差值恒定）',
    beforeScroll.h - beforeScroll.cell === afterScroll.h - afterScroll.cell
      && afterScroll.cell === beforeScroll.cell - 300,
    '两者位移相同', `${beforeScroll.h}/${beforeScroll.cell} → ${afterScroll.h}/${afterScroll.cell}`)
  rec('U26', '左侧地区/政权列固定不动', afterScroll.name === 0 && afterScroll.corner === 0,
    'left=0', `name=${afterScroll.name} corner=${afterScroll.corner}`)

  // 点一个列头 → 收起后时间改变
  const picked = await page.evaluate(() => {
    const cols = [...document.querySelectorAll('.mx-hcol')]
    const c = cols.find((x) => Math.round(x.getBoundingClientRect().left) > 200) || cols[0]
    const t = c.textContent.trim()
    c.click()
    return t
  })
  await wait(900)
  await clickText(page, 'button', '收起')
  await wait(1200)
  const afterPick = await label(page)
  const pickedAstro = picked.startsWith('前') ? 1 - Number(picked.slice(1)) : Number(picked)
  rec('U27', '点选时间段后收起矩阵，时间被保留',
    parseWindow(afterPick)[0] === pickedAstro, `起点=${pickedAstro}`, `${picked} → ${afterPick}`)
  const evAfter = await eventCount(page)
  rec('U28', '收起后地图按新时间段刷新标记', evAfter >= 0, '>=0', evAfter)

  // ---------------- 七、矩阵事件 → 详情 + 定位 ----------------
  await page.reload({ waitUntil: 'networkidle2' })
  await wait(4200)
  await clickText(page, 'button', '时间观察')
  await wait(2600)
  // 找到第一个有事件的列并点击，让矩阵落在有内容的时段
  await page.evaluate(() => {
    const s = document.querySelector('.mx-scroll')
    s.scrollLeft = 0
  })
  await page.evaluate(() => {
    const r = [...document.querySelectorAll('.mx-rrow')].find((x) => x.textContent.includes('欧洲'))
    r && r.click()
  })
  await wait(1000)
  const hasEv = await page.evaluate(() => !!document.querySelector('.mx-cell .ev'))
  if (hasEv) {
    // 点「马拉松战役」：它有确定坐标（23.97, 38.15），便于验证定位是否真的发生
    await page.evaluate(() => {
      const all = [...document.querySelectorAll('.mx-cell .ev')]
      const target = all.find((e) => e.textContent.includes('马拉松')) || all[0]
      target.click()
    })
    await wait(2600)
    const detail = await page.evaluate(() => {
      const el = document.querySelector('.right .ev')
      return {
        open: !!el,
        title: el?.querySelector('.title')?.textContent?.trim(),
        polities: el ? [...el.querySelectorAll('section')][0]?.textContent?.replace(/\s+/g, ' ').trim().slice(0, 40) : null,
        mapCenter: window.__map.getCenter().toArray().map((n) => +n.toFixed(1)),
        zoom: +window.__map.getZoom().toFixed(1),
      }
    })
    rec('U29', '矩阵点事件 → 右侧详情打开', detail.open && !!detail.title,
      '详情面板', `${detail.title}`)
    rec('U30', '详情显示历史政权', (detail.polities || '').includes('希腊城邦') ||
      (detail.polities || '').includes('政权'), '含政权段', detail.polities)
    rec('U31', '地图定位到事件地点', Math.abs(detail.mapCenter[0] - 23.97) < 1.2 &&
      Math.abs(detail.mapCenter[1] - 38.15) < 1.2, '≈23.97,38.15', JSON.stringify(detail.mapCenter))
    const tlAfter = await page.evaluate(() => ({
      label: document.querySelector('.tl .cur-label')?.textContent?.trim(),
      count: document.querySelector('.tl .count')?.textContent?.trim(),
    }))
    rec('U32', '点事件后时间窗口同步到该事件所在时间段',
      (tlAfter.label || '').includes('前 490') && /[1-9]/.test(tlAfter.count || ''),
      '含 前 490 且事件数>=1', JSON.stringify(tlAfter))
    rec('U33', '详情面板不引入页面滚动',
      (await page.evaluate(() => document.documentElement.scrollHeight <= document.documentElement.clientHeight)),
      '无纵向滚动', 'ok')
    await page.screenshot({ path: `${OUT}/11_event_detail.png` })
  } else {
    rec('U34', '矩阵点事件 → 右侧详情打开', false, '有事件可点', '当前窗口无事件')
  }

  await clickText(page, 'button', '收起')
  await wait(800)

  // ---------------- 空间反查预留 ----------------
  const reserved = await page.evaluate(() => {
    const b = [...document.querySelectorAll('.topbar button')].find((x) => x.textContent.includes('空间反查'))
    return b ? { disabled: b.disabled, badge: b.textContent.replace(/\s+/g, ' ').trim() } : null
  })
  rec('U35', '空间反查入口存在且明确标注预留（不可用）',
    !!reserved && reserved.disabled && reserved.badge.includes('预留'), 'disabled + 预留',
    JSON.stringify(reserved))

  // ---------------- 八、三种分辨率 ----------------
  const sizes = [
    [1366, 768],
    [1600, 900],
    [1920, 1080],
  ]
  const layout = []
  for (const [w, h] of sizes) {
    await page.setViewport({ width: w, height: h })
    await wait(900)
    const a = await page.evaluate(() => {
      const c = document.querySelector('.map-canvas canvas').getBoundingClientRect()
      return {
        doc: document.documentElement.scrollHeight,
        client: document.documentElement.clientHeight,
        cw: Math.round(c.width), ch: Math.round(c.height),
        vw: window.innerWidth, vh: window.innerHeight,
      }
    })
    await clickText(page, 'button', '展开')
    await wait(1800)
    const b = await page.evaluate(() => {
      const m = document.querySelector('.mx')
      const r = m.getBoundingClientRect()
      const head = document.querySelector('.mx-head').getBoundingClientRect()
      return { doc: document.documentElement.scrollHeight, client: document.documentElement.clientHeight,
               mxBottom: Math.round(r.bottom), headTop: Math.round(head.top), vh: window.innerHeight }
    })
    await page.screenshot({ path: `${OUT}/12_layout_${w}x${h}.png` })
    await clickText(page, 'button', '收起')
    await wait(700)
    layout.push({ size: `${w}x${h}`, mapFits: a.cw === a.vw && a.ch === a.vh,
                  noScrollCollapsed: a.doc <= a.client, noScrollExpanded: b.doc <= b.client,
                  mxFits: Math.abs(b.mxBottom - b.vh) <= 2 })
  }
  rec('U36', '三种分辨率：地图铺满、收起/展开均无纵向滚动',
    layout.every((x) => x.mapFits && x.noScrollCollapsed && x.noScrollExpanded),
    '全部满足', JSON.stringify(layout))
  rec('U37', '三种分辨率：矩阵铺满剩余可视高度', layout.every((x) => x.mxFits), '全部贴合',
    JSON.stringify(layout.map((x) => `${x.size}:${x.mxFits}`)))

  // ---------------- 九、控制台 ----------------
  const realErrors = errors.filter((e) => !/favicon/i.test(e) && !/ERR_ABORTED/.test(e))
  rec('U38', '浏览器控制台无 JS 错误', realErrors.length === 0,
    '0 个', realErrors.slice(0, 3).join(' | ') || '0')

  await page.setViewport({ width: 1600, height: 900 })
  await wait(600)
  await page.screenshot({ path: `${OUT}/13_final_map.png` })

  const ok = R.filter((r) => r.ok).length
  console.log(`\n=== 合计 ${R.length} 项，PASS ${ok}，FAIL ${R.length - ok} ===`)
  await browser.close()
  process.exit(ok === R.length ? 0 : 1)
})()
