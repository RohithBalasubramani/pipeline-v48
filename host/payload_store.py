"""host/payload_store.py — the card_payloads READS the host serves from: the structure-preserving honest-blank
SKELETON (payload_stripped, scalar data leaves nulled) and the RAW harvested default (the type-proof / shape oracle,
never rendered). Both cached per process; never raise. One concern; host/server re-serves through these. [atomic]
"""
from __future__ import annotations

import copy
import json

from grounding.default_assemble import null_scalar_data_leaves   # honest-blank skeleton (0.0 → None → '—')


def _as_json(v):
    """A card_payloads column value as a dict — the db_client returns JSON columns as raw strings, so parse them. Passes
    a dict through untouched; None / unparseable → None. Never raises."""
    if isinstance(v, dict):
        return v
    if isinstance(v, str) and v:
        try:
            return json.loads(v)
        except Exception:
            return None
    return None


# STRUCTURE-PRESERVING SKELETON [per-leaf-degradation: a card ALWAYS renders its REAL component] ──────────────────────
# When Layer 2 is SKIPPED (asset_no_data / asset_pending gate) or a card emitted no exact_metadata, the completed payload
# is None → the FE used to short-circuit EVERY card to the generic HonestBlank placeholder (a page of identical grey
# tiles). The mandate says a card must ALWAYS render its OWN real CMD_V2 component with the data leaves honest-blanked —
# structure preserved, never dropped. So we serve the card's HARVESTED SKELETON (card_payloads.payload_stripped: the
# default payload with every data leaf already nulled to a typed placeholder, chrome/labels intact) as the payload. The
# FE then renders <Component {...skeleton}/> in its OWN empty state (blank tiles / '—' / flat series). A card with NO
# harvested skeleton (pure narrative/chrome authored off the contract example — 6/8/160) has no skeleton to serve and
# keeps the honest machine-reason blank (it has no data leaves to preserve anyway). GENERIC — keyed only by the card's
# render identity, no per-card ids, no per-card shapes. [render-guarantee: no whole-page generic-placeholder terminal]
_SKELETON_CACHE: dict = {}


def _skeleton_payload(render_card_id):
    """The card's structure-preserving honest-blank skeleton (card_payloads.payload_stripped) for `render_card_id`, or
    None when the card has no harvested payload. Cached per process; never raises (a DB hiccup → None → the FE's honest
    machine-reason blank, never a crash). ROW CHOICE is deterministic CARD-LEVEL-FIRST (ORDER BY is_subcard, story_id
    LIMIT 1 — the grounding/default_assemble convention): a card with subcard rows must never serve a SUBCARD's shape
    as its own (card 44 got history-stats-strip's shape from an unordered rows[0], killing the clock-axis derivation
    while identical card 46 happened to get its card row). The STORED payload_stripped is already seedless (data leaves → typed
    placeholders, narrative/clock scrubbed at build time), so the honest-blank skeleton is the MINIMAL transform over
    it — null_scalar_data_leaves nulls only its scalar DATA-leaf placeholders (0.0 → None) so the host dashes them to
    '—' on a data-less asset (the card-11/74 zero family), NOT a full runtime re-strip of the raw default."""
    if render_card_id is None:
        return None
    if render_card_id in _SKELETON_CACHE:
        cached = _SKELETON_CACHE[render_card_id]
        return copy.deepcopy(cached) if cached is not None else None
    skel = None
    try:
        from data.db_client import q
        rows = q("cmd_catalog",
                 f"SELECT payload_stripped FROM card_payloads WHERE card_id='{int(render_card_id)}' "
                 f"ORDER BY is_subcard, story_id LIMIT 1")
        if rows:
            ps = _as_json(rows[0][0])
            # HONEST-BLANK skeleton: the stored seedless skeleton with its scalar data-leaf placeholders nulled (0.0 →
            # None → the host dashes '—'), so a data-less asset never renders a FABRICATED '0.0 V'. Array/series leaves
            # and all chrome stay byte-identical. None (un-built row) → None so the structure honestly degrades to blank.
            if isinstance(ps, dict):
                skel = null_scalar_data_leaves(ps)
    except Exception:
        skel = None
    _SKELETON_CACHE[render_card_id] = skel
    return copy.deepcopy(skel) if skel is not None else None


_RAW_DEFAULT_CACHE: dict = {}


def _raw_default_payload(render_card_id):
    """The card's RAW harvested default payload (card_payloads.payload) for `render_card_id`, or None. Used ONLY as the
    type-proof reference for the honest-dash policy on a served skeleton and as the executor's SHAPE ORACLE (never
    rendered — a raw default carries seed numbers). Deterministic CARD-LEVEL-FIRST row choice (ORDER BY is_subcard,
    story_id LIMIT 1) — see _skeleton_payload. Cached; never raises."""
    if render_card_id is None:
        return None
    if render_card_id in _RAW_DEFAULT_CACHE:
        return _RAW_DEFAULT_CACHE[render_card_id]
    pl = None
    try:
        from data.db_client import q
        rows = q("cmd_catalog", f"SELECT payload FROM card_payloads WHERE card_id='{int(render_card_id)}' "
                                f"ORDER BY is_subcard, story_id LIMIT 1")
        if rows:
            pl = _as_json(rows[0][0])
    except Exception:
        pl = None
    _RAW_DEFAULT_CACHE[render_card_id] = pl
    return pl
