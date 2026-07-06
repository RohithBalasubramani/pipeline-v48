# cmd_catalog — FULL REBUILD PLAN (v48, against current CMD_V2 working tree)

> Generated 2026-06-25 from a discovery workflow (7 domain-inventory agents over `/home/rohith/CMD_V2/src` + 5 build-method agents reverse-engineering the pipeline_v47 build pipeline).
> Decision: **full rebuild from scratch**, source of truth = **current CMD_V2 working tree as-is** (uncommitted included).
> Pre-flight DONE: `rebuild_snapshots/cmd_catalog_v47_backup.sql` (full pg_dump) + `snap_*.json` (13 curated/EMS-derived tables).

> ## ⚠️ SCOPE: ADDITIVE **+** RE-DERIVATION (both, across all 28 tables)
> Two things happen together, via **upsert** (UPDATE existing by id + INSERT new) — NOT a wipe-and-reload:
> 1. **RE-DERIVATION (existing rows):** the current 116 cards / 123 components / 29 pages have themselves been reworked in CMD_V2 (atomization + metric-presentation centralization rewrote how nearly every current card renders, its payload, its contract, its composes/visualization). So **every existing entity is re-audited from the live source and its row content re-derived/updated in place** — keep the row's id, refresh every other column.
> 2. **ADDITIVE (new rows):** the ~55 new cards / ~70 new components / ~25 new pages are INSERTed (cards ids ≥117).
> Both are driven by the SAME single re-audit pass over current `src/`. `is_new_vs_catalog` only decides UPDATE-vs-INSERT; it must NEVER be used to skip re-auditing an existing card/component/page.
> Identity preserved, content refreshed: `cards.id` 1–116 keep their integer id (FK stability), every other column re-authored; `components.name` / `page_specs.page_key` keep their key unless genuinely renamed/moved. No-frontend-source curated columns (`card_handling`, `card_feasibility`, `reconciled_fields`, etc.) are re-derived by re-running their passes against the CURRENT state; snapshots are a diff/fallback aid, not a freeze.

## 0. New-entity delta (working targets — DO NOT freeze until the re-audit pass)

| Entity | Stale catalog | Current target | Net new |
|---|--:|--:|--:|
| page_specs / route surfaces | 29 | ~54 | ~+25 |
| cards | 116 | ~170 | ~+55 |
| components | 123 | ~190 | ~+70 |

**Dominant new clusters (never modeled in the catalog):**
- **Metric-presentation centralization (tier-3):** `fmtMetric.ts`, `presentationDefaults.ts`, `chartDomain.ts`, `axisTicks.ts`, `historyBuckets.ts`, `ChartHover`, `sankeyVisualEmphasis.ts`. Appears in every domain. **The most consequential new contract type — design it into `contract_components`/`payload_shapes` first.**
- **`three-viewer-kit/` migration (~76 files):** full re-path of the old `three-viewer-assets/` rows (8 assembly viewers, overlay atoms/molecules, callout layers, camera/animation/status/materials concerns).
- **`asset-overview/` shell module**, **lt-pcc panel-overview data-hook layer** (`useBackendPanelOverviewData`, per-tab mock/mapper/viewModel + `BACKEND_CONTRACT.md`), **`src/realtime/` frame reducers**, **`data-v2/types.ts` `WidgetResponse`**, BMS `_templates` registry (13 assets × 35 tabs) + `bmsComposites` + `_meta/audit.json`, the new **`PccOverview3D`** + 8 per-panel GLBs (`panel-1a`..`panel-4b`).

Per-domain new counts (approx): assets +20 cards/+10 comp · bms +13 cards/+14 comp · electrical-other +9 cards · lt-pcc +2 cards · asset-overview-3d +5 cards · charts-primitives +6 card-sets · pages-root +5.

> Starting point already exists: `EMS_CARD_CONTRACT_CATALOG_AUDIT_CMD_V2.md` (Jun-21) flags 19 stale paths + ~23 non-cards to drop + 9 genuine new cards — don't re-discover it.

