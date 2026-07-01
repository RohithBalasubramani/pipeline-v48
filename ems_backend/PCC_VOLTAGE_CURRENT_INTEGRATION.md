# PCC Panel — Voltage & Current page integration

Reference for the frontend developer wiring up the **Voltage & Current** tab of any PCC Panel page (e.g. `/electrical/pcc-panels/panel-1a`). Covers every WebSocket and REST endpoint the page touches, the wire-frame shape, the supported filter/command set, and known gaps.

All examples below use **PCC Panel 1 A** (`mfm_id = 174`, `panel_id = "MFM-LT-115"`). Swap the id for any other PCC panel — same contract applies, because PCC panels are routed through the `pcc_panel` strategy bucket regardless of which row in the MFM table they live in (the dispatcher maps any MFM whose name starts with "PCC Panel" to the PCC strategy via name-prefix).

Hosts (pick whichever is reachable from the dev box):

```
Localhost   http://127.0.0.1:8888       ws://127.0.0.1:8888
LAN         http://192.168.1.20:8888    ws://192.168.1.20:8888
Tailscale   http://100.90.185.31:8888   ws://100.90.185.31:8888
```

---

## 1. Page boot sequence

Three calls in order — none of them block the others, so make them in parallel:

| # | Call | Purpose | Frequency |
|---|---|---|---|
| 1 | `GET /api/mfm/174/` | Panel name, panel_id, mfm_type, topology (incoming/outgoing/spare/coupler), resolved 3D asset | once on mount |
| 2 | `GET /api/mfm/174/config/` | Nameplate strip — nominal voltage (415 V AC), frequency (50 Hz), Icw (50 kA), per-MFM thresholds | once on mount |
| 3 | `GET /api/mfm/174/pages/` | Discovery of all tabs available for this MFM + WebSocket endpoint paths | once on mount, cache |
| 4 | Open WS `ws/.../mfm/174/voltage-current/` | Live data for everything on the V&C tab | persistent |

Optional bootstrap if the page also shows the 3D model:

| Call | Purpose |
|---|---|
| `GET /api/overview/pcc-panel-1a/` | 3D GLB asset + topology in one round-trip |

---

## 2. The WebSocket

**URL**

```
ws://<host>:8888/ws/mfm/{mfm_id}/voltage-current/
```

**Connect-time query params** (all optional)

| Param | Default | Accepts |
|---|---|---|
| `range` | `today` | `today`, `yesterday`, `last-7-days`, `this-month`, `last-month`, `custom-range` |
| `sampling` | depends on range | `hourly` (3 h), `shift` (8 h), `daily`, `weekly` |
| `start_date`, `end_date` | — | `YYYY-MM-DD` (IST midnight). Required when `range=custom-range`; ignored otherwise. ISO 8601 datetime also accepted via the same params. |
| `columns` | full set | CSV — defense-in-depth; usually you don't need to override |

**Allowed `range × sampling` combinations**

| `range` | Allowed `sampling` | Default | Bucket labels |
|---|---|---|---|
| `today` | `hourly` / `shift` | `hourly` | `00:00, 03:00, …` (hourly) · `A, B, C` (shift) |
| `yesterday` | `hourly` / `shift` | `hourly` | same as today |
| `last-7-days` | `daily` | `daily` | `D-6, D-5, D-4, D-3, D-2, D-1, Today` (7 buckets) |
| `this-month` | `daily` / `weekly` | `daily` | `D-N, …, D-1, Today` (daily) · `W-N, …, W-1, This W` (weekly) |
| `last-month` | `daily` / `weekly` | `weekly` | day-of-month `01, 02, …, 30/31` (daily) · `W-5, …, W-1` (weekly) |
| `custom-range` | `hourly` / `shift` / `daily` / `weekly` | `hourly` | per-sampling rules (D-N for daily; "Today" if today falls in the window) |

