> Part of the V48 build-spec. REWRITTEN 2026-06-29 to the **payload-morph model** (Decision A, hybrid). See `V48_PAYLOAD_MORPH_CORRECTION.md` for the authoritative correction and `V48_BUILD_SPEC.md` for the index.

## Atomic folder skeleton — payload-morph model

> **⚠ EXPANDED + LAID DOWN (2026-06-29).** The skeleton below was the 115-file first pass; it has since been laid down on disk as a **finer-grained 272-file tree** (deeper sub-folders, one file per provision) for smoother debugging. **The on-disk `pipeline_v48/` tree is authoritative.** Key splits vs the tree pictured below:
> - `layer2/metadata_producer.py` → **`layer2/emit/metadata/`** (one file per payload_shape: heatmap/rail/footer/hpq_*/kpi/progress/sankey/radar/table/text/sld/3d + base + dual_owned_slots).
> - `layer2/data_instruction_emitter.py` → **`layer2/emit/data/`** (one file per field-kind: raw/derived/const/event/text + envelope + fill_mode). Swap gate → **`layer2/swap/`** (one file per gate rule). Catalog reads → **`layer2/catalog/`** (one per table).
> - `workers/` → **`workers/fill/{kinds,sources}`**, **`workers/aggregate/{builders,semantics}`**, **`workers/sharedctx/`** (one file per Approach-B generalization), **`workers/stitch/`** (one file per merge step).
> - `frames/` → **`frames/{dialects,snapshots,quirks}`** + `resolver.py` (data_fill_shape from card_handling) + `payload_shape_map.py`.
> - `data/` → **`data/{cmd_catalog,registry,lt_panels}`** (per-DB, per-table). `layer1a/` and `layer1b/` gained **`prompts/ db_reads/ partition_inputs/ parse/ resolve/ basket/ guardrail/`** sub-folders. `registries/` → **`registries/{rtm,hpq}`**. `contracts/` gained **`invariants/`** (one file per §B4 rule).
> - **NEW `open_items/`** — one documented file per OPEN decision ($ctx form, column_row, data_fill_shape source, partition orphan 160, composite/sld, test-db, the 10 review fixes, FE-interdependency) so each has a debug/decision home. `run/` gained **`run/phases/`** (p0–p6). `tests/` is finer (20 files).
> The conceptual build-spec→file and spec-section→file mappings further below still hold — single files simply became sub-folders. Counts: **272 scaffold files across 16 top-level folders**; every `.py` compiles.

This is the proposed `pipeline_v48/` tree. It honors guiding rule #1 (one dedicated single-purpose file per concern; each layer = a small folder of single-purpose pieces) AND the corrected payload-morph contract.

### What the morph changed (read this first)

The morph is an **intra-card OUTPUT-shape change at Layer 2 and downstream** — it does NOT touch routing (1a) or asset/column resolution (1b). The new invariants this skeleton encodes:

1. **Card contract = ONE payload per card = `{data + metadata}`, ONE flat object, every key EXACTLY once, no second `root`, ZERO design-system chrome, byte-identical defaults** (CMD V2 §B4, `/home/rohith/CMD_V2/CLAUDE.md`).
2. **Layer 2 per-card OUTPUT = `{ exact_metadata, data_instructions }`** (Decision A, hybrid):
   - the AI authors the FINISHED **`exact_metadata`** block (labels/units/rosters/order/thresholds/contracts/colors/badges/tabs — byte-identical defaults copied from the CMD config/token registries);
   - the AI emits PARSEABLE **`data_instructions`** = a *resolved* `card_data_recipe.fields` (each field carries `kind/role/metric/label/unit/selects/filters_table` PLUS the resolution delta `column/agg/source/sql_fragment/base_columns/edge/value/has_data` + a per-card envelope `payload_shape/orientation/entity_dim/selection_dim/binding/window`).
3. **The HOOK/HELPER functions PARSE `data_instructions` and FILL the DATA tier.** The worker NEVER touches `exact_metadata`. Two interchangeable fill sources land in the IDENTICAL Snapshot shape: **live** (socket/`fetch_live`/`fetch_bucketed`) and **test-db** (Postgres fixture). `const` fields are baked literals, never queried.
4. **The per-tab "dialects" (`flat_asset`/`widgets_envelope`/`column_row`) survive ONLY as the DATA-FILL (mapper-input) shape the helpers target** — they become the `frames/` data-fill builders. They are NO LONGER a Layer-2 OUTPUT.
5. **Approach B (interdependent groups):** a group atom holds NO data (points at the shared buffer) but carries its OWN `exact_metadata` block + its own `data_instructions.fields[]`. The hook owns the single cursor/selection. **Frontend interdependency wiring is STILL IN PROGRESS — provisional, grounded on RTM.**
6. **§B4 build rules:** one payload/card, every key once, no root, byte-identical default, producer-always-populates, new renderers opt-in default-OFF, **LIVE Storybook-sentinel verification is the acceptance gate** (mutate ONE metadata field at :6008, read the card DOM).

Validated build references = **RTM** (`HeatmapViewModel` + `RailViewModel`) + **panel-overview HPQ** (`HpqPresentation`) — the byte-accurate templates. NOTE the morph itself is now WIDESPREAD, not a 2-tab island: a live §B4-sentinel sweep (`V48_STORYBOOK_MORPH_VERIFICATION.md`, 2026-06-29) shows ~36/59 EMS cards are strongly/moderately payload-driven across ALL panels (Equipment-Detail Power-Quality 7/9, V&C 8/12, Energy&Power 5/7, Panel-Overview ED 3/3 …). The OLD "only RTM+HPQ are morphed" claim is SUPERSEDED. The punch-list (~23 weak/zero cards: V&C hardcoded sub-cards with the known-wrong Max:430KW/Min:410KW unit bug, some aggregate cards) is where chrome is still hardcoded — for those V48 emits DATA-only until the CMD V2 morph lands.

