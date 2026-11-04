/**
 * 写保护 / 选项加载失败的界面表现验证。
 *  1) 5180（正式库，只读实例）：点「新建地点」保存 → 后端 403，界面必须显式提示，且库内不新增
 *  2) 5181（测试库）：拦截 /admin/options → 必须提示失败并禁用表单，不得静默用内置常量
 */
const puppeteer = require('puppeteer-core')
const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe'
const R = []
const wait = (ms) => new Promise((r) => setTimeout(r, ms))
function rec(id, desc, ok, expect, actual) {
  R.push(ok)
  console.log(`${ok ? 'PASS' : 'FAIL'} ${id.padEnd(5)} ${desc.padEnd(40)} | 期望 ${expect} | 实际 ${actual}`)
}
async function clickText(page, sel, t) {
  return page.evaluate((s, x) => {
    const el = [...document.querySelectorAll(s)].find((e) => (e.textContent || '').includes(x))
    if (!el) return false
    el.click(); return true
  }, sel, t)
}
async function fill(page, sel, v) {
  return page.evaluate((s, val) => {
    const el = document.querySelector(s)
    if (!el) return false
    el.focus(); el.value = val
    el.dispatchEvent(new Event('input', { bubbles: true }))
    el.dispatchEvent(new Event('change', { bubbles: true }))
    return true
  }, sel, v)
}

;(async () => {
  const b = await puppeteer.launch({
    executablePath: CHROME, headless: 'new',
    args: ['--no-sandbox', '--use-gl=swiftshader', '--enable-unsafe-swiftshader'],
    defaultViewport: { width: 1500, height: 900 },
  })

  // ---------- 1. 只读实例的写拒绝 ----------
  let p = await b.newPage()
  await p.goto('http://127.0.0.1:5180/', { waitUntil: 'networkidle2' })
  await wait(2500)
  await clickText(p, 'button', '内容管理')
  await wait(1200)
  await clickText(p, '.manage .side button', '新建地点')
  await wait(900)
  await fill(p, '.manage .main input[type=text]', '只读实例应被拒')
  const clicked = await clickText(p, '.manage .main .actions button', '创建地点')
  console.log('   （点击「创建地点」：' + clicked + '）')
  await wait(1800)
  const alert = await p.$eval('.manage .main .m2-alert', (e) => e.innerText).catch(() => null)
  const btnVisible = !!(await p.$('.manage .side button'))
  rec('W01', '只读实例写操作在界面给出明确提示',
    !!alert && /写|403|只读|白名单|拒绝/.test(alert),
    '出现含原因的错误提示', (alert || '(无提示)').replace(/\s+/g, ' ').slice(0, 90))
  rec('W02', '写按钮未被前端隐藏（权限由后端判定）', btnVisible, '按钮可见可点', btnVisible)
  await p.screenshot({ path: 'E:/01_Work/01_PersonalProjects/014-CanvasofWorldHistory/code/ops/reports/m3_prep/12_readonly_ui.png' })
  await p.close()

  // ---------- 2. 选项加载失败 ----------
  p = await b.newPage()
  await p.setRequestInterception(true)
  p.on('request', (r) => {
    if (r.url().includes('/api/v1/places/admin/options')) r.abort()
    else r.continue()
  })
  await p.goto('http://127.0.0.1:5181/', { waitUntil: 'networkidle2' })
  await wait(2500)
  await clickText(p, 'button', '内容管理')
  await wait(1500)
  await clickText(p, '.manage .side button', '新建地点')
  await wait(1200)
  const optAlert = await p.$eval('.manage .main .m2-alert', (e) => e.innerText).catch(() => null)
  const disabled = await p.evaluate(() => {
    const sel = [...document.querySelectorAll('.manage .main select')]
    return sel.length > 0 && sel.every((s) => s.disabled)
  })
  rec('W03', '选项接口失败时给出明确提示（不静默用内置常量）',
    !!optAlert && /选项加载失败/.test(optAlert),
    '出现「地点选项加载失败」', (optAlert || '(无提示)').replace(/\s+/g, ' ').slice(0, 80))
  rec('W04', '选项未加载时表单下拉被禁用', disabled, '下拉全部 disabled', disabled)
  await p.screenshot({ path: 'E:/01_Work/01_PersonalProjects/014-CanvasofWorldHistory/code/ops/reports/m3_prep/13_options_fail_ui.png' })
  await b.close()

  const ok = R.filter(Boolean).length
  console.log(`\n=== 合计 ${R.length} 项，PASS ${ok}，FAIL ${R.length - ok} ===`)
  process.exit(ok === R.length ? 0 : 1)
})()
