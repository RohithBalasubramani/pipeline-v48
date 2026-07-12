"""validation/corpus/universe.py — the cmd_catalog GROUND-TRUTH universe the generator permutes over and the coverage
analyzer measures against. One read, process-cached, ascii-sanitized at the boundary (surrogate safety).

Classes mirror layer1b's name-pattern fallback vocabulary (asset_candidates._NAME_CLASS) so category templates pick
class-appropriate metrics ('fuel' only for DG, 'pressure' only for Compressor/Dryer...). UNIQUE names (exactly one
registry row shares the class+unit token) drive confident-pin prompts; HOMONYM names (2+ rows) drive ambiguity prompts."""
from __future__ import annotations

import re
from functools import lru_cache

from validation.response import ascii_safe

_NAME_CLASS = (
    (("ups",), "UPS"), (("transformer", "xformer", "_tfr"), "Transformer"), (("ahu",), "AHU"),
    (("air_washer", "airwasher"), "AirWasher"), (("chiller",), "Chiller"), (("apfc",), "APFCR"),
    (("pump",), "Pump"), (("compressor", "_comp"), "Compressor"), (("incomer", "_inc_", "incoming"), "Incomer"),
    (("dg_", "_dg_", "diesel", "generator"), "DG"), (("exhaust", "_fan", "fan_"), "Fan"), (("feeder",), "Feeder"),
    (("bpdb", "pdb", "pcc", "mcc", "mldb", "_db", "panel", "lamination", "packing", "curing"), "Panel"),
    (("cooling_tower", "coolingtower", "_ct_"), "CoolingTower"), (("dryer",), "Dryer"),
)


def _cls(table: str) -> str:
    nm = (table or "").lower()
    for needles, cls in _NAME_CLASS:
        if any((nm.startswith(n) if n == "dg_" else n in nm) for n in needles):
            return cls
    return "Load"


def _unit_token(name: str) -> str | None:
    """The class+unit shorthand a user would type ('UPS-01', 'AHU-5', 'DG-1') — homonym detection keys on it."""
    m = re.search(r"([a-z]{2,12})[\s\-_]*0?(\d{1,2})[a-b]?\b", (name or "").lower())
    return f"{m.group(1)}-{m.group(2)}" if m else None


@lru_cache(maxsize=1)
def universe() -> dict:
    """{assets, by_class, unique_names, homonym_tokens, panel_aliases, pages, cards, card_handling}."""
    from data.db_client import q
    assets, by_class, tok_map = [], {}, {}
    for r in q("cmd_catalog", "SELECT id, name, table_name, table_exists FROM registry_lt_mfm ORDER BY id"):
        a = {"id": int(r[0]), "name": ascii_safe(r[1]), "table": r[2] or "",
             "cls": _cls(r[2] or ""), "table_exists": str(r[3]).strip().lower() in ("t", "true", "1")}
        assets.append(a)
        by_class.setdefault(a["cls"], []).append(a)
        t = _unit_token(a["name"])
        if t:
            tok_map.setdefault(t, []).append(a)
    # FULL registry names are unique by construction and the resolver confidently pins them (live-verified) — so every
    # TABLE-BACKED asset is a valid confident-pin prompt subject. (Ghost rows — table_exists false — can never render;
    # prompting them belongs to the 'invalid'/dark coverage, not the cards-expecting categories.)
    unique_names = [a for a in assets if a["name"] and a["table_exists"]]
    homonym_tokens = sorted({t.upper() for t, rows in tok_map.items() if len(rows) >= 2})

    aliases = [(ascii_safe(al), ascii_safe(pn))
               for al, pn in q("cmd_catalog", "SELECT alias, panel_name FROM pcc_panel_alias WHERE alias IS NOT NULL")]
    pages = [r[0] for r in q("cmd_catalog", "SELECT DISTINCT page_key FROM page_layout_cards ORDER BY 1")]
    cards = [int(r[0]) for r in q("cmd_catalog", "SELECT DISTINCT card_id FROM page_layout_cards ORDER BY 1")]
    handling = {int(r[0]): r[1] for r in q("cmd_catalog", "SELECT card_id, handling_class FROM card_handling")}
    return {"assets": assets, "by_class": by_class, "unique_names": unique_names,
            "homonym_tokens": homonym_tokens, "panel_aliases": aliases,
            "pages": pages, "cards": cards, "card_handling": handling}
