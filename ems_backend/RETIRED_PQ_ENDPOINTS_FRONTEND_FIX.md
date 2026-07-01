# Power Quality detail-tab — empty cards / "Page not registered" issue

**Symptom:** Detail Power Quality tab on outgoing-feeder pages (e.g.
`/equipment/pcc-panels/panel-1a/outgoing/bpdb-01`) renders entirely empty:
"No backend data", "Not evaluated", "Unknown", "Backend required", "—", and a
banner at the bottom:

> Page 'distortion-harmonics' not registered for mfm_id=18

**Root cause:** Frontend is opening a **retired** WebSocket endpoint.
Backend is fine. Data is available on the new endpoint.

---

## What changed

Last week's PQ socket consolidation folded **three** endpoints into **one**:

| Old endpoint (retired) | New endpoint (live) |
|---|---|
| `ws/mfm/{id}/distortion-harmonics/` | `ws/mfm/{id}/power-quality-summary/` |
| `ws/mfm/{id}/power-quality-history/` | `ws/mfm/{id}/power-quality-summary/` |

Backend's `power-quality-summary` dispatches per MFM type (one socket, multiple
payload shapes) — see [PCC_PQ_AND_ENERGY_DISTRIBUTION_INTEGRATION.md](PCC_PQ_AND_ENERGY_DISTRIBUTION_INTEGRATION.md)
and [HARMONICS_PQ_FE_CONTRACT_RESPONSE.md](HARMONICS_PQ_FE_CONTRACT_RESPONSE.md).

Hitting either old name now lands on the catch-all dispatcher, which sends:

```jsonc
{ "type": "error",
  "message": "Page 'distortion-harmonics' not registered for mfm_id=18" }
```

…which is exactly what the empty cards in your screenshot reflect.

---

## Live probe — proves data is available

```
ws/mfm/18/distortion-harmonics/     → type=error  ("Page … not registered")
ws/mfm/18/power-quality-summary/    → type=snapshot, full per-feeder PQ payload
                                       (THD, harmonics, K-factor, PF, all the
                                       fields the detail card expects)
```

mfm 18 = **BPDB-01** (lt_panel type) → dispatched to
[`power_quality_summary/lt_panel.py`](lt_panels/consumers/power_quality_summary/lt_panel.py)
→ **column-row** payload (per-feeder live stream, NOT the PCC-fleet aggregate).

---

## What needs to change on the frontend

Single endpoint rename. The mapper code, types, and column lists do NOT need
to change — the per-feeder lt_panel.py strategy still emits the same columns
the existing column-row mapper consumes.

### Real call site

The one place that actually opens the socket:

`src/components/charts/lt-pcc-power-quality/usePccPowerQualityData.ts:87`

```ts
// before
{ mfmId, endpointPath: 'distortion-harmonics', enabled: apiEnabled,
  frameMode: 'column-row', … }

// after
{ mfmId, endpointPath: 'power-quality-summary', enabled: apiEnabled,
  frameMode: 'column-row', … }
```

That single line is the entire functional fix.

### Other references (non-blocking)

`grep` across `CMD_V2/src` finds the string `distortion-harmonics` in **8
files**. Only the one above is a live socket-open. The rest are types,
comments, test fixtures, and config:

| File | Kind |
|---|---|
| `lt-pcc-power-quality/usePccPowerQualityData.ts` | **real socket open** (fix above) |
| `lt-pcc-power-quality/columnRowMapper.ts` | comments / error-string |
| `lt-pcc-power-quality/columnRowMapper.test.ts` | test fixture `page: 'distortion-harmonics'` |
| `lt-pcc-power-quality/pccPowerQualityConfig.ts` | comment |
| `lt-pcc-power-quality/pccPowerQualityTypes.ts` | doc comments |
| `lt-pcc-power-quality/pqDistortionSlices.ts` | comment |
| `realtime/columnRowReducer.test.ts` | test fixture `page: 'distortion-harmonics'` |
| `api/backend/mfmPageSocketClient.test.ts` | test fixture |

The 2 test fixtures using `page: 'distortion-harmonics'` will need their
`page` field updated to `'power-quality-summary'` if you want the tests to
exercise the real path; otherwise they still pass against the local mock.

---

## Two PQ pages — different shapes, **same endpoint name**

This is intentional and worth keeping straight when reading the backend code:

