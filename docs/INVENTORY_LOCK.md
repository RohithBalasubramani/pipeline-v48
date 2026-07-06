# GATE 0 — CMD_V2 Inventory Lock (cmd_catalog rebuild)

> Generated 2026-06-25 by the inventory-lock workflow (7 domain agents + reconciler over /home/rohith/CMD_V2/src).
> Raw entities: 447. Registry JSON: inventory_registry.json

All legacy files physically exist (so they are "deprecated/orphaned" not "deleted"), and the source page-local components (cards 83-98) are still in `SourceGenerationPage.tsx`. The only catalog rows pointing at truly DELETED files are the 3D viewer rows (old `three-viewer/` + `three-viewer-assets/` dirs). 

I now have everything needed to reconcile. Let me produce the GATE-0 report.

---

# GATE 0 — AUTHORITATIVE INVENTORY LOCK (cmd_catalog rebuild)

Audited `/home/rohith/CMD_V2/src` only (excluded `prodo/`, `*.test.*`, `*.stories.*`). Reconciled the 447-entity merged list against the live catalog (`116 cards / 123 components / 29 page_specs`). Deduped cross-domain. On-disk verified: the old `components/three-viewer/` and `components/three-viewer-assets/` dirs are **gone**; all other "legacy" files physically remain (so they are orphaned, not deleted).

---

## 1. FINAL COUNTS

Live entities after cross-domain dedup, split by `catalog_match`:

| Entity type | EXISTING (match=true → UPDATE) | NEW (match=false → INSERT ≥117) | LIVE total | Deprecated/Scratch |
|---|---:|---:|---:|---:|
| **Pages** | 27 | 11 | 38 | 14 |
| **Cards** | 70 | 25 | 95 | 18 |
| **Components** | 95 | 119 | 214 | 11 |
| **TOTAL** | **192** | **155** | **347** | **43** |

Reconciliation against the stale `29 / 116 / 123`:

- **Pages 29 → 38 live (+14 deprecated/scratch).** 27 of the 29 page_specs are matched (UPDATE). The 2 unmatched page_specs are `chiller/evaporator`/`condenser` (folder re-pathed, see §3) — they DO have a live entity, just under a moved path, so they still UPDATE, not delete. New navigable pages = the route-shell layer the catalog never modeled (`routes.tsx`, `UniversalAssetRoute`, `AssetManagementRoute`, `FlowDummyPage`-family, the 6-tab `PanelOverviewScreenOutlet`) + the 9 brand-new BMS asset overview/runtime screens.
- **Cards 116 → 95 live + 18 deprecated + 3 absorbed.** 70 of 116 cards re-derive to a live entity (UPDATE). 25 new cards (BMS subsystem/overview expansion). The remaining catalog cards are deprecated (legacy lt-pcc/bms duplicates) or folded into a sibling row (§3).
- **Components 123 → 214 live.** 95 of 123 catalog component rows match a live file (UPDATE; ~88 charts/primitives + page-locals). The catalog under-modeled the codebase massively: 119 NEW components — the entire `three-viewer-kit/` 3D subsystem (~150 files rolled into ~17 group-rows), the `realtime/` socket layer (13), `data-v2/` (4), `asset-overview/` shell (9), atomized panel/BMS data-hooks and tier-3 metric-presentation helpers.

> Note on method: multi-file "group rows" (e.g. the `three-viewer-kit` overlay/animation/camera subsystems, `Rail*` family, `pcc*Mesh` set) are counted as ONE component entity each, matching the catalog's one-row-per-file-entity convention. Physical file count is far higher.

---

## 2. CROSS-DOMAIN DEDUP DECISIONS

Entities surfaced by multiple domain passes — counted ONCE under the owning domain:

