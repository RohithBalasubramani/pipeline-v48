-- db/seed_window_min_span.sql — the non-zero-span floor for a resolved DATA window (config/windows.MIN_SPAN_DAYS).
--
-- DEFECT (card-12 pg02 energy-distribution false-zero): an emit whose window is a same-day custom-range (the AI wrote
-- start==end==YYYY-MM-DD, a 'today' range) resolved to a ZERO-WIDTH span [today, today]. A counter delta is (end −
-- start), so ems_exec.member_delta over [today,today] returns 0.0 for EVERY member/bucket though today genuinely
-- carries ~1389-21190 kWh (member_delta('gic_01_n3_ups_01_p1', ('2026-07-07','2026-07-07')) == 0.0 vs the real 1393.0
-- over ('2026-07-07','2026-07-08')). The window-resolution now guards every path (config.windows.ensure_nonzero_span,
-- called from layer2/build.py _backfill_default_window): when the resolved end <= start, the end is extended to at
-- least this many days so a same-day 'today' spans [day 00:00, day+1 00:00) and the delta reads real energy. A normal
-- forward multi-day/rolling window is returned UNCHANGED.
--
-- Code default = 1 (a single calendar day). This row is BYTE-EQUAL to the code default, so seeding is behavior-neutral;
-- edit the row to widen the minimum floor with no code change. Idempotent (ON CONFLICT upsert).
-- Apply: psql -U postgres -h 127.0.0.1 -p 5433 -d cmd_catalog -f db/seed_window_min_span.sql

INSERT INTO app_config (key, value, data_type, section, note) VALUES
  ('windows.min_span_days', '1', 'int', 'windows',
   'Minimum non-zero exclusive span (days) a resolved DATA window must cover — the degenerate zero-width-window guard (config.windows.ensure_nonzero_span). A same-day custom-range (start==end) folds every counter delta to a false 0.0 (card-12 energy-distribution); the end is extended to at least this span. Code default 1 (one calendar day). A normal forward window is untouched.')
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, data_type = EXCLUDED.data_type,
  section = EXCLUDED.section, note = EXCLUDED.note;
