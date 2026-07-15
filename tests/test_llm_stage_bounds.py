"""Per-stage completion-token bound resolution [decode-wall Stage 3, 2026-07-15].

Pins llm/client._max_tokens_for: per-stage row wins > base row > 0 (unbounded legacy). The truncation SEMANTICS
(finish_reason=length -> 'truncated', fail-fast, in llm.no_retry_kinds) are deliberately unchanged and stay pinned
by the existing client tests. [tests]
"""
import llm.client as C


def _with_cfg(monkeypatch, rows):
    monkeypatch.setattr(C, "_cfg", lambda k, d=None: rows.get(k, d))


def test_no_rows_is_unbounded_legacy(monkeypatch):
    _with_cfg(monkeypatch, {})
    assert C._max_tokens_for("l2_emit") == 0
    assert C._max_tokens_for(None) == 0
    assert C._max_tokens_for("") == 0


def test_base_row_applies_to_every_stage(monkeypatch):
    _with_cfg(monkeypatch, {"llm.max_tokens": "4096"})
    assert C._max_tokens_for("l2_emit") == 4096
    assert C._max_tokens_for("l1a_route") == 4096
    assert C._max_tokens_for(None) == 4096


def test_stage_row_wins_over_base(monkeypatch):
    _with_cfg(monkeypatch, {"llm.max_tokens": "4096", "llm.max_tokens.l2_emit": "6000"})
    assert C._max_tokens_for("l2_emit") == 6000
    assert C._max_tokens_for("l1b_basket") == 4096            # other stages keep the base


def test_stage_zero_row_falls_back_unbounded(monkeypatch):
    """A stage row of 0/'' means 'no cap for this stage' (the `or 0` guard), mirroring the base-row semantics."""
    _with_cfg(monkeypatch, {"llm.max_tokens.l2_emit": "0"})
    assert C._max_tokens_for("l2_emit") == 0


def test_truncated_stays_in_no_retry_kinds(monkeypatch):
    """The cap only makes sense with fail-fast truncation — pin that 'truncated' is a default no-retry kind."""
    from llm.transient_retry import no_retry_kinds
    kinds = no_retry_kinds(lambda k, d=None: d)               # code defaults
    assert "truncated" in kinds and "timeout" in kinds
