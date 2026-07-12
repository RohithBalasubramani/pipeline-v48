-- cmd_catalog: the atomized per-card roster recipes (V48 generalization package §1b).
-- Binding/slot vocabulary is defined in docs/V48_GENERALIZATION_PACKAGE.md §2. $j$...$j$::jsonb dollar-quoting throughout.
BEGIN;

-- ── card 2 : Single-Line Diagram (topology_sld) ─────────────────────────────────────────────
INSERT INTO card_fill_recipe (card_id, handling_class, roster_spec, notes) VALUES
(2, 'topology_sld', $j$
{
 "coverage_attach": "widgets._coverage",
 "slots": [
  {"slot":"widgets.sld.incoming[]","mode":"elements","scope":"members","role_filter":"supply","order":"member",
   "element":{
    "name":{"b":"attr","a":"name"},"type":{"b":"attr","a":"type"},"mfm_id":{"b":"attr","a":"mfm_id"},
    "kw":{"b":"col","c":"active_power_total_kw","q":"power","r":2},
    "kva":{"b":"col","c":"apparent_power_total_kva","q":"power","r":2},
    "kvar":{"b":"col","c":"reactive_power_total_kvar","r":2,"keep_sign":true},
    "kwh":{"b":"delta","c":"active_energy_import_kwh","r":1},
    "pf":{"b":"prefer_abs","cs":["kpi_true_pf","power_factor_total"],"r":3},
    "voltage":{"b":"col","c":"voltage_avg","r":1},"current":{"b":"col","c":"current_avg","r":1},
    "load_pct":{"b":"null","why":"no per-feeder rated capacity on gic_*"},
    "breaker_state":{"b":"null","why":"no breaker column in neuract"},
    "status":{"b":"status","policy":"pf_floors","vocab":["normal","warning","critical"]},
    "energized":{"b":"energized"}}},
  {"slot":"widgets.sld.outgoing[]","mode":"elements","scope":"members","role_filter":"load","order":"member",
   "element":{"$same_as_slot":"widgets.sld.incoming[]"}},
  {"slot":"widgets.sld.bus","mode":"aggregates","scope":"members","role_filter":"supply",
   "agg":{"kw":{"agg":"sum_magnitude","of":"kw","r":2},
          "kva":{"agg":"sum_magnitude","of":"kva","r":2},
          "kvar":{"agg":"sum_magnitude","of":"kvar","r":2},
          "pf":{"agg":"mean","of":"pf","role_filter":"all","r":4},
          "voltage":{"agg":"first_nonnull","of":"voltage"},
          "coupler_state":{"agg":"const","v":null},
          "label":{"agg":"panel_name"}}},
  {"slot":"widgets.header_kpis","mode":"aggregates","scope":"members",
   "agg":{"incoming_kw":{"agg":"sum_magnitude","of":"kw","role_filter":"supply","r":2},
          "outgoing_kw":{"agg":"sum_magnitude","of":"kw","role_filter":"load","r":2},
          "avg_pf":{"agg":"mean","of":"pf","role_filter":"all","r":4},
          "incoming_count":{"agg":"len","role_filter":"supply"},
          "outgoing_count":{"agg":"len","role_filter":"load"},
          "main_mfm_kw":{"agg":"alias","of":"incoming_kw"}}},
  {"slot":"widgets.header_status","mode":"aggregates","scope":"members","role_filter":"all",
   "agg":{"critical":{"agg":"count_status","status":"critical"},
          "warning":{"agg":"count_status","status":"warning"},
          "normal":{"agg":"count_status","status":"normal"}}},
  {"slot":"widgets.sld.selected_feeder","mode":"const","v":{}}
 ]
}
$j$::jsonb, 'was topology_sld.py render():296 + _sld_node:205 + _build_bus:272; FULL lists per side (FE slices 4/10 itself); bus = legacy _build_bus (kw/kva/kvar Σ, pf=panel avg 4dp, first incomer voltage, coupler honest-null, label=panel name via panel_name context); selected_feeder={} is the FE own select state; energized/pf floors via config.feeder_overview')
ON CONFLICT (card_id) DO UPDATE SET handling_class=EXCLUDED.handling_class, roster_spec=EXCLUDED.roster_spec, notes=EXCLUDED.notes, updated_at=now();

