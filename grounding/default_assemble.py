"""grounding/default_assemble.py — build a card's subcard-inclusive DEFAULT payload STATUS: the byte-identical
harvested default with (a) its subcards nested at their slots, (b) the correct variant chosen by slot identity, (c) a
component-sibling fallback when the card itself has no default, (d) ALL data-leaf values stripped to typed
placeholders, and (e) fabricated narrative literals scrubbed. ZERO AI — this is a deterministic transform over the
harvested `card_payloads` rows + `card_component_usage` (both editable DB tables).

WHY: Layer 3 must be shown the card's default SHAPE (which slots exist, which are metadata chrome vs data) WITHOUT any
fabricated demo number/text — otherwise the AI (and, worse, the resting render) leaks Storybook literals as if live
(card 41's "loss 43.0 kW", card 8's "DG load remains near 80%"). And a card with no harvested default must not fall to
the raw contract EXAMPLE payload — it should reuse a SIBLING card's default for the SAME primary component.

Covers:
  · [META-06] subcard structural defaults dropped → nest each subcard's default at its key_roles slot (subcard-inclusive).
  · [META-07] multiple non-subcard payloads → pick the default by SLOT IDENTITY (variant/story match), not alphabetically.
  · [META-01/05] no default → COMPONENT-LEVEL sibling fallback (a card that DOES have a default for the same primary
    component); if none, honest 'no default'.
  · [VC-02] Storybook demo values leaked as live → strip every data leaf to a typed placeholder + scrub fabricated
    narrative text so the default carries NO fabricated metric.

Every policy (typed-placeholder values, the narrative-slot scrub list) is an editable row read via `config.*`. No
hardcoded field names / magic values in logic.
"""
from __future__ import annotations

import copy

from config import quality_policy as qp
from config import reason_templates as rt
from data.db_client import q
from layer2.catalog.card_payload import default_for
from validate.leaf_classify import classify
from validate.payload_lookup import card_payloads_for


# ── typed placeholders (editable policy) ──────────────────────────────────────────────────────────
# A data leaf is stripped to a TYPED zero so the CMD_V2 component still mounts with the right prop type (a number prop
# stays a number, an array prop stays an array) — never a fabricated demo value. The zero VALUES are editable rows.
def _placeholder(kind):
    if kind == "scalar":
        # numeric 0.0 keeps the prop numeric; overridable via placeholder.scalar (e.g. to null).
        v = qp.txt("placeholder.scalar", "0")
        try:
            return float(v)
        except (TypeError, ValueError):
            return 0.0
    # array / series → an empty list keeps the prop iterable without any fabricated points.
    return []


# ── narrative-slot scrub list (editable policy) ───────────────────────────────────────────────────
# Metadata STRING leaves whose last path segment is one of these are AI-authored narrative that embed a fabricated
# metric ("Active power loss is 43.0 kW …"). They are scrubbed to a neutral placeholder so the resting default carries
# no fabricated text. The list is a comma-separated editable policy row (quality_policy 'narrative_slots').
def _narrative_slots():
    raw = qp.txt("narrative_slots",
                 "insight,text,summary,note,caption,subtitle,likelysource,nextpriority,"
                 "trendlabel,message,headline,description,detail,commentary")
    return {s.strip().lower() for s in raw.split(",") if s.strip()}


def _narrative_placeholder():
    # empty string keeps the prop a string; the reason channel carries the honest 'awaiting live data' note separately.
    return qp.txt("placeholder.narrative", "")


def _esc(s):
    return str(s).replace("'", "''")


def _last_seg(path):
    """The trailing key of a classify path ('data.insight' → 'insight', 'snapshot.h5.valuePct' → 'valuePct')."""
    if not path:
        return ""
    seg = path.rsplit(".", 1)[-1]
    return seg.split("[", 1)[0].lower()          # drop any list index


