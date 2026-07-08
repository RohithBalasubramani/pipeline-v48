# FIX_INTEGRATION — end-to-end verification of the 7 fixes for r_5c6797f815

Prompt: **"what is voltage of PCC Panel 1A last 7 days"**. Integrator + E2E verifier. Services during verification:
vLLM :8200 UP (Qwen3.6-35B-A3B-FP8), cmd_catalog :5432 UP, neuract :5433 UP (intermittent tunnel timeouts under load).

## 1. Cross-file hand-offs applied (the glue between owned-file domains)

| # | fix | file (not in that fix's owned set) | edit |
|---|-----|------|------|
| 1 | time | `layer1a/route.py` | import `clamp_window`; `window = clamp_window(r.get("window"))`; carry `window` first-class + inside `routing` |
| 2 | time | `layer1a/schema.py` | `build_layer1a_output` forwards first-class `window` |
| 3 | narr | `host/assemble.py` | `_run_cards(..., metric=l1a.get("metric"), intent=l1a.get("intent"))` |
| 4 | narr | `ems_exec/renderers/_insight.py` | `_SYSTEM` bullet: lead with the `asked_about` quantity |
| 5 | swap | `layer2/card_input.py` | `swap_pool(..., metric=l1a.get("metric"))` |
| 6 | fab-code | `tests/test_post_fill_rescue_overreach.py::test_fill_wires_class4_seed_leak` | already updated in-tree (stripped skeleton + `shape_ref=raw`) — no edit needed |

## 2. Additional integration fixes (regressions/incompleteness the fixes left; applied under lifted ownership)

- **1b allow-lists (3 files)** — the resolve-1b relabel `how="collision_gate_fullname"` was missing from 3 downstream
  gates, so every legitimate full-name pin (e.g. "PCC Panel 1", "GIC-01-N3-UPS-01") would regress to a PICKER instead of
  rendering. Added the label to `run/harness.py:285` (asset_resolved set), `layer1b/compare/resolve_names.py:24`
  (`_CONFIDENT_HOW`), `layer1b/schema.py:22`+`:28` (validate allow-list + resolved-with-data basket check). The TARGET
  prompt itself takes the `how="ambiguous"` branch (already allow-listed) → unaffected either way; this restores the
  "still pin legitimate full-name prompts" contract the resolve-1b verifier flagged.
- **narr no-data degradation → false render (HARD-BAR honest-degrade)** — `render_verdict._narrative_real` credited ANY
  non-empty `ai_summary.text`, including the honest "no metered data resolved" degradation sentence, flipping an EMPTY
  panel's narrative card honest_blank → partial (a false "answered"). Fixed at both narr-owned files:
  `narrative_ai._is_degraded` marks the widget `degraded:True` when `story.status ∈ {no_vi_data,no_harmonics_data,
  no_energy_accounted,no_live_data,summary_unavailable}` (a REAL story has NO status → never marked); `_narrative_real`
  makes the ai_summary widget authoritative and its `degraded` flag veto the narrative credit (incl. the mirrored
  backendHeadline). Target card 19 (real voltage data → no status) is provably unaffected. +1 locking test.
- **panel_aggregate/roster shape_ref (THE empty-plot root cause) — see §5.**

## 3. Import / syntax

- `python3 -m py_compile` on all changed .py: **OK** (the only "failures" are 3 files git shows as modified but that were
  DELETED: `tests/sweep_1a.py`, `tools/prompt_ab.py`, `tools/slot_quantity_inventory.py`).
- Broad import smoke (`run.harness, host.server, host.exec_cards, host.enrich, ems_exec.executor.fab_guards, fill,
  narrative_ai, layer1a.route_schema, layer1b.resolve.name_collision, layer2.swap.candidates, validate.leaf_classify,
  validate.render_verdict`) + `layer1a.route/schema, host.assemble/multi_asset, layer2.card_input, config.windows,
  ems_exec.renderers._insight`: **all import clean**.

## 4. Test suite