-- ── card 161 : SLD Faults & Events Filter (topology_sld, same page/renderer as card 2) ──────
INSERT INTO card_fill_recipe (card_id, handling_class, roster_spec, notes)
SELECT 161, 'topology_sld', roster_spec, 'shares card-2 SLD recipe (renderers/__init__.py: topology_sld cards 2/161); renders honest-empty when its payload lacks widgets.sld'
FROM card_fill_recipe WHERE card_id = 2
ON CONFLICT (card_id) DO UPDATE SET roster_spec=EXCLUDED.roster_spec, notes=EXCLUDED.notes, updated_at=now();

-- ── card 5 : Real Time Monitoring feeder heatmap (panel_aggregate) ──────────────────────────
-- SECTION GROUPING (PCC-4 defect 2026-07-03): heatmap members group into CMD_V2's section vocabulary
-- (realTimeMonitoringConfig.ts SECTION_DEFS ids incomers/ups/bpdb/hhf), matched by member type / load_group /
-- name-prefix (incomer-/solar-incomer-/ups-/bpdb-/hhf-). INCOMERS INCLUDED: role='incoming' members MUST appear
-- in the incomers section (tonight _fill_heatmap used _reporting_pairs, which dropped them). Unmatched members go
-- to a DERIVED section labeled from their load_group — heatmapMetrics.ts deriveRosterFromHistory renders any id.
INSERT INTO card_fill_recipe (card_id, handling_class, roster_spec, notes) VALUES
(5, 'panel_aggregate', $j$
{
 "coverage_attach": "widgets._coverage",
 "slots": [
  {"slot":"heatmap.history","mode":"sections","scope":"members","role_filter":"all","reporting_only":false,
   "empty_members_rule":"zero-row members are KEPT as blank rows (per-LEAF degradation, 2026-07-03 sweep fix): a dark meter is a real entity with honest-null readings, exactly like the kept blank incomers; dropping it hid the whole GIC-05 section. Coverage stays the honest telemetry.",
   "group_by":"section_defs","replace":"wholesale",
   "match_by":["type","load_group","name_prefix"],
   "section_defs":[
    {"id":"incomers","label":"Incomers","types":["incomer","solar-incomer"],"load_groups":["incomer","solar"],"name_prefixes":["incomer-","solar-incomer-"],"roles":["incoming"]},
    {"id":"ups","label":"UPS Feeders","types":["ups"],"load_groups":["ups"],"name_prefixes":["ups-"]},
    {"id":"bpdb","label":"BPDB","types":["bpdb"],"load_groups":["bpdb"],"name_prefixes":["bpdb-"]},
    {"id":"hhf","label":"HHF Reactive","types":["hhf"],"load_groups":["hhf"],"name_prefixes":["hhf-"]}
   ],
   "incomers_included":true,
   "incomers_rule":"role='incoming' members MUST appear in the incomers section — never excluded from heatmap.history (PCC-4 defect 2026-07-03: _reporting_pairs dropped them)",
   "unmatched":{"policy":"derived_section","id":"slug_of_load_group","label":"load_group","note":"members matching no section_def group into a derived section labeled from their load_group; deriveRosterFromHistory renders any section id — group, never drop"},
   "sample":{"label":{"b":"ts_label","fmt":"HH:MM:SS"}},
   "section":{"id":"slug_of_group","label":"title_of_group"},
   "elements_key":"feeders",
   "element":{
    "id":{"b":"slug","a":"name"},"label":{"b":"attr","a":"name"},"shortLabel":{"b":"attr","a":"name"},
    "kw":{"b":"col","c":"active_power_total_kw","q":"power","r":2},
    "pf":{"b":"prefer_abs","cs":["kpi_true_pf","power_factor_total"],"r":3},
    "kva":{"b":"col","c":"apparent_power_total_kva","q":"power","r":2},
    "kvar":{"b":"col","c":"reactive_power_total_kvar","r":2,"keep_sign":true},
    "current":{"b":"col","c":"current_avg","r":1},"voltage":{"b":"col","c":"voltage_avg","r":1},
    "loadPct":{"b":"null","why":"no rated_kva on gic_*"},
    "iUnbalance":{"b":"col","c":"current_unbalance_pct","r":2}},
   "section_agg":{"totalKw":{"agg":"sum_magnitude","of":"kw","r":2},
                  "totalKvar":{"agg":"sum_magnitude","of":"kvar","r":2},
                  "totalKva":{"agg":"sum_magnitude","of":"kva","r":2}}},
  {"slot":"heatmap.selectedSampleIndex","mode":"const","v":0}
 ]
}
$j$::jsonb, 'was panel_aggregate.py _fill_heatmap:544 + _heatmap_sections:521 + _feeder_obj:499; ONE real sample replaces 12 fabricated Storybook samples wholesale; sections = CMD_V2 SECTION_DEFS vocabulary (incomers/ups/bpdb/hhf by type/load_group/name-prefix), INCOMERS INCLUDED (PCC-4 defect 2026-07-03: role=incoming members were dropped), unmatched members → derived section labeled from load_group (deriveRosterFromHistory renders any id) | 2026-07-03 policy fix: reporting_only=false — zero-row outgoing members are kept as blank rows (per-leaf degradation; GIC-05 section no longer vanishes).')
ON CONFLICT (card_id) DO UPDATE SET handling_class=EXCLUDED.handling_class, roster_spec=EXCLUDED.roster_spec, notes=EXCLUDED.notes, updated_at=now();

