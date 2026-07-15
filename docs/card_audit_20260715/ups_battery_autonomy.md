# Card audit — ups-asset-dashboard/battery-autonomy

- Meter table: `gic_01_n3_ups_01_p1` (standard electrical MFM: voltage/current/power/PF/THD/KPI columns)
- Asset: GIC-01-N3-UPS-01
- Reference: CMD_V2 storybook battery/autonomy demo payloads

## Core finding
This page renders battery-domain cards (SOC, cell temperature, backup runtime, autonomy/readiness)
against an **electrical** meter. Probe of `information_schema.columns` shows **no** battery SOC,
health-score, cell-temperature, runtime, or autonomy column. So every genuinely battery-specific leaf
is `honest_absent` — V48 is correct to blank it, and the EMS only fills it because the storybook demo
fabricates battery telemetry.

Two exceptions are real electrical quantities the meter DOES measure and that were left unbound:
- `batteryHealth.metrics[1].value` (output voltage) → `voltage_avg` (24908/24908 rows, avg 234.7)
- `batteryHealth.metrics[2].value` (output current) → `current_avg` (24908/24908 rows, avg 264.3)
These are `binding_gap` (bindable). Note the EMS demo numbers (433 V / 17.7 A) are demo values; the live
meter reads ~235 V / ~264 A — a rebind shows honest live electrical values, not the demo numbers.

Data availability (last 7 days): voltage_avg, current_avg, active_power_total_kw,
apparent_power_total_kva, power_factor_total, kpi_voltage_deviation_pct,
kpi_neutral_to_phase_ratio_pct all = 24908/24908 non-null.

## Card 50 — Battery Health (TilePayload snapshot; fields=[])
| leaf | verdict | reason |
|---|---|---|
| batteryHealth.soc | honest_absent | no SOC column on electrical meter |
| batteryHealth.socMax | honest_absent | no SOC column |
| batteryHealth.socPct | honest_absent | no SOC column |
| batteryHealth.insight | honest_absent | narrative summary, no measured source |
| batteryHealth.metrics[0].value (temp 34C) | honest_absent | no temperature column |
| batteryHealth.metrics[1].value (voltage 433) | binding_gap | `voltage_avg` exists w/ data — bind it (live ~235V) |
| batteryHealth.metrics[2].value (current 17.7) | binding_gap | `current_avg` exists w/ data — bind it (live ~264A) |

## Card 51 — Battery Health History (flat_series)
Series[0..3] ARE bound source=live to real columns (active_power_total_kw, kpi_voltage_deviation_pct,
kpi_neutral_to_phase_ratio_pct, power_factor_total) as PROXY labels ("Overall Battery Score",
"DC Bus Quality", "Thermal Score", "SOC Score"). Underlying columns have data, so the plotted series
render — these are proxy/mis-labelled but not blank.

| leaf | verdict | reason |
|---|---|---|
| batteryHistory.series[0..3].legendValue | derivation_gap | series data exists; per-series legend summary just not emitted (fixable as summary-of-series; values are electrical proxies) |
| batteryHistory.insight | honest_absent | narrative summary, no measured source |
| batteryHistory.thresholds[0].value (60) | binding_gap | static Ready-zone marker — canonical constant fill |
| batteryHistory.thresholds[1].value (30) | binding_gap | static Moderate-zone marker — canonical constant fill |

## Card 52 — Backup Readiness (TilePayload snapshot; fields=[])
| leaf | verdict | reason |
|---|---|---|
| backupReadiness.score | honest_absent | no battery readiness/SOC column |
| backupReadiness.scoreMax | honest_absent | no capacity/max-readiness column |
| backupReadiness.deltaLabel | honest_absent | no historical readiness delta |
| backupReadiness.envelopePct | honest_absent | no autonomy/envelope column |
| backupReadiness.readyMarkerPct (60) | binding_gap | static ready-marker — canonical constant fill |
| backupReadiness.metrics[0].value (41 min runtime) | honest_absent | no battery runtime/duration column |
| backupReadiness.metrics[1].value (48 headroom) | derivation_gap | fn loadFactorPct measures load-factor, not readiness → correct honest-blank (wrong-quantity derivation) |

## Card 53 — Backup Readiness History (flat_series)
Series[0..3] bound source=live to active_power_total_kw / apparent_power_total_kva /
power_factor_total (proxy labels: Autonomy index, Runtime score, Load pressure score, Headroom score).
Columns populated → series render.

| leaf | verdict | reason |
|---|---|---|
| backupHistory.series[0..3].legendValue | derivation_gap | series data exists; legend summary not emitted (proxy series) |
| backupHistory.insight | honest_absent | narrative summary, no measured source |
| backupHistory.thresholds[0].value (60) | binding_gap | static Ready-zone marker — canonical constant fill |
| backupHistory.thresholds[1].value (30) | binding_gap | static Moderate-zone marker — canonical constant fill |

## fix_family clusters
- `battery_domain_absent` — SOC/temperature/runtime/readiness/autonomy leaves with no measured column (the dominant, correct-to-blank cluster)
- `narrative_insight_absent` — AI/derived insight strings, no measured source
- `unbound_electrical_bind` — card-50 output voltage/current bindable to voltage_avg/current_avg
- `static_threshold_fill` — ready/moderate zone markers (60/30) + readyMarkerPct are canonical constants
- `legendvalue_derivation` — series legend summaries derivable from already-bound live series
- `loadfactor_wrong_quant` — loadFactorPct derivation honest-blanked because it measures the wrong quantity
