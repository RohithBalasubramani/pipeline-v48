# Refactor audit 2026-07-12 — ADDENDUM: hardcoded business-logic MAPPINGS sweep

Scope: the mapping surfaces the hardcoding/config-centralization dimensions did not cover — page mappings,
asset mappings, story mappings, card mappings, plus a keep/move verdict for each. Complements
`hardcoding.md` (thresholds/knobs) and `config-centralization.md` (config surfaces).

## Applied in this sweep (behavior-identical; DB row mirrors the code default byte-for-byte)

### A1. narrative_ai card→page fallback map → `renderers.narrative_card_page` (json knob)
- **Files**: `ems_exec/renderers/_story/__init__.py` (new `card_page()` accessor over the `CARD_PAGE`
  code mirror), `ems_exec/renderers/narrative_ai.py:41` (reads the accessor).
- **Seed**: `db/seed_narrative_card_page.sql` (applied). A new AI-summary card on an existing page now
  dispatches with a row edit, no code change — the same "no card-id special-case" direction as the
  card-63 hardcode removal.

### A2. 1b table-name→equipment-class fallback vocabulary → `vocab.asset_name_class` (json knob, order preserved)
- **File**: `layer1b/resolve/asset_candidates.py` (new `_name_class_rules()` accessor over the
  `_NAME_CLASS` code mirror; `dg_` keeps its startswith semantics in code).
- **Seed**: `db/seed_asset_name_class_vocab.sql` (applied). The needles are SITE naming ('lamination',
  'curing', 'bpdb') — a new plant's tokens extend with a row edit. Order matters (UPS before Panel,
  Incomer before DG) — json list preserves it. Guarded by `tests/test_validate_streamline.py::test_name_class_port`.
- Same session (parallel edit): `_ASSET_TYPE_CLASS`/`_MFM_TYPE_CLASS` wrapped as
  `vocab.asset_type_class`/`vocab.mfm_type_class` via `_class_code_maps()`.

### A3. host special-kind split derived from the renderer registry (parallel edit, recorded here)
- `host/exec_cards.py` `_SPECIAL_KINDS` literal → `ems_exec.renderers.special_kinds()` (discovered
  HANDLING_CLASSES ∪ DB-driven roster kinds), fail-open to the shipped four.

## Examined and KEEP (deliberate hardcodes — do not move to DB)

- **`layer2/emit/instructions/endpoint_registry.py` `PAGES` snapshot (page→ems_backend-endpoint map)** — the baked
  list is a DELIBERATE anti-drift fix (docstring: the hand-maintained duplicate caused the
  power-quality-history straggler). Endpoints only change when ems_backend routes change (a code change
  anyway); a DB row would re-open the drift channel with no verification. NOTE: the orphan
  `cmd_catalog.endpoint_policy` table (dead-code.md) has a DIFFERENT shape (page×resolver_scope, missing
  load-anomalies / energy-power-history) — do NOT "wire it up" as this registry's source; it would change
  behavior. Also `consumer_binding/__init__.py:17` still says the registry "parses ems_backend's OWN
  _PAGES route table" — stale prose, the snapshot is baked.
- **`_story/__init__.py` `BUILDERS`** — page_key→Python-module dispatch; values are code objects, DB can't
  hold them. The DB-tunable half is A1's card→page map.
- **`ems_exec/renderers/__init__.py` `_BY_KIND`** — handling_class→renderer-module wiring (code objects).
- **`ems_exec/executor/derived.py` `_PERIOD_COUNTER_COLS` / `_INTEGRATION_POWER_COLS`** — documented
  contract-local mirrors of the columns the fns ALSO declare in `derivation_binding.base_columns` (already
  a DB table); moving them would decouple the fn from its own contract.
- **`ems_exec/renderers/_story/_facts.py` `LIVE_COLS`** — each verdict reads named keys in code; the list
  changes only with verdict code. (The broader column-name-knob question is hardcoding.md F10, owner call.)
- **`grounding/schema_fingerprint.py` marker columns** — each fingerprint routes to a code path per shape;
  algorithmic detection, changes only with code.
