"""run/error_terminal.py — the PIPELINE-ERROR honest terminal (atomic sibling of run/degrade_gate.py).

degrade_gate answers "did an INFRA layer fail because a live data source is UNREACHABLE" (outage → data_unavailable).
This module answers the residual: "did a pipeline layer die on a NON-outage exception and produce nothing" — the shape
that historically shipped a silent ok=True 0-card page (dangling-registry raise, audit 2026-07-14, 01 F1). The page
must never look answered when a whole layer is missing: mark data_unavailable with kind="pipeline_error" so the FE's
existing terminal renders, while errors.<layer> keeps the machine detail for triage.

Honesty note (why this doesn't violate the outage/logic split in data/outage.py): the data layer must never absorb a
logic error as "no data" — but at the PAGE layer the alternative is a silent success. kind="pipeline_error" keeps the
distinction machine-readable; nothing is absorbed, the error stays in errors.<layer> and the failures sink.

errors.validation is deliberately excluded — validation is annotate-only by design (run/harness._validate)."""

_LAYERS = ("layer1a", "layer1b", "layer2")


def apply(out):
    """Mark the honest pipeline_error terminal when a layer recorded an exception AND produced no output.
    No-op when the outage gate already fired (it ran first and is the more specific explanation). Never raises."""
    try:
        if out.get("data_unavailable"):
            return out
        errors = out.get("errors") or {}
        for layer in _LAYERS:
            detail = errors.get(layer)
            if detail and out.get(layer) is None:
                out["data_unavailable"] = True
                out["degrade"] = {"kind": "pipeline_error", "layer": layer, "detail": str(detail)[:400]}
                try:
                    from config.reason_templates import reason
                    out["degrade"]["reason"] = reason("pipeline_error", layer=layer)
                except Exception:
                    out["degrade"]["reason"] = "pipeline_error"
                return out
    except Exception:
        pass
    return out
