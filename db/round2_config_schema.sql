-- ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
--  V48 ROUND-2 CONFIG SCHEMA  (cmd_catalog, editable rows — the dedicated tables behind the new round-2 accessors)
--  Every threshold/limit/mapping here is an EDITABLE ROW; each backing accessor also carries the SAME value as a code
--  default, so seeding is optional-but-recommended (the pipeline runs identically with the DB down).
--  Run:  psql -h localhost -p 5432 -d cmd_catalog -f db/round2_config_schema.sql   (idempotent — safe to re-run)
--  Read by config/viewer_policy.py. (live_window_policy/limit_override never got readers — RETIRED 2026-07-12.)
-- ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════

-- ── viewer_policy ── page-family → viewer knobs the phase-2 asset_3d resolver reads [#1 asset_3d resolver] ───────────
--    A row keyed by page_key OR shell decides page_type (individual|overview|variant). Scalar knobs (rating vocab,
--    default asset_3d key) ride the SAME table keyed by page_key='__knob__:<key>' with the value in txt_value.
CREATE TABLE IF NOT EXISTS viewer_policy (
    page_key  text PRIMARY KEY,          -- V48 page_key 'shell/tab', a bare shell, or '__knob__:<key>' for a scalar knob
    page_type text,                       -- individual | overview | variant (NULL for a __knob__ row)
    txt_value text,                       -- value for a __knob__ row (rating_vocab CSV / default_asset_3d_key); else NULL
    note      text
);

-- ── live_window_policy + limit_override RETIRED 2026-07-12 (unused-code audit): readers never landed;
--    tables DROPPED (db/retire_unused_tables_20260712.sql; snapshots archive/db_snapshots_20260712/).
/*
-- ── live_window_policy ── how much history a LIVE card's snapshot carries + poll/advertised cadence [#7 live-window] ─
--    Resolved by (page, category); '' page/category = the catch-all. Fixes the ~60s frozen-looking default:
--    column-row live = 7200 (feeder_base.py:85), RTM 12-cell heatmap = 900 (realtime.py:22-23).
CREATE TABLE IF NOT EXISTS live_window_policy (
    page              text,               -- ems page code ('' = any page)
    category          text,               -- column_row | rtm_heatmap | '' (catch-all) — the card's live-history shape
    window_seconds    numeric,            -- seconds of history the snapshot must carry (the frozen-card fix)
    poll_seconds      numeric,            -- internal poll rate (detect a new row) — NULL → accessor code default
    advertised_seconds numeric,           -- cadence advertised to the FE (the DATA rate ~60s, NOT the poll rate)
    PRIMARY KEY (page, category)
);

-- ── limit_override ── per-meter / per-class warn+trip override for a logical band [#18 generic limit-override] ───────
--    Generic port of backend2 bms MeterLimit.resolve_limits: precedence per-METER > per-CLASS > accessor code default.
--    scope ∈ {meter,class}; key = meter_id (scope=meter) or asset_class token (scope=class); band_key = the threshold.
CREATE TABLE IF NOT EXISTS limit_override (
    scope    text,                        -- 'meter' | 'class' (the precedence level this row sits at)
    key      text,                        -- meter_id (scope=meter) or asset_class token (scope=class)
    band_key text,                        -- logical threshold name: current_high | load_pct | thd_v_pct | busbar_temp | …
    warn     numeric,                     -- warn threshold (NULL = no warn line for this band)
    trip     numeric,                     -- trip threshold (NULL = no trip line)
    note     text,
    PRIMARY KEY (scope, key, band_key)
);
*/
