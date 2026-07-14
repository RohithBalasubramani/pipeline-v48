# Latency audit 2026-07-14 — LENS: Layer-2 emit (prompt diet / output diet / concurrency / caching / streaming)

READ-ONLY audit. All numbers measured this session unless cited from the task baselines.

## Ground truth measured (obs_llm_calls, 2026-07-12..14 window, n=1,289 l2_emit calls)

| metric | p50 | p95 | notes |
|---|---|---|---|
| l2_emit latency | 18,304 ms | 40,134 ms | 1 timeout (150s) in 1,289 |
| tokens_prompt | 21,734 | 27,080 | avg 22,335 |
| tokens_completion | 1,291 | 2,762 | p99 5,089; MAX 14,614 (118s!) |
| layer2_card_ai.card span | 19,202 ms | p90 36,613 | card overhead ≈ 0.9 s over the LLM call |
| layer2_card_ai (page fan-out) | 28,870 ms | p90 49,732 | |
| metadata_resolution | 54 ms | p90 95 | gates are NOT the cost |
| executor.card | 1,038 ms | p90 6,841 | runs ONLY after ALL emits (barrier) |

**Latency regression** over all 1,288 ok calls: `latency_ms = 8891 + (-0.14)*ptok + 10.25*ctok`
=> effective decode ≈ **98 tok/s**, ~8.9 s fixed intercept (queue wait at cc=4 + prefill + scheduling).
p50 decomposition: intercept 8.9 s + decode 13.2 s ≈ 19.1 s. **DECODE (completion size) is the dominant lever.**

**Wave cliff (cc=4)**: page p50 by n_cards — 3 cards 26.6 s · 4 cards 22.7 s · **5 cards 36.6 s** · 8 cards 37.2 s.
The 5th card costs +13.9 s p50 (second wave).

**Prompt structure** (measured by building `_system()` + sampling 120 real user prompts):
- data_instructions_v2.md raw: 50,497 chars (~12.6K tok). Composed system prompt: 46.8K–65.6K chars
  (11.7K–16.4K tok) depending on roster section + per-card recovery-library filter + morph-map override.
- Cross-card COMMON system prefix: 41,955 chars ≈ **10.5K tok** (variance starts at the roster marker).
- Biggest .md sections: PART 2 MORPH-EMIT 20,178 ch (5.0K tok), ROSTER 8,782 ch (2.2K tok, already conditional),
  R1–R14 ≈ 14K ch. morphmap/prompt.md override 8,483 ch is APPENDED while the superseded PART 2 still ships.
- User message p50 27.2K chars (~6.8K tok): db_schema+basket 5.7K ch, this_card 4.6K ch,
  metadata skeleton (json indent=1) 3.3K ch (p95 6.1K), slot_catalog 2.7K ch (p95 8.2K!), panel_members 2.7K ch,
  swap_candidates 2.2K ch, relevant_cols 1.8K ch.

**Completion composition** (300 recent parsed responses): di.roster p50 1,059 ch / p95 6,221 ch;
morphs p50 818 / p95 2,536; di.fetch 240; di.other 372; notes 199; swap_decision p50 2 (mostly keep).
Top-6 completions: 6.8K–14.6K ctok on cards 19/22/24 → 54–129 s single emits. emit.morphmap_mode is **ON**
(1,234/1,289 calls emit `morphs`; the 54 full-`exact_metadata` calls are no-default-payload cards, only 669 ctok).

**vLLM :8200 facts**: version 0.16.1rc1.dev5 (not 0.17.1). `vllm:prefix_cache_queries_total = 0.0` since boot
=> **automatic prefix caching is fully DISABLED at the engine**, not merely missing. Root cause: the model is a
HYBRID linear-attention MoE — HF config `layer_types = [linear_attention x3, full_attention] x10`,
`full_attention_interval 4`, qwen3_5_moe — vLLM disables APC for hybrid (mamba/linear-attn) models unless
explicitly opted in. The model ALSO ships an MTP head (`mtp_num_hidden_layers = 1`) — speculative decoding
is available in principle. GPU KV usage peaks ~13% (huge headroom at --gpu-memory-utilization 0.55).

**Retry machinery is NOT a live cost** in this window: all 1,289 calls attempt=0 (no parse retries);
gate_feedback_retry=true 0 times; swap→re-emit 37/1,252 cards (3.0%, ~+19 s on that slot);
legacy.reflect only 12 events (policy hard_failure + preflight reroute already killed most re-loops).

