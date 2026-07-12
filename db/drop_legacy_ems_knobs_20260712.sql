-- drop_legacy_ems_knobs_20260712.sql — remove the 4 orphaned WS-fetch knobs of the retired legacy EMS media/WS
-- service (its config module is deleted; zero code consumers — the retired workers/ path was their only reader).
-- APPLIED 2026-07-12. Mirrors db/fix_orphan_knobs_20260712.sql (the campaign's orphan-knob pattern).
DELETE FROM app_config WHERE key IN
  ('ems_backend.connect_timeout_s', 'ems_backend.frame_timeout_s',
   'ems_backend.fetch_attempts',    'ems_backend.retry_backoff_s');
