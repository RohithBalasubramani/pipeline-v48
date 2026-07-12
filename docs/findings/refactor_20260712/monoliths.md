# Monolith Decomposition Audit — pipeline_v48 (2026-07-12)

Dimension: **MONOLITH DECOMPOSITION** (atomic-structure rule: one single-purpose file per concern; a layer is a folder of single-purpose pieces).
Scope: the 13 largest py files named by the campaign brief. Skipped: archive/, outputs/, .claude/, node_modules, dist, __pycache__.

Method: full read of each file; import fan-in via grep (DB-driven dispatch respected — string-grep, not import-grep); tests located by grepping tests/ for module + symbol names.

Legend per finding: responsibilities found → separable? → fan-in → split plan → risk / behavior-preserving → guarding tests.

---

## F1 — `ems_exec/executor/fab_guards.py` (972 LOC): five concerns in one file — HIGHEST-VALUE SPLIT

**Responsibilities identified (with line ranges):**
1. **DB-knob accessors + gap helpers** — `_epoch_floor`, `_guard_on`, time-axis token sets, `_reason`, `_add_gap`, `_is_num` (L59–145).
2. **CLASS 1 epoch-millis scan** — `_is_epoch_scalar/_is_epoch_array/_apply_class1` (L147–195).
3. **CLASS 2/3 per-written-field source audit** — `_ROWS_CACHE`, `_table_has_rows`, `_field_leaf_path`, `_field_has_source`, `_apply_class2_class3`, `_blank_numeric_leaf` (L198–343).
4. **CLASS 4 seed-leak + the chrome-vocab family** — `_written_toks/_is_written`, trivial thresholds, `_structural_chrome_keys`, `_chrome_selector_keys`, `_chrome_string_keys`, `_key_words`, `_is_chrome_*`, `_is_config_object_series`, `_data_value_keys`, magnitude-regex machinery, `_apply_class4_seed_leak` (L346–844).
5. **CHROME-RESTORE** — `_scale_selector_keys`, `_chrome_is_blank`, `restore_chrome` (L847–940). This is a *restoration* pass, not a blanking guard, and fill.py invokes it at a **different point in the pass order** than `apply()`:
   - fill.py:526 `_fabg_r.restore_chrome(out, default_payload, written_value_paths)` — EARLY (before view_select)
   - fill.py:592 `_fabg.apply(out, fields, present_cols, asset_table, ...)` — LATE (after every honest fill)
6. **`apply()` entry** (L946–972).

**Evidence of grown-past-structure:** `import re as _re` appears mid-file at L660 while `_key_words` (L514) already uses `_re` — it only works because nothing runs at import time. The chrome vocab (structural/selector/string/scale/data-value key sets) is shared between CLASS 4 and restore_chrome but interleaved with guard logic.

**Separable without behavior change:** yes — every seam is a pure function or a module-global cache; all cfg reads are already deferred inside functions.

**Fan-in:** `ems_exec/executor/fill.py` (two call sites above); `ems_exec/renderers/__init__.py:120` (threads shape_ref); tests import `from ems_exec.executor import fab_guards as G` and touch `G.apply`, `G.restore_chrome`, `G._ROWS_CACHE` (mutated via `.clear()` — survives a re-export by reference).

**Split plan:** convert to a package `ems_exec/executor/fab_guards/` (house style — a folder of single-purpose pieces):
- `knobs.py` — L59–145 (`_epoch_floor`, `_guard_on`, time-axis tokens, `_reason`, `_add_gap`, `_is_num`)
- `chrome_vocab.py` — L411–507 + L510–652 vocab/predicate cluster (`_structural_chrome_keys`, `_chrome_selector_keys`, `_chrome_string_keys`, `_scale_selector_keys` (from L854), `_data_value_keys`, `_key_words`, `_is_chrome_key`, `_is_chrome_leaf`, `_is_chrome_leaf_key`, `_is_data_value_key`, `_is_structural_chrome`)
- `class1_epoch.py` — L147–195
- `class23_source.py` — L198–343 (keeps `_ROWS_CACHE` as its module global)
- `class4_seed.py` — L346–410, 555–844 (seed policing, magnitude regex, `_apply_class4_seed_leak`)
- `restore.py` — L871–940 (`_scale_selector_key`, `_chrome_is_blank`, `restore_chrome`)
- `__init__.py` — `apply()` (L946–972) + explicit re-exports of EVERY current module attribute (`apply`, `restore_chrome`, `_ROWS_CACHE`, `_apply_class1`, `_is_chrome_key`, …) so `from ems_exec.executor import fab_guards as G` sees an identical surface.

