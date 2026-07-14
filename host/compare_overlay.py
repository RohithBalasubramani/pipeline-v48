"""host/compare_overlay.py — merge N per-comparand card payloads into ONE per-comparand card (the OVERLAY compare
mode). The GROUPS mode renders each panel as its own stacked dashboard (build_response_multi's default); OVERLAY
renders every card with all comparands INLINE — one strip whose KPIs read per panel, one timeline with a series per
panel, a per-panel radar rail, a panel-tagged table. Shape-general: it keys on the payload SHAPE (stats /
period.panels / points), NOT card ids, so it covers EVERY comparable card across all families with no per-card code.

It emits the SAME payload shape the bus-section overlay produces (stats.sections, sectionCompare, per-comparand
series + pres.sectionSplit), so the FE section-overlay renderers (per-section strip, EventTimelineSections,
SectionRadar, Sec-column table) render it unchanged and N-generically. [compare — overlay mode]
"""
import copy
import re


def comparand_token(name):
    """A SHORT comparand label from an asset name for the per-comparand tiles/legend/keys: 'PCC-Panel-1' → 'P1',
    'Transformer 2' → 'T2', else the first word. Kept short so a strip with 7 KPIs × N comparands stays readable."""
    s = str(name or "").strip()
    m = re.search(r"(\d+)\s*$", s)
    if m:
        head = re.sub(r"[^A-Za-z]", "", s.split("-")[-2] if "-" in s and s.split("-")[-2][:1].isalpha() else s)
        return (head[:1].upper() if head else "P") + m.group(1)
    return (s.split() or [s])[0][:6] or "?"


def _wider_tokens(name):
    """Progressively WIDER variants of comparand_token(name): the same token shape rebuilt with a LONGER alpha head
    from the name (head[:2], head[:3], ...), so a de-collided token still reads as its asset ('Pump-1' -> 'Pu1',
    'Pum1', 'Pump1'). Mirrors comparand_token's head extraction exactly; yields nothing when the head can't widen."""
    s = str(name or "").strip()
    m = re.search(r"(\d+)\s*$", s)
    if m:
        head = re.sub(r"[^A-Za-z]", "", s.split("-")[-2] if "-" in s and s.split("-")[-2][:1].isalpha() else s)
        for w in range(2, len(head) + 1):
            yield head[:1].upper() + head[1:w] + m.group(1)
        return
    word = (s.split() or [s])[0]
    for w in range(7, len(word) + 1):                        # comparand_token took word[:6]; widen past it
        yield word[:w]


def _suffixes():
    """'b', 'c', ..., 'z', 'bb', 'bc', ...: an inexhaustible tie-break stream for the pathological case where every
    widened head is also taken (identical names). Starts at 'b' -- the first holder keeps the bare token."""
    letters = "bcdefghijklmnopqrstuvwxyz"
    pool = [""]
    while True:
        pool = [p + ch for p in pool for ch in letters]
        for suf in pool:
            yield suf


def unique_comparand_tokens(named):
    """H1 fix [T0-4, deterministic_audit_20260714]: comparand_token is a per-name heuristic with NO uniqueness
    guarantee -- 'PCC-Panel-1' and 'Pump-1' both map to 'P1' -- and merge_overlay keys per-comparand payloads by
    token (per = {tok: ...}), so two same-token comparands OVERWRITE each other: one comparand's data silently
    vanishes from the merged overlay card. Uniqueness is a SET property, so it is enforced HERE where the whole
    comparand set is known; comparand_token itself stays untouched (single-name callers keep the short label).

    `named` = [(id, name), ...] in lane order; returns {id: token}, collision-free and deterministic in input
    order: first pass comparand_token(name); the FIRST holder keeps its token, and a collider is rebuilt with a
    WIDER alpha head from its OWN name ('Pump-1' beside 'PCC-Panel-1' becomes 'Pu1'); if every widening is also
    taken (identical names), 'b', 'c', ... is appended."""
    out, used = {}, set()
    for cid, name in named:
        tok = comparand_token(name)
        if tok in used:
            tok = next((c for c in _wider_tokens(name) if c not in used), tok)
        if tok in used:                                      # widening exhausted -> first free letter suffix
            tok = next(tok + suf for suf in _suffixes() if tok + suf not in used)
        out[cid] = tok
        used.add(tok)
    return out


