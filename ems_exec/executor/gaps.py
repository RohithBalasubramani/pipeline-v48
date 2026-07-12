"""ems_exec/executor/gaps.py — THE HONEST-GAP REASON CHANNEL: WHY each declared leaf blanked. Telemetry rides the
completed payload under GAPS_KEY (the host pops it at the serve boundary → render.reason / render.gaps; never a FE
prop, NEVER a render gate). Machine cause keys are cmd_catalog.reason_template rows (column_absent / structurally_null
/ derivation_unbound / no_nameplate / no_reading) — the human sentence is the editable DB template, no hardcoded prose
here. 'no_reading' = a PRESENT + LOGGED column/derivation whose current leaf has no valid reading (honest, NEVER
'below valid range' on real in-range/idle-zero data — real 0/tiny now pass _verify so those leaves fill instead).
One concern; fill.py re-exports byte-compatibly. [atomic]
"""
from __future__ import annotations

from ems_exec.data import neuract as _nx
from config import nameplates as _np
from config import nameplate_slot_map as _slot_map
from config import derivation_binding as _deriv
from ems_exec.executor.paths import _toks, _has_path, _leaf_at
from ems_exec.executor import blank as _blank
from ems_exec.executor.derived import _derived_key
from ems_exec.executor.series_fill import _element_value_key

GAPS_KEY = "_blank_gaps"


def pop_gaps(payload):
    """Remove + return the attached per-leaf gap list ([{slot, cause, metric, column, fn, reason}] or None) — the
    host's serve-boundary read (mirror of roster_stats.pop)."""
    if isinstance(payload, dict):
        return payload.pop(GAPS_KEY, None)
    return None


def _blank_val(v):
    """A leaf value that carries NO real data: None/'—'/'' scalars, and an empty or ALL-None series array (a bucketed
    read over a present-but-never-logged column returns [None]*n — as blank as []). [shared predicate: executor.blank]"""
    return _blank.is_blank(v, all_none_list=True)


def _gap_of(field, asset_table, present_cols, latest_row, asset_name=None):
    """Classify WHY one declared field blanked → (cause, params). Pure lookup against what the executor already knows
    (declared column vs the meter's present columns, the derivation's cmd_catalog binding, the real nameplate) — a
    GENUINE domain gap (no measuring column) reads column_absent; a schema column that never logs reads
    structurally_null; a missing derivation binding reads derivation_unbound. Never raises, never fabricates."""
    kind = (field.get("kind") or "raw").lower()
    col = field.get("column")
    metric = field.get("label") or field.get("metric") or col or field.get("slot") or "value"
    if kind == "derived" and (field.get("fn") or field.get("metric")):
        key = _derived_key(field)
        # FAB-BY-MISLABEL (Family G, card 72): the leaf blanked because the bound fn MEASURES a different polarity than
        # the slot means (active-energy fn on a reactive-energy slot). Say so honestly — never 'no valid reading' on a
        # column that DID have a reading (it was the wrong quantity). Matches the executor's _polarity_conflict guard.
        try:
            from ems_exec.executor.verify import _polarity_conflict as _pc
            if _pc(field, key):
                return "quantity_mismatch", {"metric": metric}
        except Exception:
            pass
        b = _deriv.binding(key) if key else None
        if not b:
            return "derivation_unbound", {"metric": metric, "fn": key or field.get("fn")}
        base = b.get("base_columns") or []
        frame = [c for c in base if not c.startswith("nameplate:")]
        absent = [c for c in frame if c not in present_cols]
        if absent:
            return "column_absent", {"metric": ", ".join(absent)}
        if "nameplate:rated_kva" in base and (_np.get_nameplate(asset_table) or {}).get("rated_kva") is None:
            return "no_nameplate", {"asset": asset_name or asset_table or "this asset"}
        # F7: only the base columns that are genuinely 100% NULL are "not logged"; a base col that IS logged (but the
        # window/latest produced no derivable value) failed the derivation's inputs, not the meter's logging — never
        # claim a live base column is unlogged. If EVERY frame base col is logged, the input is present-but-unusable.
        unlogged = [c for c in frame if not _nx.column_logged(asset_table, c)]
        if unlogged:
            return "structurally_null", {"metric": ", ".join(unlogged)}
        return "no_reading", {"metric": ", ".join(frame) or metric}
    if kind in ("const", "text"):
        rk = _slot_map.rating_key_for(field.get("slot")) or _slot_map.rating_key_for(field.get("metric"))
        if rk:
            return "no_nameplate", {"asset": asset_name or asset_table or "this asset"}
        return "column_absent", {"metric": metric}                # nothing measures this quantity (no column bound)
    # raw / bucketed / event — column-reading kinds
    if not (col and col in present_cols):
        return "column_absent", {"metric": col or metric}
    # F7 [leaf-reason-must-not-contradict-DB]: the meter DOES carry this column and it HAS non-null rows → it is logged.
    # The blank is not "not logged" — it is a value that failed the validity gates (denorm clamp / idle-zero) or a window
    # with no rows. Reserve structurally_null ("not logged by this meter") ONLY for a column that is 100% NULL in the DB.
    # The check is a direct neuract read (cached), NEVER the possibly-incomplete latest_row cache (a bucketed/event col is
    # not preloaded into latest_row, so trusting it mislabeled a live column as unlogged).
    if _nx.column_logged(asset_table, col):
        return "no_reading", {"metric": col}                      # column is logged; this leaf simply has no valid reading
    return "structurally_null", {"metric": col}