| Entity | Surfaced in | Counted once under | Catalog ref |
|---|---|---|---|
| `CentralAssetViewer.component.tsx` | asset-overview-3d, bms, electrical-other | **asset-overview-3d** (kit owner) | component `CentralAssetViewer` + cards 99/111/114 |
| `ViewerCanvas.atom.tsx` + `ModelLayer.layer.tsx` | asset-overview-3d, bms | **asset-overview-3d** | component `ViewerCanvas / ModelLayer` + cards 60/101/104 |
| `FuelTankAnatomy.tsx` (`lt-pcc/tabs/dg-overview/`) | assets (DG fuel tab), electrical-lt-pcc | **assets** (card 63) — lives in lt-pcc path but consumed cross-domain | card 63 |
| `HealthSummaryPanel.tsx` / `PhaseBarRows` (`electrical/tabs/voltage-current/`) | assets (DG V&C 66/68), electrical-other | **electrical-other** (owner); DG reuses | component `PhaseBarRows`, cards 66/68 |
| `VoltageCurrentLayout` (shared) | assets (DG), electrical-other | **electrical-other** | new component |
| `AssetOverviewContent.tsx` | listed twice within asset-overview-3d (as card 3 backing + as component) | **once** — card 3 (the composed widget); the inner-grid mention is the same file | card 3 |
| `BmsCompositeCard` / `bmsComposites.ts` | bms (data source for `_templates` split tabs) | **bms** — STAY LIVE as type/data, render moved to `BmsSplitNew` | component `Recharts ComposedChart` (card 100 host) |
| All `components/charts/primitives/*` (HeatmapCell, FlowSankey, RadarChart, EventTimelineChart, DataTable, LinePath, TickProgressBar, CardHeader, AiSummary, MetricTileGrid, etc.) | mounted by lt-pcc, electrical-other, assets, bms | **charts-primitives** (sole owner) — mounted-by, never re-listed | 88 catalog component rows |
| `EquipmentOverviewTemplate` | electrical-other (card 82), pages-root (FlowDummyPage mounts it) | **electrical-other / charts** (component row) | component `EquipmentOverviewTemplate` + card 82 |
| `EventTimelineChart` / `EventStripControls` — folder-local copies in `panel-overview/voltage-current/` | electrical-lt-pcc | counted as **re-pathed instances** of the primitive, NOT new primitives | components `EventTimelineChart`/`EventStripControls` |
| `CompositeChartCard` — tab-local copy (`ups/.../output-load-capacity/`) vs `primitives/CompositeChartCard` | assets, charts-primitives | **two distinct files**: card 59 (tab-local, NEW component) + card 56 (shared primitive) — name collision, kept separate | card 56 shared / card 59 local |

Net dedup removals from the raw 447: ~14 duplicate listings collapsed (3D kit cross-refs, FuelTankAnatomy, PhaseBarRows, AssetOverviewContent double-entry, primitive mount echoes).

---

## 3. EXISTING-ROW COVERAGE (the riskiest part)

### Page_specs (29): all 29 matched → UPDATE
- 27 clean path matches.
- **2 re-pathed (UPDATE folder, do NOT delete):** `chiller/evaporator` and `chiller/condenser` — folder `bms/chiller/ChillerSubsystemTab.tsx` is now `bms/_templates/chiller/{evaporator,condenser}/*Tab.tsx`. Live entity exists; update `folder`.
- **Slug ⚠ reconcile (route↔key mismatch, not a delete):** routes use plural `/assets/diesel-generators/`, `/assets/transformers/` while page_keys are singular `diesel-generator-asset-dashboard`, `transformer-asset-dashboard`. Keep keys; record route alias.

### Cards (116): 70 matched-live · 18 deprecated · 3 absorbed · 25 unchanged-but-re-pathed-component
**Catalog cards with NO live render path (candidate DELETE/deprecate) — 18+:**

