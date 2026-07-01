# Asset Overview WebSocket — wire contract

The Overview tab is the one **shared** page across all asset types. Unlike the
other asset pages (flat column-row streams), it streams a **per-widget
envelope**: each card is its own block, and the Energy Consumption card carries
a **today / week / month** range filter driven by a mid-connection command.

Producer: `assets/consumers/overview/` (`OverviewDispatcher` →
`_BaseOverviewDispatcher`). Strategy per type via `STRATEGIES`. Fully wired for
`lt_transformer`; `ups` ships a headline-only block; `ht_transformer` / `dg`
are `pending` stubs until specced.

---

## Endpoint

```
ws://<host>:8888/ws/asset/{asset_id}/overview/
```

Discover the URL (no hardcoded ids): `GET /api/asset/{id}/pages/` → the
`overview` page entry carries `ws_url` / `ws_url_abs`.

Close codes: `4404` asset/page not found · `4400` asset missing `asset_id` ·
`4500` repeated backend failure.

---

## Frames

### `snapshot` (on connect)
```jsonc
{
  "type": "snapshot",
  "asset_id": 18, "asset_name": "Transformer-01", "asset_key": "MFM-TF-11",
  "asset_type": "lt_transformer", "page": "overview",
  "ts": "2026-05-29T02:13:59.674619+00:00",
  "layout": [ { "name": "power_factor", "kind": "LiveGauge", "columns": [...] }, ... ],
  "widgets": { "<name>": { ...block... }, ... }
}
```
`layout` is the ordered widget catalogue (each: `name`, `kind`, `columns`; a
`WindowedKpi` also lists `ranges` + `default_range`). `widgets` holds the
initial block for every widget.

### `tick` (live cadence, ~1 s)
Only the **live** widgets (gauges/sparks/bars/KPIs), and only when the row's
`ts` advanced:
```jsonc
{ "type": "tick", "ts": "...", "widgets": { "power_factor": {...}, "phase_balance": {...}, ... } }
```

### `widget_update` (slow cadence ~30 s, or after a range command)
The `WindowedKpi` widgets:
```jsonc
{ "type": "widget_update", "widgets": { "energy_consumption": {...} } }
```

### `error`
```jsonc
{ "type": "error", "message": "..." }
```

---

## Client command — Energy Consumption range

Send to switch the filter; server replies with a `widget_update` for just that
widget:
```jsonc
// client → server
{ "widget": "energy_consumption", "range": "week" }   // "today" | "week" | "month"
```
An out-of-range token returns an `error` frame; an unknown command returns an
`ack`.

---

## LT-transformer widget blocks

| Widget (`name`) | kind | Fields → source column |
|---|---|---|
| `headline_kpis` | StaticKpi | `kpi_kw_load_pct_of_rated`, `winding_hotspot_temperature_c`, `efficiency_pct`, `remaining_useful_life_years` |
| `power_factor` | LiveGauge | `power_factor_total`, `kpi_displacement_pf`, `kpi_true_pf`, `harmonic_gap`, `last_pf_drop_at`, `last_pf_drop_cause` (+`status`: Good/Fair/Poor) |
| `voltage_deviation` | LiveGauge | `kpi_voltage_deviation_pct`, `voltage_ll_avg`*, `voltage_avg` (+`status`: Normal/Elevated/Critical) |
| `grid_frequency` | LiveSpark | `frequency_hz`, `frequency_deviation_hz`, `worst_frequency_today_hz`, `worst_frequency_today_at_time` (+`status`: Stable/Fair/Unstable) |
| `phase_balance` | LiveBars | `current_unbalance_pct`, `current_r/y/b`, `current_neutral`, `current_avg` (+`status`: Balanced/Watch/Unbalanced) |
| `harmonics` | LiveGauge | `k_factor`, `harmonic_loss_factor_fhl`, `thd_compliance_ieee519`, `thd_compliance_v_avg`, `thd_compliance_i_avg` |
| `kw_load` | StaticKpi | `kpi_kw_load_pct_of_rated`, `active_power_total_kw`, `peak_load_pct_today`(+`_at_time`), `kpi_demand_headroom_kva`/`_pct`, `kpi_load_factor` |
| `energy_consumption` | WindowedKpi | see below |