### The anti-pattern V48 replaces — V47's flat dump (DO NOT repeat)

V47 is **45+ `.py` files in one flat directory**, mixing layers, prompts, DB reads, parsers, builders, one-off migration scripts, and tests together:

```
pipeline_v47/                      ← ANTI-PATTERN: flat, monolithic, no layer boundaries
  pipeline.py            ← route_l1 + narrate + collapse_combos + number_gates + fill() + db() + llm() + main() loop  (one 600-line god-file mixing ALL concerns)
  column_resolve.py      ← resolve_asset + ASSET_SYSTEM prompt + resolve_columns + SYSTEM prompt + layer35_correct + loads_lenient + q()  (asset+column+parser+prompt+dbclient ALL inline)
  layer2_swap.py         ← SYSTEM prompt + build_user + run + gate  (prompt buried inside code)
  l6.py  l6_2.py  ems_aggregate.py  panel_resolve.py  render_contract.py  layer4.py
  ai_log.py  reslice_server.py  number_gates.py  gate_check.py  slots.py  ...
  build_topology_db.py  load_recipes.py  load_layouts.py  ...  (20+ one-off DB-build scripts intermixed)
  test_column_resolve.py  test_render_contract.py  ...  (tests intermixed with runtime)
```
Problems: prompts inline as string constants (no single place to edit a prompt); `pipeline.py`/`column_resolve.py` each hold 4–6 unrelated concerns; the DATA-fill, parser, prompt, and schema for one layer scattered across 3 files; migration scripts pollute the runtime namespace. V48 fixes this with a folder-per-layer, file-per-concern tree — and now cleanly separates **metadata authoring (layer2)** from **data filling (workers)**.

### V48 atomic tree (morph model)

