"""ems_exec/executor/members.py — PANEL MEMBER resolution + reads for the generic roster interpreter. ZERO card
knowledge: every column set arrives as a parameter (the caller reads them from app_config roster.* rows / the validated
roster instruction) — no card ids, no root keys, no element-key names, no thresholds here.

One concern: given a panel's registry mfm_id, resolve its member meters (data.neuract_live edges — incomers_of +
outgoers_of, roles preserved), read each member's declared columns from ems_exec.data.neuract (present-tolerant), select
subsets by role/reporting, and roll the electrical up into the aggregated superset row the per-card executor fills
scalar leaves from (Σ for extensive magnitudes, mean for intensities, windowed-delta Σ for the energy counter).

Lifted from ems_exec/renderers/panel_aggregate.py:84-206 (the proven fan-out) with the column sets parameterized so the
SAME functions serve every roster card. HONEST-DEGRADE everywhere: an orphan panel → ([], honest_blank coverage); a
member with no gic_* table keeps its identity but reads {} (all leaves honest-null); a column no member reported → None
(never a fabricated 0). [atomic; DATA = NEURACT ONLY]
"""
from __future__ import annotations

from ems_exec.data import neuract as _nx
from layer1b.resolve.member_scope import INCOMER
from ems_exec.renderers import _agg
# ENERGY-REGISTER pick_mover HOME moved to executor/energy_registers.py (monoliths F7, 2026-07-12) — the
# register-pair map + mover selection is a DATASET convention, not a panel-membership concern (fill.py and
# bindings.py consumed it by importing this panel module). Re-exported byte-compatibly.
from ems_exec.executor.energy_registers import (                                          # noqa: F401
    _delta_of, _export_col, register_pairs, member_delta, member_delta_pair, _bucketed_energy_delta)


def _num(x):
    return _agg.num(x)


# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
#  resolution — the fan-out door (data.neuract_live edges + the recursing has-data leaf set for honest coverage)
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
def resolve(mfm_id, section_token=None):
    """(members, coverage) for a panel. `members` = the DEDUPED union of outgoing (feeder) + incoming (source) member
    meters, each {mfm_id, name, table, role, type, load_group}; a member with no gic_* table is kept but honest-nulls
    its electrical. `coverage` = {reporting, expected, verdict} from the recursing panel_members door (the honest
    denominator). An orphan / unknown panel → ([], honest_blank). Never raises.

    `section_token` [bus-section view, e.g. '1B']: keep ONLY members whose equipment.mfm section matches exactly —
    'pcc-1b' means SECTION B of PCC-Panel-1, not the whole panel. Common/bus-level gear (section '1') and unmapped
    members stay in the FULL panel view only (per-section inclusion would double-count couplers/incomers in a
    section-vs-section compare). Coverage is recomputed over the SECTION's member set (the honest denominator)."""
    if mfm_id is None:
        return [], _agg.coverage_verdict(0, 0)
    try:
        from data.neuract_live import members as _members
        out_side = _members.outgoers_of(mfm_id) or []
        in_side = _members.incomers_of(mfm_id) or []
    except Exception:
        return [], _agg.coverage_verdict(0, 0)
    seen, members = set(), []
    for m in list(out_side) + list(in_side):
        mid = m.get("mfm_id")
        if mid in seen:
            continue
        seen.add(mid)
        reg = _meter_row(mid)
        try:
            from data.equipment.sections import section_of as _section_of
            _sec = _section_of(m.get("neuract_table"))
        except Exception:
            _sec = None
        members.append({
            "mfm_id": mid,
            "name": m.get("name"),
            "table": m.get("neuract_table"),
            "role": m.get("role"),
            "type": reg.get("type_code"),
            "load_group": reg.get("load_group"),
            "section": _sec,                              # bus-section token ('1A'/'1B'/…) — element-bindable [sections]
        })
    if section_token:
        from data.equipment.sections import section_of
        members = [m for m in members if section_of(m.get("table")) == str(section_token).upper()]
        try:
            from data.value_probe import tables_with_data
            live = tables_with_data([m["table"] for m in members if m.get("table")])
            return members, _agg.coverage_verdict(sum(1 for m in members if m.get("table") in live), len(members))
        except Exception:
            return members, _agg.coverage_verdict(0, len(members))
    try:
        from data.lt_panels.panel_members import panel_members as _panel_members
        pm = _panel_members(int(mfm_id))
        expected = pm.get("expected_count") or len(members)
        reporting = pm.get("reporting_count") or 0
    except Exception:
        expected, reporting = len(members), 0
    return members, _agg.coverage_verdict(reporting, expected)


def _meter_row(mfm_id):
    """The member's registry row ({type_code, load_group, …}) or {} (honest-degrade on a stale id / registry outage)."""
    try:
        from registries import neuract as _reg
        return _reg.meter_by(mfm_id) or {}
    except Exception:
        return {}


