# V48 — Implementation Progress

> Running build log. Started 2026-06-29. Build order: foundations → 1a → 1b → orchestrator → Layer 2 (RTM slice) → expand.
> Verification rule: each piece is **built + live-tested** before moving on (Qwen + the live `cmd_catalog`).

## Status legend
✅ done & tested · 🟡 partial · ⬜ not started · ⏸ deferred (open item)

---

## ★ Session 2026-06-30 — live render + frontend (summary; details in sections below)
1. **Data DB = neuract** (`target_version1`): `config/databases.py` (`DATA_DB`, `CONSUMER_SCHEMA="compat"`); `lt_panels` DEPRECATED. 1b `col_dict` + `validate/data_load.py` migrated to the `compat.cmp_mfm_*` views (fixed the "relation cmp_mfm_165 does not exist" errors).
2. **ems_backend live** (`ems_backend/`, V48 copy, daphne :8890): `_now()` + `EMS_REFERENCE_NOW="2026-03-26T05:55:09+05:30"` anchor (neuract data ends 2026-03-26) → WS frames carry the live history time-series.
3. **Layer 2 AI drives ems_backend**: `data_instructions` prompt+output emit `ems_backend={endpoint,window_seconds,interval_seconds,sample_count,metrics,selection}`; carried via `consumer_binding(ai_spec=…)`.
4. **Frontend renders REAL CMD_V2 components from the payload** (NO Storybook, NO adapters — the morph payload IS the props): `host/web` `@cmd-v2` alias + Tailwind plugin + React dedupe + `src/cmd/registry.tsx` (payload-shape → component). **LIVE heatmap** via CMD_V2's own `mapFrame(live_frame)` (host emits `live_frame`). Verified I1=1375kW.
5. **Swap pool restricted to the 9 available pages** (`layer2/swap/candidates.py` ⋈ `available_page_keys`; universe 31 cards).
6. **Card→component recipes discovered** for all 59 cards/subcards (workflow): 36 prop / 8 spread / 15 compose → `/tmp/wire_recipes.json` (registry build IN PROGRESS).
7. **Placement ported from V47** (atomic `host/web/src/layout/`): real page grid (`page_specs.grid_template`) + region/cell/`slot_order` + **card_grid_size** sizing, edge-to-edge (no debug frames). The **±15% swap rule** (`config/swap.SIZE_TOLERANCE`) preserves a card's `card_grid_size` footprint so a swap fits the same slot — placement = page_specs ⊕ page_layout_cards ⊕ card_grid_size, all carried by 1a.

**OPEN:** full 59-card frontend registry (only RTM wired); live rail/supply/trend/stats via `buildRailViewModel`; placement visual-verify vs EMS; the 3 validation live tests (env).

---

## ✅ Foundations
| module | what | tested |
|---|---|---|
| `llm/client.py` + `config.py` | the one Qwen 3.6 call (sync urllib, json_object, thinking off, strip `<think>`, FAIL-OPEN) | ✅ live returns dict; fail-open on bad endpoint |
| `data/db_client.py` | `q(db, sql)` via psql; raises on non-zero (no silent empty); psql user from `config/databases.py` | ✅ basic + raises + live counts match canon (135/68) |
| `obs/ai_log.py` | monkeypatch urllib → logs every :8200 call to `outputs/logs/ai_<run_id>.jsonl` | ✅ logger active + request+response captured |
| `obs/failures.py` | append-only failure recorder (no reloop) | ✅ |

## ✅ config/ provisions (Rule #1b — add/remove without touching code)
`available_pages` (9 routable pages) · `databases` · `metrics`/`intents` (vocab) · `payload_shapes` · `dialects` · `windows` · `swap` · `flags` (open-decision toggles). Wired now: `db_client`←user; 1a clamp←vocab; 1a route←available_pages.

## ✅ Layer 1a — storytelling router (CONTRACT 2 COMPLETE)
| piece | file(s) | tested |
|---|---|---|
| route (LLM) | `layer1a/route.py` + `prompts/system.md` | ✅ routes by story, asset-agnostic, scoped to 9 pages |
| per-card stories (LLM) | `layer1a/story_builder.py` + `prompts/story_instruction.md` | ✅ 100% card coverage, coherent + adaptive |
| db reads | `layer1a/db_reads/{page_specs,card_titles,cards_intent,page_layout}.py` | ✅ status=live; slot+size from page_layout_cards/card_grid_size |
| parse | `layer1a/parse/{think_strip,page_key_fallback,metric_intent_defaults}.py` | ✅ verbatim/near-miss/fallback; vocab clamp |
| schema | `layer1a/schema.py` (`build_` + `validate_layer1a_output`) | ✅ full contract-2 validation PASS |
| compose | `layer1a/build.py` (`run_1a`) | ✅ route→stories→layout→partition→Layer1aOutput |