```
pipeline_v48/
│
├── run/                                    ← orchestrator / run-harness (frontend-prompt entry) [spec §1, contract 8]
│   ├── __init__.py
│   ├── entry.py                            One public run(prompt, run_id, env) — frontend-prompt entry; returns PageFrameEnvelope of {exact_metadata+data} cards
│   ├── harness.py                          Wiring: fires 1a ∥ 1b simultaneously, joins, drives Layer 2 partition→Move1/2/3→assemble [spec §1, §wiring]
│   ├── fanout.py                           Parallel-per-card executor + the one-time group shared-context pre-pass before fan-out [spec §1 refinement]
│   ├── state.py                            OrchestratorState dataclass — single mutable run state threaded across phases [contract 8]
│   ├── asset_choice_gate.py               awaiting_asset_choice: write asset_choice.json on 1b-ambiguous, return; resume on PIPELINE_ASSET_ID [spec §1, contract 8, §1b]
│   └── assemble.py                         Final per-page assembly: stitch exact_metadata+data into ONE flat no-root payload/card, attach layout, emit PageFrameEnvelope [contract 7]
│
├── layer1a/                                ← storytelling router: Template + per-card story (UNCHANGED by morph) [spec §2 L1a, constraint #19, contract 2]
│   ├── __init__.py
│   ├── prompt.md                           1a SYSTEM prompt (narrative router; route by ANALYTICAL INTENT not keyword; emit page-level story) — its OWN file
│   ├── reroute_clause.md                   avoid_ctx re-route clause text — separate prompt fragment
│   ├── db_reads.py                         cmd_catalog reads for 1a: page_specs (status='live'), cards intent prose, page_layout_cards⋈cards titles, page_handling view [spec §10 1a]
│   ├── partition_inputs.py                 Reads Step-0 coupling sources: card_link, cards.interdependency prose, card_combo/member, selection_dimension, page_control, v_interaction [spec §6, contract 2]
│   ├── story_builder.py                    Page-level story + per-card analytical_story from analytical_theme + reusable_answers (post-LLM enrichment) [spec §2 L1a]
│   ├── parser.py                           Parses LLM JSON (strip <think>, loads_lenient), verbatim-page_key fallback, metric/intent defaults [v47-prompts §L1]
│   └── schema.py                           Layer1aOutput validator/builder [contract 2]
│
├── layer1b/                                ← asset resolve + card-agnostic column basket (UNCHANGED by morph) [spec §2 L1b, constraints #14/#20, contract 3]
│   ├── __init__.py
│   ├── asset_prompt.md                     ASSET_SYSTEM prompt (class discriminator, class-from-subject inference, confident/ambiguous/empty contract) — its OWN file
│   ├── column_prompt.md                    Column-resolver SYSTEM prompt run WITHOUT recipe_fields (card-agnostic GENEROUS basket; bind only real columns) — its OWN file
│   ├── asset_resolve.py                    resolve_asset over lt_mfm: confident pin / ambiguous candidates / empty; PIPELINE_ASSET_ID skip path [spec §2 L1b]
│   ├── candidate_list.py                   Ambiguous-asset candidate_list (mfm_id,name,class,load_group,panel_id,has_data) for the AssetPicker [constraint #14, contract 3]
│   ├── column_basket.py                    resolve_columns card-agnostic: GENEROUS feasible+probable across asset table(s)+topology siblings [spec §2 L1b, constraint #20]
│   ├── derived_reconcile.py               derived_metrics.base_columns ∩ live lt_panels schema (the *_today_kwh vs *_import_kwh drift) [db-reads §1b]
│   ├── spelling_recovery.py               L3.5 anti-hallucination: difflib fuzzy + _same_family gate + _retry_one LLM [v47-prompts §L3 guardrail]
│   ├── parser.py                           loads_lenient truncation-salvage parser [v47-prompts shared parser]
│   └── schema.py                           Layer1bOutput validator/builder [contract 3]
│
├── layer2/                                 ← per-card: swap + emit {exact_metadata, data_instructions} (MORPH CORE) [spec §2 L2, constraints #6/#7/#12/#13, contracts 4/5]
│   ├── __init__.py
│   ├── swap_prompt.md                      L2 swap SYSTEM prompt (KEEP-default; swap only on PROVABLE relevance to 1a's STORY ANGLE; no-dup; cascade combos) — its OWN file
│   ├── metadata_prompt.md                  ★ NEW. The exact_metadata AUTHORING prompt: emit the FINISHED METADATA block for the card's payload_shape (labels/units/rosters/order/thresholds/contracts/colors/badges/tabs), byte-identical defaults from the CMD registries — its OWN file
│   ├── data_instruction_prompt.md          ★ NEW. The data_instructions AUTHORING prompt: per recipe field bind kind raw/event/derived/const/text → {column, agg, source(live|test-db|const), value?}; emit the per-card envelope (payload_shape/orientation/binding/window) — its OWN file
│   ├── card_input.py                       Assembles Layer2CardInput per card: 1a story + 1b asset/basket + catalog_row + shared_ctx_ref [contract 4]
│   ├── catalog_row.py                      Reads FULL per-card cmd_catalog detail keyed by card_id: card_data_recipe(fields/reconciled_fields/payload_shape/orientation/entity_dim/selection_dim/selection_role), card_controls, contract_components(payload_schema_json/canonical_shape), card_handling(payload_family/handling_class/backend_strategy), card_grid_size, feasibility [spec §10 L2]
│   ├── swap_candidates.py                  ±15% card_grid_size pool: off-page, verdict='render_real', NOT in template_card_ids [contract 4]
│   ├── swap.py                             L2 swap decision + deterministic gate (conf≥0.9, vague-reject, offered-pool valid(), no-dup, all-or-nothing cascade) [spec §2 L2, constraint #13]
│   ├── metadata_producer.py               ★ NEW (MORPH). Authors the per-card exact_metadata block: copies the byte-identical defaults from the CMD registries (HEATMAP_CARD_TITLE/METRIC_DEFS/STATUS_COLORS/SECTION_HEADER_CHROME/RT_DIR_PRESETS/FOCUS_META/DEFAULT_HPQ_LIMITS…), applies AI label/unit/order/threshold choices, and emits the matching shape (HeatmapViewModel/RailViewModel METADATA keys; HpqPresentation.<card> block). Marks the two AI-default-DATA-OVERRIDABLE slots (RTM sectionContracts; HPQ signature spokes/selectedName). NEVER emits design-system chrome [spec §morph, contract 5 exact_metadata]
│   ├── data_instruction_emitter.py        ★ NEW (MORPH). Emits the per-card data_instructions: takes the recipe (card_data_recipe.fields) + 1b column basket, runs the card-specific column resolve, pins each field's column/agg, decides per-field source (live|test-db|const), packs the per-card envelope {payload_shape, orientation, entity_dim, selection_dim, selection_role, binding{table,ts_col,nameplate_scope}, window{lookback,sampling,time_mode}} + fields[] = the resolved recipe the workers PARSE-and-FILL. Holds NO data [spec §4, constraint #7, contract 5 data_instructions]
│   ├── card_resolve.py                     Card-specific column resolve (recipe-driven, recipe_fields=fields) + SAFE COLUMN-OVERRIDE fixing 'every tile = active_power'; feeds data_instruction_emitter [spec §5 L3-card-specific]
│   ├── recipe_reconcile.py                Reconciles recipe fields vs contract_components.payload_schema_json (persists reconciled_fields); FAIL-OPEN [v47-prompts §L5.2]
│   ├── fill_mode.py                        Per-FIELD source decision feeding data_instructions: live (bind) vs test-db (baked from fixture, identical Snapshot shape) vs const (literal) [spec §4, constraint #7, contract 5 source]
│   ├── atom_emit.py                        Group-card path (Approach B): emit lean atom carrying its OWN exact_metadata + its OWN data_instructions.fields[] but source pointing at the shared buffer (NO baked data); selection_role produces|consumes|emits [spec §6 Move2, constraint #9, contract 5 atom — PROVISIONAL, FE interdependency in progress]  ⚠ OPEN: the $ctx source FORM (bare `$ctx` vs dotted `$ctx.<buffer>` vs bare + `buffer_key` sibling) is UNRESOLVED across the build-spec (SIGNATURES uses dotted `$ctx.<buffer>`); pending user — pick one and align all four files
│   ├── standalone_emit.py                 Standalone-card path: emit {exact_metadata, data_instructions} with concrete source (live|test-db) [spec §3, constraint #6, contract 5]
│   ├── parser.py                           loads_lenient + L5.5-style self-correction loop on parse/truncation rejects [v47-prompts §L5.5]
│   └── schema.py                           Layer2CardInput + Layer2CardOutput validators (Layer2CardOutput = {exact_metadata, data_instructions}) [contracts 4, 5]
│
├── workers/                                ← deterministic DATA-FILL + aggregation + shared-context + stitch (the helper that PARSES data_instructions) [spec §4/§5/§6, constraints #8/#9, worker-aggregation]
│   ├── __init__.py
│   ├── dispatch.py                         fill(card_output, scope, panel_mfm_id, window, focus)→DATA tier. Routes by scope: panel→aggregate; else single-asset series. NEVER touches exact_metadata [worker seam, contract 7]
│   ├── data_fill.py                        ★ NEW (MORPH). PARSES data_instructions.fields[] and FILLS the named DATA keys of the payload. Per field: raw→column AVG/last, derived→sql_fragment(:NAME from nameplate), event→rising-edge COUNT, const→bake value, text→label column. Emits into the Snapshot/frame shape the FE mapper targets. Source-agnostic: same output for live frame or test-db fixture [spec §4, constraint #8, contract 7 DATA tier]
│   ├── live_source.py                      DATA-fill source = live: fetch_live/fetch_bucketed over lt_panels (the socket-equivalent path), bound by :start/:end/:bucket from window [spec §4 source=live]
│   ├── test_db_source.py                   ★ DATA-fill source = test-db: bake the SAME nested payload from the test DB (Decision B, interchangeable at the mapper boundary). DB_TARGET-parameterized [spec §9 DB2, constraint #18, contract 1 DB_TARGET]  ⚠ OPEN: the test DB is DEFERRED — build it + decide its contents (mock/golden) only AFTER the pipeline is implemented; the initial-implementation data source is NOT yet decided (pending user)
│   ├── window.py                           WINDOW_BOUNDS + _bucket_sql: today/last-7-days/hourly/shift=8h…; :start/:end/:bucket bind params so re-slice = re-bind only [worker time layer, spec §7]
│   ├── spec_seam.py                        Reads the AI's aggregation SPEC out of data_instructions (strategy/window/group_by/subset/derived fields) [spec §4, constraint #8 AI-provides-spec]
│   ├── aggregate.py                        Aggregation dispatcher: keys on contract component + per-card overrides; calls the builders below; reuses EMS semantics verbatim (energy_delta value@end−value@start NOT max−min; now_expr=max(ts); group by load_group) [worker-agg seam]
│   ├── energy_distribution.py             Aggregate builder: rail sources/consumers + 5-layer sankey + loss_pct/share_pct/efficiency_pct [worker-agg builder 1]
│   ├── panel_overview.py                   Aggregate builder: EnergySingleLineDiagram PanelOverviewData (SLD identity/incomers/outgoings + per-node KPIs) [worker-agg builder 2]
│   ├── demand_profile.py                   Aggregate builder: per-feeder-group power over buckets + peak/load-factor [worker-agg builder 3]
│   ├── current_distribution.py            Aggregate builder: RadarChart spokes (latest current_avg per feeder vs fleet mean) [worker-agg builder 4]
│   ├── feeder_pq.py                        Aggregate builder: per-feeder PQ table (I-THD/V-THD/PF/K/score→rank/severity/driver) [worker-agg builder 5]
│   ├── other_panels_events.py             Aggregate builder: per-feeder V/I + unbalance + rule-classified cause [worker-agg builder 6]
│   ├── validate.py                         Per-DATA-payload validate() (real structure + some non-null; recognizes sources/consumers/incomers/points/spokes/rows) honest-degrade, never fabricate [worker-agg, constraint #17]
│   ├── shared_context_builder.py          ★ Move-1 worker: build shared_context DATA ONCE per group (history[] HistorySample[] + buffers + interaction seeds + config). Group atoms point HERE [spec §6 Move1, contract 6, interdep §3 — PROVISIONAL]
│   ├── stitcher.py                         ★ Move-3 deterministic merge: for each card flatten {...exact_metadata, ...filled_data} into ONE no-root payload (every key once); attach $ctx to group atoms, resolve multi-buffer $id, emit {shared_context, cards:[payloads]} [spec §6 Move3, contract 7, MORPH §B4 one-payload]
│   └── reslice.py                          Re-invokable DATA-fill for a new window/drill-down (retained interactivity); re-binds :start/:end/:bucket, re-runs aggregate; stamps payload.focused AFTER validation. exact_metadata untouched [spec §7 interactivity]
│
├── frames/                                 ← the DATA-FILL TARGET shapes (the surviving "dialects" the helper fills INTO; NOT a Layer-2 output) [spec §3, frame-contract]
│   ├── __init__.py
│   ├── flat_asset.py                       DATA-fill target: FlatAssetPageFrame DATA shape (DG/transformer/UPS): {asset_id, snapshot, <historyArrays>}. data_fill.py writes the DATA keys here [frame-contract DIALECT 1 = flat_asset]
│   ├── widgets_envelope.py                DATA-fill target: AggregateSnapshotFrame DATA shape (electrical/lt-pcc): {mfm_id,…,widgets} + isAggregateEnvelope discriminator [frame-contract DIALECT 2 = widgets_envelope]
│   ├── column_row.py                       DATA-fill target: column_row DATA shape (per-meter row tables) [frame-contract DIALECT 3 = column_row]
│   ├── snapshot_shape.py                   The canonical Snapshot DATA shapes the FE mappers consume (RealTimeMonitoringSnapshot.history[]/FeederReading; PanelHarmonicsPqSnapshot.{periods,apiExtras}) — live and test-db both target these [morph, hook-helper §DATA-fill]
│   ├── quirks.py                            Reproduce exact DATA quirks: load_factor_pct fraction-vs-percent, synthetic loss/unmetered sankey node mfm_id:null, pending/error frames [constraint #22]
│   └── config_endpoint.py                 Populate GET /api/mfm/{id}/config/ (rated_kw nameplate) for y-axis auto-scale — NOT in the WS frame [constraint #21, contract 7 config_endpoint]
│
├── partition/                              ← Step-0 interdependency group detection (deterministic; UNCHANGED by morph) [spec §6 Step-0, contract 2]
│   ├── __init__.py
│   ├── group_detect.py                     Transitive-closure grouping over card_link/prose/combo/selection edges → groups + standalone_card_ids [spec §6, interdep §1]
│   └── coupling_lookup.py                  Resolves each edge's coupling rows from cmd_catalog (card_link/selection_dimension); AI never invents these [spec §6 Move2, contract 6 couplings]
│
├── data/                                   ← deterministic data-access layer (the ONLY DB clients) [spec §9 three DBs, worker-agg data-access]
│   ├── __init__.py
│   ├── db_client.py                        q(db, sql): psql -U postgres -d <db> --csv -t; raises on non-zero (no silent empty) [worker-agg q() helper]
│   ├── cmd_catalog.py                      cmd_catalog reads shared across layers (the metadata/recipe input DB) — status='live' filter centralized here [spec §9 DB1]
│   ├── registry.py                         lt_panels_db reads: lt_mfm, lt_mfm_type, lt_parameter/asset_parameter, lt_config_* (capacity) [spec §9 DB3 registry]
│   ├── lt_panels.py                        lt_panels time-series reads: per-meter tables, energy_delta, now_expr, _node_electrical, _bucketed, _table_cols cache [spec §9]
│   ├── panel_members.py                    panel_members(mfm_id): topology gotcha (panel=to_mfm; outgoing→source, incoming→consumer; exclude spare%) [worker-agg member resolution]
│   ├── derived_metrics.py                 derived_metrics formula library (metric_key/base_columns/sql_fragment/nameplate_refs) — the kind:derived data_instructions resolve against [spec §9, data-instruction-shape]
│   └── nameplate.py                        nameplate_config (scope/key/value: RATED_POWER_KW=500, V_NOM=415, mfm_type:hv V_NOM=11000) — supplies :NAME literals to derived sql_fragments [spec §9]
│
├── registries/                             ← BYTE-IDENTICAL DEFAULT SOURCES the metadata_producer copies from (mirror of CMD config/token registries) [morph §B4 byte-identical]
│   ├── __init__.py
│   ├── rtm_defaults.py                     HEATMAP_CARD_TITLE/METRIC_DEFS/STATUS_COLORS/STATUS_LEGEND/SECTION_HEADER_CHROME/SELECTION_COLORS/DEFAULT_BAND_THRESHOLDS/SECTION_CONTRACT_KW/RT_DIR_PRESETS/RAIL_TONE_TO_DS/BREAKDOWN_COLORS [morph RTM metadata defaults]
│   ├── hpq_defaults.py                     FOCUS_META/PRESENTATION_LABELS/DEFAULT_HPQ_LIMITS/strip-tile-order/feeder-column-order/driverCodeMap/signature palette+style [morph HPQ metadata defaults]
│   └── tokens.py                            The DS TOKENS the defaults reference (brand[500], warm[700], graph.purple500…) — used ONLY as default VALUES, never as live chrome [morph byte-identical]
│
├── contracts/                              ← the inter-layer JSON Schemas, one file each (the authoritative shapes) [all contracts, constraint #4]
│   ├── pipeline_input.schema.json          Contract 1 — PipelineInput (prompt, run_id, env, DB_TARGET)
│   ├── layer1a_output.schema.json          Contract 2 — Layer1aOutput (Template + per-card story + interdependency_groups)
│   ├── layer1b_output.schema.json          Contract 3 — Layer1bOutput (asset + candidate_list + column_basket)
│   ├── layer2_card_input.schema.json       Contract 4 — Layer2CardInput
│   ├── layer2_card_output.schema.json      Contract 5 — ★ Layer2CardOutput = { exact_metadata, data_instructions } (+ swap, atom-vs-standalone, per-field source) [MORPH]
│   ├── exact_metadata.schema.json          ★ NEW. The exact_metadata block shape per payload_shape (Heatmap/Rail/HpqStrip/Timeline/AiSummary/FeederTable/Signature METADATA keys) [MORPH, contract 5]
│   ├── data_instructions.schema.json       ★ NEW. The data_instructions shape: per-card envelope + fields[] (kind/role/metric/column/agg/source/value/sql_fragment/edge/has_data) [MORPH, contract 5]
│   ├── shared_context.schema.json          Contract 6 — SharedContext (DATA buffers + interaction seeds + couplings)
│   ├── page_frame_envelope.schema.json     Contract 7 — PageFrameEnvelope (per-page emit; cards = ONE flat {data+metadata} payload each, no root)
│   ├── orchestrator_state.schema.json      Contract 8 — OrchestratorState
│   └── validate.py                         Tiny shared $ref-resolving JSON-Schema validator used by every layer's schema.py
│
├── llm/                                    ← the single Qwen 3.6 call convention (no layer re-implements it) [constraint #3]
│   ├── __init__.py
│   ├── client.py                           POST :8200/v1/chat/completions, MODEL=Qwen/Qwen3.6-35B-A3B-FP8, temp 0, json_object, enable_thinking=False, strip <think>, FAIL-OPEN [constraint #3]
│   └── config.py                           LLM_URL / MODEL constants (overridable via env) [contract 1 env]
│
├── obs/                                    ← failure logging + observability (NO reloop / NO re-route) [constraint #17, contract 8 failures]
│   ├── __init__.py
│   ├── ai_log.py                           Monkeypatches urllib → logs EVERY :8200 call to logs/ai_<run_id>.jsonl (import FIRST) [interdep §6]
│   └── failures.py                         Append-only failure recorder: {stage, card_id?, group_id?, reason, detail}; never triggers reloop/re-route [constraint #17]
│
├── outputs/                                ← run artifacts (gitignored except .gitkeep) [contract 1/8]
│   ├── .gitkeep
│   ├── asset_choice.json                   Written when 1b ambiguous; consumed by frontend AssetPicker [constraint #14, contract 8]
│   ├── page_frame.<run_id>.json            The assembled PageFrameEnvelope per run (ONE flat {data+metadata} payload/card) [contract 7]
│   └── logs/
│       └── ai_<run_id>.jsonl               Per-run LLM call log (written by obs/ai_log.py)
│
├── fe_contract/                            ← the FE-OWNED hook integration CONTRACT (NOT code V48 writes; IN PROGRESS) [morph §Approach-B, interdep §7, constraint #10]
│   ├── README.md                           ★ States explicitly: the hook (useRealTimeMonitoringData-style) is OWNED BY THE FRONTEND. V48 emits {exact_metadata, data_instructions}+DATA; the FE hook owns live state, interactivity, interdependency (5 useState cells + handlers), and recomputes per-card payloads via useMemo. This folder is the CONTRACT V48 must satisfy, not files V48 ships.
│   ├── hook_contract.md                    The DATA/METADATA/UI-selection three-boundary split the FE hook implements: payload carries only a read-only SEED of interaction state; writes flow UP via setters; one setter → all interdependent useMemos recompute (Approach B). PROVISIONAL — frontend interdependency wiring STILL IN PROGRESS.
│   ├── mapper_contract.md                  The Snapshot shapes the FE mapper boundary consumes (RealTimeMonitoringSnapshot / PanelHarmonicsPqSnapshot) — what `frames/` DATA-fill must target so live and test-db are interchangeable.
│   └── acceptance_sentinel.md              The LIVE Storybook-sentinel acceptance gate (mutate ONE exact_metadata field at :6008, read the card DOM moves). The §B4 verification rule — NOT golden-payload comparison (green RTL + byte-identical defaults hid 3 real RTM gaps).
│
├── tests/                                  ← tests live in their OWN folder (NOT intermixed with runtime)
│   ├── test_layer1a_routing.py
│   ├── test_layer1b_asset_basket.py
│   ├── test_layer2_swap_dedup.py
│   ├── test_layer2_exact_metadata.py        ★ exact_metadata byte-identical-default + no-chrome assertions
│   ├── test_layer2_data_instructions.py     ★ data_instructions = resolved recipe (column/agg/source per field) assertions
│   ├── test_workers_data_fill.py            ★ parse data_instructions → fill DATA; live-vs-test-db produce IDENTICAL Snapshot shape
│   ├── test_workers_aggregation.py          (incl. verified panel-174: 4 sources / 10 consumers)
│   ├── test_stitcher_one_payload.py         ★ {...exact_metadata, ...data} flattens to ONE no-root payload, every key once
│   ├── test_partition_groups.py             (incl. verified RTM: 17 edges, combo id=24)
│   ├── test_frames_dialects.py
│   └── test_contracts.py                    Validates every schema in contracts/ round-trips
│
├── db_build/                               ← one-off cmd_catalog rebuild scripts QUARANTINED here (NOT in the runtime namespace) [spec §11]
│   ├── rebuild_sql/                         (existing) — staged upsert SQL: card_link.sql, page_control.sql, card_combo.sql, pagespecs_*.sql, ...
│   ├── rebuild_snapshots/                   (existing) — v47 backup + per-table json snapshots (inventory lock)
│   └── apply.sh                             Wrapper over rebuild_sql/apply_sql.sh (additive upsert; ID-stable; status=live/deprecated/scratch)
│
├── docs/                                   ← the existing design markdowns (the spec spine)
│   ├── V48_PAYLOAD_MORPH_CORRECTION.md      ★ the authoritative corrected model (this skeleton reflects it)
│   ├── V48_STORYBOOK_MORPH_VERIFICATION.md   ★ live §B4-sentinel per-card morph map (~36/59 payload-driven) — the current morph-status ground truth
│   ├── V48_DESIGN_NOTES.md
│   ├── V48_INTERDEPENDENT_CARDS_DESIGN.md
│   ├── CMDV2_PAYLOAD_VERIFICATION.md
│   ├── CMDV2_CARD_ATOMIZATION_AUDIT.md
│   ├── CMD_CATALOG_REBUILD_PLAN.md
│   ├── INVENTORY_LOCK.md
│   ├── V47_DB_REFERENCE.md
│   └── V47_PIPELINE_FLOW.md
│
└── README.md                               Top-level map: 3-layer wiring, metadata-vs-data split, where each concern lives, how to run
```

