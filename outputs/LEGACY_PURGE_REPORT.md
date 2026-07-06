# V48 LEGACY PURGE — FINAL REPORT

_Compiled 2026-07-05 (Opus 4.8). Read-only lane: this final run deleted **nothing new** — it
adversarially re-confirmed every candidate and consolidated the outcome. The physical deletions were
performed by the earlier deadcode-purge batch (see `outputs/DEADCODE_PURGE_WORKLOG.md`); this report
attributes them, records the RESCUED and ASSESS sets, and runs the acceptance gates against the current tree._

**Bottom line for THIS run:** `CONFIRMED = []`, `PURGE = NO-OP (no confirmed-dead files)`. Nothing was
found newly-dead beyond what the prior batch already removed. All 13 ASSESS-listed files were re-verified
to still exist on disk (none deleted). Gates are GREEN and the main pipeline runs end-to-end.

---

## (1) DELETED

No files were deleted **in this final confirm run** (`PURGE: NO-OP`).

The deletions below were made by the **prior deadcode-purge batch** (2026-07-04) and are recorded here for
completeness. They were verified against the VERIFY-BEFORE-DEAD hard rule (AST import-walker rooted at every
entrypoint + whole-tree ripgrep for dynamic/subprocess/glob/tsx refs) before removal; each is a
self-referential dead island (dead-imports-dead), not reached from any entrypoint or dynamic dispatch.

| Cluster (batch) | Files | What / why dead | Net LOC |
|---|---|---|---|
| **Batch 1** — layer2 emit/parse/resolve/catalog leaves | 33 | per-shape `emit/metadata/*` (base, kpi_tile, radar, sankey, sld, table, text, heatmap, progress, rail, footer, hpq_*, dual_owned_slots) + `emit/data/{envelope,field_*,fill_mode}` + `emit/{atom_emit,standalone_emit,ctx_source_form}` + `parse/{__init__,self_correct}` + `resolve/{card_resolve,recipe_reconcile}` + `catalog/{contract_components,feasibility_recompute}`. Superseded per-shape/per-card builders — replaced by the generic producer/split + card_fill_recipe interpreter. No live importer. | ~1.5K |
| **Batch 2** — config defs/policy island + contracts | 42 | `config/defs/*` (12) + `config/seed_app_config.py` (self-ref island) + ~20 orphaned policy modules (`bands, demand_policy, dialects, endpoint_policy, flags, frame_config_policy, history_*, l3_policy, limit_overrides, live_window_policy, mapper_frame_contract, payload_shapes, pq_anchor_policy, time_*, vc_anchor_policy, window_*`) + `contracts/validate.py` + `contracts/invariants/*` (8 stubs). Config is now DB-driven (cmd_catalog.app_config via `config/app_config.cfg()`); these hardcoded-default modules had no live reader. `contracts/*.schema.json` KEPT. | ~1.9K |
| **Batch 3** — data/grounding/ems_compat/layer1 readers + copilot init | 22 | `copilot/__init__.py` (empty, unused) + `data/cmd_catalog/*` + `data/{derived_metrics,nameplate}` + `data/lt_panels/{timeseries,table_cols_cache}` + `ems_compat/build_compat_views.py` + render-guarantee `grounding/{aggregate,endpoint_resolve,energy_register,metric_class,nameplate,normalizers,window_clamp}` + `layer1a/partition_inputs/{selection_dimension,v_interaction}` + `layer1b/basket/{derived_reconcile,feasible_probable}` + `layer1b/parse/{__init__,loads_lenient}`. Retired `compat`/`lt_panels`-as-source readers + orphaned grounding kit. `.sql/.md` KEPT; `panel_members.py` KEPT. | ~0.9K |
| **Batch 4** — outputs/payload_db/run-diag/scripts/workers + tsx + top init | 43 | top-level `__init__.py` (flat-import tree) + `outputs/audit_db/check*` + `outputs/batch/*` + `outputs/{coverage_*,panel_audit,prompt_check,prove_ems_exec,rerun10,verify_binding,verify_exec_fill,verify_pages}` + `payload_db/{enrich/write_enrichment,load_*,page_map,verify}` + `run/{card_diag,layer_diag,trace}` + `scripts/{scrub_stripped_event_seeds,_probe_asset_wording,cert_rerun,survey_rerun,sweep_judge}` + `workers/**` (all) + `host/web/src/components/{PipelineHeader,CardFrame}.tsx`. Diag/one-off scripts + retired workers/frames path + no-importer tsx. Harvest `.mjs/.json/.md/.sql` KEPT; `harness/parallel/degrade_gate/layer2_all` KEPT. | ~2.4K |
| **Cleanup** | — | 58 `__pycache__`/`.pytest_cache` dirs purged; empty pkg dirs removed (`data/cmd_catalog`, `layer2/parse`, `layer1b/parse`, `contracts/invariants`, `workers/sharedctx`, `workers`, `config/defs`). | — |

