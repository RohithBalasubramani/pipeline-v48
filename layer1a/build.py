"""layer1a/build.py — compose Layer 1a end to end: route -> per-card stories -> page layout -> partition -> Layer1aOutput. [spec section 2 L1a, contract 2]"""
from layer1a.route import route
from layer1a.story_builder import build_stories
from layer1a.db_reads.page_layout import read_page_layout
from layer1a.schema import build_layer1a_output
from partition.group_detect import detect_groups


def run_1a(prompt, db="cmd_catalog", feedback=None):
    rr = route(prompt, db, feedback=feedback)
    cards = build_stories(prompt, rr["page_key"], rr["metric"], rr["intent"], db)
    layout = read_page_layout(rr["page_key"], db)
    raw_groups, _standalone, dims = detect_groups(rr["page_key"], cards, db)
    groups = [
        {"group_id": f"{rr['page_key']}::g{i}", "card_ids": g, "coupling": dims}
        for i, g in enumerate(raw_groups)
    ]
    return build_layer1a_output(rr, cards, layout, groups)
