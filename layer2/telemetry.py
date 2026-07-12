"""layer2/telemetry.py — the DECLARED enumeration of the `data_instructions._*` telemetry family [typing F9,
2026-07-12].

Layer 2 grows an open-ended `_`-prefixed telemetry family on data_instructions (build.py's finalize/reconcile
passes) which ships to the FE verbatim via host/enrich. Nothing enumerated the full set — the FE and the sweeps
could not know which keys are telemetry vs data. This frozenset IS that contract; tests assert every `_`-key the
producer writes is enumerated here, so a new telemetry key is a one-line, discoverable addition. [atomic]"""

# every data_instructions key layer2/build.py (+ the emit reconcile) writes with a leading underscore.
DI_TELEMETRY_KEYS = frozenset({
    "_normalized",            # overlay normalization notes (build.py)
    "_window_label",          # the coherent window label the emit settled on
    "_per_leaf_gaps",         # per-leaf emit-time gap records (merged into render.gaps at serve)
    "_noop_morphs",           # declared morphs that changed nothing (drift telemetry)
    "_zero_skeleton",         # True when the stripped skeleton had zero data leaves
    "_emit_gaps",             # completeness-reconcile 'unbound_by_emit' records
    "_honest_blanked",        # the AI's explicitly-declared honest-blank slots (authoritative over rescues)
    "_cross_domain",          # cross-domain slot/source family pairs the wall flagged
    "_cross_domain_blanked",  # count of leaves the cross-domain wall honest-blanked
})
