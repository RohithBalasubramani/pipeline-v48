# V48 Build-Spec — Index

> Generated 2026-06-23 by exhaustive research (V48 docs + live `cmd_catalog`/`lt_panels` + CMD V2 + V47 code) and adversarially reviewed end-to-end. **Verdict: RUNNABLE-WITH-FIXES** (the "~85% buildable" figure is the original PRE-MORPH estimate). **The spec has since been REWRITTEN to the payload-morph model + re-reviewed — the CURRENT verdict is "RUNNABLE-WITH-FIXES for the RTM/HPQ reference path; GAPS for the broader catalog" (see the "Status — spec REWRITTEN" block below).**

## The atomic spec files
- [V48_BUILD_SPEC_CONTRACTS.md](V48_BUILD_SPEC_CONTRACTS.md) — the 8 inter-layer JSON schemas (pipeline input, 1a out, 1b out, Layer 2 per-card in/out, `shared_context`, page-frame envelope, orchestrator state). The spine; field names consistent across all.
- [V48_BUILD_SPEC_PROMPTS.md](V48_BUILD_SPEC_PROMPTS.md) — per-layer Qwen system+user prompts + output JSON-schemas for 1a / 1b / Layer 2 (+ the Move-1 aggregation-spec call); adapted from V47's working prompts.
- [V48_BUILD_SPEC_FOLDER_SKELETON.md](V48_BUILD_SPEC_FOLDER_SKELETON.md) — the atomic folder tree (one file per concern; each layer a folder of single-purpose pieces).
- [V48_BUILD_SPEC_SIGNATURES.md](V48_BUILD_SPEC_SIGNATURES.md) — Python function signatures: orchestrator, layer calls, workers, stitcher, shared_context builder, LLM + DB clients.
- [V48_BUILD_SPEC_REVIEW.md](V48_BUILD_SPEC_REVIEW.md) — the adversarial end-to-end review + fix list.

## Verdict: RUNNABLE-WITH-FIXES

> ⚠ **HISTORICAL — PRE-MORPH review (kept for the constraint check + async/orphan gaps).** This Verdict section and its "frame / `frame.oneOf` / `frames/*.py` / `frame_dialect`" framing predate the 2026-06-29 payload-morph. Under the CURRENT model Layer 2 emits **`{ exact_metadata, data_instructions }`** (one payload per card), NOT per-tab frames; the per-tab dialect (`flat_asset` / `widgets_envelope` / `column_row`) survives ONLY as the DATA-fill (mapper-input) shape. For the live verdict, scope, and fix list see **"⚠ MAJOR CORRECTION — payload-morph"** and **"Status — spec REWRITTEN to the morph model + re-reviewed"** below + `V48_PAYLOAD_MORPH_CORRECTION.md`. Items still valid post-morph: gap #3 (async/log), gap #4 (partition orphan card 160), gap #5 (test DB), and the count/`payload_shape` drift (corrected to canon below).

The architecture, the contract identity-chain (`group_id ↔ $id ↔ $ctx`), the atomic folder, and the 8 schemas are internally consistent and faithful to V47. Constraints check: **19/22 fully honored.** But two of the most common page types break on live data, and an async/observability contradiction would silently kill the failure log.

