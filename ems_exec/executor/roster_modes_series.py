"""ems_exec/executor/roster_modes_series.py — the SERIES-family roster modes: `series` (the member-rolled bucketed
array + Peak-from-series stats + per-bucket point elements), the multi-KEY `columns` trend shape (+ its legend/totals/
insight sibling scalars) and `series_split` (multiple keyed series per bucket, member-matched per feeder group). All
vocabulary arrives in the recipe rows — zero card knowledge. roster.py dispatches + re-exports byte-compatibly.
[atomic]
"""
from __future__ import annotations

import copy

from ems_exec.executor import bindings as _bindings
from ems_exec.executor import members as _members
from ems_exec.executor.roster_paths import _targets
from ems_exec.executor.roster_template import _default_list_at, _merge_template, _merge_templates
from ems_exec.executor.roster_eval import _select, _series_pairs, _slot_window


def _series_slot(payload, spec, state, default_payload):
    """The member-rolled BUCKETED value array at the slot — the per-bucket fold (`reduce`: sum_magnitude | mean, the
    same quantity rule as the aggregate row) of ONE recipe-declared `column` across the selected members' OWN bucketed
    reads. Wholesale replace of the array leaf. Honest-degrade: [] when no member reports the column — the FE still
    .map()s an empty list, never a fabricated curve. `points: true` keeps per-bucket ELEMENTS instead of the bare
    value array, template-cloned onto the DEFAULT's element chrome (the FeederDemandPoint class of contracts) with the
    recipe-declared key mapping:
        t_key      the element key the REAL bucket timestamp lands in (default 't')
        t_fmt      optional display format ('DD HH:MM' — the shared _FMT token table; raw ISO when absent)
        value_key  the element key the fold value lands in (default 'value'; an EXPLICIT null → the fold is written
                   NOWHERE — the default's own per-series keys stay typed placeholders when no member grounds them,
                   never the panel Σ misattributed to a fixture series).
        stats      [{op:'maximum'|'mean'|'minimum', r, slot, at_slot?, at_prefix?, at_fmt?, column?, reduce?}] — DERIVED
                   SCALARS over a rolled series (the Peak-from-series contract: a peak is max of the panel's OWN rolled
                   trend, NOT a per-member latest-row column read). Default source = THIS slot's series; a stat may name
                   its OWN `column`(+`reduce`) to roll an independent quantity (e.g. the mean of the rolled PF series on
                   the SAME member roster). Each writes its scalar to `slot` (any leaf, incl. an array-index leaf like
                   trend.bottomStats[0].value); `at_slot` (min/max only) receives that peak bucket's REAL timestamp
                   ('{at_prefix}{ts}' per at_fmt). Honest-null: an empty rolled series → None at every stat slot."""
    if isinstance(spec.get("columns"), list) and spec.get("columns"):
        _series_multi_slot(payload, spec, state, default_payload)   # multi-KEY per-bucket points (energy trend)
        return
    win = _slot_window(spec, state)
    series = _members.bucketed_rolled_members(_series_pairs(spec, state),
                                              spec.get("column"), win,
                                              sampling=spec.get("sampling") or "hourly",
                                              reduce=spec.get("reduce") or "sum_magnitude")
    for st in (spec.get("stats") or []):                            # derived scalars over a rolled series
        if isinstance(st, dict):
            _series_stat(payload, st, series, state, spec, default_payload, window=win)
    if spec.get("stats_only"):
        return                                                  # a stats-carrier slot: derive the scalars, write NO array
    if spec.get("points"):
        t_key = spec.get("t_key") or "t"
        v_key = spec["value_key"] if "value_key" in spec else "value"
        els = []
        for pt in series:
            el = {t_key: _bindings.format_ts(pt.get("t"), spec.get("t_fmt"))}
            if v_key:
                el[v_key] = pt.get("value")
            els.append(el)
        out = _merge_templates(els, _default_list_at(default_payload, spec.get("slot")))
    else:
        out = [pt.get("value") for pt in series]
    targets = _targets(payload, default_payload, spec.get("slot"))
    for n, (container, key, _marker) in enumerate(targets):
        container[key] = copy.deepcopy(out) if len(targets) > 1 or n > 0 else out


