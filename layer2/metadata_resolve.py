"""layer2/metadata_resolve.py — resolve a card's FINAL exact_metadata from its AI emit (the morph-map vs full
produce→gate→enforce machinery). Extracted verbatim from build._finalize_inner (atomic-structure rule; byte-identical
sequence, same comments — this is the fabrication-prevention core, so nothing here is changed, only relocated).

Returns (exact_metadata, applied, undeclared, ok_m, llm_err, failures): `failures` is seeded with the metadata-stage
failures and RETURNED so the caller keeps appending its own (roster/gate/etc.) to the same list."""
from layer2.emit.metadata.producer import produce, metadata_reference, undeclared_morphs
from layer2.emit.morphmap.producer import apply as morphmap_apply
from layer2.gates import (gate_exact_metadata, enforce_exact_metadata, enforce_free_metadata)


def resolve_exact_metadata(raw, dp):
    """`raw` = the AI emit; `dp` = the card's harvested default payload (or None). Mirrors the exact inline sequence
    _finalize_inner used, so its outputs are byte-identical to the pre-extraction code."""
    # LLM-TRANSPORT HONESTY [empty-fields family, cards 74/76]: a failed call is now a MARKER ({"_llm_error": kind}),
    # never a silent {} that reads as an intentional empty emission. The card still renders its byte-identical
    # metadata frame (per-leaf degradation), but answerability NEVER defaults to "full", conforms=False, and the
    # failure stage is 'llm' so sweeps bucket it apart from emit quality.
    llm_err = raw.get("_llm_error") if isinstance(raw, dict) else None
    # MORPH-MAP RETURN SHAPE [emit.morphmap_mode]: under the morph-map contract the emit returns a flat
    # {"morphs":{path:value}} map instead of exact_metadata+_morphed. Key off the OUTPUT shape (robust to a stray flag):
    # a dict carrying 'morphs' and no 'exact_metadata' is a morph-map emit. morphmap_apply() is a THIN wrapper over the
    # SAME produce→gate→enforce machinery (byte-equivalent — offline-proven 5831/5831), so everything downstream is
    # identical; naming a path IS declaring, so the A1 undeclared-morph silent-revert class cannot exist here.
    _mm_raw = isinstance(raw, dict) and isinstance(raw.get("morphs"), dict) and not raw.get("exact_metadata")
    ai_meta = raw.get("exact_metadata") or {}
    morphed = ai_meta.pop("_morphed", []) if isinstance(ai_meta, dict) else []
    failures = []
    if llm_err:
        failures.append(f"llm call failed ({llm_err}): {raw.get('_llm_error_detail') or ''}".strip())

    if dp:
        # REFERENCE = the STRIPPED default (data leaves → typed placeholders), NOT the raw seed-bearing default: the
        # byte-identity gate/enforce must compare metadata against what exact_metadata is actually built from, else a
        # correctly-stripped data leaf (0/[]) reads as a 'violation' and enforce reverts it back to the seed (389.2).
        # STORED skeleton (card_payloads.payload_stripped, scripts/build_stripped_payloads.py) — the pre-cleaned,
        # inspectable DB row; NULL (un-built) → producer falls back to the identical on-the-fly strip.
        _stored = dp.get("payload_stripped")
        ref = metadata_reference(dp["payload"], stored=_stored)
        if _mm_raw and _stored is not None:
            # MORPH-MAP PATH: apply() does the same produce→gate→enforce internally and returns the SAME exact_metadata
            # bytes + a report with the SAME telemetry keys the full path emits. No undeclared-morph class (naming =
            # declaring). _stored None → fall through to the full path (the AI sent no exact_metadata → full default).
            exact_metadata, _rep = morphmap_apply(raw.get("morphs") or {}, _stored, default_payload=dp["payload"])
            applied = _rep["applied"]
            failures += [f"morph rejected: {r}" for r in _rep["rejected"]]
            failures += [f"reverted to default: {p}" for p in _rep["reverted"]]
            ok_m, m_issues = _rep["conforms"], _rep["gate_issues"]
            failures += m_issues
            _undeclared = []
        else:
            exact_metadata, applied, rejected = produce(dp["payload"], ai_meta, morphed, stored=_stored)
            # UNDECLARED-MORPH TELEMETRY [A1]: metadata paths the AI authored off-default WITHOUT declaring in _morphed —
            # produce() silently reverts those to the byte-identical default (2-of-6812 _morphed compliance made ALL
            # authoring a silent no-op). Telemetry only, NO auto-promote (the byte-identity seam stays closed).
            _undeclared = undeclared_morphs(dp["payload"], ai_meta, morphed, stored=_stored)
            failures += [f"morph rejected: {r}" for r in rejected]
            ok_m, m_issues = gate_exact_metadata(exact_metadata, ref, morphed=applied)
            # LOAD-BEARING byte-identity enforcement [META-02]: if the gate flags a metadata byte-identity/chrome/shape
            # violation, REVERT the offending METADATA leaf to its byte-identical default (the stripped ref) so the resting
            # render is guaranteed conforming — WITHOUT re-introducing a seed data value.
            if not ok_m:
                exact_metadata, reverted = enforce_exact_metadata(exact_metadata, ref, morphed=applied)
                failures += [f"reverted to default: {p}" for p in reverted]
                ok_m, m_issues = gate_exact_metadata(exact_metadata, ref, morphed=applied)
            failures += m_issues
    else:
        # NO harvested default (no stored payload_stripped): the AI authors exact_metadata off the CONTRACT EXAMPLE,
        # which carries demo numbers and clock labels ('13:14:10') — shipped verbatim they render a FABRICATED live
        # time axis (cards 6/160). enforce_exact_metadata (needs a default ref) can't cover this, so the ONE scrub the
        # no-default path needs is FOLDED into the gates layer as enforce_free_metadata: data leaves → typed
        # placeholders, narrative/clock scrubbed, reusing the canonical strip worker (NOT a second strip, NOT a runtime
        # strip_to_placeholders caller). Chrome untouched; never raises.
        exact_metadata, applied = enforce_free_metadata(ai_meta), []
        _undeclared = []
        ok_m = bool(ai_meta)
        if not ok_m:
            failures.append("no default payload + empty exact_metadata")

    return exact_metadata, applied, _undeclared, ok_m, llm_err, failures
