"""ems_exec/executor/roster_pres_sections.py — deterministic PRES synthesis for section-split series keys. [sections]

Single concern: a section-compare roster ships per-section VARIANTS of the recipe's series keys (columns entries
carrying `_base`/`_section` — layer2/gates/roster._section_overlay). The chart component maps series via the payload's
OWN pres lists (stackSeries/lineSeries entries keyed by series key + stackOrder/lineOrder) — data alone renders
nothing. The AI is ASKED to pair the split with those pres morphs (data_instructions_v2 ★ rule) but the pairing is
mechanical and models flub it; this pass GUARANTEES it: for every base key that gained variants, any pres list entry
still keyed on the base is REPLACED by per-section clones — label '<base label> — Sec A/B', section A keeps the base
color, later sections get a deterministic tint (same hue family = same quantity, light vs dark = section) — and
sibling stackOrder/lineOrder string lists are rewritten the same way. An AI-authored pres entry for a variant key is
LEFT ALONE (the pass only fills what is missing). Fail-open everywhere; zero card knowledge — the walk speaks only the
generic pres vocabulary, never a card id."""
from __future__ import annotations

_SERIES_LISTS = ("stackSeries", "lineSeries")
_ORDER_LISTS = ("stackOrder", "lineOrder")


def _tint(color, f):
    """`color` mixed toward white by factor f (0..1) — the per-section tone of the SAME hue family. Non-hex → as-is."""
    try:
        c = str(color).strip()
        if not (c.startswith("#") and len(c) in (4, 7)):
            return color
        if len(c) == 4:
            c = "#" + "".join(ch * 2 for ch in c[1:])
        r, g, b = (int(c[i:i + 2], 16) for i in (1, 3, 5))
        mix = lambda v: max(0, min(255, int(round(v + (255 - v) * f))))
        return f"#{mix(r):02x}{mix(g):02x}{mix(b):02x}"
    except Exception:
        return color


def _variants_of(roster):
    """{base_key: [(variant_key, section_token), …]} from the roster's section-overlay columns entries (marker-driven:
    only entries the gate stamped `_base`/`_section` count — an AI-authored split names its own pres, not ours)."""
    out = {}
    for s in roster or []:
        if not isinstance(s, dict):
            continue
        for c in (s.get("columns") or []):
            if isinstance(c, dict) and c.get("_base") and c.get("key") and c.get("_section"):
                out.setdefault(str(c["_base"]), []).append((str(c["key"]), str(c["_section"])))
    return out


def _clone_entries(entry, variants):
    """The per-section clones of ONE pres series entry (label + ' — Sec A/B', tinted color per section index)."""
    label_keys = [k for k in ("label", "name", "title") if isinstance(entry.get(k), str)]
    clones = []
    for i, (vk, tok) in enumerate(variants):
        e = dict(entry)
        e["key"] = vk
        sec_letter = tok[-1].upper() if tok else "?"
        for lk in label_keys:
            e[lk] = f"{entry[lk]} — Sec {sec_letter}"
        if "color" in e and i > 0:
            e["color"] = _tint(e.get("color"), 0.30 + 0.25 * (i - 1))
        clones.append(e)
    return clones


def _patch_container(d, variants):
    """Rewrite ONE dict's pres lists in place: base-keyed series entries → per-section clones; order lists likewise.
    A list already carrying any variant key is left alone (the AI authored it). A container that changed is stamped
    `sectionSplit: true` — the host's sections-aware wrapper keys its generic series mapping on that marker (the
    original component stays byte-identical when the marker is absent)."""
    any_changed = False
    for lk in _SERIES_LISTS:
        lst = d.get(lk)
        if not isinstance(lst, list):
            continue
        present = {e.get("key") for e in lst if isinstance(e, dict)}
        rebuilt, changed = [], False
        for e in lst:
            base = e.get("key") if isinstance(e, dict) else None
            vs = variants.get(base)
            if vs and not any(vk in present for vk, _t in vs):
                rebuilt.extend(_clone_entries(e, vs))
                changed = True
            else:
                rebuilt.append(e)
        if changed:
            d[lk] = rebuilt
            any_changed = True
    for ok in _ORDER_LISTS:
        lst = d.get(ok)
        if not isinstance(lst, list) or not all(isinstance(x, str) for x in lst):
            continue
        present = set(lst)
        rebuilt, changed = [], False
        for x in lst:
            vs = variants.get(x)
            if vs and not any(vk in present for vk, _t in vs):
                rebuilt.extend(vk for vk, _t in vs)
                changed = True
            else:
                rebuilt.append(x)
        if changed:
            d[ok] = rebuilt
            any_changed = True
    if any_changed:
        d["sectionSplit"] = True


def apply_section_pres(payload, roster):
    """Walk the payload and patch every pres container for the roster's section-split variant keys. In-place,
    fail-open (an exception leaves the payload exactly as it was — the base keys still render)."""
    try:
        variants = _variants_of(roster)
        if not variants or not isinstance(payload, dict):
            return payload
        stack = [payload]
        while stack:
            node = stack.pop()
            if isinstance(node, dict):
                _patch_container(node, variants)
                stack.extend(node.values())
            elif isinstance(node, list):
                stack.extend(node)
    except Exception:
        pass
    return payload
