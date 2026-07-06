export const meta = {
  name: 'v48-batch12-layer2',
  description: 'FAST 70/70 loop round: fix the given residuals (parallel agents grouped by layer, disjoint files) -> host restart -> TARGETED parallel re-verify of ONLY the affected pages (6 reviewer batches) + SSR render gate -> return the new residual list. Full-18 certification is a separate final sweep; this round-harness is optimized for wall-clock (parallel reviewers, targeted pages, disk-dump reads, no idle serialization). Args: {residuals:[{page,card_id,issue,layer,log_evidence}], ts, prompts?: {page->prompt overrides}}.',
  phases: [
    { title: 'Fix', detail: 'residuals grouped by layer -> parallel fix agents (disjoint file fences)' },
    { title: 'Verify', detail: 'pytest + imports + host restart' },
    { title: 'Recheck', detail: 'parallel: affected pages re-run+audited in 6 batches + SSR gate over fresh dumps' },
  ],
}
const ROOT = "/home/rohith/desktop/BFI/backend/layer2/pipeline_v48"
const PY = "/home/rohith/.pyenv/versions/3.11.9/bin/python3.11"
const A = args || {}
const INLINE_RESIDUALS = [{"page": "transformer-asset-dashboard/thermal-life", "card_id": "76", "issue": "A1 _morphed contract: metadata.md:20 says OPTIONAL/audit-only but producer.py:64-92 applies ONLY declared morphs (2/6812 compliance) — make _morphed REQUIRED in prompt, add \"_morphed\":[] to the contract exemplar (data_instructions.md:263), add _undeclared_morphs telemetry diff in producer (NO auto-promote)", "layer": "layer2-emit-prompts", "log_evidence": "6812 parsed l2_emit across _log_archive: _morphed present in 2"}, {"page": "transformer-asset-dashboard/thermal-life", "card_id": "76", "issue": "A2 canonical proxy rule: state same-quantity-family proxy ONCE (metadata.md:7, data_instructions.md:188-198 delete 'different-quantity...you may bind it', :240, user_message.py:213-215 add SAME-QUANTITY qualifier, column_system.md:14 align vocab) — proven cross-quantity bind followed the laxest restatement", "layer": "layer2-emit-prompts", "log_evidence": "ai_r_f3b19721cb calls 6+10: loadFactorPct/active_power_total_kw bound into timeline.tempAxis.* expected_qty=temperature"}, {"page": "panel-overview-shell/voltage-current", "card_id": "18", "issue": "A4 build.py:403 answerability fail-open: absence -> 'full'; change default to 'partial' + read data_instructions-nested answerability/data_note fallback (rescues 29 nested)", "layer": "layer2-build", "log_evidence": "730/6812 emits omit top-level answerability; 29 nest inside data_instructions"}, {"page": "panel-overview-shell/voltage-current", "card_id": "18", "issue": "A5 user_message.py:255-282: panel_aggregate WITH roster_spec falls into NO-FIELDS-CARD/OMIT-ems_backend chrome text while also told 'roster MUST conform' — add third branch (ROSTER CARD: roster conforming to roster_spec + fields:[] + endpoint; answerability=member coverage); write against the gate's real acceptance", "layer": "layer2-emit", "log_evidence": "23 calls: 12 emitted ems_backend, 11 omitted; card 18 dropped roster entirely"}, {"page": "panel-overview-shell/real-time-monitoring", "card_id": "*", "issue": "A6a user_message.py:19-20 gates.fields_optional_classes default missing 'panel_aggregate' (build.py:383/validate/build.py:54 carry 5) — add token or hoist ONE accessor config/gates_vocab.py imported by all 3 (+2 test literals)", "layer": "layer2-emit", "log_evidence": "DB row has 5 entries; user_message default has 4"}, {"page": "panel-overview-shell/energy-power", "card_id": "*", "issue": "A6b host/display_dash.py:68 mirror stale: [\"kw\",\"kwh\"] vs row [\"kw\",\"kwh\",\"kva\",\"kvar\"] — byte-equal the code default (DB-outage fmt(null) re-crash parity)", "layer": "exec-display", "log_evidence": "row display.unit_value_key_suffixes extended by concurrent fixer"}, {"page": "individual-feeder-meter-shell/real-time-monitoring", "card_id": "*", "issue": "A6c ems_exec/executor/roster.py:80 default 'off' vs row 'on' — flip code default to 'on' (row stays the kill-switch); outage currently disables the whole roster interpreter", "layer": "roster-exec", "log_evidence": "SELECT roster.interpreter_enabled='on'"}, {"page": "ups-asset-dashboard/battery-autonomy", "card_id": "70", "issue": "B1 serve data_note + l2_answerability: host/server.py:312-347 _enrich_card additive fields; render beside gap-chip in host/web/src/cmd/registry.tsx:157-165 or fold into _gap_note so proxy notes hit render.reason — 1369 notes currently invisible", "layer": "frontend-web-serve", "log_evidence": "response_r_44796d791a card 70 proxy note dropped; grep host/web: no consumer of notes"}, {"page": "panel-overview-shell/harmonics-pq", "card_id": "23", "issue": "C1 user-message token bundle: RAW-star/FAIL per-line prose -> tokens + header defs (user_message.py:39-45); slot qty parenthetical -> '| expected_qty=X' (slot_catalog.py:255-261); drop empty metric/rank fields (user_message.py:34-36,210); cap relevant-cols why-prose to conf<1.0 rows (:56-65); move endpoint closed-set/retired/choose-by to system prompt (:168-174,229-232 -> data_instructions.md ems_backend section). ONE A/B run after", "layer": "layer2-emit-prompts", "log_evidence": "measured: 129580+12376 star/fail chars, 48275 slot-suffix chars, 4540/4540 empty metric+rank, 95319 endpoint chars per sweep"}, {"page": "panel-overview-shell/harmonics-pq", "card_id": "5", "issue": "C2 emit.py:24-46 filter RECOVERY LIBRARY to basket-compatible fns (+ '(N fns hidden...)' trailer, keep honest-degrade line, nameplate fns only when rating populated); ROSTER section only when roster_spec/panel_aggregate (data_instructions.md:212-232). Tail-only change preserves prefix cache", "layer": "layer2-emit", "log_evidence": "7812-char library, 50 fns unfiltered to all 85 calls; ROSTER ships to 85, needed by 28"}, {"page": "diesel-generator-asset-dashboard/voltage-current", "card_id": "69", "issue": "C3 add NAMEPLATE fact line (config/nameplates.py; '- => unbindable, omit') + DATA WINDOW first/last/age line ('anchor to last, not wall-clock') to ASSET block (user_message.py:198-199); add last=<ts> per member in panel_members_block.py. GATED on the fixed nameplate re-seed (209 fabricated class_default rows)", "layer": "layer2-emit", "log_evidence": "255 no_reading blanks; 28/38 window emits chose today; card 69 const I_RATED=131, card 40 ratedKw=600 on faith"}, {"page": "transformer-asset-dashboard/tap-rtcc", "card_id": "*", "issue": "C4 prompt text corrections: const/source contradiction (data_instructions.md:103 vs :209 vs gates.py:556 — document 'live|test-db|$ctx|const', split the 2332B bullet in 4, drop mock asides); FOUR->FIVE walls (:47,:98,:260 + user_message.py:249); '(see PART 3)' -> BEST-EFFORT+ANSWERABILITY (metadata.md:7); filename ref (user_message.py:247); move RTM/HPQ sectionContracts fixtures out of metadata.md:19 into the 2 cards' user context", "layer": "layer2-prompts", "log_evidence": "grep of logged 53482B system: no PART 3; gate wants live|test-db|const|$ctx"}];

