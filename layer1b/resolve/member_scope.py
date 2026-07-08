"""layer1b/resolve/member_scope.py — the PANEL READING DIRECTION a prompt asks for. ONE concern, DB-vocab-driven.

A panel-overview page (panel-overview-shell/*) aggregates its member meters. A panel has TWO member sides:
  · OUTGOING (fed feeders / bays / loads the panel distributes to) — the panel's DISTRIBUTION side, and the DEFAULT
    reading direction for a plain panel prompt ('voltage and current for PCC-1A' → the outgoing bays' readings).
  · INCOMER (supply / source / upstream transformers+incomers that FEED the panel) — used ONLY when the prompt
    EXPLICITLY asks for the incoming/supply side ('incomer PCC-1A', 'PCC-1A supply voltage').

This resolves that single bit from the prompt words against a cmd_catalog vocab (app_config `vocab.panel_member_direction`,
incomer-keyword list) — so 'incomer'/'incoming'/'supply'/'source'/'upstream'/'ht side'/'feed-in' select INCOMER and
everything else defaults to OUTGOING. Deterministic + config-driven (NO code literal is the source of truth — the DB row
is; the tuple below is only the DB-down fallback mirror). The chosen direction is stamped on the resolved asset
(`asset['member_scope']`) so the Layer-2 PANEL MEMBERS facts + the panel-aggregate fill read the SAME single decision.

Harmless for non-panels (the flag is only consulted when the asset has_feeders). Never raises. [atomic; AI-first-adjacent]
"""
from __future__ import annotations

# DB-DOWN FALLBACK MIRROR ONLY — the authoritative list is app_config row `vocab.panel_member_direction`
# (seed: db/seed_member_scope_vocab.sql). Keep the two in sync; the DB row wins whenever it is reachable.
_INCOMER_KEYWORDS_DEFAULT = (
    "incomer", "incomers", "incoming", "supply", "supply side", "source side",
    "upstream", "ht side", "hv side", "feed-in", "feed in", "in-feed", "infeed",
)

OUTGOING = "outgoing"
INCOMER = "incomer"


def _incomer_keywords():
    """The incomer-selecting keyword list from the DB vocab, or the code mirror on miss/outage (honest degrade)."""
    try:
        from config.vocab import vocab
        got = vocab("panel_member_direction")
        # accept either a bare list or {'incomer':[...]} shape so the seed can grow without a code edit
        if isinstance(got, dict):
            got = got.get("incomer")
        if isinstance(got, (list, tuple)) and got:
            return tuple(str(k).lower() for k in got)
    except Exception:
        pass
    return _INCOMER_KEYWORDS_DEFAULT


def member_scope(prompt):
    """'incomer' when the prompt explicitly names the supply/incoming side, else 'outgoing' (the default). Never raises."""
    try:
        p = f" {str(prompt or '').lower()} "
        for kw in _incomer_keywords():
            k = str(kw).lower().strip()
            if k and k in p:
                return INCOMER
    except Exception:
        pass
    return OUTGOING
