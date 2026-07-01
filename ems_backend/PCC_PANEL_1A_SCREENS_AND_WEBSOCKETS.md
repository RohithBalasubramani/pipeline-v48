# PCC Panel 1 A — screens and WebSocket endpoints

Frontend reference for **PCC Panel 1 A** (`mfm_id = 174`, name `"PCC Panel 1 A"`).
Six screens, eleven WebSocket endpoints. Use the page list endpoint
`GET /api/mfm/174/pages/` to fetch the same map at runtime.

**Hosts**

| Network | URL |
|---|---|
| Tailscale | `ws://100.90.185.31:8888` |
| LAN | `ws://192.168.1.20:8888` |
| Local | `ws://127.0.0.1:8888` |

> ⚠️ **Backend resolves PCC Panel 1 A as `pcc_panel` type by name prefix**, even
> though its underlying `mfm_type` is `lt_panel`. That's why the Energy
> Distribution and Power Quality sockets ship the **fleet-aggregate** widget
> envelope (not the per-feeder column-row shape).

---

## At-a-glance map

| # | Screen | WebSocket endpoint(s) | Shape |
|---|---|---|---|
| 1 | Overview | `overview` | Widget envelope |
| 2 | Real-Time Monitoring | `real-time-monitoring` | Column-row live stream (1-sec) |
| 3 | Energy & Power | `energy-power`, `demand-profile`, `load-anomalies`, `energy-power-history` | Mix (live delta + history widgets) |
| 4 | Energy Distribution | `energy-distribution` | Widget envelope (Sankey + rail) |
| 5 | Voltage & Current | `voltage-current`, `voltage-history`, `current-history` | Live delta + history widgets |
| 6 | Power Quality | `power-quality-summary` (single socket) | Widget envelope (7 widgets) |

Full WebSocket URL pattern: `ws://<host>:8888/ws/mfm/174/<endpoint>/`

---

## 1. Overview

### `ws/mfm/174/overview/`
Per-widget envelope. Live tick + range/event widgets (KPIs, gauges,
sparks, AI summary).

- Frame type: `snapshot` on connect, `tick` on auto-refresh.
- No filter commands on this socket.

---

## 2. Real-Time Monitoring

### `ws/mfm/174/real-time-monitoring/`
Single live stream of all RTM columns at **1-sec cadence**, sliding 60-sec
window. Per-cell **severity bands** are computed server-side.

- Each cell ships `value`, `band` (overall `low/normal/moderate/critical`),
  `bands` (per-metric breakdown), and `load_pct` for the kw/kvar/amp tiles
  (`load_pct = active_power / rated × 100`).
- Frame keys typically include `config`, `feeders`, `selected_feeder`.

---

## 3. Energy & Power (4 endpoints)

### `ws/mfm/174/energy-power/`
**Today's Energy + Input vs Output** live KPIs (delta queue). Reads
`lt_panel_config` for the nameplate fields:

```
energy_target_kwh_today  → "Today's Energy" /target denominator
subsidy_limit_kw         → subsidy-marker bar position
target_efficiency_pct    → Expected Loss tile
rated_kw                 → Power Energy Analysis rated reference line
contracted_kw            → Power Energy Analysis contracted reference line
loss_energy_today_kwh    → Input vs Output Loss tile (kW → kWh)
```

### `ws/mfm/174/demand-profile/`
**Power Energy Analysis** bars — bucketed Active / Reactive / Demand with
the shared range × sampling filter. Supports the new **`2hour`** sampling
on `today` / `yesterday` (12 bars over a full day).

Filter commands:
```jsonc
{ "range": "today",     "sampling": "2hour" }    // 12 bars
{ "range": "yesterday", "sampling": "shift" }    // A/B/C
{ "range": "this-month","sampling": "weekly" }
```

### `ws/mfm/174/load-anomalies/`
Bucketed actual vs expected load + surge / dip event markers. Same range ×
sampling vocab as `demand-profile`.

### `ws/mfm/174/energy-power-history/`
Bucketed Active / Reactive bars + Load Anomalies trace + window KPIs
(Today / Week / Month). Backend does **per-bucket `AVG()` aggregation**
(`AVG("col") AS "col_avg"`) on the raw `mfm_*` rows.

---

## 4. Energy Distribution

### `ws/mfm/174/energy-distribution/`
**Window-aggregate** view — single Sankey + per-feeder rail. Not a
time-series; uses an older range-only vocab (no sampling).

