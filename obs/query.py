"""obs/query.py — the READ side: dashboard/analytics queries over the obs_* store, as importable helpers and a CLI.

    python3 -m obs.query recent [N]           last N traces (obs_v_trace_summary)
    python3 -m obs.query trace <trace_id>     one execution: the stage tree with latency/tokens/db/errors
    python3 -m obs.query latency              per-stage p50/p95/p99 (obs_v_stage_latency)
    python3 -m obs.query errors [N]           latest N error events (obs_v_recent_errors)
    python3 -m obs.query tokens [DAYS]        token spend per stage/day (obs_v_token_spend)
    python3 -m obs.query llm <trace_id>       the exact LLM prompts/replies of one execution
    python3 -m obs.query card <trace_id> <id> one card's lifecycle (obs_v_card_funnel + its events)

Postgres-first (the same views a dashboard uses); `trace` falls back to outputs/logs/trace_<id>.jsonl when the DB
is unreachable, so a trace stays inspectable through an outage."""
import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


def _rows(sql, params=()):
    from data.db_client import pg_connect
    from config.databases import CMD_CATALOG
    conn = pg_connect(CMD_CATALOG)
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, r)) for r in cur.fetchall()]
    finally:
        conn.close()


def recent(n=20):
    return _rows("SELECT * FROM obs_v_trace_summary LIMIT %s", (n,))


def stage_latency():
    return _rows("SELECT * FROM obs_v_stage_latency ORDER BY p95_ms DESC NULLS LAST")


def errors(n=50):
    return _rows("SELECT * FROM obs_v_recent_errors LIMIT %s", (n,))


def token_spend(days=7):
    return _rows("SELECT * FROM obs_v_token_spend WHERE day > current_date - %s::int", (days,))


def trace_events(trace_id):
    return _rows("""SELECT seq, kind, stage, card_id, span_id, parent_span_id, latency_ms, status,
                           n_llm_calls, tokens_prompt, tokens_completion, n_db_queries, rows_returned,
                           confidence, degradation, warnings, errors, outputs
                    FROM obs_stage_events WHERE trace_id = %s ORDER BY seq""", (trace_id,))


def llm_calls(trace_id):
    return _rows("""SELECT span_id, parent_span_id, stage, card_id, ts, latency_ms, model, tokens_prompt,
                           tokens_completion, finish_reason, attempt, error_kind, prompt_system, prompt_user,
                           response, params, decision
                    FROM obs_llm_calls WHERE trace_id = %s ORDER BY ts, id""", (trace_id,))


def card_lifecycle(trace_id, card_id):
    return _rows("""SELECT seq, stage, latency_ms, status, outputs, degradation, warnings, errors
                    FROM obs_stage_events WHERE trace_id = %s AND card_id = %s ORDER BY seq""",
                 (trace_id, int(card_id)))


def _trace_from_jsonl(trace_id):
    from obs.paths import logs_dir
    p = os.path.join(logs_dir(), f"trace_{trace_id}.jsonl")
    if not os.path.exists(p):
        return []
    out = []
    with open(p) as f:
        for line in f:
            try:
                e = json.loads(line)
            except Exception:
                continue
            if e.get("kind") in ("stage", "legacy", "trace"):
                out.append({"seq": e.get("seq"), "kind": e.get("kind"), "stage": e.get("stage"),
                            "card_id": e.get("card_id"), "span_id": e.get("span_id"),
                            "parent_span_id": e.get("parent_span_id"), "latency_ms": e.get("latency_ms"),
                            "status": e.get("status"), "n_llm_calls": (e.get("ai") or {}).get("n_calls"),
                            "tokens_prompt": (e.get("ai") or {}).get("tokens_prompt"),
                            "tokens_completion": (e.get("ai") or {}).get("tokens_completion"),
                            "n_db_queries": (e.get("db") or {}).get("n_queries"),
                            "rows_returned": (e.get("db") or {}).get("rows_returned"),
                            "confidence": e.get("confidence"), "degradation": e.get("degradation"),
                            "warnings": e.get("warnings"), "errors": e.get("errors"), "outputs": None})
    return sorted(out, key=lambda r: r.get("seq") or 0)


