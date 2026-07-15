# Card audit — panel-overview-shell/energy-power

**Meter table (asset):** `pcc_panel_1_feedbacks` (lt_mfm id 317, role PCC-Panel-1)
**Cards:** 14 Cumulative Energy · 16 Energy Consumption Trend · 15 Today live power analysis · 17 Daily Power Demand by Feeder

## Ground truth about this "meter"

`pcc_panel_1_feedbacks` is **NOT an electrical MFM table** — it is the panel's
control/status feedback table. Its only columns are breaker feedback signals
(`tf_inc_*_acb_on_fb`, `bc_acb_trip_fb`, `*_earth_fault_relay_fb`, `*_ref_relay`),
ACB commands (`*_acb_on_cmd`), and transformer winding temperatures
(`tf_1..4_winding_temperature`). **There is no `active_power_*`, `apparent_power_*`,
`*_energy_*` column anywhere on it.** (123,980 rows total; 120,925 in last 7d — but
all control/temperature, no electrical.)

The electrical energy/power for this page comes from **member feeders** (panel-aggregate
roll-up), the GIC feeders under panel 1: UPS 01/02/03 = `gic_01_n3/n4/n5_ups_*_p1`
(ids 11/12/13), plus dark UPS 04/05/06 (ids 23/24/25), and BPDB `gic_01_n8_bpdb_01_p1`
(id 16) + `gic_02_n2_bpdb_02_p1` (id 20). Confirmed a member (`gic_01_n3_ups_01_p1`)
carries `active_power_total_kw`, `reactive_power_total_kvar`, `apparent_power_total_kva`,
`active_energy_import_kwh`, `reactive_energy_import_kvarh` — all with data (24,908 non-null
per column in 7d; spans 8 distinct days).

Panel 317 `rated_capacity_kva` is **NULL** → every nameplate/target/rated/contracted/
critical-threshold leaf is genuinely absent.

The roster-driven cards (14, 16, 17) correctly roll members up and DID fill their core
data. Card 15 is the outlier: it binds `fields` `source=live` **directly to the panel
feedbacks table**, which has none of those columns → all-blank. This is the page's one
real fixable structural gap.

---

## Card 14 — Cumulative Energy  (core data FILLED via member roll-up)

Real values present: `value`/`metrics[0]`/`segments[0]` active = **2,278,509 kWh**,
`metrics[1]`/`segments[1]` reactive = **10,729 kVArh**. Member roll-up works.

| leaf | ref | v48 | verdict | why |
|---|---|---|---|---|
| card.view.target | 175.6 | — | honest_absent | no nameplate/subsidy target; panel rated_capacity NULL |
| card.view.capacityValue | 175.6 | — | honest_absent | panel rated_capacity NULL |
| card.view.markerPct | 96.24 | — | honest_absent | needs rated capacity (absent) |
| card.view.markerLabel.value | 169 | — | honest_absent | target marker; rated absent |
| card.view.insight | subsidy/rated narrative | — | honest_absent | narrative keyed on absent subsidy + rating |
| card.view.metrics[2].value (SEC kWh/t) | 97 | — | honest_absent | specific-energy needs production tonnage — no such data on any meter |

fix_family: `nameplate_target_absent` (target/capacity/marker/insight), `sec_production_absent` (SEC)

---

## Card 16 — Energy Consumption Trend  (today's bucket FILLED)

Real values present for the single materialized bucket (Jul 15): ups=47,878, bpdp=121,550,
active=169,428, reactive=120 kWh.

- **HHF leaves** (`legend[2].value`, all `points[*].hhf`): `honest_absent`. No HHF load
  feeder in the 317 roster. HHF gic tables exist (`gic_01_n10_hhf_01_..._600kvar_p1` etc.)
  but they are **APFC / harmonic-filter capacitor banks** (measured avg 0.3 kW real,
  −15.9 kVAr capacitive) — not consumption feeders. No true analog for the demo's HHF
  load line. fix_family `hhf_feeder_absent`.
- **rated / contracted** (`points[*].rated`, `points[*].contracted`): `honest_absent` —
  panel rated_capacity NULL, no contracted-capacity figure. fix_family `nameplate_rating_absent`.
- **points[1..6].{ups,bpdp,active,reactive,total} + totals[1..6].value + baseRatio +
  selectedLabel**: `windowing`. The 7-day window collapsed to **1 daily bucket** (insight
  says "over 1 buckets — peak Jul 15"). Member data spans **8 distinct days** in the window,
  so the earlier daily buckets should exist. FIXABLE — the energy-delta daily roll-up only
  emitted today's bucket. fix_family `trend_single_bucket_windowing`.

