# Wall corpus-replay baseline

Generated 2026-07-06T12:45:31+00:00 by `tools/wall_corpus_replay.py` — gates sha 64f56b478e5cf854, quantity_class sha af972209d295fc22.

**Acceptance standard:** all fabrications caught, zero legit binds harmed — diff per_rule + false_positive_suspects against this baseline after every wall change.

## Corpus

- files: 558  ·  records: 14217  ·  L2 emit calls: 6123 (dupes 135)
- emits replayed: 5982  ·  response unparseable (skipped): 6  ·  other skips: 0
- emits with a TRUNCATED prompt basket (rule-(i) blanks are replay artifacts there): 14

## Totals

- fields seen: 43745  ·  fields blanked: 15617 (rate 0.357)
- suspected false positives: 2073 (of which 0 are truncated-basket replay artifacts)

## Per-rule blanks

| rule | fields blanked | emits touched |
|---|---|---|
| rule_i_membership | 2515 | 628 |
| rule_ii_reuse_smear | 1852 | 949 |
| rule_iii_quantity_wall | 4949 | 1748 |
| rule_iiib_axis_coherence | 573 | 282 |
| rule_iiic_expectation | 37 | 8 |
| rule_iiid_boundary | 134 | 129 |
| rule_iv_const_source | 5557 | 1973 |

## Gate issue classes (gate_data_instructions)

| class | count |
|---|---|
| const_without_value | 53 |
| derived_without_base_columns | 72 |
| derived_without_fn | 374 |
| fields_empty | 5 |
| missing_column | 141 |
| validate_fail_column | 42 |

## Roster issue classes (gate_roster)

| class | count |
|---|---|
| agg_differs_from_recipe | 15 |
| bad_scope | 54 |
| element_key_invented | 526 |
| fixed_key_changed | 120 |
| other | 6 |
| roster_without_recipe | 23 |
| slot_not_in_recipe | 888 |

## Bypass counts

| bypass | count |
|---|---|
| ctx_fields | 25625 |
| ctx_fields_blanked | 6651 |
| ctx_fields_kept | 18974 |
| ctx_fields_with_measured_bind | 20211 |
| ctx_kept_with_offbasket_column | 2829 |
| group_card_emits | 4713 |
| group_card_fields | 33666 |
| rule_i_exempt_fields | 31727 |

## Suspected false positives (first 60 — full list in wall_replay_baseline.json)

A blanked bind whose column quantity MATCHES its slot's quantity (or a rule-(i) blank on a truncated replay basket). Review each: a real catch stays; a harmed legit bind is a wall bug.

