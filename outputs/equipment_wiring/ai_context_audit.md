# AI-Context Audit: what each AI layer sees today vs what `equipment.*` can add

Stream: ai_context_audit (AI-context audit agent). ASCII-safe. All DB claims below were verified
live against cmd_catalog @127.0.0.1:5432 on 2026-07-08; nothing touched :5433.

---

## 0. Verified ground facts (queries run this session)

- `equipment.feeder.source_id/target_id` FK -> **`equipment.equipment(id)`**, NOT `equipment.mfm.id`
  (pg_constraint: `feeder_source_id_0983cb75_fk_equipment_id`, `feeder_target_id_0f6be5d5_fk_equipment_id`).
  Direction verified empirically on PCC-1A (equipment id=47): sources INTO it = `2500 KVA Tx-1`,
  `Solar Plant`; targets OUT of it = UPS-01/02/03, BPDB-01 Lam-01&02, HHF-01 (Type-01).
  So `source -> target` = physical power flow. Bridge to meters is `equipment.mfm.equipment_id`
  (61 of 303 mfm rows have it NULL) -- NOT usable alone; per-meter bridge stays `table_name`.
- `equipment.breaker.mfm_id` FK -> `equipment.mfm(id)`, UNIQUE per mfm. 168/301 have `rating_a`.
  Bridged to the canonical registry via unique `table_name`: **98 breaker ratings land on canonical meters**.
- `equipment.rtm_threshold` = 18 rows = 6 metrics (kw, kvar, pf, volt, amp, i_unbal) x 3
  `core_paneltype` rows (distribution_panel / transformer / lt_panel). `equipment_id` is NULL on ALL
  18 (check constraint: exactly-one-scope; every row is panel_type-scoped). Bands e.g.
  kw: low<=40 / normal<=60 / moderate<=80 / high<=95 (percent-of-rating semantics), volt: 1/2/3/5
  (percent-deviation semantics), pf: 0.98/0.95/0.9/0.85 (descending).
- `equipment.mfm` (303): role outgoing=136 / incoming=105 / spare=60 / coupler=2. `section` = the BUS
  SECTION token users actually say: HT, 1, 1A, 1B, 2A, 2B, 3, 3A, 3B, 4A, 4B (11 values -- '1A' IS
  "PCC-1A"). zone = HT/North/South. load_profile = 18 semantic classes (ups_backed, cleanroom_hvac,
  compressed_air, hv_incomer, tx_incomer, pcc_incomer, ...). asset_category populated sparsely
  (APFC/HHF/HT Panel/LT Panel/Transformer/UPS). rated_capacity_kva non-null on 302/303.
  energy_direction: import=164 / sum=132 / export=4 / net=3. energy_scale/power_scale != 1 on 51 rows.
- **table_name bridge census**: registry_lt_mfm 320 rows, 0 duplicated table_names.
  equipment.mfm 303 rows, 18 duplicated table_name groups (pattern verified: the SAME physical meter
  listed twice -- as the upstream panel's `outgoing` bay AND the downstream panel's `incoming` bay,
  e.g. `UPS-01 (600KVA)` [outgoing] + `UPS-01 incomer` [incoming] -> gic_01_n3_ups_01_p1).
  Clean one-to-one bridge (unique both sides): **183 meters**. equipment-only (no registry table): 84.
  registry-only (no equipment row): 119 -- including ALL FIVE aggregate devices
  (pcc_panel_1..4_feedbacks, main_ht_plc_feedbacks): equipment.mfm has **0** `pcc_panel%` rows.
- **Name spaces are fully disjoint**: of the 183 clean-bridged pairs, **0** have the same
  normalized name; 183/183 differ. equipment.mfm holds the HUMAN names ("Feeder -> Tx-1 (PCC-1A)",
  "UPS-02 (600KVA)", "BPDB-01 Lam-01&02", "Solar Incomer-1"), the registry holds the meter-plate
  names ("GIC-15-N3-PCC-01 (Transformer-01) [Secure Elite300]").
- 'PCC-1A' (normalized) occurs in **1** equipment.mfm name and **0** registry names. The registry's
  only PCC granularities are the per-transformer feeder meters ("...PCC-01 (Transformer-01)...")
  and the 4 whole-panel aggregates ("PCC-Panel-1..4"). equipment.equipment DOES have first-class
  PCC-1A/1B/2A/2B/3A/3B/4A/4B nodes -- a granularity the canonical registry cannot name at all.
