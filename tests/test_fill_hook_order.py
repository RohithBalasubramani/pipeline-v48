"""fill() ORCHESTRATION — every post-fill hook FIRES, in the documented pass order.

Each hook call in ems_exec/executor/fill.py is guarded by `try/except Exception: pass`, so a wiring regression (a
renamed module, a signature drift) silently no-ops while the per-module unit tests keep passing. This tiny unit runs
fill() ONCE with every hook recorded and asserts the design-comment order:

  roster.prepare_ctx → field loop → restore-array-containers → placeholder-null → roster.run_roster →
  roster_gaps.collect → yscale → norm_series → xaxis → view_select → display → freshness → trend_badge →
  prune-stale-gaps → attach-unbound-gaps

Pure unit: neuract reads + nameplate are monkeypatched (no data DB, no LLM).
"""
from __future__ import annotations

import ems_exec.data.neuract as nx
from ems_exec.executor import fill as F
from ems_exec.executor import (roster, roster_gaps, yscale, norm_series, xaxis, view_select, display,
                               freshness, trend_badge)


def test_fill_fires_every_hook_in_documented_order(monkeypatch):
    calls = []

    # neuract/nameplate stubs (no DB)
    monkeypatch.setattr(nx, "present_columns", lambda t: frozenset({"p_kw"}))
    monkeypatch.setattr(nx, "latest", lambda t, cols: {"p_kw": 5.0})
    monkeypatch.setattr(F._np, "derive_ratings_for", lambda t: {})

    # roster seams (lazily imported modules — attr patch reaches fill's `from ems_exec.executor import roster`)
    def _prep(di, ctx):
        calls.append("roster.prepare_ctx")
        ctx["_roster_state"] = {}                              # arm seam #2 so run_roster/roster_gaps must fire
    monkeypatch.setattr(roster, "prepare_ctx", _prep)
    monkeypatch.setattr(roster, "run_roster",
                        lambda out, r, ctx, default_payload=None: (calls.append("roster.run_roster"), out)[1])
    monkeypatch.setattr(roster_gaps, "collect",
                        lambda out, st, existing=None: (calls.append("roster_gaps.collect"), [])[1])

    # facade-bound internals (names bound INTO fill's namespace at import time — patch on F, not the home module)
    monkeypatch.setattr(F, "_restore_array_containers", lambda out, dp: calls.append("restore_arrays"))
    monkeypatch.setattr(F, "_null_untouched_placeholders", lambda out, p, w: calls.append("placeholder_null"))
    monkeypatch.setattr(F, "_prune_stale_gaps", lambda out, gaps: (calls.append("prune_gaps"), gaps)[1])
    monkeypatch.setattr(F, "_attach_unbound_gaps", lambda out, refs, gaps: calls.append("attach_gaps"))

    # lazily imported post-fill passes
    monkeypatch.setattr(yscale, "apply", lambda out, shape_ref=None: (calls.append("yscale"), out)[1])
    monkeypatch.setattr(norm_series, "apply", lambda out, ref: (calls.append("norm_series"), out)[1])
    monkeypatch.setattr(xaxis, "apply",
                        lambda out, ref, gaps, ts_provider=None: (calls.append("xaxis"), out)[1])
    monkeypatch.setattr(view_select, "apply", lambda out: (calls.append("view_select"), out)[1])
    monkeypatch.setattr(display, "apply", lambda out, written: (calls.append("display"), out)[1])
    monkeypatch.setattr(freshness, "apply", lambda out, t: (calls.append("freshness"), out)[1])
    monkeypatch.setattr(trend_badge, "apply", lambda out: (calls.append("trend_badge"), out)[1])

    payload = {"kpis": [{"value": 0.0}]}
    di = {"fields": [{"slot": "kpis[0].value", "kind": "raw", "source": "live", "column": "p_kw"}]}
    out = F.fill(payload, di, {"asset_table": "t1"},
                 default_payload={"kpis": [{"value": 0.0}]}, shape_ref={})

    assert out["kpis"][0]["value"] == 5.0                      # the loop itself filled the real value
    assert calls == ["roster.prepare_ctx", "restore_arrays", "placeholder_null",
                     "roster.run_roster", "roster_gaps.collect",
                     "yscale", "norm_series", "xaxis", "view_select", "display",
                     "freshness", "trend_badge", "prune_gaps", "attach_gaps"], calls
