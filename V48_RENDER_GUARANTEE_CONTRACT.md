# V48 Render-Guarantee Contract — 3 AI layers, THIN Layer 3, every card renders

Finalized from a 3-proposal design + adversarial judge (all 62 failure modes in `V48_RENDER_GUARANTEE_AUDIT.md`
verified covered). **Decision: THIN-L3.** ~48/62 modes are fixed by deterministic PRE with **zero AI**; Layer 3 (the
one AI layer) owns only ~7 genuinely-semantic modes + the reason/coverage sentences. AI names, deterministic code
fetches+verifies. Build L3 LAST — it's a thin cap over an already-correct substrate.

**"0 issues" =** 0 wrong values, 0 crashes, 0 mock/seed-shown-as-live. A real data gap → **honest blank + reason** (that counts as rendered).

## Locked architecture — 3 AI layers, everything else deterministic

```
L1 (1a ∥ 1b)  ── prompt → page+cards ∥ asset+basket            [AI, parallel]
      │
L2  ── per-card INTENT: swap + exact_metadata + data_instructions   [AI, parallel per card]
      │
[PRE — GROUNDING KIT]  deterministic: probe live tables → per-card FACT-SHEET (+ settle swaps between layers)
      │
L3  ── per-card VERDICT: names + booleans + reason (NO numbers)     [AI, parallel per card]
      │
[POST]  deterministic: fetch numbers → verify → assemble envelope → reason channel → safe-render
```
Every cross-card fact (panel members, swap dedup, `already_chosen`, variant default) is reconciled in **deterministic
code between layers**, so each L3 call is a pure function of its own fact-sheet → within-layer calls stay independent → 3 layers hold.

## Governing rule (hard acceptance gate)
Every policy is an **editable DB row** in `cmd_catalog` (via `config/databases.py`) + a **single-purpose accessor** file. **Zero hardcoded thresholds/mappings.** Even L3's output is editable rows (`render_spec`). Any component that hardcodes policy is reworked before it ships.

## PRE — the grounding kit (deterministic; builds each card's fact-sheet)
Each unit = a `grounding/*.py` engine reading a `cmd_catalog` config table.

