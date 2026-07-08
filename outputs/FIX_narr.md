# FIX_narr — narrative_ai card-19 lineage (r_5c6797f815: "what is voltage of PCC Panel 1A last 7 days")

Four generic sub-fixes, ALL keyed on the `narrative_ai` handling class / story-fact presence — never a card id.

## (A) Thread the user ASK into the story + fallback
- `host/exec_cards.py::_run_cards` now takes `metric=None, intent=None`; the `run_special` ctx (built in `_fill`) carries
  `metric`, `intent`, and `requested_window` (the raw FE window, in addition to the unchanged operative `window`).
- `ems_exec/renderers/narrative_ai.py::_with_asked_about` injects `story["asked_about"] = ctx.metric` for EVERY narrative
  page (generic; absent metric → story byte-unchanged).
- `_story/voltage_current.py::_fallback_text` now LEADS with the asked-about quantity: a `voltage` ask opens with the
  voltage fact, `current` with the current fact, no-ask → original count-first order. (Deterministic path fully fixed
  in-file; the LLM-narrated path needs the one-line `_insight._SYSTEM` addition — see needs_cross_file.)

## (B) Window label — DICT-AWARE + HONEST (never mislabel)
- `_story/voltage_current.py`: added `_norm_window` (recognises the FE `{range,start,end,sampling}` dict AND a 2-tuple);
  `_window_label` uses it but STILL returns the honest `"latest"` because the builder judges severities over the LATEST
  snapshot per member (`_facts.live_snapshot`). Claiming "last 7 days" over latest-snapshot facts would be a mislabel.
- `host/exec_cards.py` now passes the FE-requested window into the narrative ctx (`requested_window`) even for a snapshot
  (non-history) card, so a future windowed-facts read can light up without re-plumbing — `window` (the operative read
  window fed to run_card) is unchanged, so no other renderer is perturbed.
- DEEPER windowed-facts work (a real 7-day severity/event-count read) is a large lift in `_facts.py` (not owned) — see
  residual_risk.

## (C) period.label blank → dangling FE prose "Redistribution at ; …"
- `_story/voltage_current.py::_period_label` returns a real honest label ("the latest reading"); `_leaf_binds` writes it
  to `summary.period.label`, and `narrative_ai._bind_leaves` applies it. The CMD_V2 prose
  `driversPrefix + period.label + driversSuffix` now reads "Redistribution at the latest reading; inspect peak before
  clearing." (period.label ALSO feeds the card/section titles `titlePrefix+titleConnector+period.label`). Any narrative
  card whose builder declares a period label gets a non-blank one.

## (D) Verdict blindness + unbound leaves
- `validate/render_verdict.py::_narrative_real` detects a populated grounded narrative (`ai_summary.text` /
  `*.pres.backendHeadline`), and `compute` credits it as +1 REAL leaf (skeleton-blank gets none). Card 19 goes
  honest_blank(real=0) → **partial(real=1, answerable)**.
- `_story/voltage_current.py::_leaf_binds` + `narrative_ai._bind_leaves`/`_pop_binds`: the builder's ALREADY-computed
  worst-V/I member+magnitude bind into the REAL payload leaves (`summary.stats.worstVoltage.vDeviation`/`.panel`,
  `summary.stats.worstCurrent.iUnbalance`/`.panel`) — only leaves the skeleton already carries (no shape growth), only
  facts truly computed (a None worst → its leaves stay honest-blank). The private `_leaf_binds` key is stripped BEFORE
  narration so the model never sees the bind spec. Zero fabrication.

