# V48 Latency Audit — 2026-07-14

**Method:** 12-lens exhaustive workflow sweep (find → adversarial verify → synthesize) over the post-Jul-12 tree.
151 findings; 27 adversarially CONFIRMED, 2 REFUTED, 15 ground-truth MEASUREMENTS, 107 mechanism-verified-by-finder but
pending independent verification (the Fable session limit killed 108 verify agents at 02:59; resumable from cache).
Per-lens raw notes: `findings_*.md` in this directory. Merged machine-readable data: `verified_findings.json`.

**Baselines (measured, obs Jul 12–14):**
- Interactive single-prompt proxy (low-overlap runs): **p50 30.5s**. All-runs p50 81.7s / p90 346.9s (sweep-polluted).
- Cold probe-paying 5-card panel page: **236s** (trace t_4302e600…), of which **183.7s is pre-pipeline probes**.
- L2 emit per card: p50 18.3s / p95 40.1s — **89.4% of vLLM request wall is decode** (1,291 ctok @ 73 tok/s = 17.7s;
  prefill is only ~1.1s at 19,226 tok/s). Prompt size is NOT the lever; completion length and decode speed are.
- /api/frame re-fetch: p50 1.68s / p90 7.9s (already probe-free).
- Per-run p50 economics: 10 LLM calls, 98K prompt tok, 5.9K completion tok, 638 DB queries, 15.6ms tunnel RTT.

---

## The headline

**~Half of all perceived latency is one line of SQL.** The registry value probe
(`data/value_probe.py:73`, reached via `host/server.py` natural_compare_ids → `asset_candidates()`)
orders by `timestamp_utc::timestamptz`, which matches **neither** live index. Every probed table seq-scans
(641ms–1.1s each, 40-table chunks at 20–28s); the identical row via the existing `ts_imm` expression index
returns in **0.104ms — a 6,164× miss**, and the probe runs **serially before the pipeline even starts**, invisible
to the admin console (it landed in the mislabeled "1a"/gap). Per-run burden: **p50 104.7s / p90 347.9s**; ~48% of
runs pay >10s. The cache that should absorb it has a **120s TTL — shorter than the 184s probe itself**, so it can
never amortize under real traffic.

Fixing the ORDER BY (3 lines, reusing the `neuract.ts_index_fn` knob the executor already honors) + raising the TTL
+ a background warm-keeper turns the 236s cold panel page into ~52s **before touching anything else**.

After that, the pipeline is honestly LLM-decode-bound and DB-chattiness-bound, in that order — both with large,
verified levers below.

---

## Top 10 fixes (deduped clusters, ranked by verified impact)

