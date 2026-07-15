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


def fields_slim():
    """Stage 6 [emit.diet.fields]: slim fields[] contract (model emits only decisions; label/unit/metric/role/agg
    backfill deterministically from the slot catalog + basket dictionary — layer2/resolve/field_backfill.py)."""
    return _on("emit.diet.fields")


def prompt_stability():
    """Stage 4 [emit.prompt_stability='v1']: deterministic prompt bytes — freshness timestamps bucketed to the HOUR
    (nanosecond `last=` stamps at ~char 1080 busted every byte-repeat) + the per-run RUN: prefix dropped from the
    user message (the run id lives in ai_log/obs, the model never needs it). Identical card+context within an hour
    → byte-identical prompt → pinned-seed determinism actually holds run-to-run, and the Stage-5 recipe cache can
    key on the prompt bytes. off = today's exact bytes."""
    return str(cfg("emit.prompt_stability", "off") or "off").strip().lower() in ("v1", "on", "1", "true")
