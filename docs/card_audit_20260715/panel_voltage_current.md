# Card audit — panel-overview-shell/voltage-current

- Page key: `panel-overview-shell/voltage-current`
- Binding asset/table: `PCC-Panel-1` / `pcc_panel_1_feedbacks` (mfm_id 317)
- Cards: 18 Events KPI Strip, 19 AI Summary, 20 Event Timeline, 21 Current Distribution, 22 Other Panels Event
- 212 candidate gap records, all auto-classed `HONEST_ABSENT_no_column`.

## What this page actually is

Every card here is a **panel-aggregate roster** card: it fans out over the sibling
members of PCC-Panel-1 and shows per-member PQ/event stats
(`sag/swell/current/neutral` event counts, `amps/vAvg/vMax/vMin/neutralA/iUnbalance/vDeviation`).

The CMD_V2 **reference roster is a 10-panel demo set** with fabricated identities
(`UPS-01..06`, `BPDB-01/02`, `HHF-01/02`) keyed to fake tables `MFM_023..061`.
V48 renders the **real live member roster** discovered from the registry:

| card | live members (V48) | notes |
|---|---|---|
| 20 Event Timeline | 6 real | full real data incl. event counts |
| 22 Other Panels Event | 6 real | full real data incl. event counts |
| 21 Current Distribution | 8 real | current-only radar; 2 members empty tables |
| 19 AI Summary | 10 zero-skeleton | `_zero_skeleton=true`, no fan-out |

So the overwhelming majority of the 212 "gaps" are **index-aligned comparisons of a
10-slot demo roster against a smaller live roster** — the demo panels
`panels[6..9]` (BPDB/HHF under `MFM_0xx`) are simply **not real members** of this panel.
This is a roster-shape difference, not a data gap.

## Meter probing (live, port 5433)

Member tables DO carry the event + PQ columns (contrary to card 22's `_honest_blanked`
note "sag_event_active is not a scalar column"):

```
gic_01_n3_ups_01_p1 (UPS, 7d): rows 24908  sag 0  swell 0  curimb 0  neu 0  vavg 234.7  iunb 3.63  neutralA 15.7
gic_01_n8_bpdb_01_p1 (30d):    curimb_sum 55875  neu_sum 42852  vavg 234.4  iunb 12.97  neutralA 90.3  vdev -2.34
gic_02_n2_bpdb_02_p1 (30d):    curimb_sum 79146  neu_sum 72480  vavg 235.2  iunb 24.70  neutralA 166.1  vdev -1.98
```

- Event columns `sag_event_active / swell_event_active / current_imbalance_event_active /
  neutral_stress_event_active` exist (type `real`, 0/1 flags) and carry **non-zero data on
  the BPDB members**. Cards 20/22 correctly compute rising-edge counts:
  BPDB-01 `current=407 neutral=401`, BPDB-02 `current=772 neutral=1000`. UPS members are
  genuinely event-free (`current=0 neutral=0`), `sag/swell` are 0 across all members.
- `voltage_avg / current_unbalance_pct / current_neutral / kpi_voltage_deviation_pct`
  all populated → cards 20/22 fill `vAvg/vMax/vMin/iUnbalance/neutralA/vDeviation` with real values.
- **`gic_02_n6_ups_05_cl_600kva_p1` and `gic_02_n7_ups_06_cl_600kva_p1` have 0 rows (empty
  tables, no data ever).** Card 21 includes them (registry members) and honestly yields
  `amps=None / current=None`.

## Per-card verdicts

### Card 18 — Events KPI Strip
Gaps are all **UI filter/selection chrome**: `.strip.timeChoice` (`18:00`),
`.strip.filterSelection.{rangeStart,rangeEnd,customDate}` (dates). No measurement leaves.
Verdict: **chrome_noise** (`selection_chrome`). V48 correct.

### Card 19 — AI Summary
`_zero_skeleton=true`: emits a 10-panel skeleton with demo names, all metrics 0.0, `table=''`,
and leaves all `summary.stats.*` null. It does **not** run the member fan-out that cards 20/22 run.

- `summary.stats.{sag,swell,total,current,neutral}`, `worstCurrent.*`, `worstVoltage.*`,
  `selectedPanel.*` numeric leaves → **derivation_gap** (`panel_aggregate_summary_stats`).
  The inputs exist on the real members (proven by cards 20/22); these are argmax/sum
  reductions the card could compute but doesn't. `sag/swell` would resolve to 0,
  `current/neutral` non-zero on BPDB.
- `worst*/selectedPanel.{id,table}` and `summary.period.panels[*].table` (`MFM_025..035`)
  → **honest_absent** (`roster_shape`): demo identities; real roster members differ.

### Card 20 — Event Timeline
V48 fills its **6 real members fully** (real `vAvg/amps/iUnbalance/neutralA/vDeviation`
and event counts incl. BPDB `current=407/772`, `neutral=401/1000`). The only gap records are
`.trend.period.panels[6..9].*` = demo BPDB/HHF slots (`MFM_023/061/024/032`) that are **not
live members**. Verdict: **honest_absent** (`roster_shape`). Not a data gap.

### Card 21 — Current Distribution (radar)
Current-only radar (`fetch.metrics=["current"]`). Fills `amps/current` for its 8 real members.
- `panels[6].amps/current`, `panels[7].amps/current` → **honest_absent**
  (`empty_member_table`): at those slots V48's members are `ups-05`/`ups-06`, whose meter
  tables have **0 rows**.
- `panels[8..9].*` → **honest_absent** (`roster_shape`): HHF demo panels, not live members.
- `panels[0..7].table` = `''` → **binding_gap** (`roster_identifier`), low priority: cards
  20/22 fill the per-node meter-table name; the radar leaves it blank (not rendered by the radar).
- `pres.radar.selectedColor`, `selectedPanelId` → **chrome_noise** (color/selection state).
- Per-node `vAvg/vMax/vMin/sag/swell/neutral*` = 0.0 → by design (radar consumes current only),
  not flagged for real members.

### Card 22 — Other Panels Event (table)
Identical to card 20: **6 real members fully filled** with real PQ + event data. Gap records
`.table.period.panels[6..9].*` are demo BPDB/HHF slots. Verdict: **honest_absent**
(`roster_shape`).

## Bottom line

No fabricated data is warranted anywhere on this page. The real fixable items:

1. **Card 19 AI Summary** emits a zero-skeleton instead of running the member fan-out that
   cards 20/22 already run — `summary.stats.*` (sag/swell/total, worstCurrent, worstVoltage,
   selectedPanel) are derivable from live members. `fix_family=panel_aggregate_summary_stats`.
2. **Card 21** could populate `panels[*].table` node identifiers (`fix_family=roster_identifier`,
   cosmetic).

Everything else (`panels[6..9]` across cards 20/21/22, all `MFM_0xx` tables, demo ids) is a
**demo-roster-vs-live-roster shape difference** (`roster_shape`) or empty upstream member
tables (`empty_member_table`) — V48 is honest. Card 18 leaves are pure selection chrome.
