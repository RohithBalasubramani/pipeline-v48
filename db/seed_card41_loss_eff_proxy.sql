-- db/seed_card41_loss_eff_proxy.sql — CARD 41 (Input vs Output Energy) single-feeder loss/eff PROXY (2026-07-07).
-- DEFECT: card 41's derived loss/efficiency proxy slots false-blanked (expectedLossKwh over active_energy_import_kwh,
-- lossPct over active_power_total_kw) as no_reading DESPITE ~24.7k live rows on gic_01_n3_ups_01_p1 this month. The
-- values ARE computable from the live active-energy / active-power columns, but blanked because:
--   · expectedLossKwh's fn needed ctx['target_efficiency_pct'] (never wired for a single feeder) → None.
--   · lossPct's fn (distribution_loss_pct) needed a topology aggregate (incomers/consumers) a lone feeder has none of.
-- FIX (in the derivation fns, ems_exec/derivations/{energy,topology}.py): an input-vs-output card over ONE meter has no
-- modelled upstream input meter, so both derive a BOUNDED design-band estimate over the meter's REAL windowed energy/
-- power throughput — expected_loss = window_energy × band/100, loss% = band — from the SAME editable knob the energy-
-- distribution accounting reads (energy_balance.expected_loss_band_pct, default 3.0 %). Honest proxy (real_approx), never
-- a fabrication: a genuinely-dark meter / empty window still blanks (the fns' _has_real_reading / window_energy guard).
--
-- This seed sets scope='window' on both metrics so _run_derived supplies start_row/end_row/series — the windowed energy
-- basis the fns integrate AND the window-scoped 'is there a real reading this window?' guard that keeps an EMPTY window
-- honest-blank (a row-scope call would see the LATEST logged row and mask an empty window). fidelity is real_approx (a
-- bounded design-band estimate, not a hardware counter). base_columns/fn untouched. The HV/LV-leg loss (activePowerLossKw/
-- Pct) is DELIBERATELY left as-is: it honest-blanks a UPS/feeder that lacks the two physical HV/LV legs (gic_* has no
-- hv_input_kw / lv_output_kw column) — a genuinely-absent input leg, correctly blank.
-- Idempotent (UPDATE by metric — safe to re-run).  Run:
--   psql -h 127.0.0.1 -p 5432 -U postgres -d cmd_catalog -f db/seed_card41_loss_eff_proxy.sql

UPDATE derivation_binding SET scope='window', fidelity='real_approx' WHERE metric='expectedLossKwh';
UPDATE derivation_binding SET scope='window', fidelity='real_approx' WHERE metric='lossPct';

-- efficiencyPct: the card 41 'Efficiency' slot = 100 − loss% (topology.efficiency_pct), the exact complement of lossPct
-- off the SAME basis. window-scope so the single-feeder window-reading guard fires; real_approx (a bounded band
-- complement); honest-blanks whenever lossPct blanks (a dark feeder never shows a fabricated 100 %). INSERT (the metric
-- is new — the registry advertises it; this row wires it so an efficiency-slot binding resolves).
INSERT INTO derivation_binding (metric, fn, base_columns, fidelity, scope) VALUES
 ('efficiencyPct', 'efficiencyPct', 'active_power_total_kw', 'real_approx', 'window')
ON CONFLICT (metric) DO UPDATE SET fn=EXCLUDED.fn, base_columns=EXCLUDED.base_columns,
  fidelity=EXCLUDED.fidelity, scope=EXCLUDED.scope;
