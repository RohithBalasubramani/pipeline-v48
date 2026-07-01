"""seed_topology — DUMMY feeder topology.

GOAL DB    = target_version1 (ems_backend MFM.outgoing / MFM.incoming on :5433) — the consumers fan out over these.
REFERENCE  = lt_panels_db (the redundant DB, read once locally) — ONLY for the parent→child hierarchy SHAPE.
NODES      = the REAL neuract assets in target_version1; the reference's logical nodes are mapped onto them:
               · feeders / leaves      → direct name match (neuract name = "GIC-..-" + the reference name)
               · "PCC Panel N A|B"      → the real PCC-Panel-N asset
               · "Transformer N"        → the real …(Transformer-0N) asset
               · "HT Panel M1|M2"       → the real …HT Panel-M1|M2 asset
               · "Main HT Panel"        → the real …11KV HT DG Incomer
Best-effort + documented; it lights up the panel-overview / energy-distribution / Sankey feeder views. lt_panels_db is
NOT a runtime dependency (read once here). REMOVE once real topology is produced into app_device_topology.

  python manage.py seed_topology            # wire MFM.outgoing/incoming
  python manage.py seed_topology --wipe     # clear existing edges first
"""
import re
from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db import transaction

from lt_panels.data_db_link import default_db_link   # noqa: F401 — bootstraps pipeline_v48 onto sys.path
from lt_panels.models import MFM
from data.db_client import q


def _norm(s):
    return re.sub(r"[^a-z0-9]+", "", str(s).lower())


class Command(BaseCommand):
    help = "Seed dummy feeder topology (MFM.outgoing/incoming) from the lt_panels_db hierarchy onto real neuract assets."

    def add_arguments(self, parser):
        parser.add_argument("--wipe", action="store_true", help="clear existing outgoing/incoming edges first")

    def handle(self, *args, **opts):
        mfms = list(MFM.objects.all())
        bynorm = {}
        for m in mfms:
            bynorm.setdefault(_norm(m.name), m)

        def direct(name):
            nm = _norm(name)
            if nm in bynorm:
                return bynorm[nm]
            for k, m in bynorm.items():
                if nm and k.endswith(nm):           # neuract name = "GIC-..-" + reference name → suffix
                    return m
            return None

        def contains(sub):
            s = _norm(sub)
            hits = sorted((m for k, m in bynorm.items() if s in k), key=lambda m: m.id)
            return hits[0] if hits else None

        def resolve(name):                          # parent side: feeders direct; aggregates → their real home asset
            m = direct(name)
            if m:
                return m
            n = name.lower()
            mm = re.search(r"pcc panel\s*(\d)", n)
            if mm:
                return direct(f"PCC-Panel-{mm.group(1)}") or contains(f"pccpanel{mm.group(1)}")
            mm = re.search(r"transformer\s*(\d)", n)
            if mm:
                return contains(f"transformer-0{mm.group(1)}")
            if "ht panel m1" in n or "ht panel-m1" in n:
                return contains("ht panel-m1")
            if "ht panel m2" in n or "ht panel-m2" in n:
                return contains("ht panel-m2")
            if "main ht" in n:
                return contains("ht dg incomer")
            return None

        edges = q("lt_panels_db",
                  "SELECT p.name, c.name FROM lt_mfm_outgoing o "
                  "JOIN lt_mfm p ON p.id=o.from_mfm_id JOIN lt_mfm c ON c.id=o.to_mfm_id ORDER BY 1,2")

        wired = defaultdict(set)
        unresolved = set()
        with transaction.atomic():
            if opts["wipe"]:
                for m in mfms:
                    m.outgoing.clear()
                    m.incoming.clear()
            for pn, cn in edges:
                p = resolve(pn)
                c = resolve(cn)                     # children can also be intermediate aggregates (Transformer N, PCC Panel N)
                if not p:
                    unresolved.add(("parent", pn)); continue
                if not c:
                    unresolved.add(("child", cn)); continue
                if p.id == c.id:
                    continue
                p.outgoing.add(c)
                c.incoming.add(p)
                wired[p.name].add(c.name)

        self.stdout.write(self.style.SUCCESS(
            f"wired {sum(len(v) for v in wired.values())} edges across {len(wired)} parent assets"))
        for pn, cs in sorted(wired.items(), key=lambda kv: -len(kv[1]))[:14]:
            self.stdout.write(f"  {pn[:46]:46} → {len(cs)} feeders")
        if unresolved:
            self.stdout.write(self.style.WARNING(
                "unresolved nodes: " + ", ".join(sorted(f"{t}:{n}" for t, n in unresolved))[:400]))
