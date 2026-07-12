"""ems_exec/renderers/panel_aggregate.py — the PANEL-AGGREGATE fan-out renderer (the GENERIC legacy path).

A panel_aggregate card is NOT a single meter read: it fans a PANEL out to its member feeders (registries.neuract edges,
the SAME door topology_sld used) and rolls the members' REAL neuract electrical up by QUANTITY (power/energy → Σ,
pf/voltage/thd → mean, current/neutral → Σ).

CUTOVER (2026-07-03, generalization package §4 Phase 2): the per-card BESPOKE assemblers that used to live here —
meter rosters + sankey (cards 12/13), worst-of/breach strip (23), PQ panels[] rosters (24/26/27), the role-grouped
heatmap grid (5) — are DELETED. Those cards are now served by the GENERIC roster interpreter
(ems_exec/executor/roster.py) driven by their cmd_catalog.card_fill_recipe rows (valve app_config
roster.interpreter_enabled='on'; shadow-mode parity evidence in outputs/logs/roster_shadow.log). Card-specific facts
live in the recipe rows, not in code.

What REMAINS here is the recipe-less legacy path (cards without a card_fill_recipe row — e.g. 7/10/11 — fall back to
this render from the run_special valve):

  · KPI / scalar leaves → build ONE aggregated superset row {column: rolled_value} across members and hand it to the
    per-card executor via ctx['_agg_row']; the executor's raw fields fill from that row verbatim (zero duplication —
    see ems_exec.executor.fill agg_row hook).

  · member-rolled BUCKETED trend series + time axis → the fan-out the per-card executor honestly skipped (its single
    meter is the panel's own EMPTY device table, so declared trend.series came back []).

MEMBER RESOLUTION + READS + ROLL-UP = ems_exec.executor.members (the ONE proven fan-out home — resolve/rows/select/
agg_row/bucketed_rolled), parameterized with THIS renderer's own panel_aggregate.* column/config vocabulary below. The
ONLY logic kept local is the panel_aggregate.* energy REGISTER POLICY (_panel_energy_kwh/_member_energy_kwh — the
`register_policy` 'import_only' escape hatch members' roster.* config home does not know).

HONEST-DEGRADE (never fabricate): an orphan / no-member panel returns the card's payload with its data leaves honest-
blanked (the executor's own strip) + widgets._coverage={reporting:0, expected:0, verdict:'honest_blank'}. A column
absent on every member honest-nulls. A member that doesn't report is excluded from the mean denominator (partial-
coverage honesty). [atomic; DATA = NEURACT ONLY; reuses members + _agg + the executor]
"""
from __future__ import annotations

from ems_exec.data import neuract as _nx                       # noqa: F401  (the ONE neuract module — test patch anchor)
from ems_exec.executor import fill as _fill
from ems_exec.executor import members as _members
from ems_exec.derivations import energy as _energy
from ems_exec.derivations import power as _power

# the card_handling classes this renderer serves — the package __init__ discovers this declaration (self-registration)
HANDLING_CLASSES = ("panel_aggregate",)


from config.failopen import cfg_safe as _cfg   # THE guarded cfg reader (D3)


# ── the neuract leaf columns the aggregate superset row rolls up (present-tolerant: an absent one → None per member) ───
# extensive (Σ) magnitudes + intensive (mean) intensities + the cumulative energy counter (windowed-delta Σ).
_KW = "active_power_total_kw"
_KVAR = "reactive_power_total_kvar"
_KVA = "apparent_power_total_kva"
_PF_TRUE = "kpi_true_pf"
_PF_SIGNED = "power_factor_total"
_VOLT = "voltage_avg"
_CURR = "current_avg"
# energy roll-up registers — reversed-CT aware: a member wired reversed-CT keeps its real energy on the EXPORT register
# (the 3 GIC UPS feeders read import_delta=0 while active_energy_export_kwh moves ~4700 kWh); a forward member (bpdb-01)
# uses import normally. The roll-up reads BOTH per member and PICKS the register that moved (energy._pick_register). Both
# column names + the selection policy are cmd_catalog knobs (config/app_config) with the code default below.
_ENERGY = _cfg("panel_aggregate.energy_import_column", "active_energy_import_kwh")
_ENERGY_EXPORT = _cfg("panel_aggregate.energy_export_column", "active_energy_export_kwh")
_ENERGY_POLICY = str(_cfg("panel_aggregate.register_policy", "pick_mover")).strip().lower()
_NEUTRAL_A = "current_neutral"
_NEUTRAL_RATIO = "kpi_neutral_to_phase_ratio_pct"
_PF_GAP = "pf_gap_vs_full_load"
_H5 = "harmonic_5th_pct"
_H7 = "harmonic_7th_pct"
# per-phase THD → a card's iThd / vThd are the mean of the three phases (a single avg col does not exist on gic_*).
_THD_I = ("thd_current_r_pct", "thd_current_y_pct", "thd_current_b_pct")
_THD_V = ("thd_voltage_r_pct", "thd_voltage_y_pct", "thd_voltage_b_pct")
_EVT_NEUTRAL = "neutral_stress_event_active"
_IUNBAL = "current_unbalance_pct"

