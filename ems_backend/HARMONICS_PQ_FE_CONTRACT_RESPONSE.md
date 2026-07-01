# Harmonics & PQ — Backend response to frontend's `BACKEND_CONTRACT.md`

Response and changelog for the asks in
[`CMD_V2/src/pages/electrical/lt-pcc/panel-overview/harmonics-pq/BACKEND_CONTRACT.md`](../../CMD_V2/src/pages/electrical/lt-pcc/panel-overview/harmonics-pq/BACKEND_CONTRACT.md).

**Bottom line:** Everything in the FE contract is now serving on
`ws/mfm/{id}/power-quality-summary/`. The mapper can be wired and
`PANEL_OVERVIEW_HPQ_API_ENABLED` can be flipped to `true` — no further
backend changes needed.

---

## 1. Reality vs. the contract doc — what was already done

The FE doc was written before our Harmonics & PQ socket consolidation, so
most of its "we need" list was actually already in place:

| FE doc assumption | Reality |
|---|---|
| "mfm 174 is typed `lt_panel` → hits lt_panel strategy" | False — backend resolves the category by **name prefix** (`"PCC Panel 1 A"` → `pcc_panel`). The frame already reports `mfm_type: pcc_panel` and routes through `power_quality_summary/pcc_panel.py`. **No DB reclassification needed.** |
| "Need 5th widget `event_timeline`" | Already shipping, with **two** bonus line overlays the FE didn't ask for (`worst_i_thd_pct`, `worst_v_thd_pct`). |
| "Need radar signature folded into `fleet_matrix`" | Shipping as its own top-level `signature` widget. |
| "Pick Option A (reclassify) or Option B (branching logic)" | Neither needed — name-prefix category resolution already does it. |

Net new widgets compared to the FE doc: **`timeline_filter`** and **`signature`** — both already on the wire.

---

## 2. New fields shipped in this pass (the actual gaps from the FE doc)

All edits in
[`backend/lt_panels/consumers/power_quality_summary/pcc_panel.py`](lt_panels/consumers/power_quality_summary/pcc_panel.py).

### 2.1 `pq_priority.rows[i]` — 3 new columns

```jsonc
{
  "mfm_id": 13, "name": "UPS-02 CL:600KVA", "rank": 1, "selected": true,
  "score": 240.8, "severity": "high",
  "i_thd_pct":      21.7,
  "v_thd_pct":      7.0,      // ← NEW (column 3)
  "i_thd_pk_pct":   24.2,     // ← NEW (column 5 — window MAX of I-THD, not avg)
  "dominant_driver":"H5",     // ← NEW (column 6 — 'OK'|'H5'|'H7'|'V'|'PF'|'N')
  "pf":             0.932
}
```

