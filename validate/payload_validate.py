"""validate/payload_validate.py — can the validated columns fill each card payload's DATA leaves? (non-AI, coarse). [validate]"""
from config.validation import PHASE_SUFFIXES
from validate.leaf_classify import classify


def _supply(data_report):
    """Aggregate the validated columns into fill capacity. Only pass/warn columns count as usable."""
    usable = [c for c in data_report["columns"] if c["verdict"] in ("pass", "warn")]
    numeric_ok = [c for c in usable if c["numeric"]]
    phase_cols = [c for c in numeric_ok if any(c["column"].lower().endswith(s) for s in PHASE_SUFFIXES)]
    series_ok = [c for c in numeric_ok if c["series_capable"]]
    return {"numeric_ok": len(numeric_ok), "phase_cols": len(phase_cols),
            "has_timeseries": len(series_ok) > 0, "series_cols": len(series_ok)}


def validate_one(payload, supply):
    """Coarse feasibility for one payload: counts of supply vs demand categories (NOT semantic binding)."""
    cls = classify(payload)
    demand = cls["demand"]
    reasons, verdict = [], "pass"
    if demand["scalars"] and supply["numeric_ok"] == 0:
        verdict = "fail"; reasons.append("payload needs numeric values but no usable numeric column")
    if demand["series"] and not supply["has_timeseries"]:
        verdict = "fail"; reasons.append("payload needs a time-series but no series-capable column")
    if demand["arrays"]:
        # small arrays often per-phase; need either enough numeric columns or phase columns
        if supply["numeric_ok"] == 0:
            verdict = "fail"; reasons.append("payload needs array values but no usable numeric column")
        elif supply["phase_cols"] == 0 and supply["numeric_ok"] < 3:
            verdict = "warn" if verdict == "pass" else verdict
            reasons.append("array leaves present; thin numeric/phase supply (Layer 2 must bind carefully)")
    total_data = demand["scalars"] + demand["arrays"] + demand["series"]
    if total_data == 0:
        verdict = "warn" if verdict == "pass" else verdict
        reasons.append("no DATA leaves found (pure-metadata payload?)")
    return {"demand": demand, "data_leaves": total_data, "metadata_leaves": cls["metadata_leaves"],
            "verdict": verdict, "reasons": reasons}


def validate_payloads(selected_cards, lookup, data_report):
    """selected_cards: 1a cards [{card_id,title,...}]. lookup: card_id,page_key -> [story dicts].
    Returns {cards:[...], summary}."""
    supply = _supply(data_report)
    cards = []
    for c in selected_cards:
        cid = c.get("card_id")
        stories = lookup(cid) if cid is not None else []
        if not stories:
            cards.append({"card_id": cid, "title": c.get("title"), "stories": [],
                          "verdict": "warn", "reasons": ["no default payload in card_payloads for this card+page"]})
            continue
        srep = []
        for s in stories:
            r = validate_one(s["payload"], supply)
            srep.append({"story_id": s["story_id"], "story_name": s["story_name"],
                         "variant": s.get("variant"), **r})
        worst = "pass"
        for s in srep:
            if s["verdict"] == "fail": worst = "fail"; break
            if s["verdict"] == "warn": worst = "warn"
        cards.append({"card_id": cid, "title": c.get("title"), "stories": srep, "verdict": worst,
                      "reasons": []})
    summary = {"supply": supply, "n_cards": len(cards),
               "n_pass": sum(1 for x in cards if x["verdict"] == "pass"),
               "n_warn": sum(1 for x in cards if x["verdict"] == "warn"),
               "n_fail": sum(1 for x in cards if x["verdict"] == "fail")}
    return {"cards": cards, "summary": summary}
