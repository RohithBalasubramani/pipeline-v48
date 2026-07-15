# Card audit — diesel-generator-asset-dashboard/fuel-efficiency

Meter: `dg_1_mfm` (neuract). Cards: 63 Fuel Tank Anatomy, 64 All Runs (Fuel Log), 65 Fuel & Tank — Composite.

## Headline

`dg_1_mfm` is a **pure electrical MFM** — its columns are voltage / current / power /
energy / frequency / PF only. There is **no fuel telemetry** on it: no tank level,
fuel flow (L/hr), fuel temperature, tank capacity, SFC, run-hours, start-count,
fault-event, or cost column. This is a "fuel efficiency" page pointed at an electrical
meter, so the overwhelming majority of the demo's fuel leaves are **honest_absent** —
V48 is correct to blank them, and fabricating a same-dimension electrical stand-in
would be a lie (the emit layer already reasons this out in `_honest_blanked`).

Only three leaves are genuinely recoverable from the electrical data this meter does carry:

| Card.leaf | ref | column / fn | data present? | verdict |
|---|---|---|---|---|
| 64 `.stats.totalKwh` | 5588 | `active_energy_import_kwh` | YES (register 27827→29937) | binding_gap |
| 64 `.stats.avgLoad` | 66 | `loadFactorPct(active_power_total_kw)` | YES (fn already works: card65 kpi Load=56.7) | derivation_gap |
| 64 `.stats.runHours` | 16.56 | count(power>0)·interval | inputs YES, no run-hours fn | derivation_gap (needs new fn) |

Column probe (last 7 days): `active_power_total_kw` 120,925 non-null (avg 12.56, max
1495.2 kW, min −18.6); `active_energy_import_kwh` 120,925 non-null (27,827.9 → 29,937.5).

## Card 63 — Fuel Tank Anatomy (snapshot) — ALL honest_absent

Every leaf is a fuel-domain quantity with no source column on this electrical meter.
The emit layer already documents each in `_honest_blanked` with the correct reason.

- `.snapshot.fuelLevel` (ref 60.03) — no tank-level % sensor → honest_absent
- `.snapshot.fuelRate` (ref 106.5 L/hr) — no fuel-flow column → honest_absent
- `.snapshot.fuelTemp` (ref 40.86 °C) — no fuel-temp column → honest_absent
- `.snapshot.autonomy` (ref 5.58 hr) — needs flow + tank capacity → honest_absent
- `.snapshot.efficiency` (ref 39.98 %) — SFC needs fuel flow → honest_absent
- `.display.aiText` / `.display.channelDetail.flow` — narrative composed *from* the
  absent fuel snapshot → honest_absent (downstream of the blanked leaves)

fix_family: `fuel_telemetry_absent`

## Card 64 — All Runs (Fuel Log) (stats)

- `.stats.faults` (ref 1) — no fault/breaker-event column or count metric → **honest_absent** (`fault_events_absent`)
- `.stats.starts` (ref 36) — no genset start-count source → **honest_absent** (`genset_starts_absent`)
- `.stats.totalFuelL` (ref 1626) — no fuel-volume column → **honest_absent** (`fuel_telemetry_absent`)
- `.stats.totalKwh` (ref 5588, v48 "—") — `active_energy_import_kwh` EXISTS WITH DATA but
  the slot was left **unbound** (fields=[], only listed as a fetch metric, no field
  binding). → **binding_gap** / `energy_register_bindable`. Fix: bind
  `.stats.totalKwh` to windowed Δ of `active_energy_import_kwh` (max−min over window).
  Caveat: register is cumulative — a bound value will be a windowed delta (~2.1k over 7d
  here) and won't byte-match the demo's 5588, i.e. a secondary `windowed_vs_cumulative`
  consideration, but the fix is to bind, not blank.
- `.stats.avgLoad` (ref 66, v48 "—") — mean load %. Derivable via `loadFactorPct` on
  `active_power_total_kw`; that exact fn already runs successfully on card 65
  (`chart.kpis[3]` Load = 56.7). The slot here is unbound_by_emit. → **derivation_gap** /
  `loadfactor_derivable`. Fix: apply loadFactorPct (avg scope) to the same column.
- `.stats.runHours` (ref 16.56) — engine run-hours. Inputs present (power > 0 ⇒ genset
  running; count intervals × interval seconds), but there is no run-hours derivation fn
  in the catalog. → **derivation_gap** / `runhours_derivable_from_power` (needs a new
  count-active-intervals fn; the emit reason "no fn turns power into a duration" is
  accurate today but the proxy is legitimately buildable).

## Card 65 — Fuel & Tank — Composite (chart) — fuel domain honest_absent + chrome

- `.chart.band.y1` (40) / `.chart.band.y2` (55) — "Expected Range" band for the **fuel
  level** series; no fuel sensor and no series to anchor a band to → **honest_absent**
  (`fuel_telemetry_absent`).
- `.chart.kpis[1].value` SFC 0.292 L/kWh — needs fuel flow → **honest_absent** (`fuel_telemetry_absent`).
- `.chart.kpis[2].value` Cost ₹26.3/kWh — needs a tariff/cost source; none on meter →
  **honest_absent** (`cost_absent`).
- `.chart.events[0/1].{idx,why,value}` — refuel / low-level events derived from the fuel
  level series → **honest_absent** (`fuel_telemetry_absent`).
- `.chart.series[0].warn` (20) — low-fuel threshold for the absent fuel-level series →
  **honest_absent** (`fuel_telemetry_absent`).
- `.chart.series[0].limit.warnText` ("20% low"), `.chart.series[0].width` (2.2),
  `.chart.series[1].dash`/`.width`, `.chart.series[2].dash`/`.width` — pure line-styling /
  label chrome, not data leaves → **chrome_noise**.
- `.chart.insight` — narrative composed from the absent fuel series → **honest_absent**
  (`fuel_telemetry_absent`).

### Card 65 non-gap observations (not blank, so not in gaps.json, but noted)

- `.chart.kpis[0]` Efficiency: v48 = **97.0** vs ref 40. The `efficiencyPct` derivation
  fires on `active_power_total_kw` and returns an electrical-efficiency-like 97%, which is
  semantically the wrong quantity for a DG *fuel* efficiency (~40%). Not a blank gap, but
  a `derivation_semantic_mismatch` worth flagging to the fn owner.
- `.chart.legend` has **ballooned to ~168 entries** (mostly `value:0.0`, a few spikes like
  420, 450, 1241). The `chart.legend[1]` "Rate" slot was bound *bucketed* to
  `active_power_total_kw` (kW power) as a stand-in for a fuel L/hr rate — a cross-quantity
  `mis_bind` — and the bucketed binding fanned per-timestamp rows into legend slots
  instead of producing the single 4-item legend the ref shows. This is a **shape/mis-bind
  defect** (fix: drop the power→Rate stand-in, honest-blank the fuel legend rows), but the
  affected leaves carry values (not blanks) so they are outside the blank-leaf gap set.
