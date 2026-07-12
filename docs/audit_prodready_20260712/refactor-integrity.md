# Production-readiness audit 2026-07-12 — Lens: refactor-integrity

Differential check that the 2026-07-12 refactor campaign (batches 0-7) + unused-dupes dedup left no
dangling imports, broken facades, copy-drift, or half-applied moves. READ-ONLY audit; nothing edited.

Scope checked:
- compileall over the tree (excluding archive/, outputs/, host/web node stuff)
- old import paths: partition→layer1a/partition, services/dict_merge→lib/dict_merge,
  layer2/emit/data→layer2/emit/instructions, layer2/gates.py→layer2/gates/,
  ems_exec/executor/fab_guards.py→fab_guards/
- sys.modules-alias facades (identity-preserving re-exports, _ROWS_CACHE same-dict)
- lib/ homes vs old locations (blank, dict_merge, ttl_cache, parallel, leaf_paths)
- domain/ kernel facades (quantity_class, metric_affinity, asset_3d)
- import-resolution of ~15 entrypoint modules

Status: COMPLETE (4 findings: 1 medium doc-drift, 3 low; refactor batches 0-7 structurally verified sound)

## Positively verified OK (as of this audit run)

- `python3 -m compileall -q .` (excl. archive/outputs/host-web) — ZERO syntax errors, exit 0.
- `pytest --collect-only -q` — 992/1029 collected, 37 deselected, ZERO collection errors.
- Old import paths are GONE tree-wide (grep, excl. archive): no `import partition` (root),
  no `services.dict_merge` / `import services`, no `layer2.emit.data`. `layer2/gates.py`,
  `ems_exec/executor/fab_guards.py`, `layer1b/guardrail/retry_one.py` files deleted as claimed.
