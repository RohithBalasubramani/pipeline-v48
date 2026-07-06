"""layer1b/guardrail/same_family_gate.py — class-consistency TELEMETRY on the resolved outcome. [hardening]

Per the verdicts-are-telemetry mandate this is NOT a render gate: it computes a `class_mismatch` flag when the
prompt-implied class (class_from_subject prior) disagrees with the pinned asset's class / the majority candidate
class, so the run telemetry + FE picker can SURFACE that a UPS-only candidate list sailed into a DG prompt — the
exact failure that made the page-13 DG-1 cert auto-pick GIC-01-N3-UPS-01. Nothing is blocked here.
"""
from collections import Counter


def class_mismatch(prior, asset=None, candidates=None):
    """True when a class prior exists AND disagrees with the resolution: the pinned asset's class, or (ambiguous) the
    MAJORITY class of the candidate list. False when there is no prior, no resolution, or they agree."""
    if not prior:
        return False
    if asset:
        return (asset.get("class") or None) != prior
    classes = [c.get("class") for c in (candidates or []) if isinstance(c, dict) and c.get("class")]
    if not classes:
        return False
    majority = Counter(classes).most_common(1)[0][0]
    return majority != prior
