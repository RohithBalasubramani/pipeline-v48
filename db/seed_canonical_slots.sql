-- db/seed_canonical_slots.sql — voltage-monitor CONTRACT-slot completion + nameplate-first band nominal. DEFAULT OFF.
--
-- Two flags, both seeded 'off' so the tree is BYTE-IDENTICAL until an operator flips them:
--
-- fill.canonical_slots — ems_exec/executor/canonical_slots.inject (called by ems_exec/serve/run.run_card BEFORE the
--   fill). ON: deterministically fills any UNBOUND voltage-monitor contract slot from the skeleton's own labels — the
--   R/Y/B phase legend (voltage_r_n/y_n/b_n), the avg/max/min rail (voltage_avg/max/min), and the IS-12360 statutory
--   ±band on data.thresholds (the shaded region). It NEVER overrides an AI-authored bind (only fills slots the emit
--   left blank), honest-degrades every missing column / unrecoverable band, and touches ONLY voltage cards. OFF (this
--   default) = inject() is a no-op, the executor fills exactly the emit's data_instructions.
--
-- derivation.nameplate_nominal_first — ems_exec/derivations/voltage.nominal_voltage_ln. ON: the L-N nominal (hence the
--   statutory band + voltage_history_domain expected band) is the NAMEPLATE fact (asset_nameplate.nominal_voltage_ll ÷
--   √3), falling back to the measured-deviation recovery only for assets with no nameplate. OFF (this default) = the
--   deviation recovery alone (byte-identical). The recovery returns the METER-CONFIGURED nominal, which is wrong for a
--   meter logging kpi_voltage_deviation_pct against a 240 V default while reading an 11 kV feeder (→ 240 V band, not
--   the nameplate's 6351 V) — the Transformer-01 HT case.
--
-- ON CONFLICT DO NOTHING (not UPDATE): re-running must never flip an operator's 'on' back to 'off'. Idempotent.
-- Run: psql (cmd_catalog DSN per config/databases.py) -f db/seed_canonical_slots.sql

INSERT INTO app_config (key, value, data_type, section, note) VALUES
 ('fill.canonical_slots', 'off', 'text', 'fill',
  'Deterministically COMPLETE unbound voltage-monitor contract slots (R/Y/B phase legend, avg/max/min rail, statutory ±band thresholds) at fill time; never overrides an AI bind; honest-degrade; off = executor fills only the emit data_instructions (byte-identical). ems_exec/executor/canonical_slots.py'),
 ('derivation.nameplate_nominal_first', 'off', 'text', 'derivation',
  'ems_exec/derivations/voltage.nominal_voltage_ln prefers the nameplate nominal (nominal_voltage_ll/sqrt3) over the measured-deviation recovery; fixes the HT-meter band (11kV feeder logging deviation vs a 240V default → recovery inverts to 240V, nameplate states 6351V); off = deviation recovery only (byte-identical)')
ON CONFLICT (key) DO NOTHING;
