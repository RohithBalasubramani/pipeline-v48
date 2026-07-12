# Fixes — group: sweep (OBS-1, OBS-3, OBS-6)

Date: 2026-07-12 · Scope: sweep/*.py only (validation/ alias and tests/ untouched).
Source findings: docs/audit_prodready_20260712/sweep-validation-admin.md

## Change 1 — sweep/cli.py: `_call_flex` binds shapes via inspect.signature + optional kwargs [OBS-3]

- What: the shim now checks each shape with `inspect.signature(fn).bind(*args, **kwargs)` BEFORE calling; a
  TypeError raised INSIDE the analyzer is now a real reported failure, never a silent try-next-shape. Added an
  optional `kwargs` param (needed for determinism's keyword-only `session_id`). Non-introspectable callables
  (sig unavailable) call the first shape as-is.
- Why: the old shim treated in-function TypeErrors as shape misses, which masked every drifted call site below.

## Change 2 — sweep/cli.py: `_analyze_and_report` passes `(session_id,)` to metrics/coverage/failures and report builders [OBS-3.1, OBS-3.2, OBS-1]

- What: shapes were `[(results,), (results, sdir), (sdir,)]` / `[(sdir, bundle), (results, sdir), (sdir,), (bundle,)]`;
  now every analyzer/builder gets the single `(session_id,)` its signature declares (metrics.compute:73,
  coverage.analyze:55, failures.collect:80, report_json.build:118, report_html.build:203 — all `session_id: str`).
  Dropped the never-consumed `bundle` dict (only ever referenced by the dead shapes). Module names
  `validation.*` → `sweep.*` (5 sites here).
- Why (confirmed live): `metrics.compute(results_list)` "succeeded" with cases=0 and skipped its metrics.json
  write; `failures.collect(results_list)` returned n_failures=0; the only binding report shape `(sdir,)` stamped the
  ABSOLUTE session dir as the session id in every artifact.
- Evidence: before (real outputs/, untouched): smoke_1 metrics/coverage/failures/report.json all had
  `"session": "/home/rohith/.../outputs/validation/sessions/smoke_1"`. After, on a scratch COPY of smoke_1 with
  derived artifacts deleted (V48_VALIDATE_OUT=scratch), `python3 -m sweep.cli report --session smoke_1` rebuilt:
  metrics `{session: smoke_1, cases: 36, passed: 33, failed: 3}`, failures `{session: smoke_1, n_failures: 3,
  by_stage: {routing: [...3 ids]}}`, coverage `{session: smoke_1, pct: {...}}`, report sources all "ok",
  report.html written. Live session dirs never written (mtime of real smoke_1/metrics.json still 02:54).

## Change 3 — sweep/cli.py: `cmd_coverage` dispatches for real [OBS-3.3, OBS-1]

- What: shapes `[(results,), (results, sdir)]` (both non-binding → always "signature mismatch") → `[(sid,)]`;
  removed the now-unused `results = _load_results(...)` line; module `validation.coverage` → `sweep.coverage`.
- Evidence: `python3 -m sweep.cli coverage --session smoke_1` (scratch env) prints
  `coverage {'pages': 20.4, 'cards': 27.4, 'classes': 50.0, 'categories': 100.0}%` + uncovered counts, exit 0.

## Change 4 — sweep/cli.py: `cmd_determinism` restores `--session` pass-through [OBS-3.4, OBS-1]

- What: `run_determinism(cases, repeats=3, *, session_id="adhoc")` has keyword-only session_id; the old positional
  `(sample, sid, args.repeats)` never bound and the fallback `(sample, repeats)` dumped every run into
  `sessions/adhoc`. Now `_call_flex(..., [(sample, args.repeats)], kwargs={"session_id": sid})`.
- Evidence: `_call_flex("sweep.checks.determinism", "run_determinism", [([], 1)], kwargs={"session_id": "det_test"})`
  (empty cases → no network) → ok=True and `sessions/det_test/determinism.json` written at the requested id.

## Change 5 — sweep/cli.py: 11 lazy-import sites `"validation.*"` → `"sweep.*"` [OBS-1]

- What: `_analyze_and_report` (metrics/coverage/failures/report_json/report_html), cmd_generate
  (sweep.corpus.generate), cmd_stats (sweep.corpus.store), cmd_replay + cmd_replay_failed (sweep.replay),
  cmd_regress (sweep.regression), cmd_coverage (sweep.coverage), cmd_determinism (sweep.checks.determinism).
  cmd_replay also drops the unreachable wrong-shape fallbacks `[(case_id, sdir), (case_id,)]` (replay.py:56 is
  `replay(case_id, session_id, quiet=False)`) and the sdir local that only fed them.
- Why: dotted `validation.x` imports bypass the alias's PEP-562 `__getattr__` and load each sibling TWICE
  (two module objects, duplicate lru_caches); when validation/ is deleted per its own plan, every subcommand
  would degrade to "unavailable" silently.
- Evidence: after running `_analyze_and_report("smoke_1")` in-process, `sys.modules` contains ZERO `validation.*`
  entries. `prog="validation.cli"` (display string, OBS-2 cosmetic) deliberately left alone.

## Change 6 — sweep/cli.py: `cmd_datesync` real availability check [OBS-6, OBS-1]

- What: removed `_call_flex("validation.checks.datesync", "check_response", [({},)])` — it EXECUTED
  `check_response({})` and discarded the result while claiming "probe availability only", then imported the module
  directly under a second name anyway. Now one guarded `from sweep.checks.datesync import check_response`
  (try/except → honest `datesync unavailable: ...` + exit 1), placed after the raws early-exit so the no-raws path
  is unchanged.
- Evidence: `python3 -m sweep.cli datesync --session det_test` → "session det_test has no raw responses", exit 1
  (no traceback). Live /api/frame leg not driven (live-gated).

## Change 7 — sweep/report_json.py: `_load_or_build` imports `sweep.{module}` [OBS-1 class]

- What: line 37 `importlib.import_module(f"validation.{module}")` → `f"sweep.{module}"` (+ docstring word). Same
  double-load/fail-open-on-alias-delete defect as cli.py, in a file I own; audit's OBS-1 list covered cli.py only.
- Evidence: exercised via the scratch report rebuild in Change 2 (sources: metrics/coverage/failures all "ok").

## Shim semantics regression checks (Change 1)

- In-function TypeError: fake module fn raising TypeError("inside the function") → `ok=False,
  "... failed (TypeError: inside the function)"` (was: silently skipped to next shape).
- Non-binding shape: 3 args against 1-param fn → `ok=False, "... signature mismatch (TypeError: too many positional
  arguments)"` — the never-crash honest-note contract intact.

## Gates

- `python3 -m py_compile sweep/cli.py sweep/report_json.py` — OK.
- `python3 -m sweep.cli --help` — OK; `python3 -m sweep.cli stats` — 30,747 cases, source=db, no traceback.
- `python3 -m sweep.cli generate` (scratch OUT_DIR) — 30,747 cases; output byte-identical to the current on-disk
  corpus (sha1 ad87e497f45cfc6489de95fed534a3db390236ac both) — generate path behavior-unchanged.
- `python3 -m sweep.cli regress --baseline smoke_1 --session compare_recheck` (scratch) — runs, verdict ok, exit 0.
- `pytest tests/test_prompt_corpus.py tests/test_validation_regression.py tests/test_validation_runner_legs.py
  tests/test_validation_stagelogs.py -q` — 22 passed in 0.18s.
- Forbidden-ops check: no service restarts, no DB writes, no git add/commit, live outputs/ artifacts untouched.

## Skipped

- OBS-2 (cosmetic docstrings/prog= self-identifying as validation/, ARCHITECTURE.md tree) — not in the brief;
  ARCHITECTURE.md not owned by this group.
- validation/ alias itself (dotted-import duplication is inherent to `__path__`-alias design) — not owned.
- docs/testfw/TESTFW_HANDOFF_2026-07-12.md:23 advertises the coverage subcommand — claim is now TRUE again after
  Change 3; no doc edit needed (and docs/testfw not owned).
