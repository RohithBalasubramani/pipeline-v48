// payload_db/harvest_asset_payloads.mjs — harvest the 30 ASSETS deep-tab card stories' RESOLVED args
// (= each card's default/metadata payload) from the CMD_V2 ASSETS Storybook at :6030, via
// __STORYBOOK_PREVIEW__.storyStoreValue.args.initialArgsByStoryId. Sibling of harvest_payloads.mjs (EMS :6008);
// ATOMIC: separate single-purpose file, different base URL + story filter, same resolution mechanism.
// Output: /tmp/asset_payloads.json  [{id,title,name,group,importPath,componentPath,payload,argsOk,error}]
// Run from /home/rohith/CMD_V2 (playwright lives there):
//   node /home/rohith/desktop/BFI/backend/layer2/pipeline_v48/payload_db/harvest_asset_payloads.mjs
import { chromium } from 'playwright'
import { readFileSync, writeFileSync } from 'fs'

const BASE = 'http://100.90.185.31:6030'
const idx = JSON.parse(readFileSync('/tmp/sb_assets_index.json')).entries
const stories = Object.values(idx)
  .filter(e => e.type === 'story' && String(e.title || '').toLowerCase().startsWith('assets/'))
  .map(e => ({ id: e.id, title: e.title, name: e.name, importPath: e.importPath, componentPath: e.componentPath }))
  .sort((a, b) => a.title.localeCompare(b.title) || a.id.localeCompare(b.id))

console.log(`harvesting ${stories.length} ASSETS stories from ${BASE}`)
const out = []
const b = await chromium.launch({ headless: true, args: ['--no-sandbox'] })
const ctx = await b.newContext({ viewport: { width: 1400, height: 900 } })
const pg = await ctx.newPage()

for (const s of stories) {
  const rec = { ...s, group: (s.title.split('/')[0] || ''), payload: null, argsOk: false, error: null }
  try {
    await pg.goto(`${BASE}/iframe.html?id=${encodeURIComponent(s.id)}&viewMode=story`,
      { waitUntil: 'domcontentloaded', timeout: 25000 })
    const r = await pg.evaluate(async (storyId) => {
      const sleep = ms => new Promise(r => setTimeout(r, ms))
      let initial = null
      for (let i = 0; i < 50; i++) {
        const P = window.__STORYBOOK_PREVIEW__
        const A = P && P.storyStoreValue && P.storyStoreValue.args
        initial = A && (A.initialArgsByStoryId?.[storyId] || A.argsByStoryId?.[storyId])
        if (initial && Object.keys(initial).length) break
        await sleep(150)
      }
      if (!initial) return { ok: false, json: null }
      const seen = new WeakSet()
      const json = JSON.stringify(initial, (k, v) => {
        if (typeof v === 'function') return undefined
        if (typeof v === 'object' && v !== null) { if (seen.has(v)) return '[Circular]'; seen.add(v) }
        return v
      })
      return { ok: true, json }
    }, s.id)
    if (r.ok && r.json) { rec.payload = JSON.parse(r.json); rec.argsOk = true }
    else rec.error = 'no-initial-args'
  } catch (e) {
    rec.error = String(e).slice(0, 200)
  }
  out.push(rec)
  process.stdout.write(rec.argsOk ? '.' : 'x')
}
process.stdout.write('\n')
await b.close()
writeFileSync('/tmp/asset_payloads.json', JSON.stringify(out, null, 2))
const ok = out.filter(r => r.argsOk).length
console.log(`done: ${ok}/${out.length} resolved; failures:`,
  out.filter(r => !r.argsOk).map(r => r.id + ':' + r.error))
