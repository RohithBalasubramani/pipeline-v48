"""fetch_entities — compose the full corpus of suggestion entities.

Flattens the v48 asset resolver + neuract metric field_keys + cmd_catalog cards/pages/
areas/questions/time-presets into one uniform entity list (assets, metrics, cards, pages,
areas, questions, time). Assets pass a pandas has-data filter and carry validated
(answerable) columns from the v48 validation layer; metrics carry card-usage salience.
"""
import json

import db
from config import CMD_DB, DATA_DB, MAP_SCHEMA, MAP_TABLE

from .assets import _v48_assets
from .metrics import _derive_metric_labels
from .naming import _infer_kind, _infer_unit, _tidy, _title
from .parsing import _QLEN, _recipe_metrics, _split_questions, _time_presets


def fetch_entities():
    ents = []
    card_metrics, metric_count = _recipe_metrics()

    # ---- ASSETS (from the v48 pipeline resolver — layer1b/resolve/asset_candidates.py) ----
    # The resolver is the authoritative source: meta_data_version1 device registry (app_devices ⋈
    # app_device_tables ⋈ app_gateways) joined to the LIVE neuract data tables. It returns the real
    # registered device name + class + gateway (GIC node). We display the name (trimming the redundant
    # 'GIC-NN-NN-' location prefix, kept in load_group), so the copilot's assets match the pipeline's.
    # Then a pandas-driven has-data filter drops assets whose neuract table is empty (never wired).
    import has_data
    import validated
    assets = _v48_assets()
    live = has_data.tables_with_data([a["table"] for a in assets])
    kept = [a for a in assets if a["table"] in live]
    print(f"  [assets] {len(kept)}/{len(assets)} have data in neuract "
          f"({len(assets) - len(kept)} empty tables dropped)")
    # per-asset ANSWERABLE metrics from the v48 validation layer (pass/warn columns). Fail-open: if
    # the validator/tunnel is unavailable, vmetrics is {} and the answerable-gate simply stays off.
    vmetrics = validated.validated_metrics([a["table"] for a in kept])
    if vmetrics:
        print(f"  [validate] answerable columns from the v48 validation layer for {len(vmetrics)} assets")
    for a in kept:
        name, tbl = a["name"], a["table"]
        lg, cls = a.get("load_group") or "", a.get("class") or ""
        display = _tidy(name)
        payload = {"table": tbl, "class": cls, "gateway": lg}
        if tbl in vmetrics:
            payload["metric_keys"] = vmetrics[tbl]   # validated (answerable) columns for this asset
        ents.append(dict(
            type="asset", canonical=tbl, display=display, unit="",
            class_scope=cls, area=lg, table_name=tbl, panel_id="",
            kind="", has_data=1, popularity=0,
            keywords=" ".join([display, name, tbl, cls, lg]),
            payload=json.dumps(payload),
            _src_name=name))

    # ---- METRICS (v48: distinct field_key in neuract.device_mappings) ----
    # Labels are AI-derived FROM the neuract field_key (no lt_panels_db / lt_parameter). Salience = card usage.
    field_keys = [r[0] for r in db.rows(DATA_DB,
                    f"SELECT DISTINCT field_key FROM {MAP_SCHEMA}.{MAP_TABLE} "
                    f"WHERE coalesce(field_key,'') <> '' ORDER BY field_key")]
    mlabels = _derive_metric_labels(field_keys)
    for col in field_keys:
        info = mlabels.get(col) or {}
        display = info.get("label") or _title(col)
        unit = info.get("unit") if info.get("unit") not in (None, "") else _infer_unit(col)
        ents.append(dict(
            type="metric", canonical=col, display=display, unit=unit,
            class_scope="", area="", table_name="", panel_id="",
            kind=_infer_kind(col), has_data=1, popularity=float(metric_count.get(col, 0)),
            keywords=" ".join([display, col]),
            payload=json.dumps({"on_card": metric_count.get(col, 0) > 0})))

    # NOTE: cmd_catalog.derived_metrics is intentionally NOT a metric source — those keys
    # (loadPct, vDev, efficiencyPct, alertsCritical, ...) are cmd_catalog-computed, not real
    # neuract columns. The metric universe is ONLY neuract.device_mappings field_keys, so every
    # suggested metric exists in the neuract DB.

    # ---- CARDS (cmd_catalog.cards) — full semantics ----
    seen_q = set()
    for (cid, title, page, role, question, answers, purpose, insight,
         decision, visualization, sem_purpose) in db.rows(CMD_DB, """
        SELECT id, title, coalesce(page,''), coalesce(analytical_role,''),
               coalesce(user_question,''), coalesce(sem_answers,''),
               coalesce(card_purpose,''), coalesce(output_insight,''),
               coalesce(decision_support,''), coalesce(visualization,''),
               coalesce(sem_purpose,'')
        FROM cards ORDER BY id;"""):
        cid = int(cid)
        mlist = card_metrics.get(cid, [])
        ents.append(dict(
            type="card", canonical=title, display=title, unit="",
            class_scope="", area=page, table_name="", panel_id="",
            kind=role, has_data=1, popularity=float(len(mlist)),
            keywords=" ".join([title, role, question, answers, purpose[:240],
                               insight[:160], decision[:160], visualization[:120],
                               sem_purpose[:160]]),
            payload=json.dumps({"card_id": cid, "question": question, "role": role,
                                "insight": insight[:200], "decision": decision[:200],
                                "metrics": [m["label"] for m in mlist][:10]})))
        # exemplar QUESTIONS from this card
        qsources = [question] + _split_questions(answers)
        for q in qsources:
            q = q.strip()
            qn = q.lower()
            if _QLEN[0] <= len(q) <= _QLEN[1] and qn not in seen_q:
                seen_q.add(qn)
                ents.append(dict(
                    type="question", canonical=q, display=q, unit="",
                    class_scope="", area=page, table_name="", panel_id="",
                    kind=role, has_data=1, popularity=1.0,
                    keywords=q,
                    payload=json.dumps({"card_id": cid, "page": page})))

    # ---- PAGES / TEMPLATES (cmd_catalog.page_specs) — full semantics ----
    for (pkey, title, arch, theme, story, flow, obj, answers, concepts) in db.rows(CMD_DB, """
        SELECT page_key, coalesce(title,''), coalesce(archetype,''),
               coalesce(analytical_theme,''), coalesce(story_structure,''),
               coalesce(narrative_flow,''), coalesce(reusable_business_objective,''),
               coalesce(reusable_answers,''), coalesce(reusable_concepts,'')
        FROM page_specs ORDER BY id;"""):
        ents.append(dict(
            type="page", canonical=pkey, display=title or pkey, unit="",
            class_scope="", area=arch, table_name="", panel_id="",
            kind=arch, has_data=1, popularity=0,
            keywords=" ".join([title, arch, theme[:240], obj[:160],
                               concepts[:160], story[:120], flow[:120]]),
            payload=json.dumps({"archetype": arch, "objective": obj[:200]})))
        # exemplar QUESTIONS from the page's reusable answers
        for q in _split_questions(answers):
            qn = q.lower()
            if qn not in seen_q:
                seen_q.add(qn)
                ents.append(dict(
                    type="question", canonical=q, display=q, unit="",
                    class_scope="", area=arch, table_name="", panel_id="",
                    kind=arch, has_data=1, popularity=0.8, keywords=q,
                    payload=json.dumps({"page": pkey})))

    # ---- AREAS (cmd_catalog.pages) ----
    for _id, area in db.rows(CMD_DB, "SELECT id, area FROM pages ORDER BY id;"):
        ents.append(dict(
            type="area", canonical=area, display=area, unit="", class_scope="",
            area=area, table_name="", panel_id="", kind="", has_data=1,
            popularity=0, keywords=area, payload=json.dumps({})))

    # ---- TIME PRESETS (real options from card_controls) ----
    for lab in _time_presets():
        ents.append(dict(
            type="time", canonical=lab, display=lab, unit="", class_scope="",
            area="", table_name="", panel_id="", kind="", has_data=1,
            popularity=0, keywords=lab, payload=json.dumps({})))

    return ents
