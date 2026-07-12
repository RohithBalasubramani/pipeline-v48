"""replay/compare.py — original bundle vs replay bundle → one sectioned comparison dict, differences classified
automatically. Deep diffs reuse tools/payload_diff/deep_diff (STRUCTURAL vs VALUE + emptied/filled honesty subkinds).
Sections mirror the user-facing pipeline stages: request, ai_calls, page_selection, asset_resolution, l2_metadata,
sql, executor, validation, rendering, notes_errors, timing. Section severity: identical | drift (same shape, moved
values — what live data does) | diverged (structure/routing/keys changed — what code/model drift does) | missing.
Timing is informational only. Nothing is silently capped: deep-diff truncation entries are explicit."""
import json

from replay import coding
from tools.payload_diff.deep_diff import diff as deep_diff

_SQL_KINDS = ("sql.q", "sql.reg", "sql.regd", "sql.nx")


def compare_bundles(orig, repl, *, tol=0.0):
    o_art, r_art = orig.get("artifacts") or {}, repl.get("artifacts") or {}
    sections = {
        "request": _from_entries(deep_diff(_plain((orig.get("request") or {}).get("body")),
                                           _plain((repl.get("request") or {}).get("body")), tol=tol)),
        "ai_calls": _ai_calls(orig.get("events") or [], repl.get("events") or []),
        "sql": _sql(orig.get("events") or [], repl.get("events") or []),
        "executor": _executor(orig.get("events") or [], repl.get("events") or [], tol),
        "rendering": _rendering(o_art.get("response"), r_art.get("response"), tol),
        "timing": _timing(orig, repl),
    }
    sections.update(_pipeline_out_sections(o_art, r_art, tol))
    order = ["request", "ai_calls", "page_selection", "asset_resolution", "l2_metadata", "sql",
             "executor", "validation", "rendering", "notes_errors", "timing"]
    overall = _worst(s.get("severity") for k, s in sections.items() if k != "timing")
    return {
        "overall": overall,
        "original": {"trace_id": (orig.get("manifest") or {}).get("trace_id"),
                     "started_at": (orig.get("manifest") or {}).get("started_at_iso"),
                     "git_sha": (orig.get("manifest") or {}).get("git_sha"),
                     "prompt": (orig.get("manifest") or {}).get("prompt")},
        "replay": {"trace_id": (repl.get("manifest") or {}).get("trace_id"),
                   "started_at": (repl.get("manifest") or {}).get("started_at_iso"),
                   "git_sha": (repl.get("manifest") or {}).get("git_sha")},
        "sections": {k: sections[k] for k in order if k in sections},
    }


# ── section builders ─────────────────────────────────────────────────────────────────────────────────────────────────

def _pipeline_out_sections(o_art, r_art, tol):
    """page_selection / asset_resolution / l2_metadata / validation / notes_errors from the pipeline_out lanes.
    Lanes align by artifact name (run_ids are prompt-derived → identical across original and replay)."""
    o_lanes = {k: v for k, v in o_art.items() if k.startswith("pipeline_out_")}
    r_lanes = {k: v for k, v in r_art.items() if k.startswith("pipeline_out_")}
    views = {"page_selection": _page_view, "asset_resolution": _asset_view,
             "l2_metadata": _l2_view, "validation": _validation_view, "notes_errors": _notes_view}
    out = {}
    for name, view in views.items():
        entries, sides = [], {"a_only": [], "b_only": []}
        for lane in sorted(set(o_lanes) | set(r_lanes)):
            prefix = "" if len(set(o_lanes) | set(r_lanes)) == 1 else f"{lane.replace('pipeline_out_', '')}."
            if lane not in r_lanes:
                sides["a_only"].append(lane)
                continue
            if lane not in o_lanes:
                sides["b_only"].append(lane)
                continue
            a, b = view(_plain(o_lanes[lane]) or {}), view(_plain(r_lanes[lane]) or {})
            entries += deep_diff(a, b, path=prefix.rstrip("."), tol=tol)
            if name == "page_selection":
                out.setdefault("_page_pair", (a, b))
        sec = _from_entries(entries)
        # IDENTITY ESCALATION: a changed routed page / resolved asset / card set is a DIVERGENCE even though the
        # scalar itself diffs as a mere 'value' change — routing identity is structure, not data jitter.
        idkeys = {"page_selection": ("page_key", "cards"), "asset_resolution": ("asset", "how")}.get(name)
        if sec["severity"] == "drift" and idkeys and any(
                any(tok in (e.get("path") or "") for tok in idkeys) for e in entries):
            sec["severity"] = "diverged"
        if sides["a_only"] or sides["b_only"]:
            sec["severity"] = "diverged"
            sec["lanes_only_original"], sec["lanes_only_replay"] = sides["a_only"], sides["b_only"]
        out[name] = sec
    pair = out.pop("_page_pair", None)
    if pair:
        out["page_selection"]["original_page"], out["page_selection"]["replay_page"] = pair[0].get("page_key"), pair[1].get("page_key")
    return out


