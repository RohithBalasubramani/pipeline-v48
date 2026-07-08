"""tests/test_presentation_chrome_kept.py — presentation-DIMENSIONAL numeric leaves are CHROME, not DATA.

B6 fix (run r_5c6797f815). leaf_classify is TYPE-ONLY: any number is DATA unless its key is a
vocab.chrome_subtree_keys member (whole-object exempt) or a vocab.element_chrome_keys member (per-leaf exempt).
Table layout (rowHeight/headerHeight/maxRowHeight), column fit bounds (fitMin/fitMax), table minWidth/
singleModeMinWidth, rail railDecimals, line/stack dimOpacity and the colour palette are pure presentation geometry —
never a measurement. Before the fix they were data-classified, so strip_to_placeholders zeroed rowHeight:20->0.0
(unfillable -> unbound_by_emit null at exec, collapsing the table). The fix adds them to the two vocab rows
(db/seed_vocab.sql element_chrome_keys + db/fix_ieee_limit_chrome_subtree.sql chrome_subtree_keys).

Pure unit test: the two classifier accessors are monkeypatched to the FIXED vocab so the test is DB-free and locks the
classification LOGIC (given the vocab, these keys are chrome and a genuine measurement is still data)."""
from __future__ import annotations

import validate.leaf_classify as lc
from validate.leaf_classify import classify

# the object-subtree exemptions (whole subtree kept) and the per-element numeric exemptions (single leaf kept),
# mirroring the two seeded vocab rows after the B6 fix (only the members this test exercises).
_SUBTREE = {"bandthresholds", "layout", "fit", "palette", "dimopacity"}
_ELEMENT = {"decimals", "width", "warn", "trip",
            "rowheight", "headerheight", "maxrowheight", "fitmin", "fitmax",
            "minwidth", "singlemodeminwidth", "raildecimals"}


def _patch(monkeypatch):
    monkeypatch.setattr(lc, "_chrome_subtree_keys", lambda: _SUBTREE)
    monkeypatch.setattr(lc, "_chrome_element_keys", lambda: _ELEMENT)


def test_presentation_dimensional_leaves_are_chrome_not_data(monkeypatch):
    _patch(monkeypatch)
    p = {
        "table": {
            "pres": {
                "layout": {"rowHeight": 20, "headerHeight": 28, "maxRowHeight": 28},
                "minWidth": 1240, "singleModeMinWidth": 900,
                "columns": [{"key": "voltage", "fit": {"fit": True, "fitMax": 280, "fitMin": 120}}],
                "palette": {"rowHoverBg": "#fefefb", "rowSelectedBg": "#f5e6c8"},
            },
        },
        "trend": {"pres": {"dimOpacity": {"line": 0.4, "stack": 0.35}, "railDecimals": 0}},
        "strip": {"stats": {"total": 2780}},                       # a GENUINE measurement (must stay DATA)
    }
    data_paths = {d["path"] for d in classify(p)["data_leaves"]}

    # every presentation-dimensional numeric leaf is EXCLUDED from data (kept byte-identical by the strip)
    for pres_path in (
        "table.pres.layout.rowHeight", "table.pres.layout.headerHeight", "table.pres.layout.maxRowHeight",
        "table.pres.minWidth", "table.pres.singleModeMinWidth",
        "table.pres.columns[0].fit.fitMax", "table.pres.columns[0].fit.fitMin",
        "trend.pres.dimOpacity.line", "trend.pres.dimOpacity.stack", "trend.pres.railDecimals",
    ):
        assert pres_path not in data_paths, f"{pres_path} wrongly data-classified (would zero to 0.0)"

    # the fix does NOT over-exempt: a real measured value is still DATA and will honest-strip to 0.
    assert "strip.stats.total" in data_paths


def test_layout_and_fit_and_dimopacity_are_metadata_by_count(monkeypatch):
    _patch(monkeypatch)
    # a payload whose ONLY numbers are presentation-dimensional chrome has ZERO data leaves.
    p = {"pres": {"layout": {"rowHeight": 20}, "columns": [{"fit": {"fitMin": 120, "fitMax": 280}}],
                  "dimOpacity": {"line": 0.4}, "minWidth": 1240, "railDecimals": 1}}
    out = classify(p)
    assert out["data_leaves"] == []
    assert out["demand"] == {"scalars": 0, "arrays": 0, "series": 0}