### 5 BLOCKING gaps (fix before build)
1. **Missing 4th dialect — column-row/queue.** The whole `individual-feeder-meter-shell/*` family (live per-meter V&C/feeder pages) emits `ColumnRowSnapshotFrame {columns, queue[], enqueue}` — NOT one of the spec's 3 `frame.oneOf` branches. → add the dialect + a `frames/column_row.py` builder.
2. **`frame_dialect` has no DB source.** The spec treats it as a catalog column; it doesn't exist. → write a deterministic `layer2/dialect.py` resolver `(render_shell, backend_strategy, handling_class) → dialect`.
3. **Async vs sync LLM contradiction.** SIGNATURES uses `async call_qwen`; PROMPTS uses sync `urllib`. `ai_log` (the only failure-log transport, constraint #17) monkeypatches `urllib.urlopen` → async silently logs nothing. → keep sync calls + `ThreadPoolExecutor` for 1a∥1b + fan-out.
4. **Partition orphans wired-by-intent cards.** RTM card 160 (Heatmap Footer) has no `card_link`/combo/prose edge → partitioned standalone → detached from `rtm_ctx` (the user's own "card_link alone orphans the lone time-bucket card" gotcha). → add fallback edges: `card_combo.region` co-membership, `page_control.affects_cards int[]`, same composite `render_slot`.
5. **Test DB doesn't exist.** `DB_TARGET=test` + `bake_values` + `fill_mode='baked'` are coded against the parked test DB → baked/hybrid fill is dead until it's built.

### Non-blocking fixes
- **Count drift:** spec cites "38 pages / 95 cards / 214 components"; live (per canon, rebuilt `cmd_catalog`) is **145 cards (135 live, max id 176) / 75 page_specs / 280 components** (the earlier "135 cards / 68 page_specs / 278 components" reading is STALE). → read counts dynamically; drop hardcoded `handling_class` counts.
- **`payload_shape` normalization:** live includes `composite` (12) + `sld` (1) not in the 10 shapes. → `composite` signals a combo group (don't collapse); `sld` needs a decision.
- **`derived_metrics` reconcile:** don't hardcode `*_today_kwh → *_import_kwh` (verified to corrupt LT-panel tables that have the native column).
- **`panel_members`:** port the CODE (outgoing→source), not `panel_resolve.py:9`'s stale docstring.
- **`narrative_ai`-in-group:** a narrative atom inside a shared_context group emits an `ai_summary` knob (data-only), not bindings.

### 4 OPEN DECISIONS (need the user)
1. **Dialect set: two or four?** The design said "two dialects"; live data needs at least the column-row/queue one (+ pending/error). Confirm before building `frames/`.
2. **Test DB — DEFERRED (user):** build the test DB and decide its contents (mock / golden / both) **only AFTER the pipeline is implemented.** NOTE: the data source for initial implementation is **not yet decided** — do not assume.
3. ~~Asset↔page compatibility~~ — **RESOLVED (core principle):** templates are **asset-agnostic cards-combos**, not asset-specific. 1a picks the best cards-combo for the prompt for ANY asset → **no compatibility check.** Any card that can't fill from the resolved asset's data is handled per-card downstream (1b basket + Layer 2 resolve → swap or log), not a page/shell gate. (Review's Trace-A shell worry is a non-issue.)
4. **`frame_dialect` source of truth** — derive at runtime (fix #2), or add a column to `card_handling`/`contract_components` during the rebuild (cleaner, matches "from the DB")?

## ⚠ MAJOR CORRECTION (2026-06-29) — payload-morph

CMD V2 was reworked to **one payload per card** (`{data + metadata}`, AI-morphable; CLAUDE.md §B4, commit dfded69). This **supersedes the per-tab "dialect" model** this spec was written on. Corrected model + the 16 precise edits are in **`V48_PAYLOAD_MORPH_CORRECTION.md`**:
- Layer 2 (AI) produces the **METADATA** per card; the worker fills the **DATA** per card. The 3 dialects survive only as the **data-fill (mapper-input) shape**, not as Layer 2's output.
- Approach B holds with a 3-tier refinement (atoms carry their own METADATA block).
- Build against the validated references: **RTM + HPQ**. (NOTE — the "equipment-detail V&C / Power Quality are not morphed yet" claim originally here is SUPERSEDED by the live Storybook sweep below: the morph is WIDESPREAD (~36/59 cards across ALL panels, incl. equipment-detail Power-Quality 7/9 and V&C 8/12); only specific sub-cards (V&C hardcoded Deviation Band / Phase Rows, some aggregate cards) score weak/zero. See "SCOPE REALITY — CORRECTED by live Storybook verification" and `V48_STORYBOOK_MORPH_VERIFICATION.md`.)
- **Decision #1 (dialect set) is reframed** — it's no longer "how many per-tab frames," it's the one-payload-per-card contract.
- **Open Decision A — RESOLVED (hybrid):** Layer 2 per-card output = `{ exact_metadata, data_instructions }`. The AI gives the **metadata EXACT** (producer, Option-1 for that half) and gives **parseable instructions** for the data; the **hook/helper functions fill the data + own live state/interdependency** (Option-2 for that half). Helpers run the instructions → data; merge with metadata → one payload. See `V48_DESIGN_NOTES.md` → "Layer 2 emit model".

## Foundation status (checked 2026-06-29)
- **(1) `cmd_catalog` rebuild — BUILT ✅.** 145 cards (135 live, max id 176), 75 page_specs, 280 components, `status` columns present. The spec can pin DB contracts against it now.
- **(2) CMD V2 morph — RTM + HPQ done; spreading.** Morphability + presentation-metadata test files now exist for `voltage-current`/`power-quality`/`energy-power`/`energy-distribution` (panel-overview + equipment-detail) — morph expanded beyond RTM/HPQ, but per-tab completeness not yet confirmed. Git HEAD still the `dfded69` wip commit.
- **(3) Frontend interdependency — still WIP** (no new commits). Approach B's frontend coupling stays provisional.
RTM/HPQ remain the stable build references; the build-spec update workflow re-queries the *current* built DB + current morph status.

## Status (2026-06-29) — spec REWRITTEN to the morph model + re-reviewed

The 4 spec files (CONTRACTS / PROMPTS / SIGNATURES / FOLDER_SKELETON) were rewritten to `{exact_metadata, data_instructions}`. Re-review verdict: **RUNNABLE-WITH-FIXES for the RTM reference path; GAPS for the broader catalog.** The morph model is faithfully encoded — Decision A, the §B4 invariants, the 3-tier ownership split all consistent across the files, and the RTM merged payload is byte-accurate vs the real `HeatmapViewModel`.

### ⚠ SCOPE REALITY — CORRECTED by live Storybook verification (2026-06-29)
Earlier I said the morph covered only ~7 cards (RTM + HPQ) — that came from the **stale static `PAYLOAD_AUDIT_ALL.md`.** A **live §B4-sentinel sweep of all 59 EMS Storybook stories** (`CMD_V2/sb_verify.mjs`, method-validated: RTM heatmap 10/12) shows the morph has **spread far wider: ~36/59 cards are strongly or moderately payload-driven, across ALL panels** (Equipment Detail Power-Quality 7/9, V&C 8/12, Energy&Power 5/7; Panel-Overview Energy&Distribution 3/3, RTM, HPQ…). Full per-card map: **`V48_STORYBOOK_MORPH_VERIFICATION.md`**.
- **So the morph contract applies to far more than 2 tabs today** — the build scope is much larger than I claimed.
- **~23 cards score weak/zero** (need a manual look): the V&C hardcoded sub-cards (Deviation Band, Phase Rows — the baked nominals/ranges the audit flagged), some aggregate cards (Energy&Power Demand/Cumulative), and Panel-Overview V&C "AI Summary" (0/12). These are where the morph is incomplete OR the card has genuine hardcoded chrome.

### Fix list (re-review)
1. **NEW bug:** delete the leaked `emit_mode:"atom|frame"` from the PROMPTS output schema (contradicts the contract's `$ctx`). 2. Reconcile the `$ctx` source form (dotted `$ctx.history` vs bare + `buffer_key`). 3. Give standalone cards an interaction-seed owner (`card_controls.defaults`). 4. Add the `column_row` DATA-fill dialect (inherited). 5. Specify the `data_fill_shape` derivation (inherited). 6. Add `payload_family→data_fill_shape` crosswalk. 7. Close the partition orphan (card 160; inherited). 8. HPQ `limits` ownership across the 5 cards. 9. Map `composite`/`sld` payload_shapes + fix stale counts. 10. `narrative_ai`-in-group DATA branch.

### Open decisions (lead = scope)
1. **Scope:** build the RTM+HPQ 2-tab morph reference NOW (the other ~110 cards DATA-only until morphed), or defer until more tabs morph upstream? 2. `$ctx` source shape. 3. `data_fill_shape` source (derive vs DB column). 4. standalone interaction seeds. 5. HPQ `limits` emitter. 6. live-verify gate operationalization (FE-side, in progress).

**Next:** settle the scope decision + the `$ctx`/dialect-source calls → apply the 10 fixes → build the RTM/HPQ reference end-to-end (proves the whole pipeline on real morphed cards) → expand panel-by-panel as CMD V2 morphs more tabs.
