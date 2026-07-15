# Card audit — panel-overview-shell/harmonics-pq

Page asset table: `pcc_panel_1_feedbacks` (PCC-Panel-1, mfm_id 317).
This is a **panel-aggregate** page (resolver_scope=panel, roster scope=members). The
asset table itself is a breaker/feedback status table (`bc_*`, `tf_*` bits, no PQ
columns) — all PQ data flows from the member `gic_*_p1` meters. The pre-extracted
`gaps.json` auto-classed everything `HONEST_ABSENT_no_column` because it probed the
**panel** table, which is the wrong probe target for an aggregate page. Probing the
real members changes the picture.

## Ground truth (member `gic_*_p1` meters)

Probed `gic_01_n3_ups_01_p1`, `gic_01_n4_ups_02_p1`, `gic_01_n5_ups_03_p1`,
`gic_01_n8_bpdb_01_p1`, `gic_02_n2_bpdb_02_p1`, `gic_02_n5_ups_04_cl_600kva_p1`
(the 6 members V48 actually rendered) over last 7 days:

| column | populated? |
|---|---|
| thd_current_r/y/b_pct | YES (24k–70k rows) |
| kpi_true_pf, power_factor_total | YES |
| pf_gap_vs_full_load | YES |
| current_neutral | YES |
| active_power_total_kw | YES |
| neutral_stress_event_active | YES |
| **thd_voltage_r/y/b_pct** | **ALL NULL (0)** on every member |
| **harmonic_5th_pct** | column exists, **ALL NULL (0)** on every member |
| **harmonic_7th_pct** | column exists, **ALL NULL (0)** on every member |
| harmonic_3rd / peak-thd / k-factor | **no such column** |

So these meters log **current** THD + PF + neutral, but **do not log voltage THD or
individual harmonic magnitudes**. That is a genuine hardware/logging gap, not a wiring
bug.

## What V48 actually renders (not blank!)

V48 correctly fills the member-scoped leaves from real data. E.g. card 26 / 27 panels:
`kw`, `pf`/`truePf`, `iThd` (phase-mean of thd_current_*), `pfGap`, `neutralA`,
`status`, `id`, `panel`, `table` are all populated with live member values
(ups-01 kw=174.9 iThd=9.17 pf=0.992 …). Card 25 AI-summary text is fully grounded
("worst feeder GIC-01-N3-UPS-01 recorded current THD of 6.8% against 8.0% limit").
Card 23 KPI counts filled (total=5, iThd=4, pfGap=0, neutral=1, worstIThd=ups-04).

The `gaps.json` records for the data-bearing leaves (`kw`, `iThd`, `pf`, `id`, `panel`
…) fire only on **panels[6..9]** — because the EMS reference demo grid has **10**
hard-coded demo feeders (ups-01..06, bpdb-01/02, hhf-01/02 / MFM_0nn) while V48 renders
the **6 real live members**. Those are grid-shape false positives, not data gaps.

## Verdict summary by distinct leaf-type (shared across cards 23/25/26/27)

| leaf | natural column | verdict | reason |
|---|---|---|---|
| vThd | thd_voltage_r/y/b_pct | honest_absent | column present, all-null on every member |
| h3 | (none) | honest_absent | no 3rd-harmonic column |
| h5 | harmonic_5th_pct | honest_absent | column present, all-null |
| h7 | harmonic_7th_pct | honest_absent | column present, all-null |
| iThdPk | (none) | honest_absent | no peak-THD column |
| kFactor | (none) | honest_absent | no k-factor column |
| driver / driverKey | derived label | honest_absent (derivation) | "5th-harmonic" driver needs h5, which is all-null |
| worst / worstVThd (argmax vThd) | thd_voltage | honest_absent | argmax over all-null vThd → empty |
| iThd / pf / truePf / pfGap / kw / neutralA / id / panel / table / status | thd_current_*/kpi_true_pf/… | FILLED (not a gap) | real member data; gap records are grid-shape on panels[6..9] |
| table (`MFM_0nn` in ref) | — | chrome_noise | V48 fills real `gic_*` table name; ref uses demo meter-id label |

