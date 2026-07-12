"""ems_exec/executor/roster_gaps.py — PER-LEAF HONEST-GAP RECORDS for the roster interpreter. One concern: after
run_roster fills the member-scope slots, every roster-written DATA leaf that stayed BLANK gets a gap record on the
same honest-gap reason channel fill.py rides (GAPS_KEY → host render.gaps), so a roster card never ships a bare '—'
without a per-leaf reason (the 2026-07-06 card-12 defect: render.gaps=null while 22 roster leaves were blank).

Mirrors roster_stats' read-only slot addressing (the SAME closed mode vocabulary — never mutates), and adds the two
leaf families roster_stats deliberately does NOT count as data:
  · a recipe HONEST-NULL binding ({"b":"null","why":…} element/group keys) — blank BY DESIGN; the record carries the
    recipe row's own `why` sentence verbatim (the DB-authored truth: 'no per-feeder rated capacity on gic_*');
  · a const-null reducer ({"agg":"const","v":null,"why":…}) — same: the recipe's why IS the reason.
Ordinary blank data leaves (a member column with no reading, an alias of a blank sibling) read cause 'no_reading'
via the editable cmd_catalog.reason_template rows — no hardcoded prose beyond the DB fallback.

collect(payload, state, existing=None) → [records]; deduped against `existing` by slot path; capped by the app_config
row reasons.max_roster_records (default 80). Telemetry only — never raises, never gates a render. [atomic]
"""
from __future__ import annotations

from ems_exec.executor import roster_stats as _rs
from ems_exec.executor import blank as _blank_mod


def _cap():
    try:
        from config.app_config import cfg
        return int(cfg("reasons.max_roster_records", 80))
    except Exception:
        return 80


def _sentence(cause, metric):
    try:
        from config.reason_templates import reason as _reason
        return _reason(cause, metric=metric)
    except Exception:
        return cause


def _blank(v):
    return _blank_mod.is_blank(v, empty_list=True)   # scalars + the honest-empty [] [shared predicate: executor.blank]


def _rec(slot, cause, metric, *, reason=None, column=None, fn=None):
    return {"slot": slot, "cause": cause, "metric": str(metric), "column": column, "fn": fn,
            "reason": reason or _sentence(cause, str(metric))}


def _null_why(binding):
    """(is_honest_null, why) for a recipe element/group binding."""
    if isinstance(binding, dict) and (binding.get("b") or "").strip().lower() == "null":
        return True, binding.get("why")
    return False, None


def _null_keys(spec_map):
    """[(key, why)] for the recipe's honest-null bindings in an element/group spec map."""
    out = []
    for k, b in (spec_map or {}).items():
        is_null, why = _null_why(b)
        if k and is_null:
            out.append((k, why))
    return out


def _label_of(node, fallback):
    if isinstance(node, dict):
        for k in ("label", "panel", "name", "id"):
            v = node.get(k)
            if isinstance(v, str) and v.strip():
                return v
    return fallback


def collect(payload, state, existing=None):
    """Every blank roster-written data leaf of `payload` → one gap record (deduped, capped). Never raises."""
    out = []
    try:
        seen = {str(g.get("slot")) for g in (existing or []) if isinstance(g, dict) and g.get("slot")}
        cap = _cap()
        if not isinstance(payload, dict) or not isinstance(state, dict):
            return out

        def add(rec):
            if len(out) >= cap or rec["slot"] in seen:
                return
            seen.add(rec["slot"])
            out.append(rec)

        for spec in state.get("roster") or []:
            if not isinstance(spec, dict):
                continue
            try:
                _slot_gaps(payload, spec, add)
            except Exception:
                continue
    except Exception:
        return out
    return out