-- ── cards 12 & 13 : Energy Input & Distribution rail / Energy Flow (panel_aggregate) ────────
-- Re-derived FROM LIVE 2026-07-06: card 12 gained the rail.vm aggregates slot + sankey legend/rebuild/id_prefixes/
-- trunk_title_key; card 13 is NO LONGER a pure rail→flow rename of card 12 — it ADDED the flow.vm.kpis band binding
-- (source cutover_fix), so both rows are pinned verbatim here.
INSERT INTO card_fill_recipe (card_id, handling_class, roster_spec, notes) VALUES
(12, 'panel_aggregate', $j$
{
    "slots": [
        {
            "mode": "groups",
            "slot": "rail.vm.sources[]",
            "group": {
                "id": {
                    "a": "name",
                    "b": "slug"
                },
                "label": {
                    "a": "name",
                    "b": "attr"
                },
                "utilizationPct": {
                    "b": "null",
                    "why": "no group rated capacity on gic_* (legacy served None, never a placeholder 0)"
                }
            },
            "scope": "members",
            "element": {
                "id": {
                    "a": "name",
                    "b": "slug"
                },
                "kw": {
                    "b": "col",
                    "c": "active_power_total_kw",
                    "q": "power",
                    "r": 2
                },
                "kwh": {
                    "b": "delta",
                    "c": "active_energy_import_kwh",
                    "r": 1
                },
                "label": {
                    "a": "name",
                    "b": "attr"
                },
                "utilizationPct": {
                    "b": "null",
                    "why": "no per-feeder rated capacity on gic_*"
                }
            },
            "list_key": "meters",
            "template": "clone_first",
            "group_agg": {
                "totalKw": {
                    "r": 2,
                    "of": "kw",
                    "agg": "sum_magnitude"
                },
                "totalKwh": {
                    "r": 1,
                    "of": "kwh",
                    "agg": "sum_magnitude"
                }
            },
            "role_filter": "supply"
        },
        {
            "mode": "groups",
            "slot": "rail.vm.consumers[]",
            "group": {
                "$same_as_slot": "rail.vm.sources[]"
            },
            "scope": "members",
            "element": {
                "$same_as_slot": "rail.vm.sources[]"
            },
            "list_key": "meters",
            "template": "clone_first",
            "group_agg": {
                "$same_as_slot": "rail.vm.sources[]"
            },
            "role_filter": "load"
        },
        {
            "mode": "sankey_match",
            "slot": "rail.vm.sankey",
            "match": "slug_containment",
            "scope": "members",
            "legend": {
                "slot": "rail.vm.legend",
                "groups": [
                    {
                        "role": "supply",
                        "label": "Incomers"
                    },
                    {
                        "by": "load_group",
                        "role": "load",
                        "label": "Loads"
                    }
                ]
            },
            "rebuild": true,
            "link_match": "by_node_id",
            "id_prefixes": {
                "load": "meter-",
                "supply": "incomer-"
            },
            "trunk_value": "panel_kwh",
            "entity_value": null,
            "member_value": {
                "power": {
                    "b": "col",
                    "c": "active_power_total_kw",
                    "q": "power",
                    "r": 2
                },
                "energy": {
                    "b": "delta",
                    "c": "active_energy_import_kwh",
                    "r": 1
                }
            },
            "trunk_markers": {
                "kinds": [
                    "stage"
                ],
                "panel_self": true
            },
            "trunk_title_key": "stageTitle",
            "default_value_kind": "energy"
        },
        {
            "agg": {
                "allTotalKw": {
                    "of": "totalSuppliedKw",
                    "agg": "alias",
                    "why": "the 'All' rail row IS the supplied side in the design vm (default identity)"
                },
                "allTotalKwh": {
                    "of": "totalSuppliedKwh",
                    "agg": "alias"
                },
                "totalConsumedKw": {
                    "r": 2,
                    "of": "kw",
                    "agg": "sum_magnitude",
                    "role_filter": "load"
                },
                "totalSuppliedKw": {
                    "r": 2,
                    "of": "kw",
                    "agg": "sum_magnitude",
                    "role_filter": "supply"
                },
                "totalConsumedKwh": {
                    "r": 1,
                    "of": "kwh",
                    "agg": "sum_magnitude",
                    "role_filter": "load"
                },
                "totalSuppliedKwh": {
                    "r": 1,
                    "of": "kwh",
                    "agg": "sum_magnitude",
                    "role_filter": "supply"
                },
                "allUtilizationPct": {
                    "v": null,
                    "agg": "const",
                    "why": "no panel rated capacity on gic_* — honest-null (RailRow's utilizationPct<=0 guard renders the '—' badge for null too; display_dash excludes pct keys, so the null survives to the component)"
                }
            },
            "mode": "aggregates",
            "slot": "rail.vm",
            "scope": "members"
        }
    ],
    "coverage_attach": "widgets._coverage"
}
$j$::jsonb, 'was panel_aggregate.py _fill_meter_rosters:305 + _fill_sankey:358 + _node_role:339; chrome (color/kind/order) preserved via clone_first; ungrounded entity nodes/links honest-null (never duplicated panel total)')
ON CONFLICT (card_id) DO UPDATE SET handling_class=EXCLUDED.handling_class, roster_spec=EXCLUDED.roster_spec, notes=EXCLUDED.notes, updated_at=now();

