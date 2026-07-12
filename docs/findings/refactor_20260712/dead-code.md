# Dead-code audit — pipeline_v48 (dimension: DEAD CODE) — 2026-07-12

Method: for every candidate, the ENTIRE tree (py + md + sql + json + js/mjs/ts/tsx + .service,
excluding archive/ outputs/ .claude/ .playwright-mcp/ __pycache__/ node_modules/ dist/) was grepped
for both the symbol name and the bare string (house rule 5: DB-driven dispatch). Import graph
cross-checked for parenthesized, relative, and copilot's flat (`import db`) import styles; monkeypatch
seams (`monkeypatch.setattr(F._deriv, ...)`) and re-export doors (`from ...fill import GAPS_KEY`)
checked before declaring any import dead. Ruff F401/F811/F841 used only as a candidate generator —
every hit was seam-verified by hand. Dispatch doors audited: derivation registry is a closed dict
(`ems_exec/derivations/registry.py`), the DB expression language is a closed AST with only
`sqrt/abs/min/max/round` (`ems_exec/derivations/evaluate.py:23`) — DB rows cannot reach arbitrary
python fn names.

## Excluded as concurrent WIP (created TODAY 2026-07-12 02:15–02:37 by a parallel session — NOT dead)
- obs/ trace layer: `trace.py, span.py, event.py, bus.py, db_tap.py, llm_tap.py, middleware.py, sink_console.py, sink_jsonl.py, sink_pg.py, redact.py, sql_trace.py, query.py` (design: `docs/OBS_TRACE_DESIGN.md`, dated today; `docs/audit_2026-07-12/observability.md:241` already tracks the unwired `legacy_event`)
- `profiler/` (4 files), `validation/` (whole package incl. checks/, corpus/), `tools/payload_diff/` (10 files, mtimes 02:26–02:30), `db/seed_prompt_corpus.sql`

