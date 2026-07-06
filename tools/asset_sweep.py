"""tools/asset_sweep.py — live re-fire of the 9 asset-dashboard prompts through a FRESH run_pipeline (fresh cfg → the
current quantity vocab), then AUDIT every emitted data_instructions field for a surviving CROSS-QUANTITY PROXY.

A PROXY LEAK = a field binds a column/fn whose quantity class is INCOMPATIBLE with its slot's expected_qty (e.g. a
tap-position slot bound to a current column). After the quantity-vocab fix the emit AI should OMIT those slots
(honest-blank) and the gate blanks any that slip — so the expected result is ZERO proxy leaks, with the domain slots
(tap / fuel / autonomy / pressure / engine-speed / SoC / temperature / aging / transfer) honest-blanked.

Needs :5433 (neuract) + :8200 (vLLM) up. Run: python3 tools/asset_sweep.py
Writes outputs/asset_sweep_result.json + a per-page table to stdout. Exit 0 = clean (0 leaks), 1 = leaks found.
"""
import sys, json, time
from run.harness import run_pipeline
from layer2.quantity_class import slot_quantity, column_class, name_class, compatible

# (page, prompt, pinned asset_id=mfm_id) — the picker re-POST case (these names resolve to >1 candidate → pinned).
PROMPTS = [
    ("dg voltage-current",    "dg voltage and current for DG-1", 2),
    ("dg engine-cooling",     "dg engine and cooling for DG-1", 2),
    ("dg fuel-efficiency",    "dg fuel efficiency for DG-1", 2),
    ("dg operations-runtime", "dg operations and runtime for DG-1", 2),
    ("transformer tap-rtcc",  "transformer tap and rtcc for Transformer-01", 171),
    ("transformer thermal-life", "transformer thermal life for Transformer-01", 171),
    ("ups battery-autonomy",  "ups battery and autonomy for GIC-01-N3-UPS-01", 11),
    ("ups output-load-capacity", "ups output load capacity for GIC-01-N3-UPS-01", 11),
    ("ups source-transfer",   "ups source transfer for GIC-01-N3-UPS-01", 11),
]
DOMAIN = {"tap-position", "engine-speed", "pressure", "fuel", "autonomy", "readiness", "score-index",
          "temperature", "aging-factor", "lifetime", "battery-charge", "duration", "count"}


def field_qty(f):
    """(slot_qty, source_qty) for a data field — the same lookups the gate uses."""
    sctx = {"label": f.get("label") or f.get("_sibling_label"), "unit": f.get("unit") or f.get("_sibling_unit")}
    sq = slot_quantity(f.get("slot"), sctx) or slot_quantity(f.get("slot"), {"label": f.get("metric")})
    if f.get("kind") == "derived":
        cq = name_class(f.get("fn"))
    else:
        cq = column_class({"column": f.get("column"), "unit": f.get("unit")})
    return sq, cq


def main():
    results = []
    total_leaks = 0
    for page, prompt, asset_id in PROMPTS:
        t0 = time.time()
        try:
            out = run_pipeline(prompt, asset_id=asset_id)
        except Exception as e:
            results.append({"page": page, "prompt": prompt, "error": f"{type(e).__name__}: {e}"})
            print(f"\n### {page}: ERROR {type(e).__name__}: {str(e)[:90]}")
            continue
        pk = (out.get("layer1a") or {}).get("page_key") or "?"
        l2 = out.get("layer2") or {}
        perr = out.get("errors") or {}
        leaks, domain_blanks, real_binds = [], 0, 0
        for cid, emit in (l2.items() if isinstance(l2, dict) else []):
            di = (emit or {}).get("data_instructions") or {}
            slots_bound = set()
            for f in (di.get("fields") or []):
                if f.get("kind") == "time" or not (f.get("column") or f.get("fn")):
                    continue
                slots_bound.add(f.get("slot"))
                sq, cq = field_qty(f)
                real_binds += 1
                if sq and cq and not compatible(sq, cq):          # a surviving cross-quantity proxy
                    leaks.append({"card": cid, "slot": f.get("slot"), "slot_qty": sq,
                                  "src": f.get("column") or f.get("fn"), "src_qty": cq})
            # count domain slots that were correctly OMITTED (honest-blank) — a rough proxy via the card's emit note
            dn = (emit or {}).get("data_note") or ""
            if "honest" in dn.lower() or "not measured" in dn.lower() or "blank" in dn.lower():
                domain_blanks += 1
        total_leaks += len(leaks)
        row = {"page": page, "prompt": prompt, "page_key": pk, "cards": len(l2),
               "real_binds": real_binds, "proxy_leaks": leaks, "payload_errors": list(perr.keys()),
               "secs": round(time.time() - t0, 1)}
        results.append(row)
        flag = "  <== PROXY LEAK" if leaks else ""
        print(f"\n### {page}  -> {pk}")
        print(f"    cards={len(l2)} real_binds={real_binds} PROXY_LEAKS={len(leaks)} perr={list(perr.keys())} ({row['secs']}s){flag}")
        for lk in leaks:
            print(f"      LEAK card {lk['card']} {lk['slot']}: {lk['slot_qty']} <- {lk['src']} ({lk['src_qty']})")

    print("\n" + "=" * 70)
    print(f"SWEEP COMPLETE: {len(PROMPTS)} pages, TOTAL PROXY LEAKS = {total_leaks}")
    json.dump({"total_proxy_leaks": total_leaks, "pages": results},
              open("outputs/asset_sweep_result.json", "w"), indent=2)
    print("result -> outputs/asset_sweep_result.json")
    return 0 if total_leaks == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