**Risk:** low-medium (the `_ROWS_CACHE` re-export must be by-reference — tests and `_table_has_rows` must share the same dict object; keep the dict defined once in `class23_source.py` and re-exported).
**Behavior-preserving:** yes.
**Tests guarding:** `tests/test_fab_guards.py` (~670 lines, incl. wiring tests `test_fill_threads_shape_ref_into_fab_guards_apply`), `tests/test_post_fill_rescue_overreach.py`.

---

## F2 — `layer2/gates.py` (837 LOC): four gates + a shared basket helper in one file

**Responsibilities identified:**
1. **exact_metadata byte-identity gate + enforce + no-default scrub** — `_CHROME`/`_is_chrome`, `gate_exact_metadata`, `enforce_exact_metadata`, `enforce_free_metadata` (L14–113).
2. **HONEST-BLANK wall stack (SEAM 2)** — `_bindable`, `_col_issue`, `_is_series_anchor`, `_blankable_field`, `_reuse_signature`, `_slot_parent_chrome/_slot_parent_unit`, `_snake`, `_quantity_mismatch` (wall iii), `_const_without_source` (iv), `_axis_chrome_const_segs`, `_axis_slot_suffixes`, `_axis_direction_ok`, `_axis_source_mismatch` (iii-b), `_expectation_direct_bind` (iii-c), `_topology_boundary_proxy` (iii-d), `_time_axis_label_bind` (iii-e), `enforce_honest_blank` (the orchestrating pass), `_live_claim_without_source` (iv-b), `_nameplate_missing` (L116–687).
3. **gate_data_instructions** — the fields[] structural gate (L689–774).
4. **gate_roster** — recipe-authoritative roster validation/normalization (L777–837).

**Separable:** yes — the metadata gate and the roster gate share nothing with the wall stack except `_bindable`; every quantity import is already function-local (`from layer2.quantity_class import …` inside each wall).

**Fan-in:** `layer2/build.py:14` (5 names), `layer2/emit/morphmap/producer.py:20` (2 names), `tools/morphmap_ab.py`, `tools/wall_corpus_replay.py:63`. Tests import: `gate_exact_metadata`, `enforce_exact_metadata`, `enforce_free_metadata`, `enforce_honest_blank`, `gate_data_instructions`, `gate_roster`, `_bindable` (test files: 14+).

**Split plan:** package `layer2/gates/`:
- `metadata.py` — L14–113 (chrome markers + the three exact_metadata functions)
- `basket.py` — `_bindable`, `_col_issue`, `_nameplate_missing` (shared by walls + fields gate + roster gate)
- `walls.py` — the per-field wall predicates (L151–507 + `_live_claim_without_source` L650–675): each `(True, reason)` rule is already an independent pure function
- `honest_blank.py` — `enforce_honest_blank` (L510–647), the pass that sequences the walls
- `data_instructions.py` — `gate_data_instructions` (L689–774)
- `roster.py` — `gate_roster` (L777–837)
- `__init__.py` re-exports all seven public names + `_bindable` (test-imported).

**Risk:** low (pure functions; all imports already deferred).
**Behavior-preserving:** yes.
**Tests guarding:** tests/test_layer2_honest_blank_gate.py, test_layer2_gates_ctx_walls.py, test_layer2_quantity_const_gates.py, test_layer2_wall_precision_rework.py, test_layer2_roster.py, test_layer2_card.py, test_layer2_per_leaf_payload_partition.py, test_layer2_empty_roster_honest_blank.py, test_stored_skeleton_retire_strip.py, test_morphmap_producer.py, test_residual2/3_fixes.py, test_validate_streamline.py; plus tools/wall_corpus_replay.py as an offline harness.

