# prompt A/B — v1 (live emit prompt) vs v2 (data_instructions_v2.md variant)

generated: 2026-07-06 22:13:57   url: http://localhost:8200/v1/chat/completions   calls: 8 cards x 2 arms

v2 is composed from layer2/prompts/data_instructions_v2.md with the SAME dynamic content extracted from
the logged v1 call (endpoint sets, per-card recovery library, roster presence); the user message and every
sampling knob are identical — the arms differ ONLY in system-prompt structure.

## aggregate

| metric | v1 | v2 |
|---|---|---|
| parse_ok | 8 | 8 |
| conforms=true | 8 | 8 |
| fields emitted | 34 | 21 |
| bad slots | 0 | 0 |
| bad columns | 0 | 0 |
| gate issues | 0 | 1 |
| gate-blanked leaves | 5 | 10 |
| honest answers (partial/none + data_note) | 4 | 5 |
| tokens in (sum) | 167266 | 138036 |
| tokens out (sum) | 16294 | 16105 |

### card 74 — Thermal Life  (transformer-asset-dashboard/thermal-life)   [ai_r_f3b19721cb.jsonl:6]

system-prompt chars: v1=53482  v2=38993  (-28%)

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
| tokens in/out | 17944/878 | 14354/499 |
| latency s | 6.4 | 3.7 |
- v1 data_note: Showing active power loss (kW) as a proxy for thermal stress; winding and oil temperatures are not measured by this meter.
- v2 data_note: No temperature, aging, or loss-of-life columns are measured by this asset's electrical meter schema; all thermal/aging slots are honestly blank.
- v1 blanked: thermalLife.metrics[2].value: lifetime not measured by this meter (no lifetime column) — column 'active_power_total_kw' measures power, not lifetime; leaf honest-blanks

### card 61 — Thermal Timeline  (diesel-generator-asset-dashboard/engine-cooling)   [ai_r_d06f6da969.jsonl:42]

system-prompt chars: v1=53482  v2=38993  (-28%)

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
| tokens in/out | 20014/2729 | 16424/2206 |
| latency s | 18.6 | 14.9 |
- v1 data_note: Temperature columns (coolant, oil, intake, exhaust) are not measured by this DG meter; the card displays its structural metadata and narrative summary while temperature series honest-blank.
- v2 data_note: No temperature columns (coolant, oil, intake, exhaust) are measured by this asset's meter; the card renders with empty data fields as it cannot display thermal trends.
- v1 blanked: chart.band.y1: const 95 has no real DB source (not a nameplate rating slot/metric, no matching app_config consts.* row) — a literal in a data slot must come from asset_nameplate or app_config; leaf honest-blanks
- v1 blanked: chart.band.y2: const 104 has no real DB source (not a nameplate rating slot/metric, no matching app_config consts.* row) — a literal in a data slot must come from asset_nameplate or app_config; leaf honest-blanks

### card 17 — Daily Power Demand by Feeder  (panel-overview-shell/energy-power)   [ai_r_99879f110d.jsonl:33]

system-prompt chars: v1=53482  v2=38993  (-28%)

| metric | v1 (live) | v2 (variant) |
|---|---|---|
| parse_ok | True | True |
| conforms | True | True |
| answerability | full | full |
| fields emitted | 0 | 0 |
| slots omitted | 34 | 34 |
| roster entries | 2 | 2 |
| endpoint | demand-profile | demand-profile |
| bad slots (not in list) | 0 | 0 |
| bad columns (not in basket) | 0 | 0 |
| gate issues | 0 | 0 |
| gate-blanked leaves | 0 | 0 |
| roster issues | 3 | 3 |
| metadata byte-issues | 2 | 2 |
| tokens in/out | 23382/2307 | 19792/2435 |
| latency s | 16.3 | 16.6 |

### card 9 — Total Feeder Consumption / Supply  (panel-overview-shell/real-time-monitoring)   [ai_r_ab957fb3ac.jsonl:25]

system-prompt chars: v1=53482  v2=38993  (-28%)

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
| tokens in/out | 19888/874 | 16298/1114 |
| latency s | 6.8 | 10.4 |

### card 23 — PQ Issues KPI Strip (Total Issues / I-THD Events / V-THD Events / PF Gap Feeders / Neutral Stress / Worst I-THD / Worst V-THD)  (panel-overview-shell/harmonics-pq)   [ai_r_99879f110d.jsonl:38]

system-prompt chars: v1=53482  v2=38993  (-28%)

| metric | v1 (live) | v2 (variant) |
|---|---|---|
| parse_ok | True | True |
| conforms | True | True |
| answerability | full | full |
| fields emitted | 0 | 0 |
| slots omitted | 48 | 48 |
| roster entries | 1 | 1 |
| endpoint | power-quality-summary | None |
| bad slots (not in list) | 0 | 0 |
| bad columns (not in basket) | 0 | 0 |
| gate issues | 0 | 0 |
| gate-blanked leaves | 0 | 0 |
| roster issues | 0 | 0 |
| metadata byte-issues | 2 | 2 |
| tokens in/out | 24442/3074 | 20852/2867 |
| latency s | 28.4 | 21.9 |

