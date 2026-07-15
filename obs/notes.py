"""obs/notes.py — persist the reflect-loop NOTES (what Layer 2 did/substituted + why, and why a re-route still failed)
so they can be shown to the user later. One file per concern: write outputs/notes/<run_id>.json + log via stage.

notes shape: {"loop1": [{card_id, title, answerability, note}], "loop2": <str|null>}. loop1 = per-card best-effort /
substitution explanations from the first pass (+ the gaps that triggered a re-route); loop2 = the persistent-gap note."""
import json
import os

from obs.stage import stage

from obs.paths import notes_dir as _notes_dir   # the ONE writer-dir door (V48_OBS_NOTES_DIR-aware) [audit 03]


def record(run_id, notes):
    """Persist + log the run's reflect-loop notes. No-op for an empty notes set (no substitutions, no gaps).
    Telemetry only — never raises into the harness [OBS-4]: run/harness.py calls this bare at the END of an
    otherwise-successful run, so an unwritable outputs/ must degrade silently (obs/stage.py fail-open style)."""
    try:
        loop1 = notes.get("loop1") or []
        loop2 = notes.get("loop2")
        if not loop1 and not loop2:
            return notes
        _d = _notes_dir()
        os.makedirs(_d, exist_ok=True)
        with open(os.path.join(_d, f"{run_id}.json"), "w") as f:
            json.dump({"run_id": run_id, **notes}, f, indent=1)
        # count vocabulary: gaps=N, never gap= — the int used to slip through _failure_signal's boolean gap
        # branch and become a 4th fill_gap mirror per event [audit 02 F1]
        stage(run_id, "notes", loop1=len(loop1), loop2=bool(loop2),
              partial=sum(1 for n in loop1 if n.get("answerability") == "partial"),
              gaps=sum(1 for n in loop1 if n.get("answerability") == "none"))
    except Exception:
        pass
    return notes
