# pipeline_v48 — End-to-End Walkthrough
*(synthesized 2026-07-02 from 14 subsystem readers, a live runtime probe, and a two-prompt smoke run; contradictions resolved in favor of file-level/run-level evidence and flagged where unresolved)*

---

## 1. Big picture

pipeline_v48 (`/home/rohith/desktop/BFI/backend/layer2/pipeline_v48`) turns a natural-language EMS prompt into a page of **real CMD_V2 React cards filled with live meter data**, under a render-guarantee contract: every card either renders real neuract values or honest-blanks with a machine-readable reason — never mock-as-live, never a crash. Three pure-AI layers (1a storytelling page router ∥ 1b asset+column-basket resolver → Layer 2 per-card `{swap_decision, exact_metadata, data_instructions}` morph-emit against byte-identical harvested Storybook defaults) run against Qwen3.6-35B on vLLM :8200, orchestrated by `run/harness.py:run_pipeline` with a non-AI pandas validation gate and a 2-attempt reflect loop. The data fill then happens **deterministically**: `host/server.py` (:8770) fans each card out to `ems_exec.serve.run.run_card`, which reads the resolved asset's `gic_*` table in `target_version1.neuract` (:5433 tunnel) directly and completes the payload leaf-by-leaf; the Vite frontend (:5188) mounts each card as its real CMD_V2 component via `<Component {...payload}/>`. Two major designed stages — the workers/ WS data-fill and the Layer-3 AI verdict — were **built and then retired on 2026-07-02** in favor of this ems_exec path (archives in `archive/`); the render verdict is now derived deterministically in the host. Everything tunable is a `cmd_catalog` DB row with a code-default fallback.

---

## 2. Data flow: prompt → rendered card (actual execution order)

The requested stage list matches the *designed* flow; two of its stages (workers data-fill, L3 verdict) are retired and one (shared-context pre-pass) is unwired. Below is what actually executes, with the drift called out inline.

### Stage 0 — Entry
`host/web` PromptBar (:5188, with copilot typeahead from :8772/:8201 — prompt-shaping only, zero pipeline coupling) → `POST /api/run {prompt, asset_id?, date_window?}` → `host/server.py::build_response` → `run/harness.py::run_pipeline(prompt)`. `run/run_id.py::make_run_id` gives a deterministic `r_<sha1(prompt)[:10]>`; `obs/ai_log.py` (urllib monkeypatch) tags every :8200 call into `outputs/logs/ai_<run_id>.jsonl`.

### Stage 1 — 1a ∥ 1b (parallel fire + join)
`run/parallel.py::run_parallel` (ThreadPoolExecutor; exceptions returned as values, never raised) runs both legs:

- **Layer 1a** (`layer1a/build.py::run_1a`): `route.py` reads `cmd_catalog.page_specs` (status='live') filtered by `config/available_pages.py` (env > `routable_pages` table > 18-page default) and gated by `parse/template_feasibility_gate.py` (drop template if ≥40% cards unrenderable per `card_feasibility`); **AI call #1** picks `{page_key, metric, intent}`. `story_builder.py` (**AI call #2**) writes one `analytical_story` per card. `db_reads/cards_intent.py` does the 32-column join (`page_layout_cards ⋈ cards ⋈ card_grid_size ⋈ card_data_recipe ⋈ card_handling`); `db_reads/page_layout.py` fetches the grid template.
- **Partition (Step 0, inside 1a)**: `partition/group_detect.py::detect_groups` — union-find over 4 edge sources (`card_link`, `card_combo_member`, `page_control`, `cards.interdependency` prose via `layer1a/partition_inputs/*`) + `fallback_edges.attach_orphans` (same region/tab rescue, marked `[REVIEW G4, OPEN]`) → `interdependency_groups`.
- **Layer 1b** (`layer1b/build.py::run_1b`): `resolve/asset_candidates.py` builds the registry from `meta_data_version1.app_devices ⋈ app_device_tables ⋈ app_gateways` (:5433), tagging value-aware `has_data` (`resolve/has_data.py`: latest row ≥3 non-null metric cols) and `has_feeders`; **AI call #3** (`asset_resolve.py`, skipped when `PIPELINE_ASSET_ID`/picker pin) resolves by **verbatim name, ids hidden** → confident pin / ambiguous candidate list / empty / `no_data`. `basket/column_basket.py` reads real columns from `neuract` information_schema (`col_dict.py`) — with BFS to a representative feeder table for empty aggregate panels — and **AI call #4** picks `feasible`/`probable` columns (confidence, `substitute_for`), hard-filtered to real columns. `topology_siblings.py` attaches member tables + coverage for feeder panels.