def _page_view(out):
    l1a = out.get("layer1a") or {}
    return {"page_key": l1a.get("page_key"), "page_title": l1a.get("page_title"),
            "metric": l1a.get("metric"), "intent": l1a.get("intent"), "window": out.get("window"),
            "layout_primitive": (l1a.get("layout") or {}).get("layout_primitive"),
            "cards": [{"card_id": c.get("card_id"), "title": c.get("title")} for c in (l1a.get("cards") or [])]}


def _asset_view(out):
    l1b = out.get("layer1b") or {}
    a = l1b.get("asset") or {}
    return {"asset": {"name": a.get("name"), "mfm_id": a.get("mfm_id"), "class": a.get("class"),
                      "table": a.get("table"), "member_scope": a.get("member_scope")},
            "how": l1b.get("how"), "class_prior": l1b.get("class_prior"),
            "candidates": [c.get("name") for c in (l1b.get("candidate_list") or [])],
            "basket_n_columns": (l1b.get("column_basket") or {}).get("n_columns"),
            "asset_no_data": out.get("asset_no_data"), "asset_pending": out.get("asset_pending")}


def _l2_view(out):
    l2 = out.get("layer2") or {}
    view = {}
    for cid, o in sorted(l2.items(), key=lambda kv: str(kv[0])):
        o = o or {}
        view[str(cid)] = {"conforms": o.get("conforms"), "answerability": o.get("answerability"),
                          "gap": o.get("gap"), "data_note": o.get("data_note"),
                          "swap_decision": o.get("swap_decision"),
                          "exact_metadata": o.get("exact_metadata"),
                          "data_instructions": o.get("data_instructions")}
    return view


def _validation_view(out):
    v = out.get("validation") or {}
    return {"verdict": v.get("verdict"), "how": v.get("how"), "policy": v.get("policy"),
            "expected_gap_frac": v.get("expected_gap_frac"),
            "data_summary": (v.get("data") or {}).get("summary"),
            "payload_summary": (v.get("payload") or {}).get("summary"),
            "validation_blocked": out.get("validation_blocked"),
            "data_unavailable": out.get("data_unavailable"), "degrade": out.get("degrade")}


def _notes_view(out):
    return {"notes": out.get("notes"), "errors": out.get("errors")}


def _ai_calls(o_events, r_events):
    """Per-stage alignment by occurrence index. prompt drift (inputs changed) is separated from completion drift
    (same prompt, different reply) — the first is upstream data/code, the second is the model layer."""
    o_by, r_by = _llm_by_stage(o_events), _llm_by_stage(r_events)
    calls, worst = [], "identical"
    for stage in list(o_by) + [s for s in r_by if s not in o_by]:
        oq, rq = o_by.get(stage, []), r_by.get(stage, [])
        for i in range(max(len(oq), len(rq))):
            o, r = (oq[i] if i < len(oq) else None), (rq[i] if i < len(rq) else None)
            c = {"stage": stage, "n": i}
            if o is None or r is None:
                c["status"] = "only_replay" if o is None else "only_original"
                c["severity"] = "diverged"
            elif o.get("key") == r.get("key"):
                same = _plain(o.get("value")) == _plain(r.get("value")) and o.get("outcome") == r.get("outcome")
                c["status"] = "identical" if same else "completion_drift"
                c["severity"] = "identical" if same else "diverged"
                if not same:
                    c["value_diff"] = deep_diff(_plain(o.get("value")), _plain(r.get("value")), max_entries=80)
            else:
                c["status"] = "prompt_drift"
                c["severity"] = "diverged"
                c["prompt_diff"] = _prompt_drift(o, r)
                same_out = _plain(o.get("value")) == _plain(r.get("value"))
                c["same_completion_anyway"] = same_out
                if not same_out:
                    c["value_diff"] = deep_diff(_plain(o.get("value")), _plain(r.get("value")), max_entries=80)
            c["served"] = (r or {}).get("served")
            c["ms"] = {"original": (o or {}).get("ms"), "replay": (r or {}).get("ms")}
            worst = _worst([worst, c["severity"]])
            calls.append(c)
    n_diff = sum(1 for c in calls if c["severity"] != "identical")
    return {"severity": worst, "n_calls": {"original": sum(len(v) for v in o_by.values()),
                                           "replay": sum(len(v) for v in r_by.values())},
            "n_differing": n_diff, "calls": calls}


