-- ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
--  V48 RENDER-GUARANTEE SEED  — sane starting rows for the policy/mapping config tables (cmd_catalog, all EDITABLE).
--  Run AFTER render_guarantee_schema.sql:  psql -h localhost -p 5432 -d cmd_catalog -f db/render_guarantee_seed.sql
--  Idempotent (upsert / delete+insert). asset_nameplate is seeded separately by manage.py seed_nameplates.
--  Every value here is a starting policy — edit the ROW, never a magic number in logic code.
-- ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════

-- ── data_quality_policy ── the numeric/threshold knobs the meaningful-data / register / denorm gates read ──────────
INSERT INTO data_quality_policy (key, num_value, txt_value, note) VALUES
 ('value_min',                3,      NULL, 'min non-null value_counts for has_data (layer1b has_data VALUE_MIN)'),
 ('denorm_epsilon',           1e-30,  NULL, '|x| < eps → denormalized-float garbage (e.g. -4.6e-44) → treat as 0/no-reading [DS-06]'),
 ('reversed_ct_import_max',   1.0,    NULL, 'active_energy_import_kwh <= this AND export>0 → reversed-CT: use export register [DS-05]'),
 ('meaningful_min_power_kw',  0.0,    NULL, 'abs(active_power) must EXCEED this to count as meaningful (0.0 = any nonzero) [DS-01/VC-09]'),
 ('meaningful_min_energy_delta_kwh', 0.0, NULL, 'window energy delta must exceed this to be meaningful [DS-01]'),
 ('feeder_coverage_partial_pct', 50.0, NULL, 'aggregate reporting < this %% of feeders → downgrade to honest-partial [DS-08/VC-04]'),
 ('negative_power_convention', NULL, 'abs_with_flag', 'genuine negative power (UPS/incomer): abs magnitude + reverse-flow flag, not clamp [DS-06/VC-03]'),
 ('pf_sign_policy',           NULL,  'magnitude_plus_leadlag', 'PF: |PF|<=1 magnitude + lead/lag flag; never discard the sign [VC-07/DID-04]'),
 ('cumulative_counter_policy', NULL, 'window_delta', 'cumulative *_import_kwh counters → windowed MAX-MIN delta, never a spot reading [VC-06]'),
 -- rating.* — the nameplate→ratings derivation knobs (config/rating_knobs.py; ports backend2 feeder_rating_overrides) —
 ('rating.feeder_pf',           0.9,   NULL, 'assumed PF for the nameplate kVA->kW conversion [#12 derive_ratings]'),
 ('rating.lv_line_v',           415.0, NULL, 'default LT 3-phase line-to-LINE voltage (V) for the rated-current basis [#12]'),
 ('rating.current_alarm_factor',1.2,   NULL, 'high-current alarm = rated_current x this (120%% of rated) [#12]'),
 ('rating.contracted_factor',   0.9,   NULL, 'contracted kW/kVA = rated x this when no per-asset/class fraction [#12]'),
 ('rating.critical_load_factor',0.5,   NULL, 'critical-load kW = rated_kw x this [#12]'),
 ('rating.energy_target_hours', 12.0,  NULL, 'daily energy target = rated_kw x this (equivalent full-load h/day) [#12]'),
 ('rating.capacity_pf',         0.9,   NULL, 'window capacity_kwh = rated_kva x this x hours (energydist _cap_util) [#12]')
ON CONFLICT (key) DO UPDATE SET num_value=EXCLUDED.num_value, txt_value=EXCLUDED.txt_value, note=EXCLUDED.note;


