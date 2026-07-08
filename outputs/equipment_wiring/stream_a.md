# Stream A — equipment topology (bridge + bay-anchored rosters + identity gate)

Status: DONE (23/23 stream tests + 72/72 seam tests green; seed applied live; knobs-off live smoke byte-identical)

## Verified facts (2026-07-08, live cmd_catalog :5432)
- equipment.mfm: 303 rows, 285 distinct table_name (18 dup groups, all x2); roles 136 outgoing / 105 incoming / 60 spare / 2 coupler; ds counts {2: 234, 1: 69}.
- equipment.feeder: 194 rows = 192 feed + 2 coupler; FKs source_id/target_id -> equipment.equipment(id) (pg_constraint verified) — NOT equipment.mfm.id.
- equipment.mfm FKs: equipment_id AND reference_id both -> equipment.equipment(id).
- registry_lt_mfm: 320 rows / 320 distinct table_name; registry_lt_mfm_outgoing: 93 edges.
- Worked example holds: pcc_panel_1_feedbacks = canonical 317. Mirror outgoing (ORDER BY o.id): [16,11,12,13,20,23,24,25].
  Bay outgoing for nodes pcc-1a(47)+pcc-1b(160): 10 tables = the mirror 8 + gic_01_n10_hhf_01... (canonical 8) +
  gic_02_n10_hhf_02... (canonical 18). Bay incoming carries pqm_transformer_1/2_incomer_pcc_01 (NOT in registry ->
  un-bridgeable -> all-or-nothing None) + solar incomers; mirror incomers (transpose) = {17,19,164,166}.
- Feeder direction semantics verified: source FEEDS target (tx-01 -> pcc-1a; pcc-1a -> ups-01..03/bpdb-01/hhf-01-pcc1;
  pcc-3a -> ups-07; ups-07 -> ups-output-p2).
