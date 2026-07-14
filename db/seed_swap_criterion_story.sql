-- db/seed_swap_criterion_story.sql — T1-11: the CRITERION<->STORY swap gate flag + its min-token-len knob, DEFAULT OFF.
--
-- swap.criterion_story_gate — read by layer2/swap/gate_criterion_story.enabled() (config.app_config.flag_on):
--   the gate rejects a swap whose criterion names NO word of the card's own analytical story angle (a stricter sibling
--   of the cheap closed-vocab gate_vague_reject, which still runs first). It is the ONLY swap gate that leaves a
--   corrective reason, on which layer2/build.py re-emits ONCE and re-gates.
-- swap.criterion_story_min_token_len — the minimum token length kept from BOTH the criterion and the story before the
--   shared-token test (default 4); read per call in gate_criterion_story._min_token_len().
--
-- When OFF (this default) gate_criterion_story.ok() returns True unconditionally and no re-emit ever fires — the swap
-- gate chain + the emit request are BYTE-IDENTICAL to the pre-T1-11 default path.
--
-- ON CONFLICT DO NOTHING (not UPDATE): re-running this seed must never flip an operator's 'on' back to 'off'.
-- Idempotent. Run: psql (cmd_catalog DSN per config/databases.py) -f db/seed_swap_criterion_story.sql

INSERT INTO app_config (key, value, data_type, section, note) VALUES
 ('swap.criterion_story_gate', 'off', 'text', 'swap',
  'T1-11: reject a swap whose criterion shares no story-angle token with the card''s analytical story; off = byte-identical legacy path (layer2/swap/gate_criterion_story.py, decide.gate, build.py corrective re-emit)'),
 ('swap.criterion_story_min_token_len', '4', 'int', 'swap',
  'T1-11: minimum token length kept from the criterion and the story before the shared-token test (gate_criterion_story._min_token_len)')
ON CONFLICT (key) DO NOTHING;