### Build-spec → file map (the load-bearing constraints, morph model)

| Build-spec item | File(s) |
|---|---|
| **MORPH §B4 one payload/card = {data+metadata}, no root, every key once** | `workers/stitcher.py` (the flatten), `run/assemble.py`, `contracts/page_frame_envelope.schema.json` |
| **MORPH Layer 2 OUTPUT = {exact_metadata, data_instructions}** | `layer2/metadata_producer.py` + `layer2/data_instruction_emitter.py`; `contracts/layer2_card_output.schema.json` |
| **MORPH exact_metadata = AI-authored finished METADATA block, byte-identical defaults** | `layer2/metadata_producer.py` + `layer2/metadata_prompt.md` + `registries/*`; `contracts/exact_metadata.schema.json` |
| **MORPH data_instructions = resolved card_data_recipe.fields (recipe-as-binding)** | `layer2/data_instruction_emitter.py` + `layer2/data_instruction_prompt.md` + `layer2/card_resolve.py`; `contracts/data_instructions.schema.json` |
| **MORPH helper PARSES data_instructions → FILLS the DATA tier** | `workers/data_fill.py` (+ `workers/live_source.py` / `workers/test_db_source.py`); `frames/*` are the fill targets |
| **MORPH dialects survive ONLY as the DATA-FILL target shape** | `frames/flat_asset.py` / `frames/widgets_envelope.py` / `frames/column_row.py` / `frames/snapshot_shape.py` |
| **MORPH live vs test-db interchangeable at the mapper boundary (Decision B)** | `workers/live_source.py` + `workers/test_db_source.py` → same `frames/snapshot_shape.py` |
| **MORPH per-field source (live\|test-db\|const)** | `layer2/fill_mode.py` (per-field decision); `workers/data_fill.py` (executes) |
| **MORPH FE hook integration = a CONTRACT the FE owns (in progress)** | `fe_contract/` (markdown contracts ONLY — V48 writes NO hook code) |
| **MORPH acceptance = LIVE Storybook sentinel** | `fe_contract/acceptance_sentinel.md`; enforced by mutate-one-field, not golden payload |
| #1 exactly 3 layers | `layer1a/`, `layer1b/`, `layer2/` (three folders; no fourth) |
| #2 all pure-AI; deterministic only supports | AI in `*/prompt.md`+`*/*.py` LLM calls; support in `data/`, `workers/`, `partition/`, `frames/`, `registries/`, `run/` |
| #3 Qwen 3.6 mandatory in every layer | `llm/client.py` (single call site; each layer imports it) |
| #4 atomic file-per-concern | the whole tree — every prompt is `.md`, every DB-read/parser/schema/builder its own module |
| #5 wiring (1a∥1b → join → L2 fan-out + pre-pass) | `run/harness.py`, `run/fanout.py` |
| #6 emit at backend-frame boundary | `frames/*` (DATA-fill targets), `layer2/standalone_emit.py`, `workers/data_fill.py` |
| #7 per-card flexible fill (live / test-db / baked) | `layer2/fill_mode.py`, `layer2/data_instruction_emitter.py`, `workers/{live_source,test_db_source,data_fill}.py` |
| #8 aggregation in V48 workers, NOT backend2 | `workers/aggregate.py` + the 6 builders (self-contained); `catalog_row.backend_strategy` reference-only |
| #9 functions never travel in payload | `layer2/atom_emit.py` + `workers/shared_context_builder.py` (data-only); `workers/stitcher.py` emits plain JSON |
| #10 Approach B + 6 generalizations | `workers/shared_context_builder.py`, `workers/stitcher.py`, `partition/`, `fe_contract/` |
| #11 L5 retired, L6/L6.2 → workers, narrate parked | no `render_contract`/`l6` modules; data-fill+aggregation in `workers/`; narrate intentionally absent |
| #12 V47 stage mapping | asset-resolve→`layer1b/asset_resolve.py`; L3 split→`layer1b/column_basket.py`+`layer2/card_resolve.py`; L4→`layer2/swap.py`; L6/L6.2→`workers/*` |
| #13 swap dedup vs 1a's template | `layer2/swap.py` (template_card_ids guard) |
| #14 asset-picker round-trip | `layer1b/candidate_list.py`, `run/asset_choice_gate.py`, `outputs/asset_choice.json` |
| #15 placement + sizes from DB | `layer1a/db_reads.py` + `layer2/catalog_row.py` (card_grid_size); carried in contract 2 `layout`/`slot`/`size` |
| #16 interactivity retained | `layer2/catalog_row.py` (card_controls), `workers/reslice.py`, `fe_contract/hook_contract.md` |
| #17 failures logged, NO reloop/re-route | `obs/failures.py`, `obs/ai_log.py`, `workers/validate.py` (honest-degrade) |
| #18 three DBs + status='live' | `data/cmd_catalog.py`, `data/registry.py`+`data/lt_panels.py`, `workers/test_db_source.py` |
| #19 1a = storytelling router + per-card story | `layer1a/prompt.md`, `layer1a/story_builder.py` |
| #20 1b = card-agnostic full basket | `layer1b/column_basket.py` (resolve WITHOUT recipe_fields) |
| #21 populate /config/ endpoint | `frames/config_endpoint.py` |
| #22 reproduce value-semantics quirks | `frames/quirks.py` |

