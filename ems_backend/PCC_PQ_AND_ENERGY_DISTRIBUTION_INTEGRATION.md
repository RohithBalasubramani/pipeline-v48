# PCC Panel — Harmonics & PQ + Energy & Distribution integration

Frontend reference for two PCC-panel tabs, each served by a **single WebSocket**:

- **Harmonics & PQ** → `ws/mfm/{id}/power-quality-summary/`
- **Energy & Distribution** → `ws/mfm/{id}/energy-distribution/`

Examples use **PCC Panel 1 A** (`mfm_id = 174`). Hosts:
`ws://100.90.185.31:8888` (Tailscale) · `ws://192.168.1.20:8888` (LAN) · `ws://127.0.0.1:8888` (on-box).

> Postman note: after you send a command, the next frame you read may be the periodic auto-refresh `snapshot`/`tick`, not your reply. Keep reading — the command response is the frame with `"type": "widget_update"`.

---

# 1. Harmonics & PQ — `power-quality-summary`

**One socket drives the entire tab** (PQ Inspector, timeline, feeder table, priority, signature radar). The former `distortion-harmonics` and `power-quality-history` endpoints are folded in here and now return a 4404 error frame.

```
ws://<host>:8888/ws/mfm/{mfm_id}/power-quality-summary/
```

Refresh: `snapshot` on connect, then auto-refresh every ~5 s.

## 1.1 Frame shape

```jsonc
{
  "type": "snapshot",                  // or "tick" on refresh; "widget_update" on a command
  "mfm_id": 174, "mfm_type": "pcc_panel", "page": "power-quality",
  "widgets": {
    "timeline_filter":   { ... },   // THE single shared filter (range×sampling+bucket) — §1.2
    "event_timeline":    { ... },   // bucketed event counts + worst-THD overlays + records — §1.3
    "pq_exposure_share": { ... },   // PQ Inspector issue breakdown (follows the filter) — §1.4
    "header_kpis":       { ... },   // IEEE-519 state, exposure, selected feeder — §1.5
    "pq_priority":       { ... },   // ranked worst feeders — §1.6
    "fleet_matrix":      { ... },   // per-feeder metric matrix — §1.7
    "signature":         { ... }    // harmonic radar (selected vs fleet avg) — §1.8
  }
}
```

## 1.2 `timeline_filter` — the ONE shared constraint

Both the timeline **and** the PQ Inspector render under this single filter. Neither carries its own filter config.

```jsonc
{
  "current_range":    "today",
  "range_options":    ["today","yesterday","last-7-days","last-30-days","this-month","last-month","custom-range"],
  "current_sampling": "hourly",
  "sampling_options": ["hourly","shift"],          // legal samplings for the current range
  "bucket_options":   ["00:00","03:00","06:00","09:00","12:00","15:00","18:00","21:00"],
  "selected_bucket":  "21:00",                     // the "at HH:MM" selector
  "window_start": "...", "window_end": "..."       // UTC
}
```

**Allowed range × sampling** (subfilters):

| `range` | `sampling` | bucket labels |
|---|---|---|
| `today`, `yesterday` | `hourly` (3 h) / `shift` (8 h) | `00:00…` / `A`,`B`,`C` |
| `last-7-days` | `daily` | `D-6 … Today` |
| `last-30-days`, `this-month`, `last-month` | `daily` / `weekly` | day-of-month / `W-N`,`This W` |
| `custom-range` | any (+ `start_date`/`end_date`) | per sampling |

## 1.3 `event_timeline` — the chart

```jsonc
{
  "buckets": [
    { "bucket": "21:00",
      "i_thd": 1, "v_thd": 18, "h5": 20, "h7": 15, "k_factor": 18, "pf_gap": 1,   // event counts (bars)
      "worst_i_thd_pct": 24.1, "worst_v_thd_pct": 7.5 },                          // overlay lines
    ...
  ],
  "events": [ { "ts": "...", "type": "k_factor", "mfm_id": 18, "name": "BPDB-01 …" }, … ],  // discrete dots
  "totals": { "i_thd": 1, "v_thd": 18, "h5": 20, "h7": 15, "k_factor": 18, "pf_gap": 1 },
  "total_events": 73
}
```