# the full column set read per member's latest row (present-tolerant).
_MEMBER_COLS = [_KW, _KVAR, _KVA, _PF_TRUE, _PF_SIGNED, _VOLT, _CURR, _NEUTRAL_A, _NEUTRAL_RATIO, _PF_GAP,
                _H5, _H7, *_THD_I, *_THD_V, _EVT_NEUTRAL, _IUNBAL]

# columns rolled by Σ (extensive) vs mean (intensive) into the aggregate superset row. A column not listed defaults to
# mean via _agg.reducer_for (the safe intensive default).
_SUM_COLS = {_KW, _KVAR, _KVA, _CURR, _NEUTRAL_A}


# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
#  the panel_aggregate.* energy register policy — the ONE local seam members' roster.* config home does not carry
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
def _panel_energy_kwh(member_rows, window, role_filter="load"):
    """Σ of per-member windowed energy deltas over the ctx window — REVERSED-CT AWARE (the register fix). For EACH
    `role_filter`-side member the roll-up reads BOTH the import and the export cumulative counter, computes each
    register's (end−start) delta, and PICKS the register that actually moved (energy.member_energy_delta → _pick_register):
    a forward feeder keeps import, a reversed-CT feeder (import flat, export moving) keeps its real export magnitude —
    abs()'d so it shows a POSITIVE kWh. A genuinely dark feeder (neither register present / no rows / no movement)
    contributes nothing (its delta is None) and is excluded, never fabricated as 0. None when NO member yields a real
    delta (honest-null). role_filter defaults to 'load' (fed feeders — an incomer's counter measures the same flow, the
    double-count guard); 'supply' rolls the incomer side. policy!='pick_mover' → import-only."""
    start, end = window
    total = None
    for m, _r in _members.select(member_rows, role_filter=role_filter or "load"):
        picked = _member_energy_kwh(m, start, end)
        if picked is not None:
            total = (total or 0.0) + picked
    return round(total, 1) if total is not None else None


def _member_energy_kwh(m, start, end):
    """ONE load member's real windowed energy magnitude, reversed-CT aware. Reads its import + export register deltas
    (only the registers the table actually carries — members.member_delta_pair) and picks the mover. None when neither
    moved (honest-null, never a fabricated 0). policy 'import_only' → the legacy single-register delta (kept as a
    config escape hatch — the panel_aggregate.* rows stay authoritative here, never re-keyed onto roster.*)."""
    imp = _members._delta_of(_members.member_delta_pair(m, (start, end), _ENERGY))
    if _ENERGY_POLICY != "pick_mover":
        return imp                                              # legacy import-only (config escape hatch)
    exp = _members._delta_of(_members.member_delta_pair(m, (start, end), _ENERGY_EXPORT))
    return _energy.member_energy_delta(imp, exp)


# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
#  bucketed trend series — member fan-out the per-card executor can't do (its single meter is the EMPTY panel device)
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
def _rolled_series(member_rows, col, window, sampling, role_filter="load"):
    """The member-rolled [{t, value}] series for one column: per bucket Σ for extensive magnitudes (_SUM_COLS) else
    mean — the SAME quantity rule as the aggregate row (members.bucketed_rolled). role_filter defaults to 'load' (the
    fed feeders/bays) and is 'supply' for an incomer-side panel prompt. [] when no member reports the column."""
    return _members.bucketed_rolled(member_rows, col, window, sampling=sampling,
                                    reduce=("sum_magnitude" if col in _SUM_COLS else "mean"),
                                    role_filter=role_filter or "load")


