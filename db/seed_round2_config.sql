-- db/seed_round2_config.sql — editable rows for the round-2 config accessors (viewer_policy, live_window_policy,
-- limit_override) + the per-class IEEE-519 feeder-PQ limit additions on asset_class_default. Idempotent (ON CONFLICT).
-- Every value here is ALSO the accessor's code default, so seeding is optional-but-recommended (DB-down = identical).
-- Run:  psql -h localhost -p 5432 -d cmd_catalog -f db/seed_round2_config.sql
-- Prereq schema:  db/round2_config_schema.sql (viewer_policy/live_window_policy/limit_override) + render_guarantee_schema.sql

-- ── #1 viewer_policy ── page-family + the two scalar knobs the asset_3d resolver reads ─────────────────────────────
-- Shell-level page_type (a per-page_key row overrides its shell); read by config/viewer_policy.page_type_for().
INSERT INTO viewer_policy (page_key, page_type, txt_value, note) VALUES
 ('individual-feeder-meter-shell', 'individual', NULL, 'single-feeder detail shell → individual render path [#1 asset_3d]'),
 ('panel-overview-shell',          'overview',   NULL, 'panel bootstrap + 3D/SLD shell → overview render path [#1 asset_3d]'),
 ('__knob__:viewer.rating_vocab',        NULL, 'exact,strong,plausible,weak,none',
  'ordered rating tokens the resolver ranks/labels a candidate asset by (best→worst) [#1 asset_3d]'),
 ('__knob__:viewer.default_asset_3d_key', NULL, 'pcc1a-v1',
  'honest fallback 3D-asset key when a page/panel has no configured GLB (backend2 views.py:430) [#1 asset_3d]')
ON CONFLICT (page_key) DO UPDATE SET page_type = EXCLUDED.page_type, txt_value = EXCLUDED.txt_value, note = EXCLUDED.note;

-- ── #7 live_window_policy ── snapshot window + poll/advertised cadence per (page, category) ────────────────────────
-- Fixes the ~60s frozen-looking default: column-row live = 7200s (feeder_base.py:85), RTM heatmap = 900s (realtime.py:22-23).
-- Read by config/live_window_policy.window_seconds()/poll_seconds()/advertised_cadence_seconds().
INSERT INTO live_window_policy (page, category, window_seconds, poll_seconds, advertised_seconds) VALUES
 ('', 'column_row',  7200, 5, 60),   -- single-feeder live series/tiles — ~120 rows @ 1-min (feeder_base.py:85)
 ('', 'rtm_heatmap',  900, 2, 60),   -- RTM 12-cell history heatmap — ≥12 rows/feeder (realtime.py:22-23,28)
 ('', '',            7200, 5, 60)    -- catch-all: generous window so any live card isn't frozen at the old ~60s
ON CONFLICT (page, category) DO UPDATE SET
   window_seconds = EXCLUDED.window_seconds, poll_seconds = EXCLUDED.poll_seconds, advertised_seconds = EXCLUDED.advertised_seconds;

-- ── #18 limit_override ── generic per-class warn/trip bands (per-meter rows are added by ops as needed) ─────────────
-- Precedence per-METER > per-CLASS > accessor code default. Read by config/limit_overrides.resolve_limit().
-- Seeded here as the generic across-class electrical watchpoints (matches config/limit_overrides.LIMIT_DEFAULTS.__default__).
INSERT INTO limit_override (scope, key, band_key, warn, trip, note) VALUES
 ('class', '__default__', 'load_pct',        90, 100, 'loading% warn/trip vs nameplate [#18 limit-override]'),
 ('class', '__default__', 'thd_v_pct',        5,   8, 'voltage THD % (IEEE-519 typical) [#18 limit-override]'),
 ('class', '__default__', 'thd_i_pct',        8,  12, 'current THD % [#18 limit-override]'),
 ('class', '__default__', 'voltage_dev_pct',  5,  10, '|voltage deviation| % vs nominal [#18 limit-override]')
ON CONFLICT (scope, key, band_key) DO UPDATE SET warn = EXCLUDED.warn, trip = EXCLUDED.trip, note = EXCLUDED.note;

-- ── #10 asset_class_default ── ADD the per-class feeder-PQ IEEE-519 limits (merged onto the existing default_json) ──
-- So config/nameplates.pq_limits() + services/mfm_config.py hand the PQ mapper a REAL per-asset limit instead of forcing
-- the IEEE-519 code default (powerQualityMapper.ts:169-175 / IEEE_519_LV_LIMITS). Values match CMD_V2 (all 8%, flicker 1.0,
-- crest ideal √2). '||' merges the new keys onto whatever default_json a class already has (non-destructive).
UPDATE asset_class_default SET default_json = default_json || jsonb_build_object(
    'ieee_519_voltage_thd_limit_pct', 8.0,
    'ieee_519_current_thd_limit_pct', 8.0,
    'ieee_519_individual_harmonic_limit_pct', 8.0,
    'flicker_pst_limit', 1.0,
    'crest_factor_ideal', 1.414
) WHERE asset_category IN ('Transformer', 'Distribution Panel', 'LT Panel', 'DG', 'UPS');
