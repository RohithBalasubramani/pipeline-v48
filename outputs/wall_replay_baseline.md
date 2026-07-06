# Wall corpus-replay baseline

Generated 2026-07-06T21:20:12+00:00 by `tools/wall_corpus_replay.py` — gates sha 950ce138c77ec68b, quantity_class sha c63f93745299b725.

**Acceptance standard:** all fabrications caught, zero legit binds harmed — diff per_rule + false_positive_suspects against this baseline after every wall change.

## Corpus

- files: 609  ·  records: 16328  ·  L2 emit calls: 6934 (dupes 135)
- emits replayed: 6101  ·  response unparseable (skipped): 8  ·  other skips: 690
- emits with a TRUNCATED prompt basket (rule-(i) blanks are replay artifacts there): 19

## Totals

- fields seen: 44822  ·  fields blanked: 14675 (rate 0.3274)
- suspected false positives: 1678 (of which 0 are truncated-basket replay artifacts)

## Per-rule blanks

| rule | fields blanked | emits touched |
|---|---|---|
| rule_i_membership | 2120 | 386 |
| rule_ii_reuse_smear | 212 | 57 |
| rule_iii_quantity_wall | 5923 | 1955 |
| rule_iiib_axis_coherence | 141 | 79 |
| rule_iiic_expectation | 37 | 8 |
| rule_iiid_boundary | 258 | 129 |
| rule_iv_const_source | 4826 | 1766 |
| rule_unmapped | 1158 | 905 |

## Gate issue classes (gate_data_instructions)

| class | count |
|---|---|
| const_without_value | 51 |
| derived_without_base_columns | 68 |
| derived_without_fn | 233 |
| fields_empty | 5 |
| missing_column | 137 |

## Roster issue classes (gate_roster)

| class | count |
|---|---|
| agg_differs_from_recipe | 15 |
| bad_scope | 65 |
| element_key_invented | 540 |
| fixed_key_changed | 122 |
| other | 6 |
| roster_without_recipe | 23 |
| slot_not_in_recipe | 948 |

## Bypass counts

| bypass | count |
|---|---|
| ctx_fields | 26097 |
| ctx_fields_blanked | 6566 |
| ctx_fields_kept | 19531 |
| ctx_fields_with_measured_bind | 20599 |
| ctx_kept_with_offbasket_column | 2801 |
| group_card_emits | 4781 |
| group_card_fields | 34358 |
| rule_i_exempt_fields | 32309 |

## Suspected false positives (first 60 — full list in wall_replay_baseline.json)

A blanked bind whose column quantity MATCHES its slot's quantity (or a rule-(i) blank on a truncated replay basket). Review each: a real catch stays; a harmed legit bind is a wall bug.

