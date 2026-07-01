"""run/trace.py — BACKEND pipeline tracer (no browser). Runs the FULL intended flow 1a∥1b → Layer 2 (per card) and
logs every handoff so we can verify "1a+1b → 2 → frontend works as expected". Prints a readable trace AND writes
outputs/logs/trace_<run_id>.jsonl.

    python3 run/trace.py "real time monitoring for PCC Panel 1A"

What it checks, layer by layer:
  [1a] page/template + every card's slot (region/cell/slot_order) + size (the POSITIONING — must equal the template)
  [1b] resolved asset + column basket
  [2 ] per-card emit: swap_decision (keep/swap), morph → exact_metadata (the payload the FRONTEND should render), conforms
  [fe] what the frontend receives: the host sends L2's exact_metadata as the card payload (no card_payloads fallback)
"""
import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import obs.ai_log as ai_log                          # noqa: E402  (monkeypatch :8200 logging — import early)
from run.parallel import run_parallel                # noqa: E402
from run.run_id import make_run_id                   # noqa: E402
from layer1a.build import run_1a                     # noqa: E402
from layer1b.build import run_1b                     # noqa: E402
from layer2.build import run_card                    # noqa: E402
from config.databases import CMD_CATALOG             # noqa: E402

_LOGDIR = os.path.join(_ROOT, "outputs", "logs")


def _log(rid, stage, rec):
    os.makedirs(_LOGDIR, exist_ok=True)
    with open(os.path.join(_LOGDIR, f"trace_{rid}.jsonl"), "a") as f:
        f.write(json.dumps({"stage": stage, **rec}) + "\n")


def trace(prompt, asset_id=None):
    rid = make_run_id(prompt)
    ai_log.set_run_id(rid)
    print(f"\n=== RUN {rid} :: {prompt!r} ===")

    res = run_parallel({"1a": lambda: run_1a(prompt, CMD_CATALOG),
                        "1b": lambda: run_1b(prompt, asset_id=asset_id)})
    l1a, l1b = res["1a"], res["1b"]
    if isinstance(l1a, Exception):
        print(f"[1a] EXCEPTION: {type(l1a).__name__}: {l1a}"); return
    if isinstance(l1b, Exception):
        print(f"[1b] EXCEPTION: {type(l1b).__name__}: {l1b}")

    lay = l1a.get("layout") or {}
    print(f"\n[1a] page={l1a['page_key']}  primitive={lay.get('layout_primitive')!r}  cols={lay.get('grid_template_columns')!r}  cards={len(l1a['cards'])}")
    for c in l1a["cards"]:
        s, z = c.get("slot") or {}, c.get("size") or {}
        print(f"     #{c['card_id']:<4} {str(c['title'])[:26]:26} region={str(s.get('region')):7} cell={str(s.get('cell')):10} slot={s.get('slot_order')} size={z.get('width_px')}x{z.get('height_px')}")
        _log(rid, "1a", {"card_id": c["card_id"], "title": c["title"], "slot": s, "size": z})

    if not isinstance(l1b, Exception):
        a = l1b.get("asset") or {}
        print(f"\n[1b] asset={a.get('name')!r} (mfm_id={a.get('mfm_id')}, class={a.get('class')})  basket_cols={(l1b.get('column_basket') or {}).get('n_columns')}")
        _log(rid, "1b", {"asset": a, "n_cols": (l1b.get('column_basket') or {}).get('n_columns')})

    print(f"\n[2 ] per-card emit  (swap_decision | morph → exact_metadata payload | conforms):")
    chosen = set()
    n_ok = n_fail = n_exc = 0
    for c in l1a["cards"]:
        cid = c["card_id"]
        try:
            o = run_card(rid, cid, l1a, l1b, already_chosen=chosen)
            sw = o.get("swap_decision") or {}
            em = o.get("exact_metadata") or {}
            final = sw.get("swap_to_id") or cid
            if final != cid:
                chosen.add(final)
            tag = ("FAIL: " + (o["failure"]["reason"] if o.get("failure") else "?")) if not o.get("conforms") else "ok"
            print(f"     #{cid:<4} swap={str(sw.get('action','?')):5}->{final:<4} conforms={str(o.get('conforms')):5} keys={list(em.keys())[:5]}  {tag}")
            _log(rid, "2", {"card_id": cid, "swap": sw, "conforms": o.get("conforms"),
                            "exact_metadata_keys": list(em.keys()), "failure": o.get("failure")})
            n_ok += int(bool(o.get("conforms"))); n_fail += int(not o.get("conforms"))
        except Exception as e:
            print(f"     #{cid:<4} L2 EXCEPTION: {type(e).__name__}: {e}")
            _log(rid, "2", {"card_id": cid, "exception": f"{type(e).__name__}: {e}"})
            n_exc += 1

    print(f"\n[2 ] summary: {n_ok} conform, {n_fail} non-conform, {n_exc} exception (of {len(l1a['cards'])})")
    print(f"\n[fe] The host sends Layer 2's exact_metadata as each card's `payload` (run/layer2_all.py: payload=exact_metadata;")
    print(f"     host/server.py _enrich_card: payload=l2['payload'], NO card_payloads fallback) — the morphed payload above IS what renders.")
    print(f"\ntrace file: {os.path.join(_LOGDIR, f'trace_{rid}.jsonl')}\n")


if __name__ == "__main__":
    trace(sys.argv[1] if len(sys.argv) > 1 else "real time monitoring for PCC Panel 1A")