### Stage 2 — Join, degrade gate, validation, asset gate
Back in `harness.py`: `run/degrade_gate.py::apply` fingerprints transport outages in 1a/1b exceptions → honest page-level `data_unavailable` with a `cmd_catalog.reason_template` sentence. Then `validate/build.py::run_validate` (non-AI pandas, 500-row probe of the basket's first table over :5433) grades every basket column pass/warn/fail plus per-card payload feasibility — **annotate-only**; the "chilled" gate blocks Layer 2 only when the basket had columns and **zero** passed. Asset gate: Layer 2 runs only when `how ∈ {AI, user-choice}` and an asset is pinned; `no_data` → notice; ambiguous/empty → FE AssetPicker popup (pick re-enters with `asset_id`).

### Stage 3 — Layer 2 shared-context pre-pass: **DESIGNED, NOT WIRED**
The Move-1 group pre-pass exists as prompt plumbing only (`layer2/card_input.py` accepts `shared_ctx_ref`; `emit/user_message.py` has the SHARED CONTEXT REF block) — but `workers/sharedctx/builder.py` is a TODO stub and **no production caller ever passes `shared_ctx_ref`**. Group cards get `is_group_card=True` ($ctx gate rules flip) but never see a shared buffer.

### Stage 4 — Layer 2 per-card emit
`run/layer2_all.py::run_2_all` fans out `layer2/build.py::run_card` per card in parallel (vLLM batches). Per card: `card_input.py` joins 1a story + 1b asset/basket + `catalog/catalog_row.py` (7 single-purpose readers incl. the harvested `card_payloads` default) + `swap/candidates.py` pool (±15% size, `card_feasibility='render_real'`, off-page). **AI call #5** (`emit/emit.py`, one call, system = `prompts/{swap,metadata,data_instructions}.md`) decides keep/swap, metadata morphs, and the data recipe (per-slot fields with kind raw/bucketed/derived/const/text/event + endpoint/window/metrics). A second identical call happens only on an accepted swap (re-author for the target's shape). `_finalize` then applies deterministic enforcement: `emit/metadata/producer.py` overlays only declared `_morphed` metadata leaves onto `strip_to_placeholders(default)`; `gates.py::gate/enforce_exact_metadata` reverts any undeclared byte drift; `resolve/column_override.py` unit-guard-snaps columns (hallucination → `source='frame'`, silently); `consumer_binding/builder.py` builds the fetch spec (AI endpoint as-is + the one non-AI key `mfm_id`); answerability + topology-infeasibility override. Post-pass: `grounding/swap_settle.py::settle` deterministically reverts duplicate swap targets (parallel emits ran with empty `already_chosen`). Payload = `exact_metadata`, `fill_source='live-frontend'` label (data comes later).

### Stage 5 — Reflect loop
Cards with `gap` (answerability='none') on attempt 1 → `run/reflect.py::build_feedback` (failed titles + what the asset actually measures) → **one** 1a re-route (attempt 2, new run_id salt `loop2`); persistent gaps → `notes.loop2` explanation; render best-effort regardless. `obs/notes.py` persists to `outputs/notes/<run_id>.json`.

### Stage 6 — Grounding / L3 verdict: **RETIRED**
The L3 AI verdict (and its `V48_L3_REWORK_SPEC.md` payload-cleaner rework) was built then deleted on 2026-07-02 → `archive/layer3_archive_20260702.tar.gz`; `run/harness.py` header: "LAYER 3 IS RETIRED". Of the 14 `grounding/` engines, only 3 are live: `meaningful.py` (+`schema_fingerprint`/`schema_route`/`energy_register` chain, via 1b `has_data`), `default_assemble.py` (strip-to-placeholders inside the L2 producer), `swap_settle.py`. The other 7 are orphaned code whose **policies live on** through cmd_catalog config tables read by ems_exec. The render verdict moved to Stage 8.

### Stage 7 — Data fill: **workers/ RETIRED → ems_exec**
The designed workers PARSE→FILL→STITCH WS path (against ems_backend :8890) is "RETIRED and DELETED" (`workers/__init__.py`; deletions staged-uncommitted; only the never-implemented `sharedctx/` stubs remain). Instead: `host/server.py::_run_cards` fans all cards out in parallel (≤8 threads, wall budget `cfg('ems_exec.card_budget_s', 45s)`):
- Normal cards → `ems_exec/serve/run.py::run_card(exact_metadata, data_instructions, asset_table, db_link, window, default_payload)` → `ems_exec/executor/fill.py::fill`: one batched `latest()` read + per-field kind dispatch — raw (latest-row column, denorm/sign `_verify`), bucketed (`data/neuract.py::bucketed` date_trunc-AVG series), derived (`cmd_catalog.derivation_binding` fn → `derivations/registry.py` pure-fn library, nameplate pseudo-cols from `cmd_catalog.asset_nameplate`), const/text (real nameplate value over baked literal), event (rising-edge count). `_graft_container` restores gate-elided containers from the harvested default; `_set_leaf_typed` writes real-or-None type-preservingly. Never raises; never fabricates.
- Special cards (`cmd_catalog.card_handling ∈ {asset_3d, topology_sld, narrative_ai}`) → `ems_exec/renderers/run_special` (GLB envelope / SLD fan-out via `registries/neuract/members.py` + `data/lt_panels/panel_members.py` / LLM-narrated `widgets.ai_summary`). **`panel_aggregate` is deliberately excluded** from `_SPECIAL_KINDS` — the finished renderer has zero serve-time callers; panel cards honest-blank.

### Stage 8 — Assemble + verdict (host)
`host/server.py::_enrich_card`: payload = completed CMD_V2 props, `render_card_id` follows swaps, and the **deterministic render verdict** comes from `_card_leaf_stats` (real vs blank at declared `data_instructions.fields[].slot` full leaf paths) → `render|partial|honest_blank` + reason + `watermark:'live'`. `frames:{}` is emitted empty purely for FE back-compat. Response also carries page layout/groups, asset resolution state, validation, notes, degrade flags.

### Stage 9 — FE render
`host/web` (Vite :5188, proxy `/api`→:8770): `CardGrid.tsx` lays out the real page template from 1a's `page_specs` grid (`pageGrid.ts`/`cellPos.ts`; RTM flex pages → `RtmComposite.tsx` two-Card merge). `CmdCard.tsx` → `cmd/registry.tsx::renderCmd` tier order: SPECIAL/envelope → **COMPONENTS** `<Comp {...unwrap(payload)}/>` (primary; ~46 real CMD_V2 components via the `@cmd-v2` alias to `/home/rohith/CMD_V2/src`, one deduped React) → COMPOSE(card 5) → FILL glob fallback (typed-empty) → HonestBlank, wrapped in three error boundaries. `AssetResolution.tsx` handles the picker/no-data/blocked popups. Per-card date nav posts `/api/frame` — **currently a silent no-op** (contract mismatch, see gotchas).

---

## 3. AI vs deterministic split

All pipeline LLM traffic goes through `llm/client.py::call_qwen` → `POST http://localhost:8200/v1/chat/completions`, Qwen/Qwen3.6-35B-A3B-FP8, temp 0, JSON mode, thinking off, **fail-open to `{}`**, logged by `obs/ai_log.py`.

| # | Call site | Decides |
|---|---|---|
| 1 | `layer1a/route.py` | The ONE page template (`page_key`), metric (8-word vocab), intent (5-word vocab) — story-based, asset-agnostic; reflect feedback appended on the single re-route |
| 2 | `layer1a/story_builder.py` | One `analytical_story` sentence per card |
| 3 | `layer1b/resolve/asset_resolve.py` | Confident asset pin vs ambiguous candidate set vs empty — by verbatim name (ids hidden); skipped on user pin |
| 4 | `layer1b/basket/column_basket.py` | Generous feasible column basket + ranked probable columns (confidence, substitute_for) — hard-filtered to real columns |
| 5 | `layer2/emit/emit.py` (×1 per card, ×2 on accepted swap) | keep/swap + confidence + criterion; metadata morphs (declared `_morphed` only); full data recipe (fields, kinds, columns/fns, endpoint, window); answerability + data_note |
| 6 | `ems_exec/renderers/_insight.py` (narrative_ai cards 8/19/25/28 only; temp 0.2) | **Nothing** — rephrases a Python-pre-computed story into one sentence; deterministic fallback on failure |
| — | copilot `generate.py`/`starters.py` (:8201 Qwen3-4B) | Typeahead suggestions + starter chips, pre-submission only, zero pipeline coupling |
| — | Retired/offline: L3 verdict+repair (archived); `payload_db/enrich/enrich_workflow.js` (one-off build-time story→card mapping + key_roles split) | — |

**Everything else is deterministic**: registry/catalog reads, partition union-find, validation pandas, byte-identity gates/enforce, column snapping, envelope backfill, swap settle, degrade gate, the entire ems_exec fill/derivations/renderers, the render verdict, and the whole FE. Deterministic code *executes* AI-authored specs (endpoints, derived fn names) but decides nothing semantic.

---

## 4. The DB story

**Three live databases, all wiring in `config/databases.py`; access via `data/db_client.py::q` (psql subprocess CSV) / `pg_connect`, plus two pooled psycopg2 doors (`ems_exec/data/neuract.py`, `registries/neuract/_db.py`).**

### cmd_catalog (local :5432) — the brain
- **Routing/catalog**: `page_specs`, `cards`, `page_layout_cards`, `card_grid_size`, `card_data_recipe`, `card_handling` (145), `card_feasibility` (145), `card_link`, `card_combo(_member)`, `page_control`, `routable_pages` (18), `card_contract_binding`/`contract_components`/`contract_capabilities`, `card_controls`.
- **Ground truth defaults**: `card_payloads` (155 rows: 59 EMS enriched+verified byte-faithful from Storybook :6008; 30 Assets rows loaded but `page_key=NULL` → **unreachable** by the card_id+page_key lookup; 44 3D-Mapper; 22 nav) — the byte-identity reference Layer 2 morphs against and ems_exec's default-graft source.
- **Config-as-data**: `app_config` (37 rows, read once per process via `config/app_config.py::cfg`), `data_quality_policy` (28), `asset_nameplate` (320: 103 real ratings, 217 honest-NULL, **0 fabricated class_default rows — MEMORY.md's "209 fabricated" note is stale**), `schema_slot_map` (108), `metric_class` (14), `derivation_binding` (14), `reason_template` (23), `endpoint_policy` (12), `render_guarantee_matrix` (15) + `render_guarantee_page_phrase` (7), `event_threshold`, `demand_policy`. `render_spec` (188 rows) is a **stale L3 cache with zero readers**.
- **Missing** (accessors run on code defaults): `asset_class_default`, `band_policy`, `viewer_policy`, `live_window_policy`, `limit_override`, `history_sampling`, `window_metrics_policy`, `mapper_frame_contract` — ~17 `db/seed_*.sql` files not yet applied.

### target_version1, schema neuract (:5433 SSH tunnel to 10.90.200.91) — the live data
361 tables. Per-meter `gic_*` time-series (shared 72-col schema; `timestamp_utc` is ISO-8601 **TEXT**, hence the `::timestamptz` cast everywhere); topology `lt_mfm` (320), `lt_mfm_outgoing` (93 edges — the dummy fallback actually in use), `lt_feeder` (**0 rows**, seeder never run), `lt_mfm_incoming` (inverted mirror — never read); `lt_asset_3d`/`asset_3d_model` **empty** (all 3D cards → `object=null`); `lt_config_field/value` for nameplate defaults. The `compat` schema is **superseded/gone** — V48 reads neuract directly (`CONSUMER_SCHEMA='neuract'`); `ems_compat/` survives as historical tooling + the COVERAGE.md truth-table.

### meta_data_version1 (:5433) — the device registry
`app_devices`/`app_device_tables`/`app_gateways` → layer1b's asset universe (320 devices; mfm_id contract = row_number in table order, `_sch` stubs dropped *after* id assignment).

---

## 5. Current runtime state + smoke result

**All services up (probe 2026-07-02):** host API :8770 (pid 233863), Vite :5188, copilot :8772 + Qwen3-4B :8201, pipeline vLLM :8200 (Qwen3.6-35B, 64K ctx — **user process, not systemd; vllm.service inactive; a reboot drops it**), cmd_catalog :5432, and the :5433 tunnel is **back up** (the Jul-1 outage is over; sample gic table writing live at 21:16 IST). ems_backend :8890 / backend2 :8889 / CMD_V2 :3107 / Storybook :6008 also listening. Caveat: the :8770 process started Jul 01, but `server.py` was rewritten Jul 02 20:36 — **the live HTTP process may serve stale code until restarted** (the smoke bypassed it via direct import).

**Smoke run (via `build_response` import, exactly as `/api/run` does):**
- *"show me energy consumption of transformer 1 today"* — exit 0 in **5.9s** as the **designed honest no-data terminal**: 1b pinned Transformer-01 (mfm_id 171) but its table `gic_15_n3_pcc_01_transformer_01_se` has 15,427 rows with **every metric column 100% NULL** (verified read-only); `how='no_data'`, Layer 2 skipped, 4 shells all `honest_blank`, `errors={}`. A real dead feed, not a pipeline bug.
- *"show me energy consumption of DG-1 today"* — full chain in **59.3s**: 1a energy-power page (4 cards) ∥ 1b DG-1 (how=AI) → validate pass → 4/4 L2 emits conform (2 full, 2 partial with honest substitution notes, 0 swaps, 0 gaps) → 4/4 ems_exec fills ok → verdicts render=1 / partial=3 / honest_blank=0. Zero errors either run.

**Test suite (run 2026-07-02, all services up):** main suite 54 passed / **1 failed** / 11 skipped; render-guarantee acceptance **38 passed, 3 skipped, "35/35 prompts clean, 0 violations"** (22.4 min). The one failure is `test_layer2_card.py::test_layer2_card5_keep_byteidentical_live` — the known split()-vs-strip_to_placeholders classifier disagreement, a stale assertion, not a fresh regression. (This *run evidence* supersedes the grounding reader's "no positive pass record found".)

---

## 6. Honest status board

### BUILT + verified
| Piece | Evidence |
|---|---|
| Orchestrator `run/harness.py` (1a∥1b, degrade gate, chilled validation, asset gate, L2 fan-out + swap settle, reflect loop) | Smoke run 2 full chain; `test_orchestrator.py` live join passes |
| Layer 1a routing + stories + partition groups | 10 tests pass; RTM group `{5,6,7,8,9,10,11,160}` verified live |
| Layer 1b pure-AI asset resolve + column basket + value-aware has_data | AHU-5→id 36 live test; smoke correctly flagged Transformer-01 dark; no-hallucination basket test |
| Validation layer (`validate/`) | Wired into every run; 5 unit tests pass; drove the smoke gates |
| Layer 2 per-card emit + byte-identity gates + swap settle (standalone path) | 9 tests pass; smoke 4/4 conform with honest partial notes |
| ems_exec per-card fill + data/neuract door + derivations | Smoke 4/4 exec ok; `verify_binding` slot fix 31/112 → 227/227 slot_ok |
| Host API + direct CMD_V2 FE render (`@cmd-v2` alias, registry tiers, error boundaries) | Both processes live; browser-verified per project memory; render-guarantee suite green through `build_response` |
| Render-guarantee acceptance | 38 passed, 35/35 prompts clean, invariants I1–I6 |
| payload_db EMS half (59 enriched byte-faithful defaults) + `registries/neuract` | Live DB counts; serve-time importers (ems_exec renderers, host) |
| obs/ (ai_log, stage, failures, notes) + copilot (:8772/:8201) | 723 log files; monkeypatch asserted in tests; copilot health ok, no-coupling test passes |

### PARTIAL
- **Panel aggregate**: renderer `ems_exec/renderers/panel_aggregate.py` + `_agg.py` + fill's `_agg_row` hook complete, but **host `_SPECIAL_KINDS` excludes it — zero callers**; 5 panel-overview pages rendered 0/24 in the last audit; `coverage_note=None` hardcoded.
- **Asset (deep-tab) cards**: 30 harvested payloads loaded with `page_key=NULL` → invisible to lookup → 32 asset cards still `card_feasibility='no_data'`; 6 cards off_route; asset fill mappers 'planned'.
- **Data-leaf coverage**: 82/206 (40%) leaves bound after the slot fix — most payload data leaves have no field → `partial` verdicts dominate.
- **Seed-leak**: `prove_ems_exec` (Jul 2) shows `seed_survived=[25,600,92.0]` on asset-dashboard cards 57/59.
- **Special-card input**: host passes run_special a minimal dict (no exact_metadata) — narrative_ai lands on an empty skeleton.
- **Group/interdependent cards**: shared-context prompt-ready but builder unimplemented; page-wise-shared detection off (`flags.PAGE_WISE_SHARED_DETECTION=False`).
- **Grounding kit**: 3/14 engines live; 7 orphaned (policies survive via config tables); `window_clamp` (DS-02 "data from <date>" reason) orphaned.
- **DB seeds**: ~17 `db/seed_*.sql` unapplied; `asset_class_default` table missing; `lt_feeder` empty (dummy `lt_mfm_outgoing` topology live); 3D model tables empty.
- **Scaffolding debt**: ~20 layer2 + 7 data/ + guardrail/ + contracts/ "TODO(v48)" skeletons; 11 placeholder test files.

### PENDING / BROKEN
- **Per-card date navigation is dead end-to-end**: `host/web/src/api.ts` posts `{consumer, date_window}` and reads `body.frame`; the rewritten `/api/frame` requires `exact_metadata + asset_table` and returns `payload`; CmdCard swallows the 400 — and even fixed, the FE stores a `frame` the primary render path never reads.
- **`run/layer_diag.py`**: ImportError (`host.server._card_frames` deleted); `card_diag.py` frame fields vacuous (frames always `{}`).
- **contracts/**: all 10 JSON schemas + validator + 7 invariants are empty stubs with zero importers (enforcement lives in hand-rolled per-layer `schema.py`).
- **`test_layer2_card5_keep_byteidentical_live`** failing (dual-classifier drift).
- **:8770 process staleness** (restart needed to serve Jul-2 code); **vllm :8200 not under systemd**.
- **Git**: one commit (8d905cc) + 466 uncommitted changes encode the entire ems_exec/L3-retirement rework — `git checkout .` would resurrect layer3/ + ems_backend/ and orphan ems_exec.
- **Unresolved minor contradiction**: docs say canon 145 cards / **135** live / 75 page_specs; `test_foundations.py` asserts **136** live cards / **68** live page_specs and passes today — likely 75 total vs 68 live page_specs, but the 135-vs-136 live-card count is unreconciled in the inputs.

---

## 7. Top gotchas

1. **`call_qwen` is fail-open (`{}`)**: with :8200 down, 1a silently routes to the first available page (metric='power', intent='trend') — the degrade gate only catches *exceptions*, so an LLM outage never triggers the honest terminal.
2. **Two data/metadata classifiers coexist and disagree** (`layer2/emit/metadata/split.py` name-rule vs `validate/leaf_classify` + `strip_to_placeholders` value-aware) — direct cause of the one failing test; touching CMD_V2 payload conventions breaks both seed-stripping and slot demand.
3. **Parallel L2 emits run with empty `already_chosen`** — duplicate swaps are only fixed by `grounding/swap_settle` in `run_2_all`; calling `run_card` directly (verify scripts) skips it; `trace.py` threads sequentially and can differ from production.
4. **`frames` is always `{}` now** — `verify_pages`/`coverage_sweep` "with_data" metrics, `card_diag` frame fields, and `types.ts` are stale against the ems_exec path; recorded Jul-1 panel numbers predate the swap.
5. **Topology truth**: never read `lt_mfm_incoming` (inverted dummy mirror); `lt_feeder` exists but is empty, so `lt_mfm_outgoing` (dummy seed) is the live topology; `panel_members` caches per process — reseeds need restarts.
6. **Config caching bites twice**: `cfg()` lru_caches the whole `app_config` table *and* many config modules bake cfg() into import-time constants — DB edits do nothing to running processes; some accessors (`l3_policy`, `rating_knobs`, `nameplate_slot_map`) are **not** fail-open despite claiming to be.
7. **Deterministic run_id** = same prompt appends into the same log files across sessions; `ai_log` run_id is a process global (concurrent prompts cross-tag; the loop-2 re-tag splits one request across two run ids).
8. **`column_override` launders hallucinated columns silently** (`source='frame'`, always-empty issues list) — the `conforms` term in `build.py` is a no-op.
9. **Zero-declared-slot cards get verdict='render' by design** (shell render) — a fully-failed emit is never flagged blank; verdict correctness depends on L2 emitting FULL leaf paths in `fields[].slot` (the old top-level-key bug made everything 'render').
10. **`has_data` fails open on probe errors** — an outage can make dark meters look green; conversely it is value-aware (rows-with-all-NULLs = no_data, as the smoke's Transformer-01 proved).
11. **Docs/memory staleness gradient**: "workers DATA-fill DONE", "compat schema", "209 fabricated nameplates", "systemd vllm.service", README's storybook-iframe story — all stale; the only written record of the Jul-2 ems_exec swap is code docstrings.
12. **SQL hygiene**: `data/db_client.q` interpolates SQL into psql strings (dollar-quoting, no bind params) — safe today, an injection surface if prompt-derived strings ever reach it.

---

## 8. Open items, ranked by render-guarantee blockage

1. **Wire panel_aggregate into host dispatch** (add to `_SPECIAL_KINDS` or fold `coverage_verdict` into the host verdict) — 5 panel-overview pages / 24 cards currently honest-blank; the single biggest coverage gap, and I5's N-of-M coverage_note is hardcoded None.
2. **Pass the full card context (exact_metadata/data_instructions/_default_payload) into `run_special`** — without it, even wired panel_aggregate would fall back and narrative_ai keeps emitting onto an empty skeleton.
3. **Backfill `page_key` + enrichment for the 30 Assets `card_payloads` rows, then re-run `feasibility_recompute`** — unlocks 32 asset cards stuck at `no_data` despite loaded defaults (plus the 6 off_route cards decision).
4. **Close the remaining seed-leak on asset cards** (seed_survived 25/600/92.0 in prove_ems_exec) — a direct I3 violation risk once asset cards become reachable.
5. **Raise data-leaf coverage past 82/206** (per-card field emission / mapper coverage) — the difference between `partial` and `render` on most cards.
6. **Restart :8770** (serve the Jul-2 server.py) and **commit the working tree** (466 changes; a stray checkout destroys the ems_exec swap) — cheap, but everything live rides on both.
7. **Fix the /api/frame FE contract** (send exact_metadata+asset_table, swap the *payload* on response) — date navigation is a contract feature currently dead end-to-end.
8. **Apply the pending db/ seeds** (`render_guarantee_schema.sql` re-apply for `asset_class_default`, round2 tables, band/history/topology policies; run `seed_feeder_edges` for `lt_feeder`) — accessors run on code defaults, so DB policy edits are currently no-ops.
9. **Resolve the dual-classifier drift** (split.py vs strip_to_placeholders) and un-fail `test_layer2_card5` — protects the byte-identity invariant itself.
10. **Shared-context builder + page-wise-shared detection** — interdependent/group cards ($ctx) are prompt-ready but non-operational; needed for the coupled-card half of the contract.
11. **Rework the verification harnesses** (verify_pages/coverage_sweep frame metrics, card_diag, delete-or-fix layer_diag) so coverage measurement matches the ems_exec path.
12. **Fill contracts/ + the 11 placeholder tests; docs supersede pass** (README, END_TO_END_STATUS, L3_REWORK_SPEC) — lowest render impact, highest drift-prevention value.

---

# Appendix A — Completeness-critic corrections (read before trusting §6–§8)

## (a) On disk but absent/mischaracterized in the synthesis

- `services/` (dict_merge.py) and `scripts/` (_probe_asset_wording.py) — never mentioned (both tiny; state who imports them or call them out as debt).
- `data/registry/` (capacity.py, lt_mfm.py, lt_mfm_type.py, lt_parameter.py) — the DB story covers `data/db_client`, `data/cmd_catalog`, `data/lt_panels` but not this registry-reader package.
- `config/defs/` (14 single-purpose config modules: flags, gates, swap, windows, payload_shapes, …) — only `flags.PAGE_WISE_SHARED_DETECTION` is referenced obliquely.
- `docs/` as a subsystem (23 spec/audit .md + `fe_contract/`, `findings/`, `open_items/`) — synthesis names a few docs but never inventories it; `docs/open_items/` holds 4 open-item files (column_row_dialect, composite_sld_payload_shape, ctx_source_form, data_fill_shape_source) that don't appear in the §8 ranking.
- `workers/sharedctx/` undersold: besides the TODO-stub `builder.py` (verified: `# TODO(v48): implement.`) there are 6 `gen_*` generalization modules plus `tests/test_sharedctx_generalizations.py` — "only never-implemented stubs remain" is only half right.
- `layer2/morph/` is an empty dir; `outputs/batch/` unmentioned (noise-level).

## (b) Claims contradicted by spot-checked code

1. **panel_aggregate exclusion is FALSE (stale).** `host/server.py:185`: `_SPECIAL_KINDS = ("asset_3d", "topology_sld", "narrative_ai", "panel_aggregate")`, and `ems_exec/renderers/__init__.py:47` dispatches it. Synthesis Stage-7 claim, the PARTIAL-board row ("zero callers"), and Open item #1 are wrong against current disk. server.py mtime 2026-07-02 21:26 (renderers 20:55–20:58) — likely edited after the readers ran; note the file's own `_run_cards` docstring still says "panel-aggregate leaves simply honest-blank (aggregation deferred)", i.e. internally inconsistent.
2. **"run_special gets a minimal dict (no exact_metadata)" is FALSE.** `_run_cards` builds `card = {card_id, card_handling, exact_metadata, data_instructions, _default_payload}` and passes it (server.py ~253). Open item #2 is already done.
3. **/api/frame contract detail is stale (conclusion still holds).** Handler now falls back to `req.consumer` for both consumer and asset_table, and accepts `payload` as exact_metadata — but FE `api.ts:20` still posts only `{consumer, date_window}` (no exact_metadata → 400) and reads `body.frame` while the server returns `payload`. Date-nav still dead; the mechanism description needs updating.
4. **"135-vs-136 unresolved" is actually resolved on disk.** `tests/test_foundations.py:25` asserts `cards == 136 and pages == 68` with the comment "+card 12 promoted scratch→live in the energy-distribution fix" — the reconciliation the synthesis says is missing.
5. Minor: "14 grounding engines" — grounding/ has 13 engine .py files (excl. `__init__`).

Verified-true spot checks: harness "LAYER 3 IS RETIRED" header (exact); workers `__init__` "RETIRED and DELETED" (exact); `call_qwen` fail-open `{}` (llm/client.py); `_card_leaf_stats` full-leaf-path verdict incl. zero-slot→'render' (gotcha #9 accurate); `run/layer_diag.py:15` imports `host.server._card_frames` which no longer exists (ImportError claim true); contracts/ files are ~260-byte stubs (claim true); `test_layer2_card5_keep_byteidentical_live` exists at test_layer2_card.py:79.

## (c) Questions a reader would still have

- Since panel_aggregate is now wired: do the 5 panel-overview pages actually fill (the "0/24" audit predates the 21:26 Jul-2 edit)? No rerun evidence cited.
- Did the smoke run predate or postdate the panel_aggregate wiring — i.e., which server.py did §5's evidence exercise?
- What consumes `services/dict_merge.py` and `data/registry/*` — live path or dead code?
- Status of `tests/test_workers_aggregate_*.py` and `test_sharedctx_generalizations.py` given workers' retirement — are they among the 11 skips, or stale-passing?
- Which of docs/open_items' 4 items are already covered by §8 vs genuinely missing?

---

# Appendix B — Smoke run (verbatim)

SMOKE RESULT — pipeline_v48 end-to-end (invoked exactly as the host `/api/run` handler does: direct import of `host.server.build_response(prompt, asset_id=None, date_window=None)` from `/home/rohith/desktop/BFI/backend/layer2/pipeline_v48`, under `timeout 240`). No code or DB rows modified; only the pipeline's own run logs were written.

RUN 1 (the requested prompt): "show me energy consumption of transformer 1 today"
- Completed: yes, exit 0, wall 5.9s (elapsed_ms=5948), run_id r_0963d3d3a0
- 1a route: page=individual-feeder-meter-shell/energy-power, primitive=grid, cards=4, metric=energy, intent=snapshot
- 1b assets: pinned "GIC-15-N3-PCC-01 (Transformer-01) [Secure Elite300]" mfm_id=171, candidates=0, basket_cols=2 — but how=no_data
- validate: verdict=fail; asset_gate: pinned=False, no_data=True, validation_blocked=True → decision "NO-DATA → notice (Layer 2 NOT run)"
- Layer 2 / worker fill: never ran (by design). Cards emitted: 4 shells, with_payload=0, all render.verdict=honest_blank. errors={} — an honest terminal, not a crash.
- Root cause verified read-only in neuract: table gic_15_n3_pcc_01_transformer_01_se has 15,427 rows, max(timestamp_utc)=2026-07-02T21:49 IST (writing live), but EVERY metric column sampled (active_energy_import_kwh, active_power_total_kw, voltage_avg, current_avg, frequency_hz, power_factor_total, voltage_ry, active_energy_export_kwh) is 100% NULL — rows carry timestamps only. 1b's VALUE-aware has_data gate (>=3 non-null metric cols) correctly flagged it dark. Registry-wide: 230/318 assets have_data=True; Transformer-01 is genuinely a dead feed, not a pipeline bug.

RUN 2 (supplementary, same single-prompt smoke against an asset with data, to actually exercise L2/worker/gates): "show me energy consumption of DG-1 today"
- Completed: yes, exit 0, wall 59.3s (elapsed_ms=59273), run_id r_bbba7b2846
- 1a: same page energy-power, 4 cards, metric=energy, intent=snapshot
- 1b: asset=DG-1 MFM mfm_id=2, how=AI, candidates=0, basket_cols=1
- validate: pass; asset_gate: pinned=True → Layer 2
- Layer 2 emissions: 4/4 cards emitted, conform=4, gaps=0, swaps=0 (all swap=keep). Answerability: full=2 (card 39 "Today's Energy" endpoint=energy-power; card 42 "Load Anomalies" endpoint=load-anomalies), partial=2 with honest substitution notes (card 40: "Showing active energy import as a proxy for consumption; per-phase energy and reactive energy are not measured for this asset."; card 41: "Showing total active energy import as a proxy for input/output energy delta; per-phase or separate input/output energy meters are not available for this asset."). No reflect loop needed (gaps=0, loop2=None).
- Worker fill (ems_exec.run_card): exec ok=True for all 4 cards (39, 40, 41, 42); with_payload=4/4
- Degrade/render gate verdicts: render=1 (card 42), partial=3 (cards 39/40/41 — some data leaves honest-blank), honest_blank=0, data_unavailable=False, validation_blocked=False, asset_pending=False
- Errors: none. Only warning (both runs): pandas UserWarning in validate/data_load.py:24 "pandas only supports SQLAlchemy connectable... Other DBAPI2 objects are not tested" (cosmetic).

Verbatim errors: none in either run (out["errors"] == {} both times).

Artifacts: run logs /home/rohith/desktop/BFI/backend/layer2/pipeline_v48/outputs/logs/pipeline_r_0963d3d3a0.jsonl and pipeline_r_bbba7b2846.jsonl; driver + captures /tmp/v48_smoke.py, /tmp/v48_smoke2.py, /tmp/v48_smoke{,2}_{stdout,stderr}.log.

Verdict: pipeline is healthy end-to-end. The literal requested prompt hits a real data gap (Transformer-01 feed writes timestamps with all-NULL metrics) and the pipeline handles it with the designed honest NO-DATA terminal in ~6s; with a data-bearing asset the full chain (1a ∥ 1b → validate → asset gate → Layer 2 x4 → ems_exec fill x4 → render verdicts) completes in ~59s with 4/4 cards filled.

---

# Appendix C — Runtime probe (2026-07-02 ~21:20 IST)

```json
{
  "services": [
    {
      "name": "host API (pipeline_v48/host/server.py)",
      "port": 8770,
      "status": "up",
      "detail": "GET /api/health -> {\"ok\": true, \"sb_base\": \"http://100.90.185.31:6008\"}; python3.12 pid 233863, cwd /home/rohith/desktop/BFI/backend/layer2/pipeline_v48; routes /api/health,/api/assets,/api/site,/api/frame,/api/run"
    },
    {
      "name": "host web (Vite)",
      "port": 5188,
      "status": "up",
      "detail": "HTTP 200; node pid 1159185, cwd /home/rohith/desktop/BFI/backend/layer2/pipeline_v48/host/web"
    },
    {
      "name": "ems_exec serve",
      "port": 0,
      "status": "n/a (in-process, no port)",
      "detail": "/home/rohith/desktop/BFI/backend/layer2/pipeline_v48/ems_exec/serve/run.py is a plain function run_card() called by the host API \u2014 explicitly 'NO WebSocket, NO daphne'; it is effectively live iff :8770 is up (it is)"
    },
    {
      "name": "copilot API",
      "port": 8772,
      "status": "up",
      "detail": "HTTP 200 on /; python3 pid 2612167 server.py, cwd /home/rohith/desktop/BFI/backend/layer2/pipeline_v48/copilot (/health returns not-found \u2014 different health path, service itself responsive)"
    },
    {
      "name": "copilot model vLLM",
      "port": 8201,
      "status": "up",
      "detail": "GET /v1/models -> Qwen/Qwen3-4B-Instruct-2507-FP8, max_model_len 32768"
    },
    {
      "name": "pipeline LLM vLLM",
      "port": 8200,
      "status": "up",
      "detail": "GET /v1/models -> Qwen/Qwen3.6-35B-A3B-FP8, max_model_len 65536; running as user process pid 1579 (gpu-util 0.60), NOT via systemd (vllm.service inactive/disabled)"
    },
    {
      "name": "Postgres cmd_catalog (local)",
      "port": 5432,
      "status": "up",
      "detail": "psql -h 127.0.0.1 -p 5432 -U postgres -d cmd_catalog: SELECT 1 ok; counts card_payloads=155, card_handling=145, app_config=37"
    },
    {
      "name": "ssh tunnel -> target_version1/neuract",
      "port": 5433,
      "status": "up",
      "detail": "ssh pid 2035851 (-L 127.0.0.1:5433 -> rohithdev@10.90.200.91); psql to target_version1 search_path=neuract works; 361 tables in schema neuract; sample gic table max(timestamp_utc)=2026-07-02T21:16 IST (writing live today)"
    },
    {
      "name": "ems_backend (v48 data)",
      "port": 8890,
      "status": "up (listening)",
      "detail": "bonus check: port listening (process not attributable without root); backend2 :8889, CMD_V2 prod :3107 and Storybook :6008 also listening"
    }
  ],
  "cmd_catalog_db": "Reachable at 127.0.0.1:5432 user postgres db cmd_catalog (params from /home/rohith/desktop/BFI/backend/layer2/pipeline_v48/config/databases.py: CATALOG_HOST=127.0.0.1, CATALOG_PORT=5432, user postgres, empty password). SELECT 1 ok. Row counts: card_payloads=155, card_handling=145, app_config=37.",
  "neuract_db": "UP \u2014 the 2026-07-01 outage is over. ssh tunnel (pid 2035851, -L 127.0.0.1:5433 -> 10.90.200.91:5432) is established and passing queries: psql postgresql://postgres@127.0.0.1:5433/target_version1?options=-csearch_path=neuract returns current_database=target_version1 / search_path=neuract; 361 tables in schema neuract; gic_01_n10_hhf_01_type_01_300a_600kvar_p1 max(timestamp_utc)=2026-07-02T21:16:58+05:30 \u2014 data is fresh and actively writing.",
  "llm": "Both reachable. :8200 = Qwen/Qwen3.6-35B-A3B-FP8 (max_model_len 65536); :8201 = Qwen/Qwen3-4B-Instruct-2507-FP8 (max_model_len 32768). Note :8200 is a user process (vllm serve, gpu-util 0.60), not the systemd vllm.service (that unit is inactive/disabled).",
  "smoke_feasible": true,
  "notes": [
    "smoke_feasible=true because every dependency of a one-prompt run is live right now: host API :8770 healthy, pipeline LLM :8200 serving the expected Qwen3.6-35B model, cmd_catalog (:5432) answering with populated catalog tables, and the :5433 tunnel to target_version1/neuract passing queries with data fresh to today 21:16 IST.",
    "Remote 10.90.200.91 is back up (memory flagged it down 2026-07-01) \u2014 the pending work blocked on it (re-seed the FIXED nameplate seeder, run the REAL 50-prompt render-guarantee test) is now unblocked.",
    "vllm.service systemd unit is inactive/disabled; the :8200 vLLM survives only as a user-session process (pid 1579) \u2014 a reboot/logout would drop it. Memory entry 'systemd vllm.service' is stale on this point.",
    "ems_exec 'serve' is not a server: /home/rohith/desktop/BFI/backend/layer2/pipeline_v48/ems_exec/serve/run.py exposes run_card() as a plain in-process function consumed by host/server.py (:8770). No dedicated port exists (port reported as 0).",
    "Copilot :8772 answers 200 on / but 404 on /health \u2014 its health route (if any) is elsewhere; the process is the copilot server.py per /proc cwd.",
    "neuract DSN ground truth confirmed in /home/rohith/desktop/BFI/backend/layer2/pipeline_v48/config/neuract_dsn.py + config/databases.py: postgresql://postgres@127.0.0.1:5433/target_version1?options=-csearch_path=neuract (ts col timestamp_utc, ::timestamptz cast).",
    "Also listening (context): ems_backend :8890, backend2 :8889, CMD_V2 prod :3107, Storybook :6008 (host API sb_base points at :6008), local Postgres :5432. All checks were read-only; nothing was started, stopped, or restarted."
  ]
}
```
