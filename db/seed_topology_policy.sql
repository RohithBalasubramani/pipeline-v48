-- db/seed_topology_policy.sql — editable POLICY rows for config/topology_policy.py (the ported derivation-math bands).
-- Backs the input↔output loss-plausibility GATE + the trend-status deadband ported from CMD_V2 backend2
-- (panels/consumers/feeder_energypower.py :247-249 and core/derive.py trend_status band=0.05). Read by
-- derivations/topology.py, energy.py, power.py, trend.py via topology_policy.loss_plausible_band_pct() /
-- trend_deadband(). Idempotent (ON CONFLICT). NO magic number lives in the derivation files. [#4/#12 derivation-math]
-- Run:  psql -h localhost -p 5432 -d cmd_catalog -f db/seed_topology_policy.sql

-- ── input↔output loss-plausibility band ── loss trusted ONLY when loss_pct ∈ [min,max]%, else fall back to output_only
-- (a bigger figure means the paired 'input' meter is not truly upstream — no modelled HV meter). P1 #11 gate.
INSERT INTO data_quality_policy (key, num_value, txt_value, note) VALUES
 ('topology.loss_plausible_min_pct', 0.0,  NULL, 'lower bound of the trusted input->output loss band; below -> output_only [feeder_energypower.py:247]'),
 ('topology.loss_plausible_max_pct', 10.0, NULL, 'upper bound of the trusted loss band; above -> paired meter not upstream -> output_only [feeder_energypower.py:247]')
ON CONFLICT (key) DO UPDATE SET num_value = EXCLUDED.num_value, txt_value = EXCLUDED.txt_value, note = EXCLUDED.note;

-- ── trend-status deadband ── |Δ| within this fraction of |baseline| reads 'stable' (no spurious rising/falling arrows).
INSERT INTO data_quality_policy (key, num_value, txt_value, note) VALUES
 ('topology.trend_deadband', 0.05, NULL, '+/- fraction deadband for trend_status rising/stable/falling [core/derive.py:57]')
ON CONFLICT (key) DO UPDATE SET num_value = EXCLUDED.num_value, txt_value = EXCLUDED.txt_value, note = EXCLUDED.note;
