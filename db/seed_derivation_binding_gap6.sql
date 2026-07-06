-- db/seed_derivation_binding_gap6.sql — the 6 derivation_binding rows the F2 blank-without-reason audit exposed
-- (cards 57/72/81: base columns LIVE with real values, the fns exist in ems_exec/derivations/registry.py RESOLVERS
-- (registry.py:51-58), but fill._run_derived reads base_columns ONLY from THIS cmd_catalog table → binding=None →
-- honest-blank 'derivation_unbound'). Rows mirror the registry definitions byte-for-byte. Idempotent.
-- Run: psql (cmd_catalog DSN per config/databases.py) -f db/seed_derivation_binding_gap6.sql

INSERT INTO derivation_binding (metric, fn, base_columns, fidelity) VALUES
 ('progressActivePct',      'progressActivePct',      'active_energy_import_kwh,reactive_energy_import_kvarh', 'real_exact'),
 ('activeEnergyMvah',       'activeEnergyMvah',       'active_energy_import_kwh',                              'real_exact'),
 ('reactiveEnergyMvarh',    'reactiveEnergyMvarh',    'reactive_energy_import_kvarh',                          'real_exact'),
 ('cumulativeApparentMvah', 'cumulativeApparentMvah', 'active_energy_import_kwh,reactive_energy_import_kvarh', 'real_exact'),
 ('voltageStatutoryBand',   'voltageStatutoryBand',   'voltage_avg,kpi_voltage_deviation_pct',                 'real_exact'),
 ('voltageHistoryDomain',   'voltageHistoryDomain',   'voltage_avg,voltage_r_n,voltage_y_n,voltage_b_n',       'real_exact')
ON CONFLICT (metric) DO UPDATE SET fn = EXCLUDED.fn, base_columns = EXCLUDED.base_columns, fidelity = EXCLUDED.fidelity;