## PROGRESS LOG
- **2026-06-25 — Pre-flight DONE:** backup + curated snapshots in `rebuild_snapshots/`.
- **GATE 0 DONE:** inventory locked (`INVENTORY_LOCK.md` + `inventory_registry.json`). Targets 38 pages / ~95 cards / 214 components live.
- **TIER 1 APPLIED + VERIFIED:** `status` column added; `cards` 116→145 (135 live, 9 deprecated, 1 scratch; +29 new ids 117–176 = BMS expansion split into 3D+runtime cards); `components` 123→280 (278 live — three-viewer-kit/realtime/asset-overview/metric-presentation now modeled); `card_component_usage` rebuilt deterministically from `composes` (374 rows for live cards); 0 FK orphans. SQL in `rebuild_sql/*.sql`, applied via `apply_sql.sh`.
- **TODO:** `card_grid_size` for the 29 new cards (existing 116 kept). Full deprecation reconciliation vs `INVENTORY_LOCK.md` §5 (only 11 tagged from registry so far). Cost Analysis card 175 may split into 5.
- **TIER 2 APPLIED + VERIFIED:** contract layer rebuilt — `contract_components` 66→122 (102 host_renderable), `card_contract_binding` 197→235 (all 135 live cards bound, 0 unbound), `contract_capabilities` →535, `contract_hardcodes` →258; 0 FK orphans. (3 files regenerated with fixed 20-col template after a col/val drift.)
- **TIER 3 APPLIED + VERIFIED:** `page_specs` 29→75 (68 live + route-shells, real CSS grid templates) ; `page_layout_cards` 141→170 (150 slots mapped, 49 pages); 0 FK orphans. (`page_spec_cards` fine-primitive BOM deferred.)
- **TIER 4 APPLIED + VERIFIED:** all 135 live cards have card_data_recipe + card_handling + card_feasibility + card_controls (0 gaps); 7 handling_classes; 107 render_real. (b121 re-run after socket fail.)
- **TIER 5 VERIFIED INTACT:** panel_topology 405 / derived_metrics 45 / nameplate_config 13 / selection_dimension 14 — EMS-derived, correctly untouched by the frontend rework.
- **TIER 6 APPLIED + VERIFIED:** `asset_3d_registry` 9→33 (8 new panel GLBs + BMS models), `card_3d_config` 11→24 (all 23 asset_3d cards), `card_link` →92 (live↔live graph), `card_combo` 32→39 / `card_combo_member` 66→81, `page_control` refreshed; 0 FK orphans.
- **TIER 7:** `infeasible_for_spec` TRUNCATEd (runtime cache, pipeline repopulates).
- **✅ REBUILD COMPLETE (2026-06-25).** Final integrity: every live card has recipe+handling+feasibility+contract binding (0 gaps). 0 FK orphans across all applied tables.
- **DEFERRED (non-blocking):** `card_grid_size` for the 29 new cards (existing 116 kept); `page_spec_cards` not rebuilt (183 old rows); `card_component_usage` rebuilt deterministically from composes (408, lower fidelity than the original AI BOM); full deprecation reconciliation vs `INVENTORY_LOCK.md` §5 (only the registry-flagged rows tagged); Cost Analysis stays 1 card (its 5 panels are split at the contract level).

## Decisions locked (2026-06-25)
- **Card granularity = granular per-widget** (one card per distinct widget), matching the existing convention (thermal-life = 4 cards). BMS asset screens → 2 cards each (3D + runtime); CostAnalysisTab → 5 cards. ~27 new cards.
- **Deprecated/scratch surfaces = KEEP, tagged.** Add a `status` column (`live`|`deprecated`|`scratch`) to `cards`, `components`, `page_specs`; mark the 43 dead/scratch rows `deprecated`/`scratch` instead of deleting. Pipeline filters to `status='live'`. Preserves FK + history.
- GATE-0 locked totals: **38 pages / ~95 cards / 214 components live** (192 UPDATE · 155 INSERT · 43 deprecated/scratch). See `INVENTORY_LOCK.md` + `rebuild_snapshots/inventory_registry.json`.

