# Card audit — panel-overview-shell/energy-distribution (PCC-Panel-1)

Meter binding table: `pcc_panel_1_feedbacks` (panel-aggregate page; real values come from
per-member GIC meter tables, not this table).

Cards on page: **12 Energy Input & Distribution** (sankey table), **13 Energy Flow Diagram** (sankey + loss/efficiency KPIs).

The `gaps.json` harness auto-classed all 123 records `HONEST_ABSENT_no_column`, but that is because
the CMD_V2 **reference** is a *demo* topology (`meter-hhf-01`, `ups-01`, `solar-incomer-2`,
`curveSag`, `layer:3` …) that has no correspondence to V48's real member topology. The leaf-by-leaf
sankey node/link "gaps" are demo-grid-vs-real-grid shape differences, NOT data gaps. The real signal is
the **supply/incomer side is entirely null while the load side is filled**, which cascades into the
loss / efficiency / source-input KPIs.

## Meter probes (last 7 days, `timestamp_utc::timestamptz > now()-interval '7 days'`)

| Member (role) | table | rows total | kw/kwh in 7d | verdict |
|---|---|---|---|---|
| Solar Incomer-1 (source) | `gic_01_n9_solar_incomer_1_p1` | 0 | 0 | empty table |
| Solar Incomer-2 (source) | `gic_02_n1_solar_incomer_2_p1` | 0 | 0 | empty table |
| PCC-01 Transformer-01 (source) | `gic_15_n10_*` | — | — | **no table exists** |
| PCC-01 Transformer-02 (source) | `gic_15_n11_*` | — | — | **no table exists** |
| UPS-05 (load) | `gic_02_n6_ups_05_cl_600kva_p1` | 0 | 0 | empty table |
| UPS-06 (load) | `gic_02_n7_ups_06_cl_600kva_p1` | 0 | 0 | empty table |
| UPS-01 (load) | `gic_01_n3_ups_01_p1` | 91 708 | 24 908 | has data (V48 filled 3669) |

Conclusion: every null on this page traces to a member table that is **empty or missing**. There is no
`source="frame"` declared-metric slot here (the roster binds real columns), so there is **no
`frame_declared_bindable` rescue** available.

## Card 12 — Energy Input & Distribution

Load side is fully wired and real (UPS-01/02/03, BPDB-01/02, UPS-04; panel node = 169 428). Blanks:

- `.kpi.value` = `"active_power_total_kw"` (raw metricId leaked as a string), `.kpi.pf` = null —
  reference itself is `None` for both. The KPI is "Total **Input** Power"; the input (incomer) meters
  are all empty/missing → **honest_absent**. Separate minor render defect: the unresolved metricId
  *string* is leaked into the value slot instead of `—`.
- `.rail.vm.sankey.nodes[incomers].value` + incomer `.links[].value` (4 sources) — **honest_absent**,
  incomer meters empty/missing.
- `.rail.vm.sankey` UPS-05 / UPS-06 node+link `value` — **honest_absent**, member tables empty.
- `.rail.vm.legend[].items[].color` = null — **chrome_noise**.

## Card 13 — Energy Flow Diagram

Consumer (load) groups filled: `feederOutputKw` = 3109.6 = exact sum of the 6 live consumer kW
(187.6+182+183+246+438+1873). But:

- **`.flow.vm.kpis.feederOutputKwh` = "—" — FIXABLE `derivation_gap`.** Every consumer `totalKwh`
  exists (3669+3679+3680+58600+62950+36850 = **169 428**, also rendered as the panel sankey node), and
  the sibling `feederOutputKw` slot was computed from the same consumers. The kWh rollup slot was
  simply not filled. fix_family = `panel_aggregate_kwh_rollup_missing`.
- `.flow.vm.allTotalKw` / `.flow.vm.allTotalKwh` = "—" — `derivation_gap`; the consumer subtotal
  exists (same rollup engine that filled `feederOutputKw`). Partly bounded by absent sources, but the
  consumer portion is derivable. fix_family = `panel_aggregate_rollup_missing`.
- `.flow.vm.kpis.sourceInputKwh` / `.sourceInputKw` = "—"/null — `derivation_gap`, **inputs absent**
  (all 4 incomer meters empty/missing) → honest. fix_family = `source_input_meters_absent`.
- `.flow.vm.kpis.lossKwh` / `.lossPct` / `.efficiencyPct` / `.lossKw` = "—"/null — `derivation_gap`,
  needs sourceInput which is absent → honest. fix_family = `loss_needs_source_input`.
- `.flow.vm.totalSuppliedKw` / `.totalSuppliedKwh` = "—" — supplied = source side = absent →
  **honest_absent**. fix_family = `source_input_meters_absent`.
- `.flow.vm.allUtilizationPct` and every `utilizationPct` (sources/consumers/meters) = "—" —
  **honest_absent**; DI explicitly declares `utilizationPct: null` ("no per-feeder rated capacity on
  gic_*"). fix_family = `loadfactor_rating_nulled`.
- `.flow.vm.sources[].*` (totals + meters) = "—" — **honest_absent**, incomer meters empty/missing.
- `.flow.vm.consumers[UPS-05, UPS-06].*` = "—" — **honest_absent**, member tables empty.
- `.flow.vm.aiSummary` = "" — narrative depends on loss%/efficiency which are absent → **honest_absent**
  (nothing to summarize). fix_family = `narrative_needs_derivation`.
- `.flow.vm.sankey.nodes[]/.links[]` demo leaves (`curveSag`, `layer`, `meter-hhf-01`/`ups-01` ids,
  `selectedNodeId`) — **chrome_noise / grid_shape**: reference demo topology, not a real data gap.

## Summary
- 1 genuinely fixable leaf: `card 13 .flow.vm.kpis.feederOutputKwh` (consumer kWh rollup exists but not
  filled, while the kW sibling is filled). Possibly extends to `allTotalKw/Kwh`.
- Everything else is **honest**: the incomer/source side has no meters in this deployment (empty
  Solar-Incomer tables + non-existent PCC transformer meters), UPS-05/06 are empty, and utilization is
  rating-nulled by design. No frame-declared rescue exists on this page.
