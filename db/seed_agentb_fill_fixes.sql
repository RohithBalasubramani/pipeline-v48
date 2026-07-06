-- db/seed_agentb_fill_fixes.sql — AGENT B fill/roster/events/windows/reasons config seeds (fullsweep_20260706 defects).
-- Idempotent (ON CONFLICT upserts). Apply: psql -U postgres -h 127.0.0.1 -p 5432 -d cmd_catalog -f db/seed_agentb_fill_fixes.sql
--
-- (1) reversed-CT pick_mover unification  — roster.energy_register_pairs (cards 12/13/14/16 false-zero kWh)
-- (2) event registers                     — card_fill_recipe 18/22 event bindings (0-events vs 102/105 real edges)
-- (3) window honoring                     — window.honor_declared_range + card-14 slot ranges (Monthly == this-month)
-- (4) rail composite under-fill           — card-7 recipe: quickStats scalars + Peak-Today/PF series stats (card-10/11 parity)
-- (5) derivation bugs                     — voltageSpread/maxDeviation bindings (card 44) + card-46 windowed self stats
-- (6) reasons always                      — reason_template 'unbound_by_emit' + reasons.max_unbound_records

-- ═══ (6) the unbound_by_emit per-leaf reason ═════════════════════════════════════════════════════════════════════
INSERT INTO reason_template (cause, template) VALUES
  ('unbound_by_emit', '{metric} — no data binding was emitted for this leaf; left blank (no measured source declared).')
ON CONFLICT (cause) DO UPDATE SET template = EXCLUDED.template;

-- ═══ (1)(3)(6) app_config knobs (code defaults preserved in the readers) ═════════════════════════════════════════
INSERT INTO app_config (key, value, data_type, section, note) VALUES
  ('roster.energy_register_pairs',
   '{"active_energy_import_kwh":"active_energy_export_kwh","reactive_energy_import_kvarh":"reactive_energy_export_kvarh"}',
   'json', 'roster',
   'IMPORT->EXPORT cumulative-register pairs: ANY windowed delta on a paired import register reads BOTH and picks the mover (reversed-CT feeders keep real kWh on export). Used by members.member_delta / bucketed_multi energy_delta / panel_kwh.'),
  ('window.honor_declared_range', 'on', 'text', 'window',
   'When on, ems_exec widens a card window to the consumer''s declared range (last-7-days / this-month / today) anchored at the window end — the values a card renders match the range it claims.'),
  ('reasons.max_unbound_records', '60', 'int', 'reasons',
   'Cap on per-card unbound_by_emit gap records from the fill completion scan (every blank leaf carries a reason; a fully-dark card must not flood telemetry).')
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, data_type = EXCLUDED.data_type,
                                section = EXCLUDED.section, note = EXCLUDED.note;

-- ═══ (5) derivation bindings — the metric names the QUANTITY; metric-wins re-routes a wrong emit fn ═══════════════
-- card 44: 'Worst Spread' was fn=nominalVoltageLN (shipped the ~240 V NOMINAL as a spread; DB per-sample phase spread
-- <= ~4-6 V); 'Max Deviation' was fn=voltageStatutoryBand (a dict -> honest-blank while kpi_voltage_deviation_pct is
-- fully logged, window max |dev| ~2-6%). Both series-scoped windowed statistics now.
INSERT INTO derivation_binding (metric, fn, base_columns, fidelity, scope) VALUES
  ('voltageSpread',            'worstPhaseSpreadV',        'voltage_r_n,voltage_y_n,voltage_b_n', 'real_exact', 'series'),
  ('maxDeviation',             'worstVoltageDeviationPct', 'kpi_voltage_deviation_pct',           'real_exact', 'series'),
  ('worstPhaseSpreadV',        'worstPhaseSpreadV',        'voltage_r_n,voltage_y_n,voltage_b_n', 'real_exact', 'series'),
  ('worstVoltageDeviationPct', 'worstVoltageDeviationPct', 'kpi_voltage_deviation_pct',           'real_exact', 'series')
ON CONFLICT (metric) DO UPDATE SET fn = EXCLUDED.fn, base_columns = EXCLUDED.base_columns,
                                   fidelity = EXCLUDED.fidelity, scope = EXCLUDED.scope;

-- ═══ (5) endpoint → recipe-family map (the plain run_card path carries NO card_id; the consumer endpoint names the
--         same card-family data contract, so a single-asset recipe row becomes reachable) ═════════════════════════
CREATE TABLE IF NOT EXISTS endpoint_recipe_map (
  endpoint text PRIMARY KEY,
  card_id  integer NOT NULL,
  note     text
);
INSERT INTO endpoint_recipe_map (endpoint, card_id, note) VALUES
  ('current-history', 46, 'current-history family (card 46 shape): windowed self-roster history stats (Peak/Avg/Unbalance/Neutral-Peak)')
