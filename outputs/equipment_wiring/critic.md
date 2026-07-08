# Adversarial design critique — equipment wiring (streams A-E)

Role: adversarial design critic. Status: IN PROGRESS (findings appended as verified).

## Verified census facts (psql cmd_catalog @:5432, 2026-07-08)
- 22 tables in schema `equipment` — matches per_table_disposition exactly (no missing tables).
- equipment.mfm 303, feeder 194 (192 feed + 2 coupler, no other kinds), breaker 301 (168 rated),
  rtm_threshold 18, equipment 182, equipment_config 120, nameplate 432, spare roles 60,
  pcc_panel% tables in mfm: 0. Dup table_name groups: 18. Meterless equipment nodes: 34.
- FKs confirmed: feeder.source_id/target_id -> equipment.equipment.id; breaker.mfm_id -> equipment.mfm.id;
  mfm.equipment_id/reference_id -> equipment.equipment.id; rtm_threshold -> equipment + core_paneltype.
- Bridge example verified: equipment.mfm id=13 'Feeder Tx-1 (PCC-1A)' -> gic_15_n3_pcc_01_transformer_01_se
  -> registry_lt_mfm id=171. registry_lt_mfm has 320 rows, 0 duplicate table_names (registry side unique).
- registry_lt_mfm_outgoing = 93 edges, from = SOURCES (Solar Incomer, PCC-0x Transformer feeders,
  TIE feeders, HT DG Incomer, PCC-Panel-1..4), to = consumers. Source->consumer semantics at
  PCC-Panel-N *aggregate* granularity.

