# CMD_V2 Domain-Slot Research — tap / engine / thermal / battery proxies

**Scope.** The V48 asset dashboards render REAL CMD_V2 components payload-direct. The asset's ONE electrical
meter (PQM/MFM) measures only V / A / kW / PF / energy. It has NO tap-changer, engine, thermal, or
battery-management sensors. The Layer-2 emit historically proxied electrical columns into those domain slots
(tap ← active_power_total_kw = −913; tapPosition.gauge ← voltage_avg; thermal loss ← power; battery SoC ←
voltage-deviation). This document establishes, per slot, whether CMD_V2 sources it real or mock, what the
honest value/range is, whether a designed empty-state exists, and what V48 must do (BLANK / ACCEPT-as-correlate
/ WIRE-real).

**Cards in scope (V48 ids 50–81):** UPS/battery 50–59, DG engine/thermal 60–65 + 70–71, transformer thermal
74–77, transformer tap/RTCC 78–81. Electrical-real cards on the same pages (regulation 79, loss 81-KPI,
load%/loss/efficiency in 74/75, DG V/A 66–69, DG power 72–73) fill for real and are called out where they sit
next to a proxy slot.

**Global truth (grep over `src/api/**`, `src/realtime/**`).** There is NO dedicated RTCC / BMS / ECU /
thermal-controller backend. Every asset dashboard routes to ONE backend — backend2 :8889
(`src/api/backend/backendRouting.ts:38-42`) — over the asset page socket
(`src/realtime/assetPageSocket.ts`, `ws/asset/{id}/<page-code>/`). Each domain is just a page-code on that one
socket: tap=`transformer-tap-rtcc`, thermal=`transformer-thermal-life`, engine=`dg-engine-cooling`,
battery=`ups-battery-autonomy`. All four ship `*_API_ENABLED=true` (live-first) but are architecturally
**live-first-with-mock-fallback**: an unregistered asset → status `unavailable` → mock; a mapper that
null-returns on missing readings → mock. Confirmed null-returns: tap `mapper.ts:35,42`, thermal `mapper.ts:39`,
engine `mapper.ts:31`, battery `mapper.ts:55`. Every hook docblock literally says "the tab never blanks."

---

## (1) PER-SLOT TABLE

Legend for empty-state column: **TYPED-EMPTY-VM** = the V48 fill view-model runs the REAL CMD_V2 producer over
a zero/`—` scaffold, then blanks measured leaves (drawable, honest); **GUARDS-ONLY** = card 50–59 has no fill
VM, relies on `host/web/src/cmd/guards.ts`; **CLAMP** = the primitive silently coerces (no blank).

### TAP / RTCC — cards 78, 80, 81 (proxy) · 79 (electrical-real)

