# PCC Panel — Energy & Power page integration

Reference for wiring up the **Energy & Power** tab of any PCC Panel page. Covers the single WebSocket, its four widgets, every filter, and the wire-frame shapes.

Examples use **PCC Panel 1 A** (`mfm_id = 174`). Same contract for any PCC panel.

Hosts: `ws://127.0.0.1:8888` · `ws://192.168.1.20:8888` (LAN) · `ws://100.90.185.31:8888` (Tailscale).

---

## 1. The WebSocket

```
ws://<host>:8888/ws/mfm/{mfm_id}/energy-power/
```

- **No connect-time query params needed** — all four widgets render on connect with default filters.
- **Auto-refresh** every **5 s** (the live power card needs the cadence; the rest re-render with it — cheap).
- **First snapshot** ≈ 1.5–2 s.

Frame:

```jsonc
{
  "type": "snapshot",            // or "tick" on the 5 s refresh
  "mfm_id": 174, "mfm_name": "PCC Panel 1 A", "panel_id": "MFM-LT-115",
  "mfm_type": "pcc_panel", "page": "energy-power",
  "widgets": {
    "cumulative":     { ... },   // "Cumulative Energy" card        — §3
    "energy_trend":   { ... },   // "Energy Consumption Trend"       — §4
    "live_power":     { ... },   // "Today live power analysis"      — §5
    "demand_profile": { ... }    // "Daily Power Demand by Feeder"   — §6
  }
}
```

Per-widget filter commands are sent as JSON text frames; the server replies with `{type:"widget_update", widget:"<name>", data:{…}}` (overwrite just that widget). Invalid filters reply with `{type:"error", message:"…"}` and keep the socket open.

---

## 2. Filter summary

| Card | Widget key | Filter control | Command |
|---|---|---|---|
| Cumulative Energy | `cumulative` | Monthly / Weekly / Daily | `{"cumulative": {"period": "weekly"}}` |
| Energy Consumption Trend | `energy_trend` | range × sampling (Total vs By-Equipment is a display toggle over the same data — both shipped inline) | `{"energy_trend": {"range": "last-7-days", "sampling": "daily"}}` |
| Today live power analysis | `live_power` | — (live tick only) | — |
| Daily Power Demand by Feeder | `demand_profile` | Last 30 days / Last 7 days / Today | `{"demand_profile": {"preset": "last-7-days"}}` |

---

## 3. Cumulative Energy — `cumulative`

Filter: `monthly` (this calendar month) · `weekly` (this ISO week) · `daily` (today). The subsidy limit **pro-rates** to the selected period (monthly = full, weekly = limit ÷ 4.33, daily = limit ÷ 30.44).

```jsonc
{
  "config": {
    "periods": ["monthly", "weekly", "daily"],
    "current_period": "monthly",
    "window_start": "...", "window_end": "..."
  },
  "value_mvah":     2979.42,     // apparent energy this period → big number on the card
  "limit_mvah":     3200.0,      // pro-rated subsidy limit (denominator of the bar)
  "pct_used":       93.11,       // value / limit × 100  → progress-bar fill
  "headroom_mvah":  220.58,      // limit − value → "X MVAh left"
  "active_mwh":     2753.73,     // → "Active …" stat
  "reactive_mvarh": 1053.15,     // → "Reactive …" stat
  "sec_kwh_per_t":  33886.5,     // Specific Energy Consumption (real column)
  "sec_target":     207.0,
  "status":         "Watch",     // "On track" <80% | "Watch" <95% | "Over"
  "summary":        "Monthly subsidy headroom is 221.0 MVAh and rated capacity used is 93.1%."
}
```

**Source**: the simulator's pre-computed period counters (`active_energy_this_month_kwh`, `apparent_energy_this_week_kvah`, etc.). Clean rolling totals — no MAX-MIN delta, no counter-reset artifacts.

> The subsidy limit (3200 MVAh/month), rated capacities, and contract lines are **placeholder nameplate constants** in `NAMEPLATE` (top of the strategy) until per-MFM config lands. Scaled to the simulator's data magnitude so the bars read sensibly.

Command: `{"cumulative": {"period": "weekly"}}` → reply `{widget:"cumulative", data:{…}}`.

---

## 4. Energy Consumption Trend — `energy_trend`

