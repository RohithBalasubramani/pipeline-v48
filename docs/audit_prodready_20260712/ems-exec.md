# Prod-readiness audit — lens: ems-exec (post-split)

Date: 2026-07-12. Differential audit of `ems_exec/` after today's concurrent refactors
(fab_guards package split, blank.py adoption, derivations PF flip, dedup campaign).
Scope: fab_guards/ package integrity vs git HEAD, fill.py pass order + silent excepts,
blank.py adoption, derivations PF 0.9 + statutory bands, renderers `_agg_row` hook +
sankey null-endpoint sweep, H17 broad-except counts.

Status: COMPLETE (2026-07-12 ~07:50 IST). NOTE: ems_exec/executor/fill.py was actively being refactored by a
concurrent session DURING this audit (field_routing/series_router extraction, mtimes 07:39-07:41 IST) — line
numbers for fill.py cite the 620-line version current at completion time.

---

## Verified OK (positive checks)

- **fab_guards split is semantically clean.** AST-level diff of every top-level function/assign in
  `git show HEAD:ems_exec/executor/fab_guards.py` (nested repo, 972 lines) vs the new package
  (`knobs/class1_epoch/class23_source/class4_seed/restore/apply`, 1053 lines total): the ONLY
  behavior-relevant delta is the intended `_MAGNITUDE_RE` import-time compile → `_magnitude_re()`
  vocab-keyed call-time cache (ledger batch entry, audit M5/M7 fix), plus a docstring extension on
  `_epoch_floor`. Every other function byte-identical. No duplicated names across package modules.
- **`_ROWS_CACHE` identity preserved across the facade**: `python3 -c` import of both
  `ems_exec.executor.fab_guards` and `...fab_guards.class23_source` → `pkg._ROWS_CACHE is c23._ROWS_CACHE == True`.
  Tests that `G._ROWS_CACHE.clear()` (test_fab_guards.py:65,81,150; test_post_fill_rescue_overreach.py:336) stay valid.
- **All fab_guards consumers resolve**: fill.py:522 (`restore_chrome`) + fill.py:588 (`apply`) go through the
  package facade; tests import `ems_exec.executor.fab_guards as G`; no other module imports guard internals.
  `monkeypatch.setattr(_G, "apply", ...)` (test_fab_guards.py:503) still intercepts fill's call because fill
  resolves `_fabg.apply` at call time on the facade module object.
- **knobs read `cfg` lazily inside each function** (knobs.py:14,23,46,59) — the `monkeypatch.setattr(ac, "cfg", ...)`
  test seam survives the split.
- **fill.py pass order intact** after today's edits (CAUTION: fill.py is being actively refactored — mtime
  07:41:51 IST, mid-audit; line numbers below are from the current 620-line version): field loop →
  `_null_untouched_placeholders` (fill.py:390) → roster (399) → roster_gaps (409) → yscale (422) →
  norm_series (434) → xaxis (455) → restore_chrome (471) → view_select (483) → display (497) → freshness (511) →
  trend_badge (516) → fab_guards.apply (537) → scalar_mean_fill (555) → scalar_tile_fill (571) →
  load_factor_fill (588) → prune/unbound gaps (599) → GAPS_KEY attach (606) → series_router (616, NEW explicit
  wiring). Matches the documented guard-before-rescue ordering (DEFECT A/card 50 comments intact).
- **Monoliths F4/F6 extraction (landed mid-audit, ~07:39-07:41 IST) is faithful**: `series_router.py`'s five
  functions (`route_series_families`, `_series_family_groups`, `_apply_family`, `_window_for`,
  `_parse_lookback_days`) are AST-byte-identical to `git show HEAD:ems_exec/executor/indexed_families.py`;
  the sys.meta_path import-hook is genuinely deleted (indexed_families.py now 326 lines, comment :322-325);
  fill.py:608-618 wires the router AFTER the GAPS_KEY attach, explicitly preserving the old wrapper semantics
  ("the WHOLE body above — including the gaps attach — then the router"). `field_routing.plan_wildcards/plan_families`
  (fill.py:269/:277) reproduce the deleted inline logic verbatim, grow-mutation ordering preserved
  (grow at :272 between the two plan calls).
- **PF-of-record flip complete and consistent**: derivations/nameplate.py:26-31 `_nominal_pf()` default 0.9
  (validated 0<pf<=1, fallback 0.9); live cmd_catalog rows verified via SELECT — `nameplate.nominal_pf = 0.9`
  AND `rating.feeder_pf = 0.9`; config/rating_knobs.py:17 default 0.9; db/seed_pf_of_record.sql applied.
  No stray 0.8 PF conversion remains (config/asset_class_defaults.py DG `contracted_frac: 0.8` is a different
  knob; the "~0.8 pf" text there is a descriptive comment only).
- **Statutory band per-class change real + guarded**: derivations/voltage.py:32-51 `_band_deviation_pct` resolves
  ctx asset → nameplate asset_category → `asset_class_defaults.voltage_statutory_deviation_pct` (DG 5.0,
  LT Panel/UPS 10.0 verified in config/asset_class_defaults.py), knob fallback `derivation.statutory_band_pct` 10.0;
  tests/test_statutory_band_per_class.py EXISTS.
