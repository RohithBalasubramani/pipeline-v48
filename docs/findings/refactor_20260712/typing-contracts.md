# Refactor audit — TYPING & CONTRACTS (Python) — 2026-07-12

Scope: pipeline_v48 (`/home/rohith/desktop/BFI/backend/layer2/pipeline_v48`), excluding archive/, outputs/, artifacts.
Dimension: (a) untyped dict envelopes across layer boundaries, (b) contracts/ dir drift, (c) return-type / sentinel
ambiguity, (d) magic-string enums, (e) a minimal typed-core plan. All proposals respect the house rules
(atomic files, AI-first minimal code, per-leaf degradation, DB-driven config, DB-driven dispatch).

## Headline facts (verified by grep, not assumed)

- **Zero typed structures in the whole production tree.** `grep -rn "TypedDict|@dataclass|pydantic|BaseModel|NamedTuple" --include="*.py"` returns nothing outside archive/. A grep for annotated `def ... ->` signatures across layer1a, layer1b, layer2, run, host, validate, ems_exec/serve, grounding returns **0** hits. Every cross-layer envelope is a hand-assembled dict whose shape is documented only in docstrings and comments.
- **The `contracts/` dir is 10 empty stubs.** Every `contracts/*.schema.json` is 9 lines with `"properties": {}`, `"additionalProperties": true` and `"$comment": "TODO(v48): fill from V48_BUILD_SPEC_CONTRACTS.md"`. Nothing in production code loads them; the only test (`tests/test_contracts_roundtrip.py`) is `pytest.skip("TODO(v48): implement")`.
- The **real** contract enforcement is hand-rolled, annotate-only validators: `layer1a/schema.py`, `layer1b/schema.py`, `layer2/schema.py`, `validate/schema.py` — each re-declares its enums as inline set literals.

---

## F1 — contracts/ is a dead promise: 10 stub schemas never filled, never loaded (drift trap)

- **File:** `contracts/layer1a_output.schema.json:6` (representative of all 10: `data_instructions`, `exact_metadata`, `layer1a_output`, `layer1b_output`, `layer2_card_input`, `layer2_card_output`, `orchestrator_state`, `page_frame_envelope`, `pipeline_input`, `shared_context`)
- **Evidence:**
  ```json
  "properties": {},
  "additionalProperties": true,
  "$comment": "TODO(v48): fill from V48_BUILD_SPEC_CONTRACTS.md"
  ```
  `tests/test_contracts_roundtrip.py:5` → `pytest.skip("TODO(v48): implement")`. `grep -rn "contracts/" --include="*.py"` finds only that skipped test.
- **Why it matters:** the dir *names* the exact envelopes this audit cares about, implying enforcement that does not exist. Anyone trusting `layer2_card_output.schema.json` gets `additionalProperties: true` over `{}` — everything passes. Meanwhile the true shapes live in three different places (build fns, validate fns, docstrings) that can drift independently.
- **Proposed refactor:** pick one direction and finish it:
  1. *Fill + test-wire (preferred):* generate each schema from the corresponding builder's literal (`build_layer1a_output`, `build_layer1b_output`, `layer2/build._finalize` out-dict, `run/harness.run_pipeline` out-dict) and make `test_contracts_roundtrip.py` validate real fixture outputs against them with `jsonschema` **at test time only** (no runtime dependency, no runtime cost — consistent with the annotate-only validator pattern).
  2. *Or delete the stub dir* and declare per-layer `schema.py` the contract home (verify-before-delete rule: only the skipped test references it).
- **Risk:** low. **Behavior-preserving:** yes (test-only either way).
- **Tests guarding:** `tests/test_contracts_roundtrip.py` (skipped), `tests/test_layer1a_routing.py`, `tests/test_validate.py`.

## F2 — No typed core: every layer boundary passes hand-assembled dicts with zero annotations