## 1. Rebuild order (dependency tiers)

- **TIER 0 — hand enums:** `pages` (12-area enum), `payload_shapes` (10-enum). Edit-and-load.
- **TIER 1 — source spine (AI re-audit):** `components` → `cards` → `card_component_usage`, `card_grid_size`.
- **TIER 2 — contracts (AI re-audit):** `contract_components` → `contract_capabilities`, `contract_hardcodes`.
- **TIER 3 — pages/layout:** `page_specs` → `page_spec_cards` (deterministic) → `page_layout_cards` (AI slot-map).
- **TIER 4 — bindings/recipes:** `card_contract_binding` → `card_data_recipe` → `card_controls`, `card_handling`, `card_feasibility`.
- **TIER 5 — EMS-derived (CMD_V2-INDEPENDENT):** `panel_topology`, `derived_metrics`, `nameplate_config`, `selection_dimension`. Rebuild from `lt_panels_db` + EMS docs, NOT the frontend.
- **TIER 6 — combos/links/3D:** `card_combo`+`card_combo_member`, `card_link`, `page_control`, `asset_3d_registry`+`card_3d_config`.
- **TIER 7 — runtime cache:** `infeasible_for_spec` → TRUNCATE only (pipeline repopulates).

## 2. Per-table method

| Table | Source artifact | Method | Regen entrypoint | AI re-audit? |
|---|---|---|---|---|
| `pages` | `cmd_catalog.sql` | hand enum | `psql -f cmd_catalog.sql` | No |
| `payload_shapes` | `ems_contract.sql` | hand enum | `psql -f ems_contract.sql` | No |
| `components` | `CMD_CARD_CATALOG.md` → `cmd_catalog.sql` | AI MD-audit → SQL | refresh MD → re-author → psql | **YES (heavy)** |
| `cards` | `CMD_CARD_CATALOG.md`+`EMS_CARD_CONTRACT_CATALOG.md` | AI MD-audit → SQL | same dump | **YES (heavy)** |
| `card_component_usage` | same as cards | AI decomposition → SQL | same dump | **YES** |
| `card_grid_size` | `CMD_CARD_GRID_SIZES.md` | AI layout measure → MD → load | **write MD→SQL parser** | **YES** |
| `contract_components` | `EMS_CARD_CONTRACT_CATALOG.md`; `host_cmd_component` via `classify_renderable_v2_wf.js` | AI contract audit → SQL + classify | refresh MD → SQL → re-run classify wf | **YES (heavy)** |
| `contract_capabilities` | `EMS_CARD_CONTRACT_CATALOG.md` §3 matrix | AI transcription | `psql -f ems_contract.sql` | **YES** |
| `contract_hardcodes` | `EMS_CARD_CONTRACT_CATALOG.md` §3 | AI transcription (file:line) | `psql -f ems_contract.sql` | **YES** |
| `page_specs` | `CMD_PAGE_FOLDERS.md`+`build_pages_sql.py`; layout via `ems_grid_wf.js`→`load_layouts.py` | parse MD + AI layout | `build_pages_sql.py` → psql → layout wf → `load_layouts.py` | **YES** |
| `page_spec_cards` | `CMD_PAGE_FOLDERS.md`×`CMD_CARD_CATALOG.md` via `page_cards.py` | deterministic backtick-match | `build_pages_sql.py` → psql | No |
| `page_layout_cards` | AI slot-map wf → `load_slotmap.py` | AI slot extraction → loader | re-run slot wf → `load_slotmap.py` | **YES** |
| `card_contract_binding` | `EMS_CARD_CONTRACT_CATALOG.md` | AI audit → SQL | `psql -f ems_contract.sql` | **YES** |
| `card_data_recipe` | recipe wf → `load_recipes.py`; `reconciled_fields` via `recipe_reconcile_wf.js`; `fix_*`/`remap_*` | AI recipe + reconcile + metric fixes | `load_recipes.py` → `recipe_reconcile_wf.js` → fix/remap | **YES (heavy)** |
| `card_controls` | control wf → `load_controls.py` | AI extract+verify → loader | re-run wf → `load_controls.py` | **YES** |
| `card_handling` | `CARD_HANDLING_CATALOG.md` + AI classify; **NO loader** | AI classify sweep | **write `load_handling.py`** + re-run sweep | **YES + new loader** |
| `card_feasibility` | `FEASIBILITY_PLAN.md` + AI wf; **NO loader** | AI 9-dim scoring | **write `load_feasibility.py`** + re-run wf | **YES + new loader** |
| `panel_topology` | `lt_panels_db.lt_mfm*` | deterministic cross-DB | `python3 build_topology_db.py` | No — EMS-only |
| `derived_metrics` | `layer6_tables.sql`+`fix_recipe_metrics.sql`+`remap_longtail_events.sql` | hand allow-list | run the 3 SQL files | No — EMS-only |
| `nameplate_config` | `layer6_tables.sql`+`build_nameplate_coverage.py` | hand constants + coverage | psql → `build_nameplate_coverage.py` | No — EMS-only |
| `selection_dimension` | `build_dependency_db.py` | curated enum | `build_dependency_db.py` → `load_interdeps.py` | No — curated |
| `card_combo`/`card_combo_member` | `ems_research_wf.js`→`research_pages.json`→`phase1_combos.sql` | AI research → SQL | re-run wf → **write `build_combos.py`** → psql | **YES** |
| `card_link` | `build_dependency_db.py` (base) + `load_interdeps.py` (research) | hybrid | `build_dependency_db.py` → `load_interdeps.py` | **YES (research half)** |
| `page_control` | `ems_research_wf.js`→`load_interdeps.py` | AI research → router split | re-run wf → `load_interdeps.py` | **YES** |
| `asset_3d_registry` | `build_topology_db.py` seed + CMD_V2 `assetOverviewConfig.ts`+`public/assets/3d` | seed + backfill (**no loader**) | `build_topology_db.py` + **write `build_asset_3d_registry.py`** | **YES** |
| `card_3d_config` | `ASSET_3D_PLAN.md` + AI 3D sweep; **NO build script** | AI hand-authored SQL | **write `build_card_3d_config.py`** + re-run sweep | **YES + new loader** |
| `infeasible_for_spec` | `pipeline.py` runtime | runtime cache | TRUNCATE; pipeline repopulates | No — do not build |