INSERT INTO card_fill_recipe (card_id, handling_class, roster_spec, notes, source) VALUES
(13, 'panel_aggregate', $j$
{
    "slots": [
        {
            "mode": "groups",
            "slot": "flow.vm.sources[]",
            "group": {
                "id": {
                    "a": "name",
                    "b": "slug"
                },
                "label": {
                    "a": "name",
                    "b": "attr"
                },
                "utilizationPct": {
                    "b": "null",
                    "why": "no group rated capacity on gic_* (legacy served None, never a placeholder 0)"
                }
            },
            "scope": "members",
            "element": {
                "id": {
                    "a": "name",
                    "b": "slug"
                },
                "kw": {
                    "b": "col",
                    "c": "active_power_total_kw",
                    "q": "power",
                    "r": 2
                },
                "kwh": {
                    "b": "delta",
                    "c": "active_energy_import_kwh",
                    "r": 1
                },
                "label": {
                    "a": "name",
                    "b": "attr"
                },
                "utilizationPct": {
                    "b": "null",
                    "why": "no per-feeder rated capacity on gic_*"
                }
            },
            "list_key": "meters",
            "template": "clone_first",
            "group_agg": {
                "totalKw": {
                    "r": 2,
                    "of": "kw",
                    "agg": "sum_magnitude"
                },
                "totalKwh": {
                    "r": 1,
                    "of": "kwh",
                    "agg": "sum_magnitude"
                }
            },
            "role_filter": "supply"
        },
        {
            "mode": "groups",
            "slot": "flow.vm.consumers[]",
            "group": {
                "$same_as_slot": "flow.vm.sources[]"
            },
            "scope": "members",
            "element": {
                "$same_as_slot": "flow.vm.sources[]"
            },
            "list_key": "meters",
            "template": "clone_first",
            "group_agg": {
                "$same_as_slot": "flow.vm.sources[]"
            },
            "role_filter": "load"
        },
        {
            "mode": "sankey_match",
            "slot": "flow.vm.sankey",
            "match": "slug_containment",
            "scope": "members",
            "legend": {
                "slot": "flow.vm.legend",
                "groups": [
                    {
                        "role": "supply",
                        "label": "Incomers"
                    },
                    {
                        "by": "load_group",
                        "role": "load",
                        "label": "Loads"
                    }
                ]
            },
            "rebuild": true,
            "link_match": "by_node_id",
            "id_prefixes": {
                "load": "meter-",
                "supply": "incomer-"
            },
            "trunk_value": "panel_kwh",
            "entity_value": null,
            "member_value": {
                "power": {
                    "b": "col",
                    "c": "active_power_total_kw",
                    "q": "power",
                    "r": 2
                },
                "energy": {
                    "b": "delta",
                    "c": "active_energy_import_kwh",
                    "r": 1
                }
            },
            "trunk_markers": {
                "kinds": [
                    "stage"
                ],
                "panel_self": true
            },
            "trunk_title_key": "stageTitle",
            "default_value_kind": "energy"
        },
        {
            "agg": {
                "allTotalKw": {
                    "of": "totalSuppliedKw",
                    "agg": "alias",
                    "why": "the 'All' rail row IS the supplied side in the design vm (default identity)"
                },
                "allTotalKwh": {
                    "of": "totalSuppliedKwh",
                    "agg": "alias"
                },
                "totalConsumedKw": {
                    "r": 2,
                    "of": "kw",
                    "agg": "sum_magnitude",
                    "role_filter": "load"
                },
                "totalSuppliedKw": {
                    "r": 2,
                    "of": "kw",
                    "agg": "sum_magnitude",
                    "role_filter": "supply"
                },
                "totalConsumedKwh": {
                    "r": 1,
                    "of": "kwh",
                    "agg": "sum_magnitude",
                    "role_filter": "load"
                },
                "totalSuppliedKwh": {
                    "r": 1,
                    "of": "kwh",
                    "agg": "sum_magnitude",
                    "role_filter": "supply"
                },
                "allUtilizationPct": {
                    "v": null,
                    "agg": "const",
                    "why": "no panel rated capacity on gic_* — honest-null (RailRow's utilizationPct<=0 guard renders the '—' badge for null too; display_dash excludes pct keys, so the null survives to the component)"
                }
            },
            "mode": "aggregates",
            "slot": "flow.vm",
            "scope": "members"
        },
        {
            "agg": {
                "lossKw": {
                    "r": 2,
                    "by": "feederOutputKw",
                    "of": "sourceInputKw",
                    "agg": "difference",
                    "clamp_nonneg": true
                },
                "lossPct": {
                    "r": 2,
                    "by": "sourceInputKw",
                    "of": "lossKw",
                    "agg": "ratio_pct"
                },
                "efficiencyPct": {
                    "r": 2,
                    "by": "sourceInputKw",
                    "of": "feederOutputKw",
                    "agg": "ratio_pct"
                },
                "sourceInputKw": {
                    "r": 2,
                    "of": "kw",
                    "agg": "sum_magnitude",
                    "role_filter": "supply"
                },
                "feederOutputKw": {
                    "r": 2,
                    "of": "kw",
                    "agg": "sum_magnitude",
                    "role_filter": "load"
                }
            },
            "mode": "aggregates",
            "slot": "flow.vm.kpis",
            "scope": "members",
            "element": {
                "kw": {
                    "b": "col",
                    "c": "active_power_total_kw",
                    "q": "power",
                    "r": 2
                }
            }
        }
    ],
    "coverage_attach": "widgets._coverage"
}
$j$::jsonb, 'Card 12/13 energy flow — ADDED flow.vm.kpis band binding (was shipping FABRICATED Storybook seed eff=96.58/loss=52.69/sourceInput=1543.59). Binds from the SAME member aggregate the sankey uses: feederOutputKw=Sigma load power, sourceInputKw=Sigma supply power, lossKw=difference(in-out clamp>=0), efficiencyPct=ratio_pct(out/in), lossPct=ratio_pct(loss/in). PCC-Panel-1 supply (solar incomers dark + transformer SCH empty) reads null -> in/loss/eff honest-null (no fabricated efficiency). Adds reducers.difference + ratio_pct (generic, late-pass).', 'cutover_fix')
ON CONFLICT (card_id) DO UPDATE SET handling_class=EXCLUDED.handling_class, roster_spec=EXCLUDED.roster_spec, notes=EXCLUDED.notes, source=EXCLUDED.source, updated_at=now();

