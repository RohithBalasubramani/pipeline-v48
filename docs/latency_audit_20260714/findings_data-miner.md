# Latency Audit 2026-07-14 — LENS: ground-truth data miner

Role: MEASUREMENTS for the post-fix tree (Jul 12–14). Other lenses' claims are judged against these numbers.
All timestamps IST (+05:30). Sources: cmd_catalog obs_* (:5432), admin API :8790, vLLM journal, live psycopg2 RTT probes.

## Data inventory (verified)

| store | rows | window |
|---|---|---|
| obs_traces | 574 | 2026-07-12 02:52 → 2026-07-14 02:40 |
| obs_stage_events | 14,925 | same |
| obs_llm_calls | 3,442 | same |
| obs_db_queries | 311,757 | same |

obs_* store BEGINS 2026-07-12 02:52 — it covers exactly the post-fix tree; cleanly separable from the Jul 6–11 baseline.

## (a) Per-stage latency, Jul 12–14 (obs_stage_events, latency_ms NOT NULL)

| stage | n | p50 ms | p90 ms | p95 ms | max ms |
|---|---|---|---|---|---|
| layer2_card_ai (whole fan-out per run) | 304 | 28,870 | 49,732 | 63,108 | 150,212 |
| layer2_card_ai.card (per-card emit) | 1,255 | 19,202 | 36,613 | 42,948 | 150,210 |
| asset_resolution | 377 | 9,129 | **179,316** | 191,893 | 371,669 |
| story_selection | 424 | 1,540 | 2,616 | 3,132 | 8,090 |
| executor (per run) | 558 | 1,121 | 7,684 | 14,837 | 45,001 |
| executor.card | 1,909 | 1,038 | 6,841 | 12,814 | 52,683 |
| page_selection | 424 | 468 | 754 | 895 | 3,932 |
| validation | 380 | 272 | 422 | 486 | 819 |
| knowledge_gate | 317 | 166 | 271 | 344 | 3,437 |
| metadata_resolution | 1,252 | 54 | 95 | 120 | 1,816 |
| renderer | 489 | 4 | 87 | 952 | 1,996 |

All `legacy.*` events (legacy.layer2, legacy.L2.card, legacy.1a …) carry latency 0 — they are POINT events mirrored into obs, not spans. Duration lives in the file-backed admin store; pairing caveats in §(d).

KEY POST-FIX DELTAS vs Jul 6–11 baseline:
- l2_emit per-card p50 19.8s → 19.2s (unchanged; still dominates).
- asset_resolution: mined baseline p50 1.4s/p95 20.7s, LIVE was 22s median — now p50 9.1s but p90 179s / p95 192s / max 372s. The 1b tail is now the single worst per-run tail in the tree.

## (a2) E2E by trace kind + day + concurrency (obs_traces)

| kind | n | p50 | p90 | p95 | max |
|---|---|---|---|---|---|
| run | 310 | 81.7s | 346.9s | 544.4s | 758.1s |
| frame | 262 | 1.68s | 7.9s | 12.6s | 19.6s |
| replay | 2 | 123.6s | — | — | 247.2s |

run-kind by day: Jul 12 n=247 p50 59.5s p90 384.8s; Jul 13 n=45 p50 226.3s; Jul 14 n=18 p50 51.2s.
CAVEAT: the window is dominated by validation-campaign sweep traffic. Concurrency segmentation (overlapping run spans): solo n=91 p50 225.7s / high(3+) n=128 p50 188.4s / low(1-2) n=91 p50 30.5s — "solo" runs are mostly the sequential overnight sweep (heavy compare prompts), so solo≠interactive. The low-overlap bucket (p50 30.5s) is the best proxy for interactive single-prompt latency on the post-fix tree.

run e2e by n_cards (response_summary): 4 cards p50 81.7s; 5 cards n=60 p50 230.2s; 8 cards n=33 p50 204.4s; 9 cards n=21 p50 218.5s; 12 cards n=22 p50 47.3s (mixed sweep/interactive populations; treat as loads, not clean scenarios).

## (b) Token economics per LLM-call kind (obs_llm_calls, n=3,442, Jul 12–14)

