# Asset deep tabs — WebSocket contract (history widgets)

The deep transformer tabs (Thermal & Life, Loss Analysis, Utilization) are
widget-envelope pages — same envelope as the Overview (see
`ASSET_OVERVIEW_WEBSOCKET.md`), but with two **filtered** widget kinds. Each
filtered widget owns its filter independently (same vocabulary, per-widget
state) and is driven by a mid-connection command.

Producer: `assets/consumers/<type>/`, dispatchers extend `_BaseWidgetDispatcher`
(`_widgets_base.py`); time-filter vocab in `_timefilters.py`; SQL in
`services.fetch_bucketed` / `fetch_tod_peaks`.

---

## Widget kinds (beyond the live gauges/KPIs)

| Kind | Filter | Command | Block |
|---|---|---|---|
| `BucketedSeries` | **range × sampling** | `{"widget","range","sampling"[,"start","end"]}` | `{range, sampling, series:[{label, …}]}` |
| `WindowedKpi` | **window** (today/week/month) | `{"widget","range"}` | strategy-defined dict |
| `StaticKpi` / `LiveBars` / `LiveGauge` | none (live tick) | — | `{col: value, …, status?}` |
| `config` (static) | none | — | nameplate + thresholds, sent once in `snapshot` |

Frames are the same as Overview: `snapshot` (layout + all blocks), `tick`
(live widgets), `widget_update` (filtered widgets, on slow poll or after a
command), `error`.

### range × sampling vocabulary (BucketedSeries)
| `range` | allowed `sampling` | bucket labels |
|---|---|---|
| `today`, `yesterday` | `hourly` (3 h) · `shift` (8 h) | `HH:MM` / `A`,`B`,`C` |
| `last-7-days` | `daily` | `D-6 … Today` |
| `last-30-days`, `this-month`, `last-month` | `daily` · `weekly` | `DD` / `W-N`,`This W` |
| `custom-range` | any (needs `start`+`end`) | per sampling |

Illegal combos → `error`. Edges anchor to IST (midnight / Mon / 1st).

---

## Endpoint — Thermal & Life

```
ws://<host>:8888/ws/asset/{asset_id}/lt-transformer-thermal/
```
Only valid for `lt_transformer` assets (else `4404`).

### Widgets

| Widget | Kind | Source |
|---|---|---|
| `config` | static | `transformer_config`: `rated_kva`, `design_life_years`, `rated_efficiency_pct`, `hotspot_warning_temp_c`, `hotspot_critical_temp_c`, `oil_high_temp_c`, `winding_high_temp_c`, `ambient_high_temp_c` |
| `kpi_cards` | StaticKpi (live) | `thermal_stress_pct`, `total_loss_with_aux_kw`, `kpi_kw_load_pct_of_rated`, `efficiency_pct`, `remaining_useful_life_years`, `insulation_life_consumed_pct`, `faa_acceleration_factor`, `derated_capacity_kva`, `derating_headroom_kva` |
| `thermal_monitor` | LiveBars (live) | `winding_temperature_c`, `top_oil_temperature_c`, `winding_hotspot_temperature_c`, `ambient_temperature_c` + each `*_thermal_status`; hotspot peak `peak_hotspot_today_c`/`_at_time` |
| `thermal_series` | BucketedSeries | per bucket: `hotspot`=MAX `winding_hotspot_temperature_c` · `oil`=MAX `top_oil_temperature_c` · `load`=AVG `kpi_kw_load_pct_of_rated` · `efficiency`=AVG `efficiency_pct`. Default `last-7-days`/`daily`. |
| `peak_heatmap` | WindowedKpi | `{slots:[00-03…21-24], rows:{winding_hv, oil_top, hot_spot, ambient}}` — per-3h-slot MAX over today/week/month |

`thermal_series` block:
```jsonc
{ "range":"last-7-days", "sampling":"daily",
  "series":[ {"label":"D-6","hotspot":null,...}, {"label":"Today","hotspot":90.1,"oil":58.4,"load":68.7,"efficiency":98.45} ] }
```
`peak_heatmap` block:
```jsonc
{ "range":"today", "slots":["00-03",…,"21-24"],
  "rows":{ "hot_spot":[89.2,90.1,89.2,89.8,null,null,null,null], "winding_hv":[…], "oil_top":[…], "ambient":[…] } }
```

