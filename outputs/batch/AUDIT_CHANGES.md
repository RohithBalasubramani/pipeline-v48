# Endpoint Audit — all pages × all cards × the pipeline offer-list

Audited every card's `backend_strategy` (canonical ems_backend screen) and the pipeline's endpoint
offer-list against the ems_backend GROUND TRUTH (`ems_backend/lt_panels/page_registry.py` `_PAGES`).

## Ground truth
- **11 live endpoints:** overview, real-time-monitoring, energy-power, demand-profile, load-anomalies,
  energy-power-history, energy-distribution, voltage-current, voltage-history, current-history, power-quality-summary.
- **Retired** (folded into `power-quality-summary`): `distortion-harmonics`, `power-quality-history`.
- **Category coverage:** every dispatcher serves `{lt_panel, transformer, ht_panel, ups, apfc, sub_panel, pcc_panel}`.
  `dg` has NO strategy anywhere, and `mfm_type.code='dg'==category` so the `lt_panel` fallback can't rescue it.

## Card audit (145 cards)
| bucket | n | note |
|---|---|---|
| live | 61 | canonical endpoint is in the live route table — OK |
| **retired** | **2 → 0** | cards 48, 49 (fixed below) |
| off_route | 6 | cards 50/51/57/58/59 (UPS), 75 (transformer) — `assets/consumers/...` asset-dashboard cards, NOT on any of the 9 routable pages → never hit by the router. Left as-is. |
| no_endpoint | 78 | narrative / nav / 3D / composite cards — no data screen by design. |

## Changes applied

### 1. DB — `cmd_catalog.card_handling` (backup: `card_handling_backup.csv`, 145 rows)
Cards **48** ("Distortion & Harmonic Profile") and **49** ("Load Impact & Transformer Stress"), both on the
routable `individual-feeder-meter-shell/power-quality` page, were pinned to the RETIRED `distortion_harmonics` consumer:
```
UPDATE card_handling
SET backend_strategy='consumers/power_quality_summary/lt_panel.py'
WHERE card_id IN (48,49);   -- was consumers/distortion_harmonics/lt_panel.py
```
Safe per ems_backend's own `RETIRED_PQ_ENDPOINTS_FRONTEND_FIX.md` (pure endpoint rename, same columns) + a column
diff: `power_quality_summary/lt_panel.py` serves every field cards 48/49 render (per-phase THD, compliance avgs, PF,
harmonics, k_factor). The only 2 it lacks (`phase_angle_deg`, `harmonic_loss_factor_fhl`) are NULL in neuract anyway.

### 2. Code — `layer2/emit/data/consumer_binding.py`
- `_ENDPOINT`: `harmonics-pq` and `power-quality` page tails → `power-quality-summary` (were self-mapping to dead names).
- `HISTORY_ENDPOINTS`: removed `power-quality-history` (retired; no separate PQ history route).
- `_HISTORY_BY_DOMAIN`: `power-quality-summary` → `[]`; removed the `distortion-harmonics` key.

### 3. Code — `workers/fill/sources/ems_backend_source.py` (honest, fast failures)
`fetch_frame` now honors the backend's `{type:"error", message}` frame: it returns the real reason and stops,
instead of ignoring it, looping into the server's close, and mislabeling the `ConnectionReset` as "unreachable".
Verified: DG `voltage-current` → `Page 'voltage-current' not configured for category 'dg'` (0.03s); retired
`power-quality-history` → `Page 'power-quality-history' not registered` (0.0s). Diagnostics only — doesn't revive
a dead endpoint, but every failure now names its cause in ms.

## Verified
- Audit re-run: RETIRED=0, offer-list dead entries = none.
- Fresh-process run "current THD for UPS 02": cards 47/48/49 all → `power-quality-summary`, frame `ok=True`,
  3/3 payload, 3/3 conform. (Was: 48/49 → power-quality-history/distortion-harmonics → fail.)
- `pytest tests/` — green (no regressions).

## REMAINING — needs a decision (ems_backend, out of the card/pipeline scope)
- **Diesel Generator (`dg`) has no dispatcher strategy** → DG fails on ALL endpoints (now honestly reported as
  `Page '<ep>' not configured for category 'dg'`). Minimal fix options (in `ems_backend/lt_panels/consumers/_dispatch.py`):
  add a `dg → lt_panel` fallback (DG is metered via the same compat columns), or add explicit `dg` strategies.
- **Host restart** needed for the running UI to serve the new `consumer_binding` + `ems_backend_source` code + load the
  already-fixed conformance gate (the chrome-legend `conforms=false` noise).
