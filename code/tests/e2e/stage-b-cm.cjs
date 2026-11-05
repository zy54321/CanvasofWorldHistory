/**
 * 阶段 B CM06：内容管理界面的加载态、跳页、筛选与翻页交互。
 * 全部用真实点击 + 网络拦截计数，不看代码推断。
 */
const puppeteer = require('puppeteer-core')
const fs = require('fs')

const BASE = process.argv[2] || 'http://127.0.0.1:5180/'
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
    defaultViewport: { width: 1500, height: 950 },
  })
  const page = await browser.newPage()
  const pageErrors = []
  page.on('pageerror', (e) => pageErrors.push(String(e)))

  // 统计 admin 列表请求、并可选地注入延迟
  const adminReqs = []
  let delayMs = 0
  await page.setRequestInterception(true)
  page.on('request', async (req) => {
    if (req.url().includes('/api/v1/places/admin?')) adminReqs.push(req.url())
    if (delayMs && req.url().includes('/api/v1/places/admin?')) {
      await sleep(delayMs)
    }
    req.continue()
  })

  await page.goto(BASE, { waitUntil: 'networkidle2', timeout: 60000 })
  await page.waitForFunction(() => !!document.querySelector('button'), { timeout: 20000 })

  // 打开内容管理
  const opened = await page.evaluate(() => {
    const b = [...document.querySelectorAll('button')].find((x) => x.textContent.trim() === '内容管理')
    if (!b) return false
    b.click()
    return true
  })
  check('CM06-open', '内容管理可打开', opened)
  await page.waitForSelector('.manage', { timeout: 15000 })
  await sleep(2000)

  const firstPage = await page.evaluate(() => ({
    items: document.querySelectorAll('.manage .item').length,
    pager: document.querySelector('.manage .pager')?.innerText.replace(/\s+/g, ' ').trim(),
    hasFilter: document.querySelectorAll('.manage .filters select').length,
  }))
  check('CM06-a', '地点页签显示列表 + 两个筛选器 + 分页条',
        firstPage.items > 0 && firstPage.hasFilter === 2 && !!firstPage.pager,
        `${firstPage.items} 条 / 筛选器 ${firstPage.hasFilter} / ${firstPage.pager}`)

  // 列表行是否含几何计数与名称质量标签
  const rowInfo = await page.evaluate(() => {
    const it = document.querySelector('.manage .item')
    return { name: it.querySelector('.nm')?.textContent.trim(), tag: it.querySelector('.tag')?.textContent.trim(), sub: it.querySelector('.sub')?.textContent.trim() }
  })
  check('CM06-b', '列表行显示 展示名 / 名称质量 / 几何与位置计数',
        !!rowInfo.name && !!rowInfo.tag && /位置\s*\d+/.test(rowInfo.sub),
        `${rowInfo.name} | ${rowInfo.tag} | ${rowInfo.sub}`)

  // ---- 加载态：注入 1200ms 延迟后点"下一页"，按钮应禁用、列表转 busy
  delayMs = 1200
  const before = adminReqs.length
  await page.evaluate(() => {
    const btns = [...document.querySelectorAll('.manage .pager button')]
    const next = btns.find((b) => b.textContent.trim() === '下一页')
    next.click()
  })
  await sleep(300)
  const during = await page.evaluate(() => {
    const pager = document.querySelector('.manage .pager')
    const btns = [...pager.querySelectorAll('button')]
    return {
      disabled: btns.map((b) => b.disabled),
      busy: !!document.querySelector('.manage .items.busy'),
      hint: document.querySelector('.manage .loading-hint')?.textContent.trim() || '',
    }
  })
  check('CM06-c', '请求中翻页控件全部禁用 + 列表置忙 + 显示加载提示',
        during.disabled.every(Boolean) && during.busy && /正在加载/.test(during.hint),
        `disabled=${JSON.stringify(during.disabled)} busy=${during.busy} hint=${during.hint}`)

  // 请求中连续点击：不得发出重复请求
  await page.evaluate(() => {
    const btns = [...document.querySelectorAll('.manage .pager button')]
    const next = btns.find((b) => b.textContent.trim() === '下一页')
    next.click(); next.click(); next.click()
  })
  await sleep(500)
  const concurrent = adminReqs.length - before
  check('CM06-d', '请求进行中连点不会发出重复请求', concurrent === 1, `新增请求 ${concurrent} 个`)
  await sleep(1800)
  delayMs = 0

  // ---- 跳页
  await page.evaluate(() => {
    const inp = document.querySelector('.manage .jump input')
    inp.value = '300'
    inp.dispatchEvent(new Event('input', { bubbles: true }))
  })
  const beforeJump = adminReqs.length
  await page.evaluate(() => {
    const b = [...document.querySelectorAll('.manage .jump button')][0]
    b.click()
  })
  await sleep(2200)
  const afterJump = await page.evaluate(() => ({
    label: document.querySelector('.manage .pager')?.innerText.replace(/\s+/g, ' ').trim(),
    items: document.querySelectorAll('.manage .item').length,
    lastReq: performance.getEntriesByType('resource').filter((r) => r.name.includes('/places/admin?')).slice(-1)[0]?.name || '',
  }))
  const jumpOk = adminReqs.slice(beforeJump).some((u) => /page=300(&|$)/.test(u))
  check('CM06-e', '输入页码可跳转到指定页', jumpOk && afterJump.items > 0,
        `${afterJump.items} 条 / ${afterJump.label}`)

  // 非法页码：不得发请求，且给出提示
  const beforeBad = adminReqs.length
  await page.evaluate(() => {
    const inp = document.querySelector('.manage .jump input')
    inp.value = 'abc'
    inp.dispatchEvent(new Event('input', { bubbles: true }))
    ;[...document.querySelectorAll('.manage .jump button')][0].click()
  })
  await sleep(800)
  const badState = await page.evaluate(() => ({
    alert: document.querySelector('.manage .m2-alert')?.textContent.trim() || '',
    page: document.querySelector('.manage .pager')?.innerText.replace(/\s+/g, ' ').trim(),
  }))
  check('CM06-f', '非法页码被前端拦住（提示 + 不发请求）',
        adminReqs.length === beforeBad && /正整数|超出范围/.test(badState.alert),
        `新增请求 ${adminReqs.length - beforeBad} / 提示「${badState.alert}」/ ${badState.page}`)

  // 超范围页码
  const beforeFar = adminReqs.length
  await page.evaluate(() => {
    const inp = document.querySelector('.manage .jump input')
    inp.value = '99999'
    inp.dispatchEvent(new Event('input', { bubbles: true }))
    ;[...document.querySelectorAll('.manage .jump button')][0].click()
  })
  await sleep(800)
  const farState = await page.evaluate(() => document.querySelector('.manage .m2-alert')?.textContent.trim() || '')
  check('CM06-g', '超范围页码被拦住（提示范围）',
        adminReqs.length === beforeFar && /超出范围/.test(farState), `提示「${farState}」`)

  // ---- 筛选：几何 = 有线，应回到第 1 页
  const beforeFilter = adminReqs.length
  await page.select('.manage .filters select', 'line')
  await sleep(2000)
  const afterFilter = await page.evaluate(() => ({
    label: document.querySelector('.manage .pager')?.innerText.replace(/\s+/g, ' ').trim() || '',
    count: document.querySelector('.manage .hd .tiny.dim')?.textContent.trim(),
  }))
  const filterUrl = adminReqs.slice(beforeFilter).slice(-1)[0] || ''
  check('CM06-h', '切换几何筛选后请求带 geomType 且回到第 1 页',
        /geomType=line/.test(filterUrl) && /(^|\s)1\s*\//.test(afterFilter.label || '1 /'),
        `${filterUrl.split('?')[1] || ''} | ${afterFilter.label} | ${afterFilter.count}`)

  // 翻页保留筛选
  const beforePage2 = adminReqs.length
  await page.evaluate(() => {
    const b = [...document.querySelectorAll('.manage .pager button')].find((x) => x.textContent.trim() === '下一页')
    b.click()
  })
  await sleep(2000)
  const page2Url = adminReqs.slice(beforePage2).slice(-1)[0] || ''
  check('CM06-i', '翻页保留当前筛选条件',
        /geomType=line/.test(page2Url) && /page=2/.test(page2Url), page2Url.split('?')[1] || '')

  // 组合筛选：几何 + 名称质量
  const beforeCombo = adminReqs.length
  await page.select('.manage .filters select:nth-of-type(1)', 'polygon').catch(() => {})
  await page.evaluate(() => {
    const sels = [...document.querySelectorAll('.manage .filters select')]
    if (sels[1]) { sels[1].value = 'valid'; sels[1].dispatchEvent(new Event('change', { bubbles: true })) }
  })
  await sleep(2200)
  const comboUrl = adminReqs.slice(beforeCombo).slice(-1)[0] || ''
  const comboState = await page.evaluate(() => ({
    count: document.querySelector('.manage .hd .tiny.dim')?.textContent.trim(),
    items: document.querySelectorAll('.manage .item').length,
  }))
  check('CM06-j', '两层筛选可组合（请求同时带两个参数）',
        /geomType=polygon/.test(comboUrl) && /nameQuality=valid/.test(comboUrl),
        `${comboUrl.split('?')[1] || ''} | ${comboState.count}`)

  // 筛选到空结果时给空态而不是报错。
  // 注意：空集不能靠"两个少见条件相加"来猜 —— 实测 none+alias_only 其实有 53 条。
  // 这里用确定为空的一对：关键字 Athens（都是有效名称）+ 名称质量 占位无名。
  await page.evaluate(() => {
    const inp = document.querySelector('.manage .search input')
    inp.value = 'Athens'
    inp.dispatchEvent(new Event('input', { bubbles: true }))
    const sels = [...document.querySelectorAll('.manage .filters select')]
    sels[0].value = 'all'; sels[0].dispatchEvent(new Event('change', { bubbles: true }))
    sels[1].value = 'placeholder'; sels[1].dispatchEvent(new Event('change', { bubbles: true }))
  })
  await sleep(2400)
  const emptyState = await page.evaluate(() => ({
    empty: document.querySelector('.manage .items .m2-empty')?.textContent.trim() || '',
    items: document.querySelectorAll('.manage .item').length,
    alert: document.querySelector('.manage .m2-alert')?.textContent.trim() || '',
  }))
  check('CM06-k', '无匹配结果时列表显示空态而非错误',
        !!emptyState.empty && emptyState.items === 0 && !emptyState.alert,
        `「${emptyState.empty}」/ 行数 ${emptyState.items}`)

  // 恢复全量
  await page.evaluate(() => {
    const inp = document.querySelector('.manage .search input')
    inp.value = ''
    inp.dispatchEvent(new Event('input', { bubbles: true }))
    const sels = [...document.querySelectorAll('.manage .filters select')]
    sels[0].value = 'all'; sels[0].dispatchEvent(new Event('change', { bubbles: true }))
    sels[1].value = 'all'; sels[1].dispatchEvent(new Event('change', { bubbles: true }))
  })
  await sleep(2200)
  await page.screenshot({ path: `${OUT}/cm_manage.png` })

  check('CM06-l', '无 pageerror', pageErrors.length === 0, pageErrors.slice(0, 3).join(' | '))

  const passed = results.filter((r) => r.ok).length
  console.log(`\n结果 ${passed}/${results.length}`)
  fs.writeFileSync(`${OUT}/cm_browser.json`, JSON.stringify({ results, pageErrors }, null, 2))
  await browser.close()
  process.exit(passed === results.length ? 0 : 1)
})().catch((e) => { console.error('FATAL', e); process.exit(2) })