---

## F3 — `layer2/build.py` (779 LOC): window-backfill engine + cross-domain honesty + slot reconcile + finalize + run_card control flow

**Responsibilities identified:**
1. **Window-backfill engine** — `_lookback_delta`, `_range_delta`, `_window_anchor`, `_slots_declared_range`, `_calendar_start`, `_backfill_default_window` (L25–223, ~200 LOC of deterministic date math). Consumed once from `_finalize` (L471).
2. **Slot-catalog completeness reconcile** — `_reconcile_slots` (L226–288).
3. **Cross-domain honesty pass** — `_fn_quantity_map`, `_cross_domain_fields`, `_cross_domain_note`, `_blank_cross_domain_leaves` (L291–370).
4. **`_seedfree_default`** (L66–89) — payload selection policy.
5. **`_finalize`** (L373–690) — a 317-line function sequencing ~12 named post-emit passes.
6. **`run_card` + `_finalize_with_gate_retry`** (L693–779) — the fan-out unit + retry policy.

**Separable:** yes — (1)–(3) are self-contained; `_finalize` calls them by name.

**Fan-in:** only `run/layer2_all.py:12` (`run_card`, `_page_card_ids`). Tests import internals directly: `tests/test_layer2_window_label.py:16` `from layer2.build import _backfill_default_window, _range_delta`; `tests/test_residual3_fixes.py` (3 sites). ~10 test files import layer2.build.

**Split plan:**
- `layer2/window_backfill.py` — L25–223 (the whole window engine; it already leans on config/windows.py for presets)
- `layer2/reconcile_slots.py` — L226–288
- `layer2/cross_domain.py` — L291–370
- `layer2/build.py` keeps `_seedfree_default`, `_finalize`, `run_card`, `_finalize_with_gate_retry` and RE-EXPORTS `_backfill_default_window`, `_range_delta` (test-imported) from the new homes.
- Optional second step: `_finalize`'s inline blocks (morph-map branch L387–428, answerability softening L579–626, zero-skeleton L606–625) are candidates for named helpers *within* build.py, not new files — one concern (finalization), just long.

**Risk:** low. **Behavior-preserving:** yes (re-exports keep test imports intact).
**Tests guarding:** tests/test_layer2_window_label.py, tests/test_residual3_fixes.py, tests/test_layer2_card.py + ~10 files importing layer2.build; run/layer2_all is exercised by harness tests (7 files reference run_pipeline).

---

## F4 — `ems_exec/executor/indexed_families.py` (608 LOC): family fill + a SECOND series router + sys.meta_path import-hook monkey-patcher

**Responsibilities identified:**
1. **Per-index family machinery** (the fill.py pre-pass path) — `_split_indexed`, `_scalar_point_slot`, `_binding_for_field`, `_derived_bucket_values`, granularity ladder + chooser, `_family_series(_ts)`, `_bucket_ts`, `_fill_indexed_families`, `is_series_family_field` (L35–318).
2. **POST-FILL series-family router** — `_series_family_groups`, `route_series_families`, `_apply_family`, `_window_for`, `_parse_lookback_days` (L321–500): a second, generic re-detection of the same family shape that OVERWRITES the completed payload.
3. **Import-machinery** — `_install_series_router`, `_ensure_series_router_installed`, `_FILL_CALLER_MODULES`, `_install_import_hook` with two `importlib.abc.MetaPathFinder` classes and a loader wrapper, executed at module import (L503–608). This monkey-patches `fill.fill` via `sys.modules` because "fill.py is fence-frozen" (L503 comment) — but fill.py is demonstrably NOT frozen anymore: fill.py:316 already routes on `is_series_family_field(f)` (the exact fix the wrapper was built to avoid editing in).

**Evidence:** the hook exists solely to avoid one line in fill.py: `_install_import_hook()` at L608 installs global `sys.meta_path` finders that wrap the loaders of 5 hardcoded module names (`_FILL_CALLER_MODULES` L542) plus a poll finder that fires on EVERY import in the process. That is interpreter-global machinery living inside a data-fill module, and its trigger list must be maintained by hand when a new entry module appears.

