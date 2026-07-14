"""config/feasibility.py — the render-feasibility knobs shared by the RENDERABILITY GATE (Layer 1a template drop, Layer 2
per-card enforce). Tune here (or in the DB via cmd_catalog.app_config), not inline. [renderability gate; user 2026-07-02]

card_feasibility.verdict vocabulary (per card_id, read in layer2/catalog/feasibility.py):
    render_real    — real data, RENDERS                    -> renderable
    static_chrome  — headers/controls only, still RENDERS  -> renderable (counts toward the page, NOT unrenderable)
    drop           — cannot render                          -> UNRENDERABLE
    no_data        — no data to render                      -> UNRENDERABLE
"""
from config.app_config import cfg, flag_on

# LAZY module attributes (PEP 562): each access re-reads cfg(), so a DB row edit + app_config.reload() reaches
# consumers without a process restart (import-time binding pinned the boot-time value for the process life).
_LAZY = {
    # verdicts that mean "this card CANNOT be shown" — everything else (incl. static_chrome) renders SOMETHING.
    "UNRENDERABLE_VERDICTS": lambda: tuple(cfg("feasibility.unrenderable_verdicts", ["drop", "no_data"])),
    "DATALESS_ANSWERABILITY": lambda: tuple(cfg("feasibility.dataless_answerability", ["none"])),
    "FORCE_SWAP_ON_DATALESS": lambda: (str(cfg("feasibility.force_swap_on_dataless", "on")).strip().lower()
                                       not in ("off", "", "0", "false", "no", "none")),
    # T1-12 DATALESS AI-NOMINATION (DB knob swap.dataless_nomination, DEFAULT OFF): when on, a pure per-asset DATALESS
    # force-swap honors the AI's OWN swap target (if it is a valid, unclaimed pool candidate) instead of the closest-
    # size default. Off = byte-identical closest-size behavior.
    "DATALESS_NOMINATION": lambda: flag_on("swap.dataless_nomination", False),
    "TEMPLATE_MAX_UNRENDERABLE_FRAC": lambda: cfg("feasibility.template_max_unrenderable_frac", 0.40),
}


def __getattr__(name):
    if name in _LAZY:
        return _LAZY[name]()
    raise AttributeError(f"module 'config.feasibility' has no attribute {name!r}")

# DATALESS SWAP [#1 'card swap should work here'] — DATALESS_ANSWERABILITY / FORCE_SWAP_ON_DATALESS (lazy attrs above):
# the STATIC card_feasibility.verdict answers "can this KIND of card ever render real data" — it CANNOT know that THIS
# asset has no column to feed a catalog-renderable card (a Fuel Tank on a DG whose electrical meter logs no fuel; a Load
# Anomalies with no anomaly telemetry). The AI already emits that per-asset truth as answerability="none"
# (data_instructions_v2.md: "the CORE question cannot be answered by ANY real column ... signals the orchestrator to
# re-route"). These answerability values mark a card WHOLLY unfillable FOR THIS ASSET → the render-gate treats it like
# an unrenderable verdict and force-swaps it to a fillable same-page candidate (candidates.py already filters the pool
# to render_real). When NO unclaimed candidate exists (a whole-page dead-end) it honestly KEEPS the card.
#
# TEMPLATE_MAX_UNRENDERABLE_FRAC (lazy attr above) — Layer 1a whole-template drop: a candidate template/page with
# >= this fraction of its live cards UNRENDERABLE is disqualified from routing (drop-and-reselect); under it, the
# template is kept and Layer 2 force-swaps the few unrenderable cards.
