"""ems_exec/renderers/narrative_ai.py — the NARRATIVE AI-summary renderer for the AI Summary cards (8/19/25/28).

These cards render OUTSIDE the per-card column-fill executor because they need the LLM (the executor has no LLM). The
flow is the grounded-narration contract (backend2 energydist.py:329-346):

  1. Build a PRE-JUDGED `story` from REAL neuract facts (panel fan-out + latest/window reads) — a per-page builder in
     _story/ computes the BADGE and EVERY verdict in PYTHON. A missing number honest-degrades to a "no data" story.
  2. The LLM only NARRATES fields=['text'] over that story (_insight.summary — cached, thinking-off, fallback-guarded).
  3. On ANY model failure the builder's deterministic fallback text (a template over the SAME real neuract numbers) is
     used VERBATIM. A number is NEVER fabricated — the model may only rephrase facts already in the story.

Emits: payload['widgets']['ai_summary'] = {'badge': 'review'|'accounting', 'text': '<one factual sentence>'}
(placed on both payload['widgets'] and, when the CMD_V2 skeleton nests under `data`, payload['data'] — whichever the
card's payload actually carries, so the FE's own AISummary widget reads it; a card with neither leaf still gets a
top-level 'ai_summary' so nothing is silently dropped).

render(asset, card, ctx) -> payload   (sync)
ctx = {asset_table, mfm_id, db_link, window, page_key}. DATA = NEURACT ONLY. DB-driven knobs. [atomic; honest-degrade]
"""
from __future__ import annotations

import copy

from ems_exec.renderers import _insight
from ems_exec.renderers._story import BUILDERS, card_page
from ems_exec.renderers._story import _facts

# the card_handling classes this renderer serves — the package __init__ discovers this declaration (self-registration)
HANDLING_CLASSES = ("narrative_ai",)

_FIELDS = ["text"]


# ── page/card resolution ─────────────────────────────────────────────────────────────────────────────────────────────
def _page_key(card, ctx):
    """The page_key to dispatch on: ctx first, else the card_id fallback map (DB-editable via app_config
    renderers.narrative_card_page, code mirror = the 4 AI-summary cards). None if unknown."""
    pk = (ctx or {}).get("page_key")
    if pk in BUILDERS:
        return pk
    cid = _card_id(card)
    return card_page(cid)


def _card_id(card):
    if isinstance(card, dict):
        for k in ("id", "card_id", "cid"):
            v = card.get(k)
            try:
                return int(v)
            except (TypeError, ValueError):
                continue
    try:
        return int(card)
    except (TypeError, ValueError):
        return None


# ── story build (shared by sync + async paths) ───────────────────────────────────────────────────────────────────────
def _story(asset, card, ctx):
    """(story, fallback, badge) from the page builder — or a generic no-data triple when no builder matches / it errors.

    The badge and every verdict are computed in PYTHON here; the LLM never sees the badge. Honest-degrade: an unmapped
    page or a builder exception falls back to a factual 'summary unavailable' line, never a fabricated status."""
    page_key = _page_key(card, ctx)
    builder = BUILDERS.get(page_key)
    if builder is None:
        return _generic_no_data(ctx)
    try:
        members = _facts.resolve_members(ctx)                   # (members, coverage) — shared across builders
        story, fb, badge = builder.build(asset, card, ctx, members)
        return _with_asked_about(story, ctx), fb, badge
    except Exception:
        return _generic_no_data(ctx)


def _with_asked_about(story, ctx):
    """Thread the user's ASKED-ABOUT quantity (the 1a `metric`, e.g. 'voltage') into the story so the narrator LEADS with
    it (see _insight._SYSTEM). GENERIC for every narrative page (keyed on ctx.metric, never a card id); absent metric →
    story unchanged, so behaviour is identical until exec threads the ask."""
    if isinstance(story, dict):
        m = (ctx or {}).get("metric")
        if m and not story.get("asked_about"):
            story["asked_about"] = str(m)
    return story


def _generic_no_data(ctx):
    name = _facts._name_for((ctx or {}).get("mfm_id")) or (ctx or {}).get("asset_table") or "the selected scope"
    story = {"subject": name, "status": "summary_unavailable"}
    fb = {"text": "AI summary unavailable for %s — no metered data resolved for the selected scope." % name}
    return story, fb, "accounting"


# A NO-DATA DEGRADATION story: every page builder's honest no-data path (and the generic fallback) sets one of these
# `status` values; a REAL story carries NO status key at all. Used to mark the ai_summary widget as a degradation so the
# render verdict does NOT credit an honest "no metered data" sentence as a real answered leaf (empty-panel honest-blank
# must survive — otherwise a dark PCC panel would falsely verdict partial/answered). GENERIC (status vocab, no card id).
_DEGRADED_STATUS = frozenset({"no_vi_data", "no_harmonics_data", "no_energy_accounted",
                              "no_live_data", "summary_unavailable"})


def _is_degraded(story):
    """True iff the story is an honest NO-DATA degradation (its `status` ∈ the no-data vocab). A real story has no
    status → False. Never raises."""
    try:
        return isinstance(story, dict) and story.get("status") in _DEGRADED_STATUS
    except Exception:
        return False


def _widget(text, badge, degraded=False):
    # `degraded` key added ONLY for a no-data narrative → a REAL narrative keeps the exact {badge, text} shape unchanged.
    w = {"badge": badge, "text": text}
    if degraded:
        w["degraded"] = True
    return w


