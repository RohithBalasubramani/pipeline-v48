-- db/seed_resolver_member_direction_ai.sql — T1-10 [AI-first, deterministic_audit_20260714 L1B-4]: DEFAULT OFF.
--
-- resolver.member_direction_ai — read by layer1b/resolve/asset_resolve.py + answer_schema.py: when ON, the 1b
-- resolver EMITS the panel reading side ('incomer'/'outgoing') in its existing LLM call (optional schema key + a
-- prompt clause); panel_sections.stamp_section_facts enum-clamps it and stamps ONE member_scope value that both the
-- emit facts (panel_members_block) and the executor fill (members.role_filter_for) read (dual-consumer parity), with
-- the keyword scan (member_scope.py) kept as the validator + fallback + disagreement telemetry. Fixes keyword misses
-- ('what feeds PCC-1A' -> incomer) and false-positives ('power supply monitoring' should NOT force incomer).
-- When OFF (this default) the schema/prompt/parse collapse: byte-identical, keyword-scan-only, exactly as before.
--
-- Requires llm.guided_json.asset_resolve on for the schema key to bind (the clause + parse work regardless).
-- ON CONFLICT DO NOTHING (not UPDATE): re-running this seed must never flip an operator's 'on' back to 'off'.

INSERT INTO app_config (key, value, data_type, section, note) VALUES
 ('resolver.member_direction_ai', 'off', 'text', 'resolver',
  'T1-10 AI-first: on = the 1b resolver emits the panel reading side (incomer/outgoing) in its existing call, enum-clamped with the keyword scan as fallback; off = byte-identical keyword-scan only (layer1b/resolve/asset_resolve.py + panel_sections.py + answer_schema.py)')
ON CONFLICT (key) DO NOTHING;
