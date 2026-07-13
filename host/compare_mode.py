"""host/compare_mode.py — the AI decision for HOW to render a multi-comparand compare. [compare — mode]

Two modes coexist:
  · overlay — every card shows all comparands INLINE (one strip whose KPIs read per panel, one timeline with a
    series per panel, a panel-tagged table). The tight metric-by-metric comparison. [host/compare_overlay]
  · groups  — each panel renders as its OWN full stacked dashboard (the existing build_response_multi default).

The AI picks per prompt (a focused "compare voltage and current for panel 1 and 2" → overlay; "show panel 1 and
panel 2 dashboards" → groups). ONE cheap classification call; fail-open to overlay (the common intent). Simple."""
from config.app_config import cfg


_SYS = ("You choose how to render a comparison of several electrical panels/assets. Reply with EXACTLY one word: "
        "overlay OR groups.\n"
        "overlay = the user wants specific metrics/events compared side by side ACROSS the panels — one chart/strip/"
        "table per metric, each showing every panel together.\n"
        "groups = the user wants to SEE each panel's OWN full separate dashboard, stacked one after another.\n"
        "Default to overlay. Choose groups ONLY when the prompt clearly asks to view each panel's full or separate "
        "dashboard/overview (e.g. 'show the dashboards for', 'full view of each', 'separately').")


def compare_mode(prompt):
    """'overlay' | 'groups'. AI-decided (knob compare.mode_ai default on); deterministic fallback 'overlay'. Never raises."""
    if str(cfg("compare.mode_ai", "on")).strip().lower() in ("off", "0", "false", "no", ""):
        return "overlay"
    try:
        from llm.client import call_qwen
        r = call_qwen(_SYS, "Prompt: %s\nReply overlay or groups:" % (prompt or ""),
                      stage="compare_mode", on_error="empty")
        return "groups" if "group" in str(r or "").strip().lower() else "overlay"
    except Exception:
        return "overlay"