def _gap_sentence(cause, params):
    """The human sentence for a cause — the editable cmd_catalog.reason_template row (config.reason_templates). On a
    DB outage fall back to the machine cause key itself (the channel is never empty, never fabricated)."""
    try:
        from config.reason_templates import reason as _reason
        return _reason(cause, **params)
    except Exception:
        return cause


def _sentence(cause, params):
    """Render the sentence THROUGH the fill facade attribute (fill._gap_sentence) so the existing test seam — tests
    monkeypatch `fill._gap_sentence` — still lands on every internal caller; falls back to the local renderer."""
    import sys
    f = sys.modules.get("ems_exec.executor.fill")
    fn = getattr(f, "_gap_sentence", None) if f is not None else None
    return (fn if fn is not None else _gap_sentence)(cause, params)


def _prune_stale_gaps(out, gaps):
    """Drop gap records whose leaf a LATER pass filled real (yscale derives minY/maxY from the series AFTER the field
    loop blanked them; the roster overwrites emit-blanked member slots) — a reason must describe the SERVED payload,
    never a mid-pipeline state. A record whose slot cannot be resolved is kept (unverifiable ≠ stale)."""
    kept = []
    for g in gaps:
        s = g.get("slot")
        resolved, leaf = False, None
        for cand in (s, f"data.{s}" if s else None):
            if cand and _has_path(out, cand):
                resolved, leaf = True, _leaf_at(out, cand)
                break
        if resolved and not _blank_val(leaf):
            continue                                            # filled after the field loop → the gap is stale
        kept.append(g)
    return kept


