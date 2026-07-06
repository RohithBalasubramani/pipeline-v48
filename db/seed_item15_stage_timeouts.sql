-- db/seed_item15_stage_timeouts.sql — per-stage LLM timeout rows for the ITEM-15 stage= telemetry call sites.
-- [AI_QUALITY_BACKLOG item 15: "Replace literal timeout=120/60 with llm.timeout.<stage> rows."]
--
-- The 1b basket call hardcoded timeout=120 at the call site; the 1a story call rode the base default. Both now pass
-- stage= to llm.client.call_qwen, whose _timeout_for reads llm.timeout.<stage> → llm.timeout (120) → code default 120.
-- These rows are BYTE-EQUAL to the previous effective values (120s), so seeding is behavior-neutral; edit a row to
-- retune a stage with no code change. llm.timeout.asset_resolve (60) already exists — not re-seeded here.
--
-- Idempotent (ON CONFLICT upsert). Apply: psql -U postgres -h 127.0.0.1 -p 5432 -d cmd_catalog -f db/seed_item15_stage_timeouts.sql

INSERT INTO app_config (key, value, data_type, section, note) VALUES
  ('llm.timeout.basket', '120', 'int', 'llm',
   '1b column-basket call timeout seconds (was the hardcoded timeout=120 at the call site). [item 15: DB-driven per-stage timeouts]'),
  ('llm.timeout.stories', '120', 'int', 'llm',
   '1a story_builder call timeout seconds (was the base llm.timeout default). [item 15: DB-driven per-stage timeouts]')
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, data_type = EXCLUDED.data_type,
  section = EXCLUDED.section, note = EXCLUDED.note;
