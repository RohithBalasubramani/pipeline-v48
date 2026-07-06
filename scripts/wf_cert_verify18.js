export const meta = {
  name: 'v48-cert-verify18',
  description: 'Adversarial per-page audit of the 18 cert dumps (SSR-render + fab-scan + neuract cross-check) → consolidated 18-page × card verdict table',
  phases: [
    { title: 'Audit', detail: '18 parallel per-page adversarial audits' },
    { title: 'Synthesize', detail: 'consolidated verdict table + defect families' },
  ],
}

const ROOT = '/home/rohith/desktop/BFI/backend/layer2/pipeline_v48'
const DUMPS = '/tmp/cert18'
const LOGS = ROOT + '/outputs/logs'

// nn | prompt | expected page_key | pin (asset_id used, or '')  — matches tools/cert_fire18.sh
const PAGES = [
  ['01','real time monitoring for PCC Panel 1','panel-overview-shell/real-time-monitoring',''],
  ['02','energy and distribution for PCC Panel 1','panel-overview-shell/energy-distribution',''],
  ['03','energy and power for PCC Panel 1','panel-overview-shell/energy-power',''],
  ['04','harmonics and power quality for PCC Panel 1','panel-overview-shell/harmonics-pq',''],
  ['05','voltage and current for PCC Panel 1','panel-overview-shell/voltage-current',''],
  ['06','voltage and current for GIC-01-N3-UPS-01','individual-feeder-meter-shell/voltage-current',''],
  ['07','real time monitoring for GIC-01-N3-UPS-01','individual-feeder-meter-shell/real-time-monitoring',''],
  ['08','energy and power for GIC-01-N3-UPS-01','individual-feeder-meter-shell/energy-power',''],
  ['09','power quality for GIC-01-N3-UPS-01','individual-feeder-meter-shell/power-quality',''],
  ['10','dg voltage and current for DG-1','diesel-generator-asset-dashboard/voltage-current','2'],
  ['11','dg engine and cooling for DG-1','diesel-generator-asset-dashboard/engine-cooling','2'],
  ['12','dg fuel efficiency for DG-1','diesel-generator-asset-dashboard/fuel-efficiency','2'],
  ['13','dg operations and runtime for DG-1','diesel-generator-asset-dashboard/operations-runtime','2'],
  ['14','transformer tap and rtcc for Transformer-01','transformer-asset-dashboard/tap-rtcc','171'],
  ['15','transformer thermal life for Transformer-01','transformer-asset-dashboard/thermal-life','171'],
  ['16','ups battery and autonomy for GIC-01-N3-UPS-01','ups-asset-dashboard/battery-autonomy',''],
  ['17','ups output load capacity for GIC-01-N3-UPS-01','ups-asset-dashboard/output-load-capacity',''],
  ['18','ups source transfer for GIC-01-N3-UPS-01','ups-asset-dashboard/source-transfer',''],
]

const PAGE_SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['nn','routed','routed_ok','cards_total','cards_ok','ssr_ok','fabrication','cards','defects','honest_gaps'],
  properties: {
    nn: { type: 'string' },
    routed: { type: 'string', description: "the served page.page_key" },
    routed_ok: { type: 'boolean', description: 'routed == expected page_key' },
    cards_total: { type: 'number' },
    cards_ok: { type: 'number', description: 'cards that render real-or-honest-blank with no defect' },
    ssr_ok: { type: 'number', description: "cards that SSR-rendered 'rendered OK' (no THROWS, no NULL-fallback)" },
    ssr_crashes: { type: 'array', items: { type: 'number' }, description: 'card_ids that THREW or NULL-fell-back in SSR (family-H)' },
    fabrication: { type: 'array', items: { type: 'string' }, description: 'card_id:token for any REAL fabricated value (seed / mfm ref / simulator figure) — NOT a substring false-positive; [] = clean' },
    cards: { type: 'array', items: { type: 'object', additionalProperties: false,
      required: ['card_id','verdict','ok'],
      properties: {
        card_id: { type: 'number' },
        verdict: { type: 'string', description: 'render | partial | honest_blank' },
        ok: { type: 'boolean', description: 'true if renders real-where-measurable / honest-blank-with-reason, no fabrication, SSR-clean' },
        real: { type: 'number' }, data: { type: 'number' },
        issue: { type: 'string', description: 'defect description if !ok, else empty' },
        layer: { type: 'string', description: 'defect layer if !ok: layer1a|layer1b|layer2-emit|ems_exec-validate|ems_exec-fill|family-H|other' },
        evidence: { type: 'string', description: 'log line / ai_ snippet / neuract SELECT count proving the verdict' },
      } } },
    defects: { type: 'array', items: { type: 'string' }, description: 'card_id:family:one-line — a real defect (fabrication, false-blank of a column with live data, SSR crash, misroute)' },
    honest_gaps: { type: 'array', items: { type: 'string' }, description: 'card_id:reason — a leaf honestly blank WITH a reason (a PASS, not a defect)' },
  },
}