def _series_stat(payload, st, series, state, spec, default_payload, window=None):
    """ONE derived scalar over a ROLLED series ([{t, value}]) written to a leaf slot — the Peak-from-series contract
    (a peak = max of the panel's OWN rolled trend, never a per-member column read). Source = the slot's own series by
    default, or an independently-rolled `column`(+`reduce`) over the SAME member roster (incl. the 'self' roster of
    one). Closed op set (maximum|mean|minimum) delegates to the same honest-null _agg math; an empty/all-null series →
    None at every stat slot (honest-blank, never a fabricated 0). `at_slot` (min/max only) receives the peak bucket's
    REAL timestamp."""
    from ems_exec.renderers import _agg
    op = str(st.get("op") or "maximum").strip().lower()
    slot = st.get("slot")
    if not slot:
        return
    if st.get("column"):                                            # a stat over its OWN independently-rolled column
        series = _members.bucketed_rolled_members(
            _series_pairs(spec, state),
            st.get("column"), window if window is not None else state["window"],
            sampling=spec.get("sampling") or "hourly",
            reduce=st.get("reduce") or "mean")
    vals = [pt.get("value") for pt in (series or [])]
    r = st.get("r", 2)
    val = {"mean": _agg.mean, "minimum": _agg.minimum}.get(op, _agg.maximum)(vals, ndigits=r)
    for container, key, _marker in _targets(payload, default_payload, slot):
        container[key] = val
    at_slot = st.get("at_slot")
    if at_slot and op in ("maximum", "minimum"):
        real = [pt for pt in (series or []) if _agg.num(pt.get("value")) is not None]
        pick = (max if op == "maximum" else min)(real, key=lambda p: _agg.num(p.get("value"))) if real else None
        ts = _bindings.format_ts(pick.get("t"), st.get("at_fmt")) if pick else None
        text = (str(st.get("at_prefix") or "") + ts) if ts is not None else None
        for container, key, _marker in _targets(payload, default_payload, at_slot):
            container[key] = text


def _series_multi_slot(payload, spec, state, default_payload):
    """MULTI-KEY per-bucket points (the energy-TREND shape): every point carries SEVERAL real quantities on ONE shared
    real bucket axis. Vocabulary (all recipe-declared, zero card knowledge):
        columns   [{key, column, kind:'energy_delta'|'avg', reduce, r, match?}] — each a member-rolled per-bucket
                  quantity (members.bucketed_multi); `match` scopes a key to a feeder sub-group (a per-equipment split).
        label_key / label_fmt   the point key + format for the REAL bucket timestamp ('MMM DD' → 'Jun 27').
        derived   {out_key: {op:'sum', of:[keys]} | {op:'const', v:...}} — per-point keys computed from the SAME point's
                  already-rolled column values (total = active+reactive) or an honest const (rated/contracted have no
                  gic_* column → const null). A sum over an all-null point → null (honest, never a fabricated 0).
        role_filter / sampling   the member scope + bucket granularity.
    Every point is template-cloned onto the DEFAULT point chrome so unbound keys keep their typed placeholders. Honest
    per-leaf null throughout: a bucket a key never reported → null for THAT key only. [] points when no member reports."""
    rolled = _members.bucketed_multi(state["pairs"], spec.get("columns"), _slot_window(spec, state),
                                     sampling=spec.get("sampling") or "day",
                                     role_filter=spec.get("role_filter") or "load")
    label_key = spec.get("label_key") or "label"
    label_fmt = spec.get("label_fmt")
    derived = spec.get("derived") if isinstance(spec.get("derived"), dict) else {}
    els, labels, totals_by_label, key_totals = [], [], [], {}
    for pt in rolled:
        vals = pt.get("vals") or {}
        label = _bindings.format_ts(pt.get("t"), label_fmt)
        el = {label_key: label}
        for k, v in vals.items():
            el[k] = v
        for out_key, d in derived.items():                      # per-point derived keys over this point's own rolls
            el[out_key] = _derive_point(d, vals)
        els.append(el)
        labels.append(label)
        totals_by_label.append((label, el.get(spec.get("total_key") or "total")))
        from ems_exec.renderers._agg import num as _num
        for k, v in vals.items():                               # accumulate window totals per column key (Σ over buckets)
            nv = _num(v)
            if nv is not None:
                key_totals[k] = (key_totals.get(k) or 0.0) + nv
    out = _merge_templates(els, _default_list_at(default_payload, spec.get("slot")))
    for n, (container, key, _marker) in enumerate(_targets(payload, default_payload, spec.get("slot"))):
        container[key] = copy.deepcopy(out) if n > 0 else out
    emit = spec.get("emit") if isinstance(spec.get("emit"), dict) else {}
    if emit:
        _emit_trend_scalars(payload, emit, key_totals, totals_by_label, labels, default_payload)


