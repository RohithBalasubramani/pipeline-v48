"""layer2/emit/slot_catalog.py — the SLOT VOCABULARY the AI must bind to. [fixes the #1 Layer-2 failure: SLOT MISMATCH]

The executor (ems_exec/executor/fill.py::_leaf_path_for) resolves a field.slot ONLY to `data.<slot>` or `<slot>` (a
dotted/indexed path). So the AI CANNOT invent a token (`tile_r`, `series_r`, `sourceInputKw`) — it MUST emit slot = the
REAL fillable leaf path in this card's harvested default payload (e.g. `health.data.phases[0].value`,
`flow.vm.kpis.lossKwh`, `history.data.series[0].values`). This module enumerates those exact paths from the default
payload (value-aware via validate.leaf_classify) + expands a series-of-objects / numeric-array to its per-element
fillable leaves, then attaches, PER LEAF, the best-matching REAL basket columns by the leaf's measured QUANTITY — so the
AI has an obvious slot+column to name and never has to guess. DB-driven (quantity vocab = config.metrics), atomic, honest
(only real basket columns are suggested; a leaf with no matching column is shown with an empty suggestion = honest-blank).
"""
import re

from config.vocab import vocab
from config.metrics import slot_semantic_label
from validate.leaf_classify import classify


def _tok(s):
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())




def _leaf_last_key(path):
    m = re.findall(r"[A-Za-z_][A-Za-z0-9_]*", path or "")
    return m[-1] if m else ""


def _leaf_at(tree, path):
    node = tree
    for t in re.findall(r"[^.\[\]]+", path or ""):
        key = int(t) if t.isdigit() else t
        try:
            node = node[key]
        except (KeyError, IndexError, TypeError):
            return None
    return node



def _elem_numeric(o, k):
    """True iff element object `o` carries a NUMBER (or numeric string) at key `k` — the same data-vs-chrome test
    leaf_classify uses to call the container a series."""
    v = o.get(k) if isinstance(o, dict) else None
    return isinstance(v, (int, float)) and not isinstance(v, bool) \
        or (isinstance(v, str) and bool(re.match(r"^-?\d", str(v or ""))))


def _series_value_keys(value):
    """The fillable NUMERIC element keys of a series-of-objects, in first-seen order. PREFER the allowlist
    (vocab.element_value_keys) when any of its keys carries a number; otherwise FALL BACK to EVERY numeric element key
    that is not design chrome (vocab.element_chrome_keys). Generic + DB-driven: a new payload's domain-specific point
    keys (hotspotC, loadPct, voltageKv, …) expand without a code/allowlist edit, while style/threshold tokens (width,
    decimals, warn, from/to, …) stay chrome so their container is never clobbered into a flat list. [chrome-loss fix]"""
    allow = {str(k).lower() for k in (vocab("element_value_keys") or [])}
    deny = {str(k).lower() for k in (vocab("element_chrome_keys") or [])}
    seen, out = set(), []
    for o in value:
        if not isinstance(o, dict):
            continue
        for k in o.keys():
            if k in seen or not _elem_numeric(o, k):
                continue
            seen.add(k)
            out.append(k)
    preferred = [k for k in out if k.lower() in allow]
    if preferred:
        return preferred                                       # back-compat: allowlisted keys drive when present
    return [k for k in out if k.lower() not in deny]            # fallback: all measured keys minus chrome denylist


_TIME_LABEL_PATTERNS_DEFAULT = [
    r"^\d{1,2}\s*[-–]\s*\d{1,2}$",                                     # hour-range buckets: 00-03 … 21-24
    r"^\d{1,2}:\d{2}(:\d{2})?$",                                       # clock: 09:00 / 09:00:00
    r"^\d{1,2}\s*(am|pm)$",                                            # 9am / 12 pm
    r"^(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{1,2}$",   # Jun 01 / March 7
    r"^\d{1,2}\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?$",   # 01 Jun
    r"^\d{4}-\d{2}(-\d{2})?([ t].*)?$",                                # ISO date(-time)
    r"^w(eek)?\s*\d{1,2}$",                                            # W1 / Week 12
    r"^(mon|tue|wed|thu|fri|sat|sun)[a-z]*$",                          # weekday buckets
]


