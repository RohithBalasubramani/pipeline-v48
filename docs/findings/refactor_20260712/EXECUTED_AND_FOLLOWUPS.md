# Refactor campaign 2026-07-12 — what was EXECUTED and what remains (follow-ups)

Behavior-preserving architecture cleanup driven by the 9-dimension audit in this folder. Every change gated on
targeted pytest runs (see per-batch notes); a final full-suite run closes the campaign. A CONCURRENT session was
building obs-trace/replay/profiler/validation/admin the same day — items touching its in-flight areas were
deliberately deferred (marked ⏸).

## Executed

### Docs / cruft (Batch 0)
- 10 skip-only placeholder test files deleted (incl. 2 named after the retired workers/ subsystem).
- Root plan/spec docs → docs/ (`MULTI_ASSET_PLAN.md`, `V48_L3_REWORK_SPEC.md` +SUPERSEDED banner, `V48_FULL_WALKTHROUGH_2026-07-02.md`); `ems_compat/` → `docs/ems_compat/`.
- `contracts/` (10 empty stub schemas, zero loaders) → archived; real contract home = per-layer schema.py.
- Deleted: `err.log`, `host/*.log`, `App.tsx.tmp.*` (tracked editor crash file), untracked `tsconfig.tsbuildinfo`;
  `.gitignore` += `*.tsbuildinfo`, `*.tmp.*`, `host/outputs/`.
- README.md rewritten against the real tree (workers/frames/db_build claims were 10 days stale); host/README.md
  "Layer 2 not built yet" fixed; registry.tsx tier-order header now matches the real dispatch order; stale
  "BEFORE Layer 3" comment fixed in run/layer2_all.py.

### Config hygiene (Batch 2)
- `config/app_config.py`: imports now lazy inside `_load()` → `from config.app_config import cfg` can never fail at
  import (the ~67 defensive try/except wrappers tree-wide are now provably no-ops; delete opportunistically).
- Import-time cfg() freezes converted to lazy PEP-562 module attributes: `config/{windows,metrics,swap,intents,feasibility}.py`;
  `layer2/gates` chrome vocab; `host/exec_cards._exec_budget_s()`; fab_guards magnitude regex (vocab-keyed cache).
  `layer2/swap/gate_force_renderable.py` reads the feasibility knobs per call.
- `config/policy_read.py` NEW — the ONE data_quality_policy reader (esc + fail-open num/txt); rewired
  energy_balance_policy, feeder_overview, and the 11 duplicated `_esc` clones across config/.
- DB knob drift fixed (db/fix_orphan_knobs_20260712.sql, APPLIED): 4 orphan rows deleted (`llm.prompt_v2`,
  `flags.*`×3), `ems_backend.frame_budget_s` → `ems_exec.card_budget_s` (reader-verified).
- Endpoint hygiene: `llm/config.py` env names now `V48_LLM_URL`/`V48_LLM_MODEL` (legacy fallback);
  `_insight._env()` no longer hijacks generic `LLM_URL`/`TIMEOUT`/... env names (namespaced EMS_INSIGHT_* only);
  `obs/ai_log.py` match token derives from the configured LLM endpoint port (was a hard `:8200`);
  `host/server.py` STORYBOOK_URL falls back to a `host.storybook_url` cfg row.
- `config/ems_backend.py` slimmed: the 4 WS-fetch knobs + ws_url served the retired workers/ path (zero consumers).
- Hardcoding lifts: topology loss band + IEEE-519 I-THD limit + statutory band % + voltage-domain chart pads +
  story sev-warn fraction now read their DB rows; story plausibility ceiling unified on `power.loading_plausible_max_pct`.

### Dedup (Batch 3)
- `ems_exec/executor/blank.py` NEW — the ONE blank-leaf predicate + DASH sentinel; rewired gaps/roster_gaps/roster/
  scalar_mean_fill/render_verdict (each keeps its intentional list-extension).
- `llm/transient_retry.py` NEW — the ONE bounded retry policy (transient-only; deterministic timeout/truncated fail
  fast per the no-retry rule). Adopted by layer2/emit AND layer1b (asset_resolve, column_basket, now marker-mode);
  `layer1b/guardrail/retry_one.py` DELETED (it blindly re-sent deterministic failures — doubled hangs).
  Tests updated to the marker contract (+ a new fail-fast case).
