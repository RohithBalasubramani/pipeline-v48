# FINDING — neuract as the clean data source via compat views (PROVEN)

> User (2026-06-29): *"instead use this db: target_version1 — the logged meter data lives in schema neuract (tables like neuract.gic_06_n3_ups_07_cl_600_kva_p1). Full: postgresql://postgres@localhost:5432/target_version1 (alias pg_main)."* + *"this is fine via compat views + a registry repoint (zero consumer forking)."*

## The source
- `target_version1` / schema **`neuract`** — 326 tables. Electrical meters = **`mfm_001…mfm_245`** (the `gic_…` example name doesn't exist; illustrative). 244 share **one uniform 40-col schema**; clean proper names (`active_power_total_kw`, `power_factor_total`, `voltage_ln_avg`, `voltage_r_n/y_n/b_n`, `thd_voltage_*_pct`, `frequency_hz`, energies, per-phase…). Registry = **`neuract.device_mappings`** (table→field_key→modbus addr/scale, 10,904 rows).
- Data: 2024-03-19 → **2026-03-26**, ~1 Hz, 1.3M rows/table. (Latest is 2026-03-26, not "now" — same time-anchor note as before; the *schema* cleanliness is the win.)

## Why it can't be used by ems_backend as-is (3 breaking + minor)
1. **No `panel_id`** — neuract is one-table-per-asset; every `services.py` fetch is `… WHERE panel_id=%s` → would error.
2. **`timestamp_utc` is varchar, mixed offsets** (1,056,180 `+05:30` / 248,376 `+00:00`) — consumers do timestamptz math + `ORDER BY ts`; a lexical sort of mixed-offset strings mis-orders. (Cast fixes both; nanoseconds truncate to micro cleanly.)
3. **No topology / `mfm_type`** — dispatcher picks strategy by type, PCC heatmap fans out over `incoming`/`outgoing`; neuract has neither (those stay in `lt_mfm` = metadata, never the problem).
- Minor: tables in schema `neuract` (consumers assume `public`); a few cols differ (`voltage_avg`→`voltage_ln_avg`; `current_unbalance_pct`/`kpi_kw_load_pct_of_rated` absent → derive/None).

## The clean reconciliation (zero consumer forking) — PROVEN
A **compat VIEW per asset** over its neuract table that satisfies the exact contract `services.py` expects:
```sql
CREATE VIEW public.cmp_mfm_001 AS
SELECT timestamp_utc::timestamptz AS ts,           -- fix type + ordering
       'MFM-001'::text            AS panel_id,      -- inject the WHERE key
       n.*,                                          -- all 40 neuract cols (names already match mostly)
       n.voltage_ln_avg           AS voltage_avg,    -- alias the few mismatches
       (GREATEST(abs(n.current_r-n.current_avg),abs(n.current_y-n.current_avg),abs(n.current_b-n.current_avg))
          / NULLIF(n.current_avg,0)*100.0)::real AS current_unbalance_pct   -- derive the missing
FROM neuract.mfm_001 n;
```
**Proof (real `services.py`, the ONLY DB path consumers use, run via pyenv 3.11.9):**
- `fetch_live(target_version1, 'cmp_mfm_001', 'MFM-001', cols)` → row with `ts=2026-03-26…`, `active_power_total_kw=1375.2`, `power_factor_total=0.869`, `voltage_avg=6303.1` (aliased), `current_unbalance_pct=1.49` (derived), `kpi_kw_load_pct_of_rated=None` (graceful).
- `fetch_bucketed(… '2026-03-25'→'2026-03-26' hour)` → **24 hourly buckets** avg/min/max — bucket TZ math works on the cast `ts`.
⇒ Consumers run UNCHANGED; the impedance match lives entirely in the view. Approach validated.

## Remaining for the FULL rollout
- **Asset↔neuract mapping (needs decision):** `lt_mfm` uses `mfm_<type>_NNN` (`mfm_lt_115`), neuract uses flat `mfm_NNN` (1–245) — **no name correspondence**, different counts/semantics. Which `lt_mfm` asset = which `mfm_NNN`? (given map / by semantics / or switch the asset-world to neuract). **Open — surfaced to user.**
- **Compat generator:** uniform neuract schema ⇒ **one** view template parameterized per asset (panel_id + the alias/derive block). Generate a view per in-scope neuract table.
- **Registry repoint:** point each `lt_mfm` row's `db_link`→`target_version1`, `table_name`→its compat view, `panel_id`→the injected constant. Keep a backup for reversal. (Topology/type stay in `lt_mfm`.)
- **Column-contract coverage:** map every column every strategy (11 endpoints × classes) requests → neuract's 40 cols (direct/alias/derive/missing). PQ/event pages may be partial (neuract has no boolean event flags) — flag honestly.
- **Time anchor:** data ends 2026-03-26 → live trailing-30s window empty; pin a reference "now" or use historical ranges for validation.

## Artifacts
Proof view `public.cmp_mfm_001` exists in `target_version1` (throwaway — supersede with the generator). Probe was inline (no file kept).
