"""ems_exec/executor/source_role_wall.py — the SOURCE-ROLE WALL [DEFECT 56(b) / c59; monoliths F10, 2026-07-12].

Extracted from measurable_resolve.py (the column resolver is one concern; the dedicated-vs-non-dedicated source-role
vocabulary + verdict is another, and the file's own history shows the parallel vocabulary already produced the c59
inputVoltageV false-blank). measurable_resolve re-exports byte-compatibly. NOTE (flagged, NOT bundled): the longer-
term consolidation onto domain/quantity_class as the ONE role vocabulary needs a DB-row migration + corpus-replay
parity proof — see monoliths.md F10. [atomic; DB-driven marker sets with code-default mirrors]"""
from __future__ import annotations

from config.failopen import cfg_safe as _cfg
from ems_exec.executor.measurable_resolve import _tokens

# ── SOURCE-ROLE WALL [DEFECT 56(b)] ───────────────────────────────────────────────────────────────────────────────────
# A voltage/current LABEL qualified by a NON-MEASURED SOURCE ROLE names a physically distinct sensing point this meter
# does NOT have. The meter measures its OWN OUTPUT — voltage_avg / current_avg ARE that measured (output) point, NOT a
# separate bypass / input / mains / utility / grid / source / incoming / line-side rail. So:
#     'Output Voltage'  → voltage_avg  (KEEP — the meter's own measured point)
#     'Bypass Voltage'  → []           (honest blank — this meter has no bypass sensor)
#     'Input/Mains/Utility/Grid/Source/Incoming/Line-side Voltage' → []  (a separate un-metered rail)
# Generic — a SOURCE-ROLE QUALIFIER SET, never a card-specific rule. Token-EXACT (word boundaries), so it never fires on
# an unrelated substring ('sourced', 'grinder', 'inputted' … don't tokenize to the role token). DB row (code-default
# mirror) measurable.nonmeasured_source_roles. Multi-word markers ('line side' / 'line-side') match an adjacent run.
#
# DEDICATED-SENSING rails ONLY [DEFECT c59 inputVoltageV]: this default set carries ONLY roles that name a physically
# distinct, DEDICATED-sensing rail this OUTPUT-metering MFM has NO column for (bypass / utility / grid / incoming /
# line-side / source). A NON-DEDICATED role — 'input' / 'line' / 'mains' — is the meter's OWN plain reading (voltage_avg
# / current_avg ARE the input/line reading), so an input* slot LEGITIMATELY fills from the bare column and must NOT be
# walled. The default therefore EXCLUDES 'input'/'mains' (they were mis-listed, silently false-blanking every input*
# leaf — the c59 inputVoltageV defect). 'source' stays (a distinct 'source-select' rail, never the plain input reading).
_NONMEASURED_SOURCE_ROLES_DEFAULT = [
    "bypass", "utility", "grid", "source", "incoming", "line side", "line-side", "lineside",
]
# NON-DEDICATED roles [DEFECT c59]: the meter's OWN plain reading. A label carrying ONLY one of these (and no dedicated
# rail role) fills from the bare voltage_avg / current_avg — the SAME `dedicated`:false roles the honest-blank gate's
# source_role_mismatch clears. Code-default carve-out; the authoritative verdict is the `dedicated`-aware authority
# below (source_role_mismatch), this list only guarantees the offline path also clears input/line/mains.
_NONDEDICATED_ROLE_MARKERS_DEFAULT = ["input", "line", "mains"]
# roles the meter DOES measure at its OWN terminals — never blocked even if a label pairs them with a rail word.
# DB-driven (measurable.measured_source_roles) with this code-default mirror: 'output' is the ONE self/measured role
# (mirrors layer2.quantity_class where is_non_output_source('output') is False). Onboard a new measured-role NAME by
# editing the row — no card-specific rule, no code change. NOT a hardcoded label set: the DB vocab is authoritative.
_MEASURED_ROLES_DEFAULT = ["output"]


def _measured_roles():
    raw = _cfg("measurable.measured_source_roles", _MEASURED_ROLES_DEFAULT)
    if not isinstance(raw, (list, tuple)) or not raw:
        raw = _MEASURED_ROLES_DEFAULT
    return {t for m in raw for t in _tokens(m)}


def _nonmeasured_source_role_markers():
    raw = _cfg("measurable.nonmeasured_source_roles", _NONMEASURED_SOURCE_ROLES_DEFAULT)
    if not isinstance(raw, (list, tuple)) or not raw:
        raw = _NONMEASURED_SOURCE_ROLES_DEFAULT
    return [tuple(_tokens(m)) for m in raw if _tokens(m)]


def _nondedicated_role_markers():
    raw = _cfg("measurable.nondedicated_source_roles", _NONDEDICATED_ROLE_MARKERS_DEFAULT)
    if not isinstance(raw, (list, tuple)) or not raw:
        raw = _NONDEDICATED_ROLE_MARKERS_DEFAULT
    return [tuple(_tokens(m)) for m in raw if _tokens(m)]


