"""ems_exec/executor/fill.py — THE PER-CARD NEURACT EXECUTOR (simple, self-contained; Layer 3 archived, not reused).

fill(payload, data_instructions, ctx) -> completed_payload

THE SIMPLE ARCHITECTURE (no layer3, no leaf_classify, no seed-strip guessing):
  Layer 2's producer already emits exact_metadata with DATA leaves as typed placeholders (seed-free) + data_instructions
  that DECLARE every data slot. So the executor does ONE thing: fill each declared field onto its payload leaf from
  neuract, honestly. Whatever a field cannot fill honest-blanks. Leaves no field names are chrome/metadata — untouched.
    kind=raw     → the field's column value from neuract latest()/window() (denorm/sign VERIFIED).
    kind=derived → ems_exec.derivations.registry.run(fn, ctx) over a live-data superset ctx (row + window + nameplate).
    kind=const   → a per-asset NAMEPLATE slot resolves from the REAL nameplate; else the baked literal.
    kind=text    → the literal string.
    kind=event   → rising-edge count of a boolean flag column over the window (honest-degrade if absent).
    else / no real value → honest-blank ("—" / None, type-preserving: a scalar-None never nulls an array/dict leaf).
  Result = the completed CMD_V2 payload: real where neuract has it, None/'—' else. NEVER fabricated, NEVER the simulator.

PER-CARD by default — NO multi-meter fan-out here. The ONE aggregate seam: a panel_aggregate renderer that already fanned
the panel out to its members and rolled the electrical up may inject that fleet-rolled superset row via ctx['_agg_row'];
raw scalar fields then fill from THAT row (see the fill()/_field_value agg_row hook) so the aggregate renderer reuses this
executor verbatim for its KPI/scalar leaves. Member resolution + node-list assembly stay in the renderer, not here.
Self-contained: reads live values from ems_exec.data.neuract, derivations from ems_exec.derivations, and every
gate/rating/binding from a DB-driven config/* accessor with a code default. No ems_backend, no layer3, no daphne, no WS.

THIS FILE = the orchestrator FACADE: the per-field dispatch (_field_value) + the fill() pass order live here; every
other seam is an atomic sibling module (paths / verify / derived / series_fill / wildcards / indexed_families / gaps /
graft / window_policy), re-exported below byte-compatibly so every existing importer (host/server, roster, bindings,
view_select, fuel_anatomy, serve/run, tests) keeps working unchanged.
"""
from __future__ import annotations

import copy

from ems_exec.data import neuract as _nx
from ems_exec.derivations import registry as _registry
from config import nameplates as _np
from config import nameplate_slot_map as _slot_map
from config import derivation_binding as _deriv
from config import quality_policy as _qp
from config import neuract_dsn as _dsn

# ── the atomic executor seams, re-exported byte-compatibly (the facade contract) ──────────────────────────────────────
from ems_exec.executor.paths import (                                                        # noqa: F401
    _toks, _leaf_at, _set_path, _has_path, _set_leaf_typed, _leaf_path_for)
from ems_exec.executor.verify import _verify, _quantity_of, _polarity_conflict                # noqa: F401
from ems_exec.executor.derived import (                                                       # noqa: F401
    _INTEGRATION_POWER_COLS, _PERIOD_COUNTER_COLS, _site_calendar_start, _period_starts, _period_deltas,
    _derived_key, _run_derived)
from ems_exec.executor.series_fill import (                                                   # noqa: F401
    _event_count, _bucketed_values, _element_value_key, _element_time_key, _epoch_ms, _is_time_field,
    _anchor_timestamps)
from ems_exec.executor.wildcards import (                                                     # noqa: F401
    _wildcard_time_value, _split_wildcard, _fill_wildcard_arrays, _grow_one_wildcard_array)
from ems_exec.executor.indexed_families import (                                              # noqa: F401
    _IDXED, _split_indexed, _scalar_point_slot, _binding_for_field, _derived_bucket_values,
    _SAMPLING_LADDER, _sampling_ladder, _family_series, _fill_indexed_families)
from ems_exec.executor.gaps import (                                                          # noqa: F401
    GAPS_KEY, pop_gaps, _blank_val, _gap_of, _gap_sentence, _prune_stale_gaps, _attach_unbound_gaps, _note_gap)
