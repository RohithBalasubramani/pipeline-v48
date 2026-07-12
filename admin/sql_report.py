"""admin/sql_report.py — SQL execution report over sql_<run_id>.jsonl (obs/sql_trace.py records).

Record shape (sql_trace): {ts epoch, db, sql, rows, ms, params?, err?} — run_id rides the FILENAME. Answers:
what ran, where (neuract data reads vs cmd_catalog psql), how slow, what failed; searchable by SQL text."""
from admin import store
from admin.config import in_window, iso


def _rows(rid):
    files = store.files_for(rid)
    if "sql" not in files:
        return []
    out = []
    for i, rec in enumerate(store.cached(files["sql"], store.jsonl) or []):
        ts = rec.get("ts") if isinstance(rec.get("ts"), (int, float)) else None
        out.append({"run_id": rid, "idx": i, "ts_epoch": ts, "ts": iso(ts), "db": rec.get("db"),
                    "sql": str(rec.get("sql") or "")[:500], "params": rec.get("params"),
                    "rows": rec.get("rows"), "ms": rec.get("ms"), "err": rec.get("err")})
    return out


def report(t_from=None, t_to=None, run_id=None, q=None, source=None, slow_ms=None, limit=100):
    by_source, matched = {}, []
    total = errors = 0
    needle = q.lower() if q else None
    for rid in ([run_id] if run_id else store.run_ids()):
        for r in _rows(rid):
            if not in_window(r["ts_epoch"], t_from, t_to):
                continue
            if source and r["db"] != source:
                continue
            if needle and needle not in (r["sql"] or "").lower():
                continue
            if slow_ms is not None and (r["ms"] or 0) < slow_ms:
                continue
            total += 1
            errors += 1 if r["err"] else 0
            agg = by_source.setdefault(r["db"] or "unknown",
                                       {"count": 0, "errors": 0, "total_ms": 0, "rows": 0})
            agg["count"] += 1
            agg["errors"] += 1 if r["err"] else 0
            agg["total_ms"] += r["ms"] or 0
            agg["rows"] += r["rows"] or 0
            matched.append(r)
    slowest = sorted(matched, key=lambda r: -(r["ms"] or 0))[:20]
    matched.sort(key=lambda r: -(r["ts_epoch"] or 0))
    for r in matched:
        r.pop("ts_epoch", None)
    return {
        "total": total, "errors": errors,
        "by_source": [{"source": k, **v, "avg_ms": (round(v["total_ms"] / v["count"], 1) if v["count"] else None)}
                      for k, v in sorted(by_source.items(), key=lambda kv: -kv[1]["count"])],
        "slowest": [{k: v for k, v in r.items() if k != "ts_epoch"} for r in slowest],
        "recent": matched[:max(0, int(limit))],
    }
