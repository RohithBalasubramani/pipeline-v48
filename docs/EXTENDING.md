# EXTENDING V48 — the plugin points

One page per question "I want to add a NEW ___ — what do I touch?". The repo's native plugin mechanisms, in fix-order
priority: a **DB row** (cmd_catalog tables / `app_config` via `config.app_config.cfg()`), then a **self-registering
atomic file**, then generic code (last resort). Every mechanism below is fail-open: a missing row / broken module falls
back to the shipped code default and never blocks import.

## New PAGE FAMILY
DB rows only — no code:
1. `cmd_catalog` page + card rows (pages/cards/`card_payloads` skeletons, `card_handling`, `card_grid_size`, recipes).
2. Enable routing: one `routable_pages` row per page_key (`config/available_pages.py` reads it; env
   `V48_AVAILABLE_PAGES` overrides; code default = the shipped 18).
3. FE (only if the family introduces new components): drop ONE barrel file — see "New CARD TYPE".

## New ASSET CLASS (e.g. Chiller fleet, Solar inverter)
DB rows only — no code:
1. Routing/concept vocabulary: `app_config layer1b.class_concept_hints` (tokens + concepts;
   `layer1b/resolve/class_from_subject.py` — the valid class SET is read live from the registry, so a new class
   appears automatically once resolvable).
2. Class resolution: `app_config vocab.asset_type_class` / `vocab.mfm_type_class` (canonical code → class) and
   `vocab.asset_name_class` (table-name needles → class, ordered) — `layer1b/resolve/asset_candidates.py`.
3. Engineering defaults: one `cmd_catalog.asset_class_default` row (`config/asset_class_defaults.py`).
4. Granularity: add the class to `app_config routes.panel_granularity_classes` ONLY if it is a panel-style aggregate
   (`config/asset_granularity.py`).

## New SPECIAL RENDERER (a handling_class that needs fan-out / GLB / LLM)
One new file + DB rows:
1. Drop `ems_exec/renderers/<name>.py` with `render(asset, card, ctx) -> payload` and
   `HANDLING_CLASSES = ("<class>",)` — the package `__init__` DISCOVERS it (self-registration); the host's
   special-vs-generic split derives from `ems_exec.renderers.special_kinds()`, so no host edit.
2. `cmd_catalog.card_handling` rows assigning cards to the new class.
3. If the class is member-scope (serve through the roster interpreter first): add it to
   `app_config renderers.roster_kinds`.
Rules a renderer must keep: NEURACT-only data, per-leaf honest-degrade, knobs via `cfg()` with code defaults.

## New CARD TYPE (a new CMD_V2 card)
DB rows + (at most) one FE barrel entry:
1. `cmd_catalog.card_payloads` seed (byte-faithful Storybook default) + `card_handling` + `card_grid_size` (+ fill/data
   recipes). The backend needs NO code — the generic executor fills any declared leaf.
2. FE: register the card's component in the right family barrel `host/web/src/cmd/components/<family>.ts`
   (`COMPONENTS: Record<card_id, Component>`), or a NEW barrel file for a new family — discovered by
   `components/index.ts` (import.meta.glob), no registry edit. A card needing a guarded view-model instead gets a
   `fill/*.tsx` module (same discovery pattern, wins over the direct spread).

## New AI PROVIDER (swap/add the LLM behind the pipeline)
Any OpenAI-compatible endpoint: NO code — set `V48_LLM_URL` / `V48_LLM_MODEL` (the shipped `openai_compat` provider
speaks vLLM/OpenAI/Groq/Ollama).
A different wire format (e.g. Anthropic): drop `llm/providers/<name>.py` implementing
`complete(system, user, *, url, model, timeout, temperature, seed, schema=None, max_tokens=0) ->
{"text", "finish_reason", "usage"}`, then select it via env `V48_LLM_PROVIDER` or the `app_config llm.provider` row.
ALL hardening (prompt-budget preflight, parse retry, truncation fail-fast, failure classification, obs telemetry, the
replay seam) lives in `llm/client.py` and is shared — a provider is ONLY the wire call. (The copilot's own :8201
client `copilot/llm.py` is deliberately separate.)

## New EXECUTOR piece
- **Roster slot MODE**: drop `ems_exec/executor/roster_modes_<x>.py` declaring `MODES = {"<mode>": handler}` —
  `roster.py` discovers it; the mode becomes writable in `card_fill_recipe` rows immediately.
- **Reducer**: `ems_exec/executor/reducers.py` is a DELIBERATELY closed vocabulary (fabrication control) — extend the
  one `reduce()` if-chain in place; single file, single touch.
- **Derivation**: add the formula fn in its quantity module and the descriptor row in
  `ems_exec/derivations/registry.py` `RESOLVERS[db_key]` (the documented per-DB provision).
- **Field kind / post-fill pass** (`ems_exec/executor/fill.py`): NOT a plugin surface — the pass order is a certified,
  order-sensitive algorithm; extend by editing fill.py deliberately.

## Deliberately NOT abstracted (leave-as-is, reviewed 2026-07-12)
- `reducers.py` closed vocabulary and `fill.py`'s pass chain (above).
- FE envelope renderers (`cmd/special.tsx`) — exactly three envelope shapes, shape-discriminated.
- `copilot/` and `knowledge/` LLM bindings — separate services with their own endpoints by design.