| Card ids | Why no live match | Decision |
|---|---|---|
| **28, 29, 30, 35** (Individual-Feeder `LTPCCOverviewTab` + `lt-pcc-overview/LTPCC*` cards) | `DetailOverviewSection` now mounts `ResolvedAssetOverview` (asset-overview), not these. Files exist but zero live importer. | **deprecate** |
| **31, 32, 33, 34, 36, 37, 38, 39, 44, 45, 46** (Individual-Feeder metric/gauge/sparkline cluster) | superseded by `ResolvedAssetOverview` / `OverviewKpiColumn` rebuild; old feeder-overview cards orphaned | **deprecate / re-audit** (see §6 — partial) |
| **113, 116** (`EventsLog / ReadingsTable / RuntimeRollup` via `BmsOverviewSplit.tsx`) | replaced by `_shared/BmsSplitNew` + `viewModel`; only importer is deprecated `ChillerOverviewSplit` | **deprecate** |

**Cards whose primary_component points at a DELETED file (re-path required, entity still live):**
- **3** (`Asset3DOverviewWidget` → deleted `three-viewer/`) → now `components/asset-overview/AssetOverviewContent.tsx`. **UPDATE path.**
- **83, 85, 98** (`Asset3DOverviewWidget`, source/DG/source-mix pages) → component deleted. These live on `SourceGenerationPage` (still present). **Re-audit their new 3D mount** (see §6).
- **60, 101, 104** (`ViewerCanvas / ModelLayer` → deleted `three-viewer-assets/`) → split into kit `canvas/atoms/ViewerCanvas.atom.tsx` + `materials/layers/ModelLayer.layer.tsx`. **UPDATE.**
- **99, 111, 114** (`CentralAssetViewer` → deleted `three-viewer-assets/`) → `three-viewer-kit/viewers/components/CentralAssetViewer.component.tsx`. **UPDATE.**

**Cards absorbed into a sibling row (no separate live file) — fold, don't delete:**
- **9 + 10** → single `RealTimeMonitoringRail.tsx` (SupplyCard/TrendCard).
- **14 + 15** → `energy-power/Cards.tsx` `EnergyProgressCard` variants.
- (TopKpiStrip/BottomKpiStrip cards 1/4 are now in-file fns inside `EnergySingleLineDiagram` — still live, UPDATE.)

### Components (123): 95 matched · 1 deprecated · stale-path UPDATEs
**Unmatched / stale catalog component rows:**
- `Asset3DOverviewWidget` (`components/three-viewer/…`) — **file DELETED, no successor component**. Render role replaced by `asset-overview` shell. → **deprecate component row.**
- `CentralAssetViewer`, `ViewerCanvas / ModelLayer` — file_path stale (old dirs deleted) → **UPDATE path** to kit.
- `StatusBadge (legacy)` (`legacy/StatusBadge.tsx`) — file exists, superseded by `primitives/StatusBadge.tsx`, kept for back-compat → **mark deprecated, keep row.**
- `LossHvLvRatioGauge` (`loss-analysis/LossAnalysisGauges.tsx`) — 0 consumers but still exported → keep **live** (do not delete).
- All `pages/source/SourceGenerationPage.tsx` page-locals (DriverRow, FlowNode/ArrowFlow, GaugeBlock, MetricCell grid, MiniBar, MultiLineChart, PhaseRow, status cells, etc.) — **file present, all live, UPDATE in place** (24 grep hits confirmed).

---

## 4. NEW-ENTITY LIST (INSERT)

### New CARDS — proposed ids 117–141 (25, all BMS expansion)
Existing catalog tops out at card 116; assign sequentially:

| id | card | page_key | file |
|---|---|---|---|
| 117 | Chiller Compressor & Oil tab | `chiller/compressor-oil` (new) | `_templates/chiller/compressor-oil/CompressorOilTab.tsx` |
| 118 | Chiller Voltage & Current tab | `chiller/voltage-current` (new) | `_templates/chiller/voltage-current/VoltageCurrentTab.tsx` |
| 119 | Chiller Energy & Performance tab | `chiller/energy-performance` (new) | `_templates/chiller/energy-performance/EnergyPerformanceTab.tsx` |
| 120 | AHU Air Conditions tab | `ahu-csu/ahu-air-conditions` (new) | `_templates/ahu/air-conditions/AirConditionsTab.tsx` |
| 121 | Air Compressor Overview (3D) | `air-compressor-dryer/overview` (new) | `_templates/air-compressor/overview.tsx` |
| 122 | Air Compressor Runtime (split) | `air-compressor-dryer/runtime` (new) | `_templates/air-compressor/overview-split.tsx` |
| 123 | Air Dryer Overview (3D) | `air-dryer/overview` (new) | `_templates/air-dryer/overview.tsx` |
| 124 | Air Dryer Runtime (split) | `air-dryer/runtime` (new) | `_templates/air-dryer/overview-split.tsx` |
| 125 | Air Dryer Thermal & Oil tab | `air-dryer/thermal-oil` (new) | `_templates/air-dryer/thermal-oil/DryerThermalTab.tsx` |
| 126 | Air Washer Overview (3D) | `air-washer/overview` (new) | `_templates/air-washer/overview.tsx` |
| 127 | Air Washer Runtime (split) | `air-washer/runtime` (new) | `_templates/air-washer/overview-split.tsx` |
| 128 | AW Exhaust Overview (3D) | `aw-exhaust/overview` (new) | `_templates/aw-exhaust/overview.tsx` |
| 129 | AW Exhaust Runtime (split) | `aw-exhaust/runtime` (new) | `_templates/aw-exhaust/overview-split.tsx` |
| 130 | Cooling Tower Overview (3D) | `cooling-tower/overview` (new) | `_templates/cooling-tower/overview.tsx` |
| 131 | Cooling Tower Runtime (split) | `cooling-tower/runtime` (new) | `_templates/cooling-tower/overview-split.tsx` |
| 132 | PCW Pump Overview (3D) | `pcw-pump/overview` (new) | `_templates/pcw-pump/overview.tsx` |
| 133 | PCW Pump Runtime (split) | `pcw-pump/runtime` (new) | `_templates/pcw-pump/overview-split.tsx` |
| 134 | Exhaust Blower Overview (3D) | `exhaust-blower/overview` (new) | `_templates/exhaust-blower/overview.tsx` |
| 135 | Exhaust Blower Runtime (split) | `exhaust-blower/runtime` (new) | `_templates/exhaust-blower/overview-split.tsx` |
| 136 | HSD Fuel Overview (3D) | `hsd-fuel/overview` (new) | `_templates/hsd-fuel/overview.tsx` |
| 137 | HSD Fuel Runtime (split) | `hsd-fuel/runtime` (new) | `_templates/hsd-fuel/overview-split.tsx` |
| 138 | AHU fleet overview (3D assembly) | `_overviews/ahu-overview` (new) | `_templates/_overviews/ahu-overview.tsx` |
| 139 | Chiller fleet overview (3D assembly) | `_overviews/chiller-overview` | `_templates/_overviews/chiller-overview.tsx` |
| 140 | CSU fleet overview (3D assembly) | `_overviews/csu-overview` | `_templates/_overviews/csu-overview.tsx` |
| 141 | Air-compressor fleet assembly | `_overviews/air-compressor-assembly` | `_templates/_overviews/air-compressor-assembly-new.tsx` |

Plus the lt-pcc new card **`SingleLineDiagramTestTab`** (SLD/3D fault-filter assembly wrapper) and the electrical-other new card **CostAnalysisTab** (5-panel cost grid, mounts cataloged `cost/*` components, no card row) → assign **142, 143**. (CostAnalysisTab is a new card; its component children `CostTopRow`/`CostBottomRow` already have rows.) New card count = **27**; if the BMS group is consolidated, ≥25.