def _prompt_drift(o, r):
    out = {}
    for part in ("system", "user"):
        a, b = str(o.get(part) or ""), str(r.get(part) or "")
        if a == b:
            continue
        i = next((j for j, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))
        out[part] = {"len": [len(a), len(b)], "first_diff_at": i,
                     "original_excerpt": a[max(0, i - 80):i + 160], "replay_excerpt": b[max(0, i - 80):i + 160]}
    return out


def _sql(o_events, r_events):
    """Align by content key (door+db+sql+params). Same key → row-level equality check; keys on one side only are
    code-path changes (or tape misses) — listed, never summarized away."""
    o_map, r_map = _sql_by_key(o_events), _sql_by_key(r_events)
    changed, only_o, only_r = [], [], []
    for k, oe in o_map.items():
        re_ = r_map.get(k)
        if re_ is None:
            only_o.append(_sql_brief(oe))
            continue
        if _plain(oe.get("rows")) != _plain(re_.get("rows")) or oe.get("outcome") != re_.get("outcome"):
            changed.append({**_sql_brief(oe), "n_rows": [oe.get("n_rows"), re_.get("n_rows")],
                            "outcome": [oe.get("outcome"), re_.get("outcome")]})
    only_r = [_sql_brief(e) for k, e in r_map.items() if k not in o_map]
    misses = [e for e in r_events if e.get("kind") == "tape_miss"] + \
             [e for e in r_events if e.get("kind") == "tape_fuzzy"]
    sev = "identical"
    if changed:
        sev = "drift"
    if only_o or only_r:
        sev = "diverged"
    return {"severity": sev, "n_queries": {"original": len(o_map), "replay": len(r_map)},
            "changed_results": changed, "only_original": only_o, "only_replay": only_r,
            "tape_misses": [{k: v for k, v in e.items() if k in ("kind", "group", "stage", "door", "sql", "table")}
                            for e in misses]}


def _executor(o_events, r_events, tol):
    o_cards = {str(e.get("cid")): e for e in o_events if e.get("kind") == "exec_card"}
    r_cards = {str(e.get("cid")): e for e in r_events if e.get("kind") == "exec_card"}
    cards, worst = [], "identical"
    for cid in list(o_cards) + [c for c in r_cards if c not in o_cards]:
        o, r = o_cards.get(cid), r_cards.get(cid)
        if o is None or r is None:
            cards.append({"card_id": cid, "status": "only_replay" if o is None else "only_original",
                          "severity": "diverged"})
            worst = "diverged"
            continue
        entries = deep_diff(_plain(o.get("payload")), _plain(r.get("payload")), tol=tol)
        entries += deep_diff({"window": _plain(o.get("window"))}, {"window": _plain(r.get("window"))}, tol=tol)
        sec = _from_entries(entries)
        cards.append({"card_id": cid, "render_card_id": o.get("render_card_id"),
                      "handling_class": o.get("handling_class"), **sec})
        worst = _worst([worst, sec["severity"]])
    return {"severity": worst, "n_cards": {"original": len(o_cards), "replay": len(r_cards)}, "cards": cards}