- **`ems_exec/executor/verify.py` `_POLARITY_TOKENS`** — unit physics (kVArh IS reactive), not site policy.
- **`layer1b/basket/avg_phase.py`** — column grammar (`*_avg` ↔ R/Y/B suffixes), mechanics.
- **`ems_exec/data/neuract.py` `_SAMPLING`/`_GRAN_SECONDS`** — granularity mechanics.
- **`copilot/aliases.py` `METRIC_ALIAS`/`ASSET_ALIAS`** — curated source for the OFFLINE sqlite index
  build of a deliberately decoupled service (its docstring records the no-alias-table state); env-config is
  copilot house style. Revisit only if an alias table lands in cmd_catalog.
- **`run/harness.py` `_MAX_ATTEMPTS = 2`** — the 2-loop architecture, mirrored in prompts/design docs.
- **AI prompts** (`layer1a/prompts/*.md`, `layer1b/prompts/*.md`, `layer2/prompts/data_instructions_v2.md`,
  `layer2/emit/morphmap/prompt.md`, `knowledge/prompts/ems.md`, `copilot/prompts.py`) — atomic .md files are
  the sanctioned home (fix order: prompts → DB rows → code); enum lines are interpolated from DB-driven
  vocab (METRIC_VOCAB, intents.vocab) so prompt and clamp can't drift. Concrete asset names inside them are
  few-shot examples, not mappings. No prompt embeds a threshold or card/page map that isn't DB-interpolated.

## Closeout status (2026-07-12, later the same day)

- hardcoding **F10** — EXECUTED (option b): roster column half-knob retired; see EXECUTED_AND_FOLLOWUPS Batch 7.
- config-centralization **F6** — EXECUTED: 54 scalar rows migrated into app_config behind type-discriminated
  shims (policy_read/quality_policy/viewer_policy), parity-verified; legacy rows retained for transition.
- config-centralization **F8** — RESOLVED via option (b): the never-cache-empty `_load` + retry backoff landed;
  default-off is a tested contract (item17/route guided_json + morphmap producer suites), so no flip.

## Owner calls — decided and applied (2026-07-12, later)

- hardcoding.md **F7** — owner picked **0.9 for both**: `nameplate.nominal_pf` seeded 0.9
  (db/seed_pf_of_record.sql) + code mirror 0.8→0.9 in derivations/nameplate.py. Intended change: the
  feeder_rated_kw fill path now matches derive_ratings (was 12.5% lower).
- hardcoding.md **F3 follow-up** — owner said "check cmd v2": CMD_V2 wires the per-class deviation
  (config_defaults.py DG=5.0), so `statutory_band` now resolves per-class via ctx asset_table (DG ±5%, others
  ±10%, knob fallback). NEW tests/test_statutory_band_per_class.py.

## Final closeout (2026-07-12, "implement remaining")

- config-centralization **F7 — EXECUTED**: NEW `config/endpoints.py` is the ONE :8770 home (HOST_PORT/HOST_BASE,
  env-overridable, no-DB import; re-exports the llm/config vLLM endpoint + ems_backend origin). Rewired:
  host/server.py PORT, sweep/config.py BASE_URL (V48_VALIDATE_BASE still wins), admin/config.py HOST_API,
  tools/payload_diff/capture.py DEFAULT_HOST — all five now read one constant (verified equal at import).
  ops/tunnel_monitor.py probes via config.databases.conn_env(DATA_DB) instead of a hardcoded :5433 psql target
  (smoke-tested live). Copilot (:8772) stays decoupled by design; SB_BASE stays DB-knob-first in host/notes.py.
- **Epoch floors — CLOSED as deliberately distinct**: chart.epoch_list_floor (1e10) is a lenient LIST-shape test
  for axis detection; fab_guards.epoch_ms_floor (1e12) is a strict per-VALUE fabrication verdict. Unifying either
  way breaks a real case (second-resolution axes / cumulative-kWh outliers). Cross-referenced DO-NOT-UNIFY notes
  at both sites (executor/epoch.py, fab_guards/knobs.py).
- config F6 **phase 2 — PREPARED, apply-later**: `db/drop_legacy_knob_homes_phase2.sql` deletes the 52+3 legacy
  rows behind self-guarding parity checks (aborts on any divergence). Dry-run green (rollback). Run after ≥ one
  clean cert/sweep cycle; the legacy fallback READS stay in code (quality_policy's raising outage layer).
