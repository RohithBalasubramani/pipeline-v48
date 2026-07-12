# STRUCTURE & NAMING audit — pipeline_v48 (2026-07-12)

Scope: folder structure + naming consistency. Excludes archive/, outputs/, .claude/, .playwright-mcp/, __pycache__, node_modules, dist.
House rules honored: atomic-structure (folders of single-purpose files ARE the style), AI-first, per-leaf degradation, DB-driven config, DB-driven dispatch (grepped strings, not just imports, before calling anything unused).

---

## (a) Stale docs

### A1. README.md describes a retired architecture — HIGH-signal doc rot
`README.md:9` — "`workers/` data-fill + aggregation + shared-context + stitch · `frames/` DATA-fill target shapes"
`README.md:11` — "`db_build/` (quarantined)"

None of `workers/`, `frames/`, `db_build/` exist. Per `V48_FULL_WALKTHROUGH_2026-07-02.md:8` the workers/ WS data-fill and Layer-3 verdict were "built and then retired on 2026-07-02 in favor of this ems_exec path". Additional stale claims in the same README:
- `README.md:3` "→ `run/assemble` → PageFrameEnvelope" — there is no `run/assemble.py`; assembly is `host/assemble.py`.
- `README.md:10` "`registries/` byte-identical defaults" — `registries/neuract/` actually holds live neuract METADATA readers (meters/members/nameplate/topology/3d); byte-identical defaults live in `cmd_catalog.card_payloads`.
- `README.md:10` "`contracts/` JSON schemas" — all 10 schemas are empty TODO stubs (see E1).
- `README.md:13` claims the design-doc spine (`V48_DESIGN_NOTES.md` etc.) lives at the pipeline root — those files live in `docs/`.

**Refactor:** rewrite README's "Where each concern lives" section against the real tree (layer1a/layer1b/layer2/ems_exec/grounding/validate/run/host/data/registries/config). Risk: low. Behavior-preserving: yes (doc only). Tests: none.

### A2. host/README.md says Layer 2 does not exist
`host/README.md:7` — "> Layer 2 (the payload-morph layer) is not built yet, so the payload shown per card is the **default** story payload"

L2 morph-emit has been live since 2026-06-30 and the host renders morphed+filled payloads. **Refactor:** update the run-book paragraphs. Risk: low; doc only. Tests: none.

### A3. Superseded spec + finished plan docs squat at the repo root
- `V48_L3_REWORK_SPEC.md:1` — specs `run/layer3_all.run_card_l3`; L3 was retired: `ems_exec/executor/fill.py:1` says "Layer 3 archived, not reused".
- `MULTI_ASSET_PLAN.md:1` — "AS BUILT (2026-07-07)" — a finished record, not an active plan.
- `V48_FULL_WALKTHROUGH_2026-07-02.md` — dated snapshot (310 lines).

All 25 other design docs live in `docs/`. **Moves:** `V48_L3_REWORK_SPEC.md -> docs/V48_L3_REWORK_SPEC.md` (+ add a one-line SUPERSEDED banner), `MULTI_ASSET_PLAN.md -> docs/MULTI_ASSET_PLAN.md`, `V48_FULL_WALKTHROUGH_2026-07-02.md -> docs/V48_FULL_WALKTHROUGH_2026-07-02.md`. Importers: none (md only; `MULTI_ASSET_PLAN.md:34` is referenced from nothing). Risk: low. Tests: none.

### A4. Stale name propagation in the copilot decoupling guard
`copilot/tests/test_no_coupling.py:18` — FORBIDDEN set still lists `"workers"` (deleted 2026-07-02). Harmless (defensive), but any structure rename below (e.g. `partition` move) should touch this list in the same commit. Doc-level note, not a standalone finding.

---

## (b) Misplaced files

### B1. A Python seeder inside the all-SQL db/ ledger
`db/seed_schema_and_endpoints.py` is the only `.py` among 86 `.sql` files (`fix_*`, `patch_*`, `seed_*`, `*_schema.sql`, one `.retired`). Sibling Python seeders live in `scripts/` (`seed_dg_asset3d.py`) and `tools/` (`seed_quantity_vocab.py`) — three homes for the same concern.

**Move:** `db/seed_schema_and_endpoints.py -> scripts/seed_schema_and_endpoints.py`. Importers: none (standalone CLI, `python3 db/seed_schema_and_endpoints.py` per its own line 14 — update that docstring). Risk: low. Behavior-preserving: yes. Tests: none import it.