| component | slot / prop | expected qty + unit + typical range | empty-state design | real-source or mock |
|---|---|---|---|---|
| SegmentedArcGauge via TapPositionCard (`TapPositionCard.tsx:27-35`; gauge `SegmentedArcGauge.tsx:88-99`) | `gauge.value` (currentTap) + `gauge.count` | Discrete OLTC tap, small int. `count=TAP_MAX=5` (`tap-rtcc/config.ts:23`); value clamped `1..5` by `active = Math.min(n, Math.max(1, Math.round(value)))` (`SegmentedArcGauge.tsx:99`). Mock walks tap ~3 (seed `tap=3`, `mockSource.ts:53`). Real OLTC is larger range (17-pos, neutral 8) but this tab only ever renders 1..5. | **NO null render — CLAMPS.** `value:number` required (`SegmentedArcGauge.tsx:20`); a proxied kW=−913 or V=250 rounds+clamps to 5, pins needle far-right, aria `Position 5 of 5` (`:114`) — confidently wrong, never blank. V48 blanks via **TYPED-EMPTY-VM** `gauge.value=0` → clamps to position 1 (`fill/transformer-tap-rtcc/view-model.ts:99,135`). | **MOCK-ONLY.** Hook gates socket on `variant==='ht'` (`useTapRtccData.ts:33`); needs `setpointKv` in snapshot or mapper null-returns → mock (`mapper.ts:35`). Neuract meter has no tap column. |
| SegmentedArcGauge optimal arc (`SegmentedArcGauge.tsx:142-149`) | `gauge.optimal` (optimalTap) | Target tap, int 1..5, or null when aligned. Mock nudges ±1 on sustained tail drift (`mockSource.ts:90-93`); VM sets `optimal: delta===0 ? null : optimalTap` (`viewModel.ts:46`). | **Null-safe by design** — `optimal?: number|null`; guarded `optimal != null && >=1 && <=n` (`:142`). V48 forces `optimal:null` when blank. | MOCK-ONLY (derived from same mock tap walk). |
| KpiStatStrip in TapPositionCard | `kpis[current/optimal/mode]` | Current pos, optimal pos (ints), RTCC mode `Auto`/`Manual` (`viewModel.ts:47-51`). | Values are strings → V48 sets `'—'` (`view-model.ts:100`). Safe (text). | MOCK-ONLY (mode from `mapMode`, `mapper.ts:28`). |
| DataTable via RecentTapChangesCard (card 80) | `changes.rows[]` (time, fromTap, toTap) | Today's tap-change log; mock emits 0–6 rows at excursion onsets (`mockSource.ts:62-69`); capped `MAX_CHANGE_ROWS=9` (`config.ts:35`). | **Designed empty state** — DataTable renders its own "no rows" body; V48 sets `rows:[]` (`view-model.ts:103,147`). | MOCK-ONLY. |
| TapActivityCard bars + counter (card 81) | `activity.points[].count/cumTotal`, kpis `total`/`peak`/`avg` | Hourly tap ops (int, mock peak 1–2/h), lifetime counter `LIFETIME_OPS=430` (`config.ts:30`), contact-life budget 5,000,000 (`config.ts:28`). | **TYPED-EMPTY-VM** `points:[]`, kpis `'—'`, legend `'—'` (`view-model.ts:111-117`). Bars draw empty axes. | MOCK-ONLY. NOTE: `LIFETIME_OPS`/`SETPOINT_KV` are AVR **config** (chart chrome, not a measurement) — kept as structural scaffold, not a fabricated datum. |
| VoltageRegulationCard (**card 79 — ELECTRICAL**) | `regulation.points[].voltageKv`, kpis setpoint/regulation/in-range | Regulated bus voltage, kV. Mock `SETPOINT_KV=11.1` ±`REGULATION_PCT=1.7%` band (`config.ts:25-26`); drift table ±0.25 kV (`mockSource.ts:42-46`). | Points sanitized; a `'—'` point is dropped, empty axes draw (`view-model.ts:162-186`). | **REAL when the frame carries the AVR setpoint** — bus voltage IS a neuract measurement. This is the ONE tap-page card that fills real; the `tap` right-axis series stays domain/blank. |

### TRANSFORMER THERMAL & LIFE — cards 74, 76, 77 (thermal slots domain) · 75 + electrical KPIs (real)