- `ems_exec/executor/epoch.py` NEW — shared epoch-magnitude heuristic for yscale/xaxis (`chart.epoch_list_floor` knob);
  the 1e10-vs-1e12 (fab_guards) discrepancy is documented there for an owner call.

### Monolith splits (Batch 4) — re-export facades keep every import path byte-compatible
- `layer2/build.py` 818→502 lines: window engine → `layer2/window_backfill.py`; completeness reconcile →
  `layer2/reconcile_slots.py`; cross-domain honesty → `layer2/cross_domain.py`.
- `layer2/gates.py` (841) → package `layer2/gates/` {metadata, basket, walls, honest_blank, data_instructions, roster}.
- `ems_exec/executor/fab_guards.py` (972) → package `fab_guards/` {knobs, class1_epoch, class23_source (owns
  _ROWS_CACHE — same dict object re-exported), class4_seed, restore, apply}.
- SKIPPED deliberately: host/server.py split (the concurrent session already extracted handle_frame/handle_run and
  is actively wiring trace/replay there); run/harness.py reflect-loop split (reflect tests monkeypatch harness.*
  globals — the move would churn 6+ test sites for little gain).

### Typing / constants (Batch 5)
- `layer1b/how.py` NEW — the ONE `how` vocabulary (+RESOLVED_WITH_DATA/RESOLVED_ANY); rewired schema.py,
  compare/resolve_names.py, run/harness.py.
- member_scope literals rewired to the declared `OUTGOING`/`INCOMER` constants (host/enrich, host/exec_cards,
  layer2/emit/panel_members_block, ems_exec/executor/members).

### Structure moves (Batch 1)
- `partition/` → `layer1a/partition/` (was a root package depending on layer1a internals).
- `layer2/emit/data/` → `layer2/emit/instructions/` (it authors data_instructions; third distinct meaning of "data").
- `services/dict_merge.py` → `lib/dict_merge.py`; `services/` deleted.
- `db/seed_schema_and_endpoints.py` + `tools/seed_quantity_vocab.py` → `scripts/` (DB-writing one-offs);
  `tools/tunnel_monitor.py` → `ops/` (pairs with ops/db-tunnel.service).
- copilot FORBIDDEN no-coupling list refreshed (retired names kept defensively; grounding/ems_exec/registries added).

### Frontend (Batch 6) — gated on `tsc -b` + `vite build` (green)
- FIXED pre-existing build break: card-47 placeholder missing the new required `PowerQualitySnapshot.loadImpactWatch`
  (IEEE defaults via PQ_LIMITS, mirroring CMD_V2's own placeholder).
- `types.ts`: PipelineResult extended with the served-but-untyped fields (kind/answer/refused/asset_pending/
  asset_no_data/validation_blocked/data_unavailable/degrade/notes) + GapRecord/RenderVerdict.gaps + OnDateChange;
  ALL 14 `(result as any)` casts in App.tsx and the 3 in CmdCard deleted; renderCmd's card param is now `Card`.
- NEW shared: `components/icons.tsx` (Spark/Return/Mag/XIcon/Ban/Minus — 3 drifting copies),
  `components/ErrorBoundary.tsx` (one class, fallback render-prop; app root / CmdCard / RtmComposite rewired),
  `components/HonestBlankTile.tsx` (the one honest-blank markup; registry + CmdCard branches rewired),
  `hooks/useSiteStatus.ts` (the one /api/site poll loop; CommandHeader 15s + DataUnavailable 12s),
  `api.ts` now owns ALL endpoints (fetchSite/fetchAssets/copilotSuggest/copilotStarters typed).
- `cmd/fill/shared/` NEW: `sampling-window.ts` (the byte-identical feeder/DG date-wiring pair collapsed) and
  `vc-empty.ts` (the cached structured-empty V&C view-model; both folders re-export). 6 folder-level
  `DateWindow`/`OnDateChange` re-declarations now re-export the ONE root declaration (harmonics-pq's stricter local
  interface intentionally kept).

### Knob-home + half-knob closeout (Batch 7, hardcode-audit session 2026-07-12)
- **Config F6 EXECUTED** — ONE scalar-knob home: 51 `data_quality_policy` scalars + 3 `viewer_policy` `__knob__:`
  sentinel rows copied VERBATIM into app_config (`db/fix_knob_home_consolidation.sql`, APPLIED; parity-checked
  54/54). Readers are now app_config-FIRST with the legacy tables as transition fallback:
  `config/policy_read.py` num/txt (+ shared `_appcfg`), `config/quality_policy.py` num/txt (legacy path keeps its
  deliberate RAISING semantics), `config/viewer_policy.py` `_txt`. Type-discriminated (a 'number' row can't serve a
  txt() read and vice versa) so migrated one-column rows never leak into the other accessor — verified by 11
  behavior probes + the guarding suites (config_cast/equipment_ratings/asset3d/page13/derivations — 100 green).
  Legacy rows retained for one transition; drop them + the fallback reads once nothing diverges.
- **Hardcoding F10 EXECUTED (option b — retire)** — `roster.power_column`/`roster.pf_columns` half-knobs removed:
  bindings.py Policy carries the gic_* literals with a fixed-schema-vocabulary note; the 2 rows (values equalled
  the code defaults) deleted via `db/fix_retire_roster_column_knobs.sql` (APPLIED; tree-wide grep incl. CMD found
  no other reader). Consistent with the mappings-addendum KEEP verdicts for LIVE_COLS/_TEMP_COLS: gic_* column
  names are schema vocabulary, renaming one is a schema migration, not a config edit.
- **Config F8 RESOLVED via option (b), no default flip** — the audit's own alternative (never-cache-empty
  `app_config._load` + retry backoff) landed, so an outage self-heals instead of pinning defaults for process
  life. The default-off polarity is a CONTRACT asserted by test_item17_guided_json/test_route_guided_json/
  test_morphmap_producer (fail-open to the battle-tested legacy path during a genuine outage window); flipping it
  would break those tests for no remaining gain. DB rows stay "on" (certified) and win whenever the DB is up.