def _fill_bucketed_series(out, di, member_rows, window, role_filter="load"):
    """Fill the card's DECLARED bucketed/time fields by fanning out to the panel MEMBERS (cards 7/10 trend.series). The
    per-card executor honestly returned [] for these — its single meter is the panel's own EMPTY device table — so the
    renderer rolls each declared series up across members per bucket and fills the time-axis leaves from the same
    buckets. Only a non-empty rolled series overwrites; otherwise the executor's honest [] stands. `role_filter` picks
    the reading side (default 'load' = fed feeders; 'supply' = incomers)."""
    fields = [f for f in ((di or {}).get("fields") or []) if isinstance(f, dict)]
    axis = None                                              # the shared bucket axis (epoch ms) of the LAST rolled series
    for f in fields:
        kind = (f.get("kind") or "raw").lower()
        slot = f.get("slot") or f.get("target_column") or f.get("metric")
        leaf_path = _fill._leaf_path_for(out, slot)
        if leaf_path is None:
            continue
        leaf = _fill._leaf_at(out, leaf_path)
        if kind == "bucketed" or (kind in ("raw", "") and isinstance(leaf, list)):
            col = f.get("column")
            if not col:
                continue
            series = _rolled_series(member_rows, col, window, f.get("sampling") or "hourly", role_filter=role_filter)
            if series:
                _fill._set_leaf_typed(out, leaf_path, [pt["value"] for pt in series])
                axis = [_fill._epoch_ms(pt["t"]) for pt in series]
    if axis:
        for f in fields:                                      # declared kind='time' leaves ride the same bucket axis
            if (f.get("kind") or "").lower() != "time":
                continue
            slot = f.get("slot") or f.get("target_column") or f.get("metric")
            leaf_path = _fill._leaf_path_for(out, slot)
            if leaf_path is None:
                continue
            key = (leaf_path.rsplit(".", 1)[-1] or "").lower()
            if isinstance(_fill._leaf_at(out, leaf_path), list):
                _fill._set_leaf_typed(out, leaf_path, list(axis))
            elif key.endswith("startms"):
                _fill._set_leaf_typed(out, leaf_path, axis[0])
            elif key.endswith("endms"):
                _fill._set_leaf_typed(out, leaf_path, axis[-1])


# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
#  render — the renderer entry (uniform signature)
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
def render(asset, card, ctx):
    """Fill a RECIPE-LESS panel_aggregate card's payload from its members' real neuract electrical (the KPI/scalar
    agg-row fill + the member-rolled bucketed series). Returns the COMPLETED CMD_V2 payload (never raises via
    run_special's guard). Cards WITH a card_fill_recipe row never reach here under the 'on' valve — the generic roster
    interpreter serves them (cutover 2026-07-03).

    asset — {mfm_id, name, table}; card — carries the card's exact_metadata (`payload`/`exact_metadata`) + data_instructions
    + _default_payload (passed through by the host); ctx — {asset_table, mfm_id, db_link, window, page_key}. HONEST-DEGRADE:
    an orphan / no-member panel returns the payload with data leaves honest-blanked + widgets._coverage.verdict='honest_blank'."""
    ctx = ctx or {}
    card = card or {}
    payload = _card_payload(card)
    di = card.get("data_instructions") or {}
    default_payload = card.get("_default_payload")
    # shape_ref = the RAW harvested default (host hands it down). fill() threads it into fab_guards' CLASS-4 raw-vs-
    # stripped wall so PRESENTATION metadata (stackOrder/lineOrder/columnOrder/tileOrder/layout/palette/preset values)
    # is KEPT byte-identical instead of over-blanked by the legacy chrome-vocab fallback. None → legacy behaviour.
    shape_ref = card.get("shape_ref")
    mfm_id = ctx.get("mfm_id") or (asset or {}).get("mfm_id")
    window = _fill._window_of(ctx, None)
    # PANEL READING DIRECTION [panel_overview]: the prompt's incomer-vs-outgoing choice (stamped on the resolved asset;
    # threaded via host/exec_cards). 'outgoing' (default) rolls the fed feeders/bays; 'incomer' rolls the supply side.
    scope = (asset or {}).get("member_scope") or ctx.get("member_scope")
    role_filter = _members.role_filter_for(scope)

    if payload is None:
        return None                                       # no payload skeleton to fill → host falls back (run_special)

    members, coverage = _members.resolve(mfm_id)          # ([], honest_blank) on an orphan / None panel

    # orphan / no-member panel → honest-blank the data leaves (executor strip) + honest coverage badge, never fabricate.
    if not members:
        out = _fill.fill(payload, di, {"asset_table": ctx.get("asset_table"), "window": window, "_agg_row": {}},
                         default_payload=default_payload, shape_ref=shape_ref)
        _attach_coverage(out, coverage)
        return out

    member_rows = _members.rows(members, _MEMBER_COLS, ts_col=_members.ts_col())
    # the fleet-rolled superset row (Σ/mean per _SUM_COLS + the unsigned true-PF fold), energy per THIS renderer's
    # panel_aggregate.* register policy — never members' roster.* energy home (config homes stay distinct).
    agg = _members.agg_row(member_rows, window, _MEMBER_COLS, _SUM_COLS,
                           pf_cols=[_PF_TRUE, _PF_SIGNED], power_col=_KW, role_filter=role_filter)
    agg[_ENERGY] = _panel_energy_kwh(member_rows, window, role_filter=role_filter)

    # (1) KPI / scalar leaves — reuse the per-card executor verbatim, feeding it the aggregated superset row.
    out = _fill.fill(payload, di,
                     {"asset_table": ctx.get("asset_table"), "window": window, "_agg_row": agg},
                     default_payload=default_payload, shape_ref=shape_ref)

    # (2) member-rolled BUCKETED trend series + time axis — the fan-out the per-card executor honestly skipped
    # (its single meter is the panel's own EMPTY device table, so declared trend.series came back []).
    _fill_bucketed_series(out, di, member_rows, window, role_filter=role_filter)

    # (3) member-rolled LOAD-FACTOR — the per-card executor's derived load_factor read the panel's OWN (empty) device
    # power series and blanked; refill it from the SAME rolled member power series the worst-peak tile uses.
    _fill_rolled_load_factor(out, di, member_rows, window, role_filter=role_filter)

    _attach_coverage(out, coverage)
    return out


