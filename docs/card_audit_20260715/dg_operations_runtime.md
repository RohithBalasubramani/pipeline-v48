# Card Audit — Diesel Generator / Operations & Runtime

- page_key: `diesel-generator-asset-dashboard/operations-runtime`
- meter table: `dg_1_mfm` (mfm_id=2), **electrical MFM** — logs power/current/voltage/frequency/energy-register only.
- Candidate gaps in gaps.json: 97 (card70=13, card71=77, card72=7). Card73 had 0 candidate gaps.

## Meter reality (probed, last 7 days)
- Columns present with data: `active_energy_import_kwh` (cumulative register 27827→29937), `active_power_total_kw` (avg 12.6), `reactive_power_total_kvar` (avg 1.8), `apparent_power_total_kva`, `power_factor_total` (avg 0.01), `current_*`, `voltage_*`, `frequency_hz`. All ~120,926 rows/7d.
- **Absent entirely (no column):** run-hours / runtime duration, start counts, service interval/ceiling, availability/uptime, MTBF, MTTR, reactive **energy** (kVARh), apparent **energy** (kVAh), demand-limit / nameplate rating.
- `lt_mfm.rated_capacity_kva` for dg_1_mfm is **NULL** → no nameplate rating → any load-% (kW→%) or demand-limit slot cannot be honestly computed.

---

## Card 70 — Live Operations & Runtime (snapshot)
Every blanked leaf is a runtime/service/availability counter. This is a **DG electrical meter**; it does not log run-hours, starts, total-runs, availability, startup time, or service countdown. The EMS demo fills these from a genset controller / commercial service contract, not from an MFM.

| leaf | ref | verdict | fix_family |
|---|---|---|---|
| liveOps.insight | narrative | honest_absent | narrative_absent |
| liveOps.service.hours | 236.3 | honest_absent | runtime_counters_absent |
| liveOps.service.ceiling | 300 | honest_absent | service_contract_absent |
| liveOps.service.warnPct | 85 | honest_absent | service_contract_absent |
| liveOps.service.fraction | 0.788 | honest_absent | runtime_counters_absent |
| liveOps.service.remaining | 63.7 | honest_absent | runtime_counters_absent |
| liveOps.service.availability | 99.88 | honest_absent | availability_absent |
| liveOps.topKpis[0].value (runHours) | 4,300 | honest_absent | runtime_counters_absent |
| liveOps.topKpis[1].value (starts) | 295 | honest_absent | runtime_counters_absent |
| liveOps.topKpis[2].value (totalRuns) | 258 | honest_absent | runtime_counters_absent |
| liveOps.topKpis[3].value (availability) | 99.9 | honest_absent | availability_absent |
| liveOps.stateKpis[2].value (startup) | 12 | honest_absent | runtime_counters_absent |
| liveOps.stateKpis[3].value (service-in) | 64 | honest_absent | runtime_counters_absent |

**All honest_absent.** V48 is correct to blank. DI `_honest_blanked` already documents each. No fabrication warranted.

---

## Card 71 — Runtime & Duty (24h hourly duty profile)
DI binds `duty.points[*].loadPct` with metric `active_power_total_kw` (exists w/ data) but **source=frame** and it is a `%` slot → unit-crossing kW→% blocked. It cannot become an honest load-% because the **rating divisor is NULL** (`rated_capacity_kva` null). runHours/starts per hour are event/runtime data the meter never logs.

| leaf | ref | verdict | fix_family | note |
|---|---|---|---|---|
| duty.points[*].loadPct (24×) | 53–77 | honest_absent | loadfactor_rating_nulled | active_power present, but kW→% needs rating (null); becomes fillable only if DG nameplate kVA/kW is seeded |
| duty.points[*].runHours (24×) | 0.1–0.95 | honest_absent | runtime_counters_absent | no run-hour column |
| duty.points[*].starts (24×) | 1–2 | honest_absent | runtime_counters_absent | no start-count column |
| duty.topKpis[0].value | 12 | honest_absent | runtime_counters_absent | total starts |
| duty.topKpis[1].value | 36 | honest_absent | runtime_counters_absent | run hours |
| duty.topKpis[2].sub ("peak 77%") | peak load% | honest_absent | loadfactor_rating_nulled | peak-of-rating needs nameplate |
| duty.tickInterval | 2 | chrome_noise | axis_chrome | structural x-axis tick, not data |
| duty.demandLimitKw | 1700 | honest_absent | rating_nameplate_absent | demand limit is a nameplate/contract constant, rating null |