## FATAL 1 (stream A) — endpoint resolution via equipment_id fabricates rosters; superset guard is one-directional and cannot catch it
Evidence:
- 36 equipment nodes have >1 unique-table meter (e.g. UPS-10: incoming gic_21_n6_ups_10_inc_4_p1 AND
  outgoing gic_07_n5_ups_10_cl_600_kva_p1; Chiller-02: TWO 'outgoing' meters chiller NG + CWP pump;
  PCC-2A node 43 carries SEVEN 'incoming' meters that are actually downstream panels' NG incomer bays).
  52/192 feed edges TARGET multi-meter nodes; 141/192 are SOURCED from them. Step (e)
  "endpoint node -> equipment.mfm WHERE equipment_id=<node>" returns ALL of a node's meters ->
  double/multi-counted members (both sides of one UPS; pump + chiller as siblings).
- equipment.mfm.equipment_id does NOT mean "the equipment this meter measures": e.g.
  gic_16_n5_ahu_panel_05_ng ('GIC-16-N5-AHU Panel-05') has equipment_id=43 = PCC-2A (its SOURCE panel).
  So panel_edges(ahu_panel_05_table,'outgoing') resolves node 43 and returns PCC-2A's whole 11-member
  fan-out as AHU Panel-05's feeders.
- Simulated the design end-to-end for direction='outgoing' across ALL bridgeable panels:
  * Panels with mirror out-edges: 7 total; the coverage guard FAILS on all 7 (mirror members are
    PCC-Panel-N aggregate meters that don't exist in equipment.mfm; e.g. Solar Incomer-1: 4 mirror
    members ALL missing, 38 extras). => equipment-first edges NEVER serve any of today's panels;
    stream A's stated goal delivers zero coverage where it matters.
  * Panels with EMPTY mirror sets: superset guard passes trivially -> 73 registry meters
    (AHU/AW/PDB/BPDB panels, UPS meters, Solar Incomers) would ship NEW fabricated rosters of
    1-38 members the moment equipment.topology.enabled=on (e.g. AHU Panel-05 gains 11 members that
    belong to PCC-2A; Solar Incomer meters gain 38-member rosters). parent_ids() would also mark all
    73 as parents ("bridgeable panels with >=1 resolved out-edge").
Verdict: the guard as specced (superset-only) plus the equipment_id endpoint mapping is simultaneously
useless (0 panels improved) and dangerous (73 fabricated rosters when enabled). Guard must be
two-sided (exact-set or explicit per-panel allowlist), and edge->meter resolution must key on the
FEEDER BAY meter (the mfm row named 'Feeder X (...)' attached to the edge/panel), not on
"all meters of the target node". Default-OFF knob prevents immediate damage but the stream as
designed cannot ever be turned on.

(continuing: repo-side verification of B/C/D claims)

## FATAL 2 (stream C x multi-asset) — the design's multi-asset claim is FALSE; per-asset fact lines leak the representative asset's numbers onto class siblings
Evidence (repo):
- MULTI_ASSET_PLAN.md + db/seed_multi_asset.sql: "1a once, Layer 2 once per class, executor per asset" —
  Layer-2 user_message (where streams C's four fact lines land, user_message.py:251) is authored ONCE from
  the class REPRESENTATIVE; the emitted exact_metadata is reused for every sibling.
- The design's edge_cases claims "fact lines are per-asset and ride the per-asset executor pass, not the
  once-per-class L2 authoring" — WRONG: user_message.py IS the once-per-class authoring input.
- R10 (data_instructions_v2.md:30) protects DATA-slot consts (must cite nameplate metric or consts.* row,
  executor substitutes per asset). But BREAKER rating_a has NO R10(a) metric class and NO executor
  substitution; the ONLY numeric use the design teaches is exact_metadata band/threshold MORPHS
  (morphmap rule "RTM/breaker threshold facts may ground band/threshold morphs") — and R12 allows
  story-driven threshold morphs in metadata, which are NOT R10-gated.
- Consequence: "compare UPS-01 and UPS-04" → L2 authored once from UPS-01's BREAKER/ENERGY-REGISTER
  facts → a threshold/gauge-band morph grounded on UPS-01's rating_a ships on UPS-04's card = wrong
  number attributed to a sibling asset (fabrication). Same for energy_scale/direction facts.
Fix directions: suppress per-asset-variant fact lines (BREAKER, ENERGY REGISTER, per-asset EQUIPMENT
identity) whenever L2 authoring covers >1 asset; or author L2 per-asset when fact lines differ; or give
breaker rating an R10(a)-style executor-substituted metric class. The design must stop asserting the
false per-asset claim.

## FATAL 3 (cross-stream A/C/D) — equipment.mfm.equipment_id has MIXED semantics; every node-keyed consumer inherits it, and streams C/D default ON
Evidence (all :5432, verified 2026-07-08):
- reference_id sample proves the flip-flop: 'UPS-07 (600KVA)' equipment=UPS-07 / reference=PCC-3A
  (equipment = the metered thing), BUT 'AHU Panel-11' equipment=PCC-4A / reference=AHU-11 and
  'MLDB Panel incomer' equipment=PCC-2B / reference=MLDB (equipment = the HOSTING/source panel).
- Of 181 bridged unique ds2 meters: >=35 have equipment_id pointing at a PCC/panel/bus hub while the
  meter is not one; 75 sit on multi-meter nodes.
- Consumers inheriting the defect: A step (c)/(e) node resolution (see FATAL 1); C's
  equipment_line feeds=/fed_by= (feeds_fed_by(equipment_id) prints the HUB's fan-out as the asset's own
  — e.g. an AHU bay meter would claim PCC-2A's 11 feeds) with equipment.facts.enabled DEFAULT ON;
  D's kitpreview resolution (equipment_node -> key/panel_type_code/asset_type_code) can resolve the
  hosting panel's model/template for a non-panel asset, with equipment.kitpreview.enabled DEFAULT ON.
- (Softer: B/C rtm panel_type via equipment_id = the HOSTING panel's type, which is arguably the right
  banding basis for a bay meter — but the design never states this and must.)
Required: a per-row identity gate before any node-keyed use (e.g. mfm.name ~ equipment.name similarity,
or reference_id cross-check), omitting feeds/fed_by/equipment-identity/kitpreview honestly when the
mapping is unverified. Table-keyed facts (aka aliases, mfm.role/section/zone/load_profile,
energy_* scales, breaker via mfm_id) are NOT affected.

## Verified-sound claims (no action)
- 22-table disposition complete; no missing tables.
- emit.py:68 prefix-filter trap is REAL ('breaker:' base would be hidden forever as a plain basket
  column) — B's fix is necessary and correctly placed. Breaker is 1:1 per meter (0 dup mfm_id, 0 null);
  133 NULL rating_a confirmed (168 rated / 301).
- registry.py _d/_NAMEPLATE/_QUANTITY exist as claimed; 'load-percent-of-rated' is an existing hard
  class; current_avg is an established base column; _NAMEPLATE merges into the live neuract resolver.
- rtm_threshold = 6 metrics x 3 panel types, all panel_type-scoped (0 equipment-scoped) => 72 band
  consts; core_paneltype codes = distribution_panel/transformer/lt_panel; app_config PK=(key) so
  ON CONFLICT (key) works; cfg(key, default) exists; consts.* mechanism live (R10(b), 2 rows today).
- equipment_config: rated_kva 113, voltage_statutory_deviation_pct 7, contracted/demand 0, rating text
  1 — 'do not wire the NULL columns' is correct.
- Candidate row = 10 positional cols; ALL consumers len-guarded (as_asset len>6/7/8/9,
  no_data_gate/ambiguous len>6, ghost len>9) — idx10/11 append is additive-safe. asset_resolve by_name
  -> by_norm(unique-or-None) verified; alias tier slots cleanly after by_norm.
- user_message.py:251 fact tuple verified; panel_members_block lru_cache key (mfm_id, scope) untouched
  by a _lines suffix; morphmap/prompt.md + config/asset3d_media.py + databases.CMD_CATALOG exist.
- asset_3d _resolve_object is a real 4-tier chain (5th tier slots in); renderer _asset_preset already
  deep-merges default_overrides. kitpreview: 49 viewer rules; cat_asset 55 (39 glb, 25 template).
- members.py incomers_of = lt_mfm_outgoing to_mfm=panel (supply side) — guard direction semantics
  well-defined both ways; members.py reads LIVE neuract (design's claim correct).
- 18 dup groups all incoming+outgoing pairs; ds1=69=mfm_pefc rows; 40 alias-collision keys (exact match
  with the design's number); 34 meterless nodes; bridge example mfm 13 -> gic_15_..._se -> registry 171.

## Non-fatal improvements (see StructuredOutput for the full list)
cert-sequencing of default-ON knobs; edges.py import cycle on the id-map read; global-seam merge spec;
db.py error-cache poisoning; alias-vs-canonical contradiction; rtm provenance labeling; seed data_type
NOT NULL; consts key parity test; overload_pct current_avg vs max-phase basis; D remote-media existence
gate bypass; E single-door test vs the streams' own tests + case sensitivity.

VERDICT: ok=false — 3 fatal issues (A topology resolution+guard; C multi-asset fact-line leak;
cross-stream equipment_id mixed semantics). B is buildable as specced; D needs the identity gate and
the media-root caveat; E fine.

---

# ROUND 2 — adversarial critique of the REWORKED design (2026-07-08)

## Round-1 fatals: verified FIXED in the v2 design (against real data)
- Fatal-1 (equipment_id roster fabrication): rosters now bay-anchored on mfm.reference_id+role behind a per-panel
  allowlist + TWO-SIDED guard + all-or-nothing. Verified on PCC-1A/1B (nodes 47/160): outgoing bays = mirror 8 + hhf_01/02
  (all 10 bridge 1:1 to registry); incoming bays carry pqm_* tables (0 in registry) -> all-or-nothing None; mirror
  incomers 164/166 (*_sch) would be LOST -> loss-guard None either way. Spares = mfm_pefc_* only. Dup twins verified:
  one row on the PCC panel (outgoing) + one on UPS Output Panel P1 (incoming).
- Fatal-2 (compare sibling leak): run_pipeline_multi (run/harness.py:329) groups by_class BEFORE selecting members, so
  compare_group_tables = same-class tables only; intersection rule receives exactly the covered set. card_input.py:43
  passes the same l1b asset dict into card_in -> the stamp is visible to user_message. run_pipeline signature at :184
  matches the pinned additive kwarg.
- Fatal-3 (mixed equipment_id semantics): identity_node fixtures verified in-DB: UPS-07 (600KVA) eq=UPS-07 (verifies),
  AHU Panel-11 eq=PCC-4A (hosting-panel mis-pointer, fails) ref=AHU-11 (verifies), Solar Incomer-1 eq=Solar Plant
  ref=PCC-1A/2A/3A/4A (neither verifies), AW Exhaust-05 ref='Air Washer Exhaust-05' (abbreviation miss, fails).
  183 bridged ds2 unique-table meters confirmed; ds1=69, registry-only=119.

## Census re-verification (all EXACT)
mfm 303 / 18 dup groups / roles incoming 105, outgoing 136, spare 60, coupler 2; feeder 194 (192 feed + 2 coupler),
FKs source_id/target_id -> equipment.equipment(id); breaker 301/168 rated 1000-2500A; rtm_threshold 18 = 6 metrics x 3
panel types, 0 equipment-scoped; equipment_config 120: rated_kva 113, voltage_dev 7, contracted/critical/demand/eff all 0;
registry_lt_mfm 320/320 unique table_name; mirror edges 93; app_config PK(key) + data_type NOT NULL; existing
consts.rtm_% rows = 0 (no collision); paneltype codes distribution_panel/transformer/lt_panel; kitpreview_cat_asset
55 rows: glb_file 39, url 34 non-empty, template 25; app_kv keys viewer_defaults + default_panel_model;
viewer_rule cols (for_type, for_key, rating, page_type, preset, model_id). 22 tables = the disposition list exactly.
All 22 tables have a disposition. All 8 knobs carry code defaults ('off'/''/'{}' or none-needed consts). No file is
owned by two streams; the wave sequencing (A,B,D -> C -> E) matches the dependency edges; single-door regex has ZERO
pre-existing hits in the tree.

## NEW FATAL R2-1 (stream C + 1b) — unconditional prompt-file edits break cert byte-identity at DEFAULT knobs
C STEP 8/STEP 3 spec STATIC text edits to layer2/prompts/data_instructions_v2.md (R8-ROLE +=, R10(b) +=, NEVER-RESCALE),
layer2/emit/morphmap/prompt.md, and layer1b/prompts/asset_system.md — and C's test plan asserts "prompt files contain
the new rule strings". These files ARE the certified L2/1b system prompts, read from the tree at every emission: the
edits take effect at MERGE, with all knobs OFF, before any staged sweep. That contradicts (a) the design's own cert
clause ("facts/alias/derivations/kitpreview change PROMPT or PAYLOAD content ... additive-on-miss is not enough for
cert freeze"), (b) task hard rule 2 (additive context OMITTED on miss — rule text referencing an EQUIPMENT line that
never exists at default knobs is not omitted), and (c) project history (prompt-v2/morph-map were HELD OFF because a
live A/B regressed — this exact risk class). The staged-flip runbook only gates DB rows, never file content.
FIX (cheap, precedented): knob-gate the rule text with the machinery ALREADY in emit.py — marker-wrapped conditional
sections exactly like _ROSTER_BEGIN/_ROSTER_END (stripped when the knob is off; run-constant so the prefix cache
holds), or {{EQUIPMENT_RULES}} substitution keyed on equipment.facts.enabled / equipment.alias.enabled; same for the
morphmap rules and the 1b aka/loc doc block. The knobs-off snapshot test must cover the SYSTEM prompt bytes, not just
the user message.

## NEW FATAL R2-2 (stream B) — breakerOverloadPct registration leaks prompt/payload drift at DEFAULT knobs
Verified in code: _recovery_library_block(card_in) is substituted into the SYSTEM prompt per card (emit.py:148-149),
and the filter branch appends a "(N fns hidden ...)" trailer whenever hidden>0. B registers the fn unconditionally in
registry.catalog() and places the knob check in emit.py's per-card filter ("hidden iff cfg off OR known-empty"). At
default knobs that yields: (a) every basket-bearing certified card's trailer count changes N -> N+1 (byte drift), and
cards with hidden==0 today GAIN a whole trailer line; (b) the no-card_in / unknown-basket path serves "the FULL
library, unchanged" -> breakerOverloadPct is OFFERED at knobs-off, and if the AI emits it the executor's knob-off None
produces a NEW honest-blank leaf (payload drift). Either way cert byte-identity at default knobs is broken.
FIX: gate at the SOURCE — registry.catalog() omits the entry when equipment.derivations.enabled is off (absent from
every rendering, hidden counts untouched, executor can never bind it); keep the emit.py '<word>:' prefix
generalization + known-empty hiding for the knob-ON path only. Add a knobs-off SYSTEM-prompt byte-snapshot test.

## Improvements (non-fatal, see StructuredOutput)
1. B API contradiction: breaker_rating() -> dict|None conflates no-row/dup with DB-error, but the emit filter spec
   needs known-empty(False) vs unknown(None) a la _nameplate_rated — pin a tri-state probe in the API.
2. lt_mfm.py/members.py should import data.equipment.edges lazily/guarded; D's tier should catch Exception broadly
   (a half-built or import-crashing new module must never take down the certified mirror path).
3. panel_members_block per-member suffixes (breaker_a etc.) are NOT intersection-filtered — in a panel-class compare
   the rep panel's suffixed roster grounds the shared class recipe shipped on the sibling panel; suppress suffixes when
   compare_group_tables is present (len>1) or document why the pre-existing rep-roster seam makes this acceptable.
4. D conflates the local existence-check dir with the FE-served URL (url=<media_root>/<glb_file> ships a filesystem
   path to the browser); spec a served-URL prefix distinct from media_base or the staged flip can never pass.
5. identity_node token-subset verifies '<Panel> Incomer'-shaped meter names against the panel node, granting a single
   incomer meter the panel's full feeds= fan-out — add a fixture pinning intended behavior.
6. consts.rtm_* ON CONFLICT DO UPDATE reverts operator-tuned band values on re-apply — document re-derivation
   authority explicitly (contrast with the DO NOTHING knob convention) or split initial-seed vs re-derive.
7. Single-door raw-text regex will trip innocent prose comments ('# aliases from equipment.mfm') in non-exempt files
   (C's equipment_facts.py is layer2/emit/) — warn stream C in its brief or scope the scan.
8. D: resolve_model returns rule_preset separately but the disposition says 'deep-merged over default_overrides' —
   pin which envelope key the tier sets (obj['preset']=merged works with _asset_preset's viewer/preset/default_overrides chain).
9. B: overload_pct's declared plain base is current_avg only — meters with phase columns but no current_avg get the fn
   hidden though phase-max could bind; state the accepted under-offer in stream_b.md.
10. facts-knob flip mid-process serves stale lru_cached panel_members_block blocks — document restart-required (mirror
    the edges latch story) or fold the knob into the cache key.
