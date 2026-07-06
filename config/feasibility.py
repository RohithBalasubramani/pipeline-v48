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

# Layer 1a whole-template drop: a candidate template/page with >= this fraction of its live cards UNRENDERABLE is
# disqualified from routing (drop-and-reselect to another eligible template). Under it, the template is kept and
# Layer 2 force-swaps the few unrenderable cards. DB knob: cmd_catalog.app_config('feasibility.template_max_unrenderable_frac').
TEMPLATE_MAX_UNRENDERABLE_FRAC = cfg("feasibility.template_max_unrenderable_frac", 0.40)
