> V48 build-spec correction — re-grounded against CMD V2 payload-morph (commit dfded69, CLAUDE.md §B4 'one payload per card'). Generated 2026-06-29.

# Re-Grounding V48 Against CMD V2 "One Payload Per Card" (commit dfded69, CLAUDE.md §B4)

The V48 build-spec was written on a **per-tab-frame** model: Layer 2 emits a whole backend frame in one of several per-tab dialects (`flat_asset` / `widgets_envelope` / `column_row` / `shared_context`) at the `mapper.ts` *input* boundary, and the FE `mapper → viewModel → Cards.tsx` chain is treated as an untouched black box. CMD V2's payload-morph rework moved the contract: each card is now a **pure function of ONE payload object `{data + metadata}`**, and the AI-morphable half (METADATA) lives at the **producer/viewModel output** level — *downstream* of the mapper-input boundary the spec targets. The OLD "two dialects / Layer 2 emits the whole frame" union is SUPERSEDED — those per-tab dialects survive ONLY as the DATA-fill (mapper-input) shape the helper targets, not as Layer 2 output. Below is the corrected grounding.

---

## 1. The corrected card contract — one payload per card

A card is a pure function of **ONE flat object** carrying BOTH live DATA and chrome METADATA, **every key EXACTLY once**. There is no second `root` object. (CLAUDE.md §B4:213–218.) Conceptually two tiers ride the payload; a third never does:

```
Card payload (ONE object, every key once):
  ── DATA tier ────────── the numbers + initial interaction state, from the backend
  ── METADATA tier ────── labels · units · colours · rosters · order · thresholds
                          · contracts · badges · tabs  (frontend-static)  ← THE AI MORPHS THIS
  ── (DESIGN-SYSTEM CHROME) pixel geometry · fonts · Card/SegmentedControl markup · grid
                          → tokens/primitives, NEVER on the payload (by design)
```

Note: `{data: {...}, metadata: {...}}` is the right *mental* split, but the real emit **flattens both into one namespace** — NOT `{data:{}, root:{}}`. A second object was the exact bug that bred duplicate `title`/`sections`/`contractKw`.

**Concrete RTM example — the heatmap card** (`buildHeatmapViewModel`, `heatmapMetrics.ts:231-260`), every key once:

```ts
{
  // DATA (backend-fed + initial interaction state)
  history,                 // AUTHORITATIVE roster + ORDER; HeatmapSection[] derived on demand, never stored
  metric: 'all',           // initial interaction state
  selectedSampleIndex, liveMode, selectedSectionId, selectedFeederId,
  // METADATA (AI-morphable — folded in from the former dead "root")
  title,                   // label
  metricTabs,              // tabs
  metricAxisLabels,        // labels
  statusColors,            // colours
  statusLegend,            // badges/legend
  bandThresholds,          // thresholds
  units, descriptors,      // units / labels
  selectionColors,         // colours
  sectionContracts,        // contracts  ({incomers:2700, ups:1500, bpdb:600, hhf:600})
}
```

