"""layer2/schema.py — validate the assembled Layer2CardOutput (contract 5)."""

_REQUIRED = ("card_id", "render_slot", "swap_decision", "analytical_story", "exact_metadata", "data_instructions", "conforms")


def validate_layer2_card_output(out):
    p = []
    for k in _REQUIRED:
        if k not in out:
            p.append(f"missing {k}")
    if not isinstance(out.get("exact_metadata"), dict) or not out["exact_metadata"]:
        p.append("exact_metadata must be a non-empty object")
    di = out.get("data_instructions") or {}
    for k in ("payload_shape", "orientation", "fields"):
        if k not in di:
            p.append(f"data_instructions.{k} missing")
    sd = out.get("swap_decision") or {}
    if sd.get("action") not in ("keep", "swap"):
        p.append(f"swap_decision.action bad: {sd.get('action')!r}")
    if sd.get("origin") not in ("kept", "swapped", "must_swap"):
        p.append(f"swap_decision.origin bad: {sd.get('origin')!r}")
    if not isinstance(out.get("conforms"), bool):
        p.append("conforms must be bool")
    if out.get("$ctx") is not None and not out.get("is_group_marker", True):
        pass
    return p
