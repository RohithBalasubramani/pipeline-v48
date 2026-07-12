# V48 Latency Profiler — Instrumentation Plan (synthesized 2026-07-12)

Synthesized from 4 subsystem reader maps (host, harness, exec/data/db, llm, logs) over
`/home/rohith/desktop/BFI/backend/layer2/pipeline_v48`. Key line numbers spot-verified against source on 2026-07-12.
Two readers (layers_1a_1b, layer2_validate) returned nothing — their gaps were re-verified directly (see §5).

---

## 1. Per-stage wrap points

Rule of thumb driving every choice below: **patch the CONSUMER module's bound name** when the call site did
`from X import f` at module top; patch the **defining module** when call sites import lazily or hold the module and
do attribute lookup at call time. The safest universal alternative: install the profiler **before any pipeline module
is imported** (top of `host/server.py`, before line 36) — then defining-module patches work everywhere.

| Stage | Best wrap | Patch target (binding-aware) | Per-card sub-spans? |
|---|---|---|---|
| knowledge_gate | `knowledge.ems.ask` (knowledge/ems.py:68) | `knowledge.ems.ask` — imported LAZILY per request at server.py:317, so defining-module patch works | No. One LLM call inside (`call_qwen(stage="knowledge_ems")` ems.py:75). Legitimately ABSENT on pinned re-POSTs (gate at server.py:316: only fires when asset_id is None and asset_ids empty). |
| asset_resolution | `run_1b` (layer1b/build.py:10) | **`run.harness.run_1b`** (bound at harness.py:20; the lambda at harness.py:197 resolves from harness globals at call time) | Sub-spans exist but unverified line-exact (reader missing): `asset_resolve.py:157` (stage="asset_resolve") and `column_basket.py:68` (stage="basket"), each wrapped in `retry_once` (layer1b/guardrail/retry_one.py:10 — doubles worst case). Cheapest: derive from call_qwen stage tags instead of extra patches. ALSO: `host.multi_asset.natural_compare_ids` (multi_asset.py:17, called server.py:331 pre-pipeline — hidden resolution cost on compare prompts, fans resolve_asset via run_parallel) and `host.multi_asset.resolve_assets` (bound at multi_asset.py:14) for the picker path. |
| page_selection | `run_1a` (layer1a/build.py:20) | **`run.harness.run_1a`** (bound at harness.py:19; covers all 3 call sites: initial thunk :196, preflight reroute :76, reflect reroute :170). **PLUS** `run.reconcile_granularity.run_1a_to` (bound at reconcile_granularity.py:10, called :38) — 1a time a run_1a patch MISSES. | run_1a can fire 0–3x per run (+run_1a_to once). Sub-span: pure routing = `layer1a.build.route` (bound at build.py:2). In the multi shared-template lane the 1a thunk is `lambda: layer1a` (~0ms) — that's correct, not a bug. |
| story_selection | `build_stories` (layer1a/story_builder.py:22) | **`layer1a.build.build_stories`** (bound at build.py:3, called from `_assemble` build.py:10 — which serves BOTH run_1a and run_1a_to). Verified 2026-07-12. | Per-page, not per-card (one LLM call builds all card stories: `call_qwen(stage="stories")` story_builder.py:37, on_error="marker"). Runs INSIDE the 1a span — subtract, don't sum. |
| layer2 | Whole (incl. reroute+revalidate+attempt 2): `run.harness._reflect_loop` (harness.py:88). Per emit-pass: **`run.harness.run_2_all`** (bound at harness.py:16, def layer2_all.py:34). | `_reflect_loop` is only ever called from run_pipeline (harness.py:304) — defining-module patch fine. For run_2_all patch the **harness binding**. | YES: per-card emit = **`run.layer2_all.run_card`** (bound at layer2_all.py:12, def layer2/build.py:693; the per-card lambda at layer2_all.py:40 resolves from layer2_all globals). Keyword-only args (`*, already_chosen=None, shared_ctx_ref=None`) — wrapper MUST forward **kwargs. Fan-out capped at cfg('layer2.emit_concurrency',4): time INSIDE the thunk or queue wait pollutes per-card numbers; sum(cards) >> pass wall-clock. Deeper: `layer2.emit.emit.emit` (emit.py:197) = logical emit incl. ONE transport re-call (:217). |
| executor | Whole phase: `_run_cards` (host/exec_cards.py:138). Per-card: **`fill_one_card`** (host/exec_cards.py:105) — the ONE seam shared by page fan-out AND /api/frame. | `_run_cards`: patch **`host.assemble._run_cards`** (bound at assemble.py:9). `fill_one_card`: patch **BOTH `host.exec_cards.fill_one_card` AND `host.server.fill_one_card`** (re-bound at server.py:42-43; /api/frame at server.py:281 calls the server-bound name). All args keyword-only. | YES — this is THE per-card span. Runs in ThreadPool workers (max_workers=max(2,min(n,8)), exec_cards.py:175) under wall budget `_EXEC_BUDGET_S` (45s, read at IMPORT, line 18). Sub-spans: `ems_exec.serve.run.run_card` (serve/run.py:66 — defining-module patch WORKS, callers hold the module) and `ems_exec.renderers.run_special` (renderers/__init__.py:126 — lazy import at exec_cards.py:118, patch works). **Double-count hazard**: roster-recipe cards go run_special → `_interpreter_payload` (__init__.py:118) → run_card — attribute per-card totals at fill_one_card, core time at run_card, and dedupe. |
| validation | Pipeline validate: `run_validate` (validate/build.py:75) → patch **`run.harness.run_validate`** (bound at harness.py:21; covers all 3 calls: :251, :78, :172). Host per-card verdict: `validate.render_verdict.compute` (render_verdict.py:232) → defining-module patch works (enrich.py:7 imports the MODULE, attr lookup at call time). | Two DIFFERENT costs — report as `validation.pipeline` (0–3x per run) and `validation.render_verdict` (per card, in request thread). Optional: `validate.build.payload_final` (build.py:107, local import at harness.py:309 → defining-module patch works). | render_verdict is per-card; pipeline validate is per-run(-ish). |
| rendering | Whole assembly (executor + enrich): `assemble_cards` (host/assemble.py:12). Pure per-card render/enrich: `_enrich_card` (host/enrich.py:125). | `assemble_cards`: single path imports lazily (server.py:125 → defining-module patch works) but multi path binds at multi_asset.py:12 → **also patch `host.multi_asset.assemble_cards`**. `_enrich_card`: patch **`host.assemble._enrich_card`** (bound at assemble.py:8). Also `host.display_dash.apply` (display_dash.py:128, lazy both call sites) if dash-policy time is wanted. | YES: `_enrich_card` runs SERIALLY in the request thread per 1a card after the fan-out. Note: rendering = assemble_cards − _run_cards. `_enrich_card` can hit DB on the blank path (`_asset_has_logged_data` enrich.py:37) — the q patch disambiguates. assemble_cards returns [] early on data_unavailable → near-zero render time is an honest terminal, not a bug. |

