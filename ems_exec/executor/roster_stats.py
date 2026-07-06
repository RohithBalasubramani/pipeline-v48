"""ems_exec/executor/roster_stats.py — HONEST LEAF TELEMETRY for the roster interpreter. One concern: after
run_roster fills the member-scope slots, count how many roster-written DATA leaves are real vs blank so the host's
render verdict can SEE them (the 2026-07-03 PCC-4 defect: the verdict scored only data_instructions.fields[].slot KPI
leaves → a card whose 23/28 consumer rows carried real kw/kwh was reported honest_blank real=0).

WHAT COUNTS AS A ROSTER DATA LEAF (mirrors what the interpreter itself writes — never the chrome):
    elements / groups / sections   the element keys bound by a COLUMN-READING op (col / delta / phase_mean /
                                   prefer_abs, incl. the bare-string col shorthand) on every written element,
                                   plus every non-const group_agg / section_agg reducer key per group/section.
    aggregates                     every non-const reducer key merged onto the slot dict.
    series                         the array itself (ONE leaf: real iff non-empty).
    sankey_match                   every nodes[].value + links[].value under the slot.
    const / unknown                chrome — never counted.
blank = None / '—' / '' / [] (counted BEFORE the host's display-dash policy runs, same as the declared-slot verdict).

The stats ride on the completed payload under RESERVED_KEY (the host pops it off before the FE sees the payload) —
telemetry only, NEVER a render gate (per-leaf degradation stands). [atomic; pure scan; never raises]
"""
from __future__ import annotations

RESERVED_KEY = "_roster_stats"

_DATA_OPS = {"col", "delta", "phase_mean", "prefer_abs"}


def attach(payload, state):
    """Compute (real, data) over every roster-written data leaf of `payload` and stash it at payload[RESERVED_KEY].
    No-op on any failure (telemetry must never take down a card)."""
    try:
        real, data = stats(payload, state)
        if isinstance(payload, dict) and data:
            payload[RESERVED_KEY] = {"real": real, "data": data}
    except Exception:
        pass


def stats(payload, state):
    """(n_real, n_data) across every slot instruction of the prepared roster state."""
    real = data = 0
    if not isinstance(payload, dict) or not isinstance(state, dict):
        return 0, 0
    for spec in state.get("roster") or []:
        if not isinstance(spec, dict):
            continue
        try:
            r, d = _slot_stats(payload, spec)
        except Exception:
            continue
        real += r
        data += d
    return real, data


def pop(payload):
    """Remove + return the attached stats dict ({real, data} or None) — the host's serve-boundary read."""
    if isinstance(payload, dict):
        return payload.pop(RESERVED_KEY, None)
    return None


# ── per-slot counting ─────────────────────────────────────────────────────────────────────────────────────────────
def _slot_stats(payload, spec):
    mode = (spec.get("mode") or "").strip().lower()
    values = _values_at(payload, spec.get("slot"))
    real = data = 0
    if mode == "elements":
        keys = _value_keys(spec.get("element"))
        for node in values:
            for el in (node if isinstance(node, list) else []):
                r, d = _count_keys(el, keys)
                real += r; data += d
    elif mode == "groups":
        el_keys = _value_keys(spec.get("element"))
        agg_keys = _reducer_keys(spec.get("group_agg"))
        list_key = spec.get("list_key")
        for node in values:
            for g in (node if isinstance(node, list) else []):
                if not isinstance(g, dict):
                    continue
                r, d = _count_keys(g, agg_keys)
                real += r; data += d
                for el in (g.get(list_key) or []) if list_key else []:
                    r, d = _count_keys(el, el_keys)
                    real += r; data += d
    elif mode == "aggregates":
        agg_keys = _reducer_keys(spec.get("agg"))
        for node in values:
            r, d = _count_keys(node, agg_keys)
            real += r; data += d
    elif mode == "scalar":
        # ONE reducer written straight to a scalar leaf — the slot value IS the data leaf (unless a const reducer)
        if isinstance(spec.get("agg"), dict) and (spec["agg"].get("agg") or "").strip().lower() != "const":
            for node in values:
                data += 1
                if not _blank(node):
                    real += 1
    elif mode == "sections":
        el_keys = _value_keys(spec.get("element"))
        agg_keys = _reducer_keys(spec.get("section_agg"))
        elements_key = spec.get("elements_key")
        for node in values:
            for entry in _section_entries(node, spec):
                r, d = _count_keys(entry, agg_keys)
                real += r; data += d
                for el in (entry.get(elements_key) or []) if elements_key else []:
                    r, d = _count_keys(el, el_keys)
                    real += r; data += d
    elif mode == "series":
        for node in values:
            if isinstance(node, list):
                data += 1
                if node:
                    real += 1
    elif mode == "series_split":
        # MULTI-SERIES per-bucket points ({t_key: label, <series key>: fold, …}). The DATA leaves are the declared
        # series-key values on every point (ups/bpdp/hhf …) — real iff non-blank; the t_key label is chrome (not counted).
        # A series whose match found no member honest-nulls that key on every point (counts data, not real). [series_split gap fix]
        skeys = [s.get("key") for s in (spec.get("series") or []) if isinstance(s, dict) and s.get("key")]
        for node in values:
            for pt in (node if isinstance(node, list) else []):
                r, d = _count_keys(pt, skeys)
                real += r
                data += d
    elif mode == "sankey_match":
        for node in values:
            if not isinstance(node, dict):
                continue
            for part in ("nodes", "links"):
                for item in (node.get(part) or []) if isinstance(node.get(part), list) else []:
                    if isinstance(item, dict) and "value" in item:
                        data += 1
                        if not _blank(item.get("value")):
                            real += 1
    return real, data


def _section_entries(node, spec):
    """The section-entry dicts, whichever wrap shape the recipe declared (bare list / one wrapped sample)."""
    if not isinstance(node, list):
        return []
    if spec.get("wrap_sample") is False:
        return [e for e in node if isinstance(e, dict)]
    key = spec.get("sections_key") or "sections"
    out = []
    for sample in node:
        if isinstance(sample, dict):
            out.extend(e for e in (sample.get(key) or []) if isinstance(e, dict))
    return out


def _value_keys(element_spec):
    """The element keys bound by a COLUMN-READING op — the only element leaves that are data (chrome/attr/const/null
    bindings never count)."""
    keys = []
    for k, b in (element_spec or {}).items():
        if isinstance(b, str):
            keys.append(k)                                     # bare-string shorthand = a col binding
        elif isinstance(b, dict) and (b.get("b") or "").strip().lower() in _DATA_OPS:
            keys.append(k)
    return keys


def _reducer_keys(agg_map):
    """Every non-const reducer key (a const is chrome, not a measured aggregate)."""
    return [k for k, a in (agg_map or {}).items()
            if isinstance(a, dict) and (a.get("agg") or "").strip().lower() != "const"]


def _count_keys(node, keys):
    real = data = 0
    if isinstance(node, dict):
        for k in keys:
            if k in node:
                data += 1
                if not _blank(node.get(k)):
                    real += 1
    return real, data


def _blank(v):
    return v is None or v == "—" or v == "" or v == []


# ── read-only slot-path resolution — the ONE home (roster_paths.values_at: the SAME addressing as the mutating
#    _targets walk, but NEVER mutates — telemetry must not alter the served payload) ────────────────────────────────
from ems_exec.executor.roster_paths import values_at as _values_at  # noqa: E402
