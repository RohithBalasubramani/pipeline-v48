# CMD V2 Payload Verification — what V48 Layer 2 must emit

> **⚠ SUPERSEDED IN PART (2026-06-29) by the payload-morph: Layer 2 no longer emits the whole per-tab frame.** Per the corrected contract, Layer 2's per-card OUTPUT is `{ exact_metadata, data_instructions }` (Decision A, HYBRID) — the AI authors the finished METADATA block and emits a parseable data_instructions recipe; HOOK/HELPER functions parse it and FILL the DATA. The "two frame dialects (emit the right one per page)" / "Layer 2 emits the backend frame" model below is **stale** — the per-tab dialects (`flat_asset` / `widgets_envelope` / `column_row` / `shared_context`) survive ONLY as the DATA-FILL (mapper-input) shape the helper targets, NOT as Layer-2 output. See **`V48_PAYLOAD_MORPH_CORRECTION.md`** (the canonical doc) for the corrected grounding; this file is retained as the PRE-MORPH boundary verification.

> Verified 2026-06-23 by reading `/home/rohith/CMD_V2/src` at the real boundaries (mock fixtures, mapper input/backend frame, api wire, component props). Grounded with file:line citations.
> **Bottom line: HOLD-WITH-EXCEPTIONS** — the premise holds at the **backend-frame boundary**, not at component-props. *(Pre-morph framing; see banner — Layer 2 now emits the METADATA half at producer output + a data_instructions recipe, not the whole frame.)*

## 1. The boundary answer

> **Post-morph correction (canon):** this section describes the **DATA-FILL** boundary only. Layer 2 does NOT emit "the whole frame" here — it emits `{ exact_metadata, data_instructions }` per card; the data_instructions recipe is parsed by the HOOK/HELPER, which fills the DATA frame described below. The METADATA half is authored by the AI at the **producer/viewModel output** level (the per-card `{data+metadata}` payload), *downstream* of this mapper-input boundary. `viewModel.ts` is therefore **no longer an untouched black box** — it is the producer Layer 2 mirrors. See `V48_PAYLOAD_MORPH_CORRECTION.md` §1–3.

- **V48 Layer 2's DATA fill targets the BACKEND-FRAME boundary** (= the WebSocket frame, = the `mapper.ts` *input*). The frontend keeps `mapper.ts → viewModel.ts → Cards.tsx` as-is **for the DATA half only**; the METADATA half (labels/units/rosters/order/thresholds/contracts/colors/badges/tabs) is now Layer-2-authored at producer output.
- **That frame is provably plain JSON for every card type:**
  - The transport `JSON.parse(evt.data)`s every frame (`mfmPageSocketClient.ts:157`, `assetPageSocket.ts:159`) — **nothing crossing a socket can be a function or ReactNode** (structurally impossible).
  - Wire → mapper-input has **zero transformation**: the reducer stores `widgets` verbatim (`aggregateFrameReducer.ts:151-153`). The mapper sees the wire bytes unchanged.
- **The earlier "BREAKS" verdict was at the WRONG boundary** (component-props / viewModel output). At props, `EventTimelineChart` needs `value:(p)=>number` accessors and `DataTable` needs `render:(row)=>ReactNode` — not JSON. But those functions are minted in `Cards.tsx` JSX (`voltage-current/Cards.tsx:107-121,292-349`), **downstream of everything V48 touches.**

### Two frame dialects — these are the DATA-FILL (mapper-input) shapes ONLY, NOT what Layer 2 emits per card
> **Corrected (canon):** the per-tab dialects survive ONLY as the shape the HELPER fills (the `data_fill_shape`/mapper input). The full per-tab dialect set is `flat_asset` / `widgets_envelope` / `column_row` / `shared_context`. They are NOT the Layer-2 per-card emit (which is `{exact_metadata, data_instructions}`). The AI-morphable METADATA is a per-card payload (`HeatmapViewModel` / `RailViewModel` / `HpqPresentation`), dialect-free. See `V48_PAYLOAD_MORPH_CORRECTION.md` §2.
- **Flat `AssetPageFrame`** (`flat_asset`) — asset tabs (DG, transformer, UPS): `{type, asset_id, snapshot:{…}, <historyArrays>}` (`assetPageSocket.ts:27-36`).
- **Keyed `widgets{}` envelope `AggregateSnapshotFrame`** (`widgets_envelope`) — electrical/lt-pcc panel-overview: `{…, widgets:{cumulative,live_power,energy_trend,demand_profile}}`. Discriminator `isAggregateEnvelope`: has `widgets`, and **no** `queue`/`buckets`/`enqueue` keys (`aggregateFrameReducer.ts:172-179`).

