-- db/seed_knowledge.sql — the SEPARATE knowledge Q&A pipeline's knobs (user directive 2026-07-06):
-- conceptual electrical/mechanical questions get ONE restricted educator answer; off-domain prompts are refused;
-- asset/data prompts flow to the card pipeline unchanged. Prompts live in knowledge/prompts/*.md; these rows are the
-- runtime valve + the refusal sentence (mirrored in code defaults; fail-open).
INSERT INTO app_config (key, value, data_type, section, note) VALUES
 ('knowledge.enabled', 'on', 'text', 'knowledge',
  'valve for the knowledge pre-route in host /api/run (off -> every prompt goes to the card pipeline as before)'),
 ('knowledge.refusal_line', 'I can only answer electrical, mechanical and energy-management questions for this EMS.', 'text', 'knowledge',
  'the exact off-domain refusal sentence (router off_domain branch AND the system prompt hard-restriction #1 use it)')
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, data_type = EXCLUDED.data_type,
                                section = EXCLUDED.section, note = EXCLUDED.note;