def _print_tree(events):
    by_span = {e["span_id"]: e for e in events if e.get("span_id")}
    for e in events:
        depth = 0
        p = e.get("parent_span_id")
        while p and p in by_span and depth < 6:
            depth += 1
            p = by_span[p].get("parent_span_id")
        mark = {"ok": " ", "degraded": "~", "error": "!"}.get(e.get("status") or "ok", " ")
        bits = []
        if e.get("card_id") is not None:
            bits.append(f"card={e['card_id']}")
        if e.get("latency_ms"):
            bits.append(f"{e['latency_ms']}ms")
        if e.get("n_llm_calls"):
            bits.append(f"llm={e['n_llm_calls']}({e.get('tokens_prompt') or 0}+{e.get('tokens_completion') or 0}tok)")
        if e.get("n_db_queries"):
            bits.append(f"db={e['n_db_queries']}q/{e.get('rows_returned') or 0}r")
        for w in (e.get("warnings") or [])[:2]:
            bits.append(f"warn={str(w)[:80]}")
        for x in (e.get("errors") or [])[:2]:
            bits.append(f"ERROR={str(x)[:100]}")
        print(f"{mark} {'  ' * depth}{e.get('stage'):<{max(4, 34 - 2 * depth)}} " + "  ".join(bits))


def main(argv):
    cmd = (argv[1] if len(argv) > 1 else "recent").strip()
    try:
        if cmd == "recent":
            for r in recent(int(argv[2]) if len(argv) > 2 else 20):
                print(f"{r['trace_id']}  {str(r['started_at'])[:19]}  {r['status']:<8} {r.get('latency_ms') or '-':>7}ms  "
                      f"page={r.get('page_key')}  cards={r.get('n_cards')}  tok={r.get('tokens_prompt') or 0}+"
                      f"{r.get('tokens_completion') or 0}  {json.dumps(r.get('verdicts'))}  {(r.get('prompt') or '')!r}")
        elif cmd == "trace":
            tid = argv[2]
            try:
                events = trace_events(tid)
            except Exception as e:
                print(f"(pg unreachable: {e} — falling back to jsonl)", file=sys.stderr)
                events = []
            if not events:
                events = _trace_from_jsonl(tid)
            _print_tree(events)
        elif cmd == "latency":
            for r in stage_latency():
                print(f"{r['stage']:<34} n={r['n']:<6} p50={r['p50_ms']}ms  p95={r['p95_ms']}ms  "
                      f"p99={r['p99_ms']}ms  max={r['max_ms']}ms  err={r['n_error']}  degraded={r['n_degraded']}")
        elif cmd == "errors":
            for r in errors(int(argv[2]) if len(argv) > 2 else 50):
                print(f"{str(r['ts'])[:19]}  {r['trace_id']}  {r['stage']:<24} card={r.get('card_id')}  "
                      f"{json.dumps(r.get('errors'))[:160]}")
        elif cmd == "tokens":
            for r in token_spend(int(argv[2]) if len(argv) > 2 else 7):
                print(f"{r['day']}  {r['stage']:<20} calls={r['n_calls']:<5} tok={r['tokens_prompt'] or 0}+"
                      f"{r['tokens_completion'] or 0}  avg={r['avg_latency_ms']}ms  failed={r['n_failed']}")
        elif cmd == "llm":
            for r in llm_calls(argv[2]):
                print(f"── {r['stage']} card={r.get('card_id')} {r['latency_ms']}ms tok={r.get('tokens_prompt')}+"
                      f"{r.get('tokens_completion')} finish={r.get('finish_reason')} err={r.get('error_kind')}")
                print(f"   user: {(r.get('prompt_user') or '')[:400]!r}")
                print(f"   resp: {(r.get('response') or '')[:400]!r}")
        elif cmd == "card":
            for r in card_lifecycle(argv[2], argv[3]):
                print(f"{r['seq']:>4}  {r['stage']:<30} {r['status']:<9} {r.get('latency_ms') or '-':>7}ms  "
                      f"{json.dumps(r.get('outputs'))[:200] if r.get('outputs') else ''}")
        else:
            print(__doc__)
    except IndexError:
        print(__doc__)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
