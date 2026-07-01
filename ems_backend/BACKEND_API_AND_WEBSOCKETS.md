# CMD Backend — Equipment Tree API & WebSocket Design

This document describes the runtime contract the frontend talks to:

1. **Equipment Tree API** — the navigation/topology endpoint that drives the
   left-hand sidebar (`Electrical Equipment`).
2. **WebSocket design pattern** — the dispatcher → strategy architecture
   every live/historical page is built on.
3. **Implemented WebSockets** — every endpoint shipped so far, with wire
   shapes, client commands, and per-MFM-type/category coverage.

Service: `cmd-django` (systemd user unit), Daphne ASGI on port **8888**.

URLs:
- Localhost: `http://localhost:8888`
- LAN: `http://192.168.1.20:8888` · `http://192.168.1.14:8888`
- Tailscale: `http://100.90.185.31:8888`

---

## Part 1 — Equipment Tree API

### Endpoint

```
GET /api/electrical-equipment/
```

Returns the static taxonomy of every equipment node the sidebar should
render under "Electrical Equipment", with the matching backend `MFM.id`
baked into each leaf so the frontend can open WebSockets directly without
a second lookup.

### Response shape

```jsonc
{
  "count": 7,                   // top-level sections (HT/Transformers/PCC/UPS/…)
  "leaf_count": 248,            // total leaf nodes across the tree
  "matched_mfm_count": 204,     // leaves that successfully picked up an mfm_id
  "tree": [
    {
      "id": "eq-pcc",
      "label": "PCC Panels",
      "slug": "pcc-panels",
      "pathOverride": "/electrical/pcc-panels",
      "children": [
        { "id": "eq-pcc-overview", "label": "Overview", "slug": "overview",
          "pathOverride": "/electrical/pcc-panels" },
        {
          "id": "eq-pcc-p1a",
          "label": "PCC Panel 1 A",
          "slug": "panel-1a",
          "mfm_id": 174,                 // ← backend MFM ID
          "children": [
            { "id": "eq-p1a-in", "label": "Incoming", "slug": "incoming",
              "alwaysOpen": true,
              "children": [
                { "id": "eq-p1a-in-s1", "label": "Solar Incomer-1",
                  "slug": "solar-incomer-1", "mfm_id": 10 },
                { "id": "eq-p1a-in-t1", "label": "Incomer-1 (TF-01)",
                  "slug": "incomer-1" }   // no mfm_id — descriptive label
              ]
            },
            { "id": "eq-p1a-out", "label": "Outgoing", "slug": "outgoing",
              "alwaysOpen": true,
              "children": [
                { "id": "eq-p1a-out-u1", "label": "UPS-01 CL:600KVA",
                  "slug": "ups-01", "mfm_id": 12 },
                ...
              ]
            },
            ...
          ]
        },
        ...
      ]
    },
    ...
  ]
}
```

### Node fields

| Field | Type | Required | Meaning |
|---|---|---|---|
| `id` | string | yes | Stable identifier (used as React key + expand-state key) |
| `label` | string | yes | Display label in the sidebar |
| `slug` | string | yes | URL segment appended to the parent path |
| `pathOverride` | string | no | Explicit route to navigate to; falls back to computed `parent_path + slug` if absent |
| `alwaysOpen` | bool | no | True for non-collapsible group headers (Incoming / Outgoing / Spare / Bus Coupler) |
| `mfm_id` | int | no | Backend `MFM.id` if this node corresponds to a real MFM in the DB. **Frontend uses this directly to open WebSockets** (`ws/mfm/{mfm_id}/...`). |
| `children` | NavNode[] | no | Recursive child nodes |

### `mfm_id` resolution

At request time the view calls [`_build_name_to_mfm_id()`](backend/lt_panels/views.py)
to build a `{lower(MFM.name) → MFM.id}` map (single DB query), then walks the
static `ELECTRICAL_EQUIPMENT_TREE` and attaches `mfm_id` wherever a node's
`label` (lowercased + stripped) **case-insensitively matches** an MFM name.

**Skipped on purpose:**
- Group container slugs: `incoming`, `outgoing`, `spare`, `bus-coupler`
  (these are headers, not equipment).
- Descriptive labels with no DB row, e.g. `"Incomer-1 (TF-01)"`,
  `"OG 1 - Transformer 1"`.
- Top-level sections with no own MFM, e.g. `"HT Panel M1"`,
  `"HT Panel M2"` (no MFM seeded yet).

`matched_mfm_count` in the response is the diagnostic: 204 / 248 leaves
matched in the current seed.

### Frontend usage pattern

