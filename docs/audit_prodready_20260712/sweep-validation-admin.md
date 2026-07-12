# Prod-readiness audit — lens: sweep/ + validation/ + admin/

Date: 2026-07-12 · Auditor: differential lens (sweep-validation-admin)
Scope: sweep/ (validation framework, renamed today), validation/ (compat alias), admin/ (Pipeline Explorer file-backed API :8790).
Method: read-only. Findings appended incrementally below.

## Ground truth: sweep/ vs validation/

- The ledger follow-up #1 rename **WAS executed** (by a concurrent session, per `validation/__init__.py:1-8`).
  - `sweep/` = the real package (cli, runner, corpus/, checks/, reports).
  - `validation/` = compat alias: `__path__ = sweep.__path__` + PEP-562 `__getattr__` → `sweep.*` (validation/__init__.py:10-19). One code home, no duplication.
  - Both `python3 -m sweep.cli` and `python3 -m validation.cli` load the same files.

## Positively verified OK (so far)

- **Corpus determinism**: `generate()` run in two fresh processes → 30,747 cases, identical sha1
  (`44851ce172bab666a558f536dd35b71583a36962`); on-disk `outputs/validation/corpus.jsonl` matches the same hash byte-for-byte (no drift).
- **DB ↔ mirror parity**: cmd_catalog `prompt_category` 18/18 enabled, `prompt_template` 42/42, `prompt_vocab` 95/95;
  content-diffed against `sweep/corpus/templates.py::defaults()` — categories, template rows, vocab values+meta ALL equal.
- **store.py fail-open**: live source='db'; empty/absent tables → `defaults()` (sweep/corpus/store.py:31-35). Confirmed by read.
- **admin :8790 process is NOT stale**: pid 557560 started **Jul 12 07:33** (after the last admin/ code edit 07:28),
  cwd = pipeline_v48; `/admin/api/health` → `{"ok": true, ..., "n_runs": 331}`.
- **No path traversal via run-id**: rid is a single URL path segment (server.py:79-81 splits on "/", no `unquote`
  anywhere in admin/), `store.files_for` joins `pat.format(rid=rid)` under fixed dirs — `..` can't pass the
  startswith/regex gate and `/` can't appear in a segment.
- `python3 -m validation.cli` and all sweep/admin modules py_compile clean; alias `from validation import config`
  returns the SAME object as `sweep.config` (PEP-562 __getattr__ path).
- runner session dirs: `config.session_dir()` creates `cases/` (sweep/config.py:54-57); runner creates `raw/` — no missing-dir crash.
- `python3 -m sweep.cli stats` works end-to-end (30,747 cases, source=db; off_domain 54<300 shortfall is by-design
  reporting, pool-limited); tests/test_prompt_corpus + 3 test_validation_* files collect (22 tests);
  tests/test_validation_runner_legs.py passes 3/3 offline (0.12s).
- `from validation import X` (the form the tests use) returns the SAME module objects as `sweep.X` — test
  monkeypatching is safe; only dotted `validation.x.y` imports duplicate modules (OBS-1).
- admin caching honors its size policy for AI logs: ai_usage._extract caches slim rows only (ai_usage.py:39-68);
  full bodies re-read on demand (trace.py:100-121); response docs cached as slim summaries (runs.py:12-46).
- sweep/replay.py never rewrites case records (writes only `raw/<id>.replay.json`) — admin's manifest-mtime session
  cache cannot go stale from replays.
- ops/SERVICES.md:12 + ops/v48-admin.service document/run :8790 (audit R4 follow-through confirmed).
- docs/testfw/TESTFW_HANDOFF_2026-07-12.md:5-6 carries an accurate compat-alias note (updated for the rename).

## Findings

### OBS-1 (medium, safe): sweep/cli.py still lazy-imports its own siblings via the compat alias name `validation.*`
- Evidence: sweep/cli.py:121-123 (`"validation.metrics"/"validation.coverage"/"validation.failures"`), :129
  (`validation.report_json/report_html`), :144 (`validation.corpus.generate`), :163 (`validation.corpus.store`),
  :208/:226 (`validation.replay`), :243 (`validation.regression`), :263 (`validation.coverage`), :294
  (`validation.checks.determinism`), :319 (`validation.checks.datesync`).
- The REAL package depends on its own compat alias. Two consequences:
  1. Dotted imports bypass PEP-562: verified `importlib.import_module('validation.metrics') is not sweep.metrics`
     — each sibling is loaded TWICE (two module objects, duplicate lru_caches → e.g. `cmd_stats` re-reads the
     prompt_* tables through a second `store()` cache).
  2. When validation/ is deleted per the alias's own plan ("New code must import sweep.*",
     validation/__init__.py:8), every `_call_flex` degrades FAIL-OPEN to a printed "note: ... unavailable" —
     `run` would complete with **no metrics/coverage/failures/reports, silently**.
- Also contradicts validation/__init__.py:13 ("their internal imports all point at sweep.*" — false for cli.py).
- Fix (safe): string-replace `"validation.` → `"sweep.` in sweep/cli.py (11 sites).

### OBS-2 (low, safe): ARCHITECTURE.md directory tree not updated for the validation→sweep rename
- ARCHITECTURE.md:187 lists `validation/` as "The WALL harness" in the tree (real dir is `sweep/`; `sweep/` absent
  from the tree); :505 and :783 same; yet :814 already says `python3 -m sweep.cli`. Half-updated doc.
