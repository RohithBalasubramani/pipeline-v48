-- fix_retire_roster_column_knobs.sql — retire the roster column half-knobs (hardcoding audit 2026-07-12, F10).
--
-- `roster.power_column` / `roster.pf_columns` promised the canonical power/PF columns were DB rows, but editing
-- them moved ONLY ems_exec/executor/bindings.py Policy — the same gic_* names are literals in
-- derivation_binding.base_columns rows, _story/_facts.py LIVE_COLS and the schema_slot_map seed (~15 consumers).
-- Verdict (option b of F10): the neuract gic_* column names are FIXED SCHEMA VOCABULARY, not site config —
-- renaming one is a schema migration. bindings.py now carries the literals with a pointer here; deleting the rows
-- is byte-identical behavior (both rows equalled the code defaults: 'active_power_total_kw' /
-- '["kpi_true_pf","power_factor_total"]' — verified before delete, tree-wide grep incl. host/, tools/, CMD found
-- no other reader).
BEGIN;

DELETE FROM app_config WHERE key IN ('roster.power_column', 'roster.pf_columns');

COMMIT;