def _tint(color, f):
    """`color` mixed toward white by factor f (per-comparand tone) — matches roster_pres_sections._tint."""
    try:
        c = str(color).strip()
        if not (c.startswith("#") and len(c) in (4, 7)):
            return color
        if len(c) == 4:
            c = "#" + "".join(ch * 2 for ch in c[1:])
        r, g, b = (int(c[i:i + 2], 16) for i in (1, 3, 5))
        mix = lambda v: max(0, min(255, int(round(v + (255 - v) * f))))
        return "#%02x%02x%02x" % (mix(r), mix(g), mix(b))
    except Exception:
        return color


def _subtree_key(payload):
    """The card's ONE data subtree ('strip'/'trend'/'distribution'/'table'/'summary') — the first dict key that is not
    chrome (widgets/variant/ai_summary). None for a card with no mergeable subtree (rendered as-is)."""
    for k, v in (payload or {}).items():
        if isinstance(v, dict) and k not in ("widgets", "variant", "ai_summary"):
            return k
    return None


def _merge_stats(sub, per, toks):
    """stats shape (strip / KPI aggregates): stats.sections = {tok: that comparand's stats}; the union stats keep an
    element-wise SUM across comparands (the strip's Total tile). The host per-section strip renders each KPI per tok."""
    sections, union = {}, {}
    for tok in toks:
        st = per[tok].get("stats") or {}
        sections[tok] = st
        for k, v in st.items():
            if isinstance(v, (int, float)):
                union[k] = (union.get(k) or 0) + v
    sub["stats"] = {**(sub.get("stats") or {}), **union, "sections": sections}


def _merge_panels(sub, per, toks):
    """period.panels shape (radar spokes / table rows / summary panels): concat every comparand's panels, TAG each with
    its comparand (`section`=tok, id namespaced) + stamp sectionCompare. The Sec-column table + SectionRadar consume it."""
    merged = []
    for tok in toks:
        _pp = per[tok].get("period")                          # a comparand whose period is a string label → no panels
        for p in ((_pp.get("panels") if isinstance(_pp, dict) else None) or []):
            if isinstance(p, dict):
                merged.append({**p, "section": tok, "id": "%s::%s" % (tok, p.get("id"))})
    sub.setdefault("period", {})["panels"] = merged
    sub["sectionCompare"] = list(toks)
    # TABLE Sec column (mirror roster_pres_sections._stamp_element_compare): a payload-keyed events column renders
    # each row's `section` (the comparand) — so a merged table SHOWS which panel each feeder belongs to. Radar/other
    # panels-cards have no eventModeOrder → untouched (they read the section attr directly).
    pres = sub.get("pres")
    if isinstance(pres, dict):
        emo, ec = pres.get("eventModeOrder"), pres.get("eventColumn")
        if isinstance(emo, list) and isinstance(ec, dict) and isinstance(ec.get("shortByMode"), dict) \
                and "section" not in emo:
            pres["eventModeOrder"] = ["section"] + list(emo)
            ec["shortByMode"] = {**ec["shortByMode"], "section": "Sec"}


def _merge_points(sub, per, toks):
    """points shape (timeline series): align comparand points by label into ONE point per bucket carrying every base
    series key PER comparand ('sag@@<tok>'), and rewrite the pres stack/line series+order per comparand (distinct tint,
    ' — <tok>' label, sectionSplit + showLegend). EventTimelineSections maps series by key generically. Comparands share
    the window here (same labels); a label only one comparand reported still lands (missing → None, honest gap)."""
    pts_by_tok = {tok: (per[tok].get("points") or []) for tok in toks}
    order, seen = [], set()
    for tok in toks:                                            # union of labels, first-seen order (comparands aligned)
        for p in pts_by_tok[tok]:
            lab = p.get("label")
            if lab not in seen:
                seen.add(lab); order.append(lab)
    base_pts = pts_by_tok[toks[0]]
    base_keys = [k for k in (base_pts[0].keys() if base_pts else []) if k != "label"]
    idx = {tok: {p.get("label"): p for p in pts_by_tok[tok]} for tok in toks}
    merged = []
    for lab in order:
        pt = {"label": lab}
        for tok in toks:
            src = idx[tok].get(lab) or {}
            for bk in base_keys:
                pt["%s@@%s" % (bk, tok)] = src.get(bk)
        merged.append(pt)
    sub["points"] = merged
    pres = dict(sub.get("pres") or {})
    for lk in ("stackSeries", "lineSeries"):
        base_list = pres.get(lk) or []
        if not base_list:
            continue
        rebuilt = []
        for e in base_list:
            for i, tok in enumerate(toks):
                rebuilt.append({**e, "key": "%s@@%s" % (e.get("key"), tok),
                                "label": "%s — %s" % (e.get("label"), tok),
                                "color": e.get("color") if i == 0 else _tint(e.get("color"), 0.30 + 0.22 * i)})
        pres[lk] = rebuilt
    for ok in ("stackOrder", "lineOrder"):
        base_ord = pres.get(ok) or []
        if base_ord:
            pres[ok] = ["%s@@%s" % (k, tok) for k in base_ord for tok in toks]
    pres["sectionSplit"] = True
    pres["showLegend"] = True
    pres["sectionCompare"] = list(toks)
    sub["pres"] = pres


