# Refactor audit 2026-07-12 — Dimension: HARDCODING vs DB-DRIVEN

Auditor: subagent (hardcoding dimension). Scope: pipeline_v48 (skipping archive/, outputs/, artifacts).

## Overall verdict

The codebase is **unusually disciplined** about house rule 4. Nearly every threshold, band,
factor and vocab is already behind `cfg()` / a cmd_catalog reader with a code-default mirror:

- `config/app_config.py` — the canonical `cfg()` door (process-cached, fail-open).
- `config/rating_knobs.py`, `event_thresholds.py`, `asset_class_defaults.py`, `nameplates.py`,
  `quality_policy.py`, `energy_balance_policy.py`, `feeder_overview.py` — all thin DB readers
  with code defaults. **Do not touch.**
- `ems_exec/executor/bindings.py` (Policy), `yscale.py`, `norm_series.py`,
  `ems_exec/derivations/power.py`, `_story/real_time_monitoring.py` — knobs behind cfg with
  code-default mirrors. **Do not touch.**
- Ports/URLs are env-driven (`LLM_URL`, `V48_HOST_PORT`, `COPILOT_LLM_URL`, `V48_VALIDATE_BASE`).
- PCC panel IDs 317-320 appear **only in comments/docstrings**, never in logic.

The findings below are the residual outliers: mostly **knob drift** (the same physical policy
encoded twice — once as a DB row, once as a raw literal, so editing the row silently doesn't
move all consumers) and a couple of duplicated business literals.

---

## Findings

### F1. `ai_loss_summary` hardcodes the 3% loss band its own module reads from the DB
- **File**: `ems_exec/derivations/topology.py:94-96`
- **Evidence**:
  ```python
  if loss >= 3.0:
      return (f"{loss:.1f}% loss exceeds the 3% expected band — inspect winding temperature and phase loading.")
  ```
  Twenty lines above, `_single_feeder_loss_band_pct()` (line 45-54) reads the SAME policy from
  `energy_balance.expected_loss_band_pct` (default 3.0). `distribution_loss_pct` (which
  `ai_loss_summary` calls) uses the DB knob; the verdict prose compares against a frozen `3.0`
  and bakes "3%" into the string. Edit the row to 5.0 → the single-feeder proxy returns 5.0%
  and the summary says "5.0% loss exceeds the 3% expected band" — self-contradicting output.
- **Proposal**: `band = _single_feeder_loss_band_pct()`; compare `loss >= band` and interpolate
  `{band:.0f}%` into both prose strings.
- **Risk**: low. **Behavior-preserving**: yes (default is 3.0; identical until a row exists —
  and once a row exists this is the *intended* behavior).
- **Tests guarding**: `tests/test_card41_loss_eff_proxy.py`, `tests/test_derivation_evaluate.py`,
  `tests/test_residual2_fixes.py`.

