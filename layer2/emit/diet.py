"""layer2/emit/diet.py — THE emit-diet flag home [decode-wall root fix, 2026-07-15].

One concern: the DB flags that shrink the emit OUTPUT contract (stop the model re-typing facts the pipeline owns).
Forensics (1,555 real emits): ~55% of completion tokens were roster/fields retype the gates fold back to recipe truth
anyway, and the 5-21K-token runaways were zero-filled data grids / 110-entry roster retypes — not decisions. Every
flag defaults OFF = today's exact prompt bytes (goldens pin this); adoption = flip the row + service reload.

  emit.diet.roster       — Stage 1: roster-DIFF contract (emit only changed bindings; omitted slots backfill
                           verbatim — layer2/gates/roster.py:163 already reconstructs) + envelope scaffold zero-out.
  emit.diet.morph_shape  — Stage 2: collapse the skeleton's DATA-tier grids in the shown METADATA SHAPE (the
                           zero-filled-matrix temptation of obs row 4485) to a single live-fill marker.

[atomic; DB-driven with code-default off]"""
from config.app_config import cfg


def _on(key):
    return str(cfg(key, "off") or "off").strip().lower() in ("on", "1", "true", "yes")


def roster_diff():
    """Stage 1: the roster-DIFF output contract + code-owned envelope scaffold note."""
    return _on("emit.diet.roster")


def morph_shape():
    """Stage 2: data-tier shape collapse of the shown skeleton (morph-map cards only)."""
    return _on("emit.diet.morph_shape")
