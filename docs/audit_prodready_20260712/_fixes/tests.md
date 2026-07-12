# Fix log — group: tests

Audit: docs/audit_prodready_20260712/tests-ci.md (TC-1/TC-2/TC-3/TC-5 == brief OBS-1/5/2/4) + refactor-integrity.md OBS-3.
Session start ~08:10, 2026-07-12. Appended per change.

## Pre-flight state

- `tests/test_asset3d_dg_seed.py` (refactor-integrity OBS-3): ALREADY FIXED by a concurrent session at 07:55 —
  `_MEDIA` now points at `host/web/public/media` (real dir, GLBs copied 07:42, dg_final_v2.glb present), zero
  pipeline_v45 references left, honest skip kept. Re-pointing at `backend/ems_backend/media` would churn a
  deliberate concurrent fix that already satisfies the finding (and the web root is what the host actually serves).
  → SKIPPED (no edit).
- `python3 copilot/tests/test_no_coupling.py` → "OK — no pipeline imports across 11 copilot modules" (baseline green).
- grep: no copilot module imports `lib`/`domain`/`knowledge`/`data` → FORBIDDEN additions keep the guard green.

## Changes

### 1. copilot/tests/test_no_coupling.py — TC-1 (OBS-1) + TC-2 (OBS-5)
- Split the guard body out of `main()` into `find_violations()` and added `def test_no_pipeline_coupling()`
  so pytest actually collects it (was 0 tests collected). Script mode (`python3 copilot/tests/test_no_coupling.py`)
  preserved byte-equivalent output.
- FORBIDDEN list: added the refactor-campaign homes created today — `lib`, `domain`, `knowledge` — plus `data`
  (TC-2 evidence: copilot has NO copilot-local data.py, so `import data` would silently bind the pipeline package);
  NOTE comment updated to stop excusing `data`. All retired names kept.
- Pre-verified via grep that no copilot module imports lib/domain/knowledge/data → guard stays green.
- Evidence: `python3 copilot/tests/test_no_coupling.py` → "OK — no pipeline imports across 11 copilot modules";
  `pytest -q copilot/tests/test_no_coupling.py` → 1 passed in 0.09s.

### 2. pytest.ini — TC-1 (OBS-1)
- `testpaths = tests copilot/tests` (+ 2-line comment). No basename collision between the dirs (checked).
- Evidence: `pytest --collect-only -q` → 1011/1048 collected, 37 live-deselected, 0.75s, ZERO errors;
  copilot/tests/test_no_coupling.py::test_no_pipeline_coupling now in the default lane.

### 3. tests/property/conftest.py — TC-5 (OBS-4)
- Wrapped the DB reads inside the two session snapshot fixtures (`page_snapshot`, `registry_snapshot`) in
  try/except → `pytest.skip(...)` with a machine-readable reason naming the unreachable endpoint. Fixture-level
  skip → only snapshot-dependent tests skip; pure property tests still run. DBs up → identical reads, same order.
- Evidence DBs UP: `pytest -q tests/property/test_prop_page_key_resolution.py` → 5 passed in 0.47s (unchanged).
- Evidence OUTAGE (env-simulated `CATALOG_PORT=1 PG_PORT=1`): the same file + an asset property file →
  **1 passed, 7 skipped in 0.28s** (was: a wall of psycopg2 ERRORS).

### 4. tests/test_regress_cfg_never_cache_empty.py — NEW — TC-3 (OBS-2a)
- 3 tests pinning config/app_config.py: failed load NOT cached (`_CACHE is None`, backoff armed); backoff window
  serves defaults without re-hitting the DB (call counter); self-heal after backoff (rewind `_LAST_FAIL`, never
  sleeps) + success IS cached. Seam: `data.db_client.q` (imported inside `_load`) monkeypatched.
- Evidence: part of `pytest -q ...cfg... ...ttl...` → 6 passed in 0.13s.

### 5. tests/test_regress_ttl_cache.py — NEW — TC-3 (OBS-2b)
- 3 tests pinning lib/ttl_cache.TTLCache: `.get()` never serves an expired value (the 2026-07-12 fix) and agrees
  with `in`; a write refreshes the entry clock; expired entries physically evicted on next write incl. `_ts` prune.
  Deterministic: module `time` binding replaced by a hand-advanced fake clock; TTL pinned via ctor (no DB knob read).
- Evidence: same run → 6 passed in 0.13s (with #4).

### 6. tests/test_regress_exec_budget.py — NEW — TC-3 (OBS-2c)
- 3 tests pinning host/exec_cards._run_cards ER-8 budget: a card parked on an Event past a 0.4s budget →
  {ok:False, why:'executor budget exceeded'}, absent from completed_by_id, and the call RETURNS (<5s wall, straggler
  abandoned; Event released at teardown so no thread outlives the test); healthy path all-complete unchanged;
  a raising fill degrades per-card, not fatally. Seams: EC.fill_one_card / EC._exec_budget_s /
  EC._special_handling_map monkeypatched; obs.stage.stage + obs.span.stage_span no-op'd (call-time imports).
- Evidence: `pytest -q tests/test_regress_exec_budget.py` → 3 passed in 0.52s.

### 7. tests/test_regress_llm_admission.py — NEW — TC-3 (OBS-2d)
- 3 tests pinning llm/client admission control: default 0 = disabled (sentinel `False`, wire call still runs) and
  the sentinel RE-RESOLVES per call (knob flip → BoundedSemaphore(n), then never replaced); cap=1 bounds
  max_in_flight to 1 across 4 threads (counting fake provider); admission wait fails OPEN (hostage holds the only
  slot, wait 0.05s → call proceeds, never-acquired slot NOT over-released — BoundedSemaphore would raise).
  Seams: LC._providers / LC._cfg / LC.llm_tap / LC._ADMISSION monkeypatched; `_call_qwen_raw` called directly.
- Evidence: `pytest -q ...admission... ...store...` → 7 passed in 0.80s.

### 8. tests/test_regress_store_never_cache_empty.py — NEW — TC-3 (OBS-2e)
- 4 tests pinning fix-12 poison legs: host/payload_store `_skeleton_payload` + `_raw_default_payload` — DB error
  NOT cached (retry self-heals), genuinely-absent row IS cached (no re-query); layer1b/compare/detect
  `_panel_alias_index` — a mid-stream generator failure never publishes the partial index, next call re-reads and
  publishes once. Seam: `data.db_client.q` monkeypatched; caches swapped for fresh dicts via monkeypatch.
- Evidence: same run → 7 passed in 0.80s (with #7).

## Skipped

- refactor-integrity OBS-3 (tests/test_asset3d_dg_seed.py `_MEDIA`): ALREADY FIXED by a concurrent session at
  07:55 (see Pre-flight); no edit made.

## Final gates (all green)

- `python3 -m py_compile` on all 7 edited/new .py files → OK.
- Each new/edited test file individually with `pytest -q`: coupling guard 1 passed; cfg+ttl 6 passed (0.13s);
  exec_budget 3 passed (0.52s); admission+store 7 passed (0.80s). Total NEW pins: 16 tests, all offline.
- `pytest --collect-only -q` → 1011/1048 collected, 0 errors, 0.75s (was 992/1029 — +16 regress + +1 coupling,
  +2 collected-but-live elsewhere from concurrent sessions).
- FULL property tier with DBs up (`PBT_EXAMPLES=20 pytest -q tests/property/`) → **44 passed, 9 deselected in
  176s** — the outage guard changes nothing on the healthy path.
- No service restarts, no DB writes, no commits.
