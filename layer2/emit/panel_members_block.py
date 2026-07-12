"""layer2/emit/panel_members_block.py — VERBATIM panel-membership facts for the Layer-2 user message. [PCC-1 polish]

Single concern: when the resolved asset is a PANEL (an aggregate device with topology members), render its REAL member
meters — supply side (incomers: transformers / solar) + fed feeders (outgoers) — as verbatim facts
(name | gic table | has_data | last=<newest sample ts>) from data.neuract_live.members, so the AI grounds per-source / per-feeder claims (a
roster or sankey card's entity labels, per-member honest-blanks, the data_note) in the actual topology instead of
guessing "per-source breakdown is not measured" (the PCC-1 loop1 defect: the supply members exist in topology; only
their tables are dark). FACTS ONLY — no suggestions, no vocabulary, no ranking; has_data is measured (the member table's
latest row carries at least one real value). Non-panel asset / registry outage → "" (block omitted, honest-degrade).
"""
from functools import lru_cache
from layer1b.resolve.member_scope import OUTGOING, INCOMER


def _member_has_data(table):
    """True iff the member's gic_* table has a latest row with ANY real (non-null) value — a measured liveness fact
    (a row of all-NULLs, e.g. the solar incomers, is honestly dark). Outage/empty/missing → False."""
    if not table:
        return False
    try:
        from ems_exec.data import neuract as _nx
        cols = sorted(_nx.present_columns(table))
        if not cols:
            return False
        row = _nx.latest(table, cols) or {}
        return any(v is not None for v in row.values())
    except Exception:
        return False


def _member_last_ts(table):
    """The member table's newest sample timestamp (ISO string) or None — the per-member DATA WINDOW fact [C3]: the AI
    anchors a member-scope range to the members' own last samples, not wall-clock 'today' (the 28/38 empty-window
    family), and a stale member is visibly stale. Outage/empty → None (fact omitted, honest-degrade)."""
    if not table:
        return None
    try:
        from ems_exec.data import neuract as _nx
        ts = _nx.latest_ts(table)
        return str(ts) if ts else None
    except Exception:
        return None


def _member_suffix(tbl):
    """' | aka=… | breaker_a=… | load_profile=…' equipment-registry hints for one member line [stream C] — '' on
    miss/knob-off/outage so the line stays byte-identical to pre-wiring. Canonical member name stays FIRST."""
    try:
        from layer2.emit.equipment_facts import member_suffix
        return member_suffix(tbl)
    except Exception:
        return ""


def _section_suffix(tbl):
    """' | section=1A' — the member's bus-section token [sections overlay]: the AI splits series/elements per section
    (roster series_split match {"sections": [...]}) when the prompt compares bus sections ('pcc 1a and pcc 1b'). ''
    on unmapped/outage so the line stays byte-identical for unsectioned plants."""
    try:
        from data.equipment.sections import section_of
        s = section_of(tbl)
        return f" | section={s}" if s else ""
    except Exception:
        return ""


def _lines(members):
    out = []
    for m in members:
        tbl = m.get("neuract_table")
        last = _member_last_ts(tbl)
        out.append(f"    {m.get('name')} | table={tbl or '(no table)'} | "
                   f"has_data={'Y' if _member_has_data(tbl) else 'N'} | last={last or '—'}"
                   f"{_section_suffix(tbl)}{_member_suffix(tbl)}")
    return out


@lru_cache(maxsize=128)
def _block_for(mfm_id, scope):
    try:
        from data.neuract_live import members as _members
        supply = _members.incomers_of(mfm_id) or []
        feeders = _members.outgoers_of(mfm_id) or []
    except Exception:
        return ""
    if not (supply or feeders):
        return ""
    # PANEL READING DIRECTION [panel_overview]: the resolved asset's member_scope picks WHICH side is THIS page's
    # readings — 'outgoing' (fed feeders/bays, the default) or 'incomer' (supply/source). The chosen side is the PRIMARY
    # set the page's cards fill from; the other side stays as grounding context (a member may report on either side).
    incomer_primary = (scope == INCOMER)
    primary_label = ("supply side / INCOMERS (feed the panel)" if incomer_primary
                     else "fed feeders / OUTGOING bays (the panel supplies)")
    context_label = ("fed feeders / OUTGOING bays (the panel supplies)" if incomer_primary
                     else "supply side / INCOMERS (feed the panel)")
    primary_members = supply if incomer_primary else feeders
    context_members = feeders if incomer_primary else supply
    parts = ["PANEL MEMBERS (verbatim topology facts — this asset is an AGGREGATE PANEL; its own table is a stub and "
             "every real number lives on the member meters below; has_data=Y ⇒ that member reports live, N ⇒ dark → "
             "honest-blank its slots; last=<ts> is that member's newest logged sample — anchor a member-scope "
             "range/window to it, never wall-clock 'today'):",
             f"  ▶ PRIMARY — {primary_label} — THIS PAGE'S READINGS aggregate/roster from THESE members "
             f"(the prompt asked for the {'INCOMER/supply' if incomer_primary else 'OUTGOING/distribution'} side):"]
    parts += _lines(primary_members) or ["    (none mapped in topology)"]
    if context_members:
        parts.append(f"  · context only — {context_label} (do NOT fill the page's readings from these unless a card's "
                     f"own role names them):")
        parts += _lines(context_members)
    parts.append("  Per-member values are measured PER MEMBER TABLE above; the panel-aggregate renderer fills "
                 "per-member roster/sankey/feeder leaves from the PRIMARY members' own rows. Leave per-entity slots "
                 "column=null (honest-blank) instead of duplicating a panel-total column into them, and never claim "
                 "'per-source breakdown is not measured' when a PRIMARY member above says has_data=Y.")
    return "\n".join(parts)


def panel_members_block(asset):
    """The rendered PANEL MEMBERS block for a panel asset, or '' (non-panel / no members / outage). Honors the resolved
    asset's member_scope ('outgoing' default / 'incomer') so the PRIMARY reading side matches the prompt."""
    if not (isinstance(asset, dict) and asset.get("has_feeders") and asset.get("mfm_id")):
        return ""
    try:
        return _block_for(int(asset["mfm_id"]), asset.get("member_scope") or OUTGOING)
    except (TypeError, ValueError):
        return ""
