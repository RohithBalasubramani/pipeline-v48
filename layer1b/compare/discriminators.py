"""layer1b/compare/discriminators.py — the normalized-name discriminator helpers for the multi-asset COMPARE path.

Relocated 2026-07-09 from the retired layer1b/resolve/name_collision.py (the deterministic asset-resolution collision
gate was DELETED — the AI owns the end-user candidate list now; see layer1b/resolve/asset_resolve.py). These two pure
helpers were the only part of that module still used, and only by the compare detector (compare/detect.py,
compare/resolve_names.py) to tell whether a compare prompt spells out a specific asset. ONE concern; never raises.
"""
import re


def _norm(s):
    """space/punctuation/case-insensitive match key: 'PCC Panel 2 A' == 'pcc panel 2a' == 'PCC-Panel-2A'."""
    return re.sub(r"[^a-z0-9]+", "", str(s).lower())


def _discriminators(name):
    """The normalized substrings that, if present in a prompt, mean the user fully specified THIS row:
      · the full registry name ('gic01n3ups01cl600kva'), and
      · the GIC-node prefix ('gic01n3') — the true unique location key, robust to rating suffixes the user won't type.
    The GIC prefix alone is unique across the registry (one asset per GIC node position), so a prompt carrying it names
    exactly one asset."""
    out = []
    full = _norm(name)
    if full:
        out.append(full)
    m = re.match(r"\s*(gic[-_ ]?\d+[-_ ]?n\d+)", str(name).lower())
    if m:
        out.append(_norm(m.group(1)))
    return out