**Separable:** yes. Two-step plan:
- **Step A (pure decomposition, low risk):** move (2) to `ems_exec/executor/series_router.py` and (3) to `ems_exec/executor/series_router_install.py` (or the bottom of series_router.py); `indexed_families.py` keeps concern (1) and re-exports `route_series_families`/`is_series_family_field` (fill.py:53–56 re-exports from it; wildcards.py:24 and fab_guards.py:253 import `_binding_for_field`; keep it in indexed_families or a `binding_lookup.py` with re-exports).
- **Step B (the real fix, medium risk):** delete the meta_path machinery and wire the router explicitly — add `out = _series_router.route_series_families(out, data_instructions, ctx, default_payload)` as the last pass in `fill.fill()` (identical order to the wrapper: original fill body, then router; guarded by the same `_series_family_groups(...)` check + try/except). The wrapper's `_wrapped.__wrapped__` and `F._series_router_installed` flags disappear; behavior is byte-identical for every payload because the wrapper ran exactly "orig fill then router".

**Fan-in:** fill.py (top-level import + re-exports), wildcards.py, fab_guards.py; the hook itself reaches host/exec entry modules by name.
**Risk:** Step A low; Step B medium (global import-state removal — verify no other code keys off `fill.fill.__wrapped__` or `_series_router_installed`; grep found none outside this file/tests).
**Behavior-preserving:** yes (both steps).
**Tests guarding:** tests/test_indexed_family_derived_sparkline.py, tests/test_page13_dg_cert_defects.py; fill wiring covered by 17 test files importing executor.fill.

---

## F5 — `layer2/quantity_class.py` (791 LOC): the quantity vocabulary is one concern, but the const-source resolver and the rail classifier are riders

**Responsibilities identified:**
1. **Quantity class vocab + classification + compatibility** — unit/name/weak/dimensional/pair maps, `_classify_tokens`, `unit_class`, `name_class`, `slot_class`, `column_class`, `compatible`, `slot_quantity` (L33–490, 659–686). This is the core, ONE concern (mostly data + comments).
2. **Semantic families + source roles for the gates** — `_families_cfg`, `semantic_families`, `semantic_family_mismatch`, `_roles_cfg`, `source_roles`, `source_role_mismatch` (L492–593).
3. **Source-role RAIL CLASSIFIER for ems_exec** — `_role_marker_map`, `source_role_of`, `is_non_output_source` (L596–655) — consumed cross-layer by `ems_exec/executor/measurable_resolve.py` **via getattr** (L238–240 there).
4. **Const-source resolver** — `_CONST_NAMESPACE`, `_const_rows`, `_parse_numeric`, `_norm`, `_num_eq`, `_values_equal`, `numericish`, `_slot_leaf`, `const_source` (L688–792) — a distinct resolver (app_config `consts.*` rows + nameplate map) with exactly one consumer (`gates._const_without_source`).

**Separable:** yes, with a facade. **Split plan:** package `layer2/quantity/` — `classes.py` (1), `families.py` + `source_roles.py` (2+3), `const_source.py` (4) — and keep `layer2/quantity_class.py` as a pure re-export facade (or make `quantity_class` the package `__init__`). The facade is mandatory: measurable_resolve consumes `source_role_of`/`is_non_output_source` via `getattr(_qc, …)`, and gates.py has 7 distinct function-local `from layer2.quantity_class import …` sites.

**Fan-in:** layer2/gates.py (7 import sites), layer2/emit/user_message.py, layer2/emit/slot_catalog.py, ems_exec/executor/measurable_resolve.py (getattr), tools/wall_corpus_replay.py, tools/asset_sweep.py, tools/seed_quantity_vocab.py (the DB-seed tool — reads the code-default mirrors, so moved defaults must stay reachable under the same names).
**Risk:** low-medium (seed tool + getattr consumers pin the public surface; the default dicts are also DB-row mirrors seeded by tools/seed_quantity_vocab.py — keep names identical).
**Behavior-preserving:** yes.
**Tests guarding:** 5 test files grep-match quantity_class (incl. tests/test_layer2_quantity_const_gates.py, test_layer2_wall_precision_rework.py); tools/wall_corpus_replay.py offline harness.

