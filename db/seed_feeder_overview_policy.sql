-- db/seed_feeder_overview_policy.sql — the feeder-overview scalar knobs that are NOT status-band edges.
-- The single-feeder Overview page draws its card STATUS bands from db/seed_band_policy.sql (`band.overview.*`); the two
-- knobs below are the extra scalars backend2 feeder_overview.py hardcoded and bands.py has no home for:
--   • the Power-Factor tri-state floors (Good ≥ 0.95, Fair ≥ 0.90, else Poor)   — backend2 feeder_overview._build
--   • the voltage statutory |deviation| limit % shown on the voltage card       — backend2 feeder_overview._voltage_card
-- Read ONLY by config/feeder_overview.py (num()). The code default in config/feeder_overview._DEFAULTS is the DB-down
-- fallback; this row lets you retune with no code change. Idempotent (ON CONFLICT — safe to re-run). Run:
--   psql -h localhost -p 5432 -d cmd_catalog -f db/seed_feeder_overview_policy.sql
-- [BATCH D #13 — feeder overview producer]

INSERT INTO data_quality_policy (key, num_value, txt_value, note) VALUES
 ('feeder_overview.pf_good_min',           0.95, NULL, 'feeder-overview PF card: PF ≥ this → Good (else Fair/Poor)'),
 ('feeder_overview.pf_fair_min',           0.90, NULL, 'feeder-overview PF card: PF ≥ this → Fair, else Poor'),
 ('feeder_overview.voltage_statutory_pct', 5.0,  NULL, 'feeder-overview voltage card: statutory |deviation| limit %'),
 ('feeder_overview.meter_gap_review_kw',   50.0, NULL, 'SLD meter_gap_status: |Σin−Σout| kW above this → Review')
ON CONFLICT (key) DO UPDATE SET num_value = EXCLUDED.num_value, txt_value = EXCLUDED.txt_value, note = EXCLUDED.note;
