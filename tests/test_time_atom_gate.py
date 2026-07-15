"""tests/test_time_atom_gate.py — kind='time' atoms may bind ONLY designated time-axis leaves (audit 13 F1).

The epoch_ms_leak class: emit mis-declared a time atom onto a value/Y-scale leaf and the executor's series-time
fill wrote an epoch-ms bucket axis there; CLASS-1 blanked it post-hoc. The gate now refuses at the front door:
a fields[-prefixed issue (per-leaf partition — conforms stays True) AND the field is dropped so the executor can
never epoch-fill the leaf. Legal time-axis targets (ticks/labels/timestamps/startMs/points…) pass untouched. Non-live."""
from __future__ import annotations

from layer2.gates.data_instructions import gate_data_instructions


def _di(fields):
    return {"fields": [dict(f) for f in fields]}


def _basket():
    return {"columns": [{"column": "p_kw"}], "tables": ["t"]}   # _bindable reads c["column"]


def test_time_atom_on_value_leaf_partitioned_and_dropped():
    di = _di([{"slot": "data.metrics[0].value", "kind": "time", "role": "axis", "source": "live"},
              {"slot": "expectedMax", "kind": "time", "source": "live"}])
    ok, issues = gate_data_instructions(di, _basket())
    time_issues = [x for x in issues if "kind=time on a non-time-axis slot" in x]
    assert len(time_issues) == 2
    assert all(x.startswith("fields[") for x in time_issues)   # per-leaf partition shape (build.py:_field_issues)
    assert di["fields"] == []                                  # both mis-targeted atoms dropped — never epoch-filled


def test_time_atom_on_axis_leaves_passes():
    di = _di([{"slot": "sampleTimestamps", "kind": "time", "source": "live"},
              {"slot": "chart.yTicks", "kind": "time", "source": "live"},
              {"slot": "axisStartMs", "kind": "time", "source": "live"},
              {"slot": "timeline.points", "kind": "time", "source": "live"},
              {"slot": "xLabels", "kind": "time", "source": "live"}])
    ok, issues = gate_data_instructions(di, _basket())
    assert not [x for x in issues if "non-time-axis" in x]
    assert len(di["fields"]) == 5                              # every legal axis target kept


def test_mixed_fields_only_the_bad_atom_drops():
    di = _di([{"slot": "chart.series[0].value", "kind": "raw", "source": "live", "column": "p_kw"},
              {"slot": "yMin", "kind": "time", "source": "live"}])
    ok, issues = gate_data_instructions(di, _basket())
    assert any("non-time-axis" in x for x in issues)
    assert [f["slot"] for f in di["fields"]] == ["chart.series[0].value"]
