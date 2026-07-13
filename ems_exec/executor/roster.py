"""ems_exec/executor/roster.py — THE GENERIC ROSTER INTERPRETER (generalization package §3). ONE capability, ZERO card
knowledge: given a validated roster instruction list (the AI emission folded into the card_fill_recipe row — see
recipe.py), it resolves the panel's members ONCE (data.neuract_live edges, roles preserved), reads each member's
declared columns (ems_exec.data.neuract), builds one element per member from the closed binding vocabulary
(bindings.py), groups / orders / caps per the instruction, reduces aggregate KPIs (reducers.py → _agg math), and writes
every result at the instruction's slot path — per-leaf honest-null throughout. NO card ids, NO root-key literals, NO
thresholds, NO element-key names live here: all of that arrives in the instruction rows.

The closed MODE vocabulary (the ONLY branch in this file):
    elements     one element per member → role-filter → order → cap → the list at the slot path
                 (a `[*]` mid-path repeats the list into every existing array element — snapshot_per_period).
    groups       one group per member: the FIRST existing/default group is the chrome TEMPLATE (seed-stripped),
                 group-key bindings + the element under `list_key` + `group_agg` reducers per group.
    aggregates   an agg-map of reducers over the member elements, merged onto the dict at the slot path
                 (per-agg role_filter overrides; element spec shared from the roster when the slot has none).
    sections     members grouped per the recipe's section vocabulary (`section_defs` matched by role/type/load_group/
                 name-prefix — the incomers group included — or plain `group_by:'role'`; unmatched members derive their
                 own section, never dropped), Σ section_agg totals, wrapped in ONE real sample; wholesale replace.
    sankey_match the design sankey's nodes/links re-valued by slug-containment member match: member → its own read,
                 trunk (declared marker kinds / the panel's own slug) → the panel Σ, ungrounded entity → honest-null
                 (NEVER the duplicated panel total). With `rebuild: true` the nodes/links (+ optional legend) are
                 REBUILT from the real member roster instead (the fixture's foreign entity labels never survive).
    series       the member-rolled BUCKETED value array at the slot ({column, reduce: sum_magnitude|mean, sampling,
                 role_filter} — per-bucket fold of each selected member's own bucketed read; the panel trend a
                 single-meter executor cannot fill because the panel's own device table has no electrical). Honest []
                 when no member reports the column. `points: true` → per-bucket elements ({t_key, t_fmt, value_key}
                 recipe-mapped), template-cloned like every other rebuilt roster.
    series_split like `series` but MULTIPLE keyed series per bucket ({series:[{key, match}]}): each declared series
                 folds only the members its `match` (types / load_groups / name_contains, case-insensitive substring on
                 name+table) selects, aligned on the UNION of bucket timestamps into one per-bucket point element
                 ({t_key label + one value per series key}, template-cloned). A series whose match selects NO member
                 (e.g. HHF — no such feeder on this panel) writes honest-null in every point, never a misattributed Σ.
                 The demand-by-feeder split (ups/bpdp/hhf) the single-`series` fold cannot express.
    scalar       ONE fleet reducer result written directly to a single SCALAR leaf (a fixed-index KPI tile value —
                 `stats.0.value` — not a dict to merge onto). Same reducer/element/filter vocabulary as `aggregates`.

Cross-mode slot vocabulary (all recipe-declared):
    range        the slot's OWN evaluation window ('today' / 'this-month' / 'last-7-days' — AUTHORITATIVE, anchored at
                 the run window's end) so a KPI whose chrome claims a period reads exactly that period (card 14).
    role_filter 'self'   the run's OWN meter as a roster of ONE (a single-meter card's windowed history stats reuse the
                 same rolled-series machinery — card 46); never mixed into the member selections.
    stats_only   (series) derive the stats scalars but write NO array at the slot (a stats-carrier over an already-
                 filled component series).
    entries      rebuild a FIXED id-keyed array leaf whose entries are per-QUANTITY reducers (metrics [Active/Reactive/
                 SEC], segments [Active/Reactive]): members read once via the shared `element`, then each `entries[i]`
                 reduces that set by its OWN agg into its value key(s), CLONED onto the id-matched default entry (chrome
                 survives). A `{"agg":"const","v":null}` entry is an honest blank (no such neuract column).
    const        the literal at the slot path.

THE TEMPLATE-CLONE RULE (per-leaf + FE-contract, 2026-07-03 pages 02/03 chrome defect) lives in roster_template.py;
the slot-path resolver (mutating _targets walk + roster_stats' read-only values_at mirror) in roster_paths.py; the
shared evaluation helpers in roster_eval.py; the mode handlers in roster_modes_{agg,groups,series,sankey}.py — all
re-exported here byte-compatibly (THIS module stays the one import target).

SEAMS: fill.prepare hook → prepare_ctx() (valve-guarded: resolves members once + injects ctx['_agg_row'] so scalar
fields fill from the fleet roll-up); fill end hook → run_roster() (fills the member-scope slots). Both no-op unless
app_config roster.interpreter_enabled != 'off' AND ctx carries an mfm_id AND a roster instruction/recipe exists.
Never raises — every slot honest-degrades independently. [atomic]
"""
from __future__ import annotations

