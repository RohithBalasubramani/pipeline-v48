-- db/seed_resolver_section_ai.sql — T0-9 [AI-first, deterministic_audit_20260714 L1B-1]: DEFAULT OFF.
--
-- resolver.section_ai — read by layer1b/resolve/asset_resolve.py (_section_ai_on) + answer_schema.py: when ON, the
-- 1b asset resolver EMITS the prompt's bus section ('A'/'B'/'both'/'none') in its existing LLM call (optional schema
-- key + a prompt clause); layer1b/resolve/panel_sections.stamp_section_facts VALIDATES the emission against the
-- pcc_panel_alias facts and falls back to the deterministic substring detector on any miss (AI decides; deterministic
-- validates + falls back). Fixes the elided section compare 'compare pcc 1a and 1b' the substring detector misses
-- ('comparepcc1aand1b' contains 'pcc1a' but not 'pcc1b' -> silent wrong single-slice).
-- When OFF (this default) the schema, prompt, and parse all collapse: the request is BYTE-IDENTICAL and the
-- substring detector alone stamps section/compare_sections, exactly as before.
--
-- Requires llm.guided_json.asset_resolve on for the schema key to bind (the clause + lenient parse work regardless).
-- ON CONFLICT DO NOTHING (not UPDATE): re-running this seed must never flip an operator's 'on' back to 'off'.
-- Idempotent. Run: psql (cmd_catalog DSN per config/databases.py) -f db/seed_resolver_section_ai.sql

INSERT INTO app_config (key, value, data_type, section, note) VALUES
 ('resolver.section_ai', 'off', 'text', 'resolver',
  'T0-9 AI-first: on = the 1b resolver emits the bus section (A/B/both/none) in its existing call, validated vs pcc_panel_alias facts with the substring detector as fallback; off = byte-identical, detector-only (layer1b/resolve/asset_resolve.py + panel_sections.py + answer_schema.py)')
ON CONFLICT (key) DO NOTHING;