### card 48 — Distortion & Harmonic Profile  (individual-feeder-meter-shell/power-quality)   [ai_r_a77b8e4dd2.jsonl:7]

system-prompt chars: v1=53482  v2=38993  (-28%)

| metric | v1 (live) | v2 (variant) |
|---|---|---|
| parse_ok | True | True |
| conforms | True | True |
| answerability | partial | partial |
| fields emitted | 7 | 6 |
| slots omitted | 21 | 22 |
| roster entries | 0 | 0 |
| endpoint | power-quality-summary | power-quality-summary |
| bad slots (not in list) | 0 | 0 |
| bad columns (not in basket) | 0 | 0 |
| gate issues | 0 | 0 |
| gate-blanked leaves | 0 | 0 |
| roster issues | 0 | 0 |
| metadata byte-issues | 3 | 3 |
| tokens in/out | 22307/2690 | 18717/2751 |
| latency s | 22.0 | 24.1 |
- v1 data_note: Showing current THD (I-THD) and voltage THD (V-THD) trends. Voltage THD columns (thd_voltage_*) have data=N on this meter, so V-THD series will be empty; I-THD series are populated from real logged columns.
- v2 data_note: Showing current THD evolution (R/Y/B phases) — voltage THD data is not available for this asset, so V-THD series will render as empty/historical nulls.

### card 54 — Transfer readiness  (ups-asset-dashboard/source-transfer)   [ai_r_d7be9457fc.jsonl:4]

system-prompt chars: v1=53482  v2=38993  (-28%)

| metric | v1 (live) | v2 (variant) |
|---|---|---|
| parse_ok | True | True |
| conforms | True | True |
| answerability | none | partial |
| fields emitted | 0 | 0 |
| slots omitted | 7 | 7 |
| roster entries | 0 | 0 |
| endpoint | real-time-monitoring | real-time-monitoring |
| bad slots (not in list) | 0 | 0 |
| bad columns (not in basket) | 0 | 0 |
| gate issues | 0 | 1 |
| gate-blanked leaves | 0 | 0 |
| roster issues | 0 | 0 |
| metadata byte-issues | 0 | 0 |
| tokens in/out | 19138/895 | 15548/661 |
| latency s | 7.8 | 5.7 |
- v1 data_note: The card requires a composite transfer readiness score and permissive scores (input, bypass, sync), which are not measured by this asset's meter (no readiness/score columns exist in the DB schema). The card renders with honest blanks for all score fields.
- v2 data_note: Showing permissive status flags (Input/Bypass/Sync) as proxies for transfer readiness — the asset does not measure a composite 'readiness score' or 'permissive score' quantity.
- v2 gate: data_instructions.fields is empty

### card 46 — Current History  (individual-feeder-meter-shell/voltage-current)   [ai_r_92a2bfb0ae.jsonl:238]

system-prompt chars: v1=54303  v2=37666  (-31%)

| metric | v1 (live) | v2 (variant) |
|---|---|---|
| parse_ok | True | True |
| conforms | True | True |
| answerability | full | partial |
| fields emitted | 15 | 15 |
| slots omitted | 2 | 2 |
| roster entries | 4 | 4 |
| endpoint | current-history | current-history |
| bad slots (not in list) | 0 | 0 |
| bad columns (not in basket) | 0 | 0 |
| gate issues | 0 | 0 |
| gate-blanked leaves | 2 | 10 |
| roster issues | 4 | 4 |
| metadata byte-issues | 1 | 1 |
| tokens in/out | 20151/2847 | 16051/3572 |
| latency s | 21.6 | 25.8 |
- v2 data_note: Showing current history trends and statistics. Note: Nameplate ratings are unknown for this asset, so expected range lines are derived from historical peak/average statistics rather than rated capacity.
- v1 blanked: history.data.expectedMax: const 100.0 has no real DB source (not a nameplate rating slot/metric, no matching app_config consts.* row) — a literal in a data slot must come from asset_nameplate or app_config; leaf honest-blanks
- v1 blanked: history.data.expectedMin: const 0.0 has no real DB source (not a nameplate rating slot/metric, no matching app_config consts.* row) — a literal in a data slot must come from asset_nameplate or app_config; leaf honest-blanks
- v2 blanked: history.data.stats[0].value: current not measured by this meter (no current column) — fn 'worstPeakKw' measures power, not current; leaf honest-blanks
- v2 blanked: history.data.stats[1].value: current not measured by this meter (no current column) — fn 'loadFactorPct' measures load-factor, not current; leaf honest-blanks
- v2 blanked: history.data.maxY: current not measured by this meter (no current column) — fn 'worstPeakKw' measures power, not current; leaf honest-blanks
- v2 blanked: history.data.minY: current not measured by this meter (no current column) — fn 'loadFactorPct' measures load-factor, not current; leaf honest-blanks