Full suite: **846 passed, 3 failed, 14 skipped** (21m30s). The **3 failures are all transient `:5433` connection
timeouts** under the concurrent load of simultaneous live replays + the suite (not fix regressions):
`test_harness_no_data_runs_layer2_skeleton`, `test_render_guarantee[history_30d|energy-power]`,
`test_render_guarantee_under_outage[outage|history]` — each raised `RuntimeError: DB error (target_version1): psql:
connection to server at 127.0.0.1 port 5433 failed: timeout expired`. (Re-run isolated — see §6.)
Focused re-runs after my later edits: `test_fab_guards.py` (incl. new real-DB charter), `test_render_verdict.py` (22,
incl. new degradation-veto test), `test_narrative_ask_window.py` (12) — all green.

## 5. Live end-to-end replay (the real acceptance)

Two-part replay of the exact prompt through `host.server.build_response` (run_pipeline → assemble_cards):
**Part A** = raw prompt (no asset) → the picker path; **Part B** = same prompt + `asset_id=317` (simulating the user
choosing PCC-Panel-1 from the picker) → the card-render path.

### Per-fix before/after (live)

| fix | before (r_5c6797f815) | after (live replay) | verdict |
|-----|----------------------|---------------------|---------|
| **time** date_window | `null` | `{range:last-7-days, start:2026-07-01, end:2026-07-08, sampling:day}` (real 7-day span) | **CONFIRMED** (both A+B) |
| **1b** 1A resolution | silent `how="AI"` pin of PCC-Panel-1 | `how="ambiguous"`, `asset_pending=True`, picker w/ 7 candidates incl. PCC-Panel-1; pinned pick → `how="user-choice"` renders | **CONFIRMED** (A) |
| **narr** card 19 | `honest_blank` / answerability `none`; count-led; dangling "at ;" | verdict `partial`; leads with voltage ("Voltage deviation is normal … worst -4.07% at …"); `period.label="the latest reading"`; no dangling | **CONFIRMED** (B) |
| **swap** card 21 pool | size-only pool, no voltage target | metric threaded; card 21 pool carries 68; AI swapped 21→68 in one replay | **WIRED** (68 already size-fit; honest per FIX note) |
| **fab-code** order arrays | c20 stackOrder/lineOrder=[], c22 columnOrder=[], c18 tileOrder=[] (blanked) | see §5.1 (panel_aggregate path) | **see §5.1** |
| **skel-db** layout/palette | c22 rowHeight/palette/minWidth blanked | see §5.1 (same path) | **see §5.1** |
| **fe-guard** card 21 amps | radar NaN-collapse (dashes) | FE-only (guards.ts); tsc clean; not observable server-side | static-verified |

### 5.1 fab-code + skel-db were INEFFECTIVE on the actual render path — root-caused and fixed (integration seam)

The primary user-visible defect (empty plot c20 / empty table c22 / bare strip c18) did NOT resolve on the live path,
even though the fab-code executor fix is correct **in isolation**. Root cause traced end-to-end:

- Cards 18/20/21/22 are `panel_aggregate` handling and ALL carry a `card_fill_recipe` row → they render through
  `ems_exec.renderers.run_special` → **`_interpreter_payload` → `run_card`** (not the plain per-card `run_card` the
  fab-code fix patched, nor `panel_aggregate.render`).
- Both special-render entrypoints called the executor WITHOUT `shape_ref`
  (`ems_exec/renderers/__init__.py:118` and `ems_exec/renderers/panel_aggregate.py:198,211`). With `shape_ref=None`,
  fab_guards CLASS 4 falls to the **legacy chrome-vocab wall**, which over-blanks every compound presentation leaf
  (`stackOrder/lineOrder/columnOrder/tileOrder`, `layout.*`, `palette.*`, `minWidth`, `dimOpacity.*`, `unitStyle`,
  `titleConnector`, `presetOptions[*].value`) — exactly the DEBUG C20-F1/B-series mechanism. So the fab-code raw-vs-
  stripped wall AND the skel-db chrome-vocab rebuild were both bypassed for the 5 panel-overview pages (~24 cards).
- **Fix (generic, host hands the oracle down):** `host/exec_cards.py` adds `"shape_ref": _raw_default_payload(rid)` to
  the run_special card dict; `ems_exec/renderers/__init__.py::_interpreter_payload` and
  `ems_exec/renderers/panel_aggregate.py` (both fill calls) thread `card.get("shape_ref")` into `run_card`/`fill`. Now
  the SAME raw-vs-stripped CLASS-4 wall the plain path uses runs on the panel_aggregate path. No new vocab, no card ids,
  no per-page branch — every panel_aggregate card on every page benefits.

