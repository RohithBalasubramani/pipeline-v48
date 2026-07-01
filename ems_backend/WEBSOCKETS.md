# WebSocket API Reference

Live and historical streams for the LT-Panel dashboard, served by Django Channels at:

- **Tailscale:** `ws://100.90.185.31:8090`
- **LAN:**       `ws://192.168.1.20:8090`
- **Local:**     `ws://localhost:8090`

All endpoints take an `mfm_id` (Django MFM primary key) in the path. The consumer resolves it to `(db_link, table_name, panel_id)` and queries the simulator's `panel_readings` table directly.

---

## Common conventions

### Message envelope

Every consumer emits JSON with a `type` field. Three shapes are used:

| `type` | When | Body |
|---|---|---|
| `snapshot` | On connect (and on filter change for history streams) | full window/range data |
| `tick` | Live consumers, when a new sample lands in the DB | one row + status |
| `update` | History consumers, every `refresh` seconds | full bucket array (recomputed) |
| `error` | Any failure | `{message}` |

### Status labels

Live consumers attach a `status` block alongside the row when thresholds apply. Each entry maps a column name to a string label like `"Normal"`, `"Watch"`, `"High"`, `"Rising"`, `"Falling"`, `"Pass"`, `"Fail"`. Thresholds are defined in [`lt_panels/consumers.py`](lt_panels/consumers.py) and are easy to tweak.

### Default window / refresh

| Consumer family | Window | Refresh tick |
|---|---|---|
| Live (real-time monitoring, energy-power, voltage-current, power-quality-summary, distortion-harmonics) | 60 s rolling | every 1 s, on new row |
| History (demand-profile, voltage-history, current-history) | resolved range (today/this_week/this_month/last_24h…) | every 30 s, full snapshot recompute |

### Range presets (history endpoints)

| `range` value | Resolves to |
|---|---|
| `today` | midnight UTC → now |
| `yesterday` | midnight UTC of prev day → midnight today |
| `this_week` | this Monday 00:00 → now |
| `this_month` | 1st of month 00:00 → now |
| `last_24h` | now − 24 h → now |
| `last_7d` | now − 7 d → now |
| `last_30d` | now − 30 d → now |

`start` + `end` (ISO 8601) override the preset.

### Sampling values (history endpoints)

`minute`, `5min`, `15min`, `30min`, `hour`, `day`.

### Live re-config (history endpoints)

Send a JSON message to update the range/sampling without reconnecting:
```json
{"range": "this_week", "sampling": "day"}
```
or
```json
{"start": "2026-04-01T00:00:00Z", "end": "2026-04-30T23:59:59Z", "sampling": "hour"}
```
Server immediately resends a `snapshot` with the new params.

---

## Page 1 — Real Time Monitoring

One live WebSocket covering the entire page.

### `ws/mfm/{mfm_id}/real-time-monitoring/`

**Purpose:** Power & Energy panel + Voltage Monitor + Current Monitor (the 3 live cards).

**Query params** (all optional)

| Param | Default | Notes |
|---|---|---|
| `window` | `60` | seconds of history sent on connect |
| `interval` | `1` | poll cadence (seconds) |
| `columns` | (default 19-col set) | comma-separated list to override |

**Default columns** (19)

```
# Power & Energy
active_power_total_kw, reactive_power_total_kvar, apparent_power_total_kva,
active_energy_import_kwh, reactive_energy_import_kvarh,
rate_of_change_power_kw_per_min,
# Voltage
voltage_r_n, voltage_y_n, voltage_b_n,
voltage_avg, voltage_max, voltage_min,
# Current
current_r, current_y, current_b, current_neutral,
current_avg, current_max, current_min
```

