"""layer2/emit/morphmap/mode.py — the DEFAULT-OFF switch for the morph-map emit contract + the per-card
applicability gate. [ITEM 18 PREP]

ONE concern (atomic-structure rule): read the cmd_catalog app_config row `emit.morphmap_mode` with code-default
'off', and decide whether the morph-map metadata contract may be composed FOR A GIVEN CARD.

The live seam (emit._system composing morphmap/prompt.md instead of prompts/metadata.md + user_message flipping the
metadata header + build.py routing raw['morphs'] through producer.apply) is gated on TWO facts, both required:
  1. enabled()          — the DB row (code-default 'off') was deliberately flipped on; AND
  2. card_has_skeleton() — THIS card HAS a stored seedless skeleton to overlay the morphs onto
                           (card_payloads.payload_stripped, via catalog_row.default_payload).

WHY (2) matters: morph-map returns ONLY {"morphs":{path:value}} and NO exact_metadata. The producer overlays those
morphs on the STORED skeleton. A card with NO card_payloads row (no default_payload / no payload_stripped) has NO
skeleton to overlay — it is a NO-DEFAULT-PAYLOAD card that MUST author the FULL exact_metadata off the contract
example (build.py's else-branch + enforce_free_metadata; e.g. the AI-Summary narrative + Heatmap time-axis cards
8/160). Handing such a card the morphs-only prompt yields empty exact_metadata → build.py's
"no default payload + empty exact_metadata" error (the live A/B break). So morph-map applies ONLY to cards that HAVE
a stored skeleton; a no-dp card keeps the full-emit metadata.md wording even with the flag on.

MANDATE: default-path behavior is untouched while the row (and the code default) say 'off'."""
from config.app_config import cfg

_OFF = ("off", "", "0", "false", "no", "none")


def mode():
    """The configured morph-map mode string, normalized. 'off' (code default) unless the DB row says otherwise."""
    return str(cfg("emit.morphmap_mode", "off")).strip().lower()


def enabled():
    """True ONLY when the DB row was deliberately flipped ('on'/'shadow'/…) — absent row / outage / 'off' → False."""
    return mode() not in _OFF


def card_has_skeleton(card_in):
    """True when THIS card has a STORED seedless skeleton the producer can overlay morphs onto — i.e. its
    catalog_row.default_payload carries a non-null payload_stripped. This is the SAME fact build._finalize keys the
    morph-map path on (`dp` truthy AND `_stored is not None`), so the prompt the AI sees always agrees with the
    producer route its output takes.

    None card_in (unknown/generic context — no catalog_row) → True: the flag's intent stands and there is no
    no-default card to protect; the actual per-card gate runs on every real emit. A card whose dp exists but whose
    payload_stripped is NULL is treated as NO skeleton (False) — build.py falls through to the full path for it too."""
    if card_in is None:
        return True
    dp = (card_in.get("catalog_row") or {}).get("default_payload")
    return bool(dp) and dp.get("payload_stripped") is not None


def use_morphmap_metadata(card_in):
    """The ONE decision both emit._system() and user_message._build consult: compose the morph-map metadata contract
    for THIS card? True ONLY when the flag is on AND this card has a stored skeleton to overlay. A no-dp card returns
    False even with the flag on, so it authors full exact_metadata (full-emit metadata.md) and never errors."""
    return enabled() and card_has_skeleton(card_in)
