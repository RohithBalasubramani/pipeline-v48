# INTEGRATION AUDIT — AREA 1: WIRING / REACHABILITY

Auditor: integration-audit subagent (area 1). Date: 2026-07-06 ~21:25 IST.
Method: AST import graph over every .py under pipeline_v48 (350 modules, `__pycache__`/`archive`/`outputs`/node_modules excluded),
closure from live roots `run.harness`, `host.server`, `ems_exec.serve.run`; separate closures for tests/, scripts/, tools/, copilot/.
Config cross-check: every constant-key `cfg()/txt()/num()` read + literal-grep confirmation for wrapper reads (`_cfg`, `_num`, `_eb.num`, …)
vs live `cmd_catalog.app_config` (158 rows) and `cmd_catalog.data_quality_policy` (87 rows) via `data.db_client.q`, and vs keys
INSERTed by all db/*.sql.

VOLATILE-TREE NOTE: batch12's layer2 agent was writing while this audit ran. Files created DURING the audit window
(mtimes 21:19–21:21 IST): `layer2/emit/morphmap/*`, `db/seed_morphmap_flag.sql`, `tools/replay_item17_guided_asset_resolve.py`.
Findings on those are stamped VOLATILE — re-verify at batch end rather than treating as final defects.

---

## 1. Module reachability — every new/changed module classified

240 changed/new .py files audited (git status vs HEAD). Result:

- **173 LIVE** — proven import chain from `run/harness.py`, `host/server.py`, or the executor (`ems_exec/serve/run.py`,
  which is on the host live path via `host/exec_cards.py:12` → `from ems_exec.serve import run as ems_exec_run`).
  This covers ALL of: `ems_exec/**` (data/derivations/executor/renderers/serve), `registries/neuract/**`
  (importers: `ems_exec/executor/members.py`, `host/exec_cards.py`, `layer2/emit/panel_members_block.py`),
  `services/dict_merge.py` (← `ems_exec/renderers/asset_3d.py`), `host/{display_dash,enrich,exec_cards,payload_store}.py`
  (all ← `host/server.py`), `run/reconcile_granularity.py` (← `run/harness.py`), `validate/render_verdict.py`
  (← `host/enrich.py`), `validate/handling_lookup.py` (← `validate/build.py`), all new `grounding/*` scrubs
  (← `grounding/default_assemble.py` ← executor + `host/payload_store.py`), all new `layer1a/*`, `layer1b/*`,
  `layer2/*` modules (each has a live importer — e.g. `layer2/coherence.py` ← `layer2/build.py`,
  `layer2/swap/gate_force_renderable.py` ← `layer2/build.py` + `layer2/swap/decide.py`,
  `layer1a/catalog_compress.py` ← `layer1a/route.py`, `layer1b/resolve/answer_schema.py` ← `layer1b/resolve/asset_resolve.py`).
- **55 test files + 6 script files** — legitimate (`tests/*`, `scripts/*`).
- **Legitimate tools (not on live path, by design):** `tools/wall_corpus_replay.py`, `tools/replay_item17_guided_asset_resolve.py`
  (VOLATILE, new), `scripts/{build_stripped_payloads,rescan_stripped_payloads,seed_dg_asset3d,sync_neuract_registry}.py`,
  `scripts/wf_*.js` (workflow runners), `payload_db/harvest_asset_payloads.mjs`, `outputs/emit_correctness_battery.py`,
  `host/web/scripts/{ssr_repro,client_repro,tier_audit}.tsx`, `host/web/scripts/ssr_gate.mjs` (SSR gate harness).
- **`grounding/exemplar_reduce.py`** — reached ONLY by `scripts/build_stripped_payloads.py` / `scripts/rescan_stripped_payloads.py`.
  Legitimate: it is build-time tooling that populates `card_payloads.payload_stripped`, which the live path consumes from the DB.
- **`copilot/validated.py`** — reached from the copilot service's own index-build entry (`copilot/build/entities.py:30
  `import validated``; copilot dir is put on sys.path by `copilot/build/__init__.py:28-35`). Copilot is the separate :8772
  service — legitimate, not pipeline-dead.
- **Dangling-import check:** zero imports anywhere of the deleted modules (`config.flags`, `config.payload_shapes`,
  `config.dialects`, `config.endpoint_policy`, `contracts.validate`, `contracts.invariants.*`, `data.derived_metrics`,
  `data.nameplate`, `data.cmd_catalog.*`, `data.lt_panels.timeseries`, `data.registry.{capacity,lt_parameter,lt_mfm_type}`,
  `layer3.*`, `run.layer3_all`, `grounding.endpoint_resolve`). Clean.

### F1.1 — DEAD NEW CODE: `layer2/emit/morphmap/` (3 modules, zero importers) — SHOULD-FIX (VOLATILE)
`layer2/emit/morphmap/__init__.py`, `mode.py`, `producer.py` (+ `prompt.md`) have **no importer anywhere** (live, tests, scripts).
Self-documented as "ITEM 18 PREP — parallel path, NOT wired into the live emit" (`layer2/emit/morphmap/producer.py:2`,
`__init__.py:6-7`), gated on the DEFAULT-OFF row `emit.morphmap_mode` (`layer2/emit/morphmap/mode.py:15`) whose seed
(`db/seed_morphmap_flag.sql`) is **not applied** (row absent from app_config — harmless, seed value 'off' == code default).
Two problems even accepting the prep framing:
1. `db/seed_morphmap_flag.sql:5-6` cites an offline A/B gate `tools/morphmap_ab.py` + `outputs/morphmap_ab_offline.md` —
   **neither file exists** at audit time (files written 21:20 IST, agent mid-write; re-check at batch end).
2. Nothing calls `mode.py` — so even seeding the row to 'on'/'shadow' is a NO-OP. The flag is currently inert by construction.
Verdict: not cert-blocking (default-off, unwired-by-design, documented), but at batch end either the A/B tool must exist and
the row must have a caller, or this is dead new code shipping into cert.

### F1.2 — Frontend new files all reachable — PASS
- Page fill barrels auto-register via `host/web/src/cmd/registry.tsx:24`
  (`import.meta.glob("./fill/*.tsx", { eager: true })`) — covers new `dg-engine-cooling.tsx`, `dg-fuel-efficiency.tsx`,
  `dg-operations-runtime.tsx`, `diesel-generator-voltage-current.tsx`, `transformer-tap-rtcc.tsx`, `transformer-thermal-life.tsx`,
  `feeder-energy-power.tsx`, `feeder-real-time-monitoring.tsx`. Per-card subfolders load through their barrel
  (glob is deliberately non-recursive — documented in e.g. `host/web/src/cmd/fill/dg-engine-cooling.tsx:5-6`).
- `cmd/guards.ts` ← `cmd/registry.tsx:4` + fill card files; `cmd/shims.ts` ← `cmd/guards.ts`; `cmd/special.tsx` ← `cmd/registry.tsx:5`.

---

## 2. Config rows NO code reads (inert rows)

Every key below exists in the live DB and has **zero readers** (literal grep across .py/.ts/.tsx incl. dynamic-prefix readers;
dynamic namespaces `consts.*` at `layer2/quantity_class.py:349-360`, `llm.timeout.<stage>` at `llm/client.py:65`,
`vocab.*` at `config/vocab.py:31-34`, `rating_slot.*` at `config/nameplate_slot_map.py:39` were accounted for).

### F2.1 — app_config: 10 inert rows — SHOULD-FIX
| rows | orphaned by |
|---|---|
| `flags.ctx_source_form`, `flags.page_wise_shared_detection`, `flags.require_live_sentinel` | `config/flags.py` deleted (git `D config/flags.py`) |
| `payload_shapes.canonical`, `payload_shapes.shape_map` | `config/payload_shapes.py` deleted |
| `panel_aggregate.member_columns`, `panel_aggregate.sum_columns`, `panel_aggregate.event_neutral_column` | superseded by `roster.member_columns`/`roster.sum_columns` (`ems_exec/executor/roster.py:114-115`); `ems_exec/renderers/panel_aggregate.py` reads only `panel_aggregate.{energy_import_column,energy_export_column,register_policy,load_factor_fns}` (lines 66-68, 230) |
| `display.rate_key_pattern` | no reader anywhere (host/display_dash.py reads other `display.*` keys but not this) |
| `ems_backend.frame_budget_s` | old host fetch-budget; replaced by `ems_exec.card_budget_s` (`host/exec_cards.py:18`) which reads a DIFFERENT key |
Risk: an engineer edits these rows expecting behavior change; nothing happens. Delete the rows or note them retired.

### F2.2 — data_quality_policy: ~60 inert rows — SHOULD-FIX
- **`band.*` — 33 rows** (`band.ieee519.*` ×13, `band.overview.*` ×12, `band.pq_fleet.*` ×8) AND the **`band_policy` table (6 rows)**:
  the declared sole reader `config/bands.py` (per `db/seed_band_policy.sql:3` "Read ONLY by config/bands.py") **does not exist**.
  Renderers now use `config/event_thresholds.py` (reads the `event_threshold` table — 7 rows, live:
  `ems_exec/renderers/_story/harmonics_pq.py:20`, `voltage_current.py:21`). Stale docstrings still cite config.bands:
  `config/energy_balance_policy.py:10`, `config/feeder_overview.py:4` (COSMETIC).
- **`scope_map.*` — 7 rows** (asset/default/meter/none/panel/panel_default/site): reader `grounding/endpoint_resolve.py` deleted
  (the retired seed's rows — see §5).
- **`l3.*` — 6 rows** (`l3.allowed_ops`, `l3.manifest_semantic_match`, `l3.out_of_range.load_pct_max`, `l3.out_of_range.pct_max`,
  `l3.percent_slot_suffixes`, `l3.unmapped_scan_enabled`): whole `layer3/` package deleted (git `D layer3/*`, `D run/layer3_all.py`).
- **Singletons with zero readers:** `cumulative_counter_policy`, `event_marker_array_keys`, `history.dip_load_pct`,
  `history.surge_load_pct`, `meaningful_min_energy_delta_kwh` (only a docstring mention `grounding/meaningful.py:11`; code reads
  only `meaningful_min_power_kw` at line 75), `pf_sign_policy` (docstring example only, `config/quality_policy.py:19`),
  `energy_balance.assumed_pf`, `energy_balance.reactive_energy_col` (present in the defaults dicts
  `config/energy_balance_policy.py:26,33` but NO caller ever passes those keys — only `over_metered_frac`/`unmetered_surface_frac`/
  `expected_loss_band_pct` are read, `ems_exec/renderers/_story/energy_distribution.py:20-22`),
  `feeder_overview.meter_gap_review_kw`, `feeder_overview.voltage_statutory_pct` (in `_DEFAULTS` `config/feeder_overview.py:21-22`
  but no caller — callers pass only `pf_good_min`/`pf_fair_min`/`sld_flow_threshold_kw`, `ems_exec/executor/bindings.py:50-52`).
- **reason_template orphan causes (10):** `emit_failed`, `endpoint_retired`, `endpoint_unconfigured`, `frame_shape_mismatch`,
  `incomer_unverified`, `no_metered_feeders`, `no_renderer`, `no_topology`, `timed_out`, `window_clamped` — zero code references
  (data-only, harmless; 3 of them are retired-seed residue, see §5).

### F2.3 — `registered_card_ids` row is stale and its only seeder is retired — SHOULD-FIX (highest-impact row finding)
DB row `data_quality_policy.registered_card_ids` = `5..27,36..49,160`. The FE fill registry NOW also carries renderers for
cards **61–69, 71, 73–81** (`host/web/src/cmd/fill/dg-*/card-6x.tsx`, `transformer-*/card-7x/8x.tsx` — all auto-registered
via `registry.tsx:24`). Readers: `grounding/swap_settle.py:29-43` (`is_registered`, `swappable_pool`) and
`layer2/swap/candidates.py:15` — the swap-target pool filter. Effect: **no DG/transformer card can ever be chosen as a swap
target** (silently dropped from every pool), including by the force-renderable enforcer (`layer2/swap/gate_force_renderable.py`).
Its only seed lived in `db/seed_endpoint_resolve_policy.sql.retired` (lines 40-44), so nothing in the tree can re-derive or
refresh this row any more — it is hand-maintained with no owner. Not render-blocking (pages render their own cards regardless;
per-leaf degradation unaffected) but it can silently degrade the DG/transformer cert sweep whenever a swap is needed.
Fix: re-home the row in an active seed (or derive it from the FE registry) and add 61-69,71,73-81.

---

## 3. Code reading rows that do NOT exist (silent default)

House convention (`config/app_config.py:42-44`) is explicit: missing row → code default, "behaves identically until a row
exists" — so these are NOT bugs, but per the DB-driven-config goal they are un-tunable until someone knows the key to insert.

### F3.1 — read + seed file exists but seed NOT applied — SHOULD-FIX (VOLATILE, pending-apply)
- `emit.dual_owned_keys` — read `layer2/emit/user_message.py:102`; seed `db/seed_layer2_residual_knobs.sql:13-16`.
  Seed value `["sectionContracts","pres.spokes","pres.selectedName"]` == code default → **no behavior gap**, apply is cosmetic.
- `emit.morphmap_mode` — read `layer2/emit/morphmap/mode.py:15`; seed `db/seed_morphmap_flag.sql:12`. Seed 'off' == code
  default 'off' → no behavior gap (and the reader has no callers, F1.1).
These are the ONLY two keys any db/*.sql seeds into app_config/data_quality_policy that are absent from the DB — i.e. every
other seed file has been applied.

### F3.2 — read, no row, no seed anywhere (default forever) — COSMETIC (inventory)
Live-path app_config keys: `emit.slot_catalog_cap` (0=off, `layer2/emit/slot_catalog.py:242`), `ems_exec.card_budget_s`
(`host/exec_cards.py:18`, env fallback V48_EXEC_BUDGET_S), `feasibility.pool_verdicts` (`layer2/swap/candidates.py:19`),
`feasibility.template_max_unrenderable_frac` + `feasibility.unrenderable_verdicts` (`config/feasibility.py:13,18`),
`fill.window_register_delta` ('on', `ems_exec/executor/fill.py:75`), `llm.transport_retry` (1, `layer2/emit/emit.py:145`),
`llm.max_tokens` (0=don't send, `llm/client.py:135`), `metrics.{slot_shorthand,generic_slot_tokens,domain_stems}`
(`config/metrics.py:53-59`), `neuract.{host,port,db,schema,user,password,ts_col,ts_cast}` (`config/neuract_dsn.py:19-49` —
DSN override knobs, intended absent), `renderers.telemetry_snapshot_keys` (`ems_exec/renderers/__init__.py:72`),
`routes.granularity_shells` (`layer1a/parse/granularity_reconcile.py:33`), `swap.forced_swap_confidence`
(`layer2/swap/gate_force_renderable.py:28`), `validation.rollup_legacy_any_fail` (`validate/report.py:17`),
`validation.time_column` (`config/validation.py:16`), `window.site_tz` (`config/windows.py:19`), `windows.reference_now`
(replay pin, intended absent, `layer2/build.py:110`); tool keys `wall_replay.*` (`tools/wall_corpus_replay.py:340,459,514`).
data_quality_policy keys: `feeder_overview.sld_flow_threshold_kw` (`ems_exec/executor/bindings.py:52`),
`scrub.temporal_pattern`/`scrub.bare_day_pattern`/`scrub.provenance_tokens` (`grounding/default_assemble.py:92,107,134`).
(NOTE: earlier-looking "missing" keys `I_THD/V_THD/SAG/SWELL/I_UNBAL` are FALSE positives — they read the `event_threshold`
TABLE via `config/event_thresholds.py`, rows verified present.)
Recommendation: seed the new-gate knobs (`feasibility.*`, `swap.forced_swap_confidence`, `scrub.*`) so they're discoverable rows.

---

## 4. DEFAULT-OFF flags (complete list + does off == old behavior?)

| flag | state | off == old behavior? |
|---|---|---|
| `emit.morphmap_mode` (code 'off'; row absent, seed pending) | OFF | YES — off = the certified full exact_metadata retype emit. Caveat: 'on' is currently a NO-OP too (F1.1: `mode()` has zero callers). |
| `llm.guided_json.asset_resolve` (DB row = 'off') | OFF | YES — off → `asset_answer_schema()` returns None and call_qwen "builds today's byte-identical json_object request" (`layer1b/resolve/answer_schema.py:31-38`). |
| `llm.max_tokens` (no row, code default 0 = do not send) | OFF | YES — matches the post-purge behavior (all max_tokens deleted); a row would re-introduce a cap (`llm/client.py:135`). |
| `emit.slot_catalog_cap` (no row, code default 0 = uncapped) | OFF | YES — off = full slot catalog, the existing behavior (`layer2/emit/slot_catalog.py:242`). |
| `route.catalog_archetype` (DB row = 'false') | OFF | **NO** — off = the NEW item-21 compressed catalog WITHOUT the archetype tag; ON "turns it back on" i.e. restores the OLD display (`layer1a/route.py:39-41`). Off = new behavior; documented restore-switch, flag semantics inverted vs the "off = old" rule. |
| `validation.rollup_legacy_any_fail` (no row, code default False) | OFF | **NO** — off = the NEW graded rollup (`pass_with_gaps`); ON reverts to the LEGACY any-fail rollup (`validate/report.py:17-24`). Off = new behavior; intentional legacy-revert switch, same inversion. |
| `flags.page_wise_shared_detection` (DB row 'false') | OFF | MOOT — reader deleted (F2.1); the row controls nothing. |
| `l3.unmapped_scan_enabled` (qp row) | n/a | MOOT — layer3 deleted (F2.2). |

Default-ON valves with an 'off' escape (not default-off; listed for completeness): `display.null_dash`('unit_adjacent',
`host/display_dash.py:69`), `scrub.clock_strings`('on', `grounding/default_assemble.py:96-97`), `fill.window_register_delta`('on'),
`emit.prompt_char_budget`(row=36000; 0=off), `llm.prompt_budget_tok`(row=45000; 0=off), `layer1b.basket.*` (3 bool rows, all 'true').

### F4.1 — two "default-off" flags where off = NEW behavior — COSMETIC (document)
`route.catalog_archetype` and `validation.rollup_legacy_any_fail` are revert switches (off = new code path). Both are deliberate,
but any cert checklist asserting "every default-off flag preserves old behavior" must carve these two out.

---

## 5. Retired seed `db/seed_endpoint_resolve_policy.sql.retired` — CLEAN, with residue

- **No code references**: zero hits for `endpoint_resolve` / `seed_endpoint_resolve_policy` in any .py/.sql/.ts/.tsx/.js/.mjs
  outside `outputs/` worklogs and `docs/V48_RENDER_GUARANTEE_CONTRACT.md` (stale doc mention — COSMETIC).
- **Deleted reader `grounding/endpoint_resolve.py`**: zero importers anywhere. CLEAN.
- **Keys from the seed still read by LIVE code all still exist in the DB** (verified): `placeholder.scalar`
  (`grounding/default_assemble.py:52`, `ems_exec/executor/graft.py:97`), `placeholder.narrative` (`default_assemble.py:74`),
  `narrative_slots` (`default_assemble.py:66`), `registered_card_ids` (`grounding/swap_settle.py:30`). No silent-default regression.
- **`page_tail_alias.*` rows**: correctly gone from data_quality_policy; the alias moved to app_config `routes.page_tail_alias`
  (row verified present; readers `layer2/emit/data/consumer_binding/screen_map.py:12`, `layer1a/parse/granularity_reconcile.py:41`).
- **Residue (flagged above)**: `scope_map.*` ×7 orphan rows (F2.2); reason_template causes `endpoint_unconfigured`,
  `no_metered_feeders`, `no_renderer` orphaned (F2.2); `registered_card_ids` left seeder-less and stale (F2.3).

---

## Finding index

| id | severity | one-liner |
|---|---|---|
| F1.1 | SHOULD-FIX (VOLATILE) | layer2/emit/morphmap/* dead new code; flag row unapplied AND unread; cited A/B tool missing |
| F1.2 | PASS | all new FE files reachable (glob registry + barrels) |
| F2.1 | SHOULD-FIX | 10 inert app_config rows (flags.*, payload_shapes.*, panel_aggregate.{member,sum,event_neutral}*, display.rate_key_pattern, ems_backend.frame_budget_s) |
| F2.2 | SHOULD-FIX | ~60 inert quality_policy rows + band_policy table (band.* ×33, scope_map.* ×7, l3.* ×6, 10 singletons, 10 orphan reason causes); stale config/bands.py citations |
| F2.3 | SHOULD-FIX | registered_card_ids row stale (missing cards 61-81) and its only seeder is the retired file |
| F3.1 | SHOULD-FIX (VOLATILE) | 2 pending-apply seeds (emit.dual_owned_keys, emit.morphmap_mode) — values match code defaults, no behavior gap |
| F3.2 | COSMETIC | inventory of read-with-no-row keys (design-sanctioned code defaults) |
| F4.1 | COSMETIC | route.catalog_archetype + validation.rollup_legacy_any_fail: off = NEW behavior (revert switches) |
| §5 | PASS | retired seed + deleted endpoint_resolve.py: no references; live keys intact |