Note: `duty.topKpis[2].value` (Average load) IS filled via `loadFactorPct` (avg/peak ratio — needs no rating), so it is not a gap. Only the rating-relative %s and runtime counters blank.

**All honest_absent except tickInterval (chrome).** The single systemic lever here is the nulled DG nameplate rating (loadfactor_rating_nulled): if `lt_mfm.rated_capacity_kva` were seeded for dg_1_mfm, per-hour loadPct + peak% + a real demand limit would become derivable from the present `active_power_total_kw` series.

---

## Card 72 — Energy & Reliability (tiles)
Mixed. Two real derivation bugs here, the rest honest.

| leaf | ref | verdict | fix_family | note |
|---|---|---|---|---|
| cells[2].value (MTBF) | 3,180 | honest_absent | reliability_events_absent | no failure/event log on meter |
| cells[3].value (MTTR) | 3.7 | honest_absent | reliability_events_absent | no repair-event data |
| **apparentMvah** | 19.64 | **derivation_gap** | derivation_null_bug | fn `activeEnergyMvah` on `active_energy_import_kwh`; **inputs present** (cells[0] with the SAME fn already yielded 29.94). Slot returns null = fill-order/target_column collision bug → FIXABLE |
| **reactiveMvarh** | 6.33 | **mis_bind** | reactive_energy_from_power_integration | bound to fn `loadFactorPct(active_power_total_kw)` — wrong quantity. No reactive-energy register, BUT `reactive_power_total_kvar` has data → reactive kVARh = ∫kVAR dt is derivable. Rebind to a power-integration fn |
| activeFraction | 0.746 | derivation_gap | reactive_energy_from_power_integration | = active/(active+reactive) energy; unblocks once reactiveMvarh derived |
| reactiveFraction | 0.254 | derivation_gap | reactive_energy_from_power_integration | same chain |
| insight | narrative | honest_absent | narrative_absent | text summary, no source |

cells[0] (29.94 "Apparent") and cells[1] (0.0 "Power Factor") are filled — note they are mislabeled in the reference vocabulary (cells[0] is active-energy register shown as MVAh/Apparent), but they carry real values so not gaps.

**Two fixable items:** `apparentMvah` (a genuine derivation null-bug, twin already computed) and the `reactiveMvarh` family (mis-bound fn; correct path = integrate `reactive_power_total_kvar`, which unblocks both fractions). MTBF/MTTR/insight are honest_absent.

---

## Card 73 — Power Energy Analysis (SeriesPayload)
No candidate gaps in gaps.json. `backupHistory.series[0]` (Active Energy) is bound live to `active_energy_import_kwh`. `series[1]` reactive-energy, `series[2]` apparent-energy, `series[3]` demand are `_honest_blanked` because this meter has **only power registers** for reactive/apparent (`reactive_power_total_kvar`, `apparent_power_total_kva`) — no reactive/apparent **energy** columns. Thresholds are default zones (chrome). The reference does not fill these either → nothing actionable; genuine honest gap, not a grid-shape difference. Potential future derivation: reactive/apparent energy via power-integration (same lever as card 72 reactiveMvarh), but as a series it is out of current scope.

---

## Synthesis
- Dominant verdict: **honest_absent** — this is a DG electrical MFM feeding runtime/reliability cards designed for a genset controller. Runtime counters (hours/starts/runs/availability), service-contract constants, and MTBF/MTTR are structurally not on the meter.
- One systemic lever: **loadfactor_rating_nulled** — `lt_mfm.rated_capacity_kva` NULL for dg_1_mfm blocks every load-% and demand-limit leaf across cards 70/71 despite `active_power_total_kw` having data. Seeding the DG nameplate rating would light up loadPct (24 pts), peak%, and demandLimitKw.
- Two real derivation defects on card 72: `apparentMvah` null-bug (twin already computed with same fn) and `reactiveMvarh` mis-bound to loadFactorPct (should integrate `reactive_power_total_kvar`; unblocks active/reactive fractions).