-- ── card 23 : PQ Issues KPI strip (panel_aggregate) ─────────────────────────────────────────
INSERT INTO card_fill_recipe (card_id, handling_class, roster_spec, notes) VALUES
(23, 'panel_aggregate', $j$
{
 "coverage_attach": "widgets._coverage",
 "thresholds": {"iThd_floor_pct":8.0,"vThd_floor_pct":5.0,"pfGap_floor_pct":5.0,"neutral_floor_a":30.0},
 "slots": [
  {"slot":"strip.stats","mode":"aggregates","scope":"members","role_filter":"load","reporting_only":true,
   "element":{
    "id":{"b":"slug","a":"name"},"panel":{"b":"attr","a":"name"},"table":{"b":"attr","a":"table"},
    "kw":{"b":"col","c":"active_power_total_kw","q":"power","r":2},
    "pf":{"b":"prefer_abs","cs":["kpi_true_pf","power_factor_total"],"r":3},
    "truePf":{"b":"col","c":"kpi_true_pf","r":3},
    "pfGap":{"b":"col","c":"pf_gap_vs_full_load","r":2},
    "iThd":{"b":"phase_mean","cs":["thd_current_r_pct","thd_current_y_pct","thd_current_b_pct"],"r":2},
    "vThd":{"b":"phase_mean","cs":["thd_voltage_r_pct","thd_voltage_y_pct","thd_voltage_b_pct"],"r":2},
    "iThdPk":{"b":"null","why":"no peak-THD column on gic_*"},
    "h3":{"b":"null","why":"no 3rd-harmonic column on gic_*"},
    "h5":{"b":"col","c":"harmonic_5th_pct","r":2},"h7":{"b":"col","c":"harmonic_7th_pct","r":2},
    "kFactor":{"b":"null","why":"no k-factor column on gic_*"},
    "neutralA":{"b":"col","c":"current_neutral","r":1},
    "status":{"b":"status","policy":"pf_floors","vocab":["success","warning","danger"]},
    "driver":{"b":"null","why":"diagnosis label is not a neuract column"},
    "driverKey":{"b":"null","why":"diagnosis label is not a neuract column"}},
   "agg":{"worstIThd":{"agg":"argmax","of":"iThd"},
          "worstVThd":{"agg":"argmax","of":"vThd"},
          "iThd":{"agg":"count_breach","of":"iThd","floor":8.0},
          "vThd":{"agg":"count_breach","of":"vThd","floor":5.0},
          "pfGap":{"agg":"count_breach","of":"pfGap","floor":5.0},
          "neutral":{"agg":"count_breach","of":"neutralA","floor":30.0},
          "total":{"agg":"sum_of","keys":["iThd","vThd","pfGap","neutral"]}}}
 ]
}
$j$::jsonb, 'was panel_aggregate.py _fill_worst_of:450 + _pq_member:250 + _argmax:468 + _count_breach:474; floors editable here (mirror of thresholds key)')
ON CONFLICT (card_id) DO UPDATE SET handling_class=EXCLUDED.handling_class, roster_spec=EXCLUDED.roster_spec, notes=EXCLUDED.notes, updated_at=now();

