"""layer2/catalog/card_controls.py — retained interactivity seed (tabs/time/sampling/defaults). [spec §10 L2, #16]"""
import json

from data.db_client import q


def _j(v):
    try:
        return json.loads(v) if v else None
    except Exception:
        return v or None


def read(card_id):
    r = q("cmd_catalog",
          "SELECT time_mode, coalesce(time_options::text,''), coalesce(sampling_options::text,''), "
          "coalesce(segmented_tabs::text,''), coalesce(defaults::text,'') "
          f"FROM card_controls WHERE card_id={int(card_id)}")
    if not r or not r[0] or not r[0][0]:
        return {}
    x = r[0]
    return {"time_mode": x[0] or None, "time_options": _j(x[1]), "sampling_options": _j(x[2]),
            "segmented_tabs": _j(x[3]), "defaults": _j(x[4])}
