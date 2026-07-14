# Latency audit — LENS: multi-asset / compare path (2026-07-14)

Scope: RESPONSE_MULTI (admin all-time: p50 142s / p90 683s / max 835s). Worst live runs = 3-feeder compares
410-441.7s. Files: host/multi_asset.py, host/asset_lanes.py, host/rebind_consumer.py, host/compare_overlay.py,
host/compare_mode.py, layer1b/resolve/asset_resolve.py, layer1b/compare/*, run/harness.py.

VERDICT UP FRONT: the multi path's own python is negligible (rebind 0.4ms, overlay merge 2.1ms). The seconds live in
(1) the registry/has_data PROBE FAMILY over the :5433 tunnel, paid 2-3x serially per compare, whose cold cost (181s
measured today) EXCEEDS its own TTL (120s) so interactive traffic is nearly always cold; (2) SEQUENTIAL class lanes
(k classes = k x (1b + L2 wall)); (3) one PATHOLOGICAL 14.6K-completion-token L2 roster emit on panel compares
(118.6s of the worst post-fix run's 142.1s); (4) SEQUENTIAL per-asset executor fills; (5) serial LLM tails
(compare_mode, knowledge gate). Also: the 683s/835s admin numbers are measurement artifacts, and elapsed_ms
UNDERSTATES real user-visible latency by the whole pre-flight (real r_92ca384874 = 617s user-visible vs 441.7s
reported).

--------------------------------------------------------------------------------------------------
## Ground truth traces used

### A. r_92ca384874 — the 441.7s "3-feeder" compare (Jul-12 10:12-10:23, trace t_ad2d1cbbee6546f78a8b58dcdd4256aa)
prompt: 'Compare Aux-Hsd-Plc, Gic-01-N10-Hhf-01 (Type-01) 300A +600Kvar, Gic-01-N6-Spare Power Factor'
3 assets, 2 classes (Load x2, Spare x1), 12 cards. NATURAL-COMPARE path (no picker ids).
Absolute decomposition (obs_stage_events + ai_*.jsonl + pipeline_*.jsonl):
- 10:12:45 request_received; knowledge_gate 0.2s
- 10:12:45-46.9 natural-compare: asset_candidates probe (warm) + 3 CONCURRENT resolve_asset LLM calls (all done in ~1.4s)
- 10:12:47 -> 10:15:40 = ~173s: post-LLM natural-compare block (at that date each sub-resolve re-ran its OWN
  asset_candidates probe concurrently - since fixed by the cands-share; the surviving equivalent today is the
  resolve_assets probe below)
- t0 (build_response_multi) 10:15:40 -> lane1 PROMPT 10:18:32 = 172.3s: resolve_assets(asset_ids) ->
  asset_candidates() FULL COLD PROBE (host/asset_lanes.py:12)
- lane1 (Load, rep AUX-HSD-PLC): 1a 2.8s || 1b 0.3s (warm cache); L2 emit 4 cards 44.4s
- lane2 (Spare, GIC-01-N6-Spare, no_data): asset_resolution span 179.3s DEGRADED (window_nonnull/col_dict probes on
  the dark table + basket LLM under vLLM contention; basket response logged as the LAST event of the span);
  L2 emit 39.0s
- executor fills: 3 assets SEQUENTIAL, ~0.1-1.2s per card, ~3.4s total; overlay/notes ~0
- RESPONSE_MULTI 10:23:02, elapsed_ms=441,695
- REAL USER-VISIBLE: 10:12:45 -> 10:23:02 = 617s (the 175s pre-flight is BEFORE t0 and invisible to elapsed_ms)

### B. r_0038430c8b — 393.5s, 3 assets ONE class (Compressor), 12 cards (Jul-12 10:29-10:36)
- t0 10:29:47 -> lane PROMPT 10:32:40 = ~173s resolve_assets asset_candidates COLD PROBE (again)
- lane: 1a||1b join = 178.6s (1b dominated: no_data "Air Compressor Panel": asset_candidates + window_nonnull +
  feeder_table BFS probes + basket) — the probe family AGAIN, different cache keys
- L2: 35.1s (4 cards); exec 3 assets x ~1.1s serial waves = 4.6s
- => ~352s of 393.5s (89%) is probe-family + probe-shaped 1b work done TWICE; L2 was only 35s.

### C. r_597276cbd7 — the WORST POST-FIX run: 142.1s, Jul-13 16:44, 'compare harmonics and power quality for pcc
panel 1 and pcc panel 2' (2 panels, 1 class, 5 cards, overlay mode)
- resolve_assets ~0s (warm); 1a 6.6s || 1b ~0s; validate 0.3s
- L2 emit 5 cards: 118.6s wall — 4 emits (26-28.5K prompt toks, 1.9-2.7K completion) done in 24-48s;
  ONE emit (card 23, roster-based panel card) emitted 14,614 COMPLETION TOKENS and finished at 118.6s
  (14614 toks / 118.6s ~ 123 tok/s decode). THE single dominant term.
- exec: asset-1 fill 4.6s wall, THEN asset-2 fill 11.9s wall (serial; asset-2 slower - cold member caches +
  in-exec narrative LLM call per asset, 2 small ~600-tok calls observed 10s apart)
- compare_mode LLM: 167 prompt/12 completion toks, ~1-2s serial tail
- 142.1 = 6.6 (1a) + 118.6 (L2) + 16.5 (serial fills) + ~1.5 (compare_mode+misc)

### D. Live measurement (2026-07-14, this audit)
- asset_candidates(): COLD = 181.0s, WARM(TTL) = 0.01s, 328 rows. TTL knob cache.resolution_ttl_s = 120s.
  COLD COST > TTL => the cache can never stay warm without traffic every <2min; every fresh compare pays it.
  The probe = value_counts() UNION-ALL latest-row jsonb probes, ~40 tables/chunk x ~7 chunks, SEQUENTIAL chunks
  (data/value_probe.py:67 for-loop), each chunk ~26s over the VPN tunnel (matches baseline "worst 29.3s single call").
- rebind_consumer: 0.4 ms/call (12-card recipe). merge_all overlay: 2.1 ms/call (12 cards, 160KB). DEAD END.
- RESPONSE_MULTI distribution mined from outputs/logs (405 records): groups=1 n=395, groups=2 n=10 =>
  author-once-per-class HIT RATE ~97.5% of multi responses (misses only when named assets classify differently).
  Jul-13 (healthy day): p90 74.5s, max 142.1s. All 400s+ runs were Jul-12 (tunnel+vLLM chaos day).
- Admin RESPONSE_MULTI p90 683s / max 835s (n=18) = PAIRING ARTIFACT: stage latency = gap-from-previous-record;
  files holding >1 appended execution (and the shared pipeline_r_multi/pipeline_r_out fixtures) produce
  cross-execution "gaps" measured up to 243,396s. Honest per-run pairs (PROMPT->RESPONSE_MULTI, n=7, all Jul-13):
  max 142.1s. NO real regression after Jul-12; the mined e2e_multi "median 4ms" is pytest/fake-LLM pollution
  (128 assets=1 records + zero-elapsed rows).

--------------------------------------------------------------------------------------------------
## FINDINGS (ranked by estimated saving)

### MC-1. Registry/has_data probe family: cold cost (181s) > TTL (120s) — paid 1-3x serially per compare  [BIGGEST]
Evidence: measured cold=181.0s warm=0.01s (today); lib/ttl_cache.py _TTL_DEFAULT=120 + DB knob
cache.resolution_ttl_s=120; data/value_probe.py:67 sequential chunk loop; trace A paid ~172s (resolve_assets) +
179.3s (lane2 1b); trace B paid ~173s + 178.6s. Call sites per compare POST: host/asset_lanes.py:12 (resolve_assets),
host/multi_asset.py:49 (natural compare), layer1b/resolve/asset_resolve.py:110 (per class lane), + feeder BFS/
window_nonnull with distinct cache keys.
Mechanism: TTL expiry + sequential UNION-chunk probes over the FortiClient tunnel; interactive traffic arrives
>120s apart so it is nearly ALWAYS cold; a probe that takes 181s guarantees the NEXT stage's re-probe risk too.
Proposals (all honest / fail-open preserved):
  a) CONFIG: dedicated longer TTL for the registry+value-probe keys (e.g. 900s) — the resolution layer already
     tolerates 120s staleness by design; never-cache-empty + outage-raise stay.
  b) SMALL: stale-while-revalidate — serve last-good snapshot instantly, refresh in a background thread
     (the flap-poison concern that motivated TTL is already covered by never-cache-empty + outage-raise).
  c) SMALL: parallelize value_counts/tables_with_data chunks over the pooled psycopg2 door: 7 chunks x 26s
     serial -> ~26-40s wall cold.
Saving arithmetic: cold compare today = 172s (resolve_assets) + up to 179s (lane 1b) = ~350s of the 393-442s
Jul-12 runs; with (a)+(b) both go to ~0 warm / one background refresh; with (c) alone cold drops 181->~30s.
=> -170s to -350s on cold-cache compares; 0 on warm. Also applies verbatim to the single-asset path (1b live
median 22s / p95 200s is this same mechanism).

### MC-2. Giant roster-card L2 emit: 14.6K completion tokens = 118.6s of the worst post-fix multi run
Evidence: trace C — ai_r_9aa8e076e4.jsonl call 8: prompt 28,581 toks, completion 14,614 toks, returned 70.8s after
its 4 sibling emits; lane L2 wall 118.6s of the 142.1s total. Sibling emits on the same page: 1.9-2.7K completion.
Mechanism: decode-bound at ~123 tok/s — the emit enumerates per-member roster leaves that the executor's
panel_aggregate renderer re-derives from the DB anyway (roster fold exists: roster_for + deterministic gates).
Proposal: let roster cards emit a COMPACT roster directive (member enumeration folded by the existing deterministic
roster machinery), and/or set a per-card max_tokens sanity cap with per-leaf-honest degrade. AI still authors the
recipe; only the redundant enumeration shrinks.
Saving: 14,614 -> ~2,000 toks at 123 tok/s = 118.6s -> ~16s => -95 to -100s on panel-overview compares
(142.1s -> ~45s e2e). Cross-ref: layer2 lens (same finding family for single-asset panel pages).

### MC-3. Class lanes run SEQUENTIALLY (run/harness.py:409-416)
Evidence: `for cls, members in by_class.items(): lane = run_pipeline(...)` — trace A: lane1 47.5s then lane2 218.5s
(266s serial). Lanes 2+ have layer1a INJECTED (nothing to wait for except lane1's 1a, available at +2.8s).
Mechanism: k classes = k x (1b + validate + L2 wall) purely additive; lane2+ 1b (probe+basket) and L2 emits could
overlap lane1's L2 decode (vLLM KV usage 10-12% — headroom; observed per-stream ~57 tok/s at batch 4-5 vs
100-320 tok/s aggregate).
Proposal: run lane1's 1a to completion (or 1a alone first), then fan ALL class lanes' (1b + L2) concurrently;
REPLACE the per-lane emit cap (layer2.emit_concurrency=4 read inside run_2_all) with a GLOBAL vLLM admission
semaphore so k lanes don't queue k x 4 emits blindly.
Saving arithmetic: trace A: 266s serial -> ~max(47.5, 218.5)=218.5s => -47.5s. Healthy 2-class compare
(2 x ~40s lanes) => -35-45s; 3-class => -70-90s. Worst case (decode-throughput-bound vLLM) saving reduces to the
non-LLM serial parts (1b + validate, 2-180s/lane). Confidence discounted accordingly.

### MC-4. Per-asset executor fills are SEQUENTIAL (host/multi_asset.py:127-139)
Evidence: trace C — asset-1 fill wall 4.6s, then asset-2 fill wall 11.9s (16.5s serial); trace A/B: 3 assets x
~1-1.2s waves. Each assemble_cards is per-CARD parallel (<=8 workers, 45s budget) but assets serialize; the
panel narrative_ai leaf adds a small in-exec LLM call PER ASSET (2 observed, 10s apart, serial).
Mechanism: pure DB-bound fan-out (no authoring) run k_assets times back-to-back; budget is per-asset so worst case
is max_assets(6) x 45s = 270s serial ceiling.
Proposal: run per-asset assemble_cards concurrently (ThreadPool over assets; global card-fill cap ~12-16 to protect
the tunnel + pooled door), keep per-leaf honesty untouched (each lane's fill already independent by construction —
rebind_consumer deep-copies).
Saving: trace C => -4.6s; 3-panel compares (member fan-outs, cold member caches) => -10 to -25s; pathological
budget-bound case 270s -> 45s. Also parallelizes the per-asset narrative LLM calls (-10s on 2-panel compares).

### MC-5. natural_compare pre-flight work is DISCARDED and INVISIBLE
Evidence: host/server.py:398-402 -> host/multi_asset.py:46-90: detection probe + N concurrent resolve_asset LLM
calls resolve each name; the confident mfm_ids are returned but the RESOLUTIONS are thrown away —
build_response_multi then re-runs resolve_assets (fresh asset_candidates, trace A: 172s) and each lane's run_1b
re-runs pinned resolve + probes. None of this is inside elapsed_ms (trace A: 175s pre-flight; user-visible 617s vs
reported 441.7s).
Proposal: return (ids, cands, as_asset dicts) from natural_compare_ids; plumb cands into resolve_assets
(host/asset_lanes.resolve_assets(asset_ids, cands=...)) and into each lane's run_1b -> resolve_asset(cands=...)
(the kwarg already exists: layer1b/resolve/asset_resolve.py:104). Stamp a pre-flight obs span.
Saving: removes 1-2 probe slots: ~0s warm, -170 to -350s cold (multiplies with MC-1; standalone it is the
difference between 1 and 3 cold probes).

### MC-6. compare_mode LLM = serial tail on EVERY multi response, unbounded to 120s
Evidence: host/multi_asset.py:145-146 runs AFTER all lanes + fills; host/compare_mode.py call_qwen stage=
'compare_mode' — no llm.timeout.compare_mode row exists (checked app_config), so it falls to llm.timeout=120s;
fail-open default is 'overlay'. Measured: 167 prompt / 12 completion toks, ~1-2s (trace C tail).
Proposal: fire it at t0 CONCURRENTLY with run_pipeline_multi (depends only on the prompt; join before merge);
add an app_config row llm.timeout.compare_mode=10.
Saving: -1-2s p50 every multi run; caps a 120s tail risk (a vLLM hang would today add up to 120s to EVERY compare).

### MC-7. Picker round trip redoes 1a (and the probes) from zero
Evidence: first run to picker measured 7.9-12.6s (3 compare-shaped asset_pending responses); the re-POST enters
build_response_multi which re-routes 1a in lane1 (6.6s trace C) + re-probes resolve_assets; run_id =
make_run_id(prompt) is DETERMINISTIC so the first run's 1a is trivially addressable.
Proposal (flag-gated): cache the first run's layer1a by run_id (TTL ~10min); on a re-POST with asset_ids for the
same prompt-hash, inject it via the EXISTING layer1a= injection seam (run_pipeline already supports it; the multi
path already locks the template this way). The 1a decision is still the AI's — same prompt, same answer, cached.
Saving: -6-9s on every picker->compare round trip (+probe slot removal with MC-5).

### MC-8. Knowledge gate serializes ahead of every fresh compare prompt
Evidence: server.py:370-392 — _ems_ask runs BEFORE natural_compare detection; measured 0.2s (trace A span), baseline
0.7s p50. Both depend only on the prompt.
Proposal: run knowledge gate || natural_compare detection (discard compare work if the gate returns terminal).
Saving: -0.2-0.7s p50 fresh compares. Small but free.

### MC-9. Telemetry: RESPONSE_MULTI metrics mislead optimization
Evidence: (i) elapsed_ms starts at build_response_multi t0 — excludes knowledge gate + natural-compare pre-flight
(trace A: 175s invisible; real user-visible 617s). (ii) admin latency pairs gap-from-previous-record: files with
appended executions + the pipeline_r_multi/pipeline_r_out fixtures yield fake "stage latencies" up to 243,396s —
the all-time p90 683s / max 835s are artifacts; honest Jul-13 pairs: max 142.1s. (iii) mined e2e_multi median 4ms =
pytest leakage (zero-elapsed + assets=1 records).
Proposal: stamp t0 at handle_run entry for the multi leg (or add a preflight stage record under the envelope rid);
admin: pair only within marker-bounded executions; exclude fixture rids.
Saving: none directly — prevents chasing phantom regressions and hides no real 175s pre-flight regressions.

### MC-10. No recipe reuse on REPEAT prompts (flag-gated L2 recipe cache)
Evidence: every re-POST of the same compare re-pays k x L2 wall (35-120s) although the emit inputs (prompt, page,
class recipe, basket fingerprint) are identical; run ids are already deterministic prompt hashes.
Proposal (explicitly allowed: "cache/batch/shrink/parallelize AI decisions"): TTL cache keyed
(prompt_hash, page_key, class, basket fingerprint) -> layer2 recipe; flag-gated, bypassed on any fingerprint drift.
Saving: repeat compare -> probes+exec only: 142.1s -> ~20s (trace C shape); -35 to -120s per repeat.

### MC-11. Lanes 2+ pay full ~26-28K-token prefill per emit — 0% vLLM prefix-cache hits
Evidence: baseline journal "Prefix cache hit rate: 0.0% ALWAYS"; trace A lane2 re-emitted the SAME 4 cards as lane1
with ~19-21K-tok prompts; trace C emits 26-28.5K toks each. Prefill 26K/10,440 tok/s ~ 2.5s/card; a 2nd class lane
re-pays ~4 x 2.5s = 10s that a shared stable prefix would mostly skip.
Proposal: (vLLM lens owns root cause) — order L2 emit prompts stable-prefix-first (system + page + card scaffolding
BEFORE per-asset basket/facts) and enable/verify --enable-prefix-caching; multi benefits k-fold.
Saving: ~-2s/card on cards 2..N within a lane + ~-10s per additional class lane. Cross-ref: vllm/layer2 lens.

### MC-12. Bus-section 2-lane compares fill the SAME panel twice
Evidence: host/asset_lanes.py:15-30 — {"id": X, "section": "A"}/{"id": X, "section": "B"} = 2 lanes over ONE
mfm/table; each lane's fill fans out that panel's members again (section-filtered). The deterministic section_split
overlay (roster_pres_sections) already produces per-section series from ONE fill.
Proposal: for same-mfm section lanes, fill ONCE with section_split and split at the overlay merge.
Saving: -1 x panel fill wall (~4-12s; up to 45s budget-bound). Rare path (picker section entries only).

--------------------------------------------------------------------------------------------------
## Investigated DEAD ENDS (do not re-chase)
- rebind_consumer deepcopy: 0.4 ms/call (12-card recipe) — negligible.
- compare_overlay merge_all: 2.1 ms/call (12 cards, 160KB payloads) — negligible.
- copy.deepcopy(shared_1a) per lane (harness.py:413): small dict — negligible.
- Lane-folding by SCHEMA fingerprint instead of class: checked trace A's pair — aux_hsd_plc_feedbacks (67 cols) vs
  gic_01_n6_spare_p1 (72 cols) share only ONE column name; the 2-lane split was JUSTIFIED (recipes bind by column
  name). Folding would only fire on genuine schema twins; class labels are a decent proxy. Keep as-is.
- Author-once-per-class already works: 97.5% of mined multi responses were 1 group.
- "p90 683s regression after Jul-12": NOT real — admin pairing artifact + Jul-12 chaos-day outliers (see MC-9).

## Scenario summaries (post-fix estimates if MC-1..MC-6 land)
- 2-panel harmonics compare (trace C, 142.1s): MC-2 (-95s) + MC-4 (-4.6s) + MC-6 (-1.5s) => ~40s.
- 3-asset 2-class cold compare (trace A shape, 617s user-visible): MC-1/5 (-350s) + MC-3 (-47s) + MC-2 where panel
  cards present => ~90-120s.
- Picker round trip: -6-9s on the re-POST (MC-7) + first-run probe warmth (MC-1).
- Repeat compare: ~20s (MC-10).
