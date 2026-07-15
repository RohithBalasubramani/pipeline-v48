-- db/seed_derivation_alias.sql — derivation-key ALIASES (audit 2026-07-14, 14 F1: emit invents free-form
-- derivation keys; ~56% of derivation_unbound named a computable quantity under an invented spelling).
-- config/derivation_binding.binding() resolution: exact > normalized fold (case/-/_/pct folded, MAGNITUDE unit
-- tokens kept — folding kvarh onto an MVARh fn would be a silent ×1000 mismatch; unique-hit only) > THIS table.
-- Alias keys are stored in NORMALIZED form: lowercase, alnum-only, trailing pct/percent stripped.
-- RULE: an alias NEVER crosses quantity/polarity/unit-magnitude — seed only pairs whose target computes exactly
-- what the alias names (test_derivation_alias.py property-checks polarity against the registry _QUANTITY table).
-- Apply: psql -h localhost -p 5432 -U postgres -d cmd_catalog -f db/seed_derivation_alias.sql

CREATE TABLE IF NOT EXISTS derivation_alias (
  alias  text PRIMARY KEY,        -- NORMALIZED form (see header)
  metric text NOT NULL,           -- canonical derivation_binding.metric key
  note   text
);

INSERT INTO derivation_alias (alias, metric, note) VALUES
  -- audit-confirmed invented spellings (14_blank_domain_gap.md masked share); unit-suffixed variants first
  ('totalenergykwh',      'totalKwh',               'totalEnergyKwh / Total_Energy_KWH — active cumulative energy'),
  ('totalenergy',         'totalKwh',               'unitless total-energy — active by site convention'),
  ('activeenergykwh',     'active-energy-kwh',      'activeEnergyKwh / active_energy_kwh — disambiguates the activeenergy fold (kwh vs Mvah rows)'),
  ('apparentenergymvah',  'apparentMvah',           'apparentEnergyMvah / apparent_energy_mvah'),
  ('apparentenergy',      'apparentMvah',           'unitless apparent-energy'),
  ('reactiveenergymvarh', 'reactiveEnergyMvarh',    'reactive_energy_mvarh spelling variants'),
  ('reactiveenergy',      'reactiveEnergyMvarh',    'unitless reactive-energy'),
  ('energylosskwh',       'expectedLossKwh',        'energy-loss-kwh'),
  ('energyloss',          'expectedLossKwh',        'unitless energy-loss'),
  ('distributionloss',    'lossPct',                'distribution-loss-percent — loss as % of input'),
  ('losspctofinput',      'lossPct',                'lossPctOfInput (mid-string pct not stripped by the fold)'),
  ('loadfactor',          'loadFactorPct',          'load_factor / loadFactor — the ambiguous fold (loadFactorPct vs load-factor-percent rows) pinned'),
  ('powerfactor',         'truePf',                 'powerFactor / power_factor — the true (displacement+distortion) PF'),
  ('worstpeak',           'worstPeakKw',            'worst_peak — active demand peak')
ON CONFLICT (alias) DO UPDATE SET metric = EXCLUDED.metric, note = EXCLUDED.note;