Whole-request anchors: `host.server.build_response` (server.py:100, t0 at :101) and
`host.multi_asset.build_response_multi` (multi_asset.py:54, lazy import at server.py:335 → patch works). Multi path
assembles lanes SERIALLY (multi_asset.py:68-78) and `run_pipeline_multi` runs classes SEQUENTIALLY
(harness.py:344-351) — wall-clock is a SUM, not a max. Total pipeline = `run.harness.run_pipeline` (harness.py:184);
to intercept from the host side patch `host.server.run_pipeline` (bound at server.py:36).

## 2. Minimal DB patch set + AI patch points

### DB — 5 patches cover ALL Postgres time (verified: no sqlite3 in runtime, no HTTP to ems_backend)

1. **`data.db_client.q`** (data/db_client.py:11) — ALL cmd_catalog :5432 traffic. It is a **`psql --csv` SUBPROCESS**,
   not psycopg2 — a psycopg2 patch misses it entirely. Every host/pipeline import of q is lazy → defining-module patch
   catches everything (config/cfg, recipes, registry mirror, payload_store, card_handling, equipment, grounding...).
   Its cost includes ~10-30ms process spawn per call.
2. **`ems_exec.data.neuract._run`** (ems_exec/data/neuract.py:50) — ALL neuract :5433 gic_* time-series reads
   (latest/window/series/bucketed/edges/deltas all funnel here; pooled psycopg2, `_conn` at :33). Drops the connection
   and returns [] on ANY exception — errors look like fast empty returns; patch `_conn` too if reconnect counts matter.
3. **`registries.neuract._db.rows` + `.dicts`** (registries/neuract/_db.py:50 / :68; `one()` delegates to dicts) —
   the neuract METADATA twin (lt_mfm, edges, 3d tables) on the hot executor path (`_registry_mfm_id`,
   members.resolve, _story/_facts, asset_3d). Separate pool, `_conn` at :29.