Flags to confirm (data/mapping): `faa_acceleration_factor` reads ~0.1 (not the
design's "3.2x" — may want `aging_rate_pu` instead); LOSS uses
`total_loss_with_aux_kw`; the italic insight text is treated as frontend, not
backend.

---

## Endpoint — Loss Analysis

```
ws://<host>:8888/ws/asset/{asset_id}/lt-transformer-loss/
```
`lt_transformer` only.

| Widget | Kind | Source |
|---|---|---|
| `loss_inspector` | WindowedKpi — **two filters**: `range` + `bucket`. Ranges: `today`, `yesterday`, `last-7-days` (7D), `last-30-days` (30D), `this-month`, `last-month`, `last-90-days` (3M), `last-365-days` (1Y), `custom-range`. Bucket label adapts per range (3h slots for today/yesterday, days for 7D/30D/this-month/last-month, weeks for 3M/1Y; custom-range picks sampling from duration: ≤2 d hourly · ≤45 d daily · else weekly). | for the picked bucket: `totals` = AVG of `copper_loss_kw`/`iron_loss_kw`/`stray_loss_kw`/`cooling_aux_loss_kw`/`total_loss_with_aux_kw` + `efficiency_pct`; `focus` = `kpi_kw_load_pct_of_rated`, `k_factor`, `remaining_useful_life_years`; `drivers` list with `pct`-of-total + badge. Response includes `range`, `sampling`, `bucket`, `available_buckets`, `has_data`. |
| `loss_timeline` | BucketedSeries (range×sampling) | per bucket: `copper`/`core`/`stray`/`aux`/`total`/`efficiency`/`load` (all AVG) + `now` legend |
| `performance_map` | WindowedKpi (`last-24h`) | last-24h hourly scatter `points:[{load_pct, actual_kw, expected_kw, efficiency_pct}]` + live `operating_point:{load_pct, loss_kw, input_kw, output_kw, loss_pct, delta_vs_curve, components{cu,core,harm,aux}}` |
| `config` (static) | — | `best_zone` 55-75% · `watch_zone` 75-90% · `critical_zone` >90% or efficiency <98.4% (chart bands) |

`loss_inspector` commands (any combination, all optional):
`{widget:"loss_inspector", range:"last-30-days"}` · `{widget:"loss_inspector",
bucket:"D-3"}` · `{widget:"loss_inspector", range:"custom-range",
start:"2026-05-27", end:"2026-06-01"}`. Empty `bucket` ("" or unset) → the
strategy auto-picks the latest slot with data. Slots with no data return
`has_data:false`. Scatter quality on `performance_map` depends on load variance
over the 24 h window.

---

## Endpoint — Utilization

```
ws://<host>:8888/ws/asset/{asset_id}/lt-transformer-utilization/
```
`lt_transformer` only. Simpler tab — no range×sampling dropdown.

| Widget | Kind | Source |
|---|---|---|
| `config` | static | `transformer_config.rated_kva` + threshold lines `load_watch_pct`=70, `load_warning_pct`=85, `nameplate_pct`=100 |
| `kpi_cards` | StaticKpi (live) | TUF: `tuf_lifetime_pct` + `max_demand_lifetime_kva` · Load: `kva_utilization_pct` + `demand_present_kva` · Peak today: `peak_load_pct_today`(+`_at_time`) + `demand_max_kva` · Efficiency: `efficiency_pct` + `lv_output_kw`/`hv_input_kw` |
| `load_history` | WindowedKpi (fixed `24h`) | trailing-24h **hourly** load %: `{range:"24h", series:[{label:"HH:MM", load_pct, peak_pct}], peak_pct, avg_pct}` (load % = `kva_utilization_pct`) |

`load_history` ref lines (70/85/100) come from the `config` block. The window
is fixed at 24h (the only `range` is `"24h"`); it slides on the slow poll.

---

## Endpoint — UPS Battery & Autonomy

```
ws://<host>:8888/ws/asset/{asset_id}/ups-battery-autonomy/
```
`ups` only. Two live blocks + two `BucketedSeries` history charts (each with its
own range×sampling filter — the descriptor ships `ranges` + `sampling_by_range`).

| Widget | Kind | Source |
|---|---|---|
| `battery_anatomy` | StaticKpi (live) | `ups_battery_soc_pct`, `ups_battery_dc_bus_voltage_v`, `ups_battery_dc_current_a`, `ups_battery_electrical_status`, `ups_battery_temperature_c`, `ups_battery_peak_temp_c` |
| `autonomy_readiness` | StaticKpi (live) | `ups_autonomy_index`, `ups_autonomy_limited_by`, `ups_autonomy_min`, `ups_runtime_target_min`, `ups_load_headroom_pct`, `ups_inverter_status`, `ups_operating_mode` |
| `battery_history` | BucketedSeries | per bucket: `limiting`/`soc`/`dc_bus`/`thermal` = AVG of the `ups_battery_*_score` cols · `peak_temp`=MAX `ups_battery_peak_temp_c`. Plus `now:{…, mode_state}` legend (latest). |
| `autonomy_history` | BucketedSeries | per bucket: `autonomy_index`=AVG · `runtime_score`=AVG · `load_pressure`=AVG `ups_kva_used_pct` · `min_runtime`=MIN. Plus `now:{runtime_now, load_headroom, transfer_state, …}` legend. |

Both history blocks: `{range, sampling, series:[{label, …}], now:{…}}`. `now` is
the latest-row legend ("Now" column in the UI), refreshed on the slow poll.

---

## Endpoint — UPS Source & Transfer

```
ws://<host>:8888/ws/asset/{asset_id}/ups-source-transfer/
```
`ups` only. The richest tab — two live blocks, a windowed envelope, and two
bucketed charts (each with its own filter).

| Widget | Kind | Source |
|---|---|---|
| `transfer_index` | StaticKpi (live) | `ups_transfer_composite_score`, `ups_transfer_readiness_status`, `ups_transfer_limiting_permissive`, `ups_input_permissive_score`, `ups_bypass_permissive_score`, `ups_sync_permissive_score` |
| `sync_score` | StaticKpi (live) | `ups_bypass_frequency_hz` (measured), `ups_sync_deviation_hz`; target 50 Hz + penalty −1200/Hz from `config` |
| `activity_30d` | BucketedSeries (`last-30-days`/`daily`) | per-day transfer count = Δ`ups_transfers_lifetime` (extra-aggregate); `now:{lifetime, last_30d, days_since_last, last_type}` |
| `score_envelope_24h` | WindowedKpi (`24h`) | min/max/avg of `ups_transfer_composite_score` over 24h |
| `composite_timeline` | BucketedSeries (range×sampling) | per bucket: `input_v`/`bypass_v`/`input_i`/`bypass_hz`/`readiness` (AVG) · `transfer_events` (Δ counter) · `mode` (last `ups_operating_mode` per bucket) + `now` legend |
| `config` (static) | — | `sync_target_hz`=50, `sync_penalty_per_hz`=−1200, `readiness_ready`=70, `input_v_low`=390 (chart ref lines) |

`composite_timeline` folds the **mode band** into its series (`mode` per bucket,
via `bucket_last`) so the chart and the mode timeline share one filter. Known
gap: the 24h envelope's "when min/max occurred" timestamps aren't computed yet
(min/max/avg only); the insight text is frontend.

---

## Endpoint — UPS Output Load & Capacity

```
ws://<host>:8888/ws/asset/{asset_id}/ups-output-capacity/
```
`ups` only. Same shape as Source & Transfer.

| Widget | Kind | Source |
|---|---|---|
| `capacity_index` | StaticKpi (live) | `ups_capacity_headroom_score`, `ups_capacity_limiting_factor`, `ups_capacity_kva_score`, `ups_capacity_kw_score`, `ups_capacity_current_score` |
| `kw_score` | StaticKpi (live) | target `ups_kw_capacity_target_kw` · measured `active_power_total_kw` · free `ups_kw_headroom_kw` · penalty `power_factor_total` |
| `activity_30d` | BucketedSeries (`last-30-days`/`daily`) | per-day AVG load % (`ups_kva_used_pct`); `now:{peak_pct, avg_pct}` |
| `score_envelope_24h` | WindowedKpi (`24h`) | min/max/avg of `ups_capacity_headroom_score` |
| `composite_timeline` | BucketedSeries (range×sampling) | per bucket: `output_kva`=AVG `apparent_power_total_kva` · `headroom_pct`=AVG `ups_capacity_headroom_score` · `mode` (last per bucket) + `now` legend |
| `config` (static) | — | `rated_kva` + `overload_pct`=125, `watch_pct`=50, `headroom_floor_pct`=30 (ref lines) |