ON CONFLICT (endpoint) DO UPDATE SET card_id = EXCLUDED.card_id, note = EXCLUDED.note;

-- ═══ (4) card 7 — the rail composite fills the SAME live metrics its siblings fill (cards 10/11 parity) ═══════════
UPDATE card_fill_recipe SET roster_spec = '{
 "slots": [
  {"mode": "series", "slot": "railVM.trend.series", "scope": "members", "column": "active_power_total_kw",
   "reduce": "sum_magnitude", "sampling": "hourly", "role_filter": "load",
   "stats": [
    {"op": "maximum", "r": 2, "slot": "railVM.trend.bottomStats.0.value",
     "at_slot": "railVM.trend.bottomStats.0.subtext", "at_prefix": "at ", "at_fmt": "HH:MM:SS",
     "why": "Peak Today = MAX of the rails OWN rolled active-power series (card-10 parity; the rail must never dash a metric its sibling fills in the same run)"},
    {"op": "mean", "r": 3, "slot": "railVM.trend.bottomStats.1.value", "column": "kpi_true_pf", "reduce": "mean",
     "why": "Power Factor = rolled mean of the UNSIGNED true PF over the same load roster (card-10 parity)"}
   ]},
  {"agg": {"value": {"r": 2, "of": "kw", "agg": "sum_magnitude"}, "denominator": {"v": null, "agg": "const"},
           "consumedHint": {"v": null, "agg": "const"}},
   "mode": "aggregates", "slot": "railVM.supply", "scope": "members",
   "element": {"kw": {"b": "col", "c": "active_power_total_kw", "q": "power", "r": 2}}, "role_filter": "load"},
  {"mode": "sections", "slot": "railVM.supply.breakdown", "entry": {"unit": "kW"}, "scope": "members",
   "element": {"kw": {"b": "col", "c": "active_power_total_kw", "q": "power", "r": 2}},
   "group_by": "section_defs", "unmatched": {"label": "load_group", "policy": "derived_section"},
   "role_filter": "load", "section_agg": {"value": {"r": 2, "of": "kw", "agg": "sum_magnitude"}},
   "wrap_sample": false, "section_defs": [],
   "entry_palette": {"key": "color", "values": ["#237492", "#bc9e44", "#bd6184"]}, "reporting_only": true},
  {"agg": {"r": 1, "of": "voltage", "agg": "mean"}, "mode": "scalar", "slot": "railVM.quickStats.0.value",
   "scope": "members", "element": {"voltage": {"b": "col", "c": "voltage_avg", "r": 1}}, "role_filter": "load",
   "why": "card-11 parity: rolled mean member voltage — the rail binds the SAME live metrics card 11 fills"},
  {"agg": {"r": 2, "of": "iunbal", "agg": "mean"}, "mode": "scalar", "slot": "railVM.quickStats.1.value",
   "scope": "members", "element": {"iunbal": {"b": "col", "c": "current_unbalance_pct", "r": 2}}, "role_filter": "load"},
  {"agg": {"r": 0, "of": "current", "agg": "sum_magnitude"}, "mode": "scalar", "slot": "railVM.quickStats.2.value",
   "scope": "members", "element": {"current": {"b": "col", "c": "current_avg", "r": 0}}, "role_filter": "load"},
  {"v": null, "mode": "const", "slot": "railVM.aiSummaryText"}
 ],
 "coverage_attach": "widgets._coverage"
}'::jsonb,
 notes = 'AGENT-B 2026-07-06: quickStats 0/1/2 + trend.bottomStats Peak-Today/PF added (cards 10/11 parity) — rail rendered em-dashes while siblings filled the identical metrics in the same run.',
 source = 'seed_agentb_fill_fixes.sql', updated_at = now()
WHERE card_id = 7;