4. **`data.db_client.pg_connect`** (data/db_client.py:24) — validate/data_load.py:27 frame read; new connection per
   call, no pool. Wrapping pg_connect times connects only — wrap `validate.data_load.load_asset_frame` for full capture.
5. **`validate.payload_lookup.card_payloads_for` + `card_payloads_home`** (payload_lookup.py:10 / :27) — uses BARE
   `psycopg2.connect` at :13 and :32, bypassing everything else.

Anchors (already covered by patch 1, useful as named spans only): `data.lt_panels.panel_members.panel_members`
(panel_members.py:39, TTL-cached) and `data.registry.lt_mfm` accessors. Cache caveat: payload_store
(_SKELETON/_RAW_DEFAULT, process-life), neuract _COLS/_LOGGED caches, TTLCaches (120s), and `_insight._CACHE` make
cold vs warm runs incomparable — tag first-touch samples.

### AI — 2 patches cover ALL LLM traffic

1. **`llm.client.call_qwen`** (llm/client.py:103) — all six stage-tagged call sites (route / stories / asset_resolve /
   basket / l2_emit / knowledge_ems). **CRITICAL**: all six bind via `from llm.client import call_qwen`
   (route.py:12, story_builder.py:5, asset_resolve.py:18, column_basket.py:4, emit.py:17, ems.py:14 — verified) —
   patching llm.client.call_qwen AFTER they import does NOTHING for them. Install the profiler BEFORE pipeline imports,
   or rebind in all six modules. Wrapping call_qwen times the whole logical call incl. its internal parse-retry
   (llm.parse_retry=1); it natively receives `stage=`.
2. **`ems_exec.renderers._insight._post`** (_insight.py:106, urlopen at :122) — the ONLY LLM path that BYPASSES
   call_qwen (narrator cards, own 8s timeout knob insight.timeout). Wrap `summary_sync` (:153) too if cache-hit
   visibility is wanted (content-hash `_CACHE` — hits make ZERO HTTP calls).

Alternative single point: wrap `urllib.request.urlopen` filtering ":8200" — but it MUST be installed AFTER
`import obs.ai_log` (ai_log.py:56 rebinds urlopen at import; original saved in `_orig` at :10; _insight.py imports
ai_log as a side effect), it cannot recover the stage (stage is never in the HTTP payload), and it must exclude the
non-LLM urlopens in validation/runner.py:30 and validation/checks/datesync.py:25. Failure telemetry: hook
`llm.client._fail`/`_record` (client.py:78/:68) — failed/timed-out calls NEVER appear in ai_*.jsonl, only in
failures_<run_id>.jsonl; timing only successes under-counts the worst latencies (120-150s timeouts).