def _set_at(tree, path, value):
    """Set `value` at a classify-style dotted/indexed path inside `tree` (mutates in place). Silently no-ops on a path
    that no longer exists (defensive — the tree came straight from classify's own walk of the SAME object)."""
    parts, i, cur = [], 0, path
    # tokenize dotted keys + [idx] segments
    token = ""
    for ch in path:
        if ch == ".":
            if token:
                parts.append(token); token = ""
        elif ch == "[":
            if token:
                parts.append(token); token = ""
            token = "["
        elif ch == "]":
            parts.append(int(token[1:])); token = ""
        else:
            token += ch
    if token:
        parts.append(token)
    node = tree
    for p in parts[:-1]:
        try:
            node = node[p]
        except (KeyError, IndexError, TypeError):
            return
    last = parts[-1]
    try:
        node[last] = value
    except (KeyError, IndexError, TypeError):
        return


def _strip_and_scrub(payload):
    """Return a DEEP COPY of `payload` with every DATA leaf stripped to a typed placeholder and every narrative-slot
    metadata string scrubbed. The metadata chrome (colors, labels, units, structural booleans) is left byte-identical."""
    out = copy.deepcopy(payload)
    split = classify(payload)
    # 1) strip data leaves (the fabricated demo numbers/arrays/series) to typed placeholders. [VC-02]
    for d in split["data_leaves"]:
        _set_at(out, d["path"], _placeholder(d["kind"]))
    # 2) scrub narrative-slot metadata strings (fabricated metric text). [VC-02, META-01]
    narrative = _narrative_slots()
    ph = _narrative_placeholder()
    _walk_scrub(out, "", narrative, ph)
    return out


def _walk_scrub(o, path, narrative, ph):
    if isinstance(o, dict):
        for k, v in list(o.items()):
            child = f"{path}.{k}" if path else k
            if isinstance(v, str) and k.lower() in narrative:
                o[k] = ph
            else:
                _walk_scrub(v, child, narrative, ph)
    elif isinstance(o, list):
        for i, v in enumerate(o):
            _walk_scrub(v, f"{path}[{i}]", narrative, ph)


# ── slot-identity variant selection [META-07] ─────────────────────────────────────────────────────
def _pick_default_row(card_id, page_key, variant_hint=None, story_hint=None):
    """Choose the card's default (non-subcard) payload row by SLOT IDENTITY, not alphabetically. When the card has >1
    non-subcard row, prefer an exact story_id match, then a variant match; else fall back to the row default_for picks
    (rows[0]) so behaviour never regresses. Returns the row dict or None."""
    rows = card_payloads_for(card_id, page_key, include_subcards=False)
    if not rows:
        return None
    if story_hint:
        for r in rows:
            if r["story_id"] == story_hint:
                return r
    if variant_hint:
        for r in rows:
            if (r.get("variant") or "") == variant_hint:
                return r
    return rows[0]


# ── component-sibling fallback [META-01/05] ───────────────────────────────────────────────────────
def _primary_component(card_id):
    """The card's PRIMARY CMD_V2 component name (card_component_usage.is_primary). Drives the sibling-default reuse for
    a card that has no default of its own (e.g. card 8 AiSummary → reuse card 19/25's AiSummary default)."""
    rows = q("cmd_catalog",
             "SELECT component_name FROM card_component_usage "
             f"WHERE card_id={int(card_id)} AND is_primary='t' LIMIT 1")
    return rows[0][0] if rows and rows[0] and rows[0][0] else None


def _sibling_default(card_id):
    """A default payload from a SIBLING card that shares this card's primary component AND has a harvested default.
    Returns (payload, sibling_card_id, page_key, story_id) or None. This lets cards 6/8/160 reuse the
    LiveScrubberBar/AiSummary defaults harvested for 19/25 instead of the raw contract example. [META-01/05]"""
    comp = _primary_component(card_id)
    if not comp:
        return None
    rows = q("cmd_catalog",
             "SELECT DISTINCT u.card_id FROM card_component_usage u "
             f"WHERE u.component_name='{_esc(comp)}' AND u.is_primary='t' "
             f"AND u.card_id <> {int(card_id)} "
             "AND EXISTS (SELECT 1 FROM card_payloads p "
             "            WHERE p.card_id=u.card_id AND p.is_subcard=false) "
             "ORDER BY u.card_id")
    for r in rows:
        sib = int(r[0])
        # sibling may live on a different page_key — pull its default row directly (any page_key).
        srows = q("cmd_catalog",
                  "SELECT page_key, story_id FROM card_payloads "
                  f"WHERE card_id={sib} AND is_subcard=false ORDER BY story_id LIMIT 1")
        if not srows or not srows[0]:
            continue
        page_key, story_id = srows[0][0], srows[0][1]
        full = card_payloads_for(sib, page_key, include_subcards=False)
        if full:
            return full[0]["payload"], sib, page_key, story_id
    return None


