# Latency audit — LENS: caching & reuse (2026-07-14)

READ-ONLY audit of deterministic-given-inputs recomputation on the hot path.
Baselines cited: mined e2e p50 37.8s / p95 172s; layer2 wall p50 31.7s; l2_emit p50 19.8s/card.
Fresh obs ground truth pulled this session (cmd_catalog obs_*):
- obs_llm_calls per stage: l2_emit n=1289 p50 21,735 ptok / 1,291 ctok / 18.3s p50 / 40.1s p95;
  basket p50 6.38s (862 ctok); stories 1.54s; route 0.47s; asset_resolve 0.58s; knowledge_ems 0.17s.
- obs_stage_events: layer2_card_ai p50 28.9s p90 49.7s; layer2_card_ai.card p50 19.2s;
  asset_resolution p50 9.1s p90 179.3s (LLM only 0.58s of it!); executor p50 1.1s p90 7.7s;
  page_selection 0.47s; story_selection 1.54s; validation 0.27s.
- obs_traces: run p50 81.7s p90 347s (this window incl. compares); frame p50 1.68s p90 7.9s.
- admin /admin/api/runs (653 runs): repeat-prompt fraction 26.8% (478 distinct of 653);
  prompt_tokens p50 73,891 / p90 485,362 per run; elapsed p50 27.5s p90 124.8s.

────────────────────────────────────────────────────────────────────────────────────────────
## F1 (CONFIRMED ROOT CAUSE) vLLM prefix caching is HARD-DISABLED at the engine
- Evidence: `curl :8200/metrics` → vllm:cache_config_info{enable_prefix_caching="False",
  mamba_block_size="65536", mamba_cache_mode="none", block_size="1056", num_gpu_blocks="912"};
  vllm:prefix_cache_queries_total = 0.0 — the cache is never even QUERIED. Journal hit rate 0.0% always.
- Root cause: Qwen3.6-35B-A3B is a HYBRID mamba/linear-attention model; vLLM auto-disables APC for
  hybrid models unless explicitly opted in. NOT a prompt bug — layer2/emit/emit.py deliberately keeps
  per-card variance (recovery library, roster, morph envelope) at the prompt TAIL for prefix stability.
