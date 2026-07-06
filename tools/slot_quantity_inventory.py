"""tools/slot_quantity_inventory.py — full slot→expected_quantity inventory across every stored card payload.

Reads every card_payloads row, builds the emit slot catalog (empty basket), runs the LIVE slot_quantity classifier
on each fillable leaf, and buckets: CLASSIFIED (to what) vs UNCLASSIFIED (None → the gate never flags → AI free to
proxy). Prints per-card and a global unclassified roster with the sibling label/unit context so a human/agent can
assign the true quantity. READ-ONLY. Run: python3 tools/slot_quantity_inventory.py [--json]
"""
import sys, json, re
from collections import defaultdict
from data.db_client import q
from layer2.catalog import card_payload
from layer2.emit.slot_catalog import build_slot_catalog
from layer2.quantity_class import slot_quantity, _weak

WEAK = _weak()

# DOMAIN-TELEMETRY tokens: a slot whose PATH or LABEL carries one of these names a quantity an electrical MFM does
# NOT measure — if it is unclassified (AI free to proxy) or classified to an ELECTRICAL class (homonym), it is a
# fabrication risk. Used only to SURFACE the work-list; the true quantity is assigned by judgment + CMD_V2 research.
DOMAIN_TOKENS = [
    "tap", "position", "oltc", "rtcc", "soc", "stateofcharge", "charge", "coolant", "oiltemp", "oilpressure",
    "intake", "exhaust", "engine", "speed", "rpm", "fuel", "tank", "runtime", "runhours", "starts", "duty",
    "autonomy", "backup", "reserve", "transfer", "readiness", "sync", "permissive", "bypass", "hotspot",
    "winding", "aging", "faa", "lol", "lifeyears", "insulation", "battery", "thermal",
]
ELECTRICAL = {"current", "voltage", "power", "energy", "power-factor", "frequency", "load-factor",
              "current-thd", "voltage-thd", "voltage-harmonic", "unbalance", "deviation-spread", "angle"}
# chrome leaf-keys that are presentation knobs, never a measured datum (exclude from the work-list)
CHROME_LEAF = re.compile(r"opacity|index|series$|selected|hint|sectioncontract|areaop|zoom|scale|color|colour|"
                         r"width|height|glyph|order|tab|legendlabel|caption|title|unitlabel", re.I)

def has_domain_token(*strs):
    blob = _norm(" ".join(s or "" for s in strs))
    return next((t for t in DOMAIN_TOKENS if t in blob), None)

def _norm(s):
    return re.sub(r"[^a-z0-9]+", "", str(s or "").lower())

rows = q('cmd_catalog', "SELECT DISTINCT card_id, page_key FROM card_payloads WHERE payload_stripped IS NOT NULL ORDER BY card_id")
rows = [(str(c), p) for c, p in rows if str(c).strip().isdigit()]

per_card = []
classified = defaultdict(list)          # quantity -> [slot ...]
homonym = []                            # domain slot classified to an ELECTRICAL class (active mis-tag)
unclass_domain = []                     # domain slot unclassified (AI free to proxy)
seen_norm = set()                       # dedup payload. vs payload_stripped. (same tail)

def tail(slot):
    t = re.sub(r"^payload(_stripped)?\.", "", slot)
    return re.sub(r"\[\d+\]", "[*]", t)          # collapse array indices so points[0..23] dedup to points[*]

# an electrical token in the slot LEAF/label means the slot IS a real electrical reading (bypass VOLTAGE, input
# CURRENT) — never a domain-quantity homonym; exclude it from the work-list to avoid a false-positive blank.
ELEC_LEAF = re.compile(r"volt|current|power|energy|freq|kw|kva|kvar|kwh|hz|amp|\bpf\b|powerfactor|thd|harmonic", re.I)

