"""tools/payload_diff/extract.py — pure functions: one execution snapshot → the seven dimension views the diff
compares (page, cards, metadata, bindings, sql, validation, payload). Each view is a plain dict built only from the
snapshot, tolerant of every field being absent (a degraded snapshot yields a degraded view, never a crash)."""
import re


def _cards(snap):
    return ((snap.get("response") or {}).get("cards")) or []


def card_key(card):
    """Stable identity of a card across executions: the 1a template id, prefixed by the asset tag on a multi-asset
    compare (the same card_id renders once per asset there)."""
    asset = card.get("asset") or {}
    prefix = f"a{asset.get('id')}·" if asset.get("id") is not None else ""
    return f"{prefix}c{card.get('card_id')}"


def _stage(snap, name, field=None, default=None):
    """The LAST record of stage `name` in this execution's segment (reroutes re-log 1a; last one is what rendered)."""
    rec = None
    for r in snap.get("stages") or []:
        if r.get("stage") == name:
            rec = r
    if rec is None:
        return default
    return rec.get(field, default) if field else rec


def page_view(snap):
    resp = snap.get("response") or {}
    page = resp.get("page") or {}
    layout = page.get("layout") or {}
    return {
        "page_key": page.get("page_key"), "page_title": page.get("page_title"), "shell": page.get("shell"),
        "metric": page.get("metric"), "intent": page.get("intent"), "story": page.get("story"),
        "layout_primitive": layout.get("layout_primitive"), "grid_template_columns": layout.get("grid_template_columns"),
        "render_shell": layout.get("render_shell"), "groups": len(page.get("groups") or []),
        # flattened so a report names the exact moved part (start/end always move on a re-run; range/sampling rarely)
        "date_window.range": (resp.get("date_window") or {}).get("range"),
        "date_window.start": (resp.get("date_window") or {}).get("start"),
        "date_window.end": (resp.get("date_window") or {}).get("end"),
        "date_window.sampling": (resp.get("date_window") or {}).get("sampling"),
        "asset": ((resp.get("asset") or {}).get("asset") or {}).get("name"),
        "asset_how": (resp.get("asset") or {}).get("how"),
        "asset_pending": resp.get("asset_pending"), "asset_no_data": resp.get("asset_no_data"),
        "validation_blocked": resp.get("validation_blocked"), "data_unavailable": resp.get("data_unavailable"),
        "page_key_how": _stage(snap, "1a", "page_key_how"),
        "rerouted": bool(_stage(snap, "reflect", "reroute_from") or _stage(snap, "1a", "reroute")),
        "n_cards": len(_cards(snap)),
    }


def cards_view(snap):
    """{key: identity dict} — who is on the page (slot/size/swap/endpoint), not what they contain."""
    out = {}
    for i, c in enumerate(_cards(snap)):
        swap = c.get("swap") or {}
        key = card_key(c)
        if key in out:                                  # same card twice without an asset tag → disambiguate by order
            key = f"{key}#{i}"
        out[key] = {
            "card_id": c.get("card_id"), "render_card_id": c.get("render_card_id"), "title": c.get("title"),
            "slot": c.get("slot"), "size": c.get("size"), "role": c.get("role"), "endpoint": c.get("endpoint"),
            "swap_action": swap.get("action"), "swap_origin": swap.get("origin"), "swap_to": swap.get("swap_to_id"),
            "asset": (c.get("asset") or {}).get("name"),
        }
    return out


def metadata_view(snap):
    """{key: the card's presentation/authoring facts} — how each card is titled, sized, storied and disclosed."""
    out = {}
    for i, c in enumerate(_cards(snap)):
        key = card_key(c)
        if key in out:
            key = f"{key}#{i}"
        out[key] = {
            "title": c.get("title"), "size": c.get("size"), "slot": c.get("slot"), "story": c.get("story"),
            "variant": (c.get("payload") or {}).get("variant"), "is_history": c.get("is_history"),
            "date_control": (c.get("render") or {}).get("date_control"), "endpoint": c.get("endpoint"),
            "data_note": c.get("data_note"), "l2_answerability": c.get("l2_answerability"),
            "conforms": c.get("conforms"), "fill_source": c.get("fill_source"),
            "member_scope": (c.get("refetch") or {}).get("member_scope"),
        }
    return out


def bindings_view(snap):
    """{key: data_instructions} — the leaf→column/endpoint wiring Layer 2 declared for the executor."""
    out = {}
    for i, c in enumerate(_cards(snap)):
        key = card_key(c)
        if key in out:
            key = f"{key}#{i}"
        out[key] = c.get("data_instructions")
    return out


_WS = re.compile(r"\s+")
_FROM = re.compile(r'\bFROM\s+("?[\w."]+)', re.IGNORECASE)


def normalize_sql(sql):
    return _WS.sub(" ", (sql or "").strip())


def sql_table(sql):
    m = _FROM.search(sql or "")
    return (m.group(1).strip('"') if m else None)


def sql_view(snap):
    """{'db · statement': {n, table, ms_total, rows_total, errs}} grouped by the normalized statement text (keyed with
    the source db — neuract data reads vs catalog/config reads via data/db_client both ride the trace). Same-prompt
    re-runs repeat identical statements; a code/config change shows up as added/removed statement shapes."""
    out = {}
    for r in snap.get("sql") or []:
        stmt = normalize_sql(r.get("sql"))
        if not stmt:
            continue
        if r.get("db") and r["db"] != "neuract":
            stmt = f"[{r['db']}] {stmt}"
        g = out.setdefault(stmt, {"n": 0, "table": sql_table(stmt), "ms": 0, "rows": 0, "errs": 0})
        g["n"] += 1
        g["ms"] += r.get("ms") or 0
        g["rows"] += r.get("rows") or 0
        g["errs"] += 1 if r.get("err") else 0
    return out


def validation_view(snap):
    resp = snap.get("response") or {}
    val = resp.get("validation") or {}
    page = {
        "verdict": val.get("verdict"), "how": val.get("how"), "policy": val.get("policy"),
        "data_summary": val.get("data_summary"), "payload_summary": val.get("payload_summary"),
        "stage_verdict": _stage(snap, "validate", "verdict"),
        "expected_gap_frac": _stage(snap, "validate", "expected_gap_frac"),
        "asset_gate": _stage(snap, "asset_gate", "decision"),
    }
    cards = {}
    for i, c in enumerate(_cards(snap)):
        key = card_key(c)
        if key in cards:
            key = f"{key}#{i}"
        render = c.get("render") or {}
        cards[key] = {
            "verdict": render.get("verdict"), "answerability": render.get("answerability"),
            "reason": render.get("reason"), "watermark": render.get("watermark"),
            "leaf_stats": render.get("leaf_stats"), "payload_error": c.get("payload_error"),
            "fill_ok": c.get("fill_ok"), "fill_why": c.get("fill_why"), "has_payload": c.get("has_payload"),
        }
    return {"page": page, "cards": cards}


def payload_view(snap):
    """{key: the completed renderer payload} — exactly what the FE mounts as component props."""
    out = {}
    for i, c in enumerate(_cards(snap)):
        key = card_key(c)
        if key in out:
            key = f"{key}#{i}"
        out[key] = c.get("payload")
    return out