### Spec-section → file map (the morph sections)

| Spec section | File(s) |
|---|---|
| §1 orchestration / run harness | `run/entry.py`, `run/harness.py`, `run/fanout.py`, `run/state.py`, `run/asset_choice_gate.py` |
| §2 L1a storytelling router (unchanged) | `layer1a/*` |
| §2 L1b asset + card-agnostic basket (unchanged) | `layer1b/*` |
| §2 L2 swap + emit {exact_metadata, data_instructions} | `layer2/swap.py`, `layer2/metadata_producer.py`, `layer2/data_instruction_emitter.py` |
| §3 emit dialects → DATA-fill targets | `frames/*` |
| §4 per-card fill (parse instructions → fill DATA; live vs test-db) | `workers/data_fill.py`, `workers/live_source.py`, `workers/test_db_source.py`, `layer2/fill_mode.py` |
| §5 card-specific column resolve | `layer2/card_resolve.py`, `layer2/recipe_reconcile.py` |
| §6 Step-0 partition + Move1/2/3 (shared_context / atoms / stitch) | `partition/*`, `workers/shared_context_builder.py`, `layer2/atom_emit.py`, `workers/stitcher.py` |
| §7 interactivity / re-slice retained | `workers/reslice.py`, `workers/window.py`, `fe_contract/hook_contract.md` |
| §8 aggregation builders (relocated L6/L6.2) | `workers/aggregate.py` + 6 builders + `workers/validate.py` |
| §9 three DBs + data-access | `data/*`, `workers/test_db_source.py` |
| §10 per-layer DB reads | `layer1a/db_reads.py`, `layer1b` reads, `layer2/catalog_row.py` |
| §11 DB rebuild scripts | `db_build/*` |
| §morph byte-identical defaults | `registries/*`, `layer2/metadata_producer.py` |
| §morph FE hook contract (in progress) | `fe_contract/*` |

