
## [feeder_vc] voltage and current for GIC-01-N3-UPS-01  — VERDICT_OK=TRUE
Asset resolved directly by AI: mfm_id=11 GIC-01-N3-UPS-01 CL:600KVA, table=gic_01_n3_ups_01_p1, class=UPS, has_data=true, 33 cols. No asset_pending. 4 cards.
Run flags all clean: asset_no_data/validation_blocked/data_unavailable=false, degrade=None, errors={}, frame_status={}.

| card | id | verdict | answ | leaf_stats (real/data/undecl) | payload_error | NaN |
|------|----|---------|------|-------------------------------|---------------|-----|
| Voltage Live Health | 43 | partial | partial | 11/15/2 | None | no |
| Voltage History     | 44 | partial | partial | 154/156/1 | None | no |
| Current Live Health | 45 | partial | partial | 8/11/2 | None | no |
| Current History     | 46 | partial | partial | 117/118/1 | None | no |

Every card partial/partial with real>0 → honest per contract (b): a card with some real neuract values is partial. contract (d) holds (no render w/o full, no honest_blank w/o none). NO all-honest_blank false-blank regression — the meter is live and cards render its real V/I.

fake_full[] = EMPTY (zero cards are render/full with real==0 — R2 bug absent).
crashes[]   = EMPTY (no NaN/Infinity/payload_error/exception).

CROSS-CHECK vs live neuract (target_version1.neuract.gic_01_n3_ups_01_p1, tunnel :5433):
- Latest row @ 2026-07-04T23:33 (current): v_r_n=235.9 v_y_n=234.8 v_b_n=238.2 v_avg=236.3 curr_avg=253.
- Card43 payload phases = 236.7/235.3/239.2, summary 237.07 → matches live window aggregate. REAL.
- Card45 payload phase currents = 240/232/249, sideValue 14.73 → matches live current_avg ~247-253. REAL.
- Honest degrades confirmed honest:
  * Card43 metrics[2] "ts not measured by this meter" = column_absent — table has NO `ts` col (has timestamp_utc, 72 cols). UNDECLARED-blank, honest, counts to undeclared=2.
  * denorm_garbage voltage domain leaf "sensor below valid range" — main V leaves real, one derived domain leaf blanks. honest.
  * Card44 voltageMax/Min + Card45 currentMax = derivation_unbound (no binding configured) → honest blank, NOT fabricated.

VERDICT_OK = TRUE. Zero fake_full, zero crashes, every card verdict honest.

## [dg_vc] 'dg voltage and current for DG-1' — VERDICT_OK=FALSE (fabricated-zero fake-partial)
- Prompt asset_pending → re-POST asset_id=2 (DG-1 MFM, class DG, has_data=True). Pinned OK, 4 cards (66,67,68,69), no payload_error, no NaN/Inf, all frame_status.ok, all validation pass.
- ALL FOUR cards reported verdict=partial / answerability=partial with real>0:
  - 66 Voltage Live  real=5  data=11 und=3
  - 67 Voltage Hist  real=100 data=113 und=12
  - 68 Current Live  real=6  data=9  und=2
  - 69 Current Hist  real=113 data=115 und=1
- BUT payload inspection: EVERY measured value = 0.0.
  - 66/68 live: 0 non-zero numeric leaves (all phases/summary/avg/neutral = 0.0; 9 '—' placeholders each).
  - 67/69 history: all 3 series × 25 pts = 0.0; the only non-zeros are xLabelIndexes (epoch-ms timestamps) + default empty-chart yTicks (±1.0/±0.5). The high real counts are INFLATED by counting timestamps and axis ticks as real data leaves.
- neuract ground truth (target_version1.neuract.dg_1_mfm): 44,562 rows, nz_volt=0, nz_cur=0, max|v_ry|=0, max|i_avg|=0. History window (2026-07-03 17:30–21:30 UTC) = 0 rows. Latest live rows all 0. DG voltage/current is a genuinely ALL-ZERO metric on this meter.
- Columns cross-check: voltage_avg ABSENT, thd_current_* ABSENT (matches card-66 column_absent gaps); voltage_ry/yb/br + current_r/y/b/avg/neutral PRESENT but all-zero valued.
- CONTRACT (a) VIOLATION: a card whose data leaves are all 0.0 must be honest_blank/none (real=0, undeclared>0). Here all 4 are partial/partial with real>0 → fabricated-zero counted as real. Every card honest=FALSE.
- fake_full[] (strict: render/full AND real==0) = EMPTY — none is render/full, none has real==0. So R2 render/full bug not present, but a NEW fake-PARTIAL fabricated-zero bug is: 0.0 leaves (and timestamp/tick scaffolding) scored as real.
- crashes[] = EMPTY (no NaN/payload_error/exception).
- VERDICT: verdict_ok=FALSE (every card verdict dishonest per contract a).

