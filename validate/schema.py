"""validate/schema.py — structural validation of the validation-layer output. [validate, contract V]"""

_VERDICTS = {"pass", "warn", "fail", "asset_pending"}


def validate_validation_output(out):
    p = []
    if out.get("verdict") not in _VERDICTS:
        p.append(f"bad overall verdict: {out.get('verdict')!r}")
    for sect in ("data", "payload"):
        if sect not in out:
            p.append(f"missing section: {sect}")
    if "columns" not in out.get("data", {}):
        p.append("data.columns missing")
    if "cards" not in out.get("payload", {}):
        p.append("payload.cards missing")
    for col in out.get("data", {}).get("columns", []):
        if col.get("verdict") not in {"pass", "warn", "fail"}:
            p.append(f"bad column verdict: {col.get('column')}={col.get('verdict')}")
    return p
