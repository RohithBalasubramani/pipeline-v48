"""layer2/catalog/feasibility.py — card_feasibility (render_real gates the swap pool). [spec §10 L2]"""
from data.db_client import first_row


def read(card_id):
    x = first_row("cmd_catalog",
                  "SELECT family, verdict, required_topology, required_mesh, reason "
                  f"FROM card_feasibility WHERE card_id={int(card_id)}")
    if x is None:
        return {"family": None, "verdict": None, "required_topology": None, "required_mesh": None, "reason": None}
    return {"family": x[0] or None, "verdict": x[1] or None,
            "required_topology": x[2] == "t", "required_mesh": x[3] == "t", "reason": x[4] or None}