## 2. Per-card-type payload (frame boundary)

> **Corrected (canon):** the shapes below are the **DATA-FILL frame** (mapper input) the helper targets, NOT the Layer-2 per-card output. The `plain-but-preformatted` strings/labels/colours/badges in these rows are the **METADATA tier the AI now morphs** at producer output (byte-identical default) — they are no longer opaque backend strings Layer 2 ignores. The per-card METADATA payload to mirror is `HeatmapViewModel` / `RailViewModel` / `HpqPresentation`, not these frame rows.

| Card type | Frame JSON shape | how_shaped |
|---|---|---|
| DG Engine & Cooling | flat; `points:[{label,bucket,coolant,oilTemp,intake,exhaust,oilPressure,speedRaw,speedPct,loadPct,runState}]` | plain-raw |
| DG Voltage & Current | flat; `vHistory:number[3][24]`, `cHistory:number[3][24]`, `neutralHistory:number[24]`, `today:{…}` | plain-raw |
| Heatmap (mock) | `data:{rows[],cols[],values:number[][]}` | plain-raw |
| History envelope (V/I/PQ-history) | `{range,start,end,sampling,columns[],buckets:[{bucket,[metric]:number\|null}],kpis{},events?[]}` | plain-but-preformatted |
| Column-row (feeder live) | `{columns[],queue:[{ts,active_power_total_kw,…}],status:{…:'stable'}}` | plain-raw (status strings preformatted) |
| UPS Battery & Autonomy | flat; `batteryHistory:[{…}]` + `snapshot{battery_health_status,battery_health_caption}` | plain-but-preformatted |
| Transformer Thermal & Life | flat; `timeline:[{slot,hotspotC,oilC,windingC,loadPct,efficiencyPct}]`, `aging:[…]`, `snapshot{…,aging_caption}` | plain-but-preformatted |
| PCC Energy & Power (aggregate) | `widgets:{cumulative{active_mwh,limit_mvah,status,summary},live_power{apparent_kva,active_kw},energy_trend{buckets},demand_profile{buckets,kpis}}` | plain-but-preformatted |
| PCC Energy Distribution (aggregate) | `widgets:{header{measured_input_kwh,loss_pct,best_path,main_meter},incomers[{…,status}],consumers[{…,share_pct,efficiency_pct}],sankey{nodes[{id,label,kwh,layer,kind,mfm_id?}],links[]},ai_summary{badge,text}}` | plain-but-preformatted (server-domain raw kWh) |
| KPI/Donut/Gauge/Sankey/Radar/Line (mock envelope) | `WidgetResponse<T>`; data carries hex colors + preformatted strings (KPI `value:'4,280'` is a **string**) | plain-but-preformatted |
| asset-viewer (3D mock) | `{name,assetType,hotspots:[{id,label,description,position:[x,y,z],status}],stats:[{label,value,unit}]}` | plain-but-preformatted |
| story-card (composite) | `{narrative{content:markdown},alerts[],events[],diagnostics{hypotheses[{confidence,evidenceFor[],evidenceAgainst[]}]},uncertainty}` | plain-but-preformatted |

## 3. Verdict: HOLD-WITH-EXCEPTIONS

