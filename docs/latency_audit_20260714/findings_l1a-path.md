# Latency audit — Lens: Layer 1a + run-harness orchestration (2026-07-14)

Scope: run/harness.py, run/parallel (lib/parallel.py), layer1a/*, knowledge gate call site
(host/server.py + knowledge/ems.py), run/reconcile_granularity.py, run/degrade_gate.py, admin stage-span semantics.
All numbers measured live on this box today unless labeled "mined"/"admin".

=====================================================================
PART A — WHAT THE ADMIN "1a" SPAN ACTUALLY MEASURES (the headline question)
=====================================================================

## F0. Admin "1a" = max(1a_wall, 1b_wall), NOT 1a work. VERIFIED numerically.

Mechanism:
- admin/latency.py:23-35 — stage duration = ts(record) - ts(previous record) inside one execution slice
  ("Stage lines are END-markers").
- run/harness.py:241-244 — run_parallel({"layer1a","layer1b"}) JOINS both threads.
- run/harness.py:280-282 — stage(run_id,"1a",...) is stamped AFTER the join (and after the in-memory degrade
  gate at :267). The record before it is "PROMPT" (:234). So the "1a" gap = PROMPT -> join-of-both.
- run/harness.py:283-288 — the "1b" stage record follows "1a" immediately -> its "duration" is the logging gap.

Verified by recomputing the gaps from 634 raw outputs/logs/pipeline_r_*.jsonl files (same pairing rule):
  PROMPT->"1a" gap: n=2094  p50=9.6s  p90=123.9s  max=415.4s   <- exactly the admin numbers (p50 9.6/p90 120/max 415)
  "1a"->"1b" gap:   n=1856  p50=0.0s  p90=0.0s    max=0.5s     <- 1b's true cost is INVISIBLE in the admin table
True per-layer cost from obs_stage_events (cmd_catalog):
  page_selection    n=424  p50=468ms  p90=754ms   p99=2.6s  max=3.9s
  story_selection   n=424  p50=1540ms p90=2616ms  p99=4.7s  max=8.1s   -> REAL 1a p50 ~2.0s, p90 ~3.4s
  asset_resolution  n=377  p50=9129ms p90=179316ms p99=213s max=371.7s -> the "1a" p90/max is 1b's tail
Conclusion: the 120s p90 "1a" is 1b (has_data probes + resolve+basket). Fix the ADMIN grouping (derive 1a/1b from
obs spans, or stamp the stage lines inside the thunks) so optimization is steered at the right layer.
Also: knowledge-gate time is invisible for dashboard runs (no stage record; it runs BEFORE PROMPT is stamped), and
natural_compare's probe time is invisible too (before build_response t0) — see F2/F3. elapsed_ms UNDERSTATES
user-perceived latency by knowledge_gate + natural_compare + resolve_assets time.

=====================================================================
PART B — MEASURED ROOT CAUSE OF THE JOIN TAIL (cross-lens with 1b, measured here)
=====================================================================

## F1. ::timestamptz cast in the has_data value probe defeats the ts index — 70ms vs 0.042ms per table (1,667x)

Measured (neuract :5433, read-only EXPLAIN ANALYZE):
  SELECT to_jsonb(s) FROM gic_16_...ng s ORDER BY "timestamp_utc"::timestamptz DESC LIMIT 1
    -> Seq Scan (6,897 rows) + top-N heapsort, Execution 70.182ms
  same without the cast
    -> Index Scan Backward using idx_..._ts, Execution 0.042ms
Source: data/value_probe.py:73 — ORDER BY "{DATA_TS_COL}"{DATA_TS_CAST} DESC (DATA_TS_CAST='::timestamptz',
config/databases.py). ONE 40-table UNION chunk measured 14.5s; asset_candidates() COLD measured 182.9s for 328
registry rows (~8 chunks); WARM 11ms. This is exactly the asset_resolution p90 179s / "1a"-join p90 124s tail.
timestamp_utc is ISO text -> lexicographic order == chronological, so ORDER BY the RAW column (matching the existing
btree index) returns the same latest row; or add expression indexes ((timestamp_utc::timestamptz)) if writable.
Estimated saving: cold probe 183s -> ~2-5s (8 chunks x RTT+index scans). Kills ~120s off the p90 cold
single-asset dashboard join, ~170s off asset_resolution p99. THE single largest measured lever in this lens.
RTT context: SELECT 1 over :5433 = 16ms warm; information_schema read 19ms; single probe (cast, seq scan) 88ms.

## F2. TTL cache (120s) SHORTER than the cold fill (183s), no single-flight, no refresh-ahead

Evidence: lib/ttl_cache.py (_TTL_DEFAULT=120, knob cache.resolution_ttl_s=120 in DB); data/value_probe.py caches
(_CACHE/_VAL_CACHE/_EXIST_CACHE) and registry TTL caches. Any prompt arriving >120s after the last one pays a cold
(183s today; ~2-5s after F1) probe SERIALLY. No single-flight lock -> N concurrent cold requests stampede the tunnel
with N duplicate 183s probe chains. No background refresh -> interactive traffic (minutes apart) is ~always cold.
Proposal (flag-gated, honest-degradation preserved: serve-stale only within a bounded window, never-cache-empty rule
kept): (a) single-flight lock per cache key; (b) background refresher thread in the host that re-probes every
~0.8*TTL so the cache is warm-forever while the process lives; (c) raise TTL for the *value probe* specifically
(has_data flips rarely; the 120s TTL exists for flap self-heal, which the never-cache-empty rule already covers).
Estimated saving (before F1): up to 183s on any cold prompt; (after F1): ~2-5s p50 on cold prompts + stampede
elimination. Effort: small. Risk: low (staleness bounded by refresh interval).

=====================================================================
PART C — SERIAL HOST PREFIX BEFORE THE PIPELINE
=====================================================================

## F3. Knowledge gate is a serial prefix on every fresh prompt; no per-stage timeout row (worst case 120s)

Evidence: host/server.py:370-392 — _ems_ask() completes before build_response starts for every request without
asset_id/asset_ids. obs: knowledge_ems n=316 p50=166ms p90=271ms p99=1.6s max=3.4s (1,426 ptok avg / 18 ctok).
No llm.timeout.knowledge_ems row -> base llm.timeout=120s; a vLLM stall blocks EVERYTHING for up to 120s before the
fail-open returns kind=dashboard.
Proposal: (a) run the gate CONCURRENTLY with natural_compare + the pipeline start; check its verdict before the L2
fan-out (gate p99 1.6s finishes long before L2 starts at ~9s) — AI decision unchanged, just overlapped; discard the
pipeline lane on knowledge/off_scope (rare). (b) add app_config row llm.timeout.knowledge_ems=10 (p99 x6).
Saving: -0.17s p50 / -0.3s p90 on every fresh dashboard prompt; removes a 120s worst-case serial stall. Effort:
(b) config-only, (a) small.

## F4. natural_compare_ids runs asset_candidates() serially before the pipeline (host/server.py:399)

Evidence: host/multi_asset.py:46-50 — asset_candidates() (the 183s-cold / 11ms-warm probe of F1/F2) + named_full_rows
run to completion before build_response. On a cold cache the user waits the full probe BEFORE 1a even starts, and
this time is invisible to elapsed_ms (t0 starts inside build_response).
Proposal: overlap natural_compare with the knowledge gate (independent), and let 1a's route/stories (which never
touch the probe) start concurrently; single-flight (F2) makes 1b's own probe call coalesce with it instead of
re-firing. Saving: ~2s overlap (1a work) on cold prompts + removes double-probe risk; trivial after F1/F2. Effort: small.

=====================================================================
PART D — ORCHESTRATION OF MULTI-ASSET COMPARES
=====================================================================

## F5. run_pipeline_multi runs class lanes SEQUENTIALLY (run/harness.py:409-416)

Each lane = a FULL pipeline (1b resolve+basket LLM, validate, L2 fan-out of every card). Lane k only needs
shared_1a from lane 0 — lanes 1..N-1 are mutually independent.
Admin: RESPONSE_MULTI p50 142s p90 683s max 835s; slowest = 3-feeder compares 410-441s.
Proposal: run lane 0 to establish the template, then lanes 1..N-1 via run_parallel (deepcopy(shared_1a) per lane,
exactly what the code already injects); cap total vLLM pressure with the ALREADY-SHIPPED llm.global_concurrency
knob (llm/client.py:107-130, default 0=off).
Arithmetic: 3-class compare, per-lane wall ~140s: sequential 3x140=420s (matches observed 410-441s);
lane0 + max(lane1,lane2) ~ 140+140 = 280s -> -140s (-33%); with L2 contention conservatively -100s p90.
Effort: medium (lane fan-out + trace/context propagation already handled by lib/parallel contextvars copy).
Risk: medium (vLLM contention -> enable admission cap first).

## F6. Per-asset assemble_cards loop is also sequential (host/multi_asset.py:126-139)

For each group, for each asset: assemble_cards(lane_i, asset, date_window) — the executor fill per asset runs
one-after-another. obs executor span: p50 1.1s p90 7.7s per asset.
Arithmetic: 3-asset same-class compare = 3 sequential fills: p50 3x1.1=3.3s -> parallel = 1.1s (-2.2s);
p90 3x7.7=23s -> ~7.7s (-15s). DB-bound (neuract pool), not vLLM-bound, so parallelizing is safe with the pooled q().
Effort: small-medium. Risk: low-medium (pool sizing).

## F7. compare_mode LLM call on the multi serial tail (host/multi_asset.py:145-146)

p50 102ms (n=6), tiny — but it is one more serial LLM hop after ALL lanes complete. Could run concurrently with the
lane fan-out (it only needs the prompt). Saving ~0.1s. Effort: small. (Minor; listed for completeness.)

=====================================================================
PART E — 1a CRITICAL PATH ITSELF
=====================================================================

## F8. The 1a chain is 2 sequential LLM calls (route -> stories); merge or overlap saves ~0.5s

Evidence: layer1a/build.py:43-52 — route() then _assemble->build_stories(). obs: route p50 472ms (3,630 ptok / 32
ctok — prefill-bound), stories p50 1,536ms (342 ptok / 176 ctok — decode-bound at ~118 tok/s).
Route prompt measured live: system 6,994ch + user 7,997ch = ~3,747 tok, 18 pages. DB reads for the prompt are
cached after first call (page_specs 18ms cold / 0ms warm; card_titles, feasibility ~1ms). Block build 0.8ms.
Merging stories INTO the route call (one guided_json emission: page_key+metric+intent+window+stories for the chosen
page — the router already sees per-page card titles) eliminates one round trip + one prefill: saving ~0.4-0.5s p50.
BUT note: today 1a (2.0s) is hidden behind 1b (9.1s p50) at the join — this only pays off in scenarios where 1a is
the binding constraint: picker re-POST (1b pinned+fast), repeat prompts, post-F1/F2 world where 1b warm path shrinks.
AI-first: same decisions, same model, one call. Effort: medium. Risk: medium (route determinism is contract-pinned;
flag-gate per llm.guided_json pattern).

## F9. granularity_reconcile re-fires the stories LLM (~1.9s) on the critical path; fired in 43/634 runs (7%)

Evidence: run/reconcile_granularity.py:39 -> run_1a_to -> _assemble -> build_stories (fresh call_qwen stage="stories").
route_to is deterministic (no route LLM) — good. Counted 43 mirror swaps / 634 pipeline files.
Proposal options: (a) run the mirror stories call concurrently with _validate (harness.py:296-298 —
run_validate consumes 1a card ids/titles but not analytical_story — verify before shipping); (b) delay stories until
after the reconcile decision: stories start needs only page_key; 1b's resolve (asset+has_feeders) lands p50 ~0.6-2s,
so waiting for the resolve before writing stories picks the RIGHT page the first time (harness restructure: route ||
1b.resolve -> mirror-check -> stories || basket). Saving ~1.9s on 7% of runs (a), or the same with zero wasted-call
cost (b). Effort: (a) small (b) medium. Risk: low.

## F10. No per-stage timeout rows for route (base 120s); stories row = 120s; parse-retry can stack to ~240s/call

Evidence: app_config has llm.timeout.{asset_resolve=60, basket=120, l2_emit=150, stories=120} but NO llm.timeout.route
and NO llm.timeout.knowledge_ems -> both inherit llm.timeout=120. Observed maxima: route 3.9s, stories 8.1s — the
timeout is 30x the observed p99. llm.parse_retry=1 means a non-deterministic parse failure re-sends (timeout/truncated
are no-retry): worst case 2x120s per 1a call, 480s for the 1a lane. guided_json.route=on makes route parse failures
near-impossible, so the tail is all timeout-shaped.
Proposal (config-only): llm.timeout.route=30, llm.timeout.stories=30, llm.timeout.knowledge_ems=10.
Saving: none at p50; caps the 1a-lane worst case from ~480s to ~120s. Risk: low (fail-closed route raise already
surfaces the honest data_unavailable terminal; 30s = 7x observed p99).

## F11. vLLM prefix caching is fully DISABLED — hit rate 0.0% because queries_total == 0

Evidence: curl :8200/metrics — vllm:prefix_cache_queries_total = 0.0 (not just hits: QUERIES are zero; with APC
enabled this counter grows with every request). ExecStart has no --enable-prefix-caching and this build/config has
it off. So the brief's "0.0% ALWAYS" is answered: caching is OFF, not defeated-by-varying-prefix.
1a-lens impact if enabled: route re-prefills ~3.6K stable tokens every call (system.md + PAGES catalog change only
on DB edits; only the trailing "PROMPT: ..." differs) -> ~0.35s; knowledge 1.4K ~0.14s; stories system+card-listing
stable per page. Combined ~0.4-0.5s of the serial 1a path, and the far bigger l2_emit win (22.3K ptok/card avg,
n=1,289 — 8 cards x ~2.1s prefill each — belongs to the L2 lens).
Also observed: /v1/models reports max_model_len=65536 while the systemd unit says --max-model-len 32768 — the
running server was launched with different flags than the current unit file (config drift; a restart would change
behavior, including the client's 45K prompt budget assumption).
Proposal: add --enable-prefix-caching (flag-gated deploy + full determinism cert: pinned-seed outputs must be
re-certified since KV reuse can change FP reduction order on near-ties; the byte-identical single-asset contract
must gate this). Effort: config + cert sweep. Risk: medium (contract).

=====================================================================
PART F — REPEAT / RE-POST SCENARIOS
=====================================================================

## F12. Picker re-POST re-runs the full 1a (route+stories, ~2.0s) for a deterministic identical result

Evidence: handle_run with pinned asset_id skips the knowledge gate + natural compare (host/server.py:370) but
run_pipeline re-fires run_1a on the SAME prompt; temp=0 + pinned seed (llm.seed=42) makes the result deterministic;
run_id is sha1(prompt) so the first run's 1a is addressable. The injection mechanism ALREADY EXISTS
(run_pipeline(layer1a=...) — the multi-asset shared-template lane, harness.py:240-244), but it also locks re-routes
(_shared_template) which a re-POST must NOT (reconcile now matters: the asset is known).
Proposal: short-TTL in-process cache {run_id -> layer1a} at the harness; on re-POST inject it via a new
"cached, not locked" flag that keeps reconcile/preflight/reflect active. Saving: ~2.0s p50 of the join when 1b is
fast (pinned resolve skips the AI resolve; basket still runs — 1b lens owns caching that 6.4s). Effort: small-medium.
Risk: low-medium (staleness across catalog edits; TTL + catalog-version key).

## F13. Repeat prompts (same text) re-pay the whole 1a+gate chain despite full determinism

Same mechanism as F12 for the fresh-prompt path: knowledge gate (166ms) + route (472ms) + stories (1,536ms) are all
deterministic for identical input. A TTL response-cache keyed by (prompt, catalog rev) for the 1a/gate layer is the
cache-an-AI-decision pattern the constraints explicitly allow. Saving ~2.2s p50 on repeat prompts. Effort: small.

=====================================================================
PART G — REFLECT LOOP / DEGRADE GATE (checked, mostly healthy)
=====================================================================

## F14. Reflect full-page re-route doubles L2 cost when it fires — but it is rare and policy-gated (measured 6/634)

Evidence: run/harness.py:173-190 — a re-route re-runs 1a + validate + the FULL L2 fan-out for the new page
(_MAX_ATTEMPTS=2). Default policy reroute_on=hard_failure + min_gap_frac=0.34 keeps it rare: 6 reroute_from
records / 634 files; preflight_reroute fired 0 times (policy skips it). Cost when fired ~= +1 full L2 pass
(5-8 cards / 4-way concurrency x 19.8s p50 = ~30-40s) + ~2s 1a. No change proposed (honest-terminal policy is
correct and the trigger is already load-shaped by llm.global_concurrency being available); listed to close the
brief's question (e). NOTE: timeout-kind hard fails under vLLM contention cluster -> reroutes double the load;
enabling llm.global_concurrency (config-only, default 0) is the countermeasure that protects this path.

## F15. degrade_gate / stage logging / parallel primitive: no material cost (dead ends, verified)

- run/degrade_gate.py — in-memory string fingerprint match; no I/O on healthy path. ~0ms.
- lib/parallel.py — real ThreadPoolExecutor, contextvars copied per thunk; true concurrency for 1a||1b (network/LLM
  I/O releases the GIL). No sequential fallback. New pool per call = negligible.
- obs/stage.py stage() — stderr print + one append + bus.emit; sink_pg is a buffered daemon (obs/sink_pg.py:
  put_nowait, batch flush every obs.flush_interval_s=2) — does NOT block the pipeline. jsonl/console sinks are
  synchronous but micro (µs-ms each).
- host _dump_response — synchronous json.dump before returning; largest observed response 490KB -> ~10-30ms. Minor;
  could move after the socket write, not top-15.
- llm/providers/openai_compat.py — urllib per-call connection (no keep-alive) to localhost:8200: ~1ms. Not material.
- admin "notes" stage avg 87ms MAX 28.6s — the gap between the last L2/reflect record and the notes record contains
  validate.build.payload_final (harness.py:366-373), not the notes write. Attribute to the validate lens.
- 1a prompt DB reads (page_specs/card_titles/page_feasibility) are warm-cached (18ms cold, ~0 warm) — not a lever.
- /api/frame date re-fetches never touch 1a (separate handle_frame path reading the REFETCH bundle) — no 1a cost.

=====================================================================
SUMMARY RANKING (this lens)
=====================================================================
1. F1  ts-cast probe fix                 ~-120s p90 cold dashboards (cross-lens 1b/data, measured here)
2. F2  TTL refresh-ahead + single-flight ~-180s worst cold today; keeps warm-always after F1
3. F5  parallel multi lanes              ~-100..140s p90 3-class compares
4. F6  parallel per-asset assembles      ~-2..15s multi compares
5. F11 enable vLLM prefix caching        ~-0.5s 1a serial path (l2_emit win owned by L2 lens)
6. F12/F13 deterministic 1a cache        ~-2s picker re-POST / repeat prompts
7. F3/F4 gate+natural-compare overlap    ~-0.2..0.3s p50 every fresh prompt; kills 120s worst stall
8. F9  reconcile stories overlap         ~-1.9s on 7% of runs
9. F10 timeout rows (config)             tail cap 480s->120s
10. F0 admin span fix                    measurement steering (no direct ms, prevents mis-aimed optimization)
