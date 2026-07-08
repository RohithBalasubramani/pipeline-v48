"""ems_exec/executor/roster.py — THE GENERIC ROSTER INTERPRETER (generalization package §3). ONE capability, ZERO card
knowledge: given a validated roster instruction list (the AI emission folded into the card_fill_recipe row — see
recipe.py), it resolves the panel's members ONCE (registries.neuract edges, roles preserved), reads each member's
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
    if isinstance(v, list):
        return not v or all(x is None for x in v)
    return v is None or v == "—" or v == ""


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


def _run_slot(payload, spec, state, default_payload):
    """Dispatch ONE slot instruction on the closed MODE vocabulary — the only branch in this file."""
    mode = (spec.get("mode") or "").strip().lower()
    if mode == "elements":
        _elements_slot(payload, spec, state, default_payload)
    elif mode == "groups":
        _groups_slot(payload, spec, state, default_payload)
    elif mode == "aggregates":
        _aggregates_slot(payload, spec, state, default_payload)
    elif mode == "sections":
        _sections_slot(payload, spec, state, default_payload)
    elif mode == "sankey_match":
        _sankey_slot(payload, spec, state, default_payload)
    elif mode == "series":
        _series_slot(payload, spec, state, default_payload)
    elif mode == "series_split":
        _series_split_slot(payload, spec, state, default_payload)
    elif mode == "scalar":
        _scalar_slot(payload, spec, state, default_payload)
    elif mode == "entries":
        _entries_slot(payload, spec, state, default_payload)
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
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# SWAP LABEL-MORPH GAP [DEFECT c73/c53]: a swapped-in card renders its swap-TARGET's payload shape (card 53
# backupHistory.series[i]) but the slot's story bound a DIFFERENT metric family (a DG power/frequency trend). Layer 2's
# DATA fields correctly bind each `series[i].values` to a real column WITH a declared label ('Active Power (kW)', …),
# and the real (all-zero-but-honest) power series fills — yet the sibling `series[i].label` kept the swap-target SEED
# ('Autonomy index' / 'Backup time score' / 'Load Pressure score') the recipe never morphed. Real data plotted under a
# label that names a quantity this meter does not even measure = a misleading leaf (the card's own data_note declares
# those score series omitted). The FIX: after the roster fills, align each per-series LABEL to the metric its OWN values
# leaf was bound to (the emitted field's declared label / humanized metric) — ONLY when the seed label does NOT already
# name that metric (over-reach-safe: a label that already matches, or a series with no real fill and no bound field, is
# untouched). Generic — no card ids, no key literals; driven off the emitted fields + the payload's own shape.

# the leaf token a per-series VALUE array carries, and the sibling LABEL leaf token — DB-driven, code-default. A field
# whose slot ends in a value token has a sibling label at the same series element under the label token.
_SERIES_VALUE_LEAF_DEFAULT = ["values", "value", "data", "points", "series_data"]
_SERIES_LABEL_LEAF_DEFAULT = ["label", "name", "legendLabel", "seriesLabel", "title"]
# tokens dropped when comparing a label to a metric quantity (units / stats / filler) — a label that already NAMES the
# bound metric's quantity is left alone; only a STALE label naming a different quantity is renamed.
_LABEL_MATCH_STOP = {"the", "of", "and", "per", "avg", "average", "mean", "max", "min", "peak", "total", "kw", "kwh",
                     "kva", "kvar", "kvarh", "kvah", "hz", "pct", "percent", "score", "index", "a", "v"}


def _series_value_leaves():
    v = _cfg("roster.series_value_leaf_tokens", _SERIES_VALUE_LEAF_DEFAULT)
    return [str(t).lower() for t in v] if isinstance(v, (list, tuple)) and v else _SERIES_VALUE_LEAF_DEFAULT


def _series_label_leaves():
    v = _cfg("roster.series_label_leaf_tokens", _SERIES_LABEL_LEAF_DEFAULT)
    return [str(t).lower() for t in v] if isinstance(v, (list, tuple)) and v else _SERIES_LABEL_LEAF_DEFAULT


def _label_tokens(text):
    """Lowercase content tokens of a label / metric (camelCase + snake_case split, units/stats/filler dropped)."""
    if not text:
        return set()
    import re
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", str(text)).replace("_", " ").replace("-", " ")
    return {t for t in re.split(r"[^a-z0-9]+", s.lower()) if t and t not in _LABEL_MATCH_STOP and not t.isdigit()}


def _leaf_slot_swap(slot, want_value_leaves, new_leaf):
    """Given a field slot whose LAST path segment is one of `want_value_leaves` AND whose value leaf is the child of an
    ARRAY ELEMENT (a per-series element: '…series[0].values' / '…points[*].values' — an indexed or [*] segment
    immediately precedes the leaf), return the sibling slot with that last segment replaced by `new_leaf`
    ('…series[0].label'), else None. The array-element requirement is the OVER-REACH GUARD: a bare scalar
    '<tile>.value' (no array index parent) is NOT a per-series value and is never touched — only a genuine SERIES
    element's label is aligned. Preserves every earlier segment/index verbatim (surgery on the final '.<leaf>' only)."""
    import re
    s = str(slot or "")
    m = re.search(r"\.([A-Za-z_][A-Za-z0-9_]*)$", s)
    if not m or m.group(1).lower() not in want_value_leaves:
        return None
    parent = s[:m.start()]                                       # the value leaf's parent path
    # parent must END in a SPECIFIC INDEXED array element ('…[<int>]') — a per-series element addressed 1:1 by the
    # field. A bare scalar ('<tile>.value', no array parent) is skipped, AND a wildcard '…[*].values' is skipped too:
    # a [*] field would smear ONE label onto EVERY series element (the c53 fix binds each series by its own INDEX, so
    # the per-index path is the only one that carries a distinct metric identity). Over-reach guard.
    if not re.search(r"\[-?\d+\]$", parent):
        return None
    return parent + "." + new_leaf


