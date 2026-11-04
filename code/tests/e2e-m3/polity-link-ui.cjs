/**
 * M3 · 事件管理里的政权关联（任务 4.4）浏览器实测。
 * 目标 5181（测试库，可写）。
 *
 * 覆盖：打开事件 → 看到政权区 → 搜索选择已有政权 → 保存关联 → 解除关联 → 新建政权并选用。
 */
const puppeteer = require('puppeteer-core')

const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe'
const URL = process.argv[2] || 'http://127.0.0.1:5181/'
const OUT = process.argv[3] || './shots'
const R = []
const wait = (ms) => new Promise((r) => setTimeout(r, ms))

function rec(id, desc, ok, expect, actual) {
  R.push(ok)
  console.log(`${ok ? 'PASS' : 'FAIL'} ${id.padEnd(5)} ${desc.padEnd(44)} | 期望 ${expect} | 实际 ${actual}`)
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

;(async () => {
  const browser = await puppeteer.launch({
    executablePath: CHROME,
    headless: 'new',
    args: ['--no-sandbox', '--use-gl=swiftshader', '--enable-unsafe-swiftshader'],
    defaultViewport: { width: 1500, height: 950 },
  })
  const page = await browser.newPage()
  const errors = []
  page.on('pageerror', (e) => errors.push(e.message.slice(0, 160)))
  page.on('dialog', (d) => d.accept())

  await page.goto(URL, { waitUntil: 'networkidle2', timeout: 60000 })
  await wait(4000)

  // 打开内容管理 → 事件页签
  await clickText(page, 'button', '内容管理')
  await wait(1200)
  await clickText(page, '.manage .tabs button', '事件')
  await wait(1400)

  // 搜索一个演示事件并打开
  await page.evaluate(() => {
    const input = document.querySelector('.manage .side input[type=text]')
    if (input) {
      input.value = '布匿'
      input.dispatchEvent(new Event('input', { bubbles: true }))
    }
  })
  await wait(900)
  await page.evaluate(() => {
    const btn = [...document.querySelectorAll('.manage .side button')].find((b) => b.textContent.includes('搜索'))
    btn && btn.click()
  })
  await wait(1500)
  const opened = await page.evaluate(() => {
    const it = document.querySelector('.manage .side .item')
    if (!it) return null
    const t = it.textContent.trim().slice(0, 20)
    it.click()
    return t
  })
  await wait(1800)
  rec('P01', '从事件列表打开一个事件', !!opened, '进入编辑态', opened || '(无结果)')

  // 政权区存在
  const hasSection = await page.evaluate(() =>
    [...document.querySelectorAll('.manage .main .m2-sub')].some((x) => x.textContent.includes('历史政权')),
  )
  rec('P02', '事件编辑区有「历史政权」区块', hasSection, '存在', hasSection)

  // 初始应已有 1 个政权（种子数据：罗马共和国）
  const before = await page.evaluate(() =>
    [...document.querySelectorAll('.manage .main .m2-row')].map((r) => r.textContent.replace(/\s+/g, ' ').trim()),
  )
  rec('P03', '政权关联行正确展示（名称 + 地区 + 角色）',
    before.some((t) => t.includes('罗马共和国') && t.includes('欧洲')), '含 罗马共和国/欧洲',
    JSON.stringify(before.slice(0, 2)))

  // 添加关联：搜索并选择「孔雀王朝」
  await clickText(page, '.manage .main .m2-sub button', '+ 关联政权')
  await page.waitForFunction(
    () => [...document.querySelectorAll('.manage .main .pickrow button')].some((b) => b.textContent.includes('搜索政权')),
    { timeout: 8000 },
  )
  const openedPicker = await clickText(page, '.manage .main .pickrow button', '搜索政权')
  await page.waitForFunction(() => !!document.querySelector('.mask .picker'), { timeout: 8000 }).catch(() => null)
  await wait(600)
  const pickerOpen = await page.evaluate(() => !!document.querySelector('.mask .picker'))
  rec('P04', '打开政权搜索选择器（不是手填 ID）', pickerOpen, '选择器弹出', pickerOpen)

  await page.evaluate(() => {
    const input = document.querySelector('.mask .picker .search input')
    input.value = '孔雀'
    input.dispatchEvent(new Event('input', { bubbles: true }))
  })
  await wait(400)
  await clickText(page, '.mask .picker .search button', '搜索')
  await wait(1200)
  const picked = await page.evaluate(() => {
    const it = [...document.querySelectorAll('.mask .picker .item')].find((x) => x.textContent.includes('孔雀王朝'))
    if (!it) return null
    it.click()
    return '孔雀王朝'
  })
  rec('P05', '按名称搜到并选中政权', picked === '孔雀王朝', '孔雀王朝', picked || '(未找到)')
  await wait(700)
  await clickText(page, '.manage .main .subform .actions button', '保存关联')
  await wait(1800)
  const after = await page.evaluate(() =>
    [...document.querySelectorAll('.manage .main .m2-row')].map((r) => r.textContent.replace(/\s+/g, ' ').trim()),
  )
  rec('P06', '保存后关联出现在列表中', after.some((t) => t.includes('孔雀王朝')), '含 孔雀王朝',
    JSON.stringify(after.filter((t) => t.includes('孔雀')).slice(0, 1)))

  // 重复关联：选择器里应把已关联政权标灰
  await clickText(page, '.manage .main .m2-sub button', '+ 关联政权')
  await page.waitForFunction(
    () => [...document.querySelectorAll('.manage .main .pickrow button')].some((b) => b.textContent.includes('搜索政权')),
    { timeout: 8000 },
  )
  await clickText(page, '.manage .main .pickrow button', '搜索政权')
  await page.waitForFunction(() => !!document.querySelector('.mask .picker'), { timeout: 8000 }).catch(() => null)
  await wait(600)
  await page.evaluate(() => {
    const input = document.querySelector('.mask .picker .search input')
    input.value = '孔雀'
    input.dispatchEvent(new Event('input', { bubbles: true }))
  })
  await wait(400)
  await clickText(page, '.mask .picker .search button', '搜索')
  await wait(1200)
  const dupDisabled = await page.evaluate(() => {
    const it = [...document.querySelectorAll('.mask .picker .item')].find((x) => x.textContent.includes('孔雀王朝'))
    return it ? { disabled: it.disabled, text: it.textContent.replace(/\s+/g, ' ').trim().slice(-6) } : null
  })
  rec('P07', '已关联的政权在选择器里被标灰不可重复选', !!dupDisabled && dupDisabled.disabled,
    'disabled + 已关联', JSON.stringify(dupDisabled))
  await page.evaluate(() => document.querySelector('.mask .picker .x')?.click())
  await wait(500)
  await clickText(page, '.manage .main .subform .actions button', '取消')
  await wait(500)

  // 解除关联
  const beforeRemove = await page.evaluate(() =>
    [...document.querySelectorAll('.manage .main .m2-row')].filter((r) => r.textContent.includes('孔雀王朝')).length,
  )
  await page.evaluate(() => {
    const row = [...document.querySelectorAll('.manage .main .m2-row')].find((r) => r.textContent.includes('孔雀王朝'))
    const btn = row ? [...row.querySelectorAll('button')].find((b) => b.textContent.includes('解除')) : null
    btn && btn.click()
  })
  await wait(1800)
  const afterRemove = await page.evaluate(() =>
    [...document.querySelectorAll('.manage .main .m2-row')].filter((r) => r.textContent.includes('孔雀王朝')).length,
  )
  rec('P08', '解除关联后行消失（政权与事件本体保留）',
    beforeRemove === 1 && afterRemove === 0, '1 → 0', `${beforeRemove} → ${afterRemove}`)

  // 新建政权并选用
  await clickText(page, '.manage .main .m2-sub button', '新建政权')
  await page.waitForFunction(
    () => [...document.querySelectorAll('.manage .main .subform select')].length > 0,
    { timeout: 8000 },
  )
  await wait(600)
  // 注意：新建表单里还有 AstroYear 的「公元前/公元」下拉，必须按内容挑出「展示地区」那个
  const regionOptions = await page.evaluate(() => {
    const s = [...document.querySelectorAll('.manage .main .subform select')]
      .find((x) => [...x.options].some((o) => o.textContent.includes('东亚')))
    return s ? [...s.options].map((o) => o.textContent.trim()) : []
  })
  rec('P09', '新建政权时展示地区来自后端（10 个）', regionOptions.length === 10, '10 个',
    regionOptions.join('/').slice(0, 40))

  const newName = '验证政权UI-' + Date.now().toString().slice(-5)
  await page.evaluate((name) => {
    // 按 placeholder 精确定位「政权名称」，避免抓到年份输入框
    const el = document.querySelector('.manage .main .subform input[placeholder*="波斯帝国"]')
    if (!el) return false
    el.value = name
    el.dispatchEvent(new Event('input', { bubbles: true }))
    return true
  }, newName)
  await wait(400)
  await clickText(page, '.manage .main .subform .actions button', '新建并选用')
  await wait(2000)
  const created = await page.evaluate(() => {
    const msg = document.querySelector('.manage .main .tiny[style]')?.textContent?.trim()
    const input = [...document.querySelectorAll('.manage .main .pickrow input[readonly]')].pop()
    return { msg, picked: input ? input.value : null }
  })
  rec('P10', '新建政权后自动选入关联表单', (created.picked || '').includes('验证政权UI'),
    '表单显示新政权名', JSON.stringify(created))

  await clickText(page, '.manage .main .subform .actions button', '保存关联')
  await wait(1800)
  const finalRows = await page.evaluate(() =>
    [...document.querySelectorAll('.manage .main .m2-row')].map((r) => r.textContent.replace(/\s+/g, ' ').trim()),
  )
  rec('P11', '新政权关联保存成功', finalRows.some((t) => t.includes('验证政权UI')), '含新政权',
    JSON.stringify(finalRows.filter((t) => t.includes('验证政权UI'))))

  await page.screenshot({ path: `${OUT}/20_polity_link.png` })
  rec('P12', '无 JS 错误', errors.length === 0, '0', errors.slice(0, 2).join(' | ') || '0')

  const ok = R.filter(Boolean).length
  console.log(`\n=== 合计 ${R.length} 项，PASS ${ok}，FAIL ${R.length - ok} ===`)
  await browser.close()
  process.exit(ok === R.length ? 0 : 1)
})()
