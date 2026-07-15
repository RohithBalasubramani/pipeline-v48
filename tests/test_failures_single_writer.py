"""tests/test_failures_single_writer.py — ONE WRITER PER FACT in the failures sink (audit 01 F4 / 02 F1).

The 2026-07-14 audit found every exception recorded TWICE (harness record('layer-exception') + the stage-ERROR
mirror — 276+276 console rows for ~276 events) and every answerability gap recorded FOUR times (per-card bool +
layer2/reflect/notes count mirrors — 98 events → 371 rows). These pins keep the collapse permanent: the
stage(ERROR=) mirror is THE one exception writer, the per-card bool gap is THE one gap writer. Non-live."""
from __future__ import annotations

import json
import os


def _read_failures(rid):
    from obs.paths import logs_dir
    p = os.path.join(logs_dir(), f"failures_{rid}.jsonl")
    if not os.path.isfile(p):
        return []
    return [json.loads(x) for x in open(p).read().splitlines() if x.strip()]


def _cleanup(rid):
    from obs.paths import logs_dir
    for fam in ("failures", "pipeline"):
        p = os.path.join(logs_dir(), f"{fam}_{rid}.jsonl")
        if os.path.isfile(p):
            os.remove(p)


def test_validate_exception_records_exactly_one_failure(monkeypatch):
    """The layer-exception/stage_error twin cannot return: a validate exception = ONE record, stage 'validate'."""
    import run.harness as H
    rid = "t_singlewriter"
    _cleanup(rid)
    monkeypatch.setattr(H, "run_validate", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom-once")))
    out = {"errors": {}, "layer1a": {}, "layer1b": {}}
    try:
        H._validate(out, "db", rid)
        recs = _read_failures(rid)
        assert [(r["stage"], r["reason"]) for r in recs] == [("validate", "stage_error")]
        assert "boom-once" in recs[0]["detail"]
        assert out["errors"]["validation"]                     # the machine detail still lands in errors
    finally:
        _cleanup(rid)


def test_harness_has_no_direct_failures_import():
    """Permanence: run/harness.py must not re-grow a second failure writer next to the stage mirror."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src = open(os.path.join(root, "run", "harness.py")).read()
    assert "from obs.failures import" not in src
    assert '"layer-exception"' not in src and "'layer-exception'" not in src


def test_one_gap_one_record():
    """Drive the four historical mirror shapes of ONE gap event — exactly one record survives, with the note."""
    from obs.stage import stage
    rid = "t_onegap"
    _cleanup(rid)
    try:
        stage(rid, "L2.card", id=61, gap=True, note="requires temperature columns")   # the one writer
        stage(rid, "layer2", cards=3, gaps=1, hard_fails=0)                           # run-level mirror — silent
        stage(rid, "reflect", loop=1, gaps=1, honest_terminal=True)                   # run-level mirror — silent
        stage(rid, "notes", loop1=3, loop2=False, partial=1, gaps=1)                  # notes count — silent
        recs = _read_failures(rid)
        assert [(r["reason"], r["card_id"], r["detail"]) for r in recs] == \
            [("fill_gap", 61, "requires temperature columns")]
    finally:
        _cleanup(rid)
