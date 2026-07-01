"""Tier-0 retrieval — instant, no LLM, no network.

Loads the small SQLite corpus into memory once and ranks EMS entities against the
user's partial text (prefix / word-start / substring / alias / fuzzy / topic), then
synthesises deterministic suggestions grounded in real assets, salient metrics, real
time presets and the EMS's own exemplar questions. This is both the always-on
baseline AND the grounding set handed to the model in Tier-1.
"""
import difflib
import json
import math
import re
import sqlite3
from collections import defaultdict

from config import INDEX_PATH, RETRIEVE_PER_TYPE

INTENT_VERBS = {"show", "compare", "trend", "trends", "list", "monitor", "analyze",
                "analyse", "plot", "view", "display", "track", "get", "see"}
STOP = {"the", "a", "an", "of", "for", "on", "in", "and", "to", "me", "my", "this",
        "all", "across", "between", "over", "vs", "versus", "right", "now"} | INTENT_VERBS

TYPE_PRIOR = {"asset": 1.0, "metric": 1.0, "time": 0.8, "area": 0.7,
              "card": 0.85, "question": 0.95, "page": 0.8}


def _tokenize(s):
    return re.findall(r"[a-z0-9]+", s.lower())


class Index:
    def __init__(self, path=INDEX_PATH):
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        self.ents = []
        for r in conn.execute("SELECT * FROM entities"):
            e = dict(r)
            e["payload"] = json.loads(e["payload"]) if e["payload"] else {}
            e["_kw"] = e["keywords"].lower() if e["keywords"] else ""
            e["_surf"] = {e["display"].lower(), e["canonical"].lower()}
            self.ents.append(e)
        self.by_id = {e["id"]: e for e in self.ents}
        self.alias_by_id = defaultdict(set)
        for eid, alias in conn.execute("SELECT entity_id, alias FROM aliases"):
            self.alias_by_id[eid].add(alias.lower())
        for e in self.ents:
            e["_surf"] |= self.alias_by_id.get(e["id"], set())
        self.by_type = defaultdict(list)
        for e in self.ents:
            self.by_type[e["type"]].append(e)
        conn.close()

    # ---- scoring ----
    def _surface_score(self, tok, e):
        best = 0.0
        for s in e["_surf"]:
            if not s:
                continue
            if s == tok:
                best = max(best, 4.0)
            elif s.startswith(tok):
                best = max(best, 3.0)
            elif any(w.startswith(tok) for w in s.split()):
                best = max(best, 2.4)
            elif tok in s:
                best = max(best, 1.7)
        if best < 2.4 and len(tok) >= 4:  # fuzzy only for longer tokens
            for s in e["_surf"]:
                if abs(len(s) - len(tok)) <= 4:
                    r = difflib.SequenceMatcher(None, tok, s).ratio()
                    if r >= 0.8:
                        best = max(best, r * 2.2)
        return best

    def _pop_boost(self, e):
        return 1.0 + min(e["popularity"], 30) * 0.03  # salient metrics/cards rank up

    def best_surface(self, types, tok):
        if not tok:
            return 0.0
        return max((self._surface_score(tok, e) for t in types
                    for e in self.by_type.get(t, [])), default=0.0)

    def salient_metrics(self, focus_class=None, n=8, allowed=None):
        """Top metrics by semantic salience (how many cards render them), preferring the focused
        asset class. `allowed` (validated field_keys for the in-context asset, from the v48 validation
        layer) restricts to metrics that actually fill for that asset — so every suggestion is
        answerable. When restricted we don't require popularity>0 (the asset's validated columns win)."""
        if allowed:
            cand = [e for e in self.by_type["metric"] if e["canonical"] in allowed]
        else:
            cand = [e for e in self.by_type["metric"] if e["popularity"] > 0]
        def key(e):
            inclass = 1 if (focus_class and e["class_scope"] and focus_class in e["class_scope"]) else 0
            return (inclass, e["popularity"])
        cand.sort(key=key, reverse=True)
        return cand[:n]

    def rank_assets(self, tokens, limit=12):
        """Rank assets by ALL query tokens, each weighted by rarity (IDF over the asset corpus) so a
        distinctive term (e.g. 'pcc' -> the PCC-* assets) dominates a common fragment (e.g. 'pane'
        matching many '...Panel...' assets). Fixes 'whats the current usage in pcc pane' surfacing
        random Panel-class assets instead of the PCC ones."""
        toks = [t for t in tokens if len(t) >= 2]
        assets = self.by_type.get("asset", [])
        if not toks or not assets:
            return assets[:limit] if not toks else []
        n = len(assets)
        df = {}
        for t in toks:
            df[t] = sum(1 for e in assets
                        if self._surface_score(t, e) >= 2.0 or (e["_kw"] and t in e["_kw"]))
        idf = {t: math.log((n + 1) / (df[t] + 1)) + 0.4 for t in toks}
        out = []
        for e in assets:
            s = 0.0
            for t in toks:
                mq = self._surface_score(t, e)
                if mq <= 0 and e["_kw"] and t in e["_kw"]:
                    mq = 1.2
                if mq > 0:
                    s += mq * idf[t]
            if s > 0:
                out.append((s * self._pop_boost(e), e))
        out.sort(key=lambda x: -x[0])
        return [e for _, e in out[:limit]]

    def rank(self, types, tok, context_tokens, focus_class=None, limit=8, allowed=None):
        out = []
        for e in (x for t in types for x in self.by_type.get(t, [])):
            if allowed and e["type"] == "metric" and e["canonical"] not in allowed:
                continue  # metric not validated (answerable) for the in-context asset
            score = self._surface_score(tok, e) if tok else 0.0
            # topic match: how many context tokens appear in the entity's keywords
            if context_tokens and e["_kw"]:
                hits = sum(1 for c in context_tokens if len(c) >= 3 and c in e["_kw"])
                if hits:
                    score += hits * (1.4 if e["type"] in ("question", "card", "page") else 0.6)
            if score <= 0:
                continue
            if focus_class and e["type"] == "metric" and e["class_scope"] \
                    and focus_class not in e["class_scope"]:
                score *= 0.7  # mild penalty for out-of-class metrics
            out.append((score * TYPE_PRIOR.get(e["type"], 0.6) * self._pop_boost(e), e))
        out.sort(key=lambda x: -x[0])
        return [e for _, e in out[:limit]]


