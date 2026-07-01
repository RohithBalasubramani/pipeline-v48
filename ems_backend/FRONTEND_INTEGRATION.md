# CMD Backend — Frontend Integration Guide

Compatibility reference for the FE dev consuming the CMD backend. Lists
every endpoint the frontend should call, what each one returns, and which
sockets a given tab needs to open.

**Backend service:** `cmd-django.service` (Daphne ASGI), running on
**port 8888**, reachable on:

- Localhost: `http://localhost:8888`
- LAN Ethernet: `http://192.168.1.20:8888`
- LAN Wi-Fi: `http://192.168.1.14:8888`
- Tailscale VPN: `http://100.90.185.31:8888`

WebSockets use the same host with `ws://…` (or `wss://…` behind TLS).

---

## 1 · What changed in this iteration (May 2026)

This pass tightened the FE/BE contract after the FE handoff doc was
reviewed. Concrete deltas vs the previous backend state:

### 1.0 — Path A: PQ labels now ship as `frame.status.*` on every type

The FE was deriving Severity / Active Issue / Likely Source / Filter
State / Capacitor Bank / Next Priority / Nonlinear Signature / Action
Badge with hardcoded if/else rules per page. These are now derived
backend-side in `compute_status(row)` via the shared
[`consumers/_pq_labels.py`](backend/lt_panels/consumers/_pq_labels.py)
module and exposed through the `status` dict on every PQ summary tick:

```jsonc
"status": {
  "pq_severity_label":          "Critical",
  "pq_critical_issue_type":     "Harmonic Distortion",
  "pq_active_issue_count":      2,
  "pq_likely_source_label":     "Non-linear rectifier load",
  "pq_next_priority_label":     "Add 5th harmonic filter",
  "pq_nonlinear_signature_label":"Both exceeded",
  "pq_action_badge":            "APFC Tune",
  "pq_filter_state":            "APF active",
  "pq_capacitor_bank_state":    "Watch",
  "pq_dominant_harmonic_secondary": 5,
  "pf_displacement_gap":        0.022,
  "thd_compliance_ieee519":     "Pass",
  "thd_movement_pct_per_h":     "Normal",
  /* …plus flicker_pst, crest_factor_voltage/current rules */
}
```

Same set of 17 labels on transformer + UPS + LT + APFC PQ tabs. UPS
also gets stored simulator values for some of these but the derived
labels win (consistent casing across types).

### 1.0b — Energy & Power: 5 derived I/O metrics added to `status`

The FE handoff flagged Loss / Expected-Loss tiles bound to the wrong
columns (showing Active/Reactive energy in place of loss numbers). Root
cause: backend wasn't shipping the loss / efficiency values the FE
wanted. Now [`consumers/_ep_metrics.py`](backend/lt_panels/consumers/_ep_metrics.py)
computes these per-tick and they appear in `frame.status` for every
E&P live socket:

```jsonc
"status": {
  "efficiency_pct":                  94.38,
  "hv_lv_delta_pct":                 5.95,
  "active_energy_loss_today_kwh":    49.93,
  "expected_energy_loss_today_kwh":  32.24,
  "loss_pct_of_input":               5.62
}
```

Rated efficiency constants per type: transformer 98.5%, UPS 96.5%, LT
99%. Tunable in the strategy files.

### 1.0c — Stub strategies filled

Previously-pending strategies now ship real data:

- **`load-anomalies`** for transformer / UPS / LT / APFC — on-demand
  Expected Range band (mean ± k·σ), surge/dip event detection from
  bucket avgs crossing the band
- **`energy-power-history`** for transformer / LT / APFC / PCC —
  inherit the type-agnostic UPS strategy
- **`power-quality-history`** for transformer / LT / APFC / PCC —
  same pattern; IEEE 519 SQL fixed to compare TEXT values