- Alias safety census: 40 normalized equipment names map to >1 distinct table (e.g. 'Air Washer-1'
  is metered at gic_11_n5_..._p1 AND gic_23_n5_aw_panel_01_ng) -> such an alias may only ever
  surface as AMBIGUOUS. **0** equipment aliases norm-collide with a DIFFERENT registry row's name,
  so alias enrichment can never override a canonical verbatim match.
- registry mirror's own role/rated_capacity_kva columns: 0/320 populated -- equipment is the only
  local source for role/rating facts.
- Names carry non-ASCII (a right-arrow glyph in "Feeder -> Tx-1"); any logging of alias text must
  stay counts/ascii-replace per the UTF-8 rule (prompt injection itself is fine, LLM side is UTF-8).
- Canonical DB helper confirmed: `data/db_client.q("cmd_catalog", sql)` (used by layer2/catalog/*).

---

## 1. What each layer sees TODAY (read end-to-end)

### Layer 1a (layer1a/route.py + prompts/system.md)
User message = one line per PAGE (page_key | title | merged story | card titles), grouped by SHELL,
plus the raw prompt. System prompt routes on STORY WORDS only; explicit rules make device-name
class tokens inert, make panel reading-side (incomer/outgoing) a data-scope no-op, and pick page
granularity (feeder page vs panel-overview page) from the SUBJECT'S GRANULARITY. No asset registry,
no metadata about any device reaches 1a. Output is grammar-constrained to the candidate page_keys.

### Layer 1b (resolve/asset_resolve.py + asset_candidates.py + prompts/asset_system.md)
Candidate rows `[id,name,table,mfm_type_id,load_group,class,has_data,has_feeders,never_wired,
table_exists]` from the canonical registry mirror. The AI sees ONLY
`name<TAB>class<TAB>load_group<TAB>NO-DATA?` (ids hidden), narrowed by a class prior; it must copy
a registry name VERBATIM; deterministic name->row mapping (exact then normalized); collision gate,
ghost guard, member_scope stamping (this session), no_data gate. `load_group` is just the GIC-xx
node token. So the ONLY name space the resolver can match against is the meter-plate GIC-* space.

### Layer 2 emit (emit/user_message.py + asset_facts.py + panel_members_block.py + slot_catalog.py
+ prompts/data_instructions_v2.md + morphmap/prompt.md)
Per-card user message blocks, in order: run/card/page header; 1a stories; ASSET line
(name/class/table/panel_id); NAMEPLATE line (asset_nameplate row: rated_kva/kw/current_a,
'-' => unbindable); DATA WINDOW line (real first/last ts); DB SCHEMA (per-column qty/unit/data
flags); RELEVANT COLUMNS; PANEL MEMBERS block (panels only: PRIMARY side per member_scope,
name | gic table | has_data | last ts); catalog row (handling class, endpoints, recipe,
roster_spec, controls, capabilities, feasibility); metadata skeleton; FILLABLE SLOTS catalog
(leaf path + verbatim ctx + expected_qty); swap candidates; shared-ctx ref. System prompt =
data_instructions_v2.md R1-R14 (+ morphmap/prompt.md when skeleton-carded) + RECOVERY_LIBRARY.

Facts the emit AI does NOT have today and demonstrably needed:
- R8-ROLE ("this meter senses only its own rail") is enforced with ZERO facts about which rail the
  meter actually sits on -- `equipment.mfm.role` (incoming/outgoing/coupler) IS that fact.
- Overload/loading claims have no breaker denominator -- `equipment.breaker.rating_a` IS that fact
  (nameplate line only carries kva/kw/current from asset_nameplate).
- Status banding (RTM cards) has no threshold facts -- rtm_threshold IS the banding table.
- Roster/seed-roster morphs must "re-roster to verbatim member names" but the only names available
  are GIC-* meter-plate strings; the human names live in equipment.mfm.
- energy_direction (export/net meters, e.g. Solar Incomers) and energy/power scale are invisible;
  the AI cannot reason about a reversed/export register or a scaled feed (facts only -- never applied).

---

## 2. Decision per layer

### Layer 1a -- NOTHING (explicitly justified)
1a is asset-agnostic BY DESIGN: it routes story words onto page stories; the asset is resolved in
1b, and the certified prompt already contains the two rules that make device tokens and reading-side
words inert. Every equipment feed considered fails a cost/benefit test:
- Injecting any asset roster (303 rows or even a compressed class list) re-introduces exactly the
  keyword-pull the SUBJECT-vs-STORY rule exists to suppress, bloats a x27-per-sweep prompt, and
  risks flipping certified near-tie routes (the route grammar/seed work exists because near-ties
  are fragile).
- The one arguable gap -- granularity (is 'BPDB-01'/'MELDB'/'HHF-01' a panel or a device?) -- is
  already covered by the prompt's generic panel-word rule, and a wrong granularity self-heals
  downstream (granularity_reconcile / route_to exists for exactly this). If a REAL misroute of this
  family is ever observed, the bounded fix is a one-line DB-driven token vocab (panel-name tokens
  distilled from `equipment.equipment WHERE distribution_panel` -- PCC/BPDB/PDB/MELDB/MUPSDB/
  MRPDB/HHF/APFCR...) substituted into system.md like {{METRIC_VOCAB}} -- but ship it DEFAULT-OFF
  behind an app_config flag, because any 1a wording change moves certified routes. Recommendation:
  DO NOT wire now; record as a parked, evidence-gated option.

### Layer 1b -- ALIAS + locational context in the candidate listing (the big win)
REAL failure modes today (all reproduced from the data, not hypothesized):
1. "PCC-1A voltage" -- 'PCC-1A' exists in ZERO registry names. The AI must guess between
   'PCC-Panel-1' (the whole-panel aggregate, silently merging bus sections 1A+1B) and
   'GIC-15-N3-PCC-01 (Transformer-01)...' (the HT feeder INTO 1A). Whatever it picks is an
   unattributable semantic leap; 1A-vs-1B distinction is silently lost.
2. "Tx-1" / "2500 KVA Tx-1" -- registry says 'Transformer-01'; equipment says 'Tx-1'. Same for
   Tx-2..Tx-8.
3. "BPDB-01" / "Lam-01&02 board" -- registry: 'GIC-01-N8-BPDB-01 For Lamination-01&02'; usually
   recoverable semantically, but recovery is luck, not contract.
4. "UPS-02 incomer" -- equipment names BOTH bays of the same meter ('UPS-02 (600KVA)' outgoing +
   'UPS-02 incomer' incoming -> ONE gic table); today 'incomer' + UPS risks the Incomer-class trap
   the panel-qualifier rule only fixes for PANEL subjects.
Feed: ONE additive column in the listing built at candidate time via the table_name bridge:
   `name<TAB>class<TAB>load_group<TAB>flag<TAB>aka=<alias1; alias2><TAB>loc=<section>/<zone>`
- aka = ALL equipment.mfm.name values sharing the row's table_name (dup-table rows are fine here:
  N aliases -> 1 canonical row is safe; only canonical->equipment FACT lookups need uniqueness).
- loc = section/zone ONLY when the table_name is unique on the equipment side (a dup row's two
  bays sit in two sections -- ambiguous -> omit honestly).
- Both fields EMPTY-STRING when unbridged / DB-miss -> the listing is byte-identical to today
  for every asset without equipment data (cert rule 2 holds).
- Prompt rule (asset_system.md, additive): "aka= lists alternate human names for the SAME meter --
  match against them exactly like the name, but ALWAYS return the canonical NAME column verbatim,
  never an alias". The deterministic name->row map must ALSO accept a unique normalized alias
  (alias resolution stays deterministic; the 40 alias-collision keys resolve to >1 table and must
  fall through to the ambiguous/collision path, never rows[0]).
- 'PCC-1A' outcome becomes honest: candidates = the Tx-1 feeder meter (aka contains PCC-1A) +
  PCC-Panel-1 (norm-adjacent) -> picker, instead of a silent arbitrary merge.
- Collision gate interplay: colliding_rows/uniquely_named operate on prompt tokens vs registry
  names; alias matching must feed the SAME gates (an alias hit that lands in a >1-row colliding
  set surfaces the picker).

### Layer 2 -- five additive FACT lines/enrichments (all '' on miss, facts-only, no corrections)
1. EQUIPMENT IDENTITY line (per resolved asset, unique-bridge only):
   `EQUIPMENT (registry facts for this meter): aka="UPS-02 (600KVA)" | bay_role=outgoing |
   section=1A | zone=South | load_profile=ups_backed | feeds/fed_by=<equipment name via
   equipment_id>` -- grounds R8-ROLE (which rail this meter senses), roster naming, data_note
   wording, and the 1a-story-to-asset coherence. bay_role is THE missing R8-ROLE fact.
2. BREAKER line: `BREAKER (this feeder's breaker): rating_a=2500 (type=ACB)` -- the overload-%
   denominator surfaced as a FACT with the same '-' => unbindable convention as NAMEPLATE.
   Never multiplied into anything by code; if we want fns to use it, the honest path is
   registering it in the nameplate/derivations resolver (config/nameplates enrich-around,
   NOT a second rating authority in the prompt when asset_nameplate already carries one --
   on conflict show only the asset_nameplate value; add the breaker line as a separate,
   clearly-scoped fact).
3. RTM THRESHOLD BANDS line (panel-type-scoped): when the asset's panel type resolves
   (equipment.mfm -> equipment.equipment.panel_type_id, unique bridge only):
   `RTM BANDS (panel_type=lt_panel, percent-of-rating unless noted): kw 40/60/80/95 |
   kvar 20/40/60/80 | pf 0.98/0.95/0.90/0.85 | volt(dev%) 1/2/3/5 | amp 40/60/80/95 |
   i_unbal 5/10/15/20` -- feeds R10(b)-style threshold consts and status-band morphs from a REAL
   DB source instead of Storybook seeds. Also seed these as `app_config consts.*` rows so R10(b)
   citations resolve (DB knob, code-default mirror).
4. ENERGY DIRECTION/SCALE facts appended to the identity line, VERBATIM + explicitly inert:
   `energy_direction=export | energy_scale=0.1 | power_scale=1 -- FACTS about how this register
   logs; NEVER rescale a reading yourself` -- lets the AI explain a negative/export register
   (the energy-polarity guard family) and honest-note scaled feeds without any silent correction.
5. PANEL MEMBERS enrichment (panel_members_block._lines): append per-member, bridge-permitting:
   `aka=<human name> | breaker_a=<rating> | load_profile=<x>` after the existing
   name/table/has_data/last fields. Human aka names are exactly what the seed-roster morph rule
   needs ("morph identifier leaves to the verbatim real member names" -- GIC-* strings make
   terrible roster labels); breaker_a grounds per-feeder capacity claims. Members keep the
   canonical name FIRST (the executor fan-out + roster matching stay keyed on canonical).
Non-feeds (explicitly): equipment_config's all-NULL columns (contracted_kw, thd limits, ...) --
document as 'no data upstream', wire nothing. rated_capacity_kva -- do NOT add a second rating
line; if wanted, enrich the existing asset_nameplate seed offline (it is the single consumed
authority). kitpreview_* 3D config feeds the asset_3d RENDERER, not the emit AI's context (a
separate wiring stream). equipment.feeder's 194 edges are equipment-level (equipment.equipment
ids); using them to REPLACE the 93-edge lt_mfm_outgoing member graph is a topology-stream
decision, not an AI-context one -- for prompts we only surface names/facts, never re-derive
membership from a different graph (two graphs disagreeing inside one prompt would be worse than
one incomplete graph).

---

## 3. Prompt edits proposed (file + rule + grounding)

1. layer1b/prompts/asset_system.md -- INPUT line gains `aka=` + `loc=` field docs + the rule
   "aliases match like names; ALWAYS return the canonical NAME verbatim, never an alias".
   Grounding: 183/183 bridged names differ; 'PCC-1A'/'Tx-1' resolve to nothing today.
2. layer1b/resolve/asset_candidates.py + asset_resolve.py -- alias column construction (bridge via
   table_name, canonical helper `data/db_client.q`) + deterministic alias->row mapping folded into
   resolve_name with unique-or-ambiguous semantics. Grounding: 40 alias norm-collisions exist; the
   resolver's collision path must own them.
3. layer2/emit/asset_facts.py (or a new atomic equipment_facts.py) -- EQUIPMENT identity line +
   BREAKER line + direction/scale facts, all try/except -> ''. Grounding: R8-ROLE currently runs
   fact-free; 98 breaker ratings bridge cleanly; 7 export/net meters exist.
4. layer2/emit/user_message.py -- append the new fact lines in the same `for _fact in (...)` loop
   (additive, omitted-on-empty; byte-identical otherwise).
5. layer2/emit/panel_members_block.py -- per-member aka/breaker_a/load_profile suffix fields.
   Grounding: the seed-roster rule (data_instructions_v2.md PART 2 + morphmap prompt) demands
   verbatim member names for roster morphs; only meter-plate names are available today.
6. layer2/prompts/data_instructions_v2.md -- R8-ROLE gains one sentence: "the EQUIPMENT line's
   bay_role names the rail this meter senses; a leaf naming a DIFFERENT rail than bay_role has no
   column here". R10(b) gains "RTM BANDS values are legal const sources (cite consts.rtm_*)".
   Both additive; behavior for assets without equipment facts unchanged.
7. layer1a/prompts/system.md -- NO EDIT (parked, evidence-gated token-vocab option documented above).

## 4. Edge cases the final wiring must survive (user prompts + data states)

- "incomer PCC-1A voltage" -- alias resolves the panel/feeder; member_scope must STILL flip to
  incomer; the alias must not re-trigger the Incomer-class trap (panel-qualifier rule stands).
- "PCC-1A outgoing feeders" / "outgoing of PCC-2B" -- outgoing side + a bus-section alias.
- "PCC-1A" vs "PCC-1B" -- MUST NOT merge into PCC-Panel-1 silently; ambiguous picker is the
  honest outcome (registry has no 1A/1B granularity).
- "PCC Panel 1" / "PCC-Panel-1" / "PCC-01" / "pcc panel 1" -- the existing norm-match must keep
  winning (alias columns are additive; canonical exact/norm match has priority).
- "UPS-02 incomer" / "UPS-02 (600KVA)" -- dup-table twin aliases -> the SAME canonical row,
  one pin, never two candidates for one meter and never an Incomer-class row.
- "Air Washer-1" -- ONE alias, TWO tables (p1 vs ng meter) -- must surface as ambiguous
  (40 such alias keys), never rows[0].
- "Solar Incomer-1" -- exists in two GICs (01-N9, 04-N4) -- alias collision + existing
  name-collision gate must both fire -> picker.
- "HT Panel-M1", "11kV incomer", "grid incomer", "HT side of PCC-1" -- HT-zone assets; 'HT side'
  is a member_scope keyword and must only flip reading-side, never the resolved asset.
- Asset with NO equipment row (all 119 registry-only rows incl. every pcc_panel_N aggregate +
  Main-HT-PLC) -- every new line/column is '' -> byte-identical prompt (cert bar).
- Asset whose equipment table_name is DUPLICATED (18 groups) -- aliases yes, per-meter facts
  (role/section/breaker) NO (ambiguous bay) -- skip honestly.
- Ghost rows (table_exists=False) -- an alias hit must not defeat the ghost-pin guard.
- Spare feeders (60 role=spare) -- no breaker rating / no load_profile -> lines partially omitted.
- Panel with equipment facts but neuract outage on :5433 -- facts (local :5432) still print while
  has_data/last go dark; blocks must not raise (existing try/except pattern).
- Multi-asset compare ("compare UPS-01 and UPS-04") -- author-once-per-class: equipment facts are
  per-asset and must ride the per-asset executor pass, not the shared class authoring.
- PIPELINE_ASSET_ID pinned re-run -- pinned_skip bypasses the listing; facts lines must still
  attach at L2 from the pinned asset's table.
- Non-ASCII alias glyphs (the arrow in 'Feeder -> Tx-1') -- fine in prompts; any stdout/log surface
  uses ascii-replace (UTF-8 surrogate rule).
- Prompts naming a section/zone/load_profile only ("North zone power", "cleanroom HVAC load") --
  out of scope for pinning; must degrade exactly as today (class prior/empty/picker), never crash
  on the new columns.
- equipment_config empty columns -- never wired; a future upstream fill is a data change, not a
  code change (document 'no data upstream').