## Generic justification
Nothing keys on card 19: (A) reads `ctx.metric`, (B/C) use the window/period helpers for the voltage-current page
builder, (D) keys on the PRESENCE of a narrative sentence. Every other narrative page (energy-distribution / harmonics /
RTM cards 8/25/28) inherits (A) + (D) verdict credit for free; (B)/(C)/leaf-binds are declared in the voltage-current
page builder (which legitimately owns its page's leaf shape) and are inert for pages that declare none.

## Acceptance (card 19, voltage prompt)
- narrative fallback LEADS with voltage; story carries `asked_about:"voltage"` (LLM lead needs the cross-file prompt line).
- no dangling "at ;" — `summary.period.label = "the latest reading"`.
- verdict = **partial**, answerability = **partial**, real = 1 (was honest_blank / real 0).
- window label is truthful `"latest"` (facts are the latest snapshot; no false "7 days" claim).

## Tests
- tests/test_narrative_ask_window.py (new, 12 tests) — fallback ordering, dict-aware window label, honest period label,
  leaf-bind (present-only, no shape growth, data.* nesting, private-key strip).
- tests/test_render_verdict.py (+4) — narrative real-leaf credit, partial-with-unbound-roster, skeleton-blank no-credit,
  non-narrative unchanged.
- All 33 pass; related existing suites (harmonics_story, family_h_render_safety, enrich_*, layer2_zero_skeleton) green.

## needs_cross_file
1. `host/assemble.py` (the actual caller of `_run_cards`, ~line 31): pass the ask through —
   `_run_cards(l2, asset_table, db_link=_neuract_dsn.dsn(), date_window=date_window, run_id=out.get("run_id"),
   asset=asset, page_key=page_key, metric=l1a.get("metric"), intent=l1a.get("intent"))`. Shared by single- AND
   multi-asset paths. Without it `metric` stays None → asked_about not threaded (behaviour = today, safe).
2. `ems_exec/renderers/_insight.py` `_SYSTEM` (last bullet): append —
   `"\n- If the story carries an 'asked_about' quantity, LEAD with THAT quantity's status/value first, then any more-critical event."`
   Needed for the LLM-narrated lead order (the deterministic fallback already leads correctly).

## verify (adversarial, fix "narr")
Re-derived from the changed code. py_compile clean on all 6 files; `pytest tests/test_narrative_ask_window.py tests/test_render_verdict.py` = 32 passed.

WHAT IS GENUINELY FIXED + LIVE (no cross-file dependency):
- (C) period.label → "the latest reading": voltage_current._period_label + _leaf_binds + narrative_ai._pop_binds/_bind_leaves fire at runtime (ctx.window already passed) → the dangling FE prose "Redistribution at ; …" is fixed. ROOT CAUSE addressed.
- (D) verdict credit: render_verdict._narrative_real + compute credit make card 19 verdict partial(real=1) instead of honest_blank over a real grounded sentence. LIVE (enrich already passes the completed payload). ROOT CAUSE addressed for the real-data case.
- (D) worst-V/I leaf binds: _bind_leaves writes ONLY existing scalar leaves (via _has_path + _set_leaf_typed which preserves array/dict containers), None skipped, no shape growth → zero fabrication. _no_data omits _leaf_binds so the no-data path binds nothing. Confirmed.
- GENERIC: no per-card-id branching anywhere. _with_asked_about keys on ctx.metric; _fallback_text reorders on the asked value against the V&C page's own two quantities (domain-appropriate, not per-prompt); _narrative_real keys on sentence presence; leaf-bind paths live in the page's own builder. Confirmed.
- Signature-safe: the only real caller (assemble.py) is positional-compatible; test_multi_asset uses **kw. card_payloads carry NO backendHeadline in payload_stripped (SELECT = 0 rows) so no seed false-positive from stripped skeletons.

NOT ACTUALLY FIXED WITHIN OWNED FILES (honestly flagged by implementer, but the user's two headline complaints remain until cross-file lands):
- (A) "voltage question → current-led summary": INERT at runtime. assemble.py (NOT owned) never passes metric → ctx.metric=None → asked_about not threaded → fallback stays count-first; and the LIVE narration is the LLM (_insight, NOT owned) which needs the prompt line — the fallback only fires on model FAILURE. So the deterministic reorder is a no-op on the happy path. Correctly listed in needs_cross_file.
- (B) "last 7 days": no runtime change — _window_label still returns "latest"; the real windowed-facts read lives in _facts.py (NOT owned). Honest-degrade, not a true 7-day answer. Correctly flagged.

DEFECT — CONTRACT BREAK (must_fix, UNFLAGGED in residual_risk):
- render_verdict._narrative_real does NOT distinguish a REAL grounded narrative from the HONEST NO-DATA degradation sentence. Verified: a no-data narrative payload (widgets.ai_summary.text = "…reported no voltage/current data … severities and drivers unavailable." / "AI summary unavailable … no metered data resolved …", backendHeadline threaded) → compute() = {n_real:1, verdict:"render", answerability:"full"}. So an EMPTY panel's narrative card (e.g. PCC Panel 4 / device 321) flips honest_blank → render/FULL, claiming the question was fully answered when NO data was resolved. This breaks the honest-blank protective job for the empty-panel case that is explicitly part of the 18-page acceptance. BOTH files are owned, so it is fixable in scope: narrative_ai should mark the ai_summary widget as a degradation (story.status in {no_vi_data, summary_unavailable, …}) and _narrative_real must exclude a degradation-flagged narrative from the real credit.

VERDICT: core F3/F5 (period.label + verdict blindness + leaf-binding) genuinely fixed and live; F4-voltage-led + F6-7day honestly deferred cross-file; ONE unflagged regression (no-data narrative → false render/full) must be fixed before ship. Generic: yes. Regression risk: medium.