- **APFC** column-row strategies for Overview / RTM / V&C / E&P /
  PQ summary / Distortion / Voltage-History / Current-History /
  Demand-Profile — APFC-specific cols (PF before/after, compensation
  ratio, bank utilization, resonance risk, savings) layered on top of
  the LT panel column lists

Still stubs: HT panel + sub_panel (every page — simulator doesn't have
data for these types yet).

### 1.1 — Transformer pages: phase-data columns now real (was all `null`)

Transformer strategies for **RTM**, **V&C**, **E&P**, **PQ summary**,
**Distortion & Harmonics**, **voltage-history**, **current-history**
used HV-prefixed placeholder column names (`voltage_hv_r_n`,
`current_hv_r`, etc.) that didn't exist in the simulator schema. Backend's
column-tolerance silently shipped them as `null`, so every transformer
page rendered without phase voltage / current data.

Fix: stripped the `_hv_` prefix across all 5 strategy files. Frontend's
existing single-MFM mapper now gets real values for `voltage_r_n`,
`voltage_y_n`, `voltage_b_n`, `current_r`, `current_y`, `current_b`,
`current_neutral`, `voltage_avg`, `voltage_max`, `voltage_min`,
`current_avg`, `current_max`, `current_min`.

### 1.2 — `frequency_hz` added to transformer RTM

Was missing from the transformer RTM column list. Now ships on every tick.

### 1.3 — New column: `voltage_ll_avg`

The L-L average voltage (`(voltage_ry + voltage_yb + voltage_br) / 3`)
was missing from the schema (only L-N average existed). Added to
`COMMON_COLUMNS`, all 186 per-MFM tables now carry it, registered for
all five MFM types in the parameter registry.

### 1.4 — New REST endpoint: `GET /api/mfm/{id}/config/`

Per-MFM static config (chart thresholds, nameplate, ratings) was only
in the simulator's PostgreSQL tables, not reachable from the frontend.
This endpoint exposes the relevant config table per MFM type:

| MFM type | Backing table | Field count |
|---|---|---|
| `transformer` | `transformer_config` | 47 |
| `ups` | `ups_config` | 34 |
| `lt_panel` | `lt_panel_config` | 17 |
| `ht_panel` | `ht_panel_config` | 9 |
| `apfc` | `apfc_config` | 9 |

Use it for chart reference lines (Max-V / Min-V / Max-A / Min-A bands),
the Nominal V tile, PF Target, rated kVA, subsidy budgets, battery
capacity, busbar / thermal limits, etc.

### 1.5 — Page registry `pending` flag fixed

Aggregate strategies (PCC Panel pages: `IS_AGGREGATE = True`) were
mis-reported as `pending: true` because the flag only looked for
`columns` / `widgets` declarations and skipped aggregate strategies.

Now: `pending` correctly returns `false` for PCC's overview, RTM, V&C,
E&P, PQ-summary, energy-distribution.

### 1.6 — Two new history dispatchers in the page registry

`energy-power-history/` and `power-quality-history/` were added to the
backend but weren't listed in `/api/mfm/{id}/pages/`. Now they appear
under the Energy & Power and Power Quality pages respectively.

### 1.7 — Catch-all WS route for clean `4404` closes