- **Stacked bars** ← `buckets[i].{i_thd,v_thd,h5,h7,k_factor,pf_gap}`
- **Worst I-THD / Worst V-THD line overlays** ← `buckets[i].{worst_i_thd_pct,worst_v_thd_pct}`
- **Per-event dots** ← `events[]` (capped ~100 per feeder per type)
- Bucket labels come from `timeline_filter.bucket_options` (same order).

## 1.4 `pq_exposure_share` — PQ Inspector issue breakdown

Counts at the **selected bucket** (`timeline_filter.selected_bucket`). Follows the single filter — no own config.

```jsonc
{
  "categories": [
    { "key": "i_thd",    "label": "I-THD",    "rule": "I-THD > 8%",     "count": 1,  "pct": 1.4 },
    { "key": "v_thd",    "label": "V-THD",    "rule": "V-THD > 5%",     "count": 18, "pct": 24.7 },
    { "key": "h5",       "label": "H5",       "rule": "H5 > 6%",        "count": 20, "pct": 27.4 },
    { "key": "h7",       "label": "H7",       "rule": "H7 > 4%",        "count": 15, "pct": 20.5 },
    { "key": "k_factor", "label": "K-Factor", "rule": "K > 8",          "count": 18, "pct": 24.7 },
    { "key": "pf_gap",   "label": "PF gap",   "rule": "True PF < 0.9",  "count": 1,  "pct": 1.4 }
  ],
  "total_issues": 73,
  "thresholds": { "i_thd_pct": 8.0, "v_thd_pct": 5.0, "true_pf": 0.9, "neutral_ratio_pct": 10.0 },
  "footer": "Harmonic review should start with I-THD and H5/H7 drivers, then verify true PF and neutral heating."
}
```

`total_issues` and the per-category counts equal `event_timeline.buckets[selected_bucket]` exactly.

## 1.5 `header_kpis`

```jsonc
{
  "ieee_state":  { "passing": 1, "total": 4, "fail": 3, "watch": 0, "label": "IEEE 519" },
  "pq_exposure": { "status": "danger", "selected_feeder": "UPS-02 …",
                   "avg_i_thd_pct": 19.4, "avg_v_thd_pct": 6.0 },
  "selected_feeder": { "mfm_id": 13, "name": "UPS-02 …", "subtitle": "MFM-UPS-002 - H5 11.8% - H7 5.8%",
                       "status": "danger", "i_thd_pct": 23.1, "v_thd_pct": 6.3,
                       "true_pf": 0.901, "k_factor": 1.8 }
}
```

## 1.6 `pq_priority`

```jsonc
{ "rows": [ { "mfm_id": 13, "name": "UPS-02 …", "score": 264.3, "severity": "high",
              "i_thd_pct": 23.1, "pf": 0.901, "rank": 1, "selected": true }, … ] }
```

## 1.7 `fleet_matrix` — per-feeder metric table

```jsonc
{
  "config":  { "focus_options": ["i_thd","v_thd","h5","h7","k_factor","pf_gap"], "current_focus": "i_thd" },
  "metric_labels": { "i_thd": "I-THD (%)", "v_thd": "V-THD (%)", "h5": "H5 (%)",
                     "h7": "H7 (%)", "k_factor": "K-Factor", "pf_gap": "PF gap (%)" },
  "metrics": ["i_thd","v_thd","h5","h7","k_factor","pf_gap"],
  "feeders": [ { "mfm_id": 12, "label": "U1", "name": "UPS-01 …", "selected": false }, … ],
  "values":  { "i_thd": [12.0, 11.5, …], "v_thd": [...], "h5": [...], … }   // parallel to feeders[]
}
```