**Live manual check (14 varied prompts):** 14/14 correct routing + in-scope, correct intent (trend/distribution/snapshot), coherent stories, 0.6–2.3s. Qwen working as intended.

## ✅ Partition (Step-0 group detection)
| piece | file(s) | tested |
|---|---|---|
| coupling inputs | `layer1a/partition_inputs/{card_link,card_combo,page_control,interdependency_prose}.py` | ✅ |
| group detect (union-find) | `partition/group_detect.py` + `coupling_lookup.py` | ✅ RTM = {5,6,7,8,9,10,11,160} |
| orphan fallback (region+tab) | `partition/fallback_edges.py` | ✅ orphan card 160 grouped |
| 🟡 page-wise-shared detection | — | ⏸ deferred (`open_items/partition_page_wise_shared.md`; `flags.PAGE_WISE_SHARED_DETECTION=False`) |

## ✅ Layer 1b — asset resolve + card-agnostic column basket (CONTRACT 3 COMPLETE)
| piece | file(s) | tested |
|---|---|---|
| asset candidates | `layer1b/resolve/asset_candidates.py` | ✅ live `lt_mfm`⋈`lt_mfm_type`; AHU-5=id37/mfm_lt_022 |
| asset resolve (LLM, pure-AI) | `layer1b/resolve/asset_resolve.py` + `prompts/asset_system.md` | ✅ confident-pin / ambiguous-list / empty / `PIPELINE_ASSET_ID` round-trip |
| candidate list (picker) | `layer1b/resolve/candidate_list.py` | ✅ ambiguous → FE AssetPicker shape |
| column basket (LLM, card-agnostic) | `layer1b/basket/column_basket.py` + `col_dict.py` + `prompts/column_system.md` | ✅ generous basket, **only REAL `lt_panels` columns** (no hallucination), has_data flagged |
| parse / schema / compose | `layer1b/parse/loads_lenient.py`, `schema.py`, `build.py` (`run_1b`) | ✅ `build_`+`validate_layer1b_output`; `run_1b(prompt, asset_id=None)` |

**Live manual check:** (1) "voltage/current for AHU-5" → pin id37 LT-Panel `mfm_lt_022` + 48-col basket [7.1s]; (2) "battery autonomy" (bare UPS class) → 46 UPS candidates, no guess [2.2s]; (3) `PIPELINE_ASSET_ID=37` → `user-choice` pin + 49-col basket [6.1s]. All validate OK.

## ✅ Orchestrator (1a ∥ 1b join)
| piece | file(s) | tested |
|---|---|---|
| concurrency primitive | `run/parallel.py` (threads, fail-isolated) | ✅ isolates one layer's exception; proven concurrent (~max, not sum) |
| run id | `run/run_id.py` (sha1 of prompt — no `Date`/`random` in env) | ✅ stable |
| entrypoint | `run/harness.py` (`run_pipeline(prompt, asset_id=None)`) | ✅ live: fires 1a∥1b, sets ai_log run_id, joins, records layer exceptions |

**Live:** "voltage/current for AHU-5" → 1a `…/voltage-current` (voltage/snapshot, 3 cards, 1 group) ∥ 1b AHU-5 pinned + 38-col basket; **5.7s wall = max(1a,1b)** (parallel, not summed). "battery autonomy" → 1a nearest feeder ∥ 1b ambiguous 46 UPS candidates. `errors={}` both.

## Tests
**38 passing, 15 skipped** (Layer-2 stubs) — `test_foundations`, `test_layer1a_routing`, `test_partition_groups`, `test_available_pages`, `test_layer1b_asset_resolve`, `test_layer1b_column_basket`, `test_orchestrator`. Unit + live integration + contract-2/3 conformance + asset-agnostic + available-scope + no-hallucinated-columns guardrail + parallelism/isolation. Run: `python3 -m pytest tests/ -q`.

---

## ✅ Payload DB — ground-truth card/subcard payloads (`cmd_catalog.card_payloads`)
> User directive (2026-06-29): *"first make a proper db with the payload for all the cards and subcards. the payloads you can find in http://100.90.185.31:6008/."* That URL = the running **CMD_V2 Storybook**; each story's resolved **args = the card/subcard payload** Layer 2 morphs + byte-matches against.

