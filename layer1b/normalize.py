"""layer1b/normalize.py — THE asset-name match key (one concern; dedup D9, refactor campaign 2026-07-12).

'PCC Panel 2 A' == 'pcc panel 2a' == 'PCC-Panel-2A' — the space/punctuation/case-insensitive key that resolve,
compare-discriminators and spelling-recovery must all agree on (three drifted copies desynchronizing this key is the
exact bug class the full-name collision gate guarded against).

NOT the same concern as layer2/coherence._norm (whitespace-collapse) or the executor slugify — do not merge those.
"""
import re

_KEY = re.compile(r"[^a-z0-9]+")


def norm(s):
    """space/punctuation/case-insensitive match key: 'PCC Panel 2 A' == 'pcc panel 2a' == 'PCC-Panel-2A'."""
    return _KEY.sub("", str(s).lower())
