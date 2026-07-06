"""config/gates_vocab.py — THE one accessor for the gates.fields_optional_classes vocabulary. [A6a mirror-drift fix]

Handling classes whose cards carry NO data_instructions.fields (pure chrome / run_special widget builders /
panel_aggregate member-aggregation consumers). ONE DB row (app_config gates.fields_optional_classes) read through ONE
code default — imported by layer2/emit/user_message.py (the prompt), layer2/build.py (the gate) and validate/build.py
(the pre-emit gap scan), so the prompt and the gates can NEVER disagree again (the 4-of-5 drift put panel_aggregate
cards on opposite sides of the prompt vs the gate whenever the DB row was unreadable)."""
from config.app_config import cfg

# Code default MIRRORS the seeded DB row (5 entries) — DB-outage parity, never a second vocabulary.
FIELDS_OPTIONAL_DEFAULT = ["nav_index", "narrative_ai", "topology_sld", "asset_3d", "panel_aggregate"]


def fields_optional_classes():
    """The DB-driven set (app_config gates.fields_optional_classes), code default = the same 5 seeded entries."""
    return set(cfg("gates.fields_optional_classes", FIELDS_OPTIONAL_DEFAULT))