**Repeat traffic**: raw duplicate prompts 0.0% — the user message embeds `RUN: <run_id>` (user_message.py:189)
AND live data-window timestamps, so no two calls are ever byte-identical. After stripping volatile lines:
**9.6% semantic duplicates** (124/1,289) — and this window was dominated by the deliberately-mutated validation
corpus, so 9.6% is a floor. Other stages (no run-id in prompt) show 24–41% byte-identical dup (route 39.7%,
basket 40.6%, stories 38.1%) — those ARE trivially memoizable / prefix-cache friendly.

**Barrier (g) confirmed**: run/layer2_all.py runs ALL emits (run_parallel, cap 4) → swap_settle → returns;
host/server.py:63-94 only then calls assemble_cards (executor fan-out ≤8). Nothing downstream starts before
the last emit. Multi-asset: run_pipeline_multi (run/harness.py:409-416) runs class lanes SEQUENTIALLY; and
host/multi_asset.py:126-138 assembles per-asset SEQUENTIALLY.

---

## FINDINGS (ranked by estimated saving)

### F1 — Roster output contract: emit the DIFF, not the whole recipe (completion diet, the tail-killer)
- Evidence: completions decode at ~98 tok/s effective; di.roster p50 1,059 ch / p95 6,221 ch; worst emits
  6.8K–14.6K ctok = 54–129 s (cards 19/22/24 — exactly the panel-overview family). The AI retypes the ENTIRE
  roster_spec verbatim (sampled emission shows `id/panel/table/status/vocab/policy/r` all copied) even though
  user_message.py:281 says "your ONLY decision is the COLUMN inside col/delta/phase_mean/prefer_abs bindings"
  and gate_roster (build.py:154) already folds clean column choices in and BACKFILLS omitted recipe slots verbatim.
- Proposal: morph-map-style roster diff — emit per slot only `{binding_key: column | [cols] | null+short-why}`;
  gate_roster expands against the authoritative recipe row (machinery exists). Flag-gate like emit.morphmap_mode.
- Saving: sampled roster 1,310 ch → diff ≈ 450 ch (−66%). p50 roster card −200 ctok ≈ −2.0 s; p95 −1.4K ctok ≈
  −14 s; the 90–130 s p99 emits collapse to <25 s. Panel-overview 5–8-card pages: −10–30 s p95 page wall.
- Effort: medium. Risk: low (gate is already authoritative; per-leaf honesty unchanged; AI still decides bindings).

### F2 — Turn ON vLLM prefix caching (it is OFF because the model is hybrid linear-attention)
- Evidence: prefix_cache_queries_total = 0.0 (never queried); HF config layer_types hybrid; vllm.service has no
  --enable-prefix-caching; emit.py was engineered FOR a cacheable prefix (comments at emit.py:68-70/136-138) that
  never engages. Shared cross-card system prefix measured 41,955 chars ≈ 10.5K tok of a 21.7K-tok prompt.
- Proposal: add --enable-prefix-caching (vLLM hybrid-model APC / mamba block hashing — verify support in
  0.16.1rc1, else upgrade); verify with prefix_cache_hits_total > 0 and a pinned-seed determinism spot-check.
- Saving arithmetic: 5-card page prefill = 5×21.7K = 108K tok ≈ 10.4 s GPU at 10,440 tok/s; caching the 10.5K-tok
  shared prefix saves ~42K tok ≈ 4 s GPU per page, freed INTO decode during waves; cross-run the system prefix is
  a permanent hit (KV usage only ~13%) → −1–1.5 s TTFT/card. Est −3–6 s p50 page, larger at p95 under multi-run
  load; also helps route/stories/basket (24–41% byte-identical repeats).
- Effort: config (restart). Risk: medium only because hybrid-APC support must be verified on this build.

### F3 — Kill the 5-card wave cliff: emit_concurrency = page size, guarded by llm.global_concurrency
- Evidence: layer2.emit_concurrency=4 (layer2_all.py:69, DB knob). Page p50: 4 cards 22.7 s vs 5 cards 36.6 s —
  the 5th card queues a full second wave. Global admission control llm.global_concurrency already shipped
  (llm/client.py:107-130) but is 0 = disabled; the cc=4 cap was sized for cross-RUN contention, which the global
  semaphore now handles process-wide.
- Proposal: raise layer2.emit_concurrency to 8 (≥ max page size) AND set llm.global_concurrency ≈ 8–10 so sweeps
  can't stampede. Both are DB rows — config only.
- Saving arithmetic: 5-card page: total decode 5×1,291 = 6,455 tok at aggregate ~300–360 tok/s ≈ 20 s + staggered
  prefill ≈ 23–25 s vs measured 36.6 s → **−12 s p50 on 5-card pages**. 8-card: 10.3K tok / ~400 tok/s ≈ 26–30 s
  vs 37.2 s → −7 s. 4-or-fewer-card pages byte-identical.