def ts_col():
    """The neuract timestamp column name (DB-driven via config.neuract_dsn; None on outage → labels honest-null).
    The ONE fail-open accessor the member-read callers (roster prepare, panel_aggregate) share."""
    try:
        from config import neuract_dsn as _dsnc
        return _dsnc.ts_col()
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
#  reads — ONE latest-row pass per member (present-tolerant: absent column → None; no table → {})
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
def rows(members, columns, ts_col=None):
    """[(member, latest_row)] — each member's LATEST neuract row for `columns` (+ the row timestamp when `ts_col` is
    given). Present-tolerant: an absent column simply misses from the row (readers .get() → None); a member with no
    table reads {} (all leaves honest-null). This is the ONE per-member read pass."""
    cols = list(dict.fromkeys([c for c in (columns or []) if c] + ([ts_col] if ts_col else [])))
    out = []
    for m in (members or []):
        tbl = m.get("table")
        try:
            row = _nx.latest(tbl, cols) if (tbl and cols) else {}
        except Exception:
            row = {}
        out.append((m, row))
    return out


def select(pairs, role_filter="all", reporting_only=False, power_col=None):
    """The (member, row) subset by ROLE + reporting. supply → role=='incoming' (the meters that FEED the panel);
    load → every other role (the meters it feeds — the aggregation set; summing both sides would double-count the same
    physical flow); all → both. reporting_only → only members whose `power_col` read is a real number (honest partial
    coverage: a dark stub never pads a mean denominator)."""
    rf = (role_filter or "all").strip().lower()
    got = []
    for m, r in (pairs or []):
        role = (m.get("role") or "").strip().lower()
        if rf == "supply" and role != "incoming":
            continue
        if rf == "load" and role == "incoming":
            continue
        if reporting_only and power_col and _num(r.get(power_col)) is None:
            continue
        got.append((m, r))
    return got


# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
#  rollup — the AGGREGATED SUPERSET ROW {column: rolled_value} + the panel's windowed energy
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
def role_filter_for(member_scope):
    """Map a panel's READING DIRECTION (member_scope: 'outgoing' default / 'incomer') to the select() role_filter:
    'incomer' → 'supply' (the meters that FEED the panel — the supply side); anything else → 'load' (the fed
    feeders/bays the panel distributes to, the DEFAULT). One place so agg_row / panel_kwh / the bucketed rolls all agree
    on which side a member_scope selects. [panel_overview]"""
    return "supply" if str(member_scope or "").strip().lower() == INCOMER else "load"


def agg_row(pairs, window, columns, sum_cols, energy_col=None, pf_cols=None, power_col=None, role_filter="load"):
    """The fleet-rolled superset row the per-card executor fills KPI/scalar leaves from (ctx['_agg_row']). Each column
    is reduced across the `role_filter`-side members that reported it — Σ-magnitude for `sum_cols`, mean otherwise. The
    unsigned true PF fold (`pf_cols` = [preferred_unsigned, signed_fallback]) fills both PF columns; `energy_col`
    (cumulative counter) becomes the windowed-delta Σ. Honest-null: a column no member reported → None (never a
    fabricated 0). role_filter defaults to 'load' (the fed feeders/bays — a plain panel prompt) so the reading NEVER
    double-counts a flow that both sides measure; 'supply' rolls the INCOMER side instead (an 'incomer <panel>' prompt)."""
    reporting = select(pairs, role_filter=role_filter or "load", reporting_only=bool(power_col), power_col=power_col)
    row = {}
    sums = set(sum_cols or ())
    for col in (columns or []):
        vals = [r.get(col) for (_m, r) in reporting]
        row[col] = _agg.sum_magnitude(vals) if col in sums else _agg.mean(vals)
    if pf_cols and len(pf_cols) >= 2:
        preferred, signed = pf_cols[0], pf_cols[1]
        pf = _agg.mean([r.get(preferred) for (_m, r) in reporting])
        if pf is None:
            pf = _agg.mean([abs(v) for (_m, r) in reporting if (v := _num(r.get(signed))) is not None])
        row[preferred] = pf
        row[signed] = pf
    if energy_col:
        row[energy_col] = panel_kwh(pairs, window, energy_col, role_filter=role_filter or "load")
    return row