| component | slot / prop | expected qty + unit + typical range | empty-state design | real-source or mock |
|---|---|---|---|---|
| ThermalLifeCard metric strip (card 74) | `metrics[].value/tone/statusLabel` — winding °C | Winding temp, °C; warn `WINDING_WARN_C=75` (`thermal-life/config.ts:33`); hotspot−21 offset (`mockSource.ts:11,58`). Fixture windingTempC=80.4. | **TYPED-EMPTY-VM**; metric value `'—'`, **tone must be `info`** (see §4 — `success` throws). | MOCK-ONLY (no winding RTD on an MFM). |
| ThermalLifeCard metric strip | `metrics[]` — oil °C | Top-oil temp, °C; warn `OIL_WARN_C=80` (`config.ts:34`); hotspot−13 (`mockSource.ts:9,57`). Fixture **oilTempC=null** (dry-type). | `oilTempC` nullable by design; oil row DROPS when null (`types.ts:31-33,60`). Honest per-leaf blank. | MOCK-ONLY. |
| ThermalLifeCard metric strip | `metrics[]` — hotspot °C, thermalStressPct | Hotspot, °C; `HOTSPOT_ELEVATED_C=75`/`CRITICAL=85` (`config.ts:20-21`); stress `(hotspot−60)/40·100` clamp 0–100 (`config.ts:26-28`). Mock base `70+(tx%4)*2.5` (`mockSource.ts:76`); fixture 101.4. | TYPED-EMPTY-VM `stressPct=0` empty FillBar. | MOCK-ONLY. |
| ThermalLifeCard metric strip | `metrics[]` — **loss kW** (proxy target) | Total loss, kW; `noLoad + fullLoad·(load%)²` (`config.ts:49`, RATING ht 16/110, lt 1.7/10.5 `config.ts:52-54`). Fixture lossKw=9.4. | TYPED-EMPTY-VM `'—'`. | **DERIVABLE-REAL** — loss is a function of the meter's real load%/power; V48 marks load%/loss/efficiency as electrical-derivable and fills them REAL from the payload (`fill/transformer-thermal-life/view-model.ts:14`). The V48 proxy "thermal-loss ← power" lands HERE and is *correct in kind* (loss IS power-derived) — but a fabricated **temperature** would not be. |
| LifeCapacityCard (card 75) | `lifeRemainingYears`, `lifeFillPct`, derated/headroom kVA | Insulation life yrs (base `BASE_LIFE_YEARS=25`, age 4.5, `config.ts:60-63`); derated=rated−8% (`config.ts:52-54`). | TYPED-EMPTY-VM; **every scalar finitized** — `lifeRemainingYears.toFixed(1)` throws on null (`view-model.ts:123`). | MIXED: derating kVA is nameplate/derivable; aging-life is IEEE C57.91 FAA-integral → domain (FAA needs hotspot). |
| ThermalTimelineCard (card 76) | `points[].hotspotC/oilC/windingC/loadPct/efficiencyPct` | 8×3h buckets (`config.ts:67`). hotspot/oil/winding = domain temps; loadPct/efficiency = electrical-derivable. | TYPED-EMPTY-VM: single `'—'` bucket → flat blank line; oilC null drops the oil series (`view-model.ts:86-89`). | MIXED — temps mock, load%/eff derivable. |
| InsulationAgingCard (card 77) | `aging[].faa/lolPct/hotspotPeakC` | Daily FAA `2^((hotspot−65)/15)` (`config.ts:58-59`, `mockSource.ts:46`); cumulative loss-of-life %. | TYPED-EMPTY-VM: single `{faa:1, lolPct:0}` bucket; legend `'—'`; NaN-guarded axes (`view-model.ts:89,238`). | MOCK-ONLY (FAA is hotspot-driven → no MFM source). |

### DG ENGINE & COOLING / THERMAL — cards 61, 62 (proxy) · 63–65, 70–73 (fuel/runtime/power)

