# Fix log — group: docs-ledgers (2026-07-12)

Scope: doc-drift fixes only. Every claim written below was verified by a live probe
(tree grep / stat / SELECT-only psql) run by this session; probes noted per change.

## Changes
(appended as executed)

### 1. ARCHITECTURE.md — accuracy pass (docs-dx OBS-1/2/3/5/6/7/8 + refactor-integrity OBS-1, incl. the HIGH §6.3 bug)
Probes (all run this session, ~08:11-08:20 IST):
- Tree: `ls -d` — root `partition/`/`services/`/`contracts/`/`ems_compat/` GONE; `domain/ lib/ sweep/ validation/
  layer1a/partition{,_inputs} layer2/gates layer2/emit/instructions ems_exec/executor/fab_guards` all EXIST;
  `layer2/gates.py` + `ems_exec/executor/fab_guards.py` files gone. ops/ = SERVICES.md, db-tunnel.service,
  install-units.sh, tunnel_monitor.py, v48-{host,admin,web}.service. lib/ = api_auth, blank, dict_merge,
  leaf_paths, parallel, ttl_cache.
- Counts: `find` — 591 .py (excl. archive/outputs/node_modules/.venv/__pycache__), 474 excl. tests/;
  112 pytest files (95 tests/ + 17 tests/property/). Doc said 432 / 91.
- §6.3 source of truth: read `layer1b/resolve/asset_candidates.py:1-7` — candidates = cmd_catalog `registry_*`
  mirror (live-neuract fallback) via `data/registry/lt_mfm.py`; id = canonical `lt_mfm.id`; meta_data_version1
  row_number id-space RETIRED (also `config/databases.py:40`). Grep: NO live query consumer of meta_data_version1
  (only the routing set, retired-comments, copilot build docstrings).
- §9: read `data/db_client.py:1-41` — default engine 'pool' (pooled psycopg2, COPY-CSV parity),
  `V48_DB_ENGINE=psql` rollback.
- §10 SELECT-only psql: app_config=370, public base tables=56 (full list captured), equipment=22, page_specs=75,
  cards=145, card_handling=145, card_payloads=155, asset_nameplate=320, registry_lt_mfm=320; six dropped tables
  to_regclass ALL NULL; schema_migrations/derived_metrics/registry_asset_parameter exist; neuract=373 tables.
- §16 F14: `host/server.py:82-84` (retired comment, frames=[] only in a log line) + `host/web/src/types.ts:127-128`.
- §18: `host/server.py:58` signature `build_response(prompt, asset_id=None, date_window=None)` → snippet now
  passes a STRING (the dict form crashed in run_id).
- vLLM: `systemctl is-enabled/is-active vllm` = disabled/inactive; `systemctl --user` = enabled/active
  (process owned by rohith). db-tunnel system unit = enabled/active.
Edits: §2.1/§2.5/§2.6 (fab_guards pkg, ~370 rows, "DB error"), §3 mermaid+table (USER vllm unit; META node/edge
removed, :5433 row corrected), §4 tree rewritten to the post-refactor layout + counts, §6.3 candidate-source bullet
rewritten (the HIGH fix), §6.4 mermaid (gates/, emit/instructions/), §7/§8 path fixes (fab_guards/, layer2/gates/),
§8.5 sweep/ + test counts, §9 door table (pooled q(), registry-mirror device universe), §10.1 counts + dropped-table
note + unlisted tables added, §10.3 rewritten as RETIRED, §13 ~370 + band_policy→data_quality_policy example,
§16 frames note moved to retired, §18 systemctl --user + runnable snippet, §4 tools/ line (seed_quantity_vocab →
scripts/, tunnel_monitor → ops/ — verified by ls).

### 2. config/README.md — real cfg() cache semantics + the two new knobs (config-db OBS-6)
Probe: read `config/app_config.py` (whole file) — `_CACHE` populated once ON SUCCESS, NO TTL; failure not cached,
5 s `_RETRY_BACKOFF_S`, `reload()`/`_load.cache_clear()` are the only in-process refresh hooks; grep host/+admin/:
no runtime reload() caller. Replaced the "TTL-cached … changes need no restart (TTL)" paragraph with the truthful
semantics (restart or reload() to pick up edits; PEP-562 removes import-freezes only).
New-knob section: verified `lib/api_auth.py` (api.token, X-V48-Token, default-empty=off, db/seed_api_token.sql
exists) and `obs/retention.py` (obs.file_retention_days, code default 14, ≤0=keep forever, 6 h daemon) exist
in-tree; psql: NEITHER row seeded yet (documented as default-inert with code defaults). Noted the distinction
from the existing obs.retention_days=30 pg-row purge (db/seed_obs.sql:15, obs/sink_pg.py:82).