| Grounding fact | DB config table | Fixes |
|---|---|---|
| `asset_resolved` — prefer-populated de-dup on device identity (DG-01→`dg_1_mfm` 11464 rows over empty `gic_28…` 0); resolve by table_name, not row-id | (uses registry) | DS-09, RN-06 |
| `id_space_fix` + name-collision fix (control-char→space before norm key; suffix backstop) | — | RN-03, RN-04 |
| `schema_fingerprint` → {`p1_72`, `tm_ups_56`, `feedbacks_35_scada`, `sch_stub`, `ng_se_jk_70`} + routed column map | `schema_slot_map` | DS-03, DS-07 |
| `value_probe` present/non_null/**meaningful** = the ONE shared `has_meaningful_data(asset,page)` (nonzero power/energy-delta, not padded-0/all-null-THD/denorm) | `data_quality_policy` (VALUE_MIN, denorm ε, meaningful def) | DS-01, DS-04, VC-09, has_data≠meaningful |
| `meaningful_by_metric_class` — does the table expose the PAGE's required column class | `metric_class` (page→class) | DS-07, class-vs-page, SCADA-pin |
| `energy_register` — import≈0 ∧ export>0 → export register (9 reversed-CT meters) | `data_quality_policy` | DS-05, DID-01, VC-01/06 |
| `normalized_scalars` — denorm clamp \|x\|<1e-30; PF/power sign+lead/lag; rate-of-change from samples; cumulative-vs-spot | `data_quality_policy` | DS-06, DID-04, VC-03/06/07/10 |
| `window_clamp` — meter min/max ts; "data from <date>" | — | DS-02 |
| `nameplate` — rated/contract/nominal/role/section; kills fabricated `capacity:60` + hardcoded dict | **`asset_nameplate`** (seeded from `cmd_equipment.mfm` 302 + token grammar + class defaults) | RN-01/02/05/07, DS-10, DID-03, VC-05 |
| `topology_members(mfm_id)` — FROM-side fan-out (never inverted incoming), recurse empties, has_data filter, dedup, N-of-M | (uses `lt_mfm_outgoing`) | TOPO-01..07, DS-08, VC-04/08 |
| `derivation_catalog_for_asset` — only fns whose base_columns ⊆ present & fetched | `derivation_binding` | DID-02/05, DS-04(ieee519) |
| `endpoint_and_shape` — endpoint+expected_shape+is_history; pre-validate vs LIVE set (retired→no-WS); PCC-history→feeder | `endpoint_policy` | ER-1/2/4/5/7/8 |
| `default_payload_status` — subcard-inclusive, slot-identity variant, sibling fallback, **values stripped to placeholders**, literals scrubbed | (uses `card_payloads`) | META-01/05/06/07, VC-02 |
| `settled_swap` + `already_chosen` — swaps resolved deterministically BEFORE L3 | — | META-04/05, FR-5 |

## Layer 3 — the one AI layer (per card, parallel; names + booleans only)
**Input** = a self-contained fact-sheet (no raw rows, no sibling data, no rendered numbers; leaf values stripped to placeholders; only columns/fns the kit pre-verified as present). Unambiguous slots PRE already bound are **not shown to L3**.
**Output** = a tiny `render_spec` (cached to the `render_spec` table, reviewable/overridable):
```
{ render_verdict: render|honest_blank|partial, reason,
  slot_decisions:[{slot, decision: bind|substitute|blank, bind_column|substitute_fn|substitute_column, blank_reason, fidelity_note}],
  answerability: full|partial|none,  coverage_note,  date_control: enabled|disabled,
  suppress_default_leaves: [payload-paths to force-blank] }
```
L3 owns exactly four semantic calls: **final feasibility verdict**, **substitute choice among PRE-verified grounded alternatives**, **human reason/coverage sentences**, **date_control enable/disable**. Nothing else.

## L2 ↔ L3 boundary
- **L2** (before any value): swap pool+gates, `exact_metadata` morphs, `data_instructions` intent (which metrics/endpoint/window the *story* wants), an answerability first-guess from the basket. L2 **structurally cannot** know a column is uniformly 0/NULL, feeders are 4/8 empty, or a `_tm`/feedbacks table lacks the page's class.
- **L3** (first layer to see ground truth): the four semantic calls above, per card, from the fact-sheet.

## POST — deterministic (fetch/verify/assemble/render)
- **Value fetch + range/sign verify** for every L3 bind/substitute (`registry.run`); probe violation → blank+reason.
- **NO-SEED-LEAK** (systemic fix): force-blank `suppress_default_leaves` + watermark; a numeric equal to its seed with no live provenance is force-blanked — across all 9 fill modules. [VC-01/02]
- **Reason channel**: thread per-endpoint `{ok,why}` + per-slot `blank_reason`/`coverage_note`/`fidelity_note` ems_backend→host→card. [ER-6/2]
- **Envelope assembler / shape-normalizer** buckets→widgets; no rule → `frame_shape_mismatch`+reason, never a silent swap. [ER-1/3]
- **ENFORCING byte-identity gate** (revert non-conforming to default) + `_schema_issues` load-bearing. [META-02/03/08]
- **Safe-render**: app-root ErrorBoundary + wrap the `renderCmd()` call in try/catch (currently OUTSIDE the boundary → a throw white-screens the app); real `CARDS[37]`; story_id-keyed shape check. [FR-1/2/3/4]
- **Parallel `_card_frames` + wall-clock budget** — replaces the serial 60s-per-endpoint loop (~180s → drops all frames). [ER-8]

## Config tables (all `cmd_catalog`, editable) + atomic files
`asset_nameplate` · `schema_slot_map` · `metric_class` · `data_quality_policy` · `derivation_binding` · `reason_template` · `endpoint_policy` · `render_spec` (L3 cache).
Files: `grounding/{schema_fingerprint,schema_route,meaningful,metric_class,energy_register,normalizers,nameplate,window_clamp,endpoint_resolve,recovery_validate,default_assemble,swap_settle,aggregate}.py` · `layer3/{factsheet,emit,prompt,schema,apply}.py` · `config/{nameplates,schema_map,metric_class,quality_policy,derivation_binding,reason_templates,endpoint_policy}.py` · extend `layer1b/resolve/has_data.py`→`has_meaningful_data`, implement the 6 existing stubs · `layer2/{build,gates,resolve/column_override}.py` · `run/layer2_all.py` (swap-collision post-pass) · `host/server.py` (parallel+budget+reason) · `host/web/src/cmd/{registry,fill/*}.tsx`, `components/CmdCard.tsx`, `main.tsx` (boundaries).

## Build order (deterministic substrate first; L3 last)
0. **Foundation (no AI):** the 6 empty stubs as PRE units — `panel_members`, `asset_nameplate`+seed, `has_meaningful_data`, `schema_fingerprint`+map, `energy_register`+normalizers, `class_from_subject`. Fixes ~48/62, each unit-testable vs the live DB.
1. **Kill mock-as-live + safe-render + reason channel** (biggest systemic gap) — after this no card can lie; worst case is an honest blank.
2. **Nameplate → derivations** — the only rated/contract/nominal source; delete `capacity:60` + hardcoded dict.
3. **Feasibility + meaningful + class gate** before L2 — dead/SCADA/wrong-class/empty-duplicate assets never route to a live card.
4. **Normalizers + schema-route + energy register + unit-guarded snap.**
5. **Aggregation integrity + endpoint/shape + envelope assembler.**
6. **Metadata gate enforcing + swap dedup + parallel budget.**
7. **Layer 3** (the one AI layer) — the per-card fact-sheet → RenderSpec fan-out.

## Honest caveats (must be messaged, not silently absorbed)
- **~6-day data window** (2026-06-25 → 07-01, verified): every 30d/90d/YTD card is honest-blank "data from 06-25" until history accrues. Correct, not a regression.
- **Render count will DROP initially** — making the gate + meaningful-data load-bearing stops shipping silently-wrong cards. Intended ("honest blank over wrong value"), reads as regression unless pre-messaged.
- **Nameplate cross-DB match-rate** (`cmd_equipment.mfm` ↔ V48 registry) is unmeasured — needs a seed-time audit; unmatched → loading% slot honest-blank.
- **Aggregate perf:** `panel_members` recursion adds DB round-trips (a 58.9s single fetch was measured) → must cache per-run or the parallel budget is at risk on PCC panels.
- **Swap targets restricted to registered card_ids** — blocks swaps toward unwired SLD/3D/nav cards (honest "no renderer" vs white-screen); a product tradeoff to confirm.
