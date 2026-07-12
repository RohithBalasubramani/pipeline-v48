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