| stage | n | lat p50 | lat p95 | prompt tok p50 | p95 | compl tok p50 | p95 | distinct sys prompts | eff. decode tok/s p10/p50/p90 |
|---|---|---|---|---|---|---|---|---|---|
| l2_emit | 1,289 | 18,304ms | 40,134ms | **21,734** | 27,080 | 1,291 | 2,762 | **2** (each ≥32,768B — obs clips at obs.llm.max_prompt_bytes) | 45 / **73** / 95 |
| basket | 308 | 6,382ms | 20,358ms | 1,867 | 1,935 | 862 | 1,585 | 1 (2,809B) | 56 / 104 / 153 |
| stories | 423 | 1,536ms | 3,128ms | 324 | 478 | 163 | 275 | 1 (439B) | 74 / 122 / 154 |
| asset_resolve | 630 | 579ms | 2,551ms | 2,690 | 11,500 | 25 | 186 | 3 | 19 / 50 / 86 |
| route | 388 | 472ms | 905ms | 3,619 | 3,685 | 28 | 42 | 2 | 37 / 68 / 87 |
| insight_narrator | 82 | 538ms | 1,115ms | 494 | 599 | 71 | 87 | 1 | 90 / 140 / 143 |
| knowledge_ems | 316 | 166ms | 344ms | 1,413 | 1,484 | 16 | 16 | 1 (5,352B) | 59 / 96 / 103 |
| compare_mode | 6 | 102ms | 108ms | 165 | 167 | 12 | 12 | 1 | 113 / 118 / 119 |

DERIVED FACTS (arithmetic shown):
- l2_emit is ~100% DECODE-BOUND: 1,291 completion tok / 73 tok/s = 17.7s ≈ the 18.3s p50. Prefill of 21.7K tok at ~10,000 tok/s prefill ≈ 2.2s. Completion length + decode throughput are the levers, not just prompt size.
- l2_emit system prompt is STABLE: only 2 distinct hashes across 1,289 calls, each ≥32,768 chars (~8K tokens). A working vLLM prefix cache would make ~8K of the 21.7K prompt tokens near-free on every call — yet journal reports 0.0% hit rate (see §vLLM). User part p50 21,224B (~5.3K tok) varies per call (1,289 distinct).
- basket completes 862 tok p50 at ~104 tok/s → 6.4s; p95 1,585 tok → 20.4s. Completion length is 1b-basket's lever too.
- Per-run LLM decode budget (5-card page): 5×1,291 l2_emit + 862 basket + 163 stories ≈ 7.5K completion tokens.

## (c) SQL economics (obs_db_queries, n=311,757, Jul 12–14)

By db+stage (top of table):

| db_name | stage | n | total_ms | p50 | p95 | max |
|---|---|---|---|---|---|---|
| target_version1 | (NULL — outside any stage span) | 1,677 | **35,931,042** | 22,539 | 28,389 | 104,608 |
| target_version1 | asset_resolution | 1,846 | **10,532,271** | 63 | 27,698 | 35,188 |
| neuract | executor.card | 71,258 | 5,367,508 | 58 | 204 | 2,576 |
| neuract | (NULL) | 18,562 | 879,332 | 16 | 158 | 1,474 |
| neuract | layer2_card_ai.card | 8,294 | 613,410 | 58 | 215 | 1,608 |
| cmd_catalog | layer2_card_ai.card | 121,075 | 215,996 | 3 | 3 | 75 |
| cmd_catalog | executor.card | 54,597 | 40,276 | 0 | 3 | 92 |

THE FULLNESS/VALUE PROBE IS THE #1 SQL COST: db=target_version1 (the :5433 tunnel DB; 'neuract' rows are the same physical DB labeled by schema path) — 3,523 UNION-ALL probe queries totaling **46,463 seconds** in 2 days. Query shape = data/value_probe.py:71-73 `SELECT '<tbl>',(SELECT count(*) FROM jsonb_each(x.r)...) FROM (SELECT to_jsonb(s) FROM neuract."<tbl>" s ORDER BY "timestamp_utc"::timestamptz DESC LIMIT 1) x UNION ALL ...` (chunk=40 tables).
- Per-run burden: p50 **104.7s**, p90 **347.9s**, max 903s of target_version1 probe time per 'run' trace (n=293). Sequential (slow asset_resolution spans show dbq_ms ≈ span wall, e.g. 371,172ms of DB in a 371,669ms span).
- ROOT CAUSE MEASURED: `ORDER BY "timestamp_utc"::timestamptz DESC LIMIT 1` cannot use either existing index → Seq Scan (43,430 rows) + top-N sort = **641.4ms** per table (EXPLAIN ANALYZE, gic_07_n8_circulation_pump_p1). The table ALREADY HAS `idx_..._tsimm ON (neuract.ts_imm(timestamp_utc::text) DESC)` and ts_imm = `SELECT t::timestamptz` (IMMUTABLE wrapper). Rewriting the ORDER BY to `neuract.ts_imm("timestamp_utc"::text) DESC` uses the index: **0.104ms** (6,164x). 40-table chunk: ~24s → ~tens of ms + 1 RTT.
- The stage-NULL 35.9M ms rows sit in 'run' traces (32.2M ms) — probes fired outside stage spans (multi-asset lanes / enrich paths), so per-stage views UNDERCOUNT 1b probe cost.
- Tunnel RTT measured live (10× SELECT 1, psycopg2): :5433 min 8.9ms / median 15.6ms / max 17.0ms; fresh connect 27.7ms. Local :5432: 0.01ms, connect 1.6ms. → every :5433 round trip carries ~16ms floor; executor.card p50 58ms ≈ RTT + work.
- Executor per card: 71,258/1,909 = **37.3 neuract queries per card execution** × 58ms p50 ≈ 2.2s sequential floor per card (matches executor.card p50 1.0s with some batching/overlap).
- L2 emit per card: 121,075/1,255 = **96 cmd_catalog queries per card emit** (p50 3ms ≈ 0.3s) + 8,294/1,255 = 6.6 neuract queries (58ms) ≈ 0.4s.
- Frame traces (n=262): p50 1.68s e2e; 68.7 neuract queries per frame at 46ms avg = 3.2s aggregate DB (overlapped).

