const puppeteer = require('puppeteer-core')
const OUT = process.argv[2]
;(async () => {
  const b = await puppeteer.launch({ executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',
    headless:'new', args:['--no-sandbox','--use-gl=swiftshader','--enable-unsafe-swiftshader','--ignore-gpu-blocklist'],
    defaultViewport:{width:1600,height:950} })
  const p = await b.newPage()
  const reqs = [], fail = []
  p.on('request', r => { const u=r.url(); if (u.includes('maptiler')) reqs.push(u.replace(/key=[^&]+/,'key=***')) })
  p.on('requestfailed', r => { if (r.url().includes('maptiler')) fail.push(r.url().slice(0,90)) })
  await p.goto('http://127.0.0.1:5180/', {waitUntil:'networkidle2'})
  await new Promise(r=>setTimeout(r,6000))

  const banner = await p.$eval('.no-key', e=>e.innerText.split('\n')[0]).catch(()=>null)
  const st = await p.evaluate(()=>{
    const m = window.__map
    const s = m.getStyle()||{}
    const srcs = Object.keys(s.sources||{})
    return { styleName: s.name, sources: srcs.length, layers: (s.layers||[]).length,
             hasVector: srcs.includes('maptiler_planet'), hasSat: srcs.includes('satellite'),
             rasterLayers: (s.layers||[]).filter(l=>l.type==='raster').length,
             places: (m.getSource('places')?._data?.features||[]).length }
  })
  console.log('横幅:', banner ?? '无（已按有 key 模式运行）')
  console.log('样式:', JSON.stringify(st))
  console.log('maptiler 请求数:', reqs.length, '示例:', reqs.slice(0,2))
  console.log('maptiler 失败请求:', fail.length, fail.slice(0,2))
  await p.screenshot({path: OUT + '/M0-01_realkey_outdoor.png'})

  // 四样式切换 + 视野保持
  await p.evaluate(()=>window.__map.jumpTo({center:[116.4,39.9], zoom:6.2}))
  await new Promise(r=>setTimeout(r,2500))
  const cam = ()=>p.evaluate(()=>{const m=window.__map,c=m.getCenter();return {lng:+c.lng.toFixed(4),lat:+c.lat.toFixed(4),zoom:+m.getZoom().toFixed(3)}})
  const before = await cam()
  for (const label of ['Streets','Satellite','Hybrid','Outdoor']) {
    const btns = await p.$$('.style-bar button')
    for (const btn of btns) { const t=await btn.evaluate(e=>e.textContent.trim()); if (t===label) { await btn.click(); break } }
    await new Promise(r=>setTimeout(r,5000))
    const s = await p.evaluate(()=>{const m=window.__map,st=m.getStyle()||{};const srcs=Object.keys(st.sources||{});
      return {name:st.name, raster:(st.layers||[]).filter(l=>l.type==='raster').length, vector:srcs.includes('maptiler_planet'), places:(m.getSource('places')?._data?.features||[]).length}})
    const c = await cam()
    console.log(`  ${label.padEnd(9)} style=${s.name} raster层=${s.raster} vector=${s.vector} 点层=${s.places} cam=${c.lng},${c.lat} z${c.zoom} 漂移=${Math.abs(c.zoom-before.zoom)>0.001||Math.abs(c.lng-before.lng)>0.01?'YES':'no'}`)
    await p.screenshot({path: `${OUT}/M0-02_realkey_${label}.png`})
  }

  // 四区域
  for (const name of ['中国','欧洲','北美','中东']) {
    const btns = await p.$$('.region-bar button')
    for (const btn of btns) { const t=await btn.evaluate(e=>e.textContent.trim()); if (t===name) { await btn.click(); break } }
    await new Promise(r=>setTimeout(r,4000))
    const note = await p.$eval('.data-note', e=>e.innerText.replace(/\s+/g,' '))
    console.log(`  区域 ${name}: ${note.slice(note.indexOf('当前视野'))}`)
    await p.screenshot({path: `${OUT}/M0-04_realkey_${name}.png`})
  }
  await b.close()
})()
