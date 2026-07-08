"""Regression pin for card 25 (pg04 Harmonics & PQ, cert_04) narrative FABRICATION.

The AI-summary was FED a story worst_feeder current_thd_pct that came from the PEAK phase of the LATEST live snapshot
(_phase_max over thd_current_r/y/b of ONE instant), so a feeder whose REAL neuract I-THD (avg over thd_current_r/y/b
across the WINDOW) is ~6.8% (below the 8.0 IEEE-519 limit) was handed to the narrator as 8.7% — which then wrote
"current THD of 8.7%, exceeding the 8.0% limit". The narrative wasn't hallucinating; it was fed a wrong/fabricated
number by the story builder.

FIX: harmonics_pq now computes each feeder's THD as the window-AVERAGE of its per-phase thd_*_r/y/b_pct columns (the
canonical neuract THD, via data.neuract.series), so the story can ONLY ever cite a real THD — and only imply a breach
when the real avg actually exceeds the limit. A feeder with no phase-THD logged over the window is OMITTED, never
invented. These pins patch data.neuract.series so they run offline (no live DB) yet exercise the real code path.
"""
from __future__ import annotations

from ems_exec.renderers._story import harmonics_pq as H
from ems_exec.renderers._story import _facts


def _members(name="GIC-01-N3-UPS-01", table="gic_01_n3_ups_01_p1"):
    return ([{"mfm_id": 999, "name": name, "table": table, "reporting": True}],
            {"orphaned": False, "reporting_count": 1, "expected_count": 1})


def _series_for(i_phases, v_phases=None):
    """A fake data.neuract.series that returns one bucket carrying the given per-phase THD values."""
    def _series(table, cols, start, end, sampling="hourly"):
        row = {"ts": 0}
        if cols == H._I_COLS:
            for c, v in zip(H._I_COLS, i_phases):
                row[c] = v
        elif cols == H._V_COLS:
            for c, v in zip(H._V_COLS, (v_phases or [None, None, None])):
                row[c] = v
        # drop the fully-None bucket (mirrors the real series contract)
        if all(row.get(c) is None for c in cols):
            return []
        return [row]
    return _series


def _build(monkeypatch, i_phases, v_phases=None, name="GIC-01-N3-UPS-01", table="gic_01_n3_ups_01_p1"):
    monkeypatch.setattr(H._nx, "series", _series_for(i_phases, v_phases))
    monkeypatch.setattr(_facts, "_name_for", lambda mid: name)
    monkeypatch.setattr(H._facts, "_name_for", lambda mid: name)
    ctx = {"mfm_id": 999, "asset_table": table, "window": (None, None)}
    return H.build(None, None, ctx, _members(name, table))


# ── the defect: a real-6.8% feeder must NOT be reported as an 8.7% breach ────────────────────────
def test_below_limit_feeder_reports_real_avg_thd_no_false_breach(monkeypatch):
    # phases whose AVG is 6.8 (below the 8.0 I-limit) but whose PEAK is 11.1 (the old _phase_max would have surfaced
    # the peak of the latest instant → a fabricated over-limit number).
    story, fb, badge = _build(monkeypatch, i_phases=[11.1, 8.5, 0.8])   # avg = 6.8
    wf = story["worst_feeder"]
    assert wf["current_thd_pct"] == 6.8                                 # the REAL window-avg, not the 11.1 peak phase
    assert story["limits"]["current_thd_pct"] == 8.0                    # IEEE-519 code-default limit surfaced
    # the story can only ever cite the real avg; it never carries an over-limit number for a below-limit feeder
    assert wf["current_thd_pct"] < story["limits"]["current_thd_pct"]
    # the deterministic fallback (the verbatim floor the narrator gets) cites the real 6.8%, never a breach
    assert "6.8%" in fb["text"]
    assert "exceed" not in fb["text"].lower() and "limit" not in fb["text"].lower()


# ── a feeder whose real avg THD DOES exceed 8.0 still surfaces the real over-limit value ──────────
def test_above_limit_feeder_surfaces_real_over_limit_thd(monkeypatch):
    story, fb, badge = _build(monkeypatch, i_phases=[95.0, 94.0, 95.2],  # avg ≈ 94.7 — a genuine gross breach
                              name="PCW-PANEL", table="gic_10_n10_pcw_panel_p1")
    wf = story["worst_feeder"]
    assert wf["current_thd_pct"] == round((95.0 + 94.0 + 95.2) / 3.0, 2)  # the REAL avg (~94.73)
    assert wf["current_thd_pct"] > story["limits"]["current_thd_pct"]      # genuinely over the 8.0 limit
    assert "94.7%" in fb["text"]                                           # the real over-limit value is narratable


# ── honest-degrade: a feeder with no phase-THD logged is OMITTED, never invented ──────────────────
def test_no_thd_logged_is_no_data_never_fabricated(monkeypatch):
    story, fb, badge = _build(monkeypatch, i_phases=[None, None, None], v_phases=[None, None, None])
    assert story.get("status") == "no_harmonics_data"                     # omitted → the no-data story
    assert badge == "accounting"
    assert "unavailable" in fb["text"].lower()                            # says so, never a fabricated %