- **`v_thd_pct`** — same window value as `header_kpis.selected_feeder.v_thd_pct`, just per-row.
- **`i_thd_pk_pct`** — MAX of `thd_compliance_i_avg` across all timeline buckets in the current window (free piggy-back on the data we already fetch for the worst-THD overlays).
- **`dominant_driver`** — argmax of the *secondary* PQ drivers (I-THD has its own column, so it's excluded). Computed against thresholds in `_PQ_EVENT_META`:
  - `V`  if V-THD > 5%
  - `H5` if H5    > 6%
  - `H7` if H7    > 4%
  - `PF` if true_pf < 0.9
  - `N`  if neutral/phase ratio > 10%
  - `OK` if none of the above breach
  - "Worst" = breach furthest over its threshold (multiplicative).

### 2.2 `pq_exposure_share.categories[]` — 7 entries now, includes `neutral`

```jsonc
{
  "categories": [
    { "key": "i_thd",    "label": "I-THD",    "rule": "I-THD > 8%",     "count": 0, "pct": 0.0  },
    { "key": "v_thd",    "label": "V-THD",    "rule": "V-THD > 5%",     "count": 2, "pct": 8.7  },
    { "key": "h5",       "label": "H5",       "rule": "H5 > 6%",        "count": 8, "pct": 34.8 },
    { "key": "h7",       "label": "H7",       "rule": "H7 > 4%",        "count": 9, "pct": 39.1 },
    { "key": "k_factor", "label": "K-Factor", "rule": "K > 8",          "count": 4, "pct": 17.4 },
    { "key": "pf_gap",   "label": "PF gap",   "rule": "True PF < 0.9",  "count": 0, "pct": 0.0  },
    { "key": "neutral",  "label": "Neutral",  "rule": "Neutral/phase ratio > 10%", "count": 0, "pct": 0.0 }
  ],
  "total_issues": 23,
  "thresholds":   {...},
  "footer":       "..."
}
```

- **`neutral` is synthesized in-flight** from the existing
  `kpi_neutral_to_phase_ratio_pct` column — no simulator change needed.
  Per bucket: count of feeders whose MAX neutral ratio in that bucket
  exceeded `_NEUTRAL_RATIO_LIMIT = 10%`.
- FE can pick its 4 of choice (`i_thd | v_thd | pf_gap | neutral`) and
  ignore the other 3; backend keeps shipping all 7.

### 2.3 `event_timeline` — per-bucket and top-level additions

```jsonc
{
  "range":      "today",                                  // ← NEW (mirrors timeline_filter)
  "sampling":   "hourly",                                 // ← NEW
  "anchor_iso": "2026-05-31T12:30:00+00:00",              // ← NEW (start of the "Now" bucket)
  "buckets": [
    {
      "bucket":     "00:00",
      "bucket_iso": "2026-05-30T18:30:00+00:00",          // ← NEW (ISO start of THIS bucket)
      "i_thd": 1, "v_thd": 65, "h5": 60, "h7": 66,
      "k_factor": 73, "pf_gap": 1,
      "neutral": 0,                                       // ← NEW (synthesized)
      "worst_i_thd_pct": 24.1, "worst_v_thd_pct": 7.5
    }
    // ...
  ],
  "events":       [...],
  "totals":       {"i_thd": 1, "v_thd": 408, "h5": 425, "h7": 393,
                   "k_factor": 416, "pf_gap": 1, "neutral": 0},
  "total_events": 1644
}
```

Note: `range`, `sampling`, `anchor_iso` are **duplicates** of the canonical
values on `timeline_filter`. They're only here as a convenience for FE so
the timeline component doesn't have to reach into a sibling widget. The
single source of truth remains `timeline_filter`.

### 2.4 New command — `timeline_time: <ISO>`

```jsonc
// Frontend sends, e.g. when user clicks a bucket on the timeline by time:
{ "timeline_time": "2026-05-30T18:30:00+00:00" }
```

Backend rebuilds the bucket edges under the current `range`/`sampling`,
finds the bucket whose `[start, end)` contains the timestamp, and stashes
its label as the `selected_bucket`. Re-renders the whole frame.

Equivalent canonical form (also still supported):
```jsonc
{ "timeline_filter": { "bucket": "00:00" } }
```

Both forms drive the same path. The `timeline_time` alias is just easier
to call from the chart click handler (which already has the ISO ts).

---

## 3. Full command surface (post-change)

```jsonc
{ "select_feeder":   <mfm_id> }                                   // pick feeder → matrix col + header + signature
{ "fleet_matrix":    { "focus": "h5" } }                          // change matrix focus metric
{ "timeline_filter": { "range": "...", "sampling": "...",
                       "bucket": "HH:MM",
                       "start_date": "YYYY-MM-DD",
                       "end_date":   "YYYY-MM-DD" } }             // canonical filter command
{ "timeline_time":   "<ISO-8601 timestamp>" }                     // ← NEW — bucket pick by ISO
```

Reply for filter / time / feeder commands:
`{"type":"widget_update","widget":"__all__","data":{…all widgets…}}`.

Invalid combos (e.g. `sampling='weekly'` with `range='today'`) return
`{"type":"error","message":"..."}` and keep the socket open.

---

## 4. Smoke test

```bash
python3 -c "
import asyncio, json, websockets
async def main():
    async with websockets.connect('ws://100.90.185.31:8888/ws/mfm/174/power-quality-summary/') as ws:
        f = json.loads(await asyncio.wait_for(ws.recv(), timeout=15))
        w = f['widgets']
        print('widgets:', sorted(w))
        print('priority row keys:', sorted((w['pq_priority']['rows'][0] or {}).keys()))
        print('categories:', [c['key'] for c in w['pq_exposure_share']['categories']])
        print('bucket[0] keys:', sorted(w['event_timeline']['buckets'][0].keys()))
        print('et top-level:', sorted(w['event_timeline']))
asyncio.run(main())
"
```

Expected:
```
widgets: ['event_timeline','fleet_matrix','header_kpis','pq_exposure_share','pq_priority','signature','timeline_filter']
priority row keys: ['dominant_driver','i_thd_pct','i_thd_pk_pct','mfm_id','name','pf','rank','score','selected','severity','v_thd_pct']
categories: ['i_thd','v_thd','h5','h7','k_factor','pf_gap','neutral']
bucket[0] keys: ['bucket','bucket_iso','h5','h7','i_thd','k_factor','neutral','pf_gap','v_thd','worst_i_thd_pct','worst_v_thd_pct']
et top-level: ['anchor_iso','buckets','events','range','sampling','total_events','totals']
```

---

## 5. Frontend can ship now

The FE doc's "verification plan" steps should all pass against the
current backend:

- [x] `power-quality-summary` listed in `pages_for_mfm(174)` with `pending: false`
- [x] Frame includes the 4 widgets the FE doc lists, plus 3 bonus ones
      (`timeline_filter`, `event_timeline`, `signature`)
- [x] `pq_priority.rows[i]` has `v_thd_pct`, `i_thd_pk_pct`, `dominant_driver`
- [x] `pq_exposure_share.categories` includes the `neutral` key
- [x] `event_timeline` has `bucket_iso` per bucket + `anchor_iso`/`range`/`sampling` top-level
- [x] All 4 client commands wired (including the new `timeline_time` alias)

Flip `PANEL_OVERVIEW_HPQ_API_ENABLED = true` in
`usePanelHarmonicsPqData.ts` and the mapper should bind cleanly.

---

## 6. Known caveats — pass-through to FE

1. **`neutral` count reads 0** in current data because the simulator's
   `kpi_neutral_to_phase_ratio_pct` isn't currently crossing the 10%
   threshold. The **field is wired and the shape is correct** — the count
   will populate as soon as any feeder breaches. To see non-zero values
   today, simulator can lower the threshold or inject a transient spike.

2. **UPS feeders contribute 0 boolean events.** The 6 simulator boolean
   flag columns (`i_thd_event_active`, `v_thd_event_active`, etc.) are
   currently present only on `mfm_lt_*` tables, not on `mfm_ups_*`. The
   PQ socket's fetch path is column-tolerant (no crash), but UPS feeders
   silently read as 0 for those event types. Synthesized `neutral` and
   the worst-THD overlays are unaffected.

3. **`event_timeline.range/sampling/anchor_iso` are duplicated values.**
   Canonical truth lives on `timeline_filter`. If we ever change one
   without the other, treat `timeline_filter` as source. (Backend keeps
   them in sync on every render.)

---

## 7. Cross-references

- Full Harmonics & PQ socket contract (all widgets, frame shapes,
  bucket semantics): [PCC_PQ_AND_ENERGY_DISTRIBUTION_INTEGRATION.md](PCC_PQ_AND_ENERGY_DISTRIBUTION_INTEGRATION.md)
- Strategy source: [lt_panels/consumers/power_quality_summary/pcc_panel.py](lt_panels/consumers/power_quality_summary/pcc_panel.py)
- Page registry (page → socket mapping): [lt_panels/page_registry.py](lt_panels/page_registry.py)

---

## 8. Changelog

| Date | Change |
|---|---|
| 2026-05-31 | Added `v_thd_pct`, `i_thd_pk_pct`, `dominant_driver` to `pq_priority.rows[i]`. |
| 2026-05-31 | Added synthesized `neutral` category to `pq_exposure_share` + `event_timeline.buckets[i].neutral` + `totals.neutral` (from `kpi_neutral_to_phase_ratio_pct > 10%`). |
| 2026-05-31 | Added `event_timeline.buckets[i].bucket_iso` and top-level `range`/`sampling`/`anchor_iso`. |
| 2026-05-31 | Added `timeline_time: <ISO>` command alias for bucket-by-time selection. |
| (earlier)  | Single-socket consolidation: `power-quality-summary` covers the whole H&PQ tab. `distortion-harmonics` + `power-quality-history` folded in (now 4404). Single shared `timeline_filter` constraint. |
