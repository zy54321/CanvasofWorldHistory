/**
 * M2 管理界面端到端测试（浏览器真实操作）。
 * 目标：http://127.0.0.1:5181  → 代理到测试库 canvas_history_m2check（不碰正式库）
 *
 * 覆盖：管理面板打开、三页签、新建地点/人物/事件、添加名称、添加坐标、
 *       通过对象选择器建立三类关联、删除确认、列表刷新、时间 BCE 输入。
 */
const puppeteer = require('puppeteer-core')
const fs = require('node:fs')

const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe'
const URL = process.argv[2] || 'http://127.0.0.1:5181/'
const OUT = process.argv[3] || './shots'
const R = []

const wait = (ms) => new Promise((r) => setTimeout(r, ms))

function rec(id, desc, ok, expect, actual) {
  R.push({ id, desc, ok })
  console.log(`${ok ? 'PASS' : 'FAIL'} ${id.padEnd(5)} ${desc.padEnd(42)} | 期望 ${expect} | 实际 ${actual}`)
}

async function clickText(page, selector, text, exact = false) {
  return page.evaluate(
    (sel, t, ex) => {
      const els = [...document.querySelectorAll(sel)]
      const el = els.find((e) => {
        const s = (e.textContent || '').replace(/\s+/g, ' ').trim()
        return ex ? s === t : s.includes(t)
      })
      if (!el) return false
      el.click()
      return true
    },
    selector,
    text,
    exact,
  )
}

async function fill(page, selector, value, index = 0) {
  return page.evaluate(
    (sel, v, i) => {
      const el = document.querySelectorAll(sel)[i]
      if (!el) return false
      el.focus()
      el.value = v
      el.dispatchEvent(new Event('input', { bubbles: true }))
      el.dispatchEvent(new Event('change', { bubbles: true }))
      return true
    },
    selector,
    value,
    index,
  )
}

const text = (page, sel) =>
  page.evaluate((s) => {
    const el = document.querySelector(s)
    return el ? el.innerText.replace(/\s+/g, ' ').trim() : ''
  }, sel)

