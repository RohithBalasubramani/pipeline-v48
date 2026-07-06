-- db/seed_llm_emit_timeout.sql — l2_emit LLM timeout + deterministic-failure no-retry policy.
-- The largest panel-aggregate emit (card 5 RTM heatmap, ~32K-tok prompt) grazes the 120s default; a modest bump
-- lets typical runs complete, and emit.py NO LONGER retries a 'timeout'/'truncated' (deterministic) failure
-- (retrying only doubled the wall-clock hang). Idempotent.
INSERT INTO app_config (key, value, data_type, section) VALUES
 ('llm.timeout', '120', 'number', 'llm'),
 ('llm.timeout.l2_emit', '150', 'number', 'llm'),
 ('llm.no_retry_kinds', 'timeout,truncated', 'text', 'llm')
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, data_type = EXCLUDED.data_type, section = EXCLUDED.section;