_INDEX = None


def index():
    global _INDEX
    if _INDEX is None:
        _INDEX = Index()
    return _INDEX


def _compact(e):
    return {"type": e["type"], "display": e["display"], "canonical": e["canonical"],
            "unit": e["unit"], "class": e["class_scope"], "area": e["area"],
            "payload": e["payload"]}


def retrieve(text):
    ix = index()
    raw = text or ""
    low = raw.lower()
    toks = _tokenize(raw)
    ends_space = raw.endswith((" ", "\t"))
    partial = "" if (ends_space or not toks) else toks[-1]
    context_tokens = [t for t in toks if t not in STOP and t != partial]
    intent = toks[0] if toks and toks[0] in INTENT_VERBS else ("compare" if "compare" in toks else "show")

    assets = ix.rank_assets(([partial] if partial else []) + context_tokens,
                            limit=RETRIEVE_PER_TYPE["asset"])
    # assets already mentioned in the text (context for compare / class filter)
    mentioned = [e for e in ix.by_type["asset"]
                 if len(e["display"]) >= 3 and e["display"].lower() in low]
    focus_class = None
    pool = (mentioned or assets)
    if pool:
        classes = [e["class_scope"] for e in pool if e["class_scope"]]
        if classes:
            focus_class = max(set(classes), key=classes.count)

    # ANSWERABLE-METRIC GATE: restrict metric grounding to columns the v48 validation layer marked
    # answerable (pass/warn) for the in-context asset(s) — mentioned by name, else the top matched.
    # So the copilot only pairs an asset with a metric the data layer can actually fill. (Inactive
    # until the index is built with validated metric_keys — fail-open to global metrics.)
    pool_assets = mentioned or assets[:4]
    allowed = set()
    for e in pool_assets:
        allowed |= set((e.get("payload") or {}).get("metric_keys", []))
    allowed = allowed or None

    # Does the active word name an asset or a metric? If it's an asset (or no metric
    # typed yet), ground on the class's *salient* metrics rather than prefix-matching
    # that same word against metric names (so "show trans" -> transformer metrics,
    # not "transfer events").
    asset_ps = ix.best_surface(["asset"], partial)
    metric_ps = ix.best_surface(["metric"], partial)
    if partial and metric_ps >= 2.4 and metric_ps > asset_ps:
        metrics = ix.rank(["metric"], partial, context_tokens, focus_class,
                          RETRIEVE_PER_TYPE["metric"], allowed=allowed)
    else:
        metrics = ix.salient_metrics(focus_class, RETRIEVE_PER_TYPE["metric"], allowed=allowed)
        if context_tokens:
            topic = ix.rank(["metric"], "", context_tokens, focus_class, 4, allowed=allowed)
            seen = {m["id"] for m in topic}
            metrics = (topic + [m for m in metrics if m["id"] not in seen])[:RETRIEVE_PER_TYPE["metric"]]
    times = ix.rank(["time"], partial, [], limit=6) or ix.by_type["time"][:6]
    areas = ix.rank(["area"], partial, context_tokens, limit=RETRIEVE_PER_TYPE["area"])
    cards = ix.rank(["card"], partial, context_tokens, limit=RETRIEVE_PER_TYPE["card"])
    pages = ix.rank(["page"], partial, context_tokens, limit=RETRIEVE_PER_TYPE["page"])
    questions = ix.rank(["question"], partial, context_tokens, limit=6)

    return {"text": raw, "partial": partial, "intent": intent, "focus_class": focus_class,
            "context_tokens": context_tokens,
            "mentioned_assets": [_compact(e) for e in mentioned[:3]],
            "assets": [_compact(e) for e in assets],
            "metrics": [_compact(e) for e in metrics],
            "times": [_compact(e) for e in times],
            "areas": [_compact(e) for e in areas],
            "cards": [_compact(e) for e in cards],
            "pages": [_compact(e) for e in pages],
            "questions": [_compact(e) for e in questions]}


if __name__ == "__main__":
    import sys
    txt = sys.argv[1] if len(sys.argv) > 1 else "show trans"
    r = retrieve(txt)
    print("partial:", repr(r["partial"]), "| intent:", r["intent"], "| focus_class:", r["focus_class"])
    print("assets   :", [a["display"] for a in r["assets"][:6]])
    print("metrics  :", [m["display"] for m in r["metrics"][:6]])
    print("times    :", [t["display"] for t in r["times"]])
    print("questions:", [q["display"][:70] for q in r["questions"][:4]])
