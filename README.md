# pipeline_v48 — atomic 3-layer payload-morph pipeline

**Wiring:** frontend prompt → `layer1a` ∥ `layer1b` (parallel) → join → `layer2` (per atomic unit; interdependent groups get a one-time shared-context pre-pass) → `run/assemble` → PageFrameEnvelope (ONE `{data+metadata}` payload per card).

**Metadata-vs-data split (Decision A):** `layer2` (AI) emits `{exact_metadata, data_instructions}` per card. `workers` (deterministic) PARSE the instructions and FILL the DATA; the FE hook (see `fe_contract/`) owns live state + interactivity + interdependency.

## Where each concern lives
- `run/` orchestrator · `layer1a/` router · `layer1b/` asset+basket · `layer2/` swap + emit (morph core)
- `workers/` data-fill + aggregation + shared-context + stitch · `frames/` DATA-fill target shapes (the surviving dialects)
- `partition/` group detection · `data/` DB clients · `registries/` byte-identical defaults · `contracts/` JSON schemas
- `llm/` Qwen client · `obs/` failure log · `fe_contract/` FE-owned hook CONTRACT (markdown only) · `tests/` · `db_build/` (quarantined)

Design docs (the spec spine) live at the `pipeline_v48/` root: `V48_DESIGN_NOTES.md`, `V48_BUILD_SPEC*.md`, `V48_PAYLOAD_MORPH_CORRECTION.md`, `V48_INTERDEPENDENT_CARDS_DESIGN.md`, `V48_STORYBOOK_MORPH_VERIFICATION.md`, etc.

**Build references:** RTM (`HeatmapViewModel`/`RailViewModel`) + panel-overview HPQ (`HpqPresentation`). Acceptance = LIVE Storybook §B4 sentinel (`fe_contract/acceptance_sentinel.md`).
