"""ems_exec/executor/roster_eval.py — the SHARED slot-evaluation helpers every roster mode uses: member selection
(incl. the 'self' roster of one), the slot's own evaluation window (recipe `range` is AUTHORITATIVE), element
evaluation over the prepared pairs, order/cap, the lazy run-level context values and the roster's shared element spec.
roster.py re-exports byte-compatibly. [atomic]
"""
from __future__ import annotations

from ems_exec.executor import bindings as _bindings
from ems_exec.executor import members as _members
from ems_exec.executor.window_policy import _honor_range


from config.failopen import cfg_safe as _cfg   # THE guarded cfg reader (D3)


def _select(spec, state, role_filter=None, reporting_only=None):
    rf = role_filter if role_filter is not None else spec.get("role_filter") or "all"
    ro = reporting_only if reporting_only is not None else bool(spec.get("reporting_only"))
    if str(rf).strip().lower() == "self":
        # the run's OWN meter as a roster of one (recipe-declared; single-meter windowed stats). Honest []: no table.
        return [state["self_pair"]] if state.get("self_pair") else []
    return _members.select(state["pairs"], role_filter=rf, reporting_only=ro,
                           power_col=state["policy"].power_col)


def _series_pairs(spec, state):
    """The (member,row) subset a series/stat roll reads: the 'self' roster of one when the slot declares it, else the
    role-filtered members WITHOUT the reporting gate (a rolled series reads history — a member idle at this instant
    still contributed real buckets; matches the legacy bucketed_rolled selection, and needs no policy in state)."""
    rf = str(spec.get("role_filter") or "load").strip().lower()
    if rf == "self":
        return [state["self_pair"]] if state.get("self_pair") else []
    return _members.select(state["pairs"], role_filter=rf)


def _slot_window(spec, state):
    """The slot's evaluation window: the run window, unless the recipe slot declares its OWN `range` — then the range
    is AUTHORITATIVE (anchored at the run window's end) so a KPI whose chrome claims a period ('Monthly' cumulative
    energy, card 14) reads exactly that period, never whatever window the host happened to pass. DB-declared per slot;
    no range → the shared window untouched."""
    rng = spec.get("range")
    if not rng:
        return state["window"]
    # EXPLICIT USER PICK WINS [date control]: a recipe slot's `range` (a KPI's 'today' reporting pin) is a DEFAULT — a
    # date-control /api/frame re-fetch marks the window explicit, and the user's pick then moves EVERY card, this KPI
    # included (the strip stayed on 'today' when the user chose 'last month' otherwise). No-op on the initial serve.
    if state.get("window_explicit") and state.get("window"):
        return state["window"]
    w = state["window"] or (None, None)
    return _honor_range(w[0], w[1], rng, authoritative=True)


def _eval_elements(element_spec, pairs, state, window=None):
    """[(member, element)] — one evaluated element per (member, row) pair (per-leaf honest-null). `window` overrides
    the shared run window (a recipe slot's own declared range — _slot_window)."""
    w = window if window is not None else state["window"]
    return [(m, _bindings.element(element_spec, m, r, w, state["policy"], ts_col=state["ts_col"]))
            for m, r in pairs]


def _order_cap(mels, spec):
    order = (spec.get("order") or "member").strip()
    if order.startswith("by:"):
        key = order[3:]
        desc = key.startswith("-")
        key = key.lstrip("-")
        from ems_exec.renderers._agg import num
        mels = sorted(mels, key=lambda me: (num(me[1].get(key)) is None,
                                            -(num(me[1].get(key)) or 0) if desc else (num(me[1].get(key)) or 0)))
    cap = spec.get("cap")
    if isinstance(cap, int) and cap >= 0:
        mels = mels[:cap]
    return mels


def _context_vals(state):
    """Lazy run-level values reducers/sankey may name: the panel's windowed energy Σ + rolled power + its own name
    (the run's real asset identity — honest-null when the caller resolved no asset, never a fabricated label)."""
    if state.get("_context_vals") is None:
        state["_context_vals"] = {
            "panel_kwh": _members.panel_kwh(state["pairs"], state["window"], state["energy_col"]),
            "panel_kw": (state.get("agg_row") or {}).get(state["policy"].power_col),
            "panel_name": state.get("asset_name"),
        }
    return state["_context_vals"]


def _shared_element(state):
    """The roster's shared element spec — the first slot that declares one (the seed rows' aggregates slots reuse the
    element of the sibling elements-mode slot, e.g. the SLD node shape for the bus/header roll-ups)."""
    for s in state.get("roster") or []:
        el = s.get("element")
        if isinstance(el, dict) and el:
            return el
    return {}
