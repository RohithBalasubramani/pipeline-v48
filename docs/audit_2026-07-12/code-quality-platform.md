# Code Quality Audit — Platform Lens (data / config / registries / llm / obs / run / partition / services / outputs / knowledge / grounding / validate / validation / tools / copilot)

Date: 2026-07-12 · Auditor lens: code-quality-platform · Scope: pipeline_v48 shared platform + guards + copilot
All file:line references were read directly during this audit.

**IMPORTANT SNAPSHOT CAVEAT:** the `obs/` directory was being actively modified by a concurrent session
*while this audit ran* (obs/span.py, llm_tap.py, db_tap.py, middleware.py, query.py, sql_trace.py, and rewrites
of bus.py/event.py/sinks appeared with mtimes minutes old, all untracked `??` in git). Findings on obs/ are
scoped to what is committed + what the in-flight state implies (F7).

## Overall assessment

This platform layer is in much better shape than most "AI pipeline" codebases: files are genuinely
single-purpose, docstrings capture *why* (incident IDs, defect references), fail-open telemetry vs fail-fast
data is applied consistently, and the DB-driven-config-with-code-default pattern is pervasive and disciplined.
`run/parallel.py`, `run/degrade_gate.py`, `knowledge/ems.py`, `data/ttl_cache.py`,
`data/lt_panels/panel_members.py`, `llm/client.py`, and `validation/response.py` are exemplary small modules.
`validate/leaf_classify.py` is genuinely shared by 20+ consumers instead of being re-implemented.

The real debt is concentrated in four places: (1) the **telemetry identity layer** (global mutable run_id +
urlopen monkeypatch + colliding run ids) silently corrupts the very logs the replay/cert tooling treats as
ground truth; (2) the **config spine** (`cfg()`) violates the project's own never-cache-empty lesson and is
frozen at import time by 7 modules; (3) **DB access** exists in three idioms, the hottest being a
psql-subprocess-per-query API that cannot parameterize — which is why the same one-line `_esc` SQL escaper is
copy-pasted 18 times; (4) the **copilot** re-implements platform pieces (db door, LLM client, config, caching)
with small semantic drifts, one of which re-introduces the exact cache-poison bug class the main pipeline
fixed on 2026-07-09.

---

## HIGH severity

### F1. AI-call telemetry is mis-attributed under concurrency and collides across executions
- `obs/ai_log.py:8` — `_RUN_ID = "default"` is a mutable **module global**; `set_run_id` (`:13-15`) mutates it;
  every :8200 request is appended to `outputs/logs/ai_{_RUN_ID}.jsonl` (`:49`).
- `obs/ai_log.py:56` — `urllib.request.urlopen = _logged` monkeypatches urlopen **process-wide at import**
  ("Import FIRST" ordering contract in the docstring).
- `host/server.py:29` — the host is a `ThreadingHTTPServer`; `:102` calls `run_pipeline` per request, and
  `run/harness.py:187` / `:107` call `ai_log.set_run_id(...)` on the global. Two concurrent `/api/run`
  requests cross-label each other's LLM calls into the wrong file.
- The external cert framework runs at concurrency 2-3 by default (`validation/config.py:17-18`) and explicitly
  says it "correlate[s] by run_id" (`validation/config.py:34`) — so during every sweep the primary AI forensic
  log is systematically interleaved/mislabeled.
- Compounding: `run/run_id.py:5-7` — run_id = sha1(prompt)[:10], **collides across executions by design**, so
  `ai_<rid>.jsonl` / `pipeline_<rid>.jsonl` append records from different executions into one file.
- Consumers that treat these files as ground truth: `tools/wall_corpus_replay.py` (basket reconstruction from
  logged prompts), `tools/morphmap_ab.py:49`, `tools/replay_item17_guided_asset_resolve.py:76`,
  `obs/failures.py` correlation via `llm/client.py:73` (`getattr(ai_log, "_RUN_ID", "default")`).

**Why it matters:** the render-guarantee acceptance harnesses replay these logs; mixed-run records mean gate
regressions can be judged against another run's basket. `trace.py` (uuid4 trace_id) exists to fix identity,
but the file sinks still key on the colliding global run_id.

**Fix:** carry run_id in a `contextvars.ContextVar` (the pattern `obs/trace.py:16` already uses), key log
records with both run_id and trace_id, and prefer instrumenting `llm/client.call_qwen` (the single call
convention) over a process-wide urlopen patch. Coordinate with the in-flight `obs/llm_tap.py` work.
*Severity: High. Risky (log file layout consumed by replay tools).*

