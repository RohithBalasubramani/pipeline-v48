> V48 build-spec review (morph-model rewrite), 2026-06-29. See V48_BUILD_SPEC.md for the index.

> ---
> **STATUS BANNER (added 2026-06-29) — point-in-time review record; findings below are NOT rewritten.**
> Reconciliation of this review's findings against the canonical current model (2026-06-29). The body is preserved verbatim; this banner only marks addressed vs still-open and corrects two figures that the canon now supersedes.
>
> - **Still OPEN (pending user) — the 10 build-spec review fixes are explicitly the canon's open list.** Canon names these as not-yet-resolved: G1/§3 `emit_mode:"atom|frame"` leak in PROMPTS vs CONTRACTS; G2 `$ctx` `source` form (dotted `$ctx.history` vs bare token + `buffer_key`); G4 missing `column_row` data-fill dialect; G5 `data_fill_shape` derivation (not in DB); G6 `payload_family`→`data_fill_shape` crosswalk; G7 partition orphan card 160; G8 HPQ `limits`/single-`HpqPresentation` 5-card split; G9 `narrative_ai`-in-group data-fill branch; G3 standalone interaction-seed ownership; G10 `composite`/`sld` payload_shape mapping. Fix list items 1-10 and the six "Open decisions for the user" all remain open per canon. Where these are touched in sibling docs they must be referenced AS open, not asserted resolved.
> - **SUPERSEDED by canon — scope/morph figures.** The body's claim that "V48-with-morph is a 2-tab (RTM + HPQ) capability today, ~7 cards" / "the morph contract today applies to ~7 cards" is SUPERSEDED. Canon MORPH STATUS (live-verified via Storybook §B4 sentinel): morph is WIDESPREAD — ~36/59 EMS cards strongly/moderately payload-driven across ALL panels; RTM + HPQ are validated references; ~23 weak/zero on the punch-list. The OLD "only ~7 cards / 2 tabs" claim (from stale PAYLOAD_AUDIT_ALL) no longer holds.
> - **STALE counts — corrected by canon.** The body's "live totals (135 cards / 68 page_specs / 278 components)" and any "116 cards/29 pages/123 components" / "38/95/214" are STALE. Canon: cmd_catalog is REBUILT — 145 cards (135 live, max id 176), 75 page_specs, 280 components, status columns present. Per-card render shape lives in `card_handling` / `card_data_recipe.payload_shape` (no dedicated dialect column).
> - **FAITHFUL / consistent with canon (no change needed):** Decision A (Layer 2 output = `{exact_metadata, data_instructions}`, HYBRID); the §B4 ONE-payload/no-root/every-key-once/byte-identical invariants; the demotion of the per-tab dialects (flat_asset/widgets_envelope/column_row/shared_context) to DATA-fill (mapper-input) shape only; hook-as-third-class owning live state/interaction; Approach-B shared_context for interdependent groups (still IN PROGRESS / provisional, as the body marks it); placement+sizes from DB; FAILURES LOGGED with exact errors and NO reloop/re-route.
> ---

Confirmed — `HpqPresentation` is one nested object whose 5 sub-blocks (`strip`/`timeline`/`aiSummary`/`feederTable`/`signature`) map to 5 distinct HPQ cards. This validates the spec's "each HPQ card carries its OWN `HpqPresentation.<card>` block" claim, but also surfaces a real question (the 5 cards share ONE producer + ONE `limits` block — a per-card slicing concern). I have everything needed.

---

# ADVERSARIAL REVIEW — V48 BUILD-SPEC vs THE MORPH MODEL

I verified every load-bearing morph claim against the live CMD_V2 source (`CLAUDE.md` §B4, RTM `HeatmapViewModel`/`RailViewModel` in `types.ts`, HPQ `HpqPresentation` tree) and read all four rewritten spec files plus the pre-morph `V48_BUILD_SPEC_REVIEW.md`. The morph rewrite is **faithful and largely coherent** — but it carries one hard self-contradiction, several field-drifts, and inherits the pre-morph DATA-side blockers untouched (correctly, since the morph disclaims them, but they still gate runnability).

## 1. TRACE — "real-time monitoring of PCC-1A" end to end