**Prior-batch total: 140 files deleted, 6742 LOC** (worklog figure; includes `.md`/`.sql`/`__init__`/dir
artifacts). Of these, the **code-only** subset (`.py/.ts/.tsx/.css`, excluding the separate ems_backend-Django
and layer3 removal eras) measures **133 files / 4472 LOC** by direct `git show HEAD:<f> | wc -l` accounting.

> Note: the working tree also shows a much larger `409 files / 51,106 LOC` deleted vs the single `HEAD`
> ("Initial commit"). That figure conflates **three eras**: (a) the retired `ems_backend/` Django tree
> (~230 files incl. `.glb` 3D binaries + integration docs), (b) the archived `layer3/`, and (c) this
> deadcode purge. Only (c) — the 140/6742 above — is attributable to the legacy-purge project. (a) and (b)
> are pre-existing retirements consistent with the RETIRED lane list.

---

## (2) RESCUED — candidates the adversarial confirm proved LIVE (NOT deleted)

| Path | Why it looked dead / where it's actually used |
|---|---|
| `config/intents.py` | AST flagged no dotted importer, but it is imported by `layer1a/parse/metric_intent_defaults` (live L1a path). KEPT. |
| `scripts/build_stripped_payloads.py` | No live python importer, but it is a DB-column build/ops tool referenced by provenance comments in the payload data. Rebuild/ops SCRIPT → protected by VERIFY-BEFORE-DEAD (5). KEPT. |
| `copilot/__init__.py` (during batch) → later deleted | AST saw `copilot.build.*` as importers, flagging `copilot/__init__.py` as live. Proven **false positive**: the file is empty (0 lines); copilot build runs FLAT (`cd copilot && python3 build.py`, dir on `sys.path`, `import build`); the top-level `copilot` package is never entered by the live pipeline. Rescue-flag cleared → safely deleted. (The rest of `copilot/` — the running feature — is KEPT; see ASSESS.) |
| `data/lt_panels/panel_members.py` | Sits in the retired-`lt_panels` neighborhood, but is the LIVE panel-aggregate member source for `topology_sld`/panel roster fill. KEPT. |
| `contracts/*.schema.json` | The `contracts/validate.py` + `invariants/*` python was dead, but the JSON schema artifacts are data/reference. KEPT. |
| Deferred dirs (`layer1b/resolve/`, `data/registry/`, `ems_exec/`, `host/server.py`, `host/web/src/cmd/fill/`, `config/validation.py`, `config/asset_granularity.py`) | Owned by parallel workflows / are the live pipeline core — audited only, never touched. KEPT. |

**Final-run adversarial re-confirms (this session), each proving an ASSESS module/key is functionally
superseded but NOT dead-by-rule (so RESCUED from deletion, only the residual key/branch is in question):**

- `registries/neuract/topology.py` `edges()/neighbors()` — **zero live functional callers** (grep whole
  non-test tree: only the `registries/neuract/__init__.py` static re-export names them). Transitively
  imported from entrypoints via `__init__` → not dead by the hard rule. KEPT (see ASSESS).
