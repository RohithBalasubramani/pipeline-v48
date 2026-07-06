# prompt A/B — v1 (live emit prompt) vs v2 (data_instructions_v2.md variant)

generated: 2026-07-07 03:02:22   url: http://localhost:8200/v1/chat/completions   calls: 8 cards x 2 arms

v2 is composed from layer2/prompts/data_instructions_v2.md with the SAME dynamic content extracted from
the logged v1 call (endpoint sets, per-card recovery library, roster presence); the user message and every
sampling knob are identical — the arms differ ONLY in system-prompt structure.

## aggregate

| metric | v1 | v2 |
|---|---|---|
| parse_ok | 8 | 8 |
| conforms=true | 8 | 8 |
| fields emitted | 36 | 22 |
| bad slots | 0 | 0 |
| bad columns | 0 | 0 |
| gate issues | 0 | 0 |
| gate-blanked leaves | 5 | 0 |
| honest answers (partial/none + data_note) | 4 | 4 |
| tokens in (sum) | 167266 | 147364 |
| tokens out (sum) | 16194 | 15961 |

### card 74 — Thermal Life  (transformer-asset-dashboard/thermal-life)   [ai_r_f3b19721cb.jsonl:6]

system-prompt chars: v1=53482  v2=43554  (-19%)

| metric | v1 (live) | v2 (variant) |
|---|---|---|
| parse_ok | True | True |
| conforms | True | True |
| answerability | partial | none |
| fields emitted | 1 | 0 |
| slots omitted | 4 | 5 |
| roster entries | 0 | 0 |
| endpoint | real-time-monitoring | real-time-monitoring |
| bad slots (not in list) | 0 | 0 |
| bad columns (not in basket) | 0 | 0 |
| gate issues | 0 | 0 |
| gate-blanked leaves | 1 | 0 |
| roster issues | 0 | 0 |
| metadata byte-issues | 0 | 0 |
| tokens in/out | 17944/878 | 15520/802 |
| latency s | 6.4 | 5.7 |
- v1 data_note: Showing active power loss (kW) as a proxy for thermal stress; winding and oil temperatures are not measured by this meter.
- v2 data_note: This asset's meter logs electrical parameters (power, current, voltage, frequency) but does not measure thermal quantities (winding/oil temperature, thermal stress, or loss-of-life). All thermal slots are honest-blank.
- v1 blanked: thermalLife.metrics[2].value: lifetime not measured by this meter (no lifetime column) — column 'active_power_total_kw' measures power, not lifetime; leaf honest-blanks

### card 61 — Thermal Timeline  (diesel-generator-asset-dashboard/engine-cooling)   [ai_r_d06f6da969.jsonl:42]

system-prompt chars: v1=53482  v2=43554  (-19%)

| metric | v1 (live) | v2 (variant) |
|---|---|---|
| parse_ok | True | True |
| conforms | True | True |
| answerability | partial | none |
| fields emitted | 11 | 0 |
| slots omitted | 0 | 11 |
| roster entries | 0 | 0 |
| endpoint | energy-power-history | energy-power-history |
| bad slots (not in list) | 0 | 0 |
| bad columns (not in basket) | 0 | 0 |
| gate issues | 0 | 0 |
| gate-blanked leaves | 2 | 0 |
| roster issues | 0 | 0 |
| metadata byte-issues | 1 | 1 |
| tokens in/out | 20014/2729 | 17590/2157 |
| latency s | 18.6 | 14.7 |
- v1 data_note: Temperature columns (coolant, oil, intake, exhaust) are not measured by this DG meter; the card displays its structural metadata and narrative summary while temperature series honest-blank.
- v2 data_note: This card requires temperature columns (coolant, oil, intake, exhaust) which are not measured by this electrical meter asset; all temperature slots are honestly blank.
- v1 blanked: chart.band.y1: const 95 has no real DB source (not a nameplate rating slot/metric, no matching app_config consts.* row) — a literal in a data slot must come from asset_nameplate or app_config; leaf honest-blanks
- v1 blanked: chart.band.y2: const 104 has no real DB source (not a nameplate rating slot/metric, no matching app_config consts.* row) — a literal in a data slot must come from asset_nameplate or app_config; leaf honest-blanks

### card 17 — Daily Power Demand by Feeder  (panel-overview-shell/energy-power)   [ai_r_99879f110d.jsonl:33]

system-prompt chars: v1=53482  v2=43554  (-19%)

| metric | v1 (live) | v2 (variant) |
|---|---|---|
| parse_ok | True | True |
| conforms | True | True |
| answerability | full | full |
| fields emitted | 0 | 0 |
| slots omitted | 34 | 34 |
| roster entries | 2 | 7 |
| endpoint | demand-profile | demand-profile |
| bad slots (not in list) | 0 | 0 |
| bad columns (not in basket) | 0 | 0 |
| gate issues | 0 | 0 |
| gate-blanked leaves | 0 | 0 |
| roster issues | 3 | 11 |
| metadata byte-issues | 2 | 2 |
| tokens in/out | 23382/2307 | 20958/2602 |
| latency s | 16.1 | 17.8 |

### card 9 — Total Feeder Consumption / Supply  (panel-overview-shell/real-time-monitoring)   [ai_r_ab957fb3ac.jsonl:25]

system-prompt chars: v1=53482  v2=43554  (-19%)

