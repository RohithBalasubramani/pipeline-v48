-- db/seed_derivation_binding_expressions.sql — FORMULAS INTO THE DB (2026-07-03).
-- The SIMPLE derivation formulas (pure arithmetic over row / start./end. window endpoints) move out of the RESOLVERS
-- python map into their derivation_binding row as an `expression` executed by the ONE generic safe evaluator
-- (ems_exec/derivations/evaluate.py). The DB row is authoritative: a non-null expression is THE formula. SERIES /
-- topology / stateful / config-wired fns stay python (their rows keep expression=NULL).
-- Each expression mirrors its python fn byte-for-byte in semantics (same rounding, same guards):
--   · `max(denom, 0)` reproduces a `denom > 0 else None` guard (a clamped-to-0 denominator divides by zero → None);
--   · a division by a zero column reproduces the `== 0 → None` guard (ZeroDivision → honest None);
--   · every missing input → None (honest-degrade), exactly like the python None-checks.
-- Existing rows only GAIN expression+scope (fn/base_columns/fidelity untouched); missing rows are INSERTed with the
-- registry descriptors' faithful base_columns/fidelity. Idempotent (ON CONFLICT re-derives).

-- ── window-scope (deltas over the start/end endpoint rows) ──────────────────────────────────────────────────────────
UPDATE derivation_binding SET scope='window',
  expression='round(max(end.active_energy_import_kwh - start.active_energy_import_kwh, 0), 1)'
  WHERE metric='windowEnergyKwh';

-- todaysEnergyTotalKwh: PARITY FAILED on the live cutover gate (2026-07-03, dg_1_mfm has NO reactive register —
-- the python fn treats a missing reactive leg as 0, the expression honest-degrades to None: py=0.0 vs expr=None).
-- REVERTED to the python fn (expression=NULL). base_columns still completed to the registry descriptor's pair so the
-- fetched ctx feeds the reactive leg wherever it exists.
UPDATE derivation_binding SET scope='window',
  base_columns='active_energy_import_kwh,reactive_energy_import_kvarh',
  expression=NULL
  WHERE metric='todaysEnergyTotalKwh';

UPDATE derivation_binding SET scope='window',
  expression='round(max(end.active_energy_import_kwh - start.active_energy_import_kwh, 0) / (max(end.active_energy_import_kwh - start.active_energy_import_kwh, 0) + max(end.reactive_energy_import_kvarh - start.reactive_energy_import_kvarh, 0)) * 100, 1)'
  WHERE metric='progressActivePct';

-- ── row-scope (latest-row arithmetic) ───────────────────────────────────────────────────────────────────────────────
UPDATE derivation_binding SET scope='row',
  expression='round(active_energy_import_kwh / 1000, 2)'
  WHERE metric='activeEnergyMvah';

UPDATE derivation_binding SET scope='row',
  expression='round(reactive_energy_import_kvarh / 1000, 2)'
  WHERE metric='reactiveEnergyMvarh';

-- cumulativeApparentMvah: PARITY FAILED on the live cutover gate (2026-07-03, dg_1_mfm has NO reactive register —
-- the python fn quadratures with reactive→0, the expression honest-degrades to None: py=27.73 vs expr=None).
-- REVERTED to the python fn (expression=NULL).
UPDATE derivation_binding SET scope='row',
  expression=NULL
  WHERE metric='cumulativeApparentMvah';

UPDATE derivation_binding SET scope='row',
  expression='round(min(1, abs(active_power_total_kw) / abs(apparent_power_total_kva)), 3)'
  WHERE metric='truePf';

UPDATE derivation_binding SET scope='row',
  expression='round(min(1, abs(power_factor_total)), 3)'
  WHERE metric='displacementPf';

-- rows the registry advertises but the table never had — INSERT with the registry-faithful descriptor + expression.
-- nominalVoltageLN: v / (1 + dev/100), denom>0 guard reproduced by max(denom, 0) (clamped → ÷0 → None).
INSERT INTO derivation_binding (metric, fn, base_columns, fidelity, expression, scope) VALUES
 ('nominalVoltageLN',  'nominalVoltageLN',  'voltage_avg,kpi_voltage_deviation_pct', 'real_exact',
  'voltage_avg / max(1 + kpi_voltage_deviation_pct / 100, 0)', 'row'),
 ('activePowerLossKw', 'activePowerLossKw', 'hv_input_kw,lv_output_kw',              'real_exact',
  'round(hv_input_kw - lv_output_kw, 2)', 'row'),
 ('activePowerLossPct','activePowerLossPct','hv_input_kw,lv_output_kw',              'real_exact',
  'round((hv_input_kw - lv_output_kw) / hv_input_kw * 100, 2)', 'row')
ON CONFLICT (metric) DO UPDATE SET expression=EXCLUDED.expression, scope=EXCLUDED.scope;
