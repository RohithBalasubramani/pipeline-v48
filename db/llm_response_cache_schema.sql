-- db/llm_response_cache_schema.sql — the exact-match LLM response cache table + knobs [decode-wall Stage 5, 2026-07-15].
-- WHY: identical prompts at temp0/seed42 measurably return DIFFERENT completions under concurrent vLLM batching
-- (obs_llm_calls 5507 vs 5513: byte-identical prompts, 156 response diff regions) — the cache skips repeat decodes
-- AND imposes run-to-run determinism. Hits re-enter the caller's FULL gate chain; DATA always fills live.
-- Rollback: UPDATE the flag row to 'off'; poison suspicion: TRUNCATE llm_response_cache.
-- Run: psql -h localhost -p 5432 -U postgres -d cmd_catalog -f db/llm_response_cache_schema.sql

CREATE TABLE IF NOT EXISTS llm_response_cache (
  key          text PRIMARY KEY,          -- content_key(stage, model, seed, temp, schema, system, user)
  stage        text,
  model        text,
  envelope     jsonb NOT NULL,            -- the raw parsed reply (pre-gates; gates re-run on every hit)
  created_at   timestamptz NOT NULL DEFAULT now(),
  last_hit_at  timestamptz,
  hits         int NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_llm_response_cache_created ON llm_response_cache (created_at);

INSERT INTO app_config (key, value, data_type, section, note) VALUES
  ('llm.response_cache', 'off', 'text', 'llm',
   'Exact-match LLM response cache (llm/response_cache.py, hooked in llm/client.call_qwen). off = every call live '
   '(historical behavior). Guards: allowlisted stages only, temp==0 + pinned seed only, replay-recorder bypass, '
   'clean parse-successes only. Hits re-enter the full deterministic gate chain; data fills live.'),
  ('llm.response_cache.stages', 'basket,l2_emit', 'text', 'llm',
   'Comma allowlist of obs stages the response cache may serve. basket MUST ride along with l2_emit: the basket '
   'output is embedded in the l2 prompt, so an uncached (wobbling) basket busts every downstream l2 key.'),
  ('llm.response_cache_ttl_s', '86400', 'int', 'llm',
   'DB-tier freshness window in seconds (memory tier is pinned at 3600 = the prompt-stability hour bucket).')
ON CONFLICT (key) DO NOTHING;
