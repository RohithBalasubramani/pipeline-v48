"""layer1a/parse/template_feasibility_gate.py — the WHOLE-TEMPLATE renderability gate for Layer 1a.

Rule (user 2026-07-02): a candidate template/page is DISQUALIFIED from routing when
    unrenderable_frac = (live cards with card_feasibility.verdict in drop/no_data) / (all live cards on the page)
is >= cfg('feasibility.template_max_unrenderable_frac', 0.40). The router then CHOOSES ANOTHER eligible template.
This is a whole-template drop + reselect, NOT per-card pruning — a KEPT template passes ALL its cards through and
Layer 2 force-swaps the few unrenderable ones. If EVERY candidate is disqualified, fall back to the SINGLE
least-unrenderable template so the router never routes to nothing (honest degrade).

A page with unknown counts (no page_layout_cards / total == 0) is treated as unrenderable_frac == 0 (kept) — the gate
only drops on an EXPLICIT majority-unrenderable signal, never on missing data.
"""
from config.feasibility import TEMPLATE_MAX_UNRENDERABLE_FRAC


def _frac(counts, page_key):
    c = (counts or {}).get(page_key) or {}
    total = int(c.get("total") or 0)
    if total <= 0:
        return 0.0
    return int(c.get("unrenderable") or 0) / total


def filter_renderable_templates(specs, counts, threshold=None):
    """Drop specs whose unrenderable_frac >= threshold. Return (kept_specs, dropped_page_keys).

    - specs: the already available-filtered page_specs (list of dicts with 'page_key').
    - counts: {page_key: {"total", "unrenderable"}} from read_page_feasibility.
    - threshold: override for the DB knob (defaults to cfg feasibility.template_max_unrenderable_frac).
    ALL disqualified -> keep only the least-unrenderable spec (never returns an empty kept list when specs is non-empty).
    """
    if not specs:
        return specs, []
    thr = TEMPLATE_MAX_UNRENDERABLE_FRAC if threshold is None else threshold
    kept, dropped = [], []
    for s in specs:
        if _frac(counts, s["page_key"]) >= thr:
            dropped.append(s["page_key"])
        else:
            kept.append(s)
    if kept:
        return kept, dropped
    # every candidate disqualified — fall back to the single least-unrenderable template (stable order preserved).
    best = min(specs, key=lambda s: _frac(counts, s["page_key"]))
    return [best], [s["page_key"] for s in specs if s["page_key"] != best["page_key"]]