import copy

from ems_exec.executor import bindings as _bindings
from ems_exec.executor import blank as _blank
from ems_exec.executor import members as _members
from ems_exec.executor import recipe as _recipe
from ems_exec.executor.window_policy import _window_of

# ── the atomic roster seams, re-exported byte-compatibly (the facade contract) ────────────────────────────────────────
from ems_exec.executor.roster_paths import (                                                  # noqa: F401
    _TOK, _toks, _base, _readdress, _targets, _walk, values_at)
from ems_exec.executor.roster_template import (                                               # noqa: F401
    _seedfree, _default_at, _default_list_at, _merge_template, _merge_templates)
from ems_exec.executor.roster_eval import (                                                   # noqa: F401
    _cfg, _select, _series_pairs, _slot_window, _eval_elements, _order_cap, _context_vals, _shared_element)
from ems_exec.executor.roster_modes_agg import _aggregates_slot, _scalar_slot, _entries_slot  # noqa: F401
from ems_exec.executor.roster_modes_groups import (                                           # noqa: F401
    _elements_slot, _groups_slot, _sections_slot, _group_pairs, _match_def)
from ems_exec.executor.roster_modes_series import (                                           # noqa: F401
    _series_slot, _series_stat, _series_multi_slot, _fmt_num, _emit_trend_scalars, _derive_point,
    _member_match, _series_split_slot, _series_split_legend)
from ems_exec.executor.roster_modes_sankey import (                                           # noqa: F401
    _sankey_slot, _node_role, _match_slug, _sankey_rebuild)


# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
#  activation + preparation — the ONE member resolution per card run
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
def _valve():
    """app_config roster.interpreter_enabled: on/off (the interpreter runs unless the value is 'off'). The cutover
    valve — code default 'on' mirrors the live row; the DB row stays the kill-switch, so a DB outage/fail-open read
    keeps the interpreter RUNNING instead of silently disabling the whole roster path."""
    try:
        from config.app_config import cfg
        return "off" if str(cfg("roster.interpreter_enabled", "on")).strip().lower() == "off" else "on"
    except Exception:
        return "on"


def _rescue_false_nulls(roster, member_tables):
    """Rewrite each roster ELEMENT key whose binding is {"b":"null"} into {"b":"col","c":<real column>} when the leaf
    key's OWN electrical semantics resolve to a column that is PRESENT AND LOGGED on the member tables — the recipe's
    false "no such column" claim was wrong (card 18: vAvg/vMax/vMin/amps → voltage_avg/max/min, current_avg). Mutates
    the normalized roster spec list IN PLACE. Over-reach-safe: no rescue unless a real, non-null column truly measures
    the key; a genuinely-absent column keeps its honest null. Generic — no card ids, no key literals; the column is
    derived from the key + verified against the DB. Never raises (a rescue failure leaves the null untouched)."""
    tabs = [t for t in (member_tables or []) if t]
    if not tabs:
        return
    try:
        from ems_exec.executor import measurable_resolve as _mr
    except Exception:
        return
    for spec in (roster or []):
        element = spec.get("element") if isinstance(spec, dict) else None
        if not isinstance(element, dict):
            continue
        for k, b in list(element.items()):
            if not (isinstance(b, dict) and (b.get("b") or "").strip().lower() == "null"):
                continue
            try:
                col = _mr.resolve_column(k, tabs, unit=b.get("unit"))
            except Exception:
                col = None
            if col:
                element[k] = {"b": "col", "c": col, "r": b.get("r", 1)}


