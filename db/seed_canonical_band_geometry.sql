-- db/seed_canonical_band_geometry.sql — F6 flag. DEFAULT OFF (byte-identical).
--
-- fill.canonical_band_geometry — ems_exec/executor/canonical_slots._band_geometry_add (run from inject() at fill time).
-- ON: fill any UNBOUND statutory-band geometry leaf (…maxLine.value / …minLine.value / …expectedMax / …expectedMin) on a
-- voltage card from the nameplate-first IS-12360 band (the same band adopted for the Voltage Monitor card 37, extended to
-- the sibling Voltage History / DG-voltage cards which nest their chart under history.data / their own root key). Walks
-- from the payload ROOT (not ['data']) so it reaches the nested band leaves. Only fills UNBOUND leaves — a maxLine/minLine
-- the emit already bound to the data extent (voltage_max/min) is left untouched; the expected-range band (unbound) is
-- filled. Honest-blank when no band is recoverable. OFF (this default) = byte-identical.
--
-- ON CONFLICT DO NOTHING (idempotent; never flips an operator 'on' back to 'off').

INSERT INTO app_config (key, value, data_type, section, note) VALUES
 ('fill.canonical_band_geometry', 'off', 'text', 'fill',
  'F6: fill unbound statutory-band geometry leaves (maxLine/minLine/expectedMax/expectedMin) on sibling voltage cards (Voltage History, DG voltage) from the nameplate-first IS-12360 band; only unbound leaves, honest-blank when no band; off=byte-identical. ems_exec/executor/canonical_slots._band_geometry_add')
ON CONFLICT (key) DO NOTHING;
