"""PROPERTY — knowledge.ems._ask (the ONE route+answer+reject gate) is CLOSED and honest for ANY model emission:
  P1  kind closure: always dashboard | knowledge | off_scope — junk kinds and half-parsed emissions fail OPEN to
      dashboard (the card pipeline is never blocked by this layer).
  P2  off_scope is ALWAYS a refusal: refused=True and the configured refusal line — "off-domain prompts must always
      be rejected" at the plumbing level.
  P3  knowledge never ships a blank: an empty answer degrades to the refusal line with refused=True.
  P4  a transport exception fails open to dashboard.
  P5  the valve: knowledge.enabled off → dashboard without ever calling the LLM.
"""
from hypothesis import given, strategies as st

from knowledge.ems import _KINDS, _ask, refusal_line
from tests.property.gen import st_junk


@given(data=st.data())
def test_p1_p2_p3_gate_fuzz(knowledge_offline, data):
    mode = data.draw(st.sampled_from(["valid", "junk_kind", "empty", "missing_kind", "raise"]))
    answer = data.draw(st.text(max_size=80))
    if mode == "valid":
        reply = {"kind": data.draw(st.sampled_from(list(_KINDS))), "answer": answer}
    elif mode == "junk_kind":
        reply = {"kind": data.draw(st_junk), "answer": answer}
    elif mode == "missing_kind":
        reply = {"answer": answer}
    else:
        reply = {}
    knowledge_offline["reply"] = reply
    knowledge_offline["raise"] = (mode == "raise")

    out = _ask(data.draw(st_junk))

    assert out["kind"] in _KINDS                                            # P1 closure
    if out["kind"] == "off_scope":                                          # P2 refusal contract
        assert out["refused"] is True and out["answer"] == refusal_line()
    elif out["kind"] == "knowledge":                                        # P3 never a blank
        assert out["answer"] == (answer.strip() or refusal_line())
        assert out["refused"] is (not answer.strip())
    else:
        assert out["answer"] == "" and out["refused"] is False
    if mode == "valid":                                                     # a well-formed emission is honored
        assert out["kind"] == reply["kind"]
    if mode in ("junk_kind", "empty", "missing_kind", "raise"):
        expected = reply.get("kind", "").strip().lower() if mode == "junk_kind" else ""
        if expected not in _KINDS:
            assert out["kind"] == "dashboard"                               # P1/P4 fail-open


def test_p5_disabled_valve_skips_the_llm(knowledge_offline, monkeypatch):
    import knowledge.ems as KE
    monkeypatch.setattr(KE, "enabled", lambda: False)
    out = _ask("what is voltage?")
    assert out == {"kind": "dashboard", "answer": "", "refused": False}
    assert knowledge_offline["calls"] == 0