from ems_exec.executor.graft import (                                                         # noqa: F401
    _graft_seedfree, _graft_container, _null_untouched_placeholders, _restore_array_containers)
from ems_exec.executor.window_policy import _range_start, _honor_range, _window_of            # noqa: F401


def _fields_of(data_instructions):
    di = data_instructions or {}
    return [f for f in (di.get("fields") or []) if isinstance(f, dict)]


def _windowed_register_delta(asset_table, col, window):
    """(rule_applies, value) — the windowed reversed-CT-aware delta for a CUMULATIVE ENERGY REGISTER column read
    inside a bounded window. rule_applies=False when `col` is not in the register_pairs family (either leg) or the
    valve is off — the caller keeps its plain latest-row read. An export-leg bind maps to its import twin so the
    pick_mover reads BOTH registers (a reversed-CT feeder keeps its real kWh on export). Never raises."""
    try:
        from config.app_config import cfg
        if str(cfg("fill.window_register_delta", "on")).strip().lower() == "off":
            return False, None
    except Exception:
        pass
    try:
        from ems_exec.executor import members as _members
        pairs = _members.register_pairs()
        if col in pairs:
            imp = col
        elif col in pairs.values():
            imp = next((i for i, e in pairs.items() if e == col), None)
        else:
            return False, None
        if not imp:
            return False, None
        return True, _members.member_delta({"table": asset_table}, window, imp, ndigits=1)
    except Exception:
        return True, None                                       # register family, delta unresolvable → honest-blank


def _field_value(field, asset_table, present_cols, *, latest_row, ratings, window=None, leaf_is_array=False,
                 agg_row=None, element_skeleton=None):
    """The real value for ONE data field, honestly degrading to None (scalar) or [] (numeric-array series leaf).

    `element_skeleton` — for an array-of-OBJECTS target leaf (LoadAnomalyPoint {time,value}, …), the first element's
    shape, so a bucketed series fills OBJECTS matching the component's contract, not raw numbers (card-42 shape fix).

    `agg_row` (panel-aggregate hook) — a pre-computed AGGREGATED SUPERSET ROW {column: aggregated_value} the panel
    renderer injected via ctx['_agg_row']. When present, a `raw` field reads its column straight from THIS row (the
    fleet-rolled-up value across members) and NEVER falls back to the single asset's meter (which would return one
    feeder's number as if it were the panel total). derived/event/bucketed still degrade honestly (their fan-out is the
    renderer's job, not the executor's) — a KPI card fills entirely from the agg row via `raw`, zero duplication."""
    kind = (field.get("kind") or "raw").lower()
    quantity = _quantity_of(field)

    if kind == "derived" and (field.get("fn") or field.get("metric")):
        fn_key = _derived_key(field)
        # FAB-BY-MISLABEL GUARD (Family G, card 72): refuse an active-energy fn bound to a reactive-energy slot (and any
        # active↔reactive↔apparent polarity mismatch). The registry _QUANTITY table is authoritative on what the fn
        # MEASURES; the slot's unit/label declares what it MEANS. When they disagree the leaf honest-blanks rather than
        # rendering the real active delta under an MVARh label. Same-polarity / undisambiguated slots pass through.
        if _polarity_conflict(field, fn_key):
            return None
        raw, _fid = _run_derived(fn_key, asset_table, window)
        return _verify(raw, quantity=quantity)

    if kind in ("const", "text"):
        rk = _slot_map.rating_key_for(field.get("slot")) or _slot_map.rating_key_for(field.get("metric"))
        if rk:
            return (ratings or {}).get(rk)                     # real nameplate value, or None → honest-blank
        v = field.get("value")
        if isinstance(v, str):
            # a DECLARED literal STRING (an axis/label chrome const — sparkline '-29d'/'now') is chrome the AI wrote,
            # not a measurement: _verify is a NUMBER gate and used to null EVERY const/text string (card-58 labels).
            return v
        return _verify(v, quantity=quantity)                   # the baked numeric literal (const)

    if kind == "event":
        col = field.get("column")
        if not (col and col in present_cols):
            return None
        return _event_count(asset_table, col, window)

    # HISTORY / TREND numeric-array series: kind='bucketed' (AI-declared), OR a raw field whose target leaf is itself a
    # numeric ARRAY (a series[i].values leaf) — either way the leaf wants an ORDERED value array, not a scalar. Route it
    # to bucketed() over the ctx window so date-navigation re-slices to the picked window. Does NOT touch scalar raw.
    if kind == "bucketed" or (kind in ("raw", "") and leaf_is_array):
        return _bucketed_values(field, asset_table, present_cols, quantity, window,
                                element_skeleton=element_skeleton)

    # raw (default): the AI-named column from the latest row (denorm/sign verified). Only a present column.
    col = field.get("column")
    if not (col and col in present_cols):
        return None
    # PANEL-AGGREGATE: an injected agg_row wins — read the fleet-rolled value, NEVER re-read the single meter (which
    # would leak one feeder's number as the panel total). agg_row is authoritative; a column absent from it → honest-null.
    if agg_row is not None:
        return _verify(agg_row.get(col), quantity=quantity)
    # WINDOWED-REGISTER RULE [card-39 lifetime-register-as-today]: inside a BOUNDED window, a cumulative energy
    # register's value IS its windowed delta (reversed-CT pick_mover via members.member_delta — the SAME selection the
    # roster/panel paths use, so a scalar can never contradict the panel Σ). A raw read of the lifetime figure belongs
    # only to an UNBOUNDED (real-time) card. Vocabulary = the register_pairs config row; valve
    # app_config fill.window_register_delta ('on' unless 'off'). Delta unresolvable → None (honest, never the register).
    if window and window[0] and window[1]:
        hit, dv = _windowed_register_delta(asset_table, col, window)
        if hit:
            return dv
    raw = (latest_row or {}).get(col)
    if raw is None:
        raw = _nx.latest(asset_table, [col]).get(col)
    return _verify(raw, quantity=quantity)


# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
#  fill — the executor entry. NO strip step: fill each DECLARED field's leaf; a field that can't fill honest-blanks.
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
def fill(payload, data_instructions, ctx, default_payload=None, shape_ref=None):
    """Fill a card's exact_metadata payload from neuract per its data_instructions.fields[]. Returns a completed deep
    copy (input not mutated): real where neuract has it, honest None/'—' else. No leaf_classify, no seed-strip — the
    Layer 2 producer already emits seed-free placeholders; the executor fills only the DECLARED data leaves.

    `default_payload` (optional) = the card's HARVESTED default payload. The Layer-2 gate elides the whole DATA tier
    (roster arrays → None), so a declared series/roster leaf has NO container in `payload`; when the default is provided
    the executor GRAFTS the elided container back (from the default's placeholder skeleton) so the leaf becomes fillable.
    Every grafted placeholder is overwritten by the real fill (or honest-blanked) below — no seed survives.

    `shape_ref` (optional) = the card's RAW harvested default payload, used as a SHAPE ORACLE ONLY (clock-label axes,
    y-tick label element types, normalized-series contracts, zero-floor axes). NO value is ever copied from it into the
    completed payload — the post-fill passes only read its SHAPES; the stripped `default_payload` stays the only graft
    VALUE source (zero-fabrication stands). Absent → the passes fall back to the stripped default's weaker evidence.

    PANEL-AGGREGATE hook: when `ctx['_agg_row']` carries a pre-rolled AGGREGATED SUPERSET ROW {column: value} (built by
    ems_exec.renderers.panel_aggregate across the panel's members), every `raw` scalar field fills from THAT row instead
    of the single asset meter — so the panel_aggregate renderer reuses THIS executor verbatim for its KPI/scalar leaves
    (zero duplication). The row's keys ARE the present columns for the raw path; a column absent from it honest-nulls."""
    out = copy.deepcopy(payload) if payload is not None else {}
    ctx = ctx or {}
    # ── ROSTER seam #1 (valve-guarded, generalization package §3): a member-scope card resolves its panel members ONCE
    # and injects the fleet-rolled ctx['_agg_row'] so the scalar fields below fill from the aggregate. No-op unless
    # app_config roster.interpreter_enabled != 'off' AND ctx carries mfm_id AND a roster instruction/recipe exists.
    try:
        from ems_exec.executor import roster as _roster
        _roster.prepare_ctx(data_instructions, ctx)
    except Exception:
        pass
    asset_table = ctx.get("asset_table") or ctx.get("table") or ctx.get("table_name")
    agg_row = ctx.get("_agg_row")                                # panel-aggregate: injected fleet-rolled superset row
    fields = _fields_of(data_instructions)
    window = _window_of(ctx, data_instructions)
    # in the aggregate path the "present columns" for RAW fields are the keys of the injected row (every column the
    # renderer could roll up); otherwise they are the resolved single meter's real columns.
    present_cols = frozenset(agg_row.keys()) if agg_row is not None else _nx.present_columns(asset_table)

    # one latest-row read reused across raw fields; the REAL per-asset nameplate ratings (honest-degrade → {})
    if agg_row is not None:
        latest_row = agg_row                                    # the aggregate superset row IS the latest-row source
    else:
        raw_cols = sorted({f.get("column") for f in fields
                           if (f.get("kind") or "raw").lower() in ("raw", "") and f.get("column") in present_cols})
        latest_row = _nx.latest(asset_table, raw_cols) if raw_cols else {}
    ratings = _np.derive_ratings_for(asset_table)
    asset_name = ctx.get("asset_name")
    gaps = []                                                  # per-leaf honest-gap records (reason channel, telemetry)

    axis_ms = None                                             # the card's bucket-timestamp axis, computed lazily ONCE
    written_value_paths = set()                                # F2: leaf paths the executor wrote (display-sibling reconcile)
    # WILDCARD ARRAY-GROW pre-pass [composite cards 56/59]: fields whose slot is `<array>[*].<key>` cannot be resolved by
    # the scalar loop below (the '*' is neither a dict key nor a list index). Grow each such array ONCE across the shared
    # bucket axis (per-point OBJECT array), then skip those fields in the main loop.
    wild_fields = []
    for f in fields:
        sp = _split_wildcard(f.get("slot"))
        if sp:
            wild_fields.append((f, sp[0], sp[1]))
    # SINGLE-INDEX SERIES PROMOTION [card 73 false-blank, Family C]: Layer 2 sometimes fans a per-bucket trend into
    # `<array>[0].<key>` fields — several DISTINCT keys ALL at index 0 (buckets[0].active/reactive/apparent/pf) — meaning
    # "grow this array across the bucket axis; each bucket's <key> ← its column's bucketed value". A `kind='bucketed'`
    # (series) field pointed at a SCALAR per-bucket element is a series, not a scalar. The per-index family pre-pass below
    # only fires on ≥2 SAME-key fields (sparkline[0..29].loadPct — point i ← series i); DISTINCT-key SOLO fields fall to
    # the scalar loop, which crams the WHOLE ordered series into element[0].<key> (chart geometry destroyed) or blanks it
    # when the array is empty — yet maxY still computes from the same column (proving the frame carried data), so the trend
    # FALSE-BLANKS. Route ONLY the SOLO single-index fields (their (array,key) group has exactly one member — NOT a
    # same-key sparkline family) through the SAME wildcard array-grow as `[*]`, so the array grows to the full per-bucket
    # series. Generic — array/key from the slot, no card ids; a genuinely null bucket → honest None.
    _idx_by_key: dict = {}
    for f in fields:
        if (f.get("kind") or "").lower() != "bucketed" or _split_wildcard(f.get("slot")):
            continue
        sp = _split_indexed(f.get("slot"))
        if sp and _scalar_point_slot(out, default_payload, f.get("slot")):
            _idx_by_key.setdefault((sp[0], sp[2]), []).append(f)   # group by (array_path, elem_key)
    promoted_ids = set()
    for (array_path, elem_key), grp in _idx_by_key.items():
        if len(grp) != 1:
            continue                                           # ≥2 SAME-key indices = a sparkline family → indexed-fill
        f = grp[0]
        wild_fields.append((f, array_path, elem_key))          # (field, array_path, elem_key) — a wildcard-grow member
        promoted_ids.add(id(f))
    wild_paths = set()
    if wild_fields:
        wild_paths = _fill_wildcard_arrays(out, default_payload, wild_fields, asset_table, present_cols, window,
                                           gaps, asset_name=asset_name)
        for p in wild_paths:                                   # a GROWN array is fill-produced: its zeros are real
            written_value_paths.add(p)                         # readings/honest Nones — exempt from placeholder-null
            written_value_paths.add(f"data.{p}")               # (both address forms _leaf_path_for resolves)
    # PER-INDEX SERIES FAMILY pre-pass [card 58 sparkline]: group `<array>[i].<key>` bucketed fields per (array, key)
    # and fill each family from ONE shared series (point i ← bucket i, end-aligned). The scalar loop below would hand
    # EACH such slot the whole series — or [] when the field is column-less (the all-empty sparkline). Fields already
    # PROMOTED to the wildcard array-grow above (single-index per-bucket series) are excluded — they are grown, not indexed.
    idx_groups = {}
    for f in fields:
        if (f.get("kind") or "").lower() != "bucketed" or _split_wildcard(f.get("slot")):
            continue
        if id(f) in promoted_ids:
            continue
        sp = _split_indexed(f.get("slot"))
        if sp and _scalar_point_slot(out, default_payload, f.get("slot")):
            idx_groups.setdefault((sp[0], sp[2]), []).append((f, sp[1]))
    families = {k: v for k, v in idx_groups.items() if len(v) >= 2}
    consumed_ids = set()
    if families:
        consumed_ids = _fill_indexed_families(out, default_payload, families, asset_table, present_cols, window,
                                              gaps, ratings=ratings, asset_name=asset_name,
                                              written_paths=written_value_paths)
    for f in fields:
        if _split_wildcard(f.get("slot")) or id(f) in promoted_ids:
            continue                                            # handled by the wildcard array-grow pre-pass above
        if id(f) in consumed_ids:
            continue                                            # handled by the per-index series-family pre-pass above
        slot = f.get("slot") or f.get("target_column") or f.get("metric")
        # GRAFT the DATA container back from the default if the gate elided it (a roster/series leaf), so the declared
        # leaf is fillable. Try both the raw slot and the data.<slot> address the executor resolves to.
        if default_payload is not None:
            for cand in (slot, f"data.{slot}" if slot else None, f.get("metric"), f.get("target_column")):
                if cand and not _has_path(out, cand) and _has_path(default_payload, cand):
                    _graft_container(out, default_payload, cand); break
        leaf_path = (_leaf_path_for(out, slot)
                     or _leaf_path_for(out, f.get("metric"))
                     or _leaf_path_for(out, f.get("target_column")))
        if leaf_path is None:
            # skeleton has no such leaf — nothing to bind, but the declared quantity is still an EXPLAINED gap
            _note_gap(gaps, f, asset_table, present_cols, latest_row, asset_name=asset_name)
            continue
        # CHROME GUARD (generic, shape-driven from the DEFAULT — no card ids): a leaf whose DEFAULT is a list of CONFIG
        # OBJECTS (line/axis DEFINITIONS: {key, axis, name, color, trip, warn, …} — chrome; the data is bound elsewhere by
        # the component via each object's `key`) is NOT a fillable value array. The byte-identity gate elides it to None,
        # which loses the shape and lets a bucketed field flatten it into raw numbers (chart geometry destroyed — the
        # judge flagged 'chrome keys lost: chart.series[*]'). A DATA-POINT element ({time,value}/{t,value}) has a value-
        # OR time-key; a config element has NEITHER. Restore the config array byte-identical from the default + gap it. So
        # the honest-blank chart keeps its labeled lines/scale and never shows a fabricated flat series. [cards 61/62/65]
        _dflt_leaf = _leaf_at(default_payload, leaf_path) if default_payload is not None else None
        if isinstance(_dflt_leaf, list) and _dflt_leaf and all(isinstance(e, dict) for e in _dflt_leaf) \
                and _element_value_key(_dflt_leaf[0]) is None and _element_time_key(_dflt_leaf[0]) is None:
            _set_leaf_typed(out, leaf_path, copy.deepcopy(_dflt_leaf))   # config chrome preserved byte-identical
            _note_gap(gaps, f, asset_table, present_cols, latest_row, asset_name=asset_name)
            continue
        # TIME-AXIS leaf (kind='time', or a compat 'ts'-bound field): fill from the SAME bucket timestamps as this
        # card's series (epoch ms) so points and x-axis align; axisStartMs/axisEndMs get the window's first/last bucket.
        toks = _toks(leaf_path)
        # CHROME GUARD (generic, shape-driven — no card ids): a time-axis DATA leaf is a list of SCALARS (epoch ms) or a
        # scalar bound (axisStartMs/EndMs). Some primitives (thermal/mech dual-axis charts) instead keep a list of axis-
        # CONFIG OBJECTS at `chart.axes` ({id,domain,orientation,…} — pure CHROME defining the scale). If Layer 2 emitted
        # a kind='time' field pointing at such a config-object array, filling it with timestamps DESTROYS the axis config
        # (points lose their scale). So NEVER overwrite a list whose elements are dicts: it is chrome, not a time series.
        # Structure preserved byte-for-byte; the series still carries its own points. [chrome-loss cards 61/62]
        _tnow = _leaf_at(out, leaf_path)
        if _is_time_field(f, toks[-1] if toks else "") and isinstance(_tnow, list) \
                and any(isinstance(e, dict) for e in _tnow):
            continue
        # Y-SCALE GUARD [card 37 epoch-ms-in-yTicks]: a kind='time' field MIS-DECLARED onto a Y-SCALE leaf (yTicks /
        # maxY / yMin — the yscale key vocabulary) must NEVER be epoch-filled: those leaves are the chart's VALUE axis
        # and the FE derives yMax=Number(yTicks[0]) from them — 25 epoch timestamps there pin a real 228-240 V series
        # flat and print epochs as tick labels. Skip the write; the post-fill yscale pass derives the real scale from
        # the card's own filled series (or leaves the honest-blank axis). Generic — key vocabulary, no card ids.
        if _is_time_field(f, toks[-1] if toks else ""):
            try:
                from ems_exec.executor import yscale as _ys
                if _ys.is_scale_key(toks[-1] if toks else ""):
                    continue
            except Exception:
                pass
            if axis_ms is None:
                axis_ms = _anchor_timestamps(fields, asset_table, present_cols, window)
            key = (toks[-1] if toks else "").lower()
            if isinstance(_leaf_at(out, leaf_path), list):
                _set_leaf_typed(out, leaf_path, list(axis_ms))
            elif key.endswith("startms"):
                _set_leaf_typed(out, leaf_path, axis_ms[0] if axis_ms else None)
            elif key.endswith("endms"):
                _set_leaf_typed(out, leaf_path, axis_ms[-1] if axis_ms else None)
            else:
                _set_leaf_typed(out, leaf_path, list(axis_ms))
            continue
        # is this leaf a numeric ARRAY (a history/trend series[i].values)? Then a raw column must be read as a bucketed
        # SERIES, not a scalar — so the array fills a real ORDERED series, not a single number. (kind='bucketed' always
        # takes the series path regardless; this flags the raw-into-array case for the executor.)
        _leaf_now = _leaf_at(out, leaf_path)
        leaf_is_array = isinstance(_leaf_now, list)
        # CHROME GUARD (generic, shape-driven — no card ids): some dual-axis chart primitives keep `chart.series` as a
        # list of series-CONFIG OBJECTS (line DEFINITIONS: {key, axis, name, color, trip, warn, …} — pure chrome; the
        # DATA lives one level deeper in each object's own values leaf). If Layer 2 bound a bucketed column straight at
        # this config-object array, filling it would REPLACE the line definitions with a flat value array (chart geometry
        # destroyed — the judge flagged 'chrome keys lost: chart.series[*]'). A DATA-POINT element ({time,value}/{t,value})
        # has a value-key OR a time-key; a config element has NEITHER. Preserve a config-object array + record the gap.
        if leaf_is_array and _leaf_now and isinstance(_leaf_now[0], dict) \
                and _element_value_key(_leaf_now[0]) is None and _element_time_key(_leaf_now[0]) is None:
            _note_gap(gaps, f, asset_table, present_cols, latest_row, asset_name=asset_name)
            continue
        # ARRAY-OF-OBJECTS target (LoadAnomalyPoint {time,value}, …): pass the first element's shape so a bucketed series
        # fills OBJECTS matching the component's contract, never raw numbers (card-42 all-NaN geometry). [FE-contract]
        _elem = _leaf_now[0] if (leaf_is_array and _leaf_now and isinstance(_leaf_now[0], dict)) else None
        val = _field_value(f, asset_table, present_cols, latest_row=latest_row, ratings=ratings,
                           window=window, leaf_is_array=leaf_is_array, agg_row=agg_row, element_skeleton=_elem)
        _set_leaf_typed(out, leaf_path, val)                    # real number/array OR None ('—') — never array→null
        written_value_paths.add(leaf_path)                     # F2: track written value leaves for display-sibling reconcile
        if _blank_val(val):
            _note_gap(gaps, f, asset_table, present_cols, latest_row, asset_name=asset_name)  # WHY it blanked

    # FE-SAFETY NET for UNDECLARED rosters: the Layer-2 byte-identity gate elides every DATA roster to None; the graft
    # above restores only the DECLARED slots. Any roster the AI declared NO field for is still None here — and the FE
    # component .map()s it → 'Cannot read properties of null'. Restore the container TYPE (an EMPTY [] — honest, no
    # seed) wherever the default payload carries a list but the completed payload carries None/missing.
    if default_payload is not None:
        _restore_array_containers(out, default_payload)

    # PLACEHOLDER-NULL at fill completion [card-59 bypassVoltageV]: an UNTOUCHED scalar data leaf (undeclared, no
    # binding) must not ship its numeric 0.0 build placeholder as if measured — null it (display_dash → '—'). Runs
    # BEFORE the roster seam so a roster-written real zero lands after and survives; written/declared leaves and every
    # non-placeholder value are exempt (see the three fences in _null_untouched_placeholders).
    if isinstance(out, dict) and isinstance(payload, dict):
        try:
            _null_untouched_placeholders(out, payload, written_value_paths)
        except Exception:
            pass

    # ── ROSTER seam #2: the member-scope slots (elements / groups / aggregates / sections / sankey) — the generic
    # interpreter fills them from the members resolved in seam #1. Per-slot honest-degrade; no-op when not prepared.
    if ctx.get("_roster_state") is not None:
        try:
            from ems_exec.executor import roster as _roster
            out = _roster.run_roster(out, (data_instructions or {}).get("roster"), ctx,
                                     default_payload=default_payload)
        except Exception:
            pass
        # ROSTER REASONS [card-12 render.gaps=null family]: every roster-written data leaf that stayed BLANK (a dark
        # member, an alias of a blank sibling, a recipe honest-null with its DB-authored why) gets a per-leaf gap
        # record on the SAME reason channel — a rebuilt roster tree is invisible to the sources-based scan below
        # (its structure exists only in the completed payload), so the roster state itself is the discovery.
        try:
            from ems_exec.executor import roster_gaps as _rgaps
            gaps.extend(_rgaps.collect(out, ctx.get("_roster_state"), existing=gaps))
        except Exception:
            pass

    # POST-FILL Y-SCALE DERIVATION [cards 44/46/48/49 + 37/38/40]: a chart's scale object ({maxY,minY,yTicks}, the
    # yMax/yMin naming, prefix pairs like demandYMax/demandYMin, and ticks-ONLY axes) was stripped to 0.0/[] — or
    # emit-bound to a degenerate latest-sample — so the real filled series renders OFF-SCALE. Recompute each scale from
    # its sibling series' OWN min/max AFTER the series are filled (and after the roster may have filled member series).
    # `shape_ref` (the RAW default) proves tick element TYPE (string labels vs numbers), tick count and the zero-floor
    # convention. Never fabricates a scale for absent data (an empty series leaves the honest-blank axis).
    if isinstance(out, dict):
        try:
            from ems_exec.executor import yscale as _yscale
            out = _yscale.apply(out, shape_ref=shape_ref)
        except Exception:
            pass

    # POST-FILL NORMALIZED-SERIES CONTRACT [card 36]: a chart whose DEFAULT series values ALL live in [0,1] (the
    # normalized strip-chart contract — PowerEnergyChart clamps every point to 0..1) must never receive raw kW; the
    # filled raw series is normalized over its own shared range and the sibling numeric-string label axis (yLabels)
    # derives from that range — mirroring CMD_V2's own rangeFromSamples/buildSharedPowerYLabels. Shape-proven ONLY
    # (needs shape_ref); no shape evidence → untouched.
    if isinstance(out, dict) and shape_ref is not None:
        try:
            from ems_exec.executor import norm_series as _norm_series
            out = _norm_series.apply(out, shape_ref)
        except Exception:
            pass

    # POST-FILL X-AXIS LABELS [cards 44/46]: a default-proven CLOCK-LABEL axis the strip blanked ('' × 10) re-derives
    # from the card's own filled epoch-ms time axis (site-tz HH:MM at evenly spaced tick positions; a default-proven
    # INDEX sibling gets the integer positions — the FE places labels by series index). When the emit declared NO
    # time slot (or mis-declared it onto a Y-scale leaf the card-37 guard refused) the LAZY ts_provider hands xaxis
    # the card's OWN bucket axis (_anchor_timestamps — the SAME buckets the series fill used; computed only on
    # demand). Underivable → per-leaf gap. The RAW default (shape_ref) is the shape oracle — the stripped default
    # erased the clock evidence to '' × 10.
    if isinstance(out, dict) and (shape_ref is not None or default_payload is not None):
        try:
            from ems_exec.executor import xaxis as _xaxis

            def _bucket_axis():
                nonlocal axis_ms
                if axis_ms is None:
                    axis_ms = _anchor_timestamps(fields, asset_table, present_cols, window)
                return axis_ms

            out = _xaxis.apply(out, shape_ref if shape_ref is not None else default_payload, gaps,
                               ts_provider=_bucket_axis)
        except Exception:
            pass

    # POST-FILL VIEW SELECT [card 48]: a multi-view chart whose `view` selector points at a DATA-LESS view while a
    # sibling view carries the real filled series opens on the data-bearing view instead (shape-driven, honest).
    if isinstance(out, dict):
        try:
            from ems_exec.executor import view_select as _vsel
            out = _vsel.apply(out)
        except Exception:
            pass

    # DISPLAY-SIBLING RECONCILE [F2: no Storybook projection survives beside a filled value]. A CMD_V2 reading is a
    # STRUCTURED object {value, displayValue, decimals, delta, deltaText, …}; fill overwrote only `value`, so its sibling
    # displayValue/delta held the harvested seed (real value=426.75 beside stale displayValue='325.9'). Recompute
    # displayValue ≡ fmt(value) for EVERY reading object (the fmtMetric invariant, can only ever make the string
    # consistent) + blank the un-recomputable %-change/rate projections (delta/deltaText/*PerMin) beside the leaves the
    # executor WROTE. Shape-driven (value/display keys from config.vocab), no card ids. Runs after roster/yscale so
    # member-filled reading objects are reconciled too.
    if isinstance(out, (dict, list)):
        try:
            from ems_exec.executor import display as _display
            out = _display.apply(out, written_value_paths)
        except Exception:
            pass

    # HONEST STATE DERIVATIONS [family H, cards 36/37/38 + 7/10 class]: two blank-only, shape-driven passes —
    #   freshness   — the RTM {status,label,tone,lastUpdateLabel} view-model derives from the asset's OWN newest-sample
    #                 age (neuract.latest_ts, app_config freshness.stale_after_s), byte-faithful to CMD_V2's
    #                 buildFreshness (Live/Stale/Offline + the REAL 'Last update HH:MM:SS' in site tz).
    #   trend badge — a blank rail/trend statusBadge derives Rising/Stable/Falling from the card's OWN bound series
    #                 via CMD_V2's trendDir rule (display.trend_flat_pct). A derivation of bound data, never a guess;
    #                 underivable (no series / no timestamp) stays blank. Never overwrites a non-blank state.
    if isinstance(out, dict):
        try:
            from ems_exec.executor import freshness as _freshness
            out = _freshness.apply(out, asset_table)
        except Exception:
            pass
        try:
            from ems_exec.executor import trend_badge as _tbadge
            out = _tbadge.apply(out)
        except Exception:
            pass

    # REASONS-ALWAYS completion scan [cards 63/79/48]: any data leaf STILL blank after fill+roster+yscale+display that
    # no declared field explained gets a per-leaf 'unbound_by_emit' record — no bare '—' ever ships reasonless. Stale
    # records (a leaf a LATER pass filled — yscale minY, roster member slots) are pruned first: reasons describe the
    # SERVED payload only.
    if isinstance(out, dict):
        try:
            gaps = _prune_stale_gaps(out, gaps)
            _attach_unbound_gaps(out, (payload, default_payload), gaps)
        except Exception:
            pass

    # attach the honest-gap reason channel LAST (after roster may replace `out`) — telemetry the host pops (pop_gaps)
    if gaps and isinstance(out, dict):
        out[GAPS_KEY] = gaps

    return out
