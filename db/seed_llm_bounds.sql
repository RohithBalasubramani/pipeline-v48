-- db/seed_llm_bounds.sql — per-stage completion-token bound [decode-wall root fix Stage 3, 2026-07-15].
-- llm.max_tokens.<stage> wins over the base llm.max_tokens; both absent = unbounded (the historical behavior).
-- l2_emit = 6000: POST-DIET a legitimate emit is ~200-2,900 completion tokens (measured on the runaway cards' own
-- pages with emit.diet.* on: card 24 590, card 19 166, card 22 1,336, worst full-author card 23 2,861), so >6K is by
-- definition the pathology class (the 14.6K zero-filled-grid emissions). A capped runaway costs ~85s decode + ONE
-- honest-blank card (finish_reason=length -> 'truncated' = fail-fast, no-retry, per-leaf honesty) instead of a 150s
-- wall that poisons sibling decodes. ADOPT ONLY AFTER the diet flags (db/seed_emit_diet.sql) are on.
-- Pair with: UPDATE app_config SET value='120' WHERE key='llm.timeout.l2_emit';  (150->120: cap decode ~85s +
-- ~22K-token prefill 10-15s fits; 90 would RACE the truncation return and misclassify honest truncations as timeouts.)
-- ON CONFLICT DO NOTHING. Run: psql -h localhost -p 5432 -U postgres -d cmd_catalog -f db/seed_llm_bounds.sql

INSERT INTO app_config (key, value, data_type, section, note) VALUES
  ('llm.max_tokens.l2_emit', '6000', 'int', 'llm',
   'Completion-token cap for the l2_emit stage (llm/client._max_tokens_for; per-stage wins over base llm.max_tokens; '
   '0/absent = unbounded). Post-diet legit emits are ~200-2,900 tok -> 6000 is the runaway guillotine, >2x observed '
   'max. Truncation = honest-blank card (no retry), never wrong numbers.')
ON CONFLICT (key) DO NOTHING;
