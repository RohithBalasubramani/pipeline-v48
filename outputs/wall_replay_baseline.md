# Wall corpus-replay baseline

Generated 2026-07-15T10:55:44+00:00 by `tools/wall_corpus_replay.py` — gates sha 31619f526e73625e, quantity_class sha daf40d134a6a794c.

**Acceptance standard:** all fabrications caught, zero legit binds harmed — diff per_rule + false_positive_suspects against this baseline after every wall change.

## Corpus

- files: 634  ·  records: 18002  ·  L2 emit calls: 7396 (dupes 6)
- emits replayed: 283  ·  response unparseable (skipped): 3  ·  other skips: 7104
- emits with a TRUNCATED prompt basket (rule-(i) blanks are replay artifacts there): 19

## Totals

- fields seen: 2189  ·  fields blanked: 424 (rate 0.1937)
- suspected false positives: 19 (of which 0 are truncated-basket replay artifacts)

## Per-rule blanks

| rule | fields blanked | emits touched |
|---|---|---|
| rule_i_membership | 8 | 6 |
| rule_iii_quantity_wall | 174 | 64 |
| rule_iiib_axis_coherence | 41 | 22 |
| rule_iiid_boundary | 4 | 2 |
| rule_iv_const_source | 171 | 66 |
| rule_unmapped | 26 | 15 |

## Gate issue classes (gate_data_instructions)

| class | count |
|---|---|
| event_without_edge | 1 |
| missing_column | 8 |

## Roster issue classes (gate_roster)

| class | count |
|---|---|
| agg_differs_from_recipe | 2 |
| bad_scope | 14 |
| element_key_invented | 48 |
| fixed_key_changed | 7 |
| slot_not_in_recipe | 249 |

## Bypass counts

| bypass | count |
|---|---|
| ctx_fields | 979 |
| ctx_fields_blanked | 133 |
| ctx_fields_kept | 846 |
| ctx_fields_with_measured_bind | 787 |
| ctx_kept_with_offbasket_column | 12 |
| group_card_emits | 186 |
| group_card_fields | 1476 |
| rule_i_exempt_fields | 1196 |

## Suspected false positives (first 60 — full list in wall_replay_baseline.json)

A blanked bind whose column quantity MATCHES its slot's quantity (or a rule-(i) blank on a truncated replay basket). Review each: a real catch stays; a harmed legit bind is a wall bug.

| file:line | run | card | rule | slot | bind | slot_cls | src_cls | match | artifact |
|---|---|---|---|---|---|---|---|---|---|
| outputs/logs/ai_r_1f97dfa47f.jsonl:9 | r_1f97dfa47f | 65 | rule_unmapped | chart.kpis[0].value | fn:loadFactorPct | percent | load-factor | compatible |  |
| outputs/logs/ai_r_1f97dfa47f.jsonl:15 | r_1f97dfa47f | 65 | rule_unmapped | chart.kpis[0].value | fn:loadFactorPct | percent | load-factor | compatible |  |
| outputs/logs/ai_r_44796d791a.jsonl:7 | r_44796d791a | 73 | rule_i_membership | data.series[1].values | col:reactive_energy_import_kvarh | energy | energy | same |  |
| outputs/logs/ai_r_44796d791a.jsonl:33 | r_c7938ef357 | 69 | rule_unmapped | data.stats[2].value | col:kpi_voltage_deviation_pct | percent | deviation-spread | compatible |  |
| outputs/logs/ai_r_92a2bfb0ae.jsonl:152 | r_92a2bfb0ae | 43 | rule_i_membership | health.data.metrics[1].value | col:voltage_max_spread | voltage | deviation-spread | compatible |  |
| outputs/logs/ai_r_92a2bfb0ae.jsonl:163 | r_92a2bfb0ae | 46 | rule_unmapped | history.data.stats[2].value | fn:loadFactorPct | percent | load-factor | compatible |  |
| outputs/logs/ai_r_99879f110d.jsonl:29 | r_1f97dfa47f | 65 | rule_unmapped | chart.kpis[0].value | fn:loadFactorPct | percent | load-factor | compatible |  |
| outputs/logs/ai_r_99879f110d.jsonl:30 | r_bb525a5212 | 41 | rule_iiid_boundary | data.hvInputKw | col:active_power_total_kw | power | power | same |  |
| outputs/logs/ai_r_99879f110d.jsonl:30 | r_bb525a5212 | 41 | rule_iiid_boundary | data.lvOutputKw | col:active_power_total_kw | power | power | same |  |
| outputs/logs/ai_r_bb525a5212.jsonl:6 | r_bb525a5212 | 41 | rule_iiid_boundary | data.hvInputKw | col:active_power_total_kw | power | power | same |  |
| outputs/logs/ai_r_bb525a5212.jsonl:6 | r_bb525a5212 | 41 | rule_iiid_boundary | data.lvOutputKw | col:active_power_total_kw | power | power | same |  |
| outputs/logs/ai_r_bb525a5212.jsonl:7 | r_bb525a5212 | 40 | rule_iiib_axis_coherence | data.yMax | col:active_power_total_kw | power | power | same |  |
| outputs/logs/ai_r_bb525a5212.jsonl:7 | r_bb525a5212 | 40 | rule_iiib_axis_coherence | data.yMin | col:active_power_total_kw | power | power | same |  |
| outputs/logs/ai_r_bb525a5212.jsonl:7 | r_bb525a5212 | 40 | rule_iiib_axis_coherence | data.demandYMax | col:active_power_total_kw | power | power | same |  |
| outputs/logs/ai_r_bb525a5212.jsonl:7 | r_bb525a5212 | 40 | rule_iiib_axis_coherence | data.demandYMin | col:active_power_total_kw | power | power | same |  |
| outputs/logs/ai_r_d06f6da969.jsonl:35 | r_e02e4237bf | 59 | rule_unmapped | composite.points[*].bypassFrequencyHz | col:frequency_hz | frequency | frequency | same |  |
| outputs/logs/ai_r_d7be9457fc.jsonl:7 | r_d7be9457fc | 56 | rule_unmapped | composite.points[*].bypassFrequencyHz | col:frequency_hz | frequency | frequency | same |  |
| outputs/logs/ai_r_e02e4237bf.jsonl:7 | r_e02e4237bf | 59 | rule_unmapped | composite.points[*].label | col:active_power_total_kw | power | power | same |  |
| outputs/logs/ai_r_e02e4237bf.jsonl:7 | r_e02e4237bf | 59 | rule_unmapped | composite.points[*].bypassFrequencyHz | col:frequency_hz | frequency | frequency | same |  |

## How to use (future wall changes)

1. `PYTHONPATH=. python3.11 tools/wall_corpus_replay.py --out-json /tmp/after.json --out-md /tmp/after.md`
2. Diff `per_rule`, `bypass`, `false_positive_suspects` vs this committed baseline.
3. Standard: every NEW blank must be a real fabrication; every VANISHED blank must be an intended release; the FP-suspect list must not grow with quantity-matching binds.