| file:line | run | card | rule | slot | bind | slot_cls | src_cls | match | artifact |
|---|---|---|---|---|---|---|---|---|---|
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_1bc17049b9.jsonl:4 | r_f3b19721cb | 76 | rule_i_membership | timeline.points[*].hotspotC | col:hotspotC | temperature | temperature | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_1bc17049b9.jsonl:4 | r_f3b19721cb | 76 | rule_i_membership | timeline.points[*].oilC | col:oilC | temperature | temperature | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_1bc17049b9.jsonl:4 | r_f3b19721cb | 76 | rule_i_membership | timeline.points[*].windingC | col:windingC | temperature | temperature | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_1bc17049b9.jsonl:4 | r_f3b19721cb | 76 | rule_i_membership | timeline.legend[0].value | col:hotspotC | temperature | temperature | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_1bc17049b9.jsonl:4 | r_f3b19721cb | 76 | rule_i_membership | timeline.legend[1].value | col:oilC | temperature | temperature | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_1f97dfa47f.jsonl:9 | r_1f97dfa47f | 65 | rule_unmapped | chart.kpis[0].value | fn:loadFactorPct | percent | load-factor | compatible |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_1f97dfa47f.jsonl:9 | r_1f97dfa47f | 65 | rule_unmapped | chart.legend[0].value | fn:loadFactorPct | percent | load-factor | compatible |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_264fea76ed.jsonl:6 | r_264fea76ed | 41 | rule_iiid_boundary | data.hvInputKw | col:active_power_total_kw | power | power | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_264fea76ed.jsonl:6 | r_264fea76ed | 41 | rule_iiid_boundary | data.lvOutputKw | col:active_power_total_kw | power | power | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_32cbdcba77.jsonl:6 | r_d06f6da969 | 44 | rule_i_membership | history.data.stats[1].value | fn:voltageHistoryDomain | voltage | voltage | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_32cbdcba77.jsonl:6 | r_d06f6da969 | 44 | rule_i_membership | history.data.maxLine.label.value | fn:voltageStatutoryBand | voltage | voltage | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_32cbdcba77.jsonl:6 | r_d06f6da969 | 44 | rule_i_membership | history.data.minLine.label.value | fn:voltageStatutoryBand | voltage | voltage | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_44796d791a.jsonl:19 | r_44796d791a | 72 | rule_i_membership | energyReliability.cells[1].value | fn:reactiveEnergyTodayKvarh | energy | energy | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_44796d791a.jsonl:19 | r_44796d791a | 72 | rule_i_membership | energyReliability.reactiveMvarh | fn:reactiveEnergyTodayKvarh | energy | energy | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_44796d791a.jsonl:21 | r_44796d791a | 73 | rule_i_membership | data.series[1].values | col:reactive_energy_import_kvarh | energy | energy | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_44796d791a.jsonl:24 | r_e02e4237bf | 59 | rule_unmapped | composite.legend[1].value | col:frequency_hz | frequency | frequency | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_44796d791a.jsonl:24 | r_e02e4237bf | 59 | rule_unmapped | composite.points[*].bypassVoltageV | col:voltage_avg | voltage | voltage | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_44796d791a.jsonl:24 | r_e02e4237bf | 59 | rule_unmapped | composite.points[*].bypassFrequencyHz | col:frequency_hz | frequency | frequency | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_44796d791a.jsonl:24 | r_e02e4237bf | 59 | rule_unmapped | composite.kpiCells[1].value | col:voltage_avg | voltage | voltage | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_5991ad70df.jsonl:3 | r_5991ad70df | 41 | rule_iiid_boundary | data.hvInputKw | col:active_power_total_kw | power | power | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_5991ad70df.jsonl:3 | r_5991ad70df | 41 | rule_iiid_boundary | data.lvOutputKw | col:active_power_total_kw | power | power | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_5991ad70df.jsonl:4 | r_5991ad70df | 40 | rule_iiib_axis_coherence | data.demandYMin | fn:worstPeakKw | power | power | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_8cfd3d6cf1.jsonl:6 | r_8cfd3d6cf1 | 50 | rule_i_membership | batteryHealth.socPct | col:battery_soc | battery-charge | battery-charge | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_8cfd3d6cf1.jsonl:6 | r_8cfd3d6cf1 | 50 | rule_i_membership | batteryHealth.metrics[0].value | col:battery_temp | temperature | temperature | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_8cfd3d6cf1.jsonl:6 | r_8cfd3d6cf1 | 50 | rule_i_membership | batteryHealth.metrics[1].value | col:output_voltage | voltage | voltage | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_8cfd3d6cf1.jsonl:6 | r_8cfd3d6cf1 | 50 | rule_i_membership | batteryHealth.metrics[2].value | col:output_current | current | current | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_8cfd3d6cf1.jsonl:7 | r_8cfd3d6cf1 | 52 | rule_i_membership | backupReadiness.score | col:backup_readiness | readiness | readiness | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_8cfd3d6cf1.jsonl:7 | r_8cfd3d6cf1 | 52 | rule_i_membership | backupReadiness.deltaLabel | col:backup_readiness_delta | readiness | readiness | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_92a2bfb0ae.jsonl:57 | r_92a2bfb0ae | 43 | rule_i_membership | health.data.metrics[1].value | col:voltage_max_spread | voltage | deviation-spread | compatible |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_92a2bfb0ae.jsonl:70 | r_92a2bfb0ae | 43 | rule_i_membership | health.data.metrics[1].value | col:voltage_max_spread | voltage | deviation-spread | compatible |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_b57a82feb3.jsonl:4 | r_d7be9457fc | 56 | rule_unmapped | composite.points[*].bypassVoltageV | col:voltage_avg | voltage | voltage | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_b57a82feb3.jsonl:4 | r_d7be9457fc | 56 | rule_unmapped | composite.points[*].bypassFrequencyHz | col:frequency_hz | frequency | frequency | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_b57a82feb3.jsonl:4 | r_d7be9457fc | 56 | rule_unmapped | composite.kpiCells[1].value | col:voltage_avg | voltage | voltage | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_c7938ef357.jsonl:13 | r_e02e4237bf | 59 | rule_unmapped | composite.legend[1].value | col:frequency_hz | frequency | frequency | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_c7938ef357.jsonl:13 | r_e02e4237bf | 59 | rule_unmapped | composite.points[*].bypassVoltageV | col:voltage_avg | voltage | voltage | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_c7938ef357.jsonl:13 | r_e02e4237bf | 59 | rule_unmapped | composite.points[*].bypassFrequencyHz | col:frequency_hz | frequency | frequency | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_d06f6da969.jsonl:12 | r_bb525a5212 | 41 | rule_iiid_boundary | data.hvInputKw | col:active_power_total_kw | power | power | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_d06f6da969.jsonl:12 | r_bb525a5212 | 41 | rule_iiid_boundary | data.lvOutputKw | col:active_power_total_kw | power | power | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_d06f6da969.jsonl:21 | r_d06f6da969 | 79 | rule_i_membership | regulation.kpis[1].value | fn:loadFactorPct | percent | load-factor | compatible |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_d06f6da969.jsonl:21 | r_d06f6da969 | 79 | rule_i_membership | regulation.kpis[2].value | fn:loadFactorPct | percent | load-factor | compatible |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_d06f6da969.jsonl:21 | r_d06f6da969 | 79 | rule_i_membership | regulation.legend[0].value | col:voltage_avg | voltage | voltage | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_d06f6da969.jsonl:21 | r_d06f6da969 | 79 | rule_i_membership | regulation.points[*].voltageKv | col:voltage_avg | voltage | voltage | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_d7be9457fc.jsonl:7 | r_d7be9457fc | 56 | rule_unmapped | composite.points[*].bypassVoltageV | col:voltage_avg | voltage | voltage | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_d7be9457fc.jsonl:7 | r_d7be9457fc | 56 | rule_unmapped | composite.points[*].bypassFrequencyHz | col:frequency_hz | frequency | frequency | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_d836e61fd9.jsonl:11 | r_d836e61fd9 | 56 | rule_unmapped | composite.points[*].bypassVoltageV | col:voltage_ll_avg | voltage | voltage | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_d836e61fd9.jsonl:11 | r_d836e61fd9 | 56 | rule_unmapped | composite.points[*].bypassFrequencyHz | col:frequency_hz | frequency | frequency | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_d836e61fd9.jsonl:11 | r_d836e61fd9 | 56 | rule_unmapped | composite.kpiCells[1].value | col:voltage_ll_avg | voltage | voltage | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_f3b19721cb.jsonl:8 | r_f3b19721cb | 75 | rule_i_membership | lifeCapacity.deratedLoadKva | col:apparent_power_total_kva | power | power | same |  |
| outputs/_log_archive/logs_pre_20260705_002155/ai_r_0152b3ceec.jsonl:5 | r_0152b3ceec | 43 | rule_i_membership | health.data.phases[0].value | col:voltage_r_n | voltage | voltage | same |  |
| outputs/_log_archive/logs_pre_20260705_002155/ai_r_0152b3ceec.jsonl:5 | r_0152b3ceec | 43 | rule_i_membership | health.data.phases[1].value | col:voltage_y_n | voltage | voltage | same |  |
| outputs/_log_archive/logs_pre_20260705_002155/ai_r_0152b3ceec.jsonl:5 | r_0152b3ceec | 43 | rule_i_membership | health.data.phases[2].value | col:voltage_b_n | voltage | voltage | same |  |
| outputs/_log_archive/logs_pre_20260705_002155/ai_r_0152b3ceec.jsonl:5 | r_0152b3ceec | 43 | rule_i_membership | health.data.summary.value | col:voltage_avg | voltage | voltage | same |  |
| outputs/_log_archive/logs_pre_20260705_002155/ai_r_05a80485bb.jsonl:11 | r_05a80485bb | 41 | rule_iiid_boundary | hvInputKw | col:active_power_total_kw | power | power | same |  |
| outputs/_log_archive/logs_pre_20260705_002155/ai_r_05a80485bb.jsonl:11 | r_05a80485bb | 41 | rule_iiid_boundary | lvOutputKw | col:active_power_total_kw | power | power | same |  |
| outputs/_log_archive/logs_pre_20260705_002155/ai_r_075d05bffb.jsonl:73 | r_075d05bffb | 12 | rule_i_membership | rail.vm.sources[0].utilizationPct | fn:loadFactorPct | percent | load-factor | compatible |  |
| outputs/_log_archive/logs_pre_20260705_002155/ai_r_075d05bffb.jsonl:73 | r_075d05bffb | 12 | rule_i_membership | rail.vm.sources[1].utilizationPct | fn:loadFactorPct | percent | load-factor | compatible |  |
| outputs/_log_archive/logs_pre_20260705_002155/ai_r_075d05bffb.jsonl:96 | r_bb525a5212 | 41 | rule_iiid_boundary | data.hvInputKw | col:active_power_total_kw | power | power | same |  |
| outputs/_log_archive/logs_pre_20260705_002155/ai_r_075d05bffb.jsonl:96 | r_bb525a5212 | 41 | rule_iiid_boundary | data.lvOutputKw | col:active_power_total_kw | power | power | same |  |
| outputs/_log_archive/logs_pre_20260705_002155/ai_r_075d05bffb.jsonl:105 | r_d06f6da969 | 79 | rule_i_membership | regulation.kpis[1].value | fn:loadFactorPct | percent | load-factor | compatible |  |
| outputs/_log_archive/logs_pre_20260705_002155/ai_r_075d05bffb.jsonl:105 | r_d06f6da969 | 79 | rule_i_membership | regulation.kpis[2].value | fn:loadFactorPct | percent | load-factor | compatible |  |

## How to use (future wall changes)

1. `PYTHONPATH=. python3.11 tools/wall_corpus_replay.py --out-json /tmp/after.json --out-md /tmp/after.md`
2. Diff `per_rule`, `bypass`, `false_positive_suspects` vs this committed baseline.
3. Standard: every NEW blank must be a real fabrication; every VANISHED blank must be an intended release; the FP-suspect list must not grow with quantity-matching binds.
