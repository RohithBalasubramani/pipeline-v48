# cmd_catalog — V47 Catalog DB (shared input for V48 layers 1a / 1b / 2)

> **HISTORICAL SNAPSHOT (banner added 2026-06-29).** This document describes the **pre-rebuild** cmd_catalog (116 cards / 29 pages / 123 components / "38/95/214"-era component counts). The DB has since been **REBUILT**: **145 cards (135 live, max id 176), 75 page_specs, 280 components**, with **status columns** present. Per-card render shape now lives in `card_handling` / `card_data_recipe.payload_shape` (there is **no dedicated dialect column**). For current contracts, **query the live DB** — do not rely on the row counts, samples, or "TBD" tags below as current. The canonical current model is the 3 pure-AI layers (1a ∥ 1b → join → Layer 2); see the current canonical docs. Body retained below for historical reference only.

> Generated 2026-06-23 by sampling the live DB (`psql -U postgres -d cmd_catalog`).
> 28 base tables + 2 views · 116 cards · 29 page specs (12 coarse "areas"). *(pre-rebuild counts; now 145 cards / 75 page_specs / 280 components)*
> Feed tags: **1a** = prompt→page routing · **1b** = TBD (candidate) · **2** = per-card sizing/swap/selection/emit · **support** = reference/plumbing/cache. *(NOTE: the current model defines 1b = asset-resolve + card-agnostic column basket + candidate asset list + picker round-trip; Layer 2 OUTPUT = { exact_metadata, data_instructions } per card — see banner.)*

## 1. Overview

`cmd_catalog` is the V47 Postgres catalog that describes the entire CMD_V2 dashboard surface in a machine-readable form so a downstream pipeline can pick, size, route, fetch, and gate every dashboard card. It holds **116 cards** spread across **29 dashboard pages** (keyed by the fine-grained `page_key`, e.g. `panel-overview-shell/energy-power`), plus a legacy 12-row dictionary of coarse page **"areas"** (`pages.area`, the string `cards.page` FK-references). The DB has **28 base tables + 2 views**, organized into six clusters: the per-card spine (`cards-core`, five tables each 1:1 on `card_id`), the frontend render-contract layer (`components-contracts`), the page/layout structure (`pages-layout`), cross-card composition and interactivity (`combos-links-interaction`), per-card control vocabulary (`controls`), and the data/asset support tables (`metrics-3d-topology`). Together the prose columns describe what each card is *for* (so an AI can route/swap), the jsonb recipes/contracts describe the *exact data shape* each card must emit, and the support tables ground rendering in real EMS metrics, 3D assets, and the feeder topology graph.

---

## 2. Table catalog

### Cluster: `cards-core` — the per-card spine (5 tables, all 1:1 on `card_id`, 116 rows each)