## Cleared candidates (checked, ALIVE — do not delete)
- `services/dict_merge.py` — importers: `layer2/emit/metadata/asset_3d.py:162`, `ems_exec/renderers/asset_3d.py:28`.
- `knowledge/ems.py` — `host/server.py:317` (`from knowledge.ems import ask`). knowledge/prompts/ems.md is its prompt.
- `layer2/swap/{combo_cascade,gate_no_dup,gate_template_dedup}.py` — parenthesized import `layer2/swap/decide.py:10`, called at :28-30.
- `copilot/*` (db, llm, retrieve, generate, starters, has_data, validated, aliases, build/*) — flat standalone imports; wired via `copilot/server.py:16-20`, `copilot/build/__init__.py:40`, `copilot/build/entities.py:29-30`, `copilot/build/alias_build.py:7`, `copilot/build/__main__.py`.
- `ems_exec/derivations/{power_quality,expressions,current,...}.py` modules — `ems_exec/derivations/registry.py:25,297`.
- `ems_exec/renderers/_story/*` — BUILDERS dispatch → `ems_exec/renderers/narrative_ai.py:25`.
- `partition/*` — `layer1a/build.py:6`; `layer1a/partition_inputs/*` — `partition/coupling_lookup.py`.
- run/, validate/, grounding/, data/, registries/, host/ modules — every module has ≥1 real importer (validate/build.py ← run/harness.py:21; host modules ← host/server.py + host/assemble.py + tests).
- Seeded app_config keys that look unread (46 of 208 dotted keys) are ALL read via dynamic prefixes: `config/vocab.py:31-34` (`cfg(f"vocab.{name}")`), `ems_exec/executor/fab_guards.py:70-73` (`cfg(f"fab_guards.{name}")` per-class valves), `llm/client.py:65` (`cfg(f"llm.timeout.{stage}")`), `host/web/src/layout/vocab.ts:3` (FE reads section `layout_fe`), validation/corpus (WIP). NO dead app_config flags found.
- `ops/db-tunnel.service` — installed AND enabled on this host (`systemctl list-unit-files` → `db-tunnel.service enabled`); the source-of-truth for the :5433 tunnel unit.
- `payload_db/` (.mjs harvest tools + schema.sql + enrich/) and `scripts/`, `tools/`, `db/seed_*.sql` — offline/one-time ops entrypoints, documented in `docs/V48_END_TO_END_STATUS.md:77` ("payload_db/ems_compat = offline CLI harvest tools") and run-books; runnable by name. Not dead.
- `fill._deriv` (`ems_exec/executor/fill.py:37`) — LIVE monkeypatch seam: `tests/test_fill_point_slots_and_placeholder_null.py:75,86`, `tests/test_agentb_fill_fixes.py:149` patch `F._deriv.binding`. KEEP even though ruff flags F401. Same for `fill.GAPS_KEY` (re-exported to `tests/test_fuel_anatomy_structure.py:16` etc.).

---

## FINDINGS

### F1. README.md architecture section references four deleted paths and five relocated design docs
- File: `README.md:3-13` — low risk, behavior-preserving (doc only)
- Evidence: line 9 `` `workers/` data-fill + aggregation + shared-context + stitch · `frames/` DATA-fill target shapes ``; line 11 `` `db_build/` (quarantined) ``; line 3 `` → `run/assemble` → PageFrameEnvelope ``; line 13 claims `V48_DESIGN_NOTES.md`, `V48_PAYLOAD_MORPH_CORRECTION.md`, `V48_INTERDEPENDENT_CARDS_DESIGN.md`, `V48_STORYBOOK_MORPH_VERIFICATION.md` live "at the pipeline_v48/ root". Filesystem: `workers/`, `frames/`, `db_build/`, `run/assemble.py` and all of those root docs are MISSING — the docs are in `docs/`, data-fill is `ems_exec/executor/`, assembly is `host/assemble.py`.
- Refactor: rewrite "Where each concern lives" to the real tree (layer1a ∥ layer1b → layer2 → ems_exec → fab_guards → host).
- Tests: none (docs).

### F2. ems_compat/ is a superseded root directory (0 py files) holding only historical SQL template + coverage truth-table
- File: `ems_compat/compat_view_template.sql:1` + `ems_compat/COVERAGE.md` — low risk, behavior-preserving
- Evidence: `V48_FULL_WALKTHROUGH_2026-07-02.md:84` — "The `compat` schema is **superseded/gone** — V48 reads neuract directly (`CONSUMER_SCHEMA='neuract'`); `ems_compat/` survives as historical tooling + the COVERAGE.md truth-table." Only remaining live reference is the NAME string in the copilot coupling test's FORBIDDEN list (`copilot/tests/test_no_coupling.py:18`) — name-based, unaffected by a move.
- Refactor: move `ems_compat/` → `docs/ems_compat/` (COVERAGE.md is still cited by `docs/IMPLEMENTATION_PROGRESS.md:127`).
- Tests: `copilot/tests/test_no_coupling.py` (string list; still passes).

### F3. Fifteen dead import names across 11 files (ruff F401, each seam-verified: no re-export consumer, no monkeypatch handle, no DB-string dispatch)
- Anchor: `ems_exec/executor/fill.py:34` — low risk, behavior-preserving
- The list (KEEP `fill._deriv` at fill.py:37 — live test seam; everything below verified dead):
  - `host/server.py:38` — `from ems_exec.serve import run as ems_exec_run` (0 uses in body; the real consumer is `host/exec_cards.py:12`; no test references `S.ems_exec_run`)
  - `host/server.py:43` — `_run_cards` in the `from host.exec_cards import (...)` tuple (0 uses; tests patch `A._run_cards` = host.assemble at `tests/test_multi_asset.py:171`; profiler wraps `exec_cards`/`assemble`, never `server`)
  - `ems_exec/executor/fill.py:34` `_registry`, `:38` `_qp`, `:39` `_dsn` — no `fill._registry/_qp/_dsn` reference anywhere (unlike `_deriv`)
  - `ems_exec/executor/fab_guards.py:54` `_is_time_field`, `:55` `GAPS_KEY` — no `fab_guards.<name>` consumer; docstring at :6 mentions GAPS_KEY conceptually only
  - `ems_exec/derivations/voltage.py:8` `import math` — zero `math.` in file
  - `ems_exec/executor/load_factor_fill.py:218` — local `_toks as _tk` unused (only `_parent_of` used)
  - `ems_exec/renderers/panel_aggregate.py:39` `_agg` — reducers/bindings import `_agg` themselves
  - `grounding/default_assemble.py:34` `default_for`
  - `layer1b/basket/column_basket.py:7` `real_table_cols` (tests import it from `col_dict` directly: `tests/test_layer1b_column_basket.py:4`)
  - `layer1b/compare/resolve_names.py:20` `_discriminators` (detect.py imports from discriminators directly)
  - `layer1b/resolve/asset_resolve.py:19` `as_asset` (consumers import from `asset_candidates`)
  - `layer2/emit/metadata/producer.py:7` `split, DATA_SLOT` (only `path.split(".")` string method used at :92)
  - `validate/build.py:15` `cfg` (no `build.cfg` monkeypatch in tests)
- Also dead locals (ruff F841): `ems_exec/renderers/_story/real_time_monitoring.py:138` `cols`, `grounding/meaningful.py:103` `slots`, `tools/morphmap_live_ab.py:33` `em_a`.
- Refactor: delete the names from the import lines (keep `_deriv`, keep host/server.py:40-41 enrich re-exports — those carry an explicit `noqa: F401  re-exported for tests` and ARE consumed as `S.<name>`/`from host.server import _merge_emit_gaps` in tests).
- Tests guarding: `tests/test_fill_*.py` (8 files) + `tests/test_agentb_fill_fixes.py` + `tests/test_fab_guards.py` (fill/fab_guards); `tests/test_enrich_reason_per_leaf.py`, `tests/test_fe_data_note_serve.py`, `tests/test_window_extraction.py`, `tests/test_render_guarantee_50.py` (host/server); `tests/test_layer1b_column_basket.py`, `tests/test_layer1b_asset_resolve.py` (layer1b); `tests/test_layer2_card.py`, `tests/test_morphmap_producer.py`, `tests/test_stored_skeleton_retire_strip.py` (producer); `tests/test_validate.py`, `tests/test_validate_streamline.py` (validate/build).

### F4. Six ported-but-never-wired backend2-parity derivation functions are unreachable
- Anchor: `ems_exec/derivations/power.py:213` — medium risk (product intent), behavior-preserving today (unreachable)
- The functions (git-blame 2026-07-06/09, i.e. the backend2 parity port, NOT today's WIP):
  - `ems_exec/derivations/power.py:213` `mean_active_power_kw`
  - `ems_exec/derivations/power.py:324` `active_power_loss_kw_gated`
  - `ems_exec/derivations/power.py:334` `active_power_loss_pct_gated`
  - `ems_exec/derivations/energy.py:318` `specific_energy_consumption_ratio` ("Ported from CMD_V2 backend2 feeder_energypower.py _sec_fields :289-304")
  - `ems_exec/derivations/power_quality.py:59` `i_thd_peak_pct`
  - `ems_exec/derivations/topology.py:139` `io_resolution` ("ADDITIVE port of feeder_energypower.py _io_values :237-287")
- Evidence of unreachability: the ONLY dispatch door is the closed dict in `ems_exec/derivations/registry.py` — none of these names appear there; the DB expression path (`derivation_binding.expression`) is evaluated by a closed AST (`ems_exec/derivations/evaluate.py:23` `_FUNCS = {"sqrt","abs","min","max","round"}`) so a DB row cannot name a python fn; no seed .sql/.json/.md references any of the six names (tree-wide grep incl. db/ seeds). The comment at `power.py:323` ("These are NEW fns — the ungated ones keep their signatures for existing callers") shows they were staged for wiring that never landed.
- Refactor: EITHER add registry descriptors (`_d(power.mean_active_power_kw, ...)`) if the parity-port intent stands (AI-first rule: the DB/registry row is the fix, not new per-card code), OR delete the six functions. Decide with the owner — flagging as candidate_only for intent, though unreachability is CONFIRMED.
- Tests guarding: `tests/test_derivation_evaluate.py`, `tests/test_power_plausibility_knobs.py`, `tests/test_energy_from_power.py`, `tests/test_card41_loss_eff_proxy.py` (none reference the six names).

### F5. Ten dead public helpers with zero references anywhere (incl. seeds/JSON/TS — DB-dispatch ruled out)
- Anchor: `grounding/swap_settle.py:75` — low risk, behavior-preserving
  - `grounding/swap_settle.py:75` `swappable_ids` — "Convenience:"; only `swappable_pool` is consumed (`layer2/swap/candidates.py:9`)
  - `layer1b/resolve/has_data.py:86` `meaningful_probe` — "for callers that need the reason"; no caller
  - `layer1b/basket/topology_siblings.py:19` `panel_member_tables` — module alive via `expand_basket_with_siblings` (`layer1b/build.py:10`); this fn has no caller (nb: distinct from live `data/lt_panels/panel_members.py`)
  - `layer2/emit/metadata/split.py:45` `metadata_paths` — "the leaves the byte-identity gate checks"; the gate uses `split()` directly
  - `layer2/emit/data/endpoint_registry.py:27` `is_live` — consumers use the `LIVE_ENDPOINTS` set directly (`layer2/emit/emit.py:139`)
  - `registries/neuract/_db.py:110` `has_column` — `present_columns` is the consumed surface
  - `grounding/schema_fingerprint.py:92` `classify_columns`; `grounding/schema_route.py:61` `table_fingerprint`
  - Introspection quartet, likely REPL debug leftovers: `config/asset_class_defaults.py:121` `all_class_defaults`, `config/metric_class.py:18` `all_page_classes`, `config/nameplates.py:273` `all_nameplates`, `config/viewer_policy.py:82` `all_page_types`
- Refactor: delete (or, for the config quartet, keep ONE documented `python -c` introspection pattern if the team uses them interactively — candidate_only on those four; the first six are CONFIRMED).
- Tests guarding: `tests/test_layer2_swap_gates.py` (swap_settle), `tests/test_has_data_outage.py` (has_data), `tests/test_layer1b_column_basket.py` (basket), `tests/test_residual_layer2_emit.py` (endpoint_registry), `tests/test_layer2_card.py` (split/producer).

### F6. cmd_catalog `endpoint_policy` table is written by its seeder but has NO live reader — dead DB-config surface
- File: `db/seed_schema_and_endpoints.py:9-11` — low risk, behavior-preserving (no reader to affect)
- Evidence: `docs/timeseries_datechange_research.md:67-68` — "`endpoint_policy` has **no live reader** (only `db/seed_schema_and_endpoints.py`), so **`endpoint_registry.py` is the sole lever**". Grep confirms: `endpoint_policy` appears only in the seeder + a style remark in `config/viewer_policy.py:7`; the sibling `schema_slot_map` half of the same seeder IS read (`config/schema_map.py:15-48`).
- Refactor: split the seeder (atomic-structure rule) and retire the `endpoint_policy` half (rename `.retired` like `db/seed_endpoint_resolve_policy.sql.retired`), or wire `layer2/emit/data/consumer_binding/builder.py` to read the table if DB-driven is_history is wanted (DB-first house rule). Fix the stale style remark in viewer_policy.py:7.
- Tests guarding: none reference endpoint_policy.

### F7. v1 prompt-trio remnants: dead `llm.prompt_v2` fixture keys + a seed comment pointing at deleted prompts
- File: `tests/test_morphmap_dp_gate.py:226,252` — low risk, behavior-preserving
- Evidence: `layer2/emit/emit.py:150` — "the retired swap.md + metadata.md + data_instructions.md trio; the llm.prompt_v2 selector + those files are gone". Yet `tests/test_morphmap_dp_gate.py:226` still stubs `{"llm.prompt_v2": ("true", "bool"), ...}` (and :252), and `tests/test_morphmap_producer.py:127` comments "(prompt_v2 stays absent → 'false')". `db/seed_layer2_residual_knobs.sql:5` comment still says "The GENERIC rule lives in layer2/prompts/metadata.md" (file deleted 2026-07-08). `tools/morphmap_ab.py:58`'s check of the "MORPH-EMIT" header is legitimately historical (offline corpus, "all corpus eras") — leave it.
- Refactor: drop the `llm.prompt_v2` keys from the two fixtures; update the two stale comments to `data_instructions_v2.md`.
- Tests guarding: the fixtures ARE the tests (`tests/test_morphmap_dp_gate.py`, `tests/test_morphmap_producer.py`); prompt composition guarded by `tests/test_residual_layer2_emit.py:162`.

### F8. Retired seed file and log artifacts sitting in the live tree
- File: `db/seed_endpoint_resolve_policy.sql.retired:1` — low risk, behavior-preserving
- Evidence: the only `.retired` file outside archive/; plus tracked-dir junk: `err.log` (0 bytes, root), `host/host_restart.log` (217 KB and growing — mtime today), `host/vite_restart.log`, copilot screenshots (`copilot/*.png`, 9 files) + `copilot/copilot_index.sqlite` + `copilot/logs/` inside the package dir.
- Refactor: move `.retired` seed to archive/; point restart logs at outputs/ (or logs/) and gitignore; move copilot PNGs to docs/ or outputs/. Note: `copilot_index.sqlite` is the LIVE retrieval index (`copilot/db.py` reads it) — relocate only with its path config.
- Tests guarding: `copilot/tests/test_no_coupling.py`, `copilot/tests/eval.py` (index path).

---

## Summary counts
- Dead import names: 15 (+3 dead locals) — F3
- Unreachable ported functions: 6 — F4
- Dead public helpers: 10 (6 confirmed, 4 candidate REPL helpers) — F5
- Dead DB-config surface: 1 table (`endpoint_policy`) — F6
- Superseded dir: 1 (`ems_compat/`) — F2
- Stale flags: 0 in code (all 46 suspicious app_config keys resolved to dynamic-prefix readers); 2 dead fixture keys in tests — F7
- Doc rot: README.md 4 dead paths — F1