def _attach_unbound_gaps(out, sources, gaps):
    """REASONS-ALWAYS completion scan [cards 63/79/48]: EVERY data leaf still blank after the whole fill+roster+display
    pipeline carries a per-leaf reason record — a blank the declared fields explained already has one; a blank NO field
    ever declared (di.fields=[] on card 63, the emit-unbound 'Worst Spread' on card 79, an empty default view's series
    on card 48) gets an 'unbound_by_emit' record here, so the host's render.gaps never shows a bare '—'.

    Data-leaf discovery is SHAPE-DRIVEN: validate.leaf_classify over the INPUT skeleton and the HARVESTED DEFAULT
    (the completed payload's blanks are None/'—' and classify as metadata — the placeholders live in the sources). A
    series-of-objects leaf is scanned per element on its value key (stats[i].value). Only leaves that are BLANK in the
    completed payload and NOT already explained are recorded; a record cap (config reasons.max_unbound_records) keeps a
    fully-dark card from flooding telemetry. Telemetry only — never raises, never gates the render."""
    try:
        from validate.leaf_classify import classify
    except Exception:
        return
    try:
        from config.app_config import cfg
        cap = int(cfg("reasons.max_unbound_records", 60))
    except Exception:
        cap = 60

    def _norm(toks):
        return toks[1:] if toks[:1] == ("data",) else toks

    leaves, seen = [], set()
    for src in sources:
        if not isinstance(src, dict):
            continue
        try:
            for d in classify(src).get("data_leaves") or []:
                p = d.get("path")
                key = _norm(tuple(_toks(p))) if p else None
                if key and key not in seen:
                    seen.add(key)
                    leaves.append(d)
        except Exception:
            continue
    explained = {_norm(tuple(_toks(str(g.get("slot"))))) for g in gaps if g.get("slot")}
    n = 0
    for d in leaves:
        if n >= cap:
            break
        path = d.get("path") or ""
        if _norm(tuple(_toks(path))) in explained:
            continue
        v = _leaf_at(out, path)
        blanks = []                                             # (record_path, display_name)
        if isinstance(v, list) and v and all(isinstance(e, dict) for e in v):
            vk = _element_value_key(v[0])
            if vk:
                for i, el in enumerate(v):
                    if isinstance(el, dict) and _blank_val(el.get(vk)):
                        p2 = f"{path}[{i}].{vk}"
                        if _norm(tuple(_toks(p2))) not in explained:
                            blanks.append((p2, el.get("label") or el.get("id") or p2))
        elif _blank_val(v):
            blanks.append((path, _toks(path)[-1] if _toks(path) else path))
        for p2, name in blanks:
            if n >= cap:
                break
            gaps.append({
                "slot": p2,
                "cause": "unbound_by_emit",
                "metric": str(name),
                "column": None,
                "fn": None,
                "reason": _sentence("unbound_by_emit", {"metric": str(name)}),
            })
            n += 1

    # LABELED-TILE PROBE [card-12 kpi family]: a {label/title, value} tile whose value is BLANK in the SERVED payload
    # is a blank data leaf even when NO source could type-prove it (card 12's harvested default carries kpi.value=null,
    # so classify finds nothing on any source) — the label sibling IS the data contract (the same signal display_dash
    # and the numeric-string KPI rule use). Walked over the COMPLETED payload; explained/deduped/capped as above.
    try:
        from config.vocab import vocab as _vocab
        lkeys = {str(k).lower() for k in (_vocab("label_keys") or ())}
        vkeys = {str(k).lower() for k in (_vocab("value_keys") or ())}
    except Exception:
        lkeys, vkeys = set(), set()
    if lkeys and vkeys:
        found = []                                              # (path, label, value_key)

        def _probe(node, path):
            if isinstance(node, dict):
                label = next((node[k] for k in node
                              if str(k).lower() in lkeys and isinstance(node.get(k), str) and node[k].strip()), None)
                if label is not None:
                    for k, v in node.items():
                        if str(k).lower() in vkeys and (v is None or v == "—"):
                            found.append((f"{path}.{k}" if path else str(k), label))
                for k, v in node.items():
                    if isinstance(v, (dict, list)):
                        _probe(v, f"{path}.{k}" if path else str(k))
            elif isinstance(node, list):
                for i, el in enumerate(node):
                    if isinstance(el, (dict, list)):
                        _probe(el, f"{path}[{i}]")

        try:
            _probe(out, "")
        except Exception:
            found = []
        for p2, label in found:
            if n >= cap:
                break
            if _norm(tuple(_toks(p2))) in explained:
                continue
            explained.add(_norm(tuple(_toks(p2))))
            gaps.append({
                "slot": p2,
                "cause": "unbound_by_emit",
                "metric": str(label),
                "column": None,
                "fn": None,
                "reason": _sentence("unbound_by_emit", {"metric": str(label)}),
            })
            n += 1


def _note_gap(gaps, field, asset_table, present_cols, latest_row, asset_name=None):
    """Append ONE deduped gap record for a blanked declared field. Telemetry only — never raises."""
    try:
        cause, params = _gap_of(field, asset_table, present_cols, latest_row, asset_name=asset_name)
        key = (cause, params.get("metric"), field.get("fn"))
        if any((g.get("cause"), g.get("metric"), g.get("fn")) == key for g in gaps):
            return
        gaps.append({
            "slot": field.get("slot") or field.get("target_column") or field.get("metric"),
            "cause": cause,
            "metric": params.get("metric"),
            "column": field.get("column"),
            "fn": field.get("fn"),
            "reason": _sentence(cause, params),
        })
    except Exception:
        pass
