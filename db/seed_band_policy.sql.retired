-- db/seed_band_policy.sql — the ONE band store for the pipeline: RTM per-metric bands (band_policy) + every scalar
-- band knob (IEEE-519 LV limits + feeder-overview status boundaries) as data_quality_policy rows under `band.`.
-- Read ONLY by config/bands.py (band()/num()); NO logic file hardcodes a band edge, a compliance limit, or a status
-- boundary. Idempotent (ON CONFLICT — safe to re-run). Ported from backend2 core/rtm_defaults.py + powerquality.py +
-- feeder_powerquality.py + feeder_overview.py.  Run:
--   psql -h localhost -p 5432 -d cmd_catalog -f db/seed_band_policy.sql
-- [#8/#9/#12 IEEE-519 + band constants as DB config]

-- ── band_policy ── per-metric RTM bands: one 4-edge band set + basis metadata per metric ────────────────────────────
--    a metric is shown as `display_col` but BANDED on the normalized `basis_col` (basis_scale + absval), so one edge
--    set works across feeders of any size. edges = CSV of the 4 ascending boundaries (low_max,normal_max,mod_max,hi_max)
--    in the basis units. direction: 'asc' higher=worse, 'desc' higher=better (PF). [backend2 rtm_defaults METRIC_META/
--    BASIS_SCALE/DEFAULT_BANDS]
CREATE TABLE IF NOT EXISTS band_policy (
    metric      text PRIMARY KEY,   -- kw | kvar | pf | volt | amp | i_unbal
    display_col text,               -- physical column shown raw in the grid
    basis_col   text,               -- physical column the bands are evaluated on (normalized)
    direction   text,               -- 'asc' higher=worse | 'desc' higher=better (PF)
    absval      boolean,            -- band on |basis| (voltage deviation can be ±)
    edges       text,               -- CSV of 4 ascending edges in basis units (e.g. '40,60,80,95')
    basis_scale numeric,            -- factor applied to basis before banding (kvar ratio 0..1 → % via 100)
    note        text
);

INSERT INTO band_policy (metric, display_col, basis_col, direction, absval, edges, basis_scale, note) VALUES
 ('kw',      'active_power_total_kw',     'kpi_kw_load_pct_of_rated',  'asc',  false, '40,60,80,95', 1,   '% of rated kW loading'),
 ('kvar',    'reactive_power_total_kvar', 'ratio_kvar_kva',            'asc',  false, '20,40,60,80', 100, 'kVAr/kVA %; ratio 0..1 scaled ×100'),
 ('pf',      'power_factor_total',        'power_factor_total',        'desc', false, '0.98,0.95,0.90,0.85', 1, 'raw PF, DESCENDING (>=0.98 → low band)'),
 ('volt',    'voltage_ll_avg',            'kpi_voltage_deviation_pct', 'asc',  true,  '1,2,3,5',     1,   '|voltage deviation %| (can be ±)'),
 ('amp',     'current_avg',               'kpi_kva_load_pct_of_rated', 'asc',  false, '40,60,80,95', 1,   '% of rated kVA loading'),
 ('i_unbal', 'current_unbalance_pct',     'current_unbalance_pct',     'asc',  false, '5,10,15,20',  1,   'current unbalance %')
ON CONFLICT (metric) DO UPDATE SET
    display_col = EXCLUDED.display_col, basis_col = EXCLUDED.basis_col, direction = EXCLUDED.direction,
    absval = EXCLUDED.absval, edges = EXCLUDED.edges, basis_scale = EXCLUDED.basis_scale, note = EXCLUDED.note;

-- ── scalar band knobs → data_quality_policy under `band.` (read by config.bands.num) ────────────────────────────────
-- IEEE-519 LV limits (panel + feeder PQ) and the feeder-overview status boundaries. Each is an editable row; the code
-- default in config/bands._SCALAR_DEFAULTS is only the DB-down fallback.
INSERT INTO data_quality_policy (key, num_value, txt_value, note) VALUES
 -- IEEE-519 LV — panel PQ (backend2 powerquality.py: I_THD/V_THD/TRUE_PF_MIN/NEUTRAL_A)
 ('band.ieee519.i_thd_limit_pct',        8,     NULL, 'IEEE-519 LV current THD limit % (panel PQ)'),
 ('band.ieee519.v_thd_limit_pct',        5,     NULL, 'IEEE-519 LV voltage THD limit % (panel PQ)'),
 ('band.ieee519.true_pf_min',            0.9,   NULL, 'IEEE-519 true PF floor (panel PQ)'),
 ('band.ieee519.neutral_a',              30,    NULL, 'neutral current alarm A (panel PQ)'),
 -- IEEE-519 LV — feeder PQ (backend2 feeder_powerquality.py: I_THD/V_THD/IND_LIMIT/FLICKER/CREST)
 ('band.ieee519.feeder_i_thd_limit_pct', 8,     NULL, 'IEEE-519 LV current THD limit % (feeder PQ)'),
 ('band.ieee519.feeder_v_thd_limit_pct', 8,     NULL, 'IEEE-519 LV voltage THD limit % (feeder PQ)'),
 ('band.ieee519.individual_limit_pct',   6,     NULL, 'IEEE-519 individual-harmonic limit % (feeder PQ)'),
 ('band.ieee519.flicker_limit_pst',      1.0,   NULL, 'short-term flicker Pst limit (feeder PQ)'),
 ('band.ieee519.crest_ideal',            1.414, NULL, 'ideal voltage crest factor (feeder PQ)'),
 -- PQ label thresholds — shared _pq_labels derivers (backend2 sim *_config defaults)
 ('band.ieee519.pf_target',              0.95,  NULL, 'PF target for PQ label derivers (PF_TARGET)'),
 ('band.ieee519.v_unbalance_warn_pct',   2.0,   NULL, 'voltage-unbalance warn % (V_UNBALANCE_WARN_PCT)'),
 ('band.ieee519.thd_rising_rate_pct_h',  5.0,   NULL, 'THD rise %/h → Watch (THD_RISING_RATE_PCT_H)'),
 ('band.ieee519.sag_swell_event_hot',    10,    NULL, 'sag+swell/24h above → flag (SAG_SWELL_EVENT_HOT)'),
 -- panel PQ fleet rollup — composite score weights + severity/driver bands (backend2 powerquality.py _score/_sev/_driver)
 ('band.pq_fleet.score_w_i_thd',         4,     NULL, 'I-THD weight in the fleet composite score'),
 ('band.pq_fleet.score_w_v_thd',         3,     NULL, 'V-THD weight in the fleet composite score'),
 ('band.pq_fleet.score_w_h5',            2,     NULL, 'H5 weight in the fleet composite score'),
 ('band.pq_fleet.score_w_h7',            2,     NULL, 'H7 weight in the fleet composite score'),
 ('band.pq_fleet.score_w_pf_gap',        200,   NULL, '(true_pf_min − true_pf) weight (PF gap dominates)'),
 ('band.pq_fleet.watch_frac',            0.8,   NULL, 'severity ''warning'' when i_thd >= this × I-THD limit'),
 ('band.pq_fleet.driver_frac',           0.8,   NULL, 'dominant-driver labelled only when ratio >= this (else ''OK'')'),
 ('band.pq_fleet.pf_gap_norm',           0.1,   NULL, 'PF-gap normaliser in the driver ratio (backend2 /0.1)'),
 -- feeder-overview status bands (backend2 feeder_overview _band call-sites) — (lo, hi) per card
 ('band.overview.busbar_temp_c.lo',      45,    NULL, 'busbar temp Normal≤lo<Warning≤hi<Critical'),
 ('band.overview.busbar_temp_c.hi',      55,    NULL, 'busbar temp upper band edge'),
 ('band.overview.kw_load_pct.lo',        75,    NULL, 'kW-load Normal≤lo<Elevated≤hi<Critical'),
 ('band.overview.kw_load_pct.hi',        90,    NULL, 'kW-load upper band edge'),
 ('band.overview.freq_dev_hz.lo',        0.05,  NULL, 'freq |dev| Stable≤lo<Fair≤hi<Unstable'),
 ('band.overview.freq_dev_hz.hi',        0.1,   NULL, 'freq |dev| upper band edge'),
 ('band.overview.phase_balance_pct.lo',  5,     NULL, 'phase balance Balanced≤lo<Watch≤hi<Unbalanced'),
 ('band.overview.phase_balance_pct.hi',  10,    NULL, 'phase balance upper band edge'),
 ('band.overview.energy_budget_pct.lo',  75,    NULL, 'energy vs budget On-Track≤lo<Elevated≤hi<Critical'),
 ('band.overview.energy_budget_pct.hi',  90,    NULL, 'energy vs budget upper band edge'),
 ('band.overview.voltage_dev_pct.lo',    3,     NULL, 'voltage |dev| Normal≤lo<Elevated≤hi<Critical'),
 ('band.overview.voltage_dev_pct.hi',    5,     NULL, 'voltage |dev| upper band edge'),
 ('band.overview.nominal_hz',            50,    NULL, 'nominal grid frequency Hz (deviation reference)')
ON CONFLICT (key) DO UPDATE SET num_value = EXCLUDED.num_value, txt_value = EXCLUDED.txt_value, note = EXCLUDED.note;