**Rejection contract** — invalid combos (e.g. `range=today&sampling=weekly`, unknown range, `custom-range` with no dates) are rejected hard: WS opens, server sends `{type:"error", message:"…"}` then closes with **code 4400**. No silent coercion — exactly matches the history sockets' contract.

Shift edges (IST): **00–08, 08–16, 16–00** → labels `A`, `B`, `C`.

**Vocabulary aliases** — for back-compat the dispatcher also accepts the older internal forms; you can mix and match: `last_7d` ≡ `last-7-days`, `this_month` ≡ `this-month`, `last_month` ≡ `last-month`, `day` ≡ `daily`, `week` ≡ `weekly`. The `config.range` / `config.sampling` echo always returns the frontend vocab (`last-7-days`, `daily`, …) regardless of which form you sent.

**Refresh cadence**: server pushes a fresh frame every **30 s** automatically. No need to ping or re-subscribe.

**Close codes**

| Code | Reason | Action |
|---|---|---|
| 4400 | bad range / sampling / start-end | fix the URL, retry |
| 4404 | MFM not found, or page not configured for this MFM type | dead-end; surface to user |
| 4500 | 10+ consecutive DB failures (circuit-breaker) | brief backoff + reconnect |

---

## 3. Mid-connection commands

Send these as JSON text frames on the same socket. Server replies with a single frame `{ "type": "widget_update", "widget": "__all__", "data": <full widget set> }` — overwrite all widgets with `data`.

```jsonc
// Switch the trailing window (sampling auto-defaults to first allowed for the new range)
{"range": "last-7-days"}                       // → sampling=daily, 7 buckets D-6…Today
{"range": "this-month", "sampling": "weekly"}  // explicit pair
{"sampling": "shift"}                          // change sub-filter only (must be legal for current range)

// Custom date range (start_date/end_date required, YYYY-MM-DD = IST midnight)
{"range": "custom-range", "sampling": "daily",
 "start_date": "2026-05-20", "end_date": "2026-05-28"}

// Pin a moment as the right-edge of the trailing-24h window (today/yesterday only)
{"timeline_time": "2026-05-27T08:00:00Z"}

// Pick which bucket inside the window drives the right-column widgets.
// Use the EXACT label string the server returned in event_timeline.buckets[i].bucket.
{"selected_period": {"bucket": "18:00"}}     // hourly
{"selected_period": {"bucket": "B"}}         // shift
{"selected_period": {"bucket": "D-3"}}       // daily
{"selected_period": {"bucket": "This W"}}    // weekly

// Highlight one outgoing feeder across the widgets
{"selected_panel": {"mfm_id": 14}}

// Errors — frame is sent then connection stays open for retry (no close)
{"range": "today", "sampling": "weekly"}
// → {"type": "error", "message": "sampling='weekly' not allowed for range='today'. Allowed: hourly, shift"}

{"range": "custom-range", "sampling": "daily"}    // missing dates
// → {"type": "error", "message": "range='custom-range' requires start_date and end_date (YYYY-MM-DD or ISO 8601)"}
```

**Bucket label format**

| `sampling` | label format | example |
|---|---|---|
| `hourly` | `HH:MM` IST | `"18:00"` |
| `shift` | shift name | `"A"` (00–08) / `"B"` (08–16) / `"C"` (16–24) |
| `daily` | `D-N` / `"Today"` for ranges anchored to today (`today`, `last-7-days`, `this-month`, `custom-range` if today is in window) · day-of-month `DD` for `last-month` | `"D-3"`, `"Today"`, `"01"` |
| `weekly` | `W-N` / `"This W"` for `this-month` · `W-N` for `last-month` (no "current" anchor) | `"W-2"`, `"This W"` |

Always echo the label back exactly as the server sent it in `widgets.event_timeline.buckets[i].bucket`. The dispatcher uses string equality on this label when resolving `selected_period.bucket` commands.

---

## 4. Frame shape

