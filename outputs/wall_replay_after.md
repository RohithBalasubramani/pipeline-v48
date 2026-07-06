# Wall corpus-replay — AFTER the precision rework (diff vs the committed baseline)

Generated 2026-07-06 by Agent B (wall precision rework). Machine baseline: `outputs/wall_replay_after.json`
(tool: `tools/wall_corpus_replay.py`, read-only). Committed reference: `outputs/wall_replay_baseline.json`
(2026-07-06T12:45Z, gates sha `64f56b478e5cf854`).

Three snapshots are compared (the working tree moved between the committed baseline and this rework — a
separate SEMANTIC-FAMILY wall for card-65 landed concurrently, and fresh host runs grew the corpus):

| snapshot | emits | fields | blanked | rate | FP suspects |
|---|---|---|---|---|---|
| baseline (committed, 12:45Z) | 5982 | 43745 | 15617 | 0.357 | **2073** |
| pre-Agent-B (same corpus as after, incl. semantic wall) | 6047 | 44255 | 16123 | 0.364 | **2124** |
| **after (this rework)** | 6063 | 44428 | **13768** | **0.310** | **1495** |

**Headline: suspected false positives 2073 → 1495 (−578 vs the committed baseline; −629 vs the same-corpus
pre snapshot). 2,449 previously-blanked leaves released — every one in an intended release family; 97 NEW
blanks from this rework — every sampled one a real fabrication catch. Zero bypass on the named fabrication
classes (table below).**

## Per-rule blanks (baseline → pre-Agent-B → after)