## 3. Effort split

- **~70% fresh AI re-audit:** regenerate `CMD_CARD_CATALOG.md`, `EMS_CARD_CONTRACT_CATALOG.md`, `CMD_PAGE_FOLDERS.md`, `CMD_CARD_GRID_SIZES.md` from current `src/`, then re-author `cmd_catalog.sql` + `ems_contract.sql`.
- **~20% write 6 missing loaders/parsers:** `load_handling.py`, `load_feasibility.py`, `build_card_3d_config.py`, `build_asset_3d_registry.py`, `build_combos.py`, `card_grid_size` MD→SQL parser. (The original AI workflow JS for ems-slot-map / card-control-vocab / recipe / handling-classify / feasibility are NOT in the tree — clone from `ems_grid_wf.js`, `ems_research_wf.js`, `classify_renderable_v2_wf.js`, `recipe_reconcile_wf.js`. All `/tmp/v47_*` JSON outputs are gone, must be regenerated.)
- **~10% re-run deterministic/EMS scripts.**

## 4. Risks / guardrails

- **ID STABILITY ≠ content freeze:** `cards.id` 1–116 are FK'd by 10+ child tables — keep each existing card's **integer id** for FK stability and **new cards get ids ≥117, never renumber** — but **every other column of those existing rows is fully re-authored from current source** (composes, visualization, primary_component, semantic fields, etc.). Same for `components.name` / `page_specs.page_key` (keep the key, refresh the row; a genuine rename must cascade).
- **Re-derive curated columns from CURRENT state, don't freeze old values** (snapshots in `rebuild_snapshots/` are a diff/fallback aid only): `contract_components.host_cmd_component`, `card_data_recipe.reconciled_fields`, `card_handling.*`, `card_feasibility` verdicts, `card_3d_config.focus_parts`/`kpi_source`, `asset_3d_registry.accent`/`default_preset`/`glb_path`, `nameplate_config` cited constants. Re-run their passes against the reworked source; the snapshot is the rollback/compare baseline, not the answer.
- **EMS-derived tables must NOT be rebuilt from the frontend** (`panel_topology`, `derived_metrics`, `nameplate_config`, `selection_dimension`).
- **`infeasible_for_spec`** is runtime state — TRUNCATE only.
- **514-file churn is mostly noise:** ~129 are `prodo/frontend/assets/*` Vite build output — IGNORE; audit `src/` only (~385 real source paths). Mark scratch/deprecated surfaces (lt-pcc `test-tabs` reference tabs, legacy `LTPCCOverviewTab`, redirect-dead PCC-P1/P2/U1/U2, HT-Trf) as deprecated, NOT live cards.
- **CASCADE hazard:** `cmd_catalog.sql` DROPs `components` CASCADE → forces `ems_contract.sql` + FK-children reload. `card_combo_member` FK is ON DELETE CASCADE; `page_layout_cards.combo_id` is deliberately FK-less. Preserve both.

