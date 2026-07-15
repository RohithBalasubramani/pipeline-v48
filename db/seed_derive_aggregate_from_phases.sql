-- db/seed_derive_aggregate_from_phases.sql — F7 flag. DEFAULT OFF (byte-identical).
--
-- fill.derive_aggregate_from_phases — ems_exec/executor/canonical_slots._swap_aggregate_from_phases (run from inject()
-- at fill time). ON: when a raw field is bound to an aggregate column (current_avg / voltage_avg / current_unbalance_pct
-- / voltage_unbalance_pct) that is ALL-NULL on the resolved meter BUT the per-phase component columns are present, the
-- bind is swapped to the phase-derivation (phaseCurrentAvg / phaseVoltageAvg = arithmetic mean; *UnbalancePct =
-- (max-min)/mean*100). This is REAL data (mean/unbalance of the measured phases), not fabrication — an HT CT-wired meter
-- logs the phase magnitudes but never materialized the avg/unbalance register. Fact-gated: fires ONLY when the aggregate
-- is null AND every component is non-null, so a genuinely dataless leaf stays honest-blank. OFF (this default) = the
-- executor fills the emit's bind verbatim (a null column → honest-blank, byte-identical).
--
-- REQUIRES the derivation_binding rows in db/seed_phase_aggregate_bindings.sql (they give _run_derived the base columns
-- to fetch into ctx.row — without them the swapped fn sees an empty row and blanks).
--
-- ON CONFLICT DO NOTHING (idempotent; never flips an operator 'on' back to 'off').

INSERT INTO app_config (key, value, data_type, section, note) VALUES
 ('fill.derive_aggregate_from_phases', 'off', 'text', 'fill',
  'F7: swap a raw field bound to an all-NULL aggregate column (current_avg/voltage_avg/*_unbalance_pct) to the phase-mean/unbalance derivation when the per-phase components are present; real data, fact-gated, honest-blank when components also absent; off=byte-identical. ems_exec/executor/canonical_slots._swap_aggregate_from_phases + db/seed_phase_aggregate_bindings.sql')
ON CONFLICT (key) DO NOTHING;
