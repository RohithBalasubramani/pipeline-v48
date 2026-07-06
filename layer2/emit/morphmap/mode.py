"""layer2/emit/morphmap/mode.py — the DEFAULT-OFF switch for the morph-map emit contract. [ITEM 18 PREP]

ONE concern (atomic-structure rule): read the cmd_catalog app_config row `emit.morphmap_mode` with code-default
'off'. TODAY nothing on the default path consults this flag with any effect — the live seam (emit.py composing
morphmap/prompt.md instead of prompts/metadata.md + build.py routing raw['morphs'] through producer.apply) is
post-certification work; until then the flag exists so the seam lands as a one-line read, never a behavior change.
MANDATE: default-path behavior is untouched while the row (and the code default) say 'off'."""
from config.app_config import cfg

_OFF = ("off", "", "0", "false", "no", "none")


def mode():
    """The configured morph-map mode string, normalized. 'off' (code default) unless the DB row says otherwise."""
    return str(cfg("emit.morphmap_mode", "off")).strip().lower()


def enabled():
    """True ONLY when the DB row was deliberately flipped ('on'/'shadow'/…) — absent row / outage / 'off' → False."""
    return mode() not in _OFF