| file:line | run | card | rule | slot | bind | slot_cls | src_cls | match | artifact |
|---|---|---|---|---|---|---|---|---|---|
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_1bc17049b9.jsonl:4 | r_f3b19721cb | 76 | rule_i_membership | timeline.points[*].hotspotC | col:hotspotC | temperature | temperature | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_1bc17049b9.jsonl:4 | r_f3b19721cb | 76 | rule_i_membership | timeline.points[*].oilC | col:oilC | temperature | temperature | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_1bc17049b9.jsonl:4 | r_f3b19721cb | 76 | rule_i_membership | timeline.points[*].windingC | col:windingC | temperature | temperature | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_1bc17049b9.jsonl:4 | r_f3b19721cb | 76 | rule_i_membership | timeline.legend[0].value | col:hotspotC | temperature | temperature | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_1bc17049b9.jsonl:4 | r_f3b19721cb | 76 | rule_i_membership | timeline.legend[1].value | col:oilC | temperature | temperature | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_1f97dfa47f.jsonl:9 | r_1f97dfa47f | 65 | rule_ii_reuse_smear | chart.legend[0].value | fn:loadFactorPct | percent | load-factor | compatible |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_264fea76ed.jsonl:6 | r_264fea76ed | 41 | rule_iiid_boundary | data.hvInputKw | col:active_power_total_kw | power | power | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_264fea76ed.jsonl:6 | r_264fea76ed | 41 | rule_ii_reuse_smear | data.lvOutputKw | col:active_power_total_kw | power | power | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_32cbdcba77.jsonl:6 | r_d06f6da969 | 44 | rule_i_membership | history.data.stats[1].value | fn:voltageHistoryDomain | voltage | voltage | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_32cbdcba77.jsonl:6 | r_d06f6da969 | 44 | rule_i_membership | history.data.maxLine.label.value | fn:voltageStatutoryBand | voltage | voltage | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_32cbdcba77.jsonl:6 | r_d06f6da969 | 44 | rule_i_membership | history.data.minLine.label.value | fn:voltageStatutoryBand | voltage | voltage | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_44796d791a.jsonl:19 | r_44796d791a | 72 | rule_i_membership | energyReliability.cells[0].value | fn:activeEnergyTodayKwh | energy | energy | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_44796d791a.jsonl:19 | r_44796d791a | 72 | rule_i_membership | energyReliability.cells[1].value | fn:reactiveEnergyTodayKvarh | energy | energy | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_44796d791a.jsonl:19 | r_44796d791a | 72 | rule_i_membership | energyReliability.apparentMvah | fn:apparentEnergyTodayKvah | energy | energy | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_44796d791a.jsonl:19 | r_44796d791a | 72 | rule_i_membership | energyReliability.activeMwh | fn:activeEnergyTodayKwh | energy | energy | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_44796d791a.jsonl:19 | r_44796d791a | 72 | rule_i_membership | energyReliability.reactiveMvarh | fn:reactiveEnergyTodayKvarh | energy | energy | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_44796d791a.jsonl:20 | r_44796d791a | 70 | rule_ii_reuse_smear | liveOps.topKpis[3].value | fn:loadFactorPct | percent | load-factor | compatible |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_44796d791a.jsonl:21 | r_44796d791a | 73 | rule_i_membership | data.series[1].values | col:reactive_energy_import_kvarh | energy | energy | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_5991ad70df.jsonl:3 | r_5991ad70df | 41 | rule_iiid_boundary | data.hvInputKw | col:active_power_total_kw | power | power | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_5991ad70df.jsonl:3 | r_5991ad70df | 41 | rule_ii_reuse_smear | data.lvOutputKw | col:active_power_total_kw | power | power | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_5991ad70df.jsonl:4 | r_5991ad70df | 40 | rule_ii_reuse_smear | data.demandYMax | fn:worstPeakKw | power | power | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_5991ad70df.jsonl:4 | r_5991ad70df | 40 | rule_ii_reuse_smear | data.demandYMin | fn:worstPeakKw | power | power | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_8cfd3d6cf1.jsonl:6 | r_8cfd3d6cf1 | 50 | rule_i_membership | batteryHealth.socPct | col:battery_soc | battery-charge | battery-charge | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_8cfd3d6cf1.jsonl:6 | r_8cfd3d6cf1 | 50 | rule_i_membership | batteryHealth.metrics[0].value | col:battery_temp | temperature | temperature | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_8cfd3d6cf1.jsonl:6 | r_8cfd3d6cf1 | 50 | rule_i_membership | batteryHealth.metrics[1].value | col:output_voltage | voltage | voltage | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_8cfd3d6cf1.jsonl:6 | r_8cfd3d6cf1 | 50 | rule_i_membership | batteryHealth.metrics[2].value | col:output_current | current | current | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_8cfd3d6cf1.jsonl:7 | r_8cfd3d6cf1 | 52 | rule_i_membership | backupReadiness.score | col:backup_readiness | readiness | readiness | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_8cfd3d6cf1.jsonl:7 | r_8cfd3d6cf1 | 52 | rule_i_membership | backupReadiness.deltaLabel | col:backup_readiness_delta | readiness | readiness | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_92a2bfb0ae.jsonl:13 | r_92a2bfb0ae | 43 | rule_i_membership | health.data.metrics[1].value | fn:nominalVoltageLN | voltage | voltage | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_92a2bfb0ae.jsonl:16 | r_92a2bfb0ae | 46 | rule_iiib_axis_coherence | history.data.maxY | col:current_max | current | current | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_92a2bfb0ae.jsonl:16 | r_92a2bfb0ae | 46 | rule_iiib_axis_coherence | history.data.minY | col:current_min | current | current | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_92a2bfb0ae.jsonl:23 | r_92a2bfb0ae | 46 | rule_iiib_axis_coherence | history.data.maxY | col:current_max | current | current | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_92a2bfb0ae.jsonl:23 | r_92a2bfb0ae | 46 | rule_iiib_axis_coherence | history.data.minY | col:current_min | current | current | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_92a2bfb0ae.jsonl:32 | r_92a2bfb0ae | 46 | rule_iiib_axis_coherence | history.data.maxY | col:current_max | current | current | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_92a2bfb0ae.jsonl:32 | r_92a2bfb0ae | 46 | rule_iiib_axis_coherence | history.data.minY | col:current_min | current | current | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_92a2bfb0ae.jsonl:40 | r_92a2bfb0ae | 46 | rule_iiib_axis_coherence | history.data.maxY | col:current_max | current | current | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_92a2bfb0ae.jsonl:40 | r_92a2bfb0ae | 46 | rule_iiib_axis_coherence | history.data.minY | col:current_min | current | current | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_92a2bfb0ae.jsonl:47 | r_92a2bfb0ae | 46 | rule_iiib_axis_coherence | history.data.maxY | col:current_max | current | current | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_92a2bfb0ae.jsonl:47 | r_92a2bfb0ae | 46 | rule_iiib_axis_coherence | history.data.minY | col:current_min | current | current | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_92a2bfb0ae.jsonl:61 | r_92a2bfb0ae | 46 | rule_iiib_axis_coherence | history.data.maxY | col:current_max | current | current | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_92a2bfb0ae.jsonl:61 | r_92a2bfb0ae | 46 | rule_iiib_axis_coherence | history.data.minY | col:current_min | current | current | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_92a2bfb0ae.jsonl:62 | r_92a2bfb0ae | 46 | rule_iiib_axis_coherence | history.data.maxY | col:current_max | current | current | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_92a2bfb0ae.jsonl:62 | r_92a2bfb0ae | 46 | rule_iiib_axis_coherence | history.data.minY | col:current_min | current | current | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_92a2bfb0ae.jsonl:71 | r_92a2bfb0ae | 46 | rule_iiib_axis_coherence | history.data.maxY | col:current_max | current | current | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_92a2bfb0ae.jsonl:71 | r_92a2bfb0ae | 46 | rule_iiib_axis_coherence | history.data.minY | col:current_min | current | current | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_92a2bfb0ae.jsonl:80 | r_92a2bfb0ae | 46 | rule_ii_reuse_smear | history.data.maxY | col:current_max | current | current | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_92a2bfb0ae.jsonl:80 | r_92a2bfb0ae | 46 | rule_iiib_axis_coherence | history.data.minY | col:current_min | current | current | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_92a2bfb0ae.jsonl:80 | r_92a2bfb0ae | 46 | rule_ii_reuse_smear | history.data.maxLine.value | col:current_max | current | current | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_92a2bfb0ae.jsonl:80 | r_92a2bfb0ae | 46 | rule_ii_reuse_smear | history.data.maxLine.label.value | col:current_max | current | current | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_b7f5f3c4dc.jsonl:1 | r_b7f5f3c4dc | 70 | rule_ii_reuse_smear | liveOps.service.availability | fn:loadFactorPct | percent | load-factor | compatible |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_b7f5f3c4dc.jsonl:1 | r_b7f5f3c4dc | 70 | rule_ii_reuse_smear | liveOps.topKpis[3].value | fn:loadFactorPct | percent | load-factor | compatible |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_d06f6da969.jsonl:12 | r_bb525a5212 | 41 | rule_iiid_boundary | data.hvInputKw | col:active_power_total_kw | power | power | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_d06f6da969.jsonl:12 | r_bb525a5212 | 41 | rule_ii_reuse_smear | data.lvOutputKw | col:active_power_total_kw | power | power | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_d06f6da969.jsonl:17 | r_bb525a5212 | 40 | rule_iiib_axis_coherence | data.demandYMax | fn:worstPeakKw | power | power | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_d06f6da969.jsonl:21 | r_d06f6da969 | 79 | rule_i_membership | regulation.kpis[1].value | fn:loadFactorPct | percent | load-factor | compatible |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_d06f6da969.jsonl:21 | r_d06f6da969 | 79 | rule_ii_reuse_smear | regulation.kpis[2].value | fn:loadFactorPct | percent | load-factor | compatible |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_d06f6da969.jsonl:21 | r_d06f6da969 | 79 | rule_i_membership | regulation.legend[0].value | col:voltage_avg | voltage | voltage | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_d06f6da969.jsonl:21 | r_d06f6da969 | 79 | rule_i_membership | regulation.points[*].voltageKv | col:voltage_avg | voltage | voltage | same |  |
| outputs/_log_archive/logs_pre3_20260705_203145/ai_r_f3b19721cb.jsonl:8 | r_f3b19721cb | 75 | rule_i_membership | lifeCapacity.deratedLoadKva | col:apparent_power_total_kva | power | power | same |  |
| outputs/_log_archive/logs_pre_20260705_002155/ai_r_0152b3ceec.jsonl:5 | r_0152b3ceec | 43 | rule_i_membership | health.data.phases[0].value | col:voltage_r_n | voltage | voltage | same |  |

## How to use (future wall changes)

1. `PYTHONPATH=. python3.11 tools/wall_corpus_replay.py --out-json /tmp/after.json --out-md /tmp/after.md`
2. Diff `per_rule`, `bypass`, `false_positive_suspects` vs this committed baseline.
3. Standard: every NEW blank must be a real fabrication; every VANISHED blank must be an intended release; the FP-suspect list must not grow with quantity-matching binds.
