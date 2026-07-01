"""layer2/catalog/card_data_recipe.py — the UNRESOLVED recipe Layer 2 resolves into data_instructions. [spec §10 L2]"""
import json

from data.db_client import q


def _j(v):
    if not v:
        return None
    try:
        return json.loads(v)
    except Exception:
        return None


def read(card_id):
    r = q("cmd_catalog",
          "SELECT payload_shape, orientation, entity_dim, selection_dim, selection_role, "
          "coalesce(reconciled_fields::text, fields::text, '') "
          f"FROM card_data_recipe WHERE card_id={int(card_id)}")
    if not r or not r[0] or not r[0][0]:
        return {}
    x = r[0]
    return {"payload_shape": x[0], "orientation": x[1] or None, "entity_dim": x[2] or None,
            "selection_dim": x[3] or None, "selection_role": x[4] or None,
            "fields": _j(x[5]) or []}     # reconciled_fields if present else fields