# the derivation fn names that take load factor over a POWER SERIES (a windowed mean÷peak) — these are the leaves whose
# per-card executor value comes from the panel's OWN (empty) device series and must instead ride the member-rolled trend.
_LOAD_FACTOR_FNS = frozenset(str(x).strip().lower()
                             for x in _cfg("panel_aggregate.load_factor_fns",
                                           ["loadfactorpct", "loadfactorwindowpct"]))


def _fill_rolled_load_factor(out, di, member_rows, window, role_filter="load"):
    """Fill any DECLARED derived load-factor leaf from the member-rolled power series (not the empty panel device). The
    per-card executor already ran the fn against the panel's own table and honest-blanked; here we roll the members'
    power up ONCE and overwrite each declared load-factor leaf with the fleet trend's mean÷peak. Honest-degrade: an empty
    rolled series → None (the leaf stays blank), never a fabricated load factor. Only overwrites the declared leaves.
    `role_filter` picks the reading side (default 'load' = fed feeders; 'supply' = incomers)."""
    fields = [f for f in ((di or {}).get("fields") or []) if isinstance(f, dict)]
    lf_fields = [f for f in fields
                 if (f.get("kind") or "").lower() == "derived"
                 and str(f.get("fn") or "").strip().lower() in _LOAD_FACTOR_FNS]
    if not lf_fields:
        return
    series = _rolled_series(member_rows, _KW, window, "hourly", role_filter=role_filter)   # SAME roll-up the peak tile reads
    lf = _power.load_factor_from_series(series)                 # None on an empty rolled series (honest-blank)
    for f in lf_fields:
        slot = f.get("slot") or f.get("target_column") or f.get("metric")
        leaf_path = _fill._leaf_path_for(out, slot)
        if leaf_path is not None:
            _fill._set_leaf_typed(out, leaf_path, lf)


def _card_payload(card):
    """The card's payload skeleton to aggregate onto — prefer the Layer-2 exact_metadata (the specific story L2 chose),
    then a bare 'payload'. None when neither is present."""
    for k in ("exact_metadata", "payload", "skeleton"):
        v = card.get(k)
        if isinstance(v, dict):
            return v
    return None


def _attach_coverage(out, coverage):
    """Attach widgets._coverage = {reporting, expected, verdict} so the FE can badge a partial fleet sum honestly. Kept
    under a top-level 'widgets' envelope (created if absent) so it never collides with the card's own payload keys."""
    if not isinstance(out, dict):
        return
    w = out.get("widgets")
    if not isinstance(w, dict):
        w = {}
        out["widgets"] = w
    w["_coverage"] = coverage
