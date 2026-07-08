-- db/seed_card72_energy_reliability_metrics.sql — CARD 72 (pg13 cert_13, asset dg_1_mfm) energy-cell FALSE-BLANK fix.
--
-- ROOT CAUSE: Layer 2 emitted the Energy & Reliability cells as derived fields keyed by the AI's OWN snake_case metric
-- names — {slot:'energyReliability.cells[0].value', kind:'derived', metric:'active_mwh', base_columns:['active_energy_
-- import_kwh'], fn:null}. With fn=null and NO derivation_binding row for `active_mwh`, executor._derived_key fell to the
-- metric, _run_derived built binding=None → base=[] → _registry.run('active_mwh', ctx)=None → fill logged
-- 'derivation_unbound: no derivation binding configured for active_mwh' and the Active cell blanked — even though
-- active_energy_import_kwh has 17k+ live rows (cumulative 27827.9 kWh = 27.83 MWh) on dg_1_mfm.
--
-- FIX (AI-first order — a DB binding row + reuse of the EXISTING energy fns, NO card hardcode): map each energy-family
-- metric ALIAS the AI emits to the registry fn that already computes that quantity from its real base register:
--   · active_mwh     → activeEnergyMvah       (mvah_active: latest active_energy_import_kwh / 1000 → MWh)      → 27.83
--   · reactive_mvarh → reactiveEnergyMvarh    (mvah_reactive: reactive_energy_import_kvarh / 1000 → MVArh)
--   · apparent_mvah  → cumulativeApparentMvah (√(active² + reactive²) quadrature)   [spec-name alias]
--   · apparentMvah   → cumulativeApparentMvah  ← the ACTUAL emitted name on card 72's Apparent slot (camelCase); the
--                       snake `apparent_mvah` above matches no live emit, so this camel row is what actually re-routes
--                       the Apparent cell off `derivation_unbound` (false-blank) onto the fn's own honest degrade.
-- WHY base = the cumulative ENERGY registers (not the AI's declared power columns): the fn LOOKS UP its own base
-- register, and the gap channel (executor/gaps.py) reports `column_absent` off the BINDING's base_columns — so pointing
-- the base at the real energy register makes a meter that lacks it read the HONEST `column_absent` (not a false
-- `derivation_unbound`). dg_1_mfm has ONLY active_energy_import_kwh per information_schema — NO reactive/apparent energy
-- register — so reactive_mvarh honest-blanks on reactive_energy_import_kvarh (column_absent) and apparent_mvah blanks
-- because its reactive leg is absent (cumulative_apparent_mvah REQUIRES both legs — see ems_exec/derivations/energy.py
-- — so it never ships the active MWh magnitude relabeled 'Apparent'). A meter that DOES log those registers fills for
-- free. ~27.8 MWh Active = the latest active_energy_import_kwh (27827.9 kWh) / 1000, the SAME cumulative-snapshot
-- semantics as the card's default cell values (activeMwh) — NOT a windowed consumption delta (the 7-day window delta is
-- only ~0.1 MWh). scope='row': latest-row register.
--
-- DEFINITIVE ENERGY-REGISTER RULE [2026-07-07, fab-by-substitution fix]: reactiveEnergyMvarh (mvah_reactive) and
-- cumulativeApparentMvah fill ONLY from a REAL reactive/apparent ENERGY register. A transient earlier fix integrated the
-- live reactive-POWER series (∫|reactive_power|dt) to synthesize reactive kVArh when the register was absent — the
-- adversarial audit ruled that FABRICATION-BY-SUBSTITUTION (you cannot report reactive/apparent ENERGY for a meter with
-- no reactive/apparent energy REGISTER). That ∫reactive-power recovery is now REMOVED (energy.reactive_energy_from_power_
-- kvarh disabled), so dg_1_mfm's reactive_mvarh AND apparent_mvah honest-blank (None) — never 0.02 MVArh / 27.83 MVAh
-- synthesized from power. Active energy still fills real. These binding rows are UNCHANGED by that fix (same fns, same
-- real-energy-register base_columns); the honesty lives entirely in the reused registry fns.
--
-- Idempotent (ON CONFLICT re-derives). No pipeline code names these fns — the binding rows re-route every card that emits
-- these metric aliases, no code change beyond the reused registry fns + polarity-family rows in registry._QUANTITY.

INSERT INTO derivation_binding (metric, fn, base_columns, fidelity, scope) VALUES
 ('active_mwh',     'activeEnergyMvah',       'active_energy_import_kwh',                              'real_exact', 'row'),
 ('reactive_mvarh', 'reactiveEnergyMvarh',    'reactive_energy_import_kvarh',                          'real_exact', 'row'),
 ('apparent_mvah',  'cumulativeApparentMvah', 'active_energy_import_kwh,reactive_energy_import_kvarh',  'real_exact', 'row'),
 ('apparentMvah',   'cumulativeApparentMvah', 'active_energy_import_kwh,reactive_energy_import_kvarh',  'real_exact', 'row')
ON CONFLICT (metric) DO UPDATE
   SET fn=EXCLUDED.fn, base_columns=EXCLUDED.base_columns, fidelity=EXCLUDED.fidelity, scope=EXCLUDED.scope;