-- ── cards 24 / 26 / 27 : PQ rosters (panel_aggregate; same pq_member element as card 23) ────
INSERT INTO card_fill_recipe (card_id, handling_class, roster_spec, notes)
SELECT 24, 'panel_aggregate',
 jsonb_build_object('coverage_attach','widgets._coverage','slots', jsonb_build_array(jsonb_build_object(
   'slot','timeline.periods[*].panels[]','mode','elements','scope','members','role_filter','load',
   'reporting_only',true,'repeat','snapshot_per_period',
   'element',(roster_spec->'slots'->0->'element')))),
 'was panel_aggregate.py _fill_panels_array:440 per period; snapshot repeated per bucket (honest degrade until per-bucket history wired)'
FROM card_fill_recipe WHERE card_id = 23
ON CONFLICT (card_id) DO UPDATE SET roster_spec=EXCLUDED.roster_spec, notes=EXCLUDED.notes, updated_at=now();

INSERT INTO card_fill_recipe (card_id, handling_class, roster_spec, notes)
SELECT 26, 'panel_aggregate',
 jsonb_build_object('coverage_attach','widgets._coverage','slots', jsonb_build_array(jsonb_build_object(
   'slot','table.period.panels[]','mode','elements','scope','members','role_filter','load',
   'reporting_only',true,'element',(roster_spec->'slots'->0->'element')))),
 'was panel_aggregate.py _fill_panels_array:440 (table root)'