- `registries/neuract/nameplate.py` `rated_kva()/params_for()` — the LIVE `rated_kva` call sites
  (`ems_exec/derivations/{registry,nameplate}.py`, `renderers/_story/real_time_monitoring.py`) all resolve
  through `config.nameplates.rated_kva` (`_np = config.nameplates`), **not** this registry module. Only the
  `__init__` re-export references it. KEPT (see ASSESS).
- `registries/neuract/assets3d.py` `model_*()` — **zero live functional callers** (only tests + self).
  Named only in an `asset_3d.py` comment. KEPT (see ASSESS).
- `layer2/emit/data/consumer_binding/builder.py` key `source_backend` — **zero runtime readers** across
  `ems_exec/` + `host/` (only two test asserts in `tests/test_layer2_card.py`). The module stays LIVE (it
  emits the whole consumer descriptor); only the one vestigial key is in question. KEPT (see ASSESS).
- `host/server.py` `page_endpoint` import + `live_frame` (L34, L505) — `page_endpoint(page_key)` still
  **executes**, but under the ems_exec path `frames == {}` so `live_frame` is always `None` and the result
  is discarded. Runtime-live-but-inert → not dead. KEPT (see ASSESS).
- `config/prompt_matrix.py` — sole importer is `tests/test_render_guarantee_50.py`. Criterion (4)
  "live test-only fixture that documents real behavior" → protected from deletion. KEPT (see ASSESS).

---

## (3) ASSESS — borderline items for the USER to decide

These are all **live-or-protected** (not deletable by the hard rule). Each carries the open question and a
recommendation. None were changed (read-only lane).