- Data-state test fix (concurrent session, recorded here): `test_harness_no_data_runs_layer2_skeleton`'s hardcoded
  dark-asset fixture ('PCC Panel 4') started logging real data — the test now DISCOVERS a dark asset from the
  registry (or honestly skips) and is marked live.

### Deferred-backlog execution (Batch 8, "do deferred too" session 2026-07-12)
- **Follow-up #12 (pytest cwd)**: `pythonpath = .` in pytest.ini (ONE config home kept — no pyproject.toml added);
  tests now run from any cwd (verified from $HOME).
- **Follow-up #2**: `data/ttl_cache.py` → `lib/ttl_cache.py`; old path is a byte-compatible re-export facade.
- **Monoliths F4 (A+B)**: series router → `executor/series_router.py`; the sys.meta_path import-hook DELETED —
  fill() calls route_series_families explicitly as its LAST pass (wrapper-identical order/guards). meta_path
  verified clean at import.
- **Monoliths F6**: fill()'s inline pre-pass planning → `executor/field_routing.py` as TWO phases
  (plan_wildcards / plan_families) — one plan() call would have moved the family grouping ahead of the
  out-mutating wildcard grow; two phases preserve evaluation order byte-for-byte.
- **Monoliths F7**: energy-register pick_mover → `executor/energy_registers.py`; members.py re-exports. NOTE the
  monkeypatch lesson: 5 test sites patched `members._export_col` — a re-exported NAME patch never reaches the
  callee's globals; the tests now patch the defining module (4 of the 5 had only been passing by coincidence).
- **Monoliths F8**: series-label alignment → `executor/roster_labels.py` (roster.py 435→320 lines, re-exported).
- **Monoliths F9**: oversize compaction engine → `emit/prompt_compact.py` (maybe_compact + the two compactors);
  build_user is a thin call. Prose-to-DB move NOT taken (byte-identity of cached prompt prefixes at risk).
- **Monoliths F10 (split half)**: source-role wall → `executor/source_role_wall.py`, sibling resolution →
  `executor/sibling_resolve.py` (measurable_resolve 405→222 lines, re-exports; wall verdicts byte-verified:
  bypass blocks / input clears / output clears). The two-vocabulary consolidation stays flagged (DB rows + corpus
  parity required).
- **Typing F2**: 7 annotation-only types.py files (layer1a/1b/2, ems_exec, validate, run, host) + return
  annotations on build_layer1a_output / build_layer1b_output / run_pipeline / render_verdict.compute.
- **Typing F5**: vocab constant homes `validate/verdicts.py` + `layer2/swap/vocab.py`; owner-module literals
  rewired (schema/decide/build/render_verdict).
