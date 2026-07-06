export const meta = {
  name: 'v48-18card-fullsweep-logged',
  description: 'FULL 18-page × every-card acceptance sweep against the freshly-rehosted fixed pipeline (seedless payload_stripped, zero runtime strip, honest-blank import fixed, canonical ids, payload-direct FE) with MAXIMUM log collection: every page response saved durably, and every card verdict ROOT-CAUSED against that run_id\'s ai_<run_id>.jsonl (full LLM request+response), pipeline_<run_id>.jsonl (stage trace 1a→1b→validate→asset-gate→L2→fill), and failures_<run_id>.jsonl. Adversarial per-card contract (class-correct routing, payload-direct render, real-or-honest-blank+reason, zero seed/NaN/fabrication, no payload_error) + frames=payloads gate + cross-class edge batch + a date-nav /api/frame probe. Ends with a consolidated matrix, a LOG INVENTORY, and a bundled log archive. Log-only (no Playwright).',
  phases: [
    { title: 'Preflight', detail: 'health + :5433 + no-mapper gate + renderer coverage + /api/frame contract + fresh-log confirm' },
    { title: 'Sweep', detail: '3 parallel reviewers × 6 pages (throttled to spare the single vLLM): trigger + read disk-dumped response + ai_/pipeline_/failures_ logs + adversarial per-card' },
    { title: 'CrossClass', detail: 'homonym / sparse / dead edge prompts, log-grounded' },
    { title: 'Matrix', detail: 'consolidated 18-page matrix + log inventory + bundle + certified/blocked verdict' },
  ],
}
const A = args || {}
const ROOT = A.root || "/home/rohith/desktop/BFI/backend/layer2/pipeline_v48"
const PY = A.py || "/home/rohith/.pyenv/versions/3.11.9/bin/python3.11"
const TS = A.ts || "20260706_004334"
const SWEEP = A.sweep_dir || (ROOT + "/outputs/fullsweep_" + TS)
const LOGS = ROOT + "/outputs/logs"
const HOSTLOG = SWEEP + "/host.log"

const COMMON = "Root " + ROOT + " (PYTHONPATH=root; py " + PY + "). Host :8770 = the FRESHLY-REHOSTED fixed pipeline " +
  "(seedless card_payloads.payload_stripped, ZERO runtime strip_to_placeholders, honest-blank null_scalar_data_leaves import fixed, canonical lt_mfm.id, ONE pre-Layer-2 validation pass, payload-direct FE, dead code purged). " +
  "READ-ONLY against the host (do NOT restart it, do NOT edit code — this is VERIFICATION). DB SELECT via `from data.db_client import q; q('cmd_catalog',sql)`; neuract :5433 read-only for ground-truth (probe `cat </dev/null >/dev/tcp/127.0.0.1/5433`; closed → infra_down not defect).\n" +
  "CONTRACT each card must meet: (a) routed to a CLASS-APPROPRIATE page; (b) renders its REAL CMD_V2 component from its payload DIRECTLY (frames retired — the payload IS the vm/props); (c) real-where-the-meter-measures / honest-blank '—' + a per-LEAF reason else (NEVER whole-card refuse); (d) ZERO fabrication — no surviving Storybook seed number, no NaN, no fabricated capacity/derived-zero; (e) no payload_error. Honest-blank WITH a reason = PASS (telemetry), not a defect.\n" +
  "LOGS (this is a MAX-LOGGING run — USE them for root-cause): the durable host stage stream is " + HOSTLOG + " (grep `[r_<id>] PROMPT text='<prompt>'` to map a prompt → its run_id, then `[r_<id>] 1a/1b/validate/asset_gate/L2.card/layer2/exec` for the stage trace). Per run_id the pipeline also writes: " + LOGS + "/pipeline_<run_id>.jsonl (replayable stage trace), " + LOGS + "/ai_<run_id>.jsonl (EVERY :8200 LLM call — full request PROMPT + response, the ground truth for a mis-emit/mis-bind), " + LOGS + "/failures_<run_id>.jsonl (recorded gaps/failures). When you fault a card, CITE the log line/stage that proves the layer (layer1a/layer1b/layer2-emit/ems_exec-validate/ems_exec-fill/executor) — a defect claim without a log or DB citation is not accepted.\n" +
  "DURABILITY: save each page's FULL response to " + SWEEP + "/pages/v18_<nn>.json; append your per-page findings to " + ROOT + "/outputs/VERIFY18_WORKLOG.md as you go.\n" +
  "ENCODING SAFETY (a prior batch died on invalid UTF-8): NEVER cat/tail a log or JSON file raw into your output — always read via python with open(..., errors='replace') (or jq), keep quoted excerpts short, and never echo binary/surrogate bytes.\n"