| component | slot / prop | expected qty + unit + typical range | empty-state design | real-source or mock |
|---|---|---|---|---|
| EngineHistoryCharts thermal (card 61) | `SeriesDef 'coolant'` → `EngineHistoryPoint.coolant` | Coolant temp, °C; expected band 75–95 (`engine-cooling/config.ts:76`), warn 95 / trip 104 (`config.ts:29`). Mock ~80–93, spike 106 (`mockSource.ts:43,79`); fixture 92.8. | **TYPED-EMPTY-VM** (`fill/dg-engine-cooling/view-model.ts:21-59`): ONE all-zero point → valid axes/band/legend, EMPTY plotted series, insight blanked (`:93-95`). NOTE the base CMD_V2 mapper coalesces `coolant ?? 0` (`mapper.ts:37`) = real-zero not blank, so the V48 typed-empty path (not the mapper) is what makes it honest. | **MOCK-ONLY.** DG backend **NOT BUILT** — `BACKEND_API_SPEC_ASSET_TABS.md:352-355`: zero DG assets registered, all 4 DG tabs run on mock. An electrical MFM has no coolant RTD. |
| EngineHistoryCharts thermal | `'oilTemp'` → `.oilTemp` | Lube-oil temp, °C; warn 110 / trip 120 (`config.ts:34`). Mock ~90–105 (`mockSource.ts:44,93`); fixture 104.7. | TYPED-EMPTY-VM (empty series). | MOCK-ONLY (unbuilt DG backend; no oil RTD). |
| EngineHistoryCharts thermal | `'intake'` → `.intake` | Intake-air temp, °C; warn 70 (`config.ts:39`). Mock ~38–61 (`mockSource.ts:46,94`). | TYPED-EMPTY-VM. | MOCK-ONLY. |
| EngineHistoryCharts thermal | `'exhaust'` → `.exhaust` | Exhaust-gas temp, °C (right axis); warn 550 / trip 620 (`config.ts:44`). Mock ~385–640 (`mockSource.ts:47,95`). | TYPED-EMPTY-VM. | MOCK-ONLY. |
| EngineHistoryCharts mech (card 62) | `'oilPressure'` → `.oilPressure` | Oil pressure, kPa; expected 300–500 band (`config.ts:77`), warn-low 200 / trip 140 (`config.ts:50`). Mock ~150–700 (`mockSource.ts:45,91`). | TYPED-EMPTY-VM. | MOCK-ONLY. |
| EngineHistoryCharts mech | `'speedRaw'`→`speedPct` | Engine speed, rpm→% axis; mock ~1460–1540 rpm (`mockSource.ts:90`). | TYPED-EMPTY-VM. | MOCK-ONLY (no tacho on an MFM). |
| EngineHistoryCharts mech | `'loadPct'` | Load, % (`config.ts:57`). Mock 20–98 (`mockSource.ts:39`). | TYPED-EMPTY-VM. | **Load% is derivable** from real DG power (cards 72/73 fill real), but this DG has no asset-register entry so the whole tab is mock; treat as blank until DG registered. |
| Engine 3D Callout (card 60) | snapshot clusters (coolant/oil/speed/load) | Instantaneous engine snapshot. | 3D viewer envelope (SPECIAL renderer, `components.ts:91`); callouts read `ZERO_SNAPSHOT` (all 0). | MOCK-ONLY. |

### UPS BATTERY & AUTONOMY — cards 50–59 (GUARDS-ONLY, no fill VM)

