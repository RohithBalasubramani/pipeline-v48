-- db/seed_derivation_binding_fnless_metrics.sql
-- Two residual FALSE-BLANK fixes, both routed at the DB-binding layer (no per-card code):
--
-- ════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
-- DEFECT 1 (pg02 energy-distribution, card 64 fuel/energy stats — metrics totalKwh / avgLoad)
-- ════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
-- ROOT CAUSE: the final Layer-2 emit shipped these two kind=derived LIVE-DATA KPIs with fn=null (the AI named the
-- QUANTITY via `metric` but omitted the recovery fn). With NO derivation_binding row for `totalKwh` / `avgLoad`,
-- executor._derived_key fell through to the metric name, _run_derived built binding=None, and _registry.run('totalKwh')
-- / run('avgLoad') hit LIBRARY.get(...) = None → fill logged 'derivation_unbound' and BOTH KPIs false-blanked, despite
-- ~91k live non-null rows on the asset (active_energy_import_kwh moves 100.2 kWh; active_power_total_kw is fully logged).
--
-- FIX (metric-wins, the SAME mechanism the card-72 active_mwh/reactive_mvarh aliases already use): seed the binding row
-- that maps each metric → the registry fn that already computes that quantity from its real base register. A fn=null
-- derived field whose `metric` HAS a binding now resolves DETERMINISTICALLY from binding.fn — the AI is NOT required to
-- supply fn when the binding names it (executor._derived_key: metric-with-a-binding wins over a null fn).
--   · totalKwh → todaysEnergyTotalKwh  (active + reactive windowed deltas, reversed-CT aware; dg_1_mfm full-range = 100.2)
--   · avgLoad  → loadFactorPct         (energized-only mean/peak utilisation over active_power_total_kw; dg_1_mfm = 91.1%)
-- scope='window': both are windowed statistics (the delta / the mean-peak load factor need the card's window + series).
-- A meter that lacks the base register honest-blanks via gaps.py column_absent off THESE base_columns (no fabrication).
--
-- ════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
-- DEFECT 2 (pg13 dg_1_mfm operations-runtime, card 72 Energy & Reliability — reactiveMvarh / apparentMvah)
-- ════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
-- FINDING (information_schema on neuract.dg_1_mfm): there is NO cumulative reactive-ENERGY register
-- (reactive_energy_import_kvarh is ABSENT) and NO apparent-ENERGY register — only a LIVE reactive-POWER column
-- reactive_power_total_kvar. Active energy (active_energy_import_kwh) IS present.
--
-- DEFINITIVE ENERGY-REGISTER RULE [2026-07-07, fab-by-substitution fix]: reactive/apparent ENERGY fills ONLY from a real
-- reactive/apparent ENERGY register. A transient earlier fix integrated the reactive-POWER series (∫|Q|dt) to synthesize
-- reactive kVArh when the register was absent and flipped reactive_mvarh/apparent_mvah/apparentMvah/active_mwh to
-- scope='window' so the executor would supply that series. The adversarial audit ruled that synthesis
-- FABRICATION-BY-SUBSTITUTION (reporting reactive/apparent ENERGY for a meter with no such register). The ∫reactive-power
-- recovery is now REMOVED (energy.reactive_energy_from_power_kvarh disabled; energy.mvah_reactive reads ONLY its real
-- register), so those fns are purely ROW-scoped again. This DB side REVERTS reactive_mvarh/apparent_mvah/apparentMvah/
-- active_mwh to scope='row' (they read only the latest register row; no series is needed and none should be fetched to
-- feed a now-banned synthesis). Result on dg_1_mfm: active_mwh FILLS 27.83; reactive_mvarh and apparent_mvah HONEST-BLANK
-- (column_absent on reactive_energy_import_kvarh) — never 0.02 MVArh / 27.83 MVAh synthesized from power. A meter that
-- DOES carry a real reactive-energy register still fills both legs for free.
--
-- Idempotent (ON CONFLICT re-derives). DB-driven — these rows re-route every card that emits these metrics, no per-card code.

INSERT INTO derivation_binding (metric, fn, base_columns, fidelity, scope) VALUES
 -- DEFECT 1 — fn=null derived KPIs resolve deterministically from the metric's binding
 ('totalKwh', 'todaysEnergyTotalKwh',
    'active_energy_import_kwh,active_energy_export_kwh,reactive_energy_import_kvarh,reactive_energy_export_kvarh',
    'real_exact',  'window'),
 ('avgLoad',  'loadFactorPct', 'active_power_total_kw', 'real_approx', 'window')
ON CONFLICT (metric) DO UPDATE
   SET fn=EXCLUDED.fn, base_columns=EXCLUDED.base_columns, fidelity=EXCLUDED.fidelity, scope=EXCLUDED.scope;

-- DEFECT 2 [REVERTED 2026-07-07] — reactive/apparent/active MVAh are ROW-scoped: their fns read only the latest real
-- energy register. No series is fetched (the ∫reactive-power→reactive-ENERGY synthesis is BANNED as fab-by-substitution),
-- so reactive/apparent honest-blank when their register is absent (dg_1_mfm) and fill real where it exists.
UPDATE derivation_binding SET scope='row'
 WHERE metric IN ('reactive_mvarh', 'apparent_mvah', 'apparentMvah', 'active_mwh');
