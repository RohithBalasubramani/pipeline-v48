# Latency audit — LENS: host orchestration + serve path (2026-07-14)

Files: host/server.py, host/exec_cards.py, host/enrich.py, host/assemble.py, host/multi_asset.py,
host/asset_lanes.py, host/compare_mode.py, host/notes.py, host/payload_store.py, run/harness.py, validate/*.
READ-ONLY audit; measurements from outputs/logs traces + micro-benchmarks. Nothing edited, no services touched.

═══════════════════════════════════════════════════════════════════════════════════════
## A. The measured do_POST timeline (real runs)

### Run 1 — single-asset panel page (trace t_2aed84a50d9b43a8b8ca1434dfbde5e3, run r_48c83f28a2)
Prompt: 'compare voltage and current for pcc 1 and 2' (fresh, no asset_id). TOTAL USER WAIT ~296s.
```
t=0.00         request_received
t=0.00-0.34    knowledge_gate LLM (336ms)                                  [SERIAL]
t=0.34-184.62  natural_compare_ids -> asset_candidates() has_data probe    [SERIAL, 184.3s]
               8 sequential UNION-ALL value_counts chunks over :5433:
               14.4 + 19.7 + 23.8 + 26.6 + 26.8 + 27.6 + 19.3 + 26.1 s
t=184.6-195.0  1a (route 539ms + page_selection 544ms + stories 1.6s) || 1b (10.4s, cache now warm)
t=195.0-196.3  granularity_reconcile re-route (story_selection 1.26s)
t=196.3-196.6  validate 272ms
t=196.6-290.4  layer2_card_ai fan-out, 5 cards, wall = MAX card = 93.8s
               (cards: 14.2 / 21.8 / 13.4 / 36.6 / 93.8 s; emit_concurrency=4 queued card 22)
t=290.4-296.1  executor fan-out 5.7s (cards 0.9-5.7s, parallel; started ONLY after ALL emits)
t=296.1        renderer 4ms; notes 12ms; response span 0ms
```
response.elapsed_ms = 111,452 (build_response t0) — the user actually waited ~296s.

### Run 2 — 2-asset same-class compare (trace t_1dd3c2b76e2844c8a2ebfe8c33fccf30, run r_f3af900d1d)
```
t=0.00-0.16    knowledge_gate 163ms
t=0.16-173.9   natural_compare_ids: registry probe AGAIN ~173.8s, then 2 concurrent asset_resolve LLMs (433/312ms)
t=174.4-194.7  ONE lane: 1a (0.5+2.1s) || 1b 20.4s (its 'basket' LLM call alone = 20.3s)
t=195.0-223.8  L2 emit x4 cards, wall 28.8s
t=223.8-228.4  executor fan-out ASSET 1 (4.6s)          [SERIAL per asset]
t=228.4-229.6  executor fan-out ASSET 2 (1.2s, warm)    [SERIAL per asset]
t=229.7        response.  RESPONSE_MULTI elapsed_ms=55,277; true wall 229.7s.
```

### Run 3 — fresh prompt that ended at the ASSET PICKER (trace t_76d2cff59be04c6fa683316da46fd7a2)
wall 187.8s, of which 186.1s = the same registry probe. The user waited >3 minutes JUST TO SEE THE PICKER.

Probe recurrence over the last 60 traces: 4 traces paid 186-188s each; 3 paid 2-3s; 53 paid ~0 (warm).
Total probe seconds in last 60 traces: 758s.

═══════════════════════════════════════════════════════════════════════════════════════
## B. Dependency graph (single-asset /api/run) — false dependencies marked

```
do_POST -> handle_run
  1. knowledge gate LLM 0.3-0.7s        # FALSE serial dep for dashboard prompts (can overlap 2+3)
  2. natural_compare_ids                # needs only prompt + registry NAMES (5ms read);
                                        #   today transitively runs the FULL has_data probe (minutes cold)
  3. run_pipeline
     3a. 1a || 1b (run_parallel)        # OK
     3b. reconcile_granularity          # serial 1a re-run when granularity contradicts (1.3-2s when it fires)
     3c. validate data probe (:5433)    # TRUE dep for L2 gates (fold_into_basket); tail = un-indexed ts cast sort
     3d. preflight_reroute              # policy-skipped by default (reroute_on=hard_failure)
     3e. L2 emit fan-out — BARRIER      # executor per card needs only THAT card settled: FALSE all-cards dep
     3f. payload_final re-validate      # telemetry-only ("annotate-only — never a gate"), on critical path
     3g. record_notes, _replay_pipeline_out
  4. assemble_cards: executor fan-out (parallel, 45s budget) + enrich (4ms measured)
  5. _attach_l2_notes; RESPONSE stage
  6. _stamp_trace_id; _dump_response (sync disk write, 490KB)
  7. replay capture write_bundle (sync; bundle median ~0.7MB, max 4.5MB events.jsonl)
  8. obs middleware response span + end_trace (pg sink buffered — OK)
  9. _send: json.dumps AGAIN (2.8ms) + socket write. No gzip.
```

MULTI path adds: natural_compare probe -> run_pipeline_multi (class lanes SERIAL) ->
per-asset assemble_cards SERIAL -> compare_mode LLM (prompt-only input) SERIAL AT THE END -> merge.

═══════════════════════════════════════════════════════════════════════════════════════
## C. FINDINGS (ranked by estimated saving)

### HOST-1 (CRITICAL) — the registry has_data probe rides the serve path; measured 184-188s, recurs every TTL expiry
- Evidence: host/server.py:399 natural_compare_ids(prompt) on EVERY fresh prompt -> host/multi_asset.py:49
  asset_candidates() -> layer1b/resolve/asset_candidates.py:155 tables_with_values(all ~300 registry tables)
  -> data/value_probe.py value_counts(): 8-9 sequential 40-table UNION-ALL chunks, each
  'SELECT to_jsonb(latest row ORDER BY "<ts>"::timestamptz DESC LIMIT 1)' = un-indexed full sort per table
  over the :5433 VPN tunnel, 14-28s per chunk.
- TTL: lib/ttl_cache.py _TTL_DEFAULT=120 (knob cache.resolution_ttl_s). 120s TTL < 185s probe cost ⇒ any
  prompt arriving >2min after the last probe pays the full price. Also fires on GET /api/assets (picker
  browse), host/asset_lanes.resolve_assets (multi picker re-POST), 1b resolve, class_from_subject,
  empty_fallback.
- Measured: 184.3s / 173.8s / 186.1s / 187.6s in 4 of the last 60 traces (758 total probe-seconds).
  One of them (t_76d2cff5) was a run whose ENTIRE 187.8s wall was probe -> asset picker.
- Proposals (all flag-gated):
  a. Names-only compare detection: named_full_rows needs registry NAMES (measured 5ms cmd_catalog read).
     Only await has_data when >=2 full names matched. Removes the probe from the fresh-prompt pre-flight.
  b. Background stale-while-revalidate: a host-owned refresher thread (start in host/server.py main(), like
     obs.retention.ensure_started) re-probes every ~60-90s and swaps the cache; requests always read the
     last-good snapshot (staleness bound = refresh cadence, same as today's TTL freshness). Removes the probe
     from ALL request paths including 1b and the picker.
  c. (cross-lens 1b/DB) parallelize the 8 chunks (8x ~23s -> ~25s total), and/or an expression index /
     registry latest-row cache table on the DB side.
- Est saving: -180s worst-case per affected request; at the observed 4/60 incidence this is the single
  biggest wall-clock item in the fleet. Confidence 0.9.

### HOST-2 (HIGH) — multi-asset compare: class lanes run SERIALLY; per-asset executor fills run SERIALLY; compare_mode LLM trails
- Evidence: run/harness.py:410 'for cls, members in by_class.items(): lane = run_pipeline(...)' — each lane
  = full 1b + validate + L2 emit (only 1a is shared after lane 1). host/multi_asset.py:127 nested
  'for group / for asset: assemble_cards(...)' — measured Run 2: asset-1 fill 4.6s then asset-2 fill 1.2s
  strictly serial. host/multi_asset.py:146 compare_mode(prompt) — an LLM call whose ONLY input is the prompt,
  executed after all lanes complete.
- Baseline: RESPONSE_MULTI p50 142s / p90 683s / max 835s; slowest = 3-feeder compares 410-441s.
- Proposals:
  a. Run lane 1 alone (it authors the shared 1a); run lanes 2..N in parallel (each already gets
     copy.deepcopy(shared_1a); lanes are run_pipeline calls with parameter asset_id — no env pinning
     (layer1b/build.py:31 env fallback is opt-in), no shared mutable state; the host already runs concurrent
     requests through the same code via ThreadingHTTPServer).
  b. Parallelize per-asset assemble_cards with a small pool (independent neuract tables; executor fan-out
     is already thread-safe).
  c. Fire compare_mode(prompt) as a future at build_response_multi entry; join before merge_all.
- Est arithmetic: 3-class compare: 3 serial lanes (each ~30-90s of 1b+L2) -> 1 + max(2 parallel)
  = save ~1 lane wall = -30-90s (p90 compares: -60-180s). Same-class N-asset: save (N-1) x per-asset fill
  (measured 1.2-4.6s; panel classes 10-30s). compare_mode: -0.3-1s. Confidence 0.8 (a/b), 0.9 (c).
- Risk note (a): N parallel lanes multiply concurrent L2 emits (N x emit_concurrency=4 on vLLM) — cap total
  via a shared semaphore so per-emit decode throughput holds (same contention logic as layer2.emit_concurrency).

### HOST-3 (HIGH) — L2 emit -> executor is an all-cards BARRIER; per-card pipelining hides the executor wall
- Evidence: run/harness.py:118 run_2_all returns only when every card's emit finishes (lib/parallel.py joins
  all futures); host/server.py:93-94 assemble_cards then starts the fill fan-out. Measured Run 1: 4 of 5
  emits done by t=+36.6s; the fifth took 93.8s; ALL executor fills (0.9-5.7s each) waited for t=+93.8s.
- Mechanism: fill_one_card(cid) needs only that card's emit + settled swap. grounding.swap_settle only
  REVERTS colliding swaps; a swap_decision.action=='keep' card (5/5 in Run 1; the large majority fleet-wide)
  can never be changed by settle (reverts only touch cards that SWAPPED to a duplicate target).
- Proposal (flag-gated; single-asset serve contract preserved by identical final assembly): stream each
  keep-card into the executor as its emit completes; swapped cards wait for the settle pass; reflect-loop
  re-route (rare, hard-fail-only by default) discards in-flight fills for the dropped page.
- Est saving: min(executor wall, emit tail spread) = -5.7s on Run 1; -4.6s on Run 2; on panel pages where
  panel_aggregate fills run 10-30s (exec p90 3.4s but max 218s), -10-30s. Confidence 0.7.

### HOST-4 (MEDIUM-HIGH) — repeat prompts + picker re-POSTs re-pay the FULL L2 emit (p50 31.7s) though the recipe is provably reusable
- Evidence: no serve-path reuse anywhere: handle_run -> run_pipeline always re-runs 1a route + L2 emit;
  run_id = make_run_id(prompt) is deterministic yet nothing keys results off it. The multi-asset path
  PROVES recipes are portable: host/multi_asset.py:130 reuses ONE class recipe across sibling assets via
  rebind_consumer (binds by column NAME). The picker round trip is the worst case: leg 1 (fresh prompt)
  runs 1a+1b+validate (L2 gated on asset_pending), the user picks, leg 2 re-runs 1a (route 0.5s +
  stories 1.6-2.1s + page_selection 0.5s ~ 3s) + 1b + validate + FULL L2 emit — nothing from leg 1 is kept.
- Proposal (flag-gated, cache-not-replace: the cached artifact IS the AI's own decision):
  a. Short-TTL (minutes) memo of the leg-1 {layer1a, validation} keyed by prompt-hash; the pinned re-POST
     injects it exactly as run_pipeline_multi already injects layer1a= (run/harness.py:242 shared-template
     lane — the mechanism exists and is tested).
  b. Optional deeper reuse: recipe cache keyed (prompt-hash, page_key, asset_class) -> layer2 dict; a hit
     rebinds via rebind_consumer and goes straight to the executor (fresh data ALWAYS re-read; per-leaf
     honesty unchanged).
- Est arithmetic: picker leg 2 = -3-5s (1a reuse) or -(3 + 31.7)s ~ -35s (recipe reuse, L2 wall p50 31.7s);
  repeat prompt = -35s p50. Confidence 0.7 (a), 0.55 (b — product call: is a repeat prompt allowed to reuse
  the emit? AI-first constraint permits caching AI decisions).

### HOST-5 (MEDIUM) — knowledge gate LLM is a serial prefix on every fresh prompt
- Evidence: host/server.py:382-401 _ems_ask(prompt, history) completes before natural-compare + run_pipeline
  start. Measured 336ms / 163ms (baseline avg ~0.7s; vLLM-contended worse). Dashboard prompts (the majority)
  pay it as pure additive latency.
- Proposal: submit knowledge_gate + natural-compare detection + (speculatively) run_pipeline's 1a||1b at the
  same time; if the gate returns knowledge/off_scope, abandon the pipeline future (wasted work only on the
  rare knowledge prompt). The AI decision itself is unchanged.
- Est saving: -0.3-0.7s p50 on every fresh prompt (more under vLLM contention). Confidence 0.85.

### HOST-6 (MEDIUM) — telemetry work on the critical path after L2: payload_final re-validate + notes
- Evidence: run/harness.py:366-373 payload_final (validate_payloads + card_payloads_for DB reads per card)
  runs between L2 completion and the executor, and is documented 'annotate-only — never a gate'
  (validate/build.py:128-131). Admin pairs its cost into the 'notes' stage gap: avg 87ms, MAX 28.6s
  (admin/latency.py measures ts-gaps; the notes record directly follows layer2+payload_final).
  record_notes + _replay_pipeline_out also sit inline (small writes).
- Proposal: run payload_final on a background thread and attach to the response dict only if done (or attach
  to obs only); notes file write fire-and-forget. Response contract keeps validation.payload_summary from
  PASS-1 (unchanged); payload_final today only feeds out['validation']['payload_final'] telemetry.
- Est saving: -0.1s p50, -up-to-28s tail on affected runs. Confidence 0.7.

### HOST-7 (MEDIUM) — validate's pandas probe: un-indexed ORDER BY ts::timestamptz DESC LIMIT 500 over the tunnel
- Evidence: validate/data_load.py:40 — PROBE_ROWS=500 (config/validation.py:17), ORDER BY the TEXT ts cast
  to timestamptz = full sort per probe on ~100k-900k-row gic_* tables over :5433. Baseline: validate p50
  312ms, max 119s. It IS a true pre-L2 dependency (fold_into_basket feeds L2 gates), so it cannot be
  removed — only made cheaper/earlier.
- Proposals: (host-side) TTL-cache the (table, column-set) probe result for cache.resolution_ttl_s —
  identical staleness contract to has_data; kick the probe off INSIDE the 1b lane as soon as the basket is
  built (overlaps the granularity-reconcile + any 1a tail). (DB lens) bound the scan with a recent-window
  WHERE, or add the expression index.
- Est saving: -0.3s p50 when cached; kills the 119s tail. Confidence 0.6.

### HOST-8 (SMALL) — response-tail synchronous persistence before the body is sent
- Evidence: handle_run: _dump_response (host/server.py:409, sync json.dump 490KB ~3ms + write) and the
  replay capture write_bundle (replay/capture.py:81 -> replay/store.py:33 — bundle median ~0.7MB, max 4.5MB
  events.jsonl, written file-by-file) both complete BEFORE do_POST._send serializes the response AGAIN
  (json.dumps 2.8ms measured on the 490KB response) and writes the socket.
- Proposal: serialize once (reuse bytes for both the dump and the wire); move _dump_response + write_bundle
  to a fire-and-forget thread AFTER the socket write (both are already fail-open by design).
- Est arithmetic: 3ms (dump) + ~10-50ms (bundle IO) + 2.8ms (double dumps) ~ -15-55ms every /api/run AND
  /api/frame. Confidence 0.85.

### HOST-9 (SMALL) — no gzip on a ~0.5MB response
- Evidence: Handler._send writes identity encoding; measured 490KB -> 61KB at gzip-6 in 4.7ms.
- On LAN (~1Gbps) transfer is ~4ms — irrelevant. If the FE is reached over the FortiClient VPN / WAN
  (50Mbps), 490KB = ~78ms -> 10ms. Content-Encoding negotiation, config-effort.
- Est saving: -60-70ms per response on VPN links only. Confidence 0.6.

### HOST-10 (MEASUREMENT) — elapsed_ms + admin stage numbers hide/mislabel where the time goes
- Evidence: response.elapsed_ms starts at build_response t0 (host/server.py:62) — Run 1 reported 111s of a
  296s wait; RESPONSE_MULTI reported 55s of a 230s wait. Admin's '1a' stage (avg 26.9s p50 9.6s p90 120s)
  is really the 1a||1b JOIN gap from the PROMPT record (admin/latency.py ts-pairing; 1b's probes dominate),
  answering the brief's VERIFY: it includes 1b + any pre-1a stall, NOT just routing. 'notes' includes
  payload_final (HOST-6). 'validate' includes granularity_reconcile's 1a re-run.
- Proposal: stamp t_request at do_POST entry into handle_run; add stage records for knowledge_gate +
  natural_compare with their own ts; elapsed_ms from t_request. Zero-cost, makes every future latency
  number honest. Confidence 0.95.

### HOST-11 (answers to brief questions / verified non-issues)
- (b) :8770 = ThreadingHTTPServer (host/server.py:417-434), request_queue_size=128, daemon threads.
  A second user never queues on accept; concurrent prompts contend on vLLM + :5433 instead. A host-level
  global L2-emit admission semaphore (across requests) would keep per-run latency predictable under 2+
  concurrent prompts (today: 2 runs x emit_concurrency 4 = 8 concurrent 22K-tok emits split decode).
- (c) notes stage: obs/notes.py record() is a tiny file write (12ms measured); the 28.6s MAX is the
  admin ts-gap artifact = payload_final + inline telemetry (HOST-6), not the notes write itself.
- (e) insight narrator (~1.3s) runs INSIDE the executor fan-out per narrative card
  (ems_exec/renderers/narrative_ai.py:167 -> _insight.summary_sync), parallel with other card fills and
  content-hash cached — NOT a serial host cost. No action.
- (f) response size: 478KB for a 24-card multi (payload 142KB, data_instructions 130KB, render 123KB —
  the per-leaf gap records, refetch 42KB). json.dumps 2.8ms. Serialization/transfer is NOT material on LAN.
  Trimming data_instructions/render.gaps from the wire (FE uses only slices) would halve it — bytes, not ms.
- (g) sync IO per run measured: pipeline_<rid>.jsonl ~20-40 appends; trace jsonl ~700 events single-run
  (open/append/close per event under a global lock — measured 0.005ms/append => ~7-10ms/run); ai_<rid>.jsonl
  ~0.6MB/run appended per LLM call (~0.2ms each); obs pg sink is buffered+background (correct). DEAD END:
  obs sink overhead is ~10-20ms/run total — not material, do not spend effort here.
- exec budget pattern (host/exec_cards.py:242-284) as_completed(timeout)+shutdown(wait=False,
  cancel_futures=True) + done-future harvest — correct, no straggler join.
- _special_handling_map is called twice per assemble (exec_cards.py:189 and assemble.py:53) — 1 redundant
  cmd_catalog batch read (~5ms). Micro; fold into one call if touching the file anyway.
- enrich/renderer measured 4ms for 5 cards healthy; _asset_has_logged_data probes only fire per zero-real
  card (cached per column) — bounded.
- payload_store skeleton/raw-default caches are unbounded plain dicts but keyed by card_id (~116 cards) — fine.

═══════════════════════════════════════════════════════════════════════════════════════
## D. Scenario summaries (what the ranked fixes buy)

- Cold single-asset dashboard (fresh prompt, TTL-expired): 296s -> ~100s (HOST-1: -185s; HOST-5: -0.5s;
  HOST-3: -5s) — remaining wall = L2 emit (other lens).
- Warm 5-card panel page: ~40s -> ~33s (HOST-3 -5s, HOST-5 -0.5s, HOST-6/8 -0.2s).
- 3-feeder compare (multi): 410-441s -> roughly halves with HOST-1 + HOST-2 (lanes parallel, fills parallel,
  compare_mode overlapped).
- Picker round trip: leg 1 187.8s -> ~2s (HOST-1); leg 2 -3-35s (HOST-4).
- /api/frame date re-fetch: -15-55ms each (HOST-8) + the executor read itself (other lens).
- Repeat prompt: -35s p50 with HOST-4b recipe reuse.

## E. Dead ends checked (do not re-investigate)
- jsonl/console obs sinks: measured 0.005ms/append, ~10-20ms/run total. Not material.
- Response serialization/transfer on LAN: 2.8ms dumps / ~4ms wire. Not material (except VPN links, HOST-9).
- stderr stage prints: ~1us each. Not material.
- ThreadingHTTPServer accept path: not a bottleneck (backlog 128).
- pg obs sink: already buffered background with backoff. Correct.