**Snapshot payload**
```json
{
  "type": "snapshot",
  "mfm_id": 6,
  "mfm_name": "UPS-01 CL:600KVA",
  "panel_id": "MFM-UPS-01",
  "window_seconds": 60,
  "columns": ["active_power_total_kw", "..."],
  "count": 60,
  "rows": [
    {"ts": "2026-05-08T12:34:56+05:30", "panel_id": "MFM-UPS-01",
     "active_power_total_kw": 367.36, "voltage_avg": 239.23, ...},
    ...
  ],
  "status": {}
}
```

**Tick payload**
```json
{"type": "tick", "row": { "ts": "...", ...19 columns... }, "status": {}}
```

This consumer does **not** emit a `status` block (no threshold logic on this tab).

---

## Page 2 — Energy & Power

Two WebSockets, one per visual section.

### `ws/mfm/{mfm_id}/energy-power/` — left section (live KPIs + status)

**Purpose:** Today's Energy, Input vs Output, Power Profile, KPIs (SEC, Load Factor, Peak Demand, Power Rate).

**Query params**

| Param | Default | Notes |
|---|---|---|
| `window` | `60` | seconds of history on connect |
| `interval` | `1` | poll cadence |

**Columns** (21)

```
# Today's energy
active_energy_today_kwh, reactive_energy_today_kvarh, apparent_energy_today_kvah,
cumulative_vs_budget_kwh, kpi_kw_load_pct_of_rated,
# Input vs Output
hv_input_kw, lv_output_kw, active_power_loss_kw, active_power_loss_pct,
# Power profile
active_power_total_kw, reactive_power_total_kvar, apparent_power_total_kva,
# KPIs
specific_energy_consumption, kpi_load_factor,
peak_demand_today_kw, peak_demand_at_time,
power_rate_kw_per_h,
# DB-stored trend status (used to fill the status block)
sec_trend_status, load_factor_trend_status,
peak_demand_trend_status, power_trend_status
```

**Status block rules**

| Column | Source | Logic |
|---|---|---|
| `specific_energy_consumption` | DB `sec_trend_status` | pass-through |
| `kpi_load_factor` | DB `load_factor_trend_status` | pass-through |
| `peak_demand_today_kw` | DB `peak_demand_trend_status` | pass-through |
| `active_power_total_kw` | DB `power_trend_status` | pass-through |
| `power_rate_kw_per_h` | threshold | `>1.0 Rising`, `<-1.0 Falling`, else `Steady` |
| `active_power_loss_pct` | threshold | `<5 Low`, `<10 Normal`, `<12 Elevated`, else `High` |
| `kpi_kw_load_pct_of_rated` | threshold | `<70 On track`, `<90 Watch`, else `Critical` |

**Tick payload**
```json
{
  "type": "tick",
  "row": {"ts": "...", "active_power_total_kw": 426.9, "active_power_loss_pct": 9.78, ...},
  "status": {
    "active_power_total_kw": "Steady",
    "power_rate_kw_per_h": "Falling",
    "active_power_loss_pct": "Normal",
    "kpi_kw_load_pct_of_rated": "Watch"
  }
}
```

---

### `ws/mfm/{mfm_id}/demand-profile/` — right section (history)

**Purpose:** Demand / Energy Profile chart (hourly bars + demand profile lines).

**Query params**

| Param | Default | Values |
|---|---|---|
| `range` | `today` | `today`, `yesterday`, `this_week`, `this_month`, `last_24h`, `last_7d`, `last_30d` |
| `start`, `end` | — | ISO 8601 (overrides `range`) |
| `sampling` | `hour` | `minute`, `5min`, `15min`, `30min`, `hour`, `day` |
| `refresh` | `30` | seconds between auto-updates |

**Columns aggregated** (avg/min/max per bucket)

```
active_power_total_kw, reactive_power_total_kvar,
demand_present_kw, demand_avg_kva, demand_max_kw
```

