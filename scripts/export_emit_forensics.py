#!/usr/bin/env python3
"""scripts/export_emit_forensics.py — freeze the L2-emit decode-wall forensic evidence rows into test fixtures.

The 2026-07-15 forensics identified load-bearing obs_llm_calls rows for the two runaway mechanisms (A: zero-filled
data-grid morphs; B: roster/fields retype) plus the timeout/clamp cases. This script exports each row's response +
the matching card's stored skeleton (card_payloads.payload_stripped) + roster recipe (card_fill_recipe.roster_spec)
into tests/fixtures/emit_forensics/ so tests/test_emit_diet_contract.py pins the mechanisms PERMANENTLY (the obs
tables rotate; fixtures don't). Re-runnable; overwrites. Offline-safe consumers only (fixtures are plain JSON).
[dev tool — not on any serving path]"""
import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

OUT = os.path.join(_ROOT, "tests", "fixtures", "emit_forensics")

# id -> why it is load-bearing (see docs/latency_audit_20260714/ + the 2026-07-15 forensic report)
ROWS = {
    4485: {"tag": "card24_morphs_grid", "why": "Mechanism A: 14,614-tok emit, morphs = zero-filled periods[*].panels harmonic grid"},
    1372: {"tag": "card22_roster_retype", "why": "Mechanism B: 7,324-tok emit, data_instructions.roster list[110] recipe retype"},
    2590: {"tag": "card43_fields_retype", "why": "Mechanism B: 5,549-tok emit, fields list[64]"},
    4832: {"tag": "card19_obs_clamped", "why": "obs capture clamp at 32,768 chars (live parse OK) - clamped:true", "clamped": True},
    5296: {"tag": "card42_timeout", "why": "pure-concurrency timeout (error_kind=timeout, no completion)"},
}


def main():
    import psycopg2
    os.makedirs(OUT, exist_ok=True)
    c = psycopg2.connect(host="127.0.0.1", port=5432, user="postgres", password="postgres", dbname="cmd_catalog")
    cur = c.cursor()
    cur.execute("SET statement_timeout='30s'")
    exported = []
    for rid, meta in ROWS.items():
        cur.execute("SELECT card_id, response, tokens_prompt, tokens_completion, finish_reason, error_kind, ts "
                    "FROM obs_llm_calls WHERE id=%s", (rid,))
        r = cur.fetchone()
        if not r:
            print(f"  row {rid} MISSING (obs rotated?) — fixture not refreshed")
            continue
        card_id, response, tp, tc, fin, err, ts = r
        rec = {"obs_id": rid, "card_id": card_id, "tag": meta["tag"], "why": meta["why"],
               "clamped": bool(meta.get("clamped")), "tokens_prompt": tp, "tokens_completion": tc,
               "finish_reason": fin, "error_kind": err, "ts": str(ts), "response": response}
        cur.execute("SELECT payload, payload_stripped FROM card_payloads WHERE card_id=%s LIMIT 1", (card_id,))
        row = cur.fetchone()
        rec["payload"] = row[0] if row else None
        rec["payload_stripped"] = row[1] if row else None
        # data_paths exactly as the catalog loader derives them (layer2/catalog/card_payload.py:20)
        try:
            from validate.leaf_classify import classify
            rec["data_paths"] = [d["path"] for d in (classify(rec["payload"]).get("data_leaves") or [])] \
                if rec["payload"] else []
        except Exception as e:
            rec["data_paths"] = []
            print(f"  warn: data_paths derivation failed for card {card_id}: {str(e)[:80]}")
        cur.execute("SELECT roster_spec FROM card_fill_recipe WHERE card_id=%s LIMIT 1", (card_id,))
        row = cur.fetchone()
        rec["roster_spec"] = row[0] if row else None
        p = os.path.join(OUT, f"{meta['tag']}.json")
        json.dump(rec, open(p, "w"), indent=1, sort_keys=True, ensure_ascii=True)
        exported.append((meta["tag"], card_id, tc))
        print(f"  exported {meta['tag']}: card={card_id} ctok={tc} -> {p}")
    c.close()
    print(f"done: {len(exported)}/{len(ROWS)} fixtures")


if __name__ == "__main__":
    main()