- **Typing F7**: `window_policy.normalize_window` (the union normalizer) wired once in serve/run.build_ctx —
  ctx.window is always the canonical tuple; voltage_current's richer range-preserving dict reader untouched.
- **Typing F8**: `_asset3d_envelope` tri-state sentinel (url|''|None) → explicit (is_asset3d, url) pair.
- **Typing F9**: `executor/telemetry_keys.py` (RESERVED_PAYLOAD_KEYS + pop_all — enrich's order-sensitive two-pop
  dissolved) + `layer2/telemetry.py` DI_TELEMETRY_KEYS + NEW tests/test_telemetry_keys_enumerated.py asserting
  every written `di._*` key is enumerated.
- **Typing F10**: validate_layer1a_output WIRED into _assemble (non-gating `contract_problems`, 1b-parity).
- **EH F3**: `executor/degrade.py` (note/run_pass); fill.py's 20 silent `except Exception: pass` now record
  pass-failure telemetry (control flow unchanged); serve/run_card's catch-all + re-fill + sankey sweep too.
- **EH F4**: `obs/errfmt.py` (fmt_exc/record_exc); 19 hand-rolled `f"{type(e).__name__}: {e}"` sites rewired;
  data/equipment + multi_asset stderr-only failures now ALSO land in the failures channel (additive).
- **FE F16**: the ONE RTM heatmap body `cmd/rtm/HeatmapSections.tsx` ({heatmap, bordered}; variant differences
  preserved verbatim; unwrap shared) — compose.tsx HeatmapCard deleted, RtmComposite.HeatmapBody is a thin
  wrapper. tsc + vite green.
- **FE F4**: `cmd/fill/shared/vc-sanitize.ts` = the stricter feeder sanitizer, both V&C folders re-export;
  client-gate over saved DG responses byte-identical before/after (8 cards clean, 0 throw, 0 NaN).
- **Fixed en passant**: obs/decision_view.py had its domain.fetch_spec import spliced INSIDE the module docstring
  (concurrent-edit artifact) — every l2_emit decision view silently degraded to view_error:NameError;
  test_decision_inspector now green. Full offline suite after all of the above: **998 passed, 0 failed** (5 skipped).
- **Full client-gate sweep (212 archived responses)**: 209 fully clean; 3 findings in 2 files, BOTH July-7
  captures predating the campaign, neither on a changed surface — response_r_f9787f915f cards 7/10 THROW inside
  vendored CMD_V2 TrendCard (`RT_DIR_PRESETS[stat.trend.dir].color`, dir unguarded — a payload-shape condition;
  candidate follow-up: the RTM-rail fill fn should default trend.dir before it reaches the vendored component)
  and response_r_1bc17049b9 card 47 NaN-attr (the pre-Batch-6 PQ placeholder era). PRE-EXISTING, not regressions:
  the DG/feeder V&C + RTM-heatmap surfaces changed today gate byte-identical.
- **NOT executed, with reasons**: D1 + F5-quantity/F14-FE landed by the concurrent session (recorded above);
  FE F11/F12 (registry/guards splits — order-sensitive walk arrays, do with the gates in a quiet tree);
  EH F7 (llm/parse extract_json — needs the replay-corpus parity proof; _insight is a certified port);
  measurable-role vocab consolidation (DB rows); `registries/neuract/` → `data/neuract_live/` (optional 17-file
  churn, skipped while the tree is hot).

## Follow-ups (status ledger — ✅ = executed since first written; unmarked = still open)

1. ✅ EXECUTED (concurrent session; verified in-tree 2026-07-12 ~08:20) — `validation/` → `sweep/` rename done;
   `validation/` is now a compat-alias package (`validation/__init__.py`) so `python3 -m validation.cli` keeps
   working; output paths (`outputs/validation/`) unchanged.
2. ✅ EXECUTED (Batch 8 above; verified in-tree) — home is `lib/ttl_cache.py`; `data/ttl_cache.py` is a
   byte-compatible re-export facade.
3. ✅ EXECUTED (APPLY_LOG second pass; verified in-tree) — `data/neuract_pool.py` is THE pooled psycopg2 door;
   both `ems_exec/data/neuract.py:18` and `registries/neuract/_db.py:15` import it.
4. `registries/neuract/` → `data/neuract_live/` (structure C2, optional): 17-file import churn; names should state
   the live-vs-mirror transport split.