phase('Audit')
const audits = await parallel(PAGES.map(([nn, prompt, expected, pin]) => () =>
  agent(
`ADVERSARIAL CERT AUDIT of ONE V48 page. You verify, you do NOT re-run the pipeline (the dump already exists; NEVER call /api/run — that contends the shared vLLM). Repo ${ROOT}.

PAGE ${nn}: prompt='${prompt}'  expected_page_key='${expected}'${pin ? `  (fired PINNED asset_id=${pin} — an asset-picker case, legitimately re-fired with the class-matched candidate)` : ''}
DUMP (source of truth): ${DUMPS}/cert_${nn}.json  — read it. page_key is at dump['page']['page_key']; cards at dump['cards']; each card has card_id, payload, payload_error, render{verdict,answerability,reason,leaf_stats{real,data},gaps}, data_note, data_instructions.

DO, IN ORDER:
1. ROUTING: assert dump.page.page_key == '${expected}'. (routed_ok)
2. SSR RENDER GATE (family H): \`cd ${ROOT}/host/web && npx vite-node scripts/ssr_repro.tsx ${DUMPS}/cert_${nn}.json\` (use the ABSOLUTE dump path). EVERY card must print 'rendered OK'. A 'THROWS' or 'renderCmd returned NULL' on a card WITH a payload = a family-H render DEFECT for that card (ssr_crashes).
3. FABRICATION SCAN: for each card's payload, look for a REAL fabricated value: a Storybook seed (1500/2700/389.2 kVA-class magic numbers), a raw device/MFM ref leaking as data, a simulator figure, or a fixed '13:14:10'-class clock string shown as live. IGNORE substring false-positives (e.g. '1500' inside a legit float 0.99...15001) — only flag a value that renders AS a claimed reading. Data comes ONLY from neuract; metadata only from CMD_V2.
4. PER-CARD CONTRACT (adversarial — a card is ok ONLY if you TRIED and could not fault it): for each card, verdict is render/partial/honest_blank. A blank leaf is a PASS (honest_gap) ONLY if it has a reason AND the column genuinely lacks live data. CROSS-CHECK the most suspicious blank leaves against neuract directly: \`psql postgresql://postgres@127.0.0.1:5433/target_version1 -c "SET search_path=neuract; SELECT count(<col>) FROM <asset_table> WHERE <col> IS NOT NULL;"\` (the asset table + columns are in dump.asset / data_instructions.fields[].column). If a leaf is blank BUT the column HAS live data → that is a [ems_exec-validate] or [ems_exec-fill] FALSE-BLANK defect (cite the count). If the column is genuinely null → honest_gap (a PASS).
5. For a defect, set card.layer + card.evidence to the proving citation (a stage line from ${LOGS}/pipeline_<run_id>.jsonl, an ai_ prompt/response snippet from ${LOGS}/ai_<run_id>.jsonl, or the neuract count). run_id is dump['run_id'].

STANDARD: a card PASSES if it renders its real component with real-where-measurable data OR honest-blank-with-reason per leaf, no fabrication, SSR-clean. honest-blank+reason is a PASS, not a defect. Return the page verdict object.`,
    { label: `audit:${nn}`, phase: 'Audit', schema: PAGE_SCHEMA }))
).then(rs => rs.filter(Boolean))

log(`AUDIT done: ${audits.length}/18 pages. cards=${audits.reduce((a,p)=>a+(p.cards_total||0),0)} ssr_crashes=${audits.reduce((a,p)=>a+((p.ssr_crashes||[]).length),0)} fabrication=${audits.reduce((a,p)=>a+((p.fabrication||[]).length),0)}`)

phase('Synthesize')
const summary = await agent(
`Synthesize the V48 18-page CERTIFICATION VERDICT from the per-page audits below. Write it to ${ROOT}/outputs/CERT18_VERDICT.md (create/overwrite) AND return a compact text summary.

The doc MUST contain:
1. CONFIG CERTIFIED: guided_json ON, morph-map OFF (live A/B regressed), prompt-v2 OFF (A/B regressed), c49 axis-chrome carve-out ON, layer2.emit_concurrency=4. (state this at top)
2. THE 18-PAGE × CARD TABLE: one row per page — nn | page_key | routed_ok | cards ok/total | ssr ok/total | fabrication | defects(card:layer) | honest_gaps(count). Pages 10-15 note "(pinned <id>, asset-picker case)".
3. TOTALS: total cards, cards_ok, SSR-clean count, fabrication count (MUST be 0 to certify), payload_errors, misroutes.
4. DEFECT FAMILIES present (if any): A fab-by-zero, B seed-leak, C false-blank(column has live data), D misroute, E legend/unit leak, F emit-timeout, G semantic mis-bind, H SSR render-crash — with the card_ids in each.
5. VERDICT: CERTIFIED (all cards render real-or-honest-blank, 0 fabrication, 0 SSR crashes, 0 misroutes) or NOT-CERTIFIED with the exact blocking defects.
6. Note any honest-blank-heavy pages (e.g. UPS battery/source-transfer where the meter genuinely lacks those columns) as EXPECTED honest degradation, not defects.

Per-page audits (JSON):
${JSON.stringify(audits)}`,
  { label: 'synthesize', phase: 'Synthesize' })

return { pages: audits, summary,
  totals: {
    cards: audits.reduce((a,p)=>a+(p.cards_total||0),0),
    cards_ok: audits.reduce((a,p)=>a+(p.cards_ok||0),0),
    ssr_crashes: audits.flatMap(p=>(p.ssr_crashes||[]).map(c=>`${p.nn}:${c}`)),
    fabrication: audits.flatMap(p=>p.fabrication||[]),
    misroutes: audits.filter(p=>!p.routed_ok).map(p=>p.nn),
  } }