const CARD = { type: 'object', additionalProperties: false, properties: {
  card_id: { type: 'string' }, ok: { type: 'boolean' }, honest_gap: { type: 'boolean' },
  issue: { type: 'string' }, layer: { type: 'string' }, log_evidence: { type: 'string' } },
  required: ['card_id','ok'] }
const PAGE = { type: 'object', additionalProperties: false, properties: {
  nn: { type: 'string' }, prompt: { type: 'string' }, run_id: { type: 'string' }, routed: { type: 'string' }, expected: { type: 'string' },
  routed_ok: { type: 'boolean' }, asset: { type: 'string' }, cards_ok: { type: 'string' }, cards_total: { type: 'string' },
  cards: { type: 'array', items: CARD }, defects: { type: 'array', items: { type: 'string' } },
  honest_gaps: { type: 'array', items: { type: 'string' } }, infra_down: { type: 'boolean' } },
  required: ['nn','routed','routed_ok','cards_ok','cards_total','defects'] }
const BATCH = { type: 'object', additionalProperties: false, properties: {
  pages: { type: 'array', items: PAGE }, notes: { type: 'string' } }, required: ['pages'] }

// nn | prompt | expected page_key. Panel-overview on the POPULATED PCC-Panel-1 (panel-4 is genuinely empty).
const PAGES = [
  ["01","real time monitoring for PCC Panel 1","panel-overview-shell/real-time-monitoring"],
  ["02","energy and distribution for PCC Panel 1","panel-overview-shell/energy-distribution"],
  ["03","energy and power for PCC Panel 1","panel-overview-shell/energy-power"],
  ["04","harmonics and power quality for PCC Panel 1","panel-overview-shell/harmonics-pq"],
  ["05","voltage and current for PCC Panel 1","panel-overview-shell/voltage-current"],
  ["06","voltage and current for GIC-01-N3-UPS-01","individual-feeder-meter-shell/voltage-current"],
  ["07","real time monitoring for GIC-01-N3-UPS-01","individual-feeder-meter-shell/real-time-monitoring"],
  ["08","energy and power for GIC-01-N3-UPS-01","individual-feeder-meter-shell/energy-power"],
  ["09","power quality for GIC-01-N3-UPS-01","individual-feeder-meter-shell/power-quality"],
  ["10","dg voltage and current for DG-1","diesel-generator-asset-dashboard/voltage-current"],
  ["11","dg engine and cooling for DG-1","diesel-generator-asset-dashboard/engine-cooling"],
  ["12","dg fuel efficiency for DG-1","diesel-generator-asset-dashboard/fuel-efficiency"],
  ["13","dg operations and runtime for DG-1","diesel-generator-asset-dashboard/operations-runtime"],
  ["14","transformer tap and rtcc for Transformer-01","transformer-asset-dashboard/tap-rtcc"],
  ["15","transformer thermal life for Transformer-01","transformer-asset-dashboard/thermal-life"],
  ["16","ups battery and autonomy for GIC-01-N3-UPS-01","ups-asset-dashboard/battery-autonomy"],
  ["17","ups output load capacity for GIC-01-N3-UPS-01","ups-asset-dashboard/output-load-capacity"],
  ["18","ups source transfer for GIC-01-N3-UPS-01","ups-asset-dashboard/source-transfer"],
]
// THROTTLED: 3 reviewers × 6 pages = at most 3 concurrent /api/run (each fans out N card emits to the ONE :8200 vLLM).
// 6-way parallelism saturated the vLLM → 300s+ runs → curl timeouts/broken pipes. 3-way keeps pages well under timeout.
const BATCHES = [[0,6],[6,6],[12,6]].map(([s,n]) => PAGES.slice(s, s+n))

