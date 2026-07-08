# Equipment wiring — SUMMARY (2026-07-08)

The `cmd_equipment` registry (copied in full into `cmd_catalog.equipment`, 22 tables) is wired into the pipeline:
richer directed topology, real breaker/rating/threshold facts for the AI layers, human-alias asset resolution, and a
3D kitpreview fallback. Everything honest-degrades: an asset with no equipment rows produces byte-identical behavior
to the pre-wiring pipeline. All reads ride ONE fail-open door (`data/equipment/*`, :5432-local, never the :5433
tunnel), enforced by `tests/test_equipment_disposition.py`.

## Streams
- **Scaffold** — `data/equipment/__init__.py` + `db.py` (eq_q / mfm_by_table / unique_mfm_row; dup-table twins → None).
- **A topology** — `bridge.py` (table_name-only id bridge, per-row identity gate, feeds/fed_by) + `edges.py`
  (bay-anchored panel rosters from `equipment.feeder`, two-sided guard, per-panel allowlist) merged into
  `data/registry/lt_mfm.py` + `registries/neuract/members.py`. Knobs `equipment.topology.enabled` (**off**) +
  `equipment.topology.panel_allowlist` ({}); unbridged/knob-off → byte-identical neuract-mirror behavior. 23 tests.
- **B ratings/derivations** — `ratings.py` (breaker_rating/breaker_state, rtm_bands_for_asset, voltage_deviation_pct)
  + `ems_exec/derivations/breaker.py` `overload_pct` (max-phase basis, empty-denominator gate) registered in the
  derivations registry, SOURCE-GATED by `equipment.derivations.enabled` (**off**) so certified prompts never see it
  until enabled; emit.py hides breaker-based fns tri-state (known-empty hides, unknown never does). 72 `consts.rtm_*`
  rows + `derivation_binding` row seeded. ~26 tests.
- **C AI context** — `layer2/emit/equipment_facts.py`: EQUIPMENT / BREAKER / RTM STATUS BANDS / ENERGY REGISTER fact
  lines in the L2 user message (each '' on miss; never-rescale clause inline) + PANEL MEMBERS per-member
  `aka=|load_profile=|breaker_a=` suffix; 1b candidates gain `aka`/`loc` columns (idx 10/11) + a 5th listing column +
  unique-alias resolve (collision NEVER pins; canonical name stays the only return contract; asset_system.md rule).
  Prompt rules: R8-ROLE bay_role sentence, R10 rtm-const legal source, morphmap aka-display/threshold-morph rules.
  Knobs `equipment.facts.enabled` (**on**) + `equipment.alias.enabled` (**on**). 10 tests.
- **D 3D** — `kitpreview.py` + asset_3d 5th tier (viewer_rule most-specific-first → cat_asset; glb_file against the
  media base, file-existence gate, honest GAPS cause; `template` passed through). Knobs `equipment.kitpreview.enabled`
  (**off**) + `media_base` (''). 15 tests. Ops: rsync the GLBs into the media root, then enable.
- **E cleanup** — contract.md / panel_members.py stale claims fixed; single-door + knob-mirror tests.

## Per-table disposition (all 22)
| table | rows | disposition |
|---|---|---|
| mfm | 303 | **USED** A/B/C: the bridge node (table_name → role/section/zone/load_profile/scales/aliases) |
| feeder | 194 | **USED** A: the directed feed graph (bay-anchored rosters + feeds/fed_by facts) |
| equipment | 182 | **USED** A: identity nodes (equipment_id/reference_id gate) + B: rtm panel-type hop |
| breaker | 301 | **USED** B/C: rating_a overload denominator + BREAKER facts line (168 rated; NULL stays hidden) |
| rtm_threshold | 18 | **USED** B/C: RTM status bands (per-equipment first, panel-type default) + consts.rtm_* |
| equipment_config | 120 | **PARTIAL** B: rated_kva already rides public.asset_nameplate; voltage_statutory_deviation_pct (7) via ratings.voltage_deviation_pct. All other columns are 100% NULL upstream — documented, NOT wired (no data to wire) |
| core_paneltype | 3 | **USED** B: the rtm band panel-type key |
| core_assettype | 15 | **USED** (indirect): class taxonomy already mirrored in asset_nameplate/asset classes |
| nameplate | 432 | **SKIP (documented)**: OCR-harvested nameplate scans; public.asset_nameplate (already consumed) is the curated derivation of it |
| asset_meter | 29 | **SKIP**: BMS-side meter registry — no EMS card binds BMS meters today; revisit with a BMS page |
| bms_meter / bms_meter_limit | 38/15 | **SKIP**: same BMS scope |
| asset_threshold | 6 | **SKIP**: superseded by rtm_threshold for the RTM pages; 6 rows cover no EMS metric family |
| data_source | 2 | **USED** A (indirect): ds-scoping in the identity gate |
| kitpreview_app_kv/asset_rules/cat_asset/cat_group/combo/preset/version/viewer_rule | ~134 | **USED** D: the 3D fallback (viewer rules → cat_asset GLB + scene overrides + KPI template) |

## Knobs (app_config, all with code-default mirrors)
`equipment.topology.enabled=off` · `equipment.topology.panel_allowlist={}` · `equipment.derivations.enabled=off` ·
`equipment.kitpreview.enabled=off` · `equipment.kitpreview.media_base=''` · `equipment.facts.enabled=on` ·
`equipment.alias.enabled=on` · `consts.rtm_*` (72 rows).

**Enablement path**: facts+alias are live (additive AI context). topology/derivations/kitpreview are staged
kill-switch-off; enable = flip the row (+ allowlist a panel for topology; rsync GLBs for kitpreview) after a live
fire on the target pages. This is the certified-path-first rollout the design critic required.
