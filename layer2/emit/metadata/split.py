"""layer2/emit/metadata/split.py — split a card's harvested default payload into the METADATA tier (the AI authors
this as exact_metadata, byte-identical) and the DATA tier (the worker fills via data_instructions). [CONTRACTS §5a]

Name-rule (deterministic support): a subtree is DATA if it is a roster/series ARRAY (roster-named AND list-valued)
or an interaction-state seed scalar; everything else is METADATA. Far more faithful here than a pure type-classifier
(which mis-marks numeric thresholds/contracts as data). The AI is still the decider at emit; this drives what we
SHOW the AI + the byte-identity gate.
"""
import re

DATA_SLOT = "$DATA"   # placeholder shown to the AI where the worker fills

_ROSTER = re.compile(r"^(history|periods|samples|series|queue|buckets|points|spokes|nodes|links|"
                     r"segments|feeders|sources|consumers|incomers|outgoings|rows|breakdown)$", re.I)
_SEED = re.compile(r"^(metric|liveMode|cursor|selectedName|selected[A-Z]\w*)$")


def _is_data(key, value):
    if key is None:
        return False
    if _ROSTER.match(key) and isinstance(value, list):   # roster ONLY when actually an array
        return True
    if _SEED.match(key) and not isinstance(value, (list, dict)):  # interaction seed scalar
        return True
    return False


def split(payload):
    """Return (metadata_skeleton, data_paths). metadata_skeleton = payload with DATA subtrees elided to $DATA."""
    data_paths = []

    def walk(o, path, key):
        if _is_data(key, o):
            data_paths.append(path)
            return DATA_SLOT
        if isinstance(o, dict):
            return {k: walk(v, f"{path}.{k}" if path else k, k) for k, v in o.items()}
        if isinstance(o, list):
            return [walk(v, f"{path}[{i}]", None) for i, v in enumerate(o)]
        return o

    return walk(payload, "", None), data_paths


def metadata_paths(payload):
    """(metadata_leaf_paths, data_paths) — the leaves the byte-identity gate checks."""
    skel, data = split(payload)
    out = []

    def walk(o, path):
        if o == DATA_SLOT:
            return
        if isinstance(o, dict):
            for k, v in o.items():
                walk(v, f"{path}.{k}" if path else k)
        elif isinstance(o, list):
            for i, v in enumerate(o):
                walk(v, f"{path}[{i}]")
        else:
            out.append(path)
    walk(skel, "")
    return out, data