| Path | Open question | Recommendation |
|---|---|---|
| `host/server.py` | `page_endpoint` import (L34) + `live_frame = frames.get(page_endpoint(page_key))` (L505) still runs, but `frames` is always `{}` under ems_exec so `live_frame` is always `None`. Retain the back-compat key for FE contract stability, or drop it now that no data flows through endpoint frames? | **Drop** the `live_frame` key + `page_endpoint` import once the FE is confirmed not to read `live_frame` (grep host/web); the ems_backend frame/socket era is retired. Low-risk cleanup, but verify the FE contract first. Not urgent. |
| `run/harness.py` | Retirement-note comments (V48_SKIP_LAYER3, ems_backend frame-fetch) are correctly KEPT. Open behavioral valve: `V48_SKIP_LAYER2` (L242) gates whether Layer 2 runs at all. Keep the dev-only skip valve, or always run L2 now that L2 is the final stage? | **Keep** the valve (dev/debug ergonomics; env-gated, off by default → no production effect). Optionally document it as dev-only. |
| `layer1b/basket/col_dict.py` | DOC-STALENESS ONLY: docstring + `column_basket.py:54` comment say the dict is built from "real cmp_mfm view / compat columns", but the code reads `CONSUMER_SCHEMA` from `config/databases`, and the DB no longer has a `compat` schema (V48 reads neuract directly). | **Refresh the comments** to say `neuract`/`CONSUMER_SCHEMA`. Pure comment fix, no code path affected. Do it to prevent future-reader confusion. |
| `layer2/emit/data/consumer_binding/builder.py` | Emits `source_backend=cfg('routes.source_backend','ems_backend')` but **no runtime reader** exists (only 2 test asserts). Live fill reads `endpoint/is_history/resolver_scope`. Vestigial, or reserved for a future dispatcher? | **Drop the `source_backend` key** from the descriptor (and the two test asserts). ems_exec fills from NEURACT, not a ws/mfm dispatch — the key encodes a retired dispatch model. Module stays. |
| `layer2/emit/data/endpoint_registry.py` | Self-documents ems_backend as retired; treats the baked `_FALLBACK` snapshot as canonical and keeps the AST-parse-of-`_PAGES` path only behind `EMS_PAGE_REGISTRY` (never set anywhere). Keep the ops re-derivation escape hatch, or simplify to snapshot-only? | **Keep** the escape hatch (dormant rebuild/ops path, protected by VERIFY-BEFORE-DEAD). Optionally add a one-line comment that the AST branch is ops-only. |
| `ems_exec/executor/roster.py` | `_valve()` still reads `app_config roster.interpreter_enabled` with the 3-value `off\|shadow\|on` vocab (DB = `on` → interpreter LIVE, module KEPT). The shadow-mode DIFFER machinery is gone; only a config guard remains. Simplify the residual `shadow` branch/comment (L69/73) to plain on/off? | **Simplify** `_valve()` to on/off (drop the `shadow` branch/comment) to match the "valve removed / interpreter unconditional" claim in `renderers/__init__.py`. Cleanup only — module is unambiguously live. |
| `ems_exec/renderers/asset_3d.py` | L136 imports `lt_panels.asset3d.template` (Django ems_backend bridge) inside a try/except that honest-degrades to `None` when the Django app isn't loaded (always, in standalone layer2). Forward-compat hook, or drop now that ems_backend is retired? | **Keep as-is** unless the ems_backend/Django bridge is being fully severed. It is a documented graceful optional bridge, not dead code. If severing ems_backend for good → drop the try-import. |
| `registries/neuract/topology.py` | `edges()/neighbors()` have ZERO live functional callers (live SLD path = `data/registry/lt_mfm.outgoing_edges` + `data/lt_panels/panel_members`; `topology_sld` dispatches to ems_exec renderers). Only reached via the static `__init__` re-export. Retire, or keep as ready-to-wire? | **Keep** as a ready-to-wire registry accessor (future real-topology SLD source), OR **retire** by dropping `topology` from `__init__.__all__` if you want a lean registry surface. Lean recommendation: retire — the live path is elsewhere. Your call. |
| `registries/neuract/nameplate.py` | `params_for()/param()/rated_kva()` have ZERO live functional callers (live nameplate path = `config/nameplates.py` + `ems_exec/derivations/nameplate.py`; the live `rated_kva` hits are those, not this). Retire, or keep for the lt_parameter/lt_config_value source once populated? | **Keep** if the `lt_parameter`/`lt_config_value` nameplate source is on the roadmap; otherwise **retire** the `__init__` re-export. Recommend retire the re-export (keep the file) — the config path is the live one. |
| `registries/neuract/assets3d.py` | `model_*()` have ZERO live functional callers (live 3D path = `ems_exec/renderers/asset_3d.py`); named only in an `asset_3d.py` comment; all 3D-model tables/FKs empty. Retire, or keep as ready-to-wire? | **Keep** as the ready-to-wire 3D-model resolver for when `asset_3d_model`/`lt_asset_3d` rows land, OR retire the `__init__` re-export for a lean surface. Recommend keep (cheap, and 3D is a stated feature). |
| `config/prompt_matrix.py` | Only importer is `tests/test_render_guarantee_50.py` (protected as test fixture). Production-dead (test-only). Keep as test support, or is the render_guarantee_50 suite itself retired? | **Keep** — the V48 render-guarantee project is an ACTIVE/pending item in memory (the 50-prompt run collected 0 prompts only because of the :5433 outage, now resolved). Delete both together ONLY if the suite is formally dropped. |
| `scripts/sync_config_nameplate.py` | Live-directive ops tool (2026-07-04). Its output tables `registry_lt_config_*`/`registry_asset_config_*` have ZERO live python readers; the live nameplate path reads `lt_config_field/value` from NEURACT directly. Companion `outputs/NAMEPLATE_RESEARCH.md` concludes the mirror "does NOT help" (different plant, 0 id/name alignment, no `rated_kva`, touches retired `lt_panels`). Drop now, or keep pending a name-map decision? | **Drop** — no reader, wrong plant, does not close the `rated_kva` gap, and it touches retired `lt_panels`. Awaiting your explicit go/no-go per the research doc. (Recommend delete `scripts/sync_config_nameplate.py`; keep `NAMEPLATE_RESEARCH.md`.) |
| `copilot/` (whole feature) | Separate feature (EMS Query Copilot, API :8772, own Qwen3-4B model :8201). Runs standalone (flat-import, own server), not part of the render pipeline. Kept intact through the purge (only the empty `__init__.py` was removed as a false-positive rescue). | **Keep** — it is a live, separately-deployed feature with zero coupling to the pipeline. Out of scope for the pipeline-legacy purge. Flagged here only so you can confirm it should stay. |