def _time_label_patterns():
    """The time-bucket LABEL patterns — DB-driven (config.vocab time_label_patterns row, json list of regexes),
    code-default fallback. Compiled case-insensitively; a broken row entry is skipped (never raises)."""
    raw = vocab("time_label_patterns") or _TIME_LABEL_PATTERNS_DEFAULT
    out = []
    for p in raw:
        try:
            out.append(re.compile(str(p), re.IGNORECASE))
        except re.error:
            continue
    return out


def time_bucket_label_key(value):
    """The element key that carries a TIME-BUCKET label ('00-03', 'Jun 01', '09:00', …) across a series-of-objects, or
    None. Generic + DB-driven: any STRING-valued element key whose every non-empty value matches a time-label pattern
    (vocab.time_label_patterns) marks the container as ONE time-bucketed series, not distinct entities. [cards 76/77]"""
    if not (isinstance(value, list) and len(value) >= 2):
        return None
    pats = _time_label_patterns()
    elems = [o for o in value if isinstance(o, dict)]
    if len(elems) < 2:
        return None
    for k in elems[0].keys():
        vals = [o.get(k) for o in elems if k in o]
        strs = [v for v in vals if isinstance(v, str) and v.strip()]
        if len(strs) < 2 or len(strs) != len(vals):
            continue
        if all(any(p.match(s.strip()) for p in pats) for s in strs):
            return k
    return None


def _expand_leaf(path, kind, value):
    """Expand ONE classify data-leaf into concrete FILLABLE leaf paths (what the executor sets), each with a per-leaf
    QUANTITY hint. scalar → the path itself. numeric-array → the path itself (whole array). series-of-objects →
    per-element <path>[i].<value_key> for each element's numeric scalar key (so each phase/link fills independently),
    carrying that element's OWN unit/label as the quantity hint (a voltage phase's unit=V vs a current phase's unit=A).
    ★ TIME-BUCKET COMPRESSION [cards 76/77]: a series-of-objects whose elements are TIME BUCKETS of one series (a
    time-label element key per vocab.time_label_patterns) compresses to ONE `<path>[*].<value_key>` slot per element
    VALUE key — the AI emits ONE bucketed field per key and the executor distributes the buckets, instead of N×K
    near-identical per-element lines (which truncated the catalog and invited const time-label emissions)."""
    if kind == "scalar":
        return [(path, "scalar", _leaf_last_key(path), None)]
    if kind == "array":
        return [(path, "array", _leaf_last_key(path), None)]
    # kind == series
    if isinstance(value, list) and value and isinstance(value[0], dict):
        # per-object: the fillable numeric element key(s) — allowlist-first, else all measured keys minus chrome denylist
        val_keys = _series_value_keys(value)
        if not val_keys:
            # object array with no fillable numeric element key (pure-string / pure-chrome roster) → keep the container
            return [(path, "series", _leaf_last_key(path), None)]
        if time_bucket_label_key(value):
            return [(f"{path}[*].{vk}", "bucket_series", vk, len(value)) for vk in val_keys]
        out = []
        for i, o in enumerate(value):
            for vk in val_keys:
                out.append((f"{path}[{i}].{vk}", "scalar", vk, None))
        return out
    # numeric list-of-numbers series (history.data.series[0].values / xLabelIndexes) — whole array leaf
    return [(path, "array", _leaf_last_key(path), None)]