- Similarly cosmetic: sweep/__init__.py:1, sweep/cli.py:1+351 (`prog="validation.cli"`), sweep/config.py:1,
  sweep/runner.py:1, sweep/corpus/*.py docstrings all still self-identify as `validation/...`.

### OBS-3 (high, safe): sweep/cli.py `_call_flex` call shapes drifted from the analyzers' real signatures — zeroed
### metrics/failures bundles, session artifacts stamped with ABSOLUTE PATHS, a dead `coverage` subcommand, and
### `determinism --session` silently dropped. ALL empirically confirmed.
The analyzers all take `session_id: str` (metrics.compute — sweep/metrics.py:73; coverage.analyze —
sweep/coverage.py:55; failures.collect — sweep/failures.py:80; report_json/report_html.build). The CLI's
"flexible-signature shim" (`_call_flex`, sweep/cli.py:26-43) probes shapes that DON'T include the plain
`(session_id,)` and treats an in-function TypeError as "try next shape". Confirmed consequences (sandboxed repro
+ live artifacts):
1. **Zeroed metrics/failures in the run bundle.** Shapes at cli.py:121-124 are `[(results,), (results, sdir), (sdir,)]`.
   `metrics.compute(results_list)` does NOT TypeError — `ascii_safe()` stringifies the list (sweep/response.py:20),
   `os.listdir(garbage-path)` → OSError → `([], 0)` → **returns cases=0 metrics "successfully"** and its
   `metrics.json` write fails silently (metrics.py:127-132). Same for `failures.collect(results_list)`
   (failures.py:82 uses `str(session_id)`) → **n_failures=0** even when the session has failures. Reproduced:
   fake session with 1 pass + 1 fail → `metrics: True cases=0`, `failures: True n_failures=0`, no json written.
2. **Every session artifact records the absolute dir path as its session id.** The correct on-disk numbers only
   materialize because `report_json.build((sdir,))` re-derives everything via `_load_or_build` — but it receives the
   ABSOLUTE sdir as `session_id` and `os.path.join(OUT_DIR,"sessions",<abs path>)` collapses to the abs path.
   Live proof: `outputs/validation/sessions/{smoke_1,compare_recheck}/{metrics,coverage,failures,report}.json` ALL
   have `"session": "/home/rohith/desktop/BFI/.../sessions/..."`. This breaks report.json's own charter
   (report_json.py:1-8: "compare byte-for-byte across runs") for any cross-machine/out-dir comparison.
3. **`python3 -m sweep.cli coverage` is dead.** cli.py:263 shapes are `[(results,), (results, sdir)]` — no
   `(sdir,)` fallback; both raise TypeError (analyze takes 1 positional) → always prints
   "coverage failed: signature mismatch". Confirmed by direct shape replay. The testfw handoff
   (docs/testfw/TESTFW_HANDOFF_2026-07-12.md:23) advertises this subcommand as working — claim NOT true.
4. **`determinism --session X` silently ignored.** `run_determinism(cases, repeats=3, *, session_id="adhoc")`
   (sweep/checks/determinism.py:82) has keyword-only session_id; cli.py:294-295 passes it positionally →
   TypeError → next shape `(sample, repeats)` binds → every determinism run lands in `sessions/adhoc`,
   colliding/overwriting across runs.
- NOT a rename regression: smoke_1 artifacts (02:54, pre-rename) already carry abs-path session fields — the drift
  shipped with the original build; the fail-open shim masked it. Fix (safe): make each shape list lead with
  `(session_id,)` (and `(case_id, session_id)` etc.), and let `_call_flex` distinguish binding-TypeErrors
  (`inspect.signature(fn).bind`) from in-function TypeErrors.

### OBS-4 (high, owner-gated): admin :8790 repeats the H2/H3 unauth/CORS surface — never assessed (security lens
### predates admin/)
- docs/audit_2026-07-12/security.md was finalized 02:29; admin/server.py landed 03:01 — grep "8790" in security.md
  = 0 hits. H2 lists :8770/:8772/:8899/:8200-8201 only.
- admin/server.py:166 binds `0.0.0.0:8790`, no auth; :40-42 `Access-Control-Allow-Origin: *`.
- POST `/admin/api/replay` (server.py:152-155 → admin/replay.py:37-55) lets ANY LAN host or any webpage in a LAN
  browser fire live `/api/run` pipeline executions (LLM compute, up to MAX_ACTIVE=2 × ~5 min each).
- GET `/admin/api/run/<rid>/ai/<idx>` (server.py:87-90 → trace.py:100-112) serves FULL LLM request/response bodies
  (prompts embed DB-derived plant data) unauthenticated.
- do_POST reads unbounded `Content-Length` into memory (server.py:147) — the same pattern the prior audit flagged
  for host/copilot.
- Fix: same disposition as H2/H3 (bind localhost / reverse-proxy auth); cap POST body size (that one is safe).

### OBS-5 (medium, safe): admin scaling debt vs the 30k corpus — unpaginated /admin/api/validation + unbounded parse cache
- admin/validation_log.py:48-77 `sessions()` returns EVERY judged case of EVERY session in one response (no limit
  param; server.py:125-127 passes none). Today: 48 cases/123KB (measured). A planned full-corpus sweep session
  (30,747 cases) → ~7-8MB JSON assembled per hit and held in `store._CACHE`.
- admin/store.py:14 `_CACHE` is path-keyed with no eviction: entries for deleted runs/sessions persist for the
  process lifetime; cache grows monotonically with run count (331 today and counting).
- Fix (safe): limit/offset on sessions cases (mirror runs.list_runs), drop cache entries whose path no longer exists.

### OBS-6 (low, safe): cmd_datesync's "availability probe" actually executes the check and ignores the result
- sweep/cli.py:319 `_call_flex("validation.checks.datesync", "check_response", [({},)])` — comment says "probe
  availability only" but it CALLS `check_response({})`, discards `ok`, then line 321 does a direct
  `from sweep.checks.datesync import check_response` which would raise anyway if the module were missing —
  contradicting the CLI's never-crash contract and loading the module under BOTH names (see OBS-1).
