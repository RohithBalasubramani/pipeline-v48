-- db/seed_llm_admission.sql — global vLLM admission-control knobs [2026-07-12].
-- The per-run emit cap (layer2.emit_concurrency) does NOT compose across concurrent /api/run requests, so N users put
-- up to 4×N ~22K-token emits on the one :8200 vLLM at once — the documented contention that manufactures false 'timeout'
-- failures. llm.global_concurrency bounds TOTAL in-flight vLLM calls per process (acquired inside llm/client.call_qwen,
-- held only across the wire call). DEFAULT 0 = DISABLED (byte-identical to today) — set it (e.g. 8) to enable
-- back-pressure. Code-default mirrors in llm/client.py. DECLARATION seed: ON CONFLICT DO NOTHING (never clobber an
-- operator-tuned value). Idempotent. Run: psql -h localhost -p 5432 -d cmd_catalog -f db/seed_llm_admission.sql
INSERT INTO app_config (key, value, data_type, section, note) VALUES
  ('llm.global_concurrency', '0', 'int', 'llm',
   'Max concurrent in-flight :8200 vLLM calls per process. 0 = disabled (unbounded, current behavior). Set to ~8 to '
   'bound total load regardless of concurrent user count. Mirror: llm/client.py _admission_sem(). Process-fixed '
   '(sized once at first call, like a pool size) — a change needs a restart.'),
  ('llm.admission_wait_s', '60', 'int', 'llm',
   'Max seconds a call waits for a global admission slot before proceeding anyway (fail-open, so back-pressure never '
   'becomes an outage). Only consulted when llm.global_concurrency > 0. Mirror: llm/client.py.')
ON CONFLICT (key) DO NOTHING;
