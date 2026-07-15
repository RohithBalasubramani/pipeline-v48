-- db/seed_polarity_substitute.sql — the energy-polarity fn SUBSTITUTION knob [audit 2026-07-14, 13 F2].
-- ~55% of quantity_mismatch blanks were UPS-class meters that DO log the right register: grounding bound the
-- wrong-POLARITY energy fn (active↔reactive↔apparent) and verify._polarity_conflict correctly blanked it. With
-- the knob on, fill substitutes the EXPLICIT registry sibling (ems_exec/derivations/registry._POLARITY_SIBLINGS)
-- that computes the slot's own quantity — honest by construction (the slot's unit/label is the contract; the fn
-- was the mislabel). Decision telemetry: executor degrade note 'polarity_substitute'.
-- Rollback: UPDATE app_config SET value='off' WHERE key='fill.polarity_fn_substitute';  (+ host restart, cfg cache)
-- Apply: psql -h localhost -p 5432 -U postgres -d cmd_catalog -f db/seed_polarity_substitute.sql

INSERT INTO app_config (key, value, data_type, section, note) VALUES
  ('fill.polarity_fn_substitute', 'on', 'text', 'fill',
   'On a verify._polarity_conflict refusal, substitute the explicit same-meaning registry sibling of the slot''s polarity (registry._POLARITY_SIBLINGS; base columns must be present). off = pre-2026-07-15 behavior: honest blank + quantity_mismatch reason. Code default on.')
ON CONFLICT (key) DO NOTHING;
