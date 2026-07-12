-- fix_orphan_knobs_20260712.sql — knob-drift cleanup (refactor audit 2026-07-12, config-centralization F3/F4).
--
-- (1) DELETE the five app_config rows nothing reads (verified tree-wide grep incl. host/, tools/, copilot/, FE):
--     llm.prompt_v2                      — the prompt-v2 selector was deleted 2026-07-08 (emit.py:150); the row lies.
--     flags.ctx_source_form              — zero readers anywhere.
--     flags.page_wise_shared_detection   — zero readers anywhere.
--     flags.require_live_sentinel        — zero readers anywhere.
--     (ems_backend.frame_budget_s is not deleted — it is RENAMED, see (2).)
-- (2) RENAME ems_backend.frame_budget_s → ems_exec.card_budget_s: the seeded budget row used the old name while the
--     only reader (host/exec_cards.py) reads the new one. Both values are 45 → byte-identical behavior; editing the
--     row now actually moves the executor budget.

BEGIN;

DELETE FROM app_config
 WHERE key IN ('llm.prompt_v2',
               'flags.ctx_source_form',
               'flags.page_wise_shared_detection',
               'flags.require_live_sentinel');

UPDATE app_config
   SET key = 'ems_exec.card_budget_s'
 WHERE key = 'ems_backend.frame_budget_s'
   AND NOT EXISTS (SELECT 1 FROM app_config WHERE key = 'ems_exec.card_budget_s');

COMMIT;
