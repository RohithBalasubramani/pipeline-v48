"""layer1a/parse/window_default.py — clamp the 1a router's relative-time WINDOW to the config/windows preset vocab.

Single concern (the `window` sibling of metric_intent_defaults.clamp_metric_intent, added for the route-1a-timewindow
fix): map the router's `window` answer to exactly ONE config.windows.TIME_WINDOWS preset key, else None. None means "no
time range asked" — the "none"/null sentinel, an absent key, or any off-vocab token — and the host then keeps its
today/latest default UNCHANGED (a prompt with no time phrase must not force a window). The vocab is read from the SAME
config.windows.TIME_WINDOWS that route_schema.route_answer_schema pins the guided-decoding enum to, so the clamp can
never drift from the grammar (or the executor's window_policy). Never raises."""

# Non-vocabulary sentinels the router (or a legacy json_object reply) may emit for "no time mentioned".
_NONE_TOKENS = ("", "none", "null", "na", "n/a", "any", "all", "-")


def clamp_window(window):
    """The router's `window` → a valid TIME_WINDOWS preset key, or None (no / unknown / off-vocab time range).

    Mirrors clamp_metric_intent: DB-driven vocab, case-insensitive, default None on absent/invalid. Kept separate from
    the metric/intent clamp because it is the ONLY 1a field whose default is None (not a vocabulary member) — a missing
    metric/intent falls back to a real keyword, but a missing window is genuinely "no time asked"."""
    try:
        from config.windows import TIME_WINDOWS
        vocab = set((TIME_WINDOWS or {}).keys())
    except Exception:
        vocab = set()
    if window is None:
        return None
    w = str(window).strip().lower()
    if w in _NONE_TOKENS:
        return None
    return w if w in vocab else None
