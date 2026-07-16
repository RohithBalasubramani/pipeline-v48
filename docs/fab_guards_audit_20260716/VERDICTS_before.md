# fab_guards SHADOW-REPLAY VERDICTS

- generated: 2026-07-16T06:23:09
- source: `outputs/fab_guards_audit_before/renders`
- response files: 19  (parsed 19, skipped 0, no-cards 0)
- total gap records: 890  (shadow 33 / enforce 857)
- distinct (card, cause) pairs: 108

## Per-cause rollup

| cause | count |
| --- | ---: |
| unbound_by_emit | 539 |
| column_absent | 185 |
| no_reading | 129 |
| unstripped_seed | 33 |
| structurally_null | 2 |
| no_nameplate | 1 |
| quantity_mismatch | 1 |

## Verdict table  (card x cause, by count desc)

| card_id | title | cause | count | example slot | example column |
| ---: | --- | --- | ---: | --- | --- |
| 71 | Runtime & Duty | unbound_by_emit | 69 | duty.topKpis[0].value |  |
| 23 | PQ Issues KPI Strip (Total Issues / I-THD Events / V-THD Events / PF Gap Feeders / Neutral Stress / Worst I-THD / Worst V-THD) | unbound_by_emit | 30 | strip.stats.worst.h3 |  |
| 24 | Harmonics & PQ Timeline | column_absent | 30 | timeline.periods.panels[0].h3 |  |
| 26 | Feeder PQ At Today | column_absent | 30 | table.period.panels[0].h3 |  |
| 27 | Signature | column_absent | 30 | signature.period.panels[0].h3 |  |
| 42 | Load Anomalies | unbound_by_emit | 30 | data.dipEvents |  |
| 13 | Energy Flow Diagram | no_reading | 28 | flow.vm.sources[0].totalKw |  |
| 19 | AI Summary | unbound_by_emit | 28 | summary.pres.worstIDecimals |  |
| 12 | Energy Input & Distribution | column_absent | 25 | rail.vm.sources[0].utilizationPct |  |
| 13 | Energy Flow Diagram | column_absent | 25 | flow.vm.sources[0].utilizationPct |  |
| 12 | Energy Input & Distribution | no_reading | 24 | rail.vm.sources[0].totalKw |  |
| 61 | Thermal Timeline | unbound_by_emit | 19 | chart.band.y1 |  |
| 24 | Harmonics & PQ Timeline | no_reading | 18 | timeline.periods.panels[0].h5 |  |
| 26 | Feeder PQ At Today | no_reading | 18 | table.period.panels[0].h5 |  |
| 27 | Signature | no_reading | 18 | signature.period.panels[0].h5 |  |
| 70 | Live Operations & Runtime | unbound_by_emit | 18 | liveOps.service.hours |  |
| 56 | Source Transfer ? Composite | unbound_by_emit | 15 | composite.floor.value |  |
| 62 | Pressure ? Speed ? Load | unbound_by_emit | 14 | chart.band.y1 |  |
| 77 | Insulation Aging & Loss of Life | unbound_by_emit | 14 | aging.kpis.agingFactor |  |
| 76 | Thermal Timeline | unbound_by_emit | 13 | timeline.legend[0].value |  |
| 20 | Event Timeline at Today | column_absent | 12 | trend.period.panels[0].cause |  |
| 48 | Distortion & Harmonic Profile | unbound_by_emit | 12 | distortionProfile.views.h5-h7.yMax |  |
| 81 | Tap Activity & Wear | unbound_by_emit | 12 | activity.kpis[0].value |  |
| 44 | Voltage History | unbound_by_emit | 11 | data.legend[1].value |  |
| 47 | Power Quality | unbound_by_emit | 11 | snapshot.h5.valuePct |  |
| 49 | Load Impact & Transformer Stress | unbound_by_emit | 11 | loadImpact.views.k-stress.stats[0].value |  |
| 52 | Backup Readiness | unbound_by_emit | 11 | backupReadiness.score |  |
| 59 | Output Load & Capacity ? Composite | unbound_by_emit | 11 | composite.points |  |
| 45 | Current Live Health | unbound_by_emit | 10 | health.data.metrics[2].value |  |
| 57 | UPS Capacity | unbound_by_emit | 10 | capacity.deltaLabel |  |
| 67 | Voltage History | unbound_by_emit | 10 | data.stats[2].value |  |
| 50 | Battery Health | unbound_by_emit | 9 | batteryHealth.soc |  |
| 54 | Transfer readiness | unbound_by_emit | 9 | capacity.deltaLabel |  |
| 79 | Voltage Regulation Timeline | unbound_by_emit | 9 | regulation.kpis[2].value |  |
| 14 | Cumulative Energy | unbound_by_emit | 8 | card.view.target |  |
| 43 | Voltage Live Health | unbound_by_emit | 8 | health.data.metrics[2].value |  |
| 46 | Current History | unbound_by_emit | 8 | history.data.stats[2].value |  |
| 5 | Real Time Monitoring (Feeder Heatmap) | unbound_by_emit | 8 | heatmap.sectionContracts.hhf |  |
| 53 | Power Energy Analysis | unstripped_seed | 8 | backupHistory.series[0].legendValue |  |
| 63 | Fuel Tank Anatomy | column_absent | 8 | snapshot.autonomy |  |
| 78 | Tap Position Optimization | unbound_by_emit | 8 | tapPosition.kpis[0].value |  |
| 17 | Daily Power Demand by Feeder | no_reading | 7 | demand.view.points[0].hhf |  |
| 55 | Activity | unbound_by_emit | 7 | activity.metrics[0].value |  |
| 15 | Today live power analysis | unbound_by_emit | 6 | card.view.metrics[2].value |  |
| 36 | Power & Energy (Real-Time) | unbound_by_emit | 6 | data.readings.reactiveEnergy.displayValue |  |
| 36 | Power & Energy (Real-Time) | unstripped_seed | 6 | freshness.tone |  |
| 37 | Voltage Monitor (Real-Time) | unstripped_seed | 6 | freshness.tone |  |
| 38 | Current Monitor (Real-Time) | unstripped_seed | 6 | freshness.tone |  |
| 73 | Power Energy Analysis | unbound_by_emit | 6 | backupHistory.thresholds[0].value |  |
| 12 | Energy Input & Distribution | unbound_by_emit | 5 | rail.vm.kpis.lossKwh |  |
| 17 | Daily Power Demand by Feeder | unbound_by_emit | 5 | demand.view.stats[1].value |  |
| 24 | Harmonics & PQ Timeline | unbound_by_emit | 5 | timeline.limits.iThdLimit |  |
| 39 | Today's Energy | unbound_by_emit | 5 | data.secKwhPerUnit |  |
| 65 | Fuel & Tank ? Composite | unbound_by_emit | 5 | chart.band.y1 |  |
| 66 | Voltage Live Health | column_absent | 5 | data.summary.value |  |
| 75 | Life & Capacity | unbound_by_emit | 5 | lifeCapacity.deratedKva |  |
| 21 | Current Distribution at Today | no_reading | 4 | distribution.period.panels[6].amps |  |
| 26 | Feeder PQ At Today | unbound_by_emit | 4 | table.pres.decimals.thd |  |
| 27 | Signature | unbound_by_emit | 4 | signature.pres.rail.fallbackCount |  |
| 38 | Current Monitor (Real-Time) | unbound_by_emit | 4 | data.thresholds[0].value |  |
| 51 | Battery Health History | unbound_by_emit | 4 | batteryHistory.thresholds[0].value |  |
| 51 | Battery Health History | unstripped_seed | 4 | batteryHistory.series[0].legendValue |  |
| 53 | Backup Readiness History | unbound_by_emit | 4 | backupHistory.thresholds[0].value |  |
| 64 | All Runs (Fuel Log) | unbound_by_emit | 4 | stats.faults |  |
| 68 | Current Live Health | unbound_by_emit | 4 | data.phases[0].delta |  |
| 74 | Thermal Life | unbound_by_emit | 4 | thermalLife.metrics[2].value |  |
| 16 | Energy Consumption Trend | unbound_by_emit | 3 | trend.view.legend[2].value |  |
| 65 | Fuel & Tank ? Composite | column_absent | 3 | chart.legend[0].value |  |
| 66 | Voltage Live Health | unbound_by_emit | 3 | data.phases[0].delta |  |
| 7 | Context Rail Header (Overview / Section / Feeder) | unbound_by_emit | 3 | railVM.trend.areaOpacity |  |
| 80 | Recent Tap Changes | unbound_by_emit | 3 | changes.rows |  |
| 23 | PQ Issues KPI Strip (Total Issues / I-THD Events / V-THD Events / PF Gap Feeders / Neutral Stress / Worst I-THD / Worst V-THD) | no_reading | 2 | strip.stats.vThd |  |
| 36 | Power & Energy (Real-Time) | column_absent | 2 | data.readings.reactiveEnergy.value |  |
| 39 | Today's Energy | structurally_null | 2 | data.reactiveEnergyKwh | reactive_energy_import_kvarh |
| 40 | Power Energy Analysis | unbound_by_emit | 2 | data.contractedKw |  |
| 44 | Voltage History | no_reading | 2 | data.legend[0].value |  |
| 58 | UPS Load | unbound_by_emit | 2 | load.scoreCells[1].value |  |
| 67 | Voltage History | unstripped_seed | 2 | data.maxLine.label |  |
| 69 | Current History | unbound_by_emit | 2 | data.expectedMax |  |
| 7 | Context Rail Header (Overview / Section / Feeder) | column_absent | 2 | railVM.supply.denominator |  |
| 72 | Energy & Reliability | unbound_by_emit | 2 | energyReliability.activeFraction |  |
| 74 | Thermal Life | column_absent | 2 | thermalLife.metrics[0].value |  |
| 9 | Total Feeder Consumption / Supply | column_absent | 2 | supply.denominator |  |
| 9 | Total Feeder Consumption / Supply | unbound_by_emit | 2 | supply.consumedHint.leftKw |  |
| 10 | Consumption Trend / Supply Trend | unbound_by_emit | 1 | trend.areaOpacity |  |
| 160 | Heatmap Footer ? Time Axis & Shade Legend | unbound_by_emit | 1 | selectedSampleIndex |  |
| 39 | Today's Energy | no_reading | 1 | data.activeEnergyKwh | active_energy_import_kwh |
| 40 | Power Energy Analysis | no_nameplate | 1 | data.ratedKw |  |
| 41 | Input vs Output Energy | unbound_by_emit | 1 | data.lossPctOfInput |  |
| 42 | Load Anomalies | column_absent | 1 | data.maxThresholdPct |  |
| 44 | Voltage History | column_absent | 1 | data.stats[2].value |  |
| 45 | Current Live Health | column_absent | 1 | health.data.summary.value |  |
| 46 | Current History | column_absent | 1 | history.data.stats[1].value |  |
| 47 | Power Quality | unstripped_seed | 1 | snapshot.presentation.complianceStrip.trendLabel |  |
| 6 | Live Scrubber / Step Control | unbound_by_emit | 1 | selectedSampleIndex |  |
| 64 | All Runs (Fuel Log) | no_reading | 1 | stats.avgLoad |  |
| 65 | Fuel & Tank ? Composite | no_reading | 1 | chart.kpis[1].value |  |
| 66 | Voltage Live Health | no_reading | 1 | data.metrics[0].value | voltage_ll_unbalance_pct |
| 68 | Current Live Health | no_reading | 1 | data.metrics[1].value |  |
| 69 | Current History | no_reading | 1 | data.stats[2].value |  |
| 71 | Runtime & Duty | column_absent | 1 | duty.points[*].label |  |
| 71 | Runtime & Duty | no_reading | 1 | duty.points[*].loadPct |  |
| 72 | Energy & Reliability | quantity_mismatch | 1 | energyReliability.apparentMvah |  |
| 76 | Thermal Timeline | column_absent | 1 | timeline.points[*].loadPct |  |
| 77 | Insulation Aging & Loss of Life | column_absent | 1 | aging.points[*].lolPct |  |
| 79 | Voltage Regulation Timeline | column_absent | 1 | regulation.kpis[0].value |  |
| 79 | Voltage Regulation Timeline | no_reading | 1 | regulation.bandLowKv |  |
| 80 | Recent Tap Changes | column_absent | 1 | changes.rows[*].time |  |