def _fmt_num(v, ndigits=0):
    """A grouped number STRING ('1,212') for a scalar-string leaf, or None (honest — the FE display-dashes a null)."""
    from ems_exec.renderers._agg import num as _num
    n = _num(v)
    if n is None:
        return None
    return f"{round(n, ndigits):,.{ndigits}f}" if ndigits else f"{round(n):,}"


def _emit_trend_scalars(payload, emit, key_totals, totals_by_label, labels, default_payload):
    """Fill the trend card's sibling SCALAR leaves from the SAME rolled points (one coherent aggregate — the legend /
    totalLegend / totals / insight / selectedLabel all reconcile with the bars). Vocabulary (recipe-declared):
        legend   {slot, key_field, value_field, ndigits} — each entry's value ← that key's window-Σ (matched by key_field);
                 a key with no real bucket → null (honest; an idle UPS legend shows its real 0, a missing HHF shows null).
        totals   {slot, label_field, value_field, ndigits} — the per-bucket total list, one entry per real bucket.
        insight  {slot, ndigits, unit} — '<Σtotal> <unit> over <n> buckets — peak <label> at <peak>.' (real numbers only;
                 blank string when there is no real bucket, never a fabricated sentence).
        selectedLabel {slot} — the LAST real bucket label (the default-selected point)."""
    from ems_exec.renderers._agg import num as _num
    # ── legend: per-key window totals ────────────────────────────────────────────────────────────────────────────────
    for legspec_key in ("legend", "total_legend"):
        leg = emit.get(legspec_key)
        if not isinstance(leg, dict) or not leg.get("slot"):
            continue
        kf, vf, nd = leg.get("key_field") or "id", leg.get("value_field") or "value", leg.get("ndigits", 0)
        keymap = leg.get("key_map") or {}
        for container, key, _m in _targets(payload, default_payload, leg["slot"]):
            lst = container.get(key)
            if not isinstance(lst, list):
                continue
            for entry in lst:
                if not isinstance(entry, dict):
                    continue
                src = keymap.get(entry.get(kf), entry.get(kf))
                entry[vf] = _fmt_num(key_totals.get(src), nd) if src in key_totals else None
    # ── totals: per-bucket total list ────────────────────────────────────────────────────────────────────────────────
    tot = emit.get("totals")
    if isinstance(tot, dict) and tot.get("slot"):
        lf, vf, nd = tot.get("label_field") or "label", tot.get("value_field") or "value", tot.get("ndigits", 0)
        dlist = _default_list_at(default_payload, tot["slot"])
        rows = []
        for i, (label, val) in enumerate(totals_by_label):
            e = {lf: label, vf: _fmt_num(val, nd)}
            rows.append(_merge_template(e, dlist, i))
        for container, key, _m in _targets(payload, default_payload, tot["slot"]):
            container[key] = copy.deepcopy(rows) if rows else []
    # ── insight: the real one-line summary (blank when no real bucket) ────────────────────────────────────────────────
    ins = emit.get("insight")
    if isinstance(ins, dict) and ins.get("slot"):
        reals = [(lab, _num(v)) for lab, v in totals_by_label if _num(v) is not None]
        text = ""
        if reals:
            grand = sum(v for _l, v in reals)
            peak_lab, peak_v = max(reals, key=lambda lv: lv[1])
            unit = ins.get("unit") or "kWh"
            text = (f"{_fmt_num(grand, ins.get('ndigits', 0))} {unit} over {len(reals)} buckets"
                    f" — peak {peak_lab} at {_fmt_num(peak_v, ins.get('ndigits', 0))} {unit}.")
        for container, key, _m in _targets(payload, default_payload, ins["slot"]):
            container[key] = text
    # ── selectedLabel: the last real bucket ──────────────────────────────────────────────────────────────────────────
    sel = emit.get("selected_label")
    if isinstance(sel, dict) and sel.get("slot"):
        v = labels[-1] if labels else None
        for container, key, _m in _targets(payload, default_payload, sel["slot"]):
            container[key] = v


