"""layer2/emit/morphmap/producer.py — apply a MORPH MAP ({path: value}) onto the stored seedless skeleton and run
the EXISTING enforce/gates unchanged. [ITEM 18 PREP — parallel path, NOT wired into the live emit]

Contract (morphmap/prompt.md): the AI returns ONLY {"morphs": {"<path>": <value>}} for the metadata tier — naming a
path IS the declaration (there is no separate `_morphed` list and no full exact_metadata retype). This producer is a
THIN composition over the certified full-emit machinery — IMPORTED, never copied — so the two contracts can never
diverge on validation semantics:

  · layer2.emit.metadata.producer.produce   — the data-leaf guard (symmetric on/above/below), real-leaf check,
                                              chrome check, declared-only overlay onto the stored skeleton;
  · layer2.gates.gate_exact_metadata        — the byte-identity gate (vs the stripped reference);
  · layer2.gates.enforce_exact_metadata     — the load-bearing revert of any non-conforming leaf.

apply(morphs, stored_payload_stripped) → (exact_metadata, report). The synthetic authored-metadata it feeds produce()
is the skeleton with each morph path set — byte-identical everywhere else BY CONSTRUCTION, which is the whole point
of the variant contract: no retyping, no omission risk, no undeclared drift."""
import copy

from layer2.emit.metadata.producer import produce, metadata_reference, _set
from layer2.gates import gate_exact_metadata, enforce_exact_metadata


def apply(morphs, stored_payload_stripped, *, default_payload=None):
    """Build exact_metadata from a morph map. Returns (exact_metadata, report).

    morphs                  — {"<leaf path>": value} as emitted under the morph-map contract ({} / None = pure default).
    stored_payload_stripped — the card's card_payloads.payload_stripped row (the certified seedless skeleton). REQUIRED
                              (produce() raises on None — same loud failure as the live path; run
                              scripts/build_stripped_payloads.py).
    default_payload         — OPTIONAL raw harvested payload (card_payloads.payload). Used ONLY for the value-aware
                              data-leaf classification, exactly as the live path classifies (validate.leaf_classify
                              over the RAW payload). Absent → the stored skeleton classifies (honest fallback; typed
                              placeholders still classify the roster/series tiers).

    report = {"applied": [paths set], "rejected": ["path: reason"], "reverted": [paths the gate reverted],
              "gate_issues": [residual gate issues], "conforms": bool}. Never fabricates: every non-applied path
    ships its byte-identical default (produce/enforce semantics, unchanged)."""
    src = default_payload if default_payload is not None else stored_payload_stripped
    # synthetic authored-metadata: the skeleton with each declared path set. An unresolvable path is left unset —
    # produce() then rejects it as 'not a real metadata leaf' (identical wording/telemetry to the full-emit path).
    synthetic = copy.deepcopy(stored_payload_stripped)
    declared, pre_rejected = [], []
    for path, val in (morphs or {}).items():
        p = str(path)
        if not p.strip():                                      # '' addresses the whole document — never a leaf morph
            pre_rejected.append(f"{p!r}: empty morph path")
            continue
        if p in declared:
            continue
        declared.append(p)
        try:
            _set(synthetic, p, val)
        except (KeyError, IndexError, TypeError):
            pass                                               # not a real leaf — produce() records the rejection
    built, applied, rejected = produce(src, synthetic, declared, stored=stored_payload_stripped)
    ref = metadata_reference(src, stored=stored_payload_stripped)
    ok, issues = gate_exact_metadata(built, ref, morphed=applied)
    reverted = []
    if not ok:                                                 # same self-heal order as layer2/build._finalize
        built, reverted = enforce_exact_metadata(built, ref, morphed=applied)
        ok, issues = gate_exact_metadata(built, ref, morphed=applied)
    return built, {"applied": applied, "rejected": pre_rejected + rejected, "reverted": reverted,
                   "gate_issues": issues, "conforms": ok}
