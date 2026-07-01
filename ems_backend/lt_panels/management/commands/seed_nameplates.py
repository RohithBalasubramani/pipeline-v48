"""seed_nameplates — populate cmd_catalog.asset_nameplate for every neuract lt_mfm asset.

THE nameplate store V48 was missing (RN-01/02/05/07, DS-10, DID-03, VC-05). Rated/contract/nominal/role/section/class
per asset, so loading%/headroom/section cards render real numbers instead of a fabricated capacity:60 or a hardcoded dict.

Sources, in PRECEDENCE order (each row records which one supplied its rated_kva in `source`):
  1. cmd_equipment_table — DEVICE-EXACT: V48 table_name == cmd_equipment.public.mfm.table_name (82 gic_* tables match
                       exactly) → backend2's real engineering rated_capacity_kva. The reliable, authoritative join.
  2. name_parse         — the kVA/kVAR token is IN the neuract name itself ('CL:600KVA', '600 KVA UPS', '+600KVAR',
                       '750KVAR (APFCR-01)') via '(\\d+(?:\\.\\d+)?)\\s*k?VA(R)?' both orders + a '\\d+A' feeder grammar.
  3. cmd_equipment_name — fuzzy cross-ref by identity token (UPS-NN/TX-N/DG-N) or normalized name (last-resort real).
  4. none               — no real or parsed rating → honest NULL rated_kva (loading% honest-degrades). NO class_default
                       fabrication: a made-up denominator (the old 20000 for a 160 kVA incomer) is worse than a blank.
cmd_equipment is also THE source for role/section/asset_category (name_parse can't give those).

role/section/asset_category are filled from cmd_equipment cross-ref where matched, else inferred from the name class.
nominal_voltage_ll: LT assets 415 V, HT/11kV/33kV incomers by name token, else NULL (honest).

  python manage.py seed_nameplates          # upsert every asset_nameplate row + print the match-rate breakdown
  python manage.py seed_nameplates --wipe    # truncate first
"""
import re

from django.core.management.base import BaseCommand

from lt_panels.data_db_link import default_db_link   # noqa: F401 — bootstraps pipeline_v48 onto sys.path
from data.db_client import q


# ── normalization ───────────────────────────────────────────────────────────────────────────────────────────────
def _clean(s):
    """Control-char → space, collapse whitespace (fixes the HHF embedded-newline collision, RN-04)."""
    return re.sub(r"\s+", " ", re.sub(r"[\x00-\x1f]+", " ", str(s or ""))).strip()


def _norm(s):
    return re.sub(r"[^a-z0-9]+", "", _clean(s).lower())


# ── name-token grammars (RN-02) ─────────────────────────────────────────────────────────────────────────────────
_KVA_RE  = re.compile(r"(\d+(?:\.\d+)?)\s*k?va\b", re.I)          # '600KVA', '600 KVA', '20 kVA', 'CL:600KVA'
_KVAR_RE = re.compile(r"(\d+(?:\.\d+)?)\s*k?var\b", re.I)         # '+600KVAR', '750KVAR'
_AMP_RE  = re.compile(r"(\d+(?:\.\d+)?)\s*a\b", re.I)             # '300A' feeder current
_MVA_RE  = re.compile(r"(\d+(?:\.\d+)?)\s*mva\b", re.I)           # '20 MVA'


def _parse_kva(name):
    """Rated kVA parsed straight from the neuract name; prefers kVA, then MVA→kVA, then KVAR bank rating."""
    n = _clean(name)
    m = _MVA_RE.search(n)
    if m:
        return float(m.group(1)) * 1000.0
    m = _KVA_RE.search(n)
    if m:
        return float(m.group(1))
    m = _KVAR_RE.search(n)                     # APFCR/HHF bank: KVAR ≈ its kVA rating
    if m:
        return float(m.group(1))
    return None


def _parse_amp(name):
    m = _AMP_RE.search(_clean(name))
    return float(m.group(1)) if m else None