Retry layering (one logical call ≠ one HTTP round-trip): call_qwen internal parse-retry (≤2 sends) × layer2 emit
transport re-call (emit.py:217, skipped for llm.no_retry_kinds='timeout,truncated') × layer1b retry_once — worst case
one L2 emit = 4 HTTP round-trips. Time both levels or attribute retries explicitly. Over-budget prompts
(>llm.prompt_budget_tok≈45000 chars//4) are never sent at all.

## 3. Profiling-context propagation across fan-outs

There is NO asyncio anywhere; concurrency = plain `ThreadPoolExecutor` at FOUR sites, all using bare `ex.submit(fn)`
(NO contextvar copy — verified run/parallel.py:20):

1. `run.parallel.run_parallel` (parallel.py:5) — 1a∥1b join (harness.py:195) AND L2 per-card fan-out
   (layer2_all.py:49, cap 4) AND natural-compare name resolution (resolve_names.py:106).
2. `host/exec_cards.py:175` — executor per-card pool (≤8 workers).
3. `validation/runner.py:98` and 4. `validation/checks/datesync.py:84` — offline validation harness (not serving path).

Additionally the server itself is `ThreadingHTTPServer` (server.py:346) — one OS thread per request; concurrent
/api/run requests each spawn their own nested pools, so cross-request contention (vLLM :8200, neuract :5433) shows up
inside wrapped functions.

**Recommended strategy (matches existing codebase pattern, minimal invasiveness):**
- Use **explicit keys, not ambient context, wherever the seam already carries them**: `run_card(run_id, card_id, ...)`,
  `fill_one_card(cid=..., ...)`, `_run_cards(run_id=...)`, `stage(run_id, ...)` — key the profiler store on
  `(run_id, stage, card_id)` in a lock-protected dict / thread-safe accumulator. Never thread-locals, never a plain
  global scalar.
- For call sites with no explicit key (call_qwen, q, neuract._run): mirror the codebase's own pattern —
  read `obs.ai_log._RUN_ID` (module GLOBAL set at harness.py:187 and RE-KEYED at harness.py:107 for reflect attempt 2;
  visible to all worker threads for free). Accept its documented flaw: concurrent prompts in one process clobber it.
- If cross-request correctness under concurrency is required, use a `contextvar` AND patch the submit sites:
  `run/parallel.py:20` and `host/exec_cards.py:176` to `ex.submit(contextvars.copy_context().run, fn)`. Those two
  cover the whole serving path; the two validation pools can be ignored.
- Reflect-loop rid split: attempt 2 runs under `make_run_id(prompt, salt='loop2')` (harness.py:105-107). The profiler
  must map both rids to one logical run — the loop2 rid is DETERMINISTICALLY derivable from the prompt (sha1,
  run/run_id.py:5), so record `prompt → {rid, rid_loop2}` at run_pipeline entry. Also: same prompt → SAME run_id
  across repeated runs — never key persistent storage on run_id alone; add a per-invocation uuid.
- Wrappers around thunks that flow through run_parallel MUST re-raise exceptions (run_parallel returns exceptions as
  dict VALUES, parallel.py:24-25 — swallowing changes semantics). run_card/run_special/fill_one_card never raise —
  latency outliers surface as status `why='executor budget exceeded'`; note budget-expired workers KEEP RUNNING after
  the page returns (futures aren't cancelled) and their DB time still accrues.

## 4. Historical log miner — can / cannot / pairing rules

Sources: `outputs/logs/pipeline_<run_id>.jsonl` (253 files, 17 stage names) and `outputs/logs/ai_<run_id>.jsonl`
(239 files, uniform 5-key schema {ts, run_id, url, request, response}).

**CAN compute:**
- Per-run wall clock: `RESPONSE.elapsed_ms` (verified == RESPONSE.ts − PROMPT.ts); for the 302 orphan PROMPTs use ts
  deltas. Baseline distribution (n=1293): p50 38.5s / p75 64.5s / p90 124.8s / p99 219.7s / max 303s.
- Coarse stage-boundary timings from consecutive pipeline-record ts deltas within one run:
  PROMPT → {1a,1b at the parallel join} → validate → asset_gate → (L2.card* → layer2) → notes → exec* → RESPONSE.
- Per-AI-call duration: `datetime.fromisoformat(rec.ts).timestamp() − rec.response.created` — local-tz naive ISO ts
  minus server-receipt integer epoch; ±1s quantized; validated on 12,238 records (0 negatives, p50 3.18s, max 148s).
- AI-call → stage attribution: fingerprint `request.messages[0].content` (10 stable kinds: L2 emit "You are LAYER 2…"
  med 25s; "COLUMN RESOLVER" med 10.7s; "per-card ANALYTICAL STORY" med 2.2s; 1a router med 1.0s; "L1 ASSET RESOLVER"
  med 1.0s; knowledge gate med 0.76s; "AI SUMMARY line" med 1.2s; +3 minor) + run_id join.

**Pairing rules (exact):**
- 125/253 pipeline files hold MULTIPLE appended runs (≤24 PROMPTs): pair PROMPT→next RESPONSE|RESPONSE_MULTI
  **sequentially within a file**, never per-file. 1,280 closed pairs / 1,582 PROMPTs.
- NEVER pool RESPONSE_MULTI.elapsed_ms (p50=4ms, author-once-per-class cache reuse) with RESPONSE.elapsed_ms.
- Map reflect-loop rid pairs: loop2 rid = sha1('loop2|'+prompt) — derive from PROMPT.text to merge ai_ records.
- json.loads per line with try/except: 12 pipeline + 3 ai files contain NUL-byte runs (one has a valid record AFTER
  the NULs). Stream large ai files (up to 41MB) line-by-line.
- Convert ai ts with `datetime.fromisoformat(ts).timestamp()` (naive LOCAL time — never treat as UTC); pipeline ts is
  already float epoch.
- Do NOT pair consecutive ai records by ts (L2 fan-out cap 4 interleaves them) — each record is self-contained.
- 'validate' can carry only {ERROR} (9/1311); stage 'layer1b' (266 recs) is exclusively error records; 1a count (1908)
  > PROMPT count (1582) because reroutes emit extra 1a records — count invocations, never assume one per run.

**CANNOT compute (needs the new instrumentation):**
- Any DB time (zero DB records exist anywhere).
- Per-card L2 emit latency from pipeline logs (all L2.card records flush together at the layer2 join with
  near-identical ts) — only the ai-log L2-kind records give it.
- Individual 1a vs 1b latency from pipeline logs (both logged together at the join) — ai log only.
- Per-card executor internals (exec records are individually stamped but concurrent — deltas = completion spacing,
  not cost); host enrich/render split; /api/frame anything (it emits ZERO stage() records — fill_one_card is the only
  hook); queueing-vs-inference split inside an AI call; failed-LLM-call durations (absent from ai logs; only kind
  counts in failures_*.jsonl).

## 5. Conflicts between readers / uncertain points to verify before coding

1. **Two readers returned null** (layers_1a_1b_knowledge, layer2_validate). Re-verified directly 2026-07-12:
   story selection = `build_stories` def story_builder.py:22, bound into layer1a/build.py:3, called from `_assemble`
   (build.py:10) serving BOTH run_1a and run_1a_to; all six `from llm.client import call_qwen` bindings confirmed;
   emit.py:197/:209/:217, validate/build.py:75/:107, exec_cards.py:18/:105/:138/:175, _insight.py:106/:122/:153,
   db_client.py:11/:24, neuract.py:33/:50, _db.py:29/:50/:68, payload_lookup.py:13/:32 all confirmed. STILL UNVERIFIED:
   layer1b internals line-exact (asset_resolve.py:157, column_basket.py:68, retry_one.py:10 — from llm reader only),
   layer2/build.py:693 run_card signature, grounding/swap_settle cost, and everything inside layer1a/route.py beyond
   the call_qwen line — check before wrapping sub-spans there.
2. **"Validation" is two different things** — host reader anchored it at `validate.render_verdict.compute` (per-card,
   post-fill), harness reader at `run.harness.run_validate` (pipeline, pre-L2). Not a conflict, but the profiler must
   emit two distinct span names or the stage will look double-counted.
3. **run_card double-entry** — exec reader flags roster-recipe cards re-entering `ems_exec.serve.run.run_card` from
   run_special; wrapping fill_one_card + run_card without dedupe double-counts. Verify which card_ids take the roster
   path (cmd_catalog.card_fill_recipe) before summing executor time.
4. **assemble_cards patchability differs by path** — host reader says lazy import (single path, patch works) but the
   multi path binds at multi_asset.py:12. Both must be patched; test both /api/run shapes.
5. **stage() piggyback vs wrapping** — logs reader shows stage() records are completion-stamped point events with no
   durations; harness reader proposes hooking stage() for asset_gate (inline block, no function). Agreed resolution:
   hook `obs.stage.stage` for ordering/tags ONLY (all host imports of it are lazy → defining-module patch works),
   derive NO durations from it, and accept asset_gate as ~0-cost telemetry-only.
6. **urlopen layering** — llm reader: profiler urlopen patch must install AFTER `import obs.ai_log` (else ai_log
   captures the profiler wrapper as its `_orig`). If the plan sticks to call_qwen + _insight._post wraps this hazard
   vanishes; verify no other :8200 caller exists (grep for `8200` and `chat/completions`) before finalizing.
7. **Import-order dependency of the whole plan** — the six call_qwen from-imports, harness bindings (harness.py:14-21),
   host bindings (server.py:36/42-43, assemble.py:8-9, multi_asset.py:11-14) all resolve at first import. The profiler
   MUST be importable/installable at the very top of host/server.py (before line 36) OR patch every consumer binding
   listed in §1/§2. Decide ONE strategy and add a startup assertion that each wrapped target is actually the wrapper.
8. **_EXEC_BUDGET_S and llm/config constants read at import** (exec_cards.py:18, llm/config.py:4-5) — the cfg() DB
   call at import fires before any profiler installed post-import can see it; knob changes need process restart.
9. **Uncertain**: whether `/api/frame` volume matters in production traffic (no historical records exist to size it) —
   instrument first, then decide if it needs its own dashboard bucket.
10. **Clock skew for the miner**: ai-call duration uses server-side `response.created` vs client-side ts — same host
    (localhost:8200) so skew ≈ 0, but verify vLLM and the pipeline share a clock if the LLM ever moves off-host.