- **File:** `layer2/build.py:658` (the `Layer2CardOutput` literal); siblings at `layer1a/schema.py:10`, `layer1b/schema.py:6`, `layer2/card_input.py:22`, `run/harness.py:200`, `host/enrich.py:201`, `host/server.py:137`, `ems_exec/serve/run.py:52`.
- **Evidence:** `layer2/build.py:658` builds the pipeline's most-consumed envelope as a raw literal:
  ```python
  out = {
      "card_id": ci["card_id"],
      "$ctx": ci["group_id"] if ci["is_group_card"] else None,
      "render_slot": raw.get("render_slot") or "",
      ...
      "_default_payload": _seedfree_default(dp),
  }
  ```
  Downstream, every consumer re-guesses the shape defensively: `run/harness.py:120` `[o for o in l2.values() if not (o or {}).get("conforms")]`, `host/enrich.py:141` `l2.get("swap_decision") or {"action": "keep"}`, `validate/build.py:114` `sd.get("origin") == "swapped"`.
- **Proposed refactor (this IS the minimal typed-core plan, item e):** add **annotation-only `TypedDict`s (`total=False`)** — one atomic `types.py` per layer folder, matching the atomic-structure rule; no pydantic, no runtime validation, no behavior change:
  - `layer1a/types.py` — `RouteResult` (route.py:111), `Card1a`, `Layer1aOutput`
  - `layer1b/types.py` — `Asset` (name/table/class/mfm_id/panel_id/has_feeders/member_scope), `ColumnBasket`, `Layer1bOutput`
  - `layer2/types.py` — `Layer2CardInput`, `SwapDecision`, `DataInstructions`, `Layer2CardOutput`
  - `ems_exec/types.py` — `ExecCtx`, `Window` (see F7)
  - `validate/types.py` — `ValidationReport`, `RenderVerdictResult` (`{n_real, n_data, n_undeclared, verdict, answerability}`)
  - `run/types.py` — `PipelineResult` (the harness `out` dict = the real `orchestrator_state` contract)
  - `host/types.py` — `FECard` (enrich.py:201 — the TS boundary shape)
  Then annotate **only builder returns and boundary signatures** (`build_layer1a_output(...) -> Layer1aOutput`, `run_card(...) -> Layer2CardOutput`, `run_pipeline(...) -> PipelineResult`, `compute(...) -> RenderVerdictResult`). ~8 shapes remove the bulk of dict-shape guessing; everything else stays as-is.