## [panel_ep] energy and power for PCC Panel 1  (tag=panel_ep, 2026-07-04)

Route: panel-overview-shell/energy-power | mfm 317 (PCC-Panel-1) | 4 cards {14,15,16,17} | group coupling=time-bucket.
Members resolved (executor members.resolve(317)): 12 members, coverage {reporting:4, expected:8, partial}.
Live member data CONFIRMED in target_version1.neuract (tunnel :5433): e.g. gic_01_n3_ups_01_p1 = 53157 rows,
active_power_total_kw=-171.1, apparent_power_total_kva=172.1; gic_01_n8_bpdb_01_p1 = 53146 rows, 7d import-kwh
delta 542560. The panel's OWN table pcc_panel_1_feedbacks has 0 rows + only digital-status cols (no kW/kWh) —
so every energy/power number is a real MEMBER aggregate, not from the panel table. lt_feeder table empty (edges
come from registries.neuract incomers/outgoers, not lt_feeder).

Per-card verdict vs CONTRACT:
- CARD 14 Cumulative Energy   : render/full  real=1 data=1 und=0. HONEST. Scalar card.view.value=78210.0 kWh is a real
  windowed roster sum over live load members (bpdb-01 has real kwh delta). render⟺full ✔.
- CARD 15 Today live power    : render/full  real=1 data=1 und=0. HONEST. value=737 kW = real Σ|kVA| over live members
  (member latest kVA 170.8/170.8/179.0/595.0; card uses 30s/12-sample window). Loop1 note honestly blanks the
  rated-capacity marker (kVA nameplate absent on gic_*). render⟺full ✔.
- CARD 16 Energy Consumption Trend : partial/partial real=1 data=10 und=9. HONEST. Real trend points
  (points[1].bpdp=76660, active=76660) + 9 undeclared Storybook-seed leaves blank → partial. Correct.
- CARD 17 Daily Power Demand by Feeder : honest_blank/none real=0 data=4 und=4.
  ** FALSE-NEGATIVE (not fake-full) ** — payload demand.view.points carries REAL member aggregates
  (points[].ups=613.38, bpdp=335.65 over 6 pts; legend UPS=592, BPDP=309), roster[0] mode="series_split"
  binds slot demand.view.points, and members are live. BUT roster_stats._slot_stats has NO "series_split"
  branch → credits real=0/data=0 for the points series; the 4 unbound seed scalars (stats[worst-peak,load-factor]
  =0.0, criticalKw=0.0, legend[0/1].value) are counted undeclared-blank → real=0/data=4 → honest_blank/none.
  Offline recompute render_verdict.compute(pl,di,None) reproduces EXACTLY {real0,data4,und4,honest_blank,none}.
  Root cause: validate/render_verdict fold-in is correct; the miss is ems_exec/executor/roster_stats.py
  _slot_stats lacking a series_split case (companion to the existing "series" case). Card errs SAFE
  (under-reports as blank; does NOT fabricate a full render).

CONTRACT RESULT:
  fake_full[] = []  (NO card is render/full with real==0 — the R2 fabricated-zero fake-full did NOT survive)
  crashes[]   = []  (ok=true, errors={}, no payload_error, no NaN across all 4 cards)
  verdict-map (render⟺full, honest_blank⟺none, partial⟺partial): all 4 satisfy.
  BUT card 17 verdict is not HONEST w.r.t. its real data (real roster points reported as honest_blank/none).
  => verdict_ok = FALSE (card 17 dishonest-blank via series_split gap), fake_full clean, crashes clean.

## [panel_rtm] 'real time monitoring for PCC Panel 1'  (tag=panel_rtm, 2026-07-04)
Resolved directly (asset_pending=False). page_key=panel-overview-shell/real-time-monitoring, 8 cards [7,5,160,6,8,9,10,11].
NaN/Inf scan: NONE. All cards has_payload=True, fill_ok=True.