### 3. Ledgers truth-up (data-layer OBS-6, frontend OBS-6, followups OBS-6, config-db OBS-2, docs-dx OBS-4)
- EXECUTED_AND_FOLLOWUPS.md (re-read after an 08:15 concurrent edit; edits kept to the follow-ups block):
  follow-ups 1/2/3 marked ✅ EXECUTED with in-tree pointers — probes: validation/__init__.py compat alias read;
  `data/ttl_cache.py` head = re-export facade of lib/ttl_cache.py (both exist); `data/neuract_pool.py` exists and
  grep shows `ems_exec/data/neuract.py:18` + `registries/neuract/_db.py:15` import it. Follow-up 9 rewritten:
  F14 ✅ (server.py:82-84 retirement comment, multi_asset grep clean, types.ts:127; APPLY_LOG second pass is the
  execution record), F4 ✅ (`cmd/fill/shared/vc-sanitize.ts` exists), F16 ✅ (`cmd/rtm/HeatmapSections.tsx` exists);
  F11/F12 remain open. Section header re-titled to a status ledger (several items were already ✅).
- APPLY_LOG_unused_dupes_audit.md: the three stale "NOT dropped / owner-gated / NOT applied" lines (Batch 3,
  Deferred #6, second-pass DROP-script line) annotated ✅ APPLIED with pointers to the file's own THIRD PASS.
  Probes: `db/retire_unused_tables_20260712.sql` header = "APPLIED 2026-07-12 ~07:50 IST (owner authorized)";
  snapshots present in archive/db_snapshots_20260712/ (6 .sql + csv); psql `to_regclass` NULL for all six tables.

### 4. docs/audit_2026-07-12/AUDIT_REPORT.md — residual-list touch-ups
- Consensus row 5 + the §R3 recommendation block annotated ✅ APPLIED. Probe (read-only :5433): 240 indexes with
  `indexdef ILIKE '%ts_imm(%'` in schema neuract; `pg_proc` has `neuract.ts_imm` (1); cmd_catalog knob
  `neuract.ts_index_fn = ts_imm`. (NB an `indexname ILIKE '%ts_imm%'` probe returns 0 — the index NAMES use
  `_tsimm`; match on indexdef.)
- Item 17's "server doesn't yet stamp kind" note closed → points at #24; #24 annotated with multi-asset parity.
  Probe: `host/server.py:98` and `host/multi_asset.py:119` both stamp `"kind": "dashboard"` (multi landed 08:13
  by a concurrent session; verified by grep after its mtime).

### 5. Docstring fixes (behavior-preserving, comment/docstring-only)
- `layer1a/partition/group_detect.py:1` — stale `partition/` path → `layer1a/partition/`.
- `config/databases.py:1-4` — removed the false "ems_backend imports it via a sys.path bootstrap" claim
  (probe: grep of /home/rohith/desktop/BFI/backend/ems_backend for config.databases/sys.path = ZERO hits;
  Django wiring is DJANGO_DB_* env). Documented the real indirect coupling (db_link() strings in registry rows).
  Also `:8` banner 321→373 neuract tables (probe: information_schema count = 373).
- `ems_exec/executor/fab_guards/__init__.py:57` — "re-exports the original module surface byte-compatibly"
  softened to "consumed module surface" + explicit note that HEAD-private zero-consumer names are not re-exported
  (probe: tree-wide grep for _mag_re/_MAGNITUDE_RE/_NO_RAW/*_DEFAULT etc. outside the package = only a stale
  comment in tests/test_fab_guards.py:640, which is not an import).
- `validation/__init__.py` — alias-semantics comment corrected: NOT identity-preserving for `import validation.x`
  (probe: `validation.cli is sweep.cli` == False, `from validation import config` IS sweep.config); guidance added.

### 6. ops/SERVICES.md — vLLM :8200 manager corrected (docs-dx OBS-9)
Probe: `systemctl is-enabled/is-active vllm` = disabled/inactive; `systemctl --user` = enabled/active running
:8200 (process owned by rohith); db-tunnel system unit enabled/active (row left as-is). Table row 8200 → USER
unit; Install section: vllm removed from the "system units" line + a user-unit status/restart note added.

## Gates
- `python3 -m py_compile` on all 4 edited .py files — OK.
- Import smoke: validation alias (`from validation import config` is sweep.config == True), fab_guards package
  (`apply` callable, `_ROWS_CACHE` dict), config.databases db_link(), layer1a group_detect import — all OK.
- Targeted offline pytest: `tests/test_fab_guards.py` 39 passed; `tests/test_validation_runner_legs.py` 3 passed.

## Skipped (outside my file list)
- `db/fix_deadend_knobs_20260712.sql:15-16` carries the same stale "NOT dropped" claim (config-db OBS-2) — not mine.
- `host/server.py:17` docstring still says "`frames` is emitted EMPTY for back-compat" (stale vs F14) — not mine.
- `sweep/*.py` docstrings still self-identify as `validation/...` (sweep-validation OBS-2 cosmetic tail) — not mine.
- `tests/test_fab_guards.py:640` stale `_mag_re` comment (ems-exec OBS-4 first half) — not mine.
- MEMORY.md staleness (followups OBS-6 item 3) — memory updates belong to the main session, not a subagent.
