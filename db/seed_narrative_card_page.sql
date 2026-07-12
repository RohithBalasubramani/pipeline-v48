-- seed_narrative_card_page.sql — the narrative_ai card→page fallback map as an editable row (hardcoded-mappings
-- sweep, refactor audit 2026-07-12). Mirrors ems_exec/renderers/_story/__init__.py CARD_PAGE byte-for-byte —
-- behavior-identical until edited; a NEW AI-summary card on an existing page then dispatches with a row edit,
-- no code change. Reader: _story.card_page() (used by narrative_ai._page_key when ctx omits page_key).
INSERT INTO app_config (key, value, data_type, section, note) VALUES
  ('renderers.narrative_card_page',
   '{"8": "real-time-monitoring", "19": "voltage-current", "25": "harmonics-pq", "28": "individual-feeder"}',
   'json', 'renderers',
   'card_id -> page_key fallback for AI-summary (narrative_ai) cards when ctx omits page_key; mirrors _story/__init__.py CARD_PAGE')
ON CONFLICT (key) DO NOTHING;