## Per-page sections

### asset_overview  (individual-feeder-meter-shell/real-time-monitoring)

| card_id | cause | count |
| ---: | --- | ---: |
| 36 | unstripped_seed | 3 |
| 36 | unbound_by_emit | 2 |
| 36 | column_absent | 1 |
| 37 | unstripped_seed | 3 |
| 38 | unstripped_seed | 3 |
| 38 | unbound_by_emit | 2 |

### dg_engine_cooling  (diesel-generator-asset-dashboard/engine-cooling)

| card_id | cause | count |
| ---: | --- | ---: |
| 61 | unbound_by_emit | 19 |
| 62 | unbound_by_emit | 14 |

### dg_fuel_efficiency  (diesel-generator-asset-dashboard/fuel-efficiency)

| card_id | cause | count |
| ---: | --- | ---: |
| 63 | column_absent | 8 |
| 64 | unbound_by_emit | 4 |
| 64 | no_reading | 1 |
| 65 | unbound_by_emit | 5 |
| 65 | column_absent | 3 |
| 65 | no_reading | 1 |

### dg_operations_runtime  (diesel-generator-asset-dashboard/operations-runtime)

| card_id | cause | count |
| ---: | --- | ---: |
| 53 | unstripped_seed | 4 |
| 70 | unbound_by_emit | 18 |
| 71 | unbound_by_emit | 69 |
| 71 | column_absent | 1 |
| 71 | no_reading | 1 |
| 72 | unbound_by_emit | 2 |
| 72 | quantity_mismatch | 1 |
| 73 | unbound_by_emit | 6 |

