"""layer2/emit/morphmap — ITEM 18: the morph-map PARALLEL emit path (variant of the full exact_metadata retype).

The AI declares ONLY {"morphs": {"<path>": <value>}} (+ the unchanged data_instructions/answerability/data_note);
the deterministic producer copies the stored seedless skeleton and overlays each declared path, then runs the
EXISTING byte-identity gates unchanged. NOTHING here is wired into the live emit path (layer2/emit/emit.py /
layer2/build.py untouched) — adoption is gated on the offline A/B (tools/morphmap_ab.py) proving equal-or-better,
and the live seam stays behind the DEFAULT-OFF config row `emit.morphmap_mode` (mode.py). [ITEM 18 PREP]"""
