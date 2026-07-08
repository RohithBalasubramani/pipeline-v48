"""validate/render_verdict.py — THE post-fill render verdict (one concern, non-AI).

After ems_exec fills a card's payload, decide render | partial | honest_blank from the COMPLETED payload's
real-vs-blank DATA leaves — grounded in REAL FILL, never shape-conformance. This ONE module replaces the host's
old tangle (`_card_leaf_stats` declared-slot scan + roster_stats fold-in + the seed sentinel + demotion patches).

UNIVERSE = every DATA leaf the card actually has, from three honest sources that never overlap:
  1. DECLARED field leaves        — data_instructions.fields[].slot, resolved on the completed payload.
                                    real iff non-blank: the executor blanks an UNFILLABLE declared leaf to None/'—'
                                    (fill.py), so on a declared leaf non-blank ⟺ really filled. A stripped 0.0
                                    placeholder is only ever left on an UNDECLARED leaf.
  2. ROSTER-filled leaves         — the interpreter's own recipe-driven real/blank telemetry (roster_stats).
  3. UNDECLARED numeric leaves    — a numeric DATA leaf (leaf_classify) that NO field/roster bound: a leftover
                                    stripped placeholder or a Storybook seed. Never 'answered' → always BLANK.
                                    This single rule fixes the panel-aggregate fake-full (fields=[] cards report
                                    'full' over 0.0s) AND subsumes the seed sentinel.

A card is `render`/full ONLY when it has ≥1 real leaf AND every data leaf is real; some-but-not-all real →
`partial`; zero real over ≥1 data leaf → `honest_blank`. verdicts are TELEMETRY, never a render gate (per-leaf
degradation stands). [atomic; pure scan; never raises]
"""
import re

# dotted-path addressing: the ONE shared home (ems_exec/executor/paths.py); _at_path ≡ paths._leaf_at byte-for-byte.
from ems_exec.executor.paths import _toks, _leaf_at as _at_path


def _scaffold_keys():
    """Leaf-key vocab that is chart SCAFFOLDING, not measured data — the time AXIS + the y-scale/tick range keys a
    chart derives from its own series (yscale.apply). Counting these as 'real' over-reports answerability (a DG history
    card's 25 epoch-ms x-axis + maxY/minY/yTicks are not measurements). DB-driven (config.vocab 'verdict_scaffold_keys');
    code default on miss. [A-1: time-axis + scale scaffold is not measured data]"""
    default = {"t", "time", "ts", "timestamp", "epoch", "epochms", "startms", "endms", "axisstartms", "axisendms",
               "x", "xlabelindexes", "maxy", "miny", "yticks", "ymax", "ymin", "ticks", "expectedmax", "expectedmin"}
    try:
        from config.vocab import vocab as _vocab
        return {str(k).lower() for k in (_vocab("verdict_scaffold_keys") or ())} or default
    except Exception:
        return default


def _is_scaffold(path, scaffold):
    """Is the LAST key of a leaf path a chart-scaffold key (time axis / y-scale)? Then it is chrome, not measured data."""
    toks = _toks(path)
    return (toks[-1] if toks else "").lower() in scaffold


def _blank_scalar(v):
    return v is None or v == "—" or v == ""


def _value_keys():
    """The object keys that carry the fillable VALUE inside a reading/element object (config.vocab, code default) —
    so a dict-valued declared slot counts its DATA leaves (value/values/y/…), never its chrome (unit/label strings)."""
    try:
        from config.vocab import vocab as _vocab
        return [str(k) for k in (_vocab("element_value_keys") or [])] or ["value", "values", "y", "kw", "kwh", "count"]
    except Exception:
        return ["value", "values", "y", "kw", "kwh", "count"]


def _count_subtree(node, value_keys):
    """Real/blank DATA leaves inside a resolved slot value. A scalar → 1 leaf. A LIST → its elements (empty → one
    honest-blank leaf). A DICT that is a reading OBJECT (carries a value key) → count ONLY its value-key leaves (its
    unit/label are chrome); a DICT with no value key → recurse all children (a plain container)."""
    real = blank = 0
    if isinstance(node, dict):
        vkeys = [k for k in value_keys if k in node]
        children = ([(k, node[k]) for k in vkeys] if vkeys else list(node.items()))
        for _k, v in children:
            r, b = _count_subtree(v, value_keys)
            real += r
            blank += b
    elif isinstance(node, list):
        if not node:
            blank += 1                                            # an EMPTY declared series is an honest-blank leaf
        for v in node:
            r, b = _count_subtree(v, value_keys)
            real += r
            blank += b
    elif _blank_scalar(node):
        blank += 1
    else:
        real += 1
    return real, blank