### dg_voltage_current  (diesel-generator-asset-dashboard/voltage-current)

| card_id | cause | count |
| ---: | --- | ---: |
| 66 | column_absent | 5 |
| 66 | unbound_by_emit | 3 |
| 66 | no_reading | 1 |
| 67 | unbound_by_emit | 10 |
| 68 | unbound_by_emit | 4 |
| 68 | no_reading | 1 |
| 69 | unbound_by_emit | 2 |
| 69 | no_reading | 1 |

### feeder_energy_power  (individual-feeder-meter-shell/energy-power)

| card_id | cause | count |
| ---: | --- | ---: |
| 39 | unbound_by_emit | 5 |
| 39 | structurally_null | 2 |
| 39 | no_reading | 1 |
| 40 | unbound_by_emit | 2 |
| 40 | no_nameplate | 1 |
| 41 | unbound_by_emit | 1 |
| 42 | unbound_by_emit | 30 |
| 42 | column_absent | 1 |

### feeder_power_quality  (individual-feeder-meter-shell/power-quality)

| card_id | cause | count |
| ---: | --- | ---: |
| 47 | unbound_by_emit | 11 |
| 47 | unstripped_seed | 1 |
| 48 | unbound_by_emit | 12 |
| 49 | unbound_by_emit | 11 |