### F2. The config spine caches an empty load forever and 7 modules freeze knobs at import time
- `config/app_config.py:18-24` — `_load()` is `@lru_cache(maxsize=1)` and returns `{}` **on any error, which is
  then cached for the process lifetime**. A cmd_catalog blip at first `cfg()` call (e.g. local Postgres
  restarting while the host boots under systemd) silently pins *every* DB knob (~89 importing files: timeouts,
  guards, reflect policy, scrub vocab, TTLs) to code defaults until a manual restart/`reload()`. No telemetry
  records that the load failed.
- This is the exact bug class the project already paid for: `data/ttl_cache.py:1-16` (poison-permanent-fix
  2026-07-09) and `data/lt_panels/panel_members.py:62-67` ("DO NOT CACHE an empty result") encode
  never-cache-empty — but the config spine itself violates it.
- Worse, 7 config modules resolve `cfg()` into **import-time module constants**, so even `reload()` cannot
  refresh them: `config/intents.py:4-5`, `config/windows.py:4-33`, `config/validation.py:16-46`,
  `config/swap.py`, `config/metrics.py`, `config/feasibility.py`, `config/ems_backend.py`. The documented
  promise "editing the row changes behavior with no code change" (`app_config.py:43-44`) silently fails for
  these keys.

**Fix:** (1) never cache a failed/empty load — retry on next call (or a short TTL via the existing TTLCache);
(2) emit one `obs.failures` record when `_load()` falls open; (3) convert the 7 import-time constant modules
to accessor functions (mechanical, matches the other 20+ config modules).
*Severity: High. Mostly safe; touching import-time constants is a behavior-preserving refactor with wide import fan-out.*

### F3. Three parallel DB clients; the hottest path is a psql subprocess per query
- `data/db_client.py:11-21` — `q(db, sql)` shells out to `psql --csv` per query: a process spawn + fresh TCP
  connect for **every** read, rows come back as all-text CSV (each caller re-parses bools/ints, e.g.
  `data/registry/lt_mfm.py:49-50` `_bool`), and there is no parameter binding.
- ~75 files import `q()` (layer1a db_reads, layer1b resolve, layer2 catalog, config readers, partition,
  grounding, validation corpus...). It runs on every request's routing/validation path.
- Meanwhile a proper pooled, parameterized psycopg2 door already exists — `registries/neuract/_db.py:29-65`
  (thread-safe pool, `%s` params, honest-degrade) — but only `registries/neuract/*` uses it.
- Third idiom: raw `psycopg2.connect(dbname=..., user=...)` in `validate/payload_lookup.py:13` and `:32` —
  opens a **new connection per card per validation pass** and bypasses `conn_env()` routing entirely
  (`config/databases.py:73-83`), so CATALOG_HOST/PORT overrides silently don't apply to it. `data/db_client.pg_connect`
  exists precisely for this (`db_client.py:24-32`) and is unused here.

**Fix:** promote one pooled parameterized read door (generalize `registries/neuract/_db.py` to accept a db
name routed via `conn_env`), migrate `q()` call sites behind a compatible shim, and route
`validate/payload_lookup.py` through it first (hot path, wrong routing).
*Severity: High (scaling wall + consistency). Risky — hot path, but behavior-preserving.*

### F4. The same one-line SQL escaper is defined 18 times; three escaping idioms coexist
`def _esc` (i.e. `str(s).replace("'", "''")`) is duplicated in:
`config/derivation_binding.py:75`, `config/quality_policy.py:36`, `config/metric_class.py:27`,
`config/viewer_policy.py:109`, `config/reason_templates.py:53`, `config/asset_class_defaults.py:138`,
`config/nameplates.py:285`, `config/event_thresholds.py:122`, `config/energy_balance_policy.py:75`,
`config/schema_map.py:52`, `config/feeder_overview.py:51`, `data/equipment/ratings.py:40`,
`data/equipment/kitpreview.py:157`, `grounding/schema_fingerprint.py:47`, `grounding/meaningful.py:32`,
`grounding/default_assemble.py:138`, `layer2/emit/metadata/asset_3d.py:228`,
`ems_exec/derivations/expressions.py:14`.
Alongside it: `$k$...$k$` dollar-quoting in `partition/fallback_edges.py:7`, and raw un-escaped f-string
interpolation of identifiers (`layer1b/basket/col_dict.py:41`, `validate/data_load.py:25`).

