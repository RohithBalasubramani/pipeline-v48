#!/usr/bin/env python3
"""MTP losslessness cert. Replays N real l2_emit requests (from obs_llm_calls) through the pipeline's OWN provider
(byte-identical to production: temp0, seed42, json_object). `capture` saves completions; `compare` asserts a fresh run
is byte-identical to a saved baseline. Greedy decode => MTP must reproduce the exact token stream. ASCII-safe."""
import sys, os, json, time, hashlib
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
OUT = os.path.dirname(os.path.abspath(__file__))

def _rows(n=12):
    import psycopg2
    c = psycopg2.connect(host="127.0.0.1", port=5432, user="postgres", password="postgres", dbname="cmd_catalog")
    cur = c.cursor(); cur.execute("SET statement_timeout='20s'")
    # diverse: one latest row per distinct prompt_user length bucket + card, real emits only
    cur.execute("""
        SELECT DISTINCT ON (card_id, length(prompt_user))
               id, card_id, prompt_system, prompt_user, response, tokens_completion
        FROM obs_llm_calls
        WHERE stage='l2_emit' AND prompt_user IS NOT NULL AND prompt_system IS NOT NULL
              AND response IS NOT NULL AND length(response) > 50
        ORDER BY card_id, length(prompt_user), ts DESC LIMIT %s""", (n,))
    out = [dict(id=r[0], card_id=r[1], system=r[2], user=r[3], stored=r[4], stored_ctok=r[5]) for r in cur.fetchall()]
    c.close(); return out

def _complete(system, user):
    from llm import config as _cfg_mod
    from llm import providers as _providers
    from config.app_config import cfg
    provider = _providers.resolve()
    mx = int(cfg("llm.max_tokens", 0) or 0)
    t0 = time.time()
    reply = provider.complete(system, user, url=_cfg_mod.LLM_URL, model=_cfg_mod.MODEL, timeout=200,
                              temperature=cfg("llm.temperature", 0), seed=cfg("llm.seed", 42),
                              schema=None, max_tokens=mx)
    return reply, time.time() - t0

def _norm(reply):
    # provider.complete returns a parsed dict (json_object) OR a string; canonicalize to a stable string for byte-compare
    if isinstance(reply, (dict, list)):
        return json.dumps(reply, sort_keys=True, ensure_ascii=True)
    return str(reply)

def capture(tag):
    rows = _rows()
    recs = []
    for i, r in enumerate(rows):
        try:
            reply, dt = _complete(r["system"], r["user"])
            s = _norm(reply)
            recs.append(dict(id=r["id"], card_id=r["card_id"], ok=True, sec=round(dt, 2),
                             h=hashlib.sha256(s.encode()).hexdigest()[:16], n=len(s), body=s))
            print(("  [%d/%d] card=%s %.1fs len=%d h=%s" % (i+1, len(rows), r["card_id"], dt, len(s),
                   recs[-1]["h"])).encode('ascii','replace').decode())
        except Exception as e:
            recs.append(dict(id=r["id"], card_id=r["card_id"], ok=False, err=str(e)[:120]))
            print(("  [%d/%d] card=%s ERROR %s" % (i+1, len(rows), r["card_id"], str(e)[:100])).encode('ascii','replace').decode())
    p = os.path.join(OUT, "mtp_%s.json" % tag)
    json.dump(recs, open(p, "w"))
    tot = sum(r.get("sec", 0) for r in recs if r.get("ok"))
    print("saved %d recs -> %s  (total complete time %.1fs)" % (len(recs), p, tot))

def compare(a, b):
    ra = {r["id"]: r for r in json.load(open(os.path.join(OUT, "mtp_%s.json" % a)))}
    rb = {r["id"]: r for r in json.load(open(os.path.join(OUT, "mtp_%s.json" % b)))}
    ids = sorted(set(ra) & set(rb))
    ident = diff = err = 0
    ta = tb = 0.0
    for i in ids:
        x, y = ra[i], rb[i]
        if not (x.get("ok") and y.get("ok")):
            err += 1; continue
        ta += x["sec"]; tb += y["sec"]
        if x["h"] == y["h"]:
            ident += 1
        else:
            diff += 1
            print(("  MISMATCH id=%s card=%s: %s(len %d) vs %s(len %d)" %
                   (i, x["card_id"], x["h"], x["n"], y["h"], y["n"])).encode('ascii','replace').decode())
    print("CERT %s vs %s: identical=%d  MISMATCH=%d  errored=%d" % (a, b, ident, diff, err))
    print("  timing: %s total %.1fs -> %s total %.1fs  (%.2fx)" % (a, ta, b, tb, (ta/tb if tb else 0)))
    sys.exit(1 if diff else 0)

if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "capture":
        capture(sys.argv[2])
    elif cmd == "compare":
        compare(sys.argv[2], sys.argv[3])