---

## Card 15 — Today live power analysis  (ALL BLANK — mis-bound to control table)

Every field binds `source=live` to a power column **on `pcc_panel_1_feedbacks`, which has
no such column**. The same quantities exist with data on the member feeders (roll-up proven
by cards 14/17). This card should be a panel-aggregate member roll-up like its siblings.

| leaf | bound column | ref | verdict | correct source |
|---|---|---|---|---|
| card.view.value | apparent_power_total_kva | 1,675 | mis_bind | Σ members apparent_power_total_kva (col+data present) |
| card.view.metrics[0].value | active_power_total_kw | 1,491 | mis_bind | Σ members active_power_total_kw |
| card.view.metrics[1].value | reactive_power_total_kvar | 764 | mis_bind | Σ members reactive_power_total_kvar |
| card.view.segments[0].value | active_power_total_kw | 1490.9 | mis_bind | Σ members active_power_total_kw |
| card.view.segments[1].value | reactive_power_total_kvar | 763.5 | mis_bind | Σ members reactive_power_total_kvar |
| card.view.metrics[2].value | loadFactorPct (derived) | 72.9 | derivation_gap | input active_power null due to mis-bind; computable once power bound to member roll-up |
| card.view.insight | live-apparent-vs-rated narrative | (blank) | derivation_gap | power values absent; partly also needs rating (absent) |
| card.view.capacityValue | — | 2000 | honest_absent | panel rated_kva NULL |
| card.view.markerPct | — | 70 | honest_absent | needs rated capacity (absent) |
| card.view.markerLabel.value | — | 1,400 | honest_absent | needs rated capacity (absent) |

fix_family: `panel_direct_bind_should_be_member_rollup` (value/metrics[0,1]/segments/insight),
`loadfactor_derivation_gap` (load factor), `nameplate_rating_absent` (capacity/marker).

---

## Card 17 — Daily Power Demand by Feeder  (core FILLED via member roll-up)

Real values present: ups/bpdp hourly series across many buckets; `stats[0]` worst-peak =
3,194 kW at 15 01:00; legend ups=2291, bpdp=567 kW.

| leaf | ref | v48 | verdict | why |
|---|---|---|---|---|
| stats[1].value (load-factor) | 92 | — | derivation_gap | peak available (3194), avg derivable from member series → load factor computable; FIXABLE |
| stats[1].sub | at 17 | (blank) | derivation_gap | companion label of the load-factor stat |
| demand.view.insight | worst-peak + load-factor narrative | (blank) | derivation_gap | worst peak available but load factor blank → narrative partly blocked |
| legend[2].value (HHF) | 152 | — | honest_absent | HHF = APFC capacitor bank, no load feeder (see card 16) |
| points[0..6].hhf | 92..152 | null | honest_absent | HHF load feeder absent |
| demand.view.criticalKw | 270 | — | honest_absent | critical/rated threshold; panel rated NULL |
| demand.selectedLabel | 21 (Today) | null | windowing | selected-bucket label not set (chrome-ish) |

fix_family: `loadfactor_derivation_gap` (stats[1]/insight), `hhf_feeder_absent` (hhf/legend),
`nameplate_rating_absent` (criticalKw), `windowing_label` (selectedLabel).

---

## Synthesis for this page

1. **`panel_direct_bind_should_be_member_rollup`** (card 15, 5 mis_bind leaves) — the one
   structural defect: card 15 reads power off the panel *control* table. Rebind to member
   roll-up (Σ of load feeders' apparent/active/reactive power) exactly as cards 14/16/17 do.
   This unblocks load-factor and the insight too.
2. **`loadfactor_derivation_gap`** (cards 15 & 17) — load factor stays blank even where the
   demand series is fully populated (card 17). Wire the loadFactorPct derivation off the
   rolled member power series (peak + average both available).
3. **`trend_single_bucket_windowing`** (card 16) — 7-day daily trend collapsed to 1 bucket
   despite 8 days of member data; the daily energy-delta roll-up must emit all buckets.
4. **`nameplate_rating_absent`** (all 4 cards) — every target/capacity/rated/contracted/
   critical leaf is honestly blank because panel 317 has no `rated_capacity_kva`. Not
   fixable from meter data; would need a nameplate/contract figure seeded.
5. **`hhf_feeder_absent`** (cards 16 & 17) — the HHF demo line has no real load feeder;
   physical HHF feeders are APFC capacitor banks (~0 kW). Correctly blank.
6. **`sec_production_absent`** (card 14) — SEC (kWh/t) needs production tonnage; no such
   signal exists. Correctly blank.
