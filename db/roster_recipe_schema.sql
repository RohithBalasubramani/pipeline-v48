-- cmd_catalog: atomized per-card fill recipes (Inventory C recommendation: card_fill_recipe keyed like card_data_recipe)
BEGIN;

CREATE TABLE IF NOT EXISTS card_fill_recipe (
  card_id        integer PRIMARY KEY,
  handling_class text    NOT NULL,          -- panel_aggregate | topology_sld | narrative_ai (denorm for gate speed)
  roster_spec    jsonb   NOT NULL,          -- the executable per-card recipe (vocabulary in §2)
  notes          text,
  source         text    DEFAULT 'inventory-A+B 2026-07-02',
  updated_at     timestamptz DEFAULT now()
);

-- FE per-card wiring metadata (Inventory B recommendation)
CREATE TABLE IF NOT EXISTS card_rendering (
  card_id               integer PRIMARY KEY,
  page_key              text,
  render_kind           text NOT NULL CHECK (render_kind IN ('special','components','compose','fill')),
  envelope_kind         text,               -- narrative_ai | asset_3d | topology (SPECIAL only)
  component_alias       text,               -- e.g. 'Cmp7' (COMPONENTS) / import alias — the NAME only; import stays code
  fill_module           text,               -- FILL barrel path relative to host/web/src/cmd/fill/
  payload_shape_category text CHECK (payload_shape_category IN ('single_unwrap','multi_spread','envelope_only') OR payload_shape_category IS NULL),
  payload_single_key    text,               -- e.g. 'heatmap', 'rail', 'strip'
  mapper_key            text,               -- CMD_V2 mapper fn name (e.g. 'mapFrame')
  state_schema          jsonb,              -- {metric:'string', idx:'number', ...}
  state_defaults        jsonb,
  date_control          jsonb,              -- {kind:'sampling_picker'|'none', defaults:{...}}
  honest_blank_reason   text
);

-- shared (NOT card-specific) dataset facts → app_config, per the existing cfg() pattern
INSERT INTO app_config (key, value, data_type, section, note) VALUES
 ('roster.member_columns',
  '["active_power_total_kw","reactive_power_total_kvar","apparent_power_total_kva","kpi_true_pf","power_factor_total","voltage_avg","current_avg","active_energy_import_kwh","current_neutral","kpi_neutral_to_phase_ratio_pct","pf_gap_vs_full_load","harmonic_5th_pct","harmonic_7th_pct","thd_current_r_pct","thd_current_y_pct","thd_current_b_pct","thd_voltage_r_pct","thd_voltage_y_pct","thd_voltage_b_pct","current_unbalance_pct"]',
  'json','roster','the present-tolerant per-member read set (was panel_aggregate.py:41-66 _MEMBER_COLS)'),
 ('roster.sum_columns',
  '["active_power_total_kw","reactive_power_total_kvar","apparent_power_total_kva","current_avg","current_neutral"]',
  'json','roster','extensive Σ-magnitude columns; everything else means (was panel_aggregate.py:69 _SUM_COLS)'),
 ('roster.energy_column','active_energy_import_kwh','text','roster','cumulative counter → windowed-delta'),
 -- 'on' re-derived FROM LIVE 2026-07-06 (the valve was flipped on in production; seeding 'off' would silently disable the interpreter on re-run)
 ('roster.interpreter_enabled','on','text','roster','off | shadow | on — the per-card cutover valve (§4)')
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, note = EXCLUDED.note;

COMMIT;
