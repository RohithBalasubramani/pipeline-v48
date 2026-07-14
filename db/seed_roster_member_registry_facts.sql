-- db/seed_roster_member_registry_facts.sql — T2.1-1 [deterministic_audit_20260714, CONFIRMED runtime bug]: DEFAULT OFF.
--
-- roster.member_registry_facts — read by ems_exec/executor/members.py (_meter_row) + host/exec_cards.py
-- (_registry_mfm_id). The historical `from registries import neuract` import referenced a package renamed to
-- data.neuract_live; wrapped in try/except it raised EVERY call, so every roster member's type/load_group was None
-- for the process life. That silently killed the FACT-keyed roster matchers (match.types / match.load_groups in
-- card_fill_recipe 5/16/17) and forced everything onto name_contains -- e.g. card-16's `ups` energy series, keyed
-- ONLY on {types:[ups]}, matched nothing and rendered EMPTY.
-- Flag ON restores the real facts via the renamed door (meter_by returns type_code/load_group); OFF keeps the
-- dead-{} behavior so adoption is a measured, reversible payload-diff (the type-keyed series + section/legend
-- groupings regroup once real facts flow). BYTE-IDENTICAL when off.
--
-- ON CONFLICT DO NOTHING (not UPDATE): re-running this seed must never flip an operator's 'on' back to 'off'.

INSERT INTO app_config (key, value, data_type, section, note) VALUES
 ('roster.member_registry_facts', 'off', 'text', 'roster',
  'T2.1-1: on = restore member type_code/load_group facts (data.neuract_live.meter_by) that the stale registries import killed, re-enabling fact-keyed roster matchers; off = dead-{} legacy, byte-identical (ems_exec/executor/members.py + host/exec_cards.py)')
ON CONFLICT (key) DO NOTHING;
