-- db/seed_schema_fingerprint_markers.sql -- the schema-fingerprint MARKER columns as ONE json row (latency-audit T1-5).
-- grounding/schema_fingerprint._classify discriminates the five neuract shapes (p1_72 / ng_se_jk_70 / tm_ups_56 /
-- feedbacks_35 / sch_stub) by these IDENTITY marker columns. This row is the DB-editable overlay of the _MARK_*
-- code-default constants (which stay in code as the fail-open mirror): a missing/blank key inside the json falls
-- back per-key to its code default; a missing row / unreadable DB serves all defaults.
-- NOTE: fingerprint() caches per table for the process life (and cfg() caches app_config on first success), so an
-- edit to this row needs a process restart to take effect -- the same deploy semantics as editing the constants.
-- ON CONFLICT DO NOTHING (identity markers, not a retune knob): re-running this seed must never clobber an
-- operator's edited marker set back to the defaults.
-- Idempotent. Run: psql (cmd_catalog DSN per config/databases.py) -f db/seed_schema_fingerprint_markers.sql
INSERT INTO app_config (key, value, data_type, section, note) VALUES
 ('grounding.fingerprint_markers',
  '{"ups_power": "output_active_power_total_kw", "ups_batt": "battery_backup_pct", "breaker": "bc_acb_on_fb", "std_power": "active_power_total_kw", "harmonic5": "harmonic_5th_pct"}',
  'json', 'grounding',
  'The marker columns schema_fingerprint._classify discriminates the neuract table shapes by, in specificity order: '
  'ups_power OR ups_batt -> tm_ups_56; breaker -> feedbacks_35; std_power -> p1_72 when harmonic5 present else '
  'ng_se_jk_70; none -> sch_stub. Identity markers, NOT policy thresholds. Missing/blank keys fall back per-key to '
  'the _MARK_* code defaults (grounding/schema_fingerprint.py _MARKER_DEFAULTS). Marker edits need a process '
  'restart (fingerprint per-table cache + app_config process cache).')
ON CONFLICT (key) DO NOTHING;