const RESIDUALS = (A.residuals && A.residuals.length ? A.residuals : INLINE_RESIDUALS)
const COMMON = "Root " + ROOT + " (PYTHONPATH=root; py " + PY + "). DB cmd_catalog via data.db_client.q; neuract via psql :5433 target_version1 search_path=neuract or ems_exec.data.neuract. MANDATE: zero fabrication; per-leaf honest degradation (blank+reason=PASS); config-first, generic code, NO per-card hardcoding; pytest -m 'not live' GREEN; read files errors='replace'. The host dumps every /api/run response to outputs/logs/response_<run_id>.json (disk = source of truth; curl timeout harmless). SSR gate: cd host/web && npx vite-node scripts/ssr_repro.tsx <abs.json> — a card THROW = family-H defect.\n"
const FIX = { type: 'object', additionalProperties: false, properties: {
  summary: { type: 'string' }, files_changed: { type: 'array', items: { type: 'string' } }, tests: { type: 'string' } },
  required: ['summary','files_changed','tests'] }
const RES = { type: 'object', additionalProperties: false, properties: {
  pages: { type: 'array', items: { type: 'string' } }, cards_ok: { type: 'integer' }, cards_total: { type: 'integer' },
  residual_defects: { type: 'array', items: { type: 'object', additionalProperties: false, properties: {
    page: { type: 'string' }, card_id: { type: 'string' }, issue: { type: 'string' }, layer: { type: 'string' },
    log_evidence: { type: 'string' } }, required: ['page','card_id','issue','layer'] } } },
  required: ['pages','cards_ok','cards_total','residual_defects'] }