**Widgets shipped:**
- `config` — `ranges`, `current_range`, `window_start`, `window_end`
- `header` — `measured_input_kwh`, `delivered_kwh`, `loss_kwh`, `loss_pct`,
  `meter_gap_*`, `best_path`, and **`main_meter`** `{ mfm_id, name, kwh, capacity_kwh, utilization_pct, status }`
- **`incomers[]`** (top-level) — parallel to `consumers[]`, shape:
  `{ mfm_id, name, type, source_group, kwh, capacity_kwh, utilization_pct, status }`
- `consumers[]` — existing fields + new `capacity_kwh` + `utilization_pct`
- `sankey` — every `nodes[i]` carries `kind`: `"source" | "meter" | "stage" | "load" | "loss"`.
  Includes a `loss` node + `dist → loss` link so the Sankey balances.
- `ai_summary` — `{ text, badge }`

Filter command:
```jsonc
{ "range": "this_week" }   // one of: today / yesterday / this_week / this_month / last_24h / last_7d
```

> **Open caveat:** `delivered_kwh` / `loss_kwh` / `loss_pct` and the Sankey
> magnitudes still use a `MAX − MIN` counter-delta computation that swings
> wildly. The **shape is correct, the absolute numbers aren't trustworthy
> yet** — backend fix pending. The relative `share_pct` and the rail's
> `utilization_pct` (denominators from nameplate config) are reliable.

---

## 5. Voltage & Current (3 endpoints)

### `ws/mfm/174/voltage-current/`
Live V/I delta queue with status labels (Voltage Live Health + Current
Live Health tiles).

### `ws/mfm/174/voltage-history/`
Time-bucketed phase voltages + sag / swell event timeline + Primary Event
KPIs. Range × sampling filter (same vocab as `demand-profile`).

### `ws/mfm/174/current-history/`
Time-bucketed phase currents + Peak / Avg / Unbalance / Neutral KPIs.

> **Open caveat:** the weekly-bucket attribution bug (UNIX-Thursday vs
> month-anchored edges) was fixed on PQ but not yet on V&C. Day / hour /
> shift cadences are fine.

---

## 6. Power Quality

### `ws/mfm/174/power-quality-summary/` ⭐ — single socket for the whole tab

Drives every widget on the Harmonics & PQ tab. The former
`distortion-harmonics` and `power-quality-history` endpoints are folded in
here and **respond with 4404** if called.

**Frame contents — 7 widgets:**

| Widget | Purpose |
|---|---|
| `timeline_filter` | **THE single shared constraint** — `range_options`, `current_range`, `sampling_options` (`hourly`, **`2hour`**, `shift`), `bucket_options`, `selected_bucket`, `window_start`, `window_end`, `anchor_iso`. Both the timeline AND the inspector render under it; neither carries its own filter |
| `event_timeline` | `buckets[]` (each: `bucket`, `bucket_iso`, 6 event counts + `neutral`, `worst_i_thd_pct`, `worst_v_thd_pct`); `events[]` discrete records; `totals`; `total_events`. Top-level also includes `range`, `sampling`, `anchor_iso` (duplicates of `timeline_filter` for FE convenience) |
| `pq_exposure_share` | PQ Inspector breakdown — **7 categories**: `i_thd`, `v_thd`, `h5`, `h7`, `k_factor`, `pf_gap`, **`neutral`** (synthesized from `kpi_neutral_to_phase_ratio_pct > 10%`) |
| `header_kpis` | `ieee_state`, `pq_exposure`, `selected_feeder` |
| `pq_priority` | Ranked outgoing-feeders. Row fields: `mfm_id, name, rank, selected, score, severity, i_thd_pct, v_thd_pct, i_thd_pk_pct, dominant_driver, pf` |
| `fleet_matrix` | Per-feeder × metric heatmap with `current_focus` selector |
| `signature` | Harmonic radar (selected feeder vs fleet avg) |

**Commands:**

```jsonc
{ "timeline_filter": { "range": "today", "sampling": "2hour" } }   // 12-bar cadence
{ "timeline_filter": { "bucket": "14:00" } }                       // pick a bucket
{ "timeline_time":  "2026-06-01T14:00:00+05:30" }                  // pick bucket by ISO ts
{ "select_feeder":  18 }                                            // pick a feeder (highlights priority/matrix/signature)
{ "fleet_matrix": { "focus": "h5" } }                              // change matrix focus metric
```

---

## Frame envelope

All sockets emit the same outer structure:

```jsonc
{
  "type":     "snapshot" | "tick" | "widget_update" | "error" | "ack",
  "mfm_id":   174,
  "mfm_name": "PCC Panel 1 A",
  "mfm_type": "pcc_panel",          // resolved category (name-prefix), not raw lt_panel
  "page":     "<page-code>",
  // ── one of these depending on the strategy: ──
  "widgets":  { ... },              // aggregate strategies (E&D, PQ)
  "queue":    [ ... ], "columns": [...], "status": {...}, "window_seconds": 60,
  "count":    N, "capacity": M,     // column-row live streams (V&C, RTM, ...)
}
```

- `type: "snapshot"` — first frame on connect, full state.
- `type: "tick"` — periodic auto-refresh.
- `type: "widget_update"` — reply to a command; same shape as snapshot.
- `type: "error"` — validation / fetch error; socket stays open.

---

## Range × sampling cheat sheet (history sockets)

| `range` | `sampling` |
|---|---|
| `today`, `yesterday` | `hourly` (3 h, 8 bars) · **`2hour`** (2 h, 12 bars — NEW) · `shift` (8 h, A/B/C) |
| `last-7-days` | `daily` |
| `last-30-days`, `this-month`, `last-month` | `daily` · `weekly` |
| `custom-range` (+ `start_date` / `end_date`) | `hourly` · `2hour` · `shift` · `daily` · `weekly` |

The `2hour` aliases `2h`, `two-hour`, `two_hour` are all accepted.

**Energy Distribution is the exception** — uses an older range-only vocab
(`today / yesterday / this_week / this_month / last_24h / last_7d`) with
no sampling subfilter.

---

## Quick smoke tests

Open Postman or a `wscat`-equivalent and try:

```bash
# 1. Page list — confirms what's wired up
curl -s http://100.90.185.31:8888/api/mfm/174/pages/ | jq

# 2. Energy Distribution rail
wscat -c ws://100.90.185.31:8888/ws/mfm/174/energy-distribution/

# 3. Power Quality (single socket; full tab payload)
wscat -c ws://100.90.185.31:8888/ws/mfm/174/power-quality-summary/

# 4. Switch PQ sampling to 12-bar cadence
# (after opening the WS, send:)
> {"timeline_filter": {"range": "today", "sampling": "2hour"}}
```

`/api/mfm/174/config/` returns the static nameplate row from
`lt_panel_config` — every E&P card pulls its target / subsidy / rated /
contracted / efficiency values from this.

---

## Retired endpoint warning

**Do not call:**

| Old (retired) | New |
|---|---|
| `ws/mfm/174/distortion-harmonics/` | `ws/mfm/174/power-quality-summary/` |
| `ws/mfm/174/power-quality-history/` | `ws/mfm/174/power-quality-summary/` |

Hitting either returns:
```jsonc
{ "type": "error",
  "message": "Page 'distortion-harmonics' not registered for mfm_id=174" }
```

Full migration notes: [RETIRED_PQ_ENDPOINTS_FRONTEND_FIX.md](RETIRED_PQ_ENDPOINTS_FRONTEND_FIX.md).

---

## Detailed contracts (deep-dive docs)

| Topic | File |
|---|---|
| Voltage & Current page — full wire contract | [PCC_VOLTAGE_CURRENT_INTEGRATION.md](PCC_VOLTAGE_CURRENT_INTEGRATION.md) |
| Energy & Power page — full wire contract | [PCC_ENERGY_POWER_INTEGRATION.md](PCC_ENERGY_POWER_INTEGRATION.md) |
| Power Quality + Energy Distribution — full wire contract | [PCC_PQ_AND_ENERGY_DISTRIBUTION_INTEGRATION.md](PCC_PQ_AND_ENERGY_DISTRIBUTION_INTEGRATION.md) |
| PQ FE-contract response (recent additions) | [HARMONICS_PQ_FE_CONTRACT_RESPONSE.md](HARMONICS_PQ_FE_CONTRACT_RESPONSE.md) |
| Whole system overview | [ARCHITECTURE.md](ARCHITECTURE.md) |

---

## Notes

- `mfm_id` is stable across deploys — safe to hard-code `174` for PCC Panel 1 A.
- Other PCC half-panels (1 B, 2 A/B, 3 A/B, 4) have their own `mfm_id`s. Hit
  `/api/ems/` or `/api/mfm/` to discover them.
- The category resolver (name-prefix → `pcc_panel`) means **same endpoint
  paths apply** to all PCC Panel halves — only the `mfm_id` in the URL changes.