### Card 23 — PQ Issues KPI Strip
- `strip.stats.vThd` → honest_absent (thd_voltage all-null → no breach count possible).
- `strip.stats.worst.*`, `strip.stats.worstVThd.*` → honest_absent, consequent to vThd
  absence (argmax winner is empty). `worstIThd.*` IS filled.
- Absent sub-leaves h3/h5/h7/iThdPk/kFactor/vThd/driver/driverKey → honest_absent.
- `strip.pres.tiles[].pct` → chrome_noise (tile fill %, presentation).
- `strip.filterSelection.rangeStart/End/customDate` → chrome_noise (date-picker state).

### Card 24 — Harmonics & PQ Timeline (GRID, one note)
GRID card. V48 renders 1 period × 6 real members; EMS demo is (many hourly periods) ×
10 demo feeders → the 1,239 cell "gaps" are **grid-shape** (smaller live grid vs demo
grid) plus the same per-panel absent leaves (vThd/h5/h7/h3/iThdPk/kFactor/driver). The
data-bearing per-panel leaves (iThd/pf/kw/neutralA…) ARE filled for the 6 live members.
Separately, `timeline.limits.{iThdLimit,vThdLimit,truePfFloor,truePfTarget,neutralLimitA}`
are all null — these are **statutory PQ threshold constants** (IEEE-519 8%/5% etc), not
meter data. The di declares them honest-blanked "relies on executor default" but the
executor never fills them → **binding_gap / threshold_canonical_fill**: same deterministic
canonical-slot mechanism as the voltage-band fix should populate them.

### Card 25 — AI Summary (narrative/text)
Narrative text (`ai_summary.text`, `summary.pres.backendHeadline`) is fully grounded in
real member data — **not a gap**. `_zero_skeleton=true`: the decorative `summary.stats.*`
and `summary.selectedPanel.*` chips are unbound_by_emit. Data-bearing ones
(iThd/pfGap/total/neutral/kw/pf/truePf/neutralA) are technically bindable →
binding_gap, but LOW priority (card renders via text, not the stat chips). Absent ones
(vThd/h5/h7/h3/iThdPk/kFactor/driver) → honest_absent.

### Card 26 — Feeder PQ At Today (table)
6 real member rows fully filled (id/panel/table/kw/pf/iThd/pfGap/truePf/neutralA/status).
Blank per-row: vThd/h3/h5/h7/iThdPk/kFactor/driver/driverKey → honest_absent (see table).
`table.pres.pfDecimalThreshold`, `table.selectedPanelId` → chrome_noise.
Rows panels[6..9] entirely absent = grid-shape (only 6 live members vs 10 demo).

### Card 27 — Signature (radar)
Same as card 26: 6 members filled (iThd/pf/truePf/pfGap/neutralA), vThd/h5/h7/h3/iThdPk/
kFactor/driver → honest_absent. `signature.pres.style.*`, `signature.pres.palette.*`,
`signature.pres.rail.fallbackCount`, `signature.selectedPanelId` → chrome_noise.

## Bottom line
Zero fabrication candidates. The ONLY fixable, non-chrome gap on this page is
**card 24 `timeline.limits.*`** (5 statutory PQ threshold constants that should be
canonical-filled deterministically, mirroring the voltage-band canonical_slots fix).
Everything else is either (a) honest_absent — voltage-THD & individual harmonics are
not logged on any member meter, or (b) grid-shape — V48 shows 6 real members where the
EMS demo hard-codes 10, or (c) presentation chrome.

fix_families:
- `thd_voltage_absent` — vThd + its argmax consequents (honest)
- `harmonic_col_nulled` — h5/h7 columns exist but all-null (honest)
- `harmonic_3rd_absent` / `peak_thd_absent` / `kfactor_absent` — no column (honest)
- `driver_label_absent` — derived diagnosis needs absent h5 (honest)
- `threshold_canonical_fill` — card 24 timeline.limits.* (FIXABLE, canonical constants)
- `grid_shape` — 6 live members vs 10 demo feeders (not a gap)
- `narrative_stat_unbound` — card 25 decorative stat chips (low-pri bindable)
- `chrome_presentation` — tiles.pct, filterSelection, pres.style/palette, selectedPanelId