**Snapshot / update payload**
```json
{
  "type": "snapshot",
  "mfm_id": 6,
  "mfm_name": "UPS-01 CL:600KVA",
  "panel_id": "MFM-UPS-01",
  "range": "today",
  "start": "2026-05-08T00:00:00+00:00",
  "end": "2026-05-08T12:43:15+00:00",
  "sampling": "hour",
  "columns": ["active_power_total_kw", "..."],
  "count": 13,
  "buckets": [
    {
      "bucket": "2026-05-08T11:00:00+05:30",
      "active_power_total_kw_avg": 383.4,
      "active_power_total_kw_min": 357.5,
      "active_power_total_kw_max": 410.1,
      "reactive_power_total_kvar_avg": 139.3,
      "demand_max_kw_max": 451.5,
      "samples": 3600
    }
  ],
  "kpis": {
    "peak_demand_kw": 451.5,
    "peak_demand_at": "2026-05-08T11:00:00+05:30",
    "avg_active_kw": 383.6,
    "avg_reactive_kvar": 138.6,
    "total_samples": 44455
  }
}
```

---

## Page 3 — Voltage & Current

Three WebSockets: 1 live, 2 history.

### `ws/mfm/{mfm_id}/voltage-current/` — left section (live + status)

**Purpose:** Voltage panel (deviation, phase balance) + Current panel (phase loading, max spread, neutral, unbalance).

**Query params**

| Param | Default |
|---|---|
| `window` | `60` |
| `interval` | `1` |

**Columns** (28)

```
# Voltage panel
voltage_r_n, voltage_y_n, voltage_b_n,
voltage_avg, voltage_max, voltage_min,
voltage_r_deviation_pct, voltage_y_deviation_pct, voltage_b_deviation_pct,
kpi_voltage_deviation_pct,
voltage_unbalance_pct,
# Current panel
current_r, current_y, current_b, current_neutral,
current_avg, current_max, current_min,
current_r_deviation_pct, current_y_deviation_pct, current_b_deviation_pct,
current_unbalance_pct,
current_max_spread, current_spread_br, current_spread_ry, current_spread_by,
kpi_neutral_to_phase_ratio_pct,
sag_events_24h, swell_events_24h
```

**Status block rules**

| Column | Logic |
|---|---|
| `voltage_*_deviation_pct` (incl. overall) | `\|x\| ≤ 3 Normal`, `≤5 Watch`, else `Critical` |
| `voltage_unbalance_pct` | `<2 Normal`, `<3 Watch`, else `High` (NEMA MG-1) |
| `current_*_deviation_pct` | same band as voltage |
| `current_unbalance_pct` | `<10 Normal`, `<20 Elevated`, else `High` |
| `kpi_neutral_to_phase_ratio_pct` | `<10 Normal`, `<20 Elevated`, else `High` |

**Tick payload**
```json
{
  "type": "tick",
  "row": {"ts": "...", "voltage_r_n": 425, "voltage_unbalance_pct": 1.7, ...},
  "status": {
    "voltage_r_deviation_pct": "Normal",
    "voltage_unbalance_pct": "Normal",
    "current_unbalance_pct": "Elevated"
  }
}
```

---

### `ws/mfm/{mfm_id}/voltage-history/` — top-right chart

**Purpose:** Voltage History chart (Phase Voltage / Unbalance / Sag-Swell tabs) with right-hand KPIs.

**Query params:** identical to `demand-profile` (range, start/end, sampling, refresh).

**Columns aggregated** (avg/min/max per bucket)

```
voltage_r_n, voltage_y_n, voltage_b_n,
voltage_unbalance_pct,
kpi_voltage_deviation_pct
```

Plus per-bucket extras: `sag_events`, `swell_events` (running 24-h counters).

**KPIs returned per snapshot**

| Field | Meaning |
|---|---|
| `max_deviation_pct` + `max_deviation_at` | the bucket where `\|kpi_voltage_deviation_pct\|` was extreme |
| `max_unbalance_pct` + `max_unbalance_at` | the bucket with the worst voltage unbalance |
| `worst_spread_v` | max bucket-spread across R/Y/B (`max_phase_max − min_phase_min`) |
| `sag_events`, `swell_events` | latest counts (the running 24-h totals on the last bucket) |

