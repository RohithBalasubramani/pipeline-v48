# CMD Backend — Architecture

How the `lt_panels` Django app is structured: how MFMs are classified, how readings are pulled from the timeseries store, and how WebSockets are organised per page and per equipment type.

---

## 1. The big picture

```
                         ┌──────────────────────────────────────────┐
   Browser (frontend)    │  Daphne / Django Channels (ASGI, :8888)   │
   ───────────────────►  │                                           │
     REST  /api/...       │   REST  → views.py (DRF ViewSets)         │
     WS    /ws/mfm/...    │   WS    → consumers/ (dispatcher→strategy)│
                         └───────────────┬───────────────┬───────────┘
                                         │               │
                      Django "default" DB│               │ external timeseries DB
                      (catalog/topology/  │               │ (per-MFM reading tables)
                       static config)     ▼               ▼
                    ┌────────────────────────┐   ┌──────────────────────────┐
                    │ lt_mfm_type, lt_mfm,   │   │ mfm_lt_115, mfm_tf_09,   │
                    │ lt_parameter,          │   │ mfm_ups_001, …            │
                    │ lt_config_field/value, │   │ (~1 Hz rows, 564M+ total) │
                    │ lt_asset_3d            │   │ queried RAW via psycopg   │
                    └────────────────────────┘   └──────────────────────────┘
```

Two databases, deliberately separated:

| DB | Holds | Accessed via | Writable? |
|---|---|---|---|
| **Django default** | Equipment catalog, topology (SLD wiring), static nameplate config, 3D-asset catalog | Django ORM | yes (admin) |
| **External timeseries** (`lt_panels` PostgreSQL) | Per-meter reading tables (`mfm_*`), ~1 Hz | raw `psycopg` in `services.py` | **read-only** broker |

Django never writes readings — it's a pure read broker over the timeseries DB. The bridge between the two is three columns on each `MFM` row (`db_link`, `table_name`, `panel_id`).

---

## 2. How MFMs are classified

An **MFM** (Multi-Function Meter) is any metered panel/feeder/unit. Every MFM row points at one **MFMType**.

### 2.1 Stored types — `lt_mfm_type` (6 rows)

| `code` | count | examples |
|---|---|---|
| `lt_panel` | 141 | PCC panels, BPDB, PDB, HHF, feeders |
| `ups` | 46 | UPS-01…, UPS Panel 1… |
| `transformer` | 9 | Transformer 1–8, HT Transformer 1 |
| `dg` | 8 | Diesel generators |
| `ht_panel` | 7 | Main HT Panel, HT Panel M1/M2, RTCC, DG Sync |
| `apfc` | 4 | APFC Panel-1…4 |

215 MFMs total.

### 2.2 Derived category — name-prefix override

There is a **7th category that is NOT a stored type**: `pcc_panel`. PCC panels are stored as `lt_panel` but resolved to a `pcc_panel` strategy at dispatch time, by name prefix:

```python
# consumers/_dispatch.py
_PREFIX_CATEGORIES = [('pcc panel', 'pcc_panel')]

def resolve_category(mfm) -> str:
    name = (mfm.name or '').strip().lower()
    for prefix, category in _PREFIX_CATEGORIES:
        if name.startswith(prefix):
            return category
    return mfm.mfm_type.code        # fall back to the stored type
```

So PCC Panel 1 A (`mfm_type = lt_panel`, name starts with "PCC Panel") is served by the `pcc_panel` strategy on every page. This lets PCC panels get bespoke aggregate behaviour without a schema change or reassigning their type.

**Effective category set** = the 6 stored types **+** `pcc_panel` (derived) **+** `sub_panel` (reserved, stub-only).

### 2.3 Topology classification (self-referential)

`MFM` has four asymmetric self-M2M relations defining the single-line diagram wiring:

```python
incoming / outgoing / spare / coupler   # ManyToManyField('self', symmetrical=False)
```

Each produces a hidden through-table of `(from_mfm, to_mfm)` pairs. This is how a PCC panel knows its incomers/outgoings, and how aggregate strategies fan out across feeders.

---

## 3. How data is pulled

### 3.1 The bridge: three columns on `MFM`

```
lt_mfm.db_link     → libpq conn string  ("postgresql://postgres@/lt_panels?host=/run/postgresql")
lt_mfm.table_name  → timeseries table   ("mfm_lt_115")
lt_mfm.panel_id    → row filter         ("MFM-LT-115")
lt_parameter.column_name → which columns exist for this type
```

