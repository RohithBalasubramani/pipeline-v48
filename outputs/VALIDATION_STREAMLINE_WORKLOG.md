
## AUDIT-1: VALIDATION FLOW MAP (read-only) — 2026-07-04

Entrypoint: host/server.py:519 `run_pipeline(prompt, asset_id)` → run/harness.py.

EXACT ORDER inside run_pipeline (harness.py):
 1. run_parallel{ run_1a(prompt) ∥ run_1b(prompt, asset_id) }        (layer1a/build, layer1b/build)
    - run_1b INTERNALLY runs validate_layer1b_output (layer1b/schema.py) → out["contract_problems"] (ANNOTATE-only, never blocks; obs.failures.record)
 2. run.degrade_gate.apply(out)                                       (INFRA-outage terminal → data_unavailable gate; BLOCKS render only on tunnel/conn outage of 1a/1b)
 3. IF both 1a & 1b present:
    a. run.reconcile_granularity.apply  → may SWAP out["layer1a"] to correct-granularity mirror page (BEFORE validate; safety-net, never raises)
    b. _validate(out) → validate.build.run_validate(l1a, l1b)        [THE pre-Layer-2 validation pass]
         · load_asset_frame (validate/data_load.py: neuract compat, newest-first, TIME_COLUMN=timestamp_utc)
         · validate_data (per basket-column pass/warn/fail: present? null_rate? latest_ok? series_capable?)
         · validate_payloads (per card: leaf_classify demand vs data supply; payload-exempt classes pass)
         · assemble → {verdict: pass|warn|fail|asset_pending, data, payload, policy=annotate}
    c. VALIDATION GATE (chilled): out["validation_blocked"] = (n_columns>0 AND n_pass==0)   [zero-usable-data hard block]
    d. ASSET GATE: how∈{AI,user-choice,no_data} & asset → asset_pinned (unless validation_blocked); else asset_pending → picker, Layer 2 NOT run
    e. IF asset_pinned & !V48_SKIP_LAYER2:  _reflect_loop → run_2_all (Layer 2 fan-out) → gaps → maybe reroute 1a once (re-runs reconcile+validate on loop2)

