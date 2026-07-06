# ems_exec — the PER-CARD NEURACT EXECUTOR contract

The V48 render path (user-locked):

```
prompt → 1a ∥ 1b → Layer 2 { exact_metadata (= CMD_V2 props) + data_instructions } → ems_exec EXECUTOR → completed payload → FE renders directly
```

The executor is `layer3/clean.py` + `layer3/apply.py` fill logic PROMOTED to the primary path. NO frames, NO
validation, NO daphne WS, NO simulator. Layer 3 is being retired; its fill logic lives here now.

## What the executor consumes

### `exact_metadata` (the payload)
The card's CMD_V2 component props, authored in full by Layer 2 — the config tier (names/titles/units/labels/colors/
legends/thresholds) is already literal. Its **data leaves** carry Layer-2's seed/default numbers; the executor STRIPS
those and refills only what neuract really has.

### `data_instructions` (the recipe)
Only `.fields[]` (+ optional `.window`) are consumed. Each `fields[]` entry:

| field | meaning |
|---|---|
| `slot` / `path` | the payload leaf this field fills (bound as `data.<slot>` then `<slot>`; falls back to `metric` / `target_column`) |
| `kind` | `raw` \| `derived` \| `const` \| `text` \| `event` |
| `role` | series / kpi / column / line / cell / tile / row / spoke (informational) |
| `metric`, `unit` | quantity class (used only for the range/sign gate) |
| `column` | the REAL neuract column (raw / event) — must exist on the resolved table |
| `agg` | avg / last / sum / count / derived (informational at per-card scope) |
| `source` | live / test-db / $ctx (informational; the executor reads live neuract) |
| `value` | the literal (const / text only) |
| `fn` | the named recovery-library fn (derived only) |
| `base_columns` / `target_column` / `scope` | derived only (the fn's inputs + the frame column it fills) |

`data_instructions.window` = `{start, end}` (ISO or bare `YYYY-MM-DD`) — the date window for windowed-delta derivations
and bucketed series. `ctx.window` overrides it.

The executor does **not** consume `data_instructions.ems_backend`, `.consumer`, `.binding`, `.orientation`, etc. —
those drove the retired WS/aggregate path. There is **no aggregate kind**.

## Per-kind fill rules

- **raw** → the field's `column` from `neuract.latest()` (or `neuract.window()`), range/sign VERIFIED
  (`apply.verify_value`). Column absent on the table → honest-blank.
- **derived** → `registry.run(fn, ctx)` over a live-data superset ctx (latest row + window baselines + `nameplate:*`
  pseudo-cols), mirroring `apply._run_substitute_fn`. Missing inputs / unknown fn / no nameplate → honest-blank.
- **const** → a per-asset NAMEPLATE slot (rated/contracted/target, per `config.nameplate_slot_map`) resolves from the
  REAL nameplate (`config.nameplates`), NEVER the baked seed literal. Any other const keeps its literal.
- **text** → the literal string, kept as-is.
- **event** → the rising-edge count of a boolean flag `column` over the window (per-card bucketed read + transition
  scan). Column absent / no data → honest-blank.
- anything else / no real value → **honest-blank**.

## Seed-strip + honest-degrade (invariants)

1. Before filling, EVERY data leaf is blanked type-preservingly (`apply.all_data_leaf_paths` +
   `apply.suppress_leaves`: list→`[]`, dict→`{}`, scalar→`None`) and every narrative-slot string is scrubbed
   (`apply.scrub_narrative`). **No seed number survives** — not even inside prose.
2. A None/scalar NEVER nulls an array or dict leaf (the FE `.map()`s series/legend arrays) — `_set_leaf_typed`.
3. The shape is COMPLETED: every declared field leaf exists (a gap is `null`, never absent) so the FE mapper never
   reads `undefined`.
4. A missing column / empty table / read error → `None` (`'—'` in the FE), **never fabricated**, **never
   premier_energies**.

The completed payload = the CMD_V2 props with real values where neuract has them and honest blanks elsewhere. The FE
renders it directly.

## SCOPE — per-card only (aggregation intentionally OUT)

There is **no aggregate kind, no multi-meter fetch, no member resolution** in this build (the user retired fan-out for
now to keep the architecture simple). A panel-aggregate card whose leaves cannot be filled from ITS ONE resolved table
simply honest-blanks. The membership metadata (`cmd_equipment.feeder`, `panel_topology`) is ready to reuse LATER; the
executor never touches it.

## Entry points

- `ems_exec.serve.run.run_card(exact_metadata, data_instructions, asset_table, db_link=None, window=None)`
  → the completed payload (plain function; never raises; no WS).
- `ems_exec.executor.fill.fill(payload, data_instructions, ctx)` → the completed payload
  (`ctx = {asset_table, db_link?, window?}`).
- `ems_exec.data.neuract.latest / window / bucketed / present_columns` — the ONE neuract door (timestamp_utc, no
  panel_id, only-existing columns).

## DB-driven config

- DSN + ts column/cast → `config/neuract_dsn.py` (cmd_catalog `app_config` knobs `neuract.*` with the
  `config/databases.py` constants as code-defaults). Default target:
  `postgresql://postgres@127.0.0.1:5433/target_version1?options=-csearch_path%3Dneuract`.
- Range/sign gates, nameplate ratings, derivation bindings → the existing `config/*` accessors (each a cmd_catalog row
  with a code-default fallback).

## What is REUSED from layer3 (not reinvented)

- `layer3/apply.py`: `verify_value`, `all_data_leaf_paths`, `suppress_leaves`, `scrub_narrative`, `_set_path`,
  `_leaf_at` — and the `_run_substitute_fn` derivation-ctx RECIPE (superset ctx + nameplate pad + `registry.run`),
  re-expressed in `fill._run_derived` over the new neuract reader.
- `layer3/clean.py`: the strip → per-field fill → complete-shape ORDER and the `_set_leaf_typed` / `_leaf_path_for` /
  `_complete_shape` logic (promoted into `fill.py`).
- `ems_backend/lt_panels/derivations/registry.run` + the derivation modules — the named recovery fns.
- `config/nameplates`, `config/nameplate_slot_map`, `config/derivation_binding`, `config/quality_policy` — DB-driven.
