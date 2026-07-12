# Duplication audit — pipeline_v48 (2026-07-12)

Dimension: DUPLICATION (copy-paste / near-duplicate logic clusters) for the behavior-preserving refactor campaign.
House rules respected: atomic single-purpose files, AI-first minimal code, per-leaf degradation, DB-driven config,
DB-driven dispatch (grepped for string references, not just imports, before every claim).

Skipped per instructions: archive/, outputs/, .claude/, .playwright-mcp/, __pycache__, node_modules, dist.

Findings ordered by signal strength. Each cluster names ALL copies + one proposed shared home.

---

## D1. Pooled psycopg2 neuract connection door duplicated wholesale — HIGH

**Copies**
- `ems_exec/data/neuract.py:22-70` — `_LOCK/_POOL/_COLS_CACHE`, `_key()` (:28), `_conn()` (:33), `_run()` (:50)
- `registries/neuract/_db.py:19-85` — `_LOCK/_POOL/_COLS_CACHE`, `_key()` (:24), `_conn()` (:29), `rows()` (:48)

`_key()`/`_conn()` are byte-identical except one extra `c.set_session(readonly=True)` in the registries copy; `_run()`
vs `rows()` are the same function (execute → fetchall → on error `_POOL.pop(_key())`, return `[]`). Both carry the
identical docstring sentence "A live psycopg2 connection to neuract from the pool (reconnect if the pooled one died).
None on any failure." Additionally `present_columns(table)` (information_schema probe + `_COLS_CACHE`) is duplicated
near-verbatim: `ems_exec/data/neuract.py:72-87` vs `registries/neuract/_db.py:93-107`.

**Why it matters**: connection-lifecycle fixes (the member-cache-poison / :5433 tunnel-flap class, connect timeouts,
keepalives) must now land twice or the two doors drift silently.

**Proposed home**: new single-purpose `data/neuract_pool.py` (atomic rule satisfied: one concern = the pooled neuract
connection + run-read + present-columns cache), exporting `conn(readonly=False)`, `run(sql, params)`,
`present_columns(table)`. `ems_exec/data/neuract.py` (time-series facade) and `registries/neuract/_db.py` (metadata
facade) keep their public APIs and import the pool; the readonly difference becomes the kwarg.

**Risk**: medium (hot path of every card fill). Behavior-preserving: yes (pure extraction).
**Tests guarding**: tests/test_equipment_ai_context.py, tests/test_equipment_topology.py, tests/test_fab_guards.py,
tests/test_measurable_false_null_fill.py, tests/test_fill_reason_not_logged.py (importers of both doors).

---

## D2. `data_quality_policy` reader boilerplate re-implemented per config module (+ `_esc` ×13) — HIGH

**Copies (same table `cmd_catalog.data_quality_policy`, same accessor shape, different namespace + defaults dict)**
- `config/quality_policy.py:10-37` — `num`, `txt`, `all_policy`, `_esc`
- `config/energy_balance_policy.py:39-76` — `num`, `txt`, `_q`, `_esc`
- `config/feeder_overview.py:26-52` — `num`, `_q`, `_esc` (docstring: "Mirrors config/quality_policy.py num()")
- `config/topology_policy.py:17` — `_num` reader on the `topology.` namespace
- `config/rating_knobs.py`, `config/nameplate_slot_map.py` — same-table readers
- `config/event_thresholds.py:53,122` — same `_esc` + fail-open row-read mechanics (own table)

