# REST API Reference — MFM Graph

How to walk the flat MFM-to-MFM topology and read parameter metadata + live values.

For the live streaming side (60-second windows, hourly buckets, status labels), see [`WEBSOCKETS.md`](WEBSOCKETS.md).

- **Tailscale:** `http://100.90.185.31:8090`
- **LAN:**       `http://192.168.1.20:8090`
- **Local:**     `http://localhost:8090`
- **Base path:** `/api/`

---

## Topology model

```
                  ┌──────────┐
                  │  MFMType │     lt_mfm_type
                  └────┬─────┘     e.g. lt_panel_meter
                       │
        ┌──────────────┴──────────────┐
        │ mfms                        │ parameters (1-many)
        ▼                             ▼
  ┌──────────┐                   ┌───────────┐
  │   MFM    │                   │ Parameter │  lt_parameter
  │  (graph) │                   │           │  135 rows for lt_panel_meter
  └────┬─────┘                   └───────────┘  (one per column in panel_readings)
       │
   self-M2Ms ─ incoming / outgoing / spare
              (each is a *set* of other MFMs; may be empty)
```

**Key properties:**

- **No panel layer.** Each MFM is a node; FKs to other MFMs form the graph.
- **Field list lives on the MFMType.** Every MFM of the same type shares the same `Parameter` registry — no per-MFM duplication. Add a new MFMType (e.g. `chiller_meter`) and it brings its own field list.
- **Values are never stored in Django.** The MFM's `db_link` + `table_name` + `panel_id` is used to query the simulator's `panel_readings` table on demand. Django is a pure broker.

---

## Endpoint index

| URL | Method | Returns |
|---|---|---|
| `/api/mfm/` | GET | List of all MFMs (full type + parameters nested) |
| `/api/mfm/{id}/` | GET | Single MFM (full type + parameters + connections) |
| `/api/mfm/{id}/parameters/` | GET | Parameter metadata for that MFM's type (135 rows) |
| `/api/mfm/{id}/live/` | GET | Latest row from `panel_readings`, enriched per column |
| `/api/mfm/{id}/history/?minutes=N` | GET | Last N minutes of rows |

---

## MFM list and detail

### `GET /api/mfm/`

All MFMs in one call. Each MFM carries:
- its own identity (`id`, `name`, `panel_id`)
- the full `mfm_type` (including all 135 parameters — useful for a one-shot bootstrap)
- the three connection sets (`incoming`, `outgoing`, `spare`) — **each is an array of nested mini-objects** (possibly empty)

**Response (single MFM, truncated)**
```json
{
  "id": 5,
  "name": "UPS-01 CL:600KVA",
  "mfm_type": {
    "id": 1,
    "code": "lt_panel_meter",
    "name": "LT Panel Meter",
    "description": "...",
    "parameters": [
      {"id": 1, "name": "Voltage R-Y", "column_name": "voltage_ry",
       "kind": "measured", "unit": "V", "spec": "M1", "description": ""},
      ...
    ]
  },
  "db_link": "postgresql://postgres@/lt_panels?host=/run/postgresql",
  "table_name": "panel_readings",
  "panel_id": "MFM-UPS-01",
  "incoming": [
    {"id": 1, "name": "Solar Incomer-1",   "panel_id": "MFM-SOLAR-IN-01", "mfm_type": "lt_panel_meter"},
    {"id": 2, "name": "Solar Incomer-2",   "panel_id": "MFM-SOLAR-IN-02", "mfm_type": "lt_panel_meter"},
    {"id": 3, "name": "Incomer-1 (TF-01)", "panel_id": "MFM-INC-TF-01",   "mfm_type": "lt_panel_meter"},
    {"id": 4, "name": "Incomer-2 (TF-02)", "panel_id": "MFM-INC-TF-02",   "mfm_type": "lt_panel_meter"}
  ],
  "outgoing": [],
  "spare": [
    {"id": 1, "name": "Solar Incomer-1", "panel_id": "MFM-SOLAR-IN-01", "mfm_type": "lt_panel_meter"}
  ]
}
```

### `GET /api/mfm/{id}/`

Single MFM, same shape as one element from `/api/mfm/`.

### `GET /api/mfm/{id}/parameters/`

Just the parameter metadata for the MFM's type. Lighter than `/api/mfm/{id}/` because it strips DB credentials and connections.

