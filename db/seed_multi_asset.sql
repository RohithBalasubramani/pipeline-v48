-- db/seed_multi_asset.sql — MULTI-ASSET compare knobs (cmd_catalog.app_config). [author-once-per-class]
-- Both have code-default fallbacks (host/server.py cfg('multi_asset.enabled', True) + host/multi_asset.py
-- cfg('multi_asset.max_assets', 6)), so behaviour is identical until a row is edited — DB-driven, no code change.
--   multi_asset.enabled    — gate the /api/run asset_ids[] compare path (picker multi-select). false → the picker's
--                            extra ids are ignored and only the single-asset path runs.
--   multi_asset.max_assets — cap on assets compared in ONE run; a larger picker selection is truncated to this.
INSERT INTO app_config (key, value, data_type, section, note) VALUES
  ('multi_asset.enabled',    'true', 'bool', 'multi_asset',
   'Enable the /api/run asset_ids[] compare path (picker multi-select → 1a once, Layer 2 once per class, executor per asset).'),
  ('multi_asset.max_assets', '6',    'int',  'multi_asset',
   'Max assets compared in one run; the picker selection is truncated to this cap.')
ON CONFLICT (key) DO UPDATE
  SET value = EXCLUDED.value, data_type = EXCLUDED.data_type, section = EXCLUDED.section, note = EXCLUDED.note;
