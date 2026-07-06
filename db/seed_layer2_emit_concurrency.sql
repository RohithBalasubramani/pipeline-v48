-- db/seed_layer2_emit_concurrency.sql — the per-page Layer-2 emit fan-out concurrency CAP.
-- One concern: run/layer2_all.py fans one large-prompt (~22K-tok) l2_emit per card at once; an UNBOUNDED pool split
-- the vLLM's decode throughput N ways, sitting the biggest emit (the harmonics heatmap) at the 150s l2_emit fail-fast
-- edge even on a solo 5-card page — and starving it to a FALSE timeout under a multi-page sweep. This cap bounds the
-- in-flight emits so each keeps enough per-request throughput to finish with margin; excess cards queue.
-- Mirrors the code default in run/layer2_all.py (cfg("layer2.emit_concurrency", 4)) — editable with no code change.
-- Idempotent. Run: psql (cmd_catalog DSN per config/databases.py) -f db/seed_layer2_emit_concurrency.sql
INSERT INTO app_config (key, value, data_type, section, note) VALUES
 ('layer2.emit_concurrency', '4', 'int', 'layer2',
  'Max concurrent per-card l2_emit calls in the run_2_all fan-out (run/layer2_all.py). Bounds vLLM load so a large '
  'emit keeps enough decode throughput to finish inside llm.timeout.l2_emit; excess cards queue. Lower for more '
  'timeout margin on the biggest cards, raise for lower page latency. Code default 4.')
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, data_type = EXCLUDED.data_type,
                                section = EXCLUDED.section, note = EXCLUDED.note;
