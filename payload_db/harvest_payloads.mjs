// payload_db/harvest_payloads.mjs — harvest each Storybook story's RESOLVED args (= the card/subcard payload)
// from the running CMD_V2 Storybook, via __STORYBOOK_PREVIEW__.storyStoreValue.args.initialArgsByStoryId.
// Output: /tmp/ems_payloads.json  [{id,title,name,group,importPath,componentPath,payload,argsOk,error}]
import { chromium } from 'playwright'
import { readFileSync, writeFileSync } from 'fs'

const BASE = 'http://100.90.185.31:6008'
const idx = JSON.parse(readFileSync('/tmp/sb_index.json')).entries
const stories = Object.values(idx)
  .filter(e => e.type === 'story')
  .map(e => ({ id: e.id, title: e.title, name: e.name, importPath: e.importPath, componentPath: e.componentPath }))
  .sort((a, b) => a.title.localeCompare(b.title))

console.log(`harvesting ${stories.length} stories`)
const out = []
const b = await chromium.launch({ headless: true, args: ['--no-sandbox'] })
const ctx = await b.newContext({ viewport: { width: 1400, height: 900 } })
const pg = await ctx.newPage()

for (const s of stories) {
  const rec = { ...s, group: (s.title.split('/')[0] || ''), payload: null, argsOk: false, error: null }
  try {
    await pg.goto(`${BASE}/iframe.html?id=${encodeURIComponent(s.id)}&viewMode=story`,
      { waitUntil: 'domcontentloaded', timeout: 20000 })
    // poll until the preview store has resolved initialArgs for this story
    const r = await pg.evaluate(async (storyId) => {
      const sleep = ms => new Promise(r => setTimeout(r, ms))
      let initial = null
      for (let i = 0; i < 40; i++) {
        const P = window.__STORYBOOK_PREVIEW__
        const A = P && P.storyStoreValue && P.storyStoreValue.args
        initial = A && (A.initialArgsByStoryId?.[storyId] || A.argsByStoryId?.[storyId])
        if (initial && Object.keys(initial).length) break
        await sleep(150)
      }
      if (!initial) return { ok: false, json: null }
      // safe stringify: drop functions/undefined, guard cycles
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
writeFileSync('/tmp/ems_payloads.json', JSON.stringify(out, null, 2))
const ok = out.filter(r => r.argsOk).length
const ems = out.filter(r => r.group === 'EMS' && r.argsOk).length
console.log(`done: ${ok}/${out.length} resolved (EMS ${ems}); failures:`,
  out.filter(r => !r.argsOk).map(r => r.id + ':' + r.error))