(The AI Summary card is a frontend concern — not produced by this WebSocket.)

`energy_consumption` block:
```jsonc
{
  "range": "today",
  "active_kwh": 6421.5,                 // MAX-MIN of active_energy_import_kwh over the range
  "reactive_kvarh": 452.92,             // reactive_energy_{today|this_week|this_month}_kvarh
  "subsidy_target_kwh": 12000.0,        // transformer_config.subsidy_{today|this_week|this_month}_kwh
  "energy_cost": 46363.23,              // derived: active_kwh × tod_rate_inr_per_kwh
  "tod_rate_inr_per_kwh": 7.22,
  "tod_period": "Normal",
  "budget_kwh": -237425.3               // cumulative_vs_budget_kwh (latest)
}
```

\* `voltage_ll_avg` (L-L, matches the design's "Actual Voltage") is **not
populated in the current sim**; `voltage_avg` (L-N) is. Nominal voltage comes
from `transformer_config.nominal_voltage_v` (REST), not the stream.

Known gap to revisit: there is no per-week/month energy-cost counter, so cost is
derived from the live ToD rate (period kWh × rate).

---

## UPS overview widget blocks

Endpoint `ws/asset/{id}/overview/` (shared dispatcher, `ups` strategy). All
widgets are **live** (one fetch per tick — no windowed/slow loop). Static
nameplate comes from `ups_config`.

| Widget | kind | Fields → source column |
|---|---|---|
| `headline_kpis` | StaticKpi | Loading `ups_kva_used_pct` · Battery reserve `ups_battery_reserve_pct` · Autonomy `ups_autonomy_min` · I-unbalance `current_unbalance_pct` |
| `input_output_voltage` | LiveGauge | `ups_input_voltage_v`, `voltage_avg`*, `ups_input_voltage_deviation_pct`, `ups_output_input_voltage_delta_pct`, `ups_voltage_regulation_pct` |
| `output_load` | StaticKpi | `apparent_power_total_kva`, `active_power_total_kw`, `ups_kva_used_pct`, `ups_kva_free_kva` |
| `output_frequency` | LiveSpark | `frequency_hz`, `frequency_deviation_hz`, `ups_bypass_frequency_hz`, `ups_sync_window_state` |
| `phase_balance` | LiveBars | `ups_output_phase_balance_pct`, `current_unbalance_pct`, `current_r/y/b`, `current_neutral`, `current_avg` |
| `status_chips` | StaticKpi | `ups_communication_status`, `ups_operating_mode`, `ups_inverter_status`, `ups_battery_charge_state`, `ups_bypass_sync_state`, `alerts_critical_count`, `alerts_total_count` |
| `energy_autonomy` | StaticKpi | `ups_autonomy_min`, `ups_battery_soc_pct`, `ups_battery_charge_state`, `ups_battery_dc_bus_voltage_v`, `ups_battery_dc_current_a`, `ups_battery_temperature_c`, `ups_kva_used_pct` |
| `power_quality` | LiveGauge | `thd_compliance_v_avg`, `thd_compliance_i_avg`, `ups_thd_v_exposure_pct`, `ups_thd_i_exposure_pct`, `power_factor_total`, `ups_sync_window_state`, `ups_bypass_frequency_hz` |
| `config` (static) | — | `ups_config`: `rated_kva` (or `kva_rating`), `nominal_voltage_v`, `contract_limit_kva` |

\* `voltage_avg` is the output L-N voltage (~239 V); the design's "Output 412 V"
is L-L — same L-L/L-N note as the transformer. The INCOMER/OUTGOING SLD line is
topology (`Asset.incoming`/`outgoing`), not yet wired for UPS assets.