- Shared-prefix inventory (this lens's contribution):
  · L2 system prompt composed = 65,611 chars ≈ 16.4K tok (full library) / 46,792 chars ≈ 11.7K tok
    (basket-filtered); measured common prefix full-vs-filtered = 41,955 chars ≈ 10.5K tok.
    Same-page same-class cards get a BYTE-IDENTICAL system prompt → whole ~11.7-16.4K tok shared.
  · Decode/prefill split at p50: 1,291 ctok @ ~100 tok/s ≈ 12.9s decode; remainder ≈ 5.4s for 21.7K
    ptok ≈ 4K tok/s effective prefill under concurrency-4.
  · Route user msg = "PAGES:<static catalog>…PROMPT:<tail>" (cache-aligned); asset_resolve
    CANDIDATES-first (aligned); stories puts PROMPT FIRST then static card list (ANTI-aligned — reorder
    when APC lands; small, 324 ptok).
- Proposal (mechanics = vllm lens): enable APC for the hybrid model (newer vLLM supports it explicitly)
  — the pipeline needs ZERO prompt changes to benefit.
- Estimate: per card 2..N, ~11.7K cached prefix / ~4K tok/s effective ≈ ~2.9s prefill saved per card;
  5-card page, fan-out 4 → ≈ 3-6s p50 page saving; larger under multi-run contention (chunked prefill
  steals decode throughput). Also cuts route/basket/asset_resolve prefill on every run.
- CONFIG DRIFT (ops): /proc/1532/cmdline = --gpu-memory-utilization 0.60 --max-model-len 65536
  --tool-call-parser qwen3_xml --reasoning-parser qwen3, but systemd unit on disk = 0.55 / 32768 /
  hermes. Next restart silently halves the context window (llm.prompt_budget_tok=45000 assumes 64K!).

## F2 (BIGGEST) value-probe / has_data cache is 120s-TTL and cold on the request path — observed 184s pre-1a stall
- Evidence (recent kind='run' ok trace, obs_db_queries): knowledge_gate ends 0.3s → then EIGHT sequential
  jsonb value probes on :5433 (14.4s, 19.7s, 23.8s, 26.6s, 26.8s, 27.6s, 19.3s, 26.1s) from 0.4s to
  184.3s — 1a's page_selection only STARTS at 184.6s. e2e 296s, of which 184s was probe warm-up.
  This is host/multi_asset.natural_compare_ids → layer1b.resolve.asset_candidates() →
  tables_with_values(ALL registry tables) (asset_candidates.py:154) firing on EVERY fresh prompt.
- Probe cache = data/value_probe.py TTLCache, knob cache.resolution_ttl_s=120 (app_config row verified).
  Probes take 14-27s PER CHUNK × ~8 chunks — the TTL is of the same order as the probe itself; any
  prompt >2min after the last one pays again. Mined 1b "LIVE median 22s / p95 200s" is exactly this.
- Proposal: a background warm-keeper in the host process (daemon thread or systemd timer hitting an
  internal warm endpoint) that re-runs existing_tables + tables_with_values(all registry) +
  value_counts every ~0.8×TTL, with TTL raised (e.g. 900s) — the flap-safe never-cache-empty +
  TTL self-heal semantics already exist, so a stale-poison regression is designed out. User requests
  then ALWAYS hit a warm cache. (Parallelizing the 8 chunks is the DB lens's sibling fix.)
- Estimate: live 1b median 22s → ~2s (resolve LLM 0.58s + registry reads);  since 1a∥1b join at
  max(1a≈2.5s, 1b), cold single-asset dashboard saves ≈ 19-20s median and up to ~180s at the observed
  worst; p95 e2e (172s mined) largely collapses to the layer2 wall.

## F3 run-level authoring cache for REPEAT prompts (26.8% of runs)
- Evidence: admin runs 653 → 478 distinct normalized prompts (26.8% repeats; top repeat 36×
  "compare voltage and current for pcc 1a and 1b"). obs_llm_calls exact-duplicate (md5(system||user))
  rates: basket 40.6%, route 39.7%, stories 38.1%, knowledge_ems 29.7%, asset_resolve 24.3% — the
  upstream stages ALREADY receive byte-identical inputs on repeats (temp=0 + pinned seed llm.seed=42
  = deterministic by design; llm/client.py docstring).
- make_run_id(prompt) is already a deterministic prompt hash (run/run_id.py) — a natural cache key.
- Proposal: (normalized_prompt, asset_id?, date-preset, catalog_rev, schema_fingerprint) →
  {layer1a, 1b resolution, layer2 recipes} TTL cache (e.g. 1-6h) with a version key
  (max(updated_at) over page_specs/card_handling/card_payloads + prompt-file hash). On hit: skip
  route+stories+knowledge+resolve LLM+basket+the WHOLE L2 fan-out; the executor fill + validation
  verdicts still run LIVE per request (per-leaf honesty untouched — verdicts are recomputed at fill).
  AI-first compliant: it replays the AI's own emissions for inputs the deterministic model would map
  to the same output anyway. Flag-gate (cache.authoring_ttl_s=0 default-off) for the byte-identity suite.
- Estimate: on a hit, e2e p50 37.8s → executor+enrich+probes ≈ 5-8s ⇒ ≈ -30s on 26.8% of traffic
  (expected-value ≈ -8s across all runs). Multi-asset repeats (RESPONSE_MULTI p50 142s) save
  proportionally more (each class lane's L2 wall).

## F4 exact-match LLM response cache (stage-agnostic, tiered under F3)
- Key = md5(system + user + model + params) → parsed response; TTL + never-cache-error/marker.
  Correct by construction for temp-0 pinned-seed calls. Measured duplicate-call latency pools in the
  obs window: basket ≈1,156s, stories ≈348s, asset_resolve ≈141s, route ≈103s, knowledge ≈32s.
- l2_emit hits 0% today because the user message embeds (a) "RUN: r_…" as line 1, (b) DATA WINDOW
  first/last at full ts resolution + "(last sample is Nd old)", (c) member last= ts facts. After
  normalizing those in an offline experiment, same-(prompt,card) duplicates rise only to 5.1% across
  the whole window — the window ALSO spans daily prompt-template edits, so in-production short-window
  hit rates will sit between 5% and the 26.8% prompt-repeat rate. To make l2_emit cacheable: drop the
  RUN line from prompt bytes (it is telemetry; ai_log already carries the id) and bucket the DATA
  WINDOW facts to the hour. Both are prompt changes → flag-gate + re-cert.
- Estimate: repeat-prompt runs save 0.47+1.54+0.58+6.38 ≈ 9s of pre-L2 LLM time even without F3;
  with l2_emit normalization a same-hour repeat saves the full per-card 18.3s.

## F5 within-request duplicate executor SQL — 94,298 redundant identical statements
- Evidence (obs_db_queries, md5(sql_text) per trace): executor.card stage: 71,258 neuract calls,
  58,380 are exact duplicates of an earlier call in the SAME trace; redundant latency ≈ 16.6s
  summed per trace (241 traces). Top shapes: per-field window-anchor probes
  (SELECT "active_energy_import_kwh" … ts <= $1 LIMIT 1 — 2,233 calls each side) and wide
  latest-row reads (76.7ms avg × 5,476).
- Proposal: request-scoped memo (contextvar dict keyed (db, sql) installed by the obs middleware /
  trace boundary) inside ems_exec data readers — same request, same statement ⇒ same rows; zero
  staleness semantics change. Optional: a 30-60s cross-request TTLCache for /api/frame BURSTS
  (cross-card date-sync fires 3+ frames/minute in 29 observed minutes; frame p50 1.68s p90 7.9s).
- Estimate: 16.6s summed over ~8 executor workers ⇒ ~1.5-3s wall p50 page, more at p90 (exec p90
  7.7s), plus real load relief on the :5433 tunnel which speeds F2's probes and everything else.

## F6 asset_resolution intra-trace duplicate SQL — 10.4s/trace summed
- Evidence: same md5-per-trace analysis: asset_resolution stage 3,472 calls, 1,233 redundant,
  3,308s total redundant latency across 318 traces (10.4s/trace) — the expensive value probes are
  re-issued WITHIN one resolution (asset_candidates + ambiguous_candidates + grounding.meaningful
  each probe overlapping table sets; frozenset-of-tables cache keys miss when the set differs by
  one element). Proposal: per-TABLE cache entries (not per-set) + the same request-scoped memo.
  Estimate: -5-10s on ambiguous/picker-bound resolutions (which are exactly the slow ones).

## F7 data_quality_policy scalar knobs re-read per LEAF — 483 reads/trace
- Evidence: obs_db_queries: 113,626 reads of SELECT txt_value FROM data_quality_policy (keys
  placeholder.scalar/narrative, scrub.*, narrative_slots) = 483.5/trace ≈ 0.97s/trace summed;
  97,740 of them inside layer2_card_ai.card (grounding/default_assemble.py per-leaf scrub);
  +34,680 reason_template (84/trace) +6,012 derivation_binding (51.8/trace) +routable_pages 6.4 +
  card_feasibility 8 + page_specs 4.7 + catalog_row's 7 uncached reads × cards × passes.
- config/policy_read.py + config/quality_policy.py query per call, NO cache (verified in source);
  app_config itself IS process-cached. Proposal: wrap num()/txt() in the existing TTLCache (120s)
  — same fail-open semantics, knob edits land within TTL. Estimate: ~0.3-1s wall/run; trivial effort.

## F8 information_schema.columns introspection — 11.3 remote reads/trace at 69ms
- Evidence: 5,248 calls, 69ms avg, 362s total; 0.78s/trace; issued from executor.card +
  layer2_card_ai.card against neuract (data/neuract_pool.py present_columns/column_types are
  TTL-cached — the leak-through is col_dict.py + grounding/schema_fingerprint.py sites and TTL
  expiry churn). Proposal: route ALL column-list reads through the ONE cached door; include in the
  F2 warm-keeper (schema changes only at registry re-sync). Estimate: -0.5-0.8s/run.

## F9 picker re-POST re-authors 1a from scratch — the injection seam already exists
- Evidence: handle_run(asset_id=…) → build_response → run_pipeline re-runs route+stories(+validate)
  for a prompt whose 1a the pending run JUST computed. run_pipeline(layer1a=…) injection is already
  the multi-asset lane's mechanism (harness.py:242). run_id = make_run_id(prompt) is identical
  between the pending run and the re-POST.
- Proposal: host caches {run_id: layer1a} (TTL ~15min) when returning asset_pending=True; the pinned
  re-POST injects it (flag-gated). NOTE: harness suppresses reconcile/preflight/reflect when
  layer1a is injected (shared-template lock) — the picker path should inject via a new
  "cached_1a" param that keeps re-routes enabled, or accept the lock (the page was already accepted).
- Estimate: -2-4s per picker round trip (page_selection 0.47s + story_selection 1.54s + their DB
  reads + LLM queue), plus removes 2 LLM calls of :8200 load.

## F10 copilot speculative pre-warm (the prompt is known BEFORE submit)
- copilot/ (:8772) sees keystrokes; zero pipeline coupling today. Proposal: on typing-pause, fire-and-
  forget (a) probe warm (redundant if F2 daemon ships), (b) speculative run_1a(prompt) into the F3/F4
  cache keyed by normalized prompt. On submit, 1a is a cache hit.
- Estimate: hides 1a ≈ 2.5s + knowledge 0.17s on every fresh prompt typed slower than ~3s; cost = 1-2
  extra small LLM calls per typing session (route 3.6K ptok + stories) on the shared GPU — bounded by
  llm.global_concurrency admission if enabled. With F2+F3 shipped, incremental value ~2-4s.

## F11 panel_members_block: permanent lru_cache (stale-fact hazard) + cold 28-member serial probe
- layer2/emit/panel_members_block.py:78 @lru_cache(maxsize=128) on _block_for(mfm_id, scope): the
  first panel prompt pays 28 members × (present_columns + latest + latest_ts) remote reads serially
  (~2-4s) INSIDE the emit prompt build (ahead of the LLM call); afterwards it NEVER refreshes —
  has_data=Y/N and last= facts freeze for the process life (contradicts the TTL-everything rule the
  same file family established; also anti-correlates with F4 normalization). Proposal: TTLCache
  (period-bucketed ts facts) + include panel members in the F2 warm-keeper. Estimate: -2-4s on the
  first panel-overview page per process/TTL window; correctness win on the frozen facts.

## F12 static skeleton/payload caches — already good (verify only)
- host/payload_store.py _SKELETON_CACHE/_raw defaults: process-cached, deepcopy-served. OK.
- app_config: process-cached on success, never-cache-empty, 5s backoff. OK.
- data/registry/lt_mfm.py, neuract_pool cols/types, value_probe, panel_members, _LOGGED_CACHE:
  TTLCache(120s) — all correct, just TTL-short for their change rates (see F2).

## F13 dead ends (measured, NOT worth it)
- _system() per-card recomposition: 0.5ms warm (file read + str ops) — leave it.
- catalog_row.load 7 DB reads/card: ~4-6ms/card local — ~50ms/page; fold into F7 if convenient.
- import run.harness cold: 0.27s; first cfg(): <1ms — no boot-warm needed for imports.
- host _dump_response synchronous disk write: small vs payload; not measured worth chasing.

## Cross-checks / gotchas for implementers
- Single-asset serve path is byte-identity-pinned: EVERY cache must be flag-gated
  (default-off knob rows) or provably byte-identical; F5/F6/F7/F8 change no bytes (same rows served),
  F3/F4(l2_emit)/F9 change prompt bytes or provenance → gate + re-cert.
- Never-cache-empty + TTL self-heal (lib/ttl_cache.py) is the house pattern — reuse it, do not
  hand-roll new dicts.
- Estimates for LLM-stage savings assume the :8200 queue is not saturated; under sweep load the
  savings are LARGER (removed calls also un-queue everyone else).