def panel_kwh(pairs, window, energy_col, role_filter="load"):
    """Σ of per-member windowed energy deltas over the ctx window (the panel's energy). `role_filter` side only
    (double-count guard; defaults to 'load' = the fed feeders, 'supply' for an incomer prompt). None when no member
    yields a real delta (honest-null).

    REVERSED-CT AWARE (the register fix): a member wired reversed-CT keeps its real energy on the EXPORT register (its
    import delta is flat ~0 — the 3 GIC UPS feeders read import=0 while active_energy_export_kwh moves ~4700 kWh), a
    forward member (bpdb-01) on import. So per member the roll-up reads BOTH the import register (`energy_col`) and the
    configured EXPORT register and PICKS the one that moved (energy.member_energy_delta → _pick_register), abs()'d for a
    positive kWh. A genuinely dark feeder (neither register moved) contributes nothing, never a fabricated 0. When no
    export register is configured (roster.energy_export_column unset) this degrades to the legacy import-only Σ."""
    if not energy_col:
        return None
    total = None
    for m, _r in select(pairs, role_filter=role_filter or "load"):
        picked = member_delta(m, window, energy_col, ndigits=None)   # the ONE pick_mover selection (register_pairs)
        if picked is not None:
            total = (total or 0.0) + picked
    return round(total, 1) if total is not None else None


def bucketed_rolled(pairs, column, window, sampling="hourly", reduce="sum_magnitude", role_filter="load"):
    """The member-rolled [{t, value}] series for ONE column across the selected members — each member's OWN neuract
    bucketed read, folded per bucket (Σ-magnitude for extensive magnitudes, mean for intensities; the fold is
    caller-declared, mirroring agg_row's quantity rule). [] when no selected member reports the column (honest-degrade —
    never a fabricated curve). LOAD side by default: supply incomers measure the same physical flow and would
    double-count a panel trend. This is the fan-out the single-meter executor cannot do (a panel's own device table
    carries no electrical series)."""
    return bucketed_rolled_members(select(pairs, role_filter=role_filter or "load"),
                                   column, window, sampling=sampling, reduce=reduce)


def bucketed_rolled_members(subset_pairs, column, window, sampling="hourly", reduce="sum_magnitude"):
    """bucketed_rolled over an EXPLICIT (member, row) subset — the same per-bucket fold, but the caller has already
    selected the members (e.g. one feeder-group split of the panel). Same honest-degrade: [] when no member in the
    subset reports the column. This is the fan-out door for a multi-series split where each series is one member group."""
    if not column:
        return []
    start, end = (window or (None, None))
    by_t = {}
    for m, _r in (subset_pairs or []):
        tbl = m.get("table")
        try:
            if not tbl or column not in _nx.present_columns(tbl):
                continue
            for pt in _nx.bucketed(tbl, column, start, end, sampling=sampling or "hourly"):
                t = pt.get("t")
                if t is not None:
                    by_t.setdefault(t, []).append(pt.get("value"))
        except Exception:
            continue                                            # one dark/broken member never sinks the rolled series
    if not by_t:
        return []
    fold = _agg.mean if (reduce or "sum_magnitude").strip().lower() == "mean" else _agg.sum_magnitude
    return [{"t": t, "value": fold(by_t[t])} for t in sorted(by_t)]


def _spec_match(member, match):
    """True when `member` falls in a bucketed_multi spec's optional `match` group (any-of, case-insensitive): types
    (type_code), load_groups (load_group), name_contains (substring on name OR table — the reliable feeder discriminator
    when registry names are gic_* / load_groups are the GIC-xx site). No match declared → matches EVERY member (the
    fleet-wide default). A match with keys that select nobody → the spec is honest-null on every bucket (never the fleet
    Σ misattributed to an absent feeder class). Mirrors roster._member_match, inlined to avoid a circular import."""
    if not match:
        return True
    if not isinstance(match, dict):
        return False
    mtype = str(member.get("type") or "").strip().lower()
    lg = str(member.get("load_group") or "").strip().lower()
    hay = (str(member.get("name") or "") + " " + str(member.get("table") or "")).strip().lower()
    if mtype and mtype in {str(x).strip().lower() for x in (match.get("types") or [])}:
        return True
    if lg and lg in {str(x).strip().lower() for x in (match.get("load_groups") or [])}:
        return True
    if any(sub and str(sub).strip().lower() in hay for sub in (match.get("name_contains") or [])):
        return True
    return False


