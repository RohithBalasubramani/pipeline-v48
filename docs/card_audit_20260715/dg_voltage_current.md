# Card audit — diesel-generator-asset-dashboard/voltage-current

Meter: `dg_1_mfm` (DG-1). Probed 2026-07-15 over neuract :5433.

## Meter reality
`dg_1_mfm` is a **rich MFM** — it exposes every voltage/current column the EMS reference wants:

| column | 7d non-null / 120926 | running value | notes |
|---|---|---|---|
| voltage_ry / voltage_yb / voltage_br | FULL (120926) | ~11045 V (L-L) | present, **routed source=frame** |
| voltage_ll_avg | FULL | 11045.8 V | present, frame; slot wants **kV** |
| voltage_ln_avg | FULL | 6377.7 V | present, frame |
| voltage_ln_max / voltage_ln_min | FULL | 6385.9 / 6363.6 V | spread derivable (~22 V L-N) |
| voltage_ln_unbalance_pct | SPARSE 1346 | 0.220 % | populated only while running; **null at DG-off tail** |
| voltage_ll_unbalance_pct | SPARSE 1346 | — | same sparse pattern |
| kpi_voltage_deviation_pct | FULL | -100 (off) | rendered |
| current_r/y/b/neutral/avg/max/min | FULL (120925) | 0 now / 66 A hist | bound live, render 0 (DG off) |
| current_unbalance_pct | FULL (120925) | null at tail | **null at DG-off tail**; card69 max-agg recovered 2.33 |

**Root context:** DG-1 is currently OFF. Latest row = 0 V / 0 A / deviation -100 %. So `agg=last` bindings hit a null/zero tail even where the column is fully populated historically. Card 69 (which uses windowed max/avg aggs) rendered real values (peak 66 A, unbalance 2.33); the live snapshot cards blanked on the same columns.

## The #1 systemic gap on this page
Card 66 routes **voltage_ry / voltage_yb / voltage_br / voltage_ll_avg / voltage_ln_avg to `source=frame`** (honest-blank) even though all five columns are FULLY populated on this meter. This is the classic `frame_declared_bindable` rescue — rebind `source=live` to the declared column. `voltage_ll_avg` additionally needs a V→kV morph (slot is kV, column is volts ~11045); the pipeline blocked it as an "unit-crossing proxy".

## Card 66 — Voltage Live Health
- `.phases[0..2].value` (voltage_ry/yb/br, frame) → **frame_declared_bindable** — columns FULL. Rebind source=live. `frame_declared_rescue`.
- `.metrics[1].value` (voltage_ln_avg, frame) → **frame_declared_bindable** — column FULL. `frame_declared_rescue`.
- `.summary.value` (voltage_ll_avg, frame) → **frame_declared_bindable** — column FULL but needs V→kV scaling into the kV slot. `frame_kv_unit_rescue`.
- `.metrics[0].value` (voltage_ln_unbalance_pct, live BOUND) → **windowing** — column has data (0.22 running) but null at DG-off tail; `agg=last` blanks. Recover with last-non-null / windowed agg. `last_nonnull_agg`.
- `.metrics[2].value` "Spread" (unbound, ref 103) → **derivation_gap** — derivable from voltage_ln_max − voltage_ln_min (both FULL). `spread_derivation`.
- `.phases[*].delta` → **derivation_gap** — per-phase deviation vs nominal, derivable once phase values bound. `phase_delta_derived`.
- `.phases[*].tailPct/widthPct/markerPct` → **chrome_noise** — bullet-bar geometry, not independent data. `bar_geometry`.
- `.insight` → **honest_absent** — narrative string, no column. `narrative_insight`.

## Card 67 — Voltage History
- `.series[0..2]` (voltage_ry/yb/br, live bucketed) → rendered (320 pts, 0.0 in current DG-off window). Not a gap.
- `.stats[1].value` "Worst Spread" (voltage_ll_unbalance_pct, live) → **windowing** — sparse column, null tail; also semantic mismatch (ref 103 V spread vs %-unbalance column). Recover via windowed agg / consider L-L max spread. `last_nonnull_agg`.
- `.stats[1].note` "(L3-L1)" → **chrome_noise** static descriptor. `static_note`.
- `.events[0..4].index`, `.legend[0..1].value` → **honest_absent** — no sag/swell event column on this meter. `events_absent`.
- `.maxLine.value/.minLine.value/.expectedMax/.expectedMin` (±5 % band 11.55/10.45) → **derivation_gap** — derivable from nominal voltage (11 kV) ±5 % statutory band (canonical-band fill). `statutory_band_derivation`.
- `.insight` → **honest_absent** narrative. `narrative_insight`.

## Card 68 — Current Live Health
- `.phases[0..3].value` (current_r/y/b/neutral, live) → rendered 0.0 (DG off). Not a blank gap.
- `.metrics[0]` Avg, `.metrics[2]` Neutral → rendered 0.0. Not gaps.
- `.metrics[1].value` (current_unbalance_pct, live) → **windowing** — column FULL but null at DG-off tail; `agg=last` blanks. Card 69 recovered 2.33 via max-agg. `last_nonnull_agg`.
- `.phases[*].delta` → **derivation_gap** — per-phase deviation, derivable. `phase_delta_derived`.
- `.phases[*].tailPct/widthPct/markerPct` → **chrome_noise** bullet-bar geometry. `bar_geometry`.
- `.insight` → **honest_absent** narrative. `narrative_insight`.

## Card 69 — Current History
- stats (peak 66 A, avg 0.4, unbalance 2.33, neutral 1.03) and series → rendered real via windowed aggs. Not gaps.
- `.maxLine.value` "Rated: —" (ref 131 A) → **derivation_gap** — rated line needs a DG rated-current nameplate; **honest_absent if no DG current rating exists in the equipment schema**. `rated_current_nameplate`.
- `.expectedMax/.expectedMin` (99.4 / 73.5 A band) → **derivation_gap** — ±band around rated/avg current; same nameplate dependency. `rated_band_derivation`.
- `.insight` → **honest_absent** narrative. `narrative_insight`.

## Summary of fixable vs honest
- **Fixable (frame rescue):** card66 voltage_ry/yb/br, voltage_ln_avg, voltage_ll_avg(kV) — 5 leaves, columns FULL.
- **Fixable (agg):** card66 metrics[0], card67 stats[1], card68 metrics[1] — sparse/full columns null only at DG-off tail; windowed agg recovers.
- **Fixable (derivation):** card66 Spread (ln_max−ln_min), card67 ±5 % band (nominal), card69 rated/band (nameplate-dependent).
- **Honest absent:** card67 events/legend (no event column), all narrative insights, phase bullet-bar geometry (chrome).
