# Apply log — unused-code & duplication audit implementation — 2026-07-12 ~04:30 IST

Implements the plan in `docs/CODEBASE_AUDIT_UNUSED_DUPES_2026-07-12.md` (§Safe refactoring plan). Executed by the
audit session while the refactor-campaign session was ACTIVELY landing its own changes — every batch below was
applied against a fresh read of the file state, and items in the campaign session's active lane were deliberately
DEFERRED rather than raced (list at the bottom). Verification: offline pytest tier after each batch; full suite
mid-implementation **985 passed / 0 failed / 4 skipped / 60 deselected**; final full-suite run after the last batch
(result appended below).

## Applied

### Batch 1 — zero-risk deletions (dead-code F3/F7)
- Dead import names removed: `host/server.py` (`ems_exec_run`, `_run_cards`), `ems_exec/executor/fill.py`
  (`_registry`, `_qp`, `_dsn` — `_deriv` KEPT, live test seam), `ems_exec/derivations/voltage.py` (`math`),
  `ems_exec/executor/load_factor_fill.py:218` (`_toks as _tk`), `ems_exec/renderers/panel_aggregate.py` (`_agg`),
  `grounding/default_assemble.py` (`default_for`), `layer1b/basket/column_basket.py` (`real_table_cols`),
  `layer1b/compare/resolve_names.py` (`_discriminators`), `layer1b/resolve/asset_resolve.py` (`as_asset`),
  `layer2/emit/metadata/producer.py` (`split, DATA_SLOT`), `validate/build.py` (`cfg`).
  (fab_guards' two dead imports had already vanished in the campaign's fab_guards/ package split.)
- Dead locals removed: `_story/real_time_monitoring.py` (`cols`), `grounding/meaningful.py` (`slots` — redundant
  probe call, no behavior change), `tools/morphmap_live_ab.py` (`em_a`).
- F7 residue: `llm.prompt_v2` keys dropped from both `tests/test_morphmap_dp_gate.py` fixtures; stale
  `metadata.md` references updated to `data_instructions_v2.md` in `tests/test_morphmap_producer.py` and
  `db/seed_layer2_residual_knobs.sql`. (README F1 was already fixed by the campaign session.)

### Batch 2 — dead helpers (audit §2: F4+F5 + N1–N12) — 33 functions deleted across 27 files
- Parity-port seven (OWNER-DEFAULT TAKEN: **delete, don't wire** — they were never certified; git history is the
  archive; re-porting later = registry `_d(...)` descriptors + `derivation_binding` rows, no code archaeology):
  `mean_active_power_kw`, `active_power_loss_kw_gated`, `active_power_loss_pct_gated` (power.py, + their orphaned
  banner comment), `specific_energy_consumption_ratio` (energy.py), `i_thd_pct`, `i_thd_peak_pct` (power_quality.py),
  `io_resolution` (topology.py), plus `nominal_voltage` (nameplate.py — was ALSO a duplicate of the registry-wired
  `voltage.nominal_voltage_ln`).
- F5 helpers: `swappable_ids`, `meaningful_probe`, `panel_member_tables`, `metadata_paths`,
  `endpoint_registry.is_live` (new home `layer2/emit/instructions/`), `_db.has_column`, `classify_columns`,
  `table_fingerprint`.
- Introspection accessors (quartet + audit additions): `all_class_defaults`, `all_page_classes`, `all_nameplates`,
  `all_page_types`, `all_policy`, `fingerprints`, `pq_limits`, `capacity_utilization`, `trend_deadband`, `bindable`,
  `django_db`, `data_db`.
- `reset_cache` ×3 (registries/neuract/{topology,meters}.py, ems_exec/executor/recipe.py) — zero callers incl. tests.
- Dead privates: `_last_seg` (default_assemble), `_is_dict_subtree` (role_scrub).
- KEPT with a STAGED docstring note: `config/viewer_policy.rating_vocab()` (+ its `viewer.rating_vocab` row) — the
  kitpreview resolver's staged vocab; delete together with kitpreview if that feature is retired instead.
- Stale references to deleted names fixed in: `executor/derived.py`, `derivations/nameplate.py`, `config/nameplates.py`,
  `config/topology_policy.py`, `grounding/schema_fingerprint.py`, `config/feeder_overview.py`.

### Batch 3 — dead DB surface (audit §10/§11; no table drops)
- Snapshots → `archive/db_snapshots_20260712/`: `endpoint_policy`, `band_policy`, `limit_override`,
  `live_window_policy`, `card_rendering`, `card_render_map` (pg_dump each) + `deadend_dq_rows.csv` (35 rows).