**Snapshot payload**
```json
{
  "type": "snapshot",
  "range": "today", "sampling": "hour",
  "start": "...", "end": "...",
  "count": 14,
  "buckets": [
    {"bucket": "...", "voltage_r_n_avg": 410, "voltage_r_n_min": 405, "voltage_r_n_max": 420,
     "voltage_unbalance_pct_max": 1.3, "sag_events": 8, "swell_events": 2, "samples": 3600},
    ...
  ],
  "kpis": {
    "max_deviation_pct": -3.1, "max_deviation_at": "2026-05-08T10:00:00+05:30",
    "max_unbalance_pct": 3.4,  "max_unbalance_at": "2026-05-08T20:00:00+05:30",
    "worst_spread_v": 16.0,
    "sag_events": 2, "swell_events": 3
  }
}
```

---

### `ws/mfm/{mfm_id}/current-history/` — bottom-right chart

**Purpose:** Current History chart (Phase Current / Unbalance / Neutral tabs) with right-hand KPIs.

**Query params:** identical to `voltage-history`.

**Columns aggregated** (avg/min/max per bucket)

```
current_r, current_y, current_b, current_neutral,
current_avg, current_unbalance_pct
```

**KPIs returned per snapshot**

| Field | Meaning |
|---|---|
| `peak_current_a` | max across R/Y/B per-bucket peaks |
| `average_current_a` | sample-weighted mean of `current_avg` |
| `max_unbalance_pct` + `max_unbalance_at` | the bucket with the worst current unbalance |

---

## Page 4 — Power Quality

Two WebSockets: left summary KPIs (live) and right time-series + KPIs (live).

### `ws/mfm/{mfm_id}/power-quality-summary/` — left section

**Purpose:** Power Quality / Voltage Quality / Current Harmonic Stress KPI cards.

**Query params**

| Param | Default |
|---|---|
| `window` | `60` |
| `interval` | `1` |

**Columns** (10)

```
thd_compliance_ieee519,
pq_constraint,                  # already a text label (Voltage / Current / Both)
thd_movement_pct_per_h,
flicker_pst, flicker_plt,
crest_factor_voltage, crest_factor_current,
dominant_harmonic_order,
thd_compliance_v_avg, thd_compliance_i_avg
```

**Status block rules**

| Column | Logic |
|---|---|
| `flicker_pst` | `<0.5 Normal`, `<1.0 Elevated`, else `High` |
| `crest_factor_voltage`/`_current` | `\|x − 1.414\| ≤ 0.05 Normal`, `≤ 0.15 Watch`, else `High` |
| `thd_movement_pct_per_h` | `\|x\| <10 Normal`, `<30 Elevated`, else `High` |
| `thd_compliance_ieee519` | normalized `Pass` / `Fail` |
| `pq_constraint` | passes through DB value |

**Tick payload**
```json
{
  "type": "tick",
  "row": {"ts": "...", "flicker_pst": 0.74, "pq_constraint": "Both", ...},
  "status": {
    "flicker_pst": "Elevated",
    "crest_factor_voltage": "Normal",
    "crest_factor_current": "Watch",
    "thd_movement_pct_per_h": "Normal",
    "thd_compliance_ieee519": "Fail",
    "pq_constraint": "Both"
  }
}
```

> Source & Mitigation card values (Likely source, Filter state, Capacitor bank, Priority, action text) are **not** in MFM data — they require an inference / equipment-state service.

---

### `ws/mfm/{mfm_id}/distortion-harmonics/` — right section

**Purpose:** Distortion & Harmonic Profile time-series chart + Avg V/I-THD & H5/H7 KPIs, plus Phase & Load Quality Impact chart + PF / True PF / Phase Angle / K-Factor KPIs.

**Query params**

