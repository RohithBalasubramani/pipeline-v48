"""layer1b/resolve/name_collision.py — GENERIC name-collision discipline for the confident-pin path. [F5, F6]

The registry has HOMONYMS: distinct physical assets whose human names carry the SAME class+unit token.
  · 'DG-3 MFM' (id 4, legacy meter)      vs  'GIC-28-N3-DG-03 [Jackson]' (id 302)     — both are "DG-3"
  · 'GIC-02-N5-UPS-04' (id 23)           vs  'GIC-17-N4-...UPS-04 [TiMAC]' (id 191)     — both are "UPS-04"
  · 'GIC-07-N5-UPS - 10' (id 78)         vs  'GIC-21-N6-UPS-10 Incomer-4' (id 236)      — both are "UPS-10"
When a prompt names such a token, the AI confidently picks ONE — often the WRONG physical unit (a Jackson genset for a
legacy meter, a Laminator feeder for a real UPS). A confident pin there is a fabrication of certainty. So this module
detects, DETERMINISTICALLY from the PROMPT (never the AI's variable emission), whether the asset the user typed collides
across multiple distinct registry devices; if so the resolver refuses to pin and surfaces the colliding candidates for
the picker.

It ALSO repairs candidate RECALL (F6): the colliding set is computed by name-token match over the WHOLE registry, so the
correctly-named asset (e.g. 'GIC-01-N3-UPS-01', which the AI omitted) is ALWAYS present.

Policy, not hardcoded names:
  · a token = (class-word, unit-number) parsed from the free text with the DB-driven class vocabulary; class words come
    from the same class_concept_hints the class prior uses, so the two vocabularies never drift.
  · GHOST rows (table_exists=False — physically no neuract table) are dropped: they can never render, so they neither
    trigger a collision nor appear as candidates. This also fixes the ghost-table pin (P03).
  · a collision is >1 DISTINCT registry ROW sharing the token. Distinctness is by canonical lt_mfm id, NOT by the
    confident_pin `_ident` twin heuristic: the canonical device_mappings prove EVERY physical device has its OWN
    device_id — 'DG-3 MFM' (dev_...904) and 'GIC-28-N3-DG-03 [Jackson]' (dev_...031) are DIFFERENT devices, never one
    genset logged twice. Merging them (the DS-09 twin rule) is what mis-pinned the Jackson prompt to the legacy meter;
    the collision gate must treat differently-named rows as the different assets they are, and surface the picker. [F5]
"""
import re

from config.app_config import cfg
from layer1b.resolve.class_from_subject import _CONCEPT_HINTS


def _class_words():
    """The explicit class-word vocabulary (DB-driven, same source as the class prior) + a few name-string aliases that
    appear only in asset NAMES (pcc/mcc/pdb as 'panel', 'xformer'/'tf' as transformer). Lowercased, longest-first so a
    multi-word alias wins over a substring. Fail-open to the code-default hints."""
    hints = cfg("layer1b.class_concept_hints", _CONCEPT_HINTS)
    if not isinstance(hints, dict) or not hints:
        hints = _CONCEPT_HINTS
    words = set()
    for spec in hints.values():
        for w in (spec or {}).get("tokens", []):
            if w:
                words.add(str(w).lower())
    return sorted(words, key=len, reverse=True)


def unit_tokens(text):
    """Set of (class_word, unit_int) tokens in `text` — the asset the user (or a registry name) refers to. A token is a
    known class word immediately followed by a number, tolerating '-', '_', spaces and leading zeros:
    'DG-03'/'DG - 3'/'dg3' → ('dg',3); 'UPS-04'/'600 KVA UPS-04' → ('ups',4). Number-less mentions ('the UPS') yield no
    token (handled by the class prior, not here). Purely lexical; never raises."""
    if not text:
        return set()
    t = str(text).lower()
    words = _class_words()
    if not words:
        return set()
    alt = "|".join(re.escape(w) for w in words)
    out = set()
    for m in re.finditer(rf"(?<![a-z])({alt})\s*[-_ ]?\s*0*(\d+)", t):
        out.add((m.group(1), int(m.group(2))))
    return out


def _renderable(c):
    """A candidate row that can actually render: has a physical table (table_exists, index 9 — fail-open when the flag
    is absent) and is not a fully-dead placeholder. Ghost rows are dropped from collision detection AND candidate
    lists."""
    return bool(c[9]) if len(c) > 9 else bool(c[2])


def colliding_rows(prompt, cands):
    """Registry rows (renderable only) whose NAME carries any class+unit token the PROMPT carries. This is the
    homonym-aware match set: every asset the user could plausibly mean by the exact token they typed. First-seen /
    id order, de-duplicated by registry id. Empty when the prompt names no class+unit token (→ no collision gate;
    the resolver's normal path runs)."""
    ptoks = unit_tokens(prompt)
    if not ptoks:
        return []
    out, seen = [], set()
    for c in cands:
        if not _renderable(c):
            continue
        if ptoks & unit_tokens(c[1]) and c[0] not in seen:
            seen.add(c[0])
            out.append(c)
    return out


def _norm(s):
    return re.sub(r"[^a-z0-9]+", "", str(s).lower())


def _discriminators(name):
    """The normalized substrings that, if present in a prompt, mean the user fully specified THIS row:
      · the full registry name ('gic01n3ups01cl600kva'), and
      · the GIC-node prefix ('gic01n3') — the true unique location key, robust to rating suffixes the user won't type.
    The GIC prefix alone is unique across the registry (one asset per GIC node position), so a prompt carrying it names
    exactly one asset."""
    out = []
    full = _norm(name)
    if full:
        out.append(full)
    m = re.match(r"\s*(gic[-_ ]?\d+[-_ ]?n\d+)", str(name).lower())
    if m:
        out.append(_norm(m.group(1)))
    return out


def uniquely_named(prompt, rows):
    """The single colliding row the prompt spells out fully — by whole registry name OR by unique GIC-node prefix
    (space/punct/case-insensitive) — else None. When the user types the discriminating name ('GIC-01-N3-UPS-01') exactly
    ONE colliding row matches → not ambiguous, pin it. Two+ matches or zero → None (stay ambiguous). Keeps the collision
    gate from firing on an already-disambiguated full name. [F6: full-name prompts still pin]"""
    if not rows:
        return None
    p = _norm(prompt)
    if not p:
        return None
    hit = [c for c in rows if any(d in p for d in _discriminators(c[1]))]
    return hit[0] if len(hit) == 1 else None


def is_collision(prompt, cands):
    """True when the prompt's asset token maps to MORE THAN ONE distinct RENDERABLE registry row (by canonical id) AND
    the prompt does not already spell out exactly one of them by full name — a homonym the AI must not confidently pin.
    Distinctness is by id, never a name-pattern twin merge: the canonical device registry has no true twins (every
    device has its own device_id), so two differently-named rows sharing a class+unit token are two different assets the
    user must disambiguate. A prompt that names one colliding row in full ('GIC-01-N3-UPS-01') is NOT a collision. [F5]"""
    rows = colliding_rows(prompt, cands)
    if len(rows) < 2:
        return False
    return uniquely_named(prompt, rows) is None
