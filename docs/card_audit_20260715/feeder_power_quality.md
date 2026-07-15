# Card audit — individual-feeder-meter-shell/power-quality

- Meter table: `gic_15_n3_pcc_01_transformer_01_se` (neuract, 72 cols, ts col = `timestamp_utc`)
- Asset: GIC-15-N3-PCC-01 (PCC-01 Transformer-01 feeder meter)
- Cards: 47 Power Quality, 48 Distortion & Harmonic Profile, 49 Load Impact & Transformer Stress
- No large grid cards (5 / 24) on this page.

## Meter data availability (last 7 days, all rows = 49,021)

| column | non-null | min | max | avg |
|---|---|---|---|---|
| thd_voltage_r_pct | 49021 | 0.00 | 3.94 | 1.06 |
| thd_current_r_pct | 49021 | 0.00 | 13.13 | 5.23 |
| thd_compliance_v_avg | 49021 | 0.00 | 3.90 | — |
| thd_compliance_i_avg | 49021 | 0.00 | 11.95 | — |
| phase_angle_deg | 49021 | 0.00 | 177.44 | — |
| power_factor_total | 49021 | -0.999 | 1.000 | — |
| kpi_true_pf | 49011 | 0.000 | 1.001 | — |
| kpi_displacement_pf | 49021 | present | | |
| active_power_total_kw | 49021 | present | | |
| pf_gap_vs_full_load | 49011 | -2.000 | 0.098 | — |

Columns that DO NOT exist on this meter: individual harmonic-order magnitudes (5th/7th), flicker Pst, crest factor, K-factor, any dedicated thd max/min/avg column (only per-phase THD instantaneous + the two `thd_compliance_*_avg` aggregates).

The v-thd / i-thd time series (thd_voltage_r/y/b_pct, thd_current_r/y/b_pct) all bind live and render in V48 (not in the gap list), which confirms THD columns are bindable and populated — this is what makes the scalar summaries below derivable.

---

## Card 47 — Power Quality (TilePayload snapshot)

| leaf | ref | verdict | fix_family | note |
|---|---|---|---|---|
| snapshot.h5.valuePct | 10.4 | honest_absent | harmonic_order_absent | 5th-harmonic magnitude — no harmonic-order column exists (only aggregate THD). V48 correct to blank. |
| snapshot.h7.valuePct | 5.3 | honest_absent | harmonic_order_absent | 7th-harmonic magnitude — same. |
| snapshot.flickerPst.value | 0.65 | honest_absent | flicker_absent | No flicker column on this meter. |
| snapshot.flickerPst.peakToday | 0.74 | honest_absent | flicker_absent | Same. |
| snapshot.crestFactor.value | 1.51 | honest_absent | crest_factor_absent | No crest-factor column. |
| snapshot.trendPctPerHour | 289.8 | derivation_gap | thd_trend_derivation | THD is measured; a %/hr trend is derivable (last vs 1h-ago). Tile currently binds only `last`, so a 2nd fetch/derivation is needed. Low value; ref 289.8 is a demo artifact. |

## Card 48 — Distortion & Harmonic Profile (SeriesPayload)

The **h5-h7 view** targets 5th/7th harmonic ORDERS — no such columns exist → the whole view is honest_absent. The **v-thd / i-thd views** plot real THD series (live, present); their scalar summary lines are the only fixables.

| leaf | ref | verdict | fix_family | note |
|---|---|---|---|---|
| h5-h7.yMax | 7 | honest_absent | harmonic_order_absent | axis scale of an absent-quantity view. |
| h5-h7.yMin | 2 | honest_absent | harmonic_order_absent | |
| h5-h7.series[0].value | 4.3% | honest_absent | harmonic_order_absent | 5th-order value, no column. |
| h5-h7.series[1].value | 4.3% | honest_absent | harmonic_order_absent | 7th-order value, no column. |
| h5-h7.maxLine.value | 5.7 | honest_absent | harmonic_order_absent | |
| h5-h7.minLine.value | 4.1 | honest_absent | harmonic_order_absent | |
| i-thd.averageStat.value | 415V | derivation_gap | series_scalar_derivation | avg of the bound thd_current_* series (data present). ref "415V" is a copied voltage demo artifact. |
| i-thd.maxLine.value | 480 | binding_gap | canonical_threshold_fill | THD reference line — fill IEEE-519 current-TDD limit via canonical_slots (policy const, not meter data). ref 480 is a voltage demo artifact. |
| i-thd.minLine.value | 410 | binding_gap | canonical_threshold_fill | Same. |
| v-thd.averageStat.value | 415V | derivation_gap | series_scalar_derivation | avg of bound thd_voltage_* series (present). |
| v-thd.maxLine.value | 480 | binding_gap | canonical_threshold_fill | Fill IEEE-519 voltage-THD limit (5%/8%) via canonical_slots. |
| v-thd.minLine.value | 410 | binding_gap | canonical_threshold_fill | Same. |

## Card 49 — Load Impact & Transformer Stress (SeriesPayload)

Bound-and-rendered (not gaps): pf-health Power Factor (power_factor_total), True PF (kpi_true_pf); pf-angle phase_angle_deg; k-stress load-factor proxy (active_power_total_kw). K-factor itself is NOT measured — the chart plots load-factor as a proxy.

| leaf | ref | verdict | fix_family | note |
|---|---|---|---|---|
| k-stress.stats[2].value ("K-Watch") | 15 | honest_absent | kfactor_threshold_no_source | K-factor is a load-factor proxy, not measured; no nameplate K-rating exists → the watch threshold has no legitimate source. |
| k-stress.watchLines[0].value ("K-Watch") | 5.25 | honest_absent | kfactor_threshold_no_source | Same threshold on the proxy axis. |
| pf-angle.watchLines[0].value ("Lag Watch") | 485 | binding_gap | canonical_threshold_fill | phase_angle_deg IS measured (0–177°); a lag-watch limit (label says "20") is a policy const, fillable via canonical_slots. ref 485 is a demo artifact. |
| pf-health.stats[2].value ("PF Gap (displ.)") | 0.52 | derivation_gap | pf_gap_derivation | kpi_displacement_pf + power_factor_total exist → the displacement-PF gap is derivable. Emit wrongly tried fn=loadFactorPct (wrong quantity). ref 0.52 is a demo artifact. |
| pf-health.stats[3].value ("PF Target") | 0.95 | binding_gap | canonical_threshold_fill | 0.95 is the standard regulatory PF target — canonical const fill (not fabrication). |
| pf-health.watchLines[0].value ("PF Target") | 0.95 | binding_gap | canonical_threshold_fill | Same PF-target reference line. |

## Summary of fixables

- **canonical_threshold_fill** (policy consts via existing canonical_slots, NOT meter data): v-thd/i-thd max/minLine (IEEE-519 THD limits), pf-angle lag-watch, PF Target 0.95 (×2). 6 leaves.
- **series_scalar_derivation** (avg over already-bound THD series): v-thd/i-thd averageStat. 2 leaves.
- **pf_gap_derivation** (kpi_displacement_pf present): pf-health PF Gap. 1 leaf.
- **thd_trend_derivation** (THD trend %/hr, needs extra fetch): card 47 trend. 1 leaf (low value).
- **honest_absent** (genuinely not on this meter): harmonic orders (8), flicker (2), crest (1), K-factor thresholds (2). 13 leaves — V48 correctly blanks.

No fabrication proposed. All "fixable" items either bind an existing column, derive from an already-bound series, or fill a known policy/statutory constant.