def _derive_point(d, vals):
    """ONE per-point derived value from a point's already-rolled column values. op='sum' → Σ of the named keys' reals
    (all-null → null, honest, never 0); op='const' → the literal (an honest null for a no-column reference line).
    Unknown op → null (closed vocabulary)."""
    if not isinstance(d, dict):
        return None
    op = (d.get("op") or "").strip().lower()
    if op == "const":
        return d.get("v")
    if op == "sum":
        from ems_exec.renderers._agg import num as _num
        reals = [x for x in (_num(vals.get(k)) for k in (d.get("of") or [])) if x is not None]
        if not reals:
            return None
        s = sum(reals)
        return round(s, d["r"]) if d.get("r") is not None else s
    return None


def _member_match(member, match):
    """True when a member falls in a series-split group per the recipe `match` vocabulary (all case-insensitive, any-of):
    types (type_code), load_groups (load_group), name_contains (substring on name OR table — the only reliable feeder
    discriminator when registry names are gic_* / load_groups are the GIC-xx site, not the feeder class). No match keys →
    matches nothing (a series with no selector selects no member → honest-null series, never the whole panel)."""
    if not isinstance(match, dict):
        return False
    mtype = str(member.get("type") or "").strip().lower()
    lg = str(member.get("load_group") or "").strip().lower()
    hay = (str(member.get("name") or "") + " " + str(member.get("table") or "")).strip().lower()
    if mtype and mtype in {str(x).strip().lower() for x in (match.get("types") or [])}:
        return True
    if lg and lg in {str(x).strip().lower() for x in (match.get("load_groups") or [])}:
        return True
    # BUS-SECTION match [sections overlay]: `sections: ["1A"]` selects members by their equipment.mfm section token
    # (data/equipment/sections) — the dimension a section-compare prompt splits series/elements by. AI-drivable: the
    # L2 roster emission names the sections; this stays a dictionary lookup, zero card knowledge.
    secs = {str(x).strip().upper() for x in (match.get("sections") or [])}
    if secs:
        try:
            from data.equipment.sections import section_of
            if str(section_of(member.get("table")) or "").upper() in secs:
                return True
        except Exception:
            pass
    if any(sub and str(sub).strip().lower() in hay for sub in (match.get("name_contains") or [])):
        return True
    return False