- Effort: config. Risk: medium (per-request decode slows as batch grows; validate the 150 s fail-fast margin —
  worst-case card ctok tail must ALSO shrink via F1).

### F4 — Semantic emit-recipe cache (memoize the deterministic AI call)
- Evidence: temp=0 + pinned seed makes emit a pure function of its prompt, but raw dup rate is 0.0% because the
  prompt embeds RUN:<run_id> + live data-window timestamps. Stripping volatile lines yields 9.6% duplicates in a
  window dominated by a mutation corpus (production repeat/dashboard-reopen/picker-re-POST traffic will be higher).
- Proposal: flag-gated cache table in cmd_catalog keyed (page_key, card_id, asset_table, story_angle_hash,
  basket_fingerprint, skeleton_version, prompt_contract_version, coarse day bucket) → stored raw emit replayed on
  hit; miss → normal AI call + insert. The cached artifact IS the AI's own decision (AI-first preserved); window
  backfill/gates re-run deterministically per run. Invalidate on prompt-file/skeleton/library change (hash them).
- Saving: hit ⇒ −19.8 s p50 for that card; a fully-hit repeat page drops L2 wall 29 s → ~1 s. Fleet floor 9.6% ≈
  −1.9 s/card average; realistic production repeat traffic 30–60% ⇒ −6–12 s average page.
- Effort: medium. Risk: medium (staleness; must key on data-window DAY so window choices stay honest).

### F5 — MTP speculative decoding (the model ships its own draft head)
- Evidence: decode = 13.2 s of the 19.1 s p50 (98 tok/s effective); HF config mtp_num_hidden_layers=1
  (Qwen3.5-MoE MTP head present); vLLM supports MTP spec-decode for MoE families; greedy + rejection sampling is
  output-lossless at temp 0.
- Proposal: benchmark `--speculative-config` MTP on :8200 off-hours; keep pinned-seed determinism cert.
- Saving: typical MTP acceptance ~60–75% ⇒ 1.5–2× decode ⇒ −4.5–6.5 s p50 per card; page wall −5–10 s; the
  p95 2.8K-ctok cards −14–20 s.
- Effort: config + bench. Risk: medium (support for qwen3_5_moe MTP in v0.16.1 unverified; VRAM at util 0.55 fine).

### F6 — Morphs-native system prompt: stop shipping the superseded PART 2 full-author contract
- Evidence: with emit.morphmap_mode ON (it is ON; 96% of calls emit morphs), every call still carries the full
  PART 2 MORPH-EMIT exact_metadata contract (~20.2K ch incl. library zone) PLUS the 8.5K-ch PART 2 OVERRIDE, plus
  a string-level envelope rewrite hack (emit.py:194 replaces '"exact_metadata":{"_morphed":[]}' with '"morphs":{}')
  to resolve the contradiction the model otherwise follows wrong.
- Proposal: a second prompt file (morphs-native, no superseded text) selected by the SAME dp-gate; no-dp cards keep
  the full-author file. Byte-identity only matters per contract version — flag-gate.
- Saving: −3–4K tok prefill/card (~12–16K ch) ⇒ −0.3–0.4 s GPU/card, −1.5–2 s per 5-card page, plus a longer
  shared prefix for F2 and fewer envelope-confusion retries.
- Effort: small-medium. Risk: low-medium (prompt re-cert needed: sweep + suite).

### F7 — Parallelize multi-asset: class lanes AND per-asset assembles are sequential
- Evidence: run/harness.py:409-416 `for cls, members in by_class.items(): lane = run_pipeline(...)` — a 2-class
  compare pays 2 full sequential pipelines; host/multi_asset.py:126-138 `for group: for asset: assemble_cards(...)`
  — N same-class assets pay N sequential executor passes (executor.card p90 6.8 s vs :5433 tunnel). Baselines:
  RESPONSE_MULTI p50 142 s / p90 683 s; worst = 3-feeder compares 410–441 s.