| component | slot / prop | expected qty + unit + typical range | empty-state design | real-source or mock |
|---|---|---|---|---|
| BatteryHealthCard SOC headline + FillBar (card 50) | `data.soc` / `data.socPct` | State-of-Charge, 0–100 %. Mock 72–98 (`mockSnapshot.ts:71`, history clamp 60–100 `mockSource.ts:41`); fixture soc≈90–94. | **NO designed blank — GUARDS-ONLY.** `socPct = estimatedChargeRemaining ?? ups_battery_soc_pct ?? lastBat.soc` (`mapper.ts:79`); normalize coerces `?? 0` (`normalizeSnapshot.ts:80`). If frame empty the hook falls to MOCK (`useBatteryAutonomyData.ts:52`) → card shows mock ~90%, never blanks. **V48 has no typed-empty VM for 50–59** → relies on `guards.ts` g9 (`—`) + g2 (tone). | **MOCK-ONLY as a physical SoC.** Wired to `ups-battery-autonomy` (`config.ts:11-13`) but the MFM has no BMS; backend2 SYNTHESIZES `ups_battery_soc_pct`/`state_of_charge_pct` (fixture `upsBatteryAutonomy.json`). A V48 SoC ← voltage-deviation proxy is fabrication. |
| BatteryHealthCard SOC bar ticks | `data.barTicks{min,max}`, `socMax` | Static labels `'0'..'100%'`; `socMax=100`. | N/A — structural constants, always present (`BatteryHealthCard.tsx:39-42`). | Static (not fetched). |
| BatteryHealthCard metric: Temperature | `metrics[0]` battery °C | Battery temp, °C. Mock 24–45 (`mockSnapshot.ts:37`, `mockSource.ts:42`); fixture ~35–37. Tone `TEMP_WARN=38`/`TEMP_DANGER=42` (`config.ts:19-20`). | GUARDS-ONLY; `batteryTemperature ?? 0` → `'0°C'` (`normalizeSnapshot.ts:83`); frame-empty→mock. | MOCK-ONLY / SYNTHETIC (no battery thermistor). A "thermal-loss ← power" proxy would surface here as a fake temperature. |
| BatteryHealthCard metric: Voltage | `metrics[1]` DC-bus V | DC bus voltage, V. Mock 390–470 (`mockSource.ts:43`), base `432+n·1.6` (`mockSnapshot.ts:53`); nominal `V_NOMINAL=433` (`config.ts:26`). | GUARDS-ONLY; `batteryVoltage ?? 0`. | **CORRELATE-REAL** — the MFM DOES measure bus/DC voltage; this slot tracks a real quantity (unlike SoC/temp). |
| BatteryHealthCard metric: Current | `metrics[2]` battery A | Battery current, A (charge +, discharge −). Mock `±loadPct` (`mockSnapshot.ts:54`). | GUARDS-ONLY; `batteryCurrent ?? 0`. | CORRELATE-REAL-ish — MFM measures current, but battery-branch current ≠ meter current; treat as domain unless the meter IS on the battery branch. |
| ScoreHistoryCard (cards 51, 53) | `batteryHistory[].overall/soc/busScore/thermalScore` | 0–100 composite scores/bucket; `overall=min(soc,busScore,thermalScore)` (`BACKEND_API_SPEC:274`). Mock `busQualityScore(voltage)`, `thermalScore(temp)` (`mockSource.ts:44-51`). | GUARDS-ONLY; `trimNullRows` drops null buckets, `?? 0` on leaves (`mapper.ts:57-64`); empty→mock. | MOCK/SYNTHETIC — scores are functions of SoC+temp (synthetic) + bus voltage (real). |
| BackupReadinessCard / autonomy (cards 52, 54, 57, 58) | `autonomyHistory[].index/runtime/headroom/load` | Reserve index, runtime min (`RUNTIME_FULL_MIN=60`), load% headroom. Mock runtime 8–60 min (`mockSource.ts:61`), load 22–88 (`:60`). | GUARDS-ONLY; `?? 0`; empty→mock. | MIXED — load%/headroom electrical-derivable, runtime-minutes needs battery model (domain). |

---

## (2) THE VERDICT — per domain family

**TAP / RTCC (OLTC).** CMD_V2 sources it **MOCK-ONLY** in practice (HT-gated socket + setpoint-required mapper
null-return → deterministic mock; `useTapRtccData.ts:33`, `mapper.ts:35`). No neuract tap column exists. The
SegmentedArcGauge has **no honest-blank** and silently clamps any number to 1..5 — so a proxied kW/kV renders a
confidently-wrong needle. **V48 already BLANKS correctly** via the typed-empty VM
(`fill/transformer-tap-rtcc/view-model.ts`): gauge `value:0` (→position 1), `optimal:null`, KPIs `'—'`,
rows/points `[]`. The regulation card (79) is the exception — bus voltage is real and fills. **Verdict: BLANK
(tap/optimal/changes/activity); the tap-page voltage regulation stays real.**

**ENGINE (DG cooling/mech).** CMD_V2 sources it **MOCK-ONLY** and the backend is **NOT BUILT**
(`BACKEND_API_SPEC_ASSET_TABS.md:352-355`: zero DG assets registered → all 4 DG tabs on mock). An electrical
MFM can never supply coolant/oil/intake/exhaust temps, oil pressure, or engine speed. **V48 already BLANKS**
via the typed-empty EngineFrame (one all-zero point → valid axes, empty series, blanked insight;
`fill/dg-engine-cooling/view-model.ts`). **Verdict: BLANK every engine thermal/mech slot** (the base mapper's
`?? 0` real-zero is superseded by the V48 typed-empty path).

**THERMAL (transformer).** MIXED. The **temperatures** (winding/oil/hotspot) and the **aging FAA/LOL** series
are MOCK-ONLY domain metrics (no RTD/thermal model on an MFM). But **load% / loss kW / efficiency / derated
kVA** are genuinely **electrical-derivable** from the meter's real power and nameplate — CMD_V2 derives them
from the loss law (`mockSource.ts:11-15`) and V48 fills them real (`fill/transformer-thermal-life/view-model.ts:14`).
oilTempC is null-safe by design (dry-type drops the row). **Verdict: WIRE-REAL for load/loss/efficiency/derating;
BLANK winding/oil/hotspot temps + FAA/LOL aging.** The V48 "thermal-loss ← power" proxy is *acceptable in kind*
for the loss slot (loss is power-derived); a proxy into a **temperature** slot is fabrication and must blank.