def prepare_ctx(data_instructions, ctx):
    """Activate the roster interpreter for this card run (idempotent, valve-guarded). When active: resolve the panel's
    members ONCE, read every referenced column per member, stash the state under ctx['_roster_state'], and inject the
    fleet-rolled ctx['_agg_row'] (unless the caller already provided one) so the executor's scalar fields fill from the
    aggregate. No-op (and no ctx mutation) when the valve is off / no mfm_id / no roster instruction+recipe."""
    if not isinstance(ctx, dict) or "_roster_state" in ctx:
        return
    if _valve() == "off" or ctx.get("mfm_id") is None:
        return
    roster = _recipe.roster_for(data_instructions, ctx.get("card_id"))
    if not roster:
        return
    policy = _bindings.Policy()
    window = _window_of(ctx, data_instructions)
    member_cols = _cfg("roster.member_columns", [])
    sum_cols = set(_cfg("roster.sum_columns", []))
    energy_col = _cfg("roster.energy_column", "active_energy_import_kwh")
    ts = _members.ts_col()
    mlist, coverage = _members.resolve(ctx.get("mfm_id"))
    # FALSE-NULL RESCUE [R4 residual, card 18]: a recipe/emission element key declared {"b":"null"} because its `why`
    # claimed no such column — but the member tables DO carry the measuring column (vAvg/vMax/vMin/amps → voltage_avg/
    # voltage_max/voltage_min/current_avg). Rebind each such key to {"b":"col","c":<real column>} — ONLY when the
    # derived column is PRESENT AND LOGGED on the member tables (over-reach-safe; a genuinely-absent column stays null).
    # Runs BEFORE referenced_columns() so the rescued columns are read into every member row. [generic, no card ids]
    _rescue_false_nulls(roster, [m.get("table") for m in (mlist or [])])
    columns = sorted(set(member_cols) | _bindings.referenced_columns(roster)
                     | set(policy.pf_cols or []) | {policy.power_col})
    pairs = _members.rows(mlist, columns, ts_col=ts)
    # the SELF pseudo-member — the run's OWN meter as a roster of one, selected ONLY by an explicit role_filter 'self'
    # in a recipe slot (a single-meter card's windowed series stats — card 46's Peak/Neutral-Peak — reuse the SAME
    # rolled-series machinery over the card's own table). NEVER mixed into the member pairs: the 'load'/'supply'/'all'
    # selections are untouched (a panel aggregate must not double-count its own intake through a self row).
    self_pair = None
    if ctx.get("asset_table"):
        reg = _members._meter_row(ctx.get("mfm_id"))
        self_member = {"mfm_id": ctx.get("mfm_id"), "name": ctx.get("asset_name"), "table": ctx.get("asset_table"),
                       "role": "self", "type": reg.get("type_code"), "load_group": reg.get("load_group")}
        got = _members.rows([self_member], columns, ts_col=ts)
        self_pair = got[0] if got else None
    if "_agg_row" not in ctx:
        row = _members.agg_row(pairs, window, member_cols or columns, sum_cols,
                               energy_col=energy_col, pf_cols=policy.pf_cols,
                               power_col=policy.power_col)
        # inject the fleet roll-up ONLY when it actually rolled something up: a LEAF meter's roster (its one 'member'
        # is the incoming panel → empty load side) rolls all-None, and injecting THAT would blank every raw read of the
        # meter's own live row (present_cols collapses to the agg keys). No real rolled value → single-meter path stays.
        if any(v is not None for v in row.values()):
            ctx["_agg_row"] = row
    ctx["_roster_state"] = {
        "roster": roster,
        # the AI's emitted DATA fields (di.fields[]) — carried so the post-fill series-label alignment
        # (_align_series_labels) can rename a per-series LABEL leaf to the metric its OWN values leaf was actually bound
        # to on a SWAP (card 73/53: real power/frequency values plotted under stale swap-target autonomy labels).
        "emitted_fields": [f for f in ((data_instructions or {}).get("fields") or []) if isinstance(f, dict)],
        "pairs": pairs,
        "self_pair": self_pair,
        "coverage": coverage,
        "coverage_attach": _recipe.coverage_attach(ctx.get("card_id")),
        "policy": policy,
        "window": window,
        "window_explicit": bool(ctx.get("window_explicit")),   # user date-pick overrides recipe slot ranges [_slot_window]
        "sampling": ctx.get("sampling"),                       # date-control resample → series bucketing granularity [x-axis]
        "ts_col": ts,
        "energy_col": energy_col,
        "agg_row": ctx.get("_agg_row") or {},
        "asset_name": ctx.get("asset_name"),
        "panel_slugs": frozenset(s for s in (_bindings.slugify(ctx.get("asset_name")),
                                             _bindings.slugify(ctx.get("asset_table"))) if s),
        "_context_vals": None,                                  # lazy {panel_kwh, panel_kw, panel_name}
    }


# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
#  run_roster — interpret every slot instruction against the prepared member state (per-slot honest-degrade)
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
def run_roster(payload, roster, ctx, default_payload=None):
    """Fill the member-scope slots of an already-executor-completed payload. `roster` (the raw emission) is only used
    to (re)prepare when the caller skipped prepare_ctx; the NORMALIZED instructions come from ctx['_roster_state'].
    Returns the payload (mutated in place — fill() hands us its own deep copy). Never raises.

    A BLANK const roster slot ('honest-empty' [] / null / '—') no longer clobbers a leaf a real neuract DATA field
    already FILLED (the const branch's value-based guard): on card 73 the AI both bound the 4 real power/frequency trend
    columns to backupHistory.series[i].values AND emitted a const-[] roster for those same slots ('autonomy scores not
    derivable' — a FALSE reason, the electrical trends ARE measurable). The field write wins; the const-blank still lands
    on genuinely-empty leaves. Signature unchanged — every existing caller/mock stays byte-compatible."""
    if not isinstance(payload, dict):
        return payload
    if not isinstance(ctx, dict):
        return payload
    if ctx.get("_roster_state") is None:
        prepare_ctx({"roster": roster} if roster else None, ctx)
    state = ctx.get("_roster_state")
    if state is None:
        return payload
    for spec in state.get("roster") or []:
        try:
            _run_slot(payload, spec, state, default_payload)
        except Exception:
            continue                                            # one broken slot never takes down the card
    try:
        _align_series_labels(payload, state, default_payload)   # rename a per-series LABEL to the metric its values bound
    except Exception:
        pass
    try:
        from ems_exec.executor.roster_pres_sections import apply_section_pres
        apply_section_pres(payload, state.get("roster"))        # section-split keys get their pres entries [sections]
    except Exception:
        pass
    try:
        _attach_coverage(payload, state)
    except Exception:
        pass
    try:
        from ems_exec.executor import roster_stats as _stats
        _stats.attach(payload, state)                           # honest leaf telemetry for the host verdict [never gates]
    except Exception:
        pass
    return payload


def _const_is_blank(v):
    """A const roster VALUE that carries no real data: None / '—' / '' scalars, and an empty or ALL-None list (the
    'honest-empty' []). A non-blank const (a real literal, a populated list) still overwrites unconditionally."""
    return _blank.is_blank(v, all_none_list=True)   # [shared predicate: executor.blank]


