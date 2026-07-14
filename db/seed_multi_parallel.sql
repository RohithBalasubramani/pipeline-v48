-- db/seed_multi_parallel.sql — multi-asset compare parallelism knobs [Stage A/B, latency 2026-07-14].
-- DECLARATION seed: both default 0 = sequential (byte-identical to the historical loops). ON CONFLICT DO NOTHING —
-- never clobbers operator tuning. Run: psql -h localhost -p 5432 -U postgres -d cmd_catalog -f db/seed_multi_parallel.sql
--
-- ROLLOUT ORDER (operator UPDATEs, not seeds — llm rows are declared by db/seed_llm_admission.sql):
--   1. UPDATE app_config SET value='3'   WHERE key='multi_asset.fill_concurrency';   -- Stage A
--   2. UPDATE app_config SET value='4'   WHERE key='llm.global_concurrency';         -- BEFORE Stage B (contention guard)
--      UPDATE app_config SET value='300' WHERE key='llm.admission_wait_s';           -- 60s < a queued 150s emit
--   3. UPDATE app_config SET value='2'   WHERE key='multi_asset.lane_concurrency';   -- Stage B
-- Rollback: set the multi_asset rows back to '0' (config reload / host restart; no code change).
-- NOTE config.app_config caches per process — knob edits need the admin config reload or a v48-host restart, and
-- llm.global_concurrency is process-fixed once the semaphore is sized (shrink/disable needs a restart).

INSERT INTO app_config (key, value, data_type, section, note) VALUES
  ('multi_asset.fill_concurrency', '0', 'int', 'multi_asset',
   'Stage A: max concurrent per-asset card fills in host/multi_asset.build_response_multi (also hoists the '
   'compare_mode call alongside the fills). 0/1 = sequential (historical behavior, byte-identical). Suggested 3 — '
   'each fill runs an 8-way neuract executor, so F fills = up to 8*F concurrent reads on the :5433 tunnel.'),
  ('multi_asset.lane_concurrency', '0', 'int', 'multi_asset',
   'Stage B: max concurrent class lanes in run/harness.run_pipeline_multi AFTER the first lane routes the shared 1a '
   '(phase-1 stays sequential until a lane yields layer1a). 0/1 = sequential. Suggested 2 — each lane fans '
   'layer2.emit_concurrency(=4) ~22K-token emits at vLLM; enable llm.global_concurrency=4 + raise '
   'llm.admission_wait_s to 300 BEFORE setting this (the 2026-07-06 contention class: timeouts -> honest-blank cards).')
ON CONFLICT (key) DO NOTHING;
