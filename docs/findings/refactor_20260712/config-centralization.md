# CONFIG CENTRALIZATION — refactor audit findings (2026-07-12)

Scope: every configuration surface in pipeline_v48 (config/*.py, cfg()/app_config, os.environ/os.getenv,
hardcoded ports/URLs/DSNs/model names, feature flags, timeout knobs). Quarantined dirs (archive/, outputs/,
.claude/, node_modules, dist, __pycache__) excluded.

## Map of the config surfaces (inventory)

**Canonical mechanism (healthy, widely adopted):** `config/app_config.py::cfg(key, default)` — reads
`cmd_catalog.app_config` (key/value/data_type) once per process (lru_cache), casts, fail-open to the code
default. **304 call sites across ~100 files.** DB currently holds **309 rows**. `reload()` exists to drop the
process cache.

**Secondary DB knob homes (same *kind* of knob, different tables/APIs):**
- `cmd_catalog.data_quality_policy` via `config/quality_policy.py::num()/txt()` (also read by
  `config/feeder_overview.py:30`, `config/energy_balance_policy.py:44,57`, `config/nameplate_slot_map.py`
  `rating_slot.<slot>` rows).
- `cmd_catalog.viewer_policy` rows with sentinel key `page_key='__knob__:<key>'` via
  `config/viewer_policy.py:97-101` (e.g. `viewer.glb_media_base` used by `config/asset3d_media.py`).
- `neuract.lt_config_field/value` (MFM.get_config, ems_backend side — out of pipeline scope but part of the
  documented two-home rule).
- Legit *relational* config tables (fine as tables, not scalar knobs): `reason_template`, `schema_map`,
  `metric_class`, `event_threshold`, `derivation_binding`, `routable_pages`, `render_guarantee_matrix`,
  `card_handling`, `asset_class_defaults`.

**Env-var surfaces (all reads tree-wide):**
- `config/databases.py` — PG_HOST/PG_PORT/PG_DB/PG_SCHEMA/PG_USER/PG_PASSWORD, DATA_TS_COL/DATA_TS_CAST/
  DATA_HAS_PANEL_ID, CMD_CATALOG_DB, TEST_DB, DB_TARGET, CATALOG_HOST/CATALOG_PORT, PG_CONNECT_TIMEOUT.
  (Self-declared "THE SINGLE PLACE for DB wiring" — mostly true, see F7 for the two violators.)
- `llm/config.py` — `LLM_URL` (default `http://localhost:8200/v1/chat/completions`), `MODEL`
  (default `Qwen/Qwen3.6-35B-A3B-FP8`). **Generic, collision-prone env names** (see F1).
- `ems_exec/renderers/_insight.py` — `insight.llm_url/llm_model/timeout/temperature` via a private `_env()`
  that reads cfg row → `os.getenv(<last-segment-uppercased>)` → legacy `EMS_INSIGHT_*` (see F1).
- `config/ems_backend.py` — EMS_WS_SCHEME/HOST/PORT (:8890) env-only; connect/frame timeouts + retries via
  cfg with env fallback (import-time frozen, see F5).
- `config/validation.py` — cfg with `V48_*` env fallbacks (import-time frozen, see F5).
- `config/available_pages.py` — `V48_AVAILABLE_PAGES` > `routable_pages` table > code default (documented
  resolution order — healthy).
- `config/asset3d_media.py` — EMS_HTTP_SCHEME, EMS_MEDIA_URL (env-only defaults, DB knob wins).
- `validation/config.py` — V48_VALIDATE_BASE (:8770), V48_VALIDATE_RUN_CONC(_MAX), V48_VALIDATE_FRAME_CONC,
  V48_VALIDATE_RUN_TIMEOUT, V48_VALIDATE_FRAME_TIMEOUT, V48_VALIDATE_THROTTLE_*, V48_VALIDATE_OUT — env-only,
  no cfg(). (Sweep harness; deliberate DB-independence is defensible, duplication of :8770 is not — F7.)
- `host/server.py` — STORYBOOK_URL (default hardcodes LAN IP `http://100.90.185.31:6008`), V48_HOST_PORT (:8770).
- `host/exec_cards.py:18` — `cfg("ems_exec.card_budget_s", env V48_EXEC_BUDGET_S, 45)` (key drift — F4).
- `copilot/config.py` — 15 `COPILOT_*` vars incl. its own LLM endpoint (:8201, Qwen3-4B), its own copy of the
  :5433 neuract wiring, PORT :8772. Deliberate zero-coupling (memory: ems-query-copilot-layer).
- `layer1b/build.py:14-15` — V48_ALLOW_ENV_PIN + PIPELINE_ASSET_ID (guarded opt-in, healthy).
- `run/harness.py:303` — V48_SKIP_LAYER2.
- `layer2/build.py:111` — `cfg("windows.reference_now")` → env `EMS_REFERENCE_NOW` (cfg-first, healthy).
- `copilot/validated.py:20` — `os.environ.setdefault('V48_VALIDATE_ROWS', ...)` env-as-IPC hack (symptom of F5).
- `tools/tunnel_monitor.py` — TUNNEL_MONITOR_INTERVAL/HOURS/SWEEP_ON_START; **hardcodes** the psql target
  `-h 127.0.0.1 -p 5433 -d target_version1 -U postgres` (F7).
- `scripts/seed_dg_asset3d.py:55` — MEDIA_ROOT env with a path default (one-shot seeder, acceptable).
- `host/web/vite.config.ts:6-7` — V48_HOST_API (`http://localhost:8770`), V48_COPILOT_API
  (`http://localhost:8772`); dev port 5188 literal at line 22.

**Feature flags, where they live:**
- `emit.morphmap_mode` — app_config row = **on**; code default **off** (`layer2/emit/morphmap/mode.py:29`).
- `llm.prompt_v2` — app_config row = true; **reader deleted** (`layer2/emit/emit.py:150` comment: "the
  llm.prompt_v2 selector + those files are gone") → orphaned row (F3).
- `llm.guided_json.route` / `llm.guided_json.asset_resolve` — rows = on; code default off
  (`layer1a/route_schema.py:52`, `layer1b/resolve/answer_schema.py:41`).
- `equipment.facts.enabled`/`alias.enabled` (on), `equipment.topology/derivations/kitpreview.enabled` (off —
  staged, NOT collapsible yet).
- `flags.ctx_source_form`, `flags.page_wise_shared_detection`, `flags.require_live_sentinel` — rows exist,
  **zero readers** anywhere in pipeline_v48, the wider layer2 tree, or /home/rohith/CMD (F3).
- `multi_asset.enabled`, `knowledge.enabled`, `roster.interpreter_enabled`, `view.auto_select`,
  `fab_guards.*` on/off rows — all have live readers (healthy).

**Timeout/concurrency knobs:** `llm.timeout`(120) + `llm.timeout.{l2_emit=150,route,basket,stories,
asset_resolve}`, `llm.no_retry_kinds`, `llm.seed`, `llm.temperature`, `llm.max_tokens`, `llm.parse_retry`,
`llm.prompt_budget_tok` — all cleanly cfg()-driven inside `llm/client.py` (healthy). `layer2.emit_concurrency=4`
(`run/layer2_all.py:48`, lazy — healthy). `cache.resolution_ttl_s=120` (`data/ttl_cache.py:25`, lazy per call —
healthy). `ems_backend.*` timeouts — cfg but import-frozen (F5). Executor budget — key drift (F4).

---

## FINDINGS (ranked)

### F1 — Two vLLM endpoint definitions; `_insight._env()` hijacks the generic `LLM_URL`/`LLM_MODEL`/`TIMEOUT`/`TEMPERATURE` env names with different URL-shape semantics
- **File:** `ems_exec/renderers/_insight.py:48` (and `:65-68`); counterpart `llm/config.py:4-5`.
- **Evidence:**
  - `llm/config.py:4`: `LLM_URL = os.environ.get("LLM_URL", "http://localhost:8200/v1/chat/completions")` — a FULL chat/completions URL.
  - `_insight.py:48`: `raw = os.getenv(key.split(".")[-1].upper()) or os.getenv(_LEGACY_ENV.get(key, ""))` — for key `insight.llm_url` this reads env **`LLM_URL`** *before* the namespaced legacy `EMS_INSIGHT_LLM_URL`.
  - `_insight.py:65`: `LLM_URL = _env("insight.llm_url", "http://localhost:8200/v1")` — a BASE URL; `:117` appends `"/chat/completions"`.
- **Failure mode:** operator relocates vLLM by setting `LLM_URL=http://gpu2:8200/v1/chat/completions` (the documented llm/config.py contract) → the insight narrator POSTs to `.../v1/chat/completions/chat/completions` → 404 → every AI summary silently degrades to fallback. Likewise a CI/user env `TIMEOUT`, `TEMPERATURE`, or `LLM_MODEL` (all extremely generic names, derived from the key's last segment) silently reconfigures the narrator. `llm/config.py`'s own `MODEL` env name has the same genericness hazard.
- **Refactor:** make `_env()` read the namespaced env first and drop the generic last-segment fallback (`EMS_INSIGHT_LLM_URL` etc. already exist in `_LEGACY_ENV`); rename llm/config env vars to `V48_LLM_URL`/`V48_LLM_MODEL` with the legacy names kept as fallback (`os.environ.get("V48_LLM_URL", os.environ.get("LLM_URL", default))`). One canonical endpoint definition: `llm/config.py` exposes `base_url()` and both modules derive from it (cfg row `insight.llm_url` still wins for insight per its DB-first contract).
- **Risk:** low. **Behavior-preserving:** yes in a clean env (identical defaults); only the collision case changes — which is the bug.
- **Tests guarding:** `tests/test_foundations.py` (monkeypatches `config.LLM_URL`), `tests/test_seam3_seed_and_period.py`, `tests/test_strip_provenance_and_blank.py` (insight fallback path), `tests/test_failures_fanout.py`.

### F2 — `obs/ai_log.py` filters LLM telemetry by hardcoded `":8200"` substring, decoupled from the configurable endpoint
- **File:** `obs/ai_log.py:36-37`.
- **Evidence:** `url = getattr(req, "full_url", ""); if ":8200" not in url: return resp`.
- **Failure mode:** point `LLM_URL` (or `insight.llm_url` row) at any other port/host → every `ai_<run_id>.jsonl` record vanishes; run-audit and replay tooling (tools/replay_item17..., wall_corpus_replay) that mine those logs go blind with zero error. The endpoint is a knob in two modules but the observer is pinned to a literal.
- **Refactor:** derive the match token from `llm.config.LLM_URL`'s netloc at import (fallback `":8200"`), e.g. `_MATCH = urlsplit(config.LLM_URL).netloc or ":8200"`. Keep matching insight's URL too (same netloc once F1 lands).
- **Risk:** low. **Behavior-preserving:** yes (default netloc is `localhost:8200`; substring match unchanged).
- **Tests guarding:** `tests/conftest.py`, `tests/test_foundations.py`, `tests/test_failures_fanout.py` reference ai_log.

### F3 — Five orphaned app_config rows: knobs an operator can edit that nothing reads
- **Files/rows:** cmd_catalog.app_config rows `llm.prompt_v2` (true), `flags.ctx_source_form` (dotted),
  `flags.page_wise_shared_detection` (false), `flags.require_live_sentinel` (true), `ems_backend.frame_budget_s` (45).
- **Evidence:** `layer2/emit/emit.py:150`: "*the retired swap.md + metadata.md + data_instructions.md trio; the llm.prompt_v2 selector + those files are gone*". grep for `prompt_v2|ctx_source_form|page_wise_shared|require_live_sentinel|frame_budget_s` across pipeline_v48, the whole `/home/rohith/desktop/BFI/backend/layer2` tree, and `/home/rohith/CMD` finds **zero readers** (only test fixtures injecting `llm.prompt_v2` into a fake `_load`: `tests/test_morphmap_dp_gate.py:226,252`, and a comment in `tests/test_morphmap_producer.py:127`).
- **Failure mode:** operator "turns off prompt-v2" or "raises frame_budget_s" via the documented knob table → silent no-op; config table accretes lies about what is tunable.
- **Refactor:** one cleanup migration `db/cleanup_orphan_knobs.sql` deleting the five rows, plus strip the stale `llm.prompt_v2` keys from the two test fixtures. Per the verify-before-dead rule, run the same tree-wide grep before executing (done here for BFI/layer2 + CMD; re-check any other app_config consumer repos at apply time).
- **Risk:** low. **Behavior-preserving:** yes (rows have no readers by construction).
- **Tests guarding:** `tests/test_morphmap_dp_gate.py`, `tests/test_morphmap_producer.py` (fixtures to touch), `tests/test_config_cast_integrity.py` (app_config casting).

### F4 — Executor budget knob key drift: code reads `ems_exec.card_budget_s`, DB seeds `ems_backend.frame_budget_s`
- **File:** `host/exec_cards.py:18`.
- **Evidence:** `_EXEC_BUDGET_S = cfg("ems_exec.card_budget_s", float(os.environ.get("V48_EXEC_BUDGET_S", "45")))` — but app_config contains `ems_backend.frame_budget_s|45|number` and **no** `ems_exec.card_budget_s` row; `frame_budget_s` has no reader anywhere (see F3 grep).
- **Failure mode:** operator edits the seeded 45s budget row → executor keeps the code default 45; the two names diverge invisibly the first time someone tunes either.
- **Refactor:** `UPDATE app_config SET key='ems_exec.card_budget_s' WHERE key='ems_backend.frame_budget_s'` (values both 45 → byte-identical behavior), or seed the new key and delete the old under F3's migration.
- **Risk:** low. **Behavior-preserving:** yes (both values are 45 today).
- **Tests guarding:** none reference exec_cards' budget (gap worth one unit test asserting the key exists in the seed).

### F5 — Import-time `cfg()` freeze: module-level constants defeat `reload()` and per-process tunability; mixed eager/lazy access pattern
- **Files (eager/frozen):** `config/windows.py:4,11,33` (`TIME_WINDOWS = cfg(...)` etc.), `config/metrics.py:4,7,10,53,59`, `config/swap.py:4-6`, `config/intents.py:4`, `config/validation.py:16-49`, `config/ems_backend.py:13-21`, `config/feasibility.py:30`, `host/exec_cards.py:18`. **(Lazy, the house-correct pattern):** `config/neuract_dsn.py` (accessor functions), `config/gates_vocab.py:16`, `config/asset_granularity.py:16`, `data/ttl_cache.py:20-27`, `llm/client.py:_cfg` per call.
- **Evidence:** `config/windows.py:4`: `TIME_WINDOWS = cfg("windows.time_windows", {...})` — bound once at import; `config/app_config.py:51-53` ships `reload()` precisely to "call after seeding/editing app_config in the same process", but a reload never reaches these constants. The workaround this forces is visible at `copilot/validated.py:20`: `os.environ.setdefault('V48_VALIDATE_ROWS', sys.argv[2])` **before** importing the validator — env-as-IPC into an import-time freeze.
- **Failure mode:** seed/edit a row + `reload()` (or a long-running host picking up a DB edit after `cache.resolution_ttl_s`-style expiry) → half the knobs update (lazy readers), half don't (frozen constants); which half is accident of import style. Tools that tune knobs in-process (seeders, A/B replays) silently test stale values.
- **Refactor:** convert the frozen constants to accessor functions (the `neuract_dsn.py` style already in-tree) or a module-level `__getattr__` shim that keeps the existing names (`def __getattr__(n): return cfg(_KEYS[n], _DEFAULTS[n])`) so no call site changes. Values are identical; only staleness semantics improve. Do it per-file (atomic-structure rule keeps one concern per file).
- **Risk:** medium (wide import surface — windows/metrics vocab feeds 1a parsing; touch one module at a time). **Behavior-preserving:** yes for any process that doesn't edit rows mid-run (today's frozen value == today's lazy value under the lru_cache).
- **Tests guarding:** `tests/test_window_extraction.py`, `tests/test_layer2_window_label.py`, `tests/test_config_cast_integrity.py`, `tests/test_swap_metric_affinity.py`, `tests/test_layer1a_routing.py`.

### F6 — Three scalar-knob homes in cmd_catalog: app_config vs data_quality_policy vs viewer_policy `__knob__` sentinel rows
- **Files:** `config/viewer_policy.py:97-101`, `config/quality_policy.py:12,20`; dependents `config/asset3d_media.py:28-30` (`viewer.glb_media_base`), `config/feeder_overview.py:30`, `config/energy_balance_policy.py:44,57`, `config/nameplate_slot_map.py` (`rating_slot.<slot>`).
- **Evidence:** `viewer_policy.py:101`: `f"SELECT txt_value FROM viewer_policy WHERE page_key='__knob__:{_esc(key)}'"` — a scalar knob stored by overloading the page-type table's key column with a sentinel prefix; `quality_policy.py:12`: `SELECT num_value FROM data_quality_policy WHERE key=...` — a second key/value store with its own `num()/txt()` API parallel to `cfg()`.
- **Failure mode:** the same *class* of knob (scalar, keyed, typed, fail-open) is readable from three tables through three APIs; an operator auditing "what is tunable" via app_config misses `viewer.glb_media_base` and every `rating_slot.*` / `feeder.*` / `energy_balance.*` knob; per-table cache/reload semantics differ; `__knob__:` rows can collide with a future page_key.
- **Refactor:** migrate the *scalar* rows into app_config (`INSERT ... data_type`), then turn `quality_policy.num()/txt()` and `viewer_policy._txt()` into shims that read `cfg(key, ...)` first and fall back to the old table during transition — call sites unchanged. Keep genuinely relational tables (event_threshold, derivation_binding, schema_map, reason_template) where they are.
- **Risk:** medium (data migration + two accessor rewrites; values must be copied verbatim). **Behavior-preserving:** yes if rows are copied before the shim flips.
- **Tests guarding:** `tests/test_asset3d_dg_seed.py`, `tests/test_equipment_ratings.py`, `tests/test_page13_dg_cert_defects.py` (nameplate/rating paths); no direct unit tests on quality_policy/viewer_policy accessors (gap).

### F7 — No single source of truth for service endpoints; defaults duplicated per consumer, two modules bypass `config/databases.py` outright
- **Files/lines:**
  - `:8770` host default in **three** places: `host/server.py:47`, `validation/config.py:13` (`"http://127.0.0.1:8770"`), `host/web/vite.config.ts:6` (`"http://localhost:8770"`); plus prose in `host/web/src/App.tsx:143`.
  - `:8772` copilot in `copilot/config.py:18` + `host/web/vite.config.ts:7`.
  - `:8200` vLLM in `llm/config.py:4`, `ems_exec/renderers/_insight.py:65`, `obs/ai_log.py:36` (F1/F2).
  - `tools/tunnel_monitor.py:35`: `["psql", "-U", "postgres", "-h", "127.0.0.1", "-p", "5433", "-d", "target_version1", ...]` — hardcodes the tunnel target instead of `config.databases.conn_env(DATA_DB)`, despite databases.py's header claiming "Nothing else hard-codes a host/port/db/schema".
  - `copilot/config.py:26-32` re-declares the same neuract wiring under `COPILOT_*` (127.0.0.1:5433/target_version1/postgres — deliberate zero-coupling, but no `PG_PASSWORD` equivalent → drifts from databases.py).
  - `host/server.py:46`: `SB_BASE = os.environ.get("STORYBOOK_URL", "http://100.90.185.31:6008")` — a hardcoded **LAN IP** as a code default.
- **Failure mode:** change `V48_HOST_PORT` → the validation sweep still hits 8770 and the vite proxy breaks unless two more env vars are exported in *different processes*; override `PG_PORT` for a local Postgres → tunnel_monitor keeps probing :5433, declares the (relocated) DB dead and restarts an SSH tunnel nobody uses.
- **Refactor:** add one `config/endpoints.py` (single-purpose file, house style — the service-endpoint sibling of `config/databases.py`): `HOST_PORT`, `HOST_BASE`, `COPILOT_PORT`, `LLM_URL`/`LLM_BASE`, `EMS_WS_*` re-export, `STORYBOOK_URL`, each `os.environ`-overridable with today's literals as defaults. `host/server.py`, `validation/config.py`, `tools/tunnel_monitor.py` (via `conn_env`) import it; `vite.config.ts` keeps its env override but the README/env sample points at the same vars. Copilot stays decoupled by design (document the duplication in copilot/config.py instead).
- **Risk:** low-medium. **Behavior-preserving:** yes (same defaults, same env overrides).
- **Tests guarding:** `tests/test_render_guarantee_50.py` (preflights :5433/:5432/:8200/:8890), `tests/test_multi_asset.py`, `tests/test_has_data_outage.py` (tunnel-down fingerprints); none for tunnel_monitor (gap).

### F8 — Adoption-complete flags whose code defaults contradict the certified production state (`emit.morphmap_mode`, `llm.guided_json.*`)
- **Files:** `layer2/emit/morphmap/mode.py:29` (`cfg("emit.morphmap_mode", "off")`), `layer1a/route_schema.py:52` and `layer1b/resolve/answer_schema.py:41` (`cfg("llm.guided_json.*", "off")`).
- **Evidence:** DB rows are `emit.morphmap_mode|on`, `llm.guided_json.route|on`, `llm.guided_json.asset_resolve|on` (adoption campaign 2026-07-07 certified both paths ADOPTED); code defaults remain `"off"` because `cfg()` is fail-open — so a cmd_catalog outage or a fresh unseeded environment silently reverts the pipeline to the *pre-adoption* emit contract and unguided routing (`app_config.py:23-24`: any DB error → `{}` → every default).
- **Failure mode:** cmd_catalog briefly unreachable at process start → `_load()` lru_caches the **empty** dict for process life (same poison shape as the fixed panel_members cache) → the host runs full-emit/unguided all day while telemetry says nothing failed; certification claims ("guided_json routing determinism") quietly don't hold in that degraded process.
- **Refactor:** two options, needs an owner call: (a) flip the code defaults to the certified `"on"` and keep the rows as kill-switches (one-line change each; behavior-identical while the DB is up); (b) if fail-open-to-off is intentional, add a TTL/never-cache-empty to `app_config._load()` (mirror `data/ttl_cache.py`) so an outage self-heals instead of pinning defaults for process life.
- **Risk:** medium. **Behavior-preserving:** NOT strictly — identical while cmd_catalog is reachable, changes the DB-down posture (that change is the point; flag for owner decision rather than silent inclusion in a behavior-preserving campaign).
- **Tests guarding:** `tests/test_morphmap_dp_gate.py`, `tests/test_morphmap_producer.py`, `tests/test_item17_guided_json.py`, `tests/test_route_guided_json.py` (all monkeypatch `_load`, so both default polarities are exercised).

### F9 — `app_config._load()` lru_cache can pin an empty config for process life (the already-fixed member-cache poison pattern, one layer down)
- **File:** `config/app_config.py:18-24`.
- **Evidence:** `@lru_cache(maxsize=1)` on `_load()` with `except Exception: return {}` — a single failed read at first touch (e.g. catalog restart, :5432 hiccup at host boot) caches `{}` forever; **every one of the 304 cfg() call sites** then serves code defaults until a manual `reload()` or process restart. The identical failure shape was just fixed for panel_members with `data/ttl_cache.py` + never-cache-empty (memory: v48-member-cache-poison, knob `cache.resolution_ttl_s=120`).
- **Failure mode:** host boots during a catalog restart → morphmap off, guided_json off, all 309 tuned rows ignored, silently, for days.
- **Refactor:** reuse the in-tree pattern: never cache an empty result (`if not rows: don't memoize`) and/or wrap in `TTLCache` keyed by nothing with `cache.resolution_ttl_s` — one small change in one file, no call-site edits. Keep `reload()` as-is.
- **Risk:** low. **Behavior-preserving:** yes while the DB is reachable (values identical; only the poisoned-process case changes, which is the defect).
- **Tests guarding:** `tests/test_config_cast_integrity.py`; most suites monkeypatch `_load` directly so the cache change is invisible to them (add one test: first-load failure then success → rows visible).

---

## Proposed canonical pattern (one paragraph)

**`cfg(key, code_default)` is the single knob API.** Rules: (1) scalar knobs live in `cmd_catalog.app_config`
only — migrate `__knob__:` viewer rows and scalar data_quality_policy rows behind shims (F6); (2) cfg() is
called **lazily** (accessor function or module `__getattr__`), never bound to a module constant at import
(F5); (3) env vars are reserved for *bootstrap/wiring that must work with the DB down*: DSNs
(`config/databases.py`), service endpoints (new `config/endpoints.py`, F7), and process-mode switches
(`V48_SKIP_LAYER2`, `V48_ALLOW_ENV_PIN`) — every such var is `V48_`- or subsystem-prefixed, read in exactly
one module, and consumers import the constant (F1's generic `LLM_URL`/`MODEL`/`TIMEOUT` reads are the
violations); (4) a knob has exactly one key — seed rows and readers are kept in lockstep by a seed-vs-reader
check (F3/F4 are the current drift); (5) observers derive from the same constants they observe (F2).

Deviating call sites, complete list: `ems_exec/renderers/_insight.py:48,65-68` (F1);
`llm/config.py:4-5` (F1 naming); `obs/ai_log.py:36` (F2); `host/exec_cards.py:18` (F4);
`config/windows.py:4-33`, `config/metrics.py:4-59`, `config/swap.py:4-6`, `config/intents.py:4`,
`config/validation.py:16-49`, `config/ems_backend.py:13-21`, `config/feasibility.py:30` (F5);
`config/viewer_policy.py:97-101`, `config/quality_policy.py:12,20`, `config/feeder_overview.py:30`,
`config/energy_balance_policy.py:44,57` (F6); `validation/config.py:13`, `host/server.py:46-47`,
`tools/tunnel_monitor.py:35`, `host/web/vite.config.ts:6-7,22` (F7); `copilot/validated.py:20` (F5 symptom);
DB rows `llm.prompt_v2`, `flags.*` ×3, `ems_backend.frame_budget_s` (F3).