- Proposal: lane 2..N need only shared_1a (ready when lane 1's 1a resolves) — run lanes in parallel after routing;
  run per-asset assembles in a ThreadPool. L2 fan-outs then share vLLM under llm.global_concurrency (F3 guard).
- Saving: 2-class compare ≈ −(lane₂ wall) ≈ −40–60 s p50; 3-asset same-class ≈ −2×assemble ≈ −4–15 s + tail
  compression at p90 (683 s → lanes overlap).
- Effort: medium. Risk: medium (vLLM contention — needs F1/F3 first; lanes already isolated by rid).

### F8 — Break the emit→exec barrier: fill each card as its emit lands (and stream to FE)
- Evidence: host/server.py:63-94 — assemble_cards starts only after run_pipeline returns (ALL emits + swap-settle +
  reflect + notes). executor.card p50 1.0 s / p90 6.8 s is pure serial tail today. Swap-settle only affects 3% of
  cards (37/1,252) and only REVERTS to keep, so eager exec is safe for 97% and cheap to redo for reverts.
- Proposal: per-card future chain emit→gates→exec started as each emit resolves; settle pass re-execs only reverted
  cards. Flag-gated (single-asset serve contract is byte-pinned). Optional SSE endpoint: first card at
  ~1a + first emit ≈ 15–20 s instead of 37.8 s e2e p50 (perceived latency halves).
- Saving: −1.1 s p50 / −7 s p90 page wall (exec fully hidden under the L2 wall); TTFC −15–20 s with streaming.
- Effort: medium-large. Risk: medium (contract tests; per-leaf honesty unchanged).

### F9 — Terse prose knobs in the completion (why/data_note)
- Evidence: notes/other p50 199 ch p95 929; roster null-bindings each carry a `why` sentence; morphs labels verbose.
- Proposal: prompt rule "why/data_note ≤ 10 words" (they are telemetry, full reasons live in gates).
- Saving: −50–150 ctok/card ≈ −0.5–1.5 s p50. Effort: prompt-only. Risk: low.

### F10 — User-message micro-diet (contention relief, adds up at fan-out)
- skeleton json.dumps(indent=1) → indent=None,separators compact: −~25% of 3.3K ch ≈ −200 tok (AI copies paths, not
  whitespace; morph paths are dotted so formatting is not load-bearing — verify morph-path fidelity on a sweep).
- swap_candidates p50 2.2K ch: pool cap (SWAP_POOL_MAX) → 5 closest; swap rate is only 3%.
- slot_catalog p95 8.2K ch: sibling-slot compaction (prompt_compact) triggers only when OVER budget — lower the
  sibling exemplar threshold for always-on arrays >10.
- Total ≈ −1–1.5K tok/card ⇒ −0.1–0.2 s GPU/card, −0.5–1 s per page at fan-out, plus smaller KV per request.
- Effort: small. Risk: low-medium (prompt re-cert).

### F11 — Cache the composed system-prompt base per process (micro)
- Evidence: emit.py:165 re-reads data_instructions_v2.md + morphmap/prompt.md from disk and re-substitutes
  endpoints EVERY call; _recovery_library_block re-queries registry.catalog() + all_bindings per call.
  Card span − LLM latency ≈ 0.9 s of deterministic overhead per card (part is card_input DB reads).
- Proposal: mtime-keyed module cache of the base composition; TTL-cache catalog()/bindings (data/ttl_cache.py
  exists). Saving: −0.2–0.5 s/card. Effort: small. Risk: low.

### F12 — Timeout budget after diet
- llm.timeout.l2_emit=150 s; a stuck emit burns 150 s then hard-fails (observed 1×150 s). After F1/F3 the honest
  p99 is <40 s ⇒ drop to ~90 s to cap worst-case slot stalls. Config row. Risk: low once diet ships.

## Dead ends / refuted
- **Batching N cards into ONE completion (f)**: refuted by decode math — one stream serializes 8×1.3K = 10.4K tok
  at ~147 tok/s single-stream ≈ 70 s vs ~30 s for parallel streams sharing ~330 tok/s aggregate. Only attractive
  if per-card output shrank via shared context, which F1/F6 achieve without the blast-radius coupling.
- **exact_metadata → diff (b)**: ALREADY SHIPPED — emit.morphmap_mode is ON; 96% of calls emit morphs
  ({} p50 818 ch). The remaining full-author calls are no-default-payload cards and are CHEAPER (669 ctok).
- **Parse/gate/transport retries as a latency source**: not in this window (attempt=0 ×1,289; gate retries 0;
  1 timeout). Reflect re-routes: 12 events. The historical reflect n=145 predates preflight_reroute + hard_failure policy.
- **Raising --gpu-memory-utilization**: KV peaks ~13% ⇒ capacity is not the constraint at current cc; matters only
  if F3 raises batch a lot.
- **prompt_budget preflight (45K) vs real window (32,768)**: mis-calibrated but not a latency cost (vLLM rejects
  over-window instantly); should still be lowered to ~30K so doomed prompts classify as over_budget not http_400.

## Cross-lens notes (for other lenses)
- route/stories/basket/knowledge stages: 24–41% byte-identical duplicate prompts → trivial memoization there.
- asset_resolution p50 9.1 s / p90 179 s / max 372 s in this window — dwarfs everything on bad runs (1b lens).
- obs_llm_calls truncates prompt_system/prompt_user at 32,768 chars (exact-32768 rows) — token accounting for
  the biggest prompts must use tokens_prompt, not char lengths.