| Step | What happens | Shapes match? |
|---|---|---|
| Prompt → 1a∥1b | `kickoff_1a_1b` fires both on `ThreadPoolExecutor`; join. | ✓ |
| 1a route | `panel-overview-shell/real-time-monitoring`; per-card `analytical_story`; carries layout/slots; `partition_groups` builds `interdependency_groups`. | ✓ |
| 1b asset/basket | "PCC-1A" → panel mfm (174); generous voltage/current/power basket on `mfm_lt_115`. | ✓ |
| Partition | `card_link` ∪ prose → `rtm-combo` (cards 5,6,7,8,9,10,11; combo 24). | ⚠ **card 160 (Heatmap Footer) orphaned** — verified in REVIEW.md, NOT fixed by the morph (partition is "UNCHANGED by the morph"). |
| Move 1 | `build_shared_context` builds `rtm_ctx` once: `buffers:[{key:'history', history:HistorySample[], socket_owner:true}]` + interaction seeds + config. | ✓ matches `SharedContext` (§7) and the live hook's 5 `useState` cells. |
| Move 2 (per card) | `layer2_card` emits `{exact_metadata, data_instructions}`. Heatmap atom: `exact_metadata` = title/metricTabs/statusColors/statusLegend/units/descriptors/selectionColors/bandThresholds/sectionContracts; `data_instructions.fields[].source="$ctx"`. | ✓ `exact_metadata` keys match the real `HeatmapViewModel` METADATA fields exactly. |
| Move 3 stitch | `fill_from_shared` projects slots from `rtm_ctx.buffers.history`; `merge_payload` flattens `{...exact_metadata, ...filled_data}`. | ✓ but see **the interaction-seed gap** (§4 G3). |
| Render | Merged `HeatmapViewModel` → `RealTimeHeatmapSection`. | ✓ — `history`+metadata in ONE flat object matches the real interface (no `root`). |

The merged worked example in CONTRACTS §5a is **byte-accurate** against `realtime-monitoring/types.ts:213-273`: `history`, `metric`, `selectedSampleIndex`, `liveMode`, `selectedSectionId`, `selectedFeederId`, `title`, `metricTabs`, `metricAxisLabels`, `statusColors`, `statusLegend`, `units`, `descriptors`, `selectionColors`, `bandThresholds`, `sectionContracts` — all present, all flat, every key once. **The trace runs end-to-end for RTM** except the orphan (pre-existing) and the seed-ownership gap (new).

## 2. §B4 INVARIANTS — enforcement check

All eight are **stated** as build rules (CONTRACTS §B4 block lines 27-39; PROMPTS lines 28-34; SIGNATURES `assert_one_payload`) and verified against the real CLAUDE.md §B4 (ONE payload/no-root/every-key-once/byte-identical/opt-in-default-OFF all present in source).
- **One payload / every key once / no root** — enforced in `merge_payload` + `assert_one_payload` (key-collision → `ok=false`). ✓
- **Byte-identical default** — sourced from `contract_hardcodes`/`contract_capabilities`/registries; gate #2 checks defaults present. ✓ but **unenforceable deterministically** — "byte-identical to today's rendered bytes" can only be proven by the LIVE Storybook sentinel, which the spec itself admits is the real gate (good — it says so).
- **Opt-in default-OFF** — `assert_one_payload` checks `showLegend:false`. ✓
- **Zero chrome** — gate #2 rejects function/pixel keys. ✓ (shallow — a nested function string could slip; acceptable.)
- **Live-verify gate** — declared NON-NEGOTIABLE in all files (`fe_contract/acceptance_sentinel.md`). ✓

Verdict on §2: **invariants are faithfully encoded.** The one soft spot is that "byte-identical" has no offline assertion — by design, but it means CI green ≠ correct (the spec acknowledges this).

## 3. DECISION A — faithfully encoded?

**Yes, with one schema contradiction.** Layer 2 output = `{exact_metadata, data_instructions}` is consistent across CONTRACTS §5, SIGNATURES (`author_exact_metadata`/`author_data_instructions`), and FOLDER (`metadata_producer.py`/`data_instruction_emitter.py`). The hook-owns-state third class is correctly isolated (`shared_context.interaction`, marked provisional). Metadata exact + data-as-recipe split is clean.