# ── class inference from the neuract name (fallback for role/section/category) ──────────────────────────────────
def _class_of(name):
    n = _clean(name).lower()
    if re.search(r"\bups\b", n):                    return "UPS"
    if re.search(r"apfc|kvar|\bhhf\b", n):          return "APFCR"
    if re.search(r"transformer|\btx-?\d", n):       return "Transformer"
    if re.search(r"pcc-?panel|pcc panel", n):       return "PCC-Panel"
    if re.search(r"\bdg-?\d|diesel", n):            return "DG"
    if re.search(r"solar", n):                      return "Solar"
    if re.search(r"bpdb", n):                       return "BPDB"
    if re.search(r"spare", n):                      return "Spare"
    if re.search(r"plc|feedback|_sch\b|scada", n):  return "SCADA"
    if re.search(r"incomer|33kv|11kv|grid", n):     return "Incomer"
    return "LT"


# nominal line-line voltage per class (V) — genuine engineering STANDARDS (LT 415, HT/transformer 11kV), used only for
# display context, NEVER as a loading% denominator. (There is deliberately NO class-default rated_kva: a fabricated
# denominator is worse than an honest blank — unrated assets get rated_kva=NULL and honest-degrade their loading%.)
_CLASS_NOMINAL_V = {           # nominal line-line voltage per class (V); None where genuinely unknown
    "UPS": 415.0, "APFCR": 415.0, "BPDB": 415.0, "LT": 415.0, "Solar": 415.0,
    "Transformer": 11000.0, "Incomer": 11000.0, "DG": 415.0,
}


class Command(BaseCommand):
    help = "Seed cmd_catalog.asset_nameplate from cmd_equipment.mfm cross-ref + name-token grammar + class defaults."

    def add_arguments(self, parser):
        parser.add_argument("--wipe", action="store_true", help="truncate asset_nameplate first")

    def handle(self, *args, **opts):
        # ── load the neuract registry (asset table + name) ──────────────────────────────────────────────────────
        #   schema-qualify (neuract.lt_mfm) — a leading `SET search_path` would echo a spurious ['SET'] result row.
        assets = q("target_version1",
                   "SELECT table_name, name FROM neuract.lt_mfm ORDER BY id")
        # ── load the cmd_equipment nameplate (302 rows: name/role/section/asset_category/rated + table_name) ──────
        equip = q("cmd_equipment",
                  "SELECT name, role, section, asset_category, rated_capacity_kva, table_name FROM public.mfm ORDER BY name")

        # index cmd_equipment by DEVICE-EXACT table_name (the reliable join — 82 gic_* tables match V48 exactly),
        # then by identity token (UPS-NN, TX-N, DG-N) AND by normalized name (fuzzy fallbacks).
        eq_by_table, eq_by_token, eq_by_norm = {}, {}, {}
        for row in equip:
            ename, erole, esec, ecat, erated, etable = row[0], row[1], row[2], row[3], row[4], row[5]
            rated = float(erated) if erated not in (None, "", "NULL") else None
            rec = {"role": erole, "section": esec, "category": ecat, "rated": rated}
            if etable:
                eq_by_table[str(etable).strip()] = rec                # device-exact: table_name == V48 table_name
            eq_by_norm.setdefault(_norm(ename), rec)
            for tok in _identity_tokens(ename):
                eq_by_token.setdefault(tok, []).append(rec)   # ALL candidates for the token (a token is ambiguous)

        # a neuract class → the cmd_equipment asset_category it should prefer (so an 'ups1' token picks the UPS row,
        # not a same-token LT-Panel incomer; a 'transformer1' picks the Transformer, not an HT feeder).
        _PREFER_CAT = {"UPS": "UPS", "Transformer": "Transformer", "APFCR": "APFC", "DG": "DG"}

        rows, stat = [], {"cmd_equipment_table": 0, "name_parse": 0, "cmd_equipment_name": 0, "none": 0}
        for table_name, name in assets:
            cls = _class_of(name)
            # DEVICE-EXACT cross-ref: V48 table_name == cmd_equipment.public.mfm.table_name (the reliable join, 82 gic_*).
            eq_table = eq_by_table.get(str(table_name).strip())
            # fuzzy cross-ref by identity token (class-consistent candidate preferred), then by full name — for
            # role/section/category (and last-resort rated) on assets with no table_name match.
            eq = None
            for tok in _identity_tokens(name):
                cands = eq_by_token.get(tok)
                if not cands:
                    continue
                want = _PREFER_CAT.get(cls)
                eq = next((c for c in cands if want and c["category"] == want), cands[0])
                break
            if eq is None:
                eq = eq_by_norm.get(_norm(name))

            src_rec  = eq_table or eq or {}
            role     = src_rec.get("role")     or _role_of(cls)
            section  = src_rec.get("section")  or _section_of(cls)
            category = src_rec.get("category") or cls
            nominal  = _CLASS_NOMINAL_V.get(cls)

            # rated_kva precedence: DEVICE-EXACT cmd_equipment(table_name) → name_parse → fuzzy cmd_equipment → NONE.
            # NO class_default: a fabricated denominator (the old 20000 for a 160 kVA incomer) is worse than an honest
            # blank (VC-05/RN-01) — the whole point of the store. Unrated → rated_kva=NULL → loading% honest-degrades.
            parsed = _parse_kva(name)
            if eq_table and eq_table.get("rated") is not None:
                rated, source = eq_table["rated"], "cmd_equipment_table"
            elif parsed is not None:
                rated, source = parsed, "name_parse"
            elif eq and eq.get("rated") is not None:
                rated, source = eq["rated"], "cmd_equipment_name"
            else:
                rated, source = None, "none"
            stat[source] += 1

            rows.append((table_name, _clean(name), rated, None, nominal, role, section, category, source))

        # ── upsert (idempotent) — ONE batched multi-row INSERT (not 320 subprocess round-trips) ────────────────────
        if opts["wipe"]:
            q("cmd_catalog", "TRUNCATE asset_nameplate")
        values = ",\n".join(
            f"({_v(r[0])},{_v(r[1])},{_n(r[2])},{_n(r[3])},{_n(r[4])},{_v(r[5])},{_v(r[6])},{_v(r[7])},{_v(r[8])})"
            for r in rows)
        q("cmd_catalog",
          "INSERT INTO asset_nameplate "
          "(asset_table, mfm_name, rated_kva, contracted_kva, nominal_voltage_ll, role, section, asset_category, source) "
          f"VALUES {values} "
          "ON CONFLICT (asset_table) DO UPDATE SET "
          "mfm_name=EXCLUDED.mfm_name, rated_kva=EXCLUDED.rated_kva, contracted_kva=EXCLUDED.contracted_kva, "
          "nominal_voltage_ll=EXCLUDED.nominal_voltage_ll, role=EXCLUDED.role, section=EXCLUDED.section, "
          "asset_category=EXCLUDED.asset_category, source=EXCLUDED.source")

        total = len(rows)
        self.stdout.write(self.style.SUCCESS(f"seeded {total} asset_nameplate rows"))
        self.stdout.write("  match-rate by rated_kva source:")
        for k in ("cmd_equipment_table", "name_parse", "cmd_equipment_name", "none"):
            pct = 100.0 * stat[k] / total if total else 0
            self.stdout.write(f"    {k:20} {stat[k]:4}  ({pct:5.1f}%)")
        real = stat["cmd_equipment_table"] + stat["name_parse"] + stat["cmd_equipment_name"]
        self.stdout.write(f"  REAL rated (no fabrication): {real}/{total} ({100.0*real/total:.1f}%); "
                          f"{stat['none']} honest-NULL (spare/panel/scada/unrated)")


