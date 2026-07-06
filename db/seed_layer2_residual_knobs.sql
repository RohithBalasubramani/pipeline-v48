-- db/seed_layer2_residual_knobs.sql — config rows for the layer2 residual-fix group (code-default mirrors ship the
-- identical behavior until a row is edited — config-first, no code change to retune).
--
-- (C4) DUAL-OWNED metadata keys [RTM/HPQ fixture relocation]: the 'AI-default, data-overridable' metadata key-path
--      SUFFIXES. The GENERIC rule lives in layer2/prompts/metadata.md (DUAL-OWNED SLOTS); the per-card examples moved
--      OUT of the shared system prompt into exactly the cards whose own skeleton carries a matching path
--      (layer2/emit/user_message._dual_owned_line — suffix match, no card ids). Today that is RTM card 5
--      (heatmap.sectionContracts) and HPQ card 27 (signature.pres.spokes / signature.pres.selectedName).
--
-- Idempotent. Run: psql (cmd_catalog DSN per config/databases.py) -f db/seed_layer2_residual_knobs.sql

INSERT INTO app_config (key, value, data_type, section, note) VALUES
 ('emit.dual_owned_keys',
  '["sectionContracts", "pres.spokes", "pres.selectedName"]',
  'json', 'emit',
  'DUAL-OWNED (AI-default, data-overridable) metadata key-path suffixes — matched against each card''s OWN stripped skeleton paths; a hit renders the per-card ★ DUAL-OWNED flag in the emit user message (layer2/emit/user_message._dual_owned_line). Generic: no card ids; the worker may overwrite these keys from a live frame')
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, data_type = EXCLUDED.data_type,
                                section = EXCLUDED.section, note = EXCLUDED.note;
