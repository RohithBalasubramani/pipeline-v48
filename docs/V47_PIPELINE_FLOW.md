# V47 Pipeline Flow — grounded from `pipeline_v47/pipeline.py`

> **⚠️ HISTORICAL — V47 ONLY (banner added 2026-06-29).** This file is a factual snapshot of the *old* V47 orchestrator, NOT the current V48 model. The canonical CURRENT pipeline is `V48_DESIGN_NOTES.md` (+ the V48 build-spec set): **3 pure-AI layers (1a, 1b, 2)**, Qwen 3.6 mandatory in each, deterministic helpers support-only. Several V47 stages below are **RETIRED in V48** — read them as history, not current behavior:
> - **L5 build** and **L6 / L6.2 render-shaping** are RETIRED; data-domain aggregation RELOCATES into OUR pipeline's worker/helper functions (not a separate render layer, not backend2 reuse).
> - The **outer loop / reloop / L1 re-route** (`MAX_OUTER`, `REROUTE_TOL`, `infeasible_for_spec`) is RETIRED — V48 does NOT reloop or re-route; failures are LOGGED with exact errors instead.
> - **narrate** is PARKED in V48.
> - V48 wiring is FRONTEND PROMPT → 1a ∥ 1b (parallel) → join → Layer 2 (per atomic unit; interdependent groups get a one-time shared-context pre-pass) — NOT the linear L1→L2→L3→L4→L5→L6 chain shown below.
> - DB counts cited below reflect the V47-era catalog; the V48 catalog is REBUILT (145 cards / 75 page_specs / 280 components). The "29 page_specs" figure here is V47-era.

> Read directly from the orchestrator source on 2026-06-23 (not memory). The spine V48 collapses into 3 layers (1a, 1b, 2).
> Entry: `python3 pipeline.py "<prompt>"` → emits `render_demo.json` → host renders at `http://100.90.185.31:3147`.
> LLM: `Qwen/Qwen3.6-35B-A3B-FP8` at `http://localhost:8200/v1/...`, temp 0, JSON mode, thinking off.

## Ordered stages (as the orchestrator runs them)

| Stage | Call | AI? | In → Out |
|---|---|---|---|
| **L1 route** | `route_l1(prompt)` | **AI** | prompt → `page_key` + `metric` + `intent` (over 29 `page_specs`, grouped by shell; card titles from slot map) |
| **L1 asset** | `resolve_asset(prompt)` (column_resolve) | **AI** | prompt → exact meter/table; or `ambiguous` → writes `asset_choice.json` (frontend AssetPicker) → re-run via `PIPELINE_ASSET_ID` |
| **L3 columns** | `resolve_columns(+3.5)` (column_resolve) | **AI** | per-card (cached by metric,intent,table,card_id): card recipe + asset cols → real/probable columns (honest, no hallucination) |
| **L2 select** | `layer2_swap.run` / `l2_select`=`layer4.decide` | **AI** | page's real cards → keep / swap / combo. Swap pool = `card_grid_size` ±15% (`size_candidates`) — the **sizing** axis |
| **L4 slot** | `resolve_slot` → `l3_data_gate`(AI) + `_renderable`(det) + `l2_select`(AI) | **AI** | per slot: keep \| swap \| **reloop**. Payload-fillability gate; reloop escalates to L1 re-route |
| **L5 build** | `render_contract.build` | det (contract) | card → bindings + design + cmd_component + controls |
| **L6 fill** | `fill` → `l6_shape` (l6.py) | **AI** | bindings + formula library + asset cols → AI-authored SQL (guardrailed, SELECT-only) → real series from `lt_panels` |
| **L6.2 agg** | `l62_aggregate_shape` (l6_2.py) | **AI** | panel-scope aggregate/SLD card → AI config → `ems_aggregate` strategy → nested payload (no flat series) |
| **narrate** | `narrate` (AiSummary) | **AI** | page's computed numbers → 1-sentence insight (grounded, invents nothing) |
| **gates/emit** | `number_gates.gate_cards`, `HOST_RENDERABLE`, `collapse_combos` | det | NULL impossible values; drop non-mountable cmd_components; collapse combo members → `render_demo.json` |

## Control flow
- **Outer loop** `MAX_OUTER=2`: route → L2 select → per-slot resolve; a slot that can't be served records an asset-scoped dead-end in `infeasible_for_spec` and triggers an L1 **re-route** (different page, same metric+intent). Stops on: all slots filled, frontier exhausted, or no better page.
- **Asset is pinned once** at L1 (never re-resolved on re-route); **metric+intent frozen** at L1 (re-route changes only the page).
- **Slot = EMS cell**: each slot bound once to its `page_layout_cards` cell; swaps/re-routes refill the SAME cell (positions never move). `REROUTE_TOL=0.15`.
- **Single-responsibility gates**: L3 = data gate (AI, fail-open), L4 = render gate (`_renderable`, deterministic). KEEP iff both pass.

## AI call sites (every `llm()` invocation — what survives into V48's pure-AI layers)
1. `route_l1` — page route + metric + intent.
2. `resolve_asset` / `resolve_columns` (column_resolve) — meter pin + per-card column resolution.
3. `layer2_swap.run` / `layer4.decide` — card keep/swap/combo selection.
4. `layer4.feasible` (l3_data_gate) — per-card payload-fillability gate.
5. `l6.shape` — authors the data-shaping SQL.
6. `l6_2.aggregate_shape` — panel-aggregate strategy/config.
7. `narrate` — AiSummary insight.

> NOTE: This file is FACTUAL V47 background only. The V48 mapping/disposition is NOT recorded here — it lives in `V48_DESIGN_NOTES.md` and is set ONLY by the user's explicit statements. Do not infer a stage→layer mapping from this file.