---

## F6 — `ems_exec/executor/fill.py` (663 LOC): the facade is house style, but `fill()` embeds field-routing planning that belongs to the family modules

**Responsibilities identified:**
1. **Facade re-exports** (L42–61) — deliberate, byte-compatible; house style. Fine.
2. **`_honest_blank_paths`** (L69–107) — parsing the AI's declared honest-blank set.
3. **`_windowed_register_delta` + `_field_value`** (L110–207) — the per-field value dispatch.
4. **`fill()`** (L213–663, ~450 LOC): deep-copy + roster seam #1; **inline pre-pass planning** — wildcard split collection, single-index promotion (`_idx_by_key` grouping, L285–298), per-index family grouping + `_homogeneous_series` (L310–332); the scalar loop with 5 inline chrome/time/y-scale guards (L338–430); then 12 sequenced post-fill passes (L437–657).

**The mixed part:** the pre-pass planning (L265–337) is family-shape classification — knowledge that already lives in wildcards.py/indexed_families.py (`_split_wildcard`, `_split_indexed`, `_scalar_point_slot`, `is_series_family_field`) — but the grouping/promotion decisions (solo-index promotion, ≥2-same-key family, metric-homogeneity) are re-derived inline in the orchestrator. The card-58 root-cause history in indexed_families' docstrings shows this split-brain has already caused one live defect (the literal `kind=='bucketed'` gate vs `is_series_family_field`).

**Split plan:** extract `ems_exec/executor/field_routing.py` with one function `plan(fields, out, default_payload) -> (wild_fields, promoted_ids, families)` moving L265–337 verbatim (incl. `_homogeneous_series`); fill() calls it. Optionally also `field_value.py` for L110–207 with fill.py re-exporting `_field_value` (17 test files import executor.fill symbols; the facade contract at L42–61 already promises byte-compatible re-export).
**Constraint:** module path `ems_exec.executor.fill` must NOT change — `gaps.py:106` and `indexed_families.py:509` look it up via `sys.modules.get("ems_exec.executor.fill")` (string-keyed dispatch).
**Risk:** medium (the import-hook in indexed_families wraps `fill.fill`; do this together with F4 Step B or after it).
**Behavior-preserving:** yes.
**Tests guarding:** 17 test files import executor.fill (incl. tests/test_fab_guards.py wiring tests, tests/test_post_fill_rescue_overreach.py, tests/test_indexed_family_derived_sparkline.py).

---

## F7 — `ems_exec/executor/members.py` (442 LOC): panel fan-out + the energy-register pick_mover are two concerns; the single-meter fill path imports the panel module for registers

**Responsibilities identified:**
1. **Member resolution + reads + role selection** — `resolve`, `_meter_row`, `ts_col`, `rows`, `select` (L28–120).
2. **Roll-ups** — `role_filter_for`, `agg_row`, `panel_kwh`, `bucketed_rolled(_members)`, `bucketed_multi`, `_spec_match` (L126–356).
3. **ENERGY-REGISTER pick_mover** — `_delta_of`, `_export_col`, `register_pairs`, `member_delta`, `member_event_count`, `_paired_present`, `_bucketed_energy_delta`, `member_delta_pair` (L180–443 interleaved).

**Evidence of the coupling smell:** the SINGLE-METER executor reaches into the panel-member module purely for registers — `fill.py:122–132`: `from ems_exec.executor import members as _members; pairs = _members.register_pairs(); … _members.member_delta({"table": asset_table}, window, imp, ndigits=1)`. The register-pair map + pick_mover selection is a dataset convention (reversed-CT registers), not a panel-membership concern; `bindings.py:172` consumes it too.