def _verbatim_ctx(payload, slot, elem_key):
    """The leaf's VERBATIM context, copied straight from the payload — NO interpretation, NO quantity guessing: the
    element/parent object's own label + unit, and the nearest ancestor section title. The AI matches this context to the
    full column schema itself (it sees every column + unit + has_data); we only surface the facts a human would read."""
    toks = re.findall(r"[^.\[\]]+", slot or "")
    label = unit = section = None
    # element/parent object: own label + unit (verbatim)
    parent = _leaf_at(payload, ".".join(toks[:-1])) if len(toks) > 1 else None
    if isinstance(parent, dict):
        for k in ("label", "name", "id", "key"):
            v = parent.get(k)
            if isinstance(v, str) and v.strip():
                label = v; break
        u = parent.get("unit")
        if isinstance(u, str) and u.strip():
            unit = u
    # nearest ancestor SECTION heading (verbatim string)
    for cut in range(len(toks) - 1, 0, -1):
        anc = _leaf_at(payload, ".".join(toks[:cut]))
        if isinstance(anc, dict):
            for tkey in ("title", "heading", "chartTitle", "header"):
                v = anc.get(tkey)
                if isinstance(v, str) and v.strip():
                    section = v; break
        if section:
            break
    # ★ SEMANTIC FALLBACK [emit-correctness E]: many leaves carry their semantic in the PATH TOKEN (vThd, flickerPst,
    # lifeRemainingYears), not a sibling `label` key — those reached the AI as "(no label)" and it guessed a wrong-
    # semantic same-unit substitute (a current-THD column under a voltage-THD leaf). Surface the humanized path token so
    # the AI reads the leaf's real meaning. Generic + DB-driven (config.metrics.slot_semantic_label); never overrides a
    # real verbatim label.
    if not label:
        label = slot_semantic_label(slot)
    return {"label": label, "unit": unit, "section": section}


def build_slot_catalog(default_payload, basket):
    """Return the ordered list of fillable leaf slots for THIS card:
        [{slot, kind, element_key, time_axis, quantity, ctx:{label, unit, section}}]
    slot = the EXACT dotted/indexed leaf path the executor resolves. ctx = the leaf's VERBATIM payload context (its own
    label/unit + section title) — the AI binds each slot to a schema column ITSELF from the FULL column schema; this
    module does NOT rank/suggest columns (that machinery mis-led the AI; the model binds correctly from complete raw
    facts). `quantity` = the slot's EXPECTED physical-quantity CLASS (layer2.quantity_class over the sibling unit
    chrome + path tokens — the same DB vocab the gate enforces), so the AI sees the hard wall it must not cross; None
    when unclassified. A time-axis leaf is marked so the AI emits the kind='time' contract."""
    if not default_payload:
        return []
    from layer2.quantity_class import slot_quantity
    cat, seen = [], set()
    for d in (classify(default_payload).get("data_leaves") or []):
        val = _leaf_at(default_payload, d["path"])
        for slot, k, elem_key, _hint in _expand_leaf(d["path"], d["kind"], val):
            if slot in seen:
                continue
            seen.add(slot)
            entry = {"slot": slot, "kind": k, "element_key": elem_key,
                     "time_axis": _is_time_axis_key(_leaf_last_key(slot)),
                     "ctx": _verbatim_ctx(default_payload, slot.replace("[*]", "[0]"), elem_key)}
            # the slot's EXPECTED physical quantity — sibling unit chrome first ('°C' → temperature), then the slot
            # path's own name tokens (hotspotC/faa/h5/readiness/…), then the sibling label. DB-vocab-driven
            # (layer2.quantity_class); None = unclassified (no expectation shown, the gate never flags it).
            entry["quantity"] = slot_quantity(slot, entry["ctx"])
            if k == "bucket_series":
                entry["n"] = _hint                              # element count (time buckets) — the executor distributes
            cat.append(entry)
    # DERIVED-SIBLING PRUNE [audit 2026-07-14, 10 F2]: a leaf the executor derives post-fill from a sibling
    # (display.py: displayValue = fmt(value)) must not be a bindable slot when its SOURCE sibling is also in the
    # catalog — the AI can't bind it and reconcile stamped it unbound every run (~2.9% of all blank telemetry).
    # DB-vocab-driven (vocab.derived_sibling_keys, {"derived": "source"}); a derived leaf with NO source sibling
    # stays (nothing derives it). Post-pass so enumeration order can't matter.
    sib = vocab("derived_sibling_keys") or {}
    if isinstance(sib, dict) and sib:
        sibmap = {str(k): str(v) for k, v in sib.items()}
        def _derived_dup(slot):
            last = _leaf_last_key(slot)
            src = sibmap.get(last)
            return bool(src) and slot.endswith(last) and (slot[: -len(last)] + src) in seen
        cat = [e for e in cat if not _derived_dup(e["slot"])]
    return cat