### 3.2 `services.py` — the read broker

All timeseries access goes through `services.py`. It never uses the ORM for readings — it runs parameterised SQL via a **psycopg connection pool** (one pool per distinct `db_link`, 4–60 connections):

| Function | Returns |
|---|---|
| `fetch_live` | latest row for a panel_id |
| `fetch_window` | last N seconds (rolling window) |
| `fetch_history` | raw rows over trailing N minutes |
| `fetch_bucketed` | AVG/MIN/MAX per time bucket (+ `extra_aggregates`) |
| `fetch_bool_event_combo_per_bucket` / `_records` | rising-edge event counts/records from boolean flags |
| `resolve_range` | named preset (`today`, `last-7-days`, `this-month`…) → (start, end) |

### 3.3 Safety + correctness invariants

- **Column introspection cache** — strategies declare columns optimistically; `services` intersects against the real table and pads missing columns with `null`, so a widget keeps its shape even if a column doesn't exist yet.
- **SQL-safe identifiers** — column names validated against `^[a-zA-Z][a-zA-Z0-9_]{0,62}$` before reaching SQL.
- **Timezone contract** — every pooled connection runs `SET TIME ZONE 'UTC'`; `_to_dt` rejects naïve datetimes. Range presets and bucket edges shift to **IST (`Asia/Kolkata`)** for human-meaningful boundaries while storage/wire stay UTC.

---

## 4. WebSocket architecture — dispatcher → strategy

Every live/historical page is a **dispatcher** (the WebSocket consumer) that picks a **strategy** based on the MFM's category. The dispatcher owns the socket lifecycle; the strategy owns the data shape.

```
WS  /ws/mfm/{id}/{endpoint}/
        │
        ▼
   Dispatcher (per page)         e.g. VoltageCurrentDispatcher
        │  resolve_category(mfm) → "pcc_panel"
        │  lookup_strategy(STRATEGIES, mfm)
        ▼
   Strategy (per type)           e.g. PccPanelVoltageCurrent
        │  reads via services.py
        ▼
   JSON frame → client
```

### 4.1 Strategy lookup + fallback

```python
# consumers/_dispatch.py
def lookup_strategy(strategies, mfm):
    category = resolve_category(mfm)          # name-prefix or stored type
    cls = strategies.get(category)
    if cls: return cls, category
    fallback = mfm.mfm_type.code              # e.g. pcc_panel → lt_panel
    if fallback != category and strategies.get(fallback):
        return strategies[fallback], fallback
    return None, category                     # → 4404 "page not configured"
```

So a `pcc_panel` request first tries the `pcc_panel` strategy, then falls back to `lt_panel`. Missing → clean 4404, not a 500.

### 4.2 The four dispatcher families (base classes)

| Base | File | Used for | Shape |
|---|---|---|---|
| `_BaseLiveDispatcher` | `_base.py` | Live column-row **and** aggregate streams | `snapshot` + `tick`/`widget_update` |
| `_BaseHistoryDispatcher` | `_history_base.py` | Bucketed history with range/sampling | `snapshot` + periodic `update` |
| `_BaseOverviewDispatcher` | `_overview_base.py` | Overview page (gauges, SLD, KPIs) | per-widget envelope |
| `_BaseFanOutDispatcher` | `_fanout_base.py` | Per-feeder fan-out (energy distribution) | parent aggregate or per-feeder |

A strategy is either **column-row** (declares `columns`, dispatcher does the fetch) or **aggregate** (`IS_AGGREGATE = True`, strategy fans out across feeders itself via `aggregate_render`). PCC strategies are almost all aggregate.

### 4.3 Lifecycle, refresh, resilience

- **Live**: snapshot on connect, then `tick` every `interval_seconds` (1–5 s).
- **History**: snapshot on connect, periodic `update` every `refresh` seconds (default 30).
- **Circuit-breaker**: after 10 consecutive refresh failures the socket closes `4500`.
- **Close codes**: `4400` bad request (range/sampling/params), `4404` MFM or page not found, `4500` repeated backend failure.
- **Mid-connection commands**: clients send JSON to switch range/sampling/selection without reconnecting; server replies `widget_update`.

---

## 5. Pages → endpoints → dispatchers