**Split plan:** `ems_exec/executor/energy_registers.py` — move `register_pairs`, `_export_col`, `member_delta`, `member_delta_pair`, `_bucketed_energy_delta`, `_delta_of` (they only need `_nx` + `_agg` + derivations.energy). members.py re-exports all of them (tests/test_agentb_fill_fixes.py calls `M.member_delta`); fill.py/bindings.py can later repoint to the new home.
**Risk:** low. **Behavior-preserving:** yes.
**Tests guarding:** tests/test_agentb_fill_fixes.py (member_delta / pick_mover), 4 test files import executor.members; roster/panel tests exercise agg_row.

---

## F8 — `ems_exec/executor/roster.py` (426 LOC): facade already split (roster_paths/template/eval/modes_*), but the series-LABEL alignment post-pass stayed inline

**Responsibilities identified:**
1. Facade re-exports (L70–83) — house style, fine.
2. Valve + `_rescue_false_nulls` + `prepare_ctx` (L89–196) — activation/preparation, the one member resolution.
3. `run_roster` + `_run_slot` mode dispatch + const-blank guard (L202–296) — the interpreter entry.
4. **Series-LABEL alignment** — `_SERIES_VALUE_LEAF_DEFAULT/_SERIES_LABEL_LEAF_DEFAULT/_LABEL_MATCH_STOP`, `_series_value_leaves`, `_series_label_leaves`, `_label_tokens`, `_leaf_slot_swap`, `_humanize_metric`, `_align_series_labels` (L299–415, ~115 LOC) — a self-contained post-fill correction (c73/c53 swap label-morph gap) with its own DB vocab rows.
5. `_attach_coverage` (L418–426).

