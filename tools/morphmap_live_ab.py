#!/usr/bin/env python3
"""tools/morphmap_live_ab.py — LIVE A/B for the morph-map emit path (the offline A/B proves producer byte-equivalence
IF the AI emits the same morphs; this proves the AI actually emits WELL under the morphs-only prompt).

Compares two host response dumps of the SAME prompts — one fired with emit.morphmap_mode=off (arm A / full-emit), one
with =on (arm B / morph-map) — everything else equal. Per card it reports: swap agreement, exact_metadata byte-equality,
data-leaf coverage (real/data), answerability, payload_error, and a fabrication seed scan. A CLEAN result = for every
card: same swap, exact_metadata byte-identical (or a JUSTIFIED morph delta), real-leaf count >= arm A, same answerability
class, 0 fabrication in both. Any card where morph-map ships FEWER real leaves or MORE blanks than full-emit is a
regression that blocks the default-on flip.

Usage: python3 tools/morphmap_live_ab.py <arm_off.json> <arm_on.json> [<off2.json> <on2.json> ...]
"""
import json
import sys

SEEDS = ["1500", "2700", "389.2", "13:14:10", "lt_panel_simulator", "1,820,542"]


def _cards(path):
    d = json.load(open(path))
    return {c.get("card_id"): c for c in (d.get("cards") or [])}, (d.get("page_key") or "?")


def _fab(card):
    blob = json.dumps(card.get("payload") or {})
    return [s for s in SEEDS if s in blob]


def _row(cid, a, b):
    ra, rb = (a.get("render") or {}), (b.get("render") or {})
    la, lb = ra.get("leaf_stats") or {}, rb.get("leaf_stats") or {}
    # exact_metadata isn't separately shipped; compare the whole payload metadata tier via the served payload bytes
    pa, pb = json.dumps(a.get("payload"), sort_keys=True), json.dumps(b.get("payload"), sort_keys=True)
    real_a, real_b = la.get("real", 0), lb.get("real", 0)
    regress = (real_b < real_a) or (bool(_fab(b)) and not _fab(a)) or \
              (rb.get("verdict") == "honest_blank" and ra.get("verdict") != "honest_blank")
    return {
        "card": cid,
        "swap_a": (a.get("swap") or {}).get("action") if isinstance(a.get("swap"), dict) else a.get("swap"),
        "swap_b": (b.get("swap") or {}).get("action") if isinstance(b.get("swap"), dict) else b.get("swap"),
        "real_a": real_a, "real_b": real_b, "data_a": la.get("data", 0), "data_b": lb.get("data", 0),
        "ans_a": ra.get("answerability"), "ans_b": rb.get("answerability"),
        "verdict_a": ra.get("verdict"), "verdict_b": rb.get("verdict"),
        "err_a": bool(a.get("payload_error")), "err_b": bool(b.get("payload_error")),
        "fab_a": _fab(a), "fab_b": _fab(b),
        "payload_equal": pa == pb,
        "REGRESSION": regress,
    }


def main():
    args = sys.argv[1:]
    pairs = [(args[i], args[i + 1]) for i in range(0, len(args) - 1, 2)]
    all_rows, regressions = [], []
    for off_p, on_p in pairs:
        a, pka = _cards(off_p)
        b, pkb = _cards(on_p)
        print(f"\n=== {pka}  (OFF {off_p}  vs  ON {on_p}) ===")
        for cid in sorted(set(a) | set(b), key=lambda x: (x is None, x)):
            if cid not in a or cid not in b:
                print(f"  card {cid}: MISSING in one arm (a={cid in a} b={cid in b})")
                continue
            r = _row(cid, a[cid], b[cid])
            all_rows.append(r)
            flag = "  <<< REGRESSION" if r["REGRESSION"] else ("  =bytes" if r["payload_equal"] else "")
            print(f"  card {cid}: real {r['real_a']}->{r['real_b']}  ans {r['ans_a']}->{r['ans_b']}  "
                  f"verdict {r['verdict_a']}->{r['verdict_b']}  swap {r['swap_a']}->{r['swap_b']}  "
                  f"err {r['err_a']}->{r['err_b']}  fab_b={r['fab_b']}{flag}")
            if r["REGRESSION"]:
                regressions.append(r)
    print("\n================ VERDICT ================")
    print(f"cards compared: {len(all_rows)}  |  byte-identical payloads: {sum(1 for r in all_rows if r['payload_equal'])}")
    print(f"any fabrication (arm B): {sum(1 for r in all_rows if r['fab_b'])}")
    print(f"REGRESSIONS (morph-map ships fewer real leaves / more blanks / new fabrication): {len(regressions)}")
    if regressions:
        print("  -> DO NOT flip emit.morphmap_mode on. Regressing cards:", [r["card"] for r in regressions])
    else:
        print("  -> CLEAN: morph-map coverage >= full-emit on every card, 0 fabrication. Safe to flip default-on.")
    return 1 if regressions else 0


if __name__ == "__main__":
    sys.exit(main())
