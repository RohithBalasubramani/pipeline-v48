-- db/seed_asset3d.sql — editable rows for BATCH A #1+#12 (the honest 3D resolver). Idempotent (ON CONFLICT).
-- Every value here is ALSO its accessor's code default, so seeding is OPTIONAL — the pipeline runs identically DB-down.
-- Run:  psql -h localhost -p 5432 -d cmd_catalog -f db/seed_asset3d.sql
-- Prereq schema:  db/round2_config_schema.sql (viewer_policy) + db/render_guarantee_schema.sql (reason_template)
-- Read by: config/viewer_policy.py, config/asset3d_media.py (glb media base), config/reason_templates.py (no_asset_3d),
--          domain/asset_3d.py (facade: layer2/emit/metadata/asset_3d.py).

-- ── #1 viewer_policy ── the GLB media base knob the layer2 asset_3d emit prepends to a stored file path ─────────────
-- The layer2 pipeline runs OUT of the Django process, so it can't use request.build_absolute_uri — it needs the
-- media base as config (ROOT-RELATIVE since 2026-07-12: the web origin serves host/web/public/media). Rides the same viewer_policy __knob__ surface as the other viewer
-- knobs. Blank/absent → config/asset3d_media falls open to the same '/media/' code default.
INSERT INTO viewer_policy (page_key, page_type, txt_value, note) VALUES
 ('__knob__:viewer.glb_media_base', NULL, '/media/',
  'base a stored GLB file path hangs off — ROOT-RELATIVE /media/ (the web origin serves host/web/public/media) — asset_3d emit [#1 asset_3d]')
ON CONFLICT (page_key) DO UPDATE SET page_type = EXCLUDED.page_type, txt_value = EXCLUDED.txt_value, note = EXCLUDED.note;

-- ── #1/#12 reason_template ── the honest-blank cause for a card whose 3D model can't be resolved ───────────────────
-- Emitted by layer2/emit/metadata/asset_3d.py when NO model binds (no per-MFM override, no type default, no configured
-- global default). NEVER a wrong GLB — the FE shows this sentence + "—". reason() falls back to the cause key itself if
-- this row is absent, so the channel is never empty DB-down.
INSERT INTO reason_template (cause, template) VALUES
 ('no_asset_3d', 'No 3D model configured for {asset}.')
ON CONFLICT (cause) DO UPDATE SET template = EXCLUDED.template;
