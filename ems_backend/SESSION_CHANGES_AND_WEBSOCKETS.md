# CMD backend — recent session changes + WebSocket architecture guide

Single reference covering every change shipped during this session and how
the WebSocket layer is laid out today. Use it as a hand-off to anyone
joining the backend or the frontend integration.

---

## Part 1 — what changed in this session

### 1.1 Database / DSN

| Date | Change | Files |
|---|---|---|
| 2026-05-31 | **Premier Energies DSN swap** (one-shot) — remapped every MFM's `db_link`, `table_name`, `panel_id` from `lt_panels` to `premier_energies`. Backup snapshot saved before applying. | [premier_energies/swap_mfm_links.py](../premier_energies/swap_mfm_links.py), [premier_energies/mfm_catalog_backup_pre_swap.json](../premier_energies/mfm_catalog_backup_pre_swap.json) |
| 2026-05-31 | **Reversed** — restored every MFM from the backup. Now on `lt_panels` again. Either direction can be replayed by re-running the script / the inline restore. |  |

### 1.2 BMS tree restructure

| Change | Result |
|---|---|
| Reshaped `BMS_TREE` to match Figma: HVAC is the parent of Chillers / AHU / CSU / Air Washer / Air Washer Exhaust. New top-level **CDA** group with Air Compressor + Air Dryer subgroups. **PCW** promoted from leaf to group (Overview + Vaccum Degasser + Pressurization). | 4 top-level sections, 46 leaves, **38 matched to MFMs** (8 unmatched are "Overview" placeholders, by design). |
| Added 8 missing AHU leaves (AHU-4 … AHU-11), 5 Air Washer leaves (-2 … -6), 2 AW Exhaust leaves (-05, -06). | Tree now reflects every catalog MFM in the BMS scope. |
| Renamed labels: `Chiller-0N` → `Chiller-N`, `CSUN` → `CSU-N`, `AHU N` → `AHU-N`. | Matches Figma. |
| Removed CSU-3 and CSU-4 from the tree (catalog rows untouched). |  |

**5 placeholder MFMs created** in the catalog (empty `db_link` / `table_name` / `panel_id`, type = `lt_panel`):
- Vaccum Degasser Unit (id 225)
- Pressurization Unit (id 226)
- Air Washer Exhaust-01 (227)
- Air Washer Exhaust-02 (228)
- Air Washer Exhaust-03 (229)

Files: [lt_panels/views.py](lt_panels/views.py) (`BMS_TREE`).

### 1.3 Harmonics & PQ socket consolidation + FE contract response

**Earlier in the session:** `distortion-harmonics` + `power-quality-history` retired, folded into a single
[`power-quality-summary`](lt_panels/consumers/power_quality_summary/) socket.
PCC-overview Harmonics & PQ tab migrated.

**This session's additions (per FE's `BACKEND_CONTRACT.md`):**

| Where | New fields |
|---|---|
| `pq_priority.rows[i]` | `v_thd_pct`, `i_thd_pk_pct` (window MAX), `dominant_driver` (`'OK'\|'H5'\|'H7'\|'V'\|'PF'\|'N'`) |
| `pq_exposure_share.categories[]` | **`neutral`** category — synthesized in-flight from `kpi_neutral_to_phase_ratio_pct > 10%` per bucket (no simulator change needed) |
| `event_timeline.buckets[i]` | `bucket_iso`, `neutral` |
| `event_timeline` top-level | `range`, `sampling`, `anchor_iso` (duplicates of `timeline_filter` for FE convenience — canonical source remains `timeline_filter`) |
| Commands | New `timeline_time: <ISO>` alias for `timeline_filter: {bucket: "HH:MM"}` |

Files: [lt_panels/consumers/power_quality_summary/pcc_panel.py](lt_panels/consumers/power_quality_summary/pcc_panel.py), [HARMONICS_PQ_FE_CONTRACT_RESPONSE.md](HARMONICS_PQ_FE_CONTRACT_RESPONSE.md).

### 1.4 Energy & Distribution rail-rendering fields

Frontend rail (per-feeder utilization bars) was empty because the backend never shipped capacity/incomer data. Added:

| Where | New fields | Source |
|---|---|---|
| `header.main_meter` | `mfm_id`, `name`, `kwh`, `capacity_kwh`, `utilization_pct`, `status` | Panel's own `incoming_live_load_kw` × window-hours |
| Top-level **`incomers[]`** | `mfm_id, name, type, source_group, kwh, capacity_kwh, utilization_pct, status` | Walks `mfm.incoming` M2M; capacity from incomer's `outgoing_live_load_kw` |
| `consumers[i]` | `capacity_kwh`, `utilization_pct` (existing fields untouched) | Feeder's `incoming_live_load_kw` × hours |
| `sankey.nodes[i]` | `kind`: `'source'\|'meter'\|'stage'\|'load'\|'loss'` | Implicit from layer; now explicit |
| `sankey.nodes[]` | New `loss` node + `dist → loss` link so `dist` outflow sums to measured input | `header.loss_kwh` |

Rated values pulled from the **existing EAV nameplate config** (`ConfigField` / `ConfigValue`). Topology pre-stashes them on each MFM object so the async render doesn't touch the ORM.

Files: [lt_panels/consumers/energy_distribution/pcc_panel.py](lt_panels/consumers/energy_distribution/pcc_panel.py).

**Open caveat (pre-existing, not from this session):** `delivered_kwh` / `loss_kwh` / `loss_pct` on this page still use `MAX − MIN` counter deltas. Numbers are noisy until the same fix that landed on the E&P page is applied here too. Shape is correct; values aren't yet trustworthy.

### 1.5 Detail-tab E&P nameplate + cumulative columns

Per the FE dev's consolidated ask. Two tables touched.

**`lt_panel_config` — 5 new nullable columns**

| Column | Sample (BPDB-01) | Drives |
|---|---:|---|
| `energy_target_kwh_today` | 28560 kWh | "Today's Energy" headline `/target` + TickProgressBar denominator |
| `subsidy_limit_kw` | 1190 kW | Subsidy marker bar position + headline meta |
| `target_efficiency_pct` | 97.0 % | Expected Loss tile + AI summary copy |
| `rated_kw` | 1700 kW | Power Energy Analysis rated-kW reference line |
| `contracted_kw` | 1360 kW | Power Energy Analysis contracted-kW reference line |

All seeded across 141 LT panels (heuristics derived from `rated_capacity_kva` / `contracted_demand_kva`). Simulator's `CREATE TABLE`, `_seed_lt_panel_config`, and INSERT/UPSERT all patched so a fresh `--init-db` produces the same shape.

**Per-MFM `mfm_*` — `loss_energy_today_kwh`**

| Step | Action |
|---|---|
| Live DB | `ALTER TABLE … ADD COLUMN IF NOT EXISTS` applied across **244 `mfm_*` tables** |
| Simulator schema | Added to the universal-cols ALTER block — fresh `--init-db` includes it everywhere |
| State machine | New keys `e_loss_kwh` / `midnight_e_loss_kwh`; accumulator `+= active_power_loss_kw × dt_h` (None-guarded); midnight rollover; derived inject `loss_energy_today_kwh` |
| INSERT mapping | Added to the column list + row dict |
| `seed_parameters.py` | New `Parameter` row: `('loss_energy_today_kwh', 'Active Loss Energy Today', 'derived', 'kWh', 'D-PWR')` — 1 row added per MFM type (5 types) |
| E&P strategy | `loss_energy_today_kwh` appended to `LtPanelEnergyPower.columns` |

Files: [lt_panels/consumers/energy_power/lt_panel.py](lt_panels/consumers/energy_power/lt_panel.py), [lt_panels/management/commands/seed_parameters.py](lt_panels/management/commands/seed_parameters.py), [../lt_panel_simulator.py](../lt_panel_simulator.py).

### 1.6 New `2hour` sampling

Frontend's detail-tab Power Energy Analysis chart wanted 12 bars over a 24 h window; backend's `'hourly'` actually meant 3-hour buckets (8 bars). Solution: added a new sampling option without breaking the old name.