Invariants the emit must satisfy: **byte-identical default** (every metadata default = today's rendered bytes; only a mutation moves a render), every metadata field **REQUIRED and always populated by the producer** (`data.X ?? CONST` is morphable only if the producer always fills X), and new renderers **opt-in default-OFF** (`showLegend:false`). The dead duplicates (`sections`, per-section `contractKw`) are gone and locked by `@ts-expect-error` in `morphPayloadTypes.test.ts`. Reference shapes to mirror: `HeatmapViewModel` and `RailViewModel` in RTM's `types.ts`.

---

## 2. What the "dialect" question becomes

**The METADATA dialect dissolves into per-card payloads.** There is no per-tab "frame dialect" for the morphable half — every card has its own one-payload shape (`HeatmapViewModel`, `RailViewModel`, the 5 HPQ `HpqPresentation` blocks, …). The old per-tab dialect set `flat_asset | widgets_envelope | column_row | shared_context` does **not** describe what the AI emits; it survives only as the per-card `data_fill_shape` (mapper-input) the helper fills.

**But a per-tab/backend frame STILL EXISTS — for the DATA fill only, and it lives at the MAPPER INPUT, not at Layer-2 output.** The socket frame (`ws/mfm/{id}/{screen}/`) is what `*Mapper.ts` consumes; it is still real and still has tab-shaped variation (RTM's `real-time-monitoring` aggregate with `widgets.feeders[].queue[]`; HPQ's `power-quality-summary` with 5 fleet widgets; asset tabs' flat snapshot). The morph did **not** touch it. So:

| Concern | Where it lives now | Shape |
|---|---|---|
| **DATA fill** (numbers) | **MAPPER INPUT** — the live socket frame OR a test-DB fixture in the same `Snapshot` shape | still per-tab/backend-frame-shaped (the only place "dialect" survives) |
| **METADATA** (morphable chrome) | **PRODUCER OUTPUT** — folded into each card's ONE payload | per-card payload shape, no tab dialect |

The key correction: the spec put the *whole frame* (data **and** the preformatted strings/labels/colours) at Layer-2 output in one dialect. Post-morph, the **DATA** half is a mapper-input frame the worker fills, and the **METADATA** half is a per-card payload the AI morphs — two different boundaries, not one.

---

## 3. V48 Layer 2 mapping (and why it's cleaner)

The §B4 golden flow states it verbatim (CLAUDE.md:201-202): *"AI reads the one payload and morphs the METADATA fields; the backend keeps filling the DATA fields."* That sentence **is** the V48 contract:

- **Layer 2 (AI) = the metadata producer** — i.e. `buildHeatmapViewModel()` / `buildHpqPresentation()`'s METADATA half. Per card it emits the METADATA block (labels, units, colours, rosters, order, thresholds, contracts, badges, tabs) with **byte-identical defaults**, and morphs them per prompt. It must NOT touch DATA fields or design-system chrome.
- **Worker = the DATA fill** — it populates `history` / `periods` / `apiExtras` (backend numbers + initial interaction state) from EITHER the live `ws/mfm/{id}/{screen}/` frame (production) OR a **test-DB fixture in the identical `Snapshot` shape** (offline/CI). The two are interchangeable at the mapper boundary; a byte-identical metadata default means swapping the data source moves nothing else.

**This is cleaner than the old per-tab-frame emit.** Old model: Layer 2 authored an entire dialect-typed frame mixing data with preformatted labels/colours/strings — a fat, tab-shaped, all-or-nothing payload. New model: the two halves are split by ownership, each card's METADATA is an independently-morphable flat object, and the DATA fill is produced by **OUR pipeline's own worker functions** (data-domain aggregation RELOCATES into V48 workers — canon user decision; NOT backend2 :8889 reuse, and L6/L6.2 render-shaping retired) into the same Snapshot shape.

**Exactly what Layer 2 emits per card now (canon Decision A, HYBRID):** Layer 2's OUTPUT is `{ exact_metadata, data_instructions }` — it AUTHORS the finished `exact_metadata` block (labels/units/rosters/order/thresholds/contracts/colours/badges/tabs, each key exactly once, every field defaulted byte-identical from the card's static config) AND emits a parseable `data_instructions` recipe; it does NOT emit the backend DATA numbers itself. The hook/helper parses `data_instructions` and FILLS the DATA keys. The **final merged card payload** is then ONE flat object = the union of (1) DATA keys and (2) `exact_metadata` keys, **each key exactly once**, no `root`, no duplicate `title`/`sections`/`contractKw`, **zero chrome**. (Practically: Layer 2 authors `exact_metadata` + `data_instructions`; the worker/helper fills the DATA keys; the stitcher hands one merged object per card.)

**Two boundary subtleties to encode:**
- `sectionContracts` (RTM) and `signature.spokes`/`selectedName` (HPQ) are **"AI-default, data-overridable"** — METADATA slots the backend MAY overwrite. The worker writes them when present, else the AI default stands. Not pure-metadata.
- **UI-selection state** (metric / scrub / liveMode / selectedFeeder + command callbacks) is a **third class** owned by the hook — assign it to neither Layer 2 nor the worker.

---

## 4. Interdependency — Approach B still holds (with one refinement)

> **Note (canon):** the FRONTEND interdependency wiring is **STILL IN PROGRESS / provisional** — the ownership model below (hook owns the shared cursor; 3-tier lean-on-DATA/fat-on-METADATA) is the intended contract, not a shipped/verified FE state.

**Yes — Approach B (`shared_context` + lean atoms) survives the morph unchanged in ownership.** "One payload per card" is an *intra-card output-shape* change, NOT a state-ownership change. The hook is still the **sole owner** of the shared cursor/selection/metric: commit dfded69 left the five `useState` cells (`liveMode`, `selectedSampleIndex`, `selectedFeederId`, `selectedSectionId`, `metric`) and all handlers byte-identical; it only folded interaction values into `buildHeatmapViewModel(...)` and derived `heatmapSections` from `heatmap.history`.

How shared cursor/selection is handled now: each card's payload carries a **read-only snapshot/seed** of the single hook-owned state (the heatmap payload's `metric`/`selectedSampleIndex`/`liveMode`/`selectedSectionId`/`selectedFeederId` are labelled "*initial* interaction state — the live hook seeds React state from these"). It is a `useMemo` projection of the one state, **not an independent owner**. Writes never flow through a per-card payload — cards emit events (`onCellSelect`/`scrub`/`setMetric`) that call hook setters. One emit → one setter → all three per-card payloads recompute consistently. Interdependency lives in the HOOK, above the payloads; consistency is structural. (`shared_context.history` stays the single buffer/SEED, socket remains live-merge owner.)

