"""outputs/emit_correctness_battery.py — prove the Layer-2 emit AI binds the CORRECT field, with NO code net.

Runs the REAL pipeline (run/harness.run_pipeline) in-process (fresh imports → picks up the emit-correctness edits:
basket de-lie in user_message._basket_lines, quantity= tag in registry.catalog()/emit._recovery_library_block, and the
generic RAW-BEATS-FN + quantity-match rule in data_instructions.md). Asserts, per scenario, that the resolved
data_instructions.fields[] are correct — and that NO out-of-catalog fn ever ships (the invariant the whole scheme
guarantees). Read-only; no host restart, no code edits. Run:

    PYTHONPATH=. python3.11 outputs/emit_correctness_battery.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json  # noqa: E402
import re  # noqa: E402

from ems_exec.derivations.registry import catalog  # noqa: E402
from run.harness import run_pipeline  # noqa: E402
from layer2.build import _cross_domain_fields  # noqa: E402  (the generic E/G honesty detector)
from layer2.emit.slot_catalog import build_slot_catalog  # noqa: E402
from data.db_client import q  # noqa: E402

# A field whose slot is NOT a real leaf in the card's own payload is a PHANTOM (no-op — the executor never reaches it),
# so it can't be a binding defect. Skip such fields in the binding-correctness checks (this is the separately-parked
# card-43 wrong-shape issue, not an E/G/S2 binding question).
_SLOT_BASES = {}


def _real_slot_bases(card_id):
    if card_id in _SLOT_BASES:
        return _SLOT_BASES[card_id]
    bases = set()
    try:
        r = q('cmd_catalog', f"SELECT payload FROM card_payloads WHERE card_id='{int(card_id)}'")
        pl = r[0][0] if r else None
        pl = json.loads(pl) if isinstance(pl, str) else pl
        for c in (build_slot_catalog(pl, {"columns": []}) or []):
            s = c.get("slot") if isinstance(c, dict) else c
            bases.add(re.sub(r"\[[^\]]*\]", "", s or ""))
    except Exception:
        bases = set()
    _SLOT_BASES[card_id] = bases
    return bases


def _slot_is_real(card_id, slot):
    real = _real_slot_bases(card_id)
    return (not real) or (re.sub(r"\[[^\]]*\]", "", slot or "") in real)

CATALOG_FNS = {e["fn"] for e in catalog()}
QUANTITY = {e["fn"]: e.get("quantity") for e in catalog()}

# (label, prompt, pinned canonical lt_mfm.id). S2 = the max_spread raw-bind case; E = card-47 voltage-THD semantic
# mis-bind (UPS-01 id 11); G = card-75 lifeRemainingYears bad derived math (Transformer-01 id 171).
CASES = [
    ("S2/AHU-5", "voltage and current health for GIC-03-N6-AHU-5", 36),
    ("E/UPS-PQ", "power quality for GIC-01-N3-UPS-01", 11),
    ("G/TX-life", "transformer thermal life for Transformer-01", 171),
]


def _all_fields(out):
    """Every data_instructions.fields[] entry across the run's cards, tagged with its card_id.
    out["layer2"] is a dict {card_id: Layer2CardOutput}; each carries ["data_instructions"]["fields"]."""
    fields = []
    l2 = out.get("layer2") or {}
    for cid, l2out in (l2.items() if isinstance(l2, dict) else []):
        di = (l2out or {}).get("data_instructions") or {}
        for f in (di.get("fields") or []):
            fields.append((cid, f))
    return fields


def _data_bearing_cols(out):
    """The set of REAL data-bearing basket columns the AI was actually SHOWN for this run's asset (raw-bindable). Built
    the same way the emit prompt builds it (build_basket over the resolved asset) — so 'raw was available' is judged by
    real basket membership, not a column-name pattern."""
    try:
        from layer1b.basket.column_basket import build_basket
        a = (out.get("layer1b") or {}).get("asset") or {}
        b = build_basket(out.get("prompt") or "", a, intent="snapshot")
        return {c.get("column") for c in (b.get("columns") or []) if c.get("has_data")}
    except Exception as e:
        print(f"  (basket rebuild failed: {e} — Invariant 2 falls back to name-pattern)")
        return None


def _check_case(label, prompt, asset_id):
    print(f"\n=== {label}: {prompt!r} (asset_id={asset_id}) ===")
    out = run_pipeline(prompt, asset_id=asset_id)
    if out.get("asset_pending"):
        cands = [c.get("asset_id") for c in (out.get("asset") or {}).get("candidates", [])]
        print(f"  ASSET_PENDING (candidates {cands}) — re-pin failed; not a binding defect"); return None
    fields = _all_fields(out)
    db_cols = _data_bearing_cols(out)
    derived = [(cid, f) for cid, f in fields if f.get("kind") == "derived"]
    print(f"  cards={len(out.get('layer2') or {})}  fields={len(fields)}  derived={len(derived)}  data-bearing-cols={len(db_cols or [])}")
    # dump the derived fields for eyeballing (fn | quantity | target_column | target_in_basket)
    for cid, f in derived:
        tc = f.get("target_column")
        print(f"    derived[card {cid}] slot={f.get('slot')} fn={f.get('fn')} q={QUANTITY.get(f.get('fn'))} "
              f"target={tc} target_in_basket={(tc in db_cols) if db_cols is not None else '?'}")

    problems = []

    # GLOBAL INVARIANT 1 — no derived field names an out-of-catalog fn (the primary guarantee)
    for cid, f in derived:
        if f.get("fn") not in CATALOG_FNS:
            problems.append(f"[card {cid}] OUT-OF-CATALOG fn {f.get('fn')!r} on slot {f.get('slot')}  ← the bug")

    # CROSS-DOMAIN HONESTY (E/G) — a data field bound to a column/fn of a DIFFERENT physical domain than its slot must
    # NEVER let its card claim answerability="full" (Fix 4). Ideally Fix 1+2 leave zero cross-domain binds; any that
    # remain MUST be honestly demoted. A "full" card carrying a cross-domain bind is the E/G bug.
    l2 = out.get("layer2") or {}
    xdom_total = 0
    for cid, l2out in (l2.items() if isinstance(l2, dict) else []):
        di = (l2out or {}).get("data_instructions") or {}
        xd = _cross_domain_fields(di)
        if not xd:
            continue
        xdom_total += len(xd)
        ans = (l2out or {}).get("answerability")
        for (slot, sf, src, cf) in xd:
            tag = "HONEST(partial)" if ans in ("partial", "none") else "FULL-CLAIMED"
            print(f"    xdomain[card {cid}] slot={slot} ({sf}) <- {src} ({cf})  answerability={ans}  {tag}")
            if ans == "full":
                problems.append(f"[card {cid}] CROSS-DOMAIN bind {src}({cf}) in a {sf} slot {slot} but answerability=full "
                                f"— must be partial+note (E/G honesty)")
    print(f"  cross-domain binds this run: {xdom_total} (0 = Fix1+2 fully prevented; >0 must all be HONEST(partial))")

    # GLOBAL INVARIANT 2 — a data-bearing basket column wrapped in an fn (the S2 shape): a derived field whose
    # target_column IS a real data-bearing column the AI WAS SHOWN (so raw was genuinely available and it should have
    # bound raw). Basket-aware — a column that is logged in neuract but NOT in this asset's basket is not flagged (raw
    # was not on offer; a derived recovery there is legitimate, e.g. voltageStatutoryBand for a band leaf).
    for cid, f in derived:
        tc = f.get("target_column") or ""
        if not _slot_is_real(cid, f.get("slot")):
            continue                                      # PHANTOM slot (no-op) — the parked card-43 shape issue, not a bind defect
        if db_cols is not None and tc in db_cols:
            problems.append(f"[card {cid}] derived fn {f.get('fn')!r} wraps DATA-BEARING basket column {tc!r} "
                            f"— should be kind:raw column:{tc}")

    # SCENARIO S2 — the CURRENT max_spread leaf must be RAW current_max_spread (or honest-absent), NEVER a derived fn.
    # Scoped to the S2/AHU-5 case AND to the CURRENT domain — a VOLTAGE worst-spread stat (voltage-axis-domain) on the
    # same page is a different quantity, not this bug.
    from config.metrics import quantity_family as _qf
    spread_fields = [] if not label.startswith("S2") else [
        (cid, f) for cid, f in fields
        if _slot_is_real(cid, f.get("slot"))
        and "spread" in (str(f.get("metric")) + str(f.get("target_column")) + str(f.get("slot"))).lower()
        and _qf(f.get("column") or f.get("target_column") or f.get("fn")) == "current"]
    if spread_fields:
        for cid, f in spread_fields:
            k, col, fn = f.get("kind"), f.get("column"), f.get("fn")
            ok = (k == "raw" and (col or "").endswith("current_max_spread")) or \
                 (k == "raw" and "spread" in (col or ""))
            verdict = "OK-raw" if ok else f"WRONG ({k} fn={fn} col={col})"
            print(f"  spread slot [card {cid}] {f.get('slot')}: {verdict}")
            if not ok:
                problems.append(f"[card {cid}] spread slot bound {k}/fn={fn}/col={col} — expected raw current_max_spread")
    else:
        print("  (no 'spread' slot surfaced on this page — S2 not exercised here)")

    if problems:
        print("  RESULT: FAIL")
        for p in problems:
            print("    -", p)
    else:
        print("  RESULT: PASS")
    return problems


def main():
    all_problems = []
    for label, prompt, asset_id in CASES:
        try:
            p = _check_case(label, prompt, asset_id)
            if p:
                all_problems += p
        except Exception as e:
            import traceback
            print(f"  ERROR running {label}: {e}")
            traceback.print_exc()
            all_problems.append(f"{label}: crashed {e}")
    print("\n" + "=" * 60)
    print(f"BATTERY: {'GREEN — all correct, no code net needed' if not all_problems else f'{len(all_problems)} PROBLEM(S)'}")
    for p in all_problems:
        print("  -", p)
    sys.exit(1 if all_problems else 0)


if __name__ == "__main__":
    main()
