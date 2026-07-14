-- db/seed_pq_thd_deadband.sql -- the I-THD trend deadband knob (latency-audit T1-3).
-- Bounds the 'Flat' verdict of ems_exec/derivations/power_quality.thd_trend_label: a recent-vs-prior mean swing
-- within +/- this many percent reads 'Flat'; beyond it reads 'Rising'/'Falling'. Was the hardcoded +/-2 literal;
-- now a VALUE knob so retuning the trend sensitivity is a DB row edit, no code change. Code-default mirror 2.0
-- (power_quality._thd_trend_deadband_pct). Idempotent.
-- Run: psql (cmd_catalog DSN per config/databases.py) -f db/seed_pq_thd_deadband.sql
INSERT INTO app_config (key, value, data_type, section, note) VALUES
  ('pq.thd_trend_deadband_pct', '2.0', 'number', 'derivations.pq',
   'The +/-% deadband inside which thd_trend_label calls the I-THD window Flat (recent-half mean vs prior-half mean, '
   'as % of the prior mean). Beyond +band = Rising, below -band = Falling. Mirror: '
   'ems_exec/derivations/power_quality.py _thd_trend_deadband_pct code default 2.0.')
ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value, note=EXCLUDED.note;