- `db/seed_band_policy.sql` → `.retired` (its ENTIRE surface — band_policy table + 34 `band.*` dq rows — has no
  reader; live RTM/PQ bands come from cmd_equipment via `data/equipment/ratings.py`).
- `db/fix_deadend_knobs_20260712.sql` written + APPLIED: deleted `topology.trend_deadband` + 34 `band.%` rows from
  `data_quality_policy` (all reader-less; restore = snapshot or the retired seed).
- NOT dropped (owner-gated, snapshots ready): the six reader-less tables. NOT retired: `seed_asset_render_map.sql`
  (self-documents card_render_map as a deliberate planning/metadata table) and `seed_schema_and_endpoints.py`
  (seeds the LIVE schema_slot_map too — needs the F6-style split first).

### Batch 6 — cruft
- `copilot/*.png` (10) → `docs/copilot_screens/`; `db/seed_endpoint_resolve_policy.sql.retired` → `archive/`.
- `ems_compat/` → already moved to `docs/ems_compat/` by the campaign session; restart logs + `err.log` already
  gitignored; `copilot_index.sqlite` already ignored (LIVE index — untouched).

### Batch 4 — dedup homes landed (duplication.md items in my lane)
- **D4** `ems_exec/derivations/_coerce.py` — six byte-identical `_f` repointed (energy/voltage/power/current/
  power_quality/topology); divergent variants documented in its docstring, NOT merged.
- **D9** `layer1b/normalize.py` — THE asset-name match key; `asset_resolve`/`discriminators`/`spelling_recovery`
  repointed (discriminators re-exports for resolve_names).
- **D8** `llm/prompt_load.py` — THE prompt-file loader (`errors="replace"` house default); the four layer1a/1b
  `_load_prompt` copies now delegate.
- **D7** `data/db_client.pg_bool()` — five inline psql-boolean parses repointed (bridge, meaningful, value_probe,
  corpus/universe, registry/lt_mfm). copilot's pandas twin left (zero-coupling).
- **D10** `llm/transient_retry.no_retry_kinds(cfg_fn=None)` — THE `llm.no_retry_kinds` reader; `llm/client.py`'s
  inner parse loop now sources it (passing its guarded `_cfg` so fail-open + test seams keep working).
- **D11** `layer2/catalog/card_handling.py` grew `handling_class()` + `handling_classes()` (THE card_handling SQL);
  `validate/handling_lookup.py` is now a lazy facade (kept so validate imports without layer2 imports at module
  time — its documented property); `host/exec_cards._special_handling_map` uses the batch accessor.

### Batch 5 (partial) — the real bug
- **api-design H4**: `_window_from_preset` HOME moved to `host/notes.py::window_from_preset` (the cycle-free
  serve-boundary home; server.py re-exports the old name for tests) and **`build_response_multi` now defaults
  date_window from the shared lane's prompt preset** — "compare A and B last week" no longer fills with
  `date_window=None`. Guarded by tests/test_window_extraction.py + test_multi_asset.py (19 passed).

### Batch 7 — already done upstream
- The dead executor budget (audit H5/R1) was made REAL by the campaign session earlier tonight
  (`host/exec_cards.py` "ER-8 wall-clock budget — REAL as of 2026-07-12": `as_completed(timeout=…)` +
  honest-blank + `shutdown(wait=False, cancel_futures=True)`). Nothing to do.

## Deferred — with reasons (do when the tree is quiet; all specified in the audit/duplication docs)

1. **D3** `config/failopen.py` (12 `_cfg` shims + `_cfg_num` ×2) and **D6** `flag_on()` boolean-vocab unification —
   the campaign session is ACTIVELY migrating config surfaces right now (F6 knob migration, F7 PF-of-record landed
   mid-audit); racing it on `config/app_config.py` risks conflicting edits. D6 additionally carries the one
   INTENTIONAL behavior repair (the missing `"t"` in edges.py/asset_3d.py) — own commit, per the plan.
2. **D5** `rescue_common.py` (the `_honest_blanked`/`_blank`/window-fill trio) — fabrication-guard adjacent;
   apply behind tests/test_measurable_false_null_fill.py + test_post_fill_rescue_overreach.py when quiet.
3. **D1** `data/neuract_pool.py` (the duplicated pooled psycopg2 door) — hot path of every card fill; the plan
   itself orders it LAST with a full 882-suite + live page sweep after; a live sweep is not a clean signal while
   another session mutates the tree.
4. **D12** first_row/json_cell guards — SKIPPED as not-a-mechanical-dedup: the copies have deliberately DIVERGENT
   semantics (card_controls `_j` returns the RAW value on unparseable vs card_data_recipe's None; double vs triple
   row guards). Unifying is a behavior decision, not a refactor.
