-- db/patch_rtm_card7_policy.sql — RTM page-01 POLISH fixes at the DB layer (2026-07-03 sweep defects).
--
-- (1) card 7 (Overview Rail / RealTimeMonitoringRail) gets a card_fill_recipe row so the GENERIC roster interpreter
--     serves it (it was the recipe-less legacy fallback, which left three defects):
--       · railVM.aiSummaryText     = honest-null CONST — the Storybook default string ("UPS-06 leads at 244 kW …")
--                                    survived byte-identical as chrome and rendered another plant's narrative via
--                                    <AiSummary>. There is no grounded per-rail narrator slot, so the leaf honest-blanks
--                                    (AiSummary renders an empty paragraph; card 8 carries the real grounded summary).
--       · railVM.supply.consumedHint = honest-null CONST (whole object) — the legacy emit left a partially-null object
--                                    ({leftKw:null, consumedPct:null, percentUnit:'%'}) and SupplyCard's fmt(null)
--                                    crashed the card to its CmdCard Boundary. Card 9 proves the honest form is
--                                    consumedHint:null (hasConsumedHint guard hides the row).
--       · railVM.supply.denominator = honest-null CONST — no real contracted-capacity source exists in neuract (the L2
--                                    const 2700 was a fabrication); display_dash type-proves it to '—' like card 9.
--       · railVM.supply.value       = Σ|kW| over reporting LOAD-side members (mirrors card 9).
--       · railVM.supply.breakdown   = the BARE per-group aggregate roster (sections mode, wrap_sample=false) — one
--                                    entry per DERIVED load_group section (GIC-08..11 — the plant's real topology; the
--                                    seed's UPS/BPDB/HHF labels each bound to the same panel total were a fabricated
--                                    split). Same spec as card 9's proven breakdown.
--       · railVM.trend.series       = the member-rolled bucketed kW series (the NEW generic `series` roster mode —
--                                    per-bucket Σ|kW| across load-side members' own reads; the panel's own device table
--                                    carries no electrical, so the single-meter executor honestly returned []).
--     quickStats / bottomStats keep filling from the executor's declared fields over the fleet agg-row (unchanged).
--
-- (2) card 5 (RTM heatmap) roster policy: reporting_only -> false on the heatmap.history sections slot. PER-LEAF
--     degradation (the V48 rule): zero-row members are KEPT as blank rows exactly like the zero-row incomers already
--     were — the 5 dark outgoing members (incl. the whole GIC-05 section) no longer vanish from the roster; their
--     reading leaves are honest-null. Coverage (23/28 partial) stays as telemetry.
--
-- (3) app_config display.unit_sibling_suffixes — the UNIT-LIKE sibling vocabulary for host/display_dash.py (the
--     mechanism gap: honest-dash fired only next to a literal 'unit' key; percentUnit-style siblings left display
--     scalars null and unguarded fmt() sites crashed). Suffix match, code default ["unit"].
--
-- Idempotent: card_fill_recipe upserts; jsonb_set / INSERT..ON CONFLICT elsewhere.

BEGIN;

INSERT INTO card_fill_recipe (card_id, handling_class, roster_spec, notes, source)
VALUES (
  7,
  'panel_aggregate',
  '{
    "coverage_attach": "widgets._coverage",
    "slots": [
      {
        "mode": "series",
        "slot": "railVM.trend.series",
        "scope": "members",
        "role_filter": "load",
        "column": "active_power_total_kw",
        "reduce": "sum_magnitude",
        "sampling": "hourly"
      },
      {
        "mode": "aggregates",
        "slot": "railVM.supply",
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
        "slot": "railVM.supply.breakdown",
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
      },
      {
        "mode": "const",
        "slot": "railVM.aiSummaryText",
        "v": null
      }
    ]
  }'::jsonb,
  'RTM Overview Rail (2026-07-03 sweep fix): aiSummaryText honest-null (Storybook seed narrative leaked byte-identical); consumedHint whole-object null (partial-null object crashed SupplyCard fmt(null) to the card Boundary); denominator honest-null (L2 const 2700 was fabricated); breakdown = derived load_group sections (seed UPS/BPDB/HHF labels each carried the same panel total — a fabricated split); trend.series = member-rolled bucketed kW (generic series mode — the panel device table has no electrical).',
  'CMD_V2 realTimeRailViewModel.ts buildPanelVM + RealTimeMonitoringRail.tsx / RealTimeMonitoringRailCards.tsx; card 9 recipe (proven breakdown/consumedHint form); legacy ems_exec/renderers/panel_aggregate.py _rolled_series (the series-mode ancestor)'
)
-- SUPERSEDED for re-runs 2026-07-06: the live card-7 recipe has since evolved (owned by db/seed_agentb_fill_fixes.sql,
-- live source = 'seed_agentb_fill_fixes.sql'); DO NOTHING so a re-run of this patch never regresses it.
ON CONFLICT (card_id) DO NOTHING;

-- (2) card 5: keep zero-row members as blank rows (per-LEAF degradation, matching the kept blank incomers)
UPDATE card_fill_recipe
SET roster_spec = jsonb_set(
      jsonb_set(roster_spec, '{slots,0,reporting_only}', 'false'::jsonb),
      '{slots,0,empty_members_rule}',
      '"zero-row members are KEPT as blank rows (per-LEAF degradation, 2026-07-03 sweep fix): a dark meter is a real entity with honest-null readings, exactly like the kept blank incomers; dropping it hid the whole GIC-05 section. Coverage stays the honest telemetry."'::jsonb),
    notes = notes || ' | 2026-07-03 policy fix: reporting_only=false — zero-row outgoing members are kept as blank rows (per-leaf degradation; GIC-05 section no longer vanishes).',
    updated_at = now()
WHERE card_id = 5
  AND roster_spec->'slots'->0->>'slot' = 'heatmap.history'
  AND roster_spec->'slots'->0->>'reporting_only' = 'true';

-- (3) the UNIT-LIKE sibling vocabulary for the serve-boundary honest-dash (host/display_dash.py)
INSERT INTO app_config (key, value, data_type, section, note)
VALUES ('display.unit_sibling_suffixes', '["unit"]', 'json', 'display',
        'honest-dash unit-adjacency vocabulary (suffix match, lowercase): a scalar null is dashed when ANY sibling key equals or ends with a listed suffix — covers unit + camelCase percentUnit/valueUnit (the 2026-07-03 fmt(null) boundary-crash gap)')
ON CONFLICT (key) DO UPDATE
SET value = EXCLUDED.value, data_type = EXCLUDED.data_type, section = EXCLUDED.section, note = EXCLUDED.note,
    updated_at = now();

COMMIT;
