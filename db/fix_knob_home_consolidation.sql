-- fix_knob_home_consolidation.sql — config F6 (refactor audit 2026-07-12): ONE scalar-knob home.
--
-- The same class of knob (scalar, keyed, typed, fail-open) was readable from THREE tables through three APIs:
-- app_config via cfg(), data_quality_policy via policy_read/quality_policy num()/txt(), and viewer_policy
-- '__knob__:<key>' sentinel rows via viewer_policy._txt(). An operator auditing "what is tunable" in app_config
-- missed every rating.* / feeder_overview.* / energy_balance.* / viewer.* knob.
--
-- This migration COPIES the scalar rows into app_config VERBATIM (values byte-identical; txt_value wins when both
-- columns are set — the only such key, placeholder.scalar, is consumed exclusively via txt()). The readers are now
-- app_config-FIRST with the legacy tables as transition fallback, so behavior is identical whichever side serves
-- the read. Legacy rows are deliberately RETAINED for one transition period; drop them (and the fallback reads)
-- once nothing has diverged. Genuinely relational tables (event_threshold, derivation_binding, schema_map,
-- reason_template, the per-page viewer_policy rows) stay where they are.
--
-- Skipped rows: both-columns-blank rows (e.g. placeholder.narrative: num NULL + txt '') — today's readers already
-- treat those as absent, so not migrating them is byte-identical.
BEGIN;

-- data_quality_policy scalars → app_config (key verbatim; number when only num_value is set, else text)
INSERT INTO app_config (key, value, data_type, section, note)
SELECT key,
       CASE WHEN COALESCE(txt_value, '') <> '' THEN txt_value ELSE num_value::text END,
       CASE WHEN COALESCE(txt_value, '') <> '' THEN 'text' ELSE 'number' END,
       'data_quality_policy',
       'migrated from data_quality_policy (config F6 knob-home consolidation, 2026-07-12); legacy row retained as transition fallback'
FROM data_quality_policy
WHERE COALESCE(txt_value, '') <> '' OR num_value IS NOT NULL
ON CONFLICT (key) DO NOTHING;

-- viewer_policy '__knob__:' sentinel rows → app_config (sentinel prefix stripped)
INSERT INTO app_config (key, value, data_type, section, note)
SELECT substr(page_key, 10), txt_value, 'text', 'viewer',
       'migrated from viewer_policy __knob__ sentinel rows (config F6 knob-home consolidation, 2026-07-12); legacy row retained as transition fallback'
FROM viewer_policy
WHERE left(page_key, 9) = '__knob__:' AND COALESCE(txt_value, '') <> ''
ON CONFLICT (key) DO NOTHING;

COMMIT;
