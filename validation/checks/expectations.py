"""validation/checks/expectations.py — the OUTCOME JUDGE: does the parsed response match the case's category
expectation? Expectation grammar (templates.py): 'cards' | 'picker' | 'knowledge' | 'refused' | 'empty' |
'unavailable' | 'compare:N' | unions with '|' ('cards|picker').

HONESTY-AWARE: an expected-cards case that came back 'unavailable' (infra outage terminal, degrade reason set) is a
DEGRADED pass-with-flag, not a hard failure — the pipeline behaved honestly; the flake is environmental (the :5433
tunnel). It is still counted separately (degraded) so a rash of them is visible. Fabrication ALWAYS fails: any
payload_error on an otherwise-passing case flips it to fail with stage='layer2_emit'."""
from __future__ import annotations


def _matches(token: str, parsed: dict) -> bool:
    token = token.strip()
    if token.startswith("compare:"):
        return parsed["outcome"] == "compare" and parsed["n_groups"] >= int(token.split(":")[1])
    return parsed["outcome"] == token


def judge(case: dict, parsed: dict) -> dict:
    """{pass, degraded, stage, why} — stage attributes the failure to the pipeline layer that owns it."""
    expect = case.get("expect") or "cards"
    tokens = [t for t in expect.split("|") if t]
    matched = any(_matches(t, parsed) for t in tokens)

    if matched and parsed["fabrication_risk"]:
        return {"pass": False, "degraded": False, "stage": "layer2_emit",
                "why": f"{parsed['payload_errors']} card(s) carry payload_error (fabrication risk)"}
    # expected data cards but every leaf blanked -> degradation coverage (honest but worth surfacing)
    if matched and parsed["outcome"] in ("cards", "compare") and parsed["data_leaves"] > 0 and parsed["real_leaves"] == 0:
        return {"pass": True, "degraded": True, "stage": "executor_fill",
                "why": "renders honestly but 0 real leaves (asset dark or metric unmeasured)"}
    if matched:
        return {"pass": True, "degraded": False, "stage": None, "why": "as expected"}

    # honest infra terminal on a cards-expecting case: degraded, not a pipeline defect
    if parsed["outcome"] == "unavailable" and any(t.startswith(("cards", "compare")) for t in tokens):
        return {"pass": True, "degraded": True, "stage": "infra",
                "why": f"honest data_unavailable terminal ({parsed.get('degrade') or 'outage'})"}

    stage = {
        "refused": "knowledge_gate", "knowledge": "knowledge_gate",
        "picker": "asset_resolution", "empty": "asset_resolution",
        "cards": "routing", "compare": "compare_path", "unavailable": "infra",
    }.get(parsed["outcome"], "unknown")
    return {"pass": False, "degraded": False, "stage": stage,
            "why": f"expected {expect}, got {parsed['outcome']} "
                   f"(cards={parsed['n_cards']} cand={parsed['n_candidates']} groups={parsed['n_groups']})"}
