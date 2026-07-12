-- fix_deadend_knobs_20260712.sql — dead-end knob cleanup (unused-code audit 2026-07-12,
-- docs/CODEBASE_AUDIT_UNUSED_DUPES_2026-07-12.md §11).
--
-- DELETE the data_quality_policy rows NOTHING reads (verified tree-wide incl. camelCase, DB-row text,
-- data/equipment, host/web, CMD_V2):
--   topology.trend_deadband — its only reader was config/topology_policy.trend_deadband(), itself dead
--     (zero callers; removed this pass). The trend_status deadband concern lives in backend2 (core/derive.py),
--     which reads its own config, not cmd_catalog.
--   band.%  (34 rows: band.ieee519.* / band.pq_fleet.* / band.overview.*) — seeded by db/seed_band_policy.sql
--     (now .retired) for a planned config.bands reader that never landed. The LIVE RTM/PQ band source is the
--     cmd_equipment DB via data/equipment/ratings.py (equipment-schema wiring, 2026-07-08) — these cmd_catalog
--     rows were superseded before ever being read. NOTE band-THD verdict logic reads the thd_compliance_ieee519
--     COLUMN from neuract, not these knob rows.
--
-- The band_policy TABLE itself (6 rows, also reader-less) is snapshotted but NOT dropped — table drops are
-- owner-gated. Restore everything from archive/db_snapshots_20260712/ (band_policy.sql, deadend_dq_rows.csv)
-- or re-run db/seed_band_policy.sql.retired.

BEGIN;

DELETE FROM data_quality_policy WHERE key = 'topology.trend_deadband';
DELETE FROM data_quality_policy WHERE key LIKE 'band.%';

COMMIT;
