# FIX_swap — metric affinity in the swap candidate pool (F3, r_5c6797f815)

## Root cause (DEBUG F3)
`layer2/swap/candidates.py::pool()` ranked swap candidates PURELY by size
(`ORDER BY abs(width-w)+abs(height-h)`) within ±SIZE_TOLERANCE, truncated to SWAP_POOL_MAX.
Metric/story relevance was never a ranking input, so for `metric=voltage` the AI was offered a
size-closest pool with zero voltage-appropriate targets and literally could not swap a current
card to a voltage-appropriate one.

## What changed (files I own)
- **layer2/swap/candidates.py**
  - New generic helpers `_metric_tokens(metric)` (lowercased alnum tokens, len ≥ knob
    `swap.affinity_min_token_len`=2, deduped; None/blank → `()`) and `_affinity(cand, tokens)`
    (count of metric tokens appearing as substrings in the card's
    title/analytical_role/card_purpose/visualization catalog text; 0 = off-metric).
  - `pool(..., *, metric=None)` — new optional param.
    - `metric=None` (or token-less metric): **unchanged** — same closest-first loop with the
      early-break at SWAP_POOL_MAX → byte-identical output (verified by test).
    - `metric` present: materialize ALL size-fit renderable/available survivors (no early break),
      then a **soft** affinity re-rank — stable sort by `-affinity` (SQL's size-ascending order is
      preserved as the tiebreak) — then truncate to SWAP_POOL_MAX. A metric-relevant card outranks
      a size-closer off-metric one, but no size-fit candidate is ever DROPPED before ranking, so a
      page with no metric-specific card still returns its full size pool.
- **grounding/swap_settle.py**
  - `swappable_pool(pool, page_key, *, metric=None)` and `swappable_ids(..., metric=None)` — after
    the renderable/registered filter, an optional soft affinity re-rank (reusing the ONE affinity
    vocabulary via a lazy import to avoid the module-load cycle). `metric=None` preserves order
    exactly. This keeps a metric-aware pool metric-ranked after the render filter; it is defensive
    (no production caller today), the load-bearing change is in `pool()`.

## Why generic (works for ALL prompts/cards/pages/assets)
Affinity is computed from the pipeline's own 1a metric token(s) against the catalog's text columns
(`cards.title/analytical_role/card_purpose/visualization`) — the same computation for every metric
(voltage/current/energy/thd/power/temperature/…) and every card. No per-card, per-metric, or
per-page branch or list. It is a SOFT re-rank (deprioritize, never filter), so it can never empty a
pool. Backward-compatible: no metric ⇒ identical to today.

## Acceptance evidence (psql + live pool())
- Ranking validated for voltage/current/energy against real cmd_catalog: metric-matching live cards
  rank ahead of off-metric same-size ones.
- **Live effect (generic, non-trivial):** real renderable pools reorder — e.g. page
  `transformer-asset-dashboard/thermal-life` slot 74, metric=voltage: size-only pool
  `[58,54,78,80,55,57]` (all off-metric) → ranked leads with `66,43` (voltage-relevant, aff=1) that
  pure-size ranking had truncated out. Same for slots 75/76/77 (cards 66/43/79/67/44/22).
- **metric=None byte-identical:** `pool(cid,pk,tpl,metric=None) == pool(cid,pk,tpl)` (test).
- **card 21 (the reported slot) — honest outcome, NOT a fix regression:** the only voltage card in
  card 21's ±15% size box is card 87 "DG Voltage & Frequency", which is *unregistered + no
  recoverable default + off an available page* → correctly gated out by the existing render/available
  filters (swapping to it = permanent 'not wired' blank). So for that specific slot there is
  genuinely NO renderable voltage swap target and the pool honestly offers none. My ranking fix
  surfaces a voltage card *whenever a renderable/available one is size-fit*; it must not (and does
  not) fabricate or offer an unrenderable card. Card 21's missing voltage target is a
  registry/feasibility DATA gap for card 87, out of scope for swap ranking.

## Tests
- New dedicated file `tests/test_swap_metric_affinity.py` (atomic; did not touch the shared
  `tests/test_layer2_swap_gates.py`): helper unit tests + DB-backed metric=None-identity and
  affinity-ranking assertions. Result: **4 passed, 1 skipped** (the card-21 direct case skips
  honestly because no renderable voltage candidate exists in this DB, per above).

## Cross-file hand-off required (NOT my file)
`pool()` now accepts `metric`, but its real caller passes nothing. To make the fix take effect in
the pipeline, `layer2/card_input.py::build_card_input` must thread the 1a metric into the call.
See `needs_cross_file`.

## verify (adversarial) — VERDICT: UPHELD (generic), but INERT until the cross-file thread lands
Re-derived from the actual code + backup original + live DB. Judgments on evidence:

- ROOT CAUSE — ADDRESSED (within owned files). DEBUG F3 (findings line 175) names the fix exactly:
  "fix at the pool builder (add metric-affinity to the candidate ordering ... via the existing
  cards.card_purpose/analytical_role text)". The change does precisely that: a soft affinity re-rank
  in `pool()` over the catalog text columns. Correct target, correct mechanism.
- GENERIC — CONFIRMED. `_metric_tokens`/`_affinity` are the same token-substring computation for every
  metric and every card; no per-card/per-metric/per-page branch or list. Live sweep (first 6 pages,
  21 pooled slots) shows generic reorders for voltage/current/energy, e.g. slot 16 metric=voltage
  `[24,26,22,20] -> [22,24,26,20]` (card 22 aff=1 surfaces first), slot 14 metric=current
  `[25,27,19,21] -> [25,21,27,19]`. `NOT-RANKED` assertion never fired (affinity non-increasing).
- CONTRACT PRESERVED (swap must not hard-drop size-fit candidates) — CONFIRMED. The re-rank is SOFT
  and truncates at the SAME `SWAP_POOL_MAX` as before (no metric FILTER). Live sweep: 0 empty
  regressions across 21 slots (a metric-less page returns its full size pool). `metric=None` is
  byte-identical: 21/21 slots `pool(...,metric=None)==pool(...)`, and the backup diff confirms the
  `metric=None` branch appends the identical cand dict the original built (same SELECT, same shape).
  The deterministic `settle()` collision-revert logic is UNTOUCHED (diff shows only the additive
  `metric=None` kwarg on `swappable_pool`/`swappable_ids`, gated by `if metric and keep`).
- self-checks reproduced: `py_compile` OK on all 3 .py; `pytest tests/test_swap_metric_affinity.py`
  = 4 passed, 1 skipped (card-21 direct case skips honestly — no renderable voltage target in this DB).

MUST-FIX / load-bearing caveat: the fix has ZERO runtime effect until the `needs_cross_file` one-liner
threads `metric=l1a.get("metric")` into `layer2/card_input.py:46` (verified: that call still passes
only width/height; metric is read one line up at :39 but not forwarded). Integration MUST apply it or
F3 is not actually fixed in production. `swappable_pool`/`swappable_ids` have NO production caller
(only `settle` is used, via run/layer2_all.py), so that side of the change is defensive/inert.

MINOR (not blocking): (1) FIX-note phrasing "no size-fit candidate is ever dropped" is imprecise — the
post-rank truncation to SWAP_POOL_MAX still drops beyond-cap candidates (same as before); the accurate
claim is "metric affinity never FILTERS, only re-ranks under the pre-existing cap." (2) substring
affinity can false-match ('current' in 'concurrent'); soft/tiebreak-preserving so a false positive only
mildly reorders, never drops or fabricates — acceptable, no such collision in the current catalog.
