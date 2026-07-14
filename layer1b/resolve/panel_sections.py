"""layer1b/resolve/panel_sections.py — the prompt/panel BUS-SECTION facts + the ONE stamping site. [sections]

A PCC panel is ONE registry row with TWO bus sections (A/B — cmd_catalog.pcc_panel_alias.section marks which alias
names which). This module answers, deterministically from the alias dictionary: which section does the PROMPT
address (panel_section), is the prompt a SECTION COMPARE (compare_sections), and stamps the resolved-asset facts
(stamp_section_facts — member_scope + section + compare_sections) that the pinned path and _finish used to
duplicate inline (asset_resolve, pre-2026-07-14).

AI-FIRST SEAM [T0-9, flag resolver.section_ai]: stamp_section_facts accepts the RESOLVER MODEL'S own `section`
emission ('A'/'B'/'both'/'none'). The AI owns the prompt's MEANING; this module VALIDATES the emission against the
pcc_panel_alias facts (the emitted section must be a real section of the resolved panel) and falls back to the
substring detector on any miss — the detector is the validator + reproducibility floor, never deleted. A
disagreement between a fact-valid AI answer and the detector is telemetry (section_ai_mismatch), and the AI wins
(it read the meaning; the detector provably misses elided spellings like 'compare pcc 1a and 1b'). [atomic]"""
from layer1b.normalize import norm as _norm  # the ONE asset-name match key (D9)
from layer1b.resolve.member_scope import member_scope


def pcc_section_index():
    """{normalized_alias: (canonical_panel_name, section)} for SECTIONED aliases only ('pcc-1b' → ('PCC-Panel-1','B')).
    The A/B are the panel's BUS SECTIONS — one registry row, two member sets (equipment.mfm.section). {} fail-open."""
    try:
        from data.db_client import q
        return {_norm(a): (pn, str(s).strip().upper())
                for a, pn, s in q("cmd_catalog",
                                  "SELECT alias, panel_name, section FROM pcc_panel_alias WHERE section IS NOT NULL")
                if a and pn and s}
    except Exception:
        return {}


def panel_section(prompt, panel_name):
    """The BUS SECTION the PROMPT addresses for `panel_name` — 'A'/'B' when EXACTLY ONE of that panel's sectioned
    aliases appears ('voltage for pcc-1b' → 'B'), None otherwise (unsectioned mention, or BOTH sections named — the
    compare path handles the two-section case). Deterministic prompt-derived stamp, the member_scope pattern. [sections]"""
    p = _norm(prompt)
    if not p or not panel_name:
        return None
    found = set()
    for al, (pn, sec) in pcc_section_index().items():
        if pn == panel_name and al in p:
            found.add(sec)
    return next(iter(found)) if len(found) == 1 else None


def compare_sections(prompt, panel_name):
    """The 2+ BUS SECTIONS the PROMPT compares for `panel_name` — sorted ['A','B'] when TWO OR MORE of that panel's
    sectioned aliases appear ('compare pcc 1a and pcc 1b'), None otherwise. The deterministic trigger the Layer-2 user
    message turns into the ★ BUS-SECTION COMPARE OVERLAY directive (the AI authors the per-section split; this stamp
    only states the FACT that the prompt is a section compare). [sections overlay]"""
    p = _norm(prompt)
    if not p or not panel_name:
        return None
    found = {sec for al, (pn, sec) in pcc_section_index().items() if pn == panel_name and al in p}
    return sorted(found) if len(found) >= 2 else None


def _sections_of(panel_name):
    """The REAL sections of `panel_name` per the alias dictionary — the fact the AI's emission is validated against."""
    return {sec for _al, (pn, sec) in pcc_section_index().items() if pn == panel_name}


def stamp_section_facts(asset, prompt, ai_section=None, ai_member_direction=None):
    """Mutate a RESOLVED-asset dict with the prompt facts every consumer reads: member_scope (incomer/outgoing),
    section ('A'/'B' single-section view), compare_sections (['A','B'] section compare). The ONE stamping site
    (pinned path + _finish both call here).

    `ai_section` — the resolver model's own emission ('A'/'B'/'both'/'none'; None = not emitted / flag off / pinned
    path where no LLM ran). VALIDATE-then-trust: a fact-valid emission wins (the AI read the meaning); anything
    invalid/absent falls back to the substring detector (the deterministic floor). 'none' still runs the detector —
    an explicit AI no-section must not suppress a detector hit silently (disagreement = telemetry, detector wins on
    'none' because a spelled alias is a FACT in the prompt).

    `ai_member_direction` [T1-10] — the model's reading-side emission ('incomer'/'outgoing'; None off/pinned). Enum-
    clamped by the caller; wins over the keyword scan when present, with the scan kept as the validator/fallback and
    a disagreement recorded (member_direction_disagree telemetry). ONE stamped `member_scope` value — both the emit
    facts (panel_members_block) and the executor fill (members.role_filter_for) read it (dual-consumer parity)."""
    if not isinstance(asset, dict):
        return
    kw_dir = member_scope(prompt)
    if ai_member_direction in ("incomer", "outgoing"):
        asset["member_scope"] = ai_member_direction
        if ai_member_direction != kw_dir:
            _note_dir_mismatch(ai_member_direction, kw_dir, asset.get("name"))
    else:
        asset["member_scope"] = kw_dir
    det_sec = panel_section(prompt, asset.get("name"))
    det_cmp = compare_sections(prompt, asset.get("name"))
    sec, cmp_ = det_sec, det_cmp
    if ai_section in ("A", "B", "both"):
        valid = _sections_of(asset.get("name"))
        if ai_section == "both" and {"A", "B"} <= valid:
            sec, cmp_ = None, ["A", "B"]
        elif ai_section in valid:
            sec, cmp_ = ai_section, None
        # fact-invalid emission → detector result stands (validated fallback)
        if (sec, cmp_) != (det_sec, det_cmp) and (det_sec or det_cmp):
            _note_mismatch(ai_section, det_sec, det_cmp, asset.get("name"))
    if sec:
        asset["section"] = sec                      # bus-section view: 'pcc-1b' rolls SECTION B members only
    if cmp_:
        asset["compare_sections"] = cmp_            # section COMPARE fact → the L2 overlay directive [sections]


def _note_mismatch(ai_section, det_sec, det_cmp, panel_name):
    """AI-vs-detector disagreement telemetry (both produced an answer; the fact-valid AI one was kept)."""
    try:
        from obs.failures import record
        record("asset_resolve", "section_ai_mismatch",
               detail=f"ai={ai_section} detector={det_sec or det_cmp} panel={str(panel_name)[:40]}")
    except Exception:
        pass


def _note_dir_mismatch(ai_dir, kw_dir, panel_name):
    """AI-vs-keyword-scan reading-side disagreement telemetry (the enum-valid AI value was kept). [T1-10]"""
    try:
        from obs.failures import record
        record("asset_resolve", "member_direction_disagree",
               detail=f"ai={ai_dir} keyword={kw_dir} panel={str(panel_name)[:40]}")
    except Exception:
        pass