**BUT** the PROMPTS output-schema example (the literal JSON the AI is told to emit) still has the pre-morph `"emit_mode": "atom | frame"` as a top-level key (PROMPTS:512, 558) — which **does not exist** in the `Layer2CardOutput` contract (CONTRACTS §5 uses `$ctx` to distinguish residence; consistency note line 918 explicitly says "there is no `atom`/`frame` branch"). This is the single most concrete drift: the prompt would instruct the model to emit a field the schema forbids (`additionalProperties:false` on the output → validation reject, or silent drift). **This is a real bug, not cosmetic.**

## 4. GAPS & CONTRADICTIONS

**G1 — `emit_mode:"atom|frame"` survives in the PROMPTS output schema (blocking, easy).** PROMPTS:512/558 contradict CONTRACTS §5 / §9-consistency-note ("no atom/frame branch") and SIGNATURES. The morph replaced the binary with `$ctx`. Fix: delete `emit_mode` from the PROMPTS JSON example; replace with `"$ctx": null | "<id>"`.

**G2 — `source` field drift: literal `$ctx` vs dotted `$ctx.<key>` (blocking for the helper).** CONTRACTS §5 `fields[].source` enum is `["live","test-db","const","$ctx"]` (bare token) and §5a says `source="$ctx"`. But PROMPTS (423, 497, 558, 673) and SIGNATURES (152, 202, 209, 298) say `source="$ctx.<key>"` / `"$ctx.<buffer>"` (carries the buffer name). These are **incompatible parse targets** — `fill_from_shared` needs to know WHICH buffer, so the dotted form is the correct one, but the CONTRACTS enum (`additionalProperties:false`, fixed enum) would **reject** `"$ctx.history"`. Fix: make the enum a pattern (`^\$ctx(\.[a-z_]+)?$`) or move the buffer name to a sibling field (`buffer_key`), and align all four files.

**G3 — Initial-interaction-state seeds have NO owner in the standalone path (blocking gap).** `merge_payload` (SIGNATURES:251) "seeds the initial interaction-state keys (`metric`/`selectedSampleIndex`/`liveMode`/…) as a READ-ONLY snapshot." For GROUP cards these come from `shared_context.interaction`. For **STANDALONE** cards there is no `shared_context`, and `exact_metadata` explicitly excludes them (they're DATA tier, not AI-authored — CONTRACTS §5a:590 "NOT Layer-2-authored"), and `data_instructions.fields[]` has no slot kind for them either (they aren't a column read). So a standalone heatmap-like card's `metric:'all'`/`selectedSampleIndex` seed is **unsourced**. The spec says "the helper seeds these from `shared_context.interaction / card_controls.defaults`" (§5a:591) but `fill_single_asset` (SIGNATURES:205) never reads `card_controls.defaults`. Fix: give `data_instructions` an explicit `interaction_seeds` block (from `card_controls.defaults`) for standalone cards, and have `merge_payload`/`fill_single_asset` consume it.

