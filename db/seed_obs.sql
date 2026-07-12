-- db/seed_obs.sql — app_config knobs for the observability layer (obs/). Every knob is DB-tunable with the code
-- default as fallback (absent row = the value shown here), matching the cfg() convention. Idempotent.
-- Run:  psql -h localhost -p 5432 -d cmd_catalog -f db/seed_obs.sql

INSERT INTO app_config (key, value, data_type, section, note) VALUES
  ('obs.enabled',              'on',    'text',   'obs', 'Master valve for the trace/span observability layer (off = only the legacy stage/failures logs run).'),
  ('obs.sink.console',         'on',    'text',   'obs', 'Human stderr line per stage/llm event (host-log watching).'),
  ('obs.sink.jsonl',           'on',    'text',   'obs', 'Per-trace outputs/logs/trace_<trace_id>.jsonl replay file.'),
  ('obs.sink.pg',              'on',    'text',   'obs', 'Queryable cmd_catalog obs_* store (buffered background writer, db/obs_schema.sql).'),
  ('obs.max_field_bytes',      '16384', 'int',    'obs', 'Size bound per logged inputs/outputs/validation field (shape-preserving truncation, obs/redact.py).'),
  ('obs.llm.max_prompt_bytes', '32768', 'int',    'obs', 'Size bound for stored LLM prompts/responses in obs_llm_calls.'),
  ('obs.llm.max_decision_bytes', '24576', 'int',  'obs', 'Size bound for the stored decision context (candidates…) per LLM call — obs_llm_calls.decision (AI Decision Inspector).'),
  ('obs.buffer_max',           '5000',  'int',    'obs', 'pg sink queue depth; overflow drops events and counts them (never blocks the pipeline).'),
  ('obs.flush_interval_s',     '2',     'number', 'obs', 'pg sink batch flush interval, seconds.'),
  ('obs.retention_days',       '30',    'int',    'obs', 'obs_* rows older than this are purged by the pg sink (daily, fail-open); 0 = keep forever.')
ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value, data_type=EXCLUDED.data_type, note=EXCLUDED.note;
