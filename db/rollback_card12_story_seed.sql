-- db/rollback_card12_story_seed.sql — restore the pre-seed card-12 state (captured 2026-07-16).
DELETE FROM card_payloads WHERE story_id='ems-panel-overview-energy-distribution-cards--energy-input-distribution';
INSERT INTO card_payloads (story_id, title, story_name, is_subcard, card_id, payload, payload_keys)
VALUES ('kpi12_main', 'Peak kW', 'kpi12_main', false, 12,
        '{"kpi":{"pf":null,"title":"Peak kW","value":null}}'::jsonb, '{kpi}')
ON CONFLICT (story_id) DO NOTHING;
-- then re-run: PYTHONPATH=. python3 scripts/build_stripped_payloads.py
