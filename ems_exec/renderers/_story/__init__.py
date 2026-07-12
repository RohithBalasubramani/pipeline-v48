"""ems_exec/renderers/_story/ — the PER-PAGE story builders for the AI-summary cards (8/19/25/28).

Each builder turns REAL neuract facts into a PRE-JUDGED `story` dict (every threshold/severity verdict already computed
in Python) plus a deterministic `fallback` one-liner templated over the SAME real numbers. The narrator (_insight.py)
then narrates ONLY the story's `text` field; on any model failure the fallback is used verbatim. A number is NEVER
fabricated: a missing metric/member honest-degrades to a "no data" story whose fallback text says so.

Mirrors the backend2 energydist.py:118-158 `_ai_story` / `_ai_fallback` pattern, one atomic file per page:
    energy_distribution  — card 8-adjacent energy-accounting page (loss %, meter gap, best path over panel members)
    voltage_current      — card 19: V/I event counts, worst severities, likely-driver hypothesis over panel members
    harmonics_pq         — card 25: worst-feeder THD / PQ compliance over panel members
    real_time_monitoring — card 8 / 28: live load %, PF, voltage deviation, phase balance for the focused feeder

build(asset, card, ctx, members) -> (story, fallback, badge)
    story    — the pre-judged dict handed to _insight.summary(fields=['text'])
    fallback — {'text': '<deterministic sentence over the real numbers>'}  (used verbatim on any model failure)
    badge    — 'review' | 'accounting'  (computed in Python from the same verdicts; the model never sets it)
"""
from ems_exec.renderers._story import (
    energy_distribution,
    voltage_current,
    harmonics_pq,
    real_time_monitoring,
)

# page_key → the builder module for that page. The renderer dispatches on ctx['page_key'].
#   individual-feeder (card 28) reuses the real_time_monitoring builder — its single-member scope selects the fused
#   per-feeder verdict path inside real_time_monitoring.build (load%/PF/deviation/phase/busbar), NOT the panel-leader one.
BUILDERS = {
    "energy-distribution": energy_distribution,
    "voltage-current": voltage_current,
    "harmonics-pq": harmonics_pq,
    "real-time-monitoring": real_time_monitoring,
    "individual-feeder": real_time_monitoring,
}

# card_id → page_key fallback, for when ctx omits page_key (the 4 AI-summary cards this renderer serves).
# Code-default MIRROR — the live map is app_config `renderers.narrative_card_page` (json; seed
# db/seed_narrative_card_page.sql), so a NEW AI-summary card on an existing page dispatches with a row edit,
# no code change. Read through card_page(), never directly.
CARD_PAGE = {
    8: "real-time-monitoring",
    19: "voltage-current",
    25: "harmonics-pq",
    28: "individual-feeder",
}


def card_page(card_id):
    """The fallback page_key for an AI-summary card: the DB map first (app_config renderers.narrative_card_page —
    json keys arrive as strings), else the CARD_PAGE code mirror. Never raises (DB outage → mirror)."""
    try:
        from config.app_config import cfg
        m = cfg("renderers.narrative_card_page", None)
        if isinstance(m, dict):
            got = m.get(str(card_id))
            if got:
                return str(got)
    except Exception:
        pass
    return CARD_PAGE.get(card_id)


__all__ = ["BUILDERS", "CARD_PAGE", "card_page",
           "energy_distribution", "voltage_current", "harmonics_pq", "real_time_monitoring"]
