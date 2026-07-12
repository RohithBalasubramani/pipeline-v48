"""layer2/gates/roster.py — gate_roster: recipe-authoritative roster validation/normalization."""
from layer2.gates.basket import _bindable


def _gate_section_split(i, r, s, real):
    """Validate ONE sanctioned section-overlay split (see the call-site note). Returns (ok, issues, normalized_slot).
    The normalized slot is built RECIPE-FIRST: window/sampling/role_filter/t_key/label keys ship from the recipe; the
    AI contributes ONLY the series list (key + sections match + an optional recipe-or-basket column)."""
    issues = []
    recipe_cols = set()
    if s.get("column"):
        recipe_cols.add(s["column"])
    for c in (s.get("columns") or []):
        if isinstance(c, dict) and c.get("column"):
            recipe_cols.add(c["column"])
    series_norm = []
    for j, sd in enumerate(r.get("series") or []):
        if not isinstance(sd, dict) or not sd.get("key"):
            issues.append(f"roster[{i}].series[{j}] missing key"); continue
        match = sd.get("match")
        secs = (match or {}).get("sections") if isinstance(match, dict) else None
        if not (isinstance(match, dict) and list(match.keys()) == ["sections"]
                and isinstance(secs, list) and secs and all(isinstance(x, str) for x in secs)):
            issues.append(f"roster[{i}].series[{j}] match must be exactly {{'sections': [...]}}"); continue
        col = sd.get("column") or s.get("column")
        if not col:
            issues.append(f"roster[{i}].series[{j}] names no column"); continue
        if col not in recipe_cols and col not in real:
            issues.append(f"roster[{i}].series[{j}] column {col!r} not recipe/basket-real"); continue
        series_norm.append({"key": str(sd["key"]), "match": {"sections": [str(x) for x in secs]}, "column": col})
    if not series_norm or issues:
        return False, issues, None
    norm = {k: s[k] for k in ("slot", "scope", "role_filter", "sampling", "t_key", "label_key", "label_fmt",
                              "range", "null_value") if k in s}
    norm.update(mode="series_split", series=series_norm)
    if "column" in s:
        norm["column"] = s["column"]
    return True, issues, norm

def _section_overlay(normalized, toks):
    """★ SECTION-COMPARE OVERLAY GUARANTEE [sections]: the prompt DETERMINISTICALLY compares bus sections of this
    panel (1b compare_sections stamp → the caller's `sections` tokens), so every shipped series-family slot renders
    PER SECTION: the recipe's own `columns` entries are duplicated per token (key '<base>_<a|b>', match
    {'sections':[tok]}, `_base`/`_section` markers for the pres synthesis) and elements slots gain the member's own
    section attr. Applied AFTER validation/backfill so it composes with whatever the AI emitted (an AI-authored
    series_split ships untouched; an already-matched key is never re-split); BASE keys stay in the data — when the
    pres synthesis finds nothing to patch the card renders exactly as today (render-safe). Slots with `derived`
    stay untouched (their sums reference base keys). Recipe-derived + dictionary tokens only — zero card knowledge."""
    out = []
    for s in normalized:
        if not isinstance(s, dict):
            out.append(s); continue
        mode = s.get("mode")
        # `section_split` CAPABILITY FLAG (DB fact, per recipe slot): several CMD_V2 charts map series through a CLOSED
        # accessor vocabulary (EventTimelineCard's stackValueFor knows exactly sag/swell/current/neutral) — a variant
        # key there is `value: undefined` → an SSR crash, verified live. Only a slot whose recipe row declares
        # "section_split": true (its component maps series generically, or the host ships a sections-aware wrapper)
        # gets the per-section columns split; unflagged slots keep the union render (honest, crash-free).
        if (mode == "series" and s.get("section_split") and isinstance(s.get("columns"), list)
                and s["columns"] and not s.get("derived")):
            cols = list(s["columns"])
            for c in s["columns"]:
                if not (isinstance(c, dict) and c.get("key")) or c.get("match"):
                    continue
                for tok in toks:
                    cols.append({**c, "key": f"{c['key']}_{str(tok)[-1].lower()}",
                                 "match": {"sections": [tok]}, "_base": c["key"], "_section": tok})
            out.append({**s, "columns": cols})
        elif mode == "elements":
            el = {k: v for k, v in (s.get("element") or {}).items()}
            el.setdefault("section", {"a": "section", "b": "attr"})
            out.append({**s, "element": el})
        else:
            out.append(s)
    return out


