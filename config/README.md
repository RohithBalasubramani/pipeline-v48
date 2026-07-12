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
     fan-in in the system). TTL-cached; a missing row = the code default, never an error.
   - Structured policy tables: one reader module per table (the atomic-structure rule) — see the map below.
   Editable by operators; changes need no restart (TTL) unless a module froze the value at import (the 2026-07-12
   campaign converted the known freezes to lazy PEP-562 attributes — keep new modules lazy).

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

## Rules for new knobs

- Pipeline behavior → `app_config` row + code default via `cfg()`. Plant fact → neuract (or its catalog mirror).
- New policy TABLE → new single-purpose reader module here, reading through `policy_read.py`'s pattern.
- Read lazily (PEP-562 module attr or per-call) — never freeze a `cfg()` at import time.
- Scalar knobs do NOT go in `viewer_policy`/`data_quality_policy` as `__knob__:` rows (config F6 follow-up: those
  migrate INTO `app_config`).
