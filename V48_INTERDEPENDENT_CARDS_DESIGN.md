# V48 — Interdependent Cards: card-level atoms + shared context (Approach B)

> Decided 2026-06-23. Solves: card-level atomization (per-card Layer 2) AND page interdependency intact, with NO data duplication. Verified against the real CMD V2 RTM page.

## The problem

Pages like **Real-Time Monitoring** (panel-overview) have all cards interdependent — one shared data buffer + one shared cursor/selection/metric, wired in a single hook (`useRealTimeMonitoringData`). Today that forces **page-level** payloads. V48 needs **card-level** atoms (per-card Layer 2) WITHOUT losing the coupling.

## Chosen approach: B — lean card atoms + one `shared_context`

The shared data lives **once**; cards are lean atoms that point at it. NOT duplicated into each card (that was rejected Approach A — triplicated buffer + fragile dedupe, bad under live streaming).

```
worker (once/group) ─► shared_context { history[]/buffers, config, interaction }  ──┐
Layer 2 per card    ─► lean atom × N { $ctx, atom, exact_metadata, data_instructions } ─┤ stitcher ─► { shared_context, cards:[atoms] }
```

> **3-tier (post payload-morph, §B4):** each atom is lean ONLY on DATA (no buffer — it points at `$ctx.history`) but carries its OWN full per-card **`exact_metadata`** (the AI-authored METADATA tier: labels/units/colours/rosters/order/thresholds/contracts/badges/tabs) + a parseable **`data_instructions`** recipe the helper parses to FILL DATA. Don't duplicate the BUFFER (single copy in `shared_context`); DO give each atom its own METADATA — that IS the morphability. The old `{ $ctx, atom, reads/binds/emits }`-only atom (no METADATA block) is SUPERSEDED. See `V48_PAYLOAD_MORPH_CORRECTION.md` §4 + `V48_BUILD_SPEC_CONTRACTS.md` §5/§7.

### Payload shapes (RTM)

```jsonc
{
  "frame": {
    "page_key": "electrical/lt-pcc/panel-overview/realtime-monitoring",
    "interdependency_group": "rtm-combo",
    "shared_context": {                          // THE ONLY COPY OF FEEDER DATA ON THE PAGE
      "$id": "rtm_ctx",
      "asset": { "mfm_id": 4021, "panel_label": "PCC-1A" },
      "history": [ /* HistorySample[] — EXACT types.ts shape: {label, sections:[{id,label,totalKw,totalKvar,totalKva,feeders:[FeederReading]}]} */ ],
      "interaction": {                           // seeds the host useState; host stays sole owner
        "cursor":    { "dimension": "selectedSampleIndex", "initial": "latest", "live_default": true },
        "selection": { "dimension": "feeder|section|panel", "initial": { "kind": "panel" } },
        "metric":    { "dimension": "metric", "domain": ["all","kw","kvar","pf","voltage","current","iUnbalance"], "initial": "all" },
        "couplings": [ /* from cmd_catalog card_link/selection_dimension; e.g. heatmap.cellSelect → sets cursor+feeder, freezes live, ws select_feeder; footer.scrub → cursor; rail.shape ← selection */ ]
      },
      // config = TRULY-SHARED group static only. NOTE: `section_contract_kw` is the "AI-default, worker-overridable"
      // slot and is now PER-CARD METADATA carried on the heatmap atom as `sectionContracts` (Open Decision D RESOLVED:
      // atom-carried, NOT shared config — V48_BUILD_SPEC_CONTRACTS.md §7). Shown here only for legacy reference.
      "config": { "sample_count":12, "tick_interval_ms":2000 }
    },
    "cards": [                                     // lean atoms — lean ONLY on DATA ($ctx.history); each carries its OWN exact_metadata
      { "$ctx":"rtm_ctx", "card_id":"rtm_heatmap", "render_slot":"composite_card.body",
        "atom": { "kind":"heatmap-feeder-grid", "role":"selector",
                  "reads":{"buffer":"$ctx.history","group_by":"sections","metricColumns":["kw","kvar","pf","voltage","current","iUnbalance"]},
                  "binds":["cursor","selection","metric"], "emits":["cellSelect","sectionToggle"] },
        // exact_metadata = the AI-authored METADATA tier, byte-identical defaults (HeatmapViewModel METADATA keys):
        "exact_metadata": { "title":"…", "metricTabs":[], "metricAxisLabels":{}, "statusColors":{}, "statusLegend":[],
                            "bandThresholds":{}, "units":{}, "descriptors":{}, "selectionColors":{},
                            "sectionContracts":{ "incomers":2700,"ups":1500,"bpdb":600,"hhf":600 } } },   // AI-default, worker-overridable
      { "$ctx":"rtm_ctx", "card_id":"rtm_footer", "render_slot":"composite_card.footer",
        "atom": { "kind":"time-scrubber", "role":"cursor-control", "reads":{"buffer":"$ctx.history","axis":"labels"},
                  "binds":["cursor","metric","liveMode"], "emits":["scrub","stepBack","stepForward","togglePlay"] },
        "exact_metadata": { "title":"…", "metricTabs":[], "playGlyphs":{}, "stepLabels":{} } },
      { "$ctx":"rtm_ctx", "card_id":"rtm_rail", "render_slot":"rail_card",
        "atom": { "kind":"overview-rail", "role":"derived-view", "reads":{"buffer":"$ctx.history","shape":"buildRailViewModel(selection,cursor,history)"},
                  "binds":["cursor","selection"], "emits":["clear"] },
        // RailViewModel METADATA keys:
        "exact_metadata": { "title":"…", "subtitle":"…", "statusBadge":{"dsTone":"…"},
                            "supply":{"title":"…","unit":"…","deltaColor":"…","deltaGlyph":"…"},
                            "trend":{"title":"…","lineColor":"…","areaOpacity":0}, "quickStatsLayout":"…" } }
    ]
  }
}
```