**The one refinement the morph forces:** B's two tiers become **THREE**. Each lean atom is lean only with respect to **DATA** (holds none — points at `$ctx.history`), but must now carry its **OWN full per-card METADATA block** (heatmap: `metricTabs`/`statusColors`/`statusLegend`/`units`/`descriptors`/`selectionColors`/`bandThresholds`/`sectionContracts`; rail: `RT_DIR_PRESETS`/`dsTone`/`lineColor`/`areaOpacity`). That metadata is exactly what §B4 says the AI morphs. **Don't duplicate the BUFFER (single copy in `shared_context`); DO give each atom its own METADATA — that IS the morphability.** The current atom sketch (`V48_INTERDEPENDENT_CARDS_DESIGN.md:38-47`) has only `reads`/`binds`/`emits` and no `presentation` block, so it is missing precisely the fields the golden flow morphs.

---

## 5. Morph-status caveat — what's buildable today

> **CORRECTED 2026-06-29 (canon MORPH STATUS, live-verified via `V48_STORYBOOK_MORPH_VERIFICATION.md`):** the morph is **WIDESPREAD, NOT just RTM + HPQ** — ~36/59 EMS cards are strongly/moderately payload-driven across ALL panels (incl. Energy & Power, Voltage & Current, Power Quality). RTM + HPQ remain the **validated reference** tabs (Main Heatmap 10/12, Total Feeder Consumption 8/9), but they are no longer the only morphable surfaces. The static `PAYLOAD_AUDIT_ALL.md` (~7 cards / 2 tabs) is **STALE/SUPERSEDED**; trust the live Storybook §B4 sentinel, not the static audit. ~23 cards remain weak/zero (the punch-list). The per-surface rows below are re-graded to the live signal.

| Surface | Status | Buildable today as a §B4 one-payload reference? |
|---|---|---|
| **RTM — panel-overview** (`lt-pcc/panel-overview/realtime-monitoring/`) | **DONE** — one-payload-per-card, AI-morphable, live-verified; the named §B4 template | **YES** — copy `HeatmapViewModel` + `RailViewModel` directly |
| **Harmonics & PQ — panel-overview** (`lt-pcc/panel-overview/harmonics-pq/`) | **DONE** — "greenest tab", 13/13 detail fields morph; `HpqPresentation` tree | **YES** — copy the per-card `HpqPresentation` blocks (note `PANEL_OVERVIEW_HPQ_API_ENABLED=false` gates the live DATA fill until fleet-PQ is served) |
| **Power Quality sub-cards — equipment-detail** (`tabs/power-quality/`) | **MOSTLY MORPHED** — live Storybook: Power Quality Card 8/12 STRONG, Spectrum Rows 2/4 moderate; some bar chrome / tick math (Distortion Profile, Load Impact 4/12) still weak | Mostly — usable; the weak sub-cards (Distortion Profile, Load Impact) are punch-list, not full references |
| **Voltage & Current — equipment-detail** (`tabs/voltage-current/`) | **PARTLY MORPHED** — live Storybook: Metric Strip 3/4, History Stats Strip 3/4, Health Summary 2/3 STRONG; Health/History cards 6-7/12 moderate; Deviation Band + Phase Rows 0/x zero. The known-wrong `Max: 430KW`/`Min: 410KW` unit bug + Phase Rows / Deviation Band are the remaining punch-list | Partly — the STRONG strips/summaries are usable references; the zero cards are "morph next" targets (NOT the whole tab) |
| **Energy-Distribution / Energy-Power — panel-overview** | **PARTLY MORPHED** (canon/live Storybook): ED — KPI Ribbon 6/7 STRONG, Energy Input & Flow cards 5/12 moderate; EP — Energy Trend 5/12 moderate, others 2-4/12 weak. (The OLD "UNVERIFIED, low glued counts ED=4/EP=17" was from the stale static audit.) | Partly — moderate cards usable; weak EP cards are punch-list |