| # | Fix (cluster) | Findings | Effort | Risk | Verified saving |
|---|---|---|---|---|---|
| 1 | **Index-aligned probe ORDER BY** — build value_probe/has_data ORDER BY from the ts_imm knob (as the executor does) | DB-1 ✅, M1, L1B-01, L1A-01, DB-5, L1B-04, HOST-7 | 3-line | low | **-105s p50 / -348s p90** on probe-paying runs (~48%); 236s page → ~52s |
| 2 | **Probe cache that can actually hit** — TTL 120→900s + background warm-keeper + single-flight; optionally persist has_data snapshot in cmd_catalog (4ms local read) | CR-1, M3, L1A-02, DB-2, L1B-02, MC-1, MC-5 | small | low | -19s median on cold dashboards; kills the 1b p90 179s tail permanently (multiplies with #1: compares pay it 3×) |
| 3 | **Real neuract connection pool** — `data/neuract_pool.py` holds ONE psycopg2 conn; all 8 executor threads serialize on it (proved: 4 cards' summed walls == summed query latency) | EXEC-1 ✅, DB-3 | small | low | **-25s exec wall** on 4-panel-card pages; un-blanks budget-clipped cards (correctness win) |
| 4 | **Executor SQL batching + request-scope memo** — member_delta 4 queries/member/key → UNION ALL (~4-8 stmts/card); memo kills 734 duplicate queries (72.7s of 142.2s summed SQL on slow traces); multi-col bucketed(); UNION latest rows; latest_ts TTL | EXEC-2 ✅, EXEC-3 ✅, EXEC-5 ✅, EXEC-7 ✅, EXEC-9-11 ✅, CR-4, DB-4, DB-7, DB-10, DB-11, CR-7, CR-8, DB-6 | medium | low-med | worst panel-power card **52.7s → 2-4s** (with #1); -1.5-3s p50 typical page; frame p90 7.9→~3s |
| 5 | **L2 completion diet** — emit roster DIFF not full retyped recipe (executor re-derives members from DB anyway); cap `llm.max_tokens=6144` (p99=5,089; observed 14.6K-tok runaway = 118.6s of a 142s compare) | MC-2, VS-2, L2E-1, VS-4, L2E-9, M2 | small-med | low-med | **-95-100s on panel-overview compares**; -2-5s/card on roster cards; -80s on p99 timeout tails |
| 6 | **MTP speculative decoding** — checkpoint ships a draft head (mtp_num_hidden_layers=1); vLLM registers qwen3_5_mtp; decode is 13-17s of the 18.3s card | VS-1, L2E-5 | config + cert sweep | med | card p50 18.3s → ~12s; 8-card L2 wall 31.7→~20-22s; every LLM call in the tree speeds up |
| 7 | **emit_concurrency 4→8 + `llm.global_concurrency` admission** (already shipped, disabled) — one wave instead of two; admission guard prevents multi-run stampede | L2E-3, VS-5, VS-6, HOST-11, M13 | config | med | -12s p50 on 5-card pages, -7s on 8-card; protects p95 under concurrency |
| 8 | **Semantic recipe/authoring cache** — 94.2% of (page,card) emissions recur but 0% are byte-identical (a freshness anchor at char 1083 busts every key); normalize the prompt (bucket `last=` facts, move RUN:/CARD: header off the top), cache 1a+basket for picker re-POSTs | M7, L2E-4, CR-2, CR-6, S16 ✅, MC-10, CR-9, CR-10, L1B-03, L1A-07 | medium | med | repeat page **42s → ~5-8s** (30.3% of traffic is exact-repeat); picker re-POST -6-9s |
| 9 | **Parallelize the multi path** — class lanes run strictly sequentially (3-feeder compares = 3 stacked pipelines); per-asset executor fills also sequential; compare_mode LLM on the serial tail | L1A-03, MC-3, HOST-2, L2E-6, S7 ✅, EXEC-6 ✅, L1A-04, MC-4, MC-6 | medium | med | 3-class compare **-140s (-33%)**; same-class N-asset -(N-1)×exec; -1-2s tail |
| 10 | **Perceived latency: two-phase shell + progress + card streaming** — page shell is final at ~10s but renders at ~42s; RunningCard is a dead spinner for up to 11 min | S2 ✅, S1 ✅, S10 ✅, S13 ✅, HOST-3, L2E-8, S15 ✅ | med-large | med | **TTFMP -31s p50 / -64s p90**; first cards visible ~15-20s; zero compute change |

✅ = adversarially CONFIRMED with re-derived numbers.

---

## Tiered roadmap

### Tier 0 — deployable today (config/DB rows + ≤3-line diffs)
1. `value_probe.py` ORDER BY → knob-aware `ts_imm` expression (fix #1). Also mirror in col_dict sampling,
   validate's pandas probe, `window_nonnull`/`latest_nonnull` (same cast family).
2. `app_config`: `llm.max_tokens=6144` (finish=length → honest truncate, no-retry).
3. `app_config`: `cache.resolution_ttl_s` 120 → 900 (never-cache-empty already shipped; flap self-heal preserved).
4. `app_config`: `layer2.emit_concurrency=8`, `llm.global_concurrency=8-10` (admission code shipped, row=0=off).
5. `db/`: add the missing `ts_imm` expression index on the 62 gic tables lacking it (+ the one table with no ts index).
6. neuract `statement_timeout` ~15s (observed 104.6s single-query tail → honest degrade instead).
7. Serve FE as a built bundle instead of `npx vite` dev mode (-5.5s first load) + gzip on :8770 (VPN links).
8. Candidate behind a cert sweep: vLLM `--speculative-config '{"method":"qwen3_5_mtp","num_speculative_tokens":2}'`
   (temp-0 rejection sampling is output-lossless; certify with pinned-seed replay + one sweep).

### Tier 1 — small code (days)
- ThreadedConnectionPool for neuract (#3) behind `V48_DB_POOL_N`.
- Executor batching + memos (#4): paired-register single window() call; UNION ALL per (window,colset);
  TTLCache on latest_ts/panel_kwh/member rows; `_field_value` NULL-refetch fix (EXEC-11, byte-identical).
- Probe warm-keeper thread + single-flight (#2); parallelize the 8 serial probe chunks.
- Roster DIFF emit + compact directive (#5 code half).
- Knowledge-gate overlap (~0.2-0.7s), compare_mode piggyback, granularity_reconcile off critical path (7% of runs, -1.9s).
- Obs diet: sample per-query db events (51k on worst runs, -3.5s), async replay bundle, drop redundant sql jsonl leg.
- Telemetry honesty: stamp the pre-flight probe as its own span; fix admin 1a/RESPONSE_MULTI pairing artifacts
  (today they hide exactly the things fixed above).

### Tier 2 — structural (1-2 weeks)
- Two-phase shell + per-card NDJSON/SSE streaming + progress ticker (#10).
- Semantic recipe cache + prompt normalization (#8) — the 94% recurrence ceiling is the single biggest repeat-traffic win.
- Parallel class lanes + per-asset fills on the multi path (#9).
- Emit→exec per-card pipelining (fills start as each emit lands; today it's an all-cards barrier).
- Copilot speculative pre-run of 1a + probe warming while the user types (CR-11).

---

## Projections (stacked, overlaps deducted)

| Scenario | Today | After T0 | After T1 | After T2 |
|---|---|---|---|---|
| Cold 5-card panel page (probe-paying) | **236s** | ~52s | ~38-42s | ~25-30s (TTFMP ~10s) |
| Interactive single-asset page (warm probes) | ~30.5s | ~27-29s | ~23-25s | ~14-18s (TTFMP ~10s) |
| Repeat prompt (same page+asset) | ~42s | ~38s | ~35s | **~5-8s** |
| Multi-asset 3-class compare | 410-441s | ~150-200s | ~100-120s | ~60-90s |
| /api/frame date change | 1.7s p50 / 7.9s p90 | same | ~1s / ~3s | same, per-card progressive |
| Picker re-POST leg | full re-run | -probe cost | -probe cost | ~exec-only (~5-10s) |

Dominant residual after T2: L2 decode (~12s/card with MTP × one 8-wide wave) — further gains need
completion-token reduction (already dieted) or a faster/smaller emit model.

---

## Investigated and REJECTED (do not re-litigate)

- **Structured-output grammar overhead: zero** (measured 158.1 vs 157.8 tok/s). Thinking mode already off (0/1,288
  responses contain think tags). gpu-memory-utilization is fine (KV peaks 13%; only ~8GB free — copilot holds 12.9GB).
- **psql subprocess spawns are gone** from the hot path (the mined 10,982 predate the pooled q(); residual users are
  tooling/monitoring only).
- **Post-fill CPU pass fusion: pointless** — whole ~15-pass chain is 20-40ms/card (measured).
- **Picker re-POST 1a recompute (S4): refuted as a lever** — costs ~1.1s p90 only (the picker leg's real cost is probes).
- **EXEC-12 double series roll: unreachable path** in current production (interpreter valve on).
- Client HTTP overhead ~0.3ms/call; import warm-up unnecessary (harness cold import 0.27s).

## Telemetry corrections (so future audits aren't misled)
- Admin stage "1a" = the whole 1a‖1b join wall → 1b's probe tail reads as 1a; 1b reads as 0ms.
- RESPONSE_MULTI p90 683s / max 835s are cross-execution pairing artifacts; real multi worst ≈ 441s.
- "notes MAX 28.6s" = a mislabeled second L2 emit wave (reflect re-route), not notes IO.
- `elapsed_ms` excludes the pre-flight probe gap — the console *undercounts* the user's real wait.

---

## Full catalog (all 151 findings)

Verdicts: CONFIRMED = adversarially verified; UNVERIFIED = finder-verified, independent check pending
(verify agents killed by session limit; resumable); MEASUREMENT = ground truth; REFUTED = rejected.


### caching-reuse

| id | verdict | conf | effort | risk | finding | saving |
|---|---|---|---|---|---|---|
| CR-1 | UNVERIFIED | 0.90 | small | low | Value-probe/has_data cache (TTL 120s) is cold on the request path ? background warm-keeper daemon | live 1b median 22s -> ~2s; e2e joins at max(1a~2.5s, 1b) so ~-19s median on cold dashboards and ~-170s at observed worst (296s run had 184s of probes); mined p9 |
| CR-12 | UNVERIFIED | 0.90 | config | low | Dead ends measured and closed (do not spend here) | 0 |
| CR-4 | UNVERIFIED | 0.85 | small | low | 94,298 exact-duplicate neuract SQL statements WITHIN single traces in the executor ? request-scoped memo | -1.5-3s p50 page (16.6s/~8 workers), -5-10s at exec p90; plus tunnel load relief that speeds CR-1 probes; -0.5-1s per synced date-change burst |
| CR-7 | UNVERIFIED | 0.85 | small | low | data_quality_policy scalar knobs re-read from DB per LEAF ? 483 reads/trace, no cache | -0.3-1s wall per run; also removes ~600 q() round trips per prompt |
| CR-6 | UNVERIFIED | 0.80 | medium | low | Exact-match LLM response cache (md5(system+user+params) -> response) for temp-0 pinned-seed calls | -1 to -9s on partial repeats without CR-2; -18.3s/card for same-hour l2_emit repeats after normalization |
| CR-8 | UNVERIFIED | 0.80 | small | low | Remote information_schema.columns introspection repeated 11.3x per trace at 69ms | -0.5-0.8s per run; more per multi-asset lane |
| CR-9 | UNVERIFIED | 0.80 | small | low | Picker re-POST re-authors 1a from scratch ? the layer1a injection seam already exists | -2-4s per picker round trip, plus :8200 queue relief |
| CR-2 | UNVERIFIED | 0.75 | medium | medium | Run-level authoring cache for repeat prompts (26.8% of traffic) ? replay the AI's own 1a+1b+L2 emissions, fill data live | -30s per hit (37.8s -> ~5-8s executor+enrich) on 26.8% of runs = ~-8s expected p50 across traffic; RESPONSE_MULTI repeats (p50 142s) save per-class-lane L2 wall |
| CR-5 | UNVERIFIED | 0.75 | small | low | asset_resolution re-issues its own expensive probes within one resolve ? 10.4s/trace redundant | -5-10s on ambiguous/multi-name resolutions (natural-compare resolves N names against overlapping sets) |
| CR-10 | UNVERIFIED | 0.75 | small | low | panel_members_block: permanent lru_cache freezes prompt facts, and the cold path serially probes 28 members inside the emit build | -2-4s on the first panel-overview page per TTL window; enables l2_emit cacheability |
| CR-3 | UNVERIFIED | 0.70 | config | medium | vLLM prefix caching is HARD-DISABLED (hybrid mamba model auto-disable) ? the pipeline's prefix-stable prompt design earns zero | -3-6s p50 on a 5-card page (5 x ~2.9s engine prefill saved, amortized over emit_concurrency=4); larger under sweep contention since chunked prefill stops steali |
| CR-11 | UNVERIFIED | 0.60 | medium | low | Copilot speculative pre-run: the prompt is known before submit | -2-4s perceived on fresh prompts (1a hidden behind typing); with CR-1 unshipped, up to the full probe cost |

### data-miner

| id | verdict | conf | effort | risk | finding | saving |
|---|---|---|---|---|---|---|
| M1-value-probe-dominates | MEASUREMENT | 0.97 | config | low | Pre-pipeline value probe is 78% of a 5-card page's wall: p50 104.7s / p90 347.9s of :5433 probe time per run | -105s p50 / -348s p90 on any run paying the probe; sampled 5-card page 236s -> ~52s (370 tables x 0.6s -> 370 x 0.1ms + 9 RTT x 16ms) |
| M2-l2-emit-decode-bound | MEASUREMENT | 0.95 | config | low | l2_emit is ~100% decode-bound: 1,291 completion tok at 73 tok/s = 17.7s of the 18.3s p50 card emit | reference: -8.8s/card per 50% completion-token cut => -18s wall on a 5-card page (2 waves) |
| M6-1b-tail | MEASUREMENT | 0.95 | config | low | asset_resolution p90 179s / p95 192s ? the tail is 100% sequential probe DB time, not AI | -170s at p90 for resolver-probe-paying runs (falls out of M1's fix) |
| M8-admin-span-artifacts | MEASUREMENT | 0.95 | config | low | Admin stage numbers are event-spacing artifacts: '1a' includes the whole 1a//1b join (p90 120s = 1b probes); 'layer2' p50 0ms is a | n/a (semantics) |
| M12-light-stages | MEASUREMENT | 0.95 | config | low | Everything else is already cheap: page_selection 0.47s, stories 1.5s, knowledge_gate 0.17s, validation 0.27s, metadata 54ms, rende | ~0 (bounded by parallelism) |
| M3-ttl-shorter-than-probe | MEASUREMENT | 0.90 | config | low | Probe cache TTL (120s) is shorter than the probe itself (~184s) ? cache can never amortize runs spaced >2min | -180s for each converted miss; at current traffic ~48% of runs affected |
| M4-e2e-post-fix-baseline | MEASUREMENT | 0.90 | config | low | Post-fix e2e ground truth: run p50 81.7s / p90 346.9s; best interactive proxy (low-overlap) p50 30.5s; frame p50 1.68s | n/a (baseline) |
| M9-executor-rtt-floor | MEASUREMENT | 0.90 | config | low | Executor: 37.3 neuract queries per card at p50 58ms over a 15.6ms-RTT tunnel ? ~0.6s/card is pure round-trip floor | reference: full batching bound ~ -0.5s/card p50, more at p90; -1-3s on frame p90 (7.9s) |
| M10-l2-emit-catalog-chatter | MEASUREMENT | 0.90 | config | low | L2 emit does 96 cmd_catalog + 6.6 neuract queries per card (~0.7s/card aggregate) ? real but second-order next to decode | bound: -0.7s/card if fully prefetched |
| M14-frames-clean | MEASUREMENT | 0.90 | config | low | /api/frame re-fetches are already fast and probe-free: p50 1.68s / p90 7.9s; frames pay 13 target_version1 queries TOTAL across 26 | bound: -2-4s at frame p90 via batching; p50 already 1.7s |
| M15-per-run-economics | MEASUREMENT | 0.90 | config | low | Per-run p50 economics: 10 LLM calls, 98,172 prompt tokens, 5,928 completion tokens, 638 DB queries | n/a (baseline) |
| M5-prefix-cache-off | MEASUREMENT | 0.85 | config | low | vLLM prefix caching is OFF (enable_prefix_caching=False, hybrid-mamba model) ? and the prompt has a cache-busting timestamp at cha | <=1s/card => <=2s wall on a 5-card page (2 waves); small vs M1/M2 |
| M7-recurrence-ceilings | MEASUREMENT | 0.85 | config | low | Cache-hit ceilings: 30.3% of runs are exact-repeat prompts; 94.2% of card emissions recur on (page_key, card_id); 0% byte-identica | ceiling: -36.6s L2 wall on a repeated 5-card page |
| M11-basket-decode | MEASUREMENT | 0.85 | config | low | 1b basket call: p50 6.4s / p95 20.4s, decode-bound (862-1,585 completion tok at ~104 tok/s) | reference: -3s p50 / -10s p95 per 50% completion cut |
| M13-no-retries-no-queue | MEASUREMENT | 0.85 | config | low | No LLM retry storms and no vLLM queueing in the window: 100% attempt=0; queue 0.238s avg; 0 preemptions ? the client emit_concurre | reference for concurrency proposals: 8-card page ideal-1-wave bound = 25.8s -> ~19-22s IF per-stream decode holds (uncertain) |

### db-layer

| id | verdict | conf | effort | risk | finding | saving |
|---|---|---|---|---|---|---|
| DB-1 | CONFIRMED | 0.97 | small | low | value_probe ORDER BY ::timestamptz defeats both live indexes -> 20-30s seq-scan chunks (the 1b p95-200s tail) | Slightly less than claimed at the floor, more at the fleet level. Per-chunk: 20-28s -> 0.1-1s (NOT <0.1s universally): 62/302 gic tables lack the ts_imm express |
| DB-12 | UNVERIFIED | 0.95 | config | low | VERIFIED NON-ISSUE: psql subprocess spawns are gone from the hot path (mined 10,982 spawns predate the pool ship) | 0 (verification finding) |
| DB-2 | UNVERIFIED | 0.92 | small | low | value-probe cache keyed by frozenset(table-set) + 120s TTL - repeat prompts and multi-asset lanes re-pay full probes | With DB-1 unfixed: -20..-185s per cache-expired or per-lane replay; with DB-1 fixed still removes ~0.1-0.5s + RTT floors per re-probe and stops multi-asset over |
| DB-3 | UNVERIFIED | 0.90 | small | low | neuract 'pool' is ONE shared psycopg2 connection - the entire executor DB leg serializes | 5 cards x ~6s summed serialized ~= 25-30s exec DB wall -> (30s x 25/60 per-query speedup)/4 lanes ~= 3s: -15..-25s wall on DB-heavy exec pages, -3..-6s typical; |
| DB-5 | UNVERIFIED | 0.90 | small | low | col_dict 1b samples and validate data reads use the same cast-defeating ORDER BY | -0.5..-2.2s per cold 1b on large-table assets; validate tail -1..-100s on pathological runs |
| DB-6 | UNVERIFIED | 0.90 | small | low | Per-table information_schema probes at ~78ms each (~35/run) vs one 35ms whole-schema fetch | 35 x 78ms = 2.7s -> 1 x 35ms: -2..-3s per cold page; also removes contention pressure on the single conn (compounds with DB-3) |
| DB-8 | UNVERIFIED | 0.90 | config | low | 62 gic tables missing the ts_imm expression index (7 missing even the plain text index) | same arithmetic as DB-1 per read; worst-case cards on big un-indexed tables -1..-10s |
| DB-4 | UNVERIFIED | 0.85 | medium | medium | window() issues 2 round trips and fans out per-member x per-column-set (N+1 over the 16ms tunnel) | 28-member card: 56 RTs x ~50ms -> 2 RTs x ~120ms = -2.5s per aggregate card; typical page (~72 window calls) -1.8s summed / -0.5..-1s wall |
| DB-7 | UNVERIFIED | 0.85 | config | low | Per-leaf cmd_catalog policy/template reads - 24-25k repeats of constant keys; hot keys fixable config-only | -10..-13s on worst multi-card runs, -0.5..-2s typical page |
| DB-11 | UNVERIFIED | 0.85 | small | low | latest_ts freshness re-read per card for the same table (no cache) | -0.5..-0.9s per multi-card page |
| DB-9 | UNVERIFIED | 0.80 | config | medium | neuract.statement_timeout_ms = 0 - unbounded query tail (observed 104.6s single query) | tail capping: -90s on worst runs (215s probe tails -> 15s honest degrade) |
| DB-10 | UNVERIFIED | 0.75 | medium | low | One full-window LAG scan per flag column; edge_count + bucketed_edges double-scan the same data | -0.4..-0.5s per events-heavy card |

### executor-fill

| id | verdict | conf | effort | risk | finding | saving |
|---|---|---|---|---|---|---|
| EXEC-1 | CONFIRMED | 0.95 | small | low | Single shared neuract connection serializes the entire 8-way card fan-out (and /api/frame bursts) | -25s exec wall on the 4-panel-card page (45s budget-clipped, true 48.4s -> ~20s: slowest card 643q x ~30ms measured-solo + non-DB overhead; claim's 17s used 25m |
| EXEC-14 | CONFIRMED | 0.95 | config | low | Dead end (measured): post-fill CPU pass chain is negligible ? do not fuse passes | 0 confirmed (negative finding). Ceiling if anyone fused all CPU passes anyway: ~15-25ms/card on the largest payloads, ~5-10ms typical ? 0.1-0.2% of layer2_card  |
| EXEC-2 | CONFIRMED | 0.90 | medium | medium | member_delta issues 4 sequential endpoint queries per member per delta key ? batchable to ~4 statements per slot-window | Worst panel-power card (card 14): 52.7s -> ~6-9s with batching alone (4-7 UNION statements x ~1.0s each, ::timestamptz cast kept) = -44 to -47s; -> ~2-4s only w |
| EXEC-9 | CONFIRMED | 0.90 | config | low | _context_vals recomputes panel_kwh (~112 queries) though agg_row already holds the identical value | Removes exactly ONE duplicate panel_kwh per roster card that has any aggregates/scalar/entries/group_agg/sankey slot: measured -1.65s/card on a 28-member panel  |
| EXEC-11 | CONFIRMED | 0.90 | config | low | _field_value re-queries latest() per field when the batched latest row holds NULL for that column | Per affected card: ~0.07-0.4s typical (1-5 re-reads x 74-210ms, serial inside the card's fill loop), up to 1-3s wall on heavy dark-meter cards. Per run: p50 0.9 |
| EXEC-3 | CONFIRMED | 0.85 | small | low | No memoization: identical member/delta reads re-executed per slot, per card, and per /api/frame | Corrected duplicate cost: 734 dup executions / 72.7s of 142.2s summed SQL on the cited slow-tunnel trace (auditor's 867/114.6s over-counted by keying on sql tex |
| EXEC-6 | CONFIRMED | 0.85 | small | low | Multi-asset compare fills assets sequentially ? one full executor round per asset | -2s p50 / -7s p90 / up to -31s worst-case on real compare traces (measured sum-minus-max of executor spans per trace, n=93) ? NOT -15 to -30s p50. As a fraction |
| EXEC-5 | CONFIRMED | 0.85 | medium | low | bucketed() reads one column per query; a multi-column scan is measured FREE | Per observed 2-key 30-member panel trend card: 60->30 queries saves ~1.0-2.7s (half of measured 2.1-5.4s bucketed time); the claimed 3-key 28-member -2.2s is co |
| EXEC-7 | CONFIRMED | 0.85 | small | low | rows(): 28 sequential latest-row reads per panel card ? one UNION ALL statement suffices | Per 28-32-member panel card: ~0.45-0.5s uncontended floor (0.5s -> 0.02s), 1.5-3.3s in real contended page runs (median ~2s observed, slightly above the claimed |
| EXEC-10 | CONFIRMED | 0.85 | config | low | freshness.apply queries latest_ts once per card ? identical across all cards on one table | Executor freshness/backfill leg (the finding as stated): p50 ~0s, p90 ~0.5s, max ~2.7s per page-run ? the claimed -0.2 to -1s is the p75-p95 band of RTM/multi-a |
| EXEC-4 | CONFIRMED | 0.80 | medium | low | /api/frame date change re-runs the FULL member fan-out per card with zero reuse | Combined stack (EXEC-1 pool + EXEC-3 memo + EXEC-4): 4-6-card panel-page date-pick settle 9-20s observed -> ~2-3s with a real neuract checkout pool alone (each  |
| EXEC-13 | CONFIRMED | 0.70 | config | low | Exec budget (45s) fires on queue time, not card work ? spurious honest-blanks trigger user re-runs | Standalone saving is small and mostly NOT latency: converting the 3-per-182-prompt (1.6%; 4.5% of panel prompts) budget blanks into completed cards costs +3..15 |
| EXEC-8 | UNVERIFIED | 0.75 | medium | medium | Event KPIs: sequential LAG raw-row scans per member per flag column; full-table when window is open | -2 to -4s per event-timeline panel card (28 scans -> 1 batched statement ~0.3s) |
| EXEC-12 | REFUTED | 0.80 | small | low | Recipe-less panel renderer rolls the same member power series twice (bucketed series + load factor) | ~0s in current production (path unreachable: non-routable pages + no card_payloads skeleton + valve 'on' sends all live panel cards through the roster interpret |

### host-orchestration

| id | verdict | conf | effort | risk | finding | saving |
|---|---|---|---|---|---|---|
| HOST-10 | UNVERIFIED | 0.95 | config | low | elapsed_ms and admin stage numbers hide/mislabel the real wait ? pre-pipeline serve work is invisible | 0ms directly; prerequisite for tracking every other fix honestly. |
| HOST-1 | UNVERIFIED | 0.90 | small | low | Registry has_data probe rides the serve path pre-flight: measured 184-188s before the pipeline starts, recurs every TTL expiry | -180s worst-case per affected request; cold single-asset dashboard 296s -> ~110s; picker open 187.8s -> ~2s. Arithmetic: probe 184.3s measured is pure serial pr |
| HOST-12 | UNVERIFIED | 0.90 | config | low | Verified non-issues / dead ends (do not re-spend effort) | ~-10ms per run maximum; documented so other lenses skip these. |
| HOST-5 | UNVERIFIED | 0.85 | small | low | Knowledge gate LLM is a serial prefix on every fresh dashboard prompt | -0.3 to -0.7s p50 on every fresh prompt; more under contention. |
| HOST-8 | UNVERIFIED | 0.85 | small | low | Response-tail synchronous persistence + double serialization before the body is sent | -15-55ms every request; most visible on /api/frame date-control re-fetches where total is ~1-3s. |
| HOST-2 | UNVERIFIED | 0.80 | medium | medium | Multi-asset compare: class lanes run serially, per-asset executor fills run serially, compare_mode LLM trails at the end | 3-class compare: 3 serial lanes -> 1 + max(2 parallel) = -30-90s (-60-180s at p90); same-class N-asset: -(N-1) x fill (-1-30s); compare_mode -0.3-1s. Target: RE |
| HOST-11 | UNVERIFIED | 0.75 | small | low | Concurrent prompts multiply vLLM emit pressure with no host-level admission control | prevents 2x-4x per-card emit inflation under concurrency (protects the 19.8s p50 per card from becoming 40-60s); required companion to HOST-2 lane parallelism. |
| HOST-3 | UNVERIFIED | 0.70 | medium | medium | L2 emit -> executor is an all-cards barrier; per-card pipelining hides the executor wall under the emit tail | min(executor wall, emit tail spread): -5.7s on the measured 5-card page; -10-30s on panel-overview pages with slow panel_aggregate fills. |
| HOST-6 | UNVERIFIED | 0.70 | small | low | Telemetry-only work on the critical path after L2: payload_final re-validate explains the 'notes' 28.6s max | -0.1s p50; -up to 28s on tail runs. |
| HOST-4 | UNVERIFIED | 0.65 | medium | medium | Repeat prompts and picker re-POSTs re-pay the full 1a route + L2 emit (p50 31.7s) though the shared-template injection mechanism a | picker leg 2: -3-5s (a) or ~-35s (b, 3s 1a + 31.7s L2 p50); repeat prompt: -35s p50. |
| HOST-7 | UNVERIFIED | 0.60 | small | low | Validate's pandas probe: un-indexed ORDER BY ts::timestamptz DESC LIMIT 500 over the tunnel is the 119s validate tail | -0.3s p50 when cached; kills the 119s tail. |
| HOST-9 | UNVERIFIED | 0.60 | small | low | No gzip on ~0.5MB responses ? matters only on VPN/WAN links | -60-70ms per response on remote links only. |

### l1a-path

| id | verdict | conf | effort | risk | finding | saving |
|---|---|---|---|---|---|---|
| L1A-06 | UNVERIFIED | 0.97 | small | low | Admin '1a' span is max(1a,1b) wall ? 1b's 120s tail is misattributed to 1a and 1b reads as 0ms | 0ms direct; prevents mis-aimed optimization of the 120s tail (which is 1b's probes, findings L1A-01/02) |
| L1A-01 | UNVERIFIED | 0.95 | small | low | has_data value probe ORDER BY "timestamp_utc"::timestamptz defeats the ts index ? cold asset_candidates() = 182.9s measured | 183s -> ~2-5s cold probe (8 chunks x (RTT 16ms + 40 index scans x 0.042ms)); ~-120s p90 on cold single-asset dashboards, -170s off asset_resolution p99 |
| L1A-02 | UNVERIFIED | 0.90 | small | low | TTL cache (120s) is shorter than the cold fill (183s), no single-flight, no refresh-ahead ? every >2min-idle prompt pays the cold  | -180s worst / -7s p50 (9.6s join -> ~2.5s warm path) on cold dashboards today; after L1A-01 still -2-5s p50 cold + stampede elimination |
| L1A-08 | UNVERIFIED | 0.90 | small | low | Knowledge gate is a serial prefix on every fresh prompt with a 120s worst-case timeout (no per-stage row) | -0.17s p50 / -0.3s p90 every fresh dashboard prompt; caps a 120s worst-case serial stall to 10s |
| L1A-15 | UNVERIFIED | 0.90 | config | low | Verified non-findings (dead ends) so other lenses don't re-dig: parallel primitive, degrade gate, stage logging, response dump, pr | n/a |
| L1A-03 | UNVERIFIED | 0.85 | medium | medium | run_pipeline_multi executes class lanes sequentially ? 3-class compares stack 3 full pipelines | 3-class: 3x140=420s -> 140+max(140,140)=280s = -140s (-33%); conservatively -100s p90 on RESPONSE_MULTI with L2 contention |
| L1A-04 | UNVERIFIED | 0.85 | small | low | Per-asset assemble_cards loop in the multi path is also sequential | -2.2s p50 / -15s p90 on 3-asset compares (N-1 x per-asset exec time) |
| L1A-05 | UNVERIFIED | 0.85 | config | medium | vLLM prefix caching is fully disabled: prefix_cache_queries_total == 0 (not a miss problem ? APC is off) | -0.4-0.5s per run on the 1a serial path; enables the L2-lens win of ~8 cards x ~2s prefill = ~16s/page (cite, not claimed here) |
| L1A-12 | UNVERIFIED | 0.85 | config | low | No timeout rows for route; stories at 120s ? 1a-lane worst case stacks to ~480s with parse retries | 0 at p50; caps 1a-lane worst case 480s -> ~120s (route raise already lands the honest data_unavailable terminal) |
| L1A-13 | UNVERIFIED | 0.85 | small | low | compare_mode LLM call sits on the multi serial tail after all lanes complete | -0.1s on multi compares |
| L1A-09 | UNVERIFIED | 0.80 | small | low | natural_compare_ids triggers the (cold-183s) asset_candidates probe serially before the pipeline, invisible to elapsed_ms | ~-2s (the 1a work overlapped) on cold prompts; primarily fixed by L1A-01/02 ? this closes the orchestration + observability gap |
| L1A-10 | UNVERIFIED | 0.80 | medium | low | granularity_reconcile re-fires the stories LLM (~1.9s) on the critical path ? fired in 43/634 runs (7%) | -1.9s on reconciled runs (7% of traffic); zero wasted stories call in variant (b) |
| L1A-07 | UNVERIFIED | 0.70 | small | medium | Picker re-POST and repeat prompts re-run a fully deterministic 1a (route+stories ~2.0s) from scratch | -2.0s on the picker re-POST join once 1b's pinned path is fast (today hidden behind basket ~6.4s ? pairs with the 1b-lens basket cache); -2.2s on repeat prompts |
| L1A-14 | UNVERIFIED | 0.70 | config | low | Reflect full-page re-route doubles the L2 pass when it fires ? rare (6/634) and correctly policy-gated; protect it with the shippe | removes most contention-induced reroutes: -30-40s on affected runs; also stabilizes l2_emit p95 under concurrent load (cross-lens) |
| L1A-11 | UNVERIFIED | 0.60 | medium | medium | Merge route -> stories into one guided_json call: two sequential LLM hops where decode dominates | -0.4-0.5s (one round trip + one 3.6K-tok prefill; total decode tokens unchanged) in 1a-bound scenarios |

### l1b-resolve

| id | verdict | conf | effort | risk | finding | saving |
|---|---|---|---|---|---|---|
| L1B-01 | UNVERIFIED | 0.95 | small | low | has_data probe (value_counts) ::timestamptz cast defeats the timestamp index -> 195 seq scans = 114-182s | -110 to -177s on any 1b run that triggers a cold/expired value_counts re-probe (114-182s -> 4.6s). This is the p95 200s driver: asset_candidates() runs at the t |
| L1B-05 | UNVERIFIED | 0.90 | small | low | real_table_cols runs 3x per basket build ? 2 redundant information_schema tunnel reads | -~120ms per 1b run (2 redundant tunnel info_schema reads x ~60ms). |
| L1B-02 | UNVERIFIED | 0.85 | medium | low | Persist a has_data snapshot in cmd_catalog (:5432, ~4ms) refreshed by a background cron instead of a live :5433 tunnel probe | -4.6s per re-probe request even after L1B-01 (4.6s tunnel probe -> ~4ms local read), plus eliminates the flap-induced data_unavailable false terminals. Compleme |
| L1B-04 | UNVERIFIED | 0.85 | small | low | window_nonnull / latest_nonnull carry the same index-defeating ::timestamptz cast on the resolved table | -up to ~2s on single-asset runs that resolve a large meter (the 8 pqm_transformer_* incomers, 375k rows each); ~0 on small tables. |
| L1B-06 | UNVERIFIED | 0.85 | small | low | asset_candidates() is built twice per resolve_asset (2nd via class_from_subject->_known_classes) | -tens of ms per resolve (python rebuild + one redundant pcc_panel_alias query); larger if the value cache is cold. |
| L1B-03 | UNVERIFIED | 0.80 | medium | medium | Cache the basket LLM output by (prompt, column-dict fingerprint) ? picker re-POST and repeat prompts re-pay 6.4s | -6.4s p50 (up to -20s p95) on the picker re-POST round trip and on repeat prompts; -6.4s per additional distinct class on a multi-class compare (lanes run seque |
| L1B-07 | UNVERIFIED | 0.80 | small | low | Static pcc_panel_alias table (28 rows) queried ~5x uncached per resolve | -~20-40ms per resolve (5 static reads x ~4ms), more when the 2nd asset_candidates re-fires them. |
| L1B-08 | UNVERIFIED | 0.55 | config | low | asset_resolve stable 5.9K-token listing prefix shows 0% prefix cache (cross-lens note) | -~0.3-0.5s per asset_resolve when prefill is cached (5.9K tokens / 10,440 tok/s ~= 0.57s prefill saved on a hit); small vs the 182s and 6.4s levers above. |

### l2-emit-diet

| id | verdict | conf | effort | risk | finding | saving |
|---|---|---|---|---|---|---|
| L2E-13 | UNVERIFIED | 0.90 | config | low | REFUTED/dead-end ledger: card-batching in one completion; exact_metadata diff already shipped; retries not a cost | 0 (guardrail finding) |
| L2E-1 | UNVERIFIED | 0.85 | medium | low | Roster output contract: emit a DIFF (column choices only), not the full retyped recipe | Sampled 1,310-char roster -> ~450-char diff (-66%). p50 roster card: -200 ctok x 10.25ms = -2.0s; p95: -1.4K ctok = -14s; the 90-130s p99 emits collapse to <25s |
| L2E-3 | UNVERIFIED | 0.75 | config | medium | Kill the 5-card wave cliff: raise layer2.emit_concurrency to page size, guard with llm.global_concurrency | 5-card page: 5x1,291=6,455 decode tok at ~300-360 tok/s aggregate = ~20s + staggered prefill = 23-25s vs measured 36.6s -> -12s p50. 8-card: 10.3K tok/~400 tok/ |
| L2E-2 | UNVERIFIED | 0.70 | config | medium | vLLM prefix caching is engine-DISABLED (hybrid linear-attention model) ? opt in | Per 5-card page: 4 x 10.5K tok shared prefix = 42K tok = ~4.0s GPU freed into decode; cross-run the system prefix becomes a permanent hit (KV usage peaks 13%, p |
| L2E-6 | UNVERIFIED | 0.70 | medium | medium | Parallelize multi-asset: class lanes AND per-asset assembles run sequentially | 2-class compare: -(lane2 wall) = -40-60s p50; 3-asset same-class: -2x assemble = -4-15s p50 and large p90 tail compression (683s p90 has lanes stacked end-to-en |
| L2E-8 | UNVERIFIED | 0.65 | large | medium | Break the emit->exec barrier: fill each card as its emit lands; optional SSE first-card | -1.1s p50 / -7s p90 page wall (exec fully hidden under the L2 wall). With streaming: time-to-first-card ~15-20s vs 37.8s e2e p50. |
| L2E-4 | UNVERIFIED | 0.60 | medium | medium | Semantic emit-recipe cache: memoize the deterministic per-card AI call for repeat traffic | Hit = -19.8s p50 for that card; fully-hit repeat page: L2 wall 29s -> ~1s. Fleet floor 9.6% = -1.9s/card avg; realistic production repeat traffic 30-60% = -6-12 |
| L2E-7 | UNVERIFIED | 0.60 | small | medium | Morphs-native system prompt: 96% of calls still carry the superseded full-author PART 2 text | -3-4K prompt tok/card = -0.3-0.4s GPU prefill each, -1.5-2s per 5-card page, longer shared prefix for L2E-2, and removes a documented envelope-confusion failure |
| L2E-11 | UNVERIFIED | 0.60 | small | low | Cache the composed system-prompt base + recovery-library catalog per process | -0.2-0.5s per card, -1-2s per 5-card page. |
| L2E-12 | UNVERIFIED | 0.60 | config | low | Tighten llm.timeout.l2_emit after the completion diet | -60s on timeout-path runs (rare but p99-visible). |
| L2E-10 | UNVERIFIED | 0.55 | small | medium | User-message micro-diet: compact skeleton JSON, smaller swap pool, earlier sibling-slot compaction | -1-1.5K prompt tok/card = -0.1-0.2s GPU each, -0.5-1s per page at fan-out, smaller KV per request (helps L2E-3 headroom). |
| L2E-5 | UNVERIFIED | 0.50 | config | medium | MTP speculative decoding ? the model ships its own draft head, decode is 13.2s of the 19.1s p50 | Typical MTP acceptance 60-75% -> 1.5-2x decode -> -4.5-6.5s p50 per card, -5-10s page wall; p95 2.8K-ctok cards -14-20s. Compounds with L2E-3 (aggregate through |
| L2E-9 | UNVERIFIED | 0.50 | small | low | Terse-prose completion knobs: cap why/data_note length | -50-150 ctok/card = -0.5-1.5s p50 per card. |

### multi-compare

| id | verdict | conf | effort | risk | finding | saving |
|---|---|---|---|---|---|---|
| MC-1 | UNVERIFIED | 0.95 | small | low | Registry/has_data probe family: cold cost (181s measured) exceeds its own TTL (120s) and is paid 1-3x serially per compare | -170s to -350s on cold-cache compares (441.7s run -> ~90-120s); arithmetic: 172s (resolve_assets) + 179s (lane 1b) removed when warm; chunk-parallel alone: 181s |
| MC-13 | UNVERIFIED | 0.95 | config | low | Dead ends verified (do not re-chase): multi-path python is negligible; lane-fold-by-schema would not have helped the worst run | 0 |
| MC-6 | UNVERIFIED | 0.90 | config | low | compare_mode LLM call is a serial tail on every multi response, unbounded to 120s | -1-2s p50 on every multi run; caps a 120s tail |
| MC-9 | UNVERIFIED | 0.90 | small | low | Telemetry lies: admin RESPONSE_MULTI p90 683s / max 835s are cross-execution pairing artifacts, and elapsed_ms hides the pre-fligh | 0 direct ? prevents chasing phantom regressions and exposes the real 175s pre-flight for MC-1/MC-5 tracking |
| MC-4 | UNVERIFIED | 0.85 | small | low | Per-asset executor fills are sequential (and each serializes an in-exec narrative LLM call) | -4.6s measured on 2-panel run (16.5->11.9s); -10 to -25s on 3-panel compares (cold member caches + 3 narrative calls overlap); pathological 270s -> 45s |
| MC-2 | UNVERIFIED | 0.80 | medium | medium | One giant L2 roster-card emit (14,614 completion tokens) = 118.6s of the worst post-fix multi run (142.1s) | -95 to -100s on panel-overview compares: 14,614 -> ~2,000 toks at 123 tok/s = 118.6s -> ~16s; run e2e 142.1s -> ~45s. Cross-ref layer2 lens (applies to single-a |
| MC-5 | UNVERIFIED | 0.80 | small | low | Natural-compare pre-flight resolutions are discarded, then re-derived ? and the whole pre-flight is invisible to elapsed_ms | ~0s warm; -170 to -350s cold (multiplies with MC-1: it is the difference between 1 and 3 cold probes per request) |
| MC-8 | UNVERIFIED | 0.80 | small | low | Knowledge gate serializes ahead of every fresh compare prompt | -0.2 to -0.7s p50 on fresh compares |
| MC-3 | UNVERIFIED | 0.75 | medium | medium | Class lanes run sequentially: k classes = k x (1b + validate + L2 wall), purely additive | -35 to -47s on a healthy 2-class compare (2x~40s lanes -> max ~45s); -70-90s on 3-class; trace A: -47.5s. Worst case (vLLM decode-bound) saving shrinks to the n |
| MC-10 | UNVERIFIED | 0.70 | medium | medium | No recipe reuse on repeat prompts ? every re-POST re-pays k x L2 wall | -35 to -120s per repeat compare (trace C: 142.1s -> ~20s = probes + exec only) |
| MC-7 | UNVERIFIED | 0.70 | small | low | Picker round trip redoes 1a (and probe slots) from zero on the re-POST | -6 to -9s per picker->compare round trip (plus MC-1/MC-5 probe warmth) |
| MC-11 | UNVERIFIED | 0.60 | medium | low | Lanes 2+ re-pay full ~26-28K-token prefill per emit ? 0% vLLM prefix-cache hits | ~-10s per additional class lane + ~-2s/card within a lane |
| MC-12 | UNVERIFIED | 0.60 | medium | medium | Bus-section 2-lane compares fill the same panel twice | -4 to -12s on section compares (rare path) |

### obs-overhead

| id | verdict | conf | effort | risk | finding | saving |
|---|---|---|---|---|---|---|
| OBS-8 | UNVERIFIED | 0.95 | config | low | Admin 'notes MAX 28.6s' is a mislabeled second L2 emit wave (reflect re-route), hiding 17-29s from the right owner | 0s directly; exposes 17-29s/occurrence re-route waves for the reflect-loop lens to attack |
| OBS-12 | UNVERIFIED | 0.95 | config | low | Confirmed NON-issues: pg sink already async; cfg gates cached; no fsync; console/journald trivial; obs does not cause the 0% prefi | 0s (scope-closing finding) |
| OBS-1 | UNVERIFIED | 0.90 | small | low | Per-query db events unsampled: 51k synchronous telemetry events on worst multi-asset runs | -3.5s on worst multi-asset compares; -50ms on 5-8-card panel pages; obs_db_queries growth cut 10-20x |
| OBS-7 | UNVERIFIED | 0.90 | small | low | Replay bundle written synchronously at the response boundary | -13ms p50 every request, -30ms on big compares |
| OBS-10 | UNVERIFIED | 0.90 | config | medium | Kill-switch floor already exists and is DB-tunable (documented lever for incident latency) | -5 to -6s worst RESPONSE_MULTI / -140ms panel page when flipped (incident mode) |
| OBS-2 | UNVERIFIED | 0.85 | small | low | Replay capture encodes EVERY query's full result rows on the hot path | -1.4s on worst multi-asset compares, -50ms on panel pages, -100MB+ heap (GC pauses unquantified) |
| OBS-6 | UNVERIFIED | 0.85 | small | low | sql_<rid>.jsonl leg is a redundant second synchronous write per query | -0.4s worst runs, -23ms panel page, -239MB disk |
| OBS-3 | UNVERIFIED | 0.80 | medium | low | jsonl sink does open/write/close per event under one global lock | -1 to -2s on 51k-event worst runs; -25ms on panel pages; removes cross-thread telemetry serialization |
| OBS-11 | UNVERIFIED | 0.80 | small | low | Failures channel: 5.6k open/append/close cycles on validation-heavy runs | -0.08s on validation-heavy multi-asset runs |
| OBS-4 | UNVERIFIED | 0.75 | small | medium | Every LLM call's full bodies captured FOUR times (three synchronously) | -0.6s on worst multi-asset runs; -710MB disk; -50MB worst-run heap |
| OBS-5 | UNVERIFIED | 0.70 | small | low | Trace lock acquired twice per event (attribute + next_seq) | -0.5 to -1s on 51k-event worst runs; negligible at p50 |
| OBS-9 | UNVERIFIED | 0.60 | medium | low | Inspector fallback parses up to 38MB trace jsonl inside the host process GIL | avoids intermittent 1-5s stalls of concurrent live runs during inspector use |

### streaming-perceived

| id | verdict | conf | effort | risk | finding | saving |
|---|---|---|---|---|---|---|
| S10-progress-ticker | CONFIRMED | 0.95 | small | low | RunningCard is a dead spinner for up to 11 minutes ? a file-backed progress poll costs nothing | 0s wall-clock (as claimed ? this is purely perceived latency). Converts a 41s-median dead wait (p90 143s single; multi tail 4-23 min wall observed, 7.4 min max  |
| OBS-admin-1a-span-verified | CONFIRMED | 0.95 | small | low | VERIFICATION: admin stage '1a' = max(1a,1b) join and EXCLUDES the pre-flight gap ? console understates user-perceived latency | 0s direct (accounting fix) ? as claimed. What it unhides, quantified: (a) inside console '1a' p50 9.6s, ~6-7s is the 1b lane (basket LLM p50 6.4s + has_data pro |
| S3-natural-compare-preflight | CONFIRMED | 0.90 | medium | medium | natural_compare_ids runs serially BEFORE the pipeline and can burn 3+ minutes of blank spinner | Time-to-cards from the proposed de-serialization alone: ~-2 to -3s p50, ~0 to -5s p90 (NOT -186s p90 -- the shared probe stays on 1b's critical path; pinned run |
| S2-early-page-shell | CONFIRMED | 0.90 | medium | low | Page shell (page_key/layout/card list) is final at ~10s but renders at ~42s ? ship a two-phase response even without full streamin | -31s p50 / -61 to -65s p90 time-to-first-meaningful-paint (measured per-trace delta: 30.7s p50, 65.0s p90, n=102 healthy traces), on healthy UNCONTENDED single- |
| S8-vite-dev-mode-in-prod | CONFIRMED | 0.90 | config | low | Production FE served by `npx vite` dev mode ? 250 module requests / 5.3s load; a built bundle exists unserved | -5.5s per first load / hard refresh on localhost (measured: 5,609ms dev vs 113ms built ? larger than the claimed 5.3s baseline because load-event, not FCP, is t |
| S15-resolved-popup-extra-click | CONFIRMED | 0.90 | small | low | After a picker pick the finished dashboard hides behind a manual 'Open dashboard' click | -1-3s + 1 click per single-asset picker completion for an attentive user; UNBOUNDED (tens of seconds to minutes) when the user tabs away during the 13-35s leg2  |
| S9-no-gzip | CONFIRMED | 0.90 | small | low | No gzip on :8770 JSON responses (8-11x compressible, 490KB worst) | Per-response, network-leg only: ~34ms on 100Mbps LAN, ~170ms-2.3s on 5-20Mbps/1.5Mbps VPN for the 490KB worst case (p90 190KB scales to ~13ms LAN / 65-890ms VPN |
| S1-progressive-card-streaming | CONFIRMED | 0.85 | large | medium | Monolithic JSON response ? stream shell + per-card NDJSON instead | First paint (shell): -31.7s p50 (9.8 vs 41.5) / -63.9s p90 (17.9 vs 81.8) ? CONFIRMED, but only in the healthy no-queue regime (104/228 = ~46% of ok runs). Firs |
| S7-multi-asset-serialization | CONFIRMED | 0.85 | medium | medium | Multi-asset compare: class lanes AND per-asset exec assembles run sequentially, plus a trailing compare_mode LLM call | (a) parallel per-asset fills: -4 to -8s p50 / ~-11 to -16s avg on a 3-same-class compare, up to -40s+ on panel-heavy p95 fills; applies to ~68% of live multi ru |
| S5-frame-fanout-and-pending-ux | CONFIRMED | 0.85 | small | low | /api/frame date-change: one POST per card (browser 6-connection cap) and zero pending/error UI | Split the two sub-proposals. (a) Per-card in-flight overlay + error badge: unconditional, page-size-independent ? perceived feedback at 0s and un-swallows error |
| S12-knowledge-gate-serial | CONFIRMED | 0.85 | small | low | Knowledge-gate LLM call is serial before every fresh prompt's pipeline | -0.17s p50 / -0.29s p95 per fresh dashboard prompt (obs-measured dashboard-verdict gate latency, n=310), NOT -0.3-0.7s. Saving is fully realizable since 1a//1b  |
| S16-repeat-prompt-recipe-reuse | CONFIRMED | 0.80 | medium | medium | Repeat prompts recompute 1a + every L2 emit; cache the AI recipe, re-fill only data | Per repeat prompt (same prompt+asset within TTL): p50 42.0s -> ~4-6s = -36s p50 (slightly BETTER than the claimed -32s); p90 residual ~24s (executor-bound). Pan |
| S13-exec-waits-for-last-emit | CONFIRMED | 0.80 | medium | medium | Executor fills start only after the LAST L2 emit ? pipeline them per-emit | Standalone: -1.7s p50 / -3.5s p75 / -5.8s p90 e2e (optimistic upper bound; each fill starts at its own emit end). As S1 prerequisite: first-card perceived laten |
| S6-site-probe-per-poll | CONFIRMED | 0.80 | small | low | /api/site LIVE probe hits :5433 per poll per client (15s header + 12s outage cadence) | Zero on prompt->cards e2e latency (background polling, off the user-perceived path; e2e p50 37.8s is l2_emit-dominated). Healthy state: ~10-12ms server work x 4 |
| S4-picker-repost-recompute | REFUTED | 0.90 | small | low | Picker re-POST recomputes 1a (and 1b candidates) from zero for the identical prompt | ~0s p50, ~1.1s p90, <=2.5s max per picker interaction (only the 12% of legs where the 1a re-run outlasts the parallel pinned-1b basket call). Not -1.4-6.1s p50  |

### vllm-serving

| id | verdict | conf | effort | risk | finding | saving |
|---|---|---|---|---|---|---|
| VS-10 | UNVERIFIED | 0.95 | config | low | Refuted hypotheses (verified negative results ? do not spend effort here) | 0s directly; prevents misdirected work |
| VS-4 | UNVERIFIED | 0.90 | config | low | llm.max_tokens unbounded ? 14.6K-token runaway emissions burn the full 150s timeout and poison concurrent cards | -80s wall on affected runs (p95-p99 tail); removes the sibling-card decode-contention poisoning; zero effect on p50 (p99 legit completion untouched) |
| VS-9 | UNVERIFIED | 0.90 | config | low | Output-token economics: 1 completion token costs ~170 prompt tokens ? redirect all prompt-trimming effort to completion-shrinking | Frame-level: each 100 completion tokens removed = ~1-1.6s per card at measured per-req decode rates |
| VS-2 | UNVERIFIED | 0.70 | small | medium | Roster cards retype the DB-known roster_spec verbatim in the completion ? ~390 wasted output tokens on 38% of emits | -330 tok => -3.3 to -5.3s per roster card p50; 5-card panel-overview page with 4 roster cards at c=4: -13 to -21s of decode GPU time => -4 to -8s page wall p50 |
| VS-3 | UNVERIFIED | 0.70 | config | medium | Prefix caching disabled on :8200 (hybrid-model conservative default) ? prompts are already APC-shaped, server never got the flag | ~10.5K tok cached per call: -0.4s solo, ~-1.2-1.6s per 4-card wave via removed prefill contention => -2.5 to -3s p50 on an 8-card page; gate-reject retries and  |
| VS-1 | UNVERIFIED | 0.65 | config | medium | MTP speculative decoding available but not enabled (checkpoint ships draft head; decode is the dominant wall) | MTP x1.6-2.2 on decode (JSON emissions accept well): per-card decode 13s -> 6.5-8s => card p50 18.3s -> ~12s; 8-card page layer2 wall 31.7s -> ~20-22s (-10 to - |
| VS-6 | UNVERIFIED | 0.60 | config | low | Global vLLM admission control shipped but disabled ? multi-run fan-out collapses per-request decode to 39 tok/s | Multi-run: worst-card decode 33s+ -> ~21-23s and eliminates the timeout->reflect doubling cascade => est -15 to -30% on RESPONSE_MULTI p90 (683s -> ~480-580s) |
| VS-7 | UNVERIFIED | 0.60 | small | low | RUN:/CARD: header at the TOP of the user message busts cross-run prefix reuse for repeat/pinned re-runs | Only meaningful after VS-3: ~0.4s prefill per card + wave contention relief => -1.5 to -3s on a picker re-POST or repeated-prompt page |
| VS-5 | UNVERIFIED | 0.55 | config | medium | Raise layer2.emit_concurrency 4->8: measured serving headroom makes one wave beat two | 8-card page: measured extrapolation 31.7s -> ~24-27s layer2 wall (-5 to -8s p50) standalone; compounds with VS-1/VS-3 to ~14-18s |
| VS-8 | UNVERIFIED | 0.50 | config | medium | vLLM is 0.16.1rc1 (not the documented 0.17.1) ? upgrade + engine-tuning probes (--async-scheduling) | +5-15% decode => -0.7 to -2s per l2_emit card, -2 to -6s per 8-card page; also de-risks VS-1/VS-3 |