| Param | Default |
|---|---|
| `window` | `60` |
| `interval` | `1` |

**Columns** (19)

```
# Distortion & Harmonic Profile (chart series)
thd_voltage_r_pct, thd_voltage_y_pct, thd_voltage_b_pct,
thd_current_r_pct, thd_current_y_pct, thd_current_b_pct,
harmonic_3rd_pct, harmonic_5th_pct, harmonic_7th_pct,
harmonic_11th_pct, harmonic_13th_pct,
thd_compliance_v_avg, thd_compliance_i_avg,    # right-side KPIs
# Phase & Load Quality Impact (chart series)
power_factor_total, kpi_true_pf, kpi_displacement_pf,
phase_angle_deg, k_factor,
harmonic_loss_factor_fhl
```

**Status block rules**

| Column | Logic |
|---|---|
| `power_factor_total`, `kpi_true_pf`, `kpi_displacement_pf` | `≥0.95 Excellent`, `≥0.90 Good`, `≥0.85 Acceptable`, else `Poor` |
| `thd_compliance_v_avg` | `<5 Pass`, `<6 Watch`, else `Fail` |
| `thd_compliance_i_avg` | `<6 Pass`, `<8 Watch`, else `Fail` |
| `k_factor` | `<4 Normal`, `<7 Watch`, else `High` |
| `phase_angle_deg` | `\|x\| <20 Normal`, `<25 Watch`, else `High` |

**Tick payload**
```json
{
  "type": "tick",
  "row": {"ts": "...", "thd_voltage_r_pct": 6.4, "power_factor_total": 0.911, ...},
  "status": {
    "power_factor_total": "Good",
    "kpi_true_pf": "Good",
    "kpi_displacement_pf": "Good",
    "thd_compliance_v_avg": "Fail",
    "thd_compliance_i_avg": "Fail",
    "k_factor": "Normal",
    "phase_angle_deg": "Watch"
  }
}
```

---

## Endpoint matrix

| Page | Section | URL path | Type | Status labels |
|---|---|---|---|---|
| Real Time Monitoring | full page | `/ws/mfm/{id}/real-time-monitoring/` | live | — |
| Energy & Power | left (KPIs) | `/ws/mfm/{id}/energy-power/` | live | yes |
| Energy & Power | right (chart) | `/ws/mfm/{id}/demand-profile/` | history | — |
| Voltage & Current | left (live) | `/ws/mfm/{id}/voltage-current/` | live | yes |
| Voltage & Current | top-right (chart) | `/ws/mfm/{id}/voltage-history/` | history | — |
| Voltage & Current | bottom-right (chart) | `/ws/mfm/{id}/current-history/` | history | — |
| Power Quality | left (KPIs) | `/ws/mfm/{id}/power-quality-summary/` | live | yes |
| Power Quality | right (chart + KPIs) | `/ws/mfm/{id}/distortion-harmonics/` | live | yes |

---

## Error close codes

| Code | Meaning |
|---|---|
| `4400` | Bad query (missing `panel_id` on MFM, invalid sampling, bad date range) |
| `4404` | MFM with that `mfm_id` not found |
| `4500` | Backend / DB query failure |

---

## Implementation pointers

- All consumers live in [`lt_panels/consumers.py`](lt_panels/consumers.py); URL routing in [`lt_panels/routing.py`](lt_panels/routing.py).
- Live consumers extend `BaseLiveConsumer`; history consumers extend `_BaseHistoryConsumer`.
- DB helpers live in [`lt_panels/services.py`](lt_panels/services.py): `fetch_live`, `fetch_window`, `fetch_bucketed`, `resolve_range`.
- Threshold rules are plain Python functions at the top of `consumers.py` — easy to move to a config table on `Parameter` later.
- Data source: each MFM's `db_link` + `table_name` + `panel_id` filter into the simulator's `panel_readings` (currently `postgresql://postgres@/lt_panels?host=/run/postgresql`, table `panel_readings`).
