# Production-Readiness Audit — docs-dx lens (2026-07-12)

Scope: documentation/DX accuracy vs the tree AS IT IS NOW (post refactor-campaign, post unused-dupes apply, ~480 uncommitted files).
Differential vs: docs/audit_2026-07-12/*.md, docs/findings/refactor_20260712/EXECUTED_AND_FOLLOWUPS.md, CODEBASE_AUDIT_UNUSED_DUPES_2026-07-12.md, ARCHITECTURE.md.
Constraints honored: read-only; SELECT-only psql probes on cmd_catalog :5432; no server starts.

## Findings

### OBS-1 (medium) ARCHITECTURE.md §4 repo layout drifted from tree (same-day refactor outran the doc)
- Line 180: `partition/` listed as a ROOT package — it moved to `layer1a/partition/` (root `partition/` does not exist; README.md line 13 already says `layer1a/partition/`).
- Line 221: `services/` listed ("tiny shared helpers (dict_merge)") — deleted; helpers now live in `lib/` (root has no `services/`).
- Tree omits root packages that DO exist now: `domain/`, `lib/`, `sweep/`.
- Line 188-189 describes `validation/` as "The WALL harness ..." — `validation/` is now a 19-line compat alias (`validation/__init__.py`) to `sweep/`; the harness itself is `sweep/`. §8.5 (line 505) same drift.
- Line 177: layer2 "gates.py (byte-identity)" — now a package `layer2/gates/` (no `layer2/gates.py`); §8.2 heading (line 484) cites `layer2/gates.py` too.
- §2.1 (line 67) and §7 (lines 435, 457) cite `ems_exec/executor/fab_guards.py` — it is now the package `ems_exec/executor/fab_guards/` (apply.py, class1_epoch.py, class23_source.py, class4_seed.py, knobs.py, restore.py).
- Line 219: `ops/` said to hold only db-tunnel.service — it now also holds SERVICES.md, install-units.sh, tunnel_monitor.py, v48-admin/host/web.service units.
Fix: one editing pass over §4/§6.2/§7/§8 path mentions. fix_class=safe.

### OBS-2 (medium) ARCHITECTURE.md DB counts stale vs live cmd_catalog
Live counts (SELECT-only probe 2026-07-12): app_config=373 (doc says 316 at lines 89, 573, 685), public base tables=56 (doc says 61 at line 548). Verified-correct claims: page_specs=75, cards=145, card_handling=145, card_payloads=155, asset_nameplate=320, registry_lt_mfm=320, equipment schema=22 tables.
Six tables named in §10.1 were DROPPED (dead band/knob surface of the unused-dupes campaign): `card_render_map`, `card_rendering`, `endpoint_policy`, `live_window_policy`, `band_policy`, `limit_override` — §10.1 lines 572-573 and §13 line 688 still cite `band_policy`/`endpoint_policy`/`live_window_policy`/`limit_override` as live typed policy tables. Three live tables are unlisted: `schema_migrations`, `derived_metrics`, `registry_asset_parameter`.
NOTE: memory/apply-log said table DROPs were "owner-gated, script written" — the drops evidently ran; whichever doc still says "pending owner" is stale too (see OBS-4). fix_class=safe (doc edit).

### OBS-4 (medium) APPLY_LOG says the 6-table DROP was NOT applied — it WAS applied
`docs/findings/refactor_20260712/APPLY_LOG_unused_dupes_audit.md:53` ("NOT dropped (owner-gated, snapshots ready)"), `:106` ("owner-gated; snapshots are ready"), `:152` ("Owner-gated DROP script written, NOT applied: db/retire_unused_tables_20260712.sql.owner_gated"). Reality: the script exists WITHOUT the `.owner_gated` suffix (`db/retire_unused_tables_20260712.sql`), the snapshots exist (`archive/db_snapshots_20260712/{band_policy,card_render_map,card_rendering,endpoint_policy,limit_override,live_window_policy}.sql`), all six tables are GONE from live cmd_catalog (56 public tables), and `scripts/seed_schema_and_endpoints.py:99-101` records the drop as done. A later session/owner evidently applied it; the ledger was never updated. Risk: someone "completes the pending owner call" and re-runs/re-seeds. fix_class=safe (update the 3 ledger lines).

### OBS-5 (medium) ARCHITECTURE.md §18 "Run it headless" snippet crashes as written
Line 806-808: `build_response({'prompt':'voltage health of AHU-5'})` passes a DICT, but `host/server.py:57` is `build_response(prompt, asset_id=None, date_window=None)` → `run_pipeline(prompt)` → `run/run_id.py:6` does `(salt + "|" + (prompt or "")).encode()` → `TypeError: can only concatenate str` before any pipeline work. The documented onboarding command fails verbatim. Correct form: `build_response('voltage health of AHU-5')`. fix_class=safe.

### OBS-6 (medium) ARCHITECTURE.md §9 door table describes the pre-audit psql-subprocess q()
Line 525: "Catalog/registry SQL | data/db_client.py::q | psql subprocess, CSV". Reality (`data/db_client.py:3-5,31`): default engine is a pooled-psycopg2 process pool ("the audit's hottest finding"), `V48_DB_ENGINE=psql` is the rollback. The same-day audit implementation outran the same-day architecture survey. The neuract-door row (line 526, pooled psycopg2) is already correct. fix_class=safe.

### OBS-7 (low) ARCHITECTURE.md §16 legacy-artifact list contains one now-false item
Line 749: "Legacy artifacts you will still see: `frames: {}` in responses (FE back-compat)" — page-level `frames`/`frame_status`/`live_frame` wire fields were RETIRED today (frontend F14): `host/server.py:81-83` comment, `host/web/src/types.ts:127`. The other two items on that line are still true and remain the cheap-fix list: `run/layer2_all.py:30` still writes `fill_source="live-frontend"` (fill is server-side), and `layer2/emit/emit.py:1` docstring still says "Composes the 3 atomic prompt parts (swap + metadata + …)" while the prompt has been the single always-v2 `data_instructions_v2.md` since 2026-07-08. fix_class=safe.

### OBS-8 (low) Stale counts sprinkled through ARCHITECTURE.md + a stale comment in databases.py
- Line 161: "432 Python files" — now 570 (excl. archive/outputs/node_modules; 454 excl. tests).
- Lines 214, 501: "91 pytest files" — now 111 (94 in tests/ + 17 in tests/property/, the property suite landed after the survey).
- Line 224: "Empty/vestigial: `contracts/` … `ems_compat/`" — both directories no longer exist at all (deleted, good); the sentence implies they're still present.
- `config/databases.py:8` says neuract has "321 tables"; live count is 373 (ARCHITECTURE.md §10.2's 373 is CORRECT).
fix_class=safe.

### OBS-9 (low) ops/SERVICES.md: pipeline vLLM runs as a USER unit, doc says SYSTEM
`ops/SERVICES.md:15` (and line 46 "system units (root): … vllm.service") say :8200 is managed by "SYSTEM `vllm.service`". Reality: the system-level `vllm.service` is disabled+inactive; the serving unit is the USER `vllm.service` (`systemctl --user` shows it loaded/active/running, process owned by rohith). `systemctl status vllm` in ARCHITECTURE.md §18 line 793 likewise checks the system unit and reports inactive while :8200 is up. Matters for ops: restart instructions target the wrong manager. fix_class=safe (doc edit) / owner-gated if the intent is to migrate the unit.

## Verified OK (positive checks of today's claims)

- `python3 -m sweep.cli` importable; `validation/` is a deliberate 19-line compat alias to `sweep/` (`validation/__init__.py`) so `python3 -m validation.cli` still works — refactor follow-up #1 executed cleanly.
- fab_guards package split real and coherent: `ems_exec/executor/fab_guards/{apply,class1_epoch,class23_source,class4_seed,knobs,restore}.py`.
- `layer1a/partition/` + `layer1a/partition_inputs/` exist (README.md's description is current; only ARCHITECTURE.md lags).
- No dangling `import services` / `from services` anywhere outside archive — the services→lib move left no broken importers.
- Live DB counts matching docs: page_specs=75, cards=145, card_handling=145, card_payloads=155, asset_nameplate=320, registry_lt_mfm=320, equipment schema=22 tables, neuract=373 tables (§10.2 correct).
- All 7 named §13 app_config knobs exist as rows (llm.timeout.l2_emit, layer2.emit_concurrency, ems_exec.card_budget_s, cache.resolution_ttl_s, knowledge.enabled, reflect.reroute_on, site.name).
- ops/SERVICES.md unit inventory real: v48-host/v48-admin/v48-web user units enabled+running; ems-copilot + vllm-copilot running; system db-tunnel enabled+active; `tools/stack_monitor.sh`, `data/outage.py`, `copilot/deploy/*.service`, moved `/home/rohith/desktop/BFI/backend/ems_backend` all exist as stated.
- :8770 `/api/health` and :8790 `/admin/api/health` answer with the documented shapes; admin route inventory in `admin/server.py:68-152` matches ARCHITECTURE.md §11 exactly (health, runs, run/<id>, explorer, coverage, latency, failures, ai-usage, sql, assets-log, validation, search/prompts, search/errors, replays, POST replay).
- docs/EXTENDING.md recipes all check out against the tree: renderer self-registration via `HANDLING_CLASSES` + `special_kinds()` (`ems_exec/renderers/__init__.py:48-66,132`); roster-mode discovery via `MODES` declarations (`ems_exec/executor/roster.py:263-289`, `roster_modes_agg.py:125`); FE barrel discovery via `import.meta.glob` (`host/web/src/cmd/components/index.ts:8`); provider seam `llm/providers/openai_compat.py` with selection env V48_LLM_PROVIDER > app_config llm.provider > default (`llm/providers/__init__.py:14-30`); `config/{available_pages,asset_class_defaults,asset_granularity}.py` exist; AVAILABLE_PAGES code default = 18 as claimed.
- Onboarding §18 otherwise sound: `host/server.py`, `admin/server.py`, `copilot/server.py` exist; `host/web` package.json has dev/ssr-gate/client-gate/layout-gate; env names V48_HOST_PORT/V48_ADMIN_PORT/COPILOT_PORT match code; read-next files (`docs/V48_FULL_WALKTHROUGH_2026-07-02.md`, `layer2/build.py`, `host/web/src/cmd/registry.tsx::renderCmd`, `docs/fe_contract/acceptance_sentinel.md`) all exist.
- README.md is current throughout (layer1a/partition, layer2/emit/instructions one-file-per-field-kind, fab_guards/ package, lib/ homeless utilities, ops tunnel+watchdog) — only ARCHITECTURE.md drifted.
- Only ONE code reference to the six dropped tables remains (`scripts/seed_schema_and_endpoints.py`), and it is a correctly-worded retirement comment, not a live query — no runtime regression from the drops.
- degrade-gate fingerprint move is a documented facade: `run/degrade_gate.py:18-22` re-exports `is_outage_error` from the new home `data/outage.py`.


### OBS-3 (high, doc-accuracy) ARCHITECTURE.md describes the RETIRED meta_data_version1 device registry as the live 1b candidate source
§6.3 line 349-350, §9 table line 530, and §10.3 (lines 597-599) all say layer1b's candidate universe = `meta_data_version1.app_devices ⋈ app_device_tables ⋈ app_gateways` with "mfm_id contract = row_number in table order". Reality: `layer1b/resolve/asset_candidates.py:1-7` — candidates come from the CANONICAL `cmd_catalog registry_*` mirror (live-neuract fallback) via `data/registry/lt_mfm.py`; the docstring explicitly says this "replaces the old PRIVATE row_number() id-space over meta_data_version1"; `config/databases.py:40` says the meta_data_version1 shadow registry is RETIRED. Also §3 mermaid + service table (lines 130, 155) still draw META :5433 as a live dependency of the host. Misleads onboarding + debugging (wrong id-space mental model). fix_class=safe (doc edit).