def _slot_gaps(payload, spec, add):
    mode = (spec.get("mode") or "").strip().lower()
    slot = spec.get("slot") or ""
    base = slot.replace("[]", "").replace("[*]", "")
    values = _rs._values_at(payload, slot)

    if mode == "groups":
        el_keys = _rs._value_keys(spec.get("element"))
        agg_keys = _rs._reducer_keys(spec.get("group_agg"))
        null_group = _null_keys(spec.get("group"))
        null_el = _null_keys(spec.get("element"))
        list_key = spec.get("list_key")
        for node in values:
            for i, g in enumerate(node if isinstance(node, list) else []):
                if not isinstance(g, dict):
                    continue
                label = _label_of(g, f"{base}[{i}]")
                for k in agg_keys:
                    if k in g and _blank(g.get(k)):
                        add(_rec(f"{base}[{i}].{k}", "no_reading", label))
                for k, why in null_group:
                    if k in g and _blank(g.get(k)):
                        add(_rec(f"{base}[{i}].{k}", "column_absent", label, reason=why))
                for el_i, el in enumerate((g.get(list_key) or []) if list_key else []):
                    if not isinstance(el, dict):
                        continue
                    el_label = _label_of(el, label)
                    for k in el_keys:
                        if k in el and _blank(el.get(k)):
                            add(_rec(f"{base}[{i}].{list_key}[{el_i}].{k}", "no_reading", el_label))
                    for k, why in null_el:
                        if k in el and _blank(el.get(k)):
                            add(_rec(f"{base}[{i}].{list_key}[{el_i}].{k}", "column_absent", el_label, reason=why))

    elif mode == "elements":
        el_keys = _rs._value_keys(spec.get("element"))
        null_el = _null_keys(spec.get("element"))
        for node in values:
            for i, el in enumerate(node if isinstance(node, list) else []):
                if not isinstance(el, dict):
                    continue
                label = _label_of(el, f"{base}[{i}]")
                for k in el_keys:
                    if k in el and _blank(el.get(k)):
                        add(_rec(f"{base}[{i}].{k}", "no_reading", label))
                for k, why in null_el:
                    if k in el and _blank(el.get(k)):
                        add(_rec(f"{base}[{i}].{k}", "column_absent", label, reason=why))

    elif mode == "aggregates":
        aggs = spec.get("agg") or {}
        for node in values:
            if not isinstance(node, dict):
                continue
            for k, aspec in aggs.items():
                if not isinstance(aspec, dict) or k not in node or not _blank(node.get(k)):
                    continue
                is_const = (aspec.get("agg") or "").strip().lower() == "const"
                # a const-null reducer is blank BY RECIPE — the row's own why is the reason (never unreasoned)
                add(_rec(f"{base}.{k}", "column_absent" if is_const else "no_reading", k, reason=aspec.get("why")))

    elif mode == "scalar":
        aspec = spec.get("agg") if isinstance(spec.get("agg"), dict) else {}
        if (aspec.get("agg") or "").strip().lower() != "const":
            for node in values:
                if _blank(node):
                    add(_rec(base, "no_reading", base.split(".")[-1], reason=aspec.get("why")))

    elif mode == "sankey_match":
        for node in values:
            if not isinstance(node, dict):
                continue
            for part in ("nodes", "links"):
                items = node.get(part)
                for i, item in enumerate(items if isinstance(items, list) else []):
                    if isinstance(item, dict) and "value" in item and _blank(item.get("value")):
                        label = _label_of(item, f"{part}[{i}]")
                        add(_rec(f"{base}.{part}[{i}].value", "no_reading", label))

    elif mode in ("series", "series_split"):
        skeys = [s.get("key") for s in (spec.get("series") or []) if isinstance(s, dict) and s.get("key")]
        for node in values:
            if mode == "series" and isinstance(node, list) and not node:
                add(_rec(base, "no_reading", base.split(".")[-1]))
            for i, pt in enumerate(node if isinstance(node, list) else []):
                if not isinstance(pt, dict):
                    continue
                for k in skeys:
                    if k in pt and _blank(pt.get(k)):
                        add(_rec(f"{base}[{i}].{k}", "no_reading", k))