**BATTERY (UPS).** MOCK/SYNTHETIC for the battery-management quantities. Backend2 is wired
(`config.ts:11-13`) but SYNTHESIZES `ups_battery_soc_pct` / `state_of_charge_pct` / `battery_temperature_c`
(fixture `upsBatteryAutonomy.json`) — the MFM has no BMS. **SoC and battery-temperature are fabrication if
proxied.** Bus **voltage** (and, weakly, current) track real MFM measurements. **Critically, cards 50–59 have
NO V48 typed-empty view-model** (they direct-render CMD_V2 + `guards.ts` only, `components.ts:94-103`), and the
CMD_V2 hook **falls back to mock on an empty frame** rather than blanking (`useBatteryAutonomyData.ts:52`),
coercing null→0 in normalize (`normalizeSnapshot.ts:80-83`). **Verdict: BLANK SoC + battery-temp (no real
source; needs a fill VM or guards to force `—`/`info`); ACCEPT bus-voltage as a real correlate; the score
histories blank per-leaf via guards.**

---

## (3) PER-CARD RECOMMENDATION (V48 cards 50–81)

| card | title | recommendation | why + how |
|---|---|---|---|
| 50 | Battery Health | **BLANK SoC & Temp; ACCEPT Voltage** | SoC/temp synthetic (no BMS). No fill VM today → add one OR ensure guards force SoC/temp `—`. Voltage is real MFM. Prevent the CMD_V2 mock fallback (`useBatteryAutonomyData.ts:52`) — the host emits empty frames, so ensure the payload path (not the hook) drives it. |
| 51 / 53 | Battery / Backup Readiness History | **BLANK-via-guards** | Score series are min() of synthetic SoC/temp + real voltage → not a clean real series; blank per-leaf (guards g9 `—`, empty series drops). |
| 52 / 54 | Backup Readiness / Transfer readiness | **BLANK reserve/runtime; ACCEPT load-headroom if derivable** | runtime-minutes needs a battery model (domain); load%/headroom electrical-derivable. |
| 55 | Activity | **BLANK-via-guards** | Event/alarm log has no neuract source. |
| 56 | Source Transfer — Composite | **BLANK domain leaves; keep electrical** | Transfer events domain; input/output V/A real. |
| 57 / 58 | UPS Capacity / Load | **ACCEPT (electrical-real)** | Output load & capacity are real power/current — fill real. |
| 59 | Output Load & Capacity — Composite | **ACCEPT electrical; BLANK any battery slot** | same. |
| 60 | Engine 3D Callout | **BLANK callouts** | ZERO_SNAPSHOT; 3D mesh renders, callout values `—`/0. |
| 61 | Thermal Timeline (DG) | **BLANK (TYPED-EMPTY)** | Already done; coolant/oil/intake/exhaust have no MFM source + DG backend unbuilt. |
| 62 | Pressure · Speed · Load (DG) | **BLANK (TYPED-EMPTY)** | oil-pressure/speed domain; load% derivable but DG unregistered → blank. |
| 63 | Fuel Tank Anatomy | **BLANK** | Fuel level has no MFM source. |
| 64 | All Runs (Fuel Log) | **BLANK** (empty table) | Run log domain. |
| 65 | Fuel & Tank — Composite | **BLANK** | domain. |
| 66–69 | DG Voltage/Current Live+History | **ACCEPT if DG metered; else BLANK** | V/A are real *if* the DG has a meter; DG not registered today → blank until registered. |
| 70 / 71 | Live Operations & Runtime / Runtime & Duty | **BLANK runtime-hours; keep power** | engine-run-hours domain. |
| 72 / 73 | Energy & Reliability / Power Energy Analysis | **ACCEPT (electrical-real)** | real kWh/power. |
| 74 | Thermal & Life | **WIRE-REAL loss/load/eff; BLANK winding/oil/hotspot temps** | temps mock; loss/load%/eff derivable. Metric tone MUST be `info` when blank (§4). |
| 75 | Life & Capacity | **WIRE-REAL derating; BLANK aging-life** | derated kVA nameplate/derivable; insulation-life FAA-driven → blank. Finitize `lifeRemainingYears`. |
| 76 | Thermal Timeline (Tx) | **WIRE-REAL load%/eff; BLANK temps** | mixed per-series. |
| 77 | Insulation Aging & Loss of Life | **BLANK (TYPED-EMPTY)** | FAA/LOL hotspot-driven → no source. |
| 78 | Tap Position Optimization | **BLANK (TYPED-EMPTY)** | gauge `value:0`→pos1, `optimal:null`, KPIs `—`. Already done. |
| 79 | Voltage Regulation Timeline | **ACCEPT/WIRE-REAL voltage; BLANK tap series** | bus voltage real; OLTC-tap right-axis blank. |
| 80 | Recent Tap Changes | **BLANK** (empty DataTable) | no tap log. |
| 81 | Tap Activity & Wear | **BLANK (TYPED-EMPTY); keep loss KPI if wired** | tap ops domain; the "loss analysis" KPI here is power-derivable. |

