-- drop_legacy_knob_homes_phase2.sql — config F6 PHASE 2: retire the legacy scalar-knob rows.
--
-- Phase 1 (db/fix_knob_home_consolidation.sql, APPLIED 2026-07-12) copied every data_quality_policy scalar and
-- viewer_policy '__knob__:' sentinel row into app_config verbatim and made the readers app_config-FIRST; the legacy
-- rows became a transition fallback that no read reaches while app_config holds the key. Until they are dropped the
-- old hazard survives in mirror form: an operator who edits the LEGACY row sees no effect (app_config wins).
--
-- RUN THIS AFTER A CLEAN TRANSITION PERIOD (recommended: at least one full cert/sweep cycle on the consolidated
-- reads with no divergence). It is self-guarding: if ANY legacy row has diverged from its app_config copy the whole
-- transaction ABORTS — a divergence means someone tuned the wrong home and must be reconciled by hand first.
--
-- What stays: the legacy-table FALLBACK READS in config/policy_read.py, config/quality_policy.py and
-- config/viewer_policy.py remain in code — for quality_policy they are also the deliberate RAISING outage layer
-- (topology_policy wraps it), and after this drop they simply never find a row. Removing those reads is a separate,
-- semantics-changing step; do not bundle it here.
BEGIN;

DO $$
DECLARE bad integer;
BEGIN
    -- guard 1: every data_quality_policy scalar must still equal its app_config copy
    SELECT count(*) INTO bad
    FROM app_config a JOIN data_quality_policy d ON d.key = a.key
    WHERE a.section = 'data_quality_policy'
      AND NOT (CASE WHEN COALESCE(d.txt_value, '') <> '' THEN a.value = d.txt_value
                    ELSE a.value::numeric = d.num_value END);
    IF bad > 0 THEN
        RAISE EXCEPTION 'F6 phase-2 aborted: % data_quality_policy rows diverged from app_config — reconcile first', bad;
    END IF;

    -- guard 2: every viewer '__knob__:' sentinel must still equal its app_config copy
    SELECT count(*) INTO bad
    FROM app_config a JOIN viewer_policy v ON v.page_key = '__knob__:' || a.key
    WHERE a.section = 'viewer' AND a.value <> v.txt_value;
    IF bad > 0 THEN
        RAISE EXCEPTION 'F6 phase-2 aborted: % viewer __knob__ rows diverged from app_config — reconcile first', bad;
    END IF;

    -- the migrated scalars
    DELETE FROM data_quality_policy d USING app_config a
     WHERE a.key = d.key AND a.section = 'data_quality_policy';
    -- the both-columns-blank rows phase 1 skipped (readers already treat them as absent — e.g. placeholder.narrative)
    DELETE FROM data_quality_policy
     WHERE COALESCE(txt_value, '') = '' AND num_value IS NULL;
    -- the viewer sentinel rows (the per-page viewer_policy rows are RELATIONAL config and stay)
    DELETE FROM viewer_policy v USING app_config a
     WHERE v.page_key = '__knob__:' || a.key AND a.section = 'viewer';
END $$;

COMMIT;