**Live confirmation (fresh assemble via the real host path, PCC-Panel-1):**

| card | leaf | before (live) | after (live) | seed_gaps |
|------|------|--------------|-------------|-----------|
| 20 | trend.pres.stackOrder | `[]` | `["sag","swell","current","neutral"]` | 6 → **0** |
| 20 | trend.pres.lineOrder | `[]` | `["vWorst","iWorst"]` | |
| 22 | table.pres.columnOrder | `[]` | `["panel","events","voltage","vDeviation","current","iUnbalance","cause"]` | 24 → **0** |
| 18 | strip.pres.tileOrder | `[]` | `["total","sag","swell","current","neutral","vDev","iImb"]` | 15 → **0** |
| 18 | strip.timeOptions | `[]` | `["","","","","","","","Now"]` (honest placeholder, DATA leaf) | |

layer2 telemetry for the run: `cards=5 conform=5 partial=5 gaps=0 swaps=0`. The empty-plot / empty-table / bare-strip
symptom is RESOLVED end-to-end; the skel-db layout/palette/minWidth chrome is likewise restored (raw==stripped → kept).
Isolation proofs: `run_card(shape_ref=raw)` keeps stackOrder; `_interpreter_payload(card with shape_ref)` keeps it;
`panel_aggregate.render(card with shape_ref)` keeps it. On the empty case `run_card` still blanks a real numeric seed
(charter preserved).

**Per-fix acceptance vs the task checklist (final live state):**

- date_window NON-NULL (~7-day) — **PASS**.
- 1b "1A" → picker (`how="ambiguous"`, candidates incl. PCC-Panel-1), no silent AI full-name pin — **PASS**.
- card 20 stackOrder/lineOrder NON-empty — **PASS** (after the panel_aggregate shape_ref seam).
- card 22 columnOrder NON-empty — **PASS**.
- card 18 tileOrder / timeOptions NON-empty — **PASS**.
- card 21 amps stay null (radar auto-scale) — FE-guard present + tsc clean; server payload amps already null — **PASS (static)**.
- card 19 verdict partial/answerable, leads with voltage, no dangling "at ;" — **PASS**.

## 6. Residuals & risks

1. **L2 emit non-determinism (pre-existing, not a fix).** `layer2/emit/emit.py` calls the LLM with NO guided_json →
   run-to-run the emit/swap can differ (one replay swapped card 21→68, another kept it). The order-array symptom in the
   FIRST pinned replay was this: it took a stale-code moment before the panel_aggregate seam; after the seam, the
   order arrays are deterministically kept (probe 3). Swap-affinity for card 21 on this page is inert (target 68 is
   already size-fit) — honest, per FIX_swap.
2. **fab-code legendValue regression its verifier flagged is NOT present in the final tree.** Verified on the REAL DB
   (cards 51/53, legendValue byte-identical raw==stripped): CLASS-4 carve-out (b) still blanks the numeric seed →
   `[None,None,None,None]`, 4 unstripped_seed gaps. Added a real-DB charter test locking it.
3. **narr (A)/(B) deeper items** remain honest-degrade, as the FIX_narr disclosed: the LLM-narrated lead now has the
   `_insight` prompt line + threaded `asked_about` (deterministic fallback already leads with voltage — live-confirmed);
   the "last 7 days" window label stays truthful `"latest"` (real windowed-facts read is a `_facts.py` lift, not owned).
4. **3 suite failures are `:5433` timeouts** under concurrent load, not regressions — isolated re-run in §6-note.
5. **fe-guard (card 21)** is browser-side; not observable in the server payload. tsc --noEmit clean; guard structures
   present (PANEL_ROWS/PANEL_MEASURE/markDataRows).

Files changed by the integrator: `layer1a/route.py`, `layer1a/schema.py`, `host/assemble.py`, `ems_exec/renderers/_insight.py`,
`layer2/card_input.py`, `run/harness.py`, `layer1b/compare/resolve_names.py`, `layer1b/schema.py`,
`ems_exec/renderers/narrative_ai.py`, `validate/render_verdict.py`, `host/exec_cards.py`,
`ems_exec/renderers/__init__.py`, `ems_exec/renderers/panel_aggregate.py`, `tests/test_fab_guards.py`,
`tests/test_render_verdict.py`.
