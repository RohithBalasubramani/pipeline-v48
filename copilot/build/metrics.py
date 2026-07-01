"""AI-derived human labels + units for neuract metric field_keys.

No lt_panels_db, no hardcoded map: the 4B model labels each snake_case metric key
(expanding abbreviations, dropping the unit token, inferring the unit). Per-key fallback
is the deterministic title-case + suffix-inferred unit from naming.py when the model
endpoint is down.
"""
import json

from .naming import _infer_unit, _title


def _derive_metric_labels(field_keys, batch=40):
    """AI-derive a clean human label + unit per neuract metric field_key — no lt_panels_db,
    no hardcoded map. Fallback per key: title-case + suffix-inferred unit."""
    out = {k: {"label": _title(k), "unit": _infer_unit(k)} for k in field_keys}
    try:
        import llm
        if not llm.is_up():
            return out
        sys = ("You label EMS (energy/building) metric columns. For each snake_case metric key, return a "
               "short human LABEL (proper casing; expand abbreviations: thd->THD, avg->Average, "
               "pf->Power Factor, temp->Temperature, freq->Frequency; DROP the trailing unit token from "
               "the label) and its UNIT inferred from the key (_kw->kW, _kva->kVA, _kvar->kVAr, _kwh->kWh, "
               "_hz->Hz, _pct->%, voltage*->V, current*->A, *_c->°C, _rpm->rpm; \"\" if none). "
               'Return STRICT JSON: {"<key>":{"label":"..","unit":".."}}. No prose.')
        for i in range(0, len(field_keys), batch):
            chunk = field_keys[i:i + batch]
            try:
                txt = llm.chat([{"role": "system", "content": sys},
                                {"role": "user", "content": "KEYS:\n" + "\n".join(chunk)}],
                               temperature=0.2, timeout=40, response_format={"type": "json_object"})
                obj = json.loads(txt)
                for k in chunk:
                    v = obj.get(k)
                    if isinstance(v, dict) and str(v.get("label") or "").strip():
                        out[k] = {"label": str(v["label"]).strip(),
                                  "unit": str(v.get("unit") or "").strip()}
            except Exception:
                continue
    except Exception:
        pass
    return out