**`_esc` (`str(s).replace("'", "''")`) defined 13× in config/** — asset_class_defaults.py:138,
derivation_binding.py:75, energy_balance_policy.py:75, event_thresholds.py:122, feeder_overview.py:51,
metric_class.py:27, nameplates.py:285, quality_policy.py:36, reason_templates.py:53, schema_map.py:52,
viewer_policy.py:109 — plus `ems_exec/derivations/expressions.py:14`.

**Proposed home**: the per-namespace files STAY (feeder_overview.py's own docstring cites the atomic rule for having
its own file; the code-default dicts are the per-concern content). Extract only the mechanics into ONE single-purpose
`config/policy_read.py`: `esc(s)`, `policy_num(key, fallback)`, `policy_txt(key, fallback)` (fail-open, never raises,
never blocks import). Each namespace module keeps its public `num()/txt()` as a one-line delegate over its defaults.

**Risk**: low. Behavior-preserving: yes (identical SQL + fallback semantics, public APIs unchanged).
**Tests guarding**: tests/test_power_plausibility_knobs.py, tests/test_card41_loss_eff_proxy.py,
tests/test_panel_energy_register.py, tests/test_page13_dg_cert_defects.py.

---

## D3. Fail-open `_cfg(key, default)` shim ×12 + byte-identical `_cfg_num` ×2 — HIGH

**Copies of the try-import-cfg-except-default shim (same 4-6 lines)**
- obs/event.py:17, obs/bus.py:10, obs/sink_pg.py:22
- config/nameplates.py:24 (guarded-import variant)
- ems_exec/executor/roster_eval.py:13, ems_exec/executor/load_factor_fill.py:39,
  ems_exec/executor/measurable_resolve.py:30
- ems_exec/derivations/power.py:10, ems_exec/derivations/nameplate.py:17 (guarded-import variants)
- ems_exec/renderers/_insight.py:36, ems_exec/renderers/panel_aggregate.py:44
- llm/client.py:51

**Byte-identical `_cfg_num(key, default, positive=False)`** (float + clamp + fail-open):
- ems_exec/executor/norm_series.py:49 and ems_exec/executor/yscale.py:40 — same body, same docstring.

Related: `ems_exec/derivations/power.py:48-100` carries four near-identical knob getters
(`_lf_energized_fraction/_lf_ceiling_pct/_lf_ceiling_tolerance_pct/_loading_plausible_max_pct`) that are each
"float(cfg(key, default)) → clamp → default" — exactly what a shared `cfg_num` with min/max bounds expresses.

**Proposed home**: one single-purpose `config/failopen.py` with `cfg_safe(key, default)` and
`cfg_num(key, default, positive=False, lo=None, hi=None)` — the import of `config.app_config` stays INSIDE the
function so the module itself never fails to import (preserving the guarded-import property every copy exists for).
This is the established DB-driven-config pattern (house rule 4) with the fail-open half deduplicated.

**Risk**: low. Behavior-preserving: yes (each call site keeps its default; clamping variants pass their own bounds).
**Tests guarding**: tests/test_power_plausibility_knobs.py, tests/test_yscale_derivation.py,
tests/test_residual3_fixes.py, tests/test_fill_hook_order.py.

---

## D4. Float-coercion helper `_f`/`_num` — 6 identical copies in derivations, ~8 more variants tree-wide — HIGH

**Byte-identical `_f(x)` (float-or-None) in ems_exec/derivations/**: energy.py:11, voltage.py:11, power.py:14,
current.py:9, power_quality.py:10, topology.py:121.

**Same-semantics `_num` variants elsewhere** (float-or-None, some adding the psql "NULL" sentinel):
grounding/meaningful.py:36, ems_exec/data/neuract.py:123, data/equipment/ratings.py:44,
ems_exec/derivations/breaker.py:40. **Divergent semantics that must NOT be merged** (drift hazard worth documenting
at the shared home): registries/neuract/nameplate.py:25 returns the ORIGINAL value on coercion failure;
config/nameplates.py:104 RAISES on non-numeric text; ems_exec/renderers/_agg.py:24 `num()` is finite-only
(NaN/inf → None, "Mirrors topology_sld._num"); ems_exec/executor/trend_badge.py:43 is an is-number predicate;
ems_exec/derivations/evaluate.py:43 raises `_Degrade`.

**Proposed home**: `ems_exec/derivations/_coerce.py` with `f(x)` (float-or-None) for the six identical derivation
copies (keeps the derivations' documented "pure fns, no DB" property — the module imports nothing). Do NOT collapse
the divergent variants; instead note each divergence in the shared module's docstring so future readers stop assuming
they are interchangeable. `_agg.num` stays the finite-only home for executor/renderer paths (already reused by
reducers.py and members.py).

**Risk**: low. Behavior-preserving: yes (only identical copies repointed).
**Tests guarding**: tests/test_energy_from_power.py, tests/test_power_plausibility_knobs.py,
tests/test_card41_loss_eff_proxy.py.

---

## D5. Post-fill rescue trio: `_honest_blanked` ×3, `_blank` ×2(+4 variants), window-mean fill idiom ×2 — HIGH

**`_honest_blanked(path, hb)` (tokens-tuple + `[*]` wildcard matcher against fill.py's honest-blank set)**
- ems_exec/executor/scalar_mean_fill.py:28-41
- ems_exec/executor/scalar_tile_fill.py:175-190 (adds one `if not toks` guard)
- ems_exec/executor/load_factor_fill.py:321-336 `_honest_blanked_lf` (same matcher, additionally tries the
  `data.<slot>` address form — the other two get that form pre-normalized by the caller)

**`_blank(v)`** — identical `None/'—'/''` in scalar_mean_fill.py:24 and load_factor_fill.py:71; the `+ []` variant in
roster_stats.py:180 and roster_gaps.py:38; the DASH-constant variant in trend_badge.py:39 and freshness.py:49.

**Window-reduce fill idiom** (bucketed → non-null values → stat → `_verify(_agg.num(raw), quantity)` → `round(...,1)`)
- scalar_mean_fill.py:94-107 (`_try_fill`)
- scalar_tile_fill.py:129-137 (`_try_tile` mean branch)

These three files are sibling rescues consuming the SAME `fill._honest_blank_paths` contract (DEFECT 56); a matcher
fix (e.g. a new wildcard form) currently must land 3×.

**Proposed home**: one single-purpose `ems_exec/executor/rescue_common.py`: `is_blank(v)`,
`honest_blanked(path, hb, both_addresses=False)`, `window_stat(asset_table, col, window, stat, quantity)` (the
bucketed→verify→round read). The rescue files keep their distinct trigger logic (stat+quantity key vs label-keyed tile
vs load-factor derivation), which is the real per-concern content.

**Risk**: medium (fabrication-guard adjacent; the honest-blank matcher is a certified behavior). Behavior-preserving:
yes if `both_addresses` preserves load_factor_fill's dual-form probe exactly.
**Tests guarding**: tests/test_measurable_false_null_fill.py, tests/test_post_fill_rescue_overreach.py,
tests/test_page13_dg_cert_defects.py.

---

## D6. Boolean-flag parsing vocabulary DRIFTED across inline copies — MEDIUM (latent behavior divergence)

Canonical truthy set is `config/app_config.py:34` `_cast('bool')`: `("1","true","yes","t","on")`.

**Copies**
- llm/client.py:100 `_guided_on` — full set (comment: "Truthy set mirrors app_config _cast")
- layer1a/route_schema.py:31 and layer1b/resolve/answer_schema.py:33 — `_ON = ("1","true","yes","t","on")`
  (comment: "same truthy vocabulary as config/app_config.py _cast('bool')")
- data/equipment/edges.py:42 — `("1","true","yes","on")` — **MISSING "t"**
- layer2/emit/metadata/asset_3d.py:146 — `("on","true","1","yes")` — **MISSING "t"**
- layer2/emit/equipment_facts.py:17 — inverse set `_OFF = ("off","","0","false","no","none")` (different semantics:
  default-on)

A DB operator writing `t` (the natural psql boolean literal) flips `llm.guided_json.*` on but leaves
`equipment.topology.enabled` / `equipment.kitpreview.enabled` off — an invisible config foot-gun.

**Proposed home**: `flag_on(key, default)` in `config/app_config.py` (bool-casts the row regardless of its declared
data_type, using the one `_cast` vocabulary); repoint the five copies. equipment_facts keeps its default-on semantics
via `flag_on("equipment.facts.enabled", True)`.

**Risk**: low-medium — this is technically behavior-CHANGING for edges.py/asset_3d.py on the input "t"/"T" (currently
falsy there). That change is the point (drift repair); flag it in the campaign notes as an intentional unification.
**Tests guarding**: tests/test_equipment_topology.py, tests/test_asset3d_dg_seed.py, tests/test_item17_guided_json.py,
tests/test_route_guided_json.py.

---

## D7. psql boolean-cell parse `("t","true","1")` ×5 — MEDIUM

**Copies** (parsing a psql CSV boolean cell): data/equipment/bridge.py:208, grounding/meaningful.py:216,
layer1b/resolve/has_data.py:109, validation/corpus/universe.py:45, data/registry/lt_mfm.py:50.
(copilot/has_data.py:27 has a pandas twin but copilot is deliberately zero-coupled — leave it.)

**Proposed home**: `pg_bool(v)` in `data/db_client.py` (the module that owns the psql-CSV cell format).

**Risk**: low. Behavior-preserving: yes.
**Tests guarding**: tests/test_equipment_disposition.py (bridge), tests/test_layer1b_basket_logged_floor.py (has_data),
grep tests/ for `lt_mfm`.

---

## D8. `_load_prompt` ×4 across layer1a/layer1b — MEDIUM

**Copies (byte-identical: open `<layer>/prompts/<name>` and read)**
- layer1a/route.py:29, layer1a/story_builder.py:11, layer1b/basket/column_basket.py:30,
  layer1b/resolve/asset_resolve.py:35
(layer2/emit/emit.py:163 and knowledge/ems.py:46 inline the same idiom with `errors="replace"` — a robustness
divergence the shared helper should standardize: only the layer2 copy survives a stray non-UTF-8 byte in a prompt
file today.)

**Proposed home**: single-purpose `llm/prompt_load.py` — `load(base_dir, name, errors="replace")`. Callers pass their
own prompts dir (per-layer prompt folders stay where they are — the atomic structure is the folders, not the loader).

**Risk**: low. Behavior-preserving: yes (adopting `errors="replace"` everywhere is a strict robustness widening; if
byte-identity is preferred, default `errors=None` and let layer2 pass its own).
**Tests guarding**: tests/test_layer1b_asset_resolve.py, tests/test_emit_prompt_budget.py, tests/test_layer2_card.py.

---

## D9. `_norm` name-normalizer ×3 identical inside layer1b — MEDIUM

**Copies (byte-identical incl. docstring: `re.sub(r"[^a-z0-9]+", "", str(s).lower())`)**
- layer1b/resolve/asset_resolve.py:40, layer1b/compare/discriminators.py:11,
  layer1b/guardrail/spelling_recovery.py:13

This is the asset-name match key ("PCC Panel 2 A" == "pcc-panel-2a"); three copies means a future normalization tweak
(e.g. unicode dashes) can desynchronize resolve vs compare vs spelling-recovery — the exact class of bug the
full-name collision gate fixes guarded against.

**Proposed home**: `layer1b/normalize.py` (one concern: the asset-name match key). NOT merged with
layer2/coherence.py:43's `_norm` (whitespace-collapse — different semantics) or executor slugify.

**Risk**: low. Behavior-preserving: yes.
**Tests guarding**: tests/test_layer1b_asset_resolve.py, grep tests/ for `spelling_recovery`, `discriminators`.

---

## D10. `llm.no_retry_kinds` row parse duplicated client-side and emit-side — LOW/MEDIUM

**Copies (same cfg row, same comprehension)**
- llm/client.py:145 `no_retry = {k.strip() for k in str(_cfg("llm.no_retry_kinds", "timeout,truncated") or "").split(",") if k.strip()}`
- layer2/emit/emit.py:214 (same line against `cfg`)

Both sites even cross-reference each other in comments ("the SAME row layer2/emit/emit.py honors"). The shared default
`"timeout,truncated"` is stated 4× across the two files.

**Proposed home**: `no_retry_kinds()` exported from `llm/client.py` (it owns the row); emit.py imports it. While
there, note the three retry conventions around call_qwen — llm/client parse-retry, layer1b/guardrail/retry_one.py
falsy-retry, layer2/emit/emit.py marker-retry — are intentionally different semantics (keep them), but they should all
source deterministic-failure kinds from this one accessor.

**Risk**: low. Behavior-preserving: yes.
**Tests guarding**: tests/test_llm_truncation_budget.py, tests/test_emit_prompt_budget.py.

---

## D11. `card_handling` read tripled — LOW/MEDIUM

**Copies**
- layer2/catalog/card_handling.py:5-14 `read(card_id)` — full row, raises with q()
- validate/handling_lookup.py:10-15 `handling_class_for(card_id)` — one column, fail-open
- host/exec_cards.py:81 — inline batch `SELECT card_id, handling_class FROM card_handling WHERE card_id IN (...)`

**Proposed home**: `layer2/catalog/card_handling.py` grows `handling_class(card_id)` (fail-open) and
`handling_classes(card_ids)` (batch); validate/handling_lookup.py becomes a shim or is deleted after repointing
(grep first: only validate/payload_validate.py imports it), host/exec_cards.py imports the batch accessor.

**Risk**: low. Behavior-preserving: yes (fail-open modes preserved per caller).
**Tests guarding**: grep tests/ for `handling_lookup` (tests/test_payload_validate*.py), tests/test_display_dash.py.

---

## D12. psql row-guard + JSON-cell-guard idioms across catalog readers — LOW

- `if not r or not r[0] or not r[0][0]` — 7 files: layer2/catalog/{card_controls,card_handling,feasibility,
  card_data_recipe,card_fill_recipe,card_grid_size}.py, layer1b/basket/col_dict.py.
- JSON-guard `_j(v)` (json.loads-or-passthrough): layer2/catalog/card_data_recipe.py:8,
  layer2/catalog/card_controls.py:7, obs/sink_pg.py:111, data/equipment/kitpreview.py:145 (`_json`),
  copilot/build/parsing.py:18 (copilot: leave).

The per-table reader FILES are correct house style (one concern per catalog table); only the mechanical guards repeat.

**Proposed home**: `data/db_client.py` gains `first_row(db, sql)` (returns the row or None under the exact triple
guard) and `json_cell(v)`. Each catalog reader keeps its SELECT + dict-shaping.

**Risk**: low. Behavior-preserving: yes.
**Tests guarding**: tests/test_layer2_card.py, tests/test_layer2_slot_catalog_series.py, grep tests/ for `col_dict`.

---

## Verified NON-duplicates (negative findings, so the campaign doesn't chase them)

- **ems_exec/derivations/power.py (345 LOC) vs energy.py (343 LOC)** — the size match is coincidence. Audited both
  end-to-end: zero shared logic beyond the 5-line `_f` helper (see D4) and the deliberate cross-reference where
  energy's `_pick_register` is reused (imported, not copied) by panel_aggregate. Power = load-factor/peak/loss
  identities; energy = register deltas/integration. Do not merge (would violate the atomic rule).
- **copilot/llm.py + copilot/db.py vs llm/client.py + data/db_client.py** — near-duplicate call/psql idioms, but the
  copilot docstrings declare the decoupling deliberate ("zero code-edge into L1/L2/L3", own :8201 endpoint). Leave.
- **services/dict_merge.py vs ems_backend/lt_panels/services/dict_merge.py** — documented deliberate twin (importable
  without the Django chain). Leave.
- **validate/ vs grounding/** — no copy-paste found: grounding = pre-emit deterministic grounding (meaningful-data,
  schema routing, default assembly), validate = pre-L2 data probe + post-fill render verdict. The conceptual
  "does this table/column carry data" question appears in 4 places (layer1b/resolve/has_data.py,
  ems_exec/data/neuract.column_logged, grounding/meaningful.py, validate/null_gate.py) but each has distinct,
  documented semantics (row-existence / column non-null / threshold-meaningful / null-rate policy) and different DB
  doors; unifying them would be a semantic change, not a refactor.
- **tools/ + scripts/ vs run/** — tools (asset_sweep, wall_corpus_replay) import run.harness.run_pipeline /
  layer2.gates rather than re-implementing them; cert_fire18.sh / campaign_fire_extras.sh are black-box HTTP
  harnesses. No pipeline-logic duplication found. (tools/replay_item17_guided_asset_resolve.py:42-43 does re-inline
  llm/client's think-strip + first-JSON-blob extraction — acceptable for a replay tool, but if D10's accessor work
  happens, exporting `extract_json(text)` from llm/client would remove it too.)
- **layer2/emit/morphmap/producer.py vs layer2/emit/metadata/producer.py** — explicitly composed ("IMPORTED, never
  copied"); the two contracts share the gate machinery already.
- **run/parallel.py vs host/exec_cards.py:147-175 thread pools** — exec_cards needs deadline + as_completed semantics
  run_parallel lacks; unifying would change timeout behavior. Left as-is (documented).

---

## Suggested execution order (lowest risk → highest leverage)

1. D2 (`config/policy_read.py` + esc), D3 (`config/failopen.py`), D4 (`derivations/_coerce.py`) — mechanical,
   test-green trivially.
2. D7 (pg_bool), D8, D9, D10, D11, D12 — small single-file homes, few call sites each.
3. D5 (`rescue_common.py`) — behind the rescue tests; verify DEFECT-56 cases stay green.
4. D6 flag unification — includes the one intentional behavior repair (missing "t"); do it as its own commit with
   the drift called out.
5. D1 (`data/neuract_pool.py`) — last; hot path, run the 882-test suite + a live page sweep after.