| Table | Rows | Purpose (one line) | Key columns | Tiny sample | Feeds |
|---|---|---|---|---|---|
| `cards` | 116 | Card identity/intent registry; the prose the AI reads to know what a card is FOR | `id` (PK), `title`, `page` (FK→pages.area), `composes`, `primary_component` (FK→components.name), `card_purpose`/`analytical_role`/`user_question`/`output_insight`/`decision_support`, `visualization`, `link_type`/`interdependency` | id=1 'Control & Metric Strip' composes TopKpiStrip, role=Monitoring, page='Panel · Overview / SLD'; id=2 'Single-Line Diagram' composes EnergySingleLineDiagram | **1a + 2** |
| `card_data_recipe` | 116 | Authoritative per-card DATA RECIPE — the field-level jsonb spec the AI binds EMS data to | `card_id` (PK), `payload_shape` (composite/series), `orientation` (snapshot/time), `entity_dim`/`selection_dim`, `fields` (jsonb), `reconciled_fields` (jsonb cache), `selection_role` (emits/consumes) | card 4: shape=composite, orientation=snapshot, selection_role=consumes, fields=[{kind:raw,role:column,label:'Active Power',metric:active_power_total_kw,unit:kW}]; reconciled=summary.incomingKw | **2** |
| `card_handling` | 116 | Render/route classification — HOW each card is produced/resolved | `card_id` (PK), `page_key` (FINE key), `handling_class` (single_asset_series 46 / single_asset_derived 28 / panel_aggregate 25 / asset_3d 11 / narrative_ai 4 / nav_index 1 / topology_sld 1), `resolver_scope` (meter 79/panel 28/none 7/site 2), `payload_family`, `backend_strategy`, `produced_by_v47` (57t/59f) | card 1: panel_aggregate/panel/tiles/v47=f; card 3: asset_3d/panel/model_3d; backend_strategy=consumers/real_time_monitoring/pcc_panel.py | **2** |
| `card_grid_size` | 116 | Exact pixel footprint per viewport — the sizing layer | `card_id` (PK), `viewport` (all '1920x1080'), `width_px`/`height_px` (276–1838 wide, 40–946 tall), `basis` (prose) | card 1: 1838x92 (top KPI strip); card 2: 1838x738 (SLD band); card 5: 1494x902 | **2** |
| `card_feasibility` | 116 | Renderability gate — can this card render real data? | `card_id` (PK), `family` (standard 100 + 3d-viewer/3d-electrical/3d-engine/flow/pq-spectrum/sld/sankey), `verdict` (render_real 105/static_chrome 6/drop 5), `required_topology` (bool), `required_mesh` (bool), `reason` | card 2: sld/render_real/topo=t; card 3: 3d-electrical/static_chrome/mesh=t | **2** |

### Cluster: `components-contracts` — the CMD frontend render-contract layer

