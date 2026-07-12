"""layer2/catalog/card_handling.py — THE card_handling reads (one concern; full row / one class / batch classes).
[spec §10 L2, catalog_row.handling; dedup D11 2026-07-12 — validate + host read through here too]"""
from data.db_client import q


def handling_class(card_id):
    """The handling_class for one card, or None (absent row / DB error — honest fail-open; the validator's read)."""
    try:
        r = q("cmd_catalog", f"SELECT handling_class FROM card_handling WHERE card_id={int(card_id)} LIMIT 1")
        return r[0][0] if r and r[0] and r[0][0] else None
    except Exception:
        return None


def handling_classes(card_ids):
    """{card_id: handling_class} for a batch (one query), {} on any failure — the host fan-out's fail-open read."""
    ids = ",".join(str(int(c)) for c in (card_ids or []))
    if not ids:
        return {}
    try:
        rows = q("cmd_catalog", f"SELECT card_id, handling_class FROM card_handling WHERE card_id IN ({ids})")
        return {int(r[0]): r[1] for r in (rows or []) if r and r[1]}
    except Exception:
        return {}


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
