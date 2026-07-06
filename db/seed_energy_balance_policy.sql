-- db/seed_energy_balance_policy.sql — the feeder fan-out energy-balance / Sankey-conservation knobs as editable
-- data_quality_policy rows under the `energy_balance.` namespace. Read ONLY by config/energy_balance_policy.py
-- (num()/txt()); NO logic file (energy_distribution/pcc_panel.py) hardcodes the over-metering threshold, the
-- unmetered-surface threshold, the expected-loss band, the assumed PF, or the reactive-energy column.
-- Idempotent (ON CONFLICT — safe to re-run). Ported from backend2 panels/consumers/energydist.py (_build :224-347,
-- _cap_util :71-78).  Run:
--   psql -h localhost -p 5432 -d cmd_catalog -f db/seed_energy_balance_policy.sql
-- [#5 feeder fan-out energy-balance + Sankey conservation]

INSERT INTO data_quality_policy (key, num_value, txt_value, note) VALUES
 ('energy_balance.over_metered_frac',       0.02, NULL, 'Σoutgoing over Σincoming by > this fraction of measured → over-metering ''Review'' badge (energydist.py:241)'),
 ('energy_balance.unmetered_surface_frac',  0.01, NULL, 'surface unmetered remainder as own consumer + balancing Sankey node only when > this fraction of measured (energydist.py:284/311)'),
 ('energy_balance.expected_loss_band_pct',  3.0,  NULL, 'loss above this % of measured reads above-band → ''review'' badge (energydist.py EXPECTED_LOSS_BAND_PCT)'),
 ('energy_balance.assumed_pf',              0.9,  NULL, 'assumed PF turning nameplate kVA → kW for capacity (energydist.py _PF)'),
 ('energy_balance.reactive_energy_col',     NULL, 'reactive_energy_import_kvarh', 'cumulative reactive-energy counter; apparent energy derived hypot(kWh,kVArh) over the SAME window (energydist.py:207/212)')
ON CONFLICT (key) DO UPDATE SET num_value = EXCLUDED.num_value, txt_value = EXCLUDED.txt_value, note = EXCLUDED.note;
