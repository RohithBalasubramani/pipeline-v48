"""Golden-prompt eval for the EMS Query Copilot.

Runs a set of partial prompts through the full retrieve -> generate path and checks
basic invariants, printing each result. Requires the 4B endpoint (:8201) up.
    python3 tests/eval.py
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import generate  # noqa: E402

PROMPTS = [
    "show trans",
    "compare current",
    "transformer 1 ther",
    "ups batt",
    "voltage sag on pcc",
    "ahu-5 ",
    "energy this week for",
    "dg fuel",
]


def main():
    generate.generate("show", timeout=30)  # warm
    fails = 0
    for p in PROMPTS:
        t = time.time()
        out = generate.generate(p, timeout=30)
        ms = int((time.time() - t) * 1000)
        sug = out.get("suggestions", [])
        af = out.get("autofill", "")
        ok = isinstance(sug, list) and out.get("source") in ("model", "unavailable")
        if af and not af.lower().startswith(p.lower().strip()):
            ok = False  # autofill must continue the typed text
        if len(sug) > 5:
            ok = False
        fails += 0 if ok else 1
        print(f"\n[{'PASS' if ok else 'FAIL'}] {ms}ms  '{p}'")
        print(f"   autofill: {af!r}")
        for s in sug:
            print("   -", s)
    print(f"\n{'='*40}\n{len(PROMPTS)-fails}/{len(PROMPTS)} passed")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