## (c2) THE PRE-PIPELINE PROBE GAP — timeline proof

Reconstructed span timeline, t_4302e600f908455eb7f7d5e00b8b3a3d ("voltage and current for pcc panel 1", 5 cards, e2e 236.3s, Jul 14 01:44):

| phase | rel time | wall |
|---|---|---|
| request_received + knowledge_gate | 0.0 → 0.1s | 0.1s |
| **DEAD GAP (pre-pipeline)** | 0.1 → 183.8s | **183.7s** |
| PROMPT marker / 1a lane (page 0.4s + stories 1.7s) | 183.8 → 185.9s | 2.1s |
| 1b asset_resolution (parallel with 1a) | 183.8 → 193.6s | 9.8s |
| validation | 193.6 → 193.9s | 0.2s |
| layer2 fan-out (5 cards, conc=4: cards 18/19/20/21 start together, 22 starts when 20 ends) | 193.9 → 230.5s | 36.6s |
| executor (5 cards ALL concurrent) | 230.5 → 236.3s | 5.7s |

The gap contains exactly **9 stage-NULL target_version1 queries totaling 183,634ms** (obs_db_queries) + 1 knowledge_ems LLM call (139ms). These are the value_probe UNION chunks fired by host/server.py's natural-compare pre-flight: server.py → multi_asset.natural_compare_ids() → layer1b.resolve.asset_candidates.asset_candidates() → data/value_probe.value_counts() over the FULL registry (~370 tables / chunk=40 → 9-10 chunks × ~20.4s each), BEFORE run_pipeline starts. Identical pattern in t_0f16fca8e0cf49cdbb0b197df7f712ee (8 cards, gap 184.3s, e2e 232.2s).

Gap distribution across ALL 294 run traces (knowledge_gate end → PROMPT marker): p50 **1,505ms**, p90 **186,922ms**, max 533,030ms; **140/294 (48%) pay >10s**. Bimodal: _VAL_CACHE hit (TTL cache.resolution_ttl_s=120s) → ~1.5s; miss → ~180s+. The TTL (120s) is SHORTER than the probe itself (~184s), so any two runs >2min apart both pay full price — the cache can only amortize back-to-back runs.

## (d) Stage-span semantics — what admin numbers actually mean

Admin store (:8790, file-backed) durations are **event-spacing**: admin/latency.py:3-10 — "a record's duration = its ts minus the previous record's ts within one execution". Stage markers are END markers written by run/harness.py:
- "PROMPT" (harness.py:234) at run_pipeline entry — AFTER the host pre-flight gap (so admin NEVER sees the ~184s probe gap; it is invisible in the admin per-stage table AND partially inside RESPONSE elapsed only).
- "1a" (harness.py:280) is logged AFTER run_parallel joins BOTH the 1a AND 1b lanes → admin stage "1a" = PROMPT→join = **max(1a lane, 1b lane) INCLUDING 1b's in-resolver value probes**. Its p90 120s is 1b probe tail, not routing.
- "1b" (harness.py:285) immediately follows "1a" → always ~0ms. Same for "asset_gate".
- "layer2" (harness.py:135) is written right after the LAST "L2.card" marker → gap ≈ 0 → p50/p90 = 0ms artifact; its avg 17.3s comes from executions lacking L2.card records. "L2.card" values are spacing between consecutive card completions, not card durations.
- RESPONSE_MULTI is a single-record file → drops out of stage pairs by design (documented in admin/latency.py docstring).
AUTHORITATIVE per-stage numbers = obs_stage_events (real ts_start/ts_end pairs), i.e. §(a). Admin's honest field is per-run elapsed_ms only.

## (e) Repeat rates — cache-hit ceilings (Jul 12–14 run traces)