### How the contracts map to files (morph model)

Every concern in the inter-layer contracts maps to exactly one file:
- contract 1 → `run/entry.py` + `contracts/pipeline_input.schema.json`
- contract 2 → `layer1a/schema.py`
- contract 3 → `layer1b/schema.py`
- contract 4 → `layer2/schema.py` (Layer2CardInput)
- **contract 5 → `layer2/schema.py` (Layer2CardOutput = {exact_metadata, data_instructions})**, split-detailed in `contracts/exact_metadata.schema.json` + `contracts/data_instructions.schema.json`
- contract 6 → `workers/shared_context_builder.py`
- contract 7 → `run/assemble.py` + `workers/stitcher.py` (the one-payload flatten)
- contract 8 → `run/state.py`

A schema change touches one `.json` in `contracts/`; a prompt change touches one `.md` in a layer folder; a DB-read change touches one module in `data/` or a layer's `db_reads.py`; a byte-identical-default change touches one file in `registries/`; the FE-owned hook is a CONTRACT in `fe_contract/`, never V48 code — localized edits throughout, no V47-style god-files.

### Key structural deltas from the pre-morph skeleton

1. **`layer2/` split the emit:** the old single `frame_emit.py` is replaced by a **metadata producer** (`metadata_producer.py` + `metadata_prompt.md`) and a **data_instruction emitter** (`data_instruction_emitter.py` + `data_instruction_prompt.md`). Layer 2 now outputs `{exact_metadata, data_instructions}`, not a finished frame.
2. **`workers/` gained the DATA-fill:** `data_fill.py` (parse instructions → fill DATA), `live_source.py` + `test_db_source.py` (the two interchangeable sources), `window.py` (re-bind layer), plus the existing aggregation builders, `shared_context_builder.py` (Move-1), `stitcher.py` (Move-3 merge into one payload), and `reslice.py`. The worker NEVER touches `exact_metadata`.
3. **`frames/` became DATA-fill TARGETS, not emit dialects:** the three dialects (`flat_asset`/`widgets_envelope`/`column_row`) + the canonical `snapshot_shape.py` are now the shapes the helper FILLS INTO (mapper input), not a Layer-2 output. `widget_response.py` folded into `snapshot_shape.py`.
4. **NEW `registries/`:** the byte-identical default sources (RTM/HPQ config + DS tokens) the `metadata_producer` copies from — so a default lives in exactly one place.
5. **NEW `fe_contract/` (replaces `frontend/`):** the FE-side hook is now stated explicitly as a CONTRACT the frontend owns (IN PROGRESS), expressed as markdown (`README.md`, `hook_contract.md`, `mapper_contract.md`, `acceptance_sentinel.md`) — **V48 writes NO hook code.** The old `frontend/*.ts` glue is removed.
6. **`contracts/` gained two split schemas:** `exact_metadata.schema.json` + `data_instructions.schema.json` detail the two halves of Layer2CardOutput.
7. **`data/` gained `derived_metrics.py` + `nameplate.py`** as the formula/literal libraries that `kind:derived` instructions resolve against.

