"""grounding/exemplar_reduce.py — collapse a large DATA-bearing REPEATED array in the stored skeleton to ONE exemplar.
[fixes the card-5/24 l2_emit OUTPUT timeout — the AI copies the whole N-frame cube it is shown]

Two cards ship a default payload whose bulk is one identical-shaped list replicated N times:
  · card 5  heatmap.history  = list[12] frames  (each a sections × feeders grid)
  · card 24 timeline.periods = list[8]  periods (each a 10-panel snapshot)
The AI is SHOWN card_payloads.payload_stripped (layer2/emit/user_message.py) and told to author every key BYTE-IDENTICAL,
so it copies all N frames — ~11K output tokens, ~450s to generate → the emit blows the 150s l2_emit budget → the card
times out → renders blank ("piece unavailable"). The N frames are pure Storybook fixture: at render the roster
interpreter (ems_exec/executor/roster.py) WHOLESALE-REBUILDS the array from real ems data, independent of how many the
AI emitted (card 5 replace='wholesale'; card 24 repeat='snapshot_per_period' fans the member-built list into each
period). So the skeleton only needs to show the frame SHAPE ONCE — the AI copies one exemplar, the executor rebuilds N.

This reduces the STORED skeleton (build-time, in scripts/build_stripped_payloads.py) — the single source of truth the AI
copies. It touches nothing structural: split()/gates treat the array as one $DATA slot (count-agnostic), producer sets
the data leaf to None, and the executor rebuilds N from ems. Generic + DB-driven (no card ids): only a repeated array
whose elements each carry a `series` DATA leaf and that EXCEEDS the threshold is collapsed — that is exactly cards 5/24
today. Chrome-only repeated arrays (metricTabs, statusLegend, threshold stops) carry no series leaf → left untouched
(they render byte-identical from the default). KEEP ONE exemplar, never [] — card 24's `[*]` repeat fans into an
EXISTING array element; an empty array would have nothing to fan into.
"""
import copy
import re

from config.app_config import cfg
from validate.leaf_classify import classify


def _norm(path):
    return re.sub(r"\[\d+\]", "[*]", path)


def reduce_repeated(stored_skeleton, raw_payload):
    """Deep-copy `stored_skeleton` and collapse each DATA-bearing repeated array (list of >threshold dicts that
    DIRECTLY contains a `series` data leaf) to a SINGLE exemplar element. `classify` runs on the RAW payload (it has the
    real values needed to detect a series). The executor rebuilds all N frames live from ems, so this loses no rendered
    data; chrome-only repeated arrays (no series leaf) are left byte-identical. Never mutates the input."""
    thr = int(cfg("emit.repeated_exemplar_threshold", 6))
    series = {_norm(d["path"]) for d in (classify(raw_payload).get("data_leaves") or [])
              if d.get("kind") == "series"}
    out = copy.deepcopy(stored_skeleton)

    def walk(o, path):
        if isinstance(o, list) and len(o) > thr and all(isinstance(x, dict) for x in o):
            marker = _norm(path) + "["                                  # a series leaf sits DIRECTLY under this array
            if any(s.startswith(marker) for s in series):
                del o[1:]                                               # keep ONE exemplar; executor rebuilds N live
                return                                                 # do NOT recurse into it — keep its shape intact
        if isinstance(o, dict):
            for k, v in o.items():
                walk(v, f"{path}.{k}" if path else k)
        elif isinstance(o, list):
            for i, v in enumerate(o):
                walk(v, f"{path}[{i}]")

    walk(out, "")
    return out