---

## (4) HOW TO BLANK CLEANLY — exact prop values that render honest-blank without an SSR crash

These are the props/values that render blank but do NOT throw (feeds the SSR contract; the corresponding
`guards.ts` rule is cited).

1. **SegmentedArcGauge (tap gauge, card 78).** Set `value:0` → clamps to position 1 (`SegmentedArcGauge.tsx:99`),
   `optimal:null` (guarded at `:142`), `count` kept from config (5). NEVER pass a proxied kW/kV — it clamps to
   5 and reads as a real max-tap. KPI values `'—'` (strings, safe). This is exactly
   `fill/transformer-tap-rtcc/view-model.ts:97-102,135-139`.

2. **ThermalLifeCard metric strip (card 74) — the tone crash.** `ThermalLifeCard.tsx:64` passes the domain
   `tone` **directly** into `KpiStatStrip` (a DS-enum consumer), whereas UPS `BatteryHealthCard` maps through
   `STATUS_PILL_TONE` first (`ups/shared/adapters.ts:18-21,40`). `KPI_STATUS_DOT_PRESETS` keys are ONLY
   `{normal, watch, alarm, info}` (`KpiStatStrip.tsx:92-96`) — a `success`/`warning`/`danger` (or blank) tone
   derefs `undefined.dot` and **THROWS** (reproduced live, card 74 — `guards.ts` g2). **Blank tone → `info`**:
   the one token valid through BOTH vocabularies (DS enum natively + UPS domain map via `shims.ts` alias). Set
   metric `{value:'—', tone:'info', statusLabel:''}`.

3. **FillBar pcts (cards 50 SOC, 74 stress, 75 life/derated).** Any `pct` fed to FillBar or a `.toFixed()` must
   be finite — `0/0=NaN` emits a NaN width. Pin with `fin(x)` → `0` (honest empty bar), as
   `fill/transformer-thermal-life/view-model.ts:97-99`. `lifeRemainingYears` MUST be finitized —
   `.toFixed(1)` on null throws (`view-model.ts:123`; guards g3 for `*digits`).

