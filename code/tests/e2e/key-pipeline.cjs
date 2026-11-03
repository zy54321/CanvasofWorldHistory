const puppeteer = require('puppeteer-core')
;(async () => {
  const b = await puppeteer.launch({ executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',
    headless:'new', args:['--no-sandbox','--use-gl=swiftshader','--enable-unsafe-swiftshader'] })
  const p = await b.newPage()
  const reqs = []
  p.on('request', r => { if (r.url().includes('maptiler')) reqs.push(r.url()) })
  await p.goto('http://127.0.0.1:5181/', {waitUntil:'networkidle2'})
  await new Promise(r=>setTimeout(r,4000))
  const banner = await p.$eval('.no-key', e=>e.innerText).catch(()=>null)
  const errText = await p.$eval('.map-status', e=>e.innerText).catch(()=>null)
  console.log('banner(无key提示):', banner ? banner.split('\n')[0] : '无 → 说明已按有 key 模式运行')
  console.log('地图请求:', reqs.slice(0,3).map(u=>u.replace(/key=[^&]+/, 'key=<REDACTED>')))
  console.log('状态条:', (errText||'').replace(/\s+/g,' '))
  await p.screenshot({path:'./key_pipeline.png'})
  await b.close()
})()
