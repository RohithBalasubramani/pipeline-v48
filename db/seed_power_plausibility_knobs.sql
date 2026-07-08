-- db/seed_power_plausibility_knobs.sql — DB-drive the POWER-derivation plausibility guards (ems_exec/derivations/power.py).
--
-- These three app_config `power.*` knobs move bare literals that STEERED behavior out of power.py into editable rows,
-- each with a code-default mirror (the fn falls back to the same number until a row exists — behavior identical). One
-- atomic concern: the power-derivation plausibility ceilings/tolerances. Generic — the fns key off the DECLARED metric's
-- bound fn, so every card of that class (any asset) is guarded, never a per-card / per-asset rule.
--
--   power.load_factor_ceiling_pct            (100.0)  load factor = mean/peak is DEFINITIONALLY ≤ this; above
--                            ceiling+tolerance is a sign/reducer artifact (a reversed-CT signed-series >100% load
--                            factor) → honest-blank. Read by power._lf_ceiling_pct (load_factor_pct guard).
--   power.load_factor_ceiling_tolerance_pct  (0.5)    float-rounding slack above the ceiling before blanking (100.3
--                            → 100.0). Read by power._lf_ceiling_tolerance_pct.
--   power.loading_plausible_max_pct          (200.0)  present-loading % (|kW| ÷ nameplate rated_kw × 100) above this
--                            signals a WRONG rating denominator (the 20000-vs-160 fabricated/name-parsed plate the live
--                            power exceeds many-fold), NOT a real overload → honest-blank. Read by
--                            power._loading_plausible_max_pct (kpi_kw_load_pct_of_rated guard) so EVERY card binding
--                            kpiKwLoadPctOfRated / loadPct / kpiLoadFactor on any asset is guarded at the derivation.
--                            (Mirrors the DERIVATION twin of the renderer-scoped kVA/kVA `story.load_pct_plausibility_
--                            ceiling` used by real_time_monitoring.py; same 200% default, distinct computation.)
--
-- NOTE — the energized-filter floor + min-energized count (power.load_factor_energized_fraction / power.load_factor_min_
-- energized) are now ALSO read by power.py (via _lf_energized_fraction / _lf_min_energized) so the native load-factor
-- mean and the executor.rescue path share the SAME row and can never drift. Those TWO rows are OWNED by
-- db/seed_rescue_overreach_guards.sql (section 'executor.rescue') — they already exist in the live DB and are NOT
-- re-asserted here (this seed owns only the 3 new derivation-plausibility knobs, so it never clobbers that file's rows).
-- Run: psql (cmd_catalog DSN per config/databases.py) -f db/seed_power_plausibility_knobs.sql   Idempotent (upsert).

INSERT INTO app_config (key, value, data_type, section, note) VALUES
 ('power.load_factor_ceiling_pct',           '100.0', 'number', 'derivations.power',
  'Load factor (mean/peak) definitional ceiling %; above ceiling+tolerance is a sign/reducer artifact -> honest-blank.'),
 ('power.load_factor_ceiling_tolerance_pct', '0.5',   'number', 'derivations.power',
  'Float-rounding slack % above the load-factor ceiling before blanking (100.3 -> 100.0).'),
 ('power.loading_plausible_max_pct',         '200.0', 'number', 'derivations.power',
  'Loading % (|kW|/rated_kw*100) above this = wrong rating denominator (fabricated plate), not a real overload -> honest-blank; guards every card at the derivation.')
ON CONFLICT (key) DO UPDATE
   SET value=EXCLUDED.value, data_type=EXCLUDED.data_type, section=EXCLUDED.section, note=EXCLUDED.note;
