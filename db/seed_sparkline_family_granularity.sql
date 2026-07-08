-- db/seed_sparkline_family_granularity.sql — card 58 sparkline per-bucket resolution knobs (DB-driven, code-default fallback).
-- Apply: psql -U postgres -h 127.0.0.1 -p 5432 -d cmd_catalog -f db/seed_sparkline_family_granularity.sql
--
-- WHY: card 58 (UPS Load) historical-load sparkline broadcast ONE window loadFactor (33.4 flat) to all 30 bars while
-- the REAL per-day loadPct varies 33.8-36.2% (DB: round(avg(abs(active_power_total_kw))/rated_kw*100) GROUP BY day ->
-- 12-13 daily buckets). The per-index family (ems_exec/executor/indexed_families.py:_family_series) now buckets the
-- derived loadPct at the series' OWN resolution: it walks the sampling ladder and picks the FINEST granularity whose
-- real-bucket count still FITS the slot budget (day for a 29-day/30-slot window; NOT hourly's ~248 buckets). Divisor is
-- the SAME rated_kw the scalar KPI used (metric-wins -> kpiKwLoadPctOfRated) — nothing invented. A no-reading bucket
-- blanks that bar (end-aligned; the 17-18 pre-data slots stay honest-None, never 0, never broadcast).
--
-- Both knobs preserve the current code default exactly (no behavior change until a row is edited):
--   layer2.sparkline_fit_slots   — 'on'  : pick the finest ladder granularity with bucket_count <= n_slots (the real
--                                           per-day cadence). 'off' : keep the coarsest-nonempty (legacy fallback).
--   vocab.sampling_refine_ladder — the coarse->fine ladder the chooser walks (mirrors neuract._SAMPLING). The
--                                   granularity chooser and the neuract date_trunc granularities share this vocabulary.

INSERT INTO app_config (key, value, data_type, section, note) VALUES
  ('layer2.sparkline_fit_slots', 'on', 'text', 'layer2',
   'Per-index sparkline/series family (indexed_families._choose_granularity): when on, resolve the shared series at the FINEST ladder granularity whose real-bucket count fits the point-slot budget (bucket_count <= n_slots) — the series OWN resolution (day for a 29-day/30-slot loadPct sparkline, matching DB GROUP BY day), never over-refined to hourly and never a broadcast window scalar. off = coarsest-nonempty legacy fallback. Code default: on.'),
  ('vocab.sampling_refine_ladder', '["month","week","day","hourly"]', 'json', 'vocab',
   'Coarse->fine sampling ladder the per-index family granularity chooser walks (mirrors neuract._SAMPLING date_trunc granularities). Code default: ["month","week","day","hourly"].')
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, data_type = EXCLUDED.data_type,
                                section = EXCLUDED.section, note = EXCLUDED.note;