def _rendering(o_resp, r_resp, tol):
    if not isinstance(o_resp, dict) or not isinstance(r_resp, dict):
        return {"severity": "missing", "note": "response artifact absent on one side"}
    flags = ("ok", "kind", "asset_pending", "asset_no_data", "validation_blocked", "data_unavailable")
    entries = deep_diff({k: o_resp.get(k) for k in flags}, {k: r_resp.get(k) for k in flags})
    entries += deep_diff({"date_window": _plain(o_resp.get("date_window"))},
                         {"date_window": _plain(r_resp.get("date_window"))}, tol=tol)
    o_cards, r_cards = _card_view(o_resp), _card_view(r_resp)
    cards, worst = [], _from_entries(entries)["severity"]
    for key in list(o_cards) + [k for k in r_cards if k not in o_cards]:
        o, r = o_cards.get(key), r_cards.get(key)
        if o is None or r is None:
            cards.append({"card": key, "status": "only_replay" if o is None else "only_original",
                          "severity": "diverged"})
            worst = "diverged"
            continue
        c_entries = deep_diff(o, r, tol=tol)
        sec = _from_entries(c_entries)
        if sec["severity"] != "identical":
            cards.append({"card": key, "title": o.get("title"),
                          "verdict": [(o.get("render") or {}).get("verdict"), (r.get("render") or {}).get("verdict")],
                          **sec})
        worst = _worst([worst, sec["severity"]])
    return {"severity": worst, "flag_diff": entries,
            "n_cards": {"original": len(o_cards), "replay": len(r_cards)}, "cards_differing": cards}


def _timing(orig, repl):
    def _tot(b):
        ev = b.get("events") or []
        return {"elapsed_ms": ((b.get("manifest") or {}).get("ts_end") or 0) and
                int((((b.get("manifest") or {}).get("ts_end") or 0) - ((b.get("manifest") or {}).get("ts_start") or 0)) * 1000),
                "llm_ms": sum(e.get("ms") or 0 for e in ev if e.get("kind") == "llm"),
                "sql_ms": sum(e.get("ms") or 0 for e in ev if e.get("kind") in _SQL_KINDS),
                "n_events": len(ev)}
    return {"severity": "identical", "informational": True,
            "original": _tot(orig), "replay": _tot(repl)}


# ── plumbing ─────────────────────────────────────────────────────────────────────────────────────────────────────────

def _card_view(resp):
    out = {}
    for c in (resp.get("cards") or []):
        key = f"{((c.get('asset') or {}).get('id', '-'))}:{c.get('card_id')}"
        out[key] = {"card_id": c.get("card_id"), "title": c.get("title"),
                    "render": {k: (c.get("render") or {}).get(k) for k in ("verdict", "reason", "answerability")},
                    "has_payload": c.get("has_payload"), "data_note": c.get("data_note"),
                    "l2_answerability": c.get("l2_answerability"),
                    "payload": _plain(c.get("payload"))}
    return out


def _llm_by_stage(events):
    by = {}
    for e in events:
        if e.get("kind") == "llm":
            by.setdefault(e.get("stage") or "-", []).append(e)
    return by


def _sql_by_key(events):
    return {e["key"]: e for e in events if e.get("kind") in _SQL_KINDS and e.get("key")}


def _sql_brief(e):
    return {"door": e.get("kind"), "db": e.get("db"), "sql": str(e.get("sql") or "")[:400],
            "n_rows": e.get("n_rows")}


def _plain(x):
    """Typed-encoded → display-plain (datetimes/Decimals become strings) so diffs are readable AND serializable."""
    if x is None:
        return None
    try:
        return json.loads(json.dumps(coding.decode(x), default=str))
    except Exception:
        return x


def _from_entries(entries):
    sev = "identical"
    if any(e.get("cls") == "value" for e in entries):
        sev = "drift"
    if any(e.get("cls") == "structural" for e in entries):
        sev = "diverged"
    return {"severity": sev, "n_diffs": len(entries), "diffs": entries}


def _worst(sevs):
    rank = {"identical": 0, "drift": 1, "missing": 2, "diverged": 3}
    worst = "identical"
    for s in sevs or []:
        if s and rank.get(s, 0) > rank.get(worst, 0):
            worst = s
    return worst
