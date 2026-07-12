"""tests/property/gen.py — the shared strategies + mutators for the property suite (generators ONLY, no asserts).

Each mutant family is keyed to the EXACT normalization of the seam under test, so the input-side equivalence holds BY
CONSTRUCTION and the assertion exercises the SYSTEM side — a regression in the pipeline's normalization breaks the
test, never the generator:
  · edge_mutants(base)  — per-char case flips + leading/trailing whitespace: the invariance class of .strip().lower()
                          (config/metrics.normalize_metric, the 1a parse clamps, knowledge kind casing).
  · norm_mutants(base)  — per-char case flips + punctuation/whitespace churn between the alphanumeric runs: the
                          invariance class of layer1b's _norm ('PCC Panel 2 A' == 'pcc-panel-2a' == 'PCCPANEL2A').
  · rng_* twins         — random.Random versions of the same mutations for the LIVE tier (seeded, no hypothesis
                          engine, so a live failure names its exact mutant string).
"""
import re
import string

from hypothesis import strategies as st

SEPS = " -_./,()"                # separator alphabet _norm strips ([^a-z0-9]+)

# generic fuzz text — prompt-ish/emission-ish junk (never an empty alphabet)
st_junk = st.text(alphabet=string.ascii_letters + string.digits + " -_.?", min_size=1, max_size=40)


def norm_key(s):
    """layer1b _norm mirrored for GENERATION-side classification (the test side imports the real one)."""
    return re.sub(r"[^a-z0-9]+", "", str(s).lower())


@st.composite
def edge_mutants(draw, base):
    """Case-flip every letter independently + pad leading/trailing whitespace: strip().lower()-equal to `base`."""
    flips = draw(st.lists(st.booleans(), min_size=len(base), max_size=len(base)))
    body = "".join((c.upper() if f else c.lower()) if c.isalpha() else c for c, f in zip(base, flips))
    lead = draw(st.text(alphabet=" \t", max_size=3))
    tail = draw(st.text(alphabet=" \t", max_size=3))
    return lead + body + tail


@st.composite
def norm_mutants(draw, base):
    """Rebuild `base` from its alphanumeric runs with random separators + per-char case flips: _norm-equal to `base`."""
    runs = re.findall(r"[a-z0-9]+", str(base).lower())
    if not runs:
        return str(base)
    total = sum(len(r) for r in runs)
    flips = draw(st.lists(st.booleans(), min_size=total, max_size=total))
    seps = draw(st.lists(st.text(alphabet=SEPS, max_size=2), min_size=len(runs) + 1, max_size=len(runs) + 1))
    out, i = [seps[0]], 0
    for r, sep in zip(runs, seps[1:]):
        chars = []
        for ch in r:
            chars.append(ch.upper() if (flips[i] and ch.isalpha()) else ch)
            i += 1
        out.append("".join(chars))
        out.append(sep)
    return "".join(out)


def rng_prompt_mutant(rng, prompt):
    """LIVE-tier PROMPT mutant: case flips + whitespace-run stretching ONLY (never deletes/merges word characters, so
    the sentence reads the same to a human — the invariance the router is supposed to honor)."""
    out = []
    for ch in str(prompt):
        if ch == " ":
            out.append(" " * rng.choice((1, 1, 2, 3)))
        elif ch.isalpha() and rng.random() < 0.5:
            out.append(ch.upper() if ch.islower() else ch.lower())
        else:
            out.append(ch)
    return "".join(out)


def rng_name_mutant(rng, name):
    """LIVE-tier ASSET-NAME mutant: separator churn + case flips (the _norm equivalence class, e.g. 'PCC-Panel-1' →
    'pcc panel 1'). Keeps at least SOME separator between runs so the name stays human-readable in the prompt."""
    runs = re.findall(r"[a-z0-9]+", str(name).lower())
    if not runs:
        return str(name)
    seps = [rng.choice((" ", "-", "_", " - ")) for _ in range(len(runs) - 1)]
    body = []
    for i, r in enumerate(runs):
        body.append("".join(ch.upper() if (ch.isalpha() and rng.random() < 0.5) else ch for ch in r))
        if i < len(seps):
            body.append(seps[i])
    return "".join(body)