Per-card render.{verdict/answerability leaf_stats(real,data,undeclared)} + honesty:
- card 7  Context Rail Header  partial/partial  real=34 data=45 und=4   HONEST. ROSTER fold-in WORKS: railVM.supply=685.6kW(GIC-01), quickStats CurrentUnbal=6.798%, ElecLoad=977.0A, PF=0.988, 25-pt trend series. Blank leaves (Voltage '—', Peak Today '—', denominator '—') = honest per-leaf degrade (no nameplate / voltage_ll_avg not measured). real>0 -> roster NOT broken.
- card 5  Feeder Heatmap       partial/partial  real=34 data=102 und=6  HONEST verdict, but carries payload_error='llm call failed (timeout): timed out (prompt~18792 tok)' — the known v48 heatmap emit fail-fast. It SOFT-DEGRADED: default metadata + ems_exec fill, has_payload=True, fill_ok=True, real=34 live leaves, verdict=partial. Not an unhandled crash, but per literal contract crashes[]='any payload_error' -> reported in crashes[].
- card 160 Heatmap Footer      honest_blank/none real=0 data=1 und=1    HONEST. data leaf = scrubber history:[] (empty), only leftover selectedSampleIndex=0.0 (undeclared). real=0 & und>0 -> matches contract (a) exactly.
- card 6  Live Scrubber        honest_blank/none real=0 data=1 und=1    HONEST. same as 160 (history:[]; selectedSampleIndex=0.0 undeclared).
- card 8  AI Summary           render/full       real=0 data=0 und=0    HONEST (narrative_ai payload-exempt; data==0 so NOT the R2 fake_full bug). AI text grounded in REAL member telemetry ('4/8 feeders, GIC-01-N8-BPDB-01 149.0kW @51.3% load, PF 0.988').
- card 9  Total Feeder Supply  partial/partial  real=2 data=4 und=2     HONEST. supply.value=685.6kW real (GIC-01 685.6); denominator '—' honest (no nameplate).
- card 10 Consumption Trend    partial/partial  real=1 data=5 und=4     HONEST. real trend present; missing metrics honest-blank.
- card 11 Quick Stats          partial/partial  real=3 data=6 und=3     HONEST. 3 real live stats; rest honest-blank.

Biconditional (render<=>full, honest_blank<=>none): TRUE for all 8.
FAKE_FULL (render/full & real==0 & data>0): [] EMPTY -> R2 bug NOT present.

Neuract cross-check (target_version1 / schema neuract, live tunnel :5433):
- GIC-01 member tables carry LIVE data ts=2026-07-04T23:37 (current): gic_01_n8_bpdb_01_p1 ap=664kW cur=947A unbal=13.9%, ups feeders -170/-172/-167kW cur~245A unbal 5.3-5.7% (signed). Reported rail supply 685.6kW / load 977A / unbal 6.798% are real live magnitudes (dominated by bpdb 664kW/947A). REAL renders are truly LIVE.
- PCC-Panel-1 DEVICE itself is empty (memory: PCC panels are empty devices); members carry data. card7 gap 'active_power_total_kw not logged by this meter' is the PANEL device; roster reads MEMBER tables -> honest.
- honest_blank 160/6: scrubber history[] genuinely empty for the empty panel-device time axis -> honest_blank is HONEST.

VERDICT: 0 fake_full, 0 unhandled crashes, all 8 verdicts honest. ROSTER regression NOT present (card7 real=34, card9 real=2 via member fold-in).
CAVEAT: card 5 carries a recorded payload_error (emit-timeout soft-degrade) -> per literal contract goes in crashes[] -> verdict_ok=FALSE by the letter, though the card itself rendered real data honestly.

## ============ JUDGE VERDICT — reworked post-fill verdict (2026-07-04) ============
Independent re-verification of the 4-class run. Ground-truth SELECTs re-run live vs
target_version1.neuract (tunnel :5433), payloads re-flattened offline from the /tmp/vv_*.json
cache. Confirmations (all reproduced, not taken on trust):
  - DG-1 dg_1_mfm: 44625 rows, nz_volt=0, nz_cur=0, max|voltage_ry|=0, max|current_avg|=0 -> genuinely ALL-ZERO meter.
  - UPS-01 gic_01_n3_ups_01_p1: 53170 rows, voltage_*_n ~239-242, current_avg max 336, ap 229kW/231kVA -> LIVE.
  - BPDB-01 gic_01_n8_bpdb_01_p1: 53155 rows, ap 916kW, kva 928, current_avg 1326 -> LIVE.
  - DG cards 66/68 payload flatten: 15/18 numeric leaves, ZERO nonzero -> scored real=5 / real=6. FABRICATED-ZERO.
  - DG cards 67/69 history flatten: 32/34 nonzero = 25 epoch-ms + 7 axis-ticks (+2 chart-scale 131 on 69);
    ZERO real measured values -> scored real=100 / real=113. INFLATED by timestamps+ticks.
  - panel_ep card 17: demand.view.points ups=613.38/bpdp=335.65 (6 pts), legend UPS=592/BPDB=309kW REAL
    -> scored honest_blank/none/real=0. FALSE-NEGATIVE. Root cause CONFIRMED in code:
    ems_exec/executor/roster_stats.py _slot_stats has modes {elements,groups,aggregates,scalar,sections,
    series,sankey_match} but NO series_split branch -> falls through, returns real=0/data=0.