def _resolve_slot(payload, s):
    """Resolve a declared slot to (resolved_path, node) trying the slot itself then the `data.<slot>`/stripped alias
    the executor binds to — the FIRST that lands on a real node. (alias, None) when neither resolves."""
    aliases = [s, (s[5:] if s.startswith("data.") else "data." + s)]
    for p in aliases:
        node = _at_path(payload, p)
        if node is not None:
            return p, node
    return aliases[0], None


def declared_stats(payload, data_instructions):
    """(n_real, n_blank, resolved_paths) over the card's DECLARED field leaves on the COMPLETED payload. A time-axis
    field (kind='time') and any scale/tick scaffold slot are EXCLUDED — chart chrome, not measured data (A-1)."""
    vkeys = _value_keys()
    scaffold = _scaffold_keys()
    n_real = n_blank = 0
    resolved = set()
    for f in ((data_instructions or {}).get("fields") or []):
        if not isinstance(f, dict):
            continue
        if (f.get("kind") or "").strip().lower() == "time":       # a time axis is scaffolding, never a measured value
            continue
        s = f.get("slot") or f.get("target_column") or f.get("metric")
        if not s:
            continue
        path, node = _resolve_slot(payload, str(s))
        if path in resolved or _is_scaffold(path, scaffold):      # scaffold slot → excluded (not counted, not resolved)
            continue
        resolved.add(path)
        if node is None:
            n_blank += 1                                          # declared slot with no resolved leaf → honest-blank
        else:
            r, b = _count_subtree(node, vkeys)
            n_real += r
            n_blank += b
    return n_real, n_blank, resolved


def _slot_base(slot):
    """The subtree prefix of a roster slot ('consumer.rows[*].kw' → 'consumer.rows') — every fanned element sits under it."""
    return re.split(r"[\[]", slot or "", maxsplit=1)[0].rstrip(".")


def _under_any(path, bases):
    """Is `path` equal to, or a descendant of, any base path (so it is already accounted for by a declared/roster slot)?"""
    for b in bases:
        if not b:
            continue
        if path == b or path.startswith(b + ".") or path.startswith(b + "["):
            return True
    return False


def undeclared_blank_count(payload, resolved_paths, roster_bases):
    """UNDECLARED numeric DATA leaves — a leftover stripped placeholder (panel fields=[] 0.0s) or a surviving
    Storybook seed: leaf_classify finds them, but NO field/roster bound them, so they are never 'answered' → BLANK.
    Excludes anything already under a declared or roster slot (no double-count). 0 on any failure."""
    try:
        from validate.leaf_classify import classify
        bases = list(resolved_paths) + list(roster_bases or [])
        scaffold = _scaffold_keys()
        n = 0
        for d in (classify(payload).get("data_leaves") or []):
            path = d.get("path")
            if path and not _under_any(path, bases) and not _is_scaffold(path, scaffold):
                n += 1                                            # a genuine UNDECLARED measured leaf (not chart scaffold)
        return n
    except Exception:
        return 0


_ANSWER = {"render": "full", "partial": "partial", "honest_blank": "none"}


def _narrative_real(payload):
    """A populated grounded NARRATIVE (widgets.ai_summary.text / top-level ai_summary.text / a *.pres.backendHeadline)
    is an AI-summary card's REAL, DB-true content — the FE renders it through the designed backendHeadline seam. The
    declared-field + numeric-leaf scan is BLIND to a STRING narrative (never counts it real OR blank), so a grounded
    narrative_ai card verdicts honest_blank with real=0 while it renders the page's richest real element (F5). Detect
    it GENERICALLY — the PRESENCE of a non-empty summary sentence (the narrative_ai contract), never a card id — so the
    verdict credits it as >=1 REAL leaf. Returns True iff a non-empty, NON-DEGRADED narrative sentence is present.

    HONEST-BLANK PROTECTION: an ai_summary widget marked `degraded` (the honest 'no metered data resolved' sentence an
    EMPTY panel emits — narrative_ai._is_degraded) is NOT real content. It (and the SAME text threaded into every
    backendHeadline seam) must NOT flip an empty panel's card honest_blank → partial (a false 'answered'). The
    ai_summary widget is authoritative here — its `degraded` flag vetoes the whole payload's narrative credit, including
    the mirrored backendHeadline. Never raises."""
    def _find_ai(o):
        if isinstance(o, dict):
            ai = o.get("ai_summary")
            if isinstance(ai, dict):
                return ai
            for v in o.values():
                r = _find_ai(v)
                if r is not None:
                    return r
        elif isinstance(o, list):
            for v in o:
                r = _find_ai(v)
                if r is not None:
                    return r
        return None

    def _has_headline(o):
        if isinstance(o, dict):
            bh = o.get("backendHeadline")
            if isinstance(bh, str) and bh.strip():
                return True
            return any(_has_headline(v) for v in o.values())
        if isinstance(o, list):
            return any(_has_headline(v) for v in o)
        return False

    try:
        ai = _find_ai(payload)
        if ai is not None:                                       # a narrative_ai card — the widget is authoritative
            text = ai.get("text")
            if not (isinstance(text, str) and text.strip()):
                return False
            return not bool(ai.get("degraded"))                 # degradation sentence → NOT a real answered leaf
        return _has_headline(payload)                            # no ai_summary widget → a raw backendHeadline seam
    except Exception:
        return False