def bucketed_multi(pairs, specs, window, sampling="day", role_filter="load"):
    """The member-rolled MULTI-KEY bucketed series: [{"t": bucket_iso, "vals": {out_key: rolled_value}}] over the shared
    bucket axis, one entry per time bucket, ascending. Each `specs` entry declares ONE per-bucket quantity across the
    selected members:
        {"key": <out_key>, "column": <neuract col>, "kind": "energy_delta"|"avg"|"event",
         "reduce": "sum_magnitude"|"mean"|"maximum", "r":n, "match": {types|load_groups|name_contains}?}
    · kind='energy_delta' → each member's per-bucket max−min counter delta (neuract.bucketed_delta), folded Σ (energy).
    · kind='avg'          → each member's per-bucket AVG (neuract.bucketed), folded per `reduce` (Σ magnitude / mean /
                            maximum — maximum = the panel WORST-OF that bucket, e.g. the worst-feeder V-dev / I-unbalance
                            line; the intensity trend a single fold cannot express).
    · kind='event'        → each member's per-bucket RISING-EDGE (0/1): a bucket counts 1 for a member only when the flag
                            goes de-asserted→asserted at THAT bucket (a new event starting), never once per active sample;
                            folded Σ across members = the honest per-bucket event count (a genuinely quiet flag → 0 every
                            bucket, never a fabricated bar). The event-timeline stack shape.
    · match (optional)    → scopes THIS key to a member sub-group (a per-equipment split: ups / bpdb / …); absent → the
                            whole selected fleet. A match selecting nobody → the key honest-nulls every bucket.
    The bucket axis is the UNION of every member/column's buckets; a key a bucket has no member reading for → None
    (honest-null, never a fabricated 0). [] when NO spec yields any bucket. LOAD side by default (double-count guard).
    This is the ONLY multi-column member fan-out — every key rides the SAME real bucket axis so a point stays coherent."""
    subset = select(pairs, role_filter=role_filter or "load")
    specs = [s for s in (specs or []) if isinstance(s, dict) and s.get("key") and s.get("column")]
    by_t = {}                                                   # bucket_iso -> {out_key: [per-member values]}
    for s in specs:
        key, col = s["key"], s["column"]
        kind = (s.get("kind") or "avg").strip().lower()
        match = s.get("match")
        for m, _r in subset:
            if not _spec_match(m, match):
                continue
            tbl = m.get("table")
            try:
                if kind == "event":
                    # per-member per-bucket RISING-EDGE COUNT from the RAW rows (neuract.bucketed_edges): every real
                    # de-asserted→asserted crossing inside the bucket counts (a register flapping 25×/hour reports 25),
                    # never one-per-active-sample and never the collapsed bucket-avg edge (the old hourly-AVG loop saw a
                    # flapping flag as permanently asserted → ~1 edge/day — the cards-18/20/22 zero-events defect). A
                    # member's per-bucket counts fold Σ across members; a quiet flag contributes real 0s, an absent
                    # column contributes nothing (honest — never a fabricated bar).
                    for pt in _nx.bucketed_edges(tbl, col, window[0], window[1], sampling=sampling) if tbl else []:
                        t = pt.get("t")
                        if t is not None:
                            by_t.setdefault(t, {}).setdefault(key, []).append(pt.get("value"))
                    continue
                if not tbl or (col not in _nx.present_columns(tbl)
                               and not (kind == "energy_delta" and _paired_present(tbl, col))):
                    continue
                if kind == "energy_delta":
                    pts = _bucketed_energy_delta(tbl, col, window, sampling)   # pick_mover per bucket (reversed-CT)
                else:
                    pts = _nx.bucketed(tbl, col, window[0], window[1], sampling=sampling)
            except Exception:
                continue                                        # one dark/broken member never sinks the rolled series
            for pt in pts:
                t = pt.get("t")
                if t is not None:
                    by_t.setdefault(t, {}).setdefault(key, []).append(pt.get("value"))
    if not by_t:
        return []
    _folds = {"mean": _agg.mean, "maximum": _agg.maximum, "sum_magnitude": _agg.sum_magnitude}
    fold_of = {s["key"]: _folds.get((s.get("reduce") or "sum_magnitude").strip().lower(), _agg.sum_magnitude)
               for s in specs}
    r_of = {s["key"]: s.get("r") for s in specs}
    out = []
    for t in sorted(by_t):
        vals = {}
        for s in specs:
            k = s["key"]
            got = by_t[t].get(k)
            v = fold_of[k](got) if got else None
            if v is not None and r_of.get(k) is not None:
                v = round(v, r_of[k])
            vals[k] = v
        out.append({"t": t, "vals": vals})
    return out


def member_event_count(member, window, col, sampling="hourly"):
    """ONE member's windowed RISING-EDGE count for a boolean flag `col` — counted on the RAW rows (neuract.edge_count),
    so a register that flaps dozens of times an hour reports every real edge (the old hourly-AVG bucket loop collapsed
    any flapping flag to ~1 — the cards-18/22 zero-events defect). None when the column is absent / the table is empty
    (honest-null); a genuinely quiet flag over a present column → 0 (a real, honest zero — never a fabricated bar)."""
    tbl = member.get("table")
    if not tbl or not col:
        return None
    try:
        start, end = (window or (None, None))
        return _nx.edge_count(tbl, col, start, end)
    except Exception:
        return None


def _paired_present(tbl, col):
    """True when a paired-import column's EXPORT twin physically exists on the table (the import register may be absent
    while the reversed-CT export register carries the real energy)."""
    export_col = register_pairs().get(col)
    return bool(export_col and export_col in _nx.present_columns(tbl))


