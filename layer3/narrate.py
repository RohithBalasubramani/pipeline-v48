"""layer3/narrate.py — LAYER 3: the AI PAGE NARRATOR (one AI layer, mirrors layer1a/layer2 shape).

Layers 1-2 route the page, resolve the asset, and fill every card with real meter data; Layer 3 reads the FINISHED
page and tells its story in a few grounded lines. Pure AI-layer convention: a prompt file (prompts/system.md), a
built INPUT DIGEST (prompt/page/asset/validation + per-card story + real readings), and the AI TELLING the narrative
via the one call_qwen seam. Honest-degrade: any failure returns a deterministic one-line fallback — the summary is
decoration, never load-bearing, and NEVER fabricates a number (it only narrates the values it was handed).

(This is a NEW Layer 3 — a page-synthesis stage — NOT the retired 2026-07-02 payload-cleaner L3.)"""
import hashlib
import json
import os

from llm.prompt_load import load as _prompt_load
from llm.client import call_qwen

_HERE = os.path.dirname(os.path.abspath(__file__))
_SCHEMA = {"type": "object", "properties": {"summary": {"type": "string"}}, "required": ["summary"],
           "additionalProperties": False}
_CACHE = {}                       # content-hash → summary str (bounded; the AI fires only when the page changes)
_CACHE_MAX = 256
_MAX_CARDS = 12                   # a page's real card count; the digest is bounded so the prompt never runs away
_MAX_READINGS = 5                 # headline readings per card (label · value · unit)


def _load_prompt(name):
    return _prompt_load(_HERE, name)   # the ONE loader (llm/prompt_load, D8)


def _asset_name(resp):
    a = resp.get("asset")
    if isinstance(a, dict):
        inner = a.get("asset") if isinstance(a.get("asset"), dict) else a
        return inner.get("name") or inner.get("id")
    return None


_SKIP_SUBTREES = {"render", "freshness"}          # host bookkeeping, not card content


def _readings(payload):
    """[ 'Active Power · 731.3 kW', … ] — the card's real labeled scalar readings (grounding for the narrator).
    A labeled object carrying displayValue/value IS a rendered KPI; we pass its label+shown value+unit verbatim.

    Walks the WHOLE payload from its root [narrator-false-blank fix, 2026-07-16]: a card's content root is its OWN key
    (card 12 = rail.vm, card 13 = flow.vm, card 15 = card.view) — the old `payload['data']` walk returned [] for every
    non-`data`-rooted card, so the narrator was handed `readings: []` for cards FULL of rendered values and truthfully
    told the user "no rendered readings" about a page that had them."""
    out = []

    def walk(node, depth=0):
        if len(out) >= _MAX_READINGS or depth > 6:
            return
        if isinstance(node, dict):
            label = node.get("label") or node.get("title")
            val = node.get("displayValue")
            if val is None and isinstance(node.get("value"), (int, float)) and not isinstance(node.get("value"), bool):
                val = node.get("value")
            if label and val is not None and val != "":
                unit = node.get("unit") or ""
                out.append(f"{label} · {val} {unit}".strip())
            for k, v in node.items():
                if isinstance(v, (dict, list)) and k not in _SKIP_SUBTREES:
                    walk(v, depth + 1)
        elif isinstance(node, list):
            for v in node[:6]:
                walk(v, depth + 1)

    walk(payload or {})
    return out[:_MAX_READINGS]


def _leaf_stats(payload):
    """(filled, blank) scalar-leaf counts over the card's whole payload — the GROUND-TRUTH fill statistic the narrator
    reasons from. A 5-reading sample cannot distinguish 'sparse card' from 'blank card'; this count can (a card with
    189 filled numeric leaves is NOT 'no rendered readings' no matter what the sample missed). filled = numeric leaves;
    blank = None/'—'/'' leaves; chrome strings count as neither."""
    filled = blank = 0

    def walk(node, depth=0):
        nonlocal filled, blank
        if depth > 8:
            return
        if isinstance(node, dict):
            for k, v in node.items():
                if k in _SKIP_SUBTREES:
                    continue
                walk(v, depth + 1)
        elif isinstance(node, list):
            for v in node[:60]:
                walk(v, depth + 1)
        elif isinstance(node, (int, float)) and not isinstance(node, bool):
            filled += 1
        elif node is None or (isinstance(node, str) and node.strip() in ("", "—", "-")):
            blank += 1

    walk(payload or {})
    return filled, blank


