-- retire_unused_tables_20260712.sql — APPLIED 2026-07-12 ~07:50 IST (owner authorized).
--
-- Drops the six cmd_catalog tables with ZERO readers anywhere (verified tree-wide 2026-07-12 across v45–v49,
-- host/web, CMD_V2, admin, docs-as-runnable — see docs/CODEBASE_AUDIT_UNUSED_DUPES_2026-07-12.md §10).
-- Row snapshots: archive/db_snapshots_20260712/<table>.sql (pg_dump, restorable as-is).
--
--   endpoint_policy    (12 rows)  — seeded, never read; do NOT wire to endpoint_registry (different shape).
--   band_policy        ( 6 rows)  — superseded by cmd_equipment bands (data/equipment/ratings.py); seed .retired.
--   limit_override     ( 4 rows)  — round2 config surface, reader never landed.
--   live_window_policy ( 3 rows)  — round2 config surface, reader never landed.
--   card_rendering     (145 rows) — "Inventory B facts" authoring inventory; no runtime reader.
--   card_render_map    (70 rows)  — fill-module naming convention record; no runtime reader (its seed self-describes
--                                   as a planning/metadata table — dropping is optional; keep if the planning value
--                                   outweighs the dead-surface cost).
--
-- NOT included: registry_lt_mfm_incoming (documented write-only-for-completeness mirror — KEEP);
--               payload_shapes / nameplate_config / derived_metrics (still read by pipeline_v47 — retire with v47).

BEGIN;

DROP TABLE IF EXISTS endpoint_policy;
DROP TABLE IF EXISTS band_policy;
DROP TABLE IF EXISTS limit_override;
DROP TABLE IF EXISTS live_window_policy;
DROP TABLE IF EXISTS card_rendering;
DROP TABLE IF EXISTS card_render_map;

COMMIT;
