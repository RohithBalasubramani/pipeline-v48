-- db/seed_route_guided_json.sql — guided-JSON flag for the 1a PAGE ROUTER, DEFAULT OFF. [L1a routing-determinism]
--
-- llm.guided_json.route — per-call structured-output flag read by BOTH gates of the router's guided-decode seam
-- (mirrors llm.guided_json.asset_resolve exactly — db/seed_item17_guided_json.sql):
--   · layer1a/route_schema.py  route_answer_schema()  (passes the router's enum-constrained answer schema to
--     call_qwen only when on; page_key pinned to THIS prompt's candidate page_keys, metric/intent to their vocab)
--   · llm/client.py            _guided_on()           (attaches the response_format json_schema param only when
--     llm.guided_json.<stage> is on)
-- When ON, call_qwen(stage='route') sends response_format={"type":"json_schema",...} pinning page_key to the exact
-- candidate list, so a near-tie route can no longer DRIFT to a different page under sweep/batch load (the L1a
-- non-determinism defect: same prompt routed to different pages run-to-run — pg08 energy-power↔a DG page, pg11
-- engine-cooling↔operations-runtime, pg15 thermal-life↔power-quality, the compare lane↔DG operations-runtime).
-- Probed live on :8200 (vLLM 0.16.1rc1): response_format json_schema IS enforced; the legacy `guided_json`
-- extra-body param is silently ignored by that server.
-- When OFF (this default) the request payload is BYTE-IDENTICAL to the pre-fix default path (json_object).
--
-- ON CONFLICT DO NOTHING (not UPDATE): re-running this seed must never flip an operator's 'on' back to 'off'.
-- Idempotent. Run: psql (cmd_catalog DSN per config/databases.py) -f db/seed_route_guided_json.sql

INSERT INTO app_config (key, value, data_type, section, note) VALUES
 ('llm.guided_json.route', 'off', 'text', 'llm',
  'L1a routing-determinism: vLLM guided decoding (response_format json_schema) for the 1a page router; off = byte-identical legacy request; on = page_key pinned to the exact candidate page_keys + metric/intent to their vocab so a near-tie route cannot drift run-to-run under batch load (layer1a/route_schema.py + llm/client.py _guided_on)')
ON CONFLICT (key) DO NOTHING;