# ── subcard-inclusive assembly [META-06] ──────────────────────────────────────────────────────────
def _nest_subcards(parent_payload, card_id, page_key):
    """Nest each subcard's (stripped) default under the parent at its slot. A subcard's `key_roles` names its target
    slot key; we nest the subcard payload's single content object at that key when the parent exposes it. Missing slots
    are left as-is (the parent's own default already carries them). Returns (assembled, subcard_count)."""
    rows = card_payloads_for(card_id, page_key, include_subcards=True)
    subs = [r for r in rows if r.get("is_subcard")]
    if not subs:
        return parent_payload, 0
    assembled = copy.deepcopy(parent_payload)
    nested = 0
    for s in subs:
        sp = s.get("payload") or {}
        # a subcard payload is typically {<slot>: {...}, "variant": "..."}; nest the non-variant content object(s).
        for k, v in sp.items():
            if k == "variant":
                continue
            if k in assembled and isinstance(assembled.get(k), list) and isinstance(v, (dict, list)):
                assembled[k].append(_strip_and_scrub({k: v})[k]); nested += 1
            elif k not in assembled:
                assembled[k] = _strip_and_scrub({k: v})[k]; nested += 1
    return assembled, nested


def assemble(card_id, page_key, *, variant_hint=None, story_hint=None):
    """Build the card's default-payload STATUS fact-sheet (subcard-inclusive, variant-correct, sibling-fallback,
    values stripped, literals scrubbed). NO AI, NO fetched number.

    Returns:
        {
          has_default: bool,               # True → a byte-identical default exists (own or sibling)
          source: 'own' | 'sibling' | None,# where the default came from
          story_id, variant,               # the chosen slot identity
          sibling_card_id,                 # set when source='sibling'
          payload,                          # the stripped + scrubbed + subcard-assembled default (or None)
          subcard_count,                    # how many subcard defaults were nested [META-06]
          data_leaf_count,                  # how many data leaves were stripped to placeholders
          reason,                           # honest reason when has_default=False, else None
        }
    """
    out = {
        "has_default": False, "source": None, "story_id": None, "variant": None,
        "sibling_card_id": None, "payload": None, "subcard_count": 0,
        "data_leaf_count": 0, "reason": None,
    }

    row = _pick_default_row(card_id, page_key, variant_hint=variant_hint, story_hint=story_hint)
    if row is not None:
        parent = row["payload"]
        assembled, nsub = _nest_subcards(parent, card_id, page_key)
        stripped = _strip_and_scrub(assembled)
        out.update(has_default=True, source="own", story_id=row["story_id"],
                   variant=row.get("variant"), payload=stripped, subcard_count=nsub,
                   data_leaf_count=len(classify(parent)["data_leaves"]))
        return out

    # [META-01/05] no own default → component-sibling fallback.
    sib = _sibling_default(card_id)
    if sib is not None:
        payload, sib_id, sib_page, sib_story = sib
        stripped = _strip_and_scrub(payload)
        out.update(has_default=True, source="sibling", story_id=sib_story, variant=None,
                   sibling_card_id=sib_id, payload=stripped,
                   data_leaf_count=len(classify(payload)["data_leaves"]),
                   reason=rt.reason("literal_scrubbed"))
        return out

    # no own default AND no sibling → honest 'no default' (caller honest-blanks the card).
    out["reason"] = rt.reason("no_default_payload", card_id=card_id)
    return out


def has_default(card_id, page_key):
    """Convenience boolean: does this card have a recoverable (own OR sibling) default? Used by the swap-pool filter."""
    return assemble(card_id, page_key)["has_default"]
