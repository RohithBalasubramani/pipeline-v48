"""ems_compat/build_compat_views.py — generate ONE compat view per clean neuract electrical meter
(neuract.mfm_NNN) into schema `compat` of target_version1, from compat_view_template.sql.
So ems_backend consumers read neuract UNCHANGED (the impedance match lives in the view).

Run:  python3 build_compat_views.py        (needs psql on PATH; no Django)
View:  compat.cmp_mfm_NNN  with injected  panel_id = 'mfm_NNN'.
"""
import subprocess
from pathlib import Path

CONN = "postgresql://postgres@localhost:5432/target_version1"
TEMPLATE = Path(__file__).with_name("compat_view_template.sql").read_text()
# the SELECT statement body (everything from the top-level SELECT keyword onward)
SELECT_BODY = TEMPLATE[TEMPLATE.index("\nSELECT\n") + 1:]


def psql(sql):
    r = subprocess.run(["psql", CONN, "-v", "ON_ERROR_STOP=1", "-tA", "-c", sql],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip())
    return r.stdout.strip()


def main():
    psql("CREATE SCHEMA IF NOT EXISTS compat;")
    tables = [t for t in psql(
        "select table_name from information_schema.tables "
        "where table_schema='neuract' and table_name ~ '^mfm_[0-9]+$' order by table_name"
    ).splitlines() if t]
    made = 0
    for t in tables:
        nnn = t.split("_")[1]
        body = SELECT_BODY.replace("{NNN}", nnn).replace("{PANEL_ID}", t)
        psql(f"DROP VIEW IF EXISTS compat.cmp_{t}; CREATE VIEW compat.cmp_{t} AS {body}")
        made += 1
    print(f"created/updated {made} compat views (compat.cmp_mfm_NNN) over neuract.mfm_NNN")


if __name__ == "__main__":
    main()
