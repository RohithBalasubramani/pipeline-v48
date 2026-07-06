"""grounding/measured_annotation_scrub.py — scrub STRING-EMBEDDED MEASUREMENTS in data-role slots (one concern).

WHY (seed-leak class b): a harvested default carries measured numbers INSIDE annotation strings — c56/c59
floor.label='Readiness: 70%', c17 stats[].sub='at 17', c71 topKpis[].sub='peak 77%', c51 peak.label='peak temp 35°C',
c37/38 thresholds[].label='Max - 420V', c48 maxLine.label='Max: 480V'. Their KEYS are not narrative_slots and their
VALUES are not full numeric strings, so the type strip, the narrative/clock scrub AND the role scrub all missed them:
the seed number replays beside an honest-blank value ('—' with sub 'peak 77%').

Rule (config-driven PATTERN + ROLE, zero card_id):
  · PATTERN — the string VALUE embeds a number+unit / number+percent / 'at <n>' measurement token
    (data_quality_policy row scrub.embedded_number_pattern; the code default mirrors the seed row). A digit WITHOUT a
    measurement shape ('5th Harmonic', '3 Phase', 'IEEE 519', 'last-7', '#5fa64a', '-30d') does NOT match.
  · ROLE — the string is a DATA-slot annotation: its key is an annotation key (vocab.measured_annotation_keys:
    label/sub/…) AND its containing object carries a sibling NUMERIC data leaf (the measured value the annotation
    describes — floor.value, thresholds[].value, stats[].value). A caption with no measured sibling (rangeOptions[]
    'Last 7 days') is pure chrome and stays.
  · KEEP-HARD — dictionary subtrees (*Vocab / legend / palette / … — role_scrub.dictionary_subtree_keys) and design
    chrome subtrees (bandThresholds / IEEE limits — vocab.chrome_subtree_keys) are never descended into: a REAL design
    band stays byte-identical; only the seeded live-looking annotation scrubs.

BUILD-TIME strip concern: invoked by grounding.default_assemble._strip_and_scrub (persisted into payload_stripped and
folded into the no-default free-metadata enforce). Switchable via data_quality_policy scrub.embedded_numbers ('off').
On a missing row / DB outage every list falls back to its code-default mirror (db/seed_residual_seed_scrub.sql) — the
scrub never widens or narrows to a fabricated guess.
"""
from __future__ import annotations

import re

from config import quality_policy as qp
from config.vocab import vocab
from grounding.role_scrub import _dictionary_subtree_keys
from validate.leaf_classify import _chrome_subtree_keys

# Embedded-MEASUREMENT detector (default; DB-overridable via scrub.embedded_number_pattern):
#   · number + % / °C / an electrical-or-time unit token (word-bounded so '5th'/'IEEE 519'/'3 Phase' never match)
#   · 'at <n>' — a peak-position annotation ('at 17' = the seed's peak hour) whose number carries no unit
#   · (?<![\w#]) guards against hex colors ('#5fa64a') and identifier substrings ('HHF-01' matches only via a unit).
_EMBEDDED_DEFAULT = (
    r"(?<![\w#])[+-]?\d+(?:[.,]\d+)?\s*"
    r"(?:%|°\s*[CcFf]|(?:k[Ww]h?|k[Vv][Aa][Rr]?h?|k[Vv]|M[WV]A?h?|[Ww]h|[Vv][Aa]|[Vv]|[Aa]|[Hh][Zz]"
    r"|[Hh]rs?|[Hh]|ms|min(?:s)?|sec|days?|yrs?|years?)\b)"
    r"|(?i:\bat\s+[+-]?\d+(?:[.,]\d+)?\b)")


def _pattern():
    raw = qp.txt("scrub.embedded_number_pattern", _EMBEDDED_DEFAULT) or _EMBEDDED_DEFAULT
    try:
        return re.compile(raw)
    except re.error:
        return re.compile(_EMBEDDED_DEFAULT)


def _on():
    return (qp.txt("scrub.embedded_numbers", "on") or "on").strip().lower() != "off"


def _annotation_keys():
    """The annotation keys eligible for this scrub (vocab.measured_annotation_keys row; code default mirrors the
    seed). narrative_slots keys (insight/text/caption/…) are already scrubbed wholesale upstream — this list is the
    small residue of VALUE-adjacent caption keys."""
    keys = {str(k).lower() for k in (vocab("measured_annotation_keys") or ()) if str(k).strip()}
    return keys or {"label", "sub", "sublabel", "caption"}


def _is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def scrub_measured_annotation_strings(tree, ph):
    """Mutate `tree` in place: blank (→ `ph`) every annotation STRING that embeds a measurement token AND sits beside
    a numeric data sibling (the value it annotates). Dictionary/chrome subtrees are never entered. Returns the same
    tree; never raises on shape (defensive walk)."""
    if not _on():
        return tree
    pat = _pattern()
    ann_keys = _annotation_keys()
    dict_keys = _dictionary_subtree_keys()
    chrome_keys = _chrome_subtree_keys()

    def walk(o):
        if isinstance(o, dict):
            has_num_sibling = any(_is_num(v) for v in o.values())
            for k, v in list(o.items()):
                kl = str(k).lower()
                if "vocab" in kl or kl in dict_keys or kl in chrome_keys:
                    continue                                     # lookup-dictionary / design-chrome subtree — keep
                if isinstance(v, str):
                    if has_num_sibling and kl in ann_keys and v.strip() and pat.search(v):
                        o[k] = ph                                # embedded measurement in a data-role slot → honest ''
                else:
                    walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    try:
        walk(tree)
    except Exception:
        pass
    return tree