def _series_split_slot(payload, spec, state, default_payload):
    """MULTI-SERIES per-bucket points: each declared series (`series:[{key, match}]`) folds ONLY the members its
    `match` selects (a feeder group — ups / bpdp / …), each series aligned on the UNION of real bucket timestamps into
    one per-bucket point element ({t_key: label, <series key>: fold}) template-cloned onto the default point chrome.
    A series whose match selects NO member (HHF — no such feeder on this panel) writes the recipe's honest `null_value`
    (default null) into every point — never the panel Σ misattributed to a fixture series. The bucket LABEL comes from
    the real timestamps; a bucket a given series never reported → null for that series (per-leaf honest-null).
    Optional `legend`: {slot, key_field, value_field, ndigits} refreshes each legend entry's scalar from its own series'
    LAST real bucket (honest-null when the series is dark), matched by the legend entry's own key_field."""
    scope_pairs = _select(spec, state, role_filter=spec.get("role_filter") or "load")
    column = spec.get("column")
    sampling = spec.get("sampling") or "hourly"
    reduce = spec.get("reduce") or "sum_magnitude"
    ndigits = spec.get("ndigits")
    t_key = spec.get("t_key") or "label"
    null_value = spec["null_value"] if "null_value" in spec else None
    series_defs = spec.get("series") or []

    per_series = {}                                             # key -> {t: value}
    order = []                                                  # union of real bucket timestamps
    seen_t = set()
    for sd in series_defs:
        key = sd.get("key")
        if key is None:
            continue
        subset = [(m, r) for (m, r) in scope_pairs if _member_match(m, sd.get("match"))]
        # per-series column override [sections overlay]: one split slot can carry ALL point-keys x sections
        # (sag_a/sag_b/current_a/... each naming its own column); falls back to the slot-level column.
        rolled = _members.bucketed_rolled_members(subset, sd.get("column") or column, state["window"],
                                                  sampling=sampling, reduce=reduce)
        by_t = {}
        for pt in rolled:
            t, v = pt.get("t"), pt.get("value")
            if ndigits is not None and isinstance(v, (int, float)):
                v = round(v, ndigits)
            by_t[t] = v
            if t not in seen_t:
                seen_t.add(t)
                order.append(t)
        per_series[key] = by_t
    order.sort()

    els = []
    for t in order:
        el = {t_key: _bindings.format_ts(t, spec.get("t_fmt"))}
        for sd in series_defs:
            key = sd.get("key")
            if key is None:
                continue
            v = per_series.get(key, {}).get(t, null_value)
            el[key] = v if v is not None else copy.deepcopy(null_value)
        els.append(el)
    out = _merge_templates(els, _default_list_at(default_payload, spec.get("slot")))
    targets = _targets(payload, default_payload, spec.get("slot"))
    for n, (container, key, _marker) in enumerate(targets):
        container[key] = copy.deepcopy(out) if len(targets) > 1 or n > 0 else out

    legend = spec.get("legend")
    if isinstance(legend, dict):
        _series_split_legend(payload, legend, per_series, order, series_defs, default_payload)


def _series_split_legend(payload, legend, per_series, order, series_defs, default_payload):
    """Refresh each legend entry's scalar from its OWN series' LAST real bucket value (honest-null when the series is
    dark). Entries are matched by the legend `key_field` (default 'id') against the series key; the value lands in
    `value_field` (default 'value') as the recipe declares. Untouched when the slot resolves no legend list."""
    key_field = legend.get("key_field") or "id"
    value_field = legend.get("value_field") or "value"
    nd = legend.get("ndigits")
    last = {}
    for sd in series_defs:
        key = sd.get("key")
        by_t = per_series.get(key, {})
        v = next((by_t[t] for t in reversed(order) if by_t.get(t) is not None), None)
        if v is not None and nd is not None and isinstance(v, (int, float)):
            v = round(v, nd)
            if nd == 0:
                v = int(v)                                       # '622' not '622.0' — the legend renders a whole-kW badge
        last[key] = v
    for container, key, _marker in _targets(payload, default_payload, legend.get("slot")):
        lst = container.get(key)
        if not isinstance(lst, list):
            continue
        for entry in lst:
            if isinstance(entry, dict) and entry.get(key_field) in last:
                v = last[entry.get(key_field)]
                entry[value_field] = str(v) if v is not None else None


# the slot MODES this module serves — roster.py's dispatch DISCOVERS this declaration from every roster_modes_* sibling
# (self-registration): a NEW mode = a new roster_modes_<x>.py declaring MODES, no dispatch edit.
MODES = {"series": _series_slot, "series_split": _series_split_slot}