```jsonc
{
  "type":      "snapshot",           // or "tick" on auto-refresh, "widget_update" on commands
  "mfm_id":    174,
  "mfm_name":  "PCC Panel 1 A",
  "panel_id":  "MFM-LT-115",
  "mfm_type":  "lt_panel",           // resolves to pcc_panel category server-side
  "page":      "voltage-current",
  "ts":        "...",                // server time
  "window_seconds": 60,              // legacy field, ignore
  "capacity":  60,                   // legacy field, ignore
  "widgets": {
    "config":               { ... },   // active filter state — see §4.1
    "headline_kpis":        { ... },   // top KPI strip            — §4.2
    "event_timeline":       { ... },   // pink/yellow strip + bar chart + dots — §4.3
    "other_panels_at_time": { ... },   // "Other Panels Event" table + radar  — §4.4
    "selected_period":      { ... },   // bucket-options + selected-bucket cross-section — §4.5
    "selected_period_mix":  { ... },   // event-type breakdown of the selected bucket  — §4.6
    "sag_events_by_panel":  { ... }    // per-panel sag totals across the whole window — §4.7
  }
}
```

### 4.1 `config` — active filter state (echo of what the server applied)

```jsonc
{
  "range":         "last-7-days",           // echo using FE vocab (hyphenated)
  "sampling":      "daily",                 // echo using FE vocab
  "timeline_time": "2026-05-27T12:01:18Z",  // window right-edge (UTC)
  "window_start":  "2026-05-20T18:30:00Z",  // UTC start (IST-midnight aligned for daily+)
  "window_end":    "2026-05-27T12:01:18Z",  // UTC end
  "bucket_seconds": 86400,                  // 10800 hourly · 28800 shift · 86400 daily · 604800 weekly
  "selected_panel_mfm_id":  14,             // null until user clicks a feeder
  "selected_bucket_label":  "Today"         // matches event_timeline.buckets[i].bucket exactly
}
```

Use this to render the active filter chips ("Today by Hourly at 18:00") without tracking it client-side.

### 4.2 `headline_kpis` — top KPI strip

```jsonc
{
  "total_events":      7,
  "sag_events":        3,        // → "Sag events 3 (43%)"  — pct = sag/total on the client
  "swell_events":      4,        // → "Swell events 4 (57%)"
  "current_events":    0,
  "neutral_events":    0,
  "worst_v_dev_pct":  -2.84,     // signed, greatest magnitude across the window
  "worst_i_unbal_pct": 7.5       // max across the window
}
```

### 4.3 `event_timeline` — strip + bar chart + per-event dots

```jsonc
{
  "title_status": "4 affected",
  "buckets": [
    { "bucket": "18:00",
      "sag": 3, "swell": 4, "current": 0, "neutral": 0,
      "worst_i_unbal_pct": 7.5, "worst_v_dev_pct": -2.84 },
    ...
  ],
  "events": [
    // discrete dots for the timeline chart — capped at ~100 per panel, sorted by ts
    {"ts": "2026-05-27 12:46:48.768+00:00", "type": "neutral", "mfm_id": 10, "panel": "I6"},
    {"ts": "2026-05-27 12:47:22.720+00:00", "type": "swell",   "mfm_id": 10, "panel": "I6"},
    ...
  ],
  "event_thresholds": {
    // informational — simulator's flip thresholds, not used for counts
    "sag_pct_of_nominal":   92,
    "swell_pct_of_nominal": 108,
    "i_unbalance_pct":      8,
    "neutral_pct_of_phase": 15
  },
  "selected_panel": {              // null when nothing pinned
    "mfm_id": 14, "name": "UPS-03 CL:600KVA", "cause": "voltage dip"
  }
}
```

**Counting model**: counts come from **rising-edge** detection on the simulator's boolean event-flag columns (`sag_event_active`, `swell_event_active`, `current_imbalance_event_active`, `neutral_stress_event_active`). One real event = exactly one increment of `sag` / `swell` / `current` / `neutral` and exactly one record in `events[]`. The two never drift, the counts are NOT pre-aggregated counters from the simulator.