### feeder_rtm  (individual-feeder-meter-shell/real-time-monitoring)

| card_id | cause | count |
| ---: | --- | ---: |
| 36 | unbound_by_emit | 4 |
| 36 | unstripped_seed | 3 |
| 36 | column_absent | 1 |
| 37 | unstripped_seed | 3 |
| 38 | unstripped_seed | 3 |
| 38 | unbound_by_emit | 2 |

### feeder_voltage_current  (individual-feeder-meter-shell/voltage-current)

| card_id | cause | count |
| ---: | --- | ---: |
| 43 | unbound_by_emit | 8 |
| 44 | unbound_by_emit | 11 |
| 44 | no_reading | 2 |
| 44 | column_absent | 1 |
| 45 | unbound_by_emit | 10 |
| 45 | column_absent | 1 |
| 46 | unbound_by_emit | 8 |
| 46 | column_absent | 1 |
| 67 | unstripped_seed | 2 |

### panel_energy_distribution  (panel-overview-shell/energy-distribution)

| card_id | cause | count |
| ---: | --- | ---: |
| 12 | column_absent | 25 |
| 12 | no_reading | 24 |
| 12 | unbound_by_emit | 5 |
| 13 | no_reading | 28 |
| 13 | column_absent | 25 |

### panel_energy_power  (panel-overview-shell/energy-power)

