-- db/seed_equipment_topology.sql — stream A equipment-topology knobs. BOTH ship inert (kill-switch off + empty
-- allowlist) and use ON CONFLICT DO NOTHING so a re-apply NEVER flips an operator-tuned kill-switch or a staged,
-- human-vetted allowlist entry (unlike the DO UPDATE seeds — these two rows are operator state, not derived config).
-- Enabling a panel = editing the allowlist row with a curated entry, e.g. (verified worked example):
--   {"pcc_panel_1_feedbacks": {"nodes": ["pcc-1a", "pcc-1b"],
--                              "extra_ok": ["gic_01_n10_hhf_01_type_01_300a_600kvar_p1",
--                                           "gic_02_n10_hhf_02_type_01_300a_600kvar_p1"]}}
-- Idempotent. Run: psql -U postgres -h 127.0.0.1 -p 5432 -d cmd_catalog -f db/seed_equipment_topology.sql
INSERT INTO app_config (key, value, data_type, section, note) VALUES
 ('equipment.topology.enabled', 'off', 'text', 'equipment',
  'Kill-switch for the bay-anchored equipment panel rosters (data/equipment/edges.py). LATCHED at first use per '
  'process so lt_mfm/panel_members caches never see a mid-run source switch — flip + restart. Code default off.'),
 ('equipment.topology.panel_allowlist', '{}', 'json', 'equipment',
  'canonical_panel_table -> {"nodes": [equipment.equipment.key,...], "extra_ok": [canonical_table,...]}. A panel is '
  'equipment-rostered ONLY when named here AND the two-sided guard passes (never lose a mirror member; never gain a '
  'member not vetted in extra_ok). Empty dict = feature inert even when enabled. Each entry is a staged, '
  'human-verified row. Code default {}.')
ON CONFLICT (key) DO NOTHING;
