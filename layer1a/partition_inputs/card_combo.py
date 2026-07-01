"""layer1a/partition_inputs/card_combo.py — combo membership: members of one combo are mutually coupled. [spec section 6]"""
from data.db_client import q


def read_combo_member_groups(page_key, db="cmd_catalog"):
    rows = q(db, "SELECT cm.combo_id, cm.card_id FROM card_combo_member cm "
                 "JOIN card_combo cc ON cc.id=cm.combo_id "
                 f"WHERE cc.page_key=$k${page_key}$k$ AND cm.card_id IS NOT NULL")
    by_combo = {}
    for r in rows:
        by_combo.setdefault(int(r[0]), []).append(int(r[1]))
    return [g for g in by_combo.values() if len(g) >= 2]
