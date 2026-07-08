-- db/seed_equipment_ai_context.sql — stream C knobs: equipment-registry AI context [equipment wiring, 2026-07-08].
--
-- equipment.facts.enabled  — the Layer-2 user-message fact lines (EQUIPMENT / BREAKER / RTM STATUS BANDS / ENERGY
--                            REGISTER, layer2/emit/equipment_facts.py) + the PANEL MEMBERS per-member aka suffix.
-- equipment.alias.enabled  — the 1b candidate aka/loc columns (layer1b/resolve/asset_candidates._alias_map) + the
--                            5th listing column + the unique-alias resolve branch.
-- Both default 'on' (the wiring exists to feed the AI layers); each is a kill-switch back to the pre-wiring
-- byte-identical prompts. Code-default mirrors: equipment_facts._enabled / asset_candidates._alias_map ('on').
-- ON CONFLICT DO NOTHING so a re-apply never flips operator-tuned state. Run:
--   psql -h 127.0.0.1 -p 5432 -U postgres -d cmd_catalog -f db/seed_equipment_ai_context.sql

INSERT INTO app_config (key, value, data_type, section, note) VALUES
  ('equipment.facts.enabled', 'on', 'text', 'equipment',
   'Layer-2 equipment fact lines (EQUIPMENT/BREAKER/RTM BANDS/ENERGY REGISTER) + PANEL MEMBERS aka suffix. '
   'off = byte-identical pre-wiring prompts. Read by layer2/emit/equipment_facts.py.'),
  ('equipment.alias.enabled', 'on', 'text', 'equipment',
   '1b candidate aka/loc columns + aka listing column + unique-alias resolve branch. off = pre-wiring listing. '
   'Read by layer1b/resolve/asset_candidates.py.')
ON CONFLICT (key) DO NOTHING;