4. **Chart series (cards 61/62/76/77/79/81).** Blank = `points:[]` — the SVG chart draws empty axes/band/legend
   with real titles/colours. Do NOT pass a single fabricated point as data; the V48 pattern hands the CMD_V2
   *producer* ONE scaffold bucket (so `[len-1]`/reduce don't crash) then blanks the *rendered* series to `[]`
   (`fill/dg-engine-cooling/view-model.ts:50-59`, `transformer-tap-rtcc/view-model.ts:69-118`). Axis min/max/ticks
   must be finite (`domain()`/`axis()` helpers) so `GridAxis` never scales by NaN.

5. **DataTable (cards 64, 80).** Blank = `rows:[]` with real `columnLabels` — the table renders its own empty
   body; `view-model.ts:103,147`.

6. **PendingDataPlaceholder (`src/pages/electrical/lt-pcc/panel-overview/components/PendingDataPlaceholder.tsx:22-47`).**
   The ONLY *purpose-built* CMD_V2 empty-state component, but it is used by just 2 real panel tabs
   (`RealTimeMonitoringLayout.tsx:8`, `HarmonicsPqTab.tsx`) and is chosen by
   `data.history.length===0 && snapshot.availability==='unavailable'` (`RealTimeMonitoringLayout.tsx:83-91`),
   which corresponds to a backend `PendingSnapshotFrame {type:'snapshot', pending:true}`
   (`src/api/backend/backendTypes.ts` `isPendingSnapshot`). The asset tabs (tap/thermal/engine/battery) do NOT
   wire it — they fall to mock instead. So for a whole-card blank on an asset dashboard, V48 does NOT get a
   designed CMD_V2 placeholder; it must render the component's OWN structure with blanked leaves (the typed-empty
   VM pattern above). Reserve PendingDataPlaceholder only for panel-overview-style cards that already consume an
   availability snapshot.

7. **Battery cards 50–59 (GUARDS-ONLY gap).** These have no fill view-model — they direct-render CMD_V2 +
   `guards.ts`. Two hazards: (a) the CMD_V2 hook mocks on an empty frame (`useBatteryAutonomyData.ts:52`), so the
   host MUST drive the card from the served payload path, not let the hook run; (b) `normalizeSnapshot.ts:80-83`
   coerces null→0, so a blank SoC/temp reads `0` not `—` unless the served payload already carries `—` and guards
   g9 preserves it. RECOMMENDATION: give cards 50–59 the same typed-empty fill VM the tap/thermal/engine cards
   have, OR confirm the guards path forces SoC/temp to `—` and battery tone to `info` before the DS map deref.

---

## Key file:line index

- Global routing: `src/api/backend/backendRouting.ts:38-42`; asset socket `src/realtime/assetPageSocket.ts`.
- Tap: `tap-rtcc/config.ts:13,23,25-30`; `SegmentedArcGauge.tsx:16-20,88-99,114,142-149`;
  `TapPositionCard.tsx:27-35`; `mapper.ts:35,42`; `useTapRtccData.ts:33,49`; `viewModel.ts:43-56`;
  `mockSource.ts:42-46,53`.
- Thermal: `thermal-life/config.ts:19-34,49-54,60`; `mapper.ts:39`; `types.ts:31-33,60`; `mockSource.ts:9-17,46-58`;
  `ThermalLifeCard.tsx:64`; `KpiStatStrip.tsx:92-96`; `ups/shared/adapters.ts:18-21,40`; fixture `hotspot=101.4`.
- Engine: `engine-cooling/config.ts:15,29,34,39,44,50,76-77`; `mapper.ts:31,37`; `useEngineCoolingData.ts`;
  `mockSource.ts:39,43-47,90-95`; `BACKEND_API_SPEC_ASSET_TABS.md:352-355`.
- Battery: `battery-autonomy/config.ts:11-13,19-20,26`; `mapper.ts:55,79`;
  `ups/shared/normalizeSnapshot.ts:80-83`; `useBatteryAutonomyData.ts:52`; `mockSnapshot.ts:37,53,71`;
  `mockSource.ts:41-44,60-61`; `BatteryHealthCard.tsx:39-42`.
- Empty-state: `PendingDataPlaceholder.tsx:22-47`; `RealTimeMonitoringLayout.tsx:8,83-91`.
- V48 blank machinery: `host/web/src/cmd/guards.ts` (g1-g12); `host/web/src/cmd/registry.tsx:268-276`
  (FILL wins over COMPONENTS); `host/web/src/cmd/components.ts:29-31,46-49,94-117`;
  `host/web/src/cmd/fill/transformer-tap-rtcc/view-model.ts`;
  `host/web/src/cmd/fill/transformer-thermal-life/view-model.ts`;
  `host/web/src/cmd/fill/dg-engine-cooling/view-model.ts`.
