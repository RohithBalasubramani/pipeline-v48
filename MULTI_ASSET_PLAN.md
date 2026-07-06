# Multi-Asset / Compare Prompts — THE SIMPLE PLAN (2026-07-06, user-corrected)

**Requirement:** prompts naming 1+ assets must work — "compare UPS-01 and UPS-02", "DG-1 vs DG-2 power" — resolved
concurrently, in a single run.

## The model (user's, 2026-07-06)

**N× FAN-OUT IN ONE RUN.** Not a virtual panel / roster. The spine is unchanged; an OUTER LOOP over the N resolved
assets wraps `validate → L2 → executor`. 1a runs ONCE (template choice); everything from 1b's baskets onward is N×.

```
prompt
 → 1a  : choose appropriate templates (page + cards) from STORY WORDS   [UNCHANGED — 1×]
 → 1b  : resolve the N named assets → [basket_1 … basket_N]             [same logic, output = N × current, ONE run]
 → for each asset i  (N×, straightforward fan-out):
      validate(basket_i)                                                 [N×]
      L2 emit from basket_i  + card SWAP (reuse existing §A swap:         [N×]
          if a swap-candidate card has the columns for the payload AND
          matches prompt intent, swap it in for this asset)
      executor fill → asset_i's cards                                    [N×]
 → host: serve the UNION of all N assets' cards, each tagged by asset    [1 response]
```

## The seams (minimal)

1. **1a — NO CHANGE.** SUBJECT-vs-STORY routing already strips device names; the template set comes from story words.
   ("compare UPS-01 and UPS-02 energy" → energy page, same as "energy for UPS-01".)

2. **1b — N baskets, single run** (`layer1b/build.py` + `resolve/asset_resolve.py`):
   detect the N asset names (existing tokenizer), resolve each with the SAME `resolve_asset` (concurrently), and return
   a LIST: `assets: [{asset, basket, validation…}, …]` (N × the current single output). N==1 → today's shape exactly
   (list of one), so single-asset is untouched. Any unresolved name → the existing picker for that name only
   (`asset_pending`); re-POST accepts `asset_ids: [...]`.

3. **Layer 2 — per basket + swap** (no new mechanism): the existing per-card fan-out runs once per asset over that
   asset's basket. The existing KEEP/SWAP decision (swap.md §A) already picks the card whose columns tell the story;
   for a given asset, if the templated card lacks the columns but a same-footprint swap candidate has them AND matches
   the prompt intent, it swaps — which is exactly how heterogeneous assets get the right card. No code change beyond
   feeding it the asset's own basket.

4. **validate + executor — N×**: each asset's basket is validated and each asset's cards are filled by the current
   single-asset code, unchanged. Pure fan-out.

5. **host — merge + tag** (`build_response`): loop the N assets, tag each produced card with its `asset` (name/id) for
   FE grouping/labeling, return the union. `/api/run` accepts `asset_ids: [...]` for the multi-picker re-POST. FE:
   payload-direct, unchanged (may add an asset label/group header — optional, additive).

## Where the outer loop lives

`run/harness.py`: after 1a (once), 1b yields N `{asset, basket}`; loop them through the existing
`validate → run_2_all(L2) → executor` steps (each is already single-asset), collecting `cards_i`. The host flattens
`[cards_1 … cards_N]` into the response. Single-asset path = the loop with N==1 (byte-identical behavior).

## NOT building (keep it straightforward)

- No new pages/cards/layouts/FE components; no aggregation/roster machinery; no compare-overlay card.
- No cross-class fusion: comparing UPS vs DG just fans out — each renders its own cards; a metric a meter lacks
  honest-blanks per leaf with a reason (correct answer). Swap handles per-asset card fit.
- No cmd_catalog card-schema changes.

## Acceptance (compare battery)

"compare UPS-01 and UPS-02" · "DG-1 vs DG-2 power" · "energy of UPS-01, UPS-02 and UPS-03 today" (3-way) ·
"compare Transformer-01 and UPS-01" (cross-class; common metrics real, class leaves honest-blank + swap where needed) ·
"compare UPS-4 and UPS-01" (one ambiguous → picker for that name only, the other stays resolved) — every asset's
cards: real from neuract, per-leaf reasons, zero fabrication, correct card via swap, SSR+client render clean,
single-asset prompts byte-unchanged (N==1 regression pin).

## Verified grounding

- `layer1b/build.py` — one `resolve_asset(prompt, asset_id)` → wrap in a per-name loop, return the list.
- `run/harness.py` — 1a → 1b → validate → `run_2_all` (per-card L2) → executor; the outer asset loop wraps
  validate…executor.
- `layer2/prompts/swap.md` §A KEEP/SWAP — already selects the card whose columns fit + intent; reused verbatim.
- `host/server.py build_response` — flattens per-card lists today; flatten per-asset×per-card instead.
- Picker re-POST already threads `asset_id` through `/api/run → run_1b`; `asset_ids` plural is additive.