# ── identity tokens shared across both DBs (UPS-01, TRANSFORMER-01, DG-1) ─────────────────────────────────────────
def _identity_tokens(name):
    n = _clean(name).lower()
    toks = []
    for m in re.finditer(r"ups\s*-?\s*(\d+)", n):
        toks.append(f"ups{int(m.group(1))}")
    for m in re.finditer(r"transformer\s*-?\s*(\d+)", n):
        toks.append(f"transformer{int(m.group(1))}")
    for m in re.finditer(r"\btx\s*-?\s*(\d+)\b", n):        # cmd_equipment writes 'Tx-1' for the same 'Transformer-01'
        toks.append(f"transformer{int(m.group(1))}")
    for m in re.finditer(r"\bdg\s*-?\s*(\d+)", n):
        toks.append(f"dg{int(m.group(1))}")
    return toks


def _role_of(cls):
    return {"Incomer": "incoming", "Solar": "incoming", "Transformer": "incoming",
            "Spare": "spare", "PCC-Panel": "outgoing"}.get(cls, "outgoing")


def _section_of(cls):
    return "HT" if cls in ("Incomer", "Transformer") else "LT"


# ── SQL literal helpers (quote text, NULL numerics) ──────────────────────────────────────────────────────────────
def _v(x):
    return "NULL" if x is None else "'" + str(x).replace("'", "''") + "'"


def _n(x):
    return "NULL" if x is None else str(float(x))