- `'2hour': 2*3600` added to `BUCKET_SECONDS_BY_SAMPLING` and `VALID_SAMPLINGS`.
- Allowed for `today`, `yesterday`, `custom-range`.
- Aliases: `2hour` / `2h` / `two-hour` / `two_hour`.
- Labels reuse the `HH:MM` formatter from the `hourly` branch.
- Verified live: `range=yesterday, sampling=2hour` → 12 buckets `00:00 … 22:00`. The 3-hour `'hourly'` option stays untouched for back-compat.

Files: [lt_panels/consumers/_timefilters.py](lt_panels/consumers/_timefilters.py), [lt_panels/services.py](lt_panels/services.py).

### 1.7 Diagnosed: detail-tab PQ "Page not registered" 4404

Frontend's detail PQ tab was opening the **retired** `ws/mfm/{id}/distortion-harmonics/` endpoint. Backend's catch-all dispatcher returns a 4404 error frame, which the UI renders as empty cards + the "Page not registered" banner. **No backend fix needed** — one-line frontend rename to `power-quality-summary`. Full breakdown: [RETIRED_PQ_ENDPOINTS_FRONTEND_FIX.md](RETIRED_PQ_ENDPOINTS_FRONTEND_FIX.md).

---

## Part 2 — WebSocket architecture

### 2.1 Big picture

```
                  ┌────────────── Django + Daphne (port 8888) ──────────────┐
                  │                                                          │
client ──── WS ── │  routing.py  →  dispatcher  →  strategy (per MFM type)   │
                  │       ↑              ↑                ↑                  │
                  │   page_registry  one per page    one per MFMType         │
                  └──────────┬───────────────────────────────────┬──────────┘
                             │                                   │
                             └──── psycopg pool (lt_panels) ─────┘
```

- **Single ASGI app**, all sockets routed through `routing.py`.
- **`page_registry.py`** is the single source of truth: it lists each page, its endpoint(s), and which dispatcher serves them. `routing.py` builds `websocket_urlpatterns` programmatically from it; `MFMViewSet.pages` builds the per-MFM page list (with `ws_url`) from the same data.
- **Dispatcher per page** (`OverviewDispatcher`, `RealTimeMonitoringDispatcher`, `EnergyPowerDispatcher`, `PowerQualitySummaryDispatcher`, …). Each holds a `STRATEGIES = {mfm_type_code: StrategyClass}` map.
- **Strategy per MFM type** (e.g. `power_quality_summary/pcc_panel.py`, `power_quality_summary/lt_panel.py`). Picks the payload shape and the live/aggregate behaviour.

### 2.2 Two strategy shapes

The same WS path can ship two very different payloads depending on the MFM's type:

| Shape | Used by | Frame layout |
|---|---|---|
| **Per-feeder live stream** (column-row) | `lt_panel`, `transformer`, `ups`, `apfc`, etc. | `{ type, mfm_id, panel_id, page, columns: [...], queue: [...], status: {...}, window_seconds, capacity, count }` — a rolling time-window of rows, one per tick |
| **Aggregate / fleet** (widget envelope) | `pcc_panel` (via name-prefix resolution) | `{ type, mfm_id, page, widgets: { <widget_name>: {...}, ... } }` — discrete UI widgets pre-rendered backend-side |

Aggregate strategies subclass `BaseAggregateEDStrategy` and implement `aggregate_render()` + `handle_command()`. Live strategies subclass `BaseLiveStrategy`.

### 2.3 Category resolution (`resolve_category`)

`mfm.mfm_type.code` gives the literal DB type. But "PCC Panel 1 A" is stored as `lt_panel` yet semantically wants the `pcc_panel` aggregate strategy. The resolver:

1. Try **name prefix**: `"PCC Panel "` → `pcc_panel`.
2. Else use the underlying `mfm_type.code`.

Both keys are tried against each dispatcher's `STRATEGIES` map. This is how mfm 174 (`lt_panel` in the DB) ends up on `power_quality_summary/pcc_panel.py`.

### 2.4 The shared time-filter vocabulary

[`_timefilters.py`](lt_panels/consumers/_timefilters.py) is THE single place that:

- Validates `range × sampling` combinations (e.g. you can't `weekly` a `today` range).
- Resolves a preset to a UTC window anchored to IST.
- Builds chronological bucket edges with labels matching the design system (`HH:MM`, `A/B/C`, `D-N`, `W-N`, `DD`).

Allowed combos:

| `range` | `sampling` |
|---|---|
| `today`, `yesterday` | `hourly` (3 h), **`2hour`** (2 h), `shift` (8 h) |
| `last-7-days` | `daily` |
| `last-30-days`, `this-month`, `last-month` | `daily`, `weekly` |
| `custom-range` | any (+ `start_date`/`end_date`) |

Both V&C and PQ time-filtered dispatchers share this module so they can't drift.

### 2.5 `timeline_filter` — one shared constraint per page

On PCC pages where a tab has multiple time-aware widgets (timeline + inspector + tile counts), backend hoists the filter into a single top-level **`timeline_filter`** widget. Other widgets on the same tab carry no own filter — they render under the page-level constraint. Commands accept `timeline_filter` (canonical), `event_timeline` (alias), and on PQ the new `timeline_time: <ISO>` alias.

### 2.6 Current page → endpoint map

From [`page_registry.py`](lt_panels/page_registry.py):

| Page | Endpoint(s) | Dispatcher |
|---|---|---|
| Overview | `overview` | `OverviewDispatcher` |
| Real-Time Monitoring | `real-time-monitoring` | `RealTimeMonitoringDispatcher` |
| Energy & Power | `energy-power`, `demand-profile`, `load-anomalies`, `energy-power-history` | `EnergyPowerDispatcher`, `DemandProfileDispatcher`, `LoadAnomaliesDispatcher`, `EnergyPowerHistoryDispatcher` |
| Energy Distribution | `energy-distribution` | `EnergyDistributionDispatcher` |
| Voltage & Current | `voltage-current`, `voltage-history`, `current-history` | `VoltageCurrentDispatcher`, `VoltageHistoryDispatcher`, `CurrentHistoryDispatcher` |
| **Power Quality** | **`power-quality-summary`** (single socket — `distortion-harmonics` + `power-quality-history` folded in, now 4404) | `PowerQualitySummaryDispatcher` |

### 2.7 Frame types

| `type` field | When sent |
|---|---|
| `snapshot` | Initial frame on connect — full state |
| `tick` | Auto-refresh while connected (interval per strategy) |
| `widget_update` | Reply to a client command — same payload shape as a snapshot, sometimes scoped to one widget |
| `error` | Validation failures, fetch failures, unknown command — socket stays open |
| `ack` | Per-outgoing fan-out connections receive this for commands they don't accept |

### 2.8 The aggregate-render loop

For aggregate strategies (`IS_AGGREGATE = True`):

1. On connect → `accept` → call `aggregate_render(initial=True)` → emit `snapshot`.
2. Schedule `_aggregate_loop` task: sleep `interval_seconds`, call `aggregate_render(initial=False)`, emit `tick`. Sleep-first so an immediate tick doesn't race with a client command sent right after connect.
3. Client `receive` → `handle_command(cmd)` → if it returns a payload, emit `widget_update`.

If `aggregate_render` raises, the dispatcher sends an `error` frame and closes 4500. If `handle_command` raises (e.g. invalid sampling combo), it sends an `error` and **keeps the socket open** so the client can retry.

### 2.9 Database access from async

Two-layer rule that bit us once:

- ORM calls (`mfm.outgoing.all()`, `mfm.get_config(...)`) must be wrapped in `@database_sync_to_async` or pre-fetched in a sync helper.
- Anything that runs inside `aggregate_render` (the async render path) reads from already-loaded data — never opens a fresh ORM query directly.

Pattern used in `energy_distribution/pcc_panel.py`: `_load_topology` (sync) pre-stashes the rated kW values on each MFM object as plain attributes. The async render reads `mfm._rated_incoming_kw` directly — no ORM.

### 2.10 Connection-pool model

Each unique `db_link` opens its own `psycopg_pool` (4-60 connections, lazy). When a strategy needs a row, it calls `services.fetch_live` / `fetch_history` / `fetch_bucketed` / `fetch_bool_event_combo_*` with `(db_link, table, panel_id, …)`. The pool is keyed by `db_link` string — so the **DSN-swap script restarts Daphne to release old pools**. The Premier-Energies swap script does this for you.

---

## Part 3 — file index

### New / heavily-edited backend files this session

| File | What it owns |
|---|---|
| [lt_panels/views.py](lt_panels/views.py) | `BMS_TREE` (restructured), other static trees, `MFMViewSet`, `/api/mfm/{id}/config/` |
| [lt_panels/consumers/power_quality_summary/pcc_panel.py](lt_panels/consumers/power_quality_summary/pcc_panel.py) | Aggregate PQ strategy: timeline_filter / event_timeline / pq_exposure_share / pq_priority / fleet_matrix / header_kpis / signature. **Plus** `dominant_driver`, `i_thd_pk_pct`, `v_thd_pct`, neutral category, `bucket_iso`, `timeline_time` command. |
| [lt_panels/consumers/energy_distribution/pcc_panel.py](lt_panels/consumers/energy_distribution/pcc_panel.py) | E&D aggregate strategy + new `incomers[]`, capacity/utilization, `main_meter`, sankey `kind` + `loss` node |
| [lt_panels/consumers/energy_power/lt_panel.py](lt_panels/consumers/energy_power/lt_panel.py) | `loss_energy_today_kwh` added to columns list |
| [lt_panels/consumers/_timefilters.py](lt_panels/consumers/_timefilters.py) | `2hour` sampling vocabulary, labels, validator |
| [lt_panels/services.py](lt_panels/services.py) | `2hour` sampling SQL + `VALID_SAMPLINGS` |
| [lt_panels/management/commands/seed_parameters.py](lt_panels/management/commands/seed_parameters.py) | New `loss_energy_today_kwh` Parameter row |

### Simulator (external)

| File | What was patched |
|---|---|
| [/home/rohith/CMD/lt_panel_simulator.py](../lt_panel_simulator.py) | `lt_panel_config` CREATE TABLE adds 5 nameplate cols; `_seed_lt_panel_config` row + INSERT/UPSERT matches; universal-cols ALTER block adds `loss_energy_today_kwh`; state machine integrator for daily loss kWh + midnight rollover; INSERT mapping for the new derived column |

### Documentation generated for the frontend dev

| File | Covers |
|---|---|
| [PCC_PQ_AND_ENERGY_DISTRIBUTION_INTEGRATION.md](PCC_PQ_AND_ENERGY_DISTRIBUTION_INTEGRATION.md) | Full Harmonics & PQ + Energy & Distribution WS contract |
| [HARMONICS_PQ_FE_CONTRACT_RESPONSE.md](HARMONICS_PQ_FE_CONTRACT_RESPONSE.md) | Response to FE's `BACKEND_CONTRACT.md` — what was already shipped, what was added, the `timeline_time` alias |
| [RETIRED_PQ_ENDPOINTS_FRONTEND_FIX.md](RETIRED_PQ_ENDPOINTS_FRONTEND_FIX.md) | "Page 'distortion-harmonics' not registered" diagnosis + one-line FE fix |
| [PCC_VOLTAGE_CURRENT_INTEGRATION.md](PCC_VOLTAGE_CURRENT_INTEGRATION.md) | V&C page contract (pre-existing) |
| [PCC_ENERGY_POWER_INTEGRATION.md](PCC_ENERGY_POWER_INTEGRATION.md) | Energy & Power page contract (pre-existing) |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Whole-system overview |
| [SESSION_CHANGES_AND_WEBSOCKETS.md](SESSION_CHANGES_AND_WEBSOCKETS.md) | **This file** |

---

## Part 4 — verification commands

Quick smoke tests for the major touch-points.

### Config endpoint (5 new nameplate fields)

```bash
curl -s http://127.0.0.1:8888/api/mfm/18/config/ | python3 -c "
import sys, json
cfg = json.load(sys.stdin)['config']
for k in ('energy_target_kwh_today','subsidy_limit_kw','target_efficiency_pct',
          'rated_kw','contracted_kw'):
    print(f'  {k:25s} = {cfg.get(k)!r}')"
```

Expected for BPDB-01: `28560 / 1190 / 97.0 / 1700 / 1360`.

### E&D rail fields

```bash
python3 -c "
import asyncio, json, websockets
async def main():
    async with websockets.connect('ws://127.0.0.1:8888/ws/mfm/174/energy-distribution/') as ws:
        f = json.loads(await asyncio.wait_for(ws.recv(), 15))
        w = f['widgets']
        print('top-level:', sorted(w))
        print('header.main_meter:', w['header']['main_meter'])
        print('incomers count:', len(w['incomers']))
        print('sankey kinds:', sorted({n.get('kind') for n in w['sankey']['nodes']}))
asyncio.run(main())"
```

Expected widget keys include `incomers`; sankey kinds include `'loss'`.

### PQ aggregate frame

```bash
python3 -c "
import asyncio, json, websockets
async def main():
    async with websockets.connect('ws://127.0.0.1:8888/ws/mfm/174/power-quality-summary/') as ws:
        f = json.loads(await asyncio.wait_for(ws.recv(), 15))
        w = f['widgets']
        print('widgets:', sorted(w))
        print('priority row keys:', sorted(w['pq_priority']['rows'][0]))
        print('categories:', [c['key'] for c in w['pq_exposure_share']['categories']])
        print('bucket[0] keys:', sorted(w['event_timeline']['buckets'][0]))
asyncio.run(main())"
```

Expected: row keys include `dominant_driver` + `i_thd_pk_pct` + `v_thd_pct`; categories list includes `neutral`; bucket keys include `bucket_iso` + `neutral`.

### `2hour` sampling

```bash
python3 -c "
import asyncio, json, websockets
async def main():
    async with websockets.connect('ws://127.0.0.1:8888/ws/mfm/174/power-quality-summary/') as ws:
        await ws.recv()
        await ws.send(json.dumps({'timeline_filter': {'range': 'yesterday', 'sampling': '2hour'}}))
        for _ in range(4):
            f = json.loads(await asyncio.wait_for(ws.recv(), 10))
            if f.get('type') == 'widget_update':
                tlf = f['data']['timeline_filter']
                print('buckets:', tlf['bucket_options'])
                return
asyncio.run(main())"
```

Expected: 12 buckets `00:00, 02:00, … 22:00`.

### `loss_energy_today_kwh` live

```sql
SELECT panel_id, ts, active_power_loss_kw, loss_energy_today_kwh
  FROM mfm_lt_003 ORDER BY ts DESC LIMIT 5;
```

Expected: monotonically rising `loss_energy_today_kwh` since midnight IST.

---

## Part 5 — known caveats / pending items

| Item | State |
|---|---|
| `energy-distribution` `loss_pct` / `delivered_kwh` use MAX-MIN counter delta — same bug E&P had | Open. Fix already landed on E&P; equivalent fix not yet on E&D. Numbers noisy until then. |
| V&C event-timeline weekly bucket attribution (UNIX-Thursday floor vs month-anchored edges) | Open. Same fix landed on PQ; not yet applied to V&C. Flagged earlier, not actioned. |
| Simulator PQ boolean event flag columns exist on `mfm_lt_*` only, not on `mfm_ups_*` | Open. UPS feeders silently contribute 0 events. Simulator team to add. |
| Detail-tab Power Quality 4404 ("Page 'distortion-harmonics' not registered") | **Frontend** rename only; backend is correct. See `RETIRED_PQ_ENDPOINTS_FRONTEND_FIX.md`. |
| 5 placeholder BMS MFMs (Vaccum Degasser / Pressurization / AW Exhaust-01/02/03) have empty `db_link` / `table_name` / `panel_id` | Their sockets return empty / pending data. Wire timeseries when topology team provisions. |

---

## Part 6 — change log

| Date | Section |
|---|---|
| 2026-05-31 | DSN swap → premier_energies; reversed same day |
| 2026-05-31 | BMS_TREE restructure + 5 placeholder MFMs |
| 2026-05-31 | E&D rail-rendering: `incomers[]`, capacity/utilization, `main_meter`, sankey kind + loss node |
| 2026-05-31 | PQ FE contract: `dominant_driver`, `i_thd_pk_pct`, `v_thd_pct`, `neutral` category, `bucket_iso`, `anchor_iso`/`range`/`sampling` on event_timeline, `timeline_time` command |
| 2026-06-01 | `lt_panel_config` 5 nameplate cols + per-MFM `loss_energy_today_kwh` + simulator integrator |
| 2026-06-01 | `2hour` sampling added |
| 2026-06-01 | Diagnosed retired-PQ-endpoint frontend issue |
