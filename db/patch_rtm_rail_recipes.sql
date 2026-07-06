-- db/patch_rtm_rail_recipes.sql — RTM rail piece-VM binding (2026-07-03, the 'piece unavailable' fix at the DB layer).
--
-- (1) card 9 (Total Feeder Consumption / SupplyCard) gets a card_fill_recipe row so the generic roster interpreter
--     binds its supply VM from the panel's REAL members:
--       · supply.value            = Σ|kW| over the reporting LOAD-side members (the consumption side; incomers are
--                                   supply and would double-count — mirrors CMD_V2 consumptionKw()).
--       · supply.breakdown        = the BARE per-group aggregate roster (sections mode, wrap_sample=false): one entry
--                                   per DERIVED load_group section (GIC-05/08/09/10/11 for PCC-4 — the plant's real
--                                   topology; the seed's UPS/BPDB/HHF SECTION_DEFS are design fiction here), each with
--                                   its own Σ|kW|, unit chrome, and a cycled swatch color (the harvested Storybook
--                                   palette #237492/#bc9e44/#bd6184 — presentation only).
--       · supply.denominator      = honest-null CONST: there is NO real contracted-capacity source in neuract
--                                   (SECTION_CONTRACT_KW in realTimeMonitoringConfig.ts is a design constant; the L2
--                                   emission's const 2700 was a fabrication and is overridden by recipe truth).
--       · supply.consumedHint     = honest-null CONST: derived entirely from the denominator, so with no real contract
--                                   it must be ABSENT — SupplyCard renders the hint row only when the hint object
--                                   exists (fmt(null leftKw) was the 'piece unavailable' crash).
--
-- (2) card 11 (Quick Stats) card_data_recipe: the 'Current Unbalance %' tile becomes a RAW read of the REAL gic_*
--     column current_unbalance_pct (was kind=derived metric=iUnbalance, which the AI bound to a bogus neutralCurrent
--     fn over absent current_r/y/b columns → honest-null tile rendering the string 'null'). The executor's fleet
--     agg-row rolls it as the MEAN over reporting load-side members (real, honest; the CMD_V2 note's worst-case max
--     is a future agg-vocabulary refinement).
--
-- Idempotent: card_fill_recipe upserts; card_data_recipe UPDATE rewrites the same arrays.

BEGIN;

INSERT INTO card_fill_recipe (card_id, handling_class, roster_spec, notes, source)
VALUES (
  9,
  'panel_aggregate',
  '{
    "coverage_attach": "widgets._coverage",
    "slots": [
      {
        "mode": "aggregates",
        "slot": "supply",
        "scope": "members",
        "role_filter": "load",
        "element": {
          "kw": {"b": "col", "c": "active_power_total_kw", "q": "power", "r": 2}
        },
        "agg": {
          "value":        {"agg": "sum_magnitude", "of": "kw", "r": 2},
          "denominator":  {"agg": "const", "v": null},
          "consumedHint": {"agg": "const", "v": null}
        }
      },
      {
        "mode": "sections",
        "slot": "supply.breakdown",
        "scope": "members",
        "role_filter": "load",
        "reporting_only": true,
        "group_by": "section_defs",
        "section_defs": [],
        "unmatched": {"policy": "derived_section", "label": "load_group"},
        "wrap_sample": false,
        "element": {
          "kw": {"b": "col", "c": "active_power_total_kw", "q": "power", "r": 2}
        },
        "section_agg": {
          "value": {"agg": "sum_magnitude", "of": "kw", "r": 2}
        },
        "entry": {"unit": "kW"},
        "entry_palette": {"key": "color", "values": ["#237492", "#bc9e44", "#bd6184"]}
      }
    ]
  }'::jsonb,
  'RTM rail SupplyCard piece VM (2026-07-03 fix): breakdown = derived load_group sections (real topology; UPS/BPDB/HHF seed labels are design fiction for this plant); denominator + consumedHint honest-null consts (no real contracted-capacity source; fmt(null) in SupplyCard was the piece-unavailable crash; the L2 const 2700 was fabricated).',
  'CMD_V2 realTimeRailViewModel.ts buildPanelVM (consumptionSections/consumptionKw) + RealTimeMonitoringRailCards.tsx SupplyCard'
)
ON CONFLICT (card_id) DO UPDATE
SET handling_class = EXCLUDED.handling_class,
    roster_spec    = EXCLUDED.roster_spec,
    notes          = EXCLUDED.notes,
    source         = EXCLUDED.source,
    updated_at     = now();

UPDATE card_data_recipe
SET fields = (
      SELECT jsonb_agg(
        CASE WHEN f->>'metric' = 'iUnbalance'
             THEN '{"kind":"raw","role":"kpi","unit":"%","label":"Current Unbalance %","metric":"current_unbalance_pct","filters_table":false}'::jsonb
             ELSE f END)
      FROM jsonb_array_elements(fields) f),
    reconciled_fields = (
      SELECT jsonb_agg(
        CASE WHEN f->>'metric' = 'iUnbalance'
             THEN '{"kind":"raw","role":"kpi","unit":"%","label":"Current Unbalance %","metric":"current_unbalance_pct","filters_table":false}'::jsonb
             ELSE f END)
      FROM jsonb_array_elements(reconciled_fields) f),
    notes = 'Panel rollup tiles: Voltage = avg over non-incomer feeders; Current Unbalance = RAW gic_* current_unbalance_pct (fleet agg-row mean over reporting load members — was derived iUnbalance, which the AI bound to a bogus neutralCurrent fn and honest-nulled; CMD_V2 worst-case max is a future agg refinement); PF = avg across panel. Backend consumers/real_time_monitoring/pcc_panel.py rollup.quickStats.'
WHERE card_id = 11;

COMMIT;