Interpolated values today are mostly internal (catalog page keys, registry table names, int ids), so
exploitability is low — but the pattern guarantees a future call site forgets the escape, and 18 copies of a
helper is exactly the drift the atomic-structure rule exists to prevent. This is a downstream symptom of F3
(`q()` cannot parameterize).
**Fix:** parameterized door (F3), then delete every `_esc`. Until then: one shared `db_client.esc()`.
*Severity: Medium-High (counted High here for the compounding with F3). Safe.*

---

## MEDIUM severity

### F5. `validate/` vs `validation/` vs `config/validation.py` — three "validation" namespaces
- `validate/` = the in-pipeline pre-L2 pass + render verdicts (`validate/build.py:1-13`).
- `validation/` = the external black-box HTTP cert framework (`validation/cli.py:1-7`).
- `config/validation.py` = the knobs **for the first one**, imported as `from config.validation import FAILURE_POLICY`
  (`validate/build.py:17`).
The roles are genuinely different, but only docstrings distinguish them; operators, new agents, and grep all
conflate them (the env vars are even prefixed `V48_VALIDATE_*` for the *framework*, `validation/config.py:13-28`).
**Fix:** rename the external framework dir to `certify/` or `sweep/` (mechanical import rename, it's
self-contained by design), or at minimum cross-referencing README stubs in both dirs.
*Breaking (import paths) but fully mechanical.*

### F6. `_NAME_CLASS` asset-class pattern table duplicated between the resolver and the cert corpus
- `layer1b/resolve/asset_candidates.py:32` (the authoritative resolver fallback vocabulary)
- `validation/corpus/universe.py:14-21` (explicitly "mirror[s] layer1b's name-pattern fallback", `:3-5`)
When they drift, the corpus generates prompts under a class the resolver assigns differently → false sweep
failures/passes that look like routing regressions. **Fix:** hoist the table into one shared single-purpose
module (or a cmd_catalog row, matching DB-driven config) and import it from both. *Safe.*

### F7. The new obs trace layer is half-wired, entirely uncommitted, and does runtime DDL
- At git HEAD the committed `obs/trace.py:127-128` emits through `from obs import event, bus`; the bus, event
  envelope, span, taps, sinks, middleware and query modules are all **untracked** (`git status`: `?? obs/bus.py
  ?? obs/db_tap.py ?? obs/event.py ?? obs/llm_tap.py ?? obs/middleware.py ?? obs/query.py ?? obs/redact.py
  ?? obs/sink_console.py ?? obs/sink_jsonl.py ?? obs/sink_pg.py`), written minutes before this audit by a
  concurrent session.
- Grep across the tree: `run_traced`/`stage_span`/`llm_tap`/`db_tap` are referenced outside obs/ only by
  `ems_exec/data/neuract.py` — `host/server.py` does not call `obs/middleware.run_traced` yet, so no trace is
  ever opened; the whole layer (bus → sinks incl. `obs_traces` Postgres rows) is currently unreachable.
- `obs/sink_pg.py:63-76` executes `db/obs_schema.sql` DDL lazily from the first runtime write — schema
  migration on the request path, default-on (`obs/bus.py:46` `_on("obs.sink.pg", True)`).

**Fix:** land the layer atomically (wiring + tests + commit in one change); flip `obs.sink.pg` default-off
until certified; move DDL bootstrap to an explicit ops step. A deploy from git today silently loses ~700 LOC
of in-flight observability. *Severity: Medium (process + integration risk). Safe.*

### F8. Copilot re-implements platform pieces with drifted semantics
- `copilot/db.py:15-32` — a psql-CSV subprocess twin of `data/db_client.q`, but with its own routing rule
  (only `DATA_DB` goes to the tunnel, `:24-25`) and **no `PGCONNECT_TIMEOUT`** — a half-dead :5433 tunnel hangs
  copilot build steps for the OS TCP timeout (~2 min), the exact failure `config/databases.py:76-80`
  documents fixing for the main pipeline.
- `copilot/llm.py:24-25` — sends the legacy `guided_json` extra-body param, which `llm/client.py:112-114`
  documents as "silently IGNORED" by vLLM 0.16.1; no copilot caller passes it (grep) — a dead, misleading kwarg.
- `copilot/config.py` — env-var config only, a second config idiom vs `cfg()` (defensible under the standalone
  mandate, but undocumented as a deliberate divergence).
**Fix (minimal, keeps the no-import mandate):** add PGCONNECT_TIMEOUT to `copilot/db.py`; delete the
`guided_json` kwarg; note the deliberate divergences in `copilot/README.md`. *Safe.*