| metric | v1 (live) | v2 (variant) |
|---|---|---|
| parse_ok | True | True |
| conforms | True | True |
| answerability | full | full |
| fields emitted | 0 | 0 |
| slots omitted | 7 | 7 |
| roster entries | 2 | 2 |
| endpoint | None | real-time-monitoring |
| bad slots (not in list) | 0 | 0 |
| bad columns (not in basket) | 0 | 0 |
| gate issues | 0 | 0 |
| gate-blanked leaves | 0 | 0 |
| roster issues | 0 | 0 |
| metadata byte-issues | 1 | 1 |
| tokens in/out | 19888/874 | 17464/1114 |
| latency s | 6.4 | 7.9 |

### card 23 — PQ Issues KPI Strip (Total Issues / I-THD Events / V-THD Events / PF Gap Feeders / Neutral Stress / Worst I-THD / Worst V-THD)  (panel-overview-shell/harmonics-pq)   [ai_r_99879f110d.jsonl:38]

system-prompt chars: v1=53482  v2=43554  (-19%)

| metric | v1 (live) | v2 (variant) |
|---|---|---|
| parse_ok | True | True |
| conforms | True | True |
| answerability | full | full |
| fields emitted | 0 | 0 |
| slots omitted | 48 | 48 |
| roster entries | 1 | 1 |
| endpoint | None | None |
| bad slots (not in list) | 0 | 0 |
| bad columns (not in basket) | 0 | 0 |
| gate issues | 0 | 0 |
| gate-blanked leaves | 0 | 0 |
| roster issues | 0 | 0 |
| metadata byte-issues | 2 | 2 |
| tokens in/out | 24442/2875 | 22018/2835 |
| latency s | 20.0 | 19.4 |

### card 48 — Distortion & Harmonic Profile  (individual-feeder-meter-shell/power-quality)   [ai_r_a77b8e4dd2.jsonl:7]

system-prompt chars: v1=53482  v2=43554  (-19%)

| metric | v1 (live) | v2 (variant) |
|---|---|---|
| parse_ok | True | True |
| conforms | True | True |
| answerability | partial | partial |
| fields emitted | 7 | 7 |
| slots omitted | 21 | 21 |
| roster entries | 0 | 0 |
| endpoint | power-quality-summary | power-quality-summary |
| bad slots (not in list) | 0 | 0 |
| bad columns (not in basket) | 0 | 0 |
| gate issues | 0 | 0 |
| gate-blanked leaves | 0 | 0 |
| roster issues | 0 | 0 |
| metadata byte-issues | 3 | 3 |
| tokens in/out | 22307/2698 | 19883/2829 |
| latency s | 18.6 | 19.2 |
- v1 data_note: Showing current THD (I-THD) and voltage THD (V-THD) trends. Voltage THD columns (thd_voltage_*) have data=N on this meter, so V-THD series will be empty/honored-blank; I-THD series are fully populated from live current THD measurements.
- v2 data_note: Showing current THD (I-THD) and voltage THD (V-THD) trends. Voltage THD columns (thd_voltage_*) are mostly null on this meter; current THD columns (thd_current_*) are the primary available harmonic data.

### card 54 — Transfer readiness  (ups-asset-dashboard/source-transfer)   [ai_r_d7be9457fc.jsonl:4]

system-prompt chars: v1=53482  v2=43554  (-19%)

| metric | v1 (live) | v2 (variant) |
|---|---|---|
| parse_ok | True | True |
| conforms | True | True |
| answerability | none | none |
| fields emitted | 0 | 0 |
| slots omitted | 7 | 7 |
| roster entries | 0 | 0 |
| endpoint | real-time-monitoring | real-time-monitoring |
| bad slots (not in list) | 0 | 0 |
| bad columns (not in basket) | 0 | 0 |
| gate issues | 0 | 0 |
| gate-blanked leaves | 0 | 0 |
| roster issues | 0 | 0 |
| metadata byte-issues | 0 | 0 |
| tokens in/out | 19138/877 | 16714/888 |
| latency s | 6.4 | 6.3 |
- v1 data_note: Transfer readiness scores (composite, input, bypass, sync) are not measured by this meter; no columns or recovery functions exist for these quantities.
- v2 data_note: This meter class (UPS) does not measure transfer readiness scores, permissive scores, or bypass voltages; the card's core 'readiness' metric cannot be computed from available electrical columns.

### card 46 — Current History  (individual-feeder-meter-shell/voltage-current)   [ai_r_92a2bfb0ae.jsonl:238]

system-prompt chars: v1=54303  v2=42227  (-23%)

| metric | v1 (live) | v2 (variant) |
|---|---|---|
| parse_ok | True | True |
| conforms | True | True |
| answerability | full | full |
| fields emitted | 17 | 15 |
| slots omitted | 0 | 2 |
| roster entries | 4 | 4 |
| endpoint | current-history | current-history |
| bad slots (not in list) | 0 | 0 |
| bad columns (not in basket) | 0 | 0 |
| gate issues | 0 | 0 |
| gate-blanked leaves | 2 | 0 |
| roster issues | 4 | 4 |
| metadata byte-issues | 1 | 1 |
| tokens in/out | 20151/2956 | 17217/2734 |
| latency s | 20.1 | 18.4 |
- v1 blanked: history.data.expectedMax: const 100.0 has no real DB source (not a nameplate rating slot/metric, no matching app_config consts.* row) — a literal in a data slot must come from asset_nameplate or app_config; leaf honest-blanks
- v1 blanked: history.data.expectedMin: const 0.0 has no real DB source (not a nameplate rating slot/metric, no matching app_config consts.* row) — a literal in a data slot must come from asset_nameplate or app_config; leaf honest-blanks