def gate_roster(roster, roster_spec, basket, sections=None):
    """Validate + normalize data_instructions.roster against the card's card_fill_recipe row. [package §2d]

    Returns (ok, issues, normalized_roster). The recipe row is AUTHORITATIVE — the AI's ONLY authority is the COLUMN
    inside a col/delta/phase_mean/prefer_abs binding (each named column must exist VERBATIM in the basket); slot paths,
    element keys, role_filter/group_by/order/caps and reducers/floors are FIXED by the recipe. VALIDATION, not
    correction: a non-conforming part is reported (telemetry) and the recipe truth ships in its place; a clean column
    choice is folded in. Recipe slots the AI omitted are appended verbatim (deterministic fail-open, META-08 pattern),
    so an AI that emits no roster still ships the full recipe-derived roster — per-leaf degradation, never a blank card."""
    real, _failed = _bindable(basket)          # validate-FAIL columns are unbindable here too (pre-L2 verdict)
    spec_slots = {s.get("slot"): s for s in (roster_spec or {}).get("slots") or [] if isinstance(s, dict)}
    issues, normalized = [], []
    if roster and not spec_slots:
        return False, ["roster emitted for a card with no roster recipe"], []
    for i, r in enumerate(roster or []):
        if not isinstance(r, dict):
            issues.append(f"roster[{i}] is not an object"); continue
        s = spec_slots.get(r.get("slot"))
        if s is None:
            issues.append(f"roster[{i}] slot {r.get('slot')!r} not in card recipe"); continue
        # ★ SANCTIONED SECTION-OVERLAY SPLIT [sections]: a series-family recipe slot may be re-emitted as
        # mode='series_split' with one series PER BUS SECTION — the ONE AI-authored structural deviation (prompt ★ rule:
        # the user compared bus sections of this panel). VALIDATION stays strict: every series match must be EXACTLY a
        # {'sections': [...]} selector (dictionary lookup — an unknown section rolls zero members → honest nulls, never
        # invented data); every named column must be the recipe's own or basket-real; the recipe's window/sampling/
        # role_filter/t_key ship verbatim (the AI cannot move them). Everything else about the slot stays recipe truth.
        if (r.get("mode") == "series_split" and s.get("mode") in ("series", "columns")
                and isinstance(r.get("series"), list) and r.get("series")):
            ok_split, split_issues, split_norm = _gate_section_split(i, r, s, real)
            issues += split_issues
            if ok_split:
                normalized.append(split_norm)
            else:
                normalized.append(dict(s))                     # non-conforming split → the recipe truth ships
            continue
        if r.get("scope") not in (None, "members"):
            issues.append(f"roster[{i}] bad scope {r.get('scope')!r}")
        for k in ("role_filter", "group_by", "order"):
            if r.get(k) not in (None, s.get(k)):
                issues.append(f"roster[{i}] {k}={r.get(k)!r} != recipe {s.get(k)!r}")
        if r.get("cap") is not None and s.get("cap") is not None and r["cap"] > s["cap"]:
            issues.append(f"roster[{i}] cap {r['cap']} > recipe cap {s['cap']}")
        # element: keys ⊆ recipe keys; a recipe honest-null key STAYS null; every named column ∈ basket (verbatim-real)
        merged = {k: (dict(v) if isinstance(v, dict) else v) for k, v in (s.get("element") or {}).items()}
        for k, v in (r.get("element") or {}).items():
            if k not in merged:
                # ★ SANCTIONED 'section' element key [sections]: an ADDED element key is allowed ONLY when it is the
                # member's own bus-section attr binding VERBATIM ({'a':'section','b':'attr'}) — pure member metadata,
                # nothing inventable. Every other added key stays rejected.
                if k == "section" and isinstance(v, dict) and v.get("b") == "attr" and v.get("a") == "section":
                    merged[k] = dict(v)
                    continue
                issues.append(f"roster[{i}].element key {k!r} not in recipe (invented)"); continue
            b = {"b": "col", "c": v} if isinstance(v, str) else (v if isinstance(v, dict) else {})
            spec_b = merged[k] if isinstance(merged[k], dict) else {}
            if spec_b.get("b") == "null" and b.get("b") != "null":
                issues.append(f"roster[{i}].element {k!r} is honest-null in recipe; column binding rejected"); continue
            if b.get("c") == spec_b.get("c") and list(b.get("cs") or []) == list(spec_b.get("cs") or []):
                continue                                # verbatim repeat of the recipe's own binding = recipe truth
                # (member-scope columns live on MEMBER tables — the panel's own basket may not carry them; only a
                #  column the AI CHANGED is its decision, and THAT must be a real basket column below)
            bad = [c for c in ([b.get("c")] if b.get("c") else []) + list(b.get("cs") or []) if c not in real]
            if bad:
                issues += [f"roster[{i}].element {k!r} column {c!r} not in basket (hallucinated)" for c in bad]
                continue
            merged[k] = {**spec_b, **{kk: b[kk] for kk in ("c", "cs") if kk in b}}   # clean column choice folds in
        # reducers/floors are FIXED by the recipe — the AI may not move thresholds or invent aggregations
        for agg_key in ("agg", "group_agg", "section_agg"):
            _r_agg = r.get(agg_key)
            if not isinstance(_r_agg, dict):
                continue                                       # a string/list agg emission is normalized from the recipe, never indexed
            for k in _r_agg:
                if (s.get(agg_key) or {}).get(k) != _r_agg[k]:
                    issues.append(f"roster[{i}].{agg_key}[{k!r}] differs from recipe (thresholds/reducers are fixed)")
        norm = dict(s)                                          # recipe wins wholesale …
        if "element" in s:
            norm["element"] = merged                            # … with the AI's validated columns folded in
        normalized.append(norm)
    # backfill: recipe slots the AI omitted ship VERBATIM (deterministic fail-open — full roster even on emit failure)
    emitted = {r.get("slot") for r in (roster or []) if isinstance(r, dict)}
    normalized += [dict(s) for slot, s in spec_slots.items() if slot not in emitted]
    # ★ SECTION-COMPARE OVERLAY [sections]: prompt-fact-driven (see _section_overlay) — runs over the FULLY normalized
    # roster so backfilled slots split too (the guarantee holds even when the AI emitted nothing).
    if sections:
        normalized = _section_overlay(normalized, [str(t).strip().upper() for t in sections if t])
    # `_gated` stamp [single normalization home]: the executor's recipe.roster_for re-folds RAW emissions against the
    # recipe (defense for paths that bypass this gate) — that re-fold must NOT revert the gate's own sanctioned output
    # (section overlay / series_split). A stamped slot is trusted verbatim downstream.
    for s in normalized:
        if isinstance(s, dict):
            s["_gated"] = True
    return (not issues), issues, normalized
