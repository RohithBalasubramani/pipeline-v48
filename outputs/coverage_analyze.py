"""outputs/coverage_analyze.py — aggregate coverage_sweep.jsonl into the coverage verdict (no DB). Per page: drops,
fill rate, frame rate. Overall: render coverage (chilled gate should NOT block where data exists), and COLUMN COVERAGE
(union of every column the cards bound across the sweep) vs the live column universe (optional, needs DB)."""
import os, sys, json
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))


def load(path):
    rows = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def main():
    path = os.path.join(HERE, "coverage_sweep.jsonl")
    rows = load(path)
    ok = [r for r in rows if "ERROR" not in r]
    err = [r for r in rows if "ERROR" in r]
    print(f"runs: {len(rows)}  ok: {len(ok)}  errors: {len(err)}")
    if err:
        print("\n--- ERRORS (tunnel/pipeline) ---")
        for r in err[:20]:
            print(f"  {r['class']:<12} {r['asset'][:22]:<22} {r['page'].split('/')[-1]:<22} {r['ERROR'][:70]}")

    # per-page rollup
    bypage = defaultdict(list)
    for r in ok:
        bypage[r["page"]].append(r)
    print("\n--- PER PAGE (drops / fill / frames across assets) ---")
    print(f"{'page':<48} runs drops unfilled noframe blocked")
    for page in sorted(bypage):
        rs = bypage[page]
        drops = sum(1 for r in rs if (r.get("dropped") or 0) > 0)
        unfilled = sum(1 for r in rs if r.get("filled", 0) < r.get("n_cards", 0))
        noframe = sum(1 for r in rs if r.get("with_frame", 0) < r.get("data_cards", 0))
        blocked = sum(1 for r in rs if r.get("blocked"))
        flag = "  <-- " + ", ".join(x for x, c in [("DROPS", drops), ("UNFILLED", unfilled), ("BLOCKED", blocked)] if c) if (drops or unfilled or blocked) else ""
        print(f"{page:<48} {len(rs):<4} {drops:<5} {unfilled:<8} {noframe:<7} {blocked}{flag}")

    # render coverage: blocked rows = the chilled gate stopped a render
    blocked = [r for r in ok if r.get("blocked")]
    print(f"\n--- RENDER COVERAGE: {len(ok)-len(blocked)}/{len(ok)} pages rendered; {len(blocked)} blocked by chilled gate ---")
    for r in blocked:
        print(f"  BLOCKED {r['class']:<12} {r['asset'][:22]:<22} {r['page'].split('/')[-1]:<22} verdict={r['verdict']} n_cols={r.get('n_columns')}")

    # class coverage
    classes = sorted({r["class"] for r in ok})
    print(f"\n--- CLASS COVERAGE: {len(classes)} classes tested: {', '.join(classes)} ---")

    # column coverage: union of every bound column across the sweep
    allcols = set()
    for r in ok:
        allcols |= set(r.get("bound_columns") or [])
    print(f"\n--- COLUMN COVERAGE: {len(allcols)} distinct columns bound by cards across the sweep ---")
    fams = defaultdict(int)
    for c in allcols:
        fams[c.split("_")[0]] += 1
    print("  by family:", dict(sorted(fams.items(), key=lambda kv: -kv[1])))


if __name__ == "__main__":
    main()
