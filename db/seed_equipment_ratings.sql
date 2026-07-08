-- db/seed_equipment_ratings.sql — STREAM B (equipment ratings/limits): the derivations kill-switch, the RTM band
-- const rows, and the breakerOverloadPct derivation_binding row. All sourced LOCALLY (cmd_catalog :5432 — never the
-- :5433 tunnel). Idempotent. Run: psql (cmd_catalog DSN per config/databases.py) -f db/seed_equipment_ratings.sql
--
-- equipment.derivations.enabled (DEFAULT OFF — cert sequencing): gates breakerOverloadPct at the SOURCE
-- (ems_exec/derivations/registry.catalog() omits the entry, so certified prompts never gain a line, a hidden-count
-- drift, or a new trailer) AND in the fn body (ems_exec/derivations/breaker.overload_pct returns None), so a
-- knobs-off emission is byte-identical and unfillable [fatal R2-2 fix]. ON CONFLICT DO NOTHING — re-applying this
-- seed must never flip an operator's 'on' back to 'off'. Staged flip per the SUMMARY runbook before any live 'on'.

INSERT INTO app_config (key, value, data_type, section, note) VALUES
 ('equipment.derivations.enabled', 'off', 'text', 'equipment',
  'stream B kill-switch: on = breakerOverloadPct offered in the recovery library (registry.catalog) and computable; off (default) = entry absent from every prompt + fn returns None — certified emissions byte-identical')
ON CONFLICT (key) DO NOTHING;

-- consts.rtm_<paneltype>_<metric>_<band> — 72 rows (6 metrics x 3 panel types x 4 bands): the RTM banding ceilings
-- (low/normal/moderate/high _max) derived IN-DB from equipment.rtm_threshold, keyed EXACTLY as
-- data/equipment/ratings.rtm_const_key() spells them (the single key-speller; the parity test in
-- tests/test_equipment_ratings.py pins both sides so the spellings can never fork). These are the legal const
-- sources stream C's RTM BANDS fact line cites per R10(b).
--
-- RE-DERIVATION AUTHORITY (deliberate ON CONFLICT DO UPDATE, unlike the DO-NOTHING knob above):
-- equipment.rtm_threshold IS the ground truth for these bands — re-applying this seed re-derives every consts.rtm_*
-- value from it, overwriting any hand-edited const row BY DESIGN. Tune a band by editing the equipment.rtm_threshold
-- row and re-applying this seed, not by editing the const row.

INSERT INTO app_config (key, value, data_type, section, note)
SELECT 'consts.rtm_' || pt.code || '_' || t.metric || '_' || b.band,
       b.val::text,
       'number',
       'consts',
       'RTM band ceiling (' || b.band || '_max) for panel type ' || pt.code || ', metric ' || t.metric
         || ' — RE-DERIVED from equipment.rtm_threshold (the ground truth) on every seed apply; edit that table, not this row'
FROM equipment.rtm_threshold t
JOIN equipment.core_paneltype pt ON pt.id = t.panel_type_id
CROSS JOIN LATERAL (VALUES
  ('low',      t.low_max),
  ('normal',   t.normal_max),
  ('moderate', t.moderate_max),
  ('high',     t.high_max)) AS b(band, val)
WHERE t.panel_type_id IS NOT NULL
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, note = EXCLUDED.note, updated_at = now();

-- derivation_binding row for breakerOverloadPct — without it config.derivation_binding.binding() returns None and
-- the executor's derived path builds an EMPTY input row, so the fn could never fill even at knob-ON (the exact
-- defect db/seed_derivation_binding_full.sql was shipped to close). base_columns is 'current_avg' ONLY: the breaker
-- rating is NOT a frame column — the fn resolves it itself via data/equipment/ratings (the upsRatedKva precedent of
-- non-frame inputs staying out of base_columns), which also keeps bindable() satisfiable on any current-bearing
-- meter. Byte-safe at knobs-off: the row only matters for a card that names the fn, and the fn is never offered
-- (and returns None) while the knob is off. ON CONFLICT re-derives, matching the derivation_binding convention.

INSERT INTO derivation_binding (metric, fn, base_columns, fidelity, scope) VALUES
 ('breakerOverloadPct', 'breakerOverloadPct', 'current_avg', 'real_exact', 'row')
ON CONFLICT (metric) DO UPDATE SET fn = EXCLUDED.fn, base_columns = EXCLUDED.base_columns,
  fidelity = EXCLUDED.fidelity, scope = EXCLUDED.scope;
