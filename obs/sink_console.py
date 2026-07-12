"""obs/sink_console.py — the human stderr line, one per event, in the existing host-log look
(`  [trace8] stage        k=v  k=v`). Console is for WATCHING a run; the queryable record lives in the
jsonl/pg sinks — so this line shows only the small identifying fields, never payload bodies."""
import sys


def _fmt(event):
    tid = (event.get("trace_id") or "-")[-8:]
    stage = event.get("stage") or event.get("kind") or "?"
    bits = []
    if event.get("card_id") is not None:
        bits.append(f"card={event['card_id']}")
    if event.get("latency_ms") is not None and event.get("kind") != "legacy":
        bits.append(f"{event['latency_ms']}ms")
    if event.get("status") and event["status"] != "ok":
        bits.append(f"status={event['status']}")
    ai = event.get("ai") or {}
    if ai.get("n_calls"):
        bits.append(f"llm={ai['n_calls']}({ai.get('tokens_prompt') or 0}+{ai.get('tokens_completion') or 0}tok)")
    if event.get("kind") == "llm":
        bits.append(f"tok={ai.get('tokens_prompt') or 0}+{ai.get('tokens_completion') or 0}")
        if ai.get("error_kind"):
            bits.append(f"err={ai['error_kind']}")
    db = event.get("db") or {}
    if db.get("n_queries"):
        bits.append(f"db={db['n_queries']}q/{db.get('rows_returned') or 0}r")
    if event.get("kind") == "db":
        bits.append(f"{db.get('database')}: {str(db.get('sql') or '')[:60]!r} rows={db.get('rows_returned')}")
    for e in (event.get("errors") or [])[:1]:
        bits.append(f"ERROR={str(e)[:120]}")
    return f"  [{tid}] {stage:<20} " + "  ".join(bits)


def write(event):
    if event.get("kind") in ("db", "legacy"):                  # too chatty for the console; jsonl/pg keep them
        return
    print(_fmt(event), file=sys.stderr, flush=True)
