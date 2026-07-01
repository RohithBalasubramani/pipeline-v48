"""layer2/catalog/card_handling.py — read card_handling for one card. [spec §10 L2, catalog_row.handling]"""
from data.db_client import q


def read(card_id):
    r = q("cmd_catalog",
          "SELECT handling_class, resolver_scope, payload_family, backend_strategy, contract_component "
          f"FROM card_handling WHERE card_id={int(card_id)}")
    if not r or not r[0] or not r[0][0]:
        return {}
    h = r[0]
    return {"handling_class": h[0], "resolver_scope": h[1] or None,
            "payload_family": h[2] or None, "backend_strategy": h[3] or None,
            "contract_component": h[4] or None}
