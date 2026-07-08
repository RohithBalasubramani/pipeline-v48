-- db/seed_member_scope_vocab.sql — the ONE store for the PANEL READING-DIRECTION vocabulary [panel_overview, 2026-07-08].
--
-- A panel-overview page aggregates its member meters, which split into OUTGOING (fed feeders/bays/loads — the DEFAULT
-- reading direction) and INCOMER (supply/source/upstream — used only when the prompt explicitly asks for it). The
-- direction is resolved from the prompt by layer1b/resolve/member_scope.py, whose ONLY policy input is the incomer-
-- keyword list below (everything not matching defaults to outgoing). Editing this row retunes direction detection with
-- NO code edit; the code tuple _INCOMER_KEYWORDS_DEFAULT in member_scope.py is only the DB-down fallback mirror.
--
-- Idempotent (ON CONFLICT). Run:
--   psql -h localhost -p 5432 -d cmd_catalog -f db/seed_member_scope_vocab.sql

INSERT INTO app_config (key, value, data_type, section, note) VALUES
  ('vocab.panel_member_direction',
   '["incomer","incomers","incoming","supply","supply side","source side","upstream","ht side","hv side","feed-in","feed in","in-feed","infeed"]',
   'json', 'vocab',
   'Incomer-selecting keywords for a panel-overview prompt. A prompt containing any of these reads the panel''s '
   'SUPPLY (incomer) member set; every other panel prompt defaults to the OUTGOING (fed-feeder/bay) set. '
   'Mirror: layer1b/resolve/member_scope.py _INCOMER_KEYWORDS_DEFAULT. Read by member_scope().')
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, note = EXCLUDED.note, section = EXCLUDED.section;