```js
const { tree } = await fetch('/api/electrical-equipment/').then(r => r.json());

function onNodeClick(node) {
  if (node.mfm_id) {
    ws = new WebSocket(`ws://host:8888/ws/mfm/${node.mfm_id}/voltage-current/`);
  } else {
    // group / descriptive node — expand instead
  }
}
```

### Source

- View: [`backend/lt_panels/views.py:280-345`](backend/lt_panels/views.py#L280-L345)
  (`electrical_equipment`, `_build_name_to_mfm_id`, `_attach_mfm_ids`)
- Static tree: [`backend/lt_panels/electrical_equipment.py`](backend/lt_panels/electrical_equipment.py)
- Route: `path('electrical-equipment/', electrical_equipment)` in
  [`backend/lt_panels/urls.py`](backend/lt_panels/urls.py)

---

## Part 1.5 — Per-MFM Config API

```
GET /api/mfm/{id}/config/
```

Returns the static per-MFM config row (thresholds, nameplate, ratings)
that backs **chart reference lines** (Max-V / Min-V / Max-A / Min-A
bands), the **Nominal V** tile, **PF Target**, **rated kVA / kW**,
**subsidy budgets**, **battery capacity** (UPS), **busbar / thermal
limits**, **PV array nameplate** (LT-Solar). Fetch once at page load —
config doesn't change tick-to-tick.

### Response shape

```jsonc
{
  "mfm_id": 2, "panel_id": "MFM-TF-01",
  "mfm_type": "transformer", "config_table": "transformer_config",
  "config": {
    "nominal_voltage_v": 415.0,
    "rated_kva": 1500.0,
    "voltage_high_threshold_v": 456.5,
    "voltage_low_threshold_v": 373.5,
    "current_high_threshold_a": 2295.49,
    "current_low_threshold_a": 104.34,
    "pf_target": 0.95,
    "v_thd_limit_pct": 5.0,
    "i_thd_limit_pct": 8.0,
    "winding_high_temp_c": 105.0, "oil_high_temp_c": 90.0,
    "hotspot_warning_temp_c": 120.0,
    /* …47 fields total for transformer… */
  }
}
```

### Backing tables (per MFM type)

| MFM type | Config table | Field count |
|---|---|---|
| `transformer` | `transformer_config` | 47 |
| `ups` | `ups_config` | 34 |
| `lt_panel` | `lt_panel_config` | 17 |
| `ht_panel` | `ht_panel_config` | 9 |
| `apfc` | `apfc_config` | 9 |

Common across all five: `panel_id`, `panel_name`, `nameplate_source_label`,
`nameplate_meter_id`, `ct_ratio_primary`, `ct_ratio_secondary`,
`nameplate_voltage_kv`, `kva_rating`, `protection_relay_label`.

**Transformer + UPS additionally carry** the V/I thresholds, PF target,
THD limits, and subsidy budgets. **UPS** adds battery capacity, string
count, topology, test interval, contract limit, busbar temp limit.
**LT panel** (Solar Incomer flavour) adds PV-array nameplate
(`pv_array_rated_kwp`, area, module count, string count,
`inverter_rated_kw`, efficiency, temperature coefficient).

### Source

- View: [`backend/lt_panels/views.py`](backend/lt_panels/views.py)
  `MFMViewSet.config` action
- Helper: [`backend/lt_panels/services.py`](backend/lt_panels/services.py)
  `fetch_config_row()`
- Tables: created by `lt_panel_simulator.py` (`init-db` block); rows seeded
  per panel on init

---

## Part 2 — WebSocket Design

Every live/historical page is exposed as a WebSocket route with the same URL
shape:

```
ws://host:8888/ws/mfm/{mfm_id}/{page-code}/[?optional=params]
```

The frontend always uses the same URL pattern; the backend dispatches on
the MFM's category to pick the right behaviour for that specific equipment.

### Architectural primitives

```
┌────────────────────────────────────────────────────────────────────────────┐
│                            URL routing layer                               │
│                       (lt_panels/routing.py)                               │
└────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                         Dispatcher classes                                 │
│   (1 per page; each is an AsyncWebsocketConsumer registered on a URL)      │
│                                                                            │
│   _BaseLiveDispatcher       column-row delta queue (snapshot + delta tick) │
│   _BaseOverviewDispatcher   widget envelope (column-row OR aggregate)      │
│   _BaseFanOutDispatcher     per-outgoing fan-out OR parent aggregate       │
│   _BaseHistoryDispatcher    date range + sampling, refresh loop, range cmd │
└────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                   Per-(category, page) Strategy classes                    │
│   (1 per category per page; pure Python, no DB I/O of its own UNLESS       │
│    it's an aggregate strategy that does its own multi-source fetching)     │
│                                                                            │
│   BaseLiveStrategy          declares columns + status_rules                │
│   BaseOverviewStrategy      declares widgets list (or IS_AGGREGATE)        │
│   BaseHistoryStrategy       declares columns + extra_aggregates + KPIs     │
│   BaseFanOutStrategy        declares power_column                          │
│   BaseAggregateEDStrategy   parent-level aggregate for energy-distribution │
│   StubStrategy              marker for unconfigured (category, page) pairs │
└────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                          services.py (DB I/O layer)                        │
│   fetch_live, fetch_window, fetch_bucketed, fetch_energy_delta,            │
│   fetch_event_counts_per_bucket, fetch_threshold_crossings_per_bucket,     │
│   resolve_range, get_table_columns (column-tolerance cache)                │
└────────────────────────────────────────────────────────────────────────────┘
```

### Category resolution — name-prefix override

Strategy lookup is **not** purely by `mfm.mfm_type.code`. We have a small
table of name prefixes that promote an MFM into a sub-category for the
purpose of WebSocket dispatch.

```python
# consumers/_dispatch.py
_PREFIX_CATEGORIES = [
    ('pcc panel', 'pcc_panel'),
]

def resolve_category(mfm) -> str:
    name = (mfm.name or '').strip().lower()
    for prefix, category in _PREFIX_CATEGORIES:
        if name.startswith(prefix):
            return category
    return mfm.mfm_type.code

def lookup_strategy(strategies, mfm):
    """Try category first, fall back to mfm_type.code so categories that
    aren't configured for a given page transparently inherit the underlying
    type's behaviour."""
```

**Categories in use today:**

| Category key | Source | Pages with type-specific behaviour |
|---|---|---|
| `lt_panel` | `MFMType.code` | All 7 legacy pages (column-row) + Solar Incomer Overview |
| `transformer` | `MFMType.code` | RTM, V&C, E&P, PQ summary, Distortion-Harmonics, V/C/Demand history, Load Anomalies, Overview |
| `ht_panel` | `MFMType.code` | All stubs |
| `ups` | `MFMType.code` | Overview, RTM, V&C, E&P, PQ summary, Distortion-Harmonics, V/C/PQ/E&P history |
| `apfc` | `MFMType.code` | All stubs |
| `sub_panel` | `MFMType.code` | All stubs (BPDB / PDB — placeholder type) |
| `pcc_panel` | **name prefix** "PCC Panel" | All 6 pages built as aggregate strategies |

Any MFM whose name starts with `"PCC Panel"` (e.g. `PCC Panel 1 A`, `PCC Panel
4`) gets the `pcc_panel` category dispatch even though its underlying
`MFMType.code` is `lt_panel`. To add another named category, append a tuple
to `_PREFIX_CATEGORIES`.

### Two strategy flavours: column-row vs aggregate

Most pages stream a single MFM's measurements as a continuously-sliding
queue. A few pages need to combine data from many MFMs (PCC Panel pages
typically aggregate across `incoming` + `outgoing`). Both flavours sit
behind the same dispatcher base class — the strategy declares which one
it is.

| Flavour | Flag | What the strategy does | What the dispatcher does |
|---|---|---|---|
| **Column-row** (default) | `IS_AGGREGATE = False` | Declares `columns`, `status_rules` | Fetches one row at MFM's table, slides delta queue, emits `enqueue` / `dequeue` per tick |
| **Aggregate** | `IS_AGGREGATE = True` | Implements `async aggregate_render(dispatcher, initial)` and (optionally) `async handle_command(cmd)` | Just runs the loop and forwards client commands to the strategy |

### Wire frames

#### Column-row pages — `snapshot` + `tick` delta queue

```jsonc
// snapshot — sent once on connect
{
  "type": "snapshot",
  "mfm_id": 10, "mfm_name": "solar incomer 1", "panel_id": "MFM-LT-...",
  "mfm_type": "lt_panel", "page": "voltage-current",
  "window_seconds": 60, "capacity": 60,
  "columns": ["voltage_r_n", "voltage_y_n", ...],
  "count": 60,
  "queue": [
    {"ts": "...", "voltage_r_n": 240.1, ...},
    ...60 rows
  ],
  "status": {"voltage_r_deviation_pct": "Normal", ...}
}

// tick — every interval_seconds
{
  "type": "tick",
  "enqueue": [{"ts": "...", "voltage_r_n": 240.4, ...}],   // 0..N new rows
  "dequeue": 1,                                             // # of expired front rows
  "queue_size": 60,
  "status": {...}
}
```

Frontend reconstruction:
```js
let q = [];
ws.onmessage = (e) => {
  const m = JSON.parse(e.data);
  if (m.type === 'snapshot') q = m.queue;
  else if (m.type === 'tick') {
    q.push(...m.enqueue);
    q.splice(0, m.dequeue);
  }
};
```

#### Aggregate pages — `snapshot` + `tick` widget envelope + `widget_update`

```jsonc
// snapshot
{
  "type": "snapshot",
  "mfm_id": 174, "mfm_name": "PCC Panel 1 A", "panel_id": "MFM-LT-115",
  "mfm_type": "pcc_panel", "page": "energy-distribution",
  "ts": "2026-05-12T...",
  "widgets": {
    "config":     {...},
    "header":     {...},
    "consumers":  [...],
    "sankey":     {"nodes": [...], "links": [...]},
    "ai_summary": {"badge": "...", "text": "..."}
  }
}

// tick — same widget shape; full re-render at strategy.interval_seconds
{ "type": "tick", "ts": "...", "widgets": {...} }

// reply to a client command
{ "type": "widget_update", "widget": "<name|__all__>", "data": {...} }
```

#### History pages — `snapshot` + `update` with KPIs

```jsonc
{
  "type": "snapshot",   // initial
  "mfm_id": ..., "page": "voltage-history",
  "range": "today", "start": "...", "end": "...",
  "sampling": "hour",
  "columns": [...],
  "count": 24,
  "buckets": [{"bucket": "...", "voltage_r_n_avg": ..., ...}, ...],
  "kpis": {"max_deviation_pct": ..., "max_deviation_at": "...", ...}
}

// after a client range/sampling command, OR on the refresh poll
{ "type": "update", ... same shape ... }
```

Client commands accepted on history routes:
```jsonc
{"range": "this_week", "sampling": "day"}
{"start": "2026-04-01T00:00:00Z", "end": "...", "sampling": "hour"}
```

### URL query parameters (column-row dispatchers)

| Param | Default | Meaning |
|---|---|---|
| `?window=N` | `strategy.window_seconds` | Snapshot window (seconds) |
| `?interval=N` | `strategy.interval_seconds` | Tick cadence (seconds) |
| `?columns=a,b,c` | (strategy default) | Override the column list |

History dispatchers additionally accept `?range=...`, `?start=...`,
`?end=...`, `?sampling=...`, `?refresh=...`.

### Stub & 4xx behaviour

- If a strategy is a `Stub*Strategy`, the dispatcher accepts the connection
  and emits a single `pending: true` snapshot, then stops:
  ```json
  { "type": "snapshot", "pending": true,
    "note": "Strategy 'apfc/voltage-current' not yet configured" }
  ```
- If the MFM has no `panel_id`: WS closes with code **4400**.
- If no strategy is registered for the MFM's category (and no fallback to
  `mfm_type.code`): WS closes with code **4404**.
- If the MFM doesn't exist: WS closes with code **4404**.
- If a fetch raises: WS closes with code **4500** after sending an `error`
  frame.

### Column-tolerance (services.py)

`get_table_columns(db_link, table)` introspects each timeseries table once
(per process) and caches the result. `fetch_live` / `fetch_window` /
`fetch_bucketed` then **silently drop** any requested columns that don't
exist on the table and pad them with `None` in the response. So strategies
can declare optimistic column lists; missing columns just appear as `null`
in the wire frame instead of erroring.

This is what lets us ship strategies with TODO column names that get
real values flowing the moment the simulator adds the column — no code
change needed.

### Adding a new dispatch / strategy

1. Pick the right base. Most live pages → `_BaseLiveDispatcher`. Range
   pages → `_BaseHistoryDispatcher`. Per-outgoing fan-out → fan-out base
   with `STRATEGIES`. Parent-level aggregate page → fan-out base with
   `PARENT_STRATEGIES`. Widget-shape page → `_BaseOverviewDispatcher`.
2. Add a per-type Python file under `consumers/<page>/`:
   ```python
   from .._base import BaseLiveStrategy
   class TransformerVoltageCurrent(BaseLiveStrategy):
       columns = [...]
       status_rules = {...}
   ```
3. Wire it into the dispatcher's `STRATEGIES` dict in
   `consumers/<page>/__init__.py`.
4. (If a new page) add the route in `routing.py` + page entry in `views.py
   _PAGES` + export from `consumers/__init__.py`.

---

## Part 3 — Design decisions per page

This section documents *why* each page is implemented the way it is.
The architecture in Part 2 is the toolkit; this section is the case-by-case
reasoning for which tools we picked. The same page often needs **different
shapes for different MFM types** — that's the entire reason the
dispatcher/strategy split exists.

### Cross-cutting decisions (apply to every page)

Before going page-by-page, four global choices that shape every wire frame:

#### 3.0.1 — Same URL per page, polymorphic strategy

**Problem.** Should the URL encode the equipment type
(`ws/transformer/{id}/voltage-current/` vs
`ws/pcc/{id}/voltage-current/`)? Or one URL with type-aware behaviour?

**Choice.** One URL per page: `ws/mfm/{id}/{page}/`. Frontend never has to
know the MFM type to construct the URL — it just uses `mfm.id` from the
equipment tree.

**Why.** Two reasons:
1. Lets the equipment tree response stay simple (`mfm_id` + `page slug` is
   enough; no per-type URL templating).
2. Categories can be added (e.g. `pcc_panel` via name-prefix) without any
   URL changes — only the dispatcher's `STRATEGIES` dict gets a new key.

#### 3.0.2 — Stubs send a `pending: true` frame instead of HTTP 404

**Problem.** What happens when a frontend connects to a page that's not
yet specified for that type?

**Choice.** Accept the WebSocket, send a single snapshot with
`pending: true` and a human note, then stop the loop. Don't close 4404.

**Why.** Lets the frontend render a placeholder UI ("waiting for spec")
without special-casing connect failures. Easier to spot which (type, page)
pairs are still unfinished — the frontend can just badge the tab.

#### 3.0.3 — Column-tolerance over schema migration

**Problem.** Strategies need column lists, but the simulator's columns
land *after* the strategy is written.

**Choice.** `services._select_existing()` checks the table schema once
(cached per process), drops columns that don't exist from the `SELECT`
clause, pads them with `None` in the response.

**Why.** Lets us write the full target column catalogue in the strategy
TODAY, ship the WebSocket with placeholder values, and have real values
flow the moment the simulator emits the column — zero backend changes.
Trade-off: we don't catch typos at deploy time (a misspelled column just
shows as `null`). Acceptable because strategies are short and reviewed.

#### 3.0.4 — Backend manages the rolling window (delta queue)

**Problem.** For live time-series, the frontend needs the last N seconds
of data scrolling in. Naive option: backend sends the full window every
tick. Other naive option: backend sends only new rows; frontend tracks
expiration.

**Choice.** *Snapshot establishes the queue once; tick is `enqueue` +
`dequeue` deltas.* Server-side `deque` of timestamps mirrors the client.

**Why.** Frontend logic is trivial (`q.push(...enq); q.splice(0, deq)`).
Bandwidth is minimal (just the delta). Frontend never has to compute
"is this row older than 60 seconds?" — server says explicitly.

---

### Per-page decisions

Pages are listed in tab order. For each: what the page *needs*, the
options considered, the choice, and why.

#### 3.1 — Overview

**What the page needs.** Headline KPIs, status badges, and (for some
types) a topology diagram. Different types want very different layouts:
a transformer wants gauges on its own measurements, while a PCC Panel
wants an SLD aggregating across all incomings/outgoings.

**Per-type approach.**

| Type | Approach | Why |
|---|---|---|
| Transformer | Column-row + widget envelope (`BaseOverviewStrategy` with `widgets = [LiveGauge(...), LiveSpark(...), WindowedKpi(...), ...]`) | One MFM = one row. Each widget block builds itself from the row's fields. Mixed cadence (live gauges every 1s, windowed Energy Consumption widget on range cmd). |
| PCC Panel | Aggregate (`IS_AGGREGATE=True`) — does its own DB fan-out | The SLD shows ALL children with their own kW/breaker_state/status. Can't be built from the panel's own row alone. Strategy walks `mfm.incoming` + `mfm.outgoing` and assembles per-child blocks. Adds `selected_feeder` widget controlled by client cmd. |
| Others | Stubs | Awaiting spec. |

**Architecture impact.** `BaseOverviewStrategy` got the `IS_AGGREGATE`
flag specifically because Overview needed both shapes from day one — the
dispatcher checks the flag and dispatches to the right path
(`render_widgets(row)` vs `aggregate_render(dispatcher, initial)`).

#### 3.2 — Real-Time Monitoring

**What the page needs.** Continuously-updating live values. Same shape
across types in principle, but PCC Panel needs to stream every connected
feeder's queue, not just its own bus.

**Per-type approach.**

| Type | Approach | Window | Tick |
|---|---|---|---|
| LT panel / transformer | Column-row delta queue (single MFM, `BaseLiveStrategy`) | 60 s | 1 s |
| PCC Panel | Aggregate live (`BaseLiveStrategy.IS_AGGREGATE = True`) — strategy maintains per-feeder `deque[row]` | 30 s | 2 s |
| Others | Stubs | — | — |

**The PCC Panel decision.** The page table shows ~10 feeders with their
own queues (kW, kVAR, PF, V, A, I unbal) over time. Two options:

- *Per-feeder dispatcher loop in the dispatcher* — coupling the dispatcher
  to a specific shape.
- *Strategy owns the per-feeder bookkeeping* — dispatcher stays generic;
  the strategy keeps the deques and emits `feeders_enqueue` / `dequeue`.

We picked the second so the dispatcher doesn't grow page-specific
knowledge. This also extended the column-row dispatcher to support
client commands (the strategy receives them via `handle_command(cmd)` and
returns a `widget_update` payload). Same hook is now used by every
aggregate page that needs interactive filters.

#### 3.3 — Voltage & Current

**What the page needs.** *Completely* different intent per type:

- Transformer/LT panel: live phase voltages and currents per phase, with
  history charts for sag/swell/unbalance over a range.
- PCC Panel: a power-quality **event timeline** — bucketed event counts
  across 24 hours, "selected period" KPI tiles, sortable feeder table at
  the selected bucket, sag-by-panel ranking.

**Per-type approach.**

| Type | Approach |
|---|---|
| LT panel / transformer | Column-row + sibling history routes (`voltage-history/`, `current-history/`) for the bucketed charts. Standard pattern. |
| PCC Panel | Aggregate strategy — fixed 3-hour buckets across a 24-hour trailing window from `timeline_time`. 5 widgets, 3 client cmds. |

**The PCC Panel decision — bucket grain.** The screenshot fixed 3-hour
buckets (00, 03, 06, ..., Now). We could have made it user-configurable
via standard `sampling`, but the page is event-summary focused — 3-hour
buckets give a reasonable 8-bar timeline. Hardcoded for clarity, easy to
make configurable later.

**The PCC Panel decision — event counting.** Big design moment. The
simulator's `sag_events_24h` is a *rolling* counter (can decrease as old
events age out of the trailing 24-hour window). We considered:

- `MAX − MIN` over the bucket → broken for rolling counters.
- Walk every raw row in Python and count positive deltas → tens of
  thousands of rows per panel × every snapshot.
- **Sum positive deltas in SQL** → window function `LAG()` + `GREATEST(0,
  v − prev_v)` per bucket. Fast and correct.

Picked option 3. Same trick for "current event" / "neutral stress" counts,
but using rising-edge crossings (`prev <= threshold AND curr > threshold`)
instead of positive deltas — counts distinct events rather than samples
in violation. Both implemented as generic helpers in `services.py`
(`fetch_event_counts_per_bucket`,
`fetch_threshold_crossings_per_bucket`) so they're reusable on any future
page that needs event-from-counter math.

**The cause classifier.** Rule-based, in code, ordered:
1. `sag > 0 OR V dip > 5%` AND `I unbal > 6%` → `"UPS inrush / bus dip"`
2. Same trigger but lower I unbal → `"voltage dip"`
3. `4 ≤ I unbal ≤ 7%` AND `V dev < 3%` → `"light-load or capacitor step"`
4. otherwise → `"normal"`

Code-side rules instead of a DB-side `cause_label` column because the
classification depends on multiple variables and thresholds we may want
to tune without re-running the simulator.

#### 3.4 — Energy & Power

**What the page needs.** Mix of live KPIs (current load, headroom,
driver feeder), windowed energy totals (today/this_week/this_month
selectable), and bucketed history charts. Each component has its own
filter.

**Per-type approach.**

| Type | Approach |
|---|---|
| LT panel / transformer | Column-row, single live stream + sibling `demand-profile/` history socket for the bar chart. |
| PCC Panel | Aggregate strategy with **4 widgets** and **per-widget commands**. Each widget owns its own filter state. |

**The PCC Panel decision — per-widget commands.** Three of the four
widgets are independently filterable (Period Energy: 3-period switch;
Energy Trend: range+sampling; Panel Power Profile: range+sampling). Two
shapes considered:

- One global command (`{range, sampling, period}` applies to all) —
  simpler protocol but loses independence.
- **Per-widget commands** (`{period_energy: {period: 'today'}}`,
  `{energy_trend: {range: 'last_30d', sampling: 'day'}}`, ...) → server
  replies with a `widget_update` for *just that widget*.

Picked per-widget. Bandwidth-cheaper (only the affected widget
re-renders), and matches how the screenshot's filter dropdowns work
(each card has its own).

**Trade-off accepted.** Nameplate constants
(`subsidy_limit_mvah=174.6`, `rated_kw=1850`, `contract_kwh_per_day=25000`,
`sec_target_kwh_per_unit=207`) are **hardcoded at the top of the
strategy file**, not in the MFM model. Quick decision because we don't
have these in the DB yet. When you add the fields, just delete the
`NAMEPLATE` dict and read from `self.mfm.<field>` — no other change.

**UPS-specific addition — `energy-power-history/`.** The UPS Energy &
Power tab has two range-filtered charts (Power Energy Analysis bar chart,
Load Anomalies trace) whose values change with a today/week/month
dropdown. Two options considered:

- *Store one column per window per metric* (~37 new columns:
  `load_surge_events_today/this_week/this_month`,
  `expected_load_band_upper_today_kw/...`, etc.) — wastes storage,
  hardcodes thresholds at write time, breaks if rules change.
- ***Add a new history dispatcher*** that computes everything on-demand
  from raw `active_power_total_kw` over the chosen range.

Picked option 2. Net schema add: **0 new columns** for the windowed
view. Surge/dip thresholds and the expected-load band ± k·σ are
parameters of `compute_kpis`, tunable at query time. The new dispatcher
slots onto `_BaseHistoryDispatcher` with no base-class changes — same
range/sampling/refresh contract as the existing four history pages.

#### 3.5 — Energy & Distribution

**What the page needs.** Two completely different things depending on
the parent's category:

- Transformer/LT panel: per-outgoing live kW totals — tile-per-outgoing.
- PCC Panel: full energy accounting view (header KPIs + ranked consumers
  + Sankey diagram + AI summary).

**Architecture impact.** Same URL (`ws/mfm/{id}/energy-distribution/`)
must serve both shapes. Solution: `_BaseFanOutDispatcher` got a second
strategy table `PARENT_STRATEGIES` (parent-level aggregate). The
dispatcher checks `PARENT_STRATEGIES` first; if the parent's category has
an entry, it uses the rich aggregate envelope and skips the per-outgoing
fan-out entirely. Otherwise falls through to the existing per-child
fan-out path (existing transformer/lt_panel behaviour preserved).

**The PCC Panel decision — load_group rollup.** The Sankey's level-4
bucket nodes ("UPS backed loads", "Lamination heaters") need a
classification per outgoing. Three options:

- Hardcode a `name → group` map in code → fragile.
- Compute on the fly from name patterns → also fragile.
- **Add `load_group` field to MFM model + seed it via name-prefix rules
  (one-time migration)** → static metadata, queryable, editable per row.

Picked option 3. New field on `MFM`, migration `0005_mfm_load_group`,
seed script categorised 96 of 186 MFMs. The Sankey strategy reads
`og.load_group or 'Other'` and groups outgoings → load groups in pure
Python.

**The PCC Panel decision — energy delta math.** The simulator's
`active_energy_import_kwh` is non-monotonic (historical hourly snapshots
~140M kWh coexist with live sub-second samples ~48M kWh). Two options:

- `MAX − MIN` over the window — broken (would always pick from both
  streams and return huge numbers).
- **`latest@end − latest@start`** — uses two single-row probes, one at
  each window boundary. Robust to non-monotonic data.

Picked option 2. Same SQL helper (`fetch_energy_delta`) is now used by
the Energy & Power page too, so any future page needing window-energy
deltas reuses it.

#### 3.6 — Power Quality (Harmonics & PQ on PCC)

**What the page needs.** Per-feeder PQ snapshot — two cards on transformer
(`power-quality-summary` for KPIs, `distortion-harmonics` for
charts), one consolidated page on PCC (the "Harmonics & PQ" tab with a
fleet matrix + ranking + exposure breakdown).

**Per-type approach.**

| Type | Approach |
|---|---|
| LT panel / transformer | Two separate column-row sockets (`power-quality-summary/` + `distortion-harmonics/`) — each renders one card on the transformer page. |
| PCC Panel | Single aggregate socket on `power-quality-summary/` — covers all 4 widgets of the page. The `distortion-harmonics/` socket is left as a stub for `pcc_panel` (frontend doesn't connect to it). |

**Why one socket on PCC vs two on transformer.** The transformer page
has two visually-separate cards with mostly independent data. The PCC
"Harmonics & PQ" page is one page with cross-coupled widgets (selected
feeder highlights both the priority list AND the matrix column AND
updates the header). Cheaper to wire as one aggregate strategy than to
coordinate two sockets across the same selection state.

**Score formula** (PQ Priority widget) is tunable via constants at the
top of the strategy file. Same for exposure thresholds. Numbers are
chosen to match the screenshot's screenshot's distribution and can be
re-tuned without code restructuring.

**UPS-specific addition — `power-quality-history/`.** The UPS Power
Quality tab has two range-filtered chart cards (Distortion & Harmonic
Profile with V-THD/I-THD/H5/H7 toggles, Load Impact & Transformer Stress
with PF Health/PF Angle/K-Stress toggles). Same architectural choice as
the Energy & Power history dispatcher: on-demand SQL aggregation over
raw THD/PF/harmonic columns rather than pre-aggregating per window.

One socket serves both charts because the range filter is shared between
them on the page — splitting into two would force the frontend to send
the same `{"range":...}` command twice. Net schema add: **0 new
columns** for the windowed view. The 10 new PQ columns added in this
iteration are all live tile drivers (filter state, severity label,
issue type, etc.), not aggregates.

#### 3.7 — History pages (Voltage, Current, Demand Profile, Load Anomalies)

**What the pages need.** Date-range bucketed charts with switchable
range/sampling. Same exact contract regardless of equipment type — just
different column lists per type.

**Per-type approach.** Polymorphic via `_BaseHistoryDispatcher`. Each
type's strategy declares `columns`, `extra_aggregates`, and
`compute_kpis(buckets)`. The dispatcher does all the rest: range parsing,
sampling validation, refresh loop, mid-connection range/sampling switch,
KPI assembly.

**Why polymorphic from day one.** Originally the history consumers were
single LT-panel-only classes. When we wired the Transformer V&C page
(needing `voltage-history` + `current-history`), we hit the same problem
as the live consumers — column lists differed per type. We extracted the
dispatcher pattern into `_BaseHistoryDispatcher` (mirroring
`_BaseLiveDispatcher`'s shape), then migrated all four history pages
(`voltage_history/`, `current_history/`, `demand_profile/`,
`load_anomalies/`) into per-type packages. One refactor, four pages
unblocked.

**The Load Anomalies decision.** This page is *only* on the PCC
Energy & Power tab (and possibly transformer's), so we built it as a new
history page rather than overloading an existing one. New dispatcher,
new route, new STRATEGIES dict — same pattern as the existing three
history pages, no special-casing.

---

### Pattern evolution through the build

The architecture didn't land all at once; it accreted as new requirements
showed up. Quick chronological summary:

1. **Single class per page** (legacy `consumers.py`) — 8 hardcoded
   `*Consumer` classes, each with a static `COLUMNS` list tuned for LT
   panel. Worked for one type, didn't generalise.
2. **Dispatcher → strategy** — extracted the connect/loop/snapshot logic
   into `_BaseLiveDispatcher`; per-(type, page) data became
   `BaseLiveStrategy` subclasses keyed in `STRATEGIES`. Frontend URL
   shape preserved. Existing LT panel behaviour ported over by moving
   columns into per-type strategy files. New types added by registering
   new strategies — no dispatcher changes.
3. **Name-prefix categories** — PCC Panels are typed `lt_panel` in the
   DB but presentation differs. Rather than introducing a new MFMType
   (which would require schema changes and re-seeding), added a
   `_PREFIX_CATEGORIES` map and `resolve_category(mfm)` lookup. The
   dispatcher's `lookup_strategy()` tries the resolved category first,
   falls back to `mfm.mfm_type.code`, so categories that don't override
   a particular page transparently inherit the underlying type's
   behaviour.
4. **Aggregate strategies** — PCC Panel pages need to combine data from
   many MFMs (SLD, Sankey, fleet matrix). Instead of making the
   dispatcher fetch multi-source, added an `IS_AGGREGATE` flag on the
   strategy: when true, the dispatcher delegates ALL fetching to the
   strategy via `aggregate_render(dispatcher, initial)`. Strategy is
   free to do `await asyncio.gather(...)` across as many sources as it
   wants. Same pattern added to all four dispatcher bases.
5. **Per-widget commands** — aggregate pages with multiple independent
   filters (Energy & Power, V&C event timeline, Harmonics & PQ matrix)
   each got `handle_command(cmd)` on the strategy + `receive()`
   forwarding on the dispatcher. Wire reply: `{type:"widget_update",
   widget:"<name>", data:{...}}`.
6. **Robust event/energy math** — non-monotonic simulator data forced
   the move from `MAX-MIN` to `latest@end − latest@start` for cumulative
   meters, and from `SUM(CASE WHEN x > t)` to rising-edge counting for
   threshold events. Both surfaced as generic SQL helpers in
   `services.py`.

The dispatcher/strategy + category pattern has held up across **13
dispatchers and 7 categories** without needing further architectural
changes. New pages and new types slot into existing files with minimal
ceremony — strategy class + register in dict, done.

The two newest dispatchers (`EnergyPowerHistoryDispatcher`,
`PowerQualityHistoryDispatcher`) followed the same recipe: they were
added when the UPS Energy & Power and Power Quality screens introduced
range-filtered bucket charts that weren't covered by the existing four
history pages. No base-class changes were needed — both simply mounted
new strategy packages on `_BaseHistoryDispatcher`.

---

## Part 4 — Implemented WebSockets

### Route table

| URL | Dispatcher | Pattern |
|---|---|---|
| `ws/mfm/<id>/overview/` | `OverviewDispatcher` | Widget envelope (column-row or aggregate) |
| `ws/mfm/<id>/real-time-monitoring/` | `RealTimeMonitoringDispatcher` | Live (column-row OR aggregate) |
| `ws/mfm/<id>/voltage-current/` | `VoltageCurrentDispatcher` | Live (column-row OR aggregate) |
| `ws/mfm/<id>/energy-power/` | `EnergyPowerDispatcher` | Live (column-row OR aggregate) |
| `ws/mfm/<id>/energy-power-history/` | `EnergyPowerHistoryDispatcher` | History (range + sampling) |
| `ws/mfm/<id>/energy-distribution/` | `EnergyDistributionDispatcher` | Fan-out (per-outgoing kW) OR parent aggregate |
| `ws/mfm/<id>/power-quality-summary/` | `PowerQualitySummaryDispatcher` | Live (column-row OR aggregate) |
| `ws/mfm/<id>/power-quality-history/` | `PowerQualityHistoryDispatcher` | History (range + sampling) |
| `ws/mfm/<id>/distortion-harmonics/` | `DistortionHarmonicsDispatcher` | Live (column-row) |
| `ws/mfm/<id>/voltage-history/` | `VoltageHistoryDispatcher` | History (range + sampling) |
| `ws/mfm/<id>/current-history/` | `CurrentHistoryDispatcher` | History (range + sampling) |
| `ws/mfm/<id>/demand-profile/` | `DemandProfileDispatcher` | History (range + sampling) |
| `ws/mfm/<id>/load-anomalies/` | `LoadAnomaliesDispatcher` | History (range + sampling) |

### Per-page coverage matrix

✓ = full strategy implemented; **stub** = pending strategy spec; **fan-out** =
per-outgoing legacy behaviour; **agg** = aggregate strategy.

| Page | lt_panel | transformer | pcc_panel | ht_panel | ups | apfc | sub_panel |
|---|---|---|---|---|---|---|---|
| overview | ✓ (Solar Incomer) | ✓ | ✓ (agg) | stub | ✓ | stub | stub |
| real-time-monitoring | ✓ | ✓ | ✓ (agg, 30s queue) | stub | ✓ | stub | stub |
| voltage-current | ✓ | ✓ | ✓ (agg, event-timeline) | stub | ✓ | stub | stub |
| energy-power | ✓ | ✓ | ✓ (agg, 4 widgets) | stub | ✓ | stub | stub |
| energy-power-history | stub | stub | stub | stub | ✓ | stub | stub |
| energy-distribution | fan-out | fan-out | ✓ (agg, Sankey) | fan-out | fan-out | fan-out | fan-out |
| power-quality-summary | ✓ | ✓ | ✓ (agg, fleet matrix) | stub | ✓ | stub | stub |
| power-quality-history | stub | stub | stub | stub | ✓ | stub | stub |
| distortion-harmonics | ✓ | ✓ | stub | stub | ✓ | stub | stub |
| voltage-history | ✓ | ✓ | stub | stub | ✓ | stub | stub |
| current-history | ✓ | ✓ | stub | stub | ✓ | stub | stub |
| demand-profile | ✓ | ✓ | stub | stub | stub | stub | stub |
| load-anomalies | stub | ✓ | stub | stub | stub | stub | stub |

### PCC Panel pages — detailed wire shapes

#### `overview/` (aggregate)

Widget blocks: `header_status`, `header_kpis`, `sld`, `selected_feeder`.

Cadence: 2 s. Client cmds:
- `{"select_feeder": <mfm_id>}` → updates `selected_feeder`
- `{"clear_feeder": true}` → drops the selection

```jsonc
"widgets": {
  "header_status": {"all": 7, "critical": 0, "warning": 0, "normal": 7},
  "header_kpis": {
    "main_mfm_kw": 4899.5,  "main_mfm_status": "Normal",
    "incoming_kw": 1256.8,  "incoming_count": 2,
    "outgoing_kw": 2610.14, "outgoing_count": 4,
    "avg_pf": 0.903,        "avg_pf_status": "Watch",
    "meter_gap_kw": 2289.36,"meter_gap_status": "Review",
    "alerts_critical": 0, "alerts_total": 0, "alerts_status": "Normal"
  },
  "sld": {
    "incoming": [{"mfm_id": 2, "type": "transformer", "name": "Transformer 1",
                  "kw": 930.17, "breaker_state": "CLOSED", "status": "Normal"}, ...],
    "outgoing": [{"mfm_id": 12, "type": "ups", "name": "UPS-01 CL:600KVA",
                  "kw": 385.87, "breaker_state": "CLOSED", "status": "Normal"}, ...]
  }
}
```

#### `real-time-monitoring/` (aggregate, 30 s per-feeder queue)

Window 30 s, tick 2 s. Streams a per-feeder time-series for every
`incoming` + `outgoing`, with the same delta-queue semantics applied to
each feeder independently.

```jsonc
"widgets": {
  "config": {"window_seconds": 30, "interval_seconds": 2.0,
             "columns": ["kw","kvar","pf","volt","amp","i_unbal"],
             "labels":  {"kw":"KW","kvar":"KVAR","pf":"PF","volt":"VOLT","amp":"AMP","i_unbal":"I UNBAL"}},
  "feeders": [
    {"mfm_id": 12, "name": "UPS-01 CL:600KVA", "type": "ups",
     "role": "outgoing", "label": "U1",
     "queue": [{"ts": "...", "kw": 169, "kvar": 89, "pf": 0.885,
                "volt": 419, "amp": 262, "i_unbal": 7}, ...]},
    ...
  ],
  "selected_feeder": null
}
```

Tick (delta):
```jsonc
{ "type": "tick",
  "widgets": {
    "feeders_enqueue": [
      {"mfm_id": 12, "row": {"ts":"...","kw":184,...}},
      ...one new row per feeder
    ],
    "dequeue": 1
  }
}
```

Client cmds: `{"select_feeder": <mfm_id>}` · `{"clear_feeder": true}`.

#### `voltage-current/` (aggregate, event-timeline view)

5 widgets: `event_timeline`, `other_panels_at_time`, `selected_period`,
`selected_period_mix`, `sag_events_by_panel`. Cadence 30 s.

Bucket grain: **3-hour fixed**, 24-hour trailing window from
`timeline_time` (default = now). Event counts use the dedicated SQL
helpers `fetch_event_counts_per_bucket` (positive-delta sum for sag/swell
on `*_events_24h` rolling counters) and
`fetch_threshold_crossings_per_bucket` (rising-edge count for current
unbalance / neutral stress events).

Cause classifier (rule-based, in order):
1. `sag > 0` OR V dip > 5% AND I unbalance > 6% → `"UPS inrush / bus dip"`
2. Same but lower I unbalance → `"voltage dip"`
3. I unbalance 4–7% AND V dev < 3% → `"light-load or capacitor step"`
4. otherwise → `"normal"`

Client cmds:
- `{"timeline_time": "2026-05-12T18:00:00+05:30"}`
- `{"selected_panel": {"mfm_id": 12}}`
- `{"selected_period": {"bucket": "03:00"}}`

All replies: `{"type":"widget_update","widget":"__all__","data":{...}}`.

#### `energy-power/` (aggregate, 4 widgets)

Widgets: `period_energy`, `energy_trend`, `live_load`, `panel_power_profile`.
Cadence 5 s.

Per-widget client cmds:
- `{"period_energy":       {"period": "today"}}`
   (`this_period | today | this_month`)
- `{"energy_trend":        {"range": "last_30d", "sampling": "day"}}`
- `{"panel_power_profile": {"range": "today", "sampling": "hour"}}`

Reply: `{"type":"widget_update","widget":"<name>","data":{...}}` (just that
widget, not the full envelope).

Hardcoded nameplate constants at the top of
[`pcc_panel.py`](backend/lt_panels/consumers/energy_power/pcc_panel.py)
(subsidy_limit_mvah, rated_kw, contract_kwh_per_day, sec_target). Move to
MFM model fields when the data is available.

#### `energy-distribution/` (parent aggregate)

For `pcc_panel` category, `EnergyDistributionDispatcher` routes through
`PARENT_STRATEGIES` (instead of the per-outgoing fan-out used for
transformer/lt_panel). One rich envelope:

```jsonc
"widgets": {
  "config":     {"ranges":[...], "current_range":"today",
                 "window_start":"...", "window_end":"..."},
  "header":     {"measured_input_kwh": ..., "delivered_kwh": ...,
                 "loss_kwh": ..., "loss_pct": ...,
                 "meter_gap_kwh": ..., "meter_gap_pct": ...,
                 "meter_gap_status": "Review",
                 "best_path": {"mfm_id":13,"name":"UPS-02","share_pct":33.2}},
  "consumers":  [{"mfm_id":13,"name":"UPS-02","load_group":"UPS backed loads",
                  "delivered_kwh":...,"share_pct":33.2,
                  "efficiency_pct":97.9,"status":"Normal"}, ...],
  "sankey":     {"nodes": [...5 layers...], "links": [...]},
  "ai_summary": {"badge":"accounting","text":"..."}
}
```

Sankey layers:
- 0 = incomers
- 1 = "Measured PCC Panel X input"
- 2 = "Distribution allocation"
- 3 = individual outgoings
- 4 = load groups (rolled up via `MFM.load_group`)

Client cmd: `{"range": "this_week"}` (`today | yesterday | this_week |
this_month | last_24h | last_7d`).

Reply: `{"type":"widget_update","widget":"__all__","data":{...full envelope...}}`.

Cadence: 30 s.

Energy delta math: `fetch_energy_delta(...)` does
`latest@end − latest@start` (NOT `MAX − MIN`) so the calculation is robust
to non-monotonic simulator data.

#### `power-quality-summary/` (aggregate, fleet PQ view)

4 widgets: `header_kpis`, `pq_priority`, `fleet_matrix`,
`pq_exposure_share`. Cadence 5 s.

Score formula (tunable constants in
[`pcc_panel.py`](backend/lt_panels/consumers/power_quality_summary/pcc_panel.py)):
```
score = I-THD × 10 + (1 − PF) × 300 + K-factor × 2
```

Exposure thresholds:
- I-THD exposure: `i_thd > 8.0`
- V-THD exposure: `v_thd > 5.0`
- True PF gap: `true_pf < 0.9`
- Neutral stress: `neutral_ratio_pct > 10.0`

Client cmds:
- `{"select_feeder": <mfm_id>}` → re-renders all 4 widgets
- `{"fleet_matrix": {"focus": "h5"}}`
   (`i_thd | v_thd | h5 | h7 | k_factor | pf_gap`) → just the matrix widget

### Transformer pages — wire shapes

#### `overview/` (column-row widget envelope)

Strategy declares a `widgets = [LiveGauge(...), LiveSpark(...),
WindowedKpi(...), Narrative(...)]` list. Dispatcher fetches one row per
tick, hands it to every "live" widget. Widget primitives: `LiveGauge` /
`LiveSpark` / `LiveBars` / `StaticKpi` / `WindowedKpi` / `Narrative`.

15 widgets including: power_factor, voltage_deviation, grid_frequency,
phase_balance, k_factor, hlf, ieee_519, loading, hot_spot, efficiency,
rul, energy_consumption (with `{"widget":"energy_consumption","range":"this_week"}`
filter), kw_load_pct, ai_summary.

#### `real-time-monitoring/` (column-row, 20 cols)

Three live cards on one socket:
- Power & Energy (Active/Reactive Power, Active/Reactive Energy, Projected, Apparent, dKW/dt)
- Voltage Monitor (HV R/Y/B + Avg/Max/Min)
- Current Monitor (HV R/Y/B + Neutral + Avg/Max/Min)

#### `voltage-current/`, `energy-power/`, `power-quality-summary/`, `distortion-harmonics/`

Each ports the corresponding column list + status rules from the original
`MFMLiveConsumer` family — see per-file docstrings for the column
catalogue and which DB columns are TODOs.

### UPS pages — wire shapes

Every UPS page is a column-row live socket on the standard URL pattern
(`ws/mfm/<id>/<page>/`). The two chart-heavy pages (Energy & Power, Power
Quality) also open a sibling history socket for the bucketed charts.

#### `overview/` (column-row widget envelope)

Strategy declares 19 widgets covering the four big KPI tiles (Loading,
Battery Temp, Autonomy, I-Unbalance), the central Input vs Output Voltage
/ Output Load / Output Frequency / Output Phase Balance cards, the four
subsystem-status pills (Rectifier, Inverter, Bypass Sync, Static Switch),
the Energy & Autonomy reserve-runway card, the Output Power Quality card,
and supporting drill-ins (operating mode, transfer inhibit, PF detail).
52 unique columns referenced; all from registered params (`COMMON` +
`UPS_EXTRAS` + `UPS_OVERVIEW_EXTRAS`).

#### `real-time-monitoring/` (column-row, 21 cols)

Three live cards on one socket:
- Power & Energy (Active/Reactive Power · Active/Reactive Energy ·
  Projected · Apparent · dKW/dt · kVAR Trend)
- Voltage Monitor (LV-side L-N R/Y/B + Avg/Max/Min)
- Current Monitor (R/Y/B + Neutral + Avg/Max/Min)

Note: legacy frontend labels these "HV B/R/Y-Phase"; UPS-01 is on the
415 V LV side, so the strategy treats them as L-N. Chart reference lines
(Max-420V / Min-400V / Max-120A / Min-100A) come from the per-UPS
`ups_config` row, not the live stream — fetch once via REST.

#### `voltage-current/` (column-row, 45 cols)

Drives all four cards: Voltage Live Health, Current Live Health, the
header-tile KPIs on Voltage History (Max Deviation today, Worst Spread,
Primary Event, Sag/Swell counts) and Current History (Peak/Avg current,
Max Unbalance, Neutral Peak). The chart traces themselves come from the
sibling `voltage-history/` and `current-history/` sockets. 10 status
rules across per-phase deviations + unbalance + neutral ratio.

New columns: `voltage_max_spread_v`, `voltage_spread_ry_v / yb_v / br_v`
(mirror of `current_spread_*`), `worst_spread_today_pair` (TEXT,
e.g. `"B-Y"`), `primary_voltage_event_today` (TEXT).

#### `energy-power/` (column-row, 37 cols) + `energy-power-history/` (NEW)

Live socket carries the Today's Energy / Input vs Output / Load Anomalies
header tiles plus per-window energy totals (today / this_week /
this_month) and trend status pass-throughs.

The Power Energy Analysis bar chart and Load Anomalies trace chart are
served by the **new** `energy-power-history/` history socket. 3 base
columns aggregated avg/min/max per bucket; `compute_kpis` returns 12
window-level KPIs including on-demand expected-load baseline (mean ±
k·σ) and surge/dip event counts. See "New history dispatchers" below.

#### `power-quality-summary/` (column-row, 34 cols) + `power-quality-history/` (NEW)

Live socket drives the Critical Diagnosis · Current Harmonic Stress ·
Source & mitigation cards. Status labels include `pq_severity_label`,
`pq_filter_state`, `pq_capacitor_bank_state`, `pq_active_issue_count`,
plus pass-through text labels (`pq_critical_issue_type`,
`pq_likely_source_label`, `pq_next_priority_label`,
`pq_nonlinear_signature_label`).

10 new columns in this group (2 Measured + 8 Derived):
- M: `pq_filter_state`, `pq_capacitor_bank_state`
- D: `pq_dominant_harmonic_secondary`, `pq_critical_issue_type`,
  `pq_severity_label`, `pq_active_issue_count`, `pq_likely_source_label`,
  `pq_next_priority_label`, `pq_nonlinear_signature_label`,
  `pf_displacement_gap`

The Distortion & Harmonic Profile chart and Load Impact & Transformer
Stress chart are served by `power-quality-history/`.

#### `distortion-harmonics/` (column-row, 30 cols)

Live legend tiles for both Power Quality charts plus negative-sequence /
true-RMS drill-in. Status rules on PF · True PF · Displacement PF · V-THD
· I-THD · K-factor · Phase Angle · PF Displacement Gap.

#### `voltage-history/` / `current-history/` (UPS strategies)

Same `_BaseHistoryDispatcher` URLs as LT/transformer. UPS strategies add:
- **Expected Range band** in `compute_kpis` (mean ± 1·σ of `voltage_avg`
  / `current_avg` across buckets) — drives the green band on the chart
- For voltage: 4 extra-aggregate columns (sag/swell event counts +
  `MAX(primary_voltage_event_today)` + `MAX(worst_spread_today_pair)`)
- Voltage KPIs: 14 (incl. `expected_band_upper_v / lower_v`,
  `worst_spread_v / at / pair`, `primary_event`, sag/swell counts)
- Current KPIs: 9 (incl. `expected_band_upper_a / lower_a`, peak
  current, average current, max unbalance, neutral peak)

### New history dispatchers (added this iteration)

#### `energy-power-history/` — `EnergyPowerHistoryDispatcher`

Why it exists: the Power Energy Analysis bar chart and Load Anomalies
trace on the Energy & Power tab need range-filtered bucket aggregation
that the existing `demand-profile/` and `load-anomalies/` sockets don't
cover (they're tuned for different visualisations).

Strategy contract (UPS today; other types as stubs):
- `columns = ['active_power_total_kw', 'reactive_power_total_kvar',
   'kpi_kw_load_pct_of_rated']` (avg/min/max per bucket)
- `compute_kpis` returns: `max_load_pct` + at-time, `load_factor`
  (window AVG / MAX), `total_active_kwh` + `total_reactive_kvarh`
  (bucket-avg × bucket-hours), `hourly_avg_power_kw`,
  `expected_load_pct` (window mean), `expected_band_upper/lower` (mean
  ± 1·σ), `surge_events_count`, `dip_events_count`, `bucket_count`,
  `band_k_sigma`.

Critical architectural decision: **no new windowed columns added to the
schema**. All today/week/month aggregates compute on-demand from the
existing raw `active_power_total_kw` series. This avoided ~37 redundant
columns (`load_surge_events_today/this_week/this_month`,
`expected_load_band_upper_today_kw/...`, etc.) and keeps surge/dip
thresholds tunable at query time rather than frozen at write time.

#### `power-quality-history/` — `PowerQualityHistoryDispatcher`

Why it exists: the Distortion & Harmonic Profile chart (V-THD / I-THD /
H5/H7 toggles) and Load Impact & Transformer Stress chart (PF Health /
PF Angle / K-Stress toggles) on the Power Quality tab both need
range-filtered bucket aggregation. Single socket serves both charts
because the time range filter is shared.

Strategy contract (UPS today; other types as stubs):
- `columns` = THD per phase + compliance averages + harmonic orders
  3rd/5th/7th/11th/13th + voltage_avg + PF/True PF/Displacement PF +
  pf_displacement_gap + phase_angle_deg + K-factor + FHL (21 cols)
- `extra_aggregates` = IEEE 519 pass count + sample count for compliance %
- `compute_kpis` returns 16 KPIs: `v_thd_avg/max`, `i_thd_avg/max`,
  `pf_avg/min` + at-time, `true_pf_avg/min`, `k_factor_max` + at-time,
  `pf_displacement_gap_avg`, `h5_avg`, `h7_avg`,
  `ieee519_compliance_pct`, `bucket_count`.

### History pages

All six (`voltage-history`, `current-history`, `demand-profile`,
`load-anomalies`, `energy-power-history`, `power-quality-history`)
follow the same pattern via `_BaseHistoryDispatcher`:

- URL params: `?range=today&sampling=hour&start=&end=&refresh=30`
- Allowed `range`: `today | yesterday | this_week | this_month | last_24h
  | last_7d | last_30d`
- Allowed `sampling`: `minute | 5min | 15min | 30min | hour | day`
- Mid-connection range/sampling switch: `{"range": "this_week", "sampling": "day"}`
  → server replies with a fresh `update` frame.
- Refresh loop polls every `refresh_seconds` (default 30 s).

Per-type strategies live in `consumers/<page>/<type>.py` and declare:
```python
class TransformerLoadAnomalies(BaseHistoryStrategy):
    columns = [...]                     # AVG / MIN / MAX bucketed
    extra_aggregates = {                # SQL fragments for non-AVG/MIN/MAX
        'sag_events': 'MAX(sag_events_24h)',
        ...
    }
    def compute_kpis(self, buckets):    # derived headline KPIs
        ...
```

### Page registry — `/api/mfm/<id>/pages/`

The frontend can ask which pages a given MFM should render and which
WebSockets to open via the `pages` action on the MFM viewset. Output:

```jsonc
{
  "mfm_id": 174, "mfm_name": "PCC Panel 1 A", "mfm_type": "pcc_panel",
  "count": 6,
  "pages": [
    { "code": "overview", "name": "Overview", "order": 1,
      "websockets": [
        { "endpoint_path": "overview", "ws_url": "/ws/mfm/174/overview/",
          "ws_url_abs": "ws://host/ws/mfm/174/overview/",
          "pending": false, "name": "Overview Live" }
      ]},
    { "code": "real-time-monitoring", ... },
    { "code": "energy-power",
      "websockets": [
        { "endpoint_path": "energy-power", ..., "pending": false },
        { "endpoint_path": "demand-profile", ..., "pending": false },
        { "endpoint_path": "load-anomalies", ..., "pending": false }
      ]},
    ...
  ]
}
```

`pending: true` means the strategy for this MFM's category is a stub —
frontend gets an empty-but-shaped snapshot frame.

The page-list is filtered by which pages the MFM's category actually
supports, falling back to `mfm_type.code` when a name-prefix category
doesn't override that page.

---

## Part 5 — File layout

```
backend/lt_panels/
├── models.py                       MFM, MFMType, Parameter (+ load_group field)
├── electrical_equipment.py         ELECTRICAL_EQUIPMENT_TREE constant
├── views.py                        REST: MFMViewSet, electrical_equipment, pages
├── urls.py                         REST routes
├── routing.py                      WS routes (one path → one Dispatcher)
├── services.py                     fetch_live, fetch_window, fetch_bucketed,
│                                   fetch_energy_delta,
│                                   fetch_event_counts_per_bucket,
│                                   fetch_threshold_crossings_per_bucket,
│                                   resolve_range, get_table_columns
├── consumers/                      (the package)
│   ├── _base.py                    BaseLiveStrategy + _BaseLiveDispatcher
│   │                                + StubStrategy
│   ├── _overview_base.py           Widget primitives + BaseOverviewStrategy
│   │                                + _BaseOverviewDispatcher
│   ├── _history_base.py            BaseHistoryStrategy + _BaseHistoryDispatcher
│   ├── _fanout_base.py             BaseFanOutStrategy + BaseAggregateEDStrategy
│   │                                + _BaseFanOutDispatcher
│   ├── _dispatch.py                resolve_category, lookup_strategy
│   ├── _common.py                  shared status-label callables
│   ├── _serializer.py              JSON fallback (datetime, Decimal)
│   │
│   ├── overview/                   ┐
│   ├── real_time_monitoring/       │
│   ├── voltage_current/            │
│   ├── energy_power/               │  Each: __init__.py with the
│   ├── energy_power_history/       │  Dispatcher class + STRATEGIES dict,
│   ├── energy_distribution/        │  plus per-(category, page) strategy
│   ├── power_quality_summary/      │  files (lt_panel.py, transformer.py,
│   ├── power_quality_history/      │  pcc_panel.py, ups.py, etc.)
│   ├── distortion_harmonics/       │
│   ├── voltage_history/            │
│   ├── current_history/            │
│   ├── demand_profile/             │
│   └── load_anomalies/             ┘
```

## Part 6 — Operations

```bash
# Service control
systemctl --user status   cmd-django
systemctl --user restart  cmd-django   # picks up code changes + clears
                                       # column-tolerance cache
journalctl --user -u cmd-django -f     # tail logs

# Quick smoke-test from CLI
python -c "
import asyncio, json
from websockets.client import connect
async def main():
    async with connect('ws://localhost:8888/ws/mfm/174/overview/') as ws:
        print(json.loads(await ws.recv()))
asyncio.run(main())
"
```

---

## Appendix — known data caveats

The simulator's timeseries data has two known artefacts that surface
through correctly-implemented WebSockets as wrong-looking numbers:

1. **`active_energy_import_kwh` is not monotonic** — historical hourly
   snapshots (~140M kWh) coexist with live sub-second samples (~48M kWh)
   in the same panel. We use `latest@end − latest@start` instead of
   `MAX − MIN` (see `fetch_energy_delta`) so the math is correct, but the
   negative deltas reflect the underlying data quality issue.

2. **`sag_events_24h` / `swell_events_24h` are written on every sample**,
   not only on actual events. So
   `fetch_event_counts_per_bucket` (which sums positive deltas) returns
   tens of thousands of "sags" per 3-hour bucket on the live stream. The
   logic is correct; the simulator needs to only increment these counters
   when an actual sag/swell occurs.

Both are simulator-side fixes — no backend changes needed once the source
data is clean.
