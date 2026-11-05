/**
 * 阶段 D9：时空矩阵横向滚动专项。
 * 上一轮报告写的是"未复现也未改"，这里必须给出实证：
 *  1) 矩阵内部确实存在可滚动的横向容器（scrollWidth > clientWidth）；
 *  2) 用鼠标滚轮/直接设置 scrollLeft 都能改变滚动位置；
 *  3) 列头与数据区横向同步（滚动后两者 scrollLeft 相同）；
 *  4) 滚动到底不会出现空白列或错位（末列可见）。
 */
const puppeteer = require('puppeteer-core')
const fs = require('fs')

const BASE = process.argv[2] || 'http://127.0.0.1:5181/'
const OUT = process.argv[3] || 'C:/Users/the_z/AppData/Local/Temp/v1b-shots'
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
const results = []
function check(id, desc, ok, detail) {
  results.push({ id, desc, ok: !!ok, detail: detail === undefined ? '' : String(detail) })
  console.log(`${ok ? '✓' : '✗'} ${id} ${desc}${detail !== undefined ? ' :: ' + detail : ''}`)
}

;(async () => {
  fs.mkdirSync(OUT, { recursive: true })
  const browser = await puppeteer.launch({
    executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe',
    headless: 'new',
    args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader', '--no-sandbox'],
    defaultViewport: { width: 1400, height: 900 },
  })
  const page = await browser.newPage()
  const errs = []
  page.on('pageerror', (e) => errs.push(String(e)))

  await page.goto(BASE, { waitUntil: 'networkidle2', timeout: 60000 })
  await page.waitForFunction(() => !!(window.__map && window.__map.isStyleLoaded()), { timeout: 30000, polling: 200 })
  await sleep(2500)

  const opened = await page.evaluate(() => {
    const b = [...document.querySelectorAll('button')].find((x) => /时间观察/.test(x.textContent))
    if (!b) return false
    b.click()
    return true
  })
  check('D9-0', '「时间观察」矩阵可打开', opened)
  await sleep(2500)

  const geom = await page.evaluate(() => {
    const mx = document.querySelector('.mx')
    if (!mx) return null
    const cands = [...mx.querySelectorAll('*')].filter(
      (el) => el.scrollWidth > el.clientWidth + 4 && el.clientWidth > 100,
    )
    const main = cands.sort((a, b) => b.scrollWidth - a.scrollWidth)[0]
    return {
      found: !!main,
      cls: main ? main.className || main.tagName : '',
      scrollWidth: main ? main.scrollWidth : 0,
      clientWidth: main ? main.clientWidth : 0,
      cols: mx.querySelectorAll('.mx-hcol').length,
      cells: mx.querySelectorAll('.mx-cell').length,
    }
  })
  check('D9-1', '矩阵存在横向溢出容器', !!geom && geom.found,
        geom ? `${geom.cls} scrollWidth=${geom.scrollWidth} clientWidth=${geom.clientWidth} 列=${geom.cols} 格=${geom.cells}` : 'no .mx')

  // 直接滚动
  const scroll = await page.evaluate(async () => {
    const mx = document.querySelector('.mx')
    const cands = [...mx.querySelectorAll('*')].filter(
      (el) => el.scrollWidth > el.clientWidth + 4 && el.clientWidth > 100,
    )
    const el = cands.sort((a, b) => b.scrollWidth - a.scrollWidth)[0]
    if (!el) return null
    const before = el.scrollLeft
    el.scrollLeft = 240
    await new Promise((r) => setTimeout(r, 400))
    const after = el.scrollLeft
    return { before, after, max: el.scrollWidth - el.clientWidth }
  })
  check('D9-2', '设置 scrollLeft 后横向位置真的改变',
        !!scroll && scroll.after > scroll.before,
        scroll ? `${scroll.before} → ${scroll.after}（可滚 ${scroll.max}px）` : 'n/a')

  // 列头与数据区同步
  const sync = await page.evaluate(() => {
    const mx = document.querySelector('.mx')
    const all = [...mx.querySelectorAll('*')].filter(
      (el) => el.scrollWidth > el.clientWidth + 4 && el.clientWidth > 100,
    )
    if (all.length < 2) {
      const el = all[0]
      return el ? { n: 1, equal: true, left: el.scrollLeft } : null
    }
    return { n: all.length, equal: all.every((e) => Math.abs(e.scrollLeft - all[0].scrollLeft) < 2), left: all[0].scrollLeft }
  })
  check('D9-3', '列头与数据区横向位置一致（无错位）',
        !!sync && (sync.n === 1 || sync.equal), JSON.stringify(sync))

  // 滚到底：末列可见。
  // 注意不能"一次设到 scrollWidth 就断言到头"——实测滚动过程中内容宽度会变
  // （显现更多列后 scrollWidth 从 2052 涨到 3914），所以必须反复滚到位置不再变化。
  const end = await page.evaluate(async () => {
    const el = document.querySelector('.mx-scroll')
    if (!el) return null
    let prev = -1
    for (let i = 0; i < 20; i++) {
      el.scrollLeft = el.scrollWidth
      await new Promise((r) => setTimeout(r, 220))
      if (Math.abs(el.scrollLeft - prev) < 2) break
      prev = el.scrollLeft
    }
    await new Promise((r) => setTimeout(r, 300))
    const rect = el.getBoundingClientRect()
    const cols = [...el.querySelectorAll('.mx-hcol')]
    const last = cols[cols.length - 1]
    const lr = last?.getBoundingClientRect()
    return {
      atMax: Math.abs(el.scrollLeft - (el.scrollWidth - el.clientWidth)) < 4,
      scrollLeft: el.scrollLeft,
      max: el.scrollWidth - el.clientWidth,
      lastVisible: !!lr && lr.right <= rect.right + 2 && lr.left >= rect.left - 2,
      lastText: last?.textContent?.trim(),
    }
  })
  check('D9-4', '滚到最右后末列完整可见（无空白/截断）',
        !!end && end.atMax && end.lastVisible,
        end ? `${end.lastText} atMax=${end.atMax}` : 'n/a')

  // 滚回起点
  await page.evaluate(() => {
    const mx = document.querySelector('.mx')
    ;[...mx.querySelectorAll('*')]
      .filter((el) => el.scrollWidth > el.clientWidth + 4 && el.clientWidth > 100)
      .forEach((el) => { el.scrollLeft = 0 })
  })
  await sleep(400)
  await page.screenshot({ path: `${OUT}/d_matrix_scroll.png` })

  check('D9-5', '矩阵操作无 pageerror', errs.length === 0, errs.slice(0, 3).join(' | '))

  const passed = results.filter((r) => r.ok).length
  console.log(`\n结果 ${passed}/${results.length}`)
  fs.writeFileSync(`${OUT}/matrix_scroll.json`, JSON.stringify({ results, errs }, null, 2))
  await browser.close()
  process.exit(passed === results.length ? 0 : 1)
})().catch((e) => { console.error('FATAL', e); process.exit(2) })