### Caveats carried into the skeleton (per the correction doc)

- **Validated full §B4 one-payload reference templates = RTM + panel-overview HPQ** (byte-accurate). The morph itself is WIDESPREAD per the live §B4-sentinel sweep (`V48_STORYBOOK_MORPH_VERIFICATION.md`, ~36/59 cards strongly/moderately payload-driven across ALL panels) — the OLD "only RTM+HPQ morphed / only ~7 cards" claim from the stale `PAYLOAD_AUDIT_ALL` is SUPERSEDED. The remaining ~23 weak/zero punch-list cards still carry hardcoded chrome (V&C hardcoded sub-cards with the known-wrong Max:430KW/Min:410KW unit bug — the "morph next" target; some aggregate cards); for those V48 emits DATA-only and accepts hardcoded chrome until the CMD V2 morph completes.
- **Frontend interdependency wiring is STILL IN PROGRESS** — Approach B (`fe_contract/`, `layer2/atom_emit.py`, `workers/shared_context_builder.py`) is grounded on the RTM single-hook structure but marked PROVISIONAL for the broader cross-card group case.
- **Acceptance gate is LIVE Storybook sentinel** (`fe_contract/acceptance_sentinel.md`) — mutate one `exact_metadata` field at :6008 and read the card DOM. Green RTL tests + byte-identical defaults hid 3 real RTM gaps; do NOT rely on golden-payload comparison alone.