**`event.panel` short-label** (2-3 char chip used in the chart legend) is derived from the source MFM's name:
`U1, U2, …` for UPS · `B1, B2, …` for BPDB · `H1, H2, …` for HHF · `P1, P2, …` for PDB · `I1, I2, …` for Transformer/Incomer/Solar · `F1, F2, …` for generic.

### 4.4 `other_panels_at_time` — "Other Panels Event" table + Current Distribution radar

```jsonc
{
  "time_label": "18:00",            // echo of selected bucket
  "rows": [
    {
      "mfm_id":      14,
      "label":       "U3",          // 2-char chip
      "name":        "UPS-03 CL:600KVA",   // → "Panel Name"
      "sag":         2,             // → "Sag event"
      "swell":       0,             // → "Swell event"
      "current":     0,             // I-imbalance event count in this bucket (NEW)
      "neutral":     0,             // Neutral stress event count in this bucket (NEW)
      "voltage_v":   239.6,         // → "Voltage (V)" — bucket-avg L-N; ×√3 ≈ 415 if you prefer L-L
      "v_dev_pct":  -0.95,          // → "V-Deviation"
      "current_a":   567.2,         // → "Current (A)" — also drives the radar
      "i_unbal_pct": 0.6,           // → "I-Unbalance"
      "v_min":       237.2,         // bonus: tight range info if you want a sparkline
      "v_max":       242.0,
      "cause":       "voltage dip", // classifier label
      "highlight":   "danger",      // "danger" | "warn" | "normal" — color the row
      "selected":    false          // true for the row matching selected_panel_mfm_id
    },
    ...
  ]
}
```

For the **Current Distribution radar**:
- Spokes = each `rows[i]`, spoke value = `current_a`
- Total / Average / Peak panel = `sum / mean / max` over `rows[].current_a` (computed client-side)
- Use `label` as the spoke axis name

For the **table sort**: rows arrive pre-sorted (worst-first by `sag` count, then by cause severity). You can re-sort client-side if the user clicks a column header.

### 4.5 `selected_period` — bucket picker + selected bucket cross-section

```jsonc
{
  "bucket_options": ["00:00", "03:00", "06:00", "09:00", "12:00", "15:00", "18:00"],
  "current_bucket": "18:00",
  "stable_panels":  0,        // count of rows[] with highlight=='normal' AND sag==0
  "affected":       4,        // count of rows[] with highlight=='danger'
  "events":         7,        // total events in the selected bucket (sum of all 4 types)
  "periods":        7,        // total bucket count in the window
  "clean":          0         // alias of stable_panels (legacy)
}
```

Use `bucket_options` to populate the "at" dropdown directly — no need to derive it from `event_timeline.buckets[]`.

### 4.6 `selected_period_mix` — event-type pie / breakdown for the selected bucket

```jsonc
{
  "categories": [
    {"key": "sag",     "label": "Sag events",       "count": 3},
    {"key": "swell",   "label": "Swell events",     "count": 4},
    {"key": "current", "label": "Current events",   "count": 0},
    {"key": "neutral", "label": "Neutral stress",   "count": 0}
  ]
}
```

These are the same numbers in `headline_kpis.{sag,swell,current,neutral}_events` but scoped to the **selected bucket** instead of the **whole window**.

### 4.7 `sag_events_by_panel` — per-panel sag totals across the whole window

```jsonc
{
  "summary": {
    "sag":         12,           // window total
    "panels_hit":  3,            // panels with sag>0 in the selected bucket
    "worst_v_pct": -2.84,
    "worst_i_pct": 7.5
  },
  "rows": [
    { "mfm_id": 14, "name": "UPS-03 CL:600KVA",
      "bucket_count": 3,         // sag count in the selected bucket
      "total":        12,        // ALL event types summed across the window
      "rank":         1,
      "selected":     true },
    ...
  ]
}
```

