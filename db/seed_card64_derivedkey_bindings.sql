-- card 64 (pg12) stats.totalKwh/avgLoad emit as derived-KEY metrics (active-energy-kwh / load-factor-percent) with
-- fn=null; RB's bindings were keyed by the fn-name form (totalKwh/avgLoad) which the emit never uses. Bind the
-- derived-key forms to their canonical fn so a fn=null derived field resolves. DB-driven, idempotent upsert.
INSERT INTO derivation_binding (metric, fn, base_columns, fidelity, scope) VALUES
  ('active-energy-kwh', 'windowEnergyKwh', 'active_energy_import_kwh', 'real_exact', 'window'),
  ('load-factor-percent', 'loadFactorPct', 'active_power_total_kw', 'real_approx', 'window')
ON CONFLICT (metric) DO UPDATE SET fn=EXCLUDED.fn, base_columns=EXCLUDED.base_columns, fidelity=EXCLUDED.fidelity, scope=EXCLUDED.scope;