// ---- group residuals by rough layer so fixers get disjoint file fences ----
const groups = {}
for (const r of RESIDUALS) {
  const l = String(r.layer || 'other')
  const key = /layer2|emit|gates|prompt/i.test(l) ? 'layer2' : /strip|payload|grounding|seed/i.test(l) ? 'strip'
            : /fill|roster|render|exec|derivation|validate/i.test(l) ? 'emsexec' : /web|frontend|ssr|component/i.test(l) ? 'fe' : 'other'
  ;(groups[key] = groups[key] || []).push(r)
}
const FENCES = {
  layer2: "FILES: layer2/** + db seeds + tests ONLY.",
  strip: "FILES: grounding/**, validate/leaf_classify.py, db seeds, scripts/build_stripped_payloads.py (+ REBUILD payload_stripped after) + tests ONLY.",
  emsexec: "FILES: ems_exec/**, host/display_dash.py, config/**, db seeds + tests ONLY.",
  fe: "FILES: host/web/** + host/server.py + tests ONLY.",
  other: "FILES: whatever the defect requires EXCEPT files another group owns (layer2/grounding/ems_exec/host-web core) — coordinate by leaving those to their owners; db/config preferred.",
}

phase('Fix')
const fixers = Object.entries(groups).map(([k, rs]) => () => agent(
  COMMON + "RESIDUAL FIX group '" + k + "'. " + FENCES[k] + "\nClose EVERY residual below at its root (verify each against DB/logs first; generic fixes; a genuinely-honest gap = reclassify with the reason instead of forcing data):\n" +
  JSON.stringify(rs, null, 1).slice(0, 12000) + "\nRun `pytest -m 'not live' -q`. Report files + per-residual disposition.",
  { label: 'fix:' + k, phase: 'Fix', schema: FIX }))
const fixed = (await parallel(fixers)).filter(Boolean)
log('FIX groups done: ' + fixed.map(f => (f.files_changed||[]).length + 'f').join(' '))

phase('Verify')
const vf = await agent(COMMON + "VERIFY combined: (1) full `pytest -m 'not live' -q -p no:cacheprovider` GREEN; (2) imports: layer2.gates, layer2.build, ems_exec.executor.fill, grounding.role_scrub, host.server; (3) if the strip group changed anything: payload_stripped rebuilt + rescan clean; (4) RESTART the host: kill every host/server.py pid (ps|grep, kill -9), then `cd " + ROOT + " && (PYTHONPATH=. PYTHONUNBUFFERED=1 nohup " + PY + " host/server.py > outputs/replay_host.log 2>&1 &)`, poll /api/health ok. Report pass/fail per point. FIXED: " + JSON.stringify(fixed.map(f=>f.files_changed)).slice(0,1500), { label: 'verify+rehost', phase: 'Verify' })
log('VERIFY: ' + String(vf).slice(0,150))