Single source of truth: `page_registry.py`. `routing.py` is **generated** from it (`iter_websocket_endpoints()`), so adding a page is one registry entry. URL pattern: `ws/mfm/{mfm_id}/{endpoint_path}/`.

| Page (`code`) | WebSocket endpoint(s) | Dispatcher | Kind |
|---|---|---|---|
| `overview` | `overview` | OverviewDispatcher | overview |
| `real-time-monitoring` | `real-time-monitoring` | RealTimeMonitoringDispatcher | live |
| `energy-power` | `energy-power` | EnergyPowerDispatcher | live (aggregate) |
| | `demand-profile` | DemandProfileDispatcher | history |
| | `load-anomalies` | LoadAnomaliesDispatcher | history |
| | `energy-power-history` | EnergyPowerHistoryDispatcher | history |
| `energy-distribution` | `energy-distribution` | EnergyDistributionDispatcher | fan-out |
| `voltage-current` | `voltage-current` | VoltageCurrentDispatcher | live (aggregate) |
| | `voltage-history` | VoltageHistoryDispatcher | history |
| | `current-history` | CurrentHistoryDispatcher | history |
| `power-quality` | `power-quality-summary` | PowerQualitySummaryDispatcher | live |
| | `distortion-harmonics` | DistortionHarmonicsDispatcher | live |
| | `power-quality-history` | PowerQualityHistoryDispatcher | history |

`GET /api/mfms/{id}/pages/` returns exactly the pages + WS endpoints valid for that MFM's category (history-only pages are always available; live pages gate on whether a real strategy is registered).

---

## 6. WebSockets classified by type

Each **live** dispatcher carries a `STRATEGIES = {category: StrategyClass}` map. The 7 live dispatchers each define strategies for all categories:

```
                overview  rtm   energy-power  energy-dist  voltage-current  pq-summary  distortion
lt_panel          ✓       ✓        ✓            ✓             ✓               ✓            ✓
transformer       ✓       ✓        ✓            ✓             ✓               ✓            ✓
ht_panel          ✓*      ✓*       ✓*           ✓*            ✓*              ✓*           ✓*
ups               ✓       ✓        ✓            ✓             ✓               ✓            ✓
apfc              ✓       ✓        ✓            ✓             ✓               ✓            ✓
pcc_panel         ✓       ✓        ✓            ✓ (parent)    ✓               ✓            ✓
sub_panel         stub    stub     stub         stub          stub            stub         stub
```

`✓` = concrete strategy · `✓*` = some are stubs pending spec · `stub` = `StubStrategy` (returns `pending: true`).

