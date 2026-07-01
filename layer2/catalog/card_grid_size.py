"""layer2/catalog/card_grid_size.py — size from DB (116/145; missing → defaulted). [spec §10, #15]"""
from config.app_config import cfg
from data.db_client import q

DEFAULT_VIEWPORT = cfg("card_grid_size.default_viewport", "1920x1080")


def read(card_id):
    r = q("cmd_catalog",
          "SELECT viewport, width_px, height_px FROM card_grid_size "
          f"WHERE card_id={int(card_id)} ORDER BY viewport LIMIT 1")
    if not r or not r[0] or not r[0][0]:
        return {"viewport": DEFAULT_VIEWPORT, "width_px": None, "height_px": None, "size_source": "defaulted"}
    x = r[0]
    return {"viewport": x[0], "width_px": int(x[1]) if x[1] else None,
            "height_px": int(x[2]) if x[2] else None, "size_source": "card_grid_size"}