def _asset3d_envelope(payload):
    """The asset_3d ViewerResolveResponse envelope ({object: {slug,label,url,rating}|null, viewer: {…}}) — the same
    shape detect the FE registry routes on. Its ONE datum is the MODEL BINDING itself: a bound object.url IS the
    card's real content (the 3D viewer renders it), NOT a set of measured column leaves — the generic leaf scan
    mis-read the envelope as one blank undeclared leaf and verdicted a BOUND model honest_blank with a metric-card
    reason sentence (c60). Returns the url string when bound, '' when the envelope is present but unbound, None when
    the payload is not this envelope."""
    if not (isinstance(payload, dict) and "object" in payload and "viewer" in payload):
        return None
    obj = payload.get("object")
    if obj is None:
        return ""
    if isinstance(obj, dict):
        url = obj.get("url")
        return url if isinstance(url, str) and url.strip() else ""
    return None


def compute(payload, data_instructions, roster_stats, *, has_payload, skeleton_blank=False, payload_error=None):
    """THE render verdict. Combines the three honest leaf sources into one (n_real, n_data) and decides the verdict.
    Returns {n_real, n_data, n_undeclared, verdict, answerability}. Never raises — a bad input degrades to honest_blank."""
    env = _asset3d_envelope(payload)
    if env is not None and not skeleton_blank:
        # asset_3d envelope: the model binding is the datum. Bound url → render (the viewer draws the real GLB);
        # unbound → honest_blank (the per-leaf 'no_3d_model' reason rides render.gaps from the renderer).
        verdict = "render" if env else "honest_blank"
        return {"n_real": 1 if env else 0, "n_data": 1, "n_undeclared": 0,
                "verdict": verdict, "answerability": _ANSWER[verdict]}
    try:
        d_real, d_blank, dpaths = declared_stats(payload or {}, data_instructions)
        r_real = int((roster_stats or {}).get("real") or 0)
        r_data = int((roster_stats or {}).get("data") or 0)
        roster_bases = [_slot_base(s.get("slot")) for s in ((data_instructions or {}).get("roster") or [])
                        if isinstance(s, dict) and s.get("slot")]
        u_blank = undeclared_blank_count(payload or {}, dpaths, roster_bases)
        n_real = d_real + r_real
        n_data = d_real + d_blank + r_data + u_blank
        # NARRATIVE REAL LEAF [F5]: an ai_summary card carries its real content as a grounded SENTENCE the numeric scan
        # cannot see. Credit a populated narrative as >=1 REAL data leaf so the verdict is answerable (partial/render),
        # never honest_blank over a rendering, DB-true narrative. Skeleton-blank (L2 skipped) has no real sentence → no
        # credit. GENERIC (keyed on the narrative presence, not a card id).
        if not skeleton_blank and _narrative_real(payload or {}):
            n_real += 1
            n_data += 1
    except Exception:
        n_real = n_data = u_blank = 0

    if skeleton_blank or (payload_error and n_real == 0):
        verdict = "honest_blank"                                  # served skeleton / broken bind → never a live render
    elif n_data == 0:
        verdict = "render" if has_payload else "honest_blank"     # legit chrome-only card (no data leaves)
    elif n_real == 0:
        verdict = "honest_blank"
    elif n_real == n_data:
        verdict = "render"
    else:
        verdict = "partial"
    return {"n_real": n_real, "n_data": n_data, "n_undeclared": u_blank,
            "verdict": verdict, "answerability": _ANSWER[verdict]}