- Identity-gate fixtures verified in-DB:
  - 'UPS-07 (600KVA)' equipment_id=73 'UPS-07' -> verifies via equipment (paren-strip norm-equal).
  - 'AHU Panel-11' equipment_id=65 = PCC-4A (HOSTING-PANEL MIS-POINTER -> name gate rejects), reference_id=55 'AHU-11'
    -> verifies via reference. THE fatal-3 case.
  - 'Solar Incomer-1' (x4 tables, eq='Solar Plant', ref=panel) -> None both sides (and a 4-way alias collision key).
  - 'AW Exhaust-05' (eq=PCC-2B, ref='Air Washer Exhaust-05' abbreviation miss) -> None.
  - 'AHU-9 South' ~ 'AHU-09' -> verifies (de-zero-pad + token subset).
  - 'UPS-07 incomer' ~ 'UPS-07' -> verifies by token-subset (IMPROVEMENT-5 PINNED INTENDED behavior; grants the
    incomer meter the unit node's feeds/fed_by — legitimate for incomers). Fixture pins it.
- 'UPS Output Panel P1' has NO registry table of its own -> the empty-mirror vetted-extras case is tested SYNTHETIC
  (cache preload) instead of on that panel; all its bays do bridge (canon 134-162, 223) for a future allowlist entry.

## Measured gate census — DEVIATION IN NUMBERS ONLY (documented, behavior follows the spec)
The design quotes "95 via equipment_id + 45 via reference_id + 43 None" on the 183 bridged ds2 meters. Implementing
the gate EXACTLY as specced (strip parentheticals, lowercase, non-alnum->space, de-zero-pad digit tokens; verified iff
norm-equal OR token-set subset either direction) measures **108 via equipment_id + 45 via reference_id + 30 None**.
The 13-row delta is precisely the subset-verified qualifier-word meters ('UPS-07/08/10/11 incomer',
'Chiller Panel-0N outgoing', 'AHU-9/10/11 South', 'Chiller & CHW CWP-N') that the round-2 critic's improvement-5 note
explicitly acknowledges as verifying under the pinned rule ("per real rows"). Spot-checked every subset match: each is
the unit's OWN node — no hosting-panel mis-pointer verifies. Fixtures pin both verify and reject sides.

## What was built
- data/equipment/bridge.py — eq_row_for_table (unique-table bridge, dup twins -> None), aliases_for_table (twins
  included), alias_index + _norm_alias (PINNED parity with asset_resolve._norm), identity_node (equipment_id-first
  then reference_id, name-similarity gate), feeds_fed_by (kind='feed' only, identity-gated: unverified meter ->
  ([],[]) — the AHU-bay/PCC-2A fabrication wall). All fail-open; failures never cached.
- data/equipment/edges.py — enabled() + allowlist LATCHED at first call; panel_roster(panel_table, direction):
  allowlist entry {nodes:[equipment.equipment.key], extra_ok:[canonical_table]} -> bays via reference_id+role
  (spare/coupler NEVER rostered) -> table_name bridge to canonical ids (all-or-nothing) -> TWO-SIDED GUARD
  (i never lose a mirror member, ii never gain unvetted, iii no partial roster) -> mirror order + vetted extras asc.
  Registry reads DIRECT via data/db_client.q (cycle-free); deterministic outcomes cached per (table, direction),
  DB-error outcomes NEVER cached; guard violations = one ASCII stderr line. equipment_parents() = allowlisted +
  guard-passing panels only.
- data/registry/lt_mfm.py — GLOBAL MERGE: parent_ids() = mirror UNION _equipment_parent_ids(); outgoing_edges()/
  outgoing_feeders() serve the equipment roster for allowlisted panels, mirror rows byte-identical otherwise.
  Imports are LAZY + GUARDED (critic improvement: a defect in data/equipment can never crash the certified mirror
  path, even at knobs-on).
- registries/neuract/members.py — _edge_targets('outgoing') and incomers_of() consult panel_roster FIRST (local
  :5432); None -> today's live path; role tagging STAYS in the callers so member_scope -> role_filter_for ->
  select('supply'|'load') is untouched. Lazy + guarded import.
- db/seed_equipment_topology.sql — equipment.topology.enabled='off' + equipment.topology.panel_allowlist='{}',
  ON CONFLICT (key) DO NOTHING (a re-apply never flips operator-tuned state), data_type supplied. APPLIED LIVE
  (verified rows: off / {}).
- tests/test_equipment_topology.py — 23 tests, all :5432-local (:5433 paths monkeypatched); covers the 4 required
  proofs + guard loss/unvetted-gain/all-or-nothing/transpose + dup-twin rosterable + failure-not-cached + knob latch
  + knobs-off byte-identity with equipment reads rigged to explode.

## Latch semantics (documented per critic improvement 10)
enabled()/the allowlist latch at FIRST call per process; a live DB flip requires a process restart (or
edges.clear_cache() operationally) — by design, so lt_mfm._CACHE / panel_members._MEMBERS_CACHE /
panel_members_block's lru_cache never see a mid-run source switch.

## Enabling a panel (staged, human-vetted)
UPDATE app_config SET value='{"pcc_panel_1_feedbacks": {"nodes": ["pcc-1a","pcc-1b"], "extra_ok":
["gic_01_n10_hhf_01_type_01_300a_600kvar_p1","gic_02_n10_hhf_02_type_01_300a_600kvar_p1"]}}'
WHERE key='equipment.topology.panel_allowlist';  -- plus enabled='on'; then the staged 18-page sweep + SSR gate.
Result (verified in tests): outgoing roster = [16,11,12,13,20,23,24,25,8,18] (mirror 8 + the 2 real HHF feeders);
incoming guard-fails honestly (pqm_* bays unbridgeable) -> incomers stay mirror-served (solar + transformers).

## Test results
- tests/test_equipment_topology.py: 23 passed.
- Seam suites (test_ems_exec_roster, test_layer1b_asset_resolve, test_layer1b_name_collision, test_layer2_roster,
  test_panel_energy_register, test_layer2_empty_roster_honest_blank, test_layer1b_column_basket): 72 passed.
- Live knobs-off smoke: parent_ids=17 mirror parents, outgoing_edges(317)=8 mirror rows, roster=None, identity/feeds
  facts serve — byte-identical mirror behavior at defaults.
- Single-door scan ((?i)(from|join)\s+equipment\.) outside data/equipment/*.py + db/seed_equipment_*.sql +
  tests/test_equipment_*.py: ZERO hits (stream E's invariant holds pre-emptively).

## Notes for other streams
- B/C/D: bridge API is live — eq_row_for_table / aliases_for_table / alias_index / _norm_alias / identity_node /
  feeds_fed_by exactly as pinned. identity_node returns via/'equipment'|'reference' + node codes for D.
- E: the '93 edge' phrasing in lt_mfm/members docstrings was left factual (the mirror still has 93 edges; equipment
  rosters are an allowlisted overlay, described in the updated headers).