def _time_axis_keys():
    """The TIME-AXIS leaf-key vocabulary — DB-driven (config.vocab time_axis_keys row), code-default fallback."""
    return {str(k).strip().lower() for k in (vocab("time_axis_keys") or []) if str(k).strip()}


def _is_time_axis_key(key):
    """True for a TIME-AXIS leaf key (bucket timestamps / axis window bounds) — filled by the executor from the card's
    own bucketed series timestamps, never from a measured column. Vocabulary = the DB knob; the structural
    'timestamp'/'…StartMs'/'…EndMs' shape check is generic (not a name list)."""
    k = (key or "").lower()
    return k in _time_axis_keys() or "timestamp" in k or k.endswith(("startms", "endms"))


def render_slot_catalog(catalog, cap=None):
    """The prompt block: one line per fillable leaf with its VERBATIM payload context (label/unit/section). The AI
    matches the context to the FULL column schema shown elsewhere in the prompt — no suggestions, no pre-ranking.
    ★ UNCAPPED by default [card 77: cap=60 hid 42 of 102 slots while the contract said 'NEVER emit a slot that is not
    on that list' — guaranteed blanks + invented slots]. A cap, if ever wanted, is the DB row emit.slot_catalog_cap
    (0/absent = uncapped); the time-bucket [*] compression is what keeps big catalogs small now."""
    if not catalog:
        return "  (this card has NO fillable data leaves — omit data_instructions.fields)"
    if cap is None:
        try:
            from config.app_config import cfg
            cap = int(cfg("emit.slot_catalog_cap", 0) or 0)
        except Exception:
            cap = 0
    try:
        from layer2.quantity_class import _weak
        weak = _weak()
    except Exception:
        weak = set()
    out = []
    for e in (catalog[:cap] if cap else catalog):
        # expected physical quantity (from the leaf's own unit chrome / path tokens) — the bind's HARD WALL: only a
        # SAME-qty column/fn may fill this slot; no such column in the basket → OMIT the field (honest-blank). A WEAK
        # (dimension-only) class like 'percent' is a hint, not a wall — the leaf's label names the semantic.
        # TOKEN FORM [C1]: bare `| expected_qty=X` / `(weak)` suffix — the rule prose lives ONCE in the FILLABLE
        # DATA-LEAF SLOTS header (user_message), not repeated per line (~48K chars per sweep).
        eq = e.get("quantity")
        if not eq:
            q = ""
        elif str(eq).lower() in weak:
            q = f" | expected_qty={eq} (weak)"
        else:
            q = f" | expected_qty={eq}"
        if e.get("kind") == "bucket_series":
            c = e.get("ctx") or {}
            sec = f" · section=\"{c['section']}\"" if c.get("section") else ""
            out.append(f"  slot={e['slot']}  | kind=bucket_series | TIME-BUCKETED SERIES ({e.get('n')} time-bucket "
                       f"elements{sec}){q}: emit EXACTLY ONE {{kind:\"bucketed\"}} field with this [*] slot copied "
                       f"VERBATIM — the executor distributes the ordered buckets across the elements; the element's "
                       f"time-label key is chrome (NEVER a field)")
            continue
        if e.get("time_axis"):
            out.append(f"  slot={e['slot']}  | kind={e['kind']} "
                       f"→ TIME AXIS: emit {{kind:\"time\"}} — NO column (executor fills the bucket timestamps)")
            continue
        c = e.get("ctx") or {}
        bits = [f"label=\"{c['label']}\"" if c.get("label") else None,
                f"unit=\"{c['unit']}\"" if c.get("unit") else None,
                f"section=\"{c['section']}\"" if c.get("section") else None]
        ctx = " · ".join(b for b in bits if b) or "(no label/unit in payload — use the slot path itself)"
        out.append(f"  slot={e['slot']}  | kind={e['kind']} | context: {ctx}{q}")
    return "\n".join(out)
