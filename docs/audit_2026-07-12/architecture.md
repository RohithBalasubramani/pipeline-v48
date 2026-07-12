# Architecture Audit — pipeline_v48 (2026-07-12)

Lens: overall layering, dependency direction, module boundaries, missing/over-abstractions, pattern consistency.
Method: grep of the real import graph + directory-boundary reading. Complements the code-quality lenses (which cover
in-module smells) — this lens is about the seams *between* modules.

## Overall assessment

The intended layering is a clean pipeline: `layer1a ∥ layer1b → layer2 → ems_exec → grounding/guards → host`, with
`data/`, `config/`, `registries/`, `llm/`, `obs/` as shared platform, and `run/` as the orchestrator. The atomic-file
discipline is real and mostly pays off. But three seam problems undercut the clean picture: (1) the dependency graph is
**not acyclic** — a downstream layer imports an upstream one and a shared layer imports a pipeline layer, forcing 264
in-function imports as cycle workarounds; (2) two directory pairs (`validate/`↔`validation/`, and the three "config
homes") are boundary-ambiguous; (3) the DB-access and config-access idioms are each implemented three ways across the
tree. None is a correctness bug today; all are maintainability/onboarding taxes that compound at team scale.

---

## A1 — MEDIUM — Dependency inversion: downstream `ems_exec` and shared `data/` import upstream pipeline layers

- `ems_exec/executor/measurable_resolve.py:238` — `from layer2 import quantity_class as _qc` (an in-function import).
- `ems_exec/renderers/asset_3d.py:27` — `from layer2.emit.metadata.asset_3d import emit_asset_3d` (module-top).
- `data/lt_panels/panel_members.py:30` — `from layer1b.resolve.has_data import tables_with_data, tables_with_values`.

`ems_exec` is the *executor* (downstream of `layer2`), yet it reaches back up into `layer2` for quantity vocabulary and
3D emission. `data/` is the *shared platform* (imported by everything), yet `panel_members` depends on `layer1b`. This
is a layering cycle: the "lower" modules cannot be understood, tested, or reused without the "higher" ones. The symptom
is measurable — **264 function-body imports across layer1a/layer1b/layer2/ems_exec** exist largely to defer these edges
past import time and dodge circular-import errors. `code-quality-exec` M1 counts 17 such lazy imports inside `fill()`
alone.

**Why it matters at scale:** the cycle makes the true module graph unknowable from the imports (you must read function
bodies), blocks packaging any layer independently, and every new cross-layer need adds another lazy import rather than a
clean seam. **Recommendation:** hoist the genuinely-shared vocabulary (`quantity_class`, the unit/class maps) into a
neutral `config/` or a new `vocab/` module that BOTH `layer2` and `ems_exec` import downward; have `panel_members`
depend on a `data/`-level primitive, not `layer1b`. Safe (moves, no logic change), but a wide-import diff.

## A2 — MEDIUM — `validate/` vs `validation/` vs `config/validation.py`: three "validation" namespaces

(Also raised by `code-quality-platform` F5 — recorded here for the architecture angle.) `validate/` = the in-pipeline
pre-L2 pass + render verdicts; `validation/` = the external black-box HTTP cert framework; `config/validation.py` = the
knobs for the *first* one. Three grep-colliding names for three genuinely-different concerns, distinguished only by
docstrings; the cert framework's own env vars are even prefixed `V48_VALIDATE_*`. **Recommendation:** rename the external
framework to `certify/` (self-contained, mechanical import rename). Breaking-but-mechanical.

## A3 — MEDIUM — Three implementations of "read a scalar config knob"; three of "read the DB"

- **Config homes:** `app_config` (309 rows), `data_quality_policy` carrying generic `scope_map.*`/`placeholder.*` rows,
  and `viewer_policy` smuggling scalars as `page_key='__knob__:<key>'` rows (`db/round2_config_schema.sql:12-17`). Three
  lookup conventions, three failure modes, for the same "named scalar" concept (`database` lens F7).
- **DB doors:** `data/db_client.q()` (psql subprocess, no params), `registries/neuract/_db.py` (pooled psycopg2, `%s`
  params — the *right* one), and raw `psycopg2.connect()` in `validate/payload_lookup.py` (bypasses `conn_env` routing).
  The hottest path uses the weakest door (`platform` F3, `layers` finding 3).

Both are "solved three ways" smells that the atomic-structure rule was meant to prevent but does not address (it governs
file granularity, not cross-file idiom convergence). **Recommendation:** one pooled/parameterized read door generalized
from `registries/neuract/_db.py`; fold the two secondary knob stores into `app_config` sections. Risky (hot path) but
behavior-preserving — this is the single highest-leverage architectural consolidation and it removes the F9/F4
`_esc`-copied-18-times symptom for free.

## A4 — LOW — `services/` near-empty, `partition/` depends on a specific layer, `outputs/` holds code

- `services/` is 32 lines (one `dict_merge`) — a directory for a file; fine, but note the over-granularity.
- `partition/coupling_lookup.py:2-5` imports four readers from `layer1a/partition_inputs/*` — the "shared" partition
  subsystem depends on one layer's internals (`platform` F17). Either the readers move into `partition/` or `partition/`
  is really part of `layer1a`.
- `outputs/emit_correctness_battery.py` is a git-tracked test harness living in the run-artifacts directory and
  sys.path-hacking back to root (`platform` F12). Code does not belong under `outputs/`.

**Recommendation:** decide `partition/`'s owner and move accordingly; move the battery to `tools/` or `tests/`. Safe.

## What is genuinely good (keep)

- The forward pipeline shape (`1a∥1b → 2 → exec → guards → host`) is coherent and the fail-open/fail-closed asymmetry
  is applied consistently at each seam (route raises; stories/basket/resolver degrade).
- `run/parallel.py` as the single fan-out primitive, and `run/degrade_gate.py` as the single outage→terminal mapper,
  are exactly the right kind of small shared seam.
- The atomic-file rule genuinely aids navigation in `layer1a`, `layer1b/{resolve,guardrail,basket}`, and
  `ems_exec/executor` — the debt is concentrated in `layer2` (see `code-quality-layers` 1/2), not the tree as a whole.