- **HOLDS:** "Layer 2 emits JSON" is TRUE — the frame is structurally plain JSON for every card.
- **Exception 1 — "simple JSON" is overstated:** plain but **not raw**. Frames carry preformatted strings (KPI value strings, status/severity enums, `ai_summary`, captions, badges, hex colors for the mock-envelope family). **Corrected (canon):** these preformatted labels/units/colours/badges are the **METADATA tier the AI now AUTHORS and morphs** (`exact_metadata`, byte-identical default) at producer output — they move from "backend computes today, irrelevant to Layer 2" to "Layer-2-owned, AI-morphable." Only the DATA numbers stay backend/worker-filled.
- **Exception 2 — "L5/L6 retire" is only partly true; the work SPLITS:**
  - **Stays FE (genuinely leaves the pipeline):** render-shaping — tones, axis domains/`buildChartDomain`, null-row trimming, label synthesis, and self-consistent `loadKva`/`headroomKva` re-derive (`thermal-life/mapper.ts:43-47` — the mapper overrides the backend's `headroomKva`, so **V48 need not emit headroom**).
  - **Relocates into Layer 2 + labour code (NOT retired):** the **data-domain** work — aggregate lt_panels → the `widgets{}` / flat envelope, compute `measured_input_kwh`/`loss_pct`/`share_pct`/`efficiency_pct`/demand KPIs, build the layer-indexed `sankey.nodes`, classify `status`, write `ai_summary` + captions, bucket histories with explicit `null` for gaps.

## 4. Hard exceptions (all DOWNSTREAM of the frame → NOT V48's problem to emit)

Every one is a function/ReactNode created in the `Cards.tsx` JSX adapter; V48 only emits the underlying data they read:
1. `DataTable` — `columns[].render:(row)=>ReactNode` etc. → V48 emits the **rows**; JSX column-builder stays FE.
2. `EventTimelineChart` — `value:(p)=>number` accessors → V48 emits `EventTimelinePoint[]`; accessors stay FE.
3. 3D `Asset3D` — L2-fed payloads (`annotations`, `breakerStatuses`, `loadHeatmap`, `kpiItems` keyed by `targetName`) **are** JSON; only `THREE.Object3D` is runtime (never L2-fed).
4. Interactive callbacks (`onNodeClick`, `onTileSelect`, `onPeriodChange`, …) — all optional; host supplies; static render works without.
5. `ProgressKpiCard.headerAction/progressContent: ReactNode` — optional JSX slots; host-supplied.

**Net: no card is un-emittable at the frame boundary.**

## 5. What Layer 2 + labour code must actually do

Not "dump query rows," not "re-derive viewModels." A **data-domain shaping pass** in between:
- **Small:** preformat KPI value strings, classify status/severity/badge enums, attach hex colors (mock-envelope family), ISO `bucket` strings.
- **Medium (the real labour):** aggregate lt_panels into the keyed `widgets{}` envelope, compute the derived energy/loss/share/efficiency/demand figures, build sankey nodes, classify status, write `ai_summary`/captions, bucket with `null` gaps.
- **DATA-DOMAIN AGGREGATION HOME (canon — user decision):** this data-aggregation tier **RELOCATES into OUR pipeline's worker/helper functions** — it is **NOT** a reuse of the backend2 `:8889` per-page consumer strategies. (The earlier "reuse the frame backend2 already emits, not re-author" stance is SUPERSEDED by the user decision to relocate aggregation into our own workers; backend2's `services.fetch_live`/`fetch_bucketed`/`_timefilters` may serve only as a *reference* for the math, not as the producer V48 calls.) Note also: L5 is RETIRED and L6/L6.2 render-shaping retired; only the data-domain aggregation moves into the workers.

## 6. Gaps / watch-list

1. **BMS Chiller E&P** — no captured fixture (kill-switch off); its frame is mapper-inferred, least-validated.
2. **Y-axis auto-scale** needs a separate HTTP call `GET /api/mfm/{id}/config/` (rated_kw nameplate) — NOT in the WS frame. V48 must populate that config endpoint too or the FE loses auto-scaling.
3. **Value-semantics quirks** — fraction-vs-percent (`load_factor_pct` sometimes `0.8`), synthetic "Unmetered distribution" sankey node with `mfm_id:null` — must be reproduced exactly.
4. **Live 3D catalog** (`kitPreviewApi.ts`, `KitCatalogAsset`/`BmsOverviewTemplate`, real HTTP) is richer than the mock `asset-viewer` — if V48 drives 3D, it's a bigger payload.
5. **Not independently confirmed** that the documented `widgets{}` keys match byte-for-byte — before building L2 labour, diff a live `ws/mfm/{id}/energy-distribution/` capture against `energy-distribution/mapper.test.ts:17-150`. (Use backend2 `:8889` as a **reference for the aggregation math only**; per canon the producer is OUR pipeline's worker, not a backend2 reuse.)

6. **Morph-status scope is now WIDESPREAD, not ~7 cards (canon, live-verified 2026-06-29).** A Storybook §B4-sentinel sweep (`V48_STORYBOOK_MORPH_VERIFICATION.md`) found **~36/59 EMS cards strongly/moderately payload-driven across ALL panels** — RTM + HPQ are validated references; ~23 weak/zero are a punch-list. The OLD "only ~7 cards / 2 tabs morphed" claim (from the static `PAYLOAD_AUDIT_ALL.md`) is SUPERSEDED. When scoping what is buildable today as a §B4 one-payload reference, follow the live sweep, not the static audit count.

### Key files
`src/realtime/aggregateFrameReducer.ts`, `src/realtime/assetPageSocket.ts`, `src/api/backend/backendTypes.ts`, `src/data-v2/types.ts`, `src/pages/assets/transformer/tabs/thermal-life/mapper.ts`, `src/pages/electrical/lt-pcc/panel-overview/energy-distribution/mapper.test.ts`, `src/components/charts/primitives/EventTimelineChart.tsx`, `src/components/charts/primitives/DataTable.tsx`, `BACKEND_RESPONSE_EMS_TABS.md`.