**Disambiguation V48 must not conflate:** there are two surfaces per tab. The panel-overview RTM/HPQ are the **validated reference** ones; the equipment-detail and other surfaces are **partly morphed** (a mix of STRONG/moderate/weak cards per the live Storybook signal), NOT uniformly unmorphed. Grade morph status per-CARD from the live `V48_STORYBOOK_MORPH_VERIFICATION.md`, NOT per-tab from the stale `PAYLOAD_AUDIT_ALL.md` (whose "Power Quality sub-cards"/"Voltage & Current cards" counts are superseded).

**What this means for buildable-today:** V48 Layer 2's one-payload contract has its **validated reference** in **RTM and panel-overview HPQ** — template against those — but the morph is WIDESPREAD, so ~36/59 cards across all panels already have a per-card METADATA payload to emit into. Build against any STRONG/moderate card; for the ~23 weak/zero punch-list cards, V48 either waits for the CMD V2 morph or emits only the DATA half (and accepts hardcoded chrome) until the producer exists. Verification of any "done" must be LIVE (mutate ONE field via Storybook :6008, read the card DOM) — green RTL tests hid 3 real RTM gaps, and the live sentinel is precisely what proved the morph is widespread.

---

## 6. BUILD-SPEC CORRECTIONS

> **HISTORICAL / SNAPSHOT (2026-06-29) — most of these edits have since been APPLIED.** This list was authored against the pre-morph build-spec docs; the sibling `V48_BUILD_SPEC_CONTRACTS.md`/`_SIGNATURES.md`/`_FOLDER_SKELETON.md` have since been re-grounded on the morph: the per-tab dialect union is **demoted to a DATA-fill (`data_fill_shape`, renamed from `frame_dialect`) mapper-input shape only**, each card carries its own `exact_metadata`, and Layer 2 output = `{ exact_metadata, data_instructions }` (Decision A). The line:number citations below point at now-superseded stale text. For the CURRENT status of the residual fixes (the canon's 10 open items — `emit_mode` leak in PROMPTS, missing 4th `column_row` dialect, `data_fill_shape` derivation, partition orphan card 160, `composite`/`sld` payload_shape map, etc.) see **`V48_BUILD_SPEC_REVIEW.md` (G1–G10)** — those remain OPEN pending user. Read the items below as the original rationale, not as outstanding work.

Precise edits to make (as originally written). File:line citations are to the then-current stale text.

**`CMDV2_PAYLOAD_VERIFICATION.md` (the keystone — it propagates the stale model into every other doc):**

1. **Lines 6-8 / 14-16 — fix the boundary.** It says "V48 Layer 2 emits at the BACKEND-FRAME boundary (= mapper.ts input)" and the FE chain "stays as-is." Post-morph this is true ONLY for the **DATA** half (worker-filled). Add: the **METADATA** half (AI-morphable) is now emitted at the **producer/viewModel output** (the per-card `{data+metadata}` object, §B4), which is *downstream* of the mapper input. The `viewModel.ts` is no longer an untouched black box — it is the producer Layer 2 mirrors.

2. **Lines 14-16 / "Two frame dialects" — demote, don't delete.** Keep `AssetPageFrame` / `widgets{} AggregateSnapshotFrame` as the **DATA-fill (mapper-input) shapes only**. Remove any implication that they are *what Layer 2 emits per card*. Add a parallel section: "Per-card METADATA payload shape (one-payload-per-card, §B4)" listing `HeatmapViewModel`/`RailViewModel`/`HpqPresentation`.

3. **Line 38 (Exception 1) — reframe.** "Plain but not raw; carries preformatted strings/labels/colours" — clarify these preformatted **labels/colours/units/badges are the METADATA tier the AI now morphs**, not opaque backend strings. They move from "backend computes today, irrelevant" to "Layer-2-owned, AI-morphable, byte-identical default."

**`V48_DESIGN_NOTES.md`:**

4. **Lines 117-119 — replace the verdict.** "Layer 2 directly provides that whole frame JSON … Two frame dialects" is the stale per-tab model. Replace with: Layer 2 provides the **METADATA half** of a per-card one-payload object; the **worker fills the DATA half** (live frame or test-DB fixture in the same Snapshot shape); the only surviving "dialect" is the mapper-input DATA frame.

5. **Line 120 ("Hard exceptions … minted downstream in Cards.tsx") — keep but sharpen.** Functions/ReactNode/3D still stay FE — correct. But add: the *non-function* chrome that was "downstream and irrelevant" (labels/units/colours/order/thresholds/contracts) is now **on the payload as METADATA and is Layer-2's job**.

6. **Lines 122-126 (aggregation model) — keep.** The worker-does-aggregation, AI-specs split is still correct; it maps onto "worker fills DATA." No change beyond noting it fills the DATA tier, not the whole frame.

7. **Line 187 — update the "VERIFIED" claim.** "Layer 2 directly provides the plain-JSON frame" is now PARTIAL: true for DATA at mapper input; the METADATA half is a separate per-card payload at producer output. Re-mark from VERIFIED to VERIFIED-WITH-MORPH-SPLIT.

**`V48_BUILD_SPEC_CONTRACTS.md`:**

8. **Lines 478-531 — replace the `frame.oneOf` dialect union.** The three-way `oneOf` (`FlatAssetPageFrame` / `AggregateSnapshotFrame` / `WidgetResponseFrame`) currently *is* the Layer-2 per-card emit. Split it: (a) rename to a **DATA-fill frame** schema that is the worker/mapper-input target (keep the three shapes there); (b) add a new **per-card payload (METADATA)** schema (`{data..., metadata...}`, flat, every key once, no `root`) that is what the AI emits per card.

9. **Lines 422-426 / 478-531 — redefine `emit_mode`.** The `atom` vs `frame` binary conflates "interdependent vs standalone" with "where the morphable metadata lives." Both atom and frame cards now carry per-card METADATA. Either add a `payload`/`metadata` block to BOTH branches, or restructure so `emit_mode` selects DATA-residence (`$ctx` vs inline) while METADATA is a sibling block present in both.

10. **Lines 353 / 686-693 / 728-731 / 818 — retire the `frame_dialect` enum as the Layer-2 selector.** `frame_dialect ∈ {flat_asset, widgets_envelope, shared_context}` currently gates which of `atom`/`frame` is populated. Repurpose it to describe the **DATA-fill source shape only** (mapper input), and add a separate, dialect-free per-card METADATA payload that every card carries regardless of `frame_dialect`.

11. **Lines 448-476 (the `atom` schema) — add a required `presentation` block.** Today `knobs` is `["object","null"]` (optional) and the design sketch omits it. Make a per-card METADATA block REQUIRED on every atom, mirroring its card's METADATA tier (heatmap atom: `metricTabs`/`statusColors`/`statusLegend`/`units`/`descriptors`/`selectionColors`/`bandThresholds`/`sectionContracts`; rail atom: `RT_DIR_PRESETS`-equivalent/`dsTone`/`lineColor`/`areaOpacity`). Without it the lean atom is missing exactly the fields §B4 morphs.

12. **Lines 579-599 (`shared_context`) — clarify the contract boundary.** `config.section_contract_kw` lives in `shared_context` today, but `sectionContracts` is per-card METADATA (AI-default, backend-overridable). Decide its home (see Open Decision D) and annotate: `shared_context` holds the single DATA buffer + interaction seeds + truly shared config; **per-card METADATA does NOT belong in `shared_context`** (each atom carries its own).

13. **Add the §B4 invariants as build rules** anywhere the emit contract is defined: ONE payload per card, every key once, no `root`, byte-identical default, producer-always-populates, new renderers opt-in default-OFF, and LIVE verification (mutate-one-field Storybook sentinel) as the acceptance gate.

**`V48_INTERDEPENDENT_CARDS_DESIGN.md`:**

14. **Lines 38-47 (atom sketches) — add the `presentation`/METADATA block.** Each atom sketch shows only `reads`/`binds`/`emits`. Add the per-card METADATA tier so the sketch is code-true post-morph.

15. **Line 35 / lines 29-36 — split config vs per-card metadata.** `section_contract_kw` in `shared_context.config` should be flagged as the AI-default that the per-card heatmap atom carries as `sectionContracts` (backend-overridable), not a purely shared constant — unless Open Decision D rules it shared.

16. **Line 190 (DESIGN_NOTES "RESOLVED via Approach B") — annotate.** B still resolves the per-card-vs-page tension, but add the THREE-tier refinement: lean-on-DATA, fat-on-METADATA per atom.

---

### OPEN DECISIONS this raises for the user

- **(A) RESOLVED (canon Decision A, HYBRID).** Layer 2's per-card OUTPUT = `{ exact_metadata, data_instructions }`: the AI authors the FINISHED METADATA block (byte-identical defaults) at the **producer/viewModel-output** level AND emits a PARSEABLE `data_instructions` recipe; the HOOK/HELPER parses it and FILLS the DATA (owning live state/interactivity/interdependency). So V48 Layer 2 targets the producer output (per-card `{exact_metadata, data_instructions}`), NOT a mapper-input DATA frame — the per-tab dialects survive only as the `data_fill_shape` the helper targets. (Still OPEN per canon: the `$ctx` source form — dotted `$ctx.history` vs bare + `buffer_key` — and the 10 build-spec review fixes incl. the `emit_mode` leak in PROMPTS vs CONTRACTS and `data_fill_shape` derivation.)

- **(B) RESOLVED (canon user decision): the worker re-authors the DATA fill in OUR pipeline.** Data-domain aggregation **RELOCATES to OUR pipeline's worker functions — NOT backend2 :8889 reuse** (L6/L6.2 render-shaping retired). The worker fills the DATA half (live source OR test-DB fixture) into the same `Snapshot` shape so live and fixture are interchangeable at the mapper boundary. (Still OPEN per canon: the test-DB contents post-implementation.)

- **(C) Which cards are in-scope today?** The morph is WIDESPREAD — ~36/59 cards across ALL panels are strongly/moderately morphed (RTM + panel-overview HPQ are the validated *reference*, not the only morphed surfaces). Do we build the one-payload contract against any STRONG/moderate card now, and for the ~23 weak/zero punch-list cards either wait for the CMD V2 morph or build a DATA-only path with hardcoded chrome? (Grade per-card from the live Storybook sentinel, not per-tab.)

- **(D) `sectionContracts` (and HPQ `signature.spokes`) home.** These are "AI-default, backend-overridable" — both METADATA and data-touchable. Does V48 model them as per-card METADATA (atom-carried) with a worker override, or as `shared_context.config`? Spec them as one, consistently.

- **(E) Verification gate.** §B4 makes LIVE Storybook-sentinel verification NON-NEGOTIABLE (it caught 3 gaps after green tests). Does V48's acceptance harness adopt the mutate-one-field-and-read-the-DOM check for each emitted card, or rely on the test-DB golden-payload comparison alone? (The findings warn green tests + byte-identical defaults HIDE dead fields.)

---

**Key files referenced (all absolute):**
- `/home/rohith/CMD_V2/CLAUDE.md` (§B4 lines 184-279 — the contract)
- `/home/rohith/CMD_V2/src/pages/electrical/lt-pcc/panel-overview/realtime-monitoring/{types.ts,heatmapMetrics.ts,realTimeRailViewModel.ts,useRealTimeMonitoringData.ts}` (RTM reference)
- `/home/rohith/CMD_V2/src/pages/electrical/lt-pcc/panel-overview/harmonics-pq/{types.ts,viewModel.ts}` (HPQ reference)
- `/home/rohith/desktop/BFI/backend/layer2/pipeline_v48/V48_STORYBOOK_MORPH_VERIFICATION.md` (LIVE per-card morph status — 36/59, the authoritative source; supersedes the static audit)
- `/home/rohith/CMD_V2/PAYLOAD_AUDIT_ALL.md` (STALE static morph counts — ~7 cards / 2 tabs; SUPERSEDED, kept only for history)
- `/home/rohith/desktop/BFI/backend/layer2/pipeline_v48/CMDV2_PAYLOAD_VERIFICATION.md` (stale keystone — edits #1-3)
- `/home/rohith/desktop/BFI/backend/layer2/pipeline_v48/V48_DESIGN_NOTES.md` (edits #4-7, #16)
- `/home/rohith/desktop/BFI/backend/layer2/pipeline_v48/V48_BUILD_SPEC_CONTRACTS.md` (edits #8-13)
- `/home/rohith/desktop/BFI/backend/layer2/pipeline_v48/V48_INTERDEPENDENT_CARDS_DESIGN.md` (edits #14-15)