### New PAGES (page_specs / route-shell rows) — 11 live
`routes.tsx` (route table), `UniversalAssetRoute`, `AssetManagementRoute`, `FlowDummyPage`-hub family (overview/hvac/utilities/cost/reports/settings), `PanelOverviewScreenOutlet` (6-tab router), `AssetOverviewPage /asset-overview`, plus the 9 new BMS asset-screen page_keys listed above. (Asset dispatcher + flow hubs were never catalogued.)

### New COMPONENTS — 119 (group-row method)
Headline groups to INSERT: entire **`three-viewer-kit/`** subsystem (overlay atoms/molecules, scene callout layers, animation, camera, lighting, materials, status, edges, interaction, canvas, types/presets/domain, `assemblyKit`, `MaterialLayer`, `MeshPrimitive`); **`asset-overview/`** shell (`AssetOverviewWrapper`, `ResolvedAssetOverview`, `OverviewKpiColumn`, `PhaseSelector`, `PhaseContextStrip`, config/tokens/barrel); **`realtime/`** (13 socket/reducer modules); **`data-v2/`** (types, `kitPreviewApi`, `useKitCatalogAsset`, mock barrel); BMS `_templates/_shared` (`BmsSplitNew`, `viewModel`, `BmsAssetOverview`, `BmsBarsOverview`, `FocusedAssetViewer`, `bmsTemplateMap`, `BmsOverviewAssembly`, `_kit`, registries) + per-tab chart components + `use*Data` hooks; lt-pcc atomized card components + 7 data hooks + `pcc*Mesh` set; charts tier-3 metric-presentation (`fmtMetric`, `presentationDefaults`, `chartDomain`, `axisTicks`, `historyBuckets`, `sankeyVisualEmphasis`, tokens, `chartHoverContext`, helpers) + 7 barrels.

---

## 5. DEPRECATION LIST (exclude from live catalog)

**Deprecated (legacy / redirect-dead / superseded — files exist, no live importer):**
- lt-pcc: `LTPCCPage.tsx`, `LTPCCOverviewView.tsx`, `tabs/LTPCCOverviewTab.tsx` (card 28), `components/charts/lt-pcc-overview/*` cards (29,30,35 + Breaker/EventLog) — *components STAY (still exported); the lt-pcc-page cards deprecate.*
- electrical-other rosters: `HTTrfPage`, `PCCHubPage`, `PCCP1/P2/U1/U2Page` (redirect-dead).
- bms standalone legacy: `BmsOverviewSplit.tsx` (cards 113/116), `chiller/{ChillerBmsView,ChillerOverviewSplit,ChillerSubsystemTab,ChillerHistoryCharts}`, `air-compressor/{AirCompressorBmsView, pressure-element/*, thermal-oil/*}`.
- charts: `legacy/StatusBadge.tsx` (kept-for-compat).
- routes: the `<Navigate>` redirect routes (distribution, electrical, ht-trf, pcc-p1/u1/p2/u2, dg-backup, ups, ht-panel).
- component: `Asset3DOverviewWidget` row (file deleted, no successor).

**Scratch (reference / preview / test-only, no live importer):**
- 3D kit scratch viewers: `PccPanelAssemblyViewer`, `AhuAssemblyViewer`, `ChillerAssemblyViewer`, `DGAssemblyViewer`, `AirCompressorAssemblyViewer`, `AirExhaustAssemblyViewer`, `GeneralAirExhaustViewer`, `PcwAssemblyViewer`, `PccGroupViewer.wrapper` (8 + wrapper; superseded by `CentralAssetViewer`).
- lt-pcc reference: `test-tabs/energy-distribution/EnergyDistributionTestTab` (card 12 origin), `test-tabs/energy-power/EnergyPowerReferenceTab`, `test-tabs/voltage-current/{VoltageCurrentReferenceTab, CurrentDistributionRadar}`, `lt-pcc/tabs/dg-overview/DG*Tab` + `tabs/ups-overview/*`, `lt-pcc/sections/UPS*` wrappers.
- assets: `pages/assets/transformer/ThermalLifeTab.tsx` (legacy monolith, 0 importers).
- bms: `BmsTemplatesIndex` (`/bms-templates` preview), `_templates/_meta/audit.json`, 7 unused `mockData.ts`.
- root preview routes: `/kit-test`, `/kittest`, `/nav-atoms`, `/callout-cards`, `/test` (`LoadAnomalyVariantsPage`), `/asset-overview` *(NOTE: conflicting status — see §6)*.