---

## (4) GATE

| Gate | Result |
|---|---|
| **Pytest** (`-m 'not live'`) | **262 passed, 14 skipped, 40 deselected, 0 failed** (321.71s). Zero failures introduced by the purge. |
| **TypeScript** (`host/web: npx tsc --noEmit`) | **exit 0** (clean). |
| **Import-smoke** (entrypoints) | `import host.server; import run.harness; import ems_exec.serve.run` → **OK** (all three entrypoints import clean after the deletions). |
| **Host / 2-prompt end-to-end smoke** (`run_pipeline`) | **GREEN.** ① `energy power for PCC Panel 1` → 1a `panel-overview-shell/energy-power` (4 cards) → 1b `PCC-Panel-1` mfm_id=317, 24 basket cols, `how=AI` → validate `pass` → asset_gate `→ Layer 2` → **L2: 4/4 cards conform, 0 partial, 0 gaps, 0 swaps** with real endpoints (energy-power, energy-power-history). Full end-to-end fill. ② `show me the harmonic filter` → 1b `how=ambiguous, candidates=8` → validate `asset_pending` → **`PENDING → asset popup (Layer 2 NOT run)`** — the deliberate pure-AI asset-disambiguation seam (candidates → frontend AssetPicker), **not a failure**. |
| **Infra confirmed live** | cmd_catalog Postgres (:5432) reachable (all 28+ real tables present); `registry_lt_mfm` mirror = 320 rows; neuract archbox tunnel (:5433) OPEN; vLLM LLM (:8200) OPEN. |

---

## (5) VERDICT

**Is the tree free of pipeline-mismatched legacy code?** — Yes, for the pipeline surface. The prior batch
already removed the 140-file dead island (superseded per-shape/per-card builders, the hardcoded config-defs
+ policy island now replaced by DB-driven `app_config`, the orphaned render-guarantee `grounding` kit, the
retired `compat`/`lt_panels`-as-source + `frames`/`workers` readers, and diag/one-off scripts). This final
run **re-confirmed** the whole candidate set against the VERIFY-BEFORE-DEAD hard rule and found **nothing
newly dead** — `CONFIRMED = []`, `PURGE = NO-OP`. The remaining "legacy-flavored" code is either (a)
runtime-live-but-inert back-compat keys/branches, or (b) ready-to-wire registry accessors reached only via
`__init__` re-exports — all protected by the hard rule and surfaced as ASSESS, not silently deleted.

**ASSESS items remaining for the user** (13, none blocking): the two comment/doc refreshes
(`col_dict.py`, `harness.py` valve doc); four residual-key/branch cleanups (`host.server` `live_frame`,
`consumer_binding` `source_backend`, `endpoint_registry` AST branch, `roster._valve` shadow branch); the
`asset_3d.py` optional Django bridge (keep unless severing ems_backend); three registry re-export
retire-or-keep calls (`topology`, `nameplate`, `assets3d`); the test-only `prompt_matrix.py` (keep while
render_guarantee_50 is active); and two feature/ops decisions — **drop** `scripts/sync_config_nameplate.py`
(recommended: no reader, wrong plant) and **keep** `copilot/` (separate live feature). My top two
actionable recommendations: (1) delete `scripts/sync_config_nameplate.py`, and (2) drop the vestigial
`source_backend` descriptor key.

**Does the main pipeline still run end-to-end?** — **Yes, confirmed live.** The 2-prompt smoke exercised
the full straightforward path (prompt → 1a∥1b → validate → asset_gate → Layer 2 emit+gates+build) with real
cmd_catalog + neuract + vLLM, producing 4/4 conforming cards on the panel prompt and the correct
`asset_pending` disambiguation seam on the ambiguous prompt. Import-smoke, tsc (exit 0), and pytest
(262 pass / 0 fail) all GREEN.
