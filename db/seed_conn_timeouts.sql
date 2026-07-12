-- db/seed_conn_timeouts.sql — neuract connection safety knobs [half-dead-tunnel guard 2026-07-12].
-- The neuract live-data DB rides an SSH tunnel on :5433 that is documented to flap. These knobs bound how long a
-- half-open socket can wedge a pooled psycopg2 connection (and thus every executor thread behind its lock) before the
-- read fails fast and the honest-degrade path renders `data_unavailable`. Code-default mirrors live in
-- config/neuract_dsn.conn_kwargs() — this file only makes them editable without a code change, and behaves identically
-- to the code until an operator tunes a row. Both pooled doors (ems_exec/data/neuract.py + data/neuract_live/_db.py)
-- read the same conn_kwargs(), so a knob edited here moves both.
--
-- DECLARATION seed: ON CONFLICT DO NOTHING (never clobber an operator-tuned value on re-run — audit finding F3).
-- Idempotent. Run: psql -h localhost -p 5432 -d cmd_catalog -f db/seed_conn_timeouts.sql
INSERT INTO app_config (key, value, data_type, section, note) VALUES
  ('neuract.connect_timeout_s', '5', 'int', 'neuract',
   'libpq connect_timeout (s) for the pooled neuract doors. A half-dead :5433 tunnel fails the connect in this many '
   'seconds instead of the ~2-min OS TCP timeout. Mirror: config/neuract_dsn.conn_kwargs().'),
  ('neuract.keepalives_idle_s', '10', 'int', 'neuract',
   'TCP keepalive idle (s) before probing a live neuract connection — detects a mid-query half-open socket in seconds '
   'instead of the ~15-min kernel retransmission timeout. Mirror: config/neuract_dsn.conn_kwargs().'),
  ('neuract.keepalives_interval_s', '5', 'int', 'neuract',
   'TCP keepalive probe interval (s) for neuract connections. Mirror: config/neuract_dsn.conn_kwargs().'),
  ('neuract.keepalives_count', '3', 'int', 'neuract',
   'TCP keepalive probes before the neuract socket is declared dead. Mirror: config/neuract_dsn.conn_kwargs().'),
  ('neuract.statement_timeout_ms', '0', 'int', 'neuract',
   'Server-side statement_timeout (ms) for neuract reads. 0 = unlimited (current behavior). Set a generous value '
   '(e.g. 30000) ONLY after the ::timestamptz index work lands, so no legitimate slow read is blanked. '
   'Mirror: config/neuract_dsn.conn_kwargs().')
ON CONFLICT (key) DO NOTHING;
