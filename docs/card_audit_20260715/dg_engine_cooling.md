# Card audit — diesel-generator-asset-dashboard/engine-cooling

- **Meter:** `dg_1_mfm` (asset_id 2, "DG-1")
- **Meter class:** pure electrical MFM. Columns = voltage_*, current_*, active/reactive/apparent power, active_energy_import_kwh, frequency_hz, power_factor_total, phase_angle_deg, kpi_true_pf, kpi_voltage_deviation_pct. **No temperature / oil-pressure / RPM / coolant / load-percent sensor column exists.**
- **Data availability (7d):** 120,925 rows; active_power_total_kw, voltage_r_n, power_factor_total all fully populated.

## Headline verdict
This is an **engine cooling / mechanical-sensor** dashboard (thermal, oil pressure, engine speed, load) rendered against an **electrical** meter. The generator's physical sensors (coolant/oil/exhaust/intake temperature, oil-pressure kPa, engine-speed RPM) are simply **not wired into this MFM**. Almost every blank data leaf on this page is therefore `honest_absent` — V48 is correct to blank them; the EMS storybook shows numbers only because it is a demo payload, not a live read of an electrical meter.

The **only genuinely fixable** leaves are the two **load-percent** slots on card 62 (Peak Load, Load legend), which are derivable from `active_power_total_kw` + DG nameplate rating — the same inputs that already produced the working `Avg Load = 56.7 %` KPI. These are `derivation_gap`, not honest_absent.

---

## Card 60 — Engine 3D Callout Viewer
No blank data-leaf gaps recorded. The single callout `callouts[0].metric.value` (engine temperature) is already `_honest_blanked` in the data_instructions — no temperature column on this meter. **Correct.** `honest_absent` (engine_temp_absent). No fix.

## Card 61 — Thermal Timeline
Every series is bound to a **voltage** column proxied as a temperature label (`voltage_r_n`→"Oil Temperature", `voltage_y_n`→"Intake", `voltage_b_n`→"Exhaust", `voltage_ln_avg`→"Coolant"). Those series rendered as **0.0** (garbage proxy) — a **mis-bind proxy** the executor let through as non-blank, so it does not appear in gaps.json but is worth flagging: voltage is not temperature and should honest-blank, not proxy.

All recorded blank leaves are temperature quantities / temperature thresholds / temperature narrative, none of which have a source column:

| leaf group | ref example | verdict | fix_family |
|---|---|---|---|
| band.y1/y2 (coolant band 75/95°C) | 75, 95 | honest_absent | engine_temp_absent |
| kpis[*].value / note (656°C exhaust, 101, 2, "1 danger") | 656 | honest_absent | engine_temp_absent |
| events[*].idx/why/value (temp excursion events) | "load 99%", 656 | honest_absent | engine_temp_absent |
| legend[*].value (88/101/55/485 temps) | 88 | honest_absent | engine_temp_absent |
| series[*].trip/warn/limit.*.value (temp trip/warn limits, consts) | 104, 95, 120, 620 | honest_absent | threshold_const_no_source |
| insight (thermal narrative) | "Exhaust over-temp…" | honest_absent | narrative_absent |
| axes[*].width, kpis[*].swatch/unit/valueColor, series[*].width/dash | — | chrome_noise | chrome |

## Card 62 — Pressure · Speed · Load
`Avg Load` KPI **filled = 56.7 %** via `loadFactorPct(active_power_total_kw)` → DG nameplate rating exists and the derivation path works. That is the anchor proving the two other load-percent slots are fixable.

| leaf | ref | v48 | verdict | fix_family | note |
|---|---|---|---|---|---|
| kpis[0].value "Peak Load" % | 99 | — | derivation_gap | loadfactor_derivation | fn `worstPeakKw` returns kW not %; needs peak-load-percent fn over active_power_total_kw + rating (same inputs as working Avg Load) |
| chart.legend[2].value "Load" % | 68 | — | derivation_gap | loadfactor_derivation | route through loadFactorPct (current bind is `active_power_total_kw` source=frame — a kW-into-% unit crossing correctly blocked; the real fix is the derived percent, not a raw rebind) |
| kpis[2].value "Min Oil-P" kPa | 177 | — | honest_absent | oil_pressure_absent | no pressure column |
| chart.legend[0].value "Oil P" kPa | 341 | — | honest_absent | oil_pressure_absent | declared metric active_power_total_kw is a wrong-quantity proxy (kW→kPa); no pressure column exists |
| chart.legend[1].value "Speed" rpm | 1499 | — | honest_absent | engine_speed_absent | no RPM column |
| chart.band.y1/y2 (pressure band 300/500) | 300,500 | — | honest_absent | threshold_const_no_source | pressure band consts, no nameplate/app_config source |
| chart.events[0].idx/why/value (oil-pressure event) | 177 | — | honest_absent | oil_pressure_absent | pressure event; no pressure column |
| chart.series[0].trip/warn/limit.*.value (pressure limits) | 140,200 | — | honest_absent | threshold_const_no_source | pressure trip/warn consts |
| chart.insight | "Oil pressure low…" | "" | honest_absent | narrative_absent | pressure/speed narrative |
| chart.series[*].width | — | — | chrome_noise | chrome | visual |

### Fixable summary for synthesis
- `loadfactor_derivation` (card 62, 2 leaves): Peak Load % and Load legend %. Actionable — rating + power inputs both present; extend the loadFactorPct family to a peak-load-percent fn and route the Load legend value through the derived percent.
- Everything else = honest data gap: this electrical MFM does not carry engine thermal/pressure/speed sensors. Do **not** fabricate. The card-61 voltage→temperature series proxy should ideally be tightened to honest-blank rather than render 0.0.