-- ── asset_class_default ── per-CLASS engineering defaults (ports config_defaults.py) — asset_category -> default JSON ─
--    NO rated_kva here (rating stays honest per-asset). Read by config/asset_class_defaults.py; per-asset row wins.
--    Re-derived FROM LIVE 2026-07-06: every class gained ieee_519_current/voltage_thd_limit_pct,
--    ieee_519_individual_harmonic_limit_pct, crest_factor_ideal (1.414) and flicker_pst_limit (1.0).
INSERT INTO asset_class_default (asset_category, default_json) VALUES
 ('Transformer', '{"contracted_kw":2000.0,"critical_load_kw":1500.0,"contracted_frac":0.94,"voltage_statutory_deviation_pct":10.0,"current_tolerance_pct":20.0,"energy_target_kwh_today":40000.0,"target_efficiency_pct":99.0,"thd_v_limit_pct":5.0,"thd_i_limit_pct":8.0,"ieee_519_current_thd_limit_pct":8.0,"ieee_519_voltage_thd_limit_pct":8.0,"ieee_519_individual_harmonic_limit_pct":8.0,"crest_factor_ideal":1.414,"flicker_pst_limit":1.0}'),
 ('Distribution Panel', '{"contracted_kw":4000.0,"critical_load_kw":2700.0,"contracted_frac":0.94,"voltage_statutory_deviation_pct":10.0,"current_tolerance_pct":20.0,"energy_target_kwh_today":80000.0,"target_efficiency_pct":99.0,"thd_v_limit_pct":5.0,"thd_i_limit_pct":8.0,"ieee_519_current_thd_limit_pct":8.0,"ieee_519_voltage_thd_limit_pct":8.0,"ieee_519_individual_harmonic_limit_pct":8.0,"crest_factor_ideal":1.414,"flicker_pst_limit":1.0}'),
 ('LT Panel', '{"contracted_kw":450.0,"critical_load_kw":270.0,"contracted_frac":0.9,"voltage_statutory_deviation_pct":10.0,"current_tolerance_pct":20.0,"energy_target_kwh_today":1200.0,"target_efficiency_pct":97.0,"thd_v_limit_pct":5.0,"thd_i_limit_pct":8.0,"ieee_519_current_thd_limit_pct":8.0,"ieee_519_voltage_thd_limit_pct":8.0,"ieee_519_individual_harmonic_limit_pct":8.0,"crest_factor_ideal":1.414,"flicker_pst_limit":1.0}'),
 ('DG', '{"contracted_kw":808.0,"critical_load_kw":600.0,"contracted_frac":0.8,"service_interval_hours":300.0,"service_warn_pct":85.0,"demand_limit_kw":1700.0,"voltage_statutory_deviation_pct":5.0,"current_tolerance_pct":20.0,"current_unbalance_watch_pct":10.0,"energy_target_kwh_today":8000.0,"target_efficiency_pct":40.0,"thd_v_limit_pct":5.0,"thd_i_limit_pct":8.0,"ieee_519_current_thd_limit_pct":8.0,"ieee_519_voltage_thd_limit_pct":8.0,"ieee_519_individual_harmonic_limit_pct":8.0,"crest_factor_ideal":1.414,"flicker_pst_limit":1.0}'),
 ('UPS', '{"contracted_kw":540.0,"critical_load_kw":400.0,"contracted_frac":0.9,"voltage_statutory_deviation_pct":10.0,"current_tolerance_pct":20.0,"energy_target_kwh_today":6000.0,"target_efficiency_pct":96.0,"thd_v_limit_pct":5.0,"thd_i_limit_pct":8.0,"ready_threshold":60.0,"moderate_zone":30.0,"watch_zone":0.0,"readiness_floor":70.0,"ieee_519_current_thd_limit_pct":8.0,"ieee_519_voltage_thd_limit_pct":8.0,"ieee_519_individual_harmonic_limit_pct":8.0,"crest_factor_ideal":1.414,"flicker_pst_limit":1.0}')
ON CONFLICT (asset_category) DO UPDATE SET default_json=EXCLUDED.default_json;


-- ── metric_class ── which column CLASS each of the 9 EMS pages requires (per-(asset,page) feasibility gate) ────────
--    a page routes only to a meter whose table's fingerprint exposes required_class (see schema_slot_map).
DELETE FROM metric_class;
INSERT INTO metric_class (page_key, required_class) VALUES
 ('energy-power',          'power'),
 ('energy-power',          'energy'),
 ('energy-distribution',   'power'),
 ('energy-distribution',   'energy'),
 ('real-time-monitoring',  'power'),
 ('real-time-monitoring',  'voltage'),
 ('real-time-monitoring',  'current'),
 ('voltage-current',       'voltage'),
 ('voltage-current',       'current'),
 ('power-quality',         'thd'),
 ('power-quality-summary', 'thd'),
 ('harmonics-pq',          'thd'),
 ('overview',              'power'),
 ('overview-sld-3d',       'breaker');


