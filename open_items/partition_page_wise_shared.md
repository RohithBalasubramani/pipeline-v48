# OPEN: partition under-detects page-wise-shared interdependency

> Surfaced 2026-06-29 by the extensive Layer-1a sweep (UPS `battery-autonomy` reported `groups=0`).

## The finding
The partition (`partition/group_detect.py`) forms interdependency groups from **explicit** `cmd_catalog` coupling: `card_link`, `card_combo`, `page_control.affects_cards` (multi-card), `cards.interdependency` prose — plus the region+tab **orphan** fallback.

But the **page-wise-shared** class (per `CMDV2_CARD_ATOMIZATION_AUDIT.md`) — cards that share ONE backend snapshot in the FE hook (e.g. UPS Battery Health + Backup Readiness; DG voltage-current; electrical RTM power/voltage/current) — has **no explicit coupling in `cmd_catalog`**. Verified for `ups-asset-dashboard/battery-autonomy`: `card_link`=0, `card_combo`=0, `page_control` = 4 **self-controls** (host=card affects only itself). So the partition (correctly, given its inputs) returns 0 groups, but those cards ARE interdependent and should share a `shared_context` per Approach B.

**Scope:** 33/68 live pages have explicit coupling; the other ~35 (single-asset + page-wise-shared) get 0 groups — a mix of genuinely-standalone and page-wise-shared.

## Why it's parked (not auto-fixed)
- It sits in the **FE-interdependency-STILL-IN-PROGRESS** zone (Approach B's frontend coupling is provisional, grounded on RTM).
- A premature heuristic ("group all single-asset cards on the same page+tab / same asset") risks **over-grouping** truly-independent cards — the exact failure the design warns about.
- The correct "these cards share one snapshot" signal depends on how the FE hook settles upstream.

## Candidate fix (when the FE settles)
Add a page-wise-shared signal to `partition/coupling_lookup.py`: group cards on the same `(page_key, tab)` that are `single_asset_*` (`card_handling.handling_class`), resolve to the **same asset** (`resolver_scope='meter'`), and read the **live snapshot** (not their own windowed history). Validate against the audit's page-wise-shared list (UPS battery, DG v-c, electrical RTM, electrical v-c) WITHOUT over-grouping simple grids. Gate behind a test that asserts no false grouping on truly-independent single-asset pages.

## Status
Explicit-coupling partition (RTM = `{5,6,7,8,9,10,11,160}`) is **correct and tested**. Page-wise-shared detection is **deferred** to settle with the FE interdependency. Gates: `partition/coupling_lookup.py`, `partition/group_detect.py`, `workers/sharedctx/builder.py`.