**Split plan:** `ems_exec/executor/roster_labels.py` for (4), re-exported from roster.py (matches the existing `roster_modes_*`/`roster_stats` sibling pattern the file's own docstring documents at L50–53). Optionally `roster_prepare.py` for (2) if prepare grows again.
**Fan-in:** fill.py (prepare_ctx + run_roster), renderers/__init__.py.
**Risk:** low. **Behavior-preserving:** yes.
**Tests guarding:** 5 test files reference run_roster/prepare_ctx (incl. roster interpreter tests); label alignment covered under the c73/c53 tests in tests/test_page13_dg_cert_defects.py-family sweeps.

---

## F9 — `layer2/emit/user_message.py` (417 LOC): prompt assembly + an oversize-compaction engine + inline instruction prose

**Responsibilities identified:**
1. Context-line renderers — `_basket_lines`, `_recipe_fields`, `_probable_lines`, `_skeleton_paths`, `_dual_owned_line` (L32–122).
2. **Oversized-prompt compaction engine** — `_compact_arrays`, `_compact_catalog` + the budget rebuild in `build_user` (L125–187) — its own DB-knob family (`emit.prompt_char_budget`, `emit.oversize_*`).
3. **`_build`** (L190–417) — the message assembly, including three ~15-line instruction-prose branches for no-fields classes (L320–362) written as Python string literals.

**Split plan:** `layer2/emit/prompt_compact.py` for (2) (both functions + the budget decision as `maybe_compact(build_fn, card_in)` or keep `build_user` thin in user_message). Secondary (AI-first rule alignment, optional): the L320–362 roster/panel_aggregate/no-fields instruction blocks are per-class *prompt content* living in code — the established pattern for prompt content is prompts/*.md + DB rows; moving them to a `config/gates_vocab`-adjacent DB row (keyed by handling_class, code-default mirror = the current strings byte-identical) removes prose from code without changing output.
**Fan-in:** layer2/emit/emit.py:18 (`build_user`), tools/wall_corpus_replay.py (rebuilds user messages).
**Risk:** low for the compaction split; medium for the prose-to-DB move (byte-identity of prompts matters for cached prefixes — verify with the ab tool).
**Behavior-preserving:** yes (compaction split); yes if the DB default mirrors are byte-identical.
**Tests guarding:** tests/test_emit_prompt_budget.py (the compaction knobs), tests/test_residual_layer2_emit.py, tests/test_morphmap_dp_gate.py, tests/test_equipment_ai_context.py, tests/test_layer2_roster.py, tests/test_stored_skeleton_retire_strip.py.

---

## F10 — `ems_exec/executor/measurable_resolve.py` (410 LOC): column resolver + a SECOND source-role vocabulary + sibling-field resolution

**Responsibilities identified:**
1. Dataset semantic tables + token utils — quantity/stat maps, `_tokens`, `_tokset`, unit vocab, `unit_keys`, `scalar_quantity_words` (L30–122).
2. **SOURCE-ROLE WALL** — `_NONMEASURED_SOURCE_ROLES_DEFAULT`, `_NONDEDICATED_ROLE_MARKERS_DEFAULT`, `_MEASURED_ROLES_DEFAULT`, `_measured_roles`, `_nonmeasured_source_role_markers`, `_nondedicated_role_markers`, `_marker_hit`, `_is_nonmeasured_source_role` (L124–244) — **a second role vocabulary parallel to `layer2/quantity_class._SOURCE_ROLE_MARKERS_DEFAULT`**, reconciled by a 4-step "authority order" (docstring L200–210) with a getattr backstop into quantity_class. The file itself records that this duplication already produced the c59 inputVoltageV false-blank ("they were mis-listed, silently false-blanking every input* leaf" L139–140).
3. Derived-quantity guard + `candidate_columns`/`resolve_column` (L247–344) — the actual resolver.
4. **Sibling-field resolution** — `_STOPWORDS_DEFAULT`, `_stopwords`, `_content_tokens`, `sibling_column_for_scalar` (L347–410) — consumed only by `scalar_mean_fill.py:89`.

**Split plan:**
- `ems_exec/executor/source_role_wall.py` — concern (2), re-exported. Longer-term (medium risk, DB rows involved): collapse the two role vocabularies onto ONE home — quantity_class already declares itself "the ONE source-role vocabulary … hoisted here so there is exactly ONE" (its L286), yet measurable_resolve keeps its own `measurable.nonmeasured_source_roles` rows + code defaults. Consolidation = measurable_resolve consults only `quantity_class.source_role_of` + a `dedicated` flag; the `measurable.*` role rows become aliases (requires a DB-row migration, so flag it rather than bundle it with the mechanical split).
- `ems_exec/executor/sibling_resolve.py` — concern (4), re-exported (scalar_mean_fill repoints or keeps the re-export).
**Fan-in:** roster.py:111 (`resolve_column`), scalar_mean_fill.py (`_quantity_map`, `scalar_quantity_words`, `sibling_column_for_scalar`), scalar_tile_fill.py + load_factor_fill.py (`unit_keys`).
**Risk:** low for the file split; medium for vocab consolidation.
**Behavior-preserving:** yes (split); consolidation needs the corpus-replay harness to prove parity.
**Tests guarding:** tests/test_measurable_false_null_fill.py, tests/test_post_fill_rescue_overreach.py.

---

## F11 — `host/server.py` (367 LOC): the header claims "THIS FILE = the HTTP surface", but two endpoints' business logic lives inside `Handler.do_POST`

**Responsibilities identified:**
1. HTTP plumbing — `Handler._send`, `_Server`, `main` (L195–367 skeleton).
2. `build_response` — the page assembly (L100–178).
3. `_attach_l2_notes`, `_window_from_preset`, `_dump_response` (L50–97, 181–192) — serve-boundary helpers.
4. **`/api/frame` handler body** (L252–294) — ~43 lines of per-card refetch business logic: back-compat request unpacking, the RC2b consumer.range override, special-dispatch class lookup, mfm derivation, display policy + roster_stats pop.
5. **`/api/run` handler body** (L296–343) — knowledge-layer routing, natural-compare promotion, multi/single dispatch.

**Evidence:** header L20–22: "THIS FILE = the HTTP surface (Handler + build_response + the response dump). The serve-boundary seams are atomic host siblings" — yet (4) and (5) are seams that never got their sibling.

**Split plan (matches the existing host/ sibling pattern — enrich/exec_cards/payload_store/assemble/multi_asset):**
- `host/api_frame.py` — `handle_frame(req) -> (status, body)` moving L252–294 verbatim.
- `host/api_run.py` — `handle_run(req) -> (status, body)` moving L296–343 (knowledge routing + natural-compare + multi dispatch); `build_response` can stay in server.py or move with it.
- `Handler.do_POST` becomes parse-body + route to the two handlers.
**Fan-in:** scripts/systemd run `host/server.py` as `__main__`; tests import `build_response`/host.server (6 files) — keep `build_response` importable from `host.server` (re-export if moved).
**Risk:** low. **Behavior-preserving:** yes.
**Tests guarding:** tests/test_multi_asset.py, test_window_extraction.py, test_fe_data_note_serve.py, test_enrich_reason_per_leaf.py, test_render_guarantee_50.py, test_residual2_fixes.py.

---

## F12 — `run/harness.py` (352 LOC): entrypoint orchestration + the reflect/reroute loop + the multi-asset lane runner

**Responsibilities identified:**
1. `_validate` wrapper (L37–47).
2. **Pre-L2 expected-gap re-route** — `_preflight_reroute` (L50–85).
3. **Reflect loop** — `_reflect_loop` (L88–181): the policy knobs, trigger partitioning, fraction gate, re-route + loop2 notes.
4. `run_pipeline` (L184–326) — the orchestration.
5. **`run_pipeline_multi`** (L329–352) — the multi-asset lane runner, consumed only by `host/multi_asset.py:11`.

**Split plan:** `run/reflect_loop.py` for (2)+(3) (run/reflect.py already holds the note-builders — the loop is its natural sibling; both are "the reflect concern" split across files today: notes there, loop here); `run/multi.py` for (5) (or move it into host/multi_asset.py, its only caller — but run/ is the more coherent home since it calls run_pipeline). harness.py keeps run_pipeline + re-exports `run_pipeline_multi` for host/multi_asset and tools.
**Fan-in:** host/server.py:36 (`run_pipeline`), host/multi_asset.py:11 (`run_pipeline_multi`), tools/asset_sweep.py:13.
**Risk:** low. **Behavior-preserving:** yes.
**Tests guarding:** 7 test files reference run.harness/run_pipeline (incl. reflect-policy tests).

---

## F13 — `ems_exec/data/neuract.py` (447 LOC): ONE responsibility — NO split warranted

Audited: connection pool (L21–66), column introspection + logged caches (L72–139), and eight read functions (latest / latest_ts / window / series / bucketed / bucketed_raw_series / edge_count / bucketed_edges / bucketed_delta). Every function is "read one gic_* table by timestamp with honest-degrade" — the module's single stated concern. 29 non-test importers, 14 test files. Splitting this into read-shape-per-file would fragment a cohesive data door for no gain; the brief's rule "a long file with ONE responsibility is fine" applies.

*(Out-of-dimension observation, flagged for the correctness auditor: `_LOGGED_CACHE` at L25 caches `column_logged`'s `False` verdict permanently per process, and `_run` returns `[]` on a dead connection — so a :5433 tunnel flap can poison `(table,col)->False` for the process lifetime, the same cache-poison class as the 2026-07-09 panel_members fix that introduced `data/ttl_cache.py` + never-cache-empty. Not a decomposition issue; no split proposed.)*

---

## Cross-cutting notes

- **Re-export facades are the load-bearing mechanism** for every split above: fill.py, roster.py already model it ("re-exported here byte-compatibly (THIS module stays the one import target)"). Every proposed package keeps the original module path importable with an identical attribute surface, because (a) tests import underscore-private helpers directly, (b) two modules dispatch on the literal string `"ems_exec.executor.fill"` via sys.modules, (c) measurable_resolve consumes quantity_class via getattr.
- **Ordering:** F4 Step B (delete the import hook) should land before or with F6 (fill.py routing extraction) — the hook wraps `fill.fill`, so editing fill's body while the hook exists is safe (the wrapper delegates), but removing ambiguity first is cheaper.
- **Do not split:** neuract.py (F13), the roster_modes_* siblings, wildcards.py, and the small executor passes — already atomic.