Use this for a "worst feeders" leaderboard widget if the page calls for one.

---

## 5. REST endpoints used by this page

All read-only. None take request bodies. All return JSON.

### Nameplate / bootstrap

| Method + URL | Returns | Used for |
|---|---|---|
| `GET /api/mfm/{id}/` | MFM detail — name, panel_id, mfm_type, db_link, table_name, parameters, incoming/outgoing/spare/coupler topology, resolved asset_3d | Page header text |
| `GET /api/mfm/{id}/config/` | Per-MFM static config — `nominal_voltage_v`, `frequency_hz`, `icw_ka`, `voltage_low_threshold_v`, `voltage_high_threshold_v`, etc. | Nameplate strip "415 V AC / 50 Hz / 50 kA" |
| `GET /api/mfm/{id}/details/` | Static nameplate sheet | "View more" panel |
| `GET /api/mfm/{id}/pages/` | List of tabs + their WebSocket endpoint paths | Tab discovery |
| `GET /api/mfm/{id}/parameters/` | Per-parameter display-name map — `[{column_name, name, kind, unit, spec}]`. Includes the new event-flag rows (`sag_event_active`, `swell_event_active`, `current_imbalance_event_active`, `neutral_stress_event_active`). | Column header labels |
| `GET /api/mfm/{id}/asset3d/` | Resolved 3D GLB row | 3D viewport (if used) |

### Sidebar / tree (loaded once for the whole app)

| Method + URL | Returns | Notes |
|---|---|---|
| `GET /api/ems/` | Equipment sidebar tree, every leaf carries `mfm_id` where it maps to a real MFM | Use `mfm_id` directly to open WebSockets — no name lookup needed |
| `GET /api/bms/` | BMS sidebar tree, same shape | |

### Raw-row tail (fallback / debugging only — not used by this page's widgets)

| Method + URL | Returns |
|---|---|
| `GET /api/mfm/{id}/history/?minutes=60&columns=voltage_r_n,voltage_y_n,voltage_b_n` | Raw rows from the trailing N minutes (≤ 5000 rows). Used for sparklines / one-shot tails, not for bucketed history. |

---

## 6. Companion WebSockets on the same page

The V&C tab has two **history** sockets that drive smaller widgets (per-phase voltage trend chart, per-phase current trend chart):

| URL | Drives | Filter contract |
|---|---|---|
| `ws/.../mfm/{id}/voltage-history/` | Per-phase R/Y/B voltage trend, Expected Range band, sag/swell counts (now from boolean rising-edges, see §7) | Same `range × sampling` matrix as the live socket |
| `ws/.../mfm/{id}/current-history/` | Per-phase R/Y/B/N current trend, Peak/Avg/Unbalance KPIs | Same |

Both auto-refresh every 30 s, accept the same mid-connection `{range, sampling}` switch commands, and echo the active filter on every frame.

---

## 7. Event-count consistency guarantee

Across **all three** sockets on this page (`voltage-current`, `voltage-history`, `current-history`), event counts and event records are derived from the **same source**:

- The simulator emits 4 boolean columns: `sag_event_active`, `swell_event_active`, `current_imbalance_event_active`, `neutral_stress_event_active`.
- Server-side SQL counts FALSE→TRUE rising edges per bucket using `LAG()`.
- The same query (without aggregation) produces the discrete `events[]` records.

**Implication for the frontend**: if you sum the per-bucket `sag` counts from the timeline, you get the same number as `headline_kpis.sag_events`. If you filter the `events[]` list for `type === "sag"`, you get a representative sample of records (capped per panel) for the chart — the *count* you'd get from `events.filter(...).length` will be ≤ the true total (because of the cap), but the bucketed counts are uncapped and authoritative.

The previous rolling-counter columns (`sag_events_24h`, `swell_events_24h`) are **no longer read** — those were inflated artifacts.

---

## 8. Auto-update flow