## 1.8 `signature` — harmonic radar

```jsonc
{
  "axes":   ["h3","h5","h7","h11","h13","k"],
  "labels": { "h3":"H3","h5":"H5","h7":"H7","h11":"H11","h13":"H13","k":"K" },
  "selected":  { "name": "UPS-01 …", "values": { "h3": 11.8, "h5": 9.6, "h7": 5.9, "h11": 2.3, "h13": 1.9, "k": 1.6 } },
  "fleet_avg": { "h3": 10.0, "h5": 8.4, "h7": 4.7, "h11": 2.2, "h13": 1.6, "k": 1.5 }
}
```

## 1.9 Commands

```jsonc
// THE single filter — updates timeline AND inspector together (re-renders whole frame)
{"timeline_filter": {"range": "last-7-days", "sampling": "daily"}}
{"timeline_filter": {"range": "this-month",  "sampling": "weekly"}}
{"timeline_filter": {"bucket": "18:00"}}                      // "at HH:MM"
{"timeline_filter": {"range": "custom-range", "sampling": "daily",
                     "start_date": "2026-05-20", "end_date": "2026-05-28"}}
// ("event_timeline" is accepted as an alias of "timeline_filter")

// feeder focus (drives signature + header_kpis.selected_feeder)
{"select_feeder": 18}

// fleet-matrix focus metric
{"fleet_matrix": {"focus": "h5"}}
```

Reply: `{"type":"widget_update","widget":"__all__","data":{…all widgets…}}`. Invalid combos → `{"type":"error","message":"sampling='weekly' not allowed for range='today'. …"}` (socket stays open).

## 1.10 The 6 PQ events (how counts are produced)

Each event = one **rising edge** (OK → breach) of a simulator boolean flag, counted per bucket, summed across the panel's outgoing feeders. Reconciles: `sum(per-feeder) == bucket total`.

| `type` | flag column | breach rule |
|---|---|---|
| `i_thd` | `i_thd_event_active` | I-THD > 8 % |
| `v_thd` | `v_thd_event_active` | V-THD > 5 % |
| `h5` | `h5_event_active` | H5 > 6 % |
| `h7` | `h7_event_active` | H7 > 4 % |
| `k_factor` | `k_factor_event_active` | K > 8 |
| `pf_gap` | `pf_gap_event_active` | true PF < 0.9 |

**Caveat:** these flag columns currently exist only on the `mfm_lt_*` tables, **not** on `mfm_ups_*`. For PCC-1A that means only **BPDB-01** produces PQ events today; UPS-01/02/03 read 0 until the simulator adds the columns to the UPS tables (the backend is column-tolerant and will pick them up automatically).

---

# 2. Energy & Distribution — `energy-distribution`

Single socket. This page is a **window aggregate** (Sankey + per-feeder distribution shares) — **not** a time-series, so it has a **range filter only** (no sampling subfilter, no bucketed timeline).

```
ws://<host>:8888/ws/mfm/{mfm_id}/energy-distribution/
```

## 2.1 Frame shape

```jsonc
{
  "type": "snapshot",
  "mfm_id": 174, "mfm_type": "pcc_panel", "page": "energy-distribution",
  "widgets": {
    "config":    { ... },   // range filter — §2.2
    "header":    { ... },   // efficiency / loss / meter-gap KPIs — §2.3
    "consumers": [ ... ],   // per-feeder distribution shares — §2.4
    "sankey":    { ... },   // Energy Flow Diagram (nodes + links) — §2.5
    "ai_summary":{ ... }    // narrative — §2.6
  }
}
```

## 2.2 `config` — range filter

```jsonc
{
  "ranges": ["today","yesterday","this_week","this_month","last_24h","last_7d"],
  "current_range": "today",
  "window_start": "...", "window_end": "..."
}
```

