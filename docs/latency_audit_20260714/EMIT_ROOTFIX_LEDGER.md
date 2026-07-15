# L2 emit decode-wall root-fix — execution ledger (2026-07-15)

Plan: the approved 6-stage program (plan file greedy-munching-patterson.md). ALL STAGES EXECUTED + ADOPTED LIVE.
Commits: 85e7a4f (S0) · c795870 (S1+S2) · 8e914a3 (S3) · c3130a3 (S4+S5) · b68c9ce (S6).

## Root causes fixed (forensics: 1,555 real emits + frozen fixtures tests/fixtures/emit_forensics/)
1. **Mechanism A** — zero-filled DATA-grid morphs (card 24: 14,614 tok, 89% grid): the shown skeleton carried the
   grid → collapse_data_tier() replaces data-tier subtrees with `<<DATA: N element(s)>>` markers (S2). The producer
   already rejected these; S0 made the rejects countable (`_data_morph_rejects`).
2. **Mechanism B** — roster/fields retype (card 22: 110 entries, ALL rejected + recipe backfilled anyway): roster-DIFF
   contract (S1, prompt-only — gate_roster proven equivalence) + slim fields[] with deterministic backfill from the
   basket dictionary + slot ctx (S6 — the same truth the quantity gates enforce).
3. **Unbounded completion** — llm.max_tokens had no row: per-stage `_max_tokens_for` + l2_emit=6000 (>2x post-diet
   max) + timeout 150→120 (S3). Truncation stays fail-fast honest-blank.
4. **Concurrency queueing timeouts** (cards 42/18 at ~24 in-flight): admission ON (global_concurrency=4, wait 300s) (S0).
5. **Prompt entropy** — RUN: id + nanosecond freshness stamps: hour-bucketed facts + stable header (S4,
   emit.prompt_stability=v1; wall_corpus detector accepts both generations).
6. **NO determinism at temp0/seed42 (load-bearing discovery)**: obs rows 5507 vs 5513 — byte-identical prompts +
   params, 156 response diff regions. Concurrent batching flips near-tie argmax; the seed only pins sampling RNG.
   → S5 exact-match response cache (llm/response_cache.py at the call_qwen boundary, stages basket+l2_emit) BOTH
   skips repeat decodes AND imposes the determinism the serving stack cannot. basket must ride along (its output is
   embedded in the l2 prompt). Hits re-enter the FULL gate chain; DATA always fills live. NO recorder bypass
   (replay hooks wrap call_qwen's OUTER boundary — hits are taped like live replies; replays serve from the tape
   first). obs response clamp split (obs.llm.max_response_bytes=131072) so stored completions stay whole.

## Measured results (live, adopted)
| metric | baseline (Jul 12-14) | after |
|---|---|---|
| card 24 (grid bomb) | p50 1,447 / max 14,614 tok | **590 tok, 10.7s** |
| card 19 | p50 2,372 / max 11,702 | **166 tok, 5.4s** |
| card 22 (110-roster) | p50 1,524 / max 7,324 | **1,336 → smaller under S6** |
| roster entries emitted | 110 | **0-3** (genuine diffs) |
| grid morph paths | 8+ per emit | **0** (temptation removed at source) |
| feeder 4-card page (cold) | ~30-50s | **18.7s** (S6 fresh), 4/4 rendered |
| harmonics 5-card page | 292s worst / ~150s typical | **42.1s**, 5/5 rendered |
| voltage-current 5-card page | ~50-60s | **29.6s**, 5/5 rendered |
| repeat prompt (any) | full re-author | **2.5s** (1 basket + 4 l2 cache hits) |
| fresh emit tokens (cards 39-41) | 1,074-2,372 | **518-963** |

## Live knob state (all rollback = flip the row + reload)
emit.diet.roster=on · emit.diet.morph_shape=on · emit.diet.fields=on · emit.prompt_stability=v1 ·
llm.response_cache=on (stages basket,l2_emit; ttl 86400; mem tier 1h) · llm.max_tokens.l2_emit=6000 ·
llm.timeout.l2_emit=120 · llm.global_concurrency=4 · llm.admission_wait_s=300 · obs.llm.max_response_bytes=131072

## Permanence
- Contract pins: tests/test_emit_diet_contract.py (18) + test_llm_stage_bounds.py (5) + test_llm_response_cache.py (6)
  over frozen forensic fixtures — the mechanisms can never silently return.
- All flags default OFF in code (byte-identical off-states proven vs HEAD); seeds: db/seed_emit_diet.sql,
  db/seed_llm_bounds.sql, db/llm_response_cache_schema.sql, db/seed_obs_llm_bounds.sql.
- Honesty unchanged by construction: gates re-run on every path incl. cache hits; DATA fills live per request
  (fab_guards + render_verdict); truncation → honest-blank; backfilled display context comes from the same
  dictionary truth the quantity gates enforce.

## Known open / unrelated
- test_asset3d_dg_seed fails on a stale live-DB assumption (viewer.default_asset_3d_key=pcc1a-v1 seeded by the
  3D-preset workflow) — owner: 3D presets, NOT this program.
- Cache poisoning suspicion runbook: `TRUNCATE llm_response_cache;` + flip llm.response_cache off.
- Next candidates (from the audit, not in this program): wildcard slots for per-index families (card-43-class time
  fields), streaming shell (perceived), Stage-B lane parallelism re-verify in a quiet GPU window.
