"""config/feasibility.py — the render-feasibility knobs shared by the RENDERABILITY GATE (Layer 1a template drop, Layer 2
per-card enforce). Tune here (or in the DB via cmd_catalog.app_config), not inline. [renderability gate; user 2026-07-02]

card_feasibility.verdict vocabulary (per card_id, read in layer2/catalog/feasibility.py):
    render_real    — real data, RENDERS                    -> renderable
    static_chrome  — headers/controls only, still RENDERS  -> renderable (counts toward the page, NOT unrenderable)
    drop           — cannot render                          -> UNRENDERABLE
    no_data        — no data to render                      -> UNRENDERABLE
"""
from config.app_config import cfg

# verdicts that mean "this card CANNOT be shown" — everything else (incl. static_chrome) renders SOMETHING.
UNRENDERABLE_VERDICTS = tuple(cfg("feasibility.unrenderable_verdicts", ["drop", "no_data"]))

# DATALESS SWAP [#1 'card swap should work here']: the STATIC card_feasibility.verdict answers "can this KIND of card ever
# render real data" — it CANNOT know that THIS asset has no column to feed a catalog-renderable card (a Fuel Tank on a
# DG whose electrical meter logs no fuel; a Load Anomalies with no anomaly telemetry). The AI already emits that per-asset
# truth as answerability="none" (line 96 of data_instructions_v2.md: "the CORE question cannot be answered by ANY real
# column ... signals the orchestrator to re-route"). These answerability values mark a card WHOLLY unfillable FOR THIS
# ASSET → the render-gate treats it like an unrenderable verdict and force-swaps it to a fillable same-page candidate
# (candidates.py already filters the pool to render_real). When NO unclaimed candidate exists (a whole-page dead-end — a
# fuel page where every card needs fuel data) it honestly KEEPS the card (never fabricates). DB knobs:
# cmd_catalog.app_config('feasibility.dataless_answerability' / 'feasibility.force_swap_on_dataless').
DATALESS_ANSWERABILITY = tuple(cfg("feasibility.dataless_answerability", ["none"]))
FORCE_SWAP_ON_DATALESS = str(cfg("feasibility.force_swap_on_dataless", "on")).strip().lower() not in ("off", "", "0", "false", "no", "none")

# Layer 1a whole-template drop: a candidate template/page with >= this fraction of its live cards UNRENDERABLE is
# disqualified from routing (drop-and-reselect to another eligible template). Under it, the template is kept and
# Layer 2 force-swaps the few unrenderable cards. DB knob: cmd_catalog.app_config('feasibility.template_max_unrenderable_frac').
TEMPLATE_MAX_UNRENDERABLE_FRAC = cfg("feasibility.template_max_unrenderable_frac", 0.40)