-- ═══ (3) card 14 — the Monthly cumulative-energy KPI reads THIS-MONTH, not whatever window the host passed ═════════
UPDATE card_fill_recipe SET roster_spec = '{
 "slots": [
  {"agg": {"r": 1, "of": "activeKwh", "agg": "sum_magnitude"}, "mode": "scalar", "slot": "card.view.value",
   "scope": "members", "range": "this-month",
   "element": {"activeKwh": {"b": "delta", "c": "active_energy_import_kwh", "r": 1}}, "role_filter": "load",
   "why": "periodLabel says Monthly -> the delta window IS this-month (anchored at the run window end); the delta binding is pick_mover so reversed-CT export energy counts"},
  {"mode": "entries", "slot": "card.view.metrics", "scope": "members", "id_key": "id", "range": "this-month",
   "element": {"activeKwh": {"b": "delta", "c": "active_energy_import_kwh", "r": 1},
               "reactiveKvarh": {"b": "delta", "c": "reactive_energy_import_kvarh", "r": 1}},
   "entries": [
    {"id": "active", "aggs": {"unit": {"v": "kWh", "agg": "const"},
                              "value": {"r": 1, "of": "activeKwh", "agg": "sum_magnitude"}}},
    {"id": "reactive", "aggs": {"unit": {"v": "kVArh", "agg": "const"},
                                "value": {"r": 1, "of": "reactiveKvarh", "agg": "sum_magnitude"}}},
    {"id": "sec", "aggs": {"value": {"v": null, "agg": "const"}}}
   ], "role_filter": "load"},
  {"mode": "entries", "slot": "card.view.segments", "scope": "members", "id_key": "id", "range": "this-month",
   "element": {"activeKwh": {"b": "delta", "c": "active_energy_import_kwh", "r": 1},
               "reactiveKvarh": {"b": "delta", "c": "reactive_energy_import_kvarh", "r": 1}},
   "entries": [
    {"id": "active", "agg": {"r": 1, "of": "activeKwh", "agg": "sum_magnitude"}},
    {"id": "reactive", "agg": {"r": 1, "of": "reactiveKvarh", "agg": "sum_magnitude"}}
   ], "role_filter": "load"},
  {"v": "kWh", "mode": "const", "slot": "card.view.valueUnit"},
  {"v": null, "mode": "const", "slot": "card.view.capacityValue"},
  {"v": null, "mode": "const", "slot": "card.view.target"},
  {"v": null, "mode": "const", "slot": "card.view.markerPct"},
  {"v": null, "mode": "const", "slot": "card.view.markerLabel"},
  {"v": null, "mode": "const", "slot": "card.view.insight"}
 ],
 "coverage_attach": "widgets._coverage"
}'::jsonb,
 notes = 'AGENT-B 2026-07-06: slot range=this-month (label said Monthly, value was a trailing-24h delta 79,760 vs MTD ~476k pick_mover); member delta is now reversed-CT pick_mover.',
 source = 'seed_agentb_fill_fixes.sql', updated_at = now()
WHERE card_id = 14;

-- ═══ (2) card 18 — the events KPI strip counts REAL windowed rising edges of the event registers ══════════════════
UPDATE card_fill_recipe SET roster_spec = '{
 "slots": [
  {"mode": "aggregates", "slot": "strip.stats", "scope": "members", "role_filter": "load", "reporting_only": true,
   "range": "today",
   "element": {
     "id": {"a": "name", "b": "slug"},
     "sag": {"b": "event", "c": "sag_event_active"},
     "amps": {"b": "null", "why": "no aggregate current column bound for the worst-panel chip"},
     "iThd": {"b": "col", "c": "thd_compliance_i_avg", "r": 2},
     "vAvg": {"b": "null", "why": "no per-window vAvg column on gic_*"},
     "vMax": {"b": "null", "why": "no per-window vMax column on gic_*"},
     "vMin": {"b": "null", "why": "no per-window vMin column on gic_*"},
     "cause": {"b": "const", "v": ""},
     "mfmId": {"a": "mfm_id", "b": "attr"},
     "panel": {"a": "name", "b": "attr"},
     "swell": {"b": "event", "c": "swell_event_active"},
     "table": {"a": "table", "b": "attr"},
     "status": {"b": "status", "vocab": ["success", "warning", "danger"], "policy": "pf_floors"},
     "truePf": {"b": "col", "c": "kpi_true_pf", "r": 3},
     "current": {"b": "event", "c": "current_imbalance_event_active"},
     "neutral": {"b": "event", "c": "neutral_stress_event_active"},
     "causeKey": {"b": "null", "why": "cause diagnosis is not a neuract column"},
     "neutralA": {"b": "col", "c": "current_neutral", "r": 1},
     "iUnbalance": {"b": "col", "c": "current_unbalance_pct", "r": 2},
     "vDeviation": {"b": "col", "c": "kpi_voltage_deviation_pct", "r": 2, "keep_sign": true}
   },
   "agg": {
     "sag": {"agg": "sum_magnitude", "of": "sag", "r": 0,
             "why": "Sigma of per-member RAW-ROW rising-edge counts of sag_event_active over the today window — never an instant snapshot breach count"},
     "swell": {"agg": "sum_magnitude", "of": "swell", "r": 0},
     "current": {"agg": "sum_magnitude", "of": "current", "r": 0},
     "neutral": {"agg": "sum_magnitude", "of": "neutral", "r": 0},
     "total": {"agg": "sum_of", "keys": ["sag", "swell", "current", "neutral"]},
     "worstCurrent": {"of": "iUnbalance", "agg": "argmax"},
     "worstVoltage": {"of": "vDeviation", "abs": true, "agg": "argmax"}
   }}
 ],
 "thresholds": {"vSag_floor_pct": -5.0, "neutral_floor_a": 30.0, "vSwell_floor_pct": 5.0, "iUnbalance_floor_pct": 15.0},
 "coverage_attach": "widgets._coverage"
}'::jsonb,
 notes = 'AGENT-B 2026-07-06: sag/swell/current/neutral now Sigma of per-member windowed RISING-EDGE counts of the *_event_active registers (raw-row edges, range=today) — was instant count_breach on latest values (0 shown vs 102 current + 105 neutral real edges today on bpdb-01).',
 source = 'seed_agentb_fill_fixes.sql', updated_at = now()
