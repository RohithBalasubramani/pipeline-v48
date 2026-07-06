-- db/seed_item17_guided_json.sql — ITEM 17 stage 1: guided-JSON flag for the 1b ASSET RESOLVER, DEFAULT OFF.
--
-- llm.guided_json.asset_resolve — per-call structured-output flag read by BOTH gates of the item-17 seam:
--   · layer1b/resolve/answer_schema.py  (passes the resolver's answer schema to call_qwen only when on)
--   · llm/client.py _guided_on()        (attaches the guided-decoding param only when llm.guided_json.<stage> is on)
-- When ON, call_qwen(stage='asset_resolve') sends response_format={"type":"json_schema",...} pinning the reply to
-- {"names":[string],"confident":bool,"candidates":[string]} — probed live on :8200 (vLLM 0.16.1rc1): response_format
-- json_schema IS enforced; the legacy `guided_json` extra-body param is silently ignored by that server.
-- When OFF (this default) the request payload is BYTE-IDENTICAL to the pre-item-17 default path.
--
-- ON CONFLICT DO NOTHING (not UPDATE): re-running this seed must never flip an operator's 'on' back to 'off'.
-- Idempotent. Run: psql (cmd_catalog DSN per config/databases.py) -f db/seed_item17_guided_json.sql

INSERT INTO app_config (key, value, data_type, section, note) VALUES
 ('llm.guided_json.asset_resolve', 'off', 'text', 'llm',
  'item 17: vLLM guided decoding (response_format json_schema) for the 1b asset resolver; off = byte-identical legacy request; on = reply pinned to {names:[string],confident:bool,candidates:[string]} (layer1b/resolve/answer_schema.py + llm/client.py _guided_on)')
ON CONFLICT (key) DO NOTHING;