Key points:
- **`pcc_panel`** strategies are aggregate (fan out across the panel's incomers/outgoings). On `energy-distribution` it uses a separate `PARENT_STRATEGIES` map (parent-level Sankey) vs the per-feeder fan-out other types use.
- **History dispatchers** (`*-history`, `demand-profile`, `load-anomalies`) are largely **type-agnostic** — they bucket whatever columns the strategy declares; PCC falls back to the `lt_panel` history strategy.
- Adding a type to a page = add one entry to that dispatcher's `STRATEGIES`.

### 6.1 Strategy directory layout

Each page is a package under `consumers/`, one module per type:

```
consumers/
  voltage_current/__init__.py     ← dispatcher + STRATEGIES map
                  pcc_panel.py     ← PccPanelVoltageCurrent (aggregate)
                  lt_panel.py, transformer.py, ups.py, …
  energy_power/   …
  _base.py / _history_base.py / _overview_base.py / _fanout_base.py   ← base dispatchers
  _dispatch.py        ← resolve_category / lookup_strategy
  _timefilters.py     ← shared range×sampling vocab (V&C + E&P)
  _common.py / _pq_labels.py / _ep_metrics.py   ← shared label/derivation helpers
  _serializer.py / _notfound.py
```

---

## 7. Time filters (history + aggregate pages)

Shared vocabulary in `_timefilters.py`, used by both the Voltage & Current and Energy & Power PCC dispatchers (single source of truth, so the two pages can't drift):

| `range` | allowed `sampling` | bucket labels |
|---|---|---|
| `today`, `yesterday` | `hourly` (3 h) / `shift` (8 h) | `00:00…` / `A`,`B`,`C` |
| `last-7-days` | `daily` | `D-6 … Today` |
| `last-30-days`, `this-month`, `last-month` | `daily` / `weekly` | day-of-month / `W-N`,`This W` |
| `custom-range` | any | per sampling |

Bucket edges anchor to **IST** (midnight / Monday / 1st-of-month). Illegal combos are rejected with a `4400` close + `{type:"error"}`. Shift edges: 00–08 (A), 08–16 (B), 16–24 (C).

---

## 8. Registry models (Django default DB)

```
Asset3D (lt_asset_3d)            GLB 3D-model catalog, looked up by `key`
   ▲ default_asset_3d
MFMType (lt_mfm_type)            the 6 equipment types
   ▲ mfm_type
MFM (lt_mfm)                     every meter; db_link/table_name/panel_id + topology M2M ×4
Parameter (lt_parameter)         timeseries-COLUMN defs per type   (unique type+column_name)
ConfigField (lt_config_field)    static CONFIG field defs per type  (section + display_order)
ConfigValue (lt_config_value)    static config VALUE per MFM        (unique mfm+field)
```

**Two "field" systems, intentional:**
- `Parameter` = which timeseries columns a type exposes (values live in the external DB).
- `ConfigField`/`ConfigValue` = static nameplate/config EAV (values stored in Django). `ConfigField` defines per type (with a `section` + `display_order` 2-level hierarchy for the nameplate modal); `ConfigValue` holds the per-MFM value. Read via `mfm.get_config(key)` (per-MFM value → field default → caller default, cast by `data_type`).

The recurring pattern: **type-defines-shape, entity-holds-data**. `MFMType` declares the fields/parameters/config a category has; individual `MFM`s carry the values (external table for live, `ConfigValue` for static). That's why one strategy serves all meters of a type, and adding a meter is just an `MFM` row pointed at a timeseries table.

---

## 9. REST surface (views.py)

`MFMViewSet` (router at `/api/mfm/`) — read-only, plus `@action`s:

| Endpoint | Purpose |
|---|---|
| `GET /api/mfm/` · `/api/mfm/{id}/` | list / detail (type, params, topology, 3D asset) |
| `/api/mfm/{id}/pages/` | pages + WS endpoints valid for this MFM |
| `/api/mfm/{id}/parameters/` | column → display-name map |
| `/api/mfm/{id}/live/` | one-shot latest row (REST fallback to the WS) |
| `/api/mfm/{id}/history/` | raw trailing-N-minute rows |
| `/api/mfm/{id}/config/` · `/details/` · `/asset3d/` | static config / nameplate / 3D |

Tree + bootstrap endpoints: `/api/ems/`, `/api/bms/` (sidebar trees, each leaf carries `mfm_id` where it maps to a real MFM), `/api/overview/`, `/api/overview/{slug}/`, `/api/assets/`.

---

## 10. Request flow — worked example

`PCC Panel 1 A`, Voltage & Current tab:

```
1. Page mount → GET /api/mfm/174/        (name, panel_id, topology, 3D)
                GET /api/mfm/174/pages/  (discover WS endpoints)
2. Open WS  → ws/mfm/174/voltage-current/?range=today&sampling=hourly
3. Dispatcher: resolve_category(174) → "pcc_panel"
              lookup_strategy → PccPanelVoltageCurrent (aggregate)
4. Strategy: _load_topology() → 2 incomers + 4 outgoings
             services.fetch_bucketed / fetch_bool_event_combo_* per feeder
5. snapshot frame → {widgets: {config, headline_kpis, event_timeline,
                               other_panels_at_time, selected_period, …}}
6. every 30 s → update frame; client commands (range/bucket/feeder) → widget_update
```

---

## 11. Where to change things

| Task | Edit |
|---|---|
| Add a meter | insert `MFM` row (db_link/table_name/panel_id) — no code |
| Add a page | one entry in `page_registry.py` (routing auto-generates) |
| Support a type on a page | add to that dispatcher's `STRATEGIES` + a strategy module |
| New timeseries column | add a `Parameter` row for the type |
| New nameplate/config field | add a `ConfigField` row (admin) + `ConfigValue`s |
| New range/sampling preset | `_timefilters.py` + `services.resolve_range` |

---

## 12. Related docs

- `PCC_VOLTAGE_CURRENT_INTEGRATION.md` — V&C page wire contract
- `PCC_ENERGY_POWER_INTEGRATION.md` — E&P page wire contract
- `BACKEND_API_AND_WEBSOCKETS.md` — full API + WS reference
- `FRONTEND_INTEGRATION.md` — frontend handoff