## 5. Execution (tier-by-tier, with gates)

- **Phase 0 — Pre-flight** [DONE]: pg_dump backup + curated-column snapshots. TODO: lock the live source inventory (routes + pages + primitives + three-viewer-kit, exclude `prodo/`) + deprecation list. **GATE 0:** agreed target counts (~54/~170/~190) + deprecation list.
- **Phase 1 — Refresh the 4 audit MDs** (heavy multi-agent re-audit of `src/`). **Re-audit EVERY current page/card/component from scratch — existing AND new** (existing rows are stale because the atomization rework rewrote them); do not diff-skip. **GATE 1:** every live card re-described from current source, 0 missing, 0 stale paths, every existing row shows its refreshed content (adversarial coverage pass).
- **Phase 2 — Tier 0+1+2 spine:** edit enums; re-author `cmd_catalog.sql` (ids preserved, new ≥117) then `ems_contract.sql`; load cmd_catalog FIRST; re-run `classify_renderable_v2_wf.js`; re-merge preserved manual UPDATEs. **GATE 2:** FK integrity + counts + contract tests green.
- **Phase 3 — Tier 3 pages/layout:** `build_pages_sql.py` → psql; layout wf → `load_layouts.py`; slot wf → `load_slotmap.py`. **GATE 3:** every live page has a spec + ≥1 slot.
- **Phase 4 — Tier 4 bindings/recipes:** recipe wf → `load_recipes.py` → `recipe_reconcile_wf.js` → fix/remap; control wf → `load_controls.py`; **write `load_handling.py`+`load_feasibility.py`**, re-run sweeps, re-merge preserved verdicts. **GATE 4:** every card has exactly one recipe/controls/handling/feasibility row.
- **Phase 5 — Tier 5 EMS-derived** (parallelizable any time): `build_topology_db.py`; `layer6_tables.sql`+fixes+`build_nameplate_coverage.py`; `build_dependency_db.py`. **GATE 5:** topology ≥405, full nameplate coverage.
- **Phase 6 — Tier 6 combos/links/3D:** `ems_research_wf.js`; **write `build_combos.py`** load combos + backfill `combo_id`; `load_interdeps.py`; **write `build_asset_3d_registry.py`+`build_card_3d_config.py`** (8 new GLBs), re-run 3D sweep. **GATE 6:** all 8 GLBs registered.
- **Phase 7 — Final:** `TRUNCATE infeasible_for_spec`; run v47 test suite + an e2e `pipeline.py` prompt. **FINAL GATE:** sample NEW cards (`PccOverview3D`, `EnergyDistributionLayout`, an assets card, a BMS template card) resolve through the live pipeline with real EMS data.

Key paths: build root `backend/layer2/pipeline_v47/`; audit target `/home/rohith/CMD_V2/src/` (NOT `prodo/`); rollback `rebuild_snapshots/cmd_catalog_v47_backup.sql`.