## How Layer 2 handles it

**Step 0 — partition (deterministic):** from 1a's cards + `cmd_catalog` couplings (`card_link`/`interdependency`/combo/`selection_dimension`), split the page into **interdependent groups** + **standalone cards**.

**For each interdependent group — 3 moves:**
1. **Build `shared_context` ONCE (worker, group-level)** — the relocated L6.2 aggregation queries the data (from 1b's asset + column basket) and builds the one `history[]` + config. **AI decides the aggregation spec; the worker labours.** Output = one `shared_context`.
2. **Fan out atoms (AI, parallel per card)** — each card's AI run gets {shared buffer (read-only), 1a story, the card's `cmd_catalog` row} → emits its lean atom = `{ $ctx, atom, exact_metadata, data_instructions }`. The atom is lean on DATA (points at `$ctx.history`) but carries its **OWN full `exact_metadata`** (the AI-authored METADATA tier, byte-identical defaults) + a parseable `data_instructions` recipe. **Couplings come from `cmd_catalog`, AI only validates** (not AI-invented).
3. **Stitch (deterministic)** — resolve each card's `$ctx`↔`shared_context.$id`, run the helper DATA-fill from `data_instructions`, merge `{...exact_metadata, ...filled_data}` per card → emit `{ shared_context, cards:[atoms] }`.

**Standalone cards** skip Move 1 — the per-card AI emits a fully self-contained card (same `{ exact_metadata, data_instructions }` output, but DATA filled inline, no `$ctx`).

> Refinement to "Layer 2 runs parallel per card": **parallel per card for the atoms, with a one-time group-level shared-context pre-pass (worker) before the fan-out.** Per-card OUTPUT is the morph contract `{ exact_metadata, data_instructions }` (Decision A) — group atoms point DATA at `$ctx`, standalone cards fill DATA inline; `exact_metadata` is present and full either way.

## Frontend handling (CMD V2 side)

> ⚠ **IN PROGRESS / PROVISIONAL (user, 2026-06-29):** the interdependency handling on the CMD V2 / EMS frontend is **STILL BEING BUILT** — how the shared-state mechanism coexists with one-payload-per-card is not finalized. RTM is the reference, but the frontend coupling below can still move. Re-verify when the frontend morph/interdependency settles. (Per-card `exact_metadata` is the settled half; the shared-cursor wiring is the unsettled half.)

1. **`joinSharedContext.ts`** (new, ~30 lines) — `Map<$id, shared_context>`; resolves each card's `$ctx`; logs+placeholder on miss.
2. **`useRealTimeMonitoringData.ts` — source half swapped only.** `history` seeded from `shared_context.history` instead of the socket snapshot; the 5 `useState`s seeded from `interaction.*.initial`. **Lines 90-219 (derivation + handlers) unchanged.** Socket live-merge (`useMfmAggregateSocket`, freeze/resume) kept for API mode.
3. **`validateRtmWiring.ts`** (new) — asserts `couplings`/`binds` match the host's reads/writes; hard-logs on drift. Validation, not execution.
4. **`RealTimeMonitoringLayout.tsx` — unchanged.** Same hook call, same 2-card shell (composite Card = heatmap+footer, separate rail Card).

## Verified: behaves EXACTLY as the EMS frontend (with one condition)

- **Drop-in type.** The hook consumes `snapshot.history: HistorySample[]` (types.ts:85-89). `shared_context.history` IS that exact `HistorySample[]` (types.ts:37-70) → swapping the source changes nothing.
- **Source-agnostic downstream.** Hook lines 90-219 (`effectiveSampleIndex`, `cursorSample`, `rollup`, `selection`, `railVM`, `heatmapSections`, handlers) read only `history` + state.
- **Same start state.** `interaction` seeds match the current `useState` defaults (hook:64-72).
- **Components untouched.** Heatmap/footer/rail pure-render from derived values.
- **CONDITION for identical LIVE behavior:** keep the **socket as live-merge owner**; `shared_context.history` is the **SEED** (not the sole source). Then live ticking / freeze-on-stop / resume / `select_feeder` echo are byte-identical. (Sole-source-without-socket would change live behavior.)

**Verdict: static + interaction + render = provably identical; live = identical as long as socket stays the live-merge owner.**

