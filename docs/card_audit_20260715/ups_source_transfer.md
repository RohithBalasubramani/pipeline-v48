# Card audit — UPS Source Transfer

- page_key: `ups-asset-dashboard/source-transfer`
- meter: `gic_01_n3_ups_01_p1` (single 3-phase UPS meter)
- gaps in gaps.json for page: 142 leaves across cards 54/55/56

## Meter reality (probed, last 7 days)
```
rows=24908  voltage_avg=234.7  voltage_ll_avg=406.5  current_avg=264.3  frequency_hz 49.50..50.30 (avg 49.98)
active_power_total_kw filled, voltage/current/frequency ALL non-null 24908/24908
```
The meter DOES carry `voltage_ll_avg` (~406.5 V line-line, matches ref inputVoltage ~415 V),
`current_avg` (264 A), and `frequency_hz`. This DIRECTLY CONTRADICTS card 56's DI notes
("no voltage column", "no current column") — those are wrong.

What the meter does NOT have: any composite readiness/permissive SCORE column, transfer-EVENT
log, or a SEPARATE bypass-source voltage/frequency (it is one meter = one source).

---

## Card 54 — Transfer readiness (TilePayload)
All leaves are composite readiness / permissive SCORES or trend deltas. No score column, no
recovery fn on a single UPS meter. V48 correctly blanks.

| leaf | ref | verdict | fix_family |
|---|---|---|---|
| readiness.score (96) | 96 | honest_absent | readiness_score_absent |
| readiness.metrics[0].value input permissive (98) | 98 | honest_absent | permissive_score_absent |
| readiness.metrics[1].value bypass permissive (100) | 100 | honest_absent | permissive_score_absent |
| readiness.metrics[2].value sync permissive (100) | 100 | honest_absent | permissive_score_absent |
| readiness.insight | narrative | honest_absent | narrative_absent |
| readiness.deltaLabel (+36) | +36 | honest_absent | trend_delta_absent |
| readiness.scoreMax (100) | 100 | chrome_noise | static_frame_constant |
| readiness.readyMarkerPct (60) | 60 | chrome_noise | static_frame_constant |

scoreMax/readyMarkerPct are fixed gauge-frame constants (not meter data) — deterministically
canonical-fillable, not a data gap.

## Card 55 — Activity (ProgressPayload)
Transfer-EVENT counts. This meter logs time-series measurements, not transfer events. All
event-count leaves are genuinely unmeasured.

| leaf | ref | verdict | fix_family |
|---|---|---|---|
| activity.count30d (2) | 2 | honest_absent | transfer_events_absent |
| activity.lastTransferDays (5) | 5 | honest_absent | transfer_events_absent |
| activity.lifetimeTransfers (15) | 15 | honest_absent | transfer_events_absent |
| activity.metrics[0].value (5) | 5 | honest_absent | transfer_events_absent |
| activity.metrics[1].value (15) | 15 | honest_absent | transfer_events_absent |
| activity.insight | narrative | honest_absent | narrative_absent |
| activity.windowDays (30) | 30 | chrome_noise | static_frame_constant |
| activity.tickStartLabel (-30d) | -30d | chrome_noise | static_frame_constant |

## Card 56 — Source Transfer — Composite (SeriesPayload)
24 time points × 5 quantities. Verdicts are per-QUANTITY (apply identically across all 24 points).

| quantity (points[*]) | ref | verdict | fix_family | note |
|---|---|---|---|---|
| inputVoltageV | ~415 V | **binding_gap** | input_voltage_bindable | `voltage_ll_avg` exists (406.5 V, matches). Unbound slot + DI wrongly claims "no voltage column". FIXABLE: bind source=live → voltage_ll_avg. |
| inputCurrentA | 44-54 A | **binding_gap** | input_current_bindable | `current_avg` exists (264 A). Same quantity; live magnitude differs from demo. FIXABLE: bind → current_avg. |
| bypassVoltageV | ~415 V | honest_absent | bypass_source_absent | Single meter = one source; no separate bypass-line voltage. |
| bypassFrequencyHz | ~49.9-50.1 | honest_absent | bypass_source_absent | `frequency_hz` exists but is THIS meter's own freq, not a distinct bypass source. Attributing it to "bypass" would be a mis-label. |
| readiness | 68-96 | honest_absent | readiness_score_absent | Composite score, not measured; loadFactorPct is wrong-quantity proxy. |

Other card-56 leaves:
| leaf | verdict | fix_family |
|---|---|---|
| composite.legend[0].value (readiness) | honest_absent | readiness_score_absent |
| composite.legend[1].value (bypass) | honest_absent | bypass_source_absent |
| composite.floor.value (70 watchpoint) | chrome_noise | static_frame_constant |
| composite.series[0].width / series[1].width | chrome_noise | grid_shape |
| composite.insight | honest_absent | narrative_absent |

card_note: The ONLY fixable data gaps on this page are card-56 `inputVoltageV` (→ voltage_ll_avg)
and `inputCurrentA` (→ current_avg): the DI mis-declares these columns absent when they carry
full 7-day data. Everything else (readiness/permissive scores, transfer events, bypass-source
readings) is genuinely unmeasured by this single UPS meter → honest_absent. Static gauge/window
constants (scoreMax, readyMarkerPct, windowDays, tickStartLabel, floor.value) are canonical-fillable
frame chrome, not data.