| rule | baseline | pre | after | Δ (after−pre) | why |
|---|---|---|---|---|---|
| rule_i_membership | 2515 | 2528 | 2120 | −408 | derived PARTIAL-basis keeps (card-72 family) |
| rule_ii_reuse_smear | 1852 | 1866 | 213 | −1653 | distinctness = classified QUANTITY, not metric strings; classified binds delegate to wall (iii) |
| rule_iii_quantity_wall | 4949 | 4897 | 5495 | +598 | metric-name evidence + honest re-attribution of ex-reuse drops |
| rule_iiib_axis_coherence | 573 | 589 | 135 | −454 | directional extremum/range sources keep (maxY←current_max, demandYMax←worstPeakKw, domain/band fns) |
| rule_iiic_expectation | 37 | 37 | 37 | 0 | untouched |
| rule_iiid_boundary | 134 | 134 | 258 | +124 | lvOutputKw ← own-power now lands HERE (honest topology reason) instead of a positional reuse drop |
| rule_iv_const_source | 5557 | 5633 | 5047 | −586 | structural display-knob consts exempt (decimals/opacity/index/layout/windowDays) |
| rule_unmapped (semantic family) | 0 | 439 | 463 | +24 | the CONCURRENT card-65 wall (not this rework; its reason text is not in the tool's map) |

## FP suspects by rule

| rule | baseline | after |
|---|---|---|
| rule_i_membership | 1232 | 1107 |
| rule_ii_reuse_smear | 450 | **0** |
| rule_iiib_axis_coherence | 218 | 50 |
| rule_iiic_expectation | 35 | 35 |
| rule_iiid_boundary | 134 | 258 |
| rule_iv_const_source | 4 | 4 |
| rule_unmapped | 0 | 41 |

The boundary growth (134→258) is the lvOutputKw MIGRATION, not new harm: the card-41 hv/lv single-meter
proxies were previously half-killed by a positional reuse drop; both sides now blank via the boundary wall
with the honest "topology boundary quantity" reason — the suspect heuristic flags them because slot/source
quantities match (power/power), which is exactly what that fabrication class looks like. The remaining
rule_i suspects are dominated by CORRECT catches of old pre-prompt-fix emits binding columns the asset never
had (hotspotC/oilC/windingC on non-transformer meters, voltage_r_n on 33-col meters, …) — membership is
ground truth, not a wall bug.

## Acceptance spot-checks — every named fabrication still fires (pre → after, same corpus)

| fabrication class | pre | after |
|---|---|---|
| power → hotspotC (quantity wall) | 2 | 2 |
| hotspotC bound where column absent (membership) | 58 | 58 |
| const 131 A (no DB source) | 22 | 22 |
| const 120 A thresholds (card 38) | 38 | 38 |
| thd_current → h5/h7 (voltage-harmonic wall) | 160 | **249** (stronger — ex-reuse drops now honestly attributed) |
| loadFactor → readiness | 107 | **166** (same) |
| hvInputKw ← own power (boundary) | 129 | 129 |
| lvOutputKw ← own power (boundary) | 5 | **129** (migrated from positional reuse drops) |
| expectedLoad ← direct read (expectation) | 37 | 37 |
| score-index wall (raw kW/V as scores) | 69 | 119 |
| loadPct ← raw kW (card 58/76) | 471 | 471 |

## Per-pattern fixes (RULE-level only — no per-card logic)

1. **rule (i) derived — partial basis keeps** (`layer2/gates.py::_blankable_field`): a derived fn now blanks
   only when EVERY declared non-nameplate base column is absent. The executor resolves the fn's real inputs
   from its canonical `derivation_binding` row and every registry fn honest-degrades per-input, so blanking
   on ONE over-declared base (activeEnergyTodayKwh declaring import+export on an import-only meter) pre-empted
   REAL data. Released ~380 leaves (card-72 energy family, voltageStatutoryBand/nominalVoltageLN with the
   deviation base absent, peak_today_time with the ts pseudo-base, …).
2. **rule (ii) reuse smear — quantity distinctness** (`enforce_honest_blank`): fires only when the shared
   bind is UNCLASSIFIED and ≥2 scalar cells classify DISTINCT quantities. A same-quantity annotation re-bind
   (maxY + maxLine.value + maxLine.label ← current_max; summary.value + sideValue ← current_avg) is ONE
   measurement rendered in several places — released. A CLASSIFIED bind's cross-quantity cells are blanked
   per-cell by the quantity wall with their own honest reasons (c54/c55/c57 land there — same catches,
   better reasons). Reuse FP suspects 450 → 0.
3. **rule (iii) quantity wall — vocabulary + evidence precision**:
   - `lol`/`lolpct` → lifetime (`quantity.name_classes` row + code default): kills the aging-ancestor bleed
     that blanked the exactly-right `aging.points[*].lolPct ← loss_of_life_pct` bind (87 releases); power/
     energy into lolPct still blanks.
   - ordered pairs `quantity.compatible_slot_source_pairs` = [[current,deviation-spread],[voltage,deviation-
     spread]]: an amps/volts-dimensioned SPREAD statistic (current_max_spread, worstPhaseSpreadV) into the
     card-46 'Max Spread (A)' cells keeps (~230 releases). Reverse NOT granted — maxDeviation ←
     voltageStatutoryBand and crest-factor/flicker ← spread still blank.
   - metric-name evidence added LAST in the slot-side chain: metric='ups_transfers_30d' (count) ←
     energy fn, metric='backup_readiness_score' ← raw kW, metric='current_max' ← worstPeakKw now blank
     per-cell (+63 real catches that the old positional reuse drop only caught by luck of field order).
4. **rule (iii-b) axis coherence — directional sources** (`_axis_direction_ok` + config rows
   `quantity.axis_{max,min,range}_source_tokens`): an axis bound answered by a source whose OWN name is that
   bound (maxY←current_max/worstPeakKw, minY←current_min, both←voltageHistoryDomain/StatutoryBand) is a REAL
   measured extremum/range, not a live sample — released (~426). Cross-quantity sources, instantaneous-sample
   reads (yMax=yMin←active_power_total_kw) and wrong-direction reads (minY←worstPeakKw) still blank.
5. **rule (iv) const source — structural knobs + citation precision**:
   - `quantity.structural_const_tokens` (decimals/opacity/index/layout/windowdays): display/frame knobs the
     AI misplaced into data_instructions state no measurement — released (~598: decimals=0,
     selectedSampleIndex, areaOpacity, layout, windowDays). Quantity-named consts (131 A, 0.0 kW, 1461 kWh,
     expectedMin=414, thresholds) never match and stay policed.
   - `_values_equal`: a scalar citing one ELEMENT of a list `consts.*` row resolves (band rows cited as
     expectedMin/expectedMax separately); tolerant isclose comparison. No new consts.* rows were seeded —
     the recurring 410/430/414/427 band literals stay blanked (the honest fill is fn voltageStatutoryBand,
     which current prompts bind).

## Files changed

- `layer2/gates.py` — rules (i)/(ii)/(iii)/(iii-b)/(iv) precision (see above)
- `layer2/quantity_class.py` — lol/lolpct vocab, ordered compatible pairs, structural-const tokens,
  tolerant/list-membership const equality
- `db/seed_quantity_class.sql` (+ applied to cmd_catalog.app_config) — name_classes update + 5 new rows:
  compatible_slot_source_pairs, structural_const_tokens, axis_max/min/range_source_tokens
- tests: `tests/test_layer2_wall_precision_rework.py` (new, 13 pins: releases AND still-fires),
  `tests/test_layer2_honest_blank_gate.py` (3 pins updated to quantity-distinct semantics),
  `tests/test_residual2_fixes.py` (axis round-4 contract)

## Residuals / notes

- ~12 archive leaves where a `*_deviation_pct` column rides the (voltage, deviation-spread) grant into a
  V-unit series cell — right quantity family, wrong unit spelling; acceptable vs the ~230 correct spread
  releases (splitting deviation vs spread classes would break the pinned card-47 crest/flicker contract).
- rule_unmapped (463) is the concurrent card-65 semantic-family wall; its reason text should be added to the
  replay tool's `_RULE_MAP` by the tool's owner so it stops bucketing as unmapped.
- Old-emitted garbage (pre-prompt-fix hotspotC/voltage-column hallucinations, baked 410/430 band consts)
  keeps blanking by design — those are "wall correctly killed a bad old emit", weighted accordingly: of the
  after-FP suspects, only ~30 come from fresh `outputs/logs` emits, and each fresh family (card-72 energy
  fns, card-46 maxY/minY, card-41 hv/lv) is either released by this rework or an intended boundary catch.

## How this was verified

1. `PYTHONPATH=. python3.11 tools/wall_corpus_replay.py --out-json outputs/wall_replay_after.json` (6063
   emits, 44428 fields) + a field-level detail replay diffed per (file, line, slot, bind).
2. Released 2449 blanks categorized exhaustively: reuse-same-quantity 723, const-structural 598,
   axis-directional 426, derived-partial-basis 380, quantity-wall vocab/pairs 322 — no uncategorized release.
3. New 433 blanks: 336 = concurrent semantic-family wall; 97 = this rework, sampled per rule — all real
   catches (metric-evidence puns, cross-quantity axis under co-emitted series, Storybook band consts).
4. Spot-check table above; `pytest -m 'not live' -q` green — 516 passed, 14 skipped, 40 deselected (one
   transient `test_config_cast_integrity` failure during the run came from the CONCURRENT workflow seeding
   `xaxis.bucket_fallback` with data_type='string' mid-sweep; the row was corrected to 'text' seconds later
   and the test passes — not a wall-rework file).