### F2. IEEE-519 I-THD limit `8` hardcoded in `thd_compliance_ieee519`, drifting from the DB-editable copies
- **File**: `ems_exec/derivations/power_quality.py:73`
- **Evidence**: `return 1.0 if ithd <= 8 else 0.0` — while the same 8.0% limit is DB-editable in
  `config/event_thresholds.py` (`I_THD: ('thd_compliance_i_avg','above',8.0)`) and
  `config/asset_class_defaults.py` (`thd_i_limit_pct: 8.0`, `ieee_519_current_thd_limit_pct: 8.0`).
  Retuning the row (the module's stated purpose: "an engineer retunes IS-12360/IEEE-1159/IEEE-519
  limits by editing a row, NOT a magic number in a consumer") does not move this consumer.
- **Proposal**: read `config.event_thresholds.num("I_THD", 8.0)` (or `cfg("derivation.ieee519_ithd_limit_pct", 8.0)`)
  inside a try/except with the 8.0 code default, matching the module-local `_cfg` pattern already
  used in `derivations/nameplate.py`.
- **Risk**: low. **Behavior-preserving**: yes until a row diverges (then it's the intended fix).
- **Tests guarding**: `tests/test_derivation_evaluate.py`, `tests/test_fab_guards.py`
  (thd_compliance grep hits).

### F3. Statutory voltage band ±10% hardcoded in `statutory_band`, bypassing the per-class DB default
- **File**: `ems_exec/derivations/voltage.py:35`
- **Evidence**: `return {"min": round(nom * 0.90, 1), "max": round(nom * 1.10, 1), ...}` — but
  `config/asset_class_defaults.py` carries `voltage_statutory_deviation_pct` per class, and it is
  NOT uniform: Transformer/DP/LT/UPS = 10.0, **DG = 5.0**. Every DG voltage-history band drawn by
  this derivation is twice as wide as the class policy says. The band fraction is business policy
  (IS-12360) encoded as raw literals.
- **Proposal**: accept the deviation pct via `ctx` (filled by the caller from
  `asset_class_defaults.class_field(cat, "voltage_statutory_deviation_pct", 10.0)`), or minimally
  `cfg("derivation.statutory_band_pct", 10.0)`. Keep 10.0 as the code default (behavior-preserving);
  wiring the per-class value is a follow-up behavior *change* to flag to the owner.
- **Risk**: low for the cfg lift; medium if wired to per-class (DG bands narrow — visible change).
- **Behavior-preserving**: yes (cfg lift with default 10.0); no (per-class wiring).
- **Tests guarding**: `tests/test_derivation_evaluate.py` (no dedicated statutory_band test found —
  add one before touching).

### F4. Chart padding policy duplicated: `voltage_history_domain` re-hardcodes the pad the yscale/norm_series knobs own
- **File**: `ems_exec/derivations/voltage.py:97`
- **Evidence**: `pad = max((hi - lo) * 0.1, 1.0)` — the identical range-pad / flat-pad-min policy
  is DB-driven in `ems_exec/executor/norm_series.py:44-45` (`chart.norm_range_pad_pct` = 0.1,
  `chart.norm_flat_pad_min` = 1.0) and `yscale.py` (`chart.yscale_pad_pct`). Editing the chart
  rows leaves voltage-history domains on the frozen literals.
- **Proposal**: read the same `chart.norm_range_pad_pct` / `chart.norm_flat_pad_min` keys via the
  local `_cfg` fallback pattern (defaults 0.1 / 1.0).
- **Risk**: low. **Behavior-preserving**: yes.
- **Tests guarding**: `tests/test_yscale_derivation.py`, `tests/test_derivation_evaluate.py`.

### F5. Severity "warn at 70% of limit" fraction duplicated as a raw literal across two story builders
- **Files**: `ems_exec/renderers/_story/voltage_current.py:81-82` and
  `ems_exec/renderers/_story/harmonics_pq.py:60`
- **Evidence**:
  ```python
  v_sev = _sev(v_worst["mag"], min(sag_pct, swell_pct) * 0.7, min(sag_pct, swell_pct)) ...
  i_sev = _sev(i_worst["mag"], i_unbal_limit * 0.7, i_unbal_limit) ...
  ```
  and in harmonics_pq `_sev`: `if mag >= limit * 0.7: return "warning"`. The warning fraction is
  business severity policy repeated in (at least) 3 call sites across 2 files; the limits
  themselves are DB-driven (event_thresholds) but the warn fraction is not.
- **Proposal**: one `cfg("story.sev_warn_fraction", 0.7)` accessor (e.g. in `_story/_facts.py`,
  the shared helper module) used by both builders.
- **Risk**: low. **Behavior-preserving**: yes.
- **Tests guarding**: `tests/test_harmonics_story_real_thd.py` (harmonics side); no dedicated
  voltage_current story test found — verify with a live page-19/25 sweep.

### F6. Loading-% plausibility ceiling exists as TWO different app_config keys (200.0 default each)
- **Files**: `ems_exec/derivations/power.py:45` (`power.loading_plausible_max_pct`, mirror
  `_LOADING_PLAUSIBLE_MAX_PCT = 200.0`) and
  `ems_exec/renderers/_story/real_time_monitoring.py:70` (`cfg("story.load_pct_plausibility_ceiling", 200.0)`)
- **Evidence**: both guard the exact same physical policy — "a load% above N× the rating means the
  denominator is wrong, honest-blank". Two rows must now be edited in lockstep; seeding one and
  not the other silently splits the wall (card-8 story blanks at 200% while a derivation-filled
  loading leaf blanks at the other row's value, or vice versa).
- **Proposal**: point the story at the derivation's key: `cfg("power.loading_plausible_max_pct", 200.0)`
  (keep reading the old key as a fallback for one release if a row may already exist), then retire
  `story.load_pct_plausibility_ceiling`.
- **Risk**: medium (must check app_config for an existing `story.load_pct_plausibility_ceiling` row
  before retiring it). **Behavior-preserving**: yes when neither/both rows are seeded equal.
- **Tests guarding**: `tests/test_power_plausibility_knobs.py` (covers the derivation-side knob;
  the story-side key has no dedicated test).

### F7. Two kVA→kW PF-of-record knobs with different keys AND different defaults (0.9 vs 0.8)
- **Files**: `config/rating_knobs.py:15-17` (`rating.feeder_pf`, default **0.9**, used by
  `config/nameplates.py derive_ratings`) and `ems_exec/derivations/nameplate.py:24-29`
  (`nameplate.nominal_pf`, default **0.8**, used by `feeder_rated_kw`)
- **Evidence**:
  ```python
  # rating_knobs.py
  def feeder_pf(): return _qp.num("rating.feeder_pf", 0.9)
  # derivations/nameplate.py
  pf = float(_cfg("nameplate.nominal_pf", 0.8))
  ```
  Both convert nameplate kVA → rated kW. The same asset can render `rated_kw = kva*0.9` on a card
  filled via `derive_ratings_for` and `rated_kw = kva*0.8` on one filled via
  `derivations.nameplate.feeder_rated_kw` — a 12.5% disagreement between cards on one page.
  Both are DB-driven (rule-4-compliant individually) but encode ONE physical convention twice.
- **Proposal**: not a mechanical merge (defaults differ → merging changes numbers somewhere).
  Flag to owner: pick the PF-of-record, seed BOTH rows to it, then alias one accessor to the other
  and deprecate the losing key. Document which fill paths use which today.
- **Risk**: medium. **Behavior-preserving**: no (any consolidation moves one path's numbers) —
  report-only until the owner picks the convention.
- **Tests guarding**: `tests/test_equipment_ratings.py`, `tests/test_derivation_evaluate.py`.

### F8. Storybook base URL defaults to a hardcoded LAN IP, env-only (house pattern is DB → env → default)
- **File**: `host/server.py:46`
- **Evidence**: `SB_BASE = os.environ.get("STORYBOOK_URL", "http://100.90.185.31:6008").rstrip("/")` —
  a Tailscale/LAN IP baked into code as the default. Contrast the established endpoint pattern in
  `ems_exec/renderers/_insight.py:40-54` `_env()`: **app_config row first, then env, then code
  default** (used for `insight.llm_url` etc.). Every other service endpoint here defaults to
  localhost or is DB-driven (`config/neuract_dsn.py`); this is the only raw non-local IP in the
  serving path.
- **Proposal**: `SB_BASE = (os.environ.get("STORYBOOK_URL") or cfg("host.storybook_url", "http://100.90.185.31:6008")).rstrip("/")`
  (cfg is already imported in server.py as "DB-tunable operational knobs").
- **Risk**: low. **Behavior-preserving**: yes.
- **Tests guarding**: `tests/test_fe_data_note_serve.py`, `tests/test_multi_asset.py` (host.server importers).

### F9. Epoch-timestamp magnitude threshold: DB knob in fab_guards (1e12) vs raw `1e10` duplicated in two axis passes
- **Files**: `ems_exec/executor/yscale.py:124-126`, `ems_exec/executor/xaxis.py:87-90`
  (vs `ems_exec/executor/fab_guards.py:59-66`)
- **Evidence**: fab_guards reads `cfg("fab_guards.epoch_ms_floor", 1_000_000_000_000)`; yscale and
  xaxis each carry a private `_is_epoch_list` with the raw literal `x > 1e10`:
  ```python
  def _is_epoch_list(v):
      return (isinstance(v, list) and len(v) >= 2 and
              all(isinstance(x, (int, float)) and not isinstance(x, bool) and x > 1e10 for x in v))
  ```
  Three encodings of the same "this magnitude is an epoch-ms timestamp" heuristic, two of them
  frozen literals (and at a different floor, 1e10 vs 1e12 — values in between are classified
  inconsistently between the guard and the axis passes).
- **Proposal**: one shared `_is_epoch_list` helper reading its OWN key
  `cfg("chart.epoch_list_floor", 1e10)` (own key + current default preserves behavior; do NOT
  silently unify to 1e12). Flag the 1e10-vs-1e12 discrepancy to the owner.
- **Risk**: low. **Behavior-preserving**: yes (own key, same default).
- **Tests guarding**: `tests/test_yscale_derivation.py`, `tests/test_fill_hook_order.py`,
  `tests/test_fab_guards.py`.

### F10. `roster.power_column` / `roster.pf_columns` knobs are honored by ONE consumer; the same column names are raw literals in ~15 other files
- **Files**: `ems_exec/executor/bindings.py:41-42` (the knob) vs raw `"active_power_total_kw"` /
  `"kpi_true_pf"` / `"power_factor_total"` literals in `ems_exec/renderers/_story/_facts.py:18-28`
  (`LIVE_COLS`), `_story/real_time_monitoring.py:52-53` (`_TEMP_COLS` probe list, `_unsigned_pf`),
  `_story/harmonics_pq.py:65-66` (`_V_COLS`/`_I_COLS`), `ems_exec/derivations/{power,energy,topology,registry}.py`,
  `ems_exec/executor/{roster,fill,measurable_resolve,derived,scalar_mean_fill}.py`,
  `ems_exec/renderers/panel_aggregate.py` — ~51 occurrences of `active_power_total_kw` alone.
- **Evidence**: `self.power_col = cfg("roster.power_column", "active_power_total_kw")` promises the
  canonical power column is a DB row, but editing that row moves ONLY roster bindings; every other
  consumer keeps the literal. The knob half-exists — the most misleading state for an operator.
- **Proposal**: decide the knob's fate. Either (a) a single `config/dataset_columns.py` thin
  accessor (house atomic style: `power_col()`, `pf_cols()`, `temp_probe_cols()`, `thd_phase_cols()`)
  reading the existing `roster.*` keys (+ new `story.busbar_temp_columns`), adopted incrementally
  by the story/derivation modules; or (b) retire the `roster.power_column`/`roster.pf_columns`
  keys and document the gic_* column names as fixed schema vocabulary. Half-knobs are worse than
  either.
- **Risk**: medium (wide but mechanical). **Behavior-preserving**: yes (same defaults).
- **Tests guarding**: `tests/test_ems_exec_roster.py`, `tests/test_layer2_roster.py`,
  `tests/test_harmonics_story_real_thd.py`, `tests/test_page13_dg_cert_defects.py`.

---

## Examined and clean (do not refactor)

- `config/` (all 31 files): thin DB readers + code defaults throughout (`app_config.cfg`,
  `rating_knobs`, `event_thresholds`, `asset_class_defaults`, `quality_policy`,
  `energy_balance_policy`, `metric_class`, `schema_map`, `neuract_dsn`, `windows`). `databases.py`
  is the sanctioned single env-driven DB-wiring home.
- `layer2/gates.py`: every gate vocab/threshold behind cfg (`gates.chrome_markers`,
  `quantity.axis_*`, `gates.live_source_tokens`, …).
- `ems_exec/executor/fab_guards.py`, `yscale.py` (knobs), `norm_series.py`, `freshness.py`
  (`freshness.stale_after_s`), `window_policy.py`, `bindings.py` Policy: cfg + code-default mirrors.
- `ems_exec/derivations/power.py`: exemplary (`power.load_factor_*`, `power.loading_plausible_max_pct`).
- `_story/real_time_monitoring.py` `_knobs()`: all severity bands behind cfg.
- Ports/URLs: env-driven with localhost defaults (`llm/config.py`, `validation/config.py`,
  `copilot/config.py` — copilot is a deliberately decoupled service, env config is its style).
- PCC panel IDs 317-320: comments/docstrings only, never logic.
- `config/nameplates.py:76` 1% name-corroboration tolerance: single-site constant with clear
  semantics — LOW per triage rules, not worth a knob.
- `power_quality.py:99` ±2% trend deadband: single-site, LOW (bundle with F2 only if touching the file).
