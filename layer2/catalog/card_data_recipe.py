"""layer2/catalog/card_data_recipe.py — the UNRESOLVED recipe Layer 2 resolves into data_instructions. [spec §10 L2]"""
from data.db_client import q, first_row, json_cell as _j   # None-on-corrupt (this reader's contract, D12)
from layer2.catalog import card_fill_recipe


def read(card_id):
    r = q("cmd_catalog",
          "SELECT payload_shape, orientation, entity_dim, selection_dim, selection_role, "
          "coalesce(reconciled_fields::text, fields::text, '') "
          f"FROM card_data_recipe WHERE card_id={int(card_id)}")
    if not r or not r[0] or not r[0][0]:
        out = {}
    else:
        x = r[0]
        out = {"payload_shape": x[0], "orientation": x[1] or None, "entity_dim": x[2] or None,
               "selection_dim": x[3] or None, "selection_role": x[4] or None,
               "fields": _j(x[5]) or []}  # reconciled_fields if present else fields
    # ROSTER recipe [package §2c]: a panel_aggregate/topology_sld card's atomized card_fill_recipe row rides along so
    # user_message shows it VERBATIM and build gates data_instructions.roster against it. None-safe (most cards: absent).
    rs = card_fill_recipe.read(card_id).get("roster_spec")
    if rs:
        out["roster_spec"] = rs
    return out
