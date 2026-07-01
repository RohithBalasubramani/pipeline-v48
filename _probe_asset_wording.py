#!/usr/bin/env python3
"""v48 wording-sensitivity probe for layer1b.resolve.asset_resolve.resolve_asset.
For each (target meter, phrasing) call the LIVE resolver and check the confident pin's NAME == intended.
Run from pipeline_v48 root:  PYTHONPATH=. python3 _probe_asset_wording.py <transformer-numbers csv>
e.g.  PYTHONPATH=. python3 _probe_asset_wording.py 1,5,6,7,8
"""
import sys, json
from layer1b.resolve.asset_candidates import asset_candidates
from layer1b.resolve.asset_resolve import resolve_asset

TEMPLATES = [
    "Transformer {n}", "transformer {n}", "TF-{n}", "TF{n}", "TX-{n}", "transformer number {n}",
    "the {ord} transformer", "show oil temperature for transformer {n}", "tap position of TF {n}",
    "winding temperature, transformer {n}", "load on the number {n} transformer", "Incomer-{n} transformer",
]
ORD = {1:"first",2:"second",3:"third",4:"fourth",5:"fifth",6:"sixth",7:"seventh",8:"eighth"}


def main():
    nums = [int(x) for x in (sys.argv[1] if len(sys.argv) > 1 else "1,5,6,7,8").split(",")]
    cands = asset_candidates()
    by_name = {c[1].strip().lower(): c for c in cands}
    trials = []
    for n in nums:
        target = by_name.get(f"transformer {n}")
        if not target:
            continue
        exp_id, exp_name = str(target[0]), target[1]
        for pi, t in enumerate(TEMPLATES):
            prompt = t.format(n=n, ord=ORD.get(n, str(n)))
            r = resolve_asset(prompt)
            how = r.get("how")
            a = r.get("asset")
            got_name = a["name"] if a else None
            got_id = str(a["mfm_id"]) if a else None
            ok = (how == "AI" and got_name == exp_name)
            wrong_pin = (how == "AI" and got_name is not None and got_name != exp_name)
            trials.append({"spoken_n": n, "expected_id": exp_id, "expected_name": exp_name,
                           "template_idx": pi, "prompt": prompt, "how": how,
                           "got_id": got_id, "got_name": got_name, "n_cands": len(r.get("candidates", [])),
                           "verdict": "OK" if ok else ("WRONG-PIN" if wrong_pin else "ambiguous/other")})
    print(json.dumps(trials, indent=2))
    tot = len(trials); ok = sum(t["verdict"] == "OK" for t in trials)
    wp = sum(t["verdict"] == "WRONG-PIN" for t in trials)
    amb = sum(t["verdict"] == "ambiguous/other" for t in trials)
    sys.stderr.write(f"\nSUMMARY  trials={tot}  OK={ok}  WRONG-PIN={wp}  ambiguous/other={amb}\n")
    for t in trials:
        if t["verdict"] == "WRONG-PIN":
            sys.stderr.write(f"  WRONG: {t['prompt']!r} -> {t['got_name']} (expected {t['expected_name']})\n")


if __name__ == "__main__":
    main()
