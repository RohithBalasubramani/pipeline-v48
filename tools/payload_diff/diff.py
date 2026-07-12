"""tools/payload_diff/diff.py — the per-dimension comparison semantics: two snapshots → ONE report dict the renderers
(terminal + HTML) consume. Each dimension diffs independently and records why it degraded when a snapshot lacks its
source. The headline signal ordering follows the repo's honesty philosophy: REAL→EMPTY leaf regressions first, then
structural changes, then value drift (live data always drifts)."""
from tools.payload_diff import deep_diff as D
from tools.payload_diff import extract as X
from tools.payload_diff.align import align


def _field_changes(a, b, skip=()):
    out = []
    keys = list(a or {}) + [k for k in (b or {}) if k not in (a or {})]   # view order (page_key first), not alphabetical
    for k in keys:
        if k in skip:
            continue
        va, vb = (a or {}).get(k), (b or {}).get(k)
        if va != vb:
            out.append({"field": k, "a": va, "b": vb})
    return out


def _per_card(view_a, view_b, tol=0.0, max_entries=400):
    paired, only_a, only_b = align(view_a, view_b)
    cards = []
    for key in paired:
        entries = D.diff(view_a.get(key), view_b.get(key), tol=tol, max_entries=max_entries)
        if entries:
            cards.append({"key": key, "entries": entries, **{k: len(v) for k, v in D.split(entries).items()}})
    return {"cards": cards, "only_a": only_a, "only_b": only_b,
            "n_paired": len(paired), "n_changed": len(cards),
            "totals": {k: sum(c.get(k, 0) for c in cards) for k in ("structural", "value", "emptied", "filled")}}


def _sql_dim(snap_a, snap_b):
    reason = (snap_a.get("unavailable") or {}).get("sql") or (snap_b.get("unavailable") or {}).get("sql")
    va, vb = X.sql_view(snap_a), X.sql_view(snap_b)
    if not va and not vb:
        return {"unavailable": reason or "no SQL recorded on either side"}
    added = [{"sql": s, **vb[s]} for s in vb if s not in va]
    removed = [{"sql": s, **va[s]} for s in va if s not in vb]
    recount = [{"sql": s, "table": va[s]["table"], "n_a": va[s]["n"], "n_b": vb[s]["n"]}
               for s in va if s in vb and va[s]["n"] != vb[s]["n"]]
    note = None
    if (not snap_a.get("sql")) != (not snap_b.get("sql")):
        side = "A" if not snap_a.get("sql") else "B"
        note = f"execution {side} has no SQL trace — added/removed lists reflect that, not a query change"
    return {"added": added, "removed": removed, "recount": recount,
            "n_a": sum(g["n"] for g in va.values()), "n_b": sum(g["n"] for g in vb.values()),
            "same": not (added or removed or recount), "note": note}


def _validation_dim(snap_a, snap_b):
    va, vb = X.validation_view(snap_a), X.validation_view(snap_b)
    page = _field_changes(va["page"], vb["page"])
    paired, only_a, only_b = align(va["cards"], vb["cards"])
    cards, regressions = [], 0
    for key in paired:
        ca, cb = va["cards"][key], vb["cards"][key]
        changes = _field_changes(ca, cb)
        if not changes:
            continue
        # the headline: a card whose verdict fell out of the rendering set, or whose REAL leaf count dropped
        renders = ("render", "partial")
        verdict_reg = (ca.get("verdict") in renders) and (cb.get("verdict") not in renders)
        real_a = ((ca.get("leaf_stats") or {}).get("real") or 0)
        real_b = ((cb.get("leaf_stats") or {}).get("real") or 0)
        leaf_reg = real_b < real_a
        if verdict_reg or leaf_reg:
            regressions += 1
        cards.append({"key": key, "changes": changes, "verdict_a": ca.get("verdict"), "verdict_b": cb.get("verdict"),
                      "real_a": real_a, "real_b": real_b, "regression": verdict_reg or leaf_reg})
    return {"page": page, "cards": cards, "only_a": only_a, "only_b": only_b,
            "regressions": regressions, "same": not (page or cards or only_a or only_b)}


def _config_dim(snap_a, snap_b):
    ca, cb = snap_a.get("app_config") or {}, snap_b.get("app_config") or {}
    if not ca and not cb:
        return {"unavailable": "app_config fingerprint absent on both sides"}
    changes = [{"key": k, "a": ca.get(k), "b": cb.get(k)}
               for k in sorted(ca.keys() | cb.keys()) if ca.get(k) != cb.get(k)]
    note = None
    if bool(ca) != bool(cb):
        note = "one side captured no app_config fingerprint (DB unreachable at capture time) — drift list is one-sided"
    return {"changes": changes, "same": not changes, "note": note}


def compare(snap_a, snap_b, tol=0.0, max_entries=400):
    """The full report dict. `tol` = relative numeric tolerance applied to bindings + payload value comparisons."""
    resp_missing = {s: (snap.get("unavailable") or {}).get("response")
                    for s, snap in (("a", snap_a), ("b", snap_b)) if (snap.get("unavailable") or {}).get("response")}

    def dim(build):
        if resp_missing:
            side = " / ".join(f"{s.upper()}: {why}" for s, why in resp_missing.items())
            return {"unavailable": f"response unavailable — {side}"}
        return build()

    report = {
        "provenance": {
            side: {"prompt": snap["meta"].get("prompt"), "run_id": snap["meta"].get("run_id"),
                   "occurrence": snap["meta"].get("occurrence"), "captured_at": snap["meta"].get("captured_at"),
                   "source": snap["meta"].get("source"), "label": snap["meta"].get("label"),
                   "git": snap["meta"].get("git"), "elapsed_ms": snap["meta"].get("elapsed_ms"),
                   "unavailable": snap.get("unavailable") or {}}
            for side, snap in (("a", snap_a), ("b", snap_b))
        },
        "page": dim(lambda: {"changes": _field_changes(X.page_view(snap_a), X.page_view(snap_b))}),
        "cards": dim(lambda: _per_card(X.cards_view(snap_a), X.cards_view(snap_b))),
        "metadata": dim(lambda: _per_card(X.metadata_view(snap_a), X.metadata_view(snap_b))),
        "bindings": dim(lambda: _per_card(X.bindings_view(snap_a), X.bindings_view(snap_b), tol=tol)),
        "sql": _sql_dim(snap_a, snap_b),
        "validation": dim(lambda: _validation_dim(snap_a, snap_b)),
        "payload": dim(lambda: _per_card(X.payload_view(snap_a), X.payload_view(snap_b), tol=tol,
                                         max_entries=max_entries)),
        "config": _config_dim(snap_a, snap_b),
        "tol": tol,
    }
    if "changes" in report["page"]:
        report["page"]["same"] = not report["page"]["changes"]
    for d in ("cards", "metadata", "bindings", "payload"):
        r = report[d]
        if "unavailable" not in r:
            r["same"] = not (r["n_changed"] or r["only_a"] or r["only_b"])
    return report