VALIDATORS / GATES — WHEN / WHAT / BLOCK-or-ANNOTATE:
| check | file | when vs L2 | checks | verdict |
|---|---|---|---|---|
| validate_layer1b_output (contract_problems) | layer1b/schema.py | inside 1b, BEFORE L2 | how vocab; ambiguous→candidate_list; resolved→non-empty basket | ANNOTATE |
| degrade_gate | run/degrade_gate.py | after 1a/1b, BEFORE L2 | 1a/1b exception is infra-outage shaped | BLOCKS (data_unavailable terminal) |
| reconcile_granularity | run/reconcile_granularity.py | BEFORE validate/L2 | routed shell granularity vs asset has_feeders | MUTATES l1a (reroute); never blocks |
| validate_data | validate/data_validate.py | BEFORE L2 (run_validate) | per basket column present/null/latest/series | ANNOTATE |
| validate_payloads / leaf_classify | validate/payload_validate.py + leaf_classify.py | BEFORE L2 (run_validate) | payload demand (scalars/arrays/series) vs column supply — COARSE, not semantic | ANNOTATE |
| validation_blocked | harness.py:171 | BEFORE L2 | n_columns>0 & n_pass==0 (zero usable data) | BLOCKS L2 → picker |
| asset gate (pending) | harness.py:182-192 | BEFORE L2 | how resolved & asset present | BLOCKS L2 → picker |
| feasibility.read | layer2/catalog/feasibility.py via catalog_row | DURING L2 (per card_input) | card_feasibility.verdict/required_topology/mesh | feeds swap force + deterministic gap |
| swap gates (gate_confidence/force_renderable/no_dup/…) | layer2/swap/*.py | DURING L2 emit | swap pool validity/dedup/renderability | corrective, per-card |
| gate_exact_metadata / enforce | layer2/gates.py | DURING L2 (post-emit, per card) | byte-identity of METADATA leaves vs stripped default; no chrome; no data leaf | SELF-HEALS (reverts leaf); sets conforms |
| gate_data_instructions | layer2/gates.py | DURING L2 (post-emit) | every field a real basket column/const/$ctx/derived/time | ANNOTATE (conforms=False, still renders) |
| gate_roster | layer2/gates.py | DURING L2 (post-emit) | roster vs card_fill_recipe; columns verbatim-real | VALIDATE+normalize; telemetry |
| validate_layer2_card_output | layer2/schema.py | DURING L2 (per card) | envelope shape (payload_shape/orientation/fields) | ANNOTATE → may soften answerability to partial |
| _reconcile_slots | layer2/build.py | DURING L2 (per card) | slot-catalog coverage vs emitted fields | TELEMETRY (per-leaf unbound reason) |
| deterministic feasibility→gap | layer2/build.py:309 | DURING L2 (per card) | required_topology/mesh & !has_feeders & !fields_optional | forces gap → reflect reroute |

DEAD / UNWIRED: validate/schema.py `validate_validation_output` — only referenced by tests/test_validate.py; NEVER called in run_pipeline. It is the structural self-check of the run_validate report and is currently NOT run in the flow.

SHARED (not "post-L2 validators", used both sides): validate/leaf_classify.py, validate/payload_lookup.py, validate/data_load.py are LIBRARIES consumed DURING L2 (producer.py, slot_catalog.py, card_payload.py) + host — they are not a second validation pass.

CLASSIFICATION vs user directive "ALL validation BEFORE Layer 2":
 (i) genuinely-pre (already correctly pre): validate_layer1b_output, reconcile_granularity, validate_data, validate_payloads, validation_blocked, asset gate, feasibility DATA availability. These give L2 the "what data/columns exist + which asset + page-class fit" it needs to emit right.
 (ii) genuinely-post (must stay during/after emit): gate_exact_metadata/enforce, gate_data_instructions, gate_roster, validate_layer2_card_output, _reconcile_slots, swap gates, deterministic feasibility→gap — these validate the EMITTED payload's conformance to shape; they cannot precede the emit they check.
 GREY: feasibility→gap (build.py:309) is computed post-emit but its INPUT (required_topology/mesh vs has_feeders) is a PRE-L2 fact — could be surfaced in the pre-pass verdict so L2 consumes it instead of re-deriving.

## AUDIT-3 — Canonical neuract asset registry profile + adoption plan (agent, 2026-07-04)

### Registry schema map (neuract schema on :5433 / DATA_DB=target_version1)
- device_mappings (21978 rows, 323 tables, 387 field_keys): CANONICAL column dictionary. cols table_name|field_key|protocol|address|data_type|scale|deadband|device_id|encoding. field_key == the real data-table column name (verified exact match on dg_1_mfm). data_type∈{float,int,bool}, protocol∈{modbus,derived}. 306/320 lt_mfm tables + 62/64 asset tables covered. GAP: the 14 *_sch / gic_30 *_se HT-side tables have 0 mappings.
- lt_mfm (320) + lt_mfm_type (4: APFC/LT Panel/Transformer/UPS): the FULL populated meter registry. cols id|name|table_name|panel_id|mfm_type_id|load_group|role|parent_series|rated_capacity_kva. role/parent_series/rated_capacity_kva ALL NULL/empty (unpopulated). class via mfm_type_id→lt_mfm_type. dist: LT Panel 257, UPS 34, APFC 15, Transformer 14.
- asset (64) + asset_type (3: dg/ups/lt_transformer): a SECOND, narrower curated registry (DG 13, UPS 34, LT Transformer 17). cols id|name|db_link|table_name|asset_id|group|asset_type_id. Adds 8 pqm_* PCC-incomer meters NOT in lt_mfm. asset_parameter EMPTY (0).
- topology: lt_mfm_incoming (93) / lt_mfm_outgoing (93), cols id|from_mfm_id|to_mfm_id. outgoing from=feeder→to=panel. 17 feeder-parents, 77 feeders. asset_incoming/outgoing/coupler + lt_mfm_coupler all EMPTY.
- PCC-Panel-1/2/3/4 = lt_mfm.id 317/318/319/320, own tables pcc_panel_N_feedbacks (empty), aggregate via topology (panel_members(317)=8 members,4 reporting).

### CRITICAL BUG FOUND — pipeline mfm_id is a private row_number() id-space, NOT lt_mfm.id
- asset_candidates.py builds id = row_number() over meta_data_version1.app_device_tables order — a THIRD id-space, unrelated to lt_mfm.id AND asset.id (lt_mfm.id 167 = Transformer-03; asset.id 167 = DG-02 — three-way collision).
- _parents_with_feeders() reads from_mfm_id (canonical lt_mfm.id) but tags `int(e[0]) in parents` where e[0]=row_number id ⇒ 17/17 has_feeders flags land on the WRONG asset. Real parents (Transformer-01=164, PCC-Panel-1=317…) get has_feeders=False; unrelated Spares/AHUs/pqm-incomers get True.
- Downstream: feeder_table(167[pipe])→gic_03_n6_ahu_5_p1 (wrong) vs feeder_table(164[canon])→gic_01_n8_bpdb_01_p1 (right). panel_members(312[pipe PCC-1])→0 members orphaned=True vs panel_members(317[canon])→8 members. ⇒ THE root cause of "5 panel-overview pages render 0/24".

### Adoption plan (AI-first→DB→code order)
1. [code+db, HIGH] Re-source asset_candidates.py from neuract.lt_mfm (id=lt_mfm.id) instead of meta_data_version1 row_number. Fixes id-space so feeder flag + panel_members + feeder_table all key correctly. Keep the _sch de-dup (those tables genuinely don't exist as data). config knob: REGISTRY_DB / a `use_canonical_lt_mfm` flag.
2. [code, HIGH] class: fill mfm_type_id from lt_mfm (canonical) as the PRIMARY class; keep the name-regex only as the FINER sub-class fallback (lt_mfm_type is 4-way coarse — lumps DG under LT Panel — so it can't fully replace the 16-way heuristic; use it to DECIDE panel_granularity via asset_granularity.panel_classes and to authoritatively tag UPS/Transformer/APFC).
3. [code, MED] col_dict/describe: source kind/unit from device_mappings.data_type (bool→event, float+protocol=derived→derived) as canonical, name-heuristic as fallback. Covers 306/320.
4. [code, MED] has_data: keep value_counts (real, works); optionally cross-check against device_mappings presence.
5. Implement the empty data/registry/*.py scaffolds (lt_mfm.py, lt_parameter.py→device_mappings, lt_mfm_type.py) as the atomic single-purpose readers backing the above.

## AUDIT-1 — VALIDATION FLOW MAP (read-only) — 2026-07-04

### EXACT ORDER (run/harness.py run_pipeline)
S0 INSIDE 1a route (pre-everything, per attempt): config/available_pages.filter_to_available (BLOCKS candidate
   templates) → layer1a/parse/template_feasibility_gate.filter_renderable_templates over
   read_page_feasibility counts (BLOCKS templates with unrenderable_frac ≥ cfg feasibility.template_max_unrenderable_frac
   0.40; falls back to least-unrenderable) → (re-route only) mechanical exclude_page_key.
S1 run_parallel: 1a ∥ 1b. 1b internally: col_dict windowed has_data probe (annotates basket cols),
   resolve outcomes incl. resolve/no_data_gate.no_data_outcome (how='no_data' + alternatives — an OUTCOME, not a block),
   schema.validate_layer1b_output → out.contract_problems (ANNOTATE-only + obs.failures record).
S2 run/degrade_gate.apply — infra-outage fingerprints on 1a/1b exceptions → data_unavailable page terminal
   (BLOCKS page honestly; L2 skipped since the failed layer is None).
S3 run/reconcile_granularity.apply — has_feeders/class vs routed shell → rebuild 1a onto mirror page.
   Runs BEFORE validate + L2. ANNOTATES notes.reconcile; never raises.
S4 _validate → validate/build.run_validate (BEFORE Layer 2; re-run after any reflect re-route):
   · data_load.load_asset_frame (PROBE_ROWS=500 newest-first by timestamp_utc, real-column guard, :5433)
   · data_validate.validate_data — per-column present / null_rate (fail>0.5, warn>0.1) / latest_ok /
     series_capable(numeric ≥12 rows) / span. ANNOTATE.
   · payload_validate.validate_payloads (+payload_lookup/handling_lookup/leaf_classify) — per-SELECTED-card coarse
     supply-vs-demand over the HARVESTED DEFAULT payload (NOT the emitted one). payload-exempt classes pass. ANNOTATE.
   · report.assemble — overall pass/warn/fail/asset_pending; FAILURE_POLICY='annotate' (deferred).
   · validate/schema.validate_validation_output — NOT WIRED in prod (tests only).
S5 Harness gates consuming validation (the ONLY blockers):
   · validation_blocked = data.summary.n_columns>0 AND n_pass==0 → Layer 2 NOT run (picker). BLOCKS.
   · asset gate: how ∈ {AI,user-choice,no_data}+asset → pinned; else asset_pending → L2 NOT run (picker). BLOCKS.
     no_data STILL runs L2 (per-leaf-null skeleton) with no_reroute.
S6 LAYER 2 (_reflect_loop → run_2_all → run_card per card, concurrent). DURING L2 per card:
   emit (AI; transport retry, no_retry timeout/truncated) → swap decide.gate (confidence/vague/pool/dup/template-dedup/
   cascade) + gate_force_renderable (card_feasibility drop/no_data → FORCED swap; marks stamped OFFLINE by
   catalog/feasibility_recompute) → swap re-emit → _finalize: gate_exact_metadata → enforce_exact_metadata (ENFORCING
   self-heal revert), override_columns (_normalized telemetry), envelope+window backfill, consumer_build, gate_roster
   (validate+NORMALIZE to recipe truth, backfill), gate_data_instructions (fields vs basket set → conforms flag,
   telemetry-only), _reconcile_slots (slot-catalog diff → _slot_issues/_emit_gaps telemetry), answerability/gap,
   DETERMINISTIC topology-infeasibility→gap (required_topology/mesh × has_feeders — POST-emit though inputs are
   pre-emit-knowable), schema.validate_layer2_card_output → _schema_issues (demotes answerability). Then
   _finalize_with_gate_retry (ONE corrective re-emit, llm.gate_retry=1). AFTER all emits: grounding/swap_settle
   (collision revert — must be post-fan-out).
S7 Reflect (AFTER L2): gaps=answerability 'none'; no_data → never re-route; gap_frac < reflect.min_gap_frac(0.34) →
   honest-blank note; else re-route 1a ONCE (exclude failed page) → _validate again → run_2_all again.
S8 HOST (genuinely post): ems_exec run_card fill → fill.py GAPS_KEY per-leaf reasons (merges L2 _emit_gaps) →
   host/server._card_leaf_stats render verdict (render/partial/honest_blank) + seed sentinel + payload_error demotions.

### CLASSIFICATION vs 'ALL validation BEFORE Layer 2'
(i) must-be-before and ALREADY before: available-pages, template feasibility, asset resolution/no_data, granularity
    reconcile, data_validate, payload_validate (it validates DEFAULTS, not emissions — pre-emit by nature).
(i) must-be-before but currently DURING/AFTER L2:
    · topology-infeasibility→gap (layer2/build.py ~309) — inputs (card_feasibility.required_topology/mesh,
      asset.has_feeders, fields_optional class) all known pre-emit; today a FULL N-emit fan-out completes before the
      reflect loop discovers infeasibility and re-routes (then N more emits).
    · unrenderable-card force-swap — verdict is static, but run_card emits FIRST, then swap_gate forces the swap and
      re-emits the target: the first emit is always wasted for a known-unrenderable card.
    · deterministic part of the reflect re-route decision (expected gap_frac) — computable pre-L2 from the above +
      payload_validate supply-vs-demand.
(ii) genuinely-post (stay): gate_exact_metadata/enforce, gate_data_instructions, gate_roster, _reconcile_slots,
    validate_layer2_card_output, gate-failure re-prompt (all validate the EMISSION); swap_settle (needs all emits);
    AI-reported answerability reflect; host per-leaf fill verdicts + seed sentinel (validate the FILLED render).

### GAPS FOUND
G1 Validation verdicts are NOT consumed by Layer 2: gate_data_instructions' `real` set = ALL basket columns (a
   validate-FAIL mostly-null column binds cleanly); the emit prompt sees 1b's has_data flag, not validate verdicts.
   Two duplicate data probes exist (col_dict N-row window vs data_validate 500-row pandas) with different truths.
G2 validate/schema.validate_validation_output never runs in prod.
G3 payload section validates the 1a-SELECTED cards; post-swap/settle final card set differs; report never refreshed.
G4 _validate exception ⇒ validation=None ⇒ validation_blocked=False ⇒ L2 runs with ZERO validation (fail-open; the
   degrade_gate only catches 1a/1b outages, not validate-stage outages).
G5 grounding/recovery_validate.py: zero callers found tree-wide (needs the verify-before-dead check, but it is not in
   the harness path).

### TARGET FLOW (proposed)
1a∥1b → degrade_gate → reconcile_granularity → ONE pre-L2 validation pass producing a machine-consumable verdict:
  {per-column verdicts folded INTO the basket (usable=false on fail; unify with/replace 1b has_data probe — read the
   column dictionary from the registry mirror per directive (c)), per-card {payload supply-vs-demand, renderability
   (card_feasibility), topology feasibility (moved from build.py)}, page expected_gap_frac}. If expected_gap_frac ≥
  reflect.min_gap_frac → re-route BEFORE L2 (zero wasted emits). Layer 2 consumes the verdict: pre-verdict rides
  card_input (force-swap decided BEFORE the first emit; emit prompt sees usable-vs-failed columns). Post-emit
  conformance gates + settle stay during L2 (genuinely-post); host per-leaf render verdicts stay post. Wire
  validate_validation_output into run_validate; stamp a validation_error terminal when run_validate itself dies.

## AUDIT-3 — Canonical CMD_V2/neuract asset registry profile + adoption plan (2026-07-04)

### Registry schema map (neuract on DATA_DB :5433, all verified live)
- `lt_mfm` (320 rows, ids 1..320, THE canonical meter id-space): id, name, db_link, table_name, panel_id(all ''), mfm_type_id→lt_mfm_type, load_group (GIC node / 'PCC-Panel-N'), parent_series, rated_capacity_kva, role(all null). PCC-Panel-1..4 = ids **317/318/319/320** (tables pcc_panel_N_feedbacks). Transformer-01 _se = id **171**.
- `lt_mfm_type` (4): apfc/lt_panel/transformer/ups. GOTCHA: DG-x MFM rows are mis-typed `lt_panel` (mfm_type_id=2) — class must prefer `asset.asset_type`.
- `asset` (64, ids 118..181): name, db_link, table_name, asset_type_id→asset_type. Covers DGs(118-123,166-173), UPSs, LT transformers (_se), PQM incomers (174-181). NOTE: asset.id range OVERLAPS lt_mfm.id range — never mix the two id columns.
- `asset_type` (3): dg / ups / lt_transformer — authoritative class for those 64.
- `device_mappings` (21,978 rows, 323 tables; key table_name+field_key): the canonical COLUMN DICTIONARY — protocol(modbus|derived), address(register OR derivation formula), data_type, scale, deadband, device_id. Transformer-01 _se: 63 keys = 33 modbus + 30 derived (formulas for current_neutral, unbalance, deviation…); 0 mapped-but-missing vs physical cols. Even pcc_panel_N_feedbacks have 30-34 mapped feedback cols. 14 lt_mfm tables have ZERO mappings (all `_sch` stubs + GIC-30 _se HT rows) = the honest never-wired signal (beats the hardcoded `_sch` suffix filter).
- `lt_mfm_outgoing` / `lt_mfm_incoming` (93 each): edge (from,to). outgoing = from feeds to (panel→consumers, transformer→panel); incoming = EXACT mirror (verified 0 unmirrored both directions) — from=receiver, to=source. PCC-Panel-1(317): 8 outgoing consumers, 4 incoming sources (2 solar incomers + Transformer-01/02 feeders 164/166). The TOPO-02 "incoming is inverted/byte-identical dummy" comment in panel_members.py is STALE wrt canonical neuract — incoming is well-formed there (usable for upstream/SLD source rendering).
- EMPTY canonical tables (0 rows — mirror but never depend on): asset_parameter, lt_parameter, asset_incoming, asset_outgoing, asset_coupler, lt_mfm_coupler, lt_feeder (so panel_members' lt_feeder root-fix path never fires today).

### THE BUG, quantified (id-space mismatch — AUDIT-3 confirmation)
`layer1b/resolve/asset_candidates.py` builds ids via `row_number() OVER (ORDER BY tbl)` from meta_data_version1.app_device_tables, but every topology read (`_parents_with_feeders`, `feeder_table`, `data/lt_panels/panel_members.py`, grounding/aggregate.py, ems_exec members/panel_aggregate) resolves those PRIVATE ids against CANONICAL lt_mfm ids in lt_mfm_outgoing. Live measurement:
- only **8/320** private ids equal the canonical id; **295 differ**; 17 candidate tables aren't in lt_mfm at all (8 pqm_* are asset-table-only; GIC-30 node numbering even DISAGREES between the two registries).
- PCC-Panel-1: private **312** vs canonical **317** → `panel_members(312)` = orphaned/0 members, while `panel_members(317)` = 8 members / 4 reporting → THIS is why all 5 panel-overview pages dead-end no_data.
- Transformer-01 _se: private **167** collides with canonical 167 = *Transformer-03's* _sch feeder → has_feeders=True by collision, and `panel_members(167)` returns **PCC-Panel-2's 22 loads** — cross-asset fabrication if any aggregate path fires (the class-gate added this session masks it for Transformer/DG/UPS, does not fix the id-space).
- ids also DRIFT over time (memory recorded panels at 318-321, now 312-315) because row_number shifts whenever meta_data_version1 gains a table; lt_mfm.id is stable.

### Adoption plan (mirror-first, per directive c)
1. **scripts/sync_neuract_registry.py** (new): SELECT from :5433 neuract → cmd_catalog `registry_<name>` for device_mappings, asset, asset_type, asset_parameter, lt_mfm, lt_mfm_type, lt_mfm_incoming, lt_mfm_outgoing (+ lt_feeder/couplers for completeness). CREATE TABLE IF NOT EXISTS + idempotent UPSERT (PKs: lt_mfm.id, asset.id, device_mappings (table_name,field_key), edges id) + stale-row delete, stamp `registry_sync_meta(table_name, synced_at, row_count)`. Re-runnable.
2. **data/registry/** (new atomic reader module): mirror-first (`q('cmd_catalog', 'SELECT … FROM registry_lt_mfm …')`), graceful fallback to live neuract when the mirror is absent. Time-series DATA reads stay on :5433.
3. **layer1b/resolve/asset_candidates.py**: re-source from registry_lt_mfm ⋈ registry_lt_mfm_type ⋈ registry_asset(⋈ registry_asset_type). id = **canonical lt_mfm.id** (kill row_number); class = asset_type.code first (dg/ups/lt_transformer) → lt_mfm_type.code (apfc/transformer/ups; NOT lt_panel-for-DG) → existing name heuristic only for classes canonical lacks (AHU/Chiller/Fan/…); has_feeders = id ∈ registry_lt_mfm_outgoing.from_mfm_id (same id-space → bug dies); never-wired = no registry_device_mappings rows (replaces the `_sch` suffix hardcode). The 8 pqm_* asset-only meters get a non-colliding id range (e.g. 100000+asset.id) or table-keyed resolution.
4. **data/lt_panels/panel_members.py** (+`feeder_table`): read registry_lt_mfm_outgoing/registry_lt_mfm from the mirror (fallback live); delete the stale TOPO-02 'incoming inverted' comment; ids canonical end-to-end.
5. **layer1b/basket/col_dict.py**: join registry_device_mappings — wired-column set + kind/unit + derived formulas (feeds the recovery resolver); information_schema stays as fallback; fix the stale 'compat.cmp_mfm_*' docstring.
6. **layer1b/resolve/has_data.py / grounding.meaningful**: expected-column denominator from registry_device_mappings (judge a meter on its 63 mapped cols, a feedbacks panel on its 30, not the uniform 72).
7. **config/asset_granularity.py**: keep Panel-class gate, class now canonical.
8. Invalidate any persisted PIPELINE_ASSET_ID pins / caches after the id swap (private ids change meaning).

## AUDIT-4 broad prompt survey (2026-07-04, agent: audit4)

25 diverse prompts (class × metric family × density) via POST :8770/api/run. Raw JSON: /tmp/audit4/P*.json (+ /tmp/audit4/runner.log).

### Early findings (batch still running)
1. **DEFECT F1 — verdict rollup any-column-fail → page "fail"** (`validate/report.py::_roll`): P01 Transformer-05 RTM = 28/32 columns pass, 3/3 payloads pass, live kW flowing → page verdict "fail" because 4 energy-counter columns are all-NULL. Every live page with any dead/spare column reports verdict=fail — telemetry mis-flags live data (P01,P02,P03 all "fail"). Fix: roll verdict from REQUIRED/used leaves (or report pass_with_gaps), not any-column.
2. **DEFECT F2 — fabricated displayValue on blank/filled leaves** (fill overlay writes `value` but not `displayValue`): P01 card 36 payload readings: activePower value=426.75 real but displayValue='325.9' (stale card_payloads default); activeEnergy value='—' (honest) but displayValue='2165'; reactiveEnergy '—'/4562; projectedDemand '—'/328. CMD_V2 PowerEnergyRail renders `readings.*.displayValue` → any payload-fallback render (frame missing/unmappable, i.e. exactly the degraded case) shows FAKE default numbers. Zero-fabrication violation. Fix layer: fill/overlay must recompute displayValue (+ yLabels) or null it when value is blank.
3. **DEFECT F3 — misleading whole-asset reason on leaf-level gap**: P04 (energy page, Transformer-05 live 52k rows) → all 4 cards honest_blank reason "No data logged for this asset." Asset HAS data; only the 4 energy counter registers (active/reactive import/export kwh) are all-NULL in gic_24_n3_pcc_03_transformer_05_se. Reason should be per-leaf/per-metric ("energy counters not logged; power available").
4. **GAP F4 — derivable energy not derived**: same P04 — meter logs active_power_kw continuously; energy page could derive kWh by integration via the DB-keyed derivations resolver, but the energy basket only picks the 4 dead counter columns → honest_blank page for a fully-live meter.
5. Registry landmines found while picking prompts: lt_mfm rows whose table_name does NOT exist in neuract: id 167 (Transformer-03 _sch), id 314 (HT Panel-M1 gic_30_n6_ht_panel_m1_se). id 173 duplicate Transformer-03 [SE] has real table (resolver picked 173 for P03 — OK). PCC panel feedback stubs are 0-row by design.

### AUDIT-4 mid-batch findings (P01-P09)
6. **DEFECT F5 — wrong-asset confident pin (homonym)**: P06 "Real-time power of DG-03 Jackson" → pinned "DG-3 MFM" (how=AI, candidates=[]) and rendered ITS live data. GIC-28-N3-DG-03 [Jackson] (dead, 0 rows) is the asset asked about. Wrong-asset data presented as the answer = fabrication-grade. Resolver must surface candidates when registry has name collisions (DG-3 vs DG-03 [Jackson]).
7. **DEFECT F6 — ambiguous-candidate recall broken**: P08 "UPS-01 load percentage" → asset_pending with candidates [GIC-11-N11-20 kVA UPS, GIC-17-N1-600 KVA UPS-01 [TiMAC], GIC-21-N3-UPS-07 600kVA Incomer-1, GIC-27-N1-600 KVA UPS-01 [TiMAC]] — the list MISSES 'GIC-01-N3-UPS-01 CL:600KVA' (the dense, live UPS-01) and includes a UPS-07. Picker can't offer the right asset at all.
8. **DEFECT F7 — leaves claimed "not logged" while column is 100% non-null LIVE**: P06 card 70 / P07 card 71 reason "active_power_total_kw not logged by this meter" — dg_2_mfm/dg_3_mfm.active_power_total_kw is non-null in EVERY row (39519/39522) and fresh to the second. Same family: P02 card 45 claims current_r/y/b "not logged" on T-01 SE while live values (46-50 A at query time) exist AND the same card's payload phases carry filled values. L3 verdict/grounding kit contradicts both the DB and the card's own filled payload.
9. **DEFECT F8 — verdict "render/full" with leaf_stats 0/0/0 (blind leaves)**: P02 c44, P03 c46, P05/P06/P07 c73, P09 c46 — frame-fed cards (histories, Power Energy Analysis) report full answerability with ZERO tracked leaves; nothing verifies whether the client-side frame mapping yields real numbers or the fabricated defaults (interacts with F2).
10. Private id-space live-proof: P02 reports mfm_id=167 for Transformer-01 [SE]; canonical lt_mfm.id=171. Canonical 167 (Transformer-03 sch) has 1 lt_mfm_outgoing edge; 171 has 0 → P02's has_feeders=True is the AUDIT-3 wrong-asset bug reproducing.

## AUDIT-2 — Validator accuracy hunt (agent, 2026-07-04)

Tested live against 4 densities via curl /api/run: DENSE gic_01_n8_bpdb_01_p1 (54/54 pass), SPARSE Transformer-01 gic_15_n3_pcc_01_transformer_01_se (53 pass / 8 fail — all 8 verified genuinely 0-non-null whole-table → HONEST), DEAD GIC-01-N2-Spare (no_data + validation_blocked + honest_blank + 254 alternatives → correct), PANEL PCC-Panel-1 (WRONGLY no_data — see A2-1). Cross-checks: latest-row vs 20-row-window value_counts = 0 disagreements across 323 tables; text-sort newest == absolute newest on all 323 tables TODAY; no plumbing columns beyond timestamp_utc in any data table; vocab rows (value_keys/label_keys/chrome_subtree_keys) all present.

### Findings
- **A2-1 HIGH (= AUDIT-3 id-space bug, validator-side live proof)**: no_data_gate mis-fires on ALL 4 real aggregate panels. curl "PCC Panel 1 energy distribution" → asset {mfm_id:312, has_data:false, has_feeders:false}, how='no_data' — but canonical lt_mfm 317 has 8 feeders (4 reporting). asset_candidates.py:76 `int(e[0]) in parents` compares its private row_number id against canonical lt_mfm_outgoing.from_mfm_id.
- **A2-2 HIGH (inverse collision)**: 4 DEAD meters offered green — pipeline ids ∈ canonical-parent set {17,19,164,…,320} get has_data=True unconditionally: id19 GIC-02-N10-HHF-02 (realvals=0), id262 Air Compressor Panel (0), id265 AHU-02 (0), id310 GIC-30-N8-Spare (0). no_data gate silently bypassed; 17 assets total carry wrong has_feeders=True.
- **A2-3 HIGH (fabrication vector)**: topology_siblings.expand_basket_with_siblings on collided Panel-class assets attaches a FOREIGN subtree: BPDB-01 (pipeline id 17) → panel_members(17) = canonical Solar Incomer-1's members (gic_01_n3_ups_01_p1, gic_02_n2_bpdb_02_p1, …). An aggregate/feeder card for BPDB-01 would SUM unrelated meters. Same for id263 Electrical-Room panel.
- **A2-4 MED (latent, sibling of the TIME_COLUMN bug)**: every newest-row read ORDERs BY timestamp_utc as TEXT, but the column mixes tz offsets (gic_01: 38390 rows '+00:00' [≤06-30] vs 13698 '+05:30' [since 06-30]). Safe today (verified all 323 tables) ONLY because the switch was old→new; a writer reverting to +00:00 makes fresh rows text-sort BELOW stale +05:30 rows for 5.5h → data_load.py:20, col_dict.py:36/58, has_data.py:35 all silently read STALE rows (exact failure mode of the fixed 'ts' bug). config already defines DATA_TS_CAST='::timestamptz' — unused in ORDER BY. Also validate/data_validate.py:48 span: pd.to_datetime without utc=True on mixed offsets → object dtype + FutureWarning (pandas 2.3.3), hard error in pandas 3.
- **A2-5 MED**: describe.py `_EVENT` regex `_compliance(_|$)` mislabels thd_compliance_i_avg / thd_compliance_v_avg as kind='event' unit='' — live values are CONTINUOUS THD averages (5.65, 1.46 %); only thd_compliance_ieee519 is a real 0/1 flag. Basket AI + L2 inherit wrong kind/unit for two real quality metrics. device_mappings.data_type can't disambiguate (all 'float').
- **A2-6 LOW-MED**: validation.phase_suffixes misses ALL per-phase power/THD/deviation forms (active/apparent/reactive_power_{r,y,b}_{kw,kva,kvar}, thd_*_{r,y,b}_pct, *_deviation_pct, pqm power_factor_*_raw) → supply.phase_cols undercounts (dense run: 10 counted, ~25 real phase cols); and false-counts current_spread_{ry,by,br} as phase cols. Fix = edit the DB row (it IS cfg-driven).
- **A2-7 LOW-MED**: TWO knobs for one fact — validation.time_column (config/validation.py:12) vs DATA_TS_COL (config/databases.py:20); data_load orders by the former, col_dict/has_data by the latter. Editing one leaves the other stale (the structural cause of the original 'ts' bug persists). Default TIME_COLUMN to DATA_TS_COL.
- **A2-8 LOW**: col_dict._SKIP (3 names) vs has_data._PLUMBING (8 names) — two divergent plumbing sets; harmless today (no data table carries id/device_id/…), drift risk on new DBs → one shared config row.
- **A2-9 LOW**: data_validate latest_ok reads iloc[0] even when the frame was loaded UNORDERED (table lacking TIME_COLUMN) — arbitrary heap row claimed as 'latest'. All current tables have timestamp_utc.
- **A2-10 LOW**: leaf_classify _NUM_STR `^\s*[+-]?\d` misses '.5'-style numeric strings, matches digit-leading text ('3 Phase') → KPI-string data/chrome edge misclassification.

### Verified-good (no bug)
- Windowed has_data (window_nonnull) vs latest-row: no live disagreement; padded-0 kept non-null correctly.
- Sparse-meter fails are honest: Transformer-01's 8 fail columns have count()=0 over all 21345 rows (active_energy_*, current_avg, voltage_ll_avg, current_unbalance_pct, …).
- Dense-meter dead columns (thd_voltage_*, harmonic_*, thd_compliance_* on gic_01) correctly excluded by basket AI via has_data=N; validation n_fail=0 honest.
- PROBE_ROWS=500 ≈ 4h @30s cadence — adequate window; MAX_NULL_RATE/WARN thresholds produced no false verdicts on the tested meters.
- Per-leaf degradation held everywhere: even no_data PCC-Panel-1 rendered its 2 cards 'partial', never a whole-page refuse.

### AUDIT-4 P10-P11 + root-cause pins
11. **F5 again (worse)**: P10 "Load profile of UPS-04" → confident-pinned 'GIC-14-N2-UPS Supply Laminator-4.1' (candidates=[]), verdict pass 56/0 — a full healthy dashboard for the WRONG UPS. The real UPS-04 (GIC-02-N5, dead 0 rows) never surfaced.
12. **F9 — id-space collision corrupts panel aggregation flags**: P11 "PCC Panel 1 overview" → asset {mfm_id:312, has_feeders:false, has_data:false}, how=no_data, asset_no_data=true, validation n_columns=0/verdict fail — but canonical PCC-Panel-1 = lt_mfm.id 317 with 8 outgoing + 8 incoming edges (LIVE feeders). Pipeline's private id 312 = canonical 'GIC-30-N4-APFCR [SE]' (0 edges) → wrong has_feeders. Cards still filled via roster seam (heatmap 34 real leaves) so page renders, but flags/validation say dead panel. ROOT: layer1b/resolve/asset_candidates.py:47 `row_number() OVER (ORDER BY r.tbl)` private id-space vs registries/neuract/members.py joining CANONICAL lt_mfm_outgoing/incoming ids. Fix (user directive d): adopt canonical lt_mfm.id as THE id-space (and mirror registry into cmd_catalog per directive c).
13. F2 fix point: ems_exec/executor/fill.py fills ONLY declared leaf paths; sibling display projections (readings.*.displayValue, delta, yLabels) keep card_payloads seed numbers. CMD_V2 rails render displayValue → seed numbers leak wherever payload path is consumed. Fix: leaf declarations (card_payloads/L2 emit) must cover display leaves, or fill derives/blanks display siblings of a filled/blanked value (generic, not per-card).
14. Registry data gap: lt_mfm.rated_capacity_kva is NULL for ALL 320 rows → every capacity/duty/utilization leaf honest-blanks ("Rated capacity unknown"); many ratings are recoverable from names ('CL:600KVA', '600kVA') — seed a cmd_catalog nameplate mirror, never write neuract.

### AUDIT-4 FINAL (2026-07-04, batch P01-P25 complete; raw /tmp/audit4/P*.json)

Per-prompt verdicts (class/density/metric → page, pin, validation, cards, classification):

| P | family | pinned asset (table) | page ok? | validation | cards | class |
|---|--------|----------------------|----------|------------|-------|-------|
| P01 | transformer/dense/power | T-05 gic_24_n3 | yes RTM | fail 28/4 | partial+real kW | DEFECT F1,F2(displayValue x6) |
| P02 | transformer/sparse/current | T-01 SE | yes V-C | fail 13/5 (honest) | partial | DEFECT F1,F7,F8(c44); private id 167 |
| P03 | transformer/missing-table/voltage | T-03 picked live dup 173 | yes | fail 18/1 | partial | DEFECT F1,F8(c46); pin OK |
| P04 | transformer/dense/energy | T-05 | yes E-P | fail 0/4 blocked | 4x honest_blank | DEFECT F3,F4 (+F1) |
| P05 | dg/dense/power | DG-1 MFM | yes DG ops | fail 6/3 (dead unbalance cols honest) | real | DEFECT F1,F8(c73) |
| P06 | dg/dead/power | ASKED DG-03 Jackson → GOT DG-3 MFM | — | fail 9/3 | wrong asset's live data | DEFECT F5 (fabrication-grade) |
| P07 | dg/dense/energy | DG-2 MFM | yes | warn n_columns=1 | real | DEFECT F1-coverage,F7,F8 |
| P08 | ups/dense/load | asset_pending 4 cands | — | — | — | DEFECT F6 (misses live GIC-01-N3-UPS-01, offers a UPS-07) |
| P09 | ups/sparse/voltage | UPS-10 | yes | fail 14/4 (honest) | partial | honest + F1,F8 |
| P10 | ups/dead/load | ASKED UPS-04 (gic_02_n5, 0 rows) → GOT Laminator-4.1 (live) | — | PASS 56/0 | full healthy dashboard | DEFECT F5 HARD |
| P11 | panel/aggregate/overview | PCC-Panel-1 priv 312 | yes | fail 0/0 asset_no_data | heatmap 34 real leaves; c5 L2-emit timeout→default+fill partial (fail-fast held) | DEFECT F9,F8 |
| P12 | panel/dead/power | PCC-Panel-4 priv 315 | yes | fail 0/0 asset_no_data | REAL member aggregate (canonical 320 = 28 members; AHU-1 650, CWP-4 79050, nulls honest) | render GOOD; DEFECT F9 telemetry |
| P13 | panel/aggregate/energy | PCC-Panel-2 priv 313 | yes | fail 0/0 | Cumulative Energy 0.0 + live power 0.0 + empty trend + SEED chrome (Worst Peak 1,400 / legend UPS,BPDP,HHF / dates Apr 15) while canonical 318 has 18 energy-LIVE members | DEFECT F10 HIGH,F2,F8,F9 |
| P14 | feeder/dense/current | TIE Feeder HT-M2 SE | yes | fail 14/6 (honest) | partial | honest + F1 |
| P15 | feeder/power | 33KV MT-1 Feeder PM8000 (69/69 cols live) | yes | PASS 35/0 | partial real | OK |
| P16 | ahu/dense/power | AHU-1 | yes | PASS 24/0 | real | OK |
| P17 | ahu/dense/harmonics | AHU-5 | yes PQ | fail 6/7 — the 7 = exactly the 7 dead cols (thd_voltage_*, harmonic_5/7, compliance) | partial | honest-degrade + F1 |
| P18 | incomer/dense/load | asset_pending 5 sane candidates | — | — | — | OK (legit ambiguity) |
| P19 | incomer/dead/energy | asset_pending 2 cands | — | — | — | DEFECT F6 (only 2 of 4 Solar Incomer-1: misses GIC-01-N9, GIC-09-N7) |
| P20 | chiller/dense/trend | Chiller-01 | yes | fail 16/5 (honest: export/reactive dead) | c40 honest_blank rest real | honest + F1 |
| P21 | chiller/dense/pf | asset_pending 0 candidates | — | — | dead-end | DEFECT F6 HARD (canonical GIC-09-N4-CWP-1 gic_09_n4_cwp_1_p1 exists+live) |
| P22 | apfc/sparse/reactive | APFCR GIC-18-N1 | yes | fail 16/19 (honest: reactive_power_*/pf_* ALL dead on this meter) | partial real | honest-degrade + F1 |
| P23 | transformer/dense/pq | T-05 | yes | PASS 17/0 | real | OK |
| P24 | pump/sparse/current | Circulation Pump | yes | PASS 20/0 | real ('Backend unavailable' hit = statusVocab chrome, FALSE ALARM) | OK |
| P25 | htpanel/homonym/voltage | GIC-30-N7-HT Panel-M1 (TF 1-4) SE — a table canonical does NOT list (canonical GIC-30-N7='Spare'; canonical HT-M1=314 points at MISSING gic_30_n6 table) | panel-overview V-C | PASS 15/0 | all 5 cards leaf_stats 0/0/0 | lucky right pin; DEFECT F8, F11 registry drift, F5-lite silent homonym |