| piece | file(s) | tested |
|---|---|---|
| harvest | `payload_db/harvest_payloads.mjs` (Playwright; reads `__STORYBOOK_PREVIEW__.storyStoreValue.args.initialArgsByStoryId`) | ✅ **59/59 EMS** resolved (125/129 all groups; 4 non-EMS nav/3D failed a nav race) |
| page map | `payload_db/page_map.py` (Storybook shell+page → cmd_catalog `page_key`, single source) | ✅ all 9 pages map, 0 unmapped |
| schema | `payload_db/schema.sql` (`card_payloads`: jsonb payload + shell/page/card_group/is_subcard/variant/page_key + nullable `card_id`) | ✅ table + 4 indexes (gin on payload) |
| load | `payload_db/load_payloads.py` (psycopg2 upsert on story_id, idempotent) | ✅ 125 rows |
| verify | `payload_db/verify.py` (counts + **jsonb round-trips byte-equal to harvest**) | ✅ **PASS** 125/125 faithful |

**Coverage:** 59 EMS = **36 cards + 23 subcards** across all 9 pages (panel-overview 3/4/5/5/5, equipment-detail 7/9/9/12). Each payload carries a `variant` discriminator + content keys — the real per-card shape (not an assumed `{data,metadata}`). NOTE: page→card linkage in cmd_catalog is **fragmented** (`page_layout_cards` card_ids are sparse for Equipment Detail; `page_spec_cards` has names; `cards.page` is a human label) — so `card_id` is resolved by an AI map+verify pass, not a rigid join.

