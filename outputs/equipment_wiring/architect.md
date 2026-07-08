# Equipment-schema wiring — INTEGRATION DESIGN (architect stream)

Status: DESIGN COMPLETE 2026-07-08. Inputs: census.md, seams.md, cmdv2_semantics.md, ai_context_audit.md
(all in this directory). Seam anchors re-verified against the working tree before writing:
user_message.py:251/277 fact loop + panel_members_block; asset_facts.py nameplate_line/data_window_line
('' on miss); emit.py:38/68 _recovery_library_block nameplate-prefix filter; derivations/registry.py _d/_COMPAT/
_NAMEPLATE; executor/members.py select() supply==incoming / load==everything-else (coupler would count as load —
handled below); lt_mfm.py parent_ids/outgoing_edges/outgoing_feeders + _CACHE; neuract/members.py _edge_targets/
incomers_of/outgoers_of; asset_candidates positional rows + asset_resolve by_name/by_norm/resolve_name;
metadata/asset_3d.py 4-tier _resolve_object; renderers/asset_3d.py _asset_preset honors obj.default_overrides;
db_client.q + config.databases.CMD_CATALOG + app_config.cfg(key, default).

## Scaffold (created BEFORE launching A/B/D, then FROZEN — no stream edits it)

data/equipment/__init__.py — package docstring only, no imports:
  "LOCAL cmd_catalog `equipment` schema readers (:5432 ONLY — never the :5433 tunnel).
   Rules for every module here: (1) bridge id spaces ONLY via table_name (equipment.mfm.id
   != canonical lt_mfm.id); (2) fail-open — DB error / missing row -> None/''/{} so callers
   stay byte-identical to today; (3) facts only — energy_direction/energy_scale/power_scale
   are surfaced, NEVER applied to readings. Modules: db (the one accessor), bridge+edges
   (stream A), ratings (stream B), kitpreview (stream D)."