### DEFECT FAMILIES (fix these, not prompts)
- **F1 HIGH verdict-rollup** (10+ prompts): any dead column → page verdict=fail on fully-live meters. validate/report.py roll from used/required leaves; policy = cfg row.
- **F2 HIGH seed leakage in filled cards**: displayValue/marker/legend/date chrome keeps card_payloads seed numbers next to real (P01) or zero (P13) values. Generic fix in ems_exec/executor/fill.py display-sibling handling + leaf declarations.
- **F3 MED whole-asset reason on leaf gap** (P04): "No data logged for this asset" on a 52k-row meter whose 4 energy counters are null.
- **F4 MED-HIGH derivable-energy gap** (P04,P13): kWh derivable from live active_power; basket only picks dead counter cols.
- **F5 HIGH wrong-asset confident pin** (P06,P10,P25-lite): homonym/dead asset → silently pins a DIFFERENT live asset, candidates=[]; healthy dashboard for the wrong thing. Zero-fabrication violation at asset granularity.
- **F6 HIGH candidate recall** (P08,P19,P21): pending-list misses the right asset (P08: no GIC-01-N3-UPS-01; P19: 2/4 Solar Incomer-1) or is EMPTY (P21 CWP-1 → 0 candidates dead-end).
- **F7 MED leaf reason contradicts DB**: "not logged" on 100% non-null live columns (P02 current_r/y/b, P06/P07 dg active_power_total_kw).
- **F8 HIGH blind leaves**: verdict render/full with leaf_stats 0/0/0 on frame-fed cards (V-C c44/c46, DG c73, ALL panel-shell cards P13/P25) — exactly what let P13's zeros through unverified.
- **F9 HIGH private id-space** (all panel pages + 17 assets): mfm_id row_number vs canonical lt_mfm.id → asset_no_data/has_feeders wrong, validation n_columns=0, verdict fail while cards render real member data via name-roster. Fix = canonical id adoption + registry mirror (directives c/d) — plan already in this worklog.
- **F10 HIGH panel energy-power aggregate = 0.0 on live panel** (P13; NEW): energy-power/energy-power-history endpoints return zeros for PCC-Panel-2 (18 energy-live members) while energy-distribution (P12) aggregates the same panel topology correctly. Rendered 0.0 = fabricated zero; needs ems_backend energy-power panel strategy fix + zero-sum→blank guard.
- **F11 MED registry drift** (P25, feeds F5/F6/F9): canonical rows point at non-existent tables (167, 314) while live physical tables exist unreferenced (gic_30_n7_ht_panel_m1_se); rated_capacity_kva NULL x320. sync_neuract_registry.py must reconcile registry↔physical tables.