| card_id | cause | count |
| ---: | --- | ---: |
| 14 | unbound_by_emit | 8 |
| 15 | unbound_by_emit | 6 |
| 16 | unbound_by_emit | 3 |
| 17 | no_reading | 7 |
| 17 | unbound_by_emit | 5 |

### panel_harmonics_pq  (panel-overview-shell/harmonics-pq)

| card_id | cause | count |
| ---: | --- | ---: |
| 23 | unbound_by_emit | 30 |
| 23 | no_reading | 2 |
| 24 | column_absent | 30 |
| 24 | no_reading | 18 |
| 24 | unbound_by_emit | 5 |
| 26 | column_absent | 30 |
| 26 | no_reading | 18 |
| 26 | unbound_by_emit | 4 |
| 27 | column_absent | 30 |
| 27 | no_reading | 18 |
| 27 | unbound_by_emit | 4 |

### panel_rtm  (panel-overview-shell/real-time-monitoring)

| card_id | cause | count |
| ---: | --- | ---: |
| 10 | unbound_by_emit | 1 |
| 160 | unbound_by_emit | 1 |
| 5 | unbound_by_emit | 8 |
| 6 | unbound_by_emit | 1 |
| 7 | unbound_by_emit | 3 |
| 7 | column_absent | 2 |
| 9 | column_absent | 2 |
| 9 | unbound_by_emit | 2 |

### panel_voltage_current  (panel-overview-shell/voltage-current)

| card_id | cause | count |
| ---: | --- | ---: |
| 19 | unbound_by_emit | 28 |
| 20 | column_absent | 12 |
| 21 | no_reading | 4 |

### transformer_tap_rtcc  (transformer-asset-dashboard/tap-rtcc)

| card_id | cause | count |
| ---: | --- | ---: |
| 78 | unbound_by_emit | 8 |
| 79 | unbound_by_emit | 9 |
| 79 | column_absent | 1 |
| 79 | no_reading | 1 |
| 80 | unbound_by_emit | 3 |
| 80 | column_absent | 1 |
| 81 | unbound_by_emit | 12 |

### transformer_thermal_life  (transformer-asset-dashboard/thermal-life)

| card_id | cause | count |
| ---: | --- | ---: |
| 74 | unbound_by_emit | 4 |
| 74 | column_absent | 2 |
| 75 | unbound_by_emit | 5 |
| 76 | unbound_by_emit | 13 |
| 76 | column_absent | 1 |
| 77 | unbound_by_emit | 14 |
| 77 | column_absent | 1 |

### ups_battery_autonomy  (ups-asset-dashboard/battery-autonomy)

| card_id | cause | count |
| ---: | --- | ---: |
| 50 | unbound_by_emit | 9 |
| 51 | unbound_by_emit | 4 |
| 51 | unstripped_seed | 4 |
| 52 | unbound_by_emit | 11 |
| 53 | unbound_by_emit | 4 |
| 53 | unstripped_seed | 4 |

### ups_output_load  (ups-asset-dashboard/output-load-capacity)

| card_id | cause | count |
| ---: | --- | ---: |
| 57 | unbound_by_emit | 10 |
| 58 | unbound_by_emit | 2 |
| 59 | unbound_by_emit | 11 |

### ups_source_transfer  (ups-asset-dashboard/source-transfer)

| card_id | cause | count |
| ---: | --- | ---: |
| 54 | unbound_by_emit | 9 |
| 55 | unbound_by_emit | 7 |
| 56 | unbound_by_emit | 15 |