phase('Preflight')
const pre = await agent(COMMON + "PREFLIGHT (read-only gates). (1) curl /api/health (must be ok) + probe :5433 + confirm " + LOGS + " is FRESH (per-run logs accumulate here as the sweep runs). (2) FRAMES=PAYLOADS per-card gate: grep every host/web/src/cmd/fill/**/card-*.tsx (and their view-model/helpers) for a socket/frame mapper call — `mapAggregateSocketToSnapshot`, `map*SocketToSnapshot`, `map*ToFrame`, `assetPageSocket`, `build*ViewModel(` fed a payload/frame — any card fn routing its payload THROUGH a CMD_V2 socket/frame mapper is a DEFECT (ems_backend retired; payload renders direct). List offenders or confirm CLEAN. (3) RENDERER coverage: every card_id in cmd_catalog page_layout_cards for the 18 routable pages resolves to a fill entry (registry.tsx glob); list any card_id with NO renderer + any dup card_id. (4) /api/frame CONTRACT: read host/server.py do_POST /api/frame branch — report its request shape (so the sweep can probe the date-nav path). (5) SSR HARNESS READY: confirm host/web/scripts/ssr_repro.tsx runs (`cd " + ROOT + "/host/web && npx vite-node scripts/ssr_repro.tsx <any existing response json>`) — the per-page audits will SSR-render every served card; a THROW or NULL-fallback on a card WITH a payload is a family-H render DEFECT. Return a short text report of the 5 gate results.", { label: 'preflight', phase: 'Preflight' })
log('PREFLIGHT: ' + String(pre).slice(0, 200))

phase('Sweep')
const runBatch = (batch, bi) => agent(COMMON +
  "ADVERSARIAL LOGGED SWEEP batch " + (bi+1) + " (" + batch.length + " pages, sequential; other batches PARALLEL — do NOT restart host). Pages [nn|prompt|expected]:\n" +
  batch.map(p => "  " + p[0] + " | '" + p[1] + "' | " + p[2]).join("\n") +
  "\nIMPORTANT — the host DUMPS every /api/run response server-side to " + LOGS + "/response_<run_id>.json BEFORE it writes the wire, so a client-side curl timeout NEVER loses data: the disk file is the SOURCE OF TRUTH. Run pages ONE AT A TIME (sequential within your batch) — do NOT fire them concurrently (the single :8200 vLLM is shared across the 3 batches; parallel firing saturates it).\n" +
  "Per page, DO IN ORDER:\n" +
  "  (i) TRIGGER the run (long timeout — a page can take 120-300s): call Bash with timeout 560000 and run `timeout 545 curl -s -m 540 -X POST http://localhost:8770/api/run -H 'Content-Type: application/json' -d '{\"prompt\":\"<prompt>\"}' -o /tmp/trig_<nn>.json`. curl exit 28 (timeout) is OK — the server still finished; proceed to (ii).\n" +
  "  (ii) MAP prompt→run_id: `grep \"PROMPT      text='<prompt>'\" " + HOSTLOG + " | tail -1` → the [r_<id>].\n" +
  "  (iii) GET THE RESPONSE from disk (authoritative): `cp " + LOGS + "/response_<run_id>.json " + SWEEP + "/pages/v18_<nn>.json` then read it. If the file is missing, wait (the run is still going — poll host.log for `[r_<id>] RESPONSE` then retry the cp; if truly absent after ~300s, mark infra_down). If response.asset_pending is true, re-POST ONCE with the CLASS-MATCHED candidate's asset_id from response.asset.candidates (a DG prompt must never accept a UPS/Panel candidate → new run_id → cp its response_<run_id2>.json to v18_<nn>b.json; if no class match, that's a [layer1b] defect).\n" +
  "  (iv) READ that run's logs for root-cause: " + LOGS + "/pipeline_<run_id>.jsonl (stage trace) and, for any faulted/mis-bound/mis-emitted card, " + LOGS + "/ai_<run_id>.jsonl (the FULL LLM prompt+response that produced the emit) + " + LOGS + "/failures_<run_id>.jsonl.\n" +
  "  (iv-b) SSR RENDER GATE (family H — certification requires payload-honest AND render-clean): `cd " + ROOT + "/host/web && npx vite-node scripts/ssr_repro.tsx <abs path of the response json>` — EVERY card with a payload must print 'rendered OK'; a THROWS (component crash on the served payload) or a NULL-fallback is a DEFECT {layer: 'family-H render'} for that card even if its payload was honest.\n" +
  "  (iv) For EVERY card in response.cards, ADVERSARIALLY check the CONTRACT — a card is ok=true only if you TRIED and could not fault it; honest_gap=true when a leaf is honestly blank WITH a reason. Cross-check 'not logged'/blank leaves against a direct neuract SELECT (column actually has live data? if yes → [ems_exec/validate] or [ems_exec/fill] defect, cite the stage/ai log). For each defect set `log_evidence` to the citation (stage line / ai_ prompt snippet / DB count).\n" +
  "Return per page {nn,prompt,run_id,routed,expected,routed_ok,asset,cards_ok,cards_total,cards[{card_id,ok,honest_gap,issue,layer,log_evidence}],defects[],honest_gaps[],infra_down}.",
  { label: 'sweep b' + (bi+1), phase: 'Sweep', schema: BATCH })