def _digest(resp):
    """The Layer-3 INPUT: the finished page distilled to what the narrator needs (bounded, grounded)."""
    cards = []
    for c in (resp.get("cards") or [])[:_MAX_CARDS]:
        st = c.get("story")
        story = st if isinstance(st, str) else (st or {}).get("analytical_story") if isinstance(st, dict) else None
        entry = {"title": c.get("title"), "story": story, "readings": _readings(c.get("payload"))}
        # the ground-truth fill statistic (readings is a 5-item SAMPLE; this is the honest census the narrator must
        # trust over the sample — a card with hundreds of filled leaves is rendered even if the sample missed them)
        filled, blank = _leaf_stats(c.get("payload"))
        entry["fill"] = f"{filled} value leaf(es) rendered · {blank} honest-blank"
        gaps = ((c.get("payload") or {}).get("render") or {}).get("gaps")
        if not c.get("has_payload"):
            entry["blank"] = "card honest-blank (no data for this card on this asset)"
        elif gaps:
            entry["blank"] = f"{len(gaps)} leaf(es) honest-blank"
        cards.append(entry)
    v = resp.get("validation") or {}
    ds = v.get("data_summary") or {}
    return {
        "prompt": resp.get("prompt"),
        "page": (resp.get("page") or {}).get("page_title"),
        "asset": _asset_name(resp),
        "validation": f"{v.get('verdict') or 'n/a'} · {ds.get('n_pass', 0)}/{ds.get('n_columns', 0)} cols",
        "cards": cards,
    }


def _fallback(digest):
    """Deterministic honest-degrade line — no AI, no fabrication: just the page shape + the first headline reading."""
    n = len(digest["cards"])
    head = next((r for c in digest["cards"] for r in c["readings"]), None)
    asset = digest.get("asset") or "the resolved asset"
    page = digest.get("page") or "this page"
    lead = f"{page} for {asset}: {n} card(s) rendered"
    return lead + (f", led by {head}." if head else ".")


def narrate(resp):
    """{"summary": str, "degraded": bool} for a finished /api/run response. AI-told, grounded, honest-degrade + cached.
    Wrapped in a layer3 obs stage span so it shows in the run trace like every other pipeline layer."""
    from obs.span import stage_span
    from obs.stage import stage
    run_id = resp.get("run_id") or "default"
    digest = _digest(resp)
    if not digest["cards"]:
        return {"summary": "", "degraded": True}
    key = hashlib.sha1(json.dumps(digest, sort_keys=True, default=str).encode("utf-8")).hexdigest()
    if key in _CACHE:
        return {"summary": _CACHE[key], "degraded": False}
    with stage_span("layer3_narrate", inputs={"cards": len(digest["cards"]), "asset": digest.get("asset")}) as sp:
        summary, degraded = _fallback(digest), True
        try:
            system = _load_prompt("system.md")
            user = "PAGE:\n" + json.dumps(digest, ensure_ascii=False, indent=1)
            out = call_qwen(system, user, stage="layer3_narrate", schema=_SCHEMA, on_error="empty") or {}
            text = (out.get("summary") or "").strip() if isinstance(out, dict) else ""
            if text:
                summary, degraded = text, False
        except Exception:
            pass                                   # honest-degrade to the deterministic fallback (never raises)
        sp.set_outputs(chars=len(summary), degraded=degraded)
        stage(run_id, "layer3", chars=len(summary), degraded=degraded, asset=digest.get("asset"))
        if not degraded and len(_CACHE) < _CACHE_MAX:
            _CACHE[key] = summary
        return {"summary": summary, "degraded": degraded}