```
Client                                   Server
  |                                        |
  |-- WS open ----------------------------->|
  |                                        | resolve range, sampling
  |<-- frame {type:"snapshot", widgets} ---| ← render everything
  |                                        |
  |                          (30 s passes) |
  |<-- frame {type:"tick", widgets} -------| ← merge into UI (full widgets, same shape)
  |                                        |
  |-- {"selected_period":{"bucket":"18:00"}} ->|
  |<-- {type:"widget_update", widget:"__all__", data:{widgets...}} | ← overwrite all widgets
  |                                        |
  |-- {"range":"this_week"} ----------------->|
  |<-- {type:"widget_update", widget:"__all__", data:{widgets...}} |
  |                                        |
  |-- WS close ---------------------------->|
```

The server never sends partial widget patches — every frame ships the full set. Simplest client implementation: replace your whole "page state" object on every frame.

---

## 9. Known gaps

| Section | Status | Plan |
|---|---|---|
| **AI Summary** narrative text + Likely Drivers bullet | Not on the WS frame yet | Pending decision: rules-template vs. LLM hook. For now the frontend should hide this card or render a placeholder. |
| **Energy Consumption Trend chart's Percentage (%) line overlay** | Not on the WS frame yet — only the stacked bars are wired (from `event_timeline.buckets[]`) | Likely just `cumulative_events / total_events × 100` computed client-side from the bucket counts — confirm with design before adding a server field. |

---

## 10. Quick smoke test

```bash
# REST
curl -s http://100.90.185.31:8888/api/mfm/174/        | jq '.name, .panel_id, .mfm_type.code'
curl -s http://100.90.185.31:8888/api/mfm/174/config/ | jq
curl -s http://100.90.185.31:8888/api/mfm/174/pages/  | jq '.[] | {code, name, websockets:[.websockets[].endpoint_path]}'

# WebSocket — uses Python `websockets` for ad-hoc poking
python3 -c "
import asyncio, json, websockets
async def main():
    async with websockets.connect('ws://100.90.185.31:8888/ws/mfm/174/voltage-current/?range=today&sampling=hourly') as ws:
        msg = await asyncio.wait_for(ws.recv(), timeout=10)
        f = json.loads(msg)
        print('widgets:', sorted(f['widgets']))
        print('config :', f['widgets']['config'])
        print('headline:', f['widgets']['headline_kpis'])
asyncio.run(main())
"
```

---

## 11. Changelog (recent backend updates that affect this page)

| Date | Change |
|---|---|
| 2026-05-27 | Live socket now accepts `range × sampling` filter using the frontend's vocabulary: `today` / `yesterday` / `last-7-days` / `this-month` / `last-month` / `custom-range` × `hourly` / `shift` / `daily` / `weekly`. Older underscore forms (`last_7d`, `this_month`, `day`, `week`) still accepted as aliases. Bucket labels follow design-system conventions (`D-N`, `Today`, `A`/`B`/`C`, `W-N`, `This W`). Invalid combos are now rejected hard with WS close 4400 + `{type:"error"}` frame — no more silent fallback to today/hourly. |
| 2026-05-27 | New `headline_kpis` widget shipped: `total_events`, per-type counts, `worst_v_dev_pct`, `worst_i_unbal_pct`. |
| 2026-05-27 | `other_panels_at_time.rows[]` now carries `swell`, `current`, `neutral`, `voltage_v`, `v_dev_pct` in addition to the existing `sag`, `current_a`, `i_unbal_pct`. |
| 2026-05-27 | Event counts & records now derived from the simulator's boolean event-flag columns (rising-edge detection). Counts and discrete records can no longer drift. |
| 2026-05-27 | `voltage-history` socket switched to the same boolean source. `events[]` and `event_counts` ship at frame top-level; per-bucket `sag_events`/`swell_events` removed. |
| 2026-05-27 | `voltage-history` / `current-history` got the same `range × sampling` matrix + auto-aligned bucket boundaries (IST midnight). |
