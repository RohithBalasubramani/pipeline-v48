"""layer3 — the ONE AI layer of the render-guarantee contract (per-card VERDICT: names + booleans + reason, NO numbers).

Atomic pieces:
  factsheet.py — deterministic PRE->L3 seam: assemble every grounding fact into the fact-sheet shape (values stripped).
  prompt.py    — the L3 system + user prompt (names/flags only).
  emit.py      — the ONE L3 call_qwen using prompt.py.
  schema.py    — validate the RenderSpec (names+booleans+reason ONLY, no numbers) + persist to render_spec.
  apply.py     — POST: fetch+plug+range/sign verify each bound/substitute slot, force-blank suppress_default_leaves,
                 thread reason/coverage/fidelity.
"""
