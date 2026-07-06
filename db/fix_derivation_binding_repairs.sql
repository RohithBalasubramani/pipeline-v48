-- db/fix_derivation_binding_repairs.sql — derivation_binding row repairs (db-data hardening, 2026-07-03).
-- RUN AFTER db/seed_derivation_binding_full.sql (that seed closes the 25-key LIBRARY coverage gap; this file repairs
-- the pre-existing rows the seed does not touch). Idempotent: plain keyed UPDATE/DELETE, safe to re-run.
--
-- (1) pfAngleDeg base_columns listed the fn's OUTPUT ('phase_angle_deg') instead of its INPUT. The registry fn
--     power_quality.pf_angle_deg reads row['power_factor_total'] (descriptor columns=['power_factor_total']), so the
--     executor (_run_derived) was fetching the wrong frame column -> the fn ALWAYS honest-degraded. Align to the
--     registry descriptor (the code ground truth) so the recovery can actually fire.
UPDATE derivation_binding SET base_columns = 'power_factor_total'
 WHERE metric = 'pfAngleDeg' AND base_columns IS DISTINCT FROM 'power_factor_total';

-- (2) sectionContracts base was 'nameplate:contracted_kva' — asset_nameplate.contracted_kva is NULL on every row and
--     the fn (nameplate.section_contracts -> feeder_rated_kw) actually reads asset_nameplate.rated_kva. Align to the
--     registry descriptor.
UPDATE derivation_binding SET base_columns = 'nameplate:rated_kva'
 WHERE metric = 'sectionContracts' AND base_columns IS DISTINCT FROM 'nameplate:rated_kva';

-- (3) fidelity vocabulary normalization — legacy 'recovered'/'approx' values re-derived from the registry descriptors
--     (real_exact | real_approx), which is the vocabulary every newer row and the L2 prompt use. fidelity is
--     telemetry/display only (no code compares it to a literal — verified by grep before this change).
--     ratedKw stays honest at real_approx (kW = nameplate kVA x config nominal PF is a CONVENTION, not a measurement;
--     the registry descriptor over-claims real_exact — flagged for the code owner, do NOT copy that here).
UPDATE derivation_binding SET fidelity = 'real_exact'  WHERE metric = 'truePf'               AND fidelity IS DISTINCT FROM 'real_exact';
UPDATE derivation_binding SET fidelity = 'real_approx' WHERE metric = 'thdComplianceIeee519' AND fidelity IS DISTINCT FROM 'real_approx';
UPDATE derivation_binding SET fidelity = 'real_approx' WHERE metric = 'neutralCurrent'       AND fidelity IS DISTINCT FROM 'real_approx';
UPDATE derivation_binding SET fidelity = 'real_approx' WHERE metric = 'loadFactorPct'        AND fidelity IS DISTINCT FROM 'real_approx';
UPDATE derivation_binding SET fidelity = 'real_approx' WHERE metric = 'ratedKw'              AND fidelity IS DISTINCT FROM 'real_approx';

-- (4) DEAD rows deleted — registry.run() requires the metric to be a LIBRARY key BEFORE it consults the expression
--     row, and neither of these is a LIBRARY key, so they could NEVER execute (verified: both also had EMPTY
--     expression text, so even the proposed run()-reorder code fix would not activate them as stored).
--       currentUnbalancePct  (was: fn=currentUnbalancePct, base=current_r,current_y,current_b, fidelity=recovered)
--         -> redundant: the REAL raw column current_unbalance_pct exists in the neuract gic_* schema; bind that raw.
--       windowEnergyExportKwh (was: fn=windowEnergyKwh, base=active_energy_export_kwh, fidelity=real_exact)
--         -> import-energy windows are covered by windowEnergyKwh; if export-energy window slots are ever wanted,
--            resurrect as a LIBRARY key (or land the registry.run() expression-first reorder) PLUS an expression like
--            'round(max(end.active_energy_export_kwh - start.active_energy_export_kwh, 0), 1)' with scope='window'.
DELETE FROM derivation_binding WHERE metric IN ('currentUnbalancePct', 'windowEnergyExportKwh');

-- (5) activePowerLossKw / activePowerLossPct are TOPOLOGY-PAIR formulas: their base 'columns' hv_input_kw/lv_output_kw
--     are NOT gic_* columns — they are synthetic ctx keys injected only by ems_exec/derivations/topology.py loss mode.
--     Via the single-meter fill path they always honest-degrade (safe), but scope='row' was misleading. scope is
--     display/dispatch metadata (expressions.expression_row defaults unknown scopes to row-equivalent handling), so
--     'topology' is behavior-neutral today and makes the AI-visible catalog truthful when the prompt renders scope.
UPDATE derivation_binding SET scope = 'topology'
 WHERE metric IN ('activePowerLossKw', 'activePowerLossPct') AND scope IS DISTINCT FROM 'topology';