Clean: P15,P16,P18,P23,P24. Honest-degrade: P02,P03,P09,P14,P17,P20,P22 (+P04 reasons aside). 'unavailable-str' hits on V-C pages are statusVocab chrome — not a defect.

## STREAMLINE IMPLEMENTATION (2026-07-04, offline — host NOT restarted)

### 1. Canonical registry MIRROR (directives c+d) — DONE, run live
- `scripts/sync_neuract_registry.py` (NEW): mirrors device_mappings/asset/asset_type/asset_parameter/lt_mfm/lt_mfm_type/lt_mfm_incoming/lt_mfm_outgoing from :5433 neuract → cmd_catalog `registry_<name>`; CREATE-IF-ABSENT + ADD COLUMN IF NOT EXISTS (drift-safe) + full delete/insert per table inside ONE txn (idempotent upsert + stale-row delete); stamps `registry_sync_meta(table_name, synced_at, row_count, note)`. Re-run whenever plant DBs change.
- Enrichment stamped at sync (F11 reconcile): `registry_lt_mfm.table_exists` (306 t / 14 ghost) + `never_wired` (14 rows = 0 device_mappings) + a `_unreferenced_physical_tables` meta row (9 live tables no canonical row references: dg_digital_feedbacks, gic_30 *_pm8000/*_se set incl. the P25 gic_30_n7_ht_panel_m1_se).
- Ran live: 22,555 rows / 8 tables + meta. Time-series DATA reads stay on :5433; ONLY registry metadata is local now.
- `data/registry/lt_mfm.py` (reworked from skeleton): THE canonical accessor — mirror-first `_home()` (cmd_catalog registry_* when present, live neuract fallback), `registry_rows()` (320 lt_mfm + 8 pqm asset-only at 100000+asset.id), `parent_ids()`, `outgoing_edges()`, `outgoing_feeders()` (SLD/history shape).

### 2. Canonical id-space adoption (F9/AUDIT-2/AUDIT-3 HIGHs) — DONE
- `layer1b/resolve/asset_candidates.py`: row_number() private id-space DELETED; id = canonical lt_mfm.id. Row contract now 9-element [..., has_data, has_feeders, never_wired]. Class = asset_type.code FIRST (dg/ups/lt_transformer — canonical `asset` even classes the HT DG Incomer 'dg', authoritative) → trusted lt_mfm_type codes (apfc/transformer/ups; lt_panel UNTRUSTED — DG MFMs mis-typed) → ported name-vocabulary fallback. `_sch` suffix hardcode DELETED — replaced by the data-driven never_wired (which also PROVED the hardcode wrong: gic_29 *_sch are LIVE WIRED meters). has_data = value-probe OR (has_feeders AND Panel-granularity class) — a ghost non-Panel parent (the _sch 'Transformer-01' stub 164) is greyed, never greened by topology.
- ACCEPTANCE verified live: 328 candidates; PCC panels = 317-320 Panel/has_data/has_feeders TRUE; Transformer-01 = 171 single-meter (no edge) live; formerly-collided dead meters (19/310) now honestly grey; panel_members(317)=4/8, (318)=18/22 reporting; panel_members(171) orphaned. feeder_table(317)→gic_01_n8_bpdb_01_p1.
- `data/lt_panels/panel_members.py` + `grounding/endpoint_resolve.py`: topology reads now mirror-first via data/registry (no request-time tunnel for edges). Stale TOPO-02 'inverted incoming' comment corrected (canonical incoming = exact well-formed mirror). lt_feeder root-fix machinery DELETED (premise disproven, table empty canonical-wide, probe was a per-process tunnel read); config/feeder_topology.py DELETED (only consumer). If lt_feeder is ever seeded, wire it in data/registry/lt_mfm.py.
- PIPELINE_ASSET_ID pins: env/request-scoped only — nothing persisted server-side to invalidate; FE-held pins from the private-id era will simply no-op (id not in by_id → falls through to AI resolve).

### 3. ONE pre-L2 validation pass + Layer 2 CONSUMES it — DONE (before_layer2 confirmed)
- `validate/build.py`: two-pass contract documented; run_validate now (a) folds per-column verdicts INTO the 1b basket (verdict/usable/validate_reasons), (b) computes `expected_gaps` (topology infeasibility, MOVED from layer2/build post-emit) + `expected_gap_frac`, (c) wires validate_validation_output → report._schema_issues (was dead), (d) `payload_final()` post-settle refresh helper.
- `run/harness.py`: order now = reconcile → run_validate → degrade-gate re-check (VALIDATION outage → honest data_unavailable terminal, fail-open hole closed; run/degrade_gate._INFRA_LAYERS += 'validation') → PRE-flight expected-gap re-route (same reflect.min_gap_frac knob, BEFORE the N-emit fan-out) → validation_blocked / asset gates → Layer 2 → reflect (AI-discovered gaps only) → validation.payload_final post-settle.
- `layer2/gates.py`: `_bindable()` — a validate-FAIL column gates like a hallucinated one, with the validate reason in the issue (per-leaf honest-blank; F7-adjacent reason grounding). gate_roster uses the same set. Unvalidated baskets bind as before (no regression).
- `layer2/emit/user_message.py`: basket lines mark `✗ FAILED-VALIDATION` so the emit AI substitutes/honest-blanks up front (the 1b 20-row window Y/N stays the basket-AI hint only — divergent-probe issue resolved by making validate authoritative).
- `layer2/build.py`: post-emit topology check DEMOTED to note+answerability-soften (gap/re-route now pre-L2); run_card decides the FORCED renderability swap BEFORE the first emit (one guaranteed-wasted LLM call per unrenderable card eliminated; identical decision, pure reordering).
- `validate/report.py` (F1): rollup = fail ONLY when zero usable columns/cards; dead registers → 'pass_with_gaps' (telemetry); legacy any-fail behavior = DB knob validation.rollup_legacy_any_fail. schema.py accepts the new verdict.

### 4. Accuracy fixes (AUDIT-2 mediums/lows) — DONE
- Time-ordering: every newest-first read now ORDER BY ts::timestamptz (DATA_TS_CAST) — validate/data_load, col_dict window/latest_nonnull, has_data.value_counts; span uses pd.to_datetime(utc=True) (pandas-3-safe on the +00:00/+05:30 offset mix).
- latest_ok guarded: unordered read → None ('unknown'), never a fabricated latest-row claim (data_load returns `ordered`).
- ONE knob: config/validation.TIME_COLUMN code-default = config.databases.DATA_TS_COL (DB row validation.time_column stays the explicit override).
- ONE plumbing set: validation.plumbing_columns row (union of the drifted col_dict._SKIP / has_data._PLUMBING) read by both.
- describe.py event pattern narrowed via validation.event_name_pattern row: thd_compliance_i_avg/v_avg are continuous % metrics again; only *_event_active/_status/_compliance_ieee519 are flags.
- validation.phase_suffixes DB row UPDATED with the compound per-phase power/THD/deviation/raw forms; derived-kind columns excluded from the phase count (current_spread_* false-positives gone).
- leaf_classify numeric-string = full-string pattern ('.5' matches; '24x7'/'Apr 15' don't).
- col_dict/data_load stale 'compat.cmp_mfm_*' docstrings fixed.

### 5. DELETED (verify-before-delete done: grep served/run/imported across the tree first)
- grounding/recovery_validate.py (166 LOC — zero importers; L3-era grounding-kit unit, L3 retired; the live derivations path is ems_exec/derivations + config.derivation_binding)
- config/feeder_topology.py (81 LOC) + panel_members lt_feeder machinery (~55 LOC) — dead root-fix seam w/ disproven premise
- data/registry/{lt_mfm_type,lt_parameter,capacity}.py TODO skeletons (21 LOC, zero importers)
- asset_candidates row_number() SQL + `_sch` suffix filter + `_parents_with_feeders` (replaced by mirror accessor)
- config.databases TOPOLOGY_OUTGOING + LT_PANELS_DB knobs (meta_data_version1 shadow registry RETIRED from the pipeline)
- NET LOC (excl. sync script + tests): ≈ −8 (deleted ≈268 across 5 files + trims; added the pre-L2 consolidation + the 130-line mirror accessor)

### 6. DB changes
- cmd_catalog: NEW registry_device_mappings/asset/asset_type/asset_parameter/lt_mfm(+table_exists,never_wired)/lt_mfm_type/lt_mfm_incoming/lt_mfm_outgoing + registry_sync_meta (22,555 rows synced live)
- app_config: UPDATE validation.phase_suffixes (compound forms); INSERT validation.plumbing_columns, validation.event_name_pattern

### 7. Declined / out of scope for this run (validation-layer charter)
- F2 fill display-sibling seed leakage (ems_exec/executor/fill.py) · F8 blind leaf tracking (host verdicts) · F10 ems_backend energy-power panel strategy zeros · F4 kWh-from-kW derivation rows · card-5 emit prompt shrink · nameplate capacity seeding from names (rated_capacity_kva NULL x320 — sync mirrors it as-is; a nameplate seed stays the render-guarantee re-seed task) · col_dict device_mappings wired/formula join (kept information_schema base deliberately: 7 physical-but-unmapped accumulation columns are REAL data the mapped-set-only dictionary would drop)

### 8. Tests
- NEW tests/test_validate_streamline.py (17 non-live: dense/sparse/dead/panel synthetic frames, rollup, folded-verdict gates, class order, name-class port, event/numeric patterns, expected-gap assembly)
- Updated stale private-id anchors (AHU-5 37→canonical 36) + pass_with_gaps in test_layer1b_asset_resolve/test_orchestrator/test_validate; canonical PCC/Transformer-01 acceptance asserts added.
- FINAL TEST RESULT: `pytest -m 'not live'` → 193 passed, 14 skipped, 40 deselected, 0 failed (251s). End-to-end test_pipeline_live_join (real 1a∥1b + rewired harness) passed with AHU-5 at canonical id 36. Live spot-checks: PCC panels 317-320 green w/ feeders (panel_members 4/8, 18/22), Transformer-01=171 single-meter, dead GIC-01-N2-Spare → honest no_data + 246 data-bearing alternatives (no ghost rows offered). HOST NOT RESTARTED (offline mandate) — the Verify agent restarts :8770 and runs the live sweep.

## VERIFY RUN (2026-07-04, agent: verify — host RESTARTED)

- (1) `pytest -m 'not live'` FULL: **193 passed, 14 skipped, 40 deselected, 0 failed** (253.9s). GREEN.
- (5) run/harness.py READ-CONFIRMED: pipeline order = 1a∥1b → infra degrade gate → granularity reconcile → `_validate()` (pre-L2, line ~195) → validation-outage degrade re-check (honest `data_unavailable` terminal BEFORE L2) → pre-flight expected-gap re-route (re-validates) → `validation_blocked` + asset gates → Layer 2 (`_reflect_loop`) → post-settle `payload_final`. In-loop re-routes re-validate before re-emit. ALL data/asset/class validation runs BEFORE Layer 2. before_layer2=TRUE.
- (2) host :8770 killed + restarted via mandated command; /api/health `{"ok": true}`.
- (3) broad survey: re-running the AUDIT-4 25-prompt set + P26 'real-time power and current for Transformer 01' → /tmp/verify_v48/P*.json (results below when complete).