Filter: **range × sampling** — identical vocabulary to the Voltage & Current page (see `PCC_VOLTAGE_CURRENT_INTEGRATION.md` §2): today/yesterday/last-7-days/last-30-days/this-month/last-month/custom-range × hourly/shift/daily/weekly (validated combos).

The "Total Energy" vs "By Equipment" toggle is a **frontend display choice** — every bucket carries BOTH the panel-level `active`/`reactive` energy AND the per-equipment-family energy (`ups`/`bpdp`/`hhf`) inline, plus the `rated`/`contracted` reference values scaled to the bucket's duration. No `mode` param needed.

```jsonc
{
  "config": {
    "range_options":    ["today","yesterday","last-7-days","last-30-days","this-month","last-month","custom-range"],
    "current_range":    "last-7-days",
    "sampling_options": ["daily"],          // legal samplings for the current range
    "current_sampling": "daily",
    "window_start": "...", "window_end": "..."
  },
  "buckets": [
    { "bucket": "D-6", "ups": 0.0,     "bpdp": 0.0,     "hhf": 0.0,
                       "active": 0.0,     "reactive": 0.0,
                       "rated": 100000.0, "contracted": 120000.0 },
    { "bucket": "D-3", "ups": 27612.8, "bpdp": 33859.7, "hhf": 0.0,
                       "active": 115926.1, "reactive": 49290.5,
                       "rated": 100000.0,  "contracted": 120000.0 },
    ...
  ]
}
```