-- ── reason_template ── machine cause → human sentence (the honest-blank reason channel) ───────────────────────────
INSERT INTO reason_template (cause, template) VALUES
 ('no_data',            'No data logged for {asset}.'),
 ('no_history',         'Only live snapshot — no history endpoint for {domain}; data from {since}.'),
 ('no_nameplate',       'Rated capacity unknown for {asset} — loading %% unavailable.'),
 ('no_class',           'This meter is a {device_kind} device, not a {required_class} meter.'),
 ('reversed_ct',        'Showing exported energy (reversed-CT feeder).'),
 ('empty_feeders',      'Partial total: {reporting} of {expected} feeders reporting.'),
 ('structurally_null',  '{metric} not logged by this meter.'),
 ('window_clamped',     'Data available from {since}; window clamped to logged range.'),
 ('no_reading',         '{metric} — no valid reading in this window.'),
 ('denorm_garbage',     'Sensor reading below valid range — treated as no reading.'),
 ('no_topology',        'No topology mapped for {asset}.'),
 ('incomer_unverified', 'Incomer set unverified — loss / meter-gap not computed.'),
 ('frame_shape_mismatch','Card expects {expected} shape but endpoint emitted {actual}.'),
 ('endpoint_retired',   'Endpoint {endpoint} retired — use {alternative}.'),
 ('emit_failed',        'Metadata unavailable — live defaults shown.'),
 ('no_default',         'No default payload and no live fallback for this card.'),
 ('timed_out',          'Live frame timed out — showing last known state.')
ON CONFLICT (cause) DO UPDATE SET template=EXCLUDED.template;


-- ── derivation_binding ── recovery fns + their base columns + fidelity (only bind when base ⊆ present) ────────────
--    CORE subset only, re-derived FROM LIVE 2026-07-06 (fidelity vocab is real_exact/real_approx; the old
--    recovered/approx labels are retired). The full 46-fn registry coverage lives in seed_derivation_binding_full.sql
--    (+ seed_derivation_binding_expressions.sql / _gap6.sql / fix_derivation_binding_*.sql) — this block only pins the
--    render-guarantee core metrics. kwLoadPctOfRated was renamed kpiKwLoadPctOfRated; currentUnbalancePct and
--    windowEnergyExportKwh were retired from live and are gone here too.
INSERT INTO derivation_binding (metric, fn, base_columns, fidelity) VALUES
 ('windowEnergyKwh',        'windowEnergyKwh',       'active_energy_import_kwh',                              'real_exact'),
 ('todaysEnergyTotalKwh',   'todaysEnergyTotalKwh',  'active_energy_import_kwh,active_energy_export_kwh,reactive_energy_import_kvarh,reactive_energy_export_kvarh', 'real_exact'),
 ('thdComplianceIeee519',   'thdComplianceIeee519',  'thd_current_r_pct,thd_current_y_pct,thd_current_b_pct', 'real_approx'),
 ('neutralCurrent',         'neutralCurrent',        'current_r,current_y,current_b',                         'real_approx'),
 ('displacementPf',         'displacementPf',        'power_factor_total',                                    'real_exact'),
 ('truePf',                 'truePf',                'active_power_total_kw,apparent_power_total_kva',         'real_exact'),
 ('pfAngleDeg',             'pfAngleDeg',            'power_factor_total',                                    'real_exact'),
 ('loadFactorPct',          'loadFactorPct',         'active_power_total_kw',                                 'real_approx'),
 ('ratedKva',               'ratedKva',              'nameplate:rated_kva',                                   'real_exact'),
 ('ratedKw',                'ratedKw',               'nameplate:rated_kva',                                   'real_approx'),
 ('kpiKwLoadPctOfRated',    'kpiKwLoadPctOfRated',   'active_power_total_kw,nameplate:rated_kva',             'real_exact'),
 ('sectionContracts',       'sectionContracts',      'nameplate:rated_kva',                                   'real_exact')
