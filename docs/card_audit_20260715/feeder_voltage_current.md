# Card audit — individual-feeder-meter-shell/voltage-current

- Meter table: `gic_15_n3_pcc_01_transformer_01_se` (asset GIC-15-N3-PCC-01, an **HT transformer feeder**, reads ~6519 V L-N / 11 kV class)
- Cards on page: 43 Voltage Live Health, 44 Voltage History, 45 Current Live Health, 46 Current History
- 65 candidate gap leaves total.

## Meter column data availability (last 7 days, ~49,022 rows)

Voltage — ALL present: `voltage_r_n / y_n / b_n`, `voltage_ry / yb / br`, `voltage_avg`, `voltage_max`, `voltage_min`,
`voltage_unbalance_pct`, `voltage_r/y/b_deviation_pct`, `kpi_voltage_deviation_pct`.
Voltage — ABSENT: `voltage_ll_avg` = 0.

Current — present: `current_r / y / b / neutral`, `current_max`, `current_min`, `current_max_spread`, `current_spread_ry/by/br`.
Current — **all-NULL**: `current_avg` = 0, `current_unbalance_pct` = 0, `current_r/y/b_deviation_pct` = 0.

Events — present: `sag_event_active` (7 active samples), `swell_event_active` (49,014 active), numeric 0/1 flags.
`current_imbalance_event_active` / `neutral_stress_event_active` present but 0 active.

## Key findings

1. **Phase-bar geometry leaves blank while the phase VALUE renders.** Each phase tile carries `value` (present, e.g. 6543 V)
   but `delta / deltaText.value / tailPct / widthPct / markerPct` are "—". These are FE-mapper display geometry, not raw
   bound leaves. For **voltage** the deviation (`delta`) is directly derivable from `voltage_r/y/b_deviation_pct` which HAVE
   data → derivation_gap. For **current** the deviation columns are all-NULL but `delta` is still derivable from the present
   phase currents (delta = phase−avg / avg). Bar-position pcts (tail/width/marker) additionally need a nominal/rating band.

2. **`current_avg` is the systemic current gap.** The reference "Average current 243 A" (card 45 summary.value, card 46
   stats[1]) is declared `source=frame metric=current_avg`. The real column `current_avg` EXISTS but is 100% NULL on this
   meter, so this is NOT a frame_declared_bindable rescue — it is a **derivation_gap**: derive avg from `current_r/y/b`
   (all present). Same for `current_unbalance_pct` (bound-live but column all-NULL) → derivable from phase currents.

3. **Sag/swell event markers are UNBOUND but the data exists.** Card 44 `events[].index` (12 markers) and `legend[].value`
   (event counts) are null; the di declared no event slots, yet `sag_event_active`/`swell_event_active` are data-bearing →
   binding_gap. (Note: on this HT meter the wrong 415 V nominal makes "swell" fire nearly always; the count is real but the
   band reference is broken — see #5.)

4. **Line-label formatting.** Card 44 `maxLine.label.value`/`minLine.label.value` are "—" while `maxLine.value`=6543 /
   `minLine.value`=6485.95 ARE present → pure chrome formatting of an already-present number.

5. **Nominal / expected band leaves.** `band.markerPct`, `expectedMax`, `expectedMin` need a nominal voltage band. The di
   honest-blanks these ("const 0 has no real DB source"). Nameplate-nominal band fill (canonical_slots / nameplate_nominal)
   can derive them, but note this HT meter currently carries a wrong 415 V nominal — the band derivation must use the true
   6351 V (11 kV) nameplate. Marked derivation_gap.

6. **Genuinely honest-absent.** `metrics[2].value` Rate Change (V/min, and the current analog) is a time-derivative not in
   the snapshot schema. Current expected band (card 46 expectedMax/Min) has no meaningful current nominal on this feeder.

7. Narrative `insight` strings are ungenerated (derivation_gap — templatable from the present series).

## Per-card verdicts

### Card 43 — Voltage Live Health
- `band.markerPct` → derivation_gap (voltage_band_nominal_derivable) — nameplate nominal band.
- `phases[0..2].delta`, `.deltaText.value` → derivation_gap (phase_deviation_derivable) — `voltage_r/y/b_deviation_pct` present.
- `phases[0..2].tailPct/.widthPct/.markerPct` → derivation_gap (phasebar_geometry_band_derivable) — value present, needs nominal band.
- `insight` → derivation_gap (insight_narrative_ungenerated).
- `metrics[2].value` (Rate Change V/min) → honest_absent (rate_change_not_measured).

### Card 44 — Voltage History
- `events[0..11].index` → binding_gap (event_markers_unbound) — `sag_event_active`/`swell_event_active` present.
- `legend[0..1].value` → binding_gap (event_count_unbound) — event counts derivable from same columns.
- `insight` → derivation_gap (insight_narrative_ungenerated).
- `maxLine.label.value`, `minLine.label.value` → chrome_noise (linelabel_format_derivable) — numeric value already present.
- `expectedMax`, `expectedMin` → derivation_gap (voltage_band_nominal_derivable).

### Card 45 — Current Live Health
- `phases[0..3].delta`, `.deltaText.value` → derivation_gap (current_phase_delta_derivable) — deviation cols NULL but phases present.
- `phases[0..3].tailPct/.widthPct/.markerPct` → honest_absent (current_rating_band_absent) — no full-load current rating band.
- `metrics[0].value` (current_unbalance_pct, bound-live, col NULL) → derivation_gap (current_unbalance_derivable) — from phase currents.
- `metrics[2].value` → honest_absent (rate_change_not_measured).
- `summary.value` (current_avg, frame) → derivation_gap (current_avg_derivable) — `current_avg` col all-NULL, derive from phases.
- `summary.caption` ("Average current · Peak 305 A") → derivation_gap (caption_derivable) — avg derivable + peak=`current_max` present.

### Card 46 — Current History
- `stats[1].value` (current_avg, frame) → derivation_gap (current_avg_derivable).
- `stats[2].value` (current_unbalance_pct, col NULL) → derivation_gap (current_unbalance_derivable).
- `expectedMax`, `expectedMin` → honest_absent (current_rating_band_absent).

## Fix-family clusters
- `current_avg_derivable` — 2 leaves (biggest recurring current gap; `current_avg` col null → derive from phase currents).
- `current_unbalance_derivable` — 2 leaves.
- `phase_deviation_derivable` / `current_phase_delta_derivable` — phase-tile delta text (voltage from deviation cols; current from phases).
- `phasebar_geometry_band_derivable` (voltage) / `current_rating_band_absent` (current) — bar-position pcts.
- `event_markers_unbound` / `event_count_unbound` — sag/swell markers + counts (data exists, unbound).
- `voltage_band_nominal_derivable` — band.markerPct + expected band (nameplate nominal; HT nominal currently wrong).
- `linelabel_format_derivable` — chrome formatting of already-present max/min.
- `insight_narrative_ungenerated`, `caption_derivable` — generated text.
- `rate_change_not_measured` — honest, time-derivative not in schema.