const sweeps = (await parallel(BATCHES.map((b, i) => () => runBatch(b, i)))).filter(Boolean)
const allPages = sweeps.flatMap(s => s.pages || [])
const defPages = allPages.filter(p => (p.defects || []).length || !p.routed_ok)
log('SWEEP: ' + allPages.map(p => p.nn + ':' + p.cards_ok + '/' + p.cards_total + (p.routed_ok ? '' : '(MISROUTE)') + ((p.defects||[]).length ? '(DEF)' : '')).join(' '))

phase('CrossClass')
const CROSS = [
  "Real-time power of DG-03 Jackson", "Load profile of UPS-04 over the last 24 hours", "UPS-01 load percentage right now",
  "Show voltage levels for Transformer-03", "Show voltage for UPS-10", "real-time power and current for Transformer 01",
  "energy consumption of Transformer-05 today", "power quality for a spare feeder", "voltage and current health for AHU-5",
]
const cross = await agent(COMMON + "CROSS-CLASS / EDGE prompt batch (log-grounded). Run each via `curl /api/run -o " + SWEEP + "/pages/cross_<i>.json`, map prompt→run_id via " + HOSTLOG + ", and classify OK / DEFECT(family) / honest-degrade — focus on: wrong-asset HOMONYM pins (must surface picker, never render a different live asset's data as the answer), candidate recall (the named asset must be offered), class-appropriate routing, sparse/dead meters honest-blank+reason (not whole-asset 'no data' when a metric IS live), no NaN/seed. For any mis-pin/mis-route cite the layer1b/1a stage line or ai_ log. PROMPTS:\n" + JSON.stringify(CROSS, null, 1) + "\nReturn a compact per-prompt verdict list + defect families + the run_ids.", { label: 'crossclass', phase: 'CrossClass' })

phase('Matrix')
const matrix = await agent(COMMON + "FINAL VERIFICATION MATRIX + LOG INVENTORY + BUNDLE. From the sweep + cross-class + preflight below, produce and APPEND to outputs/VERIFY18_WORKLOG.md:\n" +
  "(1) the 18-page × card table — nn | page | run_id | cards ok/total | routed_ok | DEFECTS(layer+log_evidence) | honest gaps(reason) | infra.\n" +
  "(2) totals (cards ok / defects / misroutes / honest-gaps) + defect FAMILIES (A fab-by-zero, B seed, C false-blank, D misroute, E legend/unit leak, F emit-timeout, G semantic mis-bind) with the card ids in each.\n" +
  "(3) the frames=payloads gate result + renderer coverage from preflight.\n" +
  "(4) cross-class verdict.\n" +
  "(5) LOG INVENTORY: run `ls " + LOGS + "` — count pipeline_*/ai_*/failures_* files; total LLM calls = `cat " + LOGS + "/ai_*.jsonl | wc -l`; the per-page prompt→run_id map; note any page whose ai_/pipeline_ log is missing (a logging gap).\n" +
  "(6) BUNDLE the logs for the user: `cp -r " + LOGS + " " + SWEEP + "/logs && cp -r " + ROOT + "/outputs/notes " + SWEEP + "/notes 2>/dev/null; ls -la " + SWEEP + " " + SWEEP + "/pages | tail -40` — report the final bundle path + file counts.\n" +
  "(7) EXPLICIT verdict — is the contract CERTIFIED (every card on all 18 pages smooth + payload-direct + real-or-honest-blank+reason, zero fabrication/NaN/payload_error, class-correct routing) or exactly what still blocks it (strictly DEFECT vs HONEST-GAP vs INFRA vs KNOWN-OPEN[nameplate]) — cite card ids + layers + log evidence.\n" +
  "PREFLIGHT: " + JSON.stringify(String(pre).slice(0,600)) + "\nSWEEP: " + JSON.stringify(allPages, null, 1) + "\nCROSS: " + JSON.stringify(String(cross).slice(0,1500)),
  { label: 'matrix', phase: 'Matrix' })
return { sweep_dir: SWEEP, preflight: String(pre).slice(0,400), pages: allPages, defect_pages: defPages.map(p=>p.nn), cross: String(cross).slice(0,800), matrix: String(matrix) }