data/equipment/db.py — the ONE door to the schema (reuses the canonical helper):
  from config.databases import CMD_CATALOG
  from data.db_client import q
  def eq_q(sql): return q(CMD_CATALOG, sql)          # raises like q; call sites wrap fail-open
  _CACHE = {}
  def mfm_by_table() -> dict[str, list[dict]]        # ALL equipment.mfm rows keyed by table_name,
      # dups preserved (alias building needs them). Row keys: id,name,role,section,zone,
      # load_profile,asset_category,rated_capacity_kva,energy_direction,energy_scale,
      # power_scale,equipment_id,reference_id,data_source_id. Built once per process via one
      # SELECT; {} on any DB error (never raises).
  def unique_mfm_row(table_name) -> dict|None        # THE bridge: the single equipment.mfm row
      # for a canonical table_name; None when absent OR duplicated (18 dup groups = ambiguous
      # dual-view pairs -> honest skip) OR DB down.
  def clear_cache()                                  # tests only
  Single-door rule: no other file may contain `FROM equipment.` SQL except data/equipment/*.py
  and db/seed_equipment_*.sql — enforced by stream E's test.

## Streams (A,B,D parallel → C → E). Exclusive file ownership.

### A — topology (equipment.feeder graph, kill-switch OFF)
Owns: data/equipment/bridge.py, data/equipment/edges.py, data/registry/lt_mfm.py (edit),
registries/neuract/members.py (edit), db/seed_equipment_topology.sql, tests/test_equipment_topology.py,
outputs/equipment_wiring/stream_a.md.
- bridge.py API (PINNED for B/C/D):
    eq_row_for_table(table_name)->dict|None   (unique row + eq_mfm_id/equipment_id/reference_id)
    aliases_for_table(table_name)->list[str]  (dup twins included; [] on miss)
    alias_index()->dict[norm, list[table_name]]  (len>1 == collision -> ambiguous)
    equipment_node(equipment_id)->dict|None   (name,key,distribution_panel,metered,group,
                                               asset_type_code,panel_type_code)
    feeds_fed_by(equipment_id)->(fed_by_names, feeds_names)   (kind='feed' only)
- edges.py: panel_edges(panel_table, direction)->list[canonical mfm ids]|None; None = knob-off/
  unbridgeable/guard-failed -> caller falls back to today's source. Chain: panel table ->
  unique_mfm_row -> equipment_id node -> feeder rows (kind='feed' ONLY, couplers excluded —
  select() would count a coupler as load) -> endpoint node -> equipment.mfm WHERE equipment_id=node
  (unique-table rows only) -> table_name -> canonical id. COVERAGE GUARD: equipment member set must
  be a superset of the LOCAL mirror set for that panel+direction, else None (strictly-additive rule).
  pcc_panel_N have 0 equipment.mfm rows -> direct bridge miss -> automatic mirror fallback.
- Plug points (the 5 seam functions ONLY): lt_mfm.parent_ids/outgoing_edges/outgoing_feeders and
  members._edge_targets/incomers_of consult edges.panel_edges first; role tagging stays in the
  callers (_member_row(mid, role-by-direction)) so member_scope/role_filter semantics are untouched.
- Knob: equipment.topology.enabled = "off" (latched at first use; per-process caches stay consistent).
- No import cycle: edges.py reads registry_lt_mfm_outgoing directly via db_client for the guard.

### B — ratings/limits/derivations
Owns: data/equipment/ratings.py, ems_exec/derivations/breaker.py, ems_exec/derivations/registry.py (edit),
layer2/emit/emit.py (edit: extend prefix filter "breaker:" == "nameplate:" semantics + hide breaker:* fns
when breaker_rating(asset) is None; unknown never hides), db/seed_equipment_ratings.sql,
tests/test_equipment_ratings.py, outputs/equipment_wiring/stream_b.md.
- ratings.py API (PINNED for C):
    breaker_rating(asset_table)->dict|None    {rating_a: float|None, breaker_type, glb_node, panel_key}
    rtm_bands_for_asset(asset_table)->dict|None  {panel_type, bands:{metric:{low_max,normal_max,
                                                  moderate_max,high_max,basis}}}  (basis = the CMDV2
                                                  METRIC_META normalized-unit semantics, stated not applied)
    voltage_deviation_pct(asset_table)->float|None   (equipment_config, 7 rows)
  NO accessor for the 27 all-NULL equipment_config columns; rated_kva NOT exposed (asset_nameplate
  stays the single rating authority).
- overload_pct derivation: value = current_avg / breaker rating_a * 100; rating_a None/0 -> None.
  Registered as "breakerOverloadPct" with base ["current_avg", "breaker:rating_a"], fidelity real_exact,
  recover_class nameplate_lookup analog, _QUANTITY family "load-percent-of-rated" (hard class).
- Seeds: knob equipment.derivations.enabled="on"; consts.rtm_<paneltype>_<metric>_<band> generated
  IN-DB via INSERT..SELECT from equipment.rtm_threshold (72 rows, idempotent) so R10(b) citations resolve.

### C — AI context (depends on A bridge + B ratings APIs)
Owns: layer1b/resolve/asset_candidates.py + asset_resolve.py (edits), layer1b/prompts/asset_system.md,
layer2/emit/equipment_facts.py (new), layer2/emit/user_message.py (edit), layer2/emit/panel_members_block.py
(edit), layer2/prompts/data_instructions_v2.md, layer2/emit/morphmap/prompt.md,
db/seed_equipment_ai_context.sql, tests/test_equipment_ai_context.py, outputs/equipment_wiring/stream_c.md.
- 1b: additive columns idx10 aka / idx11 loc (len-guard-safe); listing gains a 5th TAB column;
  resolve_name order = exact canonical > norm canonical > UNIQUE normalized alias; any alias collision
  (40 verified keys) or alias-vs-canonical clash -> ambiguous path, never a pin; ghost/no-data guards
  unchanged downstream. Prompt rule: aliases match like names; ALWAYS return the canonical NAME verbatim.
- L2 facts (each '' on miss, never raise): EQUIPMENT line (aka|bay_role|section|zone|load_profile|
  feeds/fed_by), BREAKER line (rating_a+type), RTM BANDS line (panel-type resolved only, cites consts.rtm_*),
  ENERGY REGISTER line (direction/scale VERBATIM + never-rescale clause). Joined into the existing
  fact tuple at user_message.py:251. panel_members_block gains per-member "aka=|breaker_a=|load_profile="
  suffix inside _lines (lru_cache key unchanged; canonical name stays first).
- Prompt edits: R8-ROLE += bay_role sentence; R10(b) += consts.rtm_* legal const source; morphmap +=
  aka-as-display-label / canonical-as-data-key + thresholds-may-ground-band-morphs; NO 1a edit
  (parked, evidence-gated panel-token vocab documented only).
- Knobs: equipment.facts.enabled="on", equipment.alias.enabled="on".

### D — 3D kitpreview fallback
Owns: data/equipment/kitpreview.py, layer2/emit/metadata/asset_3d.py (edit: 5th tier),
ems_exec/renderers/asset_3d.py (edit: template pass-through only), db/seed_equipment_3d.sql,
tests/test_equipment_3d.py, outputs/equipment_wiring/stream_d.md.
- Tier 5 (fires only when the 4 DATA_SCHEMA tiers miss — all empty today): table -> unique_mfm_row ->
  equipment node -> kitpreview_viewer_rule most-specific-first (for_key > for_type+rating > for_type >
  AppKV default_panel_model; ''=wildcard) -> cat_asset. URL from glb_file relative path against the
  media base (NEVER the stale url column); file-existence gate -> object=null + GAPS reason when the
  GLB is not in the media root (no fabricated availability). Viewer = default_overrides (already honored
  by _asset_preset) + rule.preset + kitpreview_app_kv viewer_defaults merged under. template (25/55)
  passed through on object; None otherwise. Unbridged asset -> object=null exactly as today.
- Knobs: equipment.kitpreview.enabled="on", equipment.kitpreview.media_base="" (empty -> existing
  config/asset3d_media behavior). Ops note: rsync cmd_equipment media/objects/*.glb into the media root.

### E — cleanup/docs (runs LAST)
Owns: outputs/equipment_wiring/SUMMARY.md, comment/docstring-only edits in data/lt_panels/panel_members.py,
ems_exec/executor/members.py, layer1b/basket/topology_siblings.py, tests/test_equipment_disposition.py,
outputs/equipment_wiring/stream_e.md.
- Verify-before-dead: nothing deleted unless proven unreferenced at runtime; single-door enforcement test
  (no `FROM equipment.` outside data/equipment/ + db/seed_equipment_*.sql); SUMMARY carries the full
  22-table disposition + the no-data-upstream documentation for equipment_config's NULL columns +
  equipment.nameplate OCR skip rationale.

## Knobs (all app_config rows w/ code default, seeded idempotently + applied live via psql)
equipment.topology.enabled=off · equipment.facts.enabled=on · equipment.alias.enabled=on ·
equipment.derivations.enabled=on · equipment.kitpreview.enabled=on · equipment.kitpreview.media_base="" ·
consts.rtm_* family (72 rows, INSERT..SELECT from equipment.rtm_threshold).

## Per-table disposition, edge cases, test plan
Mirrored in the StructuredOutput returned to the orchestrator (all 22 tables; USED-BY A: mfm/feeder/
equipment/data_source; B: breaker/rtm_threshold/equipment_config(partial)/core_paneltype; C: mfm facts+aliases;
D: kitpreview_cat_asset/cat_group/viewer_rule/app_kv/core_assettype; SKIP: nameplate(OCR noise),
asset_meter/bms_meter/bms_meter_limit (ds1 mock), asset_threshold (hold), kitpreview_combo/preset/version/
asset_rules). Tests: five tests/test_equipment_*.py files, :5432-only, plus byte-identical snapshots
(knob-off topology; no-equipment-asset L2 prompt) and full-suite green at default knobs.

---

# REWORK v2 (2026-07-08) — post-critique redesign. THE DESIGN ABOVE IS SUPERSEDED where it conflicts.

The v1 design was rejected with 3 fatal issues. Everything below was VERIFIED live on :5432 before
being adopted into the v2 structured design returned to the orchestrator.

## Fatal 1 — Stream A edge algorithm reworked to BAY-ANCHORED rosters + per-panel allowlist + two-sided guard
- v1 resolved edge endpoints by `equipment_id` fan-out -> fabricated rosters (AHU Panel-05 claiming
  PCC-2A's fan-out via equipment_id=43) and double-counted multi-meter nodes (UPS in+out twins).
- VERIFIED replacement (CMD_V2's own semantics: MFM.objects.filter(reference_id=eid) split by role):
  panel node's members = equipment.mfm WHERE reference_id=<node>, role incoming vs outgoing.
  - PCC-1A (node 47): 2 incoming (pqm_transformer_1, gic solar_incomer_1) + 5 outgoing gic
    (ups_01/02/03, bpdb_01, hhf_01) + 7 spare (mfm_pefc_* ds1 mock).
  - PCC-1B (node 160): siblings (solar_incomer_2, ups_04/05/06, bpdb_02, hhf_02, pqm_transformer_2).
  - mirror OUT of pcc_panel_1 (317) = {ups_01..06, bpdb_01/02} -> union(1A,1B) = mirror + HHF-1/2:
    exact-set FAILS, so any gain must be human-vetted -> allowlist entries carry explicit extra_ok.
  - mirror IN of 317 (TRANSPOSED outgoing: from-side where to=317) = solar 1/2 + gic_15 *_sch
    transformer meters; equipment incoming bays carry pqm_* transformer tables instead -> resolved
    set would LOSE 164/166 -> guard=None -> incoming falls back to mirror (honest).
- Dup-twin tables (18 groups): each pair = one row on the PCC panel (outgoing) + one on 'UPS Output
  Panel P1' (incoming) -> a single panel's reference roster holds only ONE twin; table->canonical
  needs only REGISTRY-side uniqueness (320/320) -> twins ARE rosterable (v1 wrongly excluded them).
- equipment.feeder is NO LONGER a roster source (identity-gated feeds/fed_by facts only).

## Fatal 3 — per-row identity gate for mixed equipment_id semantics, MEASURED
Normalization: strip parentheticals, lowercase, non-alnum->space, de-zero-pad digit tokens; verified
iff norm-equal OR token-set subset either direction; equipment_id preferred, else reference_id.
On the 183 bridged unique ds2 meters: 95 verified via equipment_id ('UPS-07 (600KVA)'~'UPS-07'),
45 via reference_id ('AHU Panel-11'~'AHU-11', 'MLDB Panel incomer'~'MLDB'), 43 unverified
('Solar Incomer-1' eq='Solar Plant' ref='PCC-1A'; 'AW Exhaust-05' abbreviation miss) -> those 43
honestly omit feeds/fed_by, equipment-identity node, and kitpreview. Exposed as bridge.identity_node().

## Fatal 2 — multi-asset once-per-class authoring seam PINNED + intersection rule
run/harness.py run_pipeline_multi:329-352 authors L2 once per class from rep=members[0]; the emitted
exact_metadata is reused byte-identical per sibling (host/multi_asset.py rebind_consumer rebinds only
the consumer). user_message._build fact loop :251 has NO sibling visibility -> v1's mitigation claim
was FALSE and is deleted. FIX: run_pipeline gains additive kwarg compare_group_tables=None
(run_pipeline_multi passes member tables when len(members)>1); harness stamps
l1b.asset['compare_group_tables']; equipment fact lines apply the INTERSECTION RULE — a line is
emitted iff byte-identical for EVERY table in the group ('' otherwise). BREAKER / ENERGY-REGISTER
(per-asset values) drop out of compares; RTM panel-type bands survive when class-uniform.

## Improvement adoptions
- ALL feature knobs default 'off' (facts/alias/kitpreview/derivations/topology + allowlist {}) —
  staged flip: staging pass ON + 18-page sweep + SSR gate, THEN live psql flip.
- scaffold db.py: failures NEVER cached (retry next call) + clear_cache().
- edges.py reads registry_lt_mfm(_outgoing) via data/db_client directly (no import cycle).
- parent_ids()/outgoing_edges() global merge specced: allowlisted+guard-passing panels ONLY.
- alias precedence pinned: canonical exact > canonical norm > alias tier only on canonical miss;
  unique alias pins, len>1 ambiguous; tested both directions.
- rtm_bands_line provenance explicit ('panel-type defaults for the type of the equipment this meter
  is attached to'); seeds supply app_config.data_type (NOT NULL); key-spelling parity test via a
  single rtm_const_key() helper shared by B's seed check and C's line.
- overload_pct: max-phase basis where phase columns exist, else current_avg; basis stated in the
  library line so the AI cannot present average as worst-case.
- kitpreview existence gate DEFAULT-DENY: media_base is a LOCAL filesystem path by contract;
  unverifiable -> object=null. Resolution keyed on identity_node (never the hosting panel's model).
- single-door test: (?i)(from|join)\s+equipment\. over raw file text (catches f-strings); allowlist
  data/equipment/*.py + db/seed_equipment_*.sql + tests/test_equipment_*.py + the scanner itself.
- sequencing: wave1 A,B (D too, with an import-guarded lazy bridge dependency) -> wave2 C (needs
  A+B pinned APIs) -> E last.

## Seam anchors re-verified for v2
- run/harness.py run_pipeline:184 (kwarg seam) / run_pipeline_multi:329 (rep authoring).
- layer2/emit/emit.py _recovery_library_block:38-84 — 'nameplate:' prefix split at :68 ('breaker:'
  must join the non-plain set in the same edit or the fn is hidden on every card).
- registries/neuract/members.py _edge_targets:52 / incomers_of:83 (LIVE :5433; role tags stay in caller).
- data/registry/lt_mfm.py parent_ids:84 / outgoing_edges:97 / outgoing_feeders:117 (mirror-first).
- layer2/emit/panel_members_block.py _block_for lru_cache (mfm_id, scope) :54-55.