Per-bucket fields (all kWh / kVArh):
- `ups`, `bpdp`, `hhf` — energy per equipment family (sum of that family's feeders). Families with no feeders on this panel emit **0** (PCC-1A has no HHF).
- `active`, `reactive` — panel-level energy (use these for the "Total Energy" view).
- `rated`, `contracted` — reference-line values for THIS bucket's duration (a daily bucket gets the per-day value, a weekly bucket 7×, etc.) — draw straight as dashed lines.

Bucket labels follow the V&C convention (`HH:MM` / `A`/`B`/`C` / `D-N`/`Today` / day-of-month / `W-N`/`This W`).

Commands:
```jsonc
{"energy_trend": {"range": "this-month", "sampling": "weekly"}}
{"energy_trend": {"range": "custom-range", "sampling": "daily",
                  "start_date": "2026-05-20", "end_date": "2026-05-28"}}
// invalid → {"type":"error","message":"sampling='weekly' not allowed for range='today'. Allowed: hourly, shift"}
```

> **Energy is computed as average power × duration**, NOT from the cumulative energy counters. The simulator's counters have a mid-month discontinuity (data regenerated, baseline reset) that makes MAX-MIN deltas spike. Power×time is immune to that and is the correct energy-integral approximation.

---

## 5. Today live power analysis — `live_power`

No filter. Refreshes on the 5 s tick.

```jsonc
{
  "apparent_kva":    5371.6,    // → headline kVA
  "rated_kva":       6000.0,    // progress-bar denominator
  "pct_used":        89.5,      // apparent / rated × 100
  "worst_peak_kva":  5512.5,    // → "Worst Peak …" (trailing 7 days)
  "worst_peak_at":   "...",
  "active_kw":       5037.5,    // → "Active … kW"
  "reactive_kvar":   1865.0,    // → "Reactive … kVAr"
  "load_factor_pct": 72.9,      // → "Load Factor … %"
  "summary":         "Live apparent power is 5372 kVA against 6000 kVA rated capacity."
}
```

---

## 6. Daily Power Demand by Feeder — `demand_profile`

Filter: `last-30-days` · `last-7-days` · `today` (each maps to a fixed sampling — 30/7 days → daily buckets, today → 3-hour buckets).

```jsonc
{
  "config": {
    "presets": ["last-30-days", "last-7-days", "today"],
    "current_preset": "last-7-days",
    "window_start": "...", "window_end": "..."
  },
  "buckets": [
    { "bucket": "D-6", "ups": 0.0,    "bpdp": 0.0,    "hhf": 0.0 },
    { "bucket": "D-3", "ups": 1150.5, "bpdp": 1410.8, "hhf": 0.0 },
    ...
  ],
  "critical_kw": 1600.0,                   // → red "Critical" dashed line
  "kpis": {
    "worst_peak_kw":     1511.0,           // highest single-feeder instantaneous reading
    "worst_peak_at":     "D-4",
    "worst_peak_feeder": "BPDB-01 For Lamination-01&02",
    "load_factor_pct":   71.4              // mean aggregate demand / peak aggregate demand
  },
  "summary": "Worst peak 1511 kW (BPDB-01 …); load factor 71%."
}
```

Per-bucket `ups` / `bpdp` / `hhf` is the **average demand (kW) of that family = sum of its feeders** running together (3 UPS feeders → ~3× one UPS). Sum the three families at each bucket for the total demand line. Absent families emit 0.

Command: `{"demand_profile": {"preset": "today"}}` → reply `{widget:"demand_profile", data:{…}}`.

---

## 7. Equipment families

The `ups` / `bpdp` / `hhf` columns are **equipment families** (fixed keys), each the aggregate of the feeders whose name matches that family (`ups` → contains "UPS", `bpdp` → contains "BPDB"/"BPDP", `hhf` → contains "HHF"). A panel that has no feeders in a family emits **0** for it. Feeders that match none (PDB / Spare) don't appear in the per-family breakdown but still count toward the panel-level `active`/`reactive` totals on the energy-trend widget.

---

## 8. Known data caveats (simulator state)

| Symptom | Cause | Resolution |
|---|---|---|
| Energy-trend `D-6`/`D-5` (or early-month) buckets show 0 | Simulator only has continuous recent data (~last 4 days for this panel) | Resolves as the simulator accumulates more days |
| Cumulative/rated percentages look round | `NAMEPLATE` constants are placeholders scaled to the data | Replace with per-MFM nameplate config when available |
| SEC value is large (33886) | Real `specific_energy_consumption` column — simulator's scale | Confirm units with the simulator team |

No backend changes needed for these — they're data/config, not logic.

---

## 9. Quick smoke test

```bash
python3 -c "
import asyncio, json, websockets
async def main():
    async with websockets.connect('ws://100.90.185.31:8888/ws/mfm/174/energy-power/') as ws:
        f = json.loads(await asyncio.wait_for(ws.recv(), timeout=45))
        print('widgets:', sorted(f['widgets']))
        ce = f['widgets']['cumulative']
        print('cumulative:', ce['value_mvah'], '/', ce['limit_mvah'], 'MVAh', ce['pct_used'], '%')
        et = f['widgets']['energy_trend']
        print('energy_trend bucket[2]:', et['buckets'][2])
        await ws.send(json.dumps({'demand_profile': {'preset':'today'}}))
        d = json.loads(await asyncio.wait_for(ws.recv(), timeout=20))['data']
        print('demand_profile buckets:', [{k:b[k] for k in ('bucket','ups','bpdp','hhf')} for b in d['buckets']])
asyncio.run(main())
"
```

---

## 10. Changelog

| Date | Change |
|---|---|
| 2026-05-28 | Cumulative Energy filter → Monthly/Weekly/Daily with pro-rated subsidy limit; sources clean pre-computed period-energy columns + real SEC. |
| 2026-05-28 | Energy Consumption Trend → full range×sampling vocab (shared with V&C page) + Total/By-Equipment (per-feeder) mode. Energy computed from avg-power×time (counter-reset-immune). |
| 2026-05-28 | Daily Power Demand by Feeder → Last 30 days / Last 7 days / Today presets, per-feeder demand series + worst-peak / load-factor KPIs. |
| 2026-05-28 | Time-filter vocabulary extracted to `consumers/_timefilters.py` and shared between the V&C and E&P PCC dispatchers (single source of truth). |
| 2026-05-28 | **Contract reshaped to the frontend mapper spec**: widget keys are now `cumulative` / `live_power` / `energy_trend` / `demand_profile`. `energy_trend.buckets[]` carry `ups`/`bpdp`/`hhf`/`active`/`reactive`/`rated`/`contracted` inline (mode toggle dropped — both views from one payload). `demand_profile.buckets[]` carry `ups`/`bpdp`/`hhf` + top-level `critical_kw`. Families are equipment-type aggregates (sum of feeders), 0 for absent families. Commands renamed to match widget keys. Frontend can flip `PANEL_OVERVIEW_EP_API_ENABLED = true`. |