5. Monoliths F4–F10: indexed_families step B (delete the sys.meta_path import-hook, wire route_series_families as
   fill()'s last pass — the audit's plan is fully specified), fill.py field-routing extraction, quantity_class
   package (facade mandatory — getattr + seed-tool consumers), members.py energy_registers, roster label-alignment,
   user_message prompt-compaction, measurable_resolve source-role wall (+ the two-vocabulary consolidation, DB rows
   involved). All specified in monoliths.md.
6. Typing F2/F3/F5/F7-F11: per-layer `types.py` TypedDicts (annotation-only), the `_err` envelope unification,
   verdict/answerability/swap vocab constants, window normalization, telemetry-key enumeration, wiring
   validate_layer1a_output. All specified in typing-contracts.md.
7. Error-handling F3/F4: `ems_exec/executor/degrade.py` run_pass telemetry (19 silent `except: pass` in fill.py) +
   `obs/errfmt.py` (the `f"{type(e).__name__}: {e}"` ×15 + stderr-only channels) — coordinate with the obs-trace
   session, which may land equivalents.
8. Error-handling F7: `llm/parse.py` shared extract_json (client.py vs _insight.py think-strip divergence; needs a
   replay-corpus parity proof — _insight is a certified port).
9. Frontend F11/F12 remain (registry/guards package splits — mind the import.meta.glob path and walk-order array).
   ✅ F14 EXECUTED (APPLY_LOG second pass; verified in-tree 2026-07-12 ~08:20: server.py/multi_asset.py no longer
   emit page-level frames/frame_status/live_frame, types.ts:127 records the retirement, and a live archived
   response has none of the keys — per-card `frame_status` kept). ✅ F4 EXECUTED (`cmd/fill/shared/vc-sanitize.ts`,
   Batch 8). ✅ F16 EXECUTED (`cmd/rtm/HeatmapSections.tsx`, Batch 8).
10. ✅ CLOSED by owner decisions (2026-07-12, later): Hardcoding **F7** — owner picked **0.9** as the PF-of-record;
    `nameplate.nominal_pf` seeded 0.9 (db/seed_pf_of_record.sql, APPLIED) + code mirror flipped 0.8→0.9 in
    derivations/nameplate.py (INTENDED behavior change: feeder_rated_kw path renders rated kW 12.5% higher, now
    consistent with derive_ratings). Hardcoding **F3 follow-up** — owner said "check cmd v2"; CMD_V2
    (config_defaults.py:81 + dg.py V&C consumer) wires the per-class deviation, so `statutory_band` now resolves
    ctx asset → class `voltage_statutory_deviation_pct` (DG ±5, others ±10; knob fallback 10.0) — INTENDED visible
    change on DG voltage bands; guarded by NEW tests/test_statutory_band_per_class.py. Epoch floors: ✅ CLOSED as
    DELIBERATELY DISTINCT (1e10 = lenient list-shape axis test, 1e12 = strict per-value fabrication verdict —
    unifying either way breaks a real case); DO-NOT-UNIFY notes cross-referenced at executor/epoch.py +
    fab_guards/knobs.py.
11. Config F6 second phase: ✅ PREPARED — `db/drop_legacy_knob_homes_phase2.sql` (self-guarding: aborts on any
    app_config↔legacy divergence; dry-run green under rollback). APPLY after ≥ one clean cert/sweep cycle. The
    fallback READS stay in code deliberately (quality_policy's raising outage layer); removing them is a separate
    semantics-changing step.
12. A `pyproject.toml` (pytest currently relies on repo-root cwd for imports).

### Endpoint home closeout (config F7 — EXECUTED, "implement remaining" session)
- NEW `config/endpoints.py` — the ONE :8770 home (HOST_PORT / HOST_BASE, env-overridable, DB-free import;
  re-exports llm/config's vLLM endpoint + config/ems_backend's origin so there is one import point). Rewired:
  `host/server.py` PORT, `sweep/config.py` BASE_URL (V48_VALIDATE_BASE still wins), `admin/config.py` HOST_API,
  `tools/payload_diff/capture.py` DEFAULT_HOST — verified all equal at import. `ops/tunnel_monitor.py` now probes
  via `config.databases.conn_env(DATA_DB)` (relocate the DB via PG_* and the monitor follows; smoke-tested live).
  Deliberately NOT moved: copilot/config.py (zero-coupled service), host/notes.py SB_BASE (DB-knob-first pattern
  would be demoted by an env-only home), host/web/vite.config.ts (separate Node process, same defaults).