ON CONFLICT (metric) DO UPDATE SET fn=EXCLUDED.fn, base_columns=EXCLUDED.base_columns, fidelity=EXCLUDED.fidelity;


-- ── render_guarantee_page_phrase ── page-segment → NL verb phrase (the {page} token in a matrix phrasing). ─────────
INSERT INTO render_guarantee_page_phrase (page_seg, phrase) VALUES
 ('energy-power',          'energy and power for'),
 ('overview',              'overview of'),
 ('power-quality',         'power quality for'),
 ('real-time-monitoring',  'real time monitoring for'),
 ('voltage-current',       'voltage and current for'),
 ('energy-distribution',   'energy distribution for'),
 ('harmonics-pq',          'harmonics and power quality for')
ON CONFLICT (page_seg) DO UPDATE SET phrase=EXCLUDED.phrase;


-- ── render_guarantee_matrix ── the EDITABLE 50-prompt acceptance matrix (asset-selector × page × window × phrasing). ─
--    The test expands each enabled row over the LIVE page list (page_specs, cmd_catalog) and the LIVE registry names
--    when reachable, else the audit-named asset_name_hint. This makes the matrix build from CONFIG (cmd_catalog, UP)
--    instead of collapsing to 0 when the DATA DB tunnel is down. Edit a ROW to change coverage — no test-code change.
--    page_glob '<shell>/*' fans out over every live page under that shell; a bare page_key targets exactly one page.
--    phrasing uses {page} (resolved from render_guarantee_page_phrase for that page's segment) and {a} (asset name).
DELETE FROM render_guarantee_matrix;
INSERT INTO render_guarantee_matrix (tag, asset_selector, asset_name_hint, page_glob, time_window, phrasing, note) VALUES
 -- 1) POPULATED feeder UPS-01 across EVERY feeder page (the happy path)                              [baseline / all pages]
 ('populated_feeder', 'name~ups-01&has_data',        'GIC-01-N3-UPS-01 CL:600KVA',      'individual-feeder-meter-shell/*', '', '{page} {a}',                          'DS baseline: populated feeder across all live feeder pages'),
 -- 2) EMPTY meter UPS-04 (0 rows) across every feeder page → must honest-blank                       [DS-01 silent_empty]
 ('empty_meter',      'name~ups-04|class=UPS&!has_data','GIC-02-N5-UPS-04 CL:600KVA',    'individual-feeder-meter-shell/*', '', '{page} {a}',                          'DS-01: 0-row meter must honest-blank'),
 -- 3) _tm UPS (56-col UPS schema) on energy-power + real-time + overview                             [DS-03 schema-route]
 ('tm_ups',           'name~600 kva ups&has_data|name~17-n1&ups','GIC-17-N1-600 KVA UPS-01 [TiMAC]','individual-feeder-meter-shell/energy-power|individual-feeder-meter-shell/real-time-monitoring|individual-feeder-meter-shell/overview','', '{page} {a}', 'DS-03: _tm 56-col UPS schema route'),
 -- 4) SCADA aux-hsd-plc on electrical pages → class-gate must honest-blank                           [SCADA-pin class-gate]
 ('scada',            'name~aux-hsd|name~hsd-plc|name~plc','AUX-HSD-PLC',                 'individual-feeder-meter-shell/energy-power|individual-feeder-meter-shell/voltage-current|individual-feeder-meter-shell/power-quality','', '{page} {a}', 'SCADA-pin: no electrical cols → class-gate blank'),
 -- 5) PCC panel AGGREGATE across EVERY panel-overview page                                           [DS-07/08 TOPO VC]
 ('pcc_aggregate',    'name~pcc-panel-1|name~pcc panel','PCC-Panel-1',                    'panel-overview-shell/*', '', '{page} panel {a}',                   'DS-07/08 TOPO: panel aggregate / coverage'),
 -- 6) DG duplicate (prefer-populated) on energy-power + real-time + overview                         [DS-09 duplicate]
 ('dg_duplicate',     'class=DG&has_data|name~dg-1|name~dg-01','DG-1 MFM',                'individual-feeder-meter-shell/energy-power|individual-feeder-meter-shell/real-time-monitoring|individual-feeder-meter-shell/overview','', '{page} {a}', 'DS-09: prefer populated dg_N_mfm over empty gic_28_*_jk'),
 -- 7) APFCR / incomer nameplate (loading% by token)                                                  [RN-01/02 nameplate]
 ('apfcr',            'class=APFCR|name~apfc',        'GIC-01-N7-APFCR-01',                'individual-feeder-meter-shell/energy-power|individual-feeder-meter-shell/overview','', '{page} {a}', 'RN-02: nameplate by KVAR token'),
 ('incomer',          'name~bpdb-01&has_data|class=Incomer&has_data|name~incomer','GIC-01-N8-BPDB-01','individual-feeder-meter-shell/energy-power|individual-feeder-meter-shell/overview','', '{page} {a}', 'RN-01: feeder rated kW nameplate'),
 -- 8) REVERSED-CT meter energy card → energy from EXPORT register, never a false 0                   [DS-05 DID-01 VC]
 ('reversed_ct',      'name~ups-02&has_data|name~mldb&has_data|name~ups-01&has_data','GIC-01-N4-UPS-02 CL:600KVA','individual-feeder-meter-shell/energy-power|individual-feeder-meter-shell/overview','', '{page} {a}', 'DS-05: import=0 ∧ export>0 → export register'),
 -- 9) AMBIGUOUS name (HHF collision) → asset-picker gate is an honest terminal                       [RN-04 ambiguous]
 ('ambiguous',        'name~hhf|name~kvar',           'GIC-01-N10-HHF-01',                 'individual-feeder-meter-shell/power-quality','', 'power quality for {a}',  'RN-04: HHF norm-key collision → ambiguous gate'),
 ('ambiguous_concept','concept:harmonic-filter',      'harmonic filter',                   'individual-feeder-meter-shell/power-quality','', 'show me the harmonic filter','RN-04: bare-concept ambiguous phrasing'),
 -- 10) generic non-UPS feeder loading% / nameplate (all-electrical classes incl. Chiller/Compressor) [RN-01/05 VC-05]
 ('feeder_generic',   'class=Panel&has_data|class=AHU&has_data|class=Fan&has_data|class=Pump&has_data|class=Chiller&has_data|class=Compressor&has_data','GIC-05-N3-FCBC','individual-feeder-meter-shell/energy-power|individual-feeder-meter-shell/voltage-current','', '{page} {a}', 'RN-01/05: non-UPS loading%% / section (Panel/AHU/Fan/Pump + Chiller/Compressor all-electrical) [BATCH D #14]'),
 -- 11) 30-day / history window (data window ~6 days → honest-blank/clamp)                             [DS-02 ER-7 date-nav]
 ('history_30d',      'name~ups-01&has_data',         'GIC-01-N3-UPS-01 CL:600KVA',        'individual-feeder-meter-shell/energy-power','last_30d','last 30 days energy for {a}','DS-02: trailing window before earliest row → clamp+reason'),
 ('history_30d_trend','name~ups-01&has_data',         'GIC-01-N3-UPS-01 CL:600KVA',        'individual-feeder-meter-shell/energy-power','last_30d','energy trend over the past month for {a}','DS-02: trend window clamp'),
 ('history_ytd',      'name~ups-01&has_data',         'GIC-01-N3-UPS-01 CL:600KVA',        'individual-feeder-meter-shell/energy-power','ytd','year to date energy consumption for {a}','DS-02: YTD window clamp')
ON CONFLICT (tag) DO UPDATE SET asset_selector=EXCLUDED.asset_selector, asset_name_hint=EXCLUDED.asset_name_hint,
    page_glob=EXCLUDED.page_glob, time_window=EXCLUDED.time_window, phrasing=EXCLUDED.phrasing, note=EXCLUDED.note;
