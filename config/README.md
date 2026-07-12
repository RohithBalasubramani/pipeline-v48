# config/ — the THREE config planes and their precedence [audit R5, 2026-07-12]

V48 configuration lives in three planes. Every knob belongs to exactly ONE plane; when the same concept seems to exist
in two, the more specific plane wins at read time. This file is the map — the audit found the precedence existed only
in code.

## The planes

1. **Code defaults (this package).** Every `config/*.py` module carries a code-default mirror of its policy. This
   plane is the FLOOR: it makes the pipeline importable and behaviorally identical with the DB down (fail-open
   mandate). Never the place to "quickly change" a value that has a DB row — the row wins.

2. **cmd_catalog — pipeline knobs + policy tables.** The pipeline's own brain.
   - Scalar/JSON knobs: `app_config` rows via `cfg(key, default)` (`config/app_config.py` — lazy `_load()`, highest
     fan-in in the system). A missing row = the code default, never an error.
   - Structured policy tables: one reader module per table (the atomic-structure rule) — see the map below.
   CACHE SEMANTICS (verified against app_config.py 2026-07-12): the table is loaded ONCE per process and cached
   **on success only** — there is NO TTL. A FAILED load is never cached (never-cache-empty): code defaults serve
   for a 5 s backoff, then the next `cfg()` retries, so an outage self-heals. But a row EDIT does NOT reach an
   already-running process — restart the service (or call `config.app_config.reload()` /
   `_load.cache_clear()` in-process, e.g. from a seed script) to pick it up. Lazy PEP-562 module attributes
   (the 2026-07-12 campaign) remove IMPORT-time freezes, not the process cache — keep new modules lazy anyway.

3. **neuract — PLANT config (`lt_config_field` / `lt_config_value` via `MFM.get_config()` in the registry path).**
   Describes the SITE (ratings, wiring, panel facts), not the pipeline. V48 treats it as read-only ground truth:
   pipeline behavior knobs never go here; plant facts never go in `app_config`.

**Precedence at read time:** `neuract plant fact` (what the site IS) → `cmd_catalog` row (how the pipeline should
behave) → code default (the floor). A reader that consults two planes must say so in its docstring
(`config/nameplates.py` is the pattern: neuract nameplate first, `asset_nameplate` catalog fallback).

## Module → plane/table map (generated from source 2026-07-12)

| Module | Plane 2 table(s) | Notes |
|---|---|---|
| `app_config.py` | `app_config` | `cfg()` — THE scalar/JSON knob door |
| `policy_read.py` | `data_quality_policy` | THE one policy-row reader (esc + fail-open num/txt) |
| `quality_policy.py` | `data_quality_policy` | class-specific accessors over policy_read |
| `available_pages.py` | `routable_pages` | |
| `asset_class_defaults.py` | `asset_class_default` | |
| `derivation_binding.py` | `derivation_binding` | |
| `event_thresholds.py` | `event_threshold` | |
| `metric_class.py` | `metric_class` | |
| `nameplates.py` | `asset_nameplate` (+ neuract plane-3 first) | two-plane reader |
| `prompt_matrix.py` | `render_guarantee_matrix`, `render_guarantee_page_phrase` | |
| `reason_templates.py` | `reason_template` | |
| `schema_map.py` | `schema_slot_map` | |
| `viewer_policy.py` | `viewer_policy` (+ `__knob__:` rows — see F6 follow-up) | |
| `databases.py`, `neuract_dsn.py` | — | BOOTSTRAP: DSNs/endpoints only; `neuract_dsn` knob-guarded via cfg() |
| `windows.py`, `metrics.py`, `swap.py`, `intents.py`, `feasibility.py`, `vocab.py`, `gates_vocab.py`, `validation.py`, `asset_granularity.py` | via `cfg()` | knob bundles with code-default mirrors (lazy PEP-562) |
| `energy_balance_policy.py`, `feeder_overview.py`, `topology_policy.py`, `rating_knobs.py`, `asset3d_media.py`, `nameplate_slot_map.py` | via `policy_read`/`cfg` or pure defaults | |

## The config↔data package pair (deliberate)

`config/*` readers call `data.db_client.q()` (plane 2 lives in Postgres) while `data/*` reads `config.databases`
DSNs and `cfg()` knobs — a two-way PACKAGE reference that is the one coupling the 2026-07-12 cycle-kill campaign
deliberately KEPT: both packages are the shared foundation, the module-level graph is acyclic (no import SCC), and
splitting bootstrap-config from policy-readers today would churn ~14 freshly-refactored modules for layering
aesthetics. Revisit only if a real import cycle (not a package pair) reappears — the graph gate in
`tests` / the audit extractor will say so.

## Knobs added 2026-07-12 (audit hardening — both default-inert)

- `api.token` (text, default EMPTY = auth OFF) — the shared-secret gate for the :8770/:8790 HTTP surfaces
  (`lib/api_auth.require_token`, header `X-V48-Token`; declared by `db/seed_api_token.sql`). Empty/absent row =
  every request flows exactly as before; fail-open (a config-read error never locks out the API). NB: like every
  `cfg()` knob it is served from the process cache — setting it requires a restart/reload to take effect.
- `obs.file_retention_days` (int, code default 14; ≤0 = keep forever) — age-based prune of the per-run FILE
  telemetry under `outputs/logs/` + `outputs/traces/` (`obs/retention.py`, 6 h daemon the host wires at boot).
  Distinct from `obs.retention_days` (30 — the obs_* pg-row purge in `obs/sink_pg.py`).

## Rules for new knobs

- Pipeline behavior → `app_config` row + code default via `cfg()`. Plant fact → neuract (or its catalog mirror).
- New policy TABLE → new single-purpose reader module here, reading through `policy_read.py`'s pattern.
- Read lazily (PEP-562 module attr or per-call) — never freeze a `cfg()` at import time.
- Scalar knobs do NOT go in `viewer_policy`/`data_quality_policy` as `__knob__:` rows (config F6 follow-up: those
  migrate INTO `app_config`).