Previously, hitting `ws/mfm/2/totally-bogus-page/` returned HTTP 500
(Daphne's default for unmatched routes). Now: accepts the connection,
sends one `error` frame with a useful message, closes with code `4404`.

---

## 2 · Where to start (typical frontend flow)

```
1. GET /api/electrical-equipment/
       → render the left sidebar; each leaf has `mfm_id`
2. User clicks a leaf
3. GET /api/mfm/{id}/pages/
       → tells you which tabs to render + which WS URLs each tab opens
4. (optional) GET /api/mfm/{id}/config/
       → fetch chart reference lines + nameplate values once at page load
5. Open WebSocket(s) per active tab
       → receive `snapshot` once + `tick` / `update` frames continuously
```

---

## 3 · HTTP endpoint reference

### 3.1 — `GET /api/electrical-equipment/`

Static taxonomy of the entire equipment tree. The single source of truth
for `label → mfm_id` resolution.

**Response shape:**
```jsonc
{
  "count": 7,
  "leaf_count": 248,
  "matched_mfm_count": 204,
  "tree": [
    {
      "id": "eq-pcc-p1a",
      "label": "PCC Panel 1 A",
      "slug": "panel-1a",
      "pathOverride": "/electrical/pcc-panels/panel-1a",
      "mfm_id": 174,
      "children": [ ...recursive ]
    },
    ...
  ]
}
```

Node fields: `id`, `label`, `slug`, `pathOverride?`, `alwaysOpen?`,
`mfm_id?` (present on real MFM leaves), `children?` (recursive).

### 3.2 — `GET /api/mfm/`

Returns the flat list of every MFM in the DB.

```jsonc
[
  {
    "id": 2,
    "name": "Transformer 1",
    "mfm_type": "transformer",
    "db_link": "postgresql://...",
    "table_name": "mfm_tf_01",
    "panel_id": "MFM-TF-01",
    "incoming": [...], "outgoing": [...], "spare": [...], "coupler": [...]
  },
  ...
]
```

### 3.3 — `GET /api/mfm/{id}/`

Detail for one MFM, including the full Parameter catalogue for its MFMType
(name, column, unit, spec, kind).

### 3.4 — `GET /api/mfm/{id}/pages/`

Which tabs this MFM should render + which WebSocket URLs each tab opens.

```jsonc
{
  "mfm_id": 174, "mfm_name": "PCC Panel 1 A",
  "mfm_type": "lt_panel",        // ← raw DB type (don't branch shape on this)
  "count": 6,
  "pages": [
    { "code": "overview", "name": "Overview", "order": 1,
      "description": "Headline KPIs + status widgets …",
      "websockets": [
        {
          "name": "Overview Live",
          "endpoint_path": "overview",        // ← use this, not page.code
          "ws_url": "/ws/mfm/174/overview/",
          "ws_url_abs": "ws://host:8888/ws/mfm/174/overview/",
          "pending": false,
          "description": "Per-widget envelope (live tick + range widgets)."
        }
      ]
    },
    ...
  ]
}
```

**`pending` semantics:** `true` means the backend has a stub strategy for
this MFM-type/page pair and will return `{type:"snapshot",pending:true,...}`
followed by no further frames. The frontend should render a placeholder.

**Branching on shape:** do NOT use the page registry's `mfm_type` to
decide snapshot shape — that returns the raw DB type. Use the **WS
snapshot's `mfm_type` field** instead, which carries the resolved
category (e.g. `"pcc_panel"` for name-prefixed PCC panels).

### 3.5 — `GET /api/mfm/{id}/parameters/`

Parameter catalogue (column ↔ name/unit/spec/kind) for the MFM's type.
Used for label/unit lookup when rendering raw column data.

### 3.6 — `GET /api/mfm/{id}/live/`

One-shot REST fallback for the latest row, enriched with parameter
metadata (name, unit, kind, spec). Use when a WS connection isn't
practical (e.g. SSR, scheduled jobs).

### 3.7 — `GET /api/mfm/{id}/history/?minutes=60&columns=col1,col2`

One-shot REST fallback for raw rows over the trailing N minutes.

### 3.8 — `GET /api/mfm/{id}/config/` (NEW)

Per-MFM static configuration row. Use for chart reference lines and
nameplate values — fetch once at page load.

```jsonc
{
  "mfm_id": 2, "panel_id": "MFM-TF-01",
  "mfm_type": "transformer", "config_table": "transformer_config",
  "config": {
    "panel_id": "MFM-TF-01",
    "panel_name": "Transformer 1",
    "nominal_voltage_v": 415.0,
    "rated_kva": 1500.0,
    "rated_voltage_hv_kv": 11.0,
    "rated_voltage_lv_v": 415.0,
    "voltage_high_threshold_v": 456.5,
    "voltage_low_threshold_v": 373.5,
    "current_high_threshold_a": 2295.49,
    "current_low_threshold_a": 104.34,
    "winding_high_temp_c": 105.0,
    "oil_high_temp_c": 90.0,
    "hotspot_warning_temp_c": 120.0,
    "v_thd_limit_pct": 5.0,
    "i_thd_limit_pct": 8.0,
    "pf_target": 0.95,
    ...
  }
}
```

For **UPS** the config additionally carries `ups_battery_capacity_kwh`,
`ups_battery_string_count`, `ups_topology`, `ups_test_interval_days`,
`contract_limit_kva`, `voltage_deviation_limit_pct`, `busbar_high_temp_c`.

For **LT panel** (solar incomer flavour) the config carries
`pv_array_rated_kwp`, `pv_array_area_m2`, `pv_module_count`,
`pv_string_count`, `inverter_rated_kw`, `inverter_efficiency_max_pct`,
`module_temp_coefficient_pct_per_c`, `solar_components_total`.

---

## 4 · WebSocket endpoint reference

All WS URLs share the same shape:

```
ws://host:8888/ws/mfm/{mfm_id}/{endpoint_path}/[?optional=params]
```

Sockets fall into three flavours: **live column-row** (snapshot + delta
ticks), **aggregate** (snapshot + full widget envelope re-render), and
**history** (snapshot + range/sampling cmd-driven re-renders).

### 4.1 — Live sockets

| Endpoint | Dispatcher | Cadence | Description |
|---|---|---|---|
| `overview/` | `OverviewDispatcher` | 1 s (column-row) / 2 s (PCC agg) | Per-widget envelope. Headline KPIs + topology / SLD. For column-row types it ships a flat `widgets.<name>.{col: val}` shape; for PCC Panel it ships an aggregate envelope with `header_status`, `header_kpis`, `sld`, `selected_feeder`. |
| `real-time-monitoring/` | `RealTimeMonitoringDispatcher` | 1 s | Live Power/Energy + Voltage + Current. 60-sec rolling window for column-row types. For PCC Panel: 30-sec window, per-feeder queues. |
| `voltage-current/` | `VoltageCurrentDispatcher` | 1 s | Live phase voltages, currents, deviations, unbalance. For PCC Panel: PQ event-timeline (5 widgets, 3-hour buckets across 24 h). |
| `energy-power/` | `EnergyPowerDispatcher` | 1 s | Today's energy KPIs + Input vs Output + Load Anomalies header tiles. For PCC Panel: 4-widget aggregate with per-widget commands. |
| `energy-distribution/` | `EnergyDistributionDispatcher` | 1-5 s | Per-outgoing-feeder fan-out (transformer / LT). For PCC Panel: full energy-accounting aggregate (Sankey + ranked consumers). |
| `power-quality-summary/` | `PowerQualitySummaryDispatcher` | 1 s | Per-MFM PQ snapshot (Critical Diagnosis, Current Harmonic Stress, Source & mitigation). For PCC Panel: fleet matrix + ranking + exposure breakdown. |
| `distortion-harmonics/` | `DistortionHarmonicsDispatcher` | 1 s | V/I THD per phase, harmonic orders, PF, K-factor, FHL. (Stub on PCC Panel — covered by PQ aggregate.) |

### 4.2 — History sockets (range/sampling filterable)

| Endpoint | Dispatcher | Description |
|---|---|---|
| `voltage-history/` | `VoltageHistoryDispatcher` | Bucketed phase voltages + sag/swell counters + Worst Spread / Primary Event KPIs. Expected Range band (mean ± 1·σ). |
| `current-history/` | `CurrentHistoryDispatcher` | Bucketed phase currents + neutral + KPIs (peak, average, max unbalance, neutral peak). Expected Range band. |
| `demand-profile/` | `DemandProfileDispatcher` | Hourly active/reactive/demand bars. |
| `load-anomalies/` | `LoadAnomaliesDispatcher` | Actual vs Expected load + surge/dip event markers. |
| `energy-power-history/` | `EnergyPowerHistoryDispatcher` | **NEW.** Bucketed Active/Reactive bars + Load Anomalies trace + window KPIs (Today / This Week / This Month). |
| `power-quality-history/` | `PowerQualityHistoryDispatcher` | **NEW.** Bucketed V/I-THD + PF/K-Stress traces with range filter. IEEE 519 compliance %, PF gap, etc. |

**Range presets** (accepted by all history endpoints):
`today | yesterday | this_week | this_month | last_24h | last_7d | last_30d`
plus explicit `start=…&end=…` ISO datetimes.

**Sampling values:** `minute | 5min | 15min | 30min | hour | day`.

**Mid-connection range switch:** send
`{"range": "this_week", "sampling": "day"}` over the same socket; the
server responds with a fresh `update` frame.

---

## 5 · Wire-frame contracts

### 5.1 — Column-row live socket

```jsonc
// On connect
{
  "type": "snapshot",
  "mfm_id": 2, "mfm_name": "Transformer 1", "panel_id": "MFM-TF-01",
  "mfm_type": "transformer",                    // ← branch shape on this
  "page": "real-time-monitoring",
  "window_seconds": 60, "capacity": 60,
  "columns": ["active_power_total_kw", "voltage_r_n", ...],
  "count": 60,
  "queue": [{"ts": "...", "active_power_total_kw": 971.09, ...}, ...60 rows],
  "status": {}
}

// Every interval_seconds (typically 1 s)
{
  "type": "tick",
  "enqueue": [{"ts": "...", "active_power_total_kw": 971.09, ...}],
  "dequeue": 1,
  "queue_size": 60,
  "status": {"<col>": "Normal" | "Watch" | "Critical" | ...}
}
```

Client maintains the rolling queue:
```js
let q = m.queue;
ws.onmessage = e => {
  const m = JSON.parse(e.data);
  if (m.type === 'snapshot') q = m.queue;
  else if (m.type === 'tick') {
    q.push(...m.enqueue);
    q.splice(0, m.dequeue);
  }
};
```

### 5.2 — Aggregate live socket (PCC Panel pages)

```jsonc
{
  "type": "snapshot",
  "mfm_id": 174, "mfm_name": "PCC Panel 1 A",
  "mfm_type": "pcc_panel",                  // ← resolved category, NOT lt_panel
  "page": "overview",
  "ts": "2026-05-24T...",
  "widgets": {
    "header_status": {"all": 7, "critical": 0, "warning": 0, "normal": 7},
    "header_kpis":   {"main_mfm_kw": 4732, ...},
    "sld":           {"incoming": [...], "outgoing": [...]}
  }
}

// Every interval_seconds
{ "type": "tick", "ts": "...", "widgets": {...same shape...} }

// In response to a client command
{ "type": "widget_update", "widget": "<name>" | "__all__", "data": {...} }
```

Aggregate strategies accept client commands per page; common ones:
- `{"select_feeder": <mfm_id>}` / `{"clear_feeder": true}`
- `{"timeline_time": "2026-05-12T18:00:00+05:30"}`
- `{"period_energy": {"period": "today"}}`
- `{"energy_trend":  {"range": "last_30d", "sampling": "day"}}`

### 5.3 — History socket

```jsonc
{
  "type": "snapshot",
  "mfm_id": 12, "page": "power-quality-history",
  "range": "today", "start": "...", "end": "...", "sampling": "hour",
  "columns": [...],
  "count": 24,
  "buckets": [{"bucket": "...", "<col>_avg": ..., "<col>_max": ..., ...}, ...],
  "kpis": {"v_thd_avg": 3.25, "i_thd_avg": 4.37, "ieee519_compliance_pct": 100.0, ...}
}

// After a client range/sampling cmd OR on the refresh poll (~30 s)
{ "type": "update", "...same shape..." }
```

### 5.4 — Error frame

```jsonc
{ "type": "error", "message": "MFM 99999 not found" }
```

Note the keys: `type` and `message` — not `error` / `code`.

### 5.5 — Close codes

| Code | Meaning |
|---|---|
| `1000–1011` | Standard WebSocket close |
| `4400` | MFM has no `panel_id` configured |
| `4404` | MFM doesn't exist, OR page route doesn't exist (catch-all), OR no strategy registered for this MFM-type/page pair |
| `4500` | Backend fetch raised; preceded by an `error` frame |
| any other | Treat as transient, retry with backoff |

### 5.6 — `pending: true` shape

When the backend has registered the page but the strategy is a stub
(awaiting per-MFM-type spec), the snapshot looks like:

```jsonc
{
  "type": "snapshot", "pending": true,
  "note": "Strategy 'apfc/voltage-current' not yet configured",
  "page": "voltage-current", "mfm_type": "apfc",
  "columns": [], "queue": [], "widgets": {}
}
```

The dispatcher then stops the loop — frontend should render a placeholder
("waiting for spec") and not retry until the user navigates away.

---

## 6 · Per-page wiring guide

Each frontend tab opens one or more sockets. For column-row types
(transformer, UPS, plain LT) the snapshot is single-MFM shaped; for PCC
Panel the snapshot is the aggregate widget envelope — see §5.2.

### 6.1 — Overview tab

| Type | Sockets |
|---|---|
| transformer / UPS / LT Solar Incomer | `overview/` (widget envelope, column-row backed) |
| PCC Panel | `overview/` (aggregate; widgets: header_status, header_kpis, sld, selected_feeder) |

### 6.2 — Real-Time Monitoring tab

| Type | Sockets |
|---|---|
| transformer / UPS / LT | `real-time-monitoring/` |
| PCC Panel | `real-time-monitoring/` (per-feeder queues; client cmds: select_feeder / clear_feeder) |

For chart reference lines (Max-V / Min-V / Max-A / Min-A bands), call
`GET /api/mfm/{id}/config/` once and read `voltage_high_threshold_v`,
`voltage_low_threshold_v`, `current_high_threshold_a`,
`current_low_threshold_a`.

### 6.3 — Voltage & Current tab

| Type | Sockets |
|---|---|
| transformer / UPS / LT | `voltage-current/` + `voltage-history/` + `current-history/` |
| PCC Panel | `voltage-current/` (5-widget event timeline; client cmds: timeline_time, selected_panel, selected_period) |

History sockets accept `?range=today` etc. KPIs include
`max_deviation_pct`, `worst_spread_v`, `worst_spread_pair`,
`primary_event`, `sag_events`, `swell_events`,
`expected_band_upper_v / lower_v`.

### 6.4 — Energy & Power tab

| Type | Sockets |
|---|---|
| transformer / UPS / LT | `energy-power/` (live KPIs) + `energy-power-history/` (bar chart + load anomalies trace) |
| PCC Panel | `energy-power/` (4-widget aggregate; per-widget cmds for period_energy, energy_trend, panel_power_profile) |

Plus optional sibling history sockets: `demand-profile/`,
`load-anomalies/`.

### 6.5 — Energy Distribution tab

| Type | Sockets |
|---|---|
| transformer / UPS / LT | `energy-distribution/` (per-outgoing fan-out) |
| PCC Panel | `energy-distribution/` (parent aggregate: header KPIs + ranked consumers + Sankey + AI summary) |

### 6.6 — Power Quality tab

| Type | Sockets |
|---|---|
| transformer / UPS / LT | `power-quality-summary/` + `distortion-harmonics/` + `power-quality-history/` |
| PCC Panel | `power-quality-summary/` (fleet matrix + ranking + exposure breakdown — 4 widgets) |

---

## 7 · Known caveats / TODO

### 7.1 — PCC Panel ships different snapshot shapes

By design, PCC Panel pages return aggregate widget envelopes whose
internal shape is per-page (event timeline, fleet matrix, 4-widget E&P,
Sankey). Frontend must build PCC-specific snapshot types + mappers
distinct from the single-MFM shape used by transformer / UPS. See
`BACKEND_API_AND_WEBSOCKETS.md` §3 for the per-page rationale.

### 7.2 — `mfm_type` semantics

- **`/api/mfm/{id}/pages/.mfm_type`** → raw DB type (`lt_panel` for PCC
  Panels, etc.). Useful for typing; **not for branching snapshot shape**.
- **WS snapshot's `mfm_type` field** → resolved category after name-prefix
  lookup. **Branch shape on this**: `pcc_panel` vs `transformer` vs
  `lt_panel` vs `ups` vs `apfc` vs `ht_panel`.

### 7.3 — `voltage_ll_avg` historical-data caveat

The column was added today. Rows written before today have it as `null`;
rows written by the simulator from now on will populate it.

### 7.4 — Still-pending strategies (stubs)

After the latest round, only HT panel and sub_panel remain fully
stubbed — APFC, LT panel, transformer, UPS now have real strategies
for every page.

| MFM type | Pages still stubbed |
|---|---|
| `ht_panel` | every page (simulator has no HT data yet) |
| `sub_panel` | every page (placeholder type — no simulator data) |

Frontend should expect `{"pending": true}` snapshots only when opening
HT panel / sub_panel sockets. Implementations can be added incrementally
once the simulator emits those types — no wire contract change required
when they land.

### 7.5 — `dataSourceRegistry.ts` table-name lookups

Frontend's legacy `mfm_008`-style table-name identification should be
replaced with `mfm_id` from `/api/electrical-equipment/`. The table name
(`mfm_tf_01` etc.) is a backend implementation detail and not part of
the public contract.

---

## 8 · Quick smoke test

```bash
# HTTP — should return a non-empty tree with 248 leaves
curl -s http://localhost:8888/api/electrical-equipment/ | jq '.leaf_count'

# Page registry for Transformer 1
curl -s http://localhost:8888/api/mfm/2/pages/ | jq '.pages[].code'

# Config row for Transformer 1 — should have ~47 fields
curl -s http://localhost:8888/api/mfm/2/config/ | jq '.config | keys | length'

# WS — should print one snapshot frame
python -c "
import asyncio, json
from websockets.client import connect
async def main():
    async with connect('ws://localhost:8888/ws/mfm/2/real-time-monitoring/') as ws:
        snap = json.loads(await ws.recv())
        print('type:', snap['type'])
        print('mfm_type:', snap['mfm_type'])
        print('columns:', len(snap['columns']))
asyncio.run(main())
"
```

If you get `type: snapshot`, `mfm_type: transformer`, and a non-zero
column count, you're wired up.

---

## 9 · Backend service control

```bash
# Status
systemctl --user status cmd-django

# Restart (picks up code changes + clears column-tolerance cache)
systemctl --user restart cmd-django

# Live logs
journalctl --user -u cmd-django -f

# Re-seed parameter registry (after schema changes)
cd /home/rohith/CMD/backend && python manage.py seed_parameters
```

---

## 10 · Related docs

- **`BACKEND_API_AND_WEBSOCKETS.md`** — full architecture reference
  (dispatchers, strategies, design rationale per page, file layout)
- **`PAGES_PARAMETER_SPEC.md`** — per-MFM-type parameter catalogues
- **`REST_API.md`** — original REST contract reference
- **`WEBSOCKETS.md`** — original WS contract reference (legacy; superseded
  by `BACKEND_API_AND_WEBSOCKETS.md`)