def _humanize_metric(metric):
    """A readable label for a raw metric/column name when the field declared no label ('active_power_total_kw' →
    'Active Power Total Kw'). Title-cased content of the split tokens; empty → None."""
    import re
    if not metric:
        return None
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", str(metric)).replace("_", " ").replace("-", " ")
    words = [w for w in re.split(r"\s+", s.strip()) if w]
    return " ".join(w.capitalize() for w in words) or None


def _align_series_labels(payload, state, default_payload):
    """For each emitted DATA field that binds a per-SERIES value leaf ('…series[i].values') which actually FILLED with
    real data, rename the sibling '…series[i].label' to the field's declared label (or humanized metric) — but ONLY
    when the current label is a STALE seed that does NOT already name the bound metric's quantity. Fixes the c73/c53
    swap label-morph gap (real power/frequency series plotted under stale 'Autonomy index' seeds). Over-reach-safe: a
    series with no real fill, or a label already naming the bound quantity, or a field with no usable label, is left
    untouched; never fabricates a label for a genuinely-blank series. Never raises (each field independent)."""
    if not isinstance(payload, dict):
        return
    fields = state.get("emitted_fields") or []
    if not fields:
        return
    value_leaves = _series_value_leaves()
    label_leaf = (_series_label_leaves() or ["label"])[0]
    for f in fields:
        if not isinstance(f, dict):
            continue
        slot = f.get("slot")
        # the metric identity this field bound — its declared label wins, else a humanized metric/column.
        want_label = (f.get("label") or "").strip() or _humanize_metric(f.get("metric") or f.get("column"))
        if not want_label:
            continue
        label_slot = _leaf_slot_swap(slot, value_leaves, label_leaf)
        if not label_slot:
            continue
        # only rename when the field's OWN value leaf actually holds real data (an honest-blank series is not relabeled)
        vals = values_at(payload, slot)
        real = any((isinstance(v, list) and any(x is not None for x in v)) or
                   (not isinstance(v, list) and v not in (None, "", "—")) for v in vals)
        if not real:
            continue
        want_toks = _label_tokens(want_label)
        for container, key, _marker in _targets(payload, default_payload, label_slot):
            cur = container.get(key)
            # untouched when: no current label (nothing to correct) OR it already names the bound metric's quantity.
            if not isinstance(cur, str) or not cur.strip():
                continue
            cur_toks = _label_tokens(cur)
            if want_toks and cur_toks and want_toks.issubset(cur_toks):
                continue                                        # the label already names this quantity — leave it
            container[key] = want_label                          # align the label to the metric its values bound


# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
#  coverage — the honest partial-fleet badge, attached where the recipe says
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
def _attach_coverage(payload, state):
    path = state.get("coverage_attach")
    if not path:
        return
    for container, key, _marker in _targets(payload, None, path):
        container[key] = dict(state.get("coverage") or {})
