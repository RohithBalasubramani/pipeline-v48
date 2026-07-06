# Nameplate / Rated-Capacity Research — V48

Investigation (2026-07-04) into where real per-asset **rated capacity (kVA/kW)** and nameplate/identity fields for the
pipeline's plant can be sourced. Trigger: `rated_capacity_kva` is NULL for all 320 canonical MFMs, so capacity / duty /
utilization leaves honest-blank ("Rated capacity unknown"). User asked to source it from CMD_V2 / `:9120`.

## TL;DR / verdict

**There is NO clean, real per-asset `rated_kVA` source for the canonical GIC plant beyond what is already local.**
Every external candidate is either empty, a *different plant*, or hard-coded demo data. Writing any of them onto our
GIC assets would be **fabrication** (the exact thing the whole streamline removed).

- **Real ratings that DO belong to our plant (already local):** `cmd_catalog.asset_nameplate` — **103 of 320** rows
  have a real `rated_kva` (source: `cmd_equipment_table` 57, `cmd_equipment_name` 13, `name_parse` 33 — e.g. UPS
  "GIC-01-N3-UPS-01 **CL:600KVA**" → 600). The other **217 are `source='none'`, `rated_kva=NULL`** (genuinely unknown).
- **Mandate-correct default:** keep the 103 real + name-derivable (UPS `CL:<n>KVA`), **honest-blank the rest** — never
  a fabricated number.

## The canonical registry gap

- `neuract.lt_mfm.rated_capacity_kva` = **NULL for all 320** rows (schema exists, unpopulated).
- Pipeline reader today: `ems_exec/derivations/nameplate.py` (`rated_kva`/`feeder_rated_kw`/`ups_rated_kva`) →
  `config.nameplates` by table + UPS-name parse. `rated_kw ≈ rated_kva × nominal_pf` (`app_config nameplate.nominal_pf`).

## Sources checked (all dead-ends for our plant)

| Source | Location | Has real `rated_kVA`? | Joins to our plant? | Notes |
|---|---|---|---|---|
| `neuract.lt_config_value` | :5433 tunnel | ❌ 0 rows for every capacity key | n/a | rich 14-field schema (`rated_kva`, `rated_kw`, `contract_kwh_per_day`, `critical_demand_kw`, `incoming/outgoing_live_load_kw`…) but **values empty** |
| `neuract.asset_config_value` | :5433 | ❌ empty | n/a | asset registry config, unpopulated |
| **`lt_panels_db`** (CMD backend DB) | localhost:5432 | ❌ no `rated_kva` | ❌ **DIFFERENT PLANT** | `lt_config_value` has **3,654 real values** across 82 fields (`incoming/outgoing_live_load_kw` ~1000 kW ×198, `average_pf` ×198, `fault_level_ka` ×207, `frequency_hz` ×207…) BUT the MFMs are a different model: **"AHU-1"/"PCC Panel 1 A/B" short names, 220 MFMs, ids 2-224, ZERO name matches** with our "GIC-…" 320-MFM registry |
| `:9120` "EMS KPI Screens" SPA | http://100.90.185.31:9120 | ❌ hard-coded demo | ❌ different assets | bundle contains `En=[{panel:"LT-01",kva:320,capacity:520,loadPct:60,…} …10 rows LT-01..LT-10]` + `ratedCapacity:1e3` (useState default). **Fictional demo data.** |
| `:9121` "EMS Data API" (SPA backend) | http://100.90.185.31:9121 | ❌ no nameplate endpoint | ❌ 3rd dataset | FastAPI, time-series only (`/api/latest|stats|timeseries|fleet|tables/{asset_type}/{table_id}`). Transformers = `trf_001..trf_010` (10, a **third** naming scheme). `latest` exposes a computed `load_percent` (e.g. trf_001 72.16% @ 433.66 kVA → implies ~601 kVA rated) but **no explicit rated field**. |
| `/home/rohith/CMD/lt_panel_simulator.py` | file | hard-coded 1500/500/600 | n/a | **premier-energies SIMULATOR — FORBIDDEN as a data source** (fabricated, e.g. every transformer = 1500 kVA) |
| `cmd_catalog.asset_nameplate` | local :5432 | ✅ **103/320 real** | ✅ our plant | THE only real source; `source='none'` for the 217 unknowns |

## What I mirrored — DROPPED (2026-07-05)

**PURGED.** This mirror was **wrong plant, zero readers, and did NOT close the `rated_kva` gap** — so it has been
removed entirely. Deleted `scripts/sync_config_nameplate.py`; dropped its four output tables
(`registry_lt_config_field`, `registry_lt_config_value`, `registry_asset_config_field`, `registry_asset_config_value`)
and removed their `registry_sync_meta` rows.

Historical note (why it was DROPPED): per the "bring all those to our directory" directive the script mirrored the CMD
backend config from **`lt_panels_db`** → cmd_catalog (`registry_lt_config_field` 82, `registry_lt_config_value` 3654,
`registry_asset_config_*` empty). **It is a different plant** (0 id/name alignment to `registry_lt_mfm`), so it could not
be joined to our assets, and it carried **no `rated_kva`** (only kW load ratings) — so it never closed the capacity gap.
Nothing in the non-test tree read the mirrored tables. Purged rather than kept.

## Open question for the user (blocking a real fix)

Is there an **actual nameplate register for the GIC plant** — a spec sheet, the SLD, or a DB table keyed to the real
GIC asset names — with real `rated_kVA` per asset? If yes, point at it and it mirrors in like the registry. If not, the
correct behavior is: **103 real + UPS name-parse, honest-blank the rest** (no fabricated 1000/1500/520).

## Related

- Registry mirror: `scripts/sync_neuract_registry.py` → `registry_*` (canonical `lt_mfm.id`).
- Reader to re-point once a real source exists: `ems_exec/derivations/nameplate.py`, `data/nameplate.py`, `config/nameplates.py`.
- `app_config nameplate.nominal_pf` (kVA→kW convention).