✅ **Enriched** (`enrich-payload-db` workflow, 9 pages × 18 agents, adversarially verified → `enrich/write_enrichment.py`):
- **59/59 mapped to `card_id`**, 0 unmapped, **0 dangling**, all `match_verified`. Confidence: 45 high / 11 medium / 3 low (honest downgrades where layout anchors absent). Subcards inherit parent card_id (23/23). Spot-checks exact ("Today's Energy"→#39, "Main Heatmap"→#5 Feeder Heatmap).
- **Per-key morph roles** (`key_roles` jsonb): 70 metadata / 60 **mixed** / 1 data → most content objects hold BOTH morph-metadata + worker-data at the **leaf** level; per-leaf split recorded in `match_notes`. **The morph is per-leaf, not per-top-level-key** — key Layer-2 input.
- New columns: `card_id`, `card_match_confidence/reason`, `parent_story_id`, `key_roles`, `match_verified`, `match_notes`. Doc: `payload_db/PAYLOAD_DB_NOTES.md`.

---

## ✅ EMS backend — V48-local copy (`ems_backend/`)
> User (2026-06-29): *"for now copy the backend to v48 and rename it appropriately."* Done — verbatim fork of `/home/rohith/CMD/backend` → `pipeline_v48/ems_backend/`.

| piece | what | verified |
|---|---|---|
| copy | `cp` of CMD/backend (Django+Channels EMS) → `ems_backend/`; only `__pycache__`/`*.pyc` excluded; folder renamed `backend`→`ems_backend` | ✅ **148/148 `.py`** match, 0 cruft, all key files present (6.3M) |
| integrity | `py_compile` of `services.py` + `_base.py` + RTM `pcc_panel.py` + assets `services.py` | ✅ compiles clean (not copy-corrupted) |
| config | inner Django pkg kept `backend` (`manage.py`→`backend.settings`, `ASGI=backend.asgi.application`); binds `lt_panels_db`@localhost:5432; `ALLOWED_HOSTS=['*']` | ✅ |
| provenance + boundary | `ems_backend/V48_PROVENANCE.md` — why a copy, run config, **all EMS edits land here, never in live CMD** | ✅ |
| **stood up + RTM frame verified** | pyenv **3.11.9** has all deps (django 5.2.11/channels 4.3.2/psycopg 3.3.3/daphne 4.2.1); `manage.py check` = 0 issues; in-process `WebsocketCommunicator` on `ws/mfm/174/real-time-monitoring/` (PCC Panel 1 A) | ✅ `snapshot` frame, `widgets={config, feeders, selected_feeder}`, **topology fan-out found 6 feeders**, `config.columns=[kw,kvar,pf,volt,amp,i_unbal]` — envelope shape correct |

**Run recipe:** interpreter = `/home/rohith/.pyenv/versions/3.11.9/bin/python` (the live CMD's pyenv, deps already there — the default `python3`=3.12 lacks Django). In-process drive via `channels.testing.WebsocketCommunicator(backend.asgi.application, "/ws/mfm/<id>/<endpoint>/")` from inside `ems_backend/`. (Live CMD copy already runs on :8888; run V48's on a fresh port if booting daphne.)

⚠ **DATA-freshness caveat:** the `lt_panels` time-series is **~13 days stale** (latest `mfm_lt_115` ts = 2026-06-16; 1.1M rows exist) even though `live_simulator_v2.py` is running — so the RTM **trailing-30s window is empty** (feeder `queue=[]`). This does **NOT** block the morph/byte-match (which targets METADATA leaves + structure per `key_roles`; DATA leaves are live-filled and excluded from value-match), but live DATA *values* can't be validated until fresh data flows. Open: revive/redirect the simulator if live-value validation is wanted.

**Why (reverses earlier "no copy"):** V48 owns + adapts its EMS backend — chiefly to wire `mfm_type_id → lt_parameter` column-sourcing (per `findings/ems_backend_hardcoding.md`) — without touching live CMD. Hardcoding audit settled the call surface: **drive the WS dispatcher by `(resolved mfm_id, page-endpoint)`** → it picks the class-correct strategy + `?columns=` + interactivity for free.

---

## 🟡 Data source = neuract via compat views (user 2026-06-29, replaces lt_panels)
> User: *"instead use this db: target_version1 — logged meter data lives in schema neuract"* + *"this is fine via compat views + a registry repoint (zero consumer forking)."* `lt_panels` (stale + messy 191-col schema) is OUT; the **clean** source is `target_version1.neuract` (`mfm_001…245`, uniform **40-col** proper schema). Full: `findings/neuract_compat_integration.md`.

| piece | status |
|---|---|
| neuract explored — clean 40-col uniform meter schema, `device_mappings` registry, 2yr @1Hz | ✅ |
| 3 breaking mismatches identified (no `panel_id`, varchar mixed-offset `timestamp_utc`, no topology/type) | ✅ |
| **compat-view path PROVEN** — `public.cmp_mfm_001` (ts cast + panel_id inject + alias/derive) | ✅ real `services.py` `fetch_live` + `fetch_bucketed` (the only DB path consumers use) return proper rows/buckets — **zero consumer fork** |
| full column contract → neuract coverage + one compat-view template | ✅ `ems_compat/COVERAGE.md` + `compat_view_template.sql` (46 cols covered: 20 direct/4 alias/22 derive; 33 families absent) |
| **WIRED — neuract is Layer 2's DB** (user: *"wire that db ... i told neuract db"*) | ✅ see below |
| time anchor (neuract latest = 2026-03-26 → live trailing-30s empty; pin ref-now or shift ts in view) | ⬜ remaining (data flows; live windows need a now-anchor) |

**Wiring (zero consumer fork, reversible):**
- `ems_compat/build_compat_views.py` → **245 compat views** `compat.cmp_mfm_NNN` in `target_version1` (ts-cast + panel_id inject + alias/derive, from the template).
- `ems_compat/repoint_registry.py` → **215 `lt_mfm` assets repointed**: `db_link`→`target_version1` (search_path=compat), `table_name`→`cmp_mfm_NNN`, `panel_id`→`mfm_NNN`. **`mfm_type` + topology untouched.** Originals backed up in `lt_mfm_repoint_backup` (`--restore` reverts). Deterministic id-order asset→meter assignment (refine later).
- **Proven:** ORM `MFM.objects.get(174)` → repointed `cmp_mfm_165` → `fetch_live` returns real neuract row (kw=369.2, pf=0.903, unbalance=2.43%); topology fan-out children read their own neuract meters. Consumers unchanged.
- ⚠ Shared `lt_mfm` (live CMD reads it too) → live CMD now also sees neuract; intentional + reversible.

---

## ✅ Validation layer — NON-AI data+payload gate (`validate/`, runs after 1a∥1b, before Layer 2)
> User directive (2026-06-30): *"i want a data validation layer before layer 2. 1b already resolves columns, 1a already selects the cards. so i want a non ai layer using pandas to validate data and payload."* Decisions: validate **both** data + payload-fillability; **on-failure policy DEFERRED** ("decide later") → default **annotate-only** (never drops/blocks), flip via `config/validation.FAILURE_POLICY`.

Pure pandas/deterministic. Cross-checks: *can THIS asset's real data fill THESE selected cards' payloads?* — before the expensive Layer 2.

| piece | file | does |
|---|---|---|
| config | `config/validation.py` | thresholds (null-rate, recency, min-series-rows, phase suffixes) + deferred `FAILURE_POLICY` (Rule #1b) |
| data load | `validate/data_load.py` | asset's recent `lt_panels` rows → pandas (newest-first, real cols only) |
| data quality | `validate/data_validate.py` | per basket-column: present / null_rate / latest_ok / dtype / series_capable → pass·warn·fail |
| leaf split | `validate/leaf_classify.py` | payload leaves DATA vs METADATA **by TYPE** (num/array/series = data; str/bool/color = metadata) — the per-leaf morph split, no AI |
| payload feasibility | `validate/payload_validate.py` | demand (payload data leaves) vs supply (validated numeric/phase/series cols) → pass·warn·fail |
| lookup / report / schema / compose | `validate/{payload_lookup,report,schema,build}.py` | default payloads from `card_payloads`; roll-up overall verdict; `run_validate(1a,1b)` |

**Wired:** `run/harness.py` calls `run_validate` after the join → `out["validation"]` (annotate-only, try/wrapped, never sinks the run).
**Live (AHU-5 voltage-current):** **0.12s**, overall **pass** — 45/45 columns real non-null series; 3 cards (44/45/46) payload-fillable (e.g. Voltage History demand scalars/arrays/series all met). **Discrimination proven:** ambiguous asset→`asset_pending`; series-demand+empty/thin supply→`fail` (precise reasons); pure-metadata→`warn`.
**Tests:** +7 (`tests/test_validate.py`) — leaf-by-type, data verdicts, feasibility discrimination, supply counting, live. Suite **45 passed, 16 skipped**.

---

## 🟡 Layer 2 — payload-morph layer (AI EMIT DONE; data-fill helper next)
Built EXACTLY to `V48_BUILD_SPEC_{CONTRACTS,SIGNATURES,PROMPTS,FOLDER_SKELETON}.md`. Per-card output = **`{swap_decision, exact_metadata, data_instructions}`** (contract 5). ONE Qwen call per card; AI DECIDES (swap + morphs + recipe resolution), deterministic code SUPPORTS (copy byte-identical defaults, gate, assemble).

| piece | file(s) | does |
|---|---|---|
| 3 prompts | `layer2/prompts/{swap,metadata,data_instructions}.md` | the spec's L2 SYSTEM prompt, atomic; composed at call time |
| catalog reads | `layer2/catalog/{card_handling,card_data_recipe,contract,card_controls,card_grid_size,feasibility,card_payload}.py` + `catalog_row.py` | full per-card cmd_catalog detail; **metadata defaults sourced from harvested `card_payloads`** (the ground truth) not the stale `payload_schema_json` |
| metadata/data split | `layer2/emit/metadata/split.py` | §5a name-rule: roster/series arrays + interaction seeds = DATA; rest = METADATA (correct for numeric thresholds, unlike a type-classifier) |
| card_input + user msg | `layer2/card_input.py`, `layer2/emit/user_message.py` | Layer2CardInput (§4) + the prompt user message (shows byte-identical defaults, DATA elided) |
| **AI emit** | `layer2/emit/emit.py` | composes 3 prompts → ONE `call_qwen` → raw Layer2CardOutput |
| **metadata producer** | `layer2/emit/metadata/producer.py` | copies byte-identical defaults + overlays ONLY the AI's declared `_morphed` → byte-identical-by-construction (resolves the PROMPTS-vs-SIGNATURES tension toward "AI decides morphs, code copies defaults") |
| swap gate chain | `layer2/swap/{candidates,gate_confidence,gate_vague_reject,gate_pool_valid,gate_no_dup,gate_template_dedup,combo_cascade,decide}.py` | conf≥0.9 + non-vague + in-pool + no-dup + cascade → origin kept/swapped |
| emit gates | `layer2/gates.py` | exact_metadata byte-identity + no-chrome; data_instructions real-column/const/$ctx |
| column override | `layer2/resolve/column_override.py` | SAFE snap to the basket column for a unique metric (anti "every tile = active_power") |
| **consumer binding** | `layer2/emit/data/consumer_binding.py` | ★ `data_instructions.consumer` = the params to drive V48's **`ems_backend/` WS dispatcher** (`ws/mfm/<mfm_id>/<endpoint>/`): mfm_id (1b), endpoint (page), backend_strategy, range/sampling — NOT a column list |
| compose | `layer2/build.py` (`run_card`) | emit → swap gate → producer → override → gates → Layer2CardOutput; `config/swap.py` knobs |

**Proven LIVE (2 paths):** (1) RTM heatmap **#5** (group/panel_aggregate) → swap **KEEP** (conf 1.0, concrete criterion), **exact_metadata BYTE-IDENTICAL to the harvested default** (0 morphs), data_instructions = group atom (`source=$ctx`, 9 fields, `selection_role=produces`), `consumer={ems_backend, mfm_id 174, endpoint real-time-monitoring, pcc_panel.py}`, **conforms**. (2) standalone single_asset **#45** (TilePayload) → `$ctx=null`, `source=live` with **real basket columns** (`voltage_unbalance_pct`/`voltage_ll_avg`, SAFE-snapped), const label fields, binding AHU-5/`mfm_lt_022`, **conforms**. **+8 tests** (`tests/test_layer2_card.py`): producer byte-identity/morph/chrome-reject, both gates, swap chain, consumer-binding, live #5. (conftest re-pins `layer2`→pipeline_v48.)

### ✅ Data-fill helper — `workers/` driving `ems_backend/` (user 2026-06-30: *"use …/ems_backend to render the cards"* + *"atomic, separate files, minimal changes to existing files"*)
Built into the existing `workers/` skeleton; **ZERO changes to `layer2/`** — it consumes a `Layer2CardOutput`. PARSES `data_instructions` → FILLS the DATA tier → STITCHES `{...exact_metadata, ...filled_data}` → one payload.

| piece | file(s) | does |
|---|---|---|
| ems_backend config | `config/ems_backend.py` | atomic knobs: scheme/host/port/timeouts + `ws_url(mfm_id, endpoint)` (`ws/mfm/<id>/<endpoint>/`); V48 daphne :8890 |
| **live source** | `workers/fill/sources/ems_backend_source.py` | drives the WS dispatcher (websocket-client), reads the snapshot frame, **honest-degrade** (no fabrication) if unreachable |
| offline source | `workers/fill/sources/default_replay.py` | DATA leaves from the harvested default (`card_payloads`) — the byte-match proof + offline |
| frame map | `workers/fill/frame_map.py` | ems_backend frame → DATA leaves (per `payload_shape`; tolerant, extend one shape at a time) |
| data fill | `workers/fill/data_fill.py` | source select (live ems_backend ∥ replay/test) → DATA leaves; honest-degrade to replay |
| stitch | `workers/stitch/{flatten,assert_no_root,stitcher}.py` | §B4 merge into ONE flat payload, no second `root` |
| entry | `workers/dispatch.py` (`fill_card`) | `Layer2CardOutput` → the one `{data+metadata}` payload |

**Proven:** replay-fill + stitch **byte-matches the harvested default #5 (37504==37504 bytes)**; `auto` source tries `ems_backend` (`ws/mfm/174/real-time-monitoring/`) → not running → **honest-degrade to replay** with the exact reason (ConnectionRefused), never fabricates. **+8 tests** (`tests/test_workers_data_fill.py`).

**Data DB = neuract** (user 2026-06-30: *"neuract (target_version1) is now Layer 2's database"*): `config/databases.py` — `DATA_DB=target_version1`, `CONSUMER_SCHEMA="compat"` (the `cmp_mfm_*` views ems_backend reads via the `db_link` search_path), `data_db()`/`compat_view()` helpers; `lt_panels` DEPRECATED.

### ✅ Layer 1b migrated to the compat/neuract data source (the `lt_panels`→`cmp_mfm` fix)
> User 2026-06-30 (surfaced via `host/`): 1b errored — `col_dict` read legacy `lt_panels` but `lt_mfm.table_name` is repointed to `cmp_mfm_*`. Root cause was deeper than a repoint: the old `lt_parameter` dictionary names match only **47/180** of the real neuract columns.

Fix — 1b reads the REAL consumer columns, so **no reconciliation table is needed (the dictionary IS the live schema)**:
- `layer1b/basket/col_dict.py` — reads the asset's real columns from the **`compat` schema** (`config.CONSUMER_SCHEMA`); `latest_nonnull`/`real_table_cols` point at `DATA_DB`/compat.
- `layer1b/basket/describe.py` — derives label/kind/unit from the self-describing neuract names (the ONE naming-convention place).
- `column_basket.py` — one line: `cols = col_dict(table)`. Tests migrated off `lt_panels` (`mfm_lt_022`→`cmp_mfm_036`). **11/11 1b tests pass; AHU-5 → 28 real compat columns; 1b resolves end-to-end.**

**CORRECTION — the compat views + registry repoint are the PARALLEL `ems_compat/` work (canonical: `compat.cmp_mfm_*`, 245 views; `lt_mfm.db_link` pins `search_path=compat,public`).** An earlier pass THIS session mistakenly generated redundant minimal **`public.cmp_mfm_*` views** that would SHADOW compat under the default search_path → **dropped**; that generator is **SUPERSEDED** (`db_build/neuract_compat/` = `drop.py` + a SUPERSEDED README only).

**Atomic-structure (user: *"ensure all these are atomic structured"*):** each tunable = one file — column naming→`layer1b/basket/describe.py`, consumer schema→`config/databases.py` `CONSUMER_SCHEMA`, ems_backend conn→`config/ems_backend.py`, each DATA source→`workers/fill/sources/<source>.py`, each merge step→`workers/stitch/<step>.py`.

⚠ **Same bug remains in the validation layer** (`validate/data_load.py` still reads `lt_panels` via pandas → `pandas.errors.DatabaseError`, 3 live tests red) — the analogous `lt_panels`→compat migration; the parallel work's layer, left untouched.

### ✅ Swap-target re-emit (`layer2/build.py` + `card_input.build_swap_target_input`)
A gated swap accepts target T → the first emit authored the payload for the SHOWN card's shape, but the final card is T (different shape). `run_card` now **re-emits for T** (T inherits the slot's story/group/template via `build_swap_target_input`; no further swap offered) so the payload matches the FINAL card. KEEP (the default) → single emit, no re-emit. **+2 tests** (forced-swap re-emit → `card_id=T`/`_reemit_of=original`; keep → single emit).

### ⚠ Per-shape `frame_map` — likely NOT needed (verified)
The ems_backend RTM consumer returns a **`widgets` frame** (`{config, feeders:[{…queue}], selected_feeder}`), NOT the card shape; the **frontend `realTimeMonitoringMapper.ts` already does frame→card-shape** (and the design says the FE keeps its mapper as-is). So V48's `frame_map` would DUPLICATE the FE mapper — only needed if V48 must emit the fully-resolved payload server-side (the default-replay source already covers offline/byte-match). Treat `workers/fill/frame_map.py` as a thin passthrough; the FE owns the reshape.

### ✅ ems_backend LIVE + 1b col_dict migrated
- **ems_backend daphne UP on :8890** (pyenv 3.11.9; `manage.py check` clean; :8888 = live CMD copy). WS dispatcher `ws/mfm/174/real-time-monitoring/` returns a **real frame over neuract** (`widgets={config, feeders, selected_feeder}`, 6-feeder topology fan-out); our `workers/fill/sources/ems_backend_source.py` drove it end-to-end (no degrade). ⚠ neuract data ends 2026-03-26 → trailing-live window sparse; frame STRUCTURE flows, live VALUES need a pinned-now/historical range (findings time-anchor item).
- **1b col_dict migrated to neuract** (by the parallel work; verified): `layer1b/basket/col_dict.py` reads the REAL consumer columns from `config.CONSUMER_SCHEMA=compat` (`cmp_mfm_*` views) via `describe()`, replacing the stale `lt_parameter` dictionary. Fixes the `host/` error "relation cmp_mfm_165 does not exist". My redundant `public.cmp_mfm_*` views are gone (compat=245 canonical).

### ✅ Render CMD_V2 cards DIRECTLY from the payload (NO Storybook, NO adapters) — user 2026-06-30
User: *"dont layer 2 output directly give the proper payload that cmd v2 card needs"* + *"stop dont use storybook at all"* — correct. The morph made each card **a pure function of ONE payload**, and `card_payloads.payload` = that payload (the component's props). So the frontend mounts the **real CMD_V2 component** with `<Component {...payload}/>` — no reshaping (unlike V47, which needed adapters for its non-native shapes).

Pattern (V47-style, in `host/web`): Vite alias **`@cmd-v2 → CMD_V2/src`** (import-only, CMD_V2 untouched) + `@tailwindcss/vite` + `@import "@cmd-v2/index.css"`; **React deduped** to one copy; a **payload-shape registry** (`src/cmd/registry.tsx`): `{railVM}`→`RealTimeMonitoringRail`, `{supply}`→`SupplyCard`, `{trend}`→`TrendCard`, `{stats}`→`QuickStats`, `{heatmap}`→a thin compose from CMD_V2's own reusable exports (`buildHeatmapSections`+`RealTimeHeatmapSection`, the page-Layout's recipe). `CmdCard` renders via the registry; Storybook iframe removed.

**Verified live (Playwright):** all 5 payload-cards (#5 heatmap, #7 rail, #9 supply, #10 trend, #11 stats) render the **real CMD_V2 components** with real values, **0 render errors, 0 Storybook iframes**; control/nav cards (#6/#8/#160, no payload) → clean placeholders. The card composers that needed Storybook (`MainHeatmapCard` in `.stories.tsx`) are bypassed by reusing the page-Layout's reusable exports.

### ✅ LIVE data end-to-end — heatmap renders live neuract values (user 2026-06-30)
Full chain working: **prompt → 1a/1b → Layer 2 (morph metadata + `data_instructions.ems_backend` fetch spec) → ems_backend (anchored) serves the live history time-series over neuract → host fetches the frame → frontend maps it via CMD_V2's OWN `mapFrame` → real heatmap component renders LIVE values.**

| piece | where | does |
|---|---|---|
| **time anchor** | `ems_backend/lt_panels/services.py` `_now()` + `EMS_REFERENCE_NOW` env (V48 copy, editable) | window 'now' → the data's latest (neuract ends 2026-03-26) so trailing windows carry history; daphne launched with `EMS_REFERENCE_NOW="2026-03-26T05:55:09+05:30"` → 6 feeders × 30 samples of kw/kvar/pf/volt/amp/i_unbal+bands |
| **AI drives ems_backend** | `layer2/prompts/data_instructions.md` + output schema; `layer2/emit/data/consumer_binding.py` (`ai_spec`) | the AI emits `data_instructions.ems_backend = {endpoint, window_seconds, interval_seconds, sample_count, metrics, selection}` — it decides WHAT data to fetch incl. the history depth; merged with the deterministic mfm_id (1b) |
| **host live frame** | `host/server.py` `_live_frame()` → `workers/fill/sources/ems_backend_source.fetch_frame` | one aggregate frame per page in the response (`live_frame`) |
| **frontend maps it** | `host/web/src/cmd/registry.tsx` (`mapFrame` from CMD_V2) | `mapFrame(live_frame) → snapshot.history` (CMD_V2's OWN reusable mapper — NO Python re-impl) → `buildHeatmapSections` → live heatmap; threaded App→CardGrid→CardFrame→CmdCard |

**Verified (Playwright):** heatmap #5 shows `Incomers 2,105 kW (78%)/2,700 contract · I1 1375 783 0.87 6303 84 1.5 …` = **exactly the live frame** (Transformer 1 kw=1375.234), real component, 0 errors/iframes.

### ⬜ Live rail/supply/trend/stats (follow-up)
Same `mapFrame` seam: `buildRailViewModel(snapshot)` → the rail card payloads ({railVM}/{supply}/{trend}/{stats}). Currently those render the harvested default.

**DATA source: reuse V48's `ems_backend/` consumer strategies (copy of CMD), driven by `(resolved mfm_id, page-endpoint)` through the WS dispatcher.** Each card's `cmd_catalog.card_handling.backend_strategy` names the consumer **view** (e.g. `consumers/real_time_monitoring/…`); the dispatcher resolves the **class-correct** strategy from the asset's `mfm_type`. The AI emits `data_instructions` = the *parameters* (asset `mfm_id` from 1b, preset/range, sampling, widget, selection commands) — **not** the column list (columns are the consumer's fixed per-class recipe; see hardcoding finding). Pairs with the harvested `card_payloads` ground truth + `key_roles` (per-leaf DATA-fill vs METADATA-morph): METADATA leaves = AI morph; DATA leaves = filled by the consumer.

- **RTM vertical slice first** — RTM heatmap card = the `pcc_panel` aggregate (PCC-class, fixed 7-metric roster — safe, no cross-class concern): AI emits `{exact_metadata, data_instructions}` → drive `ems_backend` WS `ws/mfm/<pcc mfm_id>/real-time-monitoring/` → fills DATA leaves → stitch → **assert byte-match vs the harvested `card_payloads` default**.
- **Build-time:** stand up `ems_backend/` (deps + `lt_panels_db` reachable) and confirm the RTM WS yields the feeder-heatmap `widgets` envelope before wiring the morph.
- Then expand panel-by-panel across the 36 cards / 23 subcards.

## Open items (tracked in `open_items/`, toggled in `config/flags.py`)
page-wise-shared detection · $ctx source form · column_row dialect · data_fill_shape source · composite/sld map · test-DB contents · FE-interdependency-in-progress · the 10 review fixes.

---

## 📋 FULL-CODEBASE STATUS → see `V48_END_TO_END_STATUS.md` (2026-06-30, whole-codebase audit)
Runtime SPINE is genuinely live end-to-end on all 9 pages (**38/38 cards fillable**), backed by 44 ems_backend consumers +
DB-keyed `derivations/` + the deployed `copilot/` typeahead. BUT the atomic-structure rule left **~110+ stub files** whose
logic is inlined into live modules (layer1b ~13, layer2/emit ~37, data/ 14, workers ~20) — the tree looks more complete than
it is. **Real live gaps:** `run/layer2_all.py` drops `already_chosen` (no-dup swap gate fed empty set) · `contracts/` (validate
+ 8 invariants + 10 schema.json) ENTIRELY unbuilt · ems_backend `ht_panel`+`sub_panel` = StubStrategy across all 13 screens ·
15/25 tests are placeholders · `data/` package stubbed+bypassed. **Pending:** value-correctness sweep (6,353 V bug) · remove
inert AI-recovery emit · contract real-sourcing on compat · the 4 walls · interdependency (deferred). Full breakdown in the doc.
