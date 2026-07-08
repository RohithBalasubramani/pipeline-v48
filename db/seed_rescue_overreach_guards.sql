-- db/seed_rescue_overreach_guards.sql — the POST-FILL RESCUE over-reach-guard knobs (BUCKET 2). Every threshold / vocab
-- token / valve the ems_exec.executor post-fill rescues read is a cmd_catalog.app_config ROW here WITH a code-default
-- mirror in the owning python file, so behavior is identical until a row is edited (DB-DRIVEN, never a bare hardcode).
--
-- Owned by (fence): ems_exec/executor/{measurable_resolve,load_factor_fill,scalar_tile_fill,scalar_mean_fill,fill}.py
--
--   measurable.nonmeasured_source_roles  — SOURCE-ROLE WALL vocabulary (DEFECT 56, card 56 'Average Bypass Voltage'):
--                        a voltage/current LABEL qualified by one of these DEDICATED-SENSING rail roles names a
--                        physically distinct sensing point this OUTPUT-metering MFM does NOT have a column for — so
--                        measurable_resolve refuses the meter's own voltage_avg/current_avg for it and the leaf
--                        honest-blanks. 'output' is never in the set (the meter's own measured terminal → 'Output
--                        Voltage' KEEPS). DEDICATED rails ONLY (bypass/utility/grid/source/incoming/line-side).
--   measurable.nondedicated_source_roles — the NON-DEDICATED rail roles [DEFECT c59 inputVoltageV]: input / line /
--                        mains ARE the meter's OWN plain reading (voltage_avg/current_avg IS the input/line reading),
--                        so an input*/line*/mains* leaf carrying NO dedicated rail role fills from the bare column and
--                        must NOT be walled. 'input'/'mains' were previously (wrongly) in nonmeasured_source_roles,
--                        silently false-blanking every input* leaf (c59 inputVoltageV). Mirrors the exact
--                        `dedicated`:false roles the honest-blank gate's source_role_mismatch clears.
--   measurable.measured_source_roles     — the SELF/MEASURED roles the meter reads at its OWN terminals ('output'):
--                        a voltage/current label naming one is NEVER walled ('Output Voltage' → voltage_avg). Replaces
--                        the last hardcoded label SET in the source-role wall (no card-id, no baked set — DB vocab now).
--   measurable.quantity_prefix           — the QUANTITY token → neuract column-name PREFIX map (voltage/current + the
--                        v/i/amps abbreviations); physics/dataset semantics the resolver composes `<prefix>_<stat>` from.
--   measurable.stat_suffix               — the STATISTIC token → column-name SUFFIX map (avg/max/min + average/peak/…).
--   measurable.derived_quantity_classes  — the DERIVED / DISTORTION quantity classes (from quantity_class.name_class) a
--                        raw voltage/current column must NOT bind (a %/index, not amps/volts): '-' prefix = SUFFIX
--                        pattern ('-thd' → current-thd/voltage-thd, '-harmonic'), otherwise an EXACT class (crest-factor
--                        /flicker/k-factor). The 265-amps-as-peak-THD fab wall (DEFECT B, card 04 iThdPk).
--   measurable.display_unit_tokens       — display-unit tokens dropped from a leaf key before matching a quantity
--                        (kw/kwh/hz/pct/…) so 'activePowerAvgKw' matches on active+power, not the kW unit.
--   measurable.sibling_stopwords         — non-content tokens (articles/stat words/units) stripped before comparing a
--                        leaf's QUANTITY identity to a sibling field's (the card-40 scalar-mean sibling match).
--   measurable.unit_keys                 — object KEYS that hold a leaf's display UNIT ({unit|units|suffix}); the SHARED
--                        vocab the label-keyed tile rescue + the load-factor rescue both read (ONE home, never drift).
--   measurable.scalar_quantity_words     — generic MAGNITUDE words a reduced-scalar leaf may name that are NOT in the
--                        voltage/current prefix map (power/energy/demand/load/frequency) — the scalar-mean rescue's
--                        'is this a measurable reduced scalar?' predicate keys on these plus the prefix map.
--
--   power.load_factor_energized_fraction — fraction-of-peak below which a raw sample is STANDSTILL (excluded from the
--                        native load-factor mean). The SAME relative floor power.load_factor_pct uses so the rescue and
--                        the derivation never diverge. (load_factor_fill native-resolution recompute, cards 70/71.)
--   power.load_factor_min_energized     — minimum genuinely-energized RAW samples for a meaningful mean/peak; guards a
--                        lone raw blip from a degenerate 100 % (an idle window keeps its honest blank).
--
--   loadfactor.percent_units            — UNIT tokens that ARE percent-like (the ONLY units a load-factor % may fill
--                        into). DEFECT 71: a load-% written under an HOURS/COUNT/ENERGY unit is a mislabel — the target
--                        run-hours slot honest-blanks.
--   loadfactor.nonpercent_unit_tokens   — UNIT tokens that decisively BLOCK a load-% fill (h/hr/hours/count/kwh/…).
--   loadfactor.nonpercent_name_tokens   — id/label NAME tokens that block when the target carries no unit sibling
--                        ('total-run-hours' id / 'Run hours' / 'Transfers' → decisively non-load-%).
--   loadfactor.registry_quantity        — the derivation-registry quantity a single-power-column load-factor-% rescue
--                        targets ('load-factor-percent'); a %-of-RATED (nameplate-denominator) quantity is excluded.
--
--   fill.window_register_delta          — valve ('on'|'off') for the windowed cumulative-energy-register delta rule.
--
-- Apply:  psql "$CMD_CATALOG_DSN" -f db/seed_rescue_overreach_guards.sql   (idempotent — re-run safe)

INSERT INTO app_config (key, value, data_type, section, note) VALUES
  ('measurable.nonmeasured_source_roles',
   '["bypass","utility","grid","source","incoming","line side","line-side","lineside"]',
   'json', 'executor.rescue',
   'DEFECT 56/c59: source-role wall DEDICATED-rail block set (code-default mirror of measurable_resolve). Only rails this OUTPUT-meter has NO column for honest-blank; input/line/mains removed (they ARE the meter own reading — c59 inputVoltageV false-blank fix) and live in measurable.nondedicated_source_roles.'),
  ('measurable.nondedicated_source_roles',
   '["input","line","mains"]',
   'json', 'executor.rescue',
   'DEFECT c59: NON-DEDICATED source roles — the meter own plain reading (voltage_avg/current_avg IS the input/line reading). An input*/line*/mains* leaf with no dedicated rail role fills from the bare column and is NOT walled. Mirrors the dedicated:false roles source_role_mismatch clears.'),
  ('measurable.measured_source_roles',
   '["output"]',
   'json', 'executor.rescue',
   'The SELF/MEASURED roles the meter reads at its OWN terminals (output). A voltage/current label naming one is NEVER walled (Output Voltage -> voltage_avg). Replaces the last hardcoded label set in the source-role wall (code-default mirror of measurable_resolve._measured_roles).'),

  ('measurable.quantity_prefix',
   '{"voltage":"voltage","volt":"voltage","v":"voltage","current":"current","amps":"current","amp":"current","amperes":"current","ampere":"current","i":"current"}',
   'json', 'executor.rescue',
   'QUANTITY token -> neuract column-name PREFIX map (physics/dataset semantics). measurable_resolve composes <prefix>_<stat>. Code-default mirror of _QUANTITY_DEFAULT.'),
  ('measurable.stat_suffix',
   '{"avg":"avg","average":"avg","mean":"avg","max":"max","maximum":"max","peak":"max","min":"min","minimum":"min"}',
   'json', 'executor.rescue',
   'STATISTIC token -> column-name SUFFIX map (per-sample reduction the meter already stores). Code-default mirror of _STAT_DEFAULT.'),
  ('measurable.derived_quantity_classes',
   '["-thd","-harmonic","crest-factor","flicker","k-factor"]',
   'json', 'executor.rescue',
   'DEFECT B (card 04 iThdPk): DERIVED/DISTORTION quantity classes a raw voltage/current column must NOT bind. Entry starting "-" = SUFFIX pattern (-thd -> current-thd/voltage-thd), else EXACT class. Code-default mirror of measurable_resolve._is_derived_quantity_key.'),
  ('measurable.display_unit_tokens',
   '["kw","kwh","kva","kvar","kvarh","kvah","hz","pct","percent","deg"]',
   'json', 'executor.rescue',
   'Display-unit tokens dropped from a leaf key before matching a quantity (activePowerAvgKw matches active+power, not the kW unit). Code-default mirror of _UNIT_TOKENS_DEFAULT.'),
  ('measurable.sibling_stopwords',
   '["the","of","and","per","avg","average","mean","max","min","peak","total","kw","kwh","kva","kvar","kvarh","kvah","hz","pct","percent"]',
   'json', 'executor.rescue',
   'Non-content tokens (articles/stat words/units) stripped before comparing a leaf QUANTITY identity to a sibling field (card-40 scalar-mean sibling match). Code-default mirror of _STOPWORDS_DEFAULT.'),
  ('measurable.unit_keys',
   '["unit","units","suffix"]',
   'json', 'executor.rescue',
   'Object KEYS that hold a leaf display UNIT. SHARED by the label-keyed tile rescue + the load-factor rescue (ONE home so the two never drift). Code-default mirror of measurable_resolve._UNIT_KEYS_DEFAULT.'),
  ('measurable.scalar_quantity_words',
   '["power","energy","demand","load","frequency"]',
   'json', 'executor.rescue',
   'Generic MAGNITUDE words a reduced-scalar leaf may name that are NOT in the voltage/current prefix map. The scalar-mean rescue keys its measurable-reduced-scalar predicate on these plus the prefix map. Code-default mirror of measurable_resolve._SCALAR_QUANTITY_WORDS_DEFAULT.'),

  ('power.load_factor_energized_fraction', '0.02', 'number', 'executor.rescue',
   'DEFECT 70/71: fraction-of-peak below which a raw sample is standstill in the native load-factor mean (== power.load_factor_pct floor).'),
  ('power.load_factor_min_energized', '3', 'int', 'executor.rescue',
   'DEFECT 70/71: minimum energized RAW samples for a meaningful native load factor (guards a degenerate lone-blip 100 %).'),

  ('loadfactor.percent_units',
   '["%","pct","percent","percentage","","-","—"]',
   'json', 'executor.rescue',
   'DEFECT 71: unit tokens that are percent-like — the ONLY units a load-factor % may fill into.'),
  ('loadfactor.nonpercent_unit_tokens',
   '["h","hr","hrs","hour","hours","count","counts","n","nos","kw","kwh","kva","kvar","kvarh","kwhr","mwh","mw","wh","v","a","hz","kwh/h","min","mins","minute","s","sec","day","days"]',
   'json', 'executor.rescue',
   'DEFECT 71: unit tokens that decisively BLOCK a load-% fill (hours/count/energy). A load-% under unit=h honest-blanks.'),
  ('loadfactor.nonpercent_name_tokens',
   '["hours","hour","hrs","hr","runtime","runhours","count","counts","transfers","kwh","energy","starts","cycles"]',
   'json', 'executor.rescue',
   'DEFECT 71: id/label NAME tokens that block a load-% fill when the target carries no unit sibling (total-run-hours/Transfers).'),
  ('loadfactor.registry_quantity', 'load-factor-percent', 'text', 'executor.rescue',
   'DEFECT 70/71: the derivation-registry quantity a single-power-column load-factor-% rescue targets. A %-of-RATED (nameplate-denominator) quantity is excluded (a different, rating-dependent quantity the rescue never fabricates). Code-default mirror of load_factor_fill._LOAD_FACTOR_QUANTITY_DEFAULT.'),

  ('fill.window_register_delta', 'on', 'text', 'executor.rescue',
   'Valve for the windowed cumulative-energy-register delta rule (on|off).')
ON CONFLICT (key) DO UPDATE
  SET value = EXCLUDED.value,
      data_type = EXCLUDED.data_type,
      section = EXCLUDED.section,
      note = EXCLUDED.note,
      updated_at = now();
