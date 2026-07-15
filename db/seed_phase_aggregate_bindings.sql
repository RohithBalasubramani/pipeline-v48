-- db/seed_phase_aggregate_bindings.sql — F7: derivation_binding rows for the aggregate-from-phases recoveries.
--
-- These map each new registry fn (ems_exec/derivations/{current,voltage}.py, registered in registry._COMPAT) to the
-- per-phase base columns the executor must fetch into ctx.row. WITHOUT a row here, config.derivation_binding.binding()
-- returns None → _run_derived fetches base_columns=[] → an empty ctx.row → the fn honest-blanks (the live-null bug that
-- made card-38 "Average" stay blank even after canonical_slots swapped the bind). scope='row' (latest-row mean, no
-- window read). ON CONFLICT DO NOTHING (idempotent; never clobbers an operator edit).
--
-- Fired ONLY when fill.derive_aggregate_from_phases is on AND the meter's own aggregate register is all-NULL while the
-- phase components are present (canonical_slots._swap_aggregate_from_phases) — so this is inert until F7 is adopted.

INSERT INTO derivation_binding (metric, fn, base_columns, fidelity, scope) VALUES
 ('phaseCurrentAvg',          'phaseCurrentAvg',          'current_r,current_y,current_b',       'real_exact', 'row'),
 ('phaseCurrentUnbalancePct', 'phaseCurrentUnbalancePct', 'current_r,current_y,current_b',       'real_exact', 'row'),
 ('phaseVoltageAvg',          'phaseVoltageAvg',          'voltage_r_n,voltage_y_n,voltage_b_n', 'real_exact', 'row'),
 ('phaseVoltageUnbalancePct', 'phaseVoltageUnbalancePct', 'voltage_r_n,voltage_y_n,voltage_b_n', 'real_exact', 'row')
ON CONFLICT (metric) DO NOTHING;