- fab_guards package (`ems_exec/executor/fab_guards/__init__.py:59-71`) re-exports the original
  surface; `_ROWS_CACHE` defined ONCE in `class23_source.py:12` and re-exported by from-import
  (same dict object — tests' `G._ROWS_CACHE.clear()` hits the live cache).
- sys.modules-alias facades all correct (alias, not copy): `ems_exec/executor/blank.py`→lib.blank,
  `ems_exec/executor/paths.py`→lib.leaf_paths, `run/parallel.py`→lib.parallel,
  `layer2/quantity_class.py`→domain.quantity_class, `layer2/emit/metadata/asset_3d.py`→domain.asset_3d.
  Each is a 3-line `sys.modules[__name__] = _home` — underscore names + monkeypatch identity preserved.
- `data/ttl_cache.py` is a re-export facade of `lib/ttl_cache.py` (follow-up #2 WAS executed);
  no consumer imports underscore names through the old path (grep: only `TTLCache`, which `import *`
  + explicit re-export both carry).
- domain/ kernel real: `domain/{quantity_class,metric_affinity,asset_3d}.py`; metric_affinity
  consumers (`layer2/swap/candidates.py:25`, `grounding/swap_settle.py:69`) import domain directly;
  no copy left in layer2.
- D1 neuract-pool dedup GENUINELY done: `data/neuract_pool.py` is the one pool; both
  `ems_exec/data/neuract.py:20` and `registries/neuract/_db.py` import `data.neuract_pool as _pool`.
- layer2/build.py split wiring intact: build.py:26-30 imports window_backfill/reconcile_slots/
  cross_domain with `# noqa: F401` re-exports; call sites use the imported names.
- Endpoint home (config F7): `config/endpoints.py` exists; `sweep/config.py:13`,
  `admin/config.py:15`, `tools/payload_diff/capture.py:13` all import HOST_BASE from it.
- New homes present: `llm/transient_retry.py`, `config/policy_read.py`, `layer1b/how.py`,
  `lib/dict_merge.py`, `scripts/seed_quantity_vocab.py`, `scripts/seed_schema_and_endpoints.py`,
  `ops/tunnel_monitor.py`.
- Entry-point import matrix (python3 -c import, repo root): host.server, admin.server, run.harness,
  validation.cli, obs, obs.query, replay, profiler, knowledge, layer1a, layer1b, layer2, ems_exec,
  grounding, validate, lib, domain — ALL import clean. (copilot.server fails BY DESIGN — see OBS-2.)
- `validation/` → `sweep/` rename (ledger follow-up #1) WAS executed by a concurrent session;
  `validation/` is a compat alias package; `python3 -m validation.cli` and `from validation import X`
  resolve to sweep files.
- ems_backend move: old path `backend/layer2/pipeline_v45/ems_backend` is a compat SYMLINK →
  `../../ems_backend` (created 07:28 today), so relative-path consumers still resolve.
- README.md tree section reflects the post-refactor tree (layer1a/partition, lib/, sweep/-era wording).

- Behavioral smoke: `pytest tests/test_fab_guards.py -q` → 39 passed in 0.22s (exercises the
  fab_guards/ package split + the paths facade through real fill()).
- `tools/wall_corpus_replay.py:57-60` module-purge hack is facade-safe (purges only layer2 modules
  whose `__file__` is OUTSIDE the repo root; the domain-aliased modules live under root → kept).
- copilot/server.py flat imports (`import generate/llm/retrieve`) are BY DESIGN: the unit
  `copilot/deploy/ems-copilot.service:12-13` sets WorkingDirectory=…/copilot + `python3 server.py`.
  `python3 -m copilot.server` from repo root fails fast (ModuleNotFoundError: generate) — it is not
  a supported entrypoint; no silent llm-package shadowing possible (generate fails first).
- No merge-conflict markers tree-wide (py/md/ts/tsx, excl. archive).
- `lib/dict_merge.deep_merge` is the only merge home (grep: one `def deep_merge` tree-wide).

## Findings

### OBS-1 — ARCHITECTURE.md (the flagship onboarding doc) describes the PRE-refactor tree  [medium / safe]
Written "2026-07-12" (header line 3) but predates the batch-1/4 moves and the validation→sweep
rename executed the same day. Concretely wrong today:
- `ARCHITECTURE.md:178` + `:337` — lists root `partition/` (moved to `layer1a/partition/`).
- `ARCHITECTURE.md:221` — lists `services/` with dict_merge (deleted; home is `lib/dict_merge.py`).
- `ARCHITECTURE.md:187` — describes `validation/` as the WALL-harness home (now `sweep/`; validation/ is a 19-line compat alias).
- `ARCHITECTURE.md:383` — `emit/data/consumer_binding` (now `emit/instructions/consumer_binding`).
- `ARCHITECTURE.md:176,381,393` — `gates.py` and `:66,435,457` — `fab_guards.py` referenced as files (both are packages now; import paths unchanged but the file paths in the doc are dead).
- ZERO mentions of `lib/` or `domain/` — the two new shared homes central to today's cycle-kill.
README.md was rewritten against the real tree (README.md:13,25,29 verified current); ARCHITECTURE.md
was not. Fix: one doc pass; safe, no owner call.

### OBS-2 — validation/ compat alias is NOT identity-preserving for `import validation.X` (prior lens claim inaccurate)  [low / safe]
`validation/__init__.py:16-19` delegates via `__path__ = sweep.__path__` + PEP-562 `__getattr__` —
unlike every other facade in the tree (which use `sys.modules[__name__] = _home`). Probe (this audit):
`import validation.cli; import sweep.cli` → `validation.cli is sweep.cli` == **False** (two module
objects from the same file; also `validation is sweep` == False). `from validation import config`
DOES return sweep.config via __getattr__ (the form tests/test_validation_runner_legs.py:11-12 uses —
safe), but any `import validation.x` creates a second module instance with its own module-level state,
and afterwards even `from validation import x` returns the duplicate (the import system binds the
submodule attribute, shadowing __getattr__). The concurrent lens doc
`docs/audit_prodready_20260712/sweep-validation-admin.md:11` claims "One code home, no duplication" —
subtly wrong for the submodule-import form. Impact today: minimal (no in-tree `import validation.x`
consumers; `-m validation.cli` runs as __main__ and shared state lives in the sweep.* modules it
imports). Fix: correct the alias docstring + prior lens doc, or switch to per-module sys.modules
aliasing; keep a grep-guard that new code never uses `import validation.…`.

### OBS-3 — test still hardcodes the pre-move ems_backend path; survives only via the compat symlink  [low / safe]
`tests/test_asset3d_dg_seed.py:14` — `_MEDIA = …/../pipeline_v45/ems_backend/media`. ems_backend moved
today to `/home/rohith/desktop/BFI/backend/ems_backend`; the old location is a symlink
(`pipeline_v45/ems_backend -> ../../ems_backend`, created 07:28 today). When that transition symlink is
retired, `test_dg_glb_present_in_media_root` (line 72-74) silently SKIPs ("media root not present") —
the GLB-exists certification quietly stops running instead of failing. The sibling comment in
`scripts/seed_dg_asset3d.py:53` already states the NEW home; the test lags it. Fix: point _MEDIA at
`backend/ems_backend/media` (one line), keep the skip for genuinely-absent checkouts.

### OBS-4 — config/databases.py docstring claims an ems_backend sys.path bootstrap that no longer exists  [low / safe]
`config/databases.py:1-3`: "both the pipeline AND ems_backend read this one module (ems_backend imports
it via a sys.path bootstrap)". Grep of the moved `/home/rohith/desktop/BFI/backend/ems_backend` finds NO
sys.path.insert/append and NO import of config.databases; Django's DB wiring is env-driven
(`backend/settings.py:167-175`, DJANGO_DB_* with local trust defaults, per today's audit hardening).
The real coupling is indirect: `db_link()` strings seeded into registry rows that ems_backend pins per
MFM. Stale claim could send an operator editing this file to repoint Django (it would do nothing).
Fix: one docstring sentence.

## Not covered by this lens
- Frontend (batch 6) tsc/vite verification — not re-run here (build-gated per the ledger; separate lens).
- Config-value/knob semantics (policy_read app_config-first, F6 phase 2) — config lens.
- DB DDL / owner-gated drops — explicitly out of scope for a read-only pass.