(1) TABLE  page | card | verdict | answ | real/data/undeclared | honest
| feeder_vc voltage/current UPS-01 | 43 | partial | partial | 11/15/2 | YES |
| feeder_vc | 44 | partial | partial | 154/156/1 | YES |
| feeder_vc | 45 | partial | partial | 8/11/2 | YES |
| feeder_vc | 46 | partial | partial | 117/118/1 | YES |
| panel_rtm real-time PCC-Panel-1 | 7  | partial | partial | 34/45/4 | YES (roster fold-in) |
| panel_rtm | 5  | partial | partial | 34/102/6 | YES render; carries emit-timeout payload_error (soft-degrade) |
| panel_rtm | 160| honest_blank | none | 0/1/1 | YES (scrubber history[]) |
| panel_rtm | 6  | honest_blank | none | 0/1/1 | YES (scrubber history[]) |
| panel_rtm | 8  | render | full | 0/0/0 | YES (narrative_ai exempt, data==0) |
| panel_rtm | 9  | partial | partial | 2/4/2 | YES (supply 685.6kW member) |
| panel_rtm | 10 | partial | partial | 1/5/4 | YES |
| panel_rtm | 11 | partial | partial | 3/6/3 | YES |
| panel_ep energy/power PCC-Panel-1 | 14 | render | full | 1/1/0 | YES |
| panel_ep | 15 | render | full | 1/1/0 | YES |
| panel_ep | 16 | partial | partial | 1/10/9 | YES |
| panel_ep | 17 | honest_blank | none | 0/4/4 | NO -> FALSE-NEGATIVE (series_split gap) |
| dg_vc voltage/current DG-1 | 66 | partial | partial | 5/11/3 | NO -> fake-partial fabricated-zero |
| dg_vc | 67 | partial | partial | 100/113/12 | NO -> fake-partial (epoch+ticks) |
| dg_vc | 68 | partial | partial | 6/9/2 | NO -> fake-partial fabricated-zero |
| dg_vc | 69 | partial | partial | 113/115/1 | NO -> fake-partial (epoch+ticks) |

(2) FAKE-FULL CHECK (render/full AND real==0, the R2 bug): ZERO across all 20 cards.
    Card 8 is render/full with real==0 but data==0 (narrative_ai exemption, no data leaves) -> NOT the R2 bug.
    The R2 fabricated-zero render/full defect the rework targeted is ELIMINATED. PASS.

(3) REGRESSION CHECK (real feeder/DG/roster card that SHOULD render real came back honest_blank):
    - Roster: NO false-blank. panel_rtm card7=34, card9=2; panel_ep card14/15 render/full via member fold-in. OK.
    - Feeder: NO false-blank. UPS-01 cards 43/44/45/46 all partial real>0 (live meter). OK.
    - DG: DG-1 is genuinely all-zero, so honest_blank WOULD be the correct verdict; the cards did NOT
      false-blank, they fake-PARTIAL'd (opposite defect). Not a false-blank regression.
    - ONE false-blank on a REAL-data card: panel_ep card 17 (real member series_split points -> honest_blank/none).
      This IS a false-blank on a card that should render real. Regression class = roster series_split.

(4) EXPLICIT VERDICT: NOT CERTIFIED. The rework's PRIMARY target (R2 fake-full render/full+real==0) is
    fully eliminated (0/20) and verdict<=>answerability biconditional holds on every card, no crash/NaN/
    payload_error-exception (card5 emit-timeout is a recorded soft-degrade, not an unhandled crash). BUT two
    honesty defects remain, both live-reproduced:
      A. FAKE-PARTIAL FABRICATED-ZERO (dg_vc 66,67,68,69) — 0.0 data leaves, epoch-ms timestamps, and default
         chart axis-ticks/scale scalars are scored as `real`. A genuinely all-zero meter (DG-1 verified) renders
         partial/real>0 instead of honest_blank/none. Violates contract (a). This is the more serious defect —
         it FABRICATES answerability (over-reports), the exact spirit of the fake-full contract, just at partial
         granularity. Fix scope: leaf classifier must treat 0.0 measured leaves + timestamp/axis-scaffold leaves
         as not-real.
      B. FALSE-NEGATIVE SERIES_SPLIT (panel_ep 17) — real member split-series points scored honest_blank/none.
         Violates contract (c) (roster/member-filled must render real). Errs SAFE (under-report). Fix = add a
         `series_split` case to ems_exec/executor/roster_stats.py _slot_stats (companion to `series`).
    NET: fake-full ELIMINATED and crash/NaN clean, so a strict R2-only regression gate PASSES; but the reworked
    verdict is NOT honest end-to-end. Card ids to fix: 66,67,68,69 (leaf-classify zeros/scaffold) and 17
    (roster_stats series_split). Certification blocked until both are fixed.
