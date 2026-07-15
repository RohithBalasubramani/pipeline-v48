"""tests/test_error_terminal_backstop.py — the PIPELINE-ERROR honest terminal (run/error_terminal.py).

A NON-outage layer exception that leaves the layer with no output must mark data_unavailable with
kind="pipeline_error" — the shape that historically shipped a silent ok=True 0-card page (dangling-registry
raise, audit 2026-07-14, 01 F1). The outage gate stays the more specific explanation and always wins.
errors.validation never fires it (validation is annotate-only by design). Non-live."""
from __future__ import annotations

from run.error_terminal import apply


def _out(**kw):
    base = {"errors": {}, "layer1a": None, "layer1b": None, "layer2": None,
            "validation": None, "notes": {}}
    base.update(kw)
    return base


def test_layer1b_exception_with_no_output_fires_pipeline_error():
    # the exact audit shape: dangling registry row → uncaught missing-relation raise → layer1b None
    out = _out(layer1a={"cards": []},
               errors={"layer1b": 'RuntimeError: DB error (target_version1): relation '
                                  '"neuract.gic_15_n10_pcc_01_transformer_01_sch" does not exist'})
    apply(out)
    assert out["data_unavailable"] is True
    assert out["degrade"]["kind"] == "pipeline_error"
    assert out["degrade"]["layer"] == "layer1b"
    assert "does not exist" in out["degrade"]["detail"]
    assert out["degrade"]["reason"]                     # DB template or the bare fallback — never missing


def test_layer2_exception_with_no_output_fires():
    out = _out(layer1a={"cards": []}, layer1b={"asset": {}}, errors={"layer2": "ValueError: boom"})
    apply(out)
    assert out["data_unavailable"] is True
    assert out["degrade"]["layer"] == "layer2"


def test_layer_that_produced_output_does_not_fire():
    # attempt-2 reroute died but attempt-1's layer2 shipped — the page is answered, no terminal
    out = _out(layer1a={"cards": []}, layer1b={"asset": {}}, layer2={1: {"conforms": True}},
               errors={"layer2": "ValueError: attempt-2 boom"})
    apply(out)
    assert out.get("data_unavailable") is not True


def test_outage_gate_already_fired_wins():
    out = _out(errors={"layer1b": "connection refused"}, data_unavailable=True,
               degrade={"kind": "data_unavailable", "layer": "layer1b"})
    apply(out)
    assert out["degrade"]["kind"] == "data_unavailable"   # untouched — outage is the more specific explanation


def test_validation_error_never_fires():
    out = _out(layer1a={"cards": []}, layer1b={"asset": {}}, layer2={1: {}},
               errors={"validation": "DatabaseError: whatever"})
    apply(out)
    assert out.get("data_unavailable") is not True


def test_no_errors_no_op_and_never_raises():
    out = _out(layer1a={"cards": []}, layer1b={"asset": {}})
    assert apply(out) is out
    assert out.get("data_unavailable") is not True
    apply({})                                             # degenerate dict: still no raise