def _marker_hit(toks, seq):
    """True when the token sequence `seq` appears as an adjacent run in `toks` (token-exact, multi-word aware)."""
    if not seq:
        return False
    n = len(seq)
    for i in range(len(toks) - n + 1):
        if tuple(toks[i:i + n]) == seq:
            return True
    return False


def _is_nonmeasured_source_role(key):
    """True when the leaf/label `key` is qualified by a DEDICATED-SENSING SOURCE ROLE (bypass / utility / grid / incoming
    / line-side / source) that this OUTPUT-metering MFM has NO dedicated column for — so a voltage/current label there
    must honest-blank rather than bind the meter's OWN reading (DEFECT 56 'Average Bypass Voltage' ← voltage_avg). A
    label naming the MEASURED role ('output') is never blocked. Token-exact; never raises.

    DEDICATED-vs-NON-DEDICATED [DEFECT c59 inputVoltageV]: 'input' / 'line' / 'mains' are NON-DEDICATED roles — the
    meter's OWN plain reading (voltage_avg / current_avg ARE the input/line reading), so an input* slot LEGITIMATELY
    fills from the bare column and must NOT be walled. Only a role with its OWN distinct sensor blocks. This mirrors the
    exact `dedicated`-aware policy the honest-blank gate already uses (layer2.gates role_smear /
    quantity_class.source_role_mismatch), so the resolver and the gate agree: bypassVoltageV blanks, inputVoltageV keeps.

    AUTHORITY ORDER (DB-vocab first, then a getattr-guarded legacy backstop — this file NEVER hard-depends on a symbol
    the vocab agent may not have landed, and NEVER bakes a role label set in code):
      1. measured-role carve-out (measurable.measured_source_roles) — 'output' names the meter's own terminal → CLEAR.
      2. DEDICATED rail markers (measurable.nonmeasured_source_roles) present → BLOCK unconditionally, EVEN IF a
         non-dedicated token co-occurs (the dedicated rail wins) — the honest-blank.
      3. NON-DEDICATED markers (measurable.nondedicated_source_roles) present, no dedicated rail → CLEAR (the meter's own
         input/line/mains reading legitimately fills). Mirrors the `dedicated`:false roles the honest-blank gate's
         quantity_class.source_role_mismatch clears, so resolver and gate agree: bypassVoltageV blanks, inputVoltageV keeps.
      4. layer2.quantity_class.is_non_output_source(key) (getattr-guarded) — legacy non-dedicated-BLIND last resort,
         consulted ONLY to BLOCK a rail the DB markers missed (True → blocked). A False from it is NOT trusted to clear
         (it wrongly reports 'input' as non-output), so it can never over-blank the meter's own input/line/mains reading."""
    toks = _tokens(key)
    if not toks:
        return False
    if _measured_roles() & set(toks):
        return False                                           # 'output' is the meter's own measured terminal
    # NON-DEDICATED carve-out [DEFECT c59 inputVoltageV]: a label naming ONLY the meter's OWN plain reading (input /
    # line / mains) and NO dedicated rail role fills from the bare column — cleared FIRST so a mixed 'bypass input'
    # style label still blocks on its dedicated role below. Two agreeing authorities, either alone clears the leaf:
    #   (a) the `dedicated`-aware source_role_mismatch (getattr): a NON-dedicated 'input'/'line'/'mains' slot vs a
    #       source claiming no role returns (False, None); a DEDICATED role (bypass) returns (True, [...]).
    #   (b) the code-default non-dedicated marker set (measurable.nondedicated_source_roles) for the offline path.
    # A DEDICATED rail marker present → BLOCK unconditionally, EVEN IF a non-dedicated token co-occurs (a multi-word
    # 'line side' contains a bare 'line', 'bypass input' pairs bypass with input): the dedicated rail wins. Checked
    # FIRST so the non-dedicated carve-out below can never smuggle a dedicated-rail label past the wall.
    dedicated_hit = any(_marker_hit(toks, seq) for seq in _nonmeasured_source_role_markers())
    if dedicated_hit:
        return True
    # NON-DEDICATED carve-out [DEFECT c59 inputVoltageV]: no dedicated rail role is present, so a label naming ONLY the
    # meter's OWN plain reading (input / line / mains) fills from the bare column. Two agreeing authorities, either
    # alone clears the leaf: (a) the `dedicated`-aware source_role_mismatch (getattr) returns (False, None) for a
    # non-dedicated role; (b) the code-default non-dedicated marker set (measurable.nondedicated_source_roles) offline.
    if any(_marker_hit(toks, seq) for seq in _nondedicated_role_markers()):
        return False                                           # the meter's own input/line/mains reading legitimately fills
    # LAST RESORT (getattr-guarded): the legacy non-dedicated-BLIND is_non_output_source — trusted ONLY to BLOCK a rail
    # the marker set above missed (e.g. a future DB source_role_markers row). Reached only when NO non-dedicated marker
    # cleared the leaf, so it can never wrongly block the meter's own 'input' reading.
    try:
        from domain import quantity_class as _qc   # vocabulary home (layer2.quantity_class is its facade)
        _nonout = getattr(_qc, "is_non_output_source", None)
        if callable(_nonout) and _nonout(key) is True:
            return True
    except Exception:
        pass
    return False
