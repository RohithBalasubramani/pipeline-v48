"""ems_exec/executor/match_bounds.py — the BOUNDED-match primitives shared by the roster/member matchers (T2.1-2
roster.match_hardening). ZERO card knowledge, no heavy imports: pure string boundary logic + the one flag reader.

The collision this fixes (the gic-2 / gic-20 family): the three matchers historically decided membership by RAW
bidirectional substring — `'gic-2' in 'gic-20'` is True, so a selector for site gic-2 wrongly folded gic-20's meter
(and the sankey trunk `'pcc-panel-1' in 'pcc-panel-10'` claimed a foreign panel). The hardened primitives only accept a
substring hit when the characters ADJACENT to the match are non-word (a '-' / '_' / ' ' separator OR a string edge), so
'gic-2' matches 'gic-2' / 'gic-2-n1' but NOT 'gic-20' — a right-boundary the raw substring never checked.

Lives in its OWN module (imported by members.py AND the roster_modes_* siblings) so the shared primitive never forces a
members <-> roster_modes import cycle. Default OFF (enabled() reads roster.match_hardening) → the callers keep their
byte-identical legacy substring path; only when the operator flips the knob do the bounded primitives take over. [atomic]
"""
from __future__ import annotations

# ASCII word characters — a boundary is any char that is NOT one of these (dash/underscore/space/slash/edge all qualify).
# Explicit set (not str.isalnum) keeps this ASCII-safe: no unicode letter/digit is ever mistaken for a word char.
_WORD = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")


def _is_word_char(ch):
    """True only for an ASCII letter/digit. None (a string edge) and every separator ('-', '_', ' ', '/') are False —
    i.e. they are BOUNDARIES."""
    return ch is not None and ch in _WORD


def contains_bounded(hay, needle):
    """True when `needle` occurs in `hay` with a NON-WORD boundary on BOTH sides of the occurrence — the char just
    before AND just after the match is a separator or a string edge. Operates on the raw hay/slug (dashes, underscores
    and spaces are the boundaries), so 'gic-2' hits 'gic-2' and 'gic-2-n1' but misses 'gic-20' (the trailing '0' is a
    word char). Empty hay/needle → False. Scans every occurrence; one bounded hit is enough."""
    if not hay or not needle:
        return False
    hay = str(hay)
    needle = str(needle)
    n = len(needle)
    start = hay.find(needle)
    while start != -1:
        before = hay[start - 1] if start > 0 else None
        after = hay[start + n] if start + n < len(hay) else None
        if not _is_word_char(before) and not _is_word_char(after):
            return True
        start = hay.find(needle, start + 1)
    return False


def prefix_bounded(s, prefix):
    """True when `s` STARTS WITH `prefix` AND the char immediately after the prefix is a boundary (separator or edge).
    Left-anchored (unlike contains_bounded) — the uniformity right-boundary for the name_prefixes matcher, so prefix
    'gic-2' matches 'gic-2' / 'gic-2-n1' but not 'gic-20'. Empty prefix/s → False."""
    if not prefix or not s:
        return False
    s = str(s)
    prefix = str(prefix)
    if not s.startswith(prefix):
        return False
    after = s[len(prefix)] if len(prefix) < len(s) else None
    return not _is_word_char(after)


def unique_bounded_match(s, by_slug):
    """The bounded replacement for the sankey `k in s or s in k` bidirectional loop: a candidate key matches when it is
    bounded-contained in `s` OR `s` is bounded-contained in it. Returns the candidate's value IFF EXACTLY ONE key
    matches (an unambiguous containment); zero or two-or-more matches → None (never a fabricated / arbitrary pick).
    Empty `s` / empty map → None."""
    if not s or not by_slug:
        return None
    found = None
    count = 0
    for k, v in by_slug.items():
        if k and (contains_bounded(s, k) or contains_bounded(k, s)):
            count += 1
            if count > 1:
                return None                                     # ambiguous — two keys both contain / are contained
            found = v
    return found if count == 1 else None


def enabled():
    """True when the roster.match_hardening knob is ON (default OFF → the callers keep their legacy substring path,
    byte-identical). Reads cfg('roster.match_hardening', 'off') through flag_on (THE boolean-knob vocabulary); any config
    outage fails safe to OFF. Imported lazily so this module stays import-light and the flag stays monkeypatchable."""
    try:
        from config.app_config import cfg, flag_on
    except Exception:
        return False
    return flag_on("roster.match_hardening", False, cfg_fn=cfg)