- Exact prompt repeats (lower/trim): 216 distinct prompts over 310 runs; 39 prompts ran ≥2×, covering 133 runs → **30.3% of runs** could be served by an exact-match response cache (94 runs beyond first occurrence). Caveat: window includes validation sweeps that repeat prompts by design.
- L2 emission recurrence: 1,021 card emissions → 59 distinct (page_key, card_id) pairs = **94.2% recurring**; adding asset_id: 67 distinct triples = **93.4% recurring**. True semantic-identity ceiling lies between 30.3% and 93.4% (emissions also vary by phrasing/date window).
- At the LLM level, 0% of l2_emit calls are byte-identical: all 1,289 user prompts DISTINCT. Measured cause: a live freshness anchor ("last=2026-07-14T01:53:54…") sits at char ~1,083 of a ~28.5K-char user prompt — common prefix between two emits of the SAME card = 1,083 chars (4%). Everything after the anchor is largely shared.

## (f) Concurrency traces (from §c2 timelines)

- L2 emit fan-out honors layer2.emit_concurrency=4: 4 cards start simultaneously; card 5 starts exactly at the first completion. 5-card L2 wall 36.6s (≈2 waves of p50 ~19s); 8-card wall 25.8s (shorter cards). At conc=4, wall ≈ ceil(N/4) × card-time; card-time itself inflates under batch (73 tok/s vs ~122-154 tok/s seen on light stages).
- Executor fan-out: ALL cards start concurrently (8/8 simultaneous starts); wall = slowest card (5.7-6.8s in the samples; executor.card p50 1.0s / p90 6.8s / max 52.7s).
- vLLM server is NOT the queue: request_queue_time avg 0.238s, 0 preemptions. The client-side semaphore (emit_concurrency=4) is the governing concurrency limit.

## (g) vLLM ground truth (:8200, /metrics counters since restart, n=1,237 requests)

- prompt_tokens_total 11.49M, generation_tokens_total 803K → avg 9,292 prompt / 649 completion tokens per request.
- Time split per request (sums/counts): queue 0.238s (3.3%) + prefill 0.483s (6.6%) + decode 6.514s (**89.4%**) ≈ e2e 7.29s avg.
- Effective PREFILL throughput = 11,493,821 tok / 597.8s = **19,226 tok/s**. l2_emit 21.7K-tok prompt → ~1.13s prefill/card.
- Effective per-request DECODE rate = 803,097 / 8,057.6s = **99.7 tok/s** average (l2_emit measured 73 tok/s p50 under conc=4; light stages reach 122-154).
- TTFT avg 0.774s.
- **enable_prefix_caching="False"** (vllm:cache_config_info) — Qwen3.6-35B-A3B is hybrid-mamba (mamba_block_size=65536 present); vLLM disables APC by default for hybrid models; unit flags don't pass --enable-prefix-caching. prefix_cache_queries_total=0 → 0.0% journal hit rate explained: the cache is OFF, not thrashing. Even if enabled, the char-1083 freshness anchor caps the cacheable prefix at ~system(≈8K tok)+~270 tok unless prompt parts are reordered. Prefill saving bound if sys prefix cached: 8.4K/19.2K ≈ 0.44s per l2_emit call — small vs 17.7s decode.
- KV capacity: num_gpu_blocks=912 × block_size 1056 ≈ 963K tokens.
- LLM call hygiene: 100% of l2_emit/basket/asset_resolve calls are attempt=0 (NO parse-retries in window); l2_emit params = temp 0.0, seed 42, response_format json_object, timeout 150s.

## (h) Per-run economics (obs_traces p50, kind=run)

10 LLM calls; 98,172 prompt tokens; 5,928 completion tokens; 638 DB queries (p90 1,244). Decode budget p50: 5,928 tok / ~100 tok/s ≈ 59s of serial decode if unbatched — emit fan-out at 4 brings the L2 share to ~ceil(N/4)×18.3s.

## Summary table — where a 5-card panel page's 236s actually goes (measured sample)

| component | wall | % | governing measured fact |
|---|---|---|---|
| pre-pipeline value probe (host preflight) | 183.7s | 77.8% | 9 UNION chunks × ~20.4s; seq-scan ORDER BY ::timestamptz; ts_imm index unused (641ms vs 0.104ms/table) |
| L2 emit fan-out (5 cards, conc=4) | 36.6s | 15.5% | 18.3s p50/card, 89% decode @73 tok/s, 1,291 compl tok |
| 1b asset_resolution | 9.8s | 4.2% | in-resolver probes + resolve LLM 0.6s |
| executor (concurrent) | 5.7s | 2.4% | 37 neuract queries/card @58ms (RTT floor 15.6ms) |
| 1a lane (page+stories) | 2.1s | — | parallel with 1b, hidden |
| validation+metadata+render+assemble | <1s | — | |

Dead ends checked: LLM retries (none in window); vLLM queueing (0.24s avg, not a bottleneck); admin "layer2 p50 0ms" (artifact, not a real regression); frame path probes (frames DON'T pay the value probe — 13 queries/217ms total across 262 frames).
