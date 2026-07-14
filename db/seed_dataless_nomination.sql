-- db/seed_dataless_nomination.sql — T1-12: the DATALESS AI-NOMINATION flag, DEFAULT OFF.
--
-- swap.dataless_nomination — read by config/feasibility.py lazy attr DATALESS_NOMINATION (config.app_config.flag_on):
--   when ON, a pure per-asset DATALESS force-swap (answerability='none', NOT a static-unrenderable catalog verdict)
--   honors the AI's OWN swap target — captured pre-normalization in layer2/swap/decide.gate and passed as
--   ai_nomination into gate_force_renderable.enforce() — INSTEAD of the deterministic closest-size default, but ONLY
--   when that nominated id is a valid, unclaimed candidate in the slot's swap pool (else it falls through to the
--   closest-size loop unchanged). The knob also gates one extra clause in the emit swap directive
--   (layer2/emit/user_message.py) so a fillable, angle-relevant swap is invited.
--
-- When OFF (this default) enforce() ignores the nomination and the closest-size loop runs exactly as before, and the
-- emit user message is BYTE-IDENTICAL to the pre-T1-12 default path. The static-unrenderable path never consults the
-- nomination in either state.
--
-- ON CONFLICT DO NOTHING (not UPDATE): re-running this seed must never flip an operator's 'on' back to 'off'.
-- Idempotent. Run: psql (cmd_catalog DSN per config/databases.py) -f db/seed_dataless_nomination.sql

INSERT INTO app_config (key, value, data_type, section, note) VALUES
 ('swap.dataless_nomination', 'off', 'text', 'swap',
  'T1-12: a DATALESS force-swap honors the AI''s own swap_to_id when it is a valid, unclaimed pool candidate; off = byte-identical closest-size behavior (config/feasibility.DATALESS_NOMINATION, gate_force_renderable.enforce, user_message swap directive)')
ON CONFLICT (key) DO NOTHING;