| Page | Example URL | MFM type | Backend strategy | Payload shape |
|---|---|---|---|---|
| **PCC-overview Harmonics & PQ** (panel-1a top tab) | `mfm 174` | `pcc_panel` (name-prefix resolution) | `power_quality_summary/pcc_panel.py` | **Aggregate / fleet** — 7 widgets: `timeline_filter`, `event_timeline`, `pq_exposure_share`, `header_kpis`, `pq_priority`, `fleet_matrix`, `signature` |
| **Outgoing-feeder detail Power Quality** (BPDB-01) | `mfm 18` | `lt_panel` | `power_quality_summary/lt_panel.py` | **Column-row** — single-feeder live stream (THD, harmonic orders, K-factor, PF, compliance label) |

Both come off the same `power-quality-summary` WS path. Backend picks the
strategy from `MFM.mfm_type.code` (with name-prefix fallback for PCC panels).

The detail page in the screenshot is the **column-row** one. Its mapper
(`columnRowMapper.ts`) is already written against this shape and will bind
fine once the endpoint name is corrected.

---

## After the rename — what populates

For `mfm 18` (BPDB-01) the new endpoint returns the standard live-stream frame:

```jsonc
{
  "type":         "snapshot",
  "mfm_id":       18,
  "mfm_name":     "BPDB-01 For Lamination-01&02",
  "mfm_type":     "lt_panel",
  "panel_id":     "MFM-LT-003",
  "page":         "power-quality-summary",
  "columns":      [ "thd_compliance_v_avg", "thd_compliance_i_avg",
                    "thd_voltage_r_pct", … "harmonic_5th_pct", "harmonic_7th_pct",
                    "k_factor", "kpi_true_pf", "thd_compliance_ieee519", … ],
  "queue":        [ /* time-ordered rows of those columns */ ],
  "status":       { /* per-column status labels */ },
  "capacity":     N,
  "window_seconds": 60,
  "count":        N,
}
```

The frontend's existing `columnRowMapper` already maps these columns to the
detail-card fields the screenshot is missing:

| Card field in screenshot | Column in new payload |
|---|---|
| Critical Diagnosis → Compliance | `thd_compliance_ieee519` |
| THD Snapshot → I-THD | `thd_compliance_i_avg` |
| THD Snapshot → V-THD | `thd_compliance_v_avg` |
| Harmonic Orders → H5 | `harmonic_5th_pct` |
| Harmonic Orders → H7 | `harmonic_7th_pct` |
| Distortion & Harmonic Profile (chart) | THD-V / THD-I phase columns + harmonic orders over `queue[]` |
| Load Impact & Transformer Stress — PF Health | `kpi_true_pf`, `power_factor_total` |
| Severity / Trend / Source & mitigation | derived in the mapper from the above |

No backend change required to populate any of these.

---

## Verification steps (post-rename)

1. Open `/equipment/pcc-panels/panel-1a/outgoing/bpdb-01` → Power Quality tab.
2. DevTools → Network → WS: confirm `ws/mfm/18/power-quality-summary/` is the
   only PQ socket opened on this page (no `distortion-harmonics`).
3. The first frame should be `type=snapshot` with `mfm_type=lt_panel`, a
   non-empty `columns` array, and `queue.length > 0` within seconds.
4. THD Snapshot tile, Harmonic Orders tile, Compliance/Trend/Severity all
   show real values (not "—" / "Not evaluated").
5. The bottom banner "Page 'distortion-harmonics' not registered for mfm_id=18"
   disappears.

---

## Why the PCC-overview page works but this one doesn't

The PCC-overview Harmonics & PQ tab (the one we worked on last week) was
already migrated to `power-quality-summary` as part of the consolidation work.
The detail/leaf-feeder PQ tab is a **different page** that was missed in that
migration pass — its socket-open in `usePccPowerQualityData.ts:87` still
references the retired endpoint name.

---

## Changelog

| Date | Change |
|---|---|
| ~1 week ago | `distortion-harmonics` and `power-quality-history` retired; consolidated into single `power-quality-summary` socket with type-dispatched strategies. PCC-overview H&PQ tab migrated at the same time. |
| Outstanding | **Detail-feeder Power Quality tab** (`usePccPowerQualityData.ts:87`) still calls the retired name → all empty cards in screenshot. One-line frontend fix; no backend change. |
