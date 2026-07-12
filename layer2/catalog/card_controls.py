"""layer2/catalog/card_controls.py — retained interactivity seed (tabs/time/sampling/defaults). [spec §10 L2, #16]"""
from data.db_client import first_row, json_cell


def _j(v):
    return json_cell(v, raw_on_error=True)   # malformed blob ships as raw text (this reader's contract, D12)


def read(card_id):
    x = first_row("cmd_catalog",
                  "SELECT time_mode, coalesce(time_options::text,''), coalesce(sampling_options::text,''), "
                  "coalesce(segmented_tabs::text,''), coalesce(defaults::text,'') "
                  f"FROM card_controls WHERE card_id={int(card_id)}")
    if x is None:
        return {}
    return {"time_mode": x[0] or None, "time_options": _j(x[1]), "sampling_options": _j(x[2]),
            "segmented_tabs": _j(x[3]), "defaults": _j(x[4])}
