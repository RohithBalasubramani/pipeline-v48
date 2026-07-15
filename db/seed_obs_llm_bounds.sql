-- db/seed_obs_llm_bounds.sql — obs LLM-tap capture bounds [emit forensics 2026-07-15].
-- The response bound used to ride obs.llm.max_prompt_bytes (32768): an 11.7K-token completion (~46K chars) stored
-- truncated mid-JSON, which read as a live truncation during the decode-wall forensics (obs row 4832) and cost a
-- detour. Split bound: responses keep their full bytes (128K covers the worst observed 14.6K-token emission 2.6x)
-- while prompts stay at the existing cap. ON CONFLICT DO NOTHING (never clobber operator tuning).
-- Run: psql -h localhost -p 5432 -U postgres -d cmd_catalog -f db/seed_obs_llm_bounds.sql

INSERT INTO app_config (key, value, data_type, section, note) VALUES
  ('obs.llm.max_response_bytes', '131072', 'int', 'obs',
   'Byte cap on the RESPONSE text stored per obs_llm_calls row (obs/llm_tap.py). 0/absent = fall back to '
   'obs.llm.max_prompt_bytes (the historical behavior, which silently truncated large completions mid-JSON in the '
   'stored copy only - the live parse was fine). 131072 keeps the full worst-observed emission for forensics.')
ON CONFLICT (key) DO NOTHING;