FROM card_fill_recipe WHERE card_id = 23
ON CONFLICT (card_id) DO UPDATE SET roster_spec=EXCLUDED.roster_spec, notes=EXCLUDED.notes, updated_at=now();

INSERT INTO card_fill_recipe (card_id, handling_class, roster_spec, notes)
SELECT 27, 'panel_aggregate',
 jsonb_build_object('coverage_attach','widgets._coverage','slots', jsonb_build_array(jsonb_build_object(
   'slot','signature.period.panels[]','mode','elements','scope','members','role_filter','load',
   'reporting_only',true,'element',(roster_spec->'slots'->0->'element')))),
 'was panel_aggregate.py _fill_panels_array:440 (signature root)'
FROM card_fill_recipe WHERE card_id = 23
ON CONFLICT (card_id) DO UPDATE SET roster_spec=EXCLUDED.roster_spec, notes=EXCLUDED.notes, updated_at=now();

-- ── narrative cards 8 / 19 / 25 / 28 : envelope facts ONLY (narrative_ai.py is KEPT) ────────
INSERT INTO card_fill_recipe (card_id, handling_class, roster_spec, notes)
SELECT v.card_id, 'narrative_ai', $j$
{"mode":"narrative","slots":[],
 "containers":["widgets.ai_summary","data.ai_summary","$top"],
 "fields":{"badge":"prejudged_python_never_ai","text":"ai_narrated_single_sentence"},
 "fallback":"deterministic_template_verbatim_on_any_model_failure"}
$j$::jsonb,
 'renderer stays narrative_ai.py + _story/ (LLM path, per Inventory A KEEP list); this row is the envelope contract shown to the AI + gate'
FROM (VALUES (8),(19),(25),(28)) AS v(card_id)
ON CONFLICT (card_id) DO UPDATE SET roster_spec=EXCLUDED.roster_spec, notes=EXCLUDED.notes, updated_at=now();

