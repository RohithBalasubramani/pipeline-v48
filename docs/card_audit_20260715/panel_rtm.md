# Card audit — panel-overview-shell/real-time-monitoring (PCC-Panel-1)

- Page key: `panel-overview-shell/real-time-monitoring`
- Binding asset: PCC-Panel-1 (mfm 317), declared table `pcc_panel_1_feedbacks`
- Cards: 7, 5, 160, 6, 8, 9, 10, 11 (8 cards)

## Topology reality check
`pcc_panel_1_feedbacks` is a **breaker-status / winding-temperature** table (bc_acb_*, tf_*_winding_temperature, tf_inc_* relays) — it carries **no power columns and no rating columns**. All power/voltage/current numbers on this page come from the **panel-aggregate resolver folding member meters** (`gic_*_p1` / `gic_15_*_se`), not from the declared table. The aggregate path works: cards 7/9/10/11 fill real rolled values (supply 2934.3 kW = GIC-01 846.3 + GIC-02 2088.0; V 239.2; Iunbal 7.89 %; load 1901 A).

`reporting: 6 / expected: 8` on every card = 6 of the 8 PRIMARY load members report; UPS-05 and UPS-06 meters are empty.

## Member data probes (last 7 days, active_power_total_kw)
| feeder | table | rows | verdict input |
|---|---|---|---|
| UPS-01/02/03/04, BPDB-01/02 | gic_0*_p1 | live | FILL (already rendered) |
| Solar Incomer-1 | gic_01_n9_solar_incomer_1_p1 | **0 (0 all-time)** | dead meter |
| Solar Incomer-2 | gic_02_n1_solar_incomer_2_p1 | **0** | dead meter |
| UPS-05 | gic_02_n6_ups_05_cl_600kva_p1 | **0 (0 all-time)** | dead meter |
| UPS-06 | gic_02_n7_ups_06_cl_600kva_p1 | **0** | dead meter |
| PCC-01 Transformer-01 | gic_15_n3_pcc_01_transformer_01_se | 49021 | HT incomer, has data |
| PCC-01 Transformer-02 | gic_15_n4_pcc_01_transformer_02_se | 48880 | HT incomer, has data |

Transformer sample: active_power_total_kw = -724.5 (reverse-CT incomer), voltage_avg = **6523.7** (11 kV / √3, HT side), current_avg = **NULL**, apparent = 727.5.

---

## CARD 7 — Context Rail Header
- `railVM.trend.areaOpacity` (ref 0.15, v48 null) → **chrome_noise** (fill opacity styling). fix=chrome
- `railVM.supply.breakdown[2].value` (ref 141.2 "HHF Reactive") → **honest_absent**. V48 sections the live roster by GIC prefix and fills 2 real groups (GIC-01, GIC-02); the demo's 3rd functional group ("HHF Reactive", a kvar APFC bank, role≠load) has no 3rd live section. fix=panel_roster_shape
- `railVM.supply.denominator` (ref 2700, v48 "—") → **honest_absent**. No contracted_kw/rated_kw nameplate exists for this panel (table has zero rating columns). fix=nameplate_rating_absent
- `railVM.supply.consumedHint.leftKw` (ref 1130.6) → **derivation_gap** (honest): = denominator − value, denominator absent. fix=nameplate_rating_absent
- `railVM.supply.consumedHint.consumedPct` (ref 58.1) → **derivation_gap** (honest): needs rating. fix=nameplate_rating_absent
- `railVM.aiSummaryText` (ref narrative) → **derivation_gap** (fixable): sibling card 8 generates a real AI summary this run; the rail's own summary slot is simply not wired to reuse it. fix=ai_summary_narrative

## CARD 5 — Real Time Monitoring (Feeder Heatmap)
ONE card_note (grid; not enumerated). The gaps.json 1753-cell count is a stale/inflated extraction; the live render is a **1-sample × 12-feeder** snapshot = 96 metric cells, **42 filled**. Verdict: **predominantly a smaller-live-grid-vs-demo-grid difference plus honest per-member absence — NOT a systemic frame-blank bug.** The `di.element` already binds real live columns (`active_power_total_kw`, `voltage_avg`, `current_avg`, `current_unbalance_pct`, `kpi_true_pf`, …) and those bindings FILL correctly for 6 of 12 feeders (UPS-01/02/03/04, BPDB-01/02). Of the 6 blank feeders: **4 are honest_absent** — Solar Incomer-1/2 and UPS-05/06 member tables have **0 rows (empty all-time)**. **2 are HT-incomer edge cases** — PCC-01 Transformer-01/02 (`gic_15_*_se`) DO carry live active_power/kva/pf, but read the **11 kV side** (voltage_avg ≈ 6524 V, current_avg NULL, active_power reverse-signed −724 kW); binding them into an LV feeder heatmap would show HT-scale voltage and null current, so blanking is defensible for voltage/current though kw/kva/pf are technically bindable (a narrow frame_declared_bindable if the incomers row is wanted). Net: honest.

## CARD 160 — Heatmap Footer (Time Axis & Shade Legend)
No data-leaf gaps. Reference default is `null`; v48 is a scrubber-control payload (history [], liveMode true). Chrome/control card. No gap.

## CARD 6 — Live Scrubber / Step Control
No data-leaf gaps. Reference default `null`; v48 is live-mode scrubber control (history []). Chrome/control. No gap.

## CARD 8 — AI Summary
No gap. Reference default `null`; v48 FILLS a real AI summary ("1755.0 kW from feeder GIC-02-N5-UPS-04 … PF 0.993 … 6 of 8 members active"). Better than reference.

## CARD 9 — Total Feeder Consumption / Supply
- `supply.breakdown[2].value` (ref 141.2) → **honest_absent** panel_roster_shape (same as card 7 — 2 live sections, no 3rd)
- `supply.denominator` (ref 2700) → **honest_absent** nameplate_rating_absent
- `supply.consumedHint.leftKw` (ref 1130.6) → **derivation_gap** honest, nameplate_rating_absent
- `supply.consumedHint.consumedPct` (ref 58.1) → **derivation_gap** honest, nameplate_rating_absent

(supply.value + breakdown[0]/[1] fill real aggregated kW — no gap.)

## CARD 10 — Consumption Trend / Supply Trend
- `trend.areaOpacity` (ref 0.15) → **chrome_noise** (fill opacity). fix=chrome
- (trend.series is filled — 2 hourly buckets vs demo's 12; a windowing/sampling shape diff, value present, not a blank leaf.)

## CARD 11 — Quick Stats
No gap. All 3 stats fill real aggregated values (V 239.2, Iunbal 7.89 %, load 1901 A). Reference shows demo LV-bus "420"/"9.0"/"2,415"; v48 shows real member-rolled numbers.

---

## Fix-family clusters
- **nameplate_rating_absent** (denominator + consumedHint on cards 7, 9): no rating anywhere for PCC-Panel-1 → all honest. The single systemic driver of the "supply %" blanks.
- **panel_roster_shape** (breakdown[2] on cards 7, 9): live roster sections by GIC prefix (2 groups) vs demo's functional 3-group split → honest.
- **ai_summary_narrative** (card 7 rail): only genuinely fixable item — wire the rail's `aiSummaryText` to the already-generated card-8 summary.
- **member_meter_absent** (card 5 heatmap: Solar Incomer-1/2, UPS-05/06): empty member tables → honest.
- **ht_incomer_cross_scale** (card 5 heatmap: Transformer-01/02): live but 11 kV HT meter → honest for voltage/current, marginally bindable for kw/kva/pf.
- **chrome** (areaOpacity cards 7, 10): pure styling.