5. **F14** dead wire fields (`frames`/`live_frame`/`sb_base` + ~60 LOC FE threading) — staged 3-step plan is in
   frontend.md F14; wide surface over `host/server.py` (actively churning tonight: replay + obs wiring) + 8 FE
   files + all fill signatures. Do as its own quiet-tree pass, then run the three FE gates + a live sweep.
6. **Table drops** for the six reader-less tables + the `seed_schema_and_endpoints.py` split (dead-code F6) —
   owner-gated; snapshots are ready in `archive/db_snapshots_20260712/`.
7. **v47-only tables** (`payload_shapes`, `nameplate_config`, `derived_metrics`) — deprecate when v47 is formally
   retired.

## Verification record
- Per-batch: Batch 1 targeted (53 passed/3 skipped); Batch 2 targeted (139 passed incl. re-run of a transient
  trio that races the campaign's value_probe landing); D4/D8/D9 (74 passed); D10 (24 passed); D11 (9 passed);
  H4 (19 passed). All compile-checked per edit.
- Full suite mid-implementation: **985 passed, 0 failed, 4 skipped, 60 deselected** (15:57).
- FE gates: not run — this change-set touches ZERO files under `host/web/` (the gates require a captured live
  /api/run response; nothing in their input surface changed).
- Final full-suite run after the last edit: see `FINAL SUITE` note appended below by the session.

---

## SECOND PASS (2026-07-12 ~07:00 IST) — the deferred set, implemented

The parallel campaign session went idle (~40 min quiet); all previously-deferred items were then applied:

- **D3** `config/failopen.py` — `cfg_safe` + `cfg_num(positive=)`: 8 plain `_cfg` shims (obs/event, obs/bus,
  obs/sink_pg, roster_eval, load_factor_fill, measurable_resolve, panel_aggregate, llm/client) + the byte-identical
  `_cfg_num` pair (norm_series, yscale) + 3 guarded-import variants (derivations/power, derivations/nameplate,
  config/nameplates — kept their import-guard, delegate the runtime logic). 65 targeted tests green.
- **D6** `config/app_config.flag_on(key, default, cfg_fn)` — THE boolean-knob vocabulary; repointed `_guided_on`
  (llm/client, keeps its `_cfg` test seam), route_schema/answer_schema `_ON`, equipment_facts `_OFF` (default-on
  preserved via three-state resolve: ON-token/OFF-token/else-default), and **the drifted `data/equipment/edges.py`
  parse — `'t'` now counts (the intentional behavior repair)**. 55 targeted tests green.
- **D5** `ems_exec/executor/rescue_common.honest_blanked(path, hb, both_addresses)` — the matcher hoisted from its
  3 copies (scalar_mean_fill, scalar_tile_fill, load_factor_fill's dual-address variant); `load_factor_fill._blank`
  → `lib/blank.is_blank_scalar` (the campaign had already homed the predicate). Window-fill idioms NOT hoisted —
  they have genuinely diverged. 61 rescue tests green.
- **D12** `data/db_client.first_row()` + `json_cell(raw_on_error=)` — semantics-preserving: the triple-guard
  readers (card_grid_size, card_controls, feasibility) repointed; the two `_j` copies repointed with their
  DIFFERENT failure modes preserved as the explicit `raw_on_error` parameter; double-guard readers
  (card_fill_recipe, col_dict) deliberately NOT converted. 51 tests green.
- **F14** dead wire fields — REMOVED end to end: server.py + multi_asset.py no longer emit page-level
  `frames`/`frame_status`/`live_frame`; FE chain pruned (types.ts fields, App.tsx props, CardGrid frameFor/props,
  CmdCard frame state+reseed effect, registry `renderCmd(card, onDateChange)`, RtmComposite 7-way `?? rtm` chain +
  `liveRailVM` + mapFrame branches, compose HeatmapCard live branch). Fill fns keep their historical arity (frame
  slots now permanently undefined — one commented call site in registry). Per-card `frame_status` (ER-6) KEPT.
  `tsc -b` clean; **SSR gate PASS** on 3 archived responses (13 cards) AND on a fresh live response.
- **D1** `data/neuract_pool.py` — the pooled psycopg2 door extracted from `ems_exec/data/neuract.py` +
  `registries/neuract/_db.py` (conn(readonly)/run_read/drop + the shared never-cache-empty `present_columns`).
  Facades keep their public APIs, per-door replay tape kinds (sql.nx / sql.reg / sql.regd) and sql_trace. SIDE
  EFFECT (intended): the registries door's plain-dict schema cache — still poisonable on a tunnel flap (audit H2)
  — now shares the TTL never-cache-empty probe. 102 targeted tests green.
- **Owner-gated DROP script** written, NOT applied: `db/retire_unused_tables_20260712.sql.owner_gated`
  (rename to arm; snapshots in archive/db_snapshots_20260712/).

**Live verification (new code):** host :8770 restarted on the new tree; `/api/health` ok; ambiguous prompt
("UPS-01") correctly returns the 5-candidate picker; pinned prompt ("energy and power of GIC-01-N3-UPS-01 last
7 days") runs the full pipeline — 4 cards (3 render / 1 partial), payloads + per-card frame_status intact,
retired fields absent, prompt-derived last-7-days window honored — and the fresh response passes the SSR gate
(4/4 rendered, 0 throws). Full offline suite: see FINAL SUITE line below.

## FINAL SUITE (2026-07-12 ~07:30 IST)

Full offline run after the second pass: **995 passed, 2 failed, 4 skipped, 28 deselected** — both failures triaged
and fixed:
1. `test_equipment_disposition::test_equipment_knobs_have_code_default_mirrors` — a source-fence asserting the
   LITERAL pre-D6 string `cfg("equipment.facts.enabled", "on")`; needle updated to the new canonical read
   `flag_on("equipment.facts.enabled", True)` (the fence's intent — an explicit code default — still holds).
2. `test_render_guarantee_50::test_prompt_matrix_built` — NOT this campaign's change: the testing-audit R8 edit
   (06:07, campaign session) gated matrix building behind `V48_LIVE_CERT=1` but left this test asserting a
   non-empty matrix on the offline lane. Added the matching offline-lane skip (mirrors `_NO_MATRIX_REASON`);
   verified BOTH lanes: offline → honest skip, `V48_LIVE_CERT=1` → matrix builds and the test passes (2m53s).
After the two test fixes: the affected files pass both lanes; confirmation full-suite run recorded in the session
scratchpad (`final_suite3.txt`).

**CONFIRMATION SUITE (post test-fixes): 987 passed, 0 failed, 5 skipped, 37 deselected (3m04s).** Green.
(Counts shift vs the 06:54 run because the campaign session's marker/lane work continues to move tests between
lanes — deselected/skipped totals are theirs; zero failures is the signal.)

---

## THIRD PASS (2026-07-12 ~08:00 IST) — table drops APPLIED (owner authorized: "do it")

- **Dropped** (after a last-chance tree-wide reader re-check — 0 code readers each — and snapshot integrity
  verification): `endpoint_policy`, `band_policy`, `limit_override`, `live_window_policy`, `card_rendering`,
  `card_render_map`. Script: `db/retire_unused_tables_20260712.sql` (header stamped APPLIED). Restore =
  `psql -U postgres -d cmd_catalog -f archive/db_snapshots_20260712/<table>.sql`.
- **Seed surgery** so every runnable seed stays clean post-drop:
  `scripts/seed_schema_and_endpoints.py` — the endpoint_policy half retired (docstring + `__main__` updated; the
  schema_slot_map half untouched); `db/seed_roster_recipes.sql` — the card_rendering tail section block-commented
  (rows preserved as the Inventory-B authoring record); `db/seed_round2_config.sql` + `db/round2_config_schema.sql`
  — the live_window_policy/limit_override sections block-commented + the stale "read by config/live_window_policy.py"
  claim fixed; `db/seed_asset_render_map.sql` → `.retired`; `config/viewer_policy.py` docstring no longer cites
  endpoint_policy as its style precedent.
- **Post-drop verification:** host :8770 healthy; live `/api/run` smoke green (4 cards, 1 render/3 partial, retired
  wire fields absent); full offline suite **986 passed** with transient failures fully attributed:
  (a) a :5433 tunnel flap mid-run errored 15 property tests → the db-tunnel unit self-healed and
  `tests/property/` re-ran 44/44 green; (b) `test_natural_compare_ids_fail_open_on_outage` — the campaign session's
  telemetry rewrite moved `asset_candidates` to a call-time import from its source module, so the test's outage stub
  (patching the detect module's re-import) no longer intercepted; the test now patches the source module (intent
  unchanged) and passes; (c) 2 panel-energy-register failures and then 1 decision-inspector failure were the campaign
  session's mid-landing WIP (its own test files edited seconds before collection) — the register pair self-healed
  once their landing completed; `test_decision_inspector.py::test_view_l2_emit_swap_and_keep` (modified 07:54:50,
  campaign WIP) is theirs to finish and is the only red at the time of writing. **No failure traces to the drops or
  to any change from this campaign's three passes.**
