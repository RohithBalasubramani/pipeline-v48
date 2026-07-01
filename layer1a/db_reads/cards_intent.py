"""layer1a/db_reads/cards_intent.py — a page's live cards with the FULL per-card package Layer 2 needs:
profile (cards), data recipe (card_data_recipe), handling (card_handling), slot + size. [spec section 10 1a, contract 2/4]"""
import json

from config.app_config import cfg
from data.db_client import q


def read_page_cards(page_key, db=None):
    db = db or cfg("cards_intent.default_db", "cmd_catalog")
    viewport = cfg("cards_intent.grid_viewport", "1920x1080")
    card_status = cfg("cards_intent.card_status", "live")
    rows = q(
        db,
        "SELECT pl.card_id, coalesce(c.title,''), coalesce(c.card_purpose,''), coalesce(c.analytical_role,''), "
        "coalesce(c.user_question,''), coalesce(c.output_insight,''), coalesce(c.decision_support,''), "
        "coalesce(c.visualization,''), coalesce(c.primary_component,''), coalesce(c.composes,''), "
        "coalesce(pl.slot_order,0), coalesce(pl.cell,''), coalesce(pl.region,''), coalesce(pl.area,''), "
        "coalesce(pl.col_span::text,''), coalesce(pl.row_span::text,''), coalesce(pl.tab,''), "
        "coalesce(pl.combo_id::text,''), coalesce(pl.combo_role,''), "
        "coalesce(g.width_px::text,''), coalesce(g.height_px::text,''), "
        "coalesce(r.payload_shape,''), coalesce(r.orientation,''), coalesce(r.entity_dim,''), "
        "coalesce(r.selection_dim,''), coalesce(r.selection_role,''), coalesce(r.fields::text,''), "
        "coalesce(h.handling_class,''), coalesce(h.payload_family,''), coalesce(h.contract_component,''), "
        "coalesce(h.resolver_scope,''), coalesce(h.backend_strategy,'') "
        "FROM page_layout_cards pl JOIN cards c ON c.id=pl.card_id "
        f"LEFT JOIN card_grid_size g ON g.card_id=pl.card_id AND g.viewport='{viewport}' "
        "LEFT JOIN card_data_recipe r ON r.card_id=pl.card_id "
        "LEFT JOIN card_handling h ON h.card_id=pl.card_id "
        f"WHERE pl.page_key=$k${page_key}$k$ AND pl.card_id IS NOT NULL AND c.status='{card_status}' "
        "ORDER BY pl.slot_order",
    )
    out = []
    for r in rows:
        i = lambda v: int(v) if v else None
        n = lambda v: v or None
        try:
            fields = json.loads(r[26]) if r[26] else []
        except Exception:
            fields = []
        out.append({
            # --- identity + AI story (story_builder fills analytical_story) ---
            "card_id": int(r[0]), "title": r[1],
            "card_purpose": r[2], "analytical_role": r[3],
            # --- profile: what the card IS / answers (cards table) ---
            "profile": {
                "card_purpose": r[2], "user_question": r[4], "output_insight": r[5],
                "decision_support": r[6], "visualization": r[7],
                "primary_component": r[8], "composes": r[9],
            },
            # --- slot + size (layout) ---
            "slot": {"slot_order": int(r[10]) if r[10] else 0, "cell": n(r[11]), "region": n(r[12]),
                     "area": n(r[13]), "col_span": i(r[14]), "row_span": i(r[15]), "tab": n(r[16]),
                     "combo_id": i(r[17]), "combo_role": n(r[18])},
            "size": {"viewport": viewport, "width_px": i(r[19]), "height_px": i(r[20]),
                     "size_source": "card_grid_size" if r[19] else "defaulted"},
            # --- recipe: the DATA spec Layer 2's data_instructions builds from (card_data_recipe) ---
            "recipe": {"payload_shape": n(r[21]), "orientation": n(r[22]), "entity_dim": n(r[23]),
                       "selection_dim": n(r[24]), "selection_role": n(r[25]), "fields": fields},
            # --- handling: how it's produced/rendered (card_handling; data_fill_shape signal) ---
            "handling": {"handling_class": n(r[27]), "payload_family": n(r[28]),
                         "contract_component": n(r[29]), "resolver_scope": n(r[30]),
                         "backend_strategy": n(r[31])},
        })
    return out