for card_id, page_key in rows:
    try:
        dp = card_payload.default_for(card_id, page_key)
        cat = build_slot_catalog(dp, {"columns": []})
    except Exception as e:
        per_card.append((card_id, page_key.split("/")[-1], f"ERR {str(e)[:50]}", 0, 0, 0))
        continue
    nU = nC = 0
    for e in cat:
        slot = e["slot"]; ctx = e.get("ctx") or {}
        label = ctx.get("label") or ""; unit = ctx.get("unit") or ""; section = ctx.get("section") or ""
        qcls = e.get("quantity")
        key = (card_id, tail(slot))
        if key in seen_norm:            # skip payload_stripped mirror of the same tail
            continue
        seen_norm.add(key)
        leaf = re.sub(r"\[.*?\]", "", slot.split(".")[-1])
        is_chrome = bool(CHROME_LEAF.search(leaf))
        is_elec_leaf = bool(ELEC_LEAF.search(leaf) or ELEC_LEAF.search(label))   # a real electrical reading — never domain
        dtok = has_domain_token(leaf, label)          # domain token in the LEAF/label itself (not the container page)
        if qcls and str(qcls).lower() not in WEAK:
            nC += 1
            classified[str(qcls)].append((card_id, slot, label))
            # a true homonym: leaf/label names a DOMAIN quantity but was tagged electrical, AND the leaf is NOT itself
            # an electrical reading (excludes bypassVoltageV etc.)
            if dtok and str(qcls).lower() in ELECTRICAL and not is_chrome and not is_elec_leaf:
                homonym.append((card_id, page_key.split("/")[-1], tail(slot), label, unit, section, qcls, dtok))
        else:
            nU += 1
            if str(qcls or "").lower() in WEAK:
                classified[str(qcls) + " (weak)"].append((card_id, slot, label))
            if dtok and not is_chrome and not is_elec_leaf:
                unclass_domain.append((card_id, page_key.split("/")[-1], tail(slot), label, unit, section, dtok))
    per_card.append((card_id, page_key.split("/")[-1], "", len(cat), nC, nU))

if "--dump" in sys.argv:
    # every (card, slot) → quantity, for a BEFORE/AFTER diff. Rebuild from scratch so all slots (not just domain) show.
    full = {}
    for card_id, page_key in rows:
        try:
            cat = build_slot_catalog(card_payload.default_for(card_id, page_key), {"columns": []})
        except Exception:
            continue
        for e in cat:
            t = tail(e["slot"]); ctx = e.get("ctx") or {}
            full[f"{card_id}|{t}"] = {"q": e.get("quantity"), "label": ctx.get("label") or "", "unit": ctx.get("unit") or ""}
    print(json.dumps(full, indent=0, ensure_ascii=False))
    sys.exit(0)

if "--json" in sys.argv:
    print(json.dumps({
        "homonym_mis_tagged": [dict(zip(("card","page","slot","label","unit","section","cur_qty","domain_token"), h)) for h in homonym],
        "unclassified_domain": [dict(zip(("card","page","slot","label","unit","section","domain_token"), u)) for u in unclass_domain],
        "classes": {k: len(v) for k, v in sorted(classified.items())},
    }, indent=2))
    sys.exit(0)

print(f"\n==== HOMONYM MIS-TAGS ({len(homonym)}) — domain slot tagged as an ELECTRICAL quantity (ACTIVE fabrication) ====")
print(f"{'card':5} {'page':20} {'slot':46} {'label':20} {'cur_qty':16} {'domain'}")
for cid, page, slot, label, unit, section, qcls, dtok in homonym:
    print(f"{cid:5} {page[:20]:20} {slot[:46]:46} {label[:20]:20} {str(qcls)[:16]:16} {dtok}")

print(f"\n==== UNCLASSIFIED DOMAIN SLOTS ({len(unclass_domain)}) — no expected_qty → AI free to proxy ====")
print(f"{'card':5} {'page':20} {'slot':48} {'label':22} {'unit':8} {'domain'}")
for cid, page, slot, label, unit, section, dtok in unclass_domain:
    print(f"{cid:5} {page[:20]:20} {slot[:48]:48} {label[:22]:22} {unit[:8]:8} {dtok}")

print(f"\n==== QUANTITY CLASSES IN USE ({len(classified)}) ====")
for k, v in sorted(classified.items(), key=lambda x: -len(x[1])):
    print(f"  {k:28} {len(v):4}  e.g. {v[0][1] if v else ''}")
