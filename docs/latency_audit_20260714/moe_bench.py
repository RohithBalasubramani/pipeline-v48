#!/usr/bin/env python3
"""MoE kernel-config throughput bench (paired with the fused_moe tuned-config install). Replays real l2_emit prompts
through the pipeline's OWN provider (mtp_cert._complete: temp0/seed42/json_object) in two shapes:
  solo : 3 sequential requests            (best-case per-stream decode)
  cc4  : 8 requests at concurrency 4     (the PRODUCTION shape - layer2.emit_concurrency=4)
Metrics: per-request completion chars/sec (same prompts across runs -> relative) AND the server's own
vllm generation_tokens_total delta / wall (authoritative aggregate tok/s). ASCII-safe. Usage: moe_bench.py <tag>"""
import sys, os, json, time, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mtp_cert  # noqa: E402  (reuses _complete/_norm + repo sys.path bootstrap)
import urllib.request

OUT = os.path.dirname(os.path.abspath(__file__))
METRICS = "http://127.0.0.1:8200/metrics"


def _rows(n=8, lo=800, hi=6000):
    import psycopg2
    c = psycopg2.connect(host="127.0.0.1", port=5432, user="postgres", password="postgres", dbname="cmd_catalog")
    cur = c.cursor(); cur.execute("SET statement_timeout='20s'")
    cur.execute("""
        SELECT DISTINCT ON (card_id, length(prompt_user))
               id, card_id, prompt_system, prompt_user, tokens_completion
        FROM obs_llm_calls
        WHERE stage='l2_emit' AND prompt_user IS NOT NULL AND prompt_system IS NOT NULL
              AND response IS NOT NULL AND tokens_completion BETWEEN %s AND %s
        ORDER BY card_id, length(prompt_user), ts DESC LIMIT %s""", (lo, hi, n))
    out = [dict(id=r[0], card_id=r[1], system=r[2], user=r[3], ctok=r[4]) for r in cur.fetchall()]
    c.close(); return out


def _gen_tokens():
    try:
        txt = urllib.request.urlopen(METRICS, timeout=5).read().decode()
        tot = 0.0
        for line in txt.splitlines():
            if line.startswith("vllm:generation_tokens_total") or line.startswith("vllm_generation_tokens_total"):
                m = re.search(r"\s([0-9.e+]+)\s*$", line)
                if m:
                    tot += float(m.group(1))
        return tot
    except Exception:
        return None


def _one(r):
    t0 = time.time()
    reply, dt = mtp_cert._complete(r["system"], r["user"])
    s = mtp_cert._norm(reply)
    return dict(id=r["id"], card_id=r["card_id"], sec=round(dt, 2), chars=len(s), cps=round(len(s) / dt, 1))


def main(tag):
    rows = _rows()
    assert len(rows) >= 6, "need >=6 bench rows"
    print("bench rows: %d (ctok %s)" % (len(rows), [r["ctok"] for r in rows]))
    res = {"tag": tag, "solo": [], "cc4": []}

    g0 = _gen_tokens(); t0 = time.time()
    for r in rows[:3]:
        rec = _one(r); res["solo"].append(rec)
        print("  solo card=%s %.1fs %d chars -> %.0f chars/s" % (rec["card_id"], rec["sec"], rec["chars"], rec["cps"]))
    g1 = _gen_tokens(); t1 = time.time()
    if g0 is not None and g1 is not None and t1 > t0:
        res["solo_server_toks"] = round((g1 - g0) / (t1 - t0), 1)
        print("  solo aggregate (server counter): %.0f tok/s" % res["solo_server_toks"])

    from concurrent.futures import ThreadPoolExecutor
    g2 = _gen_tokens(); t2 = time.time()
    with ThreadPoolExecutor(max_workers=4) as ex:
        for rec in ex.map(_one, rows):
            res["cc4"].append(rec)
            print("  cc4  card=%s %.1fs %d chars -> %.0f chars/s" % (rec["card_id"], rec["sec"], rec["chars"], rec["cps"]))
    g3 = _gen_tokens(); t3 = time.time()
    res["cc4_wall"] = round(t3 - t2, 1)
    if g2 is not None and g3 is not None and t3 > t2:
        res["cc4_server_toks"] = round((g3 - g2) / (t3 - t2), 1)
        print("  cc4 wall %.1fs, aggregate (server counter): %.0f tok/s" % (res["cc4_wall"], res["cc4_server_toks"]))

    med = lambda xs: sorted(xs)[len(xs) // 2] if xs else None
    res["solo_med_cps"] = med([r["cps"] for r in res["solo"]])
    res["cc4_med_cps"] = med([r["cps"] for r in res["cc4"]])
    p = os.path.join(OUT, "moe_bench_%s.json" % tag)
    json.dump(res, open(p, "w"), indent=1)
    print("SUMMARY %s: solo med %.0f chars/s | cc4 med %.0f chars/s | cc4 wall %.1fs -> %s"
          % (tag, res["solo_med_cps"], res["cc4_med_cps"], res["cc4_wall"], p))


if __name__ == "__main__":
    main(sys.argv[1])
