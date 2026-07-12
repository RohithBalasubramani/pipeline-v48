# Production-Readiness Audit — Lens: tests-ci

Date: 2026-07-12
Auditor: differential lens agent (tests + CI state)
Scope root: /home/rohith/desktop/BFI/backend/layer2/pipeline_v48
Mode: READ-ONLY, differential vs docs/audit_2026-07-12/*, refactor ledger, unused-dupes apply log.

Checks: pytest.ini + collect-only health, marker discipline (offline tier truly offline),
incident-class regression tests present, CI wiring (systemd/cron/gh), copilot no-coupling
FORBIDDEN list currency, new test files added today.

## Status

- [x] pytest --collect-only run (992/1029, 0.72 s, 0 errors)
- [x] marker discipline grep (T2 fix verified; new files scanned clean)
- [x] incident regression tests inventory (TC-3: gaps on today's fixes)
- [x] CI wiring check (TC-4: none)
- [x] copilot no-coupling list vs today's moves (TC-1/TC-2)
- [x] targeted new-test runs: `pytest tests/test_statutory_band_per_class.py tests/test_payload_diff.py tests/test_decision_inspector.py -q` → **32 passed in 0.17 s**
- [x] stale ems_backend-path check in tests: none (all refs are logical endpoint/docstring mentions, no filesystem paths to the old pipeline_v45 location)

## Collection health (verified 2026-07-12)

- `pytest --collect-only -q` from repo root: **992 selected / 1029 collected, 37 live-deselected, 0.72 s, ZERO collection errors** (real 1.5 s wall). R8's claim ("1001 collect, 28 deselected, 0.69s") drifted only by the property live tier added since — consistent.
- `pytest.ini` exists (R8 executed): `testpaths = tests`, `addopts = -m "not live"`, `live` marker declared (pytest.ini:6-9).
- Concurrent full-suite run observed live (PID 560898: `pytest tests/ copilot/tests/ -q`); per instructions nothing else was read from it.

## Marker discipline (verified)

- All T2-flagged files now carry `@pytest.mark.live`: test_orchestrator.py:30, test_layer1a_routing.py:54-77, test_layer1b_asset_resolve.py:18-57, test_available_pages.py:25, test_render_guarantee_50.py:455/491, plus test_foundations/test_item21/test_layer1b_column_basket. 15 files use the marker.
- `test_render_guarantee_50` module-level matrix build is gated behind `V48_LIVE_CERT=1` (lines 182-201) — R8 claim TRUE.
- New-today test files (test_admin_console, test_decision_inspector, test_obs_trace, test_payload_diff, test_prompt_corpus, test_replay_engine, test_statutory_band_per_class, test_validation_*) scanned: no unmocked urlopen/requests/socket; `:8200` strings are fixture data; decision_inspector monkeypatches urlopen (line 169).
- tests/conftest.py now stubs `obs.sink_pg.write` session-wide so tests never write to the production obs_* store — good hermetic addition (conftest diff, today).

## Findings

### TC-1 — HIGH — copilot no-coupling guard NEVER runs under pytest: 0 tests collected
`copilot/tests/test_no_coupling.py` defines only `imported_names()` + `main()` — no `test_*` function, no pytest entry. Verified: `pytest --collect-only copilot/tests/` → "no tests collected". Additionally `pytest.ini testpaths = tests` excludes it from the default lane entirely. The concurrent session's full run (`pytest tests/ copilot/tests/`) silently gets zero coverage from it. The guard works ONLY when run as a script (`python3 copilot/tests/test_no_coupling.py` — verified exit 0 today). Fix: wrap `main()` body in a `def test_no_pipeline_coupling()` (safe, 3 lines).

### TC-2 — MEDIUM — FORBIDDEN list in the coupling guard is stale vs today's package moves
copilot/tests/test_no_coupling.py:16-24 forbids old/retired names (`workers`, `ems_compat`, `partition`, `contracts`) but NOT the two package homes CREATED today by the refactor campaign: `lib/` (ttl_cache/parallel/blank/dict_merge — the new shared-primitives home) and `domain/` (quantity_class/metric_affinity/asset_3d — the new kernel). Also `data` is excused by the NOTE ("copilot has its OWN config.py/llm.py/db.py") but copilot has NO own data.py — `import data` from pipeline root would resolve to the pipeline package and pass the guard. `knowledge` is also absent. A copilot module importing `lib.ttl_cache` or `domain.quantity_class` couples silently.
(Positive: the `layer1b`/`validate` strings in copilot/validated.py:21-23 are inside the subprocess `_CODE` string literal — the AST guard correctly does not flag them; ran the guard: "OK across 11 modules".)

### TC-3 — HIGH — Today's applied fixes 2/10/11/12 have ZERO regression tests (new code, new behavior, no pins)
The AUDIT_REPORT "Fixes Applied" (lines 197-234) landed behavior changes today with no accompanying tests:
- Fix 2 `lib/ttl_cache.py` (TTL-aware get, value-before-timestamp, eviction): `grep -rn "TTLCache|ttl_cache" tests/` → zero matches. T3's rec (test_ttl_cache.py) was NOT executed even as the code changed underneath.
- Fix 10 executor budget `host/exec_cards.py:20-22,171-227` (`as_completed` + deadline + honest-blank 'executor budget exceeded'): only test hit is tests/test_failures_fanout.py:34,52 which tests the failure-signal STRING classifier, not the timeout path. The C4-outage-completing fix is unpinned.
- Fix 11 admission semaphore `llm/client.py:117,211-213` (`_admission_sem`, `llm.admission_wait_s` fail-open): zero test references to admission/BoundedSemaphore/global_concurrency in tests/.
- Fix 12 cache-poison legs `host/payload_store.py` (_skeleton_payload never-cache-empty) + `layer1b/compare/detect.py` (publish-only-on-success alias index): zero test pins (test_multi_asset.py touches detect but not the poison behavior).
Cache-poison legs status: has_data leg PINNED (tests/test_has_data_outage.py:20,31,43 — 3 tests, modified today), panel_members leg still UNPINNED, neuract schema-probe leg (now data/neuract_pool.py present_columns TTL+never-cache-empty) UNPINNED (tests only stub present_columns, never test its cache). cfg never-cache-empty (fix 1) UNPINNED (conftest only cache_clears _load).

### TC-4 — HIGH — No CI runner of any kind (unchanged, now owner-gated): R8 delivered tiers, not CI
No `.github/` anywhere up the tree, `crontab` binary not even installed, systemd user units are services only (v48-host/admin/web + db-tunnel — ops/, verified via list-unit-files; no *.timer, no test/ssr-gate unit). ops/SERVICES.md has no test/CI mention. The offline tier is now cheap (992 tests, collection 0.72 s) and hermetic enough to host in a systemd --user timer on this box; the ssr-gate (`npm run ssr-gate`) is also still invoked by nothing (T4 unchanged — only docstring mention in tests/test_multi_asset.py:3). Owner call: where to host (systemd timer on dev box vs future forge CI).

### TC-5 — MEDIUM — The property suite's "offline" tier requires BOTH live DBs at session start (no outage skip-guard)
tests/property/conftest.py:41-69: session fixtures `page_snapshot` (read_page_specs/read_card_titles/read_page_feasibility → cmd_catalog :5432) and `registry_snapshot` (asset_candidates → :5432; `tables_with_values` → live neuract **:5433 value probe**) do real DB reads with NO try/skip guard — unlike the live tier's `qwen_live` which properly skips (conftest.py:165-173). On a machine without the tunnel, the "offline" property tier ERRORS (a wall of psycopg2 errors), the exact fake-red T8 warned about, re-introduced in a package built today AFTER that lens. The fake-LLM claim is true (call_qwen holder-faked); the no-services claim implied by pytest.ini's comment ("a plain pytest runs green with no services", pytest.ini:4) is FALSE for tests/property/. Fix: wrap both session snapshots in try/except → `pytest.skip` with a machine-readable reason (safe).

### TC-6 — LOW — pytest.ini comment overclaims the offline lane contract
pytest.ini:4-5 says the default lane "runs green with no services". Besides TC-5, the long-known unmarked cmd_catalog readers (T5/T8, e.g. tests/test_foundations.py:12-25 exact-count asserts `cards == 136 and pages == 68`, unmarked) still hard-require :5432. Not re-reporting T5/T8 themselves — the NEW issue is that today's pytest.ini codified a contract the suite doesn't meet, which will burn the first CI adopter (TC-4). Either soften the comment or land T8's shared skip-guard.

## Verified OK (differential confirmations)

- pytest.ini exists with offline-default addopts + testpaths (T1 pytest-config half EXECUTED).
- T2 marker fix EXECUTED: all 9+ flagged live tests now marked; 37 live-deselected at collect.
- R8 collection-hang fix TRUE: render-guarantee matrix gated on V48_LIVE_CERT; full collect 0.72 s, zero errors.
- T6 EXECUTED: all 10 permanent-skip stub files deleted (verified ls: test_invariants, test_contracts_roundtrip, test_layer2_metadata_byte_identical, etc. all gone).
- T7 partially closed: validation/ now has 4 test files (test_validation_regression/runner_legs/stagelogs/test_prompt_corpus); obs/ now has test_obs_trace + test_decision_inspector + test_admin_console.
- conftest obs.sink_pg.write stub — production obs store protected from test writes.
- copilot/validated.py pipeline imports are subprocess-string-only; AST guard honest (ran clean, 11 modules).
- has_data cache-poison leg: 3 tests incl. never-cache-outage (test_has_data_outage.py, extended today).
- New-today test files contain no unmocked network calls.
- tests/test_layer2_card.py /tmp/l2_inputs.json skip-dependency unchanged (T9 still open, not re-reported).