WHERE card_id = 18;

-- ═══ (2) card 22 — the per-panel event table binds the event REGISTERS as windowed edge counts ════════════════════
UPDATE card_fill_recipe SET roster_spec = '{
 "slots": [
  {"mode": "elements", "slot": "table.period.panels[]", "scope": "members", "range": "today",
   "element": {
     "id": {"a": "name", "b": "slug"},
     "sag": {"b": "event", "c": "sag_event_active"},
     "amps": {"b": "col", "c": "current_avg", "r": 1},
     "vAvg": {"b": "col", "c": "voltage_avg", "r": 1},
     "vMax": {"b": "col", "c": "voltage_max", "r": 1},
     "vMin": {"b": "col", "c": "voltage_min", "r": 1},
     "cause": {"b": "const", "v": ""},
     "panel": {"a": "name", "b": "attr"},
     "swell": {"b": "event", "c": "swell_event_active"},
     "table": {"a": "table", "b": "attr"},
     "status": {"b": "status", "vocab": ["success", "warning", "danger"], "policy": "pf_floors"},
     "current": {"b": "event", "c": "current_imbalance_event_active"},
     "neutral": {"b": "event", "c": "neutral_stress_event_active"},
     "causeKey": {"b": "const", "v": "normal"},
     "neutralA": {"b": "col", "c": "current_neutral", "r": 1},
     "iUnbalance": {"b": "col", "c": "current_unbalance_pct", "r": 1},
     "vDeviation": {"b": "col", "c": "kpi_voltage_deviation_pct", "r": 2}
   },
   "role_filter": "load", "reporting_only": true}
 ],
 "coverage_attach": "widgets._coverage"
}'::jsonb,
 notes = 'AGENT-B 2026-07-06: sag/swell/current/neutral were instant col reads of the flag (0/1 snapshot shipped as an event count) -> windowed raw-row rising-edge counts per member (range=today).',
 source = 'seed_agentb_fill_fixes.sql', updated_at = now()
WHERE card_id = 22;

-- ═══ (5) card 46 — history stats = window statistics over the meters OWN rolled series (self roster of one) ═══════
INSERT INTO card_fill_recipe (card_id, handling_class, roster_spec, notes, source, updated_at) VALUES
 (46, 'single_asset_series', '{
 "slots": [
  {"mode": "series", "slot": "history.data.stats", "stats_only": true, "scope": "self", "role_filter": "self",
   "column": "current_max", "reduce": "mean", "sampling": "hourly",
   "why": "windowed HISTORY stats over the meters OWN rolled series — a history stat is a window statistic, never the live snapshot the emit bound (agg=last)",
   "stats": [
    {"op": "maximum", "r": 1, "slot": "history.data.stats.0.value",
     "why": "Peak Current = window max of the rolled phase-max register"},
    {"op": "mean", "r": 1, "column": "current_avg", "reduce": "mean", "slot": "history.data.stats.1.value",
     "why": "Average Current = window mean, not the latest sample"},
    {"op": "maximum", "r": 2, "column": "current_unbalance_pct", "reduce": "mean", "slot": "history.data.stats.2.value",
     "why": "Max Unbalance = window max"},
    {"op": "maximum", "r": 2, "column": "current_neutral", "reduce": "mean", "slot": "history.data.stats.3.value",
     "why": "Neutral Peak = window max of current_neutral — the emit mis-bound current_max (250 A phase snapshot shipped as neutral; DB window max current_neutral ~18-26 A)"}
   ]}
 ]
}'::jsonb,
 'AGENT-B 2026-07-06: card 46 Neutral Peak shipped the LIVE phase snapshot (current_max 250 A) as neutral vs DB max(current_neutral) ~23 A (10x off) + every history stat was the live snapshot. Reached via endpoint_recipe_map (current-history) + the self pseudo-member.',
 'seed_agentb_fill_fixes.sql', now())
ON CONFLICT (card_id) DO UPDATE SET handling_class = EXCLUDED.handling_class, roster_spec = EXCLUDED.roster_spec,
                                    notes = EXCLUDED.notes, source = EXCLUDED.source, updated_at = EXCLUDED.updated_at;
