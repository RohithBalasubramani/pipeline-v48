"""cmd_catalog semantic extraction: exemplar questions, recipe metrics, time presets.

The EMS cards/pages already encode what a meaningful query is, so this module mines that
semantics from cmd_catalog (@ CMD_DB): split sem_answers/reusable_answers blobs into
first-class exemplar questions, parse card_data_recipe.fields into the REAL metrics each
card renders (salience = card usage), and pull REAL time presets from card_controls.
"""
import json
import re

import db
from config import CMD_DB

_TEXTY = {"text"}            # card_data_recipe field kinds that are not real metrics
_QLEN = (10, 170)           # exemplar question length bounds


def _j(s):
    try:
        return json.loads(s) if s else None
    except Exception:
        return None


def _split_questions(text):
    """Split a sem_answers / reusable_answers blob into individual questions."""
    if not text:
        return []
    parts = re.split(r"\(\d+\)|•|\n|(?<=\?)\s+", text)
    out = []
    for p in parts:
        q = p.strip(" -·\t")
        if not q:
            continue
        if not q.endswith("?") and "?" in q:
            q = q[: q.rindex("?") + 1].strip()
        if _QLEN[0] <= len(q) <= _QLEN[1]:
            out.append(q)
    return out


def _recipe_metrics():
    """Parse card_data_recipe.fields -> (card_metrics, metric_card_count).

    card_metrics:      {card_id: [{label, metric, unit}]}  (real raw/derived fields only)
    metric_card_count: {metric_key_or_column: n cards that render it}  (= semantic salience)
    """
    card_metrics, count = {}, {}
    for cid, fields in db.rows(CMD_DB,
            "SELECT card_id, fields FROM card_data_recipe WHERE jsonb_typeof(fields)='array';"):
        arr = _j(fields) or []
        mlist = []
        for f in arr:
            if not isinstance(f, dict):
                continue
            m, kind = f.get("metric"), f.get("kind")
            if not m or kind in _TEXTY:
                continue
            mlist.append({"label": f.get("label") or m, "metric": m, "unit": f.get("unit", "")})
            count[m] = count.get(m, 0) + 1
        if mlist:
            card_metrics[int(cid)] = mlist
    return card_metrics, count


def _time_presets():
    """Distinct (window, label) time presets from card_controls.time_options."""
    seen, out = set(), []
    for (label,) in db.rows(CMD_DB,
            "SELECT DISTINCT jsonb_array_elements(time_options)->>'label' "
            "FROM card_controls WHERE jsonb_typeof(time_options)='array';"):
        lab = (label or "").strip()
        key = lab.lower()
        if lab and key not in seen and not lab.lower().startswith("custom"):
            seen.add(key)
            out.append(lab)
    return out