**Response**
```json
{
  "mfm_id": 5,
  "mfm_type": "lt_panel_meter",
  "count": 135,
  "parameters": [
    {"id": 1,   "name": "Voltage R-Y", "column_name": "voltage_ry",
     "kind": "measured", "unit": "V", "spec": "M1"},
    ...
    {"id": 135, "name": "Sustained THD Breach Since",
     "column_name": "sustained_thd_breach_started_at",
     "kind": "derived", "unit": "timestamp", "spec": "D-PQ"}
  ]
}
```

`kind` is either `"measured"` (raw sensor) or `"derived"` (computed by the simulator). `spec` carries the spec reference (`M1`–`M15`, `PQ1`–`PQ10`, `1.x`, `2.x`, `4.x`, `8.x` for the originals; `D-V`, `D-I`, `D-PWR`, `D-PQ`, `D-DMD`, `D-E`, `D-TREND` for the new derived ones).

---

## Connections (graph edges)

Each MFM has three **many-to-many** sets to other MFMs:

| Field | Meaning | Cardinality |
|---|---|---|
| `incoming` | MFMs that feed this one (upstream) | 0..N |
| `outgoing` | MFMs this one feeds (downstream) | 0..N |
| `spare` | redundant / standby peers | 0..N |

Each is an **array** in the JSON response (possibly empty). A busbar fed by 4 incomers shows all 4 in its `incoming` array; an MFM feeding 10 downstream loads shows all 10 in its `outgoing` array.

Reverse lookups (who points at me?) are not exposed via the API — frontends are expected to wire both ends explicitly when modelling the graph (`A.outgoing.add(B); B.incoming.add(A)`).

To inspect the full graph in one call: `GET /api/mfm/` and walk client-side using the `incoming`/`outgoing`/`spare` arrays.

---

## Live & history (REST counterparts of WebSockets)

Simple polling alternatives. Use the WebSocket consumers (see [`WEBSOCKETS.md`](WEBSOCKETS.md)) for real-time streaming.

### `GET /api/mfm/{id}/live/`

Latest row from `panel_readings` filtered by this MFM's `panel_id`, with each column enriched from the Parameter metadata.

**Response (truncated)**
```json
{
  "mfm_id": 5,
  "panel_id": "MFM-UPS-01",
  "ts": "2026-05-08T17:42:01.234567+05:30",
  "data": [
    {"column": "active_power_total_kw", "value": 426.9,
     "name": "Active Power Total", "unit": "kW", "kind": "measured", "spec": "M5"},
    {"column": "voltage_avg", "value": 239.7,
     "name": "Voltage Average", "unit": "V", "kind": "derived", "spec": "D-V"},
    ...
  ]
}
```

The first 4 columns (`id`, `ts`, `panel_id`, `panel_name`) come from `panel_readings` but are not Parameter rows — they have `kind: null`.

### `GET /api/mfm/{id}/history/?minutes=N&columns=col1,col2,...`

Last N minutes of rows ordered ascending. Both query params optional (`minutes=60` default, all columns by default).

**Response**
```json
{
  "mfm_id": 5,
  "panel_id": "MFM-UPS-01",
  "minutes": 60,
  "count": 3600,
  "rows": [{"ts": "...", "active_power_total_kw": 401.2, ...}, ...]
}
```

---

## End-to-end example

```bash
# 1. Bootstrap — full MFM graph + metadata in one call
curl http://100.90.185.31:8090/api/mfm/

# 2. Optionally get just the parameter metadata for one type
curl http://100.90.185.31:8090/api/mfm/5/parameters/

# 3. Open the real-time stream for a specific MFM
wscat -c "ws://100.90.185.31:8090/ws/mfm/5/real-time-monitoring/"

# 4. Hourly history chart, this week
wscat -c "ws://100.90.185.31:8090/ws/mfm/5/voltage-history/?range=this_week&sampling=day"
```

---

## Summary

| Task | Endpoint |
|---|---|
| Full graph + metadata bootstrap | `GET /api/mfm/` |
| Single MFM detail (+ connections) | `GET /api/mfm/{id}/` |
| Just parameter metadata for charts/labels | `GET /api/mfm/{id}/parameters/` |
| One-shot read of latest values | `GET /api/mfm/{id}/live/` |
| One-shot read of recent history | `GET /api/mfm/{id}/history/?minutes=60` |
| Live streaming (per page) | see [`WEBSOCKETS.md`](WEBSOCKETS.md) |

All endpoints are read-only. No authentication is configured yet (`ALLOWED_HOSTS = ['*']`); add DRF permission classes before exposing publicly.