def _leaf_is_real(container, key):
    """True when the leaf currently at container[key] already holds REAL data (a non-blank scalar, or a non-empty list
    with at least one non-None element). Used to protect a field-filled trend from a BLANK const overwrite."""
    try:
        v = container[key]
    except (KeyError, IndexError, TypeError):
        return False
    if isinstance(v, list):
        return bool(v) and any(x is not None for x in v)
    return v is not None and v != "—" and v != ""


# ── the slot-mode dispatch table: DISCOVERED from the roster_modes_* siblings (self-registration) ───────────────────
def _discover_modes():
    """{mode: handler} merged from every ems_exec.executor.roster_modes_* module's MODES declaration. A NEW mode = a
    new roster_modes_<x>.py declaring MODES = {"<mode>": handler} — no dispatch edit here. Deterministic (sorted module
    order, first claim of a mode wins); a module that fails to import is skipped (one broken mode must never take down
    the interpreter — the shipped modules are still hard-imported above, so a defect in THOSE fails loudly as before)."""
    import importlib
    import pkgutil
    import ems_exec.executor as _pkg
    modes = {}
    for name in sorted(m.name for m in pkgutil.iter_modules(_pkg.__path__) if m.name.startswith("roster_modes_")):
        try:
            mod = importlib.import_module(f"ems_exec.executor.{name}")
        except Exception:
            continue
        for k, fn in (getattr(mod, "MODES", None) or {}).items():
            if callable(fn):
                modes.setdefault(str(k).strip().lower(), fn)
    return modes


_MODES = _discover_modes()


def _run_slot(payload, spec, state, default_payload):
    """Dispatch ONE slot instruction on the MODE vocabulary — the discovered _MODES table above; `const` stays inline
    (its measurable-leaf protect reads this module's own helpers). Unknown mode → honest no-op."""
    mode = (spec.get("mode") or "").strip().lower()
    handler = _MODES.get(mode)
    if handler is not None:
        handler(payload, spec, state, default_payload)
    elif mode == "const":
        # MEASURABLE-LEAF PROTECT [card 73 false-blank, Family C]: a BLANK const ('honest-empty' [] / null) must not
        # clobber a leaf a real neuract DATA field already FILLED — the AI relabeled the 4 real power/frequency trend
        # series as underivable 'autonomy scores' AND const-[]'d their slots, wiping the measured trend. The field write
        # wins; the const-blank still lands on genuinely-empty leaves and every non-blank const overwrites as before. The
        # guard is VALUE-based (the leaf currently holds real non-blank data): a const-BLANK overwriting a real value IS
        # the false-blank pattern we forbid, so no separate written-paths cross-check is needed. Over-reach-safe — a
        # non-blank const (a real literal / a populated list) still overwrites unconditionally.
        blank = _const_is_blank(spec.get("v"))
        for container, key, _marker in _targets(payload, default_payload, spec.get("slot")):
            if blank and _leaf_is_real(container, key):
                continue                                        # real filled trend survives the honest-empty const
            container[key] = copy.deepcopy(spec.get("v"))
    # unknown mode → honest no-op (closed vocabulary)


# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
#  series-LABEL alignment — a per-series LABEL must name the METRIC its OWN values leaf was actually bound to
# SERIES-LABEL ALIGNMENT home = executor/roster_labels.py (monoliths F8, 2026-07-12); re-exported byte-compatibly.
from ems_exec.executor.roster_labels import (                                              # noqa: F401
    _SERIES_VALUE_LEAF_DEFAULT, _SERIES_LABEL_LEAF_DEFAULT, _LABEL_MATCH_STOP,
    _series_value_leaves, _series_label_leaves, _label_tokens, _leaf_slot_swap,
    _humanize_metric, _align_series_labels)

# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
#  coverage — the honest partial-fleet badge, attached where the recipe says
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
def _attach_coverage(payload, state):
    path = state.get("coverage_attach")
    if not path:
        return
    for container, key, _marker in _targets(payload, None, path):
        container[key] = dict(state.get("coverage") or {})
