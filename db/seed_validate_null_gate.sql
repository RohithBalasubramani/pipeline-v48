-- db/seed_validate_null_gate.sql — the >50%-null column gate policy + the event/counter/boolean column vocabulary
-- (validate/null_gate.py). One concern: null-gate rows only.
--
-- DEFECT (2026-07-07 user directive): the validate layer FAILED any basket column >MAX_NULL_RATE (0.5) null over the
-- probe window, so the page banner showed 'N fail' for NORMAL event-column sparsity — dg_1_mfm
-- current_imbalance_event_active is 99.85% null because it is a 12-minute event BURST column: NULL means 'no event',
-- not missing data. The >50%-null check now produces an informational WARN at most (never verdict=fail), and
-- EVENT/COUNTER/BOOLEAN-semantic columns (name tokens below / boolean data_type) read NULL as 0 ('no event') for the
-- verdict statistics, so their sparsity is a PASS with an informational reason. Electrical quantities are NEVER
-- coerced (a null voltage is NOT 0 V) — a genuinely all-null electrical column still surfaces as a warn.
--
-- Rows are BYTE-EQUAL to the code defaults (validate/null_gate.py DEFAULT_MODE / DEFAULT_EVENT_TOKENS), so seeding is
-- behavior-neutral; edit a row to change the gate with no code change. Idempotent (ON CONFLICT upsert).
-- Apply: psql -U postgres -h 127.0.0.1 -p 5432 -d cmd_catalog -f db/seed_validate_null_gate.sql

INSERT INTO app_config (key, value, data_type, section, note) VALUES
  ('validate.null_gate_mode', 'warn', 'text', 'validate',
   'What the >MAX_NULL_RATE (mostly-null) basket-column check produces for a NON-event column: fail (legacy page-blocking verdict) | warn (informational annotation, the default) | off (no mostly-null annotation at all; the separate >WARN_NULL_RATE band and the latest-row warn are untouched). Consumed by validate/null_gate.py null_gate_mode() inside validate/data_validate.py. Code default warn.'),
  ('validate.event_semantic_tokens', '["_event_", "_count", "_active", "_flag"]', 'json', 'validate',
   'Name-token vocabulary marking a column as EVENT/COUNTER/FLAG-semantic (NULL = no event = 0 for the validate verdict statistics; sparsity is normal, never a null-rate warn/fail). A token ending "_" matches anywhere in the lowercased column name; any other token matches as a suffix. A boolean data_type is event-semantic regardless of name. Verified against live neuract information_schema: these tokens hit only *_event_*, *_count, *_flag, *_active and boolean status/breaker columns — no electrical quantity. Consumed by validate/null_gate.py is_event_semantic(). Code default ["_event_", "_count", "_active", "_flag"].')
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, data_type = EXCLUDED.data_type,
  section = EXCLUDED.section, note = EXCLUDED.note;