;(async () => {
  fs.mkdirSync(OUT, { recursive: true })
  const browser = await puppeteer.launch({
    executablePath: CHROME,
    headless: 'new',
    args: ['--no-sandbox', '--disable-dev-shm-usage', '--use-gl=swiftshader', '--enable-unsafe-swiftshader'],
    defaultViewport: { width: 1600, height: 950 },
  })
  const page = await browser.newPage()
  const errors = []
  page.on('pageerror', (e) => errors.push('pageerror: ' + e.message))
  page.on('console', (m) => {
    if (m.type() === 'error') errors.push('console: ' + m.text())
  })
  page.on('dialog', (d) => d.accept())

  await page.goto(URL, { waitUntil: 'networkidle2', timeout: 45000 })
  await wait(2500)

  // ---------- 0. 打开管理面板 ----------
  const opened = await clickText(page, 'button', '内容管理')
  await wait(900)
  const tabText = await text(page, '.manage .tabs')
  rec('U00', '管理入口可打开三页签面板', opened && /地点/.test(tabText) && /人物/.test(tabText) && /事件/.test(tabText),
    '面板打开且含地点/人物/事件', tabText)
  await page.screenshot({ path: `${OUT}/01_manage_open.png` })

  // ---------- 1. 地点：新建 ----------
  await clickText(page, '.manage .tabs button', '地点', true)
  await wait(600)
  await clickText(page, '.manage .side button', '新建地点')
  await wait(600)
  await fill(page, '.manage .main .m2-field input[type=text]', '界面测试地点')
  await fill(page, '.manage .main textarea', '由浏览器端到端测试创建')
  await clickText(page, '.manage .main .actions button', '创建地点')
  await wait(1500)
  const placeTitle = await text(page, '.manage .main .title')
  rec('U01', '界面新建地点 → 进入该地点编辑态', /地点 #\d+/.test(placeTitle),
    '标题显示 地点 #id', placeTitle)
  await page.screenshot({ path: `${OUT}/02_place_created.png` })

  // ---------- 2. 地点：加历史名称 ----------
  await clickText(page, '.manage .main .m2-sub button', '添加名称')
  await wait(500)
  await fill(page, '.manage .main .subform input[type=text]', '界面测试城', 0)
  await fill(page, '.manage .main .subform input[type=text]', 'zh', 1)
  await page.evaluate(() => {
    const sel = document.querySelectorAll('.manage .main .subform select')
    if (sel[0]) {
      sel[0].value = 'primary'
      sel[0].dispatchEvent(new Event('change', { bubbles: true }))
    }
    if (sel[1]) {
      sel[1].value = 'bounded'
      sel[1].dispatchEvent(new Event('change', { bubbles: true }))
    }
  })
  await wait(400)
  // 填有效期：公元前 500 ~ 前 400
  await page.evaluate(() => {
    const rows = [...document.querySelectorAll('.manage .main .subform .astro-year')]
    const setYear = (row, era, y) => {
      const s = row.querySelector('select')
      const i = row.querySelector('input')
      s.value = era
      s.dispatchEvent(new Event('change', { bubbles: true }))
      i.value = String(y)
      i.dispatchEvent(new Event('input', { bubbles: true }))
    }
    if (rows[0]) setYear(rows[0], 'BCE', 500)
    if (rows[1]) setYear(rows[1], 'BCE', 400)
  })
  await wait(400)
  await clickText(page, '.manage .main .subform .actions button', '保存名称')
  await wait(1600)
  const namesBlock = await text(page, '.manage .main .m2-row')
  rec('U02', '界面添加带有效期的历史名称', /界面测试城/.test(namesBlock) && /前500/.test(namesBlock),
    '名称行出现且显示 前500~前400', namesBlock.slice(0, 90))
  await page.screenshot({ path: `${OUT}/03_place_name.png` })

  // ---------- 3. 地点：加坐标 ----------
  await clickText(page, '.manage .main .m2-sub button', '添加位置')
  await wait(500)
  await page.evaluate(() => {
    const inputs = [...document.querySelectorAll('.manage .main .subform input[type=text]')]
    const set = (el, v) => {
      el.value = v
      el.dispatchEvent(new Event('input', { bubbles: true }))
    }
    if (inputs[0]) set(inputs[0], '112.5')
    if (inputs[1]) set(inputs[1], '34.7')
    const sels = [...document.querySelectorAll('.manage .main .subform select')]
    if (sels[0]) {
      sels[0].value = 'approximate'
      sels[0].dispatchEvent(new Event('change', { bubbles: true }))
    }
  })
  await wait(300)
  await clickText(page, '.manage .main .subform .actions button', '保存位置')
  await wait(1600)
  const locText = await text(page, '.manage .main .m2-row')
  rec('U03', '界面添加坐标与定位精度', /112\.50000/.test(await text(page, '.manage .main')),
    '出现 112.50000, 34.70000', locText.slice(0, 80))
  await page.screenshot({ path: `${OUT}/04_place_location.png` })

  // ---------- 4. 人物：新建 + BCE 生年 ----------
  await clickText(page, '.manage .tabs button', '人物', true)
  await wait(800)
  await clickText(page, '.manage .side button', '新建人物')
  await wait(600)
  await fill(page, '.manage .main .m2-field input[type=text]', '界面测试人物', 0)
  // 生年：公元前 551
  await page.evaluate(() => {
    const row = document.querySelector('.manage .main .astro-year')
    const s = row.querySelector('select')
    const i = row.querySelector('input')
    s.value = 'BCE'
    s.dispatchEvent(new Event('change', { bubbles: true }))
    i.value = '551'
    i.dispatchEvent(new Event('input', { bubbles: true }))
  })
  await wait(300)
  await page.evaluate(() => {
    // 出生精度是「.m2-field 下的 select」；须排除 .astro-year 内的纪元选择框
    const sels = [...document.querySelectorAll('.manage .main select')].filter(
      (s) => !s.closest('.astro-year'),
    )
    const birth = sels[0]
    if (birth) {
      birth.value = 'approximate'
      birth.dispatchEvent(new Event('change', { bubbles: true }))
    }
  })
  await wait(300)
  await clickText(page, '.manage .main .actions button', '创建人物')
  await wait(1600)
  const pTitle = await text(page, '.manage .main .title')
  const pHint = await page.evaluate(() => {
    const el = [...document.querySelectorAll('.manage .main .astro-year .hint')][0]
    return el ? el.innerText : ''
  })
  rec('U04', '界面新建人物并输入公元前 551 年', /人物 #\d+/.test(pTitle) && /-550/.test(pHint),
    '标题 人物 #id，生年内部 -550', `${pTitle} / ${pHint}`)
  await page.screenshot({ path: `${OUT}/05_person_created.png` })

  // ---------- 5. 人物：关联活动地点（对象选择器） ----------
  await clickText(page, '.manage .main .m2-sub button', '关联地点')
  await wait(500)
  await clickText(page, '.manage .main .subform button', '选择地点')
  await wait(1500)
  const pickerOpen = await page.$('.mask .picker')
  rec('U05', '关联地点弹出对象选择器（非手填 ID）', !!pickerOpen, '出现选择器弹窗', !!pickerOpen)
  await page.screenshot({ path: `${OUT}/06_picker_place.png` })
  const picked = await page.evaluate(() => {
    const items = [...document.querySelectorAll('.picker .item')]
    if (!items.length) return null
    const el = items[0]
    const name = el.querySelector('.nm')?.textContent?.trim()
    el.click()
    return name
  })
  await wait(800)
  await page.evaluate(() => {
    const inputs = [...document.querySelectorAll('.manage .main .subform input[type=text]')]
    // 关系类型输入框（第 2 个 input，第 1 个是只读的地点名）
    const rel = inputs[1]
    if (rel) {
      rel.value = 'residence'
      rel.dispatchEvent(new Event('input', { bubbles: true }))
    }
  })
  await wait(200)
  await clickText(page, '.manage .main .subform .actions button', '保存关联')
  await wait(1600)
  const linkText = await text(page, '.manage .main .m2-row')
  rec('U06', '选定地点后建立活动地点关联', /residence/.test(await text(page, '.manage .main')),
    '关联行含 residence', `picked=${picked} / ${linkText.slice(0, 70)}`)
  await page.screenshot({ path: `${OUT}/07_person_place_link.png` })

  // ---------- 6. 人物：关联事件 ----------
  await clickText(page, '.manage .main .m2-sub button', '关联事件')
  await wait(500)
  await clickText(page, '.manage .main .subform button', '选择事件')
  await wait(1500)
  const evPicked = await page.evaluate(() => {
    const items = [...document.querySelectorAll('.picker .item')]
    if (!items.length) return null
    const el = items[0]
    const name = el.querySelector('.nm')?.textContent?.trim()
    el.click()
    return name
  })
  await wait(800)
  await clickText(page, '.manage .main .subform .actions button', '保存关联')
  await wait(1600)
  const evLink = await text(page, '.manage .main')
  rec('U07', '通过选择器关联事件', evPicked ? /person|角色|participant/.test(evLink) && evLink.includes(evPicked) : false,
    '关联行出现所选事件', `picked=${evPicked}`)
  await page.screenshot({ path: `${OUT}/08_person_event_link.png` })

  // ---------- 7. 事件：新建（时间未知）+ 关联人物与地点 ----------
  await clickText(page, '.manage .tabs button', '事件', true)
  await wait(800)
  await clickText(page, '.manage .side button', '新建事件')
  await wait(600)
  await fill(page, '.manage .main .m2-field input[type=text]', '界面测试事件', 0)
  await clickText(page, '.manage .main .actions button', '创建事件')
  await wait(1600)
  const eTitle = await text(page, '.manage .main .title')
  const ePrec = await page.evaluate(() => {
    const s = document.querySelector('.manage .main select')
    return s ? s.value : ''
  })
  rec('U08', '新建事件（时间判定=未知，不填年份）', /事件 #\d+/.test(eTitle) && ePrec === 'unknown',
    '标题 事件 #id，精度 unknown', `${eTitle} / ${ePrec}`)
  await page.screenshot({ path: `${OUT}/09_event_created.png` })

  await clickText(page, '.manage .main .m2-sub button', '关联人物')
  await wait(500)
  await clickText(page, '.manage .main .subform button', '选择人物')
  await wait(1500)
  const perPicked = await page.evaluate(() => {
    const items = [...document.querySelectorAll('.picker .item')]
    if (!items.length) return null
    const el = items[0]
    const name = el.querySelector('.nm')?.textContent?.trim()
    el.click()
    return name
  })
  await wait(700)
  await clickText(page, '.manage .main .subform .actions button', '保存关联')
  await wait(1600)
  rec('U09', '事件关联人物', perPicked ? (await text(page, '.manage .main')).includes(perPicked) : false,
    '关联行出现所选人物', `picked=${perPicked}`)

  await clickText(page, '.manage .main .m2-sub button', '关联地点')
  await wait(500)
  await clickText(page, '.manage .main .subform button', '选择地点')
  await wait(1500)
  const plPicked = await page.evaluate(() => {
    const items = [...document.querySelectorAll('.picker .item')]
    if (!items.length) return null
    const el = items[0]
    const name = el.querySelector('.nm')?.textContent?.trim()
    el.click()
    return name
  })
  await wait(700)
  await clickText(page, '.manage .main .subform .actions button', '保存关联')
  await wait(1600)
  rec('U10', '事件关联地点', plPicked ? (await text(page, '.manage .main')).includes(plPicked) : false,
    '关联行出现所选地点', `picked=${plPicked}`)
  await page.screenshot({ path: `${OUT}/10_event_links.png` })

  // ---------- 8. 列表刷新与搜索 ----------
  await fill(page, '.manage .side input[type=text]', '界面测试')
  await clickText(page, '.manage .side button', '搜索')
  await wait(1400)
  const items = await page.$$eval('.manage .item .nm', (els) => els.map((e) => e.textContent.trim()))
  rec('U11', '列表关键词搜索命中新建记录', items.some((x) => /界面测试/.test(x)),
    '结果含「界面测试事件」', items.join('、').slice(0, 60))
  await page.screenshot({ path: `${OUT}/11_list_search.png` })

  // ---------- 9. 删除（带二次确认） ----------
  await clickText(page, '.manage .main .actions button', '删除事件')
  await wait(1500)
  const afterDel = await text(page, '.manage .main')
  rec('U12', '删除事件（确认后）回到空态', /从左侧选择一条记录/.test(afterDel),
    '编辑器回到空态提示', afterDel.slice(0, 40))
  await page.screenshot({ path: `${OUT}/12_after_delete.png` })

  rec('U13', '浏览器控制台无 JS 错误', errors.length === 0,
    '0 个错误', errors.length ? errors.slice(0, 3).join(' | ') : '0')

  await browser.close()
  fs.writeFileSync(`${OUT}/ui_result.json`, JSON.stringify({ results: R, errors }, null, 2))
  const fail = R.filter((x) => !x.ok)
  console.log(`\n=== 合计 ${R.length} 项，PASS ${R.length - fail.length}，FAIL ${fail.length} ===`)
  process.exit(fail.length ? 1 : 0)
})().catch((e) => {
  console.error('UI E2E ABORTED:', e.message)
  process.exit(2)
})
