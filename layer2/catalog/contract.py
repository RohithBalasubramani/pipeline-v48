"""layer2/catalog/contract.py — the contract component + payload_schema_json (declared METADATA shape) + caps.
Component preference: card_handling.contract_component (authoritative) over an arbitrary card_contract_binding. [spec §10 L2]"""
import json

from data.db_client import q


def read(card_id, prefer_component=None):
    comp = prefer_component or None
    if not comp:
        b = q("cmd_catalog", f"SELECT component FROM card_contract_binding WHERE card_id={int(card_id)} LIMIT 1")
        comp = b[0][0] if b and b[0] and b[0][0] else None
    out = {"component": comp, "host_cmd_component": None, "canonical_shape": None,
           "payload_schema_json": None, "capabilities": []}
    if not comp:
        return out
    cc = q("cmd_catalog",
           "SELECT host_cmd_component, canonical_shape, coalesce(payload_schema_json::text,'') "
           f"FROM contract_components WHERE name=$a${comp}$a$ LIMIT 1")
    if cc and cc[0] and cc[0][0] is not None:
        out["host_cmd_component"] = cc[0][0] or None
        out["canonical_shape"] = cc[0][1] or None
        try:
            out["payload_schema_json"] = json.loads(cc[0][2]) if cc[0][2] else None
        except Exception:
            out["payload_schema_json"] = None
    caps = q("cmd_catalog", f"SELECT metric, supported FROM contract_capabilities WHERE component=$a${comp}$a$")
    out["capabilities"] = [{"metric": c[0], "supported": c[1] == "t"} for c in caps if c and c[0]]
    return out