**G4 — `data_fill_shape` still omits the column-row/queue dialect (blocking, inherited).** The enum is `["flat_asset","widgets_envelope","shared_context"]` (CONTRACTS:379, 801; `DataFillFrame` has 3 branches). The pre-morph REVIEW.md G2 proved the entire `individual-feeder-meter-shell/*` family (cards 44/45/46, the most common single-meter V&C pages) emits a **4th `ColumnRowSnapshotFrame {columns, queue[], enqueue}`** with no branch here. The morph renamed `frame_dialect`→`data_fill_shape` but did **not** add the missing dialect — and FOLDER does list `frames/column_row.py`, so the tree and the contract enum now contradict each other. The DATA tier for those cards is un-fillable. (Affects the second trace the task didn't ask for but the spec claims buildable.)

**G5 — `data_fill_shape` has no DB source / no derivation (blocking, inherited).** REVIEW.md G1 stands: no `cmd_catalog` column stores this; it must be derived from `render_shell`/`backend_strategy`/`handling_class` and that resolver is unspecified. The morph kept the field authoritative (`catalog_row.contract.data_fill_shape`, page-envelope `data_fill_shape`) without adding the derivation. FOLDER omits a `dialect.py`.

**G6 — Two competing "dialect" analogs unreconciled.** `catalog_row` carries BOTH `payload_family` (`flat_series/tiles/scene/…`, from `card_handling`, line 340) AND `data_fill_shape` (`flat_asset/widgets_envelope/shared_context`, line 379). CONTRACTS §6:628 says `data_fill_shape` is "driven by `card_handling.payload_family`" — but provides no mapping table. Two overlapping vocabularies for the same concept (which DATA frame to fill) with no crosswalk = ambiguous worker dispatch.

**G7 — partition orphan unfixed (blocking for trace, inherited).** Card 160 detaches from `rtm_ctx` (REVIEW.md G4). The morph explicitly leaves partition "UNCHANGED," so the orphan persists: a standalone card 160 emits `data_instructions` with inline `source` instead of `$ctx`, and its time-axis footer renders detached. The morph rewrite did not add the `page_control.affects_cards`/combo-region fallback the prior review demanded.

**G8 — HPQ per-card `exact_metadata` slicing is under-specified.** Verified: `HpqPresentation` is ONE object with 5 card-blocks (`strip/timeline/aiSummary/feederTable/signature`) PLUS a shared `limits` block, all from ONE `buildHpqPresentation` producer. The spec says each HPQ card "carries its OWN `HpqPresentation.<card>` block" (5 separate `exact_metadata` emits) — but `limits` is shared across all 5, and the 5 cards are one combo. Who emits `limits`? If each of the 5 cards re-emits it → duplicate-key risk at the page level; if one does → which? This is the HPQ analog of the RTM `sectionContracts` dual-owned slot but isn't called out. Non-blocking for RTM, blocking for the HPQ half of "buildable-today."

**G9 — `narrative_ai` inside the aggregate group (inherited, minor).** Card 8 (AiSummary, `narrative_ai`) is combo-24 member inside the `panel_aggregate` RTM group. CONTRACTS:924 ("`handling_class ∈ {panel_aggregate, topology_sld}` gates the aggregate worker; else single_asset is fetch+list") doesn't classify a `narrative_ai` atom in a shared_context group. The morph note says `exact_metadata` is authored "regardless of handling_class" (good), but the DATA-fill branch for it (`fill_data` scope routing, SIGNATURES:198) has no `narrative_ai` case.

**G10 — counts/`payload_shape` normalization (inherited, non-blocking but breaks tests).** REVIEW.md G5/G6 stand: live totals (135 cards / 68 page_specs / 278 components) vs stale "38/95/214"; and `payload_shape` live values include `composite` (12) and `sld` (1) with no entry in the 10 `payload_shapes` the spec normalizes to. The morph's `data_instructions.payload_shape` inherits this un-mapped gap; `composite` is exactly the Approach-B combo case and must NOT collapse to one shape.

### What's NOT buildable beyond RTM / panel-overview HPQ (correctly flagged, but consequential)
The spec is honest: V&C / Power-Quality equipment-detail (unmorphed, V&C bakes 415V/237A + the `Max:430KW` unit bug), Energy-Distribution/Energy-Power (unverified). For these there is **no `metadata_shape` to author `exact_metadata` into** — so Layer 2's morph half is inert and the spec says "emit DATA-only + hardcoded chrome." That means **for the majority of the 116-card catalog, the morph contract does not yet apply** — V48-with-morph is a 2-tab (RTM + HPQ) capability today, ~7 cards. That's the single biggest scope reality to surface to the user.

## 5. VERDICT

**RUNNABLE-WITH-FIXES** for the RTM reference path; **GAPS** for the broader catalog.

The morph model is correctly and faithfully encoded — Decision A, the §B4 invariants, the three-tier ownership split, the hook-as-third-class, and the demotion of the dialects to DATA-fill-only are all internally consistent across CONTRACTS/SIGNATURES/FOLDER and accurately mirror the live CMD_V2 source. CONTRACTS and SIGNATURES agree. But (a) the PROMPTS file leaks the retired `emit_mode:"atom|frame"` into the schema the model is told to emit, (b) the `$ctx` `source` form is incompatible between files, (c) standalone interaction-seeds have no owner, and (d) the inherited DATA-side blockers (missing column_row dialect, underived `data_fill_shape`, partition orphan) were not closed because the morph disclaims that layer — yet they still gate any non-RTM/HPQ page.

### FIX LIST (ordered)
1. **Delete `emit_mode` from the PROMPTS §5(c) output-JSON example** (lines 512, 558); replace with `"$ctx": null | "<ctx-id>"` and `selection_role` per group field — to match `Layer2CardOutput`.
2. **Reconcile the `$ctx` `source` form.** Pick the dotted `"$ctx.<key>"` (the helper needs the buffer name); change the CONTRACTS §5 enum from a fixed `"$ctx"` to a pattern (or add a `buffer_key` sibling), and align §5a, PROMPTS, SIGNATURES.
3. **Give standalone cards an interaction-seed source.** Add `data_instructions.interaction_seeds` (from `card_controls.defaults`) and have `fill_single_asset` + `merge_payload` consume it, so `metric`/`selectedSampleIndex`/`liveMode` are owned, not orphaned, off the shared-context path.
4. **Add the 4th DATA-fill dialect.** Add `column_row` to the `data_fill_shape` enum (CONTRACTS:379/801) and a `ColumnRowFillFrame` branch to `DataFillFrame` (§6); the `frames/column_row.py` file already exists in FOLDER — make the contract match.
5. **Specify the `data_fill_shape` derivation** (`layer2/dialect.py` or a `data/` resolver): `(render_shell, backend_strategy, handling_class) → {flat_asset|widgets_envelope|column_row|shared_context}`. It is not in the DB.
6. **Add the `payload_family → data_fill_shape` crosswalk table** (G6) so the two dialect vocabularies have one mapping.
7. **Close the partition orphan** (G7): in `partition_groups`, union `page_control.affects_cards` + combo-region/`render_slot` co-membership; add a test asserting RTM = {5,6,7,8,9,10,11,160}.
8. **Specify HPQ `limits` ownership** (G8): make `limits` a dual-owned/shared slot emitted once (e.g. by the strip card or carried in `shared_context.config`), and document the 5-card slicing of the single `HpqPresentation` object.
9. **Map `composite`/`sld` payload_shapes** (G10): `composite` → signals a combo group (do NOT collapse); decide `sld` → topology_sld path or a new shape. Replace stale "38/95/214" counts with live totals or dynamic reads.
10. **Add a `narrative_ai`-in-group DATA-fill branch** (G9) in `fill_data` scope routing.

### OPEN DECISIONS FOR THE USER
1. **Scope honesty:** the morph contract today applies to ~7 cards (RTM + HPQ). Is V48 built as a 2-tab morph reference now, with the other ~110 cards on a DATA-only/hardcoded-chrome path until CMD_V2 morphs them — or is the morph deferred until more tabs are morphed upstream?
2. **`$ctx` `source` shape:** bare token + sibling `buffer_key`, or dotted `$ctx.history`? (Affects the schema enum and `fill_from_shared`.)
3. **`data_fill_shape` source of truth:** derive at runtime (fix #5) or add a real column to `card_handling`/`contract_components` in the rebuild (matches the "from the DB" ethos)?
4. **Standalone interaction seeds:** are they `data_instructions`-carried (worker fills from `card_controls.defaults`), or do standalone interactive cards simply not exist outside groups? (If the latter, document it; if not, fix #3 is mandatory.)
5. **HPQ `limits` + the 5-card single-producer split** — one emitter or shared config?
6. **Live-verify gate operationalization:** §B4 makes the Storybook :6008 mutate-one-field check non-negotiable, but it is FE-side and `fe_contract/` is "in progress." Is RTM's acceptance gate runnable today, or is the whole acceptance story provisional with it?

Key files: `/home/rohith/desktop/BFI/backend/layer2/pipeline_v48/V48_BUILD_SPEC_{CONTRACTS,PROMPTS,SIGNATURES,FOLDER_SKELETON,REVIEW}.md`; ground truth `/home/rohith/CMD_V2/CLAUDE.md` §B4 (lines ~200-218), `/home/rohith/CMD_V2/src/pages/electrical/lt-pcc/panel-overview/realtime-monitoring/types.ts:213-273` (HeatmapViewModel/RailViewModel), `/home/rohith/CMD_V2/src/pages/electrical/lt-pcc/panel-overview/harmonics-pq/types.ts:311-318` (HpqPresentation).