### F9. `starters._CACHE` re-introduces the cache-poison class fixed on 2026-07-09
- `copilot/starters.py:16` `_CACHE = None`; `:53-55` returns it forever once set; **`:84-91` assigns the
  deterministic fallback roster into `_CACHE` on the model-down path**.
- `copilot/server.py:106-114` warmup thread calls `starters.starters()` at boot — so if :8201 is still loading
  when the copilot starts (typical after a host reboot: both units start together), the fallback roster is
  pinned until process restart.
- The suggest cache 40 lines up encodes the opposite, correct rule with a full rationale comment
  (`copilot/server.py:41-49`: "NEVER cache an 'unavailable'/error response").
**Fix:** don't assign `_CACHE` on the fallback path (return without caching), or wrap in a TTL. *Safe, 3 lines.*

### F10. The copilot coupling guarantee doesn't scan what it claims
- `copilot/tests/test_no_coupling.py:44` — `os.listdir(ROOT)` is non-recursive: `build/` (13 modules) and
  `tests/` are never scanned, while the docstring (`:1-4`) claims "Scans every .py in ems_copilot".
- `copilot/validated.py` and `build/assets.py` import `layer1b`/`validate` inside subprocess `python -c` code
  strings — invisible to AST scanning by design, but that means the guarantee is import-shaped only and the
  README/test wording oversells it.
**Fix:** `os.walk` instead of `listdir`; state the subprocess exception explicitly. *Safe.*

### F11. `copilot/build/__init__.py` mutates sys.path and the copilot's bare module names shadow pipeline packages
- `copilot/build/__init__.py:36-38` — `sys.path.insert(0, <copilot dir>)` at import, so the sub-modules' bare
  imports (`import config`, `import db`, `import llm`) resolve. Because copilot/ ships top-level modules named
  `config.py` and `llm.py` — the same names as the pipeline's `config/` and `llm/` packages — any process that
  ever imports `copilot.build` (or adds copilot/ to path) will have every later `import config` resolve to the
  copilot's, silently breaking the main pipeline in-process.
- Same file: the barrel re-exports ~20 underscore-private names in `__all__` (`:40-91`), and carries a dead
  `if __name__ == "__main__": main()` (`:94-95`) that can never fire in an `__init__.py` (`__main__.py` exists).
**Fix:** rename the copilot's bare modules (e.g. `cp_config`, `cp_db`) or convert to package-relative imports;
drop the private re-exports and the dead block. *Risky only inside copilot; zero pipeline behavior change.*

### F12. Unbounded file telemetry + code living in the artifacts directory
- `outputs/` is 488 MB with 864 files under `outputs/logs/` alone; `obs/ai_log.py:49` and `obs/stage.py:17`
  append forever with no rotation/retention anywhere, keyed by the colliding run_id (F1) so files also grow
  across executions.
- `outputs/emit_correctness_battery.py:1-14` is a real, git-tracked test harness living in the run-artifacts
  dir (it even sys.path-hacks its way back to the root, `:14`), amid 20+ worklog `.md`s and cert artifacts.
**Fix:** a retention knob (`obs.log_retention_days`) + a tiny prune step in `tools/stack_monitor.sh` or cron;
move `emit_correctness_battery.py` to `tools/` or `tests/`. *Safe.*

### F13. cfg()-replaces-not-merges vocab drift is solved for exactly one vocabulary
- `tools/seed_quantity_vocab.py:3-9` exists because "cfg() REPLACES ... The DB rows had DRIFTED behind the
  code default" — a real incident. The identical replace-not-merge hazard applies to every other seeded vocab:
  `role_scrub.*` (code defaults inline at `grounding/role_scrub.py:48-80`, seed in `db/seed_role_scrub_vocab.sql`),
  `validation.*`, gates vocab — none has a seeder or drift check.
- Broader context: `db/` holds 88 hand-applied SQL files including 12 `fix_*`/`patch_*` one-offs with no
  applied-state tracking — rebuilding cmd_catalog from scratch is archaeology.
**Fix:** generalize the seeder into one registry-driven `tools/seed_vocab.py` (key → code-default source) plus a
pytest that diffs DB rows vs code defaults and warns on drift; adopt a numbered-migration convention for new
`db/` files. *Safe.*

