# FIX: time — prompt→date_window extraction (route-1a-timewindow)

Root cause (DEBUG Q2 F3/F4/F5): no layer extracts a relative time range from the prompt. 1a's answer was
`{page_key, metric, intent}` only; `run_pipeline` was time-blind; the only `date_window` producer was the FE date
control (`host/server.py` `req.get("date_window")`), which is null for a typed prompt. So "last 7 days" was dropped and
each page defaulted to today, while the ask leaked incoherently through per-card L2 story prose.

## What changed (AI-first: the fix lives in the 1a prompt + schema, then a DB-vocab clamp, then a host default)

Files I own (edited):
- `layer1a/route_schema.py` — added a 4th REQUIRED enum property `window` to `route_answer_schema`. Its vocab is
  imported from `config.windows.TIME_WINDOWS` (never hardcoded — the schema can't drift from the clamp/executor) plus a
  `"none"` sentinel for "no time mentioned". Pure string enum (xgrammar treats it exactly like metric/intent). Property
  order `page_key→metric→intent→window`, all four required. Flag-OFF path unchanged (returns None before touching windows).
- `layer1a/prompts/system.md` — taught the router `WINDOW` = the relative time range as ONE preset
  (`today|last-24h|last-7-days|shift-8h|live`) with phrasing maps, `"none"` when no time (or an unrepresentable range);
  updated the `JSON only:` reply shape to carry `"window"`; added a `...last 7 days -> window:"last-7-days"` example (the
  exact failing prompt's shape) and window fields on the other examples.
- `layer1a/parse/window_default.py` (NEW, single-purpose) — `clamp_window()` folds the router's `window` → a valid
  `TIME_WINDOWS` key, else `None` (the `"none"`/null sentinel, absent, or any off-vocab token → None). DB-driven vocab,
  case-insensitive, never raises — the `window` sibling of `metric_intent_defaults.clamp_metric_intent`.
- `run/harness.py` — added `out["window"]` (init None), set from the FIRST resolved 1a answer
  (`l1a.get("window") or routing.get("window")`) BEFORE any reconcile/preflight/reflect re-route, so the prompt-derived
  window (page-invariant) survives every re-route. Surfaced for the host to read.
- `host/server.py` — added `_window_from_preset(preset)` → concrete `{range,start,end,sampling}` date_window, REUSING the
  executor's own `ems_exec.executor.window_policy._range_start` for the start instant (same calendar-anchor / TIME_WINDOWS
  lookback / last-N logic the exec uses, so host default and exec reads never disagree) + site-tz `now` as end + a
  bucket→FE-sampling map. In `build_response`, when the FE sent NO `date_window`, DEFAULT it from `out["window"]` via that
  helper (an explicit FE pick always wins; a no-time prompt keeps `None` → today/latest unchanged). The existing
  `"date_window": date_window` echo now carries the resolved window, and `assemble_cards` runs the exec history seam over it.
- `tests/test_route_guided_json.py` — updated the exact-shape assertions to include `window`; added
  `test_route_schema_on_includes_window_preset_enum` (string enum, `none`+`last-7-days` present, schema ⊇ TIME_WINDOWS).
- `tests/test_window_extraction.py` (NEW) — offline coverage of `clamp_window` (preset accept, case-insensitive, none/
  sentinel/off-vocab → None, whole-vocab survives) and `_window_from_preset` (last-7-days → concrete ~7-day range with
  `sampling:day`; None/unknown → None).

`host/web/src/api.ts` — NO CHANGE NEEDED. It already forwards `date_window` in the request and returns the full response
body (which now carries a non-null `response.date_window`). App.tsx has no global date bar; per-card strip
initialization from `response.date_window` is the exec/NARR domain (`strip.filterSelection`), out of this scope.

## Why this is generic (works for ALL prompts/cards/pages/assets)
- The window is extracted by the SAME 1a AI layer that already reads the raw prompt for metric/intent — no per-card /
  per-prompt / per-asset branch. Any prompt naming a preset time range gets it; any prompt without one gets `none` → None
  and today/latest behavior is byte-unchanged.
- Vocab is a single DB source (`config.windows.TIME_WINDOWS`) shared by the guided-decode enum, the clamp, and the host
  resolver — add a preset to the DB row and it propagates everywhere (the prompt prose is the only manual follow-up,
  identical to metric/intent).
- The host resolver reuses the executor's canonical `_range_start`, so no duplicated/inconsistent date math.

## Acceptance
- "...last 7 days": 1a emits `window="last-7-days"` (guided enum + prompt); clamp keeps it; `out["window"]="last-7-days"`;
  `response.date_window = {range:"last-7-days", start:<T-7d>, end:<now>, sampling:"day"}` (non-null, real 7-day span).
- No-time prompt: `window="none"` → clamp None → `out["window"]=None` → `date_window` stays None → today/latest unchanged.
- An explicit FE date pick still overrides (defaulting only fires when the request's `date_window` is null/absent).

## Cross-file dependency (NOT in my owned set — see needs_cross_file)
`layer1a/route.py` MUST parse + clamp + carry the window (the parse site + the returned route_result). My owned changes
are INERT (no regression: the model emits `window`, route.py currently ignores it) until this lands. `layer1a/schema.py`
is an OPTIONAL cleanliness edit — route.py placing `window` inside the `routing` telemetry dict (which
`build_layer1a_output` already forwards verbatim) makes the harness fallback pick it up with NO schema.py edit.

## verify (adversarial — fix "time")

VERDICT: upheld=FALSE (incomplete/inert as delivered) · generic=TRUE · contract_preserved=TRUE · regression=LOW.

Re-derived from code, not the report:

1. ROOT CAUSE NOT FIXED END-TO-END (the decisive finding). The observed defect is
   `response.date_window == null` for "…last 7 days". The whole chain hinges on
   `out["window"]` (run/harness.py:232 `out["window"] = l1a.get("window") or _rt.get("window")`).
   But layer1a/route.py (line 109-112) STILL returns
   `{page_key, metric, intent, page_spec, routing{page_key_how,dropped_templates,excluded_page_key,raw_page_key}}`
   — NO `window` first-class, NO `window` in the routing dict, and it never imports/calls clamp_window.
   schema.build_layer1a_output likewise forwards no first-class window. Verified live:
     route.py imports clamp_window: False · route.py returns a window key: False · schema forwards window: False.
   Therefore `l1a.get("window")` is None AND `_rt.get("window")` is None → `out["window"]` is ALWAYS None →
   `_window_from_preset(None)` → None → `date_window` stays None. The target prompt STILL yields date_window=null.
   The fix is fully INERT within the owned set. The implementer disclosed this (status=partial, residual_risk #1,
   needs_cross_file lists the exact route.py edit) — honest, but the delivered files do not fix the bug.
   MUST FIX (blocker): wire layer1a/route.py — `from layer1a.parse.window_default import clamp_window`,
   `window = clamp_window(r.get("window"))`, and put `window` into route_result (at minimum inside the `routing`
   dict, which schema forwards verbatim → the harness fallback `_rt.get("window")` picks it up; first-class is
   cleaner). Only then does out["window"]/date_window become non-null.

2. GENERIC: confirmed. Vocab is a single DB source (windows.time_windows), shared by the guided enum
   (route_schema), the clamp (window_default), and the host resolver (_window_from_preset via TIME_WINDOWS +
   window_policy._range_start). No per-card/per-prompt/per-asset branch. clamp_window offline:
   last-7-days→last-7-days, Last-7-Days→last-7-days, today→today, None/'none'/''/'this-month'/'gibberish'/42→None.
   _window_from_preset offline: last-7-days→concrete 7-day span sampling:day; today→site-midnight..now hourly;
   last-24h→24h hourly; this-month/None/''→None (honest — unsupported phrasings degrade to no-window, never a wrong one).

3. CONTRACT PRESERVED (default window ONLY when FE sent none): confirmed. build_response gates on
   `if not date_window:`; an explicit FE pick (populated dict from req.get("date_window")) is truthy → the prompt
   default never fires → FE wins. A no-time prompt → out["window"]=None → date_window stays None → today/latest
   byte-unchanged. (Minor edge: a literal empty `{}` from the FE is falsy and would trigger the default, but that
   is not a real FE selection and matches today's pass-through behavior.)

4. REGRESSION: LOW (not none). The owned changes are functionally inert today, so the date_window path is
   unchanged. HOWEVER llm.guided_json.route is ON in cmd_catalog.app_config, so the schema's new REQUIRED `window`
   enum is LIVE in the grammar now — the model must emit a window token on every route. system.md teaches WINDOW
   fully (phrasing maps, the exact failing prompt example, window in the JSON reply shape) and the emission is
   grammar-constrained to {presets…, none}, so it can't produce an off-vocab/unsatisfiable output; route.py
   currently ignores it. Negligible chance the extra constrained field perturbs the greedy page_key/metric/intent
   decode. py_compile OK on all 6 changed .py; tests/test_window_extraction.py + tests/test_route_guided_json.py
   = 15 passed.

BOTTOM LINE: the scaffolding (schema enum, clamp, harness plumbing, host resolver, prompt teaching) is correct,
generic, and contract-safe, but the fix does NOT resolve the reported defect until the layer1a/route.py wiring
(recorded in needs_cross_file) is applied. Integration MUST land that edit and re-run the target prompt to confirm
response.date_window is a concrete last-7-days span before this is considered fixed.