-- ── FE card_rendering section RETIRED 2026-07-12 (unused-code audit): card_rendering had NO runtime reader
--    and was DROPPED (db/retire_unused_tables_20260712.sql; snapshot archive/db_snapshots_20260712/).
--    The rows are preserved (block-commented) as the Inventory-B authoring record.
/*
-- ── FE card_rendering seeds (Inventory B facts) ─────────────────────────────────────────────
INSERT INTO card_rendering (card_id, page_key, render_kind, envelope_kind, component_alias, payload_shape_category, payload_single_key, mapper_key, state_schema, state_defaults, date_control, honest_blank_reason) VALUES
 (2,  'panel-overview-shell/overview-sld-3d',        'special','topology',    'EnergySingleLineDiagram','envelope_only','widgets',NULL,NULL,NULL,'{"kind":"none"}',NULL),
 (5,  'panel-overview-shell/real-time-monitoring',   'compose', NULL,         'RealTimeHeatmapSection','single_unwrap','heatmap','mapFrame','{"metric":"string"}','{"metric":"$heatmap.metric"}','{"kind":"none"}',NULL),
 (6,  'panel-overview-shell/real-time-monitoring',   'compose', NULL,         'LiveScrubberBar','single_unwrap','scrubber',NULL,'{"liveMode":"boolean"}','{"liveMode":true}','{"kind":"none"}','callbacks stubbed (deferred interdependency)'),
 (8,  'panel-overview-shell/real-time-monitoring',   'special','narrative_ai','AiSummary','envelope_only',NULL,NULL,NULL,NULL,'{"kind":"none"}','honest-blank when ai_summary missing'),
 (12, 'panel-overview-shell/energy-distribution',    'components',NULL,       NULL,'single_unwrap','rail',NULL,NULL,NULL,'{"kind":"none"}',NULL),
 (13, 'panel-overview-shell/energy-distribution',    'components',NULL,       NULL,'single_unwrap','flow',NULL,NULL,NULL,'{"kind":"none"}',NULL),
 (23, 'panel-overview-shell/harmonics-pq',           'components',NULL,       NULL,'single_unwrap','strip',NULL,NULL,NULL,'{"kind":"none"}',NULL),
 (24, 'panel-overview-shell/harmonics-pq',           'components',NULL,       NULL,'single_unwrap','timeline',NULL,NULL,NULL,'{"kind":"none"}',NULL),
 (26, 'panel-overview-shell/harmonics-pq',           'components',NULL,       NULL,'single_unwrap','table',NULL,NULL,NULL,'{"kind":"none"}',NULL),
 (27, 'panel-overview-shell/harmonics-pq',           'components',NULL,       NULL,'single_unwrap','signature',NULL,NULL,NULL,'{"kind":"none"}',NULL),
 (28, 'individual-feeder-meter-shell/overview',      'special','narrative_ai','AiSummary','envelope_only',NULL,NULL,NULL,NULL,'{"kind":"none"}',NULL),
 (60, 'diesel-generator-asset-dashboard/engine-cooling','special','asset_3d', 'ComingSoon3D','envelope_only','object',NULL,NULL,NULL,'{"kind":"none"}','object=null honest V48 state'),
 (160,'panel-overview-shell/real-time-monitoring',   'compose', NULL,         'RealTimeMonitoringFooter',NULL,NULL,'mapAggregateSocketToSnapshot','{"idx":"number","liveMode":"boolean"}','{"idx":0,"liveMode":true}','{"kind":"none"}','payload_required=false; all props derived from liveFrame')
ON CONFLICT (card_id) DO UPDATE SET page_key=EXCLUDED.page_key, render_kind=EXCLUDED.render_kind,
  envelope_kind=EXCLUDED.envelope_kind, component_alias=EXCLUDED.component_alias,
  payload_shape_category=EXCLUDED.payload_shape_category, payload_single_key=EXCLUDED.payload_single_key,
  mapper_key=EXCLUDED.mapper_key, state_schema=EXCLUDED.state_schema, state_defaults=EXCLUDED.state_defaults,
  date_control=EXCLUDED.date_control, honest_blank_reason=EXCLUDED.honest_blank_reason;

-- backfill the ~58 FILL cards from the existing card_render_map (additive; inventoried rows above win)
INSERT INTO card_rendering (card_id, page_key, render_kind, fill_module)
SELECT crm.card_id, crm.page_key, 'fill', crm.fill_module
FROM card_render_map crm
WHERE crm.fill_module IS NOT NULL
ON CONFLICT (card_id) DO NOTHING;

-- backfill remaining direct-render cards as 'components'
INSERT INTO card_rendering (card_id, page_key, render_kind)
SELECT ch.card_id, ch.page_key, 'components'
FROM card_handling ch
ON CONFLICT (card_id) DO NOTHING;

COMMIT;
*/
