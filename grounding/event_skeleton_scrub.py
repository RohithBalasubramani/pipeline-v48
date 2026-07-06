"""grounding/event_skeleton_scrub.py — empty SEED EVENT-INSTANCE LISTS in the build-time skeleton (one concern).

WHY (seed-leak class d): an event/anomaly INSTANCE list in a harvested default (c67 data.events[5], c42
data.anomalies[5], DG chart.events[1..2], voltage-history history.data.events[12]) survives the strip as a SKELETON —
leaf_classify calls the list a series and zeroes each element's numbers, role_scrub blanks each element's assertion
strings — but the ELEMENT COUNT itself is data: N skeleton rows render N ghost event markers 'as if real' on an asset
with ZERO live events. The honest rest state of an occurrence list is EMPTY.

Rule (role-based, zero card_id): a LIST under an event-parent key (config vocab role_scrub.event_parents — the same
role vocabulary role_scrub uses for its string blanks) is emptied to []. A singular event OBJECT (dict) is untouched
(role_scrub blanks its strings; its shape is chrome). Lookup dictionaries are exempt by the ancestor rule
(eventTypeKeys / eventModeOrder / *Vocab / legend — role_scrub.dictionary_subtree_keys).

BUILD-TIME ONLY: invoked by grounding.default_assemble._strip_and_scrub (persisted into payload_stripped, and folded
into the no-default free-metadata enforce). The runtime graft (blank_data_leaves) is NOT routed here — a graft imports
a container the AI explicitly bound, and the declared per-element fill needs the element template. On a missing vocab
row / DB outage the parent list is the code default mirror (db/seed_role_scrub_vocab.sql), so behavior never silently
widens or narrows to a fabricated guess.
"""
from __future__ import annotations

from grounding.role_scrub import _dictionary_subtree_keys, _event_parents


def empty_event_instance_lists(tree):
    """Mutate `tree` in place: every LIST sitting at an event-parent key (role_scrub.event_parents) becomes [] —
    the seedless rest state of an occurrence list. Dictionary subtrees (*Vocab / eventTypeKeys / legend / …) are
    never descended into. Returns the same tree; never raises on shape (defensive walk)."""
    parents = _event_parents()
    dict_keys = _dictionary_subtree_keys()

    def walk(o):
        if isinstance(o, dict):
            for k, v in list(o.items()):
                kl = str(k).lower()
                if "vocab" in kl or kl in dict_keys:
                    continue                                     # lookup-dictionary subtree — keep byte-identical
                if kl in parents and isinstance(v, list):
                    if v:
                        o[k] = []                                # N ghost instances → honest empty occurrence list
                    continue
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    try:
        walk(tree)
    except Exception:
        pass
    return tree