- **Epoch-floor DO-NOT-UNIFY closeout cross-referenced both ways**: fab_guards/knobs.py:10-12 + executor/epoch.py:6.
- **Sankey null-endpoint sweep intact**: serve/run.py:23 imports `_prune_dark_edges`; `_sweep_sankeys` (:37-45)
  recurses any {nodes,links} dict; called as the LAST word at :115-118 after the fill/fallback path.
- **panel_aggregate `_agg_row` hook consistent with today's fill.py**: roster.prepare_ctx injects
  `ctx['_agg_row']` only for a non-empty rollup (roster.py:169-177); fill.py reads it (:240 in prior rev) and
  `_field_value` treats it as authoritative (agg_row present → never re-read the single meter); legacy
  panel_aggregate path passes `_agg_row` explicitly (panel_aggregate.py:205,219). Guarded by
  tests/test_agentb_fill_fixes.py:209 (empty-rollup non-injection).
- **AUDIT_REPORT fix #4 verified true**: ems_exec/data/neuract.py — `_LOGGED_CACHE` is now a TTLCache (:24),
  `present_columns` rides the shared never-cache-empty probe in data/neuract_pool (:58-61, D1); `_run_raw`
  records the obs sql_trace leg fail-open (:42-52).
- **Offline test spot-runs green**: tests/test_fab_guards.py 39 passed (0.22s); tests/test_post_fill_rescue_overreach.py
  28 passed (0.14s). Every ems_exec module imports clean (pkgutil walk over the package: 0 failures).
- **D5 verified**: rescue_common.honest_blanked is the one matcher; no drifted copy remains.
- **blank.py facade correct**: `ems_exec/executor/blank.py` is a 7-line sys.modules alias onto `lib/blank.py`
  (same module object both paths); gaps._blank_val (gaps.py:34), roster_gaps._blank (:39),
  roster._const_is_blank (roster.py:246) all delegate to the shared predicate.
- **D5 rescue dedup real**: `rescue_common.honest_blanked` is THE matcher; scalar_mean_fill.py:29 and
  scalar_tile_fill.py:175 import it; load_factor_fill._honest_blanked_lf (:315-319) is a thin
  `both_addresses=True` delegator, not a drifted copy.
- **obs landed inside ems_exec's data door**: data/neuract.py:44 records the per-run SQL leg via
  `obs.sql_trace`; _insight.py routes :8200 traffic through `obs.ai_log`/`llm_tap`.

## Findings

### OBS-1 (medium, safe) — "Cache-poison campaign completed" (AUDIT_REPORT fix #12) is overstated: recipe.py's two negative caches and fab_guards' `_ROWS_CACHE` are still process-lifetime
The prior audit's H1 (code-quality-exec lens) named FOUR ems_exec spots; fix #4 repaired two
(`_COLS_CACHE`/`_LOGGED_CACHE`) and fix #12 declared the campaign "completed" naming only host/payload_store +
layer1b/compare/detect. Still unfixed in-tree:
- `ems_exec/executor/recipe.py:26` `@lru_cache read(card_id)` returns AND CACHES `{}` on any DB error (:39-40) —
  a cmd_catalog blip at a card's first touch silently disables its roster recipe (panel/roster cards degrade to
  recipe-less/legacy behavior) for the process life of :8770.
- `ems_exec/executor/recipe.py:71` `@lru_cache _endpoint_card(endpoint)` caches `None` on outage (:84-85) —
  same family, kills the endpoint→family-recipe fallthrough (`_card_key`, :94-102) until restart.
- `ems_exec/executor/fab_guards/class23_source.py:12` `_ROWS_CACHE` plain dict caches `ok=False` on outage
  (:27-29) — fail-safe direction (CLASS 2 stays its hand) but pins the wrong state for process life.
cmd_catalog is local :5432 (less flappy than the :5433 tunnel), so probability is lower than the fixed spots —
but the never-cache-empty rule (member-cache-poison 2026-07-09) is violated and the "completed" claim would stop
anyone from looking here. Fix: cache only successful/non-empty reads (recipe) + TTLCache (pattern already in
data/neuract.py:24); `_ROWS_CACHE` should only cache `True` (or TTL the False). Safe, no behavior change healthy-path.
NOTE: tests clear `G._ROWS_CACHE` by identity — keep it the same dict object (never rebind), per the package
__init__ contract (:57-58).

