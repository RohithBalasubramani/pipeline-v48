# Multi-Asset / Compare — AS BUILT (2026-07-07)

**Requirement:** prompts naming 1+ assets work — "compare UPS-01 and UPS-02", 3-way, cross-class — in a single run.

## The model (user-corrected twice; final): AUTHOR ONCE PER CLASS

Layer 2 authors the card recipe from the column **schema**, which same-class assets share — so it is **NOT** N×:

```
1a        → ONCE            (template from story words; later class lanes get it INJECTED + LOCKED)
1b        → per class lane  (representative asset resolves; siblings need no basket — executor rediscovers schema)
Layer 2   → ONCE PER CLASS  (recipe binds by column NAME → portable across sibling meters)
executor  → PER ASSET       (same recipe, each asset's OWN neuract table; honest-blank data-driven at fill time)
host      → merge + tag each card `card.asset={id,name,class}`
FE        → picker multi-select → asset_ids[] re-POST; CardGrid groups by card.asset (stacked page per asset)
```

Primary entry = the **picker re-POST `asset_ids:[…]`** (AI-free — the F5/F6 collision gate pre-empts short names, so the
picker is where N is chosen). N==1 never enters this path: the single-asset `run_pipeline`/`build_response` are
byte-untouched; dispatch requires `len(asset_ids) >= 2` AND the DB knob `multi_asset.enabled`.

## Implementation (atomic files)

- `run/harness.py` — `run_pipeline(..., layer1a=None)`: inject a shared template + LOCK it (reconcile / preflight /
  reflect re-routes suppressed for shared-template lanes). `run_pipeline_multi(prompt, assets)`: group by class → ONE
  `run_pipeline` per class (first routes 1a; later classes get `deepcopy`; run_id salted `class:<cls>`).
- `host/assemble.py` — `assemble_cards(out, asset, date_window)`: the per-asset executor+enrich (pure extraction of
  build_response's block; single path calls it byte-identically).
- `host/rebind_consumer.py` — repoint a reused recipe's `consumer.mfm_id` + `binding.asset_id/table` at a sibling
  (deep-copied; the AI fields are copied verbatim — zero fabrication).
- `host/asset_lanes.py` — `resolve_assets(ids)`: registry ids → as_asset dicts (unknown dropped, order kept).
- `host/multi_asset.py` — `build_response_multi`: per asset rebind → assemble (own table) → tag → concat; propagates a
  lane's `data_unavailable`/`degrade` (no silent blank grid). `host/server.py do_POST` dispatches on `asset_ids`.
- DB: `db/seed_multi_asset.sql` → `app_config` `multi_asset.enabled` (bool) / `multi_asset.max_assets` (int, cap 6).
- FE: `AssetResolution.tsx` = ONE interaction model — **click row = toggle select (never runs); one adaptive button**
  ("Open X" / "Compare N assets") fires once, disabled while loading. `App.tsx` `run(id|ids[])` + honest
  `DataUnavailable` notice on outage/0-cards. `CardGrid.tsx` groups by `card.asset` under an AssetHeader.
- Related hardening: `layer1b/resolve/has_data.py` chunk handlers now RAISE on an outage-shaped error (fingerprints from
  `run/degrade_gate`) instead of fabricating has_data=True — a full :5433 outage reaches the honest
  `data_unavailable` terminal instead of the picker (bad-table fail-open preserved).

## Verified (2026-07-07, live + logs)

- Same-class 3-way `asset_ids:[11,12,13]` → 12 cards = 4×3 groups, ALL render; distinct real values per meter
  (totalEnergyKwh 29,111/29,202/29,285); **1 Layer-2 authoring** for 3 assets; 59.5s; SSR gate 12/12.
- Cross-class `[11,171]` (UPS + Transformer) → one shared page, 6 cards = 3×2 groups all render, **2 authorings (one
  per class)**, 0 errors, 84.5s.
- Outage: single + multi both return `data_unavailable:True` + degrade.reason (FE shows the notice, not a blank grid).
- Tests: `tests/test_multi_asset.py` (10) + `tests/test_has_data_outage.py` (3) + full non-live suite; client-gate
  103/103; `tsc` clean.

## NOT built (deliberate)

- No cross-class fusion/overlay card — each class renders its own group; shared page only.
- No AI multi-name confident path (picks[1:]) — the picker re-POST covers it; additive fast-follow if ever needed.
- Sequential class lanes (usually 1); parallel lanes = fast-follow (needs ai_log contextvar).
