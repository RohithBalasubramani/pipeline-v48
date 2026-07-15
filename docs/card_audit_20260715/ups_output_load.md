# Card audit — ups-asset-dashboard/output-load-capacity

- **Meter:** `gic_01_n3_ups_01_p1` (asset GIC-01-N3-UPS-01)
- **Cards:** 57 UPS Capacity, 58 UPS Load, 59 Output Load & Capacity — Composite
- **Gap records for page:** 119 (57→7, 58→32, 59→80)

## Meter data availability (last 7 days, 24908 rows)

All measured columns are fully populated:

| column | non-null | avg |
|---|---|---|
| active_power_total_kw | 24908 | 185.3 (max 230.6) |
| apparent_power_total_kva | 24908 | 186.1 |
| power_factor_total | 24908 | 0.999 |
| current_avg | 24908 | — |
| voltage_avg (L-N) | 24908 | 234.7 |
| frequency_hz | 24908 | 49.98 |

**Columns that DO NOT EXIST on this (or any) meter, and have no DB source anywhere in the instance:**
`load_factor_pct`, any **UPS kVA/kW rating / nameplate**, `readiness`, `bypass_voltage`, `bypass_frequency`, `transfer_count`. There is **no nameplate/rating table in neuract, cmd_catalog, equipment, or public** — verified by information_schema scan. `cmd_catalog.app_config` does not exist here either.

## Headline finding

This page is dominated by **honest gaps**, not binding gaps. Almost every blank leaf is a **load-factor / capacity / headroom / readiness / bypass** quantity. Each of those needs either:
1. a **UPS nameplate rating** (to turn measured kW/kVA into a load%/headroom/score), which does not exist as data anywhere, or
2. a **readiness / bypass / transfer-count** column, which this line meter simply does not carry.

The CMD_V2 reference "fills" these because its storybook defaults are **demo constants**, not values read from a UPS-rating source. V48 is **correct to blank them** (per the per-leaf honesty rule). There is **no fabrication-free fix** for the rating-dependent leaves on this page.

The single "data-exists" flag (`bypassFrequencyHz`, quantity=frequency) is a **role mismatch**: `frequency_hz` is this meter's input/line frequency, not a static-bypass measurement, and the sibling bypass-voltage leaf is genuinely absent — binding it would mislabel input freq as bypass freq. Kept honest.

---

## Card 57 — UPS Capacity (TilePayload, snapshot)

Bound & filling: none of the flagged leaves. `scoreCells` labels/units are chrome.

| leaf | ref | verdict | why |
|---|---|---|---|
| capacity.insight | narrative | honest_absent | Sentence composed from capacity-headroom, which needs a rating (absent). |
| capacity.deltaLabel | -8 | honest_absent | Snapshot card, no time-series delta binding. `snapshot_no_delta`. |
| capacity.scoreCells[0].value | 52 | honest_absent | fn `kpiKwLoadPctOfRated` = kW load% of rated; **no rating** → rating-nulled. |
| capacity.scoreCells[1].value | 58 | honest_absent | fn `kpiLoadFactor`; needs rating. |
| capacity.scoreCells[2].value | 52 | honest_absent | fn `loadFactorWindowPct`; needs rating. |
| capacity.readyMarkerPct | 60 | honest_absent | Const literal in a data slot; no nameplate/app_config source. `const_no_nameplate_source`. |
| capacity.capacityHeadroom | 52 | honest_absent | Headroom = rating − load; **no rating**. |

`fix_family` cluster: **loadfactor_rating_nulled** (+ snapshot_no_delta, const_no_nameplate_source).

## Card 58 — UPS Load (ProgressPayload)

Bound & filling correctly (NOT gaps): `scoreCells[0].value` = active_power_total_kw (Load kW), `scoreCells[2].value` = power_factor_total (PF), `averageLoadPct` = derived loadFactorPct — note this derived leaf ALSO depends on a rating; if it fills it is using a code-default rating, worth a follow-up check.

| leaf | ref | verdict | why |
|---|---|---|---|
| load.insight | "kW healthy — 115 kW headroom" | honest_absent | Headroom needs rating. |
| load.sparkline[0..29].loadPct (30 pts) | 30–64% | honest_absent | loadPct series = active_power_total_kw / **rating**. Base column has data; rating absent → cannot convert to %. `loadfactor_rating_nulled`. |
| load.scoreCells[1].value | 115 | honest_absent | Headroom kW = rating − load; **no rating**. |

`fix_family` cluster: **loadfactor_rating_nulled**. (30 sparkline points collapsed into one verdict row below.)

## Card 59 — Output Load & Capacity — Composite (SeriesPayload, 24h hourly)

Bound & filling (NOT gaps): `points[*].inputCurrentA`=current_avg, `points[*].inputVoltageV`=voltage_avg, `kpiCells[0]`=voltage_avg. **Note:** inputVoltageV/kpiCells[0] are bound to `voltage_avg` = L-N (~234), while the EMS demo shows ~415 (L-L). `voltage_ll_avg` column exists on this meter — a candidate rebind for a truer input-voltage number (not a blank, so out of gap scope, flagged for owner).

| leaf | ref | verdict | why |
|---|---|---|---|
| composite.floor.value | 70 | honest_absent | Readiness floor; **no readiness column** (load used as proxy → blanked). |
| composite.legend[0].value | 58 | honest_absent | Readiness legend; no readiness column. |
| composite.legend[1].value | 50 | honest_absent | Bypass-voltage legend; no bypass column. |
| composite.points[*].readiness (24) | 48–56 | honest_absent | No readiness column; `active_power_total_kw` measures power, not readiness. |
| composite.points[*].bypassVoltageV (24) | ~414–416 | honest_absent | No bypass-voltage column on this meter. |
| composite.points[*].bypassFrequencyHz (24) | ~50 | honest_absent | `frequency_hz` EXISTS with data but is **input/line** freq, not static-bypass; sibling bypass-voltage is absent → binding = role mislabel. Kept honest. `bypass_role_no_column`. |
| composite.series[0].width / [1].width | 2 / 1.8 | chrome_noise | Chart line-width styling, not data. |
| composite.insight | narrative | honest_absent | Composed from readiness/headroom proxies (absent). |
| composite.kpiCells[1].value | 414.9 | honest_absent | Bypass-voltage KPI; no bypass column. |
| composite.kpiCells[2].value | 4 | honest_absent | Transfer-count KPI; no transfer-count column. |

`fix_family` clusters: **readiness_no_column**, **bypass_no_column**, **bypass_role_no_column**, **transfer_count_no_column**, chrome.

---

## Verdict roll-up

- **honest_absent:** everything except the 2 chart-width leaves. Root causes: (a) no UPS nameplate rating anywhere → all load-factor/capacity/headroom leaves; (b) no readiness/bypass/transfer-count columns on a line meter.
- **chrome_noise:** composite.series[*].width (2 leaves).
- **No frame_declared_bindable / binding_gap / mis_bind fixes on this page.** The one "data-exists" auto-flag (bypassFrequencyHz) is a genuine role mismatch and correctly left honest.
- **Secondary owner flags (not blanks):** (1) inputVoltageV/kpiCells[0] bound to `voltage_avg` (L-N ~234) vs EMS L-L ~415 — consider `voltage_ll_avg`; (2) card 58 `averageLoadPct` derived leaf depends on a rating — confirm it is not silently using a hardcoded default.
