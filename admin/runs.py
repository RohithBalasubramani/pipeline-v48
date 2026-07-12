"""admin/runs.py — per-run summary + the recent-runs listing (date filter, text query, pagination).

A "run" = one run_id. The id is deterministic sha1(prompt) (run/run_id.py), so re-running the SAME prompt APPENDS to
the same pipeline/ai/failures/sql files while response_/notes are overwritten — the summary therefore reflects the
LATEST execution (last PROMPT→RESPONSE block of the stage file, the current response doc), and `executions` counts
how many times the prompt ran. The response doc can be ~MBs (full card payloads) so its parser extracts a SLIM
summary that is what gets cached (store.cached) — never the raw doc."""
from admin import ai_usage, store
from admin.config import in_window, iso


def _slim_response(path):
    """response_<rid>.json → the small header the console needs (never cache the full doc: payloads are big)."""
    d = store.jdoc(path)
    page = d.get("page") or {}
    a = (d.get("asset") or {})
    asset = a.get("asset") or {}
    cards = []
    for c in d.get("cards") or []:
        r = c.get("render") or {}
        v = c.get("validation") if isinstance(c.get("validation"), dict) else {}
        cards.append({
            "card_id": c.get("card_id"), "render_card_id": c.get("render_card_id"), "title": c.get("title"),
            "endpoint": c.get("endpoint"), "verdict": r.get("verdict"), "answerability": r.get("answerability"),
            "reason": r.get("reason"), "leaf_stats": r.get("leaf_stats"), "gaps": r.get("gaps"),
            "payload_error": c.get("payload_error"), "fill_ok": c.get("fill_ok"), "fill_why": c.get("fill_why"),
            "data_note": c.get("data_note"), "l2_answerability": c.get("l2_answerability"),
            "validation_verdict": v.get("verdict"), "swap": bool(c.get("swap")), "asset": c.get("asset"),
        })
    val = d.get("validation") or {}
    return {
        "ok": d.get("ok"), "prompt": d.get("prompt"), "run_id": d.get("run_id"),
        "elapsed_ms": d.get("elapsed_ms"), "kind": d.get("kind"),
        "page_key": page.get("page_key"), "page_title": page.get("page_title"),
        "shell": page.get("shell"), "metric": page.get("metric"), "intent": page.get("intent"),
        "asset_name": asset.get("name"), "asset_class": asset.get("class"), "asset_mfm_id": asset.get("mfm_id"),
        "asset_table": asset.get("table"), "asset_how": a.get("how"),
        "n_candidates": len(a.get("candidates") or []),
        "asset_pending": d.get("asset_pending"), "asset_no_data": d.get("asset_no_data"),
        "data_unavailable": d.get("data_unavailable"), "degrade": d.get("degrade"),
        "validation_blocked": d.get("validation_blocked"), "multi_asset": d.get("multi_asset"),
        "validation": {"verdict": val.get("verdict"), "how": val.get("how"), "policy": val.get("policy"),
                       "data_summary": val.get("data_summary"), "payload_summary": val.get("payload_summary")},
        "date_window": d.get("date_window"), "errors": d.get("errors"),
        "notes": d.get("notes"), "cards": cards,
    }


def response_summary(rid):
    path = store.files_for(rid).get("response")
    return store.cached(path, _slim_response) if path else None


def stage_records(rid):
    """The run's stage timeline rows (pipeline_<rid>.jsonl, ts-sorted; [] when absent)."""
    path = store.files_for(rid).get("pipeline")
    recs = (store.cached(path, store.jsonl) or []) if path else []
    return sorted(recs, key=lambda r: r.get("ts") or 0)


def executions(rid):
    """Split the appended stage timeline into executions: a new slice starts at each PROMPT record."""
    slices, cur = [], []
    for rec in stage_records(rid):
        if rec.get("stage") == "PROMPT" and cur:
            slices.append(cur)
            cur = []
        cur.append(rec)
    if cur:
        slices.append(cur)
    return slices


def summary(rid):
    """RunSummary — the row every listing renders. Sources: last execution's stage lines + slim response + counts."""
    files = store.files_for(rid)
    resp = response_summary(rid)
    execs = executions(rid)
    last = execs[-1] if execs else []
    by_stage = {}
    for rec in last:
        by_stage.setdefault(rec.get("stage"), rec)          # first occurrence per stage in the last execution
    prompt_rec = by_stage.get("PROMPT") or {}
    resp_rec = by_stage.get("RESPONSE") or by_stage.get("RESPONSE_MULTI") or {}
    onea, oneb = by_stage.get("1a") or {}, by_stage.get("1b") or {}
    n_fail = len(store.cached(files["failures"], store.jsonl) or []) if "failures" in files else 0
    n_sql = len(store.cached(files["sql"], store.jsonl) or []) if "sql" in files else 0
    n_ai, ptok, ctok = ai_usage.tokens_for(rid)
    prompt = (resp or {}).get("prompt") or str(prompt_rec.get("text") or "").strip("'\"") or None
    ts = store.last_ts(rid)
    return {
        "run_id": rid,
        "ts": iso(ts), "ts_epoch": ts,
        "prompt": prompt,
        "kind": (resp or {}).get("kind"),
        "page_key": (resp or {}).get("page_key") or onea.get("page"),
        "page_title": (resp or {}).get("page_title"),
        "metric": (resp or {}).get("metric") or onea.get("metric"),
        "asset": (resp or {}).get("asset_name") or oneb.get("asset"),
        "asset_class": (resp or {}).get("asset_class") or oneb.get("class_prior"),
        "asset_how": (resp or {}).get("asset_how") or oneb.get("how"),
        "ok": (resp or {}).get("ok"),
        "asset_pending": (resp or {}).get("asset_pending") if resp else resp_rec.get("asset_pending"),
        "data_unavailable": (resp or {}).get("data_unavailable"),
        "degrade": (resp or {}).get("degrade"),
        "multi_asset": (resp or {}).get("multi_asset"),
        "cards": resp_rec.get("cards") if resp_rec.get("cards") is not None else len((resp or {}).get("cards") or []),
        "rendered": resp_rec.get("rendered"), "partial": resp_rec.get("partial"), "blank": resp_rec.get("blank"),
        "elapsed_ms": (resp or {}).get("elapsed_ms") or resp_rec.get("elapsed_ms"),
        "executions": len(execs),
        "n_failures": n_fail, "n_ai_calls": n_ai, "n_sql": n_sql,
        "prompt_tokens": ptok, "completion_tokens": ctok,
        "has": {fam: (fam in files) for fam in store.FAMILIES},
    }


def list_runs(t_from=None, t_to=None, q=None, page_key=None, limit=50, offset=0, sink="real"):
    """Newest-first run listing with date window, substring query (prompt/run_id/page/asset), page filter."""
    rows = []
    for rid in store.run_ids(sink):
        ts = store.last_ts(rid)
        if not in_window(ts, t_from, t_to):
            continue
        rows.append(summary(rid))
    if q:
        needle = q.lower()
        rows = [r for r in rows if needle in " ".join(
            str(r.get(k) or "") for k in ("prompt", "run_id", "page_key", "asset")).lower()]
    if page_key:
        rows = [r for r in rows if r.get("page_key") == page_key]
    rows.sort(key=lambda r: -(r["ts_epoch"] or 0))
    total = len(rows)
    return {"total": total, "runs": rows[offset:offset + max(0, int(limit))]}