phase('Recheck')
// targeted pages only; canonical prompt per page_key
const PROMPTS = Object.assign({
  "panel-overview-shell/real-time-monitoring": "real time monitoring for PCC Panel 1",
  "panel-overview-shell/energy-distribution": "energy and distribution for PCC Panel 1",
  "panel-overview-shell/energy-power": "energy and power for PCC Panel 1",
  "panel-overview-shell/harmonics-pq": "harmonics and power quality for PCC Panel 1",
  "panel-overview-shell/voltage-current": "voltage and current for PCC Panel 1",
  "individual-feeder-meter-shell/voltage-current": "voltage and current for GIC-01-N3-UPS-01",
  "individual-feeder-meter-shell/real-time-monitoring": "real time monitoring for GIC-01-N3-UPS-01",
  "individual-feeder-meter-shell/energy-power": "energy and power for GIC-01-N3-UPS-01",
  "individual-feeder-meter-shell/power-quality": "power quality for GIC-01-N3-UPS-01",
  "diesel-generator-asset-dashboard/voltage-current": "dg voltage and current for DG-1",
  "diesel-generator-asset-dashboard/engine-cooling": "dg engine and cooling for DG-1",
  "diesel-generator-asset-dashboard/fuel-efficiency": "dg fuel efficiency for DG-1",
  "diesel-generator-asset-dashboard/operations-runtime": "dg operations and runtime for DG-1",
  "transformer-asset-dashboard/tap-rtcc": "transformer tap and rtcc for Transformer-01",
  "transformer-asset-dashboard/thermal-life": "transformer thermal life for Transformer-01",
  "ups-asset-dashboard/battery-autonomy": "ups battery and autonomy for GIC-01-N3-UPS-01",
  "ups-asset-dashboard/output-load-capacity": "ups output load capacity for GIC-01-N3-UPS-01",
  "ups-asset-dashboard/source-transfer": "ups source transfer for GIC-01-N3-UPS-01",
}, A.prompts || {})
const pages = Array.from(new Set(RESIDUALS.map(r => String(r.page)))).filter(p => PROMPTS[p])
const chunks = []
for (let i = 0; i < pages.length; i += 3) chunks.push(pages.slice(i, i + 3))
const audit = (chunk, bi) => agent(COMMON +
  "TARGETED RE-VERIFY batch " + (bi+1) + " — pages: " + JSON.stringify(chunk) + " (prompts: " + JSON.stringify(chunk.map(p=>PROMPTS[p])) + "). Per page SEQUENTIALLY: curl -s -m 540 -X POST http://localhost:8770/api/run -d '{\"prompt\":\"<prompt>\"}' -H 'Content-Type: application/json' (asset_pending -> re-POST once with the class-matched candidate id); read the disk dump outputs/logs/response_<run_id>.json; AUDIT EVERY card adversarially vs neuract (zero fabrication incl seeds/cross-quantity/derived-zero/wrong-window; every blank leaf carries a reason; no payload_error) AND run the SSR gate on the dump (cd host/web && npx vite-node scripts/ssr_repro.tsx <abs dump>) — any THROW is a family-H defect. Return {pages, cards_ok, cards_total, residual_defects[]}.",
  { label: 'recheck b' + (bi+1), phase: 'Recheck', schema: RES })
const results = (await parallel(chunks.map((c, i) => () => audit(c, i)))).filter(Boolean)
const residual = results.flatMap(r => r.residual_defects || [])
const ok = results.reduce((s, r) => s + (r.cards_ok||0), 0), tot = results.reduce((s, r) => s + (r.cards_total||0), 0)
log('RECHECK: ' + ok + '/' + tot + ' ok on affected pages; residuals=' + residual.length)
return { fixed_groups: Object.keys(groups), cards_ok: ok, cards_total: tot, residual_defects: residual }
