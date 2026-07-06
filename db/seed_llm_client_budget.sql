-- db/seed_llm_client_budget.sql — LLM-client deterministic-failure policy rows [backlog A3]
-- (code-default mirrors in llm/client.py — behavior is identical until a row is edited).
--
-- TRUNCATION NO-RETRY + PROMPT-BUDGET PREFLIGHT [ai_r_f9787f915f: 3 length-truncated emits, the parse retry GREW the
-- prompt 46,438→46,589 ptok against the 65,536-token window and deterministically truncated again]:
--   llm.no_retry_kinds     — failure kinds that are DETERMINISTIC for a pinned-seed temp-0 call and therefore never
--                            retried, neither by llm/client.py's parse-retry loop nor by layer2/emit/emit.py's
--                            transport retry (both read THIS row; same default).
--   llm.prompt_budget_tok  — preflight ceiling on the (system+user)/4 chars→token estimate; a prompt over it is
--                            never sent (kind 'over_budget', obs.failures telemetry) instead of burning the full
--                            timeout on a doomed call. 0 = preflight off.
--
-- Idempotent. Run: psql (cmd_catalog DSN per config/databases.py) -f db/seed_llm_client_budget.sql

INSERT INTO app_config (key, value, data_type, section, note) VALUES
 ('llm.no_retry_kinds', 'timeout,truncated', 'text', 'llm',
  'comma-separated LlmError kinds that fail FAST (deterministic for a pinned-seed temp-0 call — a retry only doubles the hang / grows the prompt); honored by llm/client.py parse-retry AND layer2/emit/emit.py transport retry'),
 ('llm.prompt_budget_tok', '45000', 'int', 'llm',
  'prompt-budget preflight: (len(system)+len(user))//4 token estimate above this → kind over_budget, call never sent; sized to the 65,536-token vLLM window minus a ~20K completion floor; 0 = off')
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, data_type = EXCLUDED.data_type,
                                section = EXCLUDED.section, note = EXCLUDED.note;