### B2. tools/ vs scripts/ split is real but leaks (see also (f))
Reconstructed rationale: `tools/` = read-only diagnostic harnesses (replay/AB/sweep/monitor: `morphmap_ab.py`, `morphmap_live_ab.py`, `wall_corpus_replay.py`, `asset_sweep.py`, `replay_item17_guided_asset_resolve.py`); `scripts/` = state-building one-offs that WRITE the DB (`build_stripped_payloads.py`, `rescan_stripped_payloads.py`, `seed_dg_asset3d.py`, `sync_neuract_registry.py`). Two leaks:
- `tools/seed_quantity_vocab.py:7` — "READ the code default, WRITE the DB" — a DB seeder in the read-only dir.
- `tools/tunnel_monitor.py` — ops infrastructure (pairs with `ops/db-tunnel.service`), not a diagnostic harness.

**Moves:** `tools/seed_quantity_vocab.py -> scripts/seed_quantity_vocab.py`; `tools/tunnel_monitor.py -> ops/tunnel_monitor.py`. Importers: none (`grep "from tools\|import tools"` = 0 hits); self-referencing docstrings/strings only (`tools/seed_quantity_vocab.py:7,20` — note line 20's string is UPSERTed into app_config notes; regenerate or accept the stale note). Memory doc `v48-quantity-vocab-domain-telemetry` references `tools/seed_quantity_vocab.py` — update after move. Risk: low. Behavior-preserving: yes. Tests: none.

### B3. Ten 6-line placeholder skip-only test files, two named after a deleted subsystem
`tests/test_workers_aggregate_builders.py:6`, `tests/test_workers_aggregate_panel174.py:6`, `tests/test_sharedctx_generalizations.py`, `tests/test_contracts_roundtrip.py`, `tests/test_invariants.py`, `tests/test_layer1a_partition_inputs.py`, `tests/test_layer2_data_instructions.py`, `tests/test_layer2_metadata_byte_identical.py`*, `tests/test_layer2_metadata_no_chrome.py`*, `tests/test_partition_orphan_160.py` — each is exactly `def test_placeholder(): pytest.skip("TODO(v48): implement")`. (*the byte-identical/no-chrome CONCERNS are guarded elsewhere — real suites exist under similar names per the 882-green suite; these two stubs shadow that naming.) `test_workers_*` reference the retired `workers/` path; `test_sharedctx_generalizations.py` references retired sharedctx stubs.

**Refactor:** delete the 2 `test_workers_*` + `test_sharedctx_generalizations.py` (their subject no longer exists); for the other 7 either implement or delete — a skip-only file is pure suite-count noise. Risk: low. Behavior-preserving: yes (skip-only tests assert nothing). Tests guarding: n/a (these ARE tests).

### B4. Runtime cruft committed in-tree / at root
- `err.log` (0 bytes) at repo root — untracked, gitignored by `*.log`, but sitting in the tree.
- `host/host_restart.log`, `host/vite_restart.log` — same.
- `host/outputs/FILL_PERCARD_WORKLOG.md` — a TRACKED worklog inside an outputs/ dir (root `.gitignore` covers `outputs/*` patterns at root only, not `host/outputs/`).
- `host/web/tsconfig.tsbuildinfo` — a TRACKED TypeScript build artifact.

**Refactor:** `rm err.log host/*.log`; move `host/outputs/FILL_PERCARD_WORKLOG.md -> docs/FILL_PERCARD_WORKLOG.md`; `git rm --cached host/web/tsconfig.tsbuildinfo` and add `*.tsbuildinfo` + `host/outputs/` to `.gitignore`. Risk: low. Behavior-preserving: yes. Tests: none.

### B5. copilot/tests/ outside tests/ — ACCEPTABLE, do not move
`copilot/tests/{eval.py,test_no_coupling.py}` is deliberate: the copilot layer is designed liftable with zero pipeline coupling (`test_no_coupling.py:1` "the copilot layer imports NOTHING from the pipeline"). Keeping its tests inside the package is the decoupling working as intended. No action. (`eval.py` is an eval harness, not pytest — fine, it is not collected.)

---

## (c) Naming inconsistency

### C1. `validate/` vs `validation/` vs `config/validation.py` — three near-identical names, three different concerns (HIGHEST-signal naming finding)
- `validate/` (11 files) = the in-pipeline pre-Layer-2 validation pass (`validate/build.py:1` "THE one pre-Layer-2 validation pass").
- `validation/` (NEW — created 2026-07-12, mid-construction: `__init__.py`, `config.py`, `response.py`, `corpus/`) = an OFFLINE prompt-sweep QA framework (`validation/__init__.py:1` "NOT a benchmark, NOT a unit suite — a failure-mode exposer").
- `config/validation.py:1` = knobs FOR `validate/` ("Edit here, not in validate/") — now reads as if it configures `validation/`.

**Refactor:** rename `validation/ -> sweep/` (or `qa/`) NOW, while external importers are ZERO (only `validation/corpus/{universe,generate}.py` import `validation.config` internally) and the package is hours old. Renaming later, after `cli.py`/`runner.py`/reports land and outputs paths (`outputs/validation/`) calcify, multiplies the cost. Also update `validation/config.py:32` OUT_DIR default (`outputs/validation` -> `outputs/sweep`). Risk: medium ONLY because the package is under concurrent active construction today — coordinate with that session; mechanically it is a 3-line import fix. Behavior-preserving: yes. Tests: none yet (framework is pre-test).

### C2. `registries/` vs `data/registry/` — two top-level homes both named "registry", overlapping purpose
- `registries/neuract/` = LIVE :5433 metadata reads. `registries/neuract/members.py:1` — "THE aggregation source the panel-aggregate stage calls".
- `data/registry/lt_mfm.py:1` — "the CANONICAL asset registry reader … MIRROR-FIRST" (cmd_catalog `registry_*` mirror to dodge tunnel flaps) and `data/lt_panels/panel_members.py:1` — "THE single source of truth for panel fan-out".

Two files EACH claim to be THE source for panel membership. Consumers split by transport, not by concern: `ems_exec/executor/members.py:36` resolves member edges via `registries.neuract` (live) while layer1b/host resolve via the mirror stack (`data/registry`, `data/lt_panels`) — i.e. the tunnel-flap immunity built for the mirror stack (member-cache-poison fix, `data/ttl_cache.py`) does not shelter the executor's live-edge path. The split (live vs mirror) is *semi*-principled but the NAMES don't state it, and the top-level dir count grows.

**Refactor (minimal, naming-only):** move `registries/neuract/ -> data/neuract_live/` so both stacks live under `data/` with transport-honest names (`data/registry` mirror-first vs `data/neuract_live`). Importers to update (10 non-internal): `ems_exec/executor/members.py`, `ems_exec/executor/roster.py`, `ems_exec/renderers/{_agg,asset_3d,__init__,panel_aggregate}.py`, `ems_exec/renderers/_story/_facts.py`, `layer2/emit/panel_members_block.py`, `tests/test_equipment_ai_context.py`, `tests/test_equipment_topology.py` (+7 internal files). Risk: medium (import churn only; no logic edits). Behavior-preserving: yes. Tests guarding: `tests/test_equipment_ai_context.py`, `tests/test_equipment_topology.py`, `tests/test_ems_exec_roster.py`, `tests/test_layer2_metadata_byte_identical.py` reference `registries`. The deeper unification (route executor edges through the mirror-first door) is a BEHAVIOR change — out of scope here, flagged for the resilience dimension.

### C3. Top-level `partition/` is layer1a-private and inverts layering
`partition/coupling_lookup.py:2-5` imports `layer1a.partition_inputs.*` — a ROOT package depending on a subpackage of a layer. Its only production importer is `layer1a/build.py:6` (`from partition.group_detect import detect_groups`). 83 LOC, 3 files. Meanwhile the layer1a folder already hosts the sibling `layer1a/partition_inputs/`.

**Moves:** `partition/{__init__,coupling_lookup,fallback_edges,group_detect}.py -> layer1a/partition/`. Importers to update: `layer1a/build.py:6`; `partition/group_detect.py:2-3` (internal); `tests/test_partition_groups.py:3`; optional: drop `"partition"` from `copilot/tests/test_no_coupling.py:19` FORBIDDEN set (covered by `"layer1a"` after the move). Risk: low. Behavior-preserving: yes. Tests guarding: `tests/test_partition_groups.py`, `tests/test_layer1a_routing.py`, `tests/test_orchestrator.py` (indirect via layer1a build).

### C4. `layer2/emit/data/` is not data — it authors data_instructions; third distinct meaning of a dir named "data"
Three dirs named `data`: top-level `data/` (resolution DB doors), `ems_exec/data/` (the neuract time-series door — well named), and `layer2/emit/data/` (`__init__.py:1` "data_instructions authoring, ONE file per field-kind" — authoring code, not data access).

**Move:** `layer2/emit/data/ -> layer2/emit/instructions/`. Importers to update: `layer2/build.py`, `layer2/emit/emit.py`, `layer2/emit/user_message.py`, `db/seed_schema_and_endpoints.py`, `tests/test_layer2_card.py` (+5 internal files under `consumer_binding/`). Risk: low. Behavior-preserving: yes. Tests guarding: `tests/test_layer2_card.py`, `tests/test_layer2_data_instructions.py` (placeholder), `tests/test_residual_layer2_emit.py`.

### C5. `services/` = a 32-LOC junk drawer with a misleading name
`services/dict_merge.py:1` — "the pure recursive deep-merge helper". Nothing service-like; 2 importers (`layer2/emit/metadata/asset_3d.py:162`, `ems_exec/renderers/asset_3d.py:28`). A twin homeless pure utility exists at `data/ttl_cache.py` (generic TTL cache, imported by `data/lt_panels/panel_members.py`, `data/registry/lt_mfm.py`, `layer1b/resolve/has_data.py`) — it is NOT a DB door yet lives in `data/`.

**Moves:** `services/dict_merge.py -> lib/dict_merge.py`; `data/ttl_cache.py -> lib/ttl_cache.py`; delete `services/`. Importers: the 5 files above (+ docstring at `ems_exec/renderers/asset_3d.py:16`). Risk: low. Behavior-preserving: yes. Tests guarding: none direct (indirect: `tests/test_has_data_outage.py`, `tests/test_equipment_3d.py`, `tests/test_layer2_metadata_byte_identical.py`).

### C6. Minor verb-order inconsistency — note only, no move proposed
Convention is noun_verb (`asset_resolve.py`, `measurable_resolve.py`, `swap_settle.py`, `scalar_tile_fill.py`); outlier: `layer1b/compare/resolve_names.py` (verb_noun). The four per-layer `build.py` files (`layer1a/build.py`, `layer1b/build.py`, `layer2/build.py`, `validate/build.py`) are a CONSISTENT "compose this layer end-to-end" convention — imports read as `layer1a.build`, so ambiguity is low; only `copilot/build/` (an offline index builder subpackage) collides in meaning. `ems_exec/executor/fill.py` anchors the `*_fill.py` family and has ~20-file fan-in — rename cost exceeds benefit. No action.

---

## (d) Duplicate-purpose data/DB dirs — the map

| dir | holds | verdict |
|---|---|---|
| `data/` | resolution-time DB doors: `db_client.py` (psql q() for cmd_catalog), `registry/lt_mfm.py` (canonical mirror-first registry), `lt_panels/panel_members.py` (panel fan-out), `equipment/` (single door to `equipment` schema), `ttl_cache.py` (misfiled utility, see C5) | principled EXCEPT ttl_cache |
| `ems_exec/data/` | `neuract.py` — "the ONLY door to the live NEURACT time-series" (line 1) | principled, well named |
| `registries/neuract/` | live neuract METADATA doors (meters/members/nameplate/topology/3d) | overlaps `data/registry` + `data/lt_panels` in concern; split is transport (live vs mirror), names don't say so — see C2 |
| `db/` | 86 flat cmd_catalog SQL files (`fix_*`/`patch_*`/`seed_*`/`*_schema.sql` + 1 `.retired`) + 1 misfiled .py (B1) | flat append-only ledger is defensible; ~15 docstrings + 2 test error-strings cite `db/<file>.sql` paths (`tests/test_render_guarantee_50.py:198,419`), so re-foldering buys little — keep flat, move only the .py |
| `payload_db/` | offline Storybook harvest tooling: 2 `.mjs`, `schema.sql`, `enrich/` (js + json), notes | build-time-only; fine where it is; could join `tools/` but zero importers, zero benefit |
| `ems_compat/` | `compat_view_template.sql` + `COVERAGE.md` — SUPERSEDED per `V48_FULL_WALKTHROUGH_2026-07-02.md:84` ("The `compat` schema is superseded/gone"); code deleted in the legacy purge, sql/md deliberately KEPT | move `ems_compat/ -> docs/ems_compat/` (historical truth-table); importers: none (string in copilot FORBIDDEN list is name-based, unaffected) |

---

## (e) Empty / near-empty dirs

### E1. contracts/ — 10 dead stub schemas
Every file, e.g. `contracts/data_instructions.schema.json`: `"properties": {}, "additionalProperties": true, "$comment": "TODO(v48): fill from V48_BUILD_SPEC_CONTRACTS.md"`. The real contracts were implemented as per-layer `schema.py` builders instead. Verify-before-dead: only consumer tree-wide is `tests/test_contracts_roundtrip.py` — itself a 6-line placeholder skip (B3); no code loads `contracts/` (grep for `contracts/` in *.py = that one test docstring).

**Refactor:** either backfill from `docs/V48_BUILD_SPEC_CONTRACTS.md` and make the roundtrip test real, or move `contracts/ -> archive/contracts/` and delete the placeholder test. Risk: low. Behavior-preserving: yes. Tests: only the placeholder itself.

### E2. ops/ — 1 file; the tunnel concern is split across two dirs
`ops/db-tunnel.service` (systemd unit) vs `tools/tunnel_monitor.py` (its watchdog). **Move** (same as B2): `tools/tunnel_monitor.py -> ops/tunnel_monitor.py` so ops/ = the :5433 tunnel concern, complete. Risk: low. Tests: none.

### E3. knowledge/ (2 py + prompts/) and llm/ (3 py) — small but single-purpose; per the atomic rule these are FINE. No action.

---

## (f) tools/ vs scripts/ — rationale + fixes
Covered in B2: the split (diagnostic-replay vs state-building) is real and worth keeping — write it down as one line each in the README rewrite (A1), and fix the two misfiles (`seed_quantity_vocab.py`, `tunnel_monitor.py`).

---

## Target structure (minimal-move summary — every move named)

```
partition/coupling_lookup.py            -> layer1a/partition/coupling_lookup.py     (importers: layer1a/build.py, tests/test_partition_groups.py, internal x2)
partition/fallback_edges.py             -> layer1a/partition/fallback_edges.py
partition/group_detect.py               -> layer1a/partition/group_detect.py
partition/__init__.py                   -> layer1a/partition/__init__.py
layer2/emit/data/**                     -> layer2/emit/instructions/**              (importers: layer2/build.py, layer2/emit/{emit,user_message}.py, db/seed_schema_and_endpoints.py, tests/test_layer2_card.py, internal x5)
services/dict_merge.py                  -> lib/dict_merge.py                        (importers: layer2/emit/metadata/asset_3d.py, ems_exec/renderers/asset_3d.py)
data/ttl_cache.py                       -> lib/ttl_cache.py                         (importers: data/lt_panels/panel_members.py, data/registry/lt_mfm.py, layer1b/resolve/has_data.py)
db/seed_schema_and_endpoints.py         -> scripts/seed_schema_and_endpoints.py     (importers: none)
tools/seed_quantity_vocab.py            -> scripts/seed_quantity_vocab.py           (importers: none)
tools/tunnel_monitor.py                 -> ops/tunnel_monitor.py                    (importers: none)
validation/                             -> sweep/ (rename before it grows)          (importers: internal only today)
registries/neuract/**                   -> data/neuract_live/**  [OPTIONAL/medium]  (importers: 10 external listed in C2)
MULTI_ASSET_PLAN.md                     -> docs/MULTI_ASSET_PLAN.md
V48_L3_REWORK_SPEC.md                   -> docs/V48_L3_REWORK_SPEC.md (+SUPERSEDED banner)
V48_FULL_WALKTHROUGH_2026-07-02.md      -> docs/V48_FULL_WALKTHROUGH_2026-07-02.md
ems_compat/                             -> docs/ems_compat/
contracts/                              -> archive/contracts/ (or backfill + real roundtrip test)
host/outputs/FILL_PERCARD_WORKLOG.md    -> docs/FILL_PERCARD_WORKLOG.md
DELETE: err.log, host/host_restart.log, host/vite_restart.log, tests/test_workers_aggregate_builders.py, tests/test_workers_aggregate_panel174.py, tests/test_sharedctx_generalizations.py (+7 more skip-only stubs or implement them)
REWRITE: README.md (workers/frames/db_build/registries/contracts/run-assemble claims), host/README.md (L2 "not built yet")
```

Sequencing note: land C1 (validation/ rename) FIRST — it is in active construction today and gets more expensive by the hour. Everything else is import-churn-only and can ship behind the 882-green suite. There is no pytest.ini/pyproject — pytest relies on repo-root cwd for imports; none of the proposed moves change that, but a future packaging pass should add a pyproject.