def _thread_headline(node, text):
    """BACKEND-PARAGRAPH SEAM [family H, cards 19/25]: CMD_V2's AI-summary cards read `pres.backendHeadline` (V&C) /
    the `backendAiSummary` prop (HPQ) and only fall back to a LOCAL composition — which derefs the stats tree
    UNGUARDED and throws on an honest-blank payload. Thread the REAL generated sentence into every presentation dict
    that carries the seam (an explicit blank 'backendHeadline' key, or a template 'vocab' dict — the AI-pres
    signature) so the designed override path renders it and the crashing local compose never runs. Real text only;
    blank-only writes; extra keys on non-consumer dicts are inert props."""
    if isinstance(node, dict):
        if node.get("backendHeadline") in (None, "") and ("backendHeadline" in node or isinstance(node.get("vocab"), dict)):
            node["backendHeadline"] = text
        for v in node.values():
            _thread_headline(v, text)
    elif isinstance(node, list):
        for v in node:
            _thread_headline(v, text)


def _emit(payload, widget):
    """Place the ai_summary widget where the card's CMD_V2 skeleton carries it: under `widgets` and/or `data`, else at
    the top level. NEVER nulls an existing array/dict leaf elsewhere — only writes the ai_summary slot (and threads
    the same REAL text into the CMD_V2 backendHeadline seam — see _thread_headline)."""
    out = copy.deepcopy(payload) if isinstance(payload, dict) else {}
    placed = False
    for container_key in ("widgets", "data"):
        node = out.get(container_key)
        if isinstance(node, dict):
            node["ai_summary"] = widget
            placed = True
    if not placed:
        # no widgets/data container in the skeleton → make a widgets container so the FE contract still holds
        out.setdefault("widgets", {})["ai_summary"] = widget
    # also mirror at the top level for callers/tests that read payload['ai_summary'] directly (harmless duplicate)
    out["ai_summary"] = widget
    if isinstance(widget.get("text"), str) and widget["text"].strip():
        _thread_headline(out, widget["text"])
    return out


# ── public API ───────────────────────────────────────────────────────────────────────────────────────────────────────
def render(asset, card, ctx):
    """SYNC render → the completed payload with widgets.ai_summary = {badge, text}. Uses the cached, fallback-guarded
    narrator (summary_sync); the model narrates only `text`, badge is the Python verdict. Never raises."""
    ctx = ctx or {}
    story, fallback, badge = _story(asset, card, ctx)
    degraded = _is_degraded(story)                             # honest no-data narrative → not a real answered leaf
    binds = _pop_binds(story)                                   # lift the builder's real-fact leaf binds (narrator MUST NOT see them)
    try:
        result = _insight.summary_sync(story, fields=_FIELDS, fallback=fallback)
        text = (result or {}).get("text") or fallback["text"]
    except Exception:
        text = fallback["text"]
    return _bind_leaves(_emit(_honest_skeleton(card), _widget(text, badge, degraded)), binds)


def _pop_binds(story):
    """Lift the page builder's payload-leaf bindings out of the story — a PRIVATE `_leaf_binds` key the narrator must
    NOT see (it is a bind spec, not a fact to narrate). A builder MAY declare story['_leaf_binds'] = {dotted_leaf_path:
    real_value} for facts it ALREADY computed that map to the card's REAL payload leaves (worst-V/I member+magnitude,
    period label). Absent → {} → no binding (every other narrative page is byte-unchanged)."""
    if isinstance(story, dict):
        b = story.pop("_leaf_binds", None)
        if isinstance(b, dict):
            return b
    return {}


def _bind_leaves(payload, binds):
    """Write each builder-declared REAL fact into the matching EXISTING payload leaf so it renders REAL instead of a
    stripped 0.0 / nulled placeholder / surviving seed. ZERO-FABRICATION: values are the builder's OWN computed facts,
    and ONLY a leaf the skeleton already carries is filled (never grows the shape). Tolerates the CMD_V2 `data.<slot>`
    nesting. GENERIC (applies whatever binds the page builder declared); never raises. [F5 unaudited-side-channel fix]"""
    if not (isinstance(payload, dict) and isinstance(binds, dict) and binds):
        return payload
    try:
        from ems_exec.executor.paths import _has_path, _set_leaf_typed
        for path, val in binds.items():
            if val is None or not path:
                continue
            p = str(path)
            for cand in (p, ("data." + p) if not p.startswith("data.") else p[5:]):
                if _has_path(payload, cand):
                    _set_leaf_typed(payload, cand, val)          # scalar leaf ← real value (arrays/dicts untouched)
                    break
    except Exception:
        pass
    return payload


def _honest_skeleton(card):
    """The card's skeleton with every SCALAR data-leaf placeholder nulled (0.0 → None → the host dashes '—').

    ZERO-SKELETON HONESTY [cards 19/25, 2026-07-06]: this renderer fills ONLY the ai_summary widget — the rest of the
    skeleton rides through untouched, and the L2 emission is the STRIPPED default whose data leaves are 0.0 typed
    placeholders. Emitted verbatim they render a false '0 issues' story (stats.total=0.0 beside a sibling card whose
    real total is 1) while the verdict channel already knows the card is honest_blank. Same transform the host's
    skeleton-blank path uses (grounding.default_assemble.null_scalar_data_leaves); the per-leaf reasons ride
    di._emit_gaps → render.gaps (host merge). Never raises — on any failure the raw skeleton stands."""
    skel = _payload_of(card)
    try:
        from grounding.default_assemble import null_scalar_data_leaves
        out = null_scalar_data_leaves(skel)
        return out if isinstance(out, dict) else skel
    except Exception:
        return skel


def _payload_of(card):
    """The card's exact_metadata payload skeleton to fill (so the ai_summary lands on the real CMD_V2 shape). {} when the
    card carries no payload — the emitter then creates a widgets container so the FE contract still holds."""
    if isinstance(card, dict):
        for k in ("payload", "exact_metadata", "skeleton"):
            v = card.get(k)
            if isinstance(v, dict):
                return v
    return {}
