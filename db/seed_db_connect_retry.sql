-- db/seed_db_connect_retry.sql — bounded outage-retry budget for FRESH-CONNECT failures [audit 2026-07-14, 01 F3].
-- The hardened db-tunnel.service restarts in 3-30s; a run in flight during that window failed its first connect
-- instantly (5s fail-fast) and terminated as a whole-page data_unavailable. With the budget on, each connect site
-- (data/db_client checkout + stale-retry reconnect, data/neuract_pool._new) re-attempts OUTAGE-shaPED failures
-- only, with per-caller jittered backoff, for up to this many seconds. 0 = off (code default, byte-identical).
-- Mirror: data/connect_retry.py.  Rollback: UPDATE ... value='0' + v48-host restart (cfg cache).
-- Apply: psql -h localhost -p 5432 -U postgres -d cmd_catalog -f db/seed_db_connect_retry.sql

INSERT INTO app_config (key, value, data_type, section, note) VALUES
  ('db.connect_retry_s', '8', 'number', 'db',
   'Total seconds of bounded, jittered re-attempts for OUTAGE-shaped fresh-connect failures (rides db-tunnel RestartSec 3-30s). Logic errors never retry; nested (cfg-read) connects never retry. 0 = off. Mirror: data/connect_retry.py. Restart required.')
ON CONFLICT (key) DO NOTHING;