### OBS-2 (medium, defer) — the silent-except telemetry seam (ledger follow-up 7 / error-handling F3) is NOW SAFE to implement, but fill.py is being refactored mid-flight by a concurrent session
Current counts (AST, not grep): ems_exec has **214 broad `except Exception:`/bare handlers** (was 211 at the
morning audit), **67 of them body==`pass`** (was 64); fill.py alone has **20** silent passes (was 19 — the new
`_null_untouched_placeholders` guard added one). `import logging`/`getLogger` still appear NOWHERE in the package
(grep: zero hits) — a TypeError in any post-fill pass still silently regresses the payload with no trace.
What changed since the morning: the obs layer LANDED inside the package (data/neuract.py:44 sql_trace,
_insight.py:29/114 ai_log + llm_tap; run-scoped trace_id contextvar per AUDIT_REPORT R7 note), so pass-failure
events now have a run-keyed sink to land in. The ONE seam (do NOT scatter): `ems_exec/executor/degrade.py`
`run_pass(name, fn, *a, **kw)` — wraps each of the ~17 post-fill guard blocks (fill.py:388-618), preserves
fail-open, emits `logging.getLogger("ems_exec").warning(..., exc_info=True)` + optionally an obs event keyed by
current_run_id, and can count pass-failures next to GAPS_KEY. Behavior-preserving = safe — BUT fill.py's mtime
is 07:41:51 IST today (field_routing/series_router extraction landed DURING this audit), so the edit itself is
**defer**: land it as the next batch after the in-flight fill.py extraction settles, coordinating with that
session (the ledger already says "coordinate with the obs-trace session"; verified no equivalent landed).

### OBS-3 (low, safe) — blank.py adoption incomplete: two leftover local blank predicates lib/blank.py's own docstring does not exempt
The ledger claims rewiring of gaps/roster_gaps/roster/scalar_mean_fill/render_verdict (all verified true), and
lib/blank.py:6-7 names the ONLY intentional local extensions (scalar_tile placeholder-0.0, sankey DB-sentinel
list). Not rewired and not exempted:
- `ems_exec/executor/trend_badge.py:25` local `DASH = "—"` + `:39` `_blank(v)` == exactly `is_blank_scalar`;
- `ems_exec/executor/roster_stats.py:180-181` `_blank(v)` (`None/'—'/''/[]`) == exactly `is_blank(v, empty_list=True)`.
Both are the "ninth spelling" drift risk the home was built to kill (a future edit to the wire contract misses
them). Mechanical repoint, safe.

### OBS-4 (low, safe) — post-split staleness: a misleading test comment and an over-claiming facade docstring
- tests/test_fab_guards.py:640: "NB: _mag_re()/_MAGNITUDE_RE are module-level — rebuild via reload" — FALSE
  post-split: both names are gone; the regex is now the call-time vocab-keyed `_magnitude_re()`
  (fab_guards/class4_seed.py), and no reload is needed for the knob to take effect (that was the point of the fix).
- fab_guards/__init__.py:57 claims it "re-exports the original module surface byte-compatibly" — 12 HEAD-private
  names are NOT re-exported (`_mag_re`, `_MAGNITUDE_RE`, `_NO_RAW`, `_mag_units`, `_trivial_int_magnitude`,
  `_trivial_string_maxlen`, `_is_structural_chrome`, `_TIME_SUFFIXES_DEFAULT`, `_TIME_EXACT_DEFAULT`,
  `_DATA_VALUE_KEYS_DEFAULT`, `_MAG_UNITS_DEFAULT`, `_SCALE_SELECTOR_KEYS_DEFAULT`). Verified NO external
  consumer references any of them (tree-wide grep), so this is doc accuracy only — soften the claim or add them.

### OBS-5 (low, defer) — cross-session doc drift: today's followups-triage lens is already stale on monoliths F4-F10
docs/audit_prodready_20260712/followups-triage.md:119 records "OPEN: meta_path import-hook still installed
(ems_exec/executor/indexed_families.py:582-602); fill.py 672 lines / 21 except sites". In-tree NOW: the hook is
DELETED (indexed_families.py is 326 lines; only a tombstone comment at :322-325 remains), fill.py is 620 lines,
and the extraction landed as untracked `field_routing.py` (mtime 07:41) + `series_router.py` (07:39) +
`energy_registers.py` + `roster_labels.py`. Anyone triaging the F4-F10 row from that table will re-plan work
that is already done. Defer to (or notify) the triage/refactor sessions; the fix is a one-line status update
after the in-flight batch lands.

## Prior findings re-checked, unchanged (NOT re-reported — recorded for closure only)
- M5 import-time knob reads persist: panel_aggregate.py:62-64 `_ENERGY/_ENERGY_EXPORT/_ENERGY_POLICY` + :236
  `_LOAD_FACTOR_FNS`; _insight.py:68-71 `LLM_*`. D3 repointed their `_cfg` to config/failopen.cfg_safe but the
  module-import-time evaluation stays. Still open, still as the morning lens described.
- M11 manual SQL escape of an LLM-declared endpoint persists (recipe.py:81-82).
- M4 residue: `_tokset` still duplicated (measurable_resolve.py:84 vs load_factor_fill.py:166);
  scalar_tile_fill.py:165-166 `_toks` per-call re-import shim. (The `_honest_blanked`/`_blank`/`_cfg` limbs of
  M4 WERE deduped — D5/D3 verified.)
- M3 wildcards `filled_paths.add` outside the try persists (wildcards.py — unchanged today).