### F14. `tools/wall_corpus_replay.py` (532 lines) parses "three historical header dialects" — unversioned log schema
- `tools/wall_corpus_replay.py:1-41` — the acceptance harness for *every* gate change reconstructs column
  baskets by regexing archived prompts across three historical formats; it is the largest file in the audited
  area and mixes corpus parsing, basket reconstruction, gate replay, and two report writers.
**Fix:** stamp a `schema`/version field into the emit-log record now (one line in ai_log/llm layer) so the next
dialect is dispatch, not regex archaeology; split parse/replay/report when next touched. *Safe.*

---

## LOW severity

### F15. Domain math lives under config/: `config/nameplates.py`
`config/nameplates.py:167-199` (`derive_ratings`: kVA→kW/A, L-L→L-N √3 conversion), `:251-259`
(`capacity_utilization`) are real derivation logic (ported from backend2) in a namespace otherwise reserved
for thin cfg()/row readers. Coherent and well-documented, but it breaks the "config = readers" convention and
is the file a physics bug would hide in. Consider `ems_exec/derivations/` as its home. *Safe move.*

### F16. Operator tools hardcode policy that is DB-driven elsewhere
- `tools/cert_fire18.sh:3-6,41,61` writes artifacts to `/tmp/cert18` + `/tmp/cert_routed.tsv` (against the
  outputs/ convention; lost on reboot) and hardcodes the 18 prompts + expected page map in the script, while
  `config/prompt_matrix.py` exists precisely to hold test-prompt policy rows.
- `tools/morphmap_live_ab.py:17` — fabrication scan = hardcoded literal list
  `SEEDS = ["1500", "2700", "389.2", ...]`; goes stale the day card_payloads is re-seeded.
*Fix: point both at DB rows (prompt matrix / a seed-markers row). Safe.*

### F17. `partition/` is not self-contained
`partition/coupling_lookup.py:2-5` imports four readers from `layer1a/partition_inputs/*` — the "shared"
partition subsystem depends on a specific layer's internals. Either the readers belong in partition/ or
partition/ belongs in layer1a. One-direction move, no logic change. *Safe.*

### F18. Copilot repo hygiene + dead DDL
- 10 PNG screenshots are git-tracked inside `copilot/` (git ls-files: `copilot-demo.png`, `v48-*.png`).
- `copilot/build/schema.py:10-11` DROPs `templates` and `query_log` tables that no statement creates and no
  code reads/writes — remnants of a removed design. *Safe deletions.*

### F19. `registries/neuract/_db.py` pool is a single shared connection; broken connections leak
`registries/neuract/_db.py:20` — the "pool" is one psycopg2 connection per frozen-DSN key shared by all
threads: concurrent metadata reads serialize on it (psycopg2 connections are thread-safe but execute
serially), and on error the connection is popped from the pool without `close()` (`:60-65`, `:79-84`).
Fine at current volume; revisit when this door takes over from `q()` per F3. *Safe.*

### F20. The lazy fail-open `_cfg` wrapper is duplicated ~14×
`def _cfg(key, default): try: from config.app_config import cfg ...` appears in `llm/client.py:51`,
`obs/bus.py:10`, `obs/event.py:17`, `obs/sink_pg.py:22`, `obs/db_tap.py:12`, `obs/llm_tap.py:10`,
`config/nameplates.py:24`, and 7 ems_exec modules. It exists to dodge circular imports; a single
`config.app_config.cfg_safe(key, default)` (import-lazy inside) would remove all copies. *Safe.*

---

## Explicitly checked and found fine
- `validate/schema.py` is NOT dead: `_schema_issues` is consumed by `layer2/build.py` (grep verified).
- `services/dict_merge.py` twin of the ems_backend copy is deliberate and documented (Django-free import), pure, correct.
- `data/equipment/*` plain `_CACHE` dicts: local :5432 source, failures explicitly never cached
  (`data/equipment/db.py:39-42`) — the tunnel-poison hazard does not apply.
- `data/ttl_cache.py`, `data/lt_panels/panel_members.py` — the 2026-07-09 poison fix is real and correctly scoped.
- `run/harness.py` at 352 lines is commentary-heavy but structurally clean (policy is knob-driven, no card/page vocabulary).
- `knowledge/ems.py`, `run/degrade_gate.py`, `run/parallel.py`, `validation/response.py`, `validation/config.py` — clean.
- `validation/cli.py:_call_flex` (`:26-44`) is overly defensive (a TypeError inside an analyzer renders as
  "signature mismatch" note) but it re-raises non-TypeError exceptions as explicit failure notes — kept out of
  the top findings as an internal-tool tradeoff the docstring owns.
