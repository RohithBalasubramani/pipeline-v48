
## Reachability Map (read-only) — 2026-07-04

AST import-walker rooted at entrypoints: host/server.py, run/harness.py, host/display_dash.py,
ems_exec/serve/run.py, scripts/sync_neuract_registry.py, copilot/server.py, db/seed_schema_and_endpoints.py,
copilot/build/__main__+cli, ALL tests/. Copilot treated as its OWN import root (flat `import generate` etc.).

TOTAL .py (excl archive/node_modules/pycache) = 411 | REACHED = 272 | DEAD = 139.
NONE of the 139 dead files fall under the deferred (parallel-edit) dirs — all dead code is OUTSIDE
layer1b/resolve, data/registry, ems_exec, host/web/src/cmd/fill, host/server.py, config/validation.py,
config/asset_granularity.py. So this run's dead[] = delete candidates + a few build-tool keeps; zero 'defer'.

Verify-before-delete method: ripgrep whole tree for dotted-path + basename; then filter to REAL python
import statements (from/import) + subprocess/glob/path strings; discarded .md/.sql/.git substring noise.
Key rescues found by verification (NOT dead): config/intents.py (imported by layer1a/parse/metric_intent_defaults);
scripts/build_stripped_payloads.py (DB-column build tool, referenced by provenance comments — KEEP).
Dead clusters are self-referential islands (dead-imports-dead): config/defs/* + seed_app_config; the
grounding render-guarantee kit; the per-shape layer2/emit/metadata/* files; contracts/*; workers/sharedctx/*.

## PURGE RUN — 2026-07-04 (Opus 4.8)

Re-verified all 140 candidates (AST import-walker across whole tree + rg for
dynamic/subprocess/glob/tsx refs). Only rescue-flag was copilot/__init__.py (AST saw
copilot.build.* as importers) — PROVEN false positive: copilot/__init__.py is EMPTY(0 lines),
copilot build runs FLAT (`cd copilot && python3 build.py`, dir on sys.path, `import build`),
top-level `copilot` package is never entered (verified: `import build` OK with copilot NOT in
sys.modules; live pipeline never loads copilot). Safe to delete. 0 real rescues; 139 dead + copilot init.

### Batch 1 — layer2 emit/parse/resolve/catalog leaves (33 files)
Deleted layer2/emit/metadata/{base,dual_owned_slots,footer,heatmap,hpq_*,kpi_tile,progress,radar,
rail,sankey,sld,table,text}.py + layer2/emit/data/{envelope,field_*,fill_mode}.py +
layer2/emit/{atom_emit,standalone_emit,ctx_source_form}.py + layer2/parse/{__init__,self_correct}.py +
layer2/resolve/{card_resolve,recipe_reconcile}.py + layer2/catalog/{contract_components,feasibility_recompute}.py.
(emit/metadata & emit/data dirs KEPT — asset_3d/producer/split/endpoint_registry/consumer_binding are live.)
After: import host.server+run.harness OK; pytest collect 259/299 clean (was 249/289 — dead modules had
blocked some collection).

### Batch 2 — config defs/policy island + contracts (42 files)
config/defs/{__init__,card_grid_size,cards_intent,ems_backend,flags,gates,intents,metrics,
payload_shapes,routes,swap,validation,windows}.py + config/seed_app_config.py (self-ref island) +
config/{bands,demand_policy,dialects,endpoint_policy,flags,frame_config_policy,history_bucket_ts,
history_policy,l3_policy,limit_overrides,live_window_policy,mapper_frame_contract,payload_shapes,
pq_anchor_policy,time_labels,time_policy,vc_anchor_policy,window_metrics_policy,window_read}.py +
contracts/validate.py + contracts/invariants/*.py (8, stubs). contracts/*.schema.json KEPT.
Import OK after.

### Batch 3 — data/grounding/ems_compat/layer1a-b readers + copilot init (22 files)
copilot/__init__.py (empty, unused) + data/cmd_catalog/*.py + data/{derived_metrics,nameplate}.py +
data/lt_panels/{timeseries,table_cols_cache}.py (panel_members.py KEPT) +
ems_compat/build_compat_views.py (.sql/.md KEPT) +
grounding/{aggregate,endpoint_resolve,energy_register,metric_class,nameplate,normalizers,window_clamp}.py +
layer1a/partition_inputs/{selection_dimension,v_interaction}.py (card_combo/card_link/page_control/
interdependency_prose KEPT) + layer1b/basket/{derived_reconcile,feasible_probable}.py +
layer1b/parse/{__init__,loads_lenient}.py. layer1b/resolve/ (DEFERRED) untouched. Import OK.

### Batch 4 — outputs/payload_db/run-diag/scripts/workers + tsx + top init (43 files)
__init__.py (top; pipeline_v48 imported flat, no dotted-pkg refs) + outputs/audit_db/check*.py +
outputs/batch/{analyze,audit_endpoints,build_prompts,compare_runs,run_batch}.py +
outputs/{coverage_analyze,coverage_sweep,panel_audit,prompt_check,prove_ems_exec,rerun10,
verify_binding,verify_exec_fill,verify_pages}.py + payload_db/{enrich/write_enrichment,
load_asset_payloads,load_payloads,page_map,verify}.py (harvest_*.mjs/schema.sql/*.json/*.md KEPT) +
run/{card_diag,layer_diag,trace}.py (harness/parallel/degrade_gate/layer2_all/... KEPT) +
scripts/{scrub_stripped_event_seeds,_probe_asset_wording,cert_rerun,survey_rerun,sweep_judge}.py +
workers/**/*.py (all) + host/web/src/components/{PipelineHeader,CardFrame}.tsx (no importers).

### Cleanup
Purged 58 __pycache__/.pytest_cache dirs. Removed orphaned-empty pkg dirs: data/cmd_catalog,
layer2/parse, layer1b/parse, contracts/invariants, workers/sharedctx, workers, config/defs.
LEFT (not mine / not empty-by-me): layer2/morph (pre-existing empty), .claude/worktrees (harness).

### Deferred dirs — audit only (parallel workflow owns; NOT touched)
layer1b/resolve/, data/registry/, ems_exec/, host/server.py, host/web/src/cmd/fill/,
config/validation.py, config/asset_granularity.py. The two listed deferred files
host/web/src/cmd/fill/dg-{engine-cooling,fuel-efficiency}/types.ts were ALREADY GONE on disk
(parallel workflow removed them; their view-model.ts still `import './types'` — parallel's in-progress state).

### RESULT
140 files deleted (6742 LOC). host.server+run.harness import OK; pytest collect 259/299 clean
(rose from 249/289 — dead modules had blocked collection); host/web `npx tsc --noEmit` exit 0. GREEN.
