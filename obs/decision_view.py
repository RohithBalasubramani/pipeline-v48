"""obs/decision_view.py — the READ-side decision normalizer for the AI Decision Inspector: one stored LLM call
(stage + raw response text + the stage-declared decision context) → the canonical decision view

    {kind, candidate_kind, candidates, candidates_total, selected, rejected, reasoning, confidence, error}

Selected/reasoning/confidence live INSIDE each stage's response JSON under stage-specific keys, so extraction is a
small DECLARATIVE per-stage mapping here — never re-derived by another model, never guessed from prompt text. The
candidates come verbatim from what the stage materialized before prompting (obs_llm_calls.decision, set via
obs/llm_tap.set_decision); `rejected` = candidates minus the selection, computed here at read time so the stored
record stays raw. Unknown stages fall back to a generic key sniff (reason*/why → reasoning, confidence → confidence).
Pure + fail-open: bad/missing JSON yields a view that says so instead of raising. [atomic: the ONE decision-shaping
concern; consumed by host/inspector_api.py]"""
import json
import re

from domain.fetch_spec import fetch_spec as _fetch_spec   # legacy-alias-aware (old run dumps)

_REJECTED_CAP = 400


def _parse_response(text):
    """The model reply → parsed dict (mirrors llm/client.py's extraction: strip <think>, first {...} blob)."""
    if not text or not isinstance(text, str):
        return None
    txt = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    m = re.search(r"\{.*\}", txt, re.DOTALL)
    if not m:
        return None
    try:
        out = json.loads(m.group(0))
        return out if isinstance(out, dict) else None
    except Exception:
        return None


def _cand_names(decision, key):
    """The candidate identity list (strings) out of the stored decision context, whatever the per-stage dict shape."""
    names = []
    for c in (decision or {}).get("candidates") or []:
        if isinstance(c, dict):
            v = c.get(key)
            if v is not None:
                names.append(v)
        elif isinstance(c, str) and not c.startswith("…[truncated]"):
            names.append(c)
    return names


def _cap_rejected(rejected):
    if len(rejected) > _REJECTED_CAP:
        return rejected[:_REJECTED_CAP] + [f"…[truncated] {len(rejected) - _REJECTED_CAP} more"]
    return rejected


# ── per-stage extractors: (parsed response, decision ctx) → partial view ─────────────────────────────────────────

def _route(out, decision):
    sel = {k: out.get(k) for k in ("page_key", "metric", "intent", "window")}
    pages = _cand_names(decision, "page_key")
    return {"selected": sel,
            "rejected": _cap_rejected([p for p in pages if p != sel.get("page_key")]),
            "reasoning": None, "confidence": None}


def _asset_resolve(out, decision):
    confident = bool(out.get("confident", False))
    names = [n for n in (out.get("names") or []) if n]
    shortlist = [n for n in (out.get("candidates") or []) if n]
    if confident and names:
        sel = {"branch": "confident_pin", "names": names}
    elif not confident:
        sel = {"branch": "ambiguous", "proposed_candidates": shortlist}
    else:
        sel = {"branch": "empty (no asset implied)", "names": []}
    keep = set(names) | set(shortlist)
    return {"selected": sel,
            "rejected": _cap_rejected([n for n in _cand_names(decision, "name") if n not in keep]),
            "reasoning": None, "confidence": confident}


def _basket(out, decision):
    feasible = [c for c in (out.get("feasible") or []) if isinstance(c, str)]
    probable = [p for p in (out.get("probable") or []) if isinstance(p, dict) and p.get("column")]
    sel = {"feasible": feasible,
           "probable": [{"column": p["column"], "confidence": p.get("confidence"), "rank": p.get("rank"),
                         "substitute_for": p.get("substitute_for")} for p in probable]}
    keep = set(feasible) | {p["column"] for p in probable}
    whys = [f"{p['column']}: {p['why']}" for p in probable if p.get("why")]
    confs = [p.get("confidence") for p in probable if isinstance(p.get("confidence"), (int, float))]
    return {"selected": sel,
            "rejected": _cap_rejected([c for c in _cand_names(decision, "column") if c not in keep]),
            "reasoning": "\n".join(whys) or None,
            "confidence": round(sum(confs) / len(confs), 3) if confs else None}


def _l2_emit(out, decision):
    sw = out.get("swap_decision") or {}
    di = out.get("data_instructions") or {}
    sel = {"action": sw.get("action"),
           "swap_to_id": sw.get("swap_to_id"), "swap_to_title": sw.get("swap_to_title"),
           "cascade": sw.get("cascade") or None,
           "endpoint": _fetch_spec(di).get("endpoint"),
           "answerability": out.get("answerability")}
    pool = _cand_names(decision, "card_id")
    if sw.get("action") == "swap":
        rejected = [c for c in pool if c != sw.get("swap_to_id")]
    else:
        rejected = list(pool)                                   # keep = the whole pool was declined
    reason_bits = [b for b in (sw.get("criterion"), sw.get("reason"), out.get("data_note")) if b]
    return {"selected": sel, "rejected": _cap_rejected(rejected),
            "reasoning": " — ".join(str(b) for b in reason_bits) or None,
            "confidence": sw.get("confidence")}


def _knowledge(out, decision):
    kind = out.get("kind")
    return {"selected": {"kind": kind},
            "rejected": [k for k in _cand_names(decision, "kind") or ["dashboard", "knowledge", "off_scope"]
                         if k != kind],
            "reasoning": None, "confidence": None}


def _generative(out, decision):
    return {"selected": None, "rejected": [], "reasoning": None, "confidence": None}


def _generic(out, decision):
    """Unknown stage: sniff the conventional keys so a NEW AI stage is inspectable before it gets a mapping here."""
    reasoning = next((out[k] for k in ("reasoning", "reason", "why", "criterion")
                      if isinstance(out.get(k), str) and out[k].strip()), None)
    confidence = next((out[k] for k in ("confidence", "score", "confident")
                       if isinstance(out.get(k), (int, float, bool))), None)
    return {"selected": None, "rejected": [], "reasoning": reasoning, "confidence": confidence}


_EXTRACTORS = {
    "route": _route,
    "stories": _generative,
    "asset_resolve": _asset_resolve,
    "basket": _basket,
    "l2_emit": _l2_emit,
    "knowledge_ems": _knowledge,
    "insight_narrator": _generative,
}


def view(stage, response_text, decision=None, error_kind=None):
    """One stored LLM call → the canonical decision view (never raises)."""
    decision = decision if isinstance(decision, dict) else {}
    base = {
        "kind": decision.get("kind") or ("selection" if stage in _EXTRACTORS and _EXTRACTORS[stage] is not _generative
                                         else "unknown"),
        "candidate_kind": decision.get("candidate_kind"),
        "candidates": decision.get("candidates") or [],
        "candidates_total": decision.get("candidates_total") or len(decision.get("candidates") or []),
        "selected": None, "rejected": [], "reasoning": None, "confidence": None,
        "error": error_kind or None,
    }
    try:
        out = _parse_response(response_text)
        if error_kind and out is None:
            return base                                         # the call failed — there IS no selection to extract
        if out is None:
            base["error"] = base["error"] or "unparseable_response"
            return base
        base.update(_EXTRACTORS.get(stage, _generic)(out, decision))
    except Exception as e:                                      # read-side telemetry must never break the API
        base["error"] = base["error"] or f"view_error: {type(e).__name__}"
    return base
