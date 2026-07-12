"""PROPERTY — the host fork (host/server.handle_run): "knowledge prompts must never invoke dashboards" and
"off-domain prompts are always rejected", enforced at the ONE place the two pipelines split:
  P1  a gate verdict of knowledge/off_scope returns the TERMINAL knowledge response — the card pipeline
      (build_response) is NEVER entered, so no dashboard can be invoked for such a prompt, by construction.
  P2  off_scope responses carry refused=True + the configured refusal line.
  P3  a dashboard verdict — or ANY gate junk/failure (fail-open) — falls through to EXACTLY ONE pipeline build.
  P4  a picker re-POST (asset_id pinned) skips the knowledge gate ENTIRELY (zero gate LLM calls) and runs the
      pipeline with the exact pin.
  P5  an empty prompt is a 400, and neither the gate nor the pipeline runs.
"""
from hypothesis import assume, given, strategies as st

from knowledge.ems import refusal_line
from tests.property.gen import st_junk


@given(data=st.data())
def test_p1_p2_p3_fork(host_offline, data):
    prompt = data.draw(st_junk)
    assume(prompt.strip())
    kind = data.draw(st.one_of(st.sampled_from(["knowledge", "off_scope", "dashboard"]), st_junk))
    answer = data.draw(st.text(max_size=60))
    host_offline["gate"]["reply"] = {"kind": kind, "answer": answer}
    host_offline["gate"]["raise"] = False
    before = host_offline["calls"]["pipeline"]

    code, resp = host_offline["handle_run"]({"prompt": prompt})

    assert code == 200
    ran = host_offline["calls"]["pipeline"] - before
    terminal = str(kind).strip().lower() in ("knowledge", "off_scope")
    if terminal:
        assert ran == 0, f"gate kind={kind!r} but the card pipeline STILL ran — dashboards invoked for knowledge"
        assert resp["kind"] == "knowledge" and "answer" in resp
        if str(kind).strip().lower() == "off_scope":
            assert resp["refused"] is True and resp["answer"] == refusal_line()
    else:
        assert ran == 1, f"gate kind={kind!r} should fall through to exactly one pipeline build, got {ran}"
        assert resp.get("_sentinel") == "pipeline"


@given(data=st.data())
def test_p3_gate_transport_failure_fails_open(host_offline, data):
    prompt = data.draw(st_junk)
    assume(prompt.strip())
    host_offline["gate"]["raise"] = True
    before = host_offline["calls"]["pipeline"]
    code, resp = host_offline["handle_run"]({"prompt": prompt})
    assert code == 200 and host_offline["calls"]["pipeline"] - before == 1
    assert resp.get("_sentinel") == "pipeline"


@given(data=st.data())
def test_p4_pinned_repost_skips_the_gate(host_offline, data):
    prompt = data.draw(st_junk)
    assume(prompt.strip())
    host_offline["gate"]["reply"] = {"kind": "off_scope", "answer": "MUST NOT APPEAR"}
    gate_before = host_offline["gate"]["calls"]
    before = host_offline["calls"]["pipeline"]
    code, resp = host_offline["handle_run"]({"prompt": prompt, "asset_id": "7"})
    assert code == 200
    assert host_offline["gate"]["calls"] == gate_before, "pinned re-POST must never consult the knowledge gate"
    assert host_offline["calls"]["pipeline"] - before == 1 and resp.get("asset_id") == "7"


def test_p5_empty_prompt_is_a_400(host_offline):
    before = host_offline["calls"]["pipeline"]
    code, _resp = host_offline["handle_run"]({"prompt": "   "})
    assert code == 400
    assert host_offline["calls"]["pipeline"] == before and host_offline["gate"]["calls"] == 0