> Note: this page uses the **older underscore range vocab** (`this_week`, `last_7d`), distinct from the `last-7-days` / `daily` × sampling vocabulary on V&C / Energy&Power / PQ. There is no sampling subfilter here.

## 2.3 `header`

```jsonc
{
  "measured_input_kwh": 54934.7,
  "delivered_kwh":      29131.6,
  "loss_kwh":           25803.1,
  "loss_pct":           46.97,
  "meter_gap_kwh":     -25803.1, "meter_gap_pct": -46.97, "meter_gap_status": "Review",
  "best_path": { "mfm_id": 18, "name": "BPDB-01 …", "share_pct": 55.07 }
}
```

## 2.4 `consumers` — per-feeder shares

```jsonc
[ { "mfm_id": 18, "name": "BPDB-01 …", "type": "lt_panel", "load_group": "Lamination heaters",
    "delivered_kwh": 16043.5, "share_pct": 55.07, "efficiency_pct": 53.0, "status": "Critical" }, … ]
```

## 2.5 `sankey` — Energy Flow Diagram

```jsonc
{
  "nodes": [ { "id": "in-2", "label": "Transformer 1", "kwh": 10556.6, "layer": 0, "mfm_id": 2 },
             { "id": "measured", "label": "Measured PCC Panel 1 A input", "kwh": 54934.7, "layer": 1, "mfm_id": 174 },
             { "id": "dist", "label": "Distribution allocation", "kwh": 54934.7, "layer": 2 },
             { "id": "out-18", "label": "BPDB-01 …", "kwh": 16043.5, "layer": 3, "mfm_id": 18, "load_group": "Lamination heaters" }, … ],
  "links": [ { "source": "...", "target": "...", "value": ... }, … ]
}
```

## 2.6 `ai_summary`

```jsonc
{ "text": "…", "badge": "…" }
```

## 2.7 Command

```jsonc
{"range": "this_week"}     // one of config.ranges
```

Reply: `{"type":"widget_update", …}`.

## 2.8 Known caveat (open)

`loss_pct` reads implausibly high (~47%) because the strategy still computes energy via `MAX − MIN` of the cumulative counters, which spike across the simulator's counter discontinuities. The Energy & Power page was already fixed (switched to avg-power × time); the same fix is pending here. Until then, `delivered_kwh` / `loss_kwh` / `loss_pct` and the Sankey magnitudes are unreliable; `consumers[].share_pct` (relative split) is more trustworthy than the absolute kWh.

---

# 3. Quick smoke test

```bash
python3 -c "
import asyncio, json, websockets
async def dump(ep):
    async with websockets.connect(f'ws://100.90.185.31:8888/ws/mfm/174/{ep}/') as ws:
        f = json.loads(await asyncio.wait_for(ws.recv(), timeout=30))
        print(ep, '→', sorted(f['widgets']))
async def main():
    await dump('power-quality-summary')
    await dump('energy-distribution')
asyncio.run(main())
"
```

Expected:
```
power-quality-summary → ['event_timeline','fleet_matrix','header_kpis','pq_exposure_share','pq_priority','signature','timeline_filter']
energy-distribution   → ['ai_summary','config','consumers','header','sankey']
```

---

# 4. Changelog

| Date | Change |
|---|---|
| 2026-05-29 | **Harmonics & PQ consolidated to one socket** (`power-quality-summary`). Added `timeline_filter` (single shared range×sampling+bucket constraint), `event_timeline` (6 PQ event types + worst-THD overlays + discrete records), time-filtered `pq_exposure_share` inspector, and `signature` radar. `distortion-harmonics` + `power-quality-history` folded in (now 4404). |
| 2026-05-29 | PQ events sourced from 6 simulator boolean flags (rising-edge counts, reconciling per feeder). Weekly bucket attribution fixed (fine-grain fetch + range-sum). |
| (existing) | Energy & Distribution `energy-distribution` socket — header / consumers / sankey / ai_summary with a range filter. Energy-counter `loss_pct` artifact still open. |