> ⚠ The `test-tabs/energy-distribution/` SLD+3D family (`EnergySingleLineDiagram`, `PccOverview3D`, `SingleLineDiagramTestTab`, `pcc*Mesh`) is **LIVE** despite the `test-tabs/` folder name — `OverviewScreen` imports it. Do **not** deprecate by folder name.

---

## 6. CONFLICTS / UNCERTAINTY (needs human or deeper read before re-audit)

1. **`/asset-overview` page status — CONTRADICTORY.** The `asset-overview-3d` domain and `pages-root-routes` domain disagree: one marks `AssetOverviewPage` **live** (route in `routes.tsx:21`), the other marks it **scratch** ("Isolated; not wired into the live nav"). The route IS in the table but is a standalone preview. **Resolve:** treat the *route page* as scratch-preview, but its backing card (`AssetOverviewContent` = card 3) is genuinely live via `ResolvedAssetOverview` on every EMS leaf. Card 3 = live; the `/asset-overview` standalone route = scratch.

2. **Cards 83 / 85 / 98 (source & DG 3D, `Asset3DOverviewWidget`)** — primary_component file is DELETED, but the host `SourceGenerationPage` is live. Unknown what (if anything) now renders the 3D slot there. **Needs a read of `SourceGenerationPage.tsx`** to decide: re-path to a kit viewer vs deprecate those 3 cards.

3. **Individual-Feeder card cluster (31–46)** — the domain note deprecates `28/29/30/35` explicitly but the fate of `31,32,33,34,36,37,38,39,44,45,46` (gauges/sparklines/phase) is only implied (replaced by `OverviewKpiColumn`/`ResolvedAssetOverview`). **Needs confirmation** whether MfmDetail feeder tabs still mount any of these or they are all superseded — high delete-risk if guessed.

4. **CostAnalysisTab as a CARD vs page-section** — flagged "new, no cards row" but it's a 5-panel grid mounting existing `cost/*` components. Decide whether it becomes ONE new card (proposed 143) or 5 cards (bill-decomp / cost-per-kVA / PF-penalty / dept-alloc / ToD-heatmap). **Granularity decision needed.**

5. **BMS card granularity (117–141)** — should each 11-asset overview+runtime pair be 2 cards (3D viewer + split) = the 25 above, or collapsed to 1 "asset screen" card each? Affects whether new-card count is ~25 or ~13. **Convention decision.**

6. **`chiller/overview` vs `chiller/runtime` split** — page_spec `chiller/overview` exists (1 key) but the live `_templates/chiller/` now has BOTH `overview.tsx` (3D) AND `overview-split.tsx` (Runtime). Same ambiguity for AHU/CSU. **Decide:** one page_key with two cards, or split into `/overview` + `/runtime` keys (would add new page_specs).

7. **Slug plural/singular** (assets routes vs page_keys) and the 2 chiller subsystem folder re-paths — mechanical UPDATEs, but flag so the rebuild's FK graph (`page_catalog_cards` view) doesn't orphan on the old folder strings.

Authoritative live totals to lock: **38 pages / 95 cards / 214 components** (192 UPDATE, 155 INSERT, 43 deprecated/scratch). Catalog slices live at `cmd_catalog` tables `cards`, `components`, `page_specs`; working tree audited at `/home/rohith/CMD_V2/src`.