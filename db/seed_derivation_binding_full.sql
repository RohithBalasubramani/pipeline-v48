-- db/seed_derivation_binding_full.sql — CLOSE THE derivation_binding COVERAGE GAP (2026-07-03).
-- ROOT CAUSE (voltage-and-current-for-UPS polish): ems_exec.derivations.registry.catalog() advertises 46 fns to
-- Layer 2, but derivation_binding held only 14 rows. A fn without a row -> config.derivation_binding.binding()=None
-- -> executor _run_derived built an EMPTY input row -> honest None, even when every base column was live
-- (upsRatedKva / neutralToPhaseRatioPct / progressActivePct / nominalVoltageLN on gic_01_n3_ups_01_p1).
-- This seed upserts ONE row per registry value_key, base_columns/fidelity copied verbatim from the registry
-- descriptors (the code ground truth). upsRatedKva's input is the asset NAME carried in ctx (not a frame column),
-- so its base_columns is empty. Idempotent: ON CONFLICT re-derives.
-- SINGLE-FEEDER LOSS/EFF PROXY (2026-07-07, card 41 Input-vs-Output false-blank): expectedLossKwh + lossPct are now
-- real_approx — an input-vs-output card over ONE meter has no modelled upstream input, so both derive a BOUNDED
-- design-band estimate (energy_balance.expected_loss_band_pct) over the meter's REAL windowed energy/power throughput
-- (expected_loss = window_energy × band/100; loss% = band). Honest proxy, never a fabrication (blanks a genuinely-dark
-- meter). The HV/LV-leg loss (activePowerLossKw/Pct) stays real_exact-or-None: it blanks honestly when a UPS/feeder
-- lacks the two physical HV/LV legs (gic_* has no hv_input_kw/lv_output_kw column).
INSERT INTO derivation_binding (metric, fn, base_columns, fidelity) VALUES
 ('nominalVoltageLN',            'nominalVoltageLN',            'voltage_avg,kpi_voltage_deviation_pct',                          'real_exact'),
 ('voltageStatutoryBand',        'voltageStatutoryBand',        'voltage_avg,kpi_voltage_deviation_pct',                          'real_exact'),
 ('voltageHistoryDomain',        'voltageHistoryDomain',        'voltage_avg,voltage_r_n,voltage_y_n,voltage_b_n',                'real_exact'),
 ('progressActivePct',           'progressActivePct',           'active_energy_import_kwh,reactive_energy_import_kvarh',          'real_exact'),
 ('activeEnergyMvah',            'activeEnergyMvah',            'active_energy_import_kwh',                                       'real_exact'),
 ('reactiveEnergyMvarh',         'reactiveEnergyMvarh',         'reactive_energy_import_kvarh',                                   'real_exact'),
 ('cumulativeApparentMvah',      'cumulativeApparentMvah',      'active_energy_import_kwh,reactive_energy_import_kvarh',          'real_exact'),
 ('expectedLossKwh',             'expectedLossKwh',             'active_energy_import_kwh',                                       'real_approx'),
 ('worstPeakKw',                 'worstPeakKw',                 'active_power_total_kw',                                          'real_exact'),
 ('worstPeakAt',                 'worstPeakAt',                 'active_power_total_kw,ts',                                       'real_exact'),
 ('apparentPeakKva',             'apparentPeakKva',             'apparent_power_total_kva',                                       'real_approx'),
 ('activePowerDeltaPerMinute',   'activePowerDeltaPerMinute',   'active_power_total_kw,ts',                                       'real_exact'),
 ('lossPct',                     'lossPct',                     'active_power_total_kw',                                          'real_approx'),
 ('aiSummary',                   'aiSummary',                   'active_power_total_kw',                                          'real_exact'),
 ('sectionTrendSums',            'sectionTrendSums',            'active_power_total_kw',                                          'real_exact'),
 ('upsRatedKva',                 'upsRatedKva',                 '',                                                               'real_approx'),
 ('neutralToPhaseRatioPct',      'neutralToPhaseRatioPct',      'current_r,current_y,current_b,current_avg',                      'real_approx'),
 ('thdTrendLabel',               'thdTrendLabel',               'thd_current_r_pct,thd_current_y_pct,thd_current_b_pct,ts',       'real_approx'),
 ('thdTrendRatePctPerHour',      'thdTrendRatePctPerHour',      'thd_current_r_pct,thd_current_y_pct,thd_current_b_pct,ts',       'real_approx'),
 ('activeEnergyTodayKwh',        'activeEnergyTodayKwh',        'active_energy_import_kwh,active_energy_export_kwh',              'real_exact'),
 ('activeEnergyThisWeekKwh',     'activeEnergyThisWeekKwh',     'active_energy_import_kwh,active_energy_export_kwh',              'real_exact'),
 ('activeEnergyThisMonthKwh',    'activeEnergyThisMonthKwh',    'active_energy_import_kwh,active_energy_export_kwh',              'real_exact'),
 ('reactiveEnergyTodayKvarh',    'reactiveEnergyTodayKvarh',    'reactive_energy_import_kvarh,reactive_energy_export_kvarh',      'real_exact'),
 ('reactiveEnergyThisWeekKvarh', 'reactiveEnergyThisWeekKvarh', 'reactive_energy_import_kvarh,reactive_energy_export_kvarh',      'real_exact'),
 ('reactiveEnergyThisMonthKvarh','reactiveEnergyThisMonthKvarh','reactive_energy_import_kvarh,reactive_energy_export_kvarh',      'real_exact'),
 ('apparentEnergyTodayKvah',     'apparentEnergyTodayKvah',     'active_energy_import_kwh,reactive_energy_import_kvarh',          'real_exact'),
 ('apparentEnergyThisWeekKvah',  'apparentEnergyThisWeekKvah',  'active_energy_import_kwh,reactive_energy_import_kvarh',          'real_exact'),
 ('apparentEnergyThisMonthKvah', 'apparentEnergyThisMonthKvah', 'active_energy_import_kwh,reactive_energy_import_kvarh',          'real_exact'),
 ('specificEnergyConsumption',   'specificEnergyConsumption',   'active_energy_import_kwh',                                       'real_exact'),
 ('kpiKwLoadPctOfRated',         'kpiKwLoadPctOfRated',         'active_power_total_kw,nameplate:rated_kva',                      'real_exact'),
 ('kpiLoadFactor',               'kpiLoadFactor',               'active_power_total_kw,nameplate:rated_kva',                      'real_exact'),
 ('activePowerLossKw',           'activePowerLossKw',           'hv_input_kw,lv_output_kw',                                       'real_exact'),
 ('activePowerLossPct',          'activePowerLossPct',          'hv_input_kw,lv_output_kw',                                       'real_exact'),
 ('rateOfChangePowerKwPerMin',   'rateOfChangePowerKwPerMin',   'active_power_total_kw,ts',                                       'real_exact'),
 ('loadFactorWindowPct',         'loadFactorWindowPct',         'active_power_total_kw',                                          'real_approx')
ON CONFLICT (metric) DO UPDATE SET fn=EXCLUDED.fn, base_columns=EXCLUDED.base_columns, fidelity=EXCLUDED.fidelity;