def _side_by_side(entries):
    """The SIDE-BY-SIDE fallback [all-cards coverage]: a card whose payload has no inline-mergeable shape (a scalar KPI
    card, a gauge, a sankey, a closed-vocab line chart — inline-forcing a comparand series into those would crash the
    bespoke component or fake a comparison) carries every comparand's FULL payload under `_compare_group`; the FE
    renders the N per-comparand cards next to each other. Crash-safe (each renders its own unmodified component) and
    honest (each shows its own panel's real data) — so EVERY card compares, inline where clean, side-by-side else."""
    return [{"token": tok, "name": (card.get("asset") or {}).get("name"), "payload": (card.get("payload") or {})}
            for tok, card in entries]


def merge_overlay(entries, tokens):
    """entries: [(tok, card), …] for ONE render_card_id (one card per comparand). Returns the SINGLE merged card: inline
    per-comparand in the section-overlay shape when the payload has a mergeable shape (stats / period.panels / points —
    the shapes with sections-aware FE renderers), else the side-by-side `_compare_group` fallback. `asset` tag dropped
    so the FE renders it flat (not a group)."""
    base = entries[0][1]
    payload = copy.deepcopy(base.get("payload") or {})
    sk = _subtree_key(payload)
    out = {k: v for k, v in base.items() if k != "asset"}
    out["payload"] = payload
    sub = payload.get(sk) if sk else None
    merged_any = False
    if isinstance(sub, dict):
        per = {tok: ((card.get("payload") or {}).get(sk) or {}) for tok, card in entries}
        if isinstance(sub.get("stats"), dict):
            _merge_stats(sub, per, tokens); merged_any = True
        _period = sub.get("period")                            # a scalar card's period is a STRING label, not a dict —
        if isinstance(_period, dict) and isinstance(_period.get("panels"), list):   # guard like the stats/points sibs
            _merge_panels(sub, per, tokens); merged_any = True  # (was `(sub.get("period") or {}).get(...)` → crashed on str)
        if isinstance(sub.get("points"), list):
            _merge_points(sub, per, tokens); merged_any = True
    if not merged_any:
        out["_compare_group"] = _side_by_side(entries)         # no inline shape → side-by-side per comparand
    return out


def merge_all(cards, tokens_by_id):
    """Merge a flat multi-asset `cards` list (each tagged card.asset) into per-comparand overlay cards — one per
    render_card_id, in emit order. `tokens_by_id`: {asset_id: comparand_token}. Cards with no asset tag pass through."""
    from collections import OrderedDict
    groups = OrderedDict()
    for c in cards:
        rc = c.get("render_card_id")
        groups.setdefault(rc, []).append(c)
    merged = []
    for rc, entries in groups.items():
        tagged = [(tokens_by_id.get((e.get("asset") or {}).get("id")), e) for e in entries]
        tagged = [(t, e) for t, e in tagged if t is not None]
        if len(tagged) < 2:
            merged.append({k: v for k, v in entries[0].items()})     # not a real compare for this card
            continue
        toks = []
        for t, _e in tagged:                                          # preserve order, dedupe
            if t not in toks:
                toks.append(t)
        merged.append(merge_overlay(tagged, toks))
    return merged
