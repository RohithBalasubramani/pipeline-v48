-- db/seed_reason_templates_sweep.sql — GENERIC honest-blank reason templates for the fullsweep_20260706 defect causes.
-- Idempotent (ON CONFLICT upsert). Run:  psql -h localhost -p 5432 -d cmd_catalog -f db/seed_reason_templates_sweep.sql
-- Prereq schema: db/render_guarantee_schema.sql (reason_template).
--
-- WHY: the 18-page sweep (outputs/fullsweep_20260706_004334) introduced blank-leaf causes that had NO reason_template
-- row, so config.reason_templates.reason(cause) fell back to the bare machine key (e.g. layer2/build.py:177 renders the
-- literal string 'unbound_by_emit'). The per-LEAF honest-degradation contract counts a blank as PASS only when it
-- carries a HUMAN reason — these rows close that gap generically (no per-card/per-slot rows, placeholders only).
-- reason() leaves a missing {placeholder} literal and never raises, so every template also reads sanely bare.

INSERT INTO reason_template (cause, template) VALUES
 -- layer2/build.py: a catalog slot the AI emit covered with NO field (the deterministic completeness reconcile).
 -- sentence re-derived FROM LIVE 2026-07-06 (live evolved past the original seed text)
 ('unbound_by_emit',       '{metric} — no data binding was emitted for this leaf; left blank (no measured source declared).'),
 -- gates rule (iii) quantity wall: the slot names one physical quantity, the bound column/fn measures another.
 ('quantity_mismatch',     '{metric} not measured by this meter — the only available source measures a different quantity, so this value is not shown.'),
 -- gates rule (iv) const-source: a numeric literal with no real DB source (no nameplate rating, no app_config consts.* row).
 ('const_no_source',       '{metric} has no configured source (no nameplate rating, no site-approved config row) — placeholder value removed.'),
 -- 3D viewer cards: nothing binds in the 4-tier lt_asset_3d resolve (generic alias of no_asset_3d, task-mandated key).
 ('no_3d_model',           'No 3D model registered for this asset.'),
 -- event/count leaves: the meter exposes no *_event_active register for this event family.
 ('event_register_absent', '{metric} — this meter logs no event register for this event type; count unavailable.'),
 -- grounding/meaningful.py: the resolved table is a sch_stub (unknown fingerprint) — nothing routes.
 ('schema_stub',           'Meter table has an unrecognized schema — no readings can be routed for {asset}.'),
 -- validate/build.py topology gap: a feeder-topology card whose resolved asset has no feeders mapped.
 ('topology_infeasible',   'This card needs feeder topology; {asset} has no feeders mapped.')
ON CONFLICT (cause) DO UPDATE SET template = EXCLUDED.template;
