# pipeline_v48 — atomic 3-layer payload-morph pipeline

**Wiring:** frontend prompt → `layer1a` (route) ∥ `layer1b` (asset + basket) → join → `validate` (pre-L2 pass) →
`layer2` (per-card morph-emit: `{swap_decision, exact_metadata, data_instructions}`) → **host executor fan-out**
(`ems_exec` fills each card's payload from NEURACT — real values or honest-blank, never fabricated) → `fab_guards`
(post-fill fabrication classes) → PageFrameEnvelope (ONE `{data+metadata}` payload per card, rendered by `host/web`).

**Metadata-vs-data split (Decision A):** `layer2` (AI) emits `{exact_metadata, data_instructions}` per card;
`ems_exec` (deterministic) PARSES the instructions and FILLS the DATA; the FE hook (see `docs/fe_contract/`) owns
live state + interactivity + interdependency.

## Where each concern lives
- `run/` orchestrator (harness + reflect loop) · `layer1a/` router (+ `layer1a/partition/` group detection) ·
  `layer1b/` asset + basket · `layer2/` swap + emit + gates (morph core; `layer2/emit/instructions/` authors
  `data_instructions`, one file per field-kind)
- `ems_exec/` deterministic executor — `data/` the ONE neuract time-series door, `executor/` fill passes +
  `fab_guards/` (one guard class per module), `derivations/` pure recovery fns, `renderers/` special-kind renderers,
  `serve/` the run_card entry
- `validate/` THE pre-L2 validation pass + the post-fill render verdict · `grounding/` swap settle + default assemble
- `host/` HTTP surface + enrich/assemble/exec_cards seams · `host/web/` the React FE (payload IS props) ·
  `admin/` internal console
- `data/` resolution-time DB doors (cmd_catalog client, mirror-first registry, panel members, equipment, TTL cache) ·
  `registries/neuract/` LIVE neuract metadata doors · `db/` the flat cmd_catalog SQL ledger (fix_*/seed_*/schema)
- `config/` DB-driven knobs (`cfg()` over cmd_catalog.app_config; per-namespace policy readers share
  `config/policy_read.py`) · `llm/` the Qwen client + the ONE transient-retry policy · `lib/` homeless pure utilities
- `obs/` failure/stage/trace telemetry · `replay/` record/replay seams · `profiler/` perf capture ·
  `ops/` the :5433 tunnel unit + its watchdog
- `copilot/` standalone typeahead service (zero pipeline coupling) · `knowledge/` the separate concept-Q&A lane
- `tools/` read-only diagnostic harnesses (replay/AB/sweep) · `scripts/` state-building one-offs that WRITE the DB
- `tests/` (pytest, repo-root cwd) · `docs/` design docs + findings + the FE contract · `archive/` quarantined history

Deep-dive: `ARCHITECTURE.md` (onboarding-grade, surveyed 2026-07-12). Historical spec spine: `docs/V48_*`.

**Build references:** RTM (`HeatmapViewModel`/`RailViewModel`) + panel-overview HPQ (`HpqPresentation`).
Acceptance = LIVE Storybook §B4 sentinel (`docs/fe_contract/acceptance_sentinel.md`).