## Generalization — verified across ALL 11 coupled/page-wise tabs (2026-06-23)

Verified B against every interdependent family (not just RTM). **Verdict: B GENERALIZES TO ALL — no hard failures.** The only thing that genuinely cannot enter `shared_context` is a **function**, handled host-side (same as RTM). The RTM design above is the *special case*; to be tab-agnostic it adds 6 refinements:

1. **`interaction` = any host-owned scalar/enum seed** — not just `cursor/selection/metric`. Add `selectedLabel`/`selectedPeriod` (panel V&C, H&PQ), `selectedBucket` (DG Ops, int index), `selTime`+`series`+footer-`tab` (BMS), `compositeView` (UPS source-transfer), per-card `sampling` (electrical V&C/PQ, UPS battery/source-transfer). **Rule: any host-owned plain scalar/enum is a seed from `interaction.initial`.**
2. **Multi-buffer / multi-window `shared_context`** — not just one `history[]`. Some tabs need **N independently-windowed buffers** (UPS battery-autonomy: live + 2 windowed = 3 sockets / 2 sampling windows; UPS source-transfer: live + composite; transformer thermal-life: one multiplexed socket). **Each buffer carries its own range/sampling seed and keeps its own socket as live-merge owner.** "One buffer" is the RTM special case.
3. **Whole-tab-snapshot IS the context** — forbid Layer 2 from splitting a tab into per-card data slices when (a) a card reads a sibling's stats (electrical V&C "Current Health" reads `currentHistory.stats`), or (b) a shared axis/threshold derives from one source (electrical RTM axis, PQ `limitPct`→chart `maxLine`). The `shared_context` is the whole tab snapshot; cards are lean read-only views.
4. **Functions NEVER travel in `shared_context`** (hard invariant). Today some tabs inject `onSamplingChange` setters into the data object. All handlers/setters (`onSamplingChange`, kpi/footer `onClick`/`onSelect`, `requestChart`) are **re-attached host-side after the pure viewModel** — the payload is pure serializable data only.
5. **`apiExtras` / whole-typed-boundary passthrough** — carry the **entire** typed snapshot (incl. extras like H&PQ `priorityRows`/`signature`), not a hand-picked subset.
6. **Known gap (not a failure):** H&PQ's socket is flag-gated off (`PANEL_OVERVIEW_HPQ_API_ENABLED=false`); B verified on mock, but live-merge identicality is only testable once the flag flips.

**Per-tab outcome:** 3 cleanly identical (electrical RTM — *simpler* than RTM-combo, interaction-free; DG voltage-current — pure data-share; lt-pcc Voltage & Current). The rest work with refinements 1–5; the two "hard breakers" (electrical voltage-current sibling-reach + function-prop) are fully handled by #3 + #4. (Breaker evidence: `electrical/tabs/voltage-current/voltageCurrentViewModel.ts:326-327` + `types.ts:134`; `power-quality/viewModel.ts:465-470`; `ups/tabs/battery-autonomy/BatteryAutonomyTab.tsx:37-46`.)

## Open decisions

> **Resolved by the payload-morph (2026-06-29, `V48_PAYLOAD_MORPH_CORRECTION.md` + `V48_BUILD_SPEC_CONTRACTS.md`):** (i) per-card output = `{ exact_metadata, data_instructions }` (Decision A) — each atom carries its OWN `exact_metadata`; B's two tiers become THREE (lean-on-DATA, fat-on-METADATA). (ii) `sectionContracts` / HPQ `signature.spokes`+`selectedName` are **per-card METADATA carried on the atom** (AI-default, worker-overridable) — NOT `shared_context.config` (Open Decision D RESOLVED: atom-carried). (iii) the three "dialects" survive ONLY as the DATA-fill (mapper-input) shape via `data_fill_shape` (renamed from `frame_dialect`) — never as Layer-2 per-card output.
> Still OPEN (pending user, shared with the build-spec review): `$ctx` source form (dotted `$ctx.history` vs bare + buffer_key), test-DB contents, and the build-spec review fixes (`column_row` dialect, `data_fill_shape` derivation, partition orphan card 160, composite/sld `payload_shape` map).

1. **Live ticks = seed (recommended)** — `shared_context.history` seeds; socket owns live-merge. (Confirm; the alternative changes live behavior.)
2. **Couplings from `cmd_catalog`** (`card_link` + `interdependency`/`selection_dimension`), AI validates only. Confirm these columns are populated for the grouped cards (ties to the DB rebuild).
3. **Move-1 spec** — AI decides the aggregation spec + worker executes (recommended), or Move 1 fully deterministic from `cmd_catalog` recipes.
4. **Atom granularity** — keep 3 atoms (1:1 with `cmd_catalog` rows) mounted into the existing 2-card shell via `render_slot`.
5. **Generalization later** — B's per-page hook now; migrate to a generic `useLinkAssembler` (Approach C) once ≥2 more coupled tabs (V&C/BMS/DG) are live. B and C share this same `shared_context`/worker tier, so B→C is a promotion, not a rewrite.
