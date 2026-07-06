"""OVERSIZED-PROMPT CONTEXT CAP [c24 harmonics-timeline: a ~23.4K-tok (~43K-char user) emit prompt blew the 150s
l2_emit budget → payload_error=llm_timeout — fullsweep_20260706_004334 v18_04]. layer2/emit/user_message.build_user
now rebuilds a user message over the DB-config char budget (emit.prompt_char_budget) with honesty-preserving
compaction: skeleton arrays → first-K exemplars + marker, DB SCHEMA lines capped with a '+N more' trailer, sibling
per-element slot lines folded to K exemplars + a summary that keeps the omitted indices NAMED (the card-77 lesson:
never hide slots silently). Generic — no card ids. All non-live, deterministic."""
import layer2.emit.user_message as um
from layer2.emit.user_message import _compact_arrays, _compact_catalog, _basket_lines


def test_compact_arrays_truncates_with_marker_and_keeps_shape():
    skel = {"periods": [{"panels": [1, 2, 3, 4, 5]}] * 6, "limits": {"a": 1}, "tabs": ["x", "y"]}
    out = _compact_arrays(skel, 2)
    assert len(out["periods"]) == 3                                # 2 exemplars + 1 marker
    assert isinstance(out["periods"][-1], str) and "+4 more" in out["periods"][-1]
    assert len(out["periods"][0]["panels"]) == 3 and "+3 more" in out["periods"][0]["panels"][-1]
    assert out["tabs"] == ["x", "y"]                               # short arrays untouched
    assert skel["periods"][0]["panels"] == [1, 2, 3, 4, 5]         # input never mutated


def test_compact_catalog_folds_siblings_and_names_the_omitted_indices():
    cat = ([{"slot": f"timeline.periods[0].panels[{i}].kw", "kind": "scalar"} for i in range(10)]
           + [{"slot": "timeline.limits.vThdLimit", "kind": "scalar"}]
           + [{"slot": "trend.series[*].values", "kind": "bucket_series"}])
    kept, summaries = _compact_catalog(cat, 3)
    slots = [e["slot"] for e in kept]
    assert slots[:3] == [f"timeline.periods[0].panels[{i}].kw" for i in range(3)]
    assert "timeline.limits.vThdLimit" in slots                    # non-indexed entries always kept
    assert "trend.series[*].values" in slots                       # [*] bucket slots always kept
    assert len(summaries) == 1 and "×10 sibling elements" in summaries[0]
    assert "timeline.periods[*].panels[*].kw" in summaries[0]      # omitted slots stay NAMED, never hidden


def test_basket_lines_cap_names_the_truncation():
    basket = {"columns": [{"column": f"c{i}", "unit": "kW", "has_data": True} for i in range(10)]}
    lines = _basket_lines(basket, cap=4)
    assert lines.count("\n") == 4                                  # 4 columns + 1 trailer
    assert "+6 lower-ranked columns not shown" in lines


def test_build_user_rebuilds_compacted_only_over_budget(monkeypatch):
    calls = []

    def fake_build(card_in, *, oversize=False):
        calls.append(oversize)
        return "L" * (2000 if oversize else 10000)

    monkeypatch.setattr(um, "_build", fake_build)
    monkeypatch.setattr(um, "cfg", lambda k, d: d)                 # module-level cfg (not used by build_user's local import)
    import config.app_config as ac
    monkeypatch.setattr(ac, "cfg", lambda k, d: 5000 if k == "emit.prompt_char_budget" else d)
    out = um.build_user({"card": 1})
    assert calls == [False, True] and len(out) == 2000             # over budget → compacted rebuild wins

    calls.clear()
    monkeypatch.setattr(ac, "cfg", lambda k, d: 50000 if k == "emit.prompt_char_budget" else d)
    out = um.build_user({"card": 1})
    assert calls == [False] and len(out) == 10000                  # under budget → untouched

    calls.clear()
    monkeypatch.setattr(ac, "cfg", lambda k, d: 0 if k == "emit.prompt_char_budget" else d)
    out = um.build_user({"card": 1})
    assert calls == [False] and len(out) == 10000                  # 0 = knob off
