"""
Static Electrical-Equipment hierarchy — single source of truth for the sidebar
tree under the "Equipment" section of the CMD frontend.

Mirrors the shape of `equipmentTree` in
`frontend/src/data/navTree.ts` (HT Panel → Transformers → PCC Panels →
UPS → Production Lines → Power Quality), with the HHF Breakers section and
every HHF reference stripped per spec.

Each node:
  id            stable identifier
  label         display label
  slug          url segment
  pathOverride  optional explicit route (else parent_path + slug)
  alwaysOpen    optional flag for non-collapsible group headers
  children      list of child nodes
"""

ELECTRICAL_EQUIPMENT_TREE = [
    {"id": "eq-overview", "label": "Overview", "slug": "overview",
     "pathOverride": "/equipment"},

    # ── HT Panels ────────────────────────────────────────────────────
    {
        "id": "eq-ht", "label": "HT Panels", "slug": "ht-panels",
        "pathOverride": "/electrical/ht-panels",
        "children": [
            {"id": "eq-ht-overview", "label": "Overview", "slug": "overview"},
            {"id": "eq-ht-rtcc",     "label": "RTCC Panel", "slug": "rtcc"},

            # ── 11KV HT Panel-01 ─────────────────────────────────────
            {"id": "eq-ht-11kv-01", "label": "11KV HT Panel-01", "slug": "11kv-ht-panel-01",
             "mfm_name": "Main HT Panel",
             "children": [
                {"id": "eq-ht-11kv-01-overview", "label": "Overview", "slug": "overview"},
                {"id": "eq-ht-11kv-01-in", "label": "Incomings", "slug": "incoming", "alwaysOpen": True, "children": [
                    {"id": "eq-ht-11kv-01-in-tx", "label": "HT Transformer 1", "slug": "ht-transformer-1"},
                    {"id": "eq-ht-11kv-01-in-dg", "label": "DG Sync Panel",    "slug": "from-dg-sync"},
                ]},
                {"id": "eq-ht-11kv-01-out", "label": "Outgoings", "slug": "outgoing", "alwaysOpen": True, "children": [
                    {"id": "eq-ht-11kv-01-out-m1", "label": "HT Panel-M1", "slug": "to-ht-m1", "mfm_name": "HT Panel M1"},
                    {"id": "eq-ht-11kv-01-out-m2", "label": "HT Panel-M2", "slug": "to-ht-m2", "mfm_name": "HT Panel M2"},
                ]},
            ]},

            # ── HT Panel-M1 ──────────────────────────────────────────
            {"id": "eq-ht-m1", "label": "HT Panel-M1", "slug": "panel-m1",
             "mfm_name": "HT Panel M1",
             "children": [
                {"id": "eq-ht-m1-overview", "label": "Overview", "slug": "overview"},
                {"id": "eq-ht-m1-in", "label": "Incomings", "slug": "incoming", "alwaysOpen": True, "children": [
                    {"id": "eq-ht-m1-in-src", "label": "11KV HT Panel-01", "slug": "from-11kv-01", "mfm_name": "Main HT Panel"},
                ]},
                {"id": "eq-ht-m1-out", "label": "Outgoings", "slug": "outgoing", "alwaysOpen": True, "children": [
                    {"id": "eq-ht-m1-og-1", "label": "OG T/F 1", "slug": "og-tf-1", "mfm_name": "Transformer 1"},
                    {"id": "eq-ht-m1-og-2", "label": "OG T/F 2", "slug": "og-tf-2", "mfm_name": "Transformer 2"},
                    {"id": "eq-ht-m1-og-3", "label": "OG T/F 3", "slug": "og-tf-3", "mfm_name": "Transformer 3"},
                    {"id": "eq-ht-m1-og-4", "label": "OG T/F 4", "slug": "og-tf-4", "mfm_name": "Transformer 4"},
                ]},
            ]},

            # ── HT Panel-M2 ──────────────────────────────────────────
            {"id": "eq-ht-m2", "label": "HT Panel-M2", "slug": "panel-m2",
             "mfm_name": "HT Panel M2",
             "children": [
                {"id": "eq-ht-m2-overview", "label": "Overview", "slug": "overview"},
                {"id": "eq-ht-m2-in", "label": "Incomings", "slug": "incoming", "alwaysOpen": True, "children": [
                    {"id": "eq-ht-m2-in-src", "label": "11KV HT Panel-01", "slug": "from-11kv-01", "mfm_name": "Main HT Panel"},
                ]},
                {"id": "eq-ht-m2-out", "label": "Outgoings", "slug": "outgoing", "alwaysOpen": True, "children": [
                    {"id": "eq-ht-m2-og-5", "label": "OG T/F 5", "slug": "og-tf-5", "mfm_name": "Transformer 5"},
                    {"id": "eq-ht-m2-og-6", "label": "OG T/F 6", "slug": "og-tf-6", "mfm_name": "Transformer 6"},
                    {"id": "eq-ht-m2-og-7", "label": "OG T/F 7", "slug": "og-tf-7", "mfm_name": "Transformer 7"},
                    {"id": "eq-ht-m2-og-8", "label": "OG T/F 8", "slug": "og-tf-8", "mfm_name": "Transformer 8"},
                    {"id": "eq-ht-m2-og-ac", "label": "Air Compressor", "slug": "air-compressor", "mfm_name": "Air Compressor (HT M2)"},
                ]},
            ]},

            # ── 11KV DG SYNC Panel ───────────────────────────────────
            {"id": "eq-ht-dg-sync", "label": "11KV DG SYNC Panel", "slug": "dg-sync-panel",
             "children": [
                {"id": "eq-ht-dg-sync-overview", "label": "Overview", "slug": "overview"},
                {"id": "eq-ht-dg-sync-in", "label": "Incomings", "slug": "incoming", "alwaysOpen": True, "children": [
                    {"id": "eq-ht-dg-sync-in-1", "label": "DG 1", "slug": "dg-1", "mfm_name": "Diesel Generator-01"},
                    {"id": "eq-ht-dg-sync-in-2", "label": "DG 2", "slug": "dg-2", "mfm_name": "Diesel Generator-02"},
                    {"id": "eq-ht-dg-sync-in-3", "label": "DG 3", "slug": "dg-3", "mfm_name": "Diesel Generator-03"},
                    {"id": "eq-ht-dg-sync-in-4", "label": "DG 4", "slug": "dg-4", "mfm_name": "Diesel Generator-04"},
                    {"id": "eq-ht-dg-sync-in-5", "label": "DG 5", "slug": "dg-5", "mfm_name": "Diesel Generator-05"},
                    {"id": "eq-ht-dg-sync-in-6", "label": "DG 6", "slug": "dg-6", "mfm_name": "Diesel Generator-06"},
                    {"id": "eq-ht-dg-sync-in-7", "label": "DG 7", "slug": "dg-7", "mfm_name": "Diesel Generator-07"},
                    {"id": "eq-ht-dg-sync-in-8", "label": "DG 8", "slug": "dg-8", "mfm_name": "Diesel Generator-08"},
                ]},
                {"id": "eq-ht-dg-sync-out", "label": "Outgoings", "slug": "outgoing", "alwaysOpen": True, "children": [
                    {"id": "eq-ht-dg-sync-out-1", "label": "DG Sync Outgoing 1", "slug": "out-1"},
                    {"id": "eq-ht-dg-sync-out-2", "label": "DG Sync Outgoing 2", "slug": "out-2"},
                ]},
            ]},
        ],
    },

    # ── PCC Panels ───────────────────────────────────────────────────
    {
        "id": "eq-pcc", "label": "PCC Panels", "slug": "pcc-panels",
        "pathOverride": "/electrical/pcc-panels",
        "children": [
            # ── PCC Panel 1 (split into A / B halves) ─────────────────
            {"id": "eq-pcc-p1a", "label": "PCC Panel 1 A", "slug": "panel-1a", "children": [
                {"id": "eq-p1a-overview", "label": "Overview", "slug": "overview"},
                {"id": "eq-p1a-in", "label": "Incoming", "slug": "incoming", "alwaysOpen": True, "children": [
                    {"id": "eq-p1a-in-s1", "label": "Solar Incomer-1",     "slug": "solar-incomer-1", "mfm_name": "solar incomer 1"},
                    {"id": "eq-p1a-in-t1", "label": "Incomer-1 (TF-01)",   "slug": "incomer-1",       "mfm_name": "Transformer 1"},
                ]},
                {"id": "eq-p1a-out", "label": "Outgoing", "slug": "outgoing", "alwaysOpen": True, "children": [
                    {"id": "eq-p1a-out-u1", "label": "UPS-01 CL:600KVA",            "slug": "ups-01"},
                    {"id": "eq-p1a-out-u2", "label": "UPS-02 CL:600KVA",            "slug": "ups-02"},
                    {"id": "eq-p1a-out-u3", "label": "UPS-03 CL:600KVA",            "slug": "ups-03"},
                    {"id": "eq-p1a-out-b1", "label": "BPDB-01 For Lamination-01&02", "slug": "bpdb-01"},
                ]},
                {"id": "eq-p1a-spare", "label": "Spare", "slug": "spare", "alwaysOpen": True, "children": [
                    {"id": "eq-p1a-sp1", "label": "Spare-01", "slug": "spare-01"},
                    {"id": "eq-p1a-sp2", "label": "Spare-02", "slug": "spare-02"},
                    {"id": "eq-p1a-sp3", "label": "Spare-06", "slug": "spare-06"},
                    {"id": "eq-p1a-sp4", "label": "Spare-07", "slug": "spare-07"},
                ]},
            ]},
            {"id": "eq-pcc-p1b", "label": "PCC Panel 1 B", "slug": "panel-1b", "children": [
                {"id": "eq-p1b-overview", "label": "Overview", "slug": "overview"},
                {"id": "eq-p1b-in", "label": "Incoming", "slug": "incoming", "alwaysOpen": True, "children": [
                    {"id": "eq-p1b-in-s2", "label": "Solar Incomer-2",     "slug": "solar-incomer-2", "mfm_name": "solar incomer 2"},
                    {"id": "eq-p1b-in-t2", "label": "Incomer-2 (TF-02)",   "slug": "incomer-2",       "mfm_name": "Transformer 2"},
                ]},
                {"id": "eq-p1b-out", "label": "Outgoing", "slug": "outgoing", "alwaysOpen": True, "children": [
                    {"id": "eq-p1b-out-u1", "label": "UPS-04 CL:600KVA",            "slug": "ups-04"},
                    {"id": "eq-p1b-out-u2", "label": "UPS-05 CL:600KVA",            "slug": "ups-05"},
                    {"id": "eq-p1b-out-u3", "label": "UPS-06 CL:600KVA",            "slug": "ups-06"},
                    {"id": "eq-p1b-out-b1", "label": "BPDB-02 For Lamination-03&04", "slug": "bpdb-02"},
                ]},
                {"id": "eq-p1b-spare", "label": "Spare", "slug": "spare", "alwaysOpen": True, "children": [
                    {"id": "eq-p1b-sp1", "label": "Spare-17", "slug": "spare-17"},
                    {"id": "eq-p1b-sp2", "label": "Spare-18", "slug": "spare-18"},
                    {"id": "eq-p1b-sp3", "label": "Spare-22", "slug": "spare-22"},
                    {"id": "eq-p1b-sp4", "label": "Spare-23", "slug": "spare-23"},
                ]},
            ]},

            # ── PCC Panel 2 (split into A / B halves) ─────────────────
            {"id": "eq-pcc-p2a", "label": "PCC Panel 2 A", "slug": "panel-2a", "children": [
                {"id": "eq-p2a-overview", "label": "Overview", "slug": "overview"},
                {"id": "eq-p2a-in", "label": "Incoming", "slug": "incoming", "alwaysOpen": True, "children": [
                    {"id": "eq-p2a-in-s1", "label": "Solar Incomer-1",   "slug": "solar-incomer-1", "mfm_name": "solar incomer 1"},
                    {"id": "eq-p2a-in-t1", "label": "Incomer-1 (TF-03)", "slug": "incomer-1",       "mfm_name": "Transformer 3"},
                ]},
                {"id": "eq-p2a-out", "label": "Outgoing", "slug": "outgoing", "alwaysOpen": True, "children": [
                    {"id": "eq-p2a-out-1",  "label": "Curing Line CSU-02",          "slug": "csu-02"},
                    {"id": "eq-p2a-out-2",  "label": "Axial Fan Panel-1",           "slug": "axial-1"},
                    {"id": "eq-p2a-out-3",  "label": "Utility Panel-1",             "slug": "util-1"},
                    {"id": "eq-p2a-out-4",  "label": "Canteen Building",            "slug": "canteen"},
                    {"id": "eq-p2a-out-5",  "label": "STP Panel",                   "slug": "stp"},
                    {"id": "eq-p2a-out-6",  "label": "AHU-5",                       "slug": "ahu-5"},
                    {"id": "eq-p2a-out-7",  "label": "MRPDB",                       "slug": "mrpdb"},
                    {"id": "eq-p2a-out-8",  "label": "AHU-6",                       "slug": "ahu-6"},
                    {"id": "eq-p2a-out-9",  "label": "AHU-7",                       "slug": "ahu-7"},
                    {"id": "eq-p2a-out-10", "label": "AHU-8",                       "slug": "ahu-8"},
                    {"id": "eq-p2a-out-11", "label": "Admin+IT+Other Emergency",    "slug": "admin-it"},
                    {"id": "eq-p2a-out-12", "label": "BPDB-03 For Lamination-05&06","slug": "bpdb-03"},
                ]},
                {"id": "eq-p2a-spare", "label": "Spare", "slug": "spare", "alwaysOpen": True, "children": [
                    {"id": "eq-p2a-sp1", "label": "Spare-11", "slug": "spare-11"},
                    {"id": "eq-p2a-sp2", "label": "Spare-12", "slug": "spare-12"},
                    {"id": "eq-p2a-sp3", "label": "Spare-14", "slug": "spare-14"},
                    {"id": "eq-p2a-sp4", "label": "Spare-24", "slug": "spare-24"},
                ]},
            ]},
            {"id": "eq-pcc-p2b", "label": "PCC Panel 2 B", "slug": "panel-2b", "children": [
                {"id": "eq-p2b-overview", "label": "Overview", "slug": "overview"},
                {"id": "eq-p2b-in", "label": "Incoming", "slug": "incoming", "alwaysOpen": True, "children": [
                    {"id": "eq-p2b-in-s2", "label": "Solar Incomer-2",   "slug": "solar-incomer-2", "mfm_name": "solar incomer 2"},
                    {"id": "eq-p2b-in-t2", "label": "Incomer-2 (TF-04)", "slug": "incomer-2",       "mfm_name": "Transformer 4"},
                ]},
                {"id": "eq-p2b-out", "label": "Outgoing", "slug": "outgoing", "alwaysOpen": True, "children": [
                    {"id": "eq-p2b-out-1",  "label": "FCBC",                         "slug": "fcbc-1"},
                    {"id": "eq-p2b-out-2",  "label": "Air Washer Exhaust-04",        "slug": "aw-ex-04"},
                    {"id": "eq-p2b-out-3",  "label": "Air Washer Exhaust-05",        "slug": "aw-ex-05"},
                    {"id": "eq-p2b-out-4",  "label": "Air Washer-5",                 "slug": "aw-5"},
                    {"id": "eq-p2b-out-5",  "label": "Air Washer-6",                 "slug": "aw-6"},
                    {"id": "eq-p2b-out-6",  "label": "FCBC",                         "slug": "fcbc-2"},
                    {"id": "eq-p2b-out-7",  "label": "Air Washer Exhaust-06",        "slug": "aw-ex-06"},
                    {"id": "eq-p2b-out-8",  "label": "Electrical Room North Side",   "slug": "elec-north"},
                    {"id": "eq-p2b-out-9",  "label": "Frisking+Security",            "slug": "frisking"},
                    {"id": "eq-p2b-out-10", "label": "Axial Fan Panel-2",            "slug": "axial-2"},
                    {"id": "eq-p2b-out-11", "label": "Air Washer-4",                 "slug": "aw-4"},
                    {"id": "eq-p2b-out-12", "label": "MLDB",                         "slug": "mldb"},
                    {"id": "eq-p2b-out-13", "label": "BPDB-04 For Lamination-07&08", "slug": "bpdb-04"},
                ]},
                {"id": "eq-p2b-spare", "label": "Spare", "slug": "spare", "alwaysOpen": True, "children": [
                    {"id": "eq-p2b-sp1", "label": "Spare-26", "slug": "spare-26"},
                    {"id": "eq-p2b-sp2", "label": "Spare-27", "slug": "spare-27"},
                    {"id": "eq-p2b-sp3", "label": "Spare-29", "slug": "spare-29"},
                ]},
            ]},

            # ── PCC Panel 3 (split into A / B halves) ─────────────────
            {"id": "eq-pcc-p3a", "label": "PCC Panel 3 A", "slug": "panel-3a", "children": [
                {"id": "eq-p3a-overview", "label": "Overview", "slug": "overview"},
                {"id": "eq-p3a-in", "label": "Incoming", "slug": "incoming", "alwaysOpen": True, "children": [
                    {"id": "eq-p3a-in-t1", "label": "Incomer-1",       "slug": "incomer-1",       "mfm_name": "Transformer 5"},
                    {"id": "eq-p3a-in-s1", "label": "Solar Incomer-1", "slug": "solar-incomer-1", "mfm_name": "solar incomer 1"},
                ]},
                {"id": "eq-p3a-out", "label": "Outgoing", "slug": "outgoing", "alwaysOpen": True, "children": [
                    {"id": "eq-p3a-out-u1", "label": "UPS-07 CL:600KVA",            "slug": "ups-07"},
                    {"id": "eq-p3a-out-u2", "label": "UPS-08 CL:600KVA",            "slug": "ups-08"},
                    {"id": "eq-p3a-out-u3", "label": "UPS-09 CL:600KVA",            "slug": "ups-09"},
                    {"id": "eq-p3a-out-b1", "label": "BPDB-05 For Lamination-09&10", "slug": "bpdb-05"},
                ]},
                {"id": "eq-p3a-spare", "label": "Spare", "slug": "spare", "alwaysOpen": True, "children": [
                    {"id": "eq-p3a-sp1", "label": "Spare-01", "slug": "spare-01"},
                    {"id": "eq-p3a-sp2", "label": "Spare-02", "slug": "spare-02"},
                    {"id": "eq-p3a-sp3", "label": "Spare-06", "slug": "spare-06"},
                    {"id": "eq-p3a-sp4", "label": "Spare-07", "slug": "spare-07"},
                ]},
            ]},
            {"id": "eq-pcc-p3b", "label": "PCC Panel 3 B", "slug": "panel-3b", "children": [
                {"id": "eq-p3b-overview", "label": "Overview", "slug": "overview"},
                {"id": "eq-p3b-in", "label": "Incoming", "slug": "incoming", "alwaysOpen": True, "children": [
                    {"id": "eq-p3b-in-t2", "label": "Incomer-2",       "slug": "incomer-2",       "mfm_name": "Transformer 6"},
                    {"id": "eq-p3b-in-s2", "label": "Solar Incomer-2", "slug": "solar-incomer-2", "mfm_name": "solar incomer 2"},
                ]},
                {"id": "eq-p3b-out", "label": "Outgoing", "slug": "outgoing", "alwaysOpen": True, "children": [
                    {"id": "eq-p3b-out-u1", "label": "UPS-10 CL:600KVA",            "slug": "ups-10"},
                    {"id": "eq-p3b-out-u2", "label": "UPS-11 CL:600KVA",            "slug": "ups-11"},
                    {"id": "eq-p3b-out-u3", "label": "UPS-12 CL:600KVA",            "slug": "ups-12"},
                    {"id": "eq-p3b-out-b1", "label": "BPDB-06 For Lamination-11&12", "slug": "bpdb-06"},
                ]},
                {"id": "eq-p3b-spare", "label": "Spare", "slug": "spare", "alwaysOpen": True, "children": [
                    {"id": "eq-p3b-sp1", "label": "Spare-17", "slug": "spare-17"},
                    {"id": "eq-p3b-sp2", "label": "Spare-21", "slug": "spare-21"},
                    {"id": "eq-p3b-sp3", "label": "Spare-22", "slug": "spare-22"},
                ]},
            ]},

            # ── PCC Panel 4 (split into A / B halves) ─────────────────
            {"id": "eq-pcc-p4a", "label": "PCC Panel 4 A", "slug": "panel-4a", "children": [
                {"id": "eq-p4a-overview", "label": "Overview", "slug": "overview"},
                {"id": "eq-p4a-in", "label": "Incomings", "slug": "incoming", "alwaysOpen": True, "children": [
                    {"id": "eq-p4a-in-1", "label": "Incomer 1 from Transformer-7",   "slug": "incomer-1", "mfm_name": "Transformer 7"},
                    {"id": "eq-p4a-in-2", "label": "Incomer-2 from Solar Incomer-1", "slug": "incomer-2", "mfm_name": "solar incomer 1"},
                ]},
                {"id": "eq-p4a-out", "label": "Outgoings", "slug": "outgoing", "alwaysOpen": True, "children": [
                    {"id": "eq-p4a-og-01",    "label": "OG-1 to HHF-01 (Type-02), 300A+750kVAr",  "slug": "og-1-hhf-01",    "mfm_name": "HHF-01 (TYPE-02) 300A + 750KVAR"},
                    {"id": "eq-p4a-og-02",    "label": "OG-2 to AHU-1",                          "slug": "og-2-ahu-1",       "mfm_name": "AHU-1"},
                    {"id": "eq-p4a-og-03",    "label": "OG-3 to AHU-2",                          "slug": "og-3-ahu-2",       "mfm_name": "AHU-2"},
                    {"id": "eq-p4a-og-04",    "label": "OG-4 to Chiller and CHW, CWP-1",         "slug": "og-4-chiller-1",   "mfm_name": "Chiller & CHW, CWP-1"},
                    {"id": "eq-p4a-og-05",    "label": "OG-5 to Chiller and CHW, CWP-3",         "slug": "og-5-chiller-3",   "mfm_name": "Chiller & CHW, CWP-3"},
                    {"id": "eq-p4a-og-06",    "label": "OG-6 to Axial Fan Panel-2",              "slug": "og-6-axial-2",     "mfm_name": "Axial Fan Panel-2"},
                    {"id": "eq-p4a-og-07",    "label": "OG-7 to Utility Panel-2",                "slug": "og-7-util-2",      "mfm_name": "Utility Panel-02"},
                    {"id": "eq-p4a-og-08",    "label": "OG-8 to FCBC-3",                         "slug": "og-8-fcbc-3",    "mfm_name": "FCBC-3"},
                    {"id": "eq-p4a-og-09",    "label": "OG-9 to AHU-3",                          "slug": "og-9-ahu-3",       "mfm_name": "AHU-3"},
                    {"id": "eq-p4a-og-10",    "label": "OG-10 to Curing Line CSU-1",             "slug": "og-10-csu-1",      "mfm_name": "Curing Line CSU-01"},
                    {"id": "eq-p4a-og-11",    "label": "OG-11 to Electrical Room (External South Side)", "slug": "og-11-er-south", "mfm_name": "Electrical Room External-South"},
                    {"id": "eq-p4a-og-12",    "label": "OG-12 to FCBC-4",                        "slug": "og-12-fcbc-4",   "mfm_name": "FCBC-4"},
                    {"id": "eq-p4a-og-13",    "label": "OG-13 to FCBC-5",                        "slug": "og-13-fcbc-5",   "mfm_name": "FCBC-5"},
                    {"id": "eq-p4a-og-14-18", "label": "OG-14 to OG-18: Spare",                  "slug": "og-14-18-spare"},
                    {"id": "eq-p4a-og-19",    "label": "OG-19 to AHU-9 South Side",              "slug": "og-19-ahu-9",      "mfm_name": "AHU-9"},
                    {"id": "eq-p4a-og-20",    "label": "OG-20 to AHU-10 South Side",             "slug": "og-20-ahu-10",     "mfm_name": "AHU-10"},
                    {"id": "eq-p4a-og-21",    "label": "OG-21 to AHU-11 South Side",             "slug": "og-21-ahu-11",     "mfm_name": "AHU-11"},
                ]},
            ]},
            {"id": "eq-pcc-p4b", "label": "PCC Panel 4 B", "slug": "panel-4b", "children": [
                {"id": "eq-p4b-overview", "label": "Overview", "slug": "overview"},
                {"id": "eq-p4b-in", "label": "Incomings", "slug": "incoming", "alwaysOpen": True, "children": [
                    {"id": "eq-p4b-in-1", "label": "Incomer 1 from Transformer-8",   "slug": "incomer-1", "mfm_name": "Transformer 8"},
                    {"id": "eq-p4b-in-2", "label": "Incomer-2 from Solar Incomer-2", "slug": "incomer-2", "mfm_name": "solar incomer 2"},
                ]},
                {"id": "eq-p4b-out", "label": "Outgoings", "slug": "outgoing", "alwaysOpen": True, "children": [
                    {"id": "eq-p4b-og-01-02", "label": "OG-1 to OG-2: Spare",                "slug": "og-1-2-spare"},
                    {"id": "eq-p4b-og-03",    "label": "OG-3 to Air Washer-1",                "slug": "og-3-aw-1",        "mfm_name": "Air Washer-1"},
                    {"id": "eq-p4b-og-04",    "label": "OG-4 to Air Washer-2",                "slug": "og-4-aw-2",        "mfm_name": "Air Washer-2"},
                    {"id": "eq-p4b-og-05",    "label": "OG-5 to Air Washer-3",                "slug": "og-5-aw-3",        "mfm_name": "Air Washer-3"},
                    {"id": "eq-p4b-og-06",    "label": "OG-6 to AW Exhaust-1",                "slug": "og-6-aw-ex-1",     "mfm_name": "AW-EX-Panel-01"},
                    {"id": "eq-p4b-og-07",    "label": "OG-7 to AW Exhaust-2",                "slug": "og-7-aw-ex-2",     "mfm_name": "AW-EX-Panel-02"},
                    {"id": "eq-p4b-og-08",    "label": "OG-8 to AW Exhaust-3",                "slug": "og-8-aw-ex-3",     "mfm_name": "AW-EX-Panel-03"},
                    {"id": "eq-p4b-og-09",    "label": "OG-9 to AHU-4",                       "slug": "og-9-ahu-4",       "mfm_name": "AHU-4"},
                    {"id": "eq-p4b-og-10",    "label": "OG-10 to Chiller & CHW, CWP-2",       "slug": "og-10-chiller-2",  "mfm_name": "Chiller & CHW, CWP-2"},
                    {"id": "eq-p4b-og-11",    "label": "OG-11 to Chiller & CHW, CWP-4",       "slug": "og-11-chiller-4",  "mfm_name": "Chiller & CHW, CWP-4"},
                    {"id": "eq-p4b-og-12",    "label": "OG-12 to General Exhaust",            "slug": "og-12-gen-ex",     "mfm_name": "General Exhaust"},
                    {"id": "eq-p4b-og-13",    "label": "OG-13 to Axial Fan Panel-4",          "slug": "og-13-axial-4",    "mfm_name": "Axial Fan Panel-4"},
                    {"id": "eq-p4b-og-14",    "label": "OG-14 to Domestic Water Pump",        "slug": "og-14-dom-pump",   "mfm_name": "Domestic Water Pump"},
                    {"id": "eq-p4b-og-15",    "label": "OG-15 to Treated Water Pump",         "slug": "og-15-treat-pump", "mfm_name": "Treated Water"},
                    {"id": "eq-p4b-og-16",    "label": "OG-16 to Irrigation Water Pump",      "slug": "og-16-irr-pump",   "mfm_name": "Irrigation Water Pump"},
                    {"id": "eq-p4b-og-17",    "label": "OG-17 to Compressor Dryer",           "slug": "og-17-comp-dryer", "mfm_name": "Compressor Dryer"},
                    {"id": "eq-p4b-og-18",    "label": "OG-18 to Fire Fighting System",       "slug": "og-18-fire",       "mfm_name": "Fire Fighting System"},
                    {"id": "eq-p4b-og-19",    "label": "OG-19 to PDB For RM Warehouse",       "slug": "og-19-pdb-rm",     "mfm_name": "PDB For RM"},
                    {"id": "eq-p4b-og-20",    "label": "OG-20 to PDB for FG Warehouse",       "slug": "og-20-pdb-fg",     "mfm_name": "PDB For FG"},
                    {"id": "eq-p4b-og-21",    "label": "OG-21 to HHF-02 (Type-02), 300A+750kVAr", "slug": "og-21-hhf-02", "mfm_name": "HHF-02 (TYPE-02) 300A + 750KVAR"},
                    {"id": "eq-p4b-og-22",    "label": "OG-22 to PCW Panel",                  "slug": "og-22-pcw",        "mfm_name": "PCW Panel"},
                    {"id": "eq-p4b-og-23-28", "label": "OG-23 to OG-28: Spare",               "slug": "og-23-28-spare"},
                ]},
            ]},
        ],
    },

    # ── UPS Panels ───────────────────────────────────────────────────
    {
        "id": "eq-ups", "label": "UPS Panels", "slug": "ups",
        "pathOverride": "/electrical/ups",
        "children": [
            {"id": "eq-ups-overview", "label": "Overview", "slug": "overview",
             "pathOverride": "/electrical/ups"},

            # ── UPS Panel-1A ─────────────────────────────────────────
            {"id": "eq-ups-p1a", "label": "UPS Panel-1A", "slug": "panel-1a", "children": [
                {"id": "eq-ups-p1a-overview", "label": "Overview", "slug": "overview"},
                {"id": "eq-ups-p1a-in", "label": "Incomings", "slug": "incoming", "alwaysOpen": True, "children": [
                    {"id": "eq-ups-p1a-in-1", "label": "Incomer-1 from UPS-01 (600kVA)", "slug": "incomer-1", "mfm_name": "UPS-01 CL:600KVA"},
                    {"id": "eq-ups-p1a-in-2", "label": "Incomer-2 from UPS-02 (600kVA)", "slug": "incomer-2", "mfm_name": "UPS-02 CL:600KVA"},
                    {"id": "eq-ups-p1a-in-3", "label": "Incomer-3 from UPS-03 (600kVA)", "slug": "incomer-3", "mfm_name": "UPS-03 CL:600KVA"},
                    {"id": "eq-ups-p1a-in-4", "label": "Incomer-4 from UPS-04 (600kVA)", "slug": "incomer-4", "mfm_name": "UPS-04 CL:600KVA"},
                    {"id": "eq-ups-p1a-in-5", "label": "Incomer-5 from UPS-05 (600kVA)", "slug": "incomer-5", "mfm_name": "UPS-05 CL:600KVA"},
                    {"id": "eq-ups-p1a-in-6", "label": "Incomer-6 from UPS-06 (600kVA)", "slug": "incomer-6", "mfm_name": "UPS-06 CL:600KVA"},
                ]},
                {"id": "eq-ups-p1a-out", "label": "Outgoings", "slug": "outgoing", "alwaysOpen": True, "children": [
                    {"id": "eq-ups-p1a-out-pdb", "label": "PDB / Production Feeders", "slug": "pdb-feeders", "alwaysOpen": True, "children": [
                        {"id": "eq-ups-p1a-pdb-3", "label": "PDB-3 Packing Line-01",       "slug": "pdb-3", "mfm_name": "PDB-3 Packaging-01"},
                        {"id": "eq-ups-p1a-pdb-1", "label": "PDB-1 Pre Laminator Line-01", "slug": "pdb-1"},
                        {"id": "eq-ups-p1a-pdb-4", "label": "PDB-4 Post Laminator Line-01","slug": "pdb-4"},
                        {"id": "eq-ups-p1a-pdb-2", "label": "PDB-2 Pre Laminator Line-02", "slug": "pdb-2"},
                        {"id": "eq-ups-p1a-pdb-5", "label": "PDB-5 Post Laminator Line-02","slug": "pdb-5"},
                    ]},
                    {"id": "eq-ups-p1a-out-lam", "label": "UPS Supply Laminator Feeders", "slug": "laminator-feeders", "alwaysOpen": True, "children": [
                        {"id": "eq-ups-p1a-lam-3-1", "label": "UPS Supply Laminator-3.1", "slug": "lam-3-1"},
                        {"id": "eq-ups-p1a-lam-1-2", "label": "UPS Supply Laminator-1.2", "slug": "lam-1-2"},
                        {"id": "eq-ups-p1a-lam-2-2", "label": "UPS Supply Laminator-2.2", "slug": "lam-2-2"},
                        {"id": "eq-ups-p1a-lam-2-1", "label": "UPS Supply Laminator-2.1", "slug": "lam-2-1"},
                        {"id": "eq-ups-p1a-lam-3-2", "label": "UPS Supply Laminator-3.2", "slug": "lam-3-2"},
                        {"id": "eq-ups-p1a-lam-1-1", "label": "UPS Supply Laminator-1.1", "slug": "lam-1-1"},
                        {"id": "eq-ups-p1a-lam-4-1", "label": "UPS Supply Laminator-4.1", "slug": "lam-4-1"},
                        {"id": "eq-ups-p1a-lam-4-2", "label": "UPS Supply Laminator-4.2", "slug": "lam-4-2"},
                        {"id": "eq-ups-p1a-lam-5-1", "label": "UPS Supply Laminator-5.1", "slug": "lam-5-1"},
                        {"id": "eq-ups-p1a-lam-5-2", "label": "UPS Supply Laminator-5.2", "slug": "lam-5-2"},
                        {"id": "eq-ups-p1a-lam-6-1", "label": "UPS Supply Laminator-6.1", "slug": "lam-6-1"},
                        {"id": "eq-ups-p1a-lam-6-2", "label": "UPS Supply Laminator-6.2", "slug": "lam-6-2"},
                    ]},
                    {"id": "eq-ups-p1a-out-other", "label": "Other feeders", "slug": "other-feeders", "alwaysOpen": True, "children": [
                        {"id": "eq-util-pid-qc-lab", "label": "PID, QC Lab, Store ofc(FG)", "slug": "pid-qc-lab", "mfm_name": "PID, QC Lab, Store ofc(FG)"},
                    ]},
                    {"id": "eq-ups-p1a-out-spare", "label": "Spare Feeders", "slug": "spare", "alwaysOpen": True, "children": [
                        {"id": "eq-ups-p1a-sp-02", "label": "Spare-02", "slug": "spare-02"},
                        {"id": "eq-ups-p1a-sp-05", "label": "Spare-05", "slug": "spare-05"},
                        {"id": "eq-ups-p1a-sp-12", "label": "Spare-12", "slug": "spare-12"},
                        {"id": "eq-ups-p1a-sp-21", "label": "Spare-21", "slug": "spare-21"},
                        {"id": "eq-ups-p1a-sp-26", "label": "Spare-26", "slug": "spare-26"},
                        {"id": "eq-ups-p1a-sp-29", "label": "Spare-29", "slug": "spare-29"},
                    ]},
                ]},
            ]},

            # ── UPS Panel-2B ─────────────────────────────────────────
            {"id": "eq-ups-p2b", "label": "UPS Panel-2B", "slug": "panel-2b", "children": [
                {"id": "eq-ups-p2b-overview", "label": "Overview", "slug": "overview"},
                {"id": "eq-ups-p2b-in", "label": "Incomings", "slug": "incoming", "alwaysOpen": True, "children": [
                    {"id": "eq-ups-p2b-in-1", "label": "Incomer-1 from UPS-07 (600kVA)", "slug": "incomer-1", "mfm_name": "UPS-07 CL:600KVA"},
                    {"id": "eq-ups-p2b-in-2", "label": "Incomer-2 from UPS-08 (600kVA)", "slug": "incomer-2", "mfm_name": "UPS-08 CL:600KVA"},
                    {"id": "eq-ups-p2b-in-3", "label": "Incomer-3 from UPS-09 (600kVA)", "slug": "incomer-3", "mfm_name": "UPS-09 CL:600KVA"},
                    {"id": "eq-ups-p2b-in-4", "label": "Incomer-4 from UPS-10 (600kVA)", "slug": "incomer-4", "mfm_name": "UPS-10 CL:600KVA"},
                    {"id": "eq-ups-p2b-in-5", "label": "Incomer-5 from UPS-11 (600kVA)", "slug": "incomer-5", "mfm_name": "UPS-11 CL:600KVA"},
                    {"id": "eq-ups-p2b-in-6", "label": "Incomer-6 from UPS-12 (600kVA)", "slug": "incomer-6", "mfm_name": "UPS-12 CL:600KVA"},
                ]},
                {"id": "eq-ups-p2b-out", "label": "Outgoings", "slug": "outgoing", "alwaysOpen": True, "children": [
                    {"id": "eq-ups-p2b-out-pdb", "label": "PDB / Production Feeders", "slug": "pdb-feeders", "alwaysOpen": True, "children": [
                        {"id": "eq-ups-p2b-pdb-10", "label": "PDB-10 Packing Line-02",        "slug": "pdb-10", "mfm_name": "PDB-10 Packaging-02"},
                        {"id": "eq-ups-p2b-pdb-06", "label": "PDB-06 Pre Laminator Line-03",  "slug": "pdb-06"},
                        {"id": "eq-ups-p2b-pdb-08", "label": "PDB-08 Pre Laminator Line-03",  "slug": "pdb-08"},
                        {"id": "eq-ups-p2b-pdb-07", "label": "PDB-07 Pre Laminator Line-04",  "slug": "pdb-07"},
                        {"id": "eq-ups-p2b-pdb-09", "label": "PDB-09 Pre Laminator Line-04",  "slug": "pdb-09"},
                    ]},
                    {"id": "eq-ups-p2b-out-lam", "label": "UPS Supply Laminator Feeders", "slug": "laminator-feeders", "alwaysOpen": True, "children": [
                        {"id": "eq-ups-p2b-lam-7-1",  "label": "UPS Supply Laminator-7.1",  "slug": "lam-7-1"},
                        {"id": "eq-ups-p2b-lam-7-2",  "label": "UPS Supply Laminator-7.2",  "slug": "lam-7-2"},
                        {"id": "eq-ups-p2b-lam-8-1",  "label": "UPS Supply Laminator-8.1",  "slug": "lam-8-1"},
                        {"id": "eq-ups-p2b-lam-8-2",  "label": "UPS Supply Laminator-8.2",  "slug": "lam-8-2"},
                        {"id": "eq-ups-p2b-lam-9-1",  "label": "UPS Supply Laminator-9.1",  "slug": "lam-9-1"},
                        {"id": "eq-ups-p2b-lam-9-2",  "label": "UPS Supply Laminator-9.2",  "slug": "lam-9-2"},
                        {"id": "eq-ups-p2b-lam-10-1", "label": "UPS Supply Laminator-10.1", "slug": "lam-10-1"},
                        {"id": "eq-ups-p2b-lam-10-2", "label": "UPS Supply Laminator-10.2", "slug": "lam-10-2"},
                        {"id": "eq-ups-p2b-lam-11-1", "label": "UPS Supply Laminator-11.1", "slug": "lam-11-1"},
                        {"id": "eq-ups-p2b-lam-11-2", "label": "UPS Supply Laminator-11.2", "slug": "lam-11-2"},
                        {"id": "eq-ups-p2b-lam-12-1", "label": "UPS Supply Laminator-12.1", "slug": "lam-12-1"},
                        {"id": "eq-ups-p2b-lam-12-2", "label": "UPS Supply Laminator-12.2", "slug": "lam-12-2"},
                    ]},
                ]},
            ]},
        ],
    },

    # ── APFC Panel ───────────────────────────────────────────────────
    {
        "id": "eq-apfc", "label": "APFC Panel", "slug": "apfc",
        "pathOverride": "/electrical/apfc",
        "children": [
            {"id": "eq-apfc-1", "label": "APFC Panel-1", "slug": "panel-1"},
            {"id": "eq-apfc-2", "label": "APFC Panel-2", "slug": "panel-2"},
            {"id": "eq-apfc-3", "label": "APFC Panel-3", "slug": "panel-3"},
            {"id": "eq-apfc-4", "label": "APFC Panel-4", "slug": "panel-4"},
        ],
    },

    # ── Production Panels ────────────────────────────────────────────
    {
        "id": "eq-prod", "label": "Production Panels", "slug": "production",
        "pathOverride": "/electrical/production",
        "children": [
            {"id": "eq-prod-bpdb-1", "label": "BPDB-1 -Lamination- 01&02",  "slug": "bpdb-1", "mfm_name": "BPDB-01 For Lamination-01&02"},
            {"id": "eq-prod-bpdb-2", "label": "BPDB-2 -Lamination- 03&04",  "slug": "bpdb-2", "mfm_name": "BPDB-02 For Lamination-03&04"},
            {"id": "eq-prod-bpdb-3", "label": "BPDB-3 - Lamination- 05&06", "slug": "bpdb-3", "mfm_name": "BPDB-03 For Lamination-05&06"},
            {"id": "eq-prod-bpdb-4", "label": "BPDB-4 -Lamination- 07&08",  "slug": "bpdb-4", "mfm_name": "BPDB-04 For Lamination-07&08"},
            {"id": "eq-prod-bpdb-5", "label": "BPDB-5 -Lamination- 09&10",  "slug": "bpdb-5", "mfm_name": "BPDB-05 For Lamination-09&10"},
            {"id": "eq-prod-bpdb-6", "label": "BPDB-6 -Lamination- 11&12",  "slug": "bpdb-6", "mfm_name": "BPDB-06 For Lamination-11&12"},
            {"id": "eq-prod-pdb-fg", "label": "PDB For FG",                  "slug": "pdb-fg"},
            {"id": "eq-prod-pdb-rm", "label": "PDB For RM",                  "slug": "pdb-rm"},
            {"id": "eq-prod-pdb-1",  "label": "PDB-1 Pre Lamination Line-01","slug": "pdb-1"},
            {"id": "eq-prod-pdb-2",  "label": "PDB-2 Pre Lamination Line-02","slug": "pdb-2"},
            {"id": "eq-prod-pdb-3",  "label": "PDB-3 Packaging-01",          "slug": "pdb-3"},
            {"id": "eq-prod-pdb-4",  "label": "PDB-4 Post Lamination Line-01","slug": "pdb-4"},
            {"id": "eq-prod-pdb-5",  "label": "PDB-5 Post Lamination Line-02","slug": "pdb-5"},
            {"id": "eq-prod-pdb-6",  "label": "PDB-6 Pre Lamination Line-03","slug": "pdb-6"},
            {"id": "eq-prod-pdb-7",  "label": "PDB-7 Pre Lamination Line-04","slug": "pdb-7"},
            {"id": "eq-prod-pdb-8",  "label": "PDB-8 Post Lamination Line-03","slug": "pdb-8"},
            {"id": "eq-prod-pdb-9",  "label": "PDB-9 Post Lamination Line-04","slug": "pdb-9"},
            {"id": "eq-prod-pdb-10", "label": "PDB-10 Packaging-02",         "slug": "pdb-10"},
        ],
    },

    # ── Utility Panels ───────────────────────────────────────────────
    {
        "id": "eq-util", "label": "Utility Panels", "slug": "utility",
        "pathOverride": "/electrical/utility",
        "children": [
            {"id": "eq-util-canteen",       "label": "Canteen Building",                  "slug": "canteen"},
            {"id": "eq-util-er-north",      "label": "Electrical Room- Ext North Side",   "slug": "er-north",     "mfm_name": "Electrical Room North Side"},
            {"id": "eq-util-er-south",      "label": "Electrical Room- Ext South Side",   "slug": "er-south",     "mfm_name": "Electrical Room External-South"},
            {"id": "eq-util-frisking",      "label": "Frisking & Security",               "slug": "frisking",     "mfm_name": "Frisking+Security"},
            {"id": "eq-util-gen-exhaust",   "label": "General Exhaust Panel",             "slug": "gen-exhaust",  "mfm_name": "General Exhaust"},
            {"id": "eq-util-meldb",         "label": "MELDB Panel",                       "slug": "meldb"},
            {"id": "eq-util-mldb",          "label": "MLDB Panel",                        "slug": "mldb",         "mfm_name": "MLDB"},
            {"id": "eq-util-mrpdb",         "label": "MRPDB Panel",                       "slug": "mrpdb",        "mfm_name": "MRPDB"},
            {"id": "eq-util-mupsdb",        "label": "MUPSDB Panel",                      "slug": "mupsdb"},
            {"id": "eq-util-pcw",           "label": "PCW Panel",                         "slug": "pcw"},
            {"id": "eq-util-pid-qc-lab",    "label": "PID, QC Lab, Store ofc(FG)",        "slug": "pid-qc-lab"},
            {"id": "eq-util-panel-01",      "label": "Utility Panel-01",                  "slug": "panel-01",     "mfm_name": "Utility Panel-1"},
            {"id": "eq-util-panel-02",      "label": "Utility Panel-02",                  "slug": "panel-02"},
            {"id": "eq-util-aux-hsd",       "label": "Aux HSD Panel",                     "slug": "aux-hsd"},
            {"id": "eq-util-tf-fire",       "label": "TF Area-Fire Extinguishing System", "slug": "tf-fire",      "mfm_name": "Fire Fighting System"},
        ],
    },

    # ── HVAC Panels ──────────────────────────────────────────────────
    {
        "id": "eq-hvac", "label": "HVAC Panels", "slug": "hvac",
        "pathOverride": "/electrical/hvac",
        "children": [
            {"id": "eq-hvac-ahu-01",   "label": "AHU Panel-01",   "slug": "ahu-01",   "mfm_name": "AHU-1"},
            {"id": "eq-hvac-ahu-02",   "label": "AHU Panel-02",   "slug": "ahu-02",   "mfm_name": "AHU-2"},
            {"id": "eq-hvac-ahu-03",   "label": "AHU Panel-03",   "slug": "ahu-03",   "mfm_name": "AHU-3"},
            {"id": "eq-hvac-ahu-04",   "label": "AHU Panel-04",   "slug": "ahu-04",   "mfm_name": "AHU-4"},
            {"id": "eq-hvac-ahu-05",   "label": "AHU Panel-05",   "slug": "ahu-05",   "mfm_name": "AHU-5"},
            {"id": "eq-hvac-ahu-06",   "label": "AHU Panel-06",   "slug": "ahu-06",   "mfm_name": "AHU-6"},
            {"id": "eq-hvac-ahu-07",   "label": "AHU Panel-07",   "slug": "ahu-07",   "mfm_name": "AHU-7"},
            {"id": "eq-hvac-ahu-08",   "label": "AHU Panel-08",   "slug": "ahu-08",   "mfm_name": "AHU-8"},
            {"id": "eq-hvac-ahu-09",   "label": "AHU Panel-09",   "slug": "ahu-09",   "mfm_name": "AHU-9"},
            {"id": "eq-hvac-ahu-10",   "label": "AHU Panel-10",   "slug": "ahu-10",   "mfm_name": "AHU-10"},
            {"id": "eq-hvac-ahu-11",   "label": "AHU Panel-11",   "slug": "ahu-11",   "mfm_name": "AHU-11"},
            {"id": "eq-hvac-awex-01",  "label": "AW-EX-Panel-01", "slug": "aw-ex-01"},
            {"id": "eq-hvac-awex-02",  "label": "AW-EX-Panel-02", "slug": "aw-ex-02"},
            {"id": "eq-hvac-awex-03",  "label": "AW-EX-Panel-03", "slug": "aw-ex-03"},
            {"id": "eq-hvac-awex-04",  "label": "AW-EX-Panel-04", "slug": "aw-ex-04", "mfm_name": "Air Washer Exhaust-04"},
            {"id": "eq-hvac-awex-05",  "label": "AW-EX-Panel-05", "slug": "aw-ex-05", "mfm_name": "Air Washer Exhaust-05"},
            {"id": "eq-hvac-awex-06",  "label": "AW-EX-Panel-06", "slug": "aw-ex-06", "mfm_name": "Air Washer Exhaust-06"},
            {"id": "eq-hvac-aw-01",    "label": "AW-Panel-01",    "slug": "aw-01",    "mfm_name": "Air Washer-1"},
            {"id": "eq-hvac-aw-02",    "label": "AW-Panel-02",    "slug": "aw-02",    "mfm_name": "Air Washer-2"},
            {"id": "eq-hvac-aw-03",    "label": "AW-Panel-03",    "slug": "aw-03",    "mfm_name": "Air Washer-3"},
            {"id": "eq-hvac-aw-04",    "label": "AW-Panel-04",    "slug": "aw-04",    "mfm_name": "Air Washer-4"},
            {"id": "eq-hvac-aw-05",    "label": "AW-Panel-05",    "slug": "aw-05",    "mfm_name": "Air Washer-5"},
            {"id": "eq-hvac-aw-06",    "label": "AW-Panel-06",    "slug": "aw-06",    "mfm_name": "Air Washer-6"},
            {"id": "eq-hvac-chiller-01", "label": "Chiller Panel-01", "slug": "chiller-01", "mfm_name": "Chiller & CHW, CWP-1"},
            {"id": "eq-hvac-chiller-02", "label": "Chiller Panel-02", "slug": "chiller-02", "mfm_name": "Chiller & CHW, CWP-2"},
            {"id": "eq-hvac-chiller-03", "label": "Chiller Panel-03", "slug": "chiller-03", "mfm_name": "Chiller & CHW, CWP-3"},
            {"id": "eq-hvac-chiller-04", "label": "Chiller Panel-04", "slug": "chiller-04", "mfm_name": "Chiller & CHW, CWP-4"},
            {"id": "eq-hvac-csu-01",   "label": "CSU-01",          "slug": "csu-01",   "mfm_name": "Curing Line CSU-01"},
            {"id": "eq-hvac-csu-02",   "label": "CSU-02",          "slug": "csu-02",   "mfm_name": "Curing Line CSU-02"},
        ],
    },
]
