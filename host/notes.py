"""host/notes.py — the serve-boundary pieces BOTH host entrypoints share (single + multi-asset), so neither imports
the other. Home moved out of host/server.py: multi_asset needed SB_BASE + _attach_l2_notes and the only way in was a
lazy `from host.server import …` — a two-way server↔multi_asset import cycle. [cycle-kill 2026-07-12]"""
import os

from config.app_config import cfg

# Storybook base: env wins (bootstrap wiring), then the DB knob, then the LAN default (house pattern: DB → env → default
# is _insight's order; here env-first is kept because the run scripts already export STORYBOOK_URL).
SB_BASE = (os.environ.get("STORYBOOK_URL") or cfg("host.storybook_url", "http://100.90.185.31:6008")).rstrip("/")


def _attach_l2_notes(cards, l2):
    """B1 [residual 'fe' — invisible proxy notes]: attach Layer 2's card-level honesty disclosures to each served card
    as ADDITIVE fields. _enrich_card's whitelist dropped them — e.g. r_44796d791a card 70's 'kWh shown as a proxy for
    run-hours' data_note reached only the page-level notes.loop1, never the card the FE renders — so every emitted
    proxy/substitution note was invisible on the card itself.
      data_note        — the emit's plain-words proxy/substitution/blank explanation. Canonical home = the Layer 2
                         output's TOP level (layer2/build.py `out['data_note']`); falls back to the emit-variance
                         location inside data_instructions (the model sometimes nests it there — see r_44796d791a
                         card 71). Whitespace-only / non-string → None (honest, never fabricated).
      l2_answerability — Layer 2's OWN full/partial/none claim. Telemetry beside the verdict: render.answerability
                         (derived from the completed payload by validate/render_verdict) stays the single source of
                         truth; this is the AI's claim, served so a disagreement is visible.
    Generic (no card ids), additive (no existing field moves). Mutates + returns `cards`."""
    for c in cards or []:
        l2o = (l2 or {}).get(c.get("card_id")) or {}
        note = l2o.get("data_note") or (l2o.get("data_instructions") or {}).get("data_note")
        c["data_note"] = note.strip() if isinstance(note, str) and note.strip() else None
        c["l2_answerability"] = l2o.get("answerability")
    return cards


def window_from_preset(preset):
    """route-1a-timewindow: a prompt-derived TIME_WINDOWS preset ('last-7-days') → a concrete FE-vocabulary date_window
    {range,start,end,sampling}, or None. Mirrors the FE date-wiring (host/web/.../date-wiring.ts): the `range` TOKEN is
    the preset itself; start/end are the resolved span in the SITE timezone; sampling maps the preset's bucket to the FE
    sampling vocab. Start is computed by REUSING the executor's own ems_exec.window_policy._range_start (the SAME
    calendar-anchor / TIME_WINDOWS-lookback / last-N logic exec uses to honor a declared range) so the host default and
    the exec reads can never disagree. None in / unknown preset / any failure → None (the page keeps today/latest,
    unchanged). Never raises. HOME here (not server.py) so the multi-asset path applies the SAME prompt-derived
    default — api-design H4: 'compare A and B last week' used to fill with date_window=None. [2026-07-12]"""
    if not preset:
        return None
    try:
        from config.windows import TIME_WINDOWS, site_tz
        spec = (TIME_WINDOWS or {}).get(str(preset))
        if not spec:
            return None
        from ems_exec.executor.window_policy import _range_start   # reuse the canonical range→start resolver (no dup math)
        from replay.clock import now as _replay_now                # frozen to the original instant during a replay
        now = _replay_now(site_tz())
        start = _range_start(str(preset), now)
        if start is None:
            return None
        bucket = str(spec.get("bucket", "hour")).strip().lower()
        sampling = {"minute": "minute", "15 min": "minute", "hour": "hourly",   # [RC5] minute/15-min → sub-hour sampling
                    "day": "day", "week": "week"}.get(bucket, "hourly")
        return {"range": str(preset), "start": start.isoformat(), "end": now.isoformat(), "sampling": sampling}
    except Exception:
        return None