- **Risk:** low (annotations are runtime-inert; TypedDict keys can be verified against F1's schemas in the same round-trip test).
- **Behavior-preserving:** yes, by construction.
- **Tests guarding:** `tests/test_layer2_card.py`, `tests/test_orchestrator.py`, `tests/test_layer1a_routing.py`, `tests/test_layer1b_asset_resolve.py`, `tests/test_render_verdict.py`.

## F3 — Layer2CardOutput has two producer variants with different key sets and two disjoint failure channels

- **File:** `run/layer2_all.py:17`
- **Evidence:** the fan-out exception envelope:
  ```python
  def _err(cid, e):
      return {"card_id": cid, "exception": f"{type(e).__name__}: {e}", "conforms": False,
              "exact_metadata": None, "payload": None, "swap_decision": {"action": "keep"}}
  ```
  omits `answerability`, `data_instructions`, `gap`, `data_note`, `failure` — all of which `layer2/build.py:658-679` always provides (that path signals failure via `failure={"stage": "llm"|"emit", ...}`, `layer2/build.py:671`). So a "failed card" reads differently depending on *where* it failed, and consumers must probe both channels: `host/enrich.py:170` `payload_error = l2.get("exception") or (l2.get("failure") or {}).get("detail")`; `run/harness.py:116-130` treats both variants via `(o or {}).get(...)`. Note the `_err` swap_decision also lacks `origin`, so `layer2/schema.py:20`'s origin check would flag it — it's just never run on that variant.
- **Proposed refactor:** one canonical envelope builder (e.g. `layer2/envelope.py`, atomic) used by both `_finalize` and `_err`: the exception path emits the full key set with `failure={"stage": "fanout", "reason": ..., "detail": ...}`, `answerability: "none"`, `data_instructions: {"fields": []}`, `gap: True`, and **keeps the `exception` key as an alias** so every existing reader (enrich, harness, sweeps that mine response_*.json) sees identical truthiness. Annotate both as `Layer2CardOutput` (F2).
- **Risk:** medium (offline sweep/log tooling may key on the exact minimal `_err` shape; keep all existing keys, add only).
- **Behavior-preserving:** yes if `exception` and all current keys are retained (additive keys only).
- **Tests guarding:** `tests/test_orchestrator.py`, `tests/test_reflect_honest_terminal.py`, `tests/test_layer2_card.py`.
- **Side note (doc drift):** `run/layer2_all.py:9-10` still says "This settles swaps BEFORE Layer 3" — Layer 3 is retired (`run/harness.py:7`). Fix the comment while touching the file.

## F4 — The 1b `how` vocabulary is re-declared as inline set literals in 3+ files, in three different subsets

- **File:** `run/harness.py:288`
- **Evidence:**
  - `layer1b/schema.py:24` — full enum: `{"AI", "user-choice", "ambiguous", "empty", "no_data", "collision_gate_fullname"}`
  - `layer1b/schema.py:30` — resolved-with-data subset: `{"AI", "user-choice", "collision_gate_fullname"}`
  - `layer1b/compare/resolve_names.py:26` — `_CONFIDENT_HOW = {"AI", "user-choice", "no_data", "collision_gate_fullname"}`
  - `run/harness.py:288` — `asset_resolved = (how in {"AI", "user-choice", "no_data", "collision_gate_fullname"} ...)`
  - `host/multi_asset.py:112` — hardcodes `"how": "user-choice"`.
  The comments in schema.py and harness.py show `collision_gate_fullname` had to be threaded through every site by hand — exactly the drift this invites.
- **Proposed refactor:** atomic `layer1b/how.py`: `HOW_AI = "AI"`, …, `ALL = frozenset(...)`, `RESOLVED_WITH_DATA = frozenset({HOW_AI, HOW_USER_CHOICE, HOW_COLLISION_GATE})`, `RESOLVED_ANY = RESOLVED_WITH_DATA | {HOW_NO_DATA}`; import at all five sites. Plain str constants (JSON/DB-safe), plus a `Literal` alias in `layer1b/types.py`. No Enum class — these values serialize into responses and logs.
- **Risk:** low. **Behavior-preserving:** yes (identical string values).
- **Tests guarding:** `tests/test_layer1b_asset_resolve.py`, `tests/test_layer1_reconcile_no_data.py`, `tests/test_multi_asset.py`.

## F5 — Four verdict/decision string families have no declared home (scattered literals)

- **File:** `validate/render_verdict.py:160` (representative)
- **Evidence:**
  - **answerability** `{"full","partial","none"}` — `layer2/build.py:580` (`if answerability not in ("full", "partial", "none")`), `layer2/gates.py:722`, `validate/render_verdict.py:160` (`_ANSWER = {"render": "full", ...}`), `run/harness.py:128`.
  - **render verdict** `{"render","partial","honest_blank"}` — `validate/render_verdict.py:239-270`, `host/server.py:132-134` (`in ("render", "partial")` inline), `host/enrich.py:185`, plus host/web TS.
  - **data verdict** `{"pass","warn","fail"}` (+ page roll-up `"pass_with_gaps"`, `"asset_pending"`) — `validate/data_validate.py:16-37`, `validate/schema.py:5` (`_VERDICTS`), `validate/build.py:42` (`c["usable"] = v["verdict"] != "fail"`).
  - **swap** action `{"keep","swap"}` × origin `{"kept","swapped","must_swap"}` — `layer2/schema.py:18-21`, `layer2/swap/decide.py:23-34`, `layer2/swap/gate_force_renderable.py:62-73`, `grounding/swap_settle.py:92`, `validate/build.py:114`, `run/harness.py:130`.
- **Proposed refactor:** module-level str constants + `Literal` aliases in the concept owner's folder (atomic rule): `validate/verdicts.py` (data + render + answerability, since render_verdict already owns the mapping), `layer2/swap/vocab.py` (action/origin). Importers replace literals 1:1. Explicitly **not** `enum.Enum` — every one of these strings crosses a JSON/DB/FE boundary; `str` constants keep serialization byte-identical with no `.value` churn.
- **Risk:** low. **Behavior-preserving:** yes.
- **Tests guarding:** `tests/test_render_verdict.py`, `tests/test_layer2_swap_gates.py`, `tests/test_validate.py`, `tests/test_validate_streamline.py`, `tests/test_reflect_honest_terminal.py`.

## F6 — member_scope constants exist but consumers hardcode "outgoing"/"incomer"

- **File:** `host/exec_cards.py:157`
- **Evidence:** `layer1b/resolve/member_scope.py:26-27` already declares `OUTGOING = "outgoing"` / `INCOMER = "incomer"`, yet:
  - `host/exec_cards.py:107` `member_scope="outgoing"` (kwarg default) and `:157` `(asset or {}).get("member_scope") or "outgoing"`
  - `host/enrich.py:219` `"member_scope": (asset or {}).get("member_scope") or "outgoing"`
  - `layer2/emit/panel_members_block.py:78` `incomer_primary = (scope == "incomer")` and `:109` `or "outgoing"`
  The default reading direction is thus declared in four places; changing the default (or adding a third scope) is a 4-file hunt.
- **Proposed refactor:** import `OUTGOING`/`INCOMER` from `layer1b/resolve/member_scope.py` at all four sites; if a host→layer1b import is judged a layering smell, move the two constants to a neutral atomic home (`config/member_scope.py`) and have member_scope.py re-export.
- **Risk:** low. **Behavior-preserving:** yes.
- **Tests guarding:** `tests/test_equipment_topology.py`, `tests/test_equipment_ai_context.py`, `tests/test_residual_layer2_emit.py`.

## F7 — `window` is a polymorphic union (tuple | dict | None) across the executor boundary; every renderer re-normalizes it

- **File:** `ems_exec/serve/run.py:50`
- **Evidence:** the contract is docstring-only: `"window = (start,end) tuple or {start,end} dict, or None"` (`ems_exec/serve/run.py:50-51`, repeated at :76). Each story renderer hand-rolls the same normalization:
  - `ems_exec/renderers/_story/real_time_monitoring.py:318` `isinstance(window, (list, tuple)) and len(window) == 2 ...`
  - `ems_exec/renderers/_story/voltage_current.py:166-171` handles **both** `isinstance(window, dict)` and the tuple form
  - `ems_exec/renderers/_story/harmonics_pq.py:146`, `energy_distribution.py:111` — tuple-only (a dict window silently falls through: latent shape-drift bug class).
- **Proposed refactor:** one `normalize_window(window) -> Optional[tuple[start, end]]` in `ems_exec/executor/window_policy.py` (already the window concern's home), called once in `serve/run.build_ctx` so `ctx["window"]` is always the canonical tuple; renderers drop their isinstance ladders. First enumerate per-site differences (voltage_current accepts dicts, harmonics does not) — the normalizer must be the union of accepted forms so no site gets *stricter*.
- **Risk:** medium (subtle per-renderer acceptance differences; needs the acceptance table + tests before the switch).
- **Behavior-preserving:** yes in intent; requires the per-site diff check to guarantee it.
- **Tests guarding:** `tests/test_window_extraction.py`, `tests/test_narrative_ask_window.py`, `tests/test_layer2_window_label.py`, `tests/test_harmonics_story_real_thd.py`.

## F8 — Three-state string sentinel: `_asset3d_envelope` returns url-str | '' | None

- **File:** `validate/render_verdict.py:214`
- **Evidence:** the docstring is the only type spec: *"Returns the url string when bound, '' when the envelope is present but unbound, None when the payload is not this envelope"* — and the caller (`compute`, :235-241) decodes it with `env is not None` then truthiness:
  ```python
  env = _asset3d_envelope(payload)
  if env is not None and not skeleton_blank:
      verdict = "render" if env else "honest_blank"
  ```
  `''` vs `None` carrying different meanings is exactly the sentinel-ambiguity class this audit targets; a future caller using plain truthiness conflates "not this envelope" with "unbound".
- **Proposed refactor:** return an explicit pair `(is_asset3d: bool, url: str | None)` (single caller, trivial mechanical change), or keep the function but add a documented `Asset3dEnvelope = Union[str, None]`-style alias in `validate/types.py` with the tri-state spelled out. The pair form is preferred — it deletes the sentinel rather than documenting it.
- **Risk:** low (one caller, pure function). **Behavior-preserving:** yes.
- **Tests guarding:** `tests/test_render_verdict.py`, `tests/test_asset3d_dg_seed.py`, `tests/test_equipment_3d.py`.

## F9 — Reserved telemetry keys ride *inside* payload/data_instructions dicts as stringly side-channels with order-sensitive pops

- **File:** `host/enrich.py:160`
- **Evidence:** two independent modules each smuggle a reserved key into the completed payload — `ems_exec/executor/gaps.py:19` `GAPS_KEY = "_blank_gaps"` and `ems_exec/executor/roster_stats.py:21` `RESERVED_KEY = "_roster_stats"` — and the serve boundary must pop both, in the right order, before the leaf scan (`host/enrich.py:158-163`: *"Pop the reserved telemetry keys FIRST so neither the roster stats dict nor the gap records are seen by the verdict's own leaf scan"*). Layer 2 separately grows an open-ended `_`-prefixed telemetry family on `data_instructions` (`_normalized` build.py:456, `_window_label` :488, `_zero_skeleton` :618, `_cross_domain`/`_cross_domain_blanked` :655-657, `_emit_gaps`, `_per_leaf_gaps`) which ships to the FE verbatim via `host/enrich.py:227`. Nothing enumerates the full reserved set; a new reserved payload key that one consumer forgets to pop is silently counted as a data leaf by the verdict scan.
- **Proposed refactor:** atomic `ems_exec/executor/telemetry_keys.py`: `RESERVED_PAYLOAD_KEYS = (GAPS_KEY, ROSTER_STATS_KEY)` + `pop_all(payload) -> {"gaps": ..., "roster_stats": ...}`; enrich calls `pop_all` once (order problem dissolves). For the `di._*` family, a declared frozenset (`layer2/types.py` or a `layer2/telemetry.py`) + a one-line test asserting every `_`-key written by `_finalize` is enumerated — so the contract is discoverable and the FE knows exactly which keys are telemetry.
- **Risk:** low. **Behavior-preserving:** yes (same pops, same keys).
- **Tests guarding:** `tests/test_render_verdict.py`, `tests/test_enrich_reason_per_leaf.py`, `tests/test_ems_exec_roster.py`, `tests/test_layer2_zero_skeleton.py`.

## F10 — Contract-validator asymmetry: 1a's validator is never wired; 1b/L2 use different keys for the same concept

- **File:** `layer1a/schema.py:36`
- **Evidence:** `validate_layer1a_output` is defined and unit-tested (`tests/test_layer1a_routing.py:9,65`) but `grep -rn "validate_layer1a_output"` shows **no production caller** — `layer1a/build.py` never runs it, unlike its siblings: `layer1b/build.py:28-30` attaches `out["contract_problems"] = problems`, `layer2/build.py:680` attaches `out["_schema_issues"]`, `validate/build.py:103` attaches `report["_schema_issues"]`. Same concept, two key names, and one layer silently unchecked in prod (the harness even logs `contract_problems=l1b.get("contract_problems")` at `run/harness.py:241` — 1a has no equivalent).
- **Proposed refactor:** wire `validate_layer1a_output` into `run_1a`'s return (annotate-only, same non-gating pattern as 1b — per-leaf degradation intact) and standardize on one key. Since `contract_problems` is already surfaced in stage telemetry, prefer it; keep `_schema_issues` as-is where sweeps read it, or dual-write during a transition.
- **Risk:** medium — wiring a previously-unrun validator *is* a behavior change in telemetry (new key in 1a output, new stage log field); the validation itself must stay annotate-only to be safe.
- **Behavior-preserving:** telemetry-additive only (no gating); render behavior unchanged.
- **Tests guarding:** `tests/test_layer1a_routing.py`, `tests/test_stage_telemetry_item15.py`, `tests/test_orchestrator.py`.

## F11 — "Blank scalar" is defined three times with slightly different domains

- **File:** `validate/render_verdict.py:48`
- **Evidence:** `validate/render_verdict.py:48-49` `_blank_scalar(v): return v is None or v == "—" or v == ""`; `ems_exec/executor/gaps.py` `_blank_val` (same trio **plus** empty/all-None list handling); `host/enrich.py:83` inline `holder.get("title") in (None, "", "—")`. The em-dash sentinel is a cross-layer wire value (the executor writes it, the verdict and the FE read it) with no single declared home; a fourth spelling that forgets `"—"` mis-verdicts filled-vs-blank.
- **Proposed refactor:** declare `BLANK = "—"` + `is_blank_scalar()` once in `ems_exec/executor/paths.py` (render_verdict already imports from there: `from ems_exec.executor.paths import _toks, _leaf_at`) and have gaps/render_verdict/enrich reuse it. Keep `_blank_val`'s list extension where it is (list semantics are a gaps concern).
- **Risk:** low. **Behavior-preserving:** yes.
- **Tests guarding:** `tests/test_display_dash.py`, `tests/test_render_verdict.py`, `tests/test_fill_point_slots_and_placeholder_null.py`, `tests/test_enrich_title_graft.py`.

---

## (e) The minimal typed-core plan — 8 shapes, defined once, annotation-only

Ordered by dict-shape-guessing removed per line of code added. No pydantic; `TypedDict(total=False)` + `Literal`
aliases only; one atomic `types.py` per layer folder (house style). Runtime validation stays where it already is
(the annotate-only `schema.py` validators + F1's test-time JSON-schema round-trip).

| # | Shape | Home | Built at | Guessed at (examples) |
|---|-------|------|----------|-----------------------|
| 1 | `Layer2CardOutput` (+ `SwapDecision`) | `layer2/types.py` | `layer2/build.py:658`, `run/layer2_all.py:17` | harness, enrich, validate/build, swap_settle, host/web |
| 2 | `Layer1bOutput` + `Asset` + `ColumnBasket` | `layer1b/types.py` | `layer1b/schema.py:6` | harness gates, card_input, exec_cards, panel_members_block, assemble |
| 3 | `Layer1aOutput` + `Card1a` + `RouteResult` | `layer1a/types.py` | `layer1a/schema.py:10`, `layer1a/route.py:111` | card_input, harness, server.build_response |
| 4 | `DataInstructions` (incl. the declared `_*` telemetry keys) | `layer2/types.py` | `layer2/build.py:442-657` | fill, render_verdict, enrich, FE |
| 5 | `PipelineResult` (the harness `out`) | `run/types.py` | `run/harness.py:200` | server, assemble, multi_asset, sweeps |
| 6 | `ExecCtx` + `Window` | `ems_exec/types.py` | `ems_exec/serve/run.py:52` | fill, window_policy, every _story renderer |
| 7 | `RenderVerdictResult` + verdict/answerability Literals | `validate/types.py` / `validate/verdicts.py` | `validate/render_verdict.py:271` | enrich, server stage counts |
| 8 | `FECard` | `host/types.py` | `host/enrich.py:201` | host/web TS (mirror interface), asset_lanes |

Sequencing: F5/F4/F6 (constants) first — they are pure 1:1 literal swaps; then F2 types over the now-named vocab;
then F3 (envelope unification) and F9 (telemetry enumeration) which the types make checkable; F1 (contracts round-trip
test) last so the schemas are generated from the typed shapes rather than hand-written twice. F7 and F10 are the only
items needing real diligence (per-renderer window acceptance table; telemetry-additive wiring).
