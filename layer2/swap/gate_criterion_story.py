"""layer2/swap/gate_criterion_story.py — the CRITERION<->STORY swap gate (T1-11, DB knob swap.criterion_story_gate,
DEFAULT OFF). A stricter sibling of gate_vague_reject: that cheap backstop only rejects a criterion drawn from the
CLOSED vague-word list ('better', 'nicer', ...); THIS gate rejects a criterion that — while not a canned vague word —
names NO word of the card's OWN analytical story angle (a swap 'to a sankey material-flow view' on a voltage-harmonics
card is off-angle even though 'sankey material flow' is a concrete phrase). gate_vague_reject STAYS the first, cheap
backstop; this runs after it.

DETERMINISTIC + fail-OPEN: tokenize BOTH the AI's criterion and the card's story via the ONE generic tokenizer
(domain.metric_affinity.metric_tokens), keep tokens >= swap.criterion_story_min_token_len (default 4), and require at
least ONE shared token. When EITHER token set is empty (no story text, a token-less criterion) the gate FAILS OPEN
(returns True) — the absence of a comparable signal is never a rejection. Disabled -> always True (byte-identical path).

The rejection is the ONLY swap gate that leaves a CORRECTIVE reason (build.py re-emits ONCE with reject_reason as the
gate feedback, then re-gates); every other gate stays a silent safe-KEEP."""
import re

from config.app_config import cfg, flag_on


def enabled():
    """DB flag swap.criterion_story_gate — DEFAULT OFF (byte-identical legacy path when off)."""
    return flag_on("swap.criterion_story_gate", False)


def _min_token_len():
    """Minimum token length kept from BOTH the criterion and the story (drop short noise). Editable DB knob."""
    return int(cfg("swap.criterion_story_min_token_len", 4))


def _tokenize(text):
    """Lowercased token SET of `text`, filtered to len >= the min-token-len knob. Uses the ONE generic tokenizer
    domain.metric_affinity.metric_tokens; if that module is unavailable, falls back to a simple alnum word-split
    (same lowercase + length filter). Empty/blank text -> empty set (drives the fail-open in ok())."""
    if not text:
        return set()
    try:
        from domain.metric_affinity import metric_tokens
        toks = metric_tokens(text)
    except Exception:
        toks = re.split(r"[^a-z0-9]+", str(text).lower())
    ml = _min_token_len()
    return {t for t in toks if t and len(t) >= ml}


def ok(decision, story_text):
    """True iff the swap MAY proceed: disabled -> True; else require >= 1 shared token between the criterion and the
    story. Fails OPEN (True) when either token set is empty (no comparable signal is never a rejection)."""
    if not enabled():
        return True
    crit_toks = _tokenize((decision or {}).get("criterion"))
    story_toks = _tokenize(story_text)
    if not crit_toks or not story_toks:
        return True                                    # fail-open: no comparable signal on one side
    return bool(crit_toks & story_toks)                # at least one shared story-angle token


def reject_reason(decision, story_text):
    """The corrective feedback for the ONE re-emit (build.py appends it verbatim to the emit user message)."""
    crit = ((decision or {}).get("criterion") or "").strip()
    return (f"swap criterion {crit!r} shares no story-angle word with this card's analytical story; either KEEP the "
            "card or name a swap criterion built from a CONCRETE word of the card's own story angle "
            "(swap.criterion_story_gate)")
