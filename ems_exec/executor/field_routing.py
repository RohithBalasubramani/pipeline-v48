"""ems_exec/executor/field_routing.py — the PRE-PASS field-routing PLAN for fill() [monoliths F6, 2026-07-12].

fill() used to re-derive the family-shape classification inline (wildcard split collection, single-index series
promotion, per-index family grouping + metric-homogeneity) — knowledge whose primitives live in wildcards.py /
indexed_families.py; that split-brain already caused one live defect (card-58: a literal kind=='bucketed' gate vs
is_series_family_field). The GROUPING/PROMOTION decisions now live here in one home; fill() consumes the plan and
performs the fills (the wildcard grow + the family fill stay in fill's body — this module DECIDES, never writes).

TWO phases, not one, on purpose: the original inline order was collect+promote → _fill_wildcard_arrays (which
MUTATES out, growing arrays) → family grouping (whose _scalar_point_slot probes out). A single plan() call would
move the family grouping BEFORE the grow — a silent evaluation-order change. plan_wildcards()/plan_families()
preserve the original order byte-for-byte around the grow.

[atomic; pure classification — no DB read, no payload write]"""
from __future__ import annotations

from ems_exec.executor.wildcards import _split_wildcard
from ems_exec.executor.indexed_families import _split_indexed, _scalar_point_slot, is_series_family_field


def plan_wildcards(fields, out, default_payload):
    """(wild_fields, promoted_ids) — the wildcard array-grow pre-pass members.

    wild_fields: [(field, array_path, elem_key), …] = every true `<array>[*].<key>` slot [composite cards 56/59]
    PLUS the SINGLE-INDEX SERIES PROMOTIONS [card 73 false-blank, Family C]: Layer 2 sometimes fans a per-bucket
    trend into `<array>[0].<key>` fields — several DISTINCT keys ALL at index 0 (buckets[0].active/reactive/
    apparent/pf) — meaning "grow this array across the bucket axis; each bucket's <key> ← its column's bucketed
    value". A `kind='bucketed'` (series) field pointed at a SCALAR per-bucket element is a series, not a scalar.
    The per-index family pre-pass only fires on ≥2 SAME-key fields (sparkline[0..29].loadPct — point i ← series i);
    DISTINCT-key SOLO fields would fall to the scalar loop, which crams the WHOLE ordered series into
    element[0].<key> (chart geometry destroyed) or blanks it when the array is empty — yet maxY still computes from
    the same column (proving the frame carried data), so the trend FALSE-BLANKS. Route ONLY the SOLO single-index
    fields (their (array,key) group has exactly one member — NOT a same-key sparkline family) through the SAME
    wildcard array-grow as `[*]`. Generic — array/key from the slot, no card ids; a genuinely null bucket → honest
    None. promoted_ids = {id(field), …} so the family grouping + scalar loop skip the promoted fields."""
    wild_fields = []
    for f in fields:
        sp = _split_wildcard(f.get("slot"))
        if sp:
            wild_fields.append((f, sp[0], sp[1]))
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
    return wild_fields, promoted_ids


def plan_families(fields, out, default_payload, promoted_ids):
    """{(array_path, elem_key): [(field, idx), …]} — the ≥2-member, METRIC-HOMOGENEOUS per-index series families
    _fill_indexed_families fans from ONE shared series (point i ← bucket i, end-aligned) [card 58 sparkline].

    ROUTES on is_series_family_field (not the literal kind=='bucketed'): the LIVE card-58 emit fans the sparkline
    into `kind='derived'` per-point fields (fn='loadFactorPct') — a literal 'bucketed' gate excluded them so all 30
    fell to the scalar loop and BROADCAST one window value. The predicate accepts both bucketed points and
    per-bucket derived points, while still returning False for the paired kind='time'/'const' label/axis leaf.
    Fields PROMOTED to the wildcard array-grow are excluded (they are grown, not indexed). A genuine per-bucket
    SERIES binds ONE metric/fn across ALL its points; DISTINCT-metric siblings are NOT a time series (card-72
    energyReliability.cells[0]=active / [1]=reactive / [2]=apparent are separate KPIs sharing an array+key —
    fanning one bucketed series across them blanks the real active 24h delta), so a mixed-metric group falls
    through to the scalar loop and each KPI fills (or honest-blanks) on its own."""
    idx_groups = {}
    for f in fields:
        if not is_series_family_field(f) or _split_wildcard(f.get("slot")):
            continue
        if id(f) in promoted_ids:
            continue
        sp = _split_indexed(f.get("slot"))
        if sp and _scalar_point_slot(out, default_payload, f.get("slot")):
            idx_groups.setdefault((sp[0], sp[2]), []).append((f, sp[1]))

    def _homogeneous_series(members):
        sig = {((f.get("metric") or "").strip().lower(), (f.get("fn") or "").strip().lower()) for f, _ in members}
        return len(sig) == 1

    return {k: v for k, v in idx_groups.items() if len(v) >= 2 and _homogeneous_series(v)}
