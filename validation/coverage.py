"""validation/coverage.py — the ACHIEVED-vs-UNIVERSE coverage matrix. WHY: a 95%-pass sweep means nothing if it only
ever exercised 4 pages and 12 cards — pass-rate measures correctness of what ran, coverage measures how much of the
cmd_catalog universe (pages, cards, asset classes, assets, workflow categories) the session actually touched. This
module reads every per-case record a runner session left on disk (sessions/<sid>/cases/*.json), extracts every
coverage dimension the pipeline can express (page families/tabs, rendered card ids, handling kinds, verdicts,
degradation whys, failure stages), compares against corpus.universe + templates.CATEGORIES, and reports the UNCOVERED
paths — the to-do list for the next corpus generation. Degrades honestly: a missing session, unreadable case file, or
unreachable cmd_catalog yields partial-but-truthful output, never a raise."""
from __future__ import annotations

import json
import os

from validation import config
from validation.response import ascii_safe


def _sort_key(v):
    """Stable ordering over possibly-mixed int/str id sets (ints first numerically, then strings lexically)."""
    return (isinstance(v, str), v)


def _pct(achieved: int, total: int) -> float:
    return round(100.0 * achieved / total, 1) if total else 0.0


def _load_records(sdir: str) -> list[dict]:
    cases_dir = os.path.join(sdir, "cases")
    recs = []
    try:
        names = sorted(os.listdir(cases_dir))
    except OSError:
        return recs
    for fn in names:
        if not fn.endswith(".json"):
            continue
        try:
            with open(os.path.join(cases_dir, fn)) as f:
                recs.append(json.load(f))
        except (OSError, ValueError):
            continue                                  # one corrupt record must not sink the analysis
    return recs


def _universe_or_empty() -> dict:
    """cmd_catalog may be unreachable (the :5433 tunnel) — coverage still reports the achieved side."""
    try:
        from validation.corpus.universe import universe
        return universe()
    except Exception:
        return {"assets": [], "by_class": {}, "pages": [], "cards": [], "card_handling": {},
                "unique_names": [], "homonym_tokens": [], "panel_aliases": []}


def analyze(session_id: str) -> dict:
    """Read every case record of sessions/<session_id>, compute achieved coverage vs the universe, write
    sessions/<sid>/coverage.json, and return the report dict. Never raises on bad/missing data."""
    sdir = config.session_dir(session_id)
    recs = _load_records(sdir)

    pages, families, tabs = set(), set(), set()
    card_ids, classes, assets, categories, outcomes = set(), set(), set(), set(), set()
    handling_kinds, verdict_kinds, degraded_whys, error_stages = set(), set(), set(), set()

    u = _universe_or_empty()
    handling = u.get("card_handling") or {}

    for rec in recs:
        case = rec.get("case") or {}
        meta = case.get("meta") or {}
        if case.get("category"):
            categories.add(ascii_safe(case["category"]))
        if meta.get("cls"):
            classes.add(ascii_safe(meta["cls"]))
        if meta.get("asset"):
            assets.add(ascii_safe(meta["asset"]))
        for a in (meta.get("assets") or []):
            assets.add(ascii_safe(a))

        judgment = rec.get("judgment") or {}
        if judgment.get("degraded") and judgment.get("why"):
            degraded_whys.add(ascii_safe(judgment["why"])[:200])
        if not judgment.get("pass") and judgment.get("stage"):
            error_stages.add(ascii_safe(judgment["stage"]))

        parsed = rec.get("parsed")
        if not isinstance(parsed, dict):
            continue
        outcomes.add(ascii_safe(parsed.get("outcome") or "none"))
        pk = parsed.get("page_key")
        if pk:
            pk = ascii_safe(pk)
            pages.add(pk)
            parts = pk.split("/")
            families.add(parts[0])
            if len(parts) > 1 and parts[1]:
                tabs.add(parts[1])
        for v in (parsed.get("verdicts") or {}):
            verdict_kinds.add(ascii_safe(v))
        for cr in (parsed.get("cards") or []):
            if not isinstance(cr, dict):
                continue
            for key in ("card_id", "render_card_id"):
                cid = cr.get(key)
                if cid is None:
                    continue
                try:
                    cid = int(cid)
                except (TypeError, ValueError):
                    cid = ascii_safe(cid)
                card_ids.add(cid)
                hk = handling.get(cid)
                if hk:
                    handling_kinds.add(ascii_safe(hk))
            if cr.get("verdict"):
                verdict_kinds.add(ascii_safe(cr["verdict"]))

    # --- universe side ---
    from validation.corpus.templates import CATEGORIES
    u_pages = sorted({ascii_safe(p) for p in (u.get("pages") or []) if p})
    u_cards = sorted({c for c in (u.get("cards") or [])}, key=_sort_key)
    u_classes = sorted(ascii_safe(k) for k in (u.get("by_class") or {}))
    u_categories = sorted(CATEGORIES)
    n_u_assets = len(u.get("assets") or [])

    achieved = {
        "n_cases": len(recs),
        "pages": sorted(pages), "n_pages": len(pages),
        "families": sorted(families), "n_families": len(families),
        "tabs": sorted(tabs), "n_tabs": len(tabs),
        "cards": sorted(card_ids, key=_sort_key), "n_cards": len(card_ids),
        "classes": sorted(classes), "n_classes": len(classes),
        "assets": sorted(assets), "n_assets": len(assets),
        "categories": sorted(categories), "n_categories": len(categories),
        "outcomes": sorted(outcomes),
        "handling_kinds": sorted(handling_kinds),
        "verdict_kinds": sorted(verdict_kinds),
        "degradation_paths": sorted(degraded_whys),
        "error_stages": sorted(error_stages),
    }
    universe_counts = {
        "n_pages": len(u_pages), "n_cards": len(u_cards), "n_classes": len(u_classes),
        "n_assets": n_u_assets, "n_categories": len(u_categories),
    }
    report = {
        "session": session_id,
        "achieved": achieved,
        "universe": universe_counts,
        "pct": {
            "pages": _pct(len(pages & set(u_pages)), len(u_pages)),
            "cards": _pct(len(card_ids & set(u_cards)), len(u_cards)),
            "classes": _pct(len(classes & set(u_classes)), len(u_classes)),
            "categories": _pct(len(categories & set(u_categories)), len(u_categories)),
        },
        "uncovered": {
            "pages": sorted(set(u_pages) - pages),
            "cards": sorted(set(u_cards) - card_ids, key=_sort_key),
            "classes": sorted(set(u_classes) - classes),
            "categories": sorted(set(u_categories) - categories),
        },
    }
    try:
        with open(os.path.join(sdir, "coverage.json"), "w") as f:
            json.dump(report, f, indent=1, sort_keys=True)
    except OSError:
        pass                                           # report is still returned; disk failure is not analysis failure
    return report