| Table | Rows | Purpose (one line) | Key columns | Tiny sample | Feeds |
|---|---|---|---|---|---|
| `components` | 123 | Raw registry of every CMD React component with a deep semantic profile | `name` (join key), `file_path`, `category` (16 buckets), `renders`/`key_props`, `card_purpose`/`analytical_role`/`user_question`/`output_insight`, `sem_*`, `visualization` | AiSummary \| primitives/AiSummary.tsx \| renders='sparkle icon + AI insight paragraph' \| props='text,density,withIcon' | **support / 1a** |
| `card_component_usage` | 509 | Card→component composition map (all composing components, with primary flag) | `card_id` (FK→cards.id), `component_name` (FK→components.name), `role` (prose), `is_primary` (72t/437f) | card 5: HeatmapCell (PRIMARY), Card/CardHeader/SegmentedControl (non-primary) | **support / 1a** |
| `card_contract_binding` | 197 | Curated card→contract-component link the pipeline actually joins on | `card_id` (FK→cards.id), `component` (FK→contract_components.name), `match_via` (cards-hint 105/composes 55/composes-primary 36/manual 1) | card 72→ProgressKpiCard (composes/primary); cards 1-4 all bind EnergySingleLineDiagram | **2** |
| `contract_components` | 66 | Full per-component data contract — the exact emit target + host primitive | `name` (join key), `payload_schema_json` (jsonb, 65/66), `host_cmd_component` (55/66), `host_renderable` (55t), `reusability_class` (FULLY GENERIC 24/PARTIALLY 30/HARDCODED 12), `props_interface`/`data_contract`/`layer3_contract`/`rendering_rules`/`visual_constraints`/`generic_capability`/`cards_hint`/`areas` | LTPCCLargeInsightCard schema={unit:'kWh',value:'1905',progress:54.4...}→host ProgressKpiCard | **2** |
| `contract_capabilities` | 407 | Per-component × per-metric capability flags (can/can't render) | `component` (FK→contract_components.name), `metric` (Voltage/Current/Power/Energy/PF…), `supported` (286t/121f) | RealTimeHeatmapSection: Voltage=t, Current=t, Power=t, Energy=**f**, PF=t | **2** |
| `contract_hardcodes` | 184 | Audit of baked-in assumptions blocking generic reuse | `component` (FK→contract_components.name), `assumption` (prose), `classification` (REQUIRES REFACTOR 118/SAFE TO GENERALIZE 66), `file_line` | EnergySingleLineDiagram: 'Incomer cap 4 (.slice(0,4), l.1136)' REQUIRES REFACTOR | **2** |
| `payload_shapes` | 10 | Canonical normalized-payload vocabulary (allowed output shapes) | `name`, `description` (NULL for all) | TextPayload, TilePayload, ProgressPayload, SeriesPayload, TablePayload, RadarPayload, SankeyPayload, HeatmapPayload, PqDiagnosisPayload, PqEventStatsPayload | **2 (support)** |

### Cluster: `pages-layout` — the 29 pages and their structure

| Table | Rows | Purpose (one line) | Key columns | Tiny sample | Feeds |
|---|---|---|---|---|---|
| `pages` | 12 | Legacy lookup of 12 top-level EMS "areas" (cards.page FK target) | `id` (PK), `area` (UNIQUE) | id=1 'Asset · DG'; id=2 'Asset · Transformer / Source'; 'Panel · Overview / SLD' | **support** |
| `page_specs` | 29 | Master spec — one row per page: identity + 7-part narrative + literal CSS grid rule | `page_key` (UNIQUE), `shell`, `title`/`purpose`/`reusable_answers`/`analytical_theme`/`story_structure`/`card_roles`, `grid_template_columns`/`grid_template_rows`/`layout_primitive`/`layout_gap`/`layout_padding`/`layout_shape`, `whats_on_page` (NOT fed to router) | page_key='panel-overview-shell/energy-power'; purpose='Answers "how much energy has this LT panel consumed…"' | **1a + support** |
| `page_layout_cards` | 141 | Canonical slot map — one grid slot per row → its card_id | `page_key`+`slot_order` (slot identity), `card_id` (FK→cards.id, NULL if unmatched), `cell`+`region`, `component`, `match_confidence`, `combo_id`/`combo_role`, `tab` | (source-generation,12,DGLoadProfileCard,'row4 col2',card_id=90,combo_id=26,tab='DG Overview') | **2 + 1a** |
| `page_spec_cards` | 183 | Flatter per-page inventory of React primitives a page is built from | `page_key` (FK→page_specs), `card_name`, `category` (Axis/SVG 48/Controls 25/KPI 21…), `file_path`, `component_name` | (real-time-monitoring, HeatmapCell, 'Bars/Segments', primitives/HeatmapCell.tsx) | **support / 1a (secondary)** |
| `page_control` | 103 | Catalog of every interactive control per page + cards it affects | `page_key`, `control_kind` (25 vals), `dimension`, `host_card`, `affects_cards` int[] NOT NULL, `dst_effect`, `wired`, `trigger`, `evidence` | (ahu-overview, series-solo, dim=series, host=112, affects={112}, rerender, wired=t) | **2 / support** |
| `page_handling` *(VIEW)* | 28 | Rolls card_handling up to one row per page (per-class counts + dominant) | `page_key`, `cards`, `v47_cards`, `single_asset`/`panel_agg`/`sld`/`asset_3d`/`narrative`, `dominant_class` | (ahu-overview, cards=3, single_asset=2, asset_3d=1, dominant='single_asset_derived') | **1a / 2** |

### Cluster: `combos-links-interaction` — composition + cross-card interactivity

| Table | Rows | Purpose (one line) | Key columns | Tiny sample | Feeds |
|---|---|---|---|---|---|
| `card_combo` | 32 | Composition containers — cards rendered as ONE visual/interactive unit | `id` (PK), `page_key`, `combo_key`, `combo_type` (8 vals), `container_component`, `render_strategy` (single-slot/context-sync/tab-group), `region`/`cell`, `over_decomposed`, `evidence` | id=1 ahu-overview composite-card-tabbed-footer container=BmsOverviewRight single-slot over_decomposed=t | **2** |
| `card_combo_member` | 66 | Membership rows linking cards into a combo | `combo_id` (FK→card_combo.id), `card_id` (FK→cards), `member_order`, `member_role`, `member_primitive` (MetricTileGrid/DataTable/EventTimelineChart/ProgressKpiCard/AiSummary), `tab_key`/`flex_basis`/`is_droppable` | combo 1: card 112 order=0 'chart-and-header'; card 113 order=1 'lower-tabbed-panel' primitive=DataTable | **2** |
| `card_link` | 106 | Typed DIRECTIONAL cross-card interaction edges (src emits → dst reacts) | `page_key`, `src_card`, `dst_card`, `dimension` (→selection_dimension), `link_type` (shared-selection/cross-highlight/drill-down/master-selector/…), `src_effect`/`dst_effect`, `trigger`, `scope`, `bidirectional`, `wired`; UNIQUE(page_key,src_card,dst_card,dimension) | src=112 dst=113 dim=time-bucket shared-selection rerender wired=t | **2 + 1a (date-sync)** |
| `v_interaction` *(VIEW)* | 261 | Unifies card_link (origin='edge') + page_control (origin='control', unnest affects_cards) into one src→dst stream | `page_key`, `src_card`, `dst_card`, `dimension`, `kind`, `dst_effect`, `trigger`, `scope`, `wired`, `origin` | 106 edge + 155 control = 261; kinds: shared-selection 123, master-selector 42, drill-down 29 | **2** |
| `selection_dimension` | 14 | Closed-vocabulary registry of selection dimensions + id-space + wired status | `dimension` (key), `unit` (label/id/mfm_id/mesh_name/key/index/route_path), `is_navigation`, `host_wired`, `socket_command`, `note` | feeder \| unit=mfm_id \| socket_command=select_feeder \| host_wired=f; source \| route_path \| is_navigation=t | **support (consumed at 2)** |
| `page_control` | 103 | (also above) page-level/intra-card controls; source of v_interaction origin='control' | `page_key`, `control_kind` (25 vals), `dimension`, `host_card`, `affects_cards` int[], `dst_effect`, `trigger`, `scope`, `wired`, `evidence` | csu-overview master-selector dim=series host=115 affects={115} rerender | **2 (via v_interaction)** |

### Cluster: `controls` — per-card control vocabulary (1 table)

| Table | Rows | Purpose (one line) | Key columns | Tiny sample | Feeds |
|---|---|---|---|---|---|
| `card_controls` | 116 | One row per card — its OWN interactive control vocabulary as built in CMD_V2 | `card_id` (PK+FK→cards.id), `time_mode` (none 73/choice 23/flexible 20), `time_options` (jsonb {value,label,wire,window}), `sampling_options` (jsonb {value,label,bucket}), `segmented_tabs` (jsonb {value,label}, 32 cards), `other_controls` (prose), `defaults` (jsonb), `source_files`, `confidence` (~0.966) | card 2 (SLD): time_mode=none, segmented_tabs=[SLD/3D/3D2], defaults={segmented:'sld',zoom:1,selectedId:'pcc-panel-1-bus'} | **2** |

### Cluster: `metrics-3d-topology` — data/asset support tables

| Table | Rows | Purpose (one line) | Key columns | Tiny sample | Feeds |
|---|---|---|---|---|---|
| `derived_metrics` | 45 | Formula library — metric_key → SQL fragment + base-column deps | `metric_key`, `sql_fragment`, `base_columns`, `nameplate_refs`, `unit`/`label`, `exact`, `source` | active_mwh \| MAX(active_energy_today_kwh)/1000.0 \| base=active_energy_today_kwh \| MWh | **2 (L3 grounding)** |
| `nameplate_config` | 13 | Named constants formulas substitute for :NAME placeholders, with scope overlay | `scope` (default / mfm_type:hv), `key` (V_NOM/band_pct/RATED_POWER_KW/ENERGY_TARGET_KWH), `value`, `unit`/`source` | default V_NOM=415; mfm_type:hv V_NOM=11000 (only hv overlay) | **2 (support)** |
| `infeasible_for_spec` | 48 | Per-run feasibility dead-end cache (card couldn't render for a spec/asset) | `metric`+`intent`, `card_id` (FK→cards.id), `asset_table`, `reason` | metric=THD intent=distribution card_id=25 asset=mfm_lt_115 'L3: no data for fields on this asset' | **1a + 2 (feedback cache)** |
| `asset_3d_registry` | 9 | Catalog of available 3D GLB assets | `key`, `category` (lt_panel/panel/source/feeder/transformer), `file`/`url`/`glb_path`, `name`/`accent`/`default_preset`, `source` | pcc-panel-1 \| panel \| /assets/3d/PCC panel-01 assembly v1.glb \| accent #b35b43 | **support** |
| `card_3d_config` | 11 | Per-card 3D viewer config for asset_3d cards | `card_id` (FK→cards.id), `component`, `asset3d_id` (→asset_3d_registry.key), `resolver_scope` (panel/meter/site), `focus_parts`, `kpi_source`/`meter_table` | card 3 \| Asset3DOverviewWidget \| asset3d_id=pcc-panel-1 \| scope=panel \| mfm_lt_115 | **2** |
| `panel_topology` | 405 | Directed feeder/bus edge graph (from_mfm→to_mfm with edge_kind) | `from_mfm`/`from_name`/`from_table`, `to_mfm`/`to_name`/`to_table`, `edge_kind` (incoming 201/outgoing 147/spare 48/coupler 8/power_quality 1), `to_load_group`/`panel_id`, `id` | from_mfm=2 Transformer 1 → to_mfm=178 HT Panel M1, edge_kind=incoming | **2 (+1a re-route via is_panel)** |

---

## 3. FK / join graph

### Foreign keys (as declared)

```
card_combo_member.combo_id          -> card_combo.id
card_component_usage.card_id        -> cards.id
card_component_usage.component_name -> components.name
card_contract_binding.card_id       -> cards.id
card_contract_binding.component     -> contract_components.name
card_controls.card_id               -> cards.id
cards.page                          -> pages.area
cards.primary_component             -> components.name
contract_capabilities.component     -> contract_components.name
contract_components.canonical_shape -> payload_shapes.name
contract_components.cmd_component   -> components.name
contract_hardcodes.component        -> contract_components.name
page_layout_cards.page_key          -> page_specs.page_key
page_spec_cards.page_key            -> page_specs.page_key
```

> **Note on two FKs:** `contract_components.canonical_shape` and `contract_components.cmd_component` are **empty strings for all 66 rows** — the live host mapping is the newer `host_cmd_component` column (no FK), and the closed shape vocab is read directly from `payload_shapes.name` by `render_contract.py`. So although the FKs point at `payload_shapes.name` / `components.name`, in practice these two columns carry no values and should not be relied on.

### Main join paths

**card → page (two distinct keys — do not confuse).**
- Coarse: `cards.page` → `pages.area` (12-row area dictionary; the same `area` string is denormalized into `page_layout_cards.area`).
- Fine: the real `page_key` lives on `card_handling.page_key` and `page_layout_cards.page_key` (→ `page_specs.page_key`), e.g. `panel-overview-shell/overview-sld-3d`. `cards.page` is NOT the fine page key.

**card → page slots.** `page_specs.page_key` (1) ⋈ `page_layout_cards.page_key` (N slots) ⋈ `cards.id` via `page_layout_cards.card_id` (nullable for unmatched primitive slots). Yields each page's real card set with `cell`/`region`/`tab`/`combo_id`. `page_spec_cards.page_key` → `page_specs.page_key` gives a finer primitive-level inventory (no `card_id` link).

**card → components (provenance).** `cards.id` ⋈ `card_component_usage.card_id`, and `.component_name` → `components.name`; `cards.primary_component` → `components.name`. (509-row usage map = all composing components; the curated subset the pipeline joins is `card_contract_binding`.)

**card → contract (the render contract).** `cards.id` ⋈ `card_contract_binding.card_id`, then `.component` → `contract_components.name`. From there fan out to `contract_capabilities.component` (per-metric supported flags), `contract_hardcodes.component` (refactor caveats), and the host primitive via `contract_components.host_cmd_component`. A card may bind multiple components (cards 1–4 each bind EnergySingleLineDiagram).

**card → controls / recipe / handling / size / feasibility.** All five `cards-core` tables plus `card_controls` are 1:1 on `card_id` (PK = `cards.id`).

**combos.** `card_combo.id` ⋈ `card_combo_member.combo_id`; members carry `card_id` → `cards`. `page_layout_cards.combo_id`/`combo_role` mirror the grouping at slot level.

**interactions.** `card_link` + `page_control` both key on `page_key` and reference cards via `src_card`/`dst_card`/`host_card`/`affects_cards[]`; their `dimension` conforms to `selection_dimension.dimension`. The `v_interaction` view UNIONs both into one `src_card → dst_card` stream.

**metrics/topology.** `derived_metrics.nameplate_refs` → `nameplate_config.key`; `card_3d_config.asset3d_id` → `asset_3d_registry.key`; `infeasible_for_spec.card_id` → `cards.id`; `panel_topology` joins by `to_mfm`/`from_mfm` meter ids (not a catalog FK).

---

## 4. How each V48 layer would read this DB

### Layer 1a — STORYTELLING ROUTER (prompt → best cards-combo template)
> *(banner update 2026-06-29: current model — 1a is a STORYTELLING ROUTER that picks the template = best CARDS-COMBO for the prompt for ANY asset (templates are ASSET-AGNOSTIC; NOT asset/metric matching, NO asset↔page compatibility check) and emits a per-card analytical story. The "prompt → page route" framing is a narrower historical label.)*
- **`page_specs`** — `page_key`/`title`/`purpose`/`reusable_answers`/`analytical_theme`/`story_structure`/`card_roles` read `ORDER BY shell, page_key`; AI returns one `page_key` verbatim. (`whats_on_page` deliberately NOT fed.)
- **`cards`** — identity/intent prose and `cards.page` for page→card-set context.
- **`page_layout_cards` ⋈ cards** — show router each page's REAL card titles (`string_agg`).
- **`page_handling`** (VIEW) — `dominant_class` / per-class counts.
- **`infeasible_for_spec`** — "PREVIOUSLY-FAILED" feedback block. *(Current model has NO reloop/re-route — failures are LOGGED with exact errors; treat this as a feasibility/feedback cache, not a re-route trigger.)*
- Secondary: `components`, `card_component_usage`, `page_spec_cards`, `panel_topology.is_panel()`.

### Layer 1b — asset-resolve + card-agnostic column basket + candidate-asset list + picker round-trip
> *(banner update 2026-06-29: 1b is NO LONGER "TBD". Current model: 1b runs in parallel with 1a from the same FRONTEND PROMPT, resolves the asset, emits a CARD-AGNOSTIC column basket — all relevant tables+cols — plus a candidate ASSET list and the picker round-trip via `PIPELINE_ASSET_ID`; class-from-concept inference. The "candidate / pending user definition" framing below is stale.)*
Candidate tables (historical framing — see note above):
- `page_layout_cards` — chosen page → concrete ordered card set / slots / combos / tab.
- `page_handling` — per-page handling-class mix.
- `card_handling` — per-card `handling_class`/`resolver_scope`/`backend_strategy` if 1b assigns producers up front.
- `card_combo` / `card_combo_member` — grouping members.
- `card_link` / `v_interaction` / `selection_dimension` — page-level interaction/date-sync graph.

### Layer 2 — per-card metadata + data-instructions (the bulk of the catalog)
> *(banner update 2026-06-29: Layer 2's per-card OUTPUT is `{ exact_metadata, data_instructions }` (Decision A, HYBRID) — the AI authors the FINISHED metadata block and emits a parseable `data_instructions` recipe; HOOK/HELPER functions parse it, FILL the data, and own live state/interactivity/interdependency. There is NO reloop/re-route — FAILURES are LOGGED with exact errors. L5 is RETIRED; L6/L6.2 render-shaping retired, data-domain aggregation RELOCATES to our pipeline's worker functions, not backend2. The "swap/emit/re-route" framing below predates this.)*
- **Sizing/swap:** `card_grid_size` (±15% size-match), `card_feasibility` (only `render_real` admitted), `cards` (swap reasoning).
- **Data recipe & contract:** `card_data_recipe` (`fields`/`reconciled_fields`/`orientation`/`entity_dim`/`selection_role`), `card_contract_binding` → `contract_components` (`payload_schema_json`/`host_cmd_component`/`layer3_contract`), `contract_capabilities` (supported-metric gate), `contract_hardcodes` (caveats), `payload_shapes` (allowed shape vocab).
- **Producer routing:** `card_handling` (`handling_class` → aggregate vs single-asset; `backend_strategy`/`resolver_scope`).
- **Composition & interaction:** `card_combo`/`card_combo_member`, `card_link`/`v_interaction`/`page_control`/`selection_dimension`, `page_layout_cards`.
- **Controls per prompt:** `card_controls` (legal time/sampling/segmented values).
- **Data grounding:** `derived_metrics`/`nameplate_config`, `card_3d_config`/`asset_3d_registry`, `panel_topology`, `infeasible_for_spec`.

---

## 5. Open questions (need user confirmation)

> *(banner update 2026-06-29: row counts referenced below are PRE-REBUILD; the DB is now 145 cards / 75 page_specs / 280 components with status columns. Items resolved by the current canonical model are marked **[RESOLVED]**.)*

1. **What is Layer 1b?** **[RESOLVED]** 1b = asset-resolve + CARD-AGNOSTIC column basket (all relevant tables+cols) + candidate ASSET list + picker round-trip (`PIPELINE_ASSET_ID`); runs parallel to 1a from the FRONTEND PROMPT. *(Original open question retained: source docs tagged tables only as 1a / 2 / support.)*
2. **Single-viewport sizing.** `card_grid_size` is keyed by `card_id` alone and every row is `1920x1080`. Single viewport for V48, or load others first?
3. **`fields` vs `reconciled_fields`.** `fields` is the mutated source of truth; `reconciled_fields` is a nullable EMS-aligned cache. Read reconciled-when-present with fallback, or always treat `fields` as authoritative?
4. **Dead `contract_components.canonical_shape` / `cmd_component`.** Empty for all 66 rows; real mapping is `host_cmd_component` + `payload_shapes.name`. Confirm V48 ignores the two empty columns.
5. **Page count mismatch.** *(Pre-rebuild figures; the DB is now 75 page_specs — re-verify against the live DB.)* `page_specs`=29 vs `page_handling`(view)=28 — one `page_key` has no `card_handling` rows. Routable in 1a, or excluded?
6. **`infeasible_for_spec` lifecycle.** Transient per-run cache (flushed per spec+asset at run start). Confirm V48 treats it as runtime state it both writes and reads.
7. **Coarse vs fine page key.** Confirm all V48 routing/joins use `page_key`; treat `pages.area` purely as legacy classification.
8. **`wired=false` interactions.** `card_link`/`page_control`/`selection_dimension` contain documented-but-unimplemented couplings + `host_wired=false` dimensions. Filter on `wired`/`host_wired` before relying on an edge?
9. **`panel_topology` direction gotcha.** Querying `WHERE to_mfm=<bus>`: `edge_kind='outgoing'` → source/incomer, `edge_kind='incoming'` → consumer/feeder (opposite of naive reading); `consumer` rows must exclude `from_name ILIKE 'spare%'`. Confirm V48's resolver honors this.
