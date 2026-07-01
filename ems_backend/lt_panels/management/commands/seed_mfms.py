"""Seed all 179 MFMs from the simulator's per-MFM tables.

Each entry: (table_name, original_mfm_name, category)
  - table_name → MFM.table_name (e.g. 'mfm_tf_01')
  - original_mfm_name → MFM.name
  - category → MFM.mfm_type.code
  - panel_id is derived as table_name.upper().replace('_', '-')
  - db_link uses the model default
"""

from django.core.management.base import BaseCommand
from lt_panels.models import MFM, MFMType


# Mapping from the spreadsheet's "category" column to MFMType.code
CATEGORY_TO_TYPE_CODE = {
    'Transformer': 'transformer',
    'HT Panel':    'ht_panel',
    'LT Panel':    'lt_panel',
    'UPS':         'ups',
    'APFC':        'apfc',
    'DG':          'dg',
}


# (table_name, original_mfm_name, category)
MFMS = [
    ('mfm_tf_01',  'Transformer 1', 'Transformer'),
    ('mfm_tf_02',  'Transformer 2', 'Transformer'),
    ('mfm_tf_03',  'Transformer 3', 'Transformer'),
    ('mfm_tf_04',  'Transformer 4', 'Transformer'),
    ('mfm_tf_05',  'Transformer 5', 'Transformer'),
    ('mfm_tf_06',  'Transformer 6', 'Transformer'),
    ('mfm_tf_07',  'Transformer 7', 'Transformer'),
    ('mfm_tf_08',  'Transformer 8', 'Transformer'),

    ('mfm_lt_001', 'solar incomer 1', 'LT Panel'),
    ('mfm_lt_002', 'solar incomer 2', 'LT Panel'),

    ('mfm_ups_001', 'UPS-01 CL:600KVA', 'UPS'),
    ('mfm_ups_002', 'UPS-02 CL:600KVA', 'UPS'),
    ('mfm_ups_003', 'UPS-03 CL:600KVA', 'UPS'),
    ('mfm_ups_004', 'UPS-04 CL:600KVA', 'UPS'),
    ('mfm_ups_005', 'UPS-05 CL:600KVA', 'UPS'),
    ('mfm_ups_006', 'UPS-06 CL:600KVA', 'UPS'),

    ('mfm_lt_003', 'BPDB-01 For Lamination-01&02', 'LT Panel'),
    ('mfm_lt_004', 'BPDB-02 For Lamination-03&04', 'LT Panel'),
    ('mfm_lt_005', 'HHF-01 (TYPE-01) 300A +600KVAR', 'LT Panel'),
    ('mfm_lt_006', 'HHF-02 (TYPE-01) 300A +600KVAR', 'LT Panel'),
    ('mfm_lt_007', 'Spare-01', 'LT Panel'),
    ('mfm_lt_008', 'Spare-02', 'LT Panel'),
    ('mfm_lt_009', 'Spare-06', 'LT Panel'),
    ('mfm_lt_010', 'Spare-07', 'LT Panel'),
    ('mfm_lt_011', 'Spare-17', 'LT Panel'),
    ('mfm_lt_012', 'Spare-18', 'LT Panel'),
    ('mfm_lt_013', 'Spare-22', 'LT Panel'),
    ('mfm_lt_014', 'Spare-23', 'LT Panel'),
    ('mfm_lt_015', 'BusCoupler-12', 'LT Panel'),
    ('mfm_lt_016', 'BPDB-03 For Lamination-05&06', 'LT Panel'),
    ('mfm_lt_017', 'BPDB-04 For Lamination-07&08', 'LT Panel'),
    ('mfm_lt_018', 'HHF-01 (TYPE-02) 300A + 750KVAR', 'LT Panel'),
    ('mfm_lt_019', 'HHF-02 (TYPE-02) 300A + 750KVAR', 'LT Panel'),
    ('mfm_lt_020', 'Curing Line CSU-02', 'LT Panel'),
    ('mfm_lt_021', 'Axial Fan Panel-1', 'LT Panel'),
    ('mfm_lt_022', 'AHU-5', 'LT Panel'),
    ('mfm_lt_023', 'AHU-6', 'LT Panel'),
    ('mfm_lt_024', 'AHU-7', 'LT Panel'),
    ('mfm_lt_025', 'AHU-8', 'LT Panel'),
    ('mfm_lt_026', 'Air Washer-4', 'LT Panel'),
    ('mfm_lt_027', 'Air Washer Exhaust-04', 'LT Panel'),
    ('mfm_lt_028', 'Air Washer Exhaust-05', 'LT Panel'),
    ('mfm_lt_029', 'Air Washer-5', 'LT Panel'),
    ('mfm_lt_030', 'Air Washer-6', 'LT Panel'),
    ('mfm_lt_031', 'Air Washer Exhaust-06', 'LT Panel'),
    ('mfm_lt_032', 'Axial Fan Panel-2', 'LT Panel'),
    ('mfm_lt_033', 'Utility Panel-1', 'LT Panel'),
    ('mfm_lt_034', 'STP Panel', 'LT Panel'),
    ('mfm_lt_035', 'Canteen Building', 'LT Panel'),
    ('mfm_lt_036', 'MRPDB', 'LT Panel'),
    ('mfm_lt_037', 'Admin+IT+Other Emergency', 'LT Panel'),
    ('mfm_lt_038', 'MLDB', 'LT Panel'),
    ('mfm_lt_039', 'FCBC', 'LT Panel'),
    ('mfm_lt_040', 'Electrical Room North Side', 'LT Panel'),
    ('mfm_lt_041', 'Frisking+Security', 'LT Panel'),
    ('mfm_lt_042', 'Spare-11', 'LT Panel'),
    ('mfm_lt_043', 'Spare-12', 'LT Panel'),
    ('mfm_lt_044', 'Spare-14', 'LT Panel'),
    ('mfm_lt_045', 'Spare-24', 'LT Panel'),
    ('mfm_lt_046', 'Spare-26', 'LT Panel'),
    ('mfm_lt_047', 'Spare-27', 'LT Panel'),
    ('mfm_lt_048', 'Spare-29', 'LT Panel'),
    ('mfm_lt_049', 'Bus Coupler-19', 'LT Panel'),

    ('mfm_ups_007', 'UPS-07 CL:600KVA', 'UPS'),
    ('mfm_ups_008', 'UPS-08 CL:600KVA', 'UPS'),
    ('mfm_ups_009', 'UPS-09 CL:600KVA', 'UPS'),
    ('mfm_ups_010', 'UPS-10 CL:600KVA', 'UPS'),
    ('mfm_ups_011', 'UPS-11 CL:600KVA', 'UPS'),
    ('mfm_ups_012', 'UPS-12 CL:600KVA', 'UPS'),

    ('mfm_lt_050', 'BPDB-05 For Lamination-09&10', 'LT Panel'),
    ('mfm_lt_051', 'BPDB-06 For Lamination-11&12', 'LT Panel'),
    ('mfm_lt_052', 'Spare-21', 'LT Panel'),
    ('mfm_lt_053', 'Curing Line CSU-01', 'LT Panel'),
    ('mfm_lt_054', 'AHU-9', 'LT Panel'),
    ('mfm_lt_055', 'AHU-10', 'LT Panel'),
    ('mfm_lt_056', 'AHU-11', 'LT Panel'),
    ('mfm_lt_057', 'AHU-1', 'LT Panel'),
    ('mfm_lt_058', 'AHU-2', 'LT Panel'),
    ('mfm_lt_059', 'AHU-3', 'LT Panel'),
    ('mfm_lt_060', 'AHU-4', 'LT Panel'),
    ('mfm_lt_061', 'General Exhaust', 'LT Panel'),
    ('mfm_lt_062', 'Exhaust Fan-1', 'LT Panel'),
    ('mfm_lt_063', 'Air Washer-1', 'LT Panel'),
    ('mfm_lt_064', 'Exhaust Fan-2', 'LT Panel'),
    ('mfm_lt_065', 'Exhaust Fan-3', 'LT Panel'),
    ('mfm_lt_066', 'Air Washer-2', 'LT Panel'),
    ('mfm_lt_067', 'Air Washer-3', 'LT Panel'),
    ('mfm_lt_068', 'Axial Fan Panel-4', 'LT Panel'),
    ('mfm_lt_069', 'Chiller & CHW, CWP-2', 'LT Panel'),
    ('mfm_lt_070', 'Chiller & CHW, CWP-4', 'LT Panel'),
    ('mfm_lt_071', 'Chiller & CHW, CWP-1', 'LT Panel'),
    ('mfm_lt_072', 'Chiller & CHW, CWP-3', 'LT Panel'),
    ('mfm_lt_073', 'Fire Fighting System', 'LT Panel'),
    ('mfm_lt_074', 'Irrigation Water Pump', 'LT Panel'),
    ('mfm_lt_075', 'PCW Panel', 'LT Panel'),
    ('mfm_lt_076', 'Domestic Water Pump', 'LT Panel'),
    ('mfm_lt_077', 'Treated Water', 'LT Panel'),
    ('mfm_lt_078', 'Compressor Dryer', 'LT Panel'),
    ('mfm_lt_079', 'Electrical Room External-South', 'LT Panel'),
    ('mfm_lt_080', 'PDB For RM', 'LT Panel'),
    ('mfm_lt_081', 'Spare-15', 'LT Panel'),
    ('mfm_lt_082', 'Spare-16', 'LT Panel'),
    ('mfm_lt_083', 'Spare-20', 'LT Panel'),
    ('mfm_lt_084', 'Spare-30', 'LT Panel'),
    ('mfm_lt_085', 'Spare-35', 'LT Panel'),
    ('mfm_lt_086', 'Spare-37', 'LT Panel'),
    ('mfm_lt_087', 'Spare-40', 'LT Panel'),
    ('mfm_lt_088', 'Spare-42', 'LT Panel'),
    ('mfm_lt_089', 'Spare-43', 'LT Panel'),
    ('mfm_lt_090', 'Spare-51', 'LT Panel'),

    ('mfm_ups_013', 'UPS 01', 'UPS'),
    ('mfm_ups_014', 'UPS 02', 'UPS'),
    ('mfm_ups_015', 'UPS 03', 'UPS'),
    ('mfm_ups_016', 'UPS 04', 'UPS'),
    ('mfm_ups_017', 'UPS 05', 'UPS'),
    ('mfm_ups_018', 'UPS 06', 'UPS'),

    ('mfm_lt_091', 'PDB-1 Pre Laminator Line-01', 'LT Panel'),
    ('mfm_lt_092', 'PDB-4 Post Laminator Line-01', 'LT Panel'),
    ('mfm_lt_093', 'PDB-2 Pre Laminator Line-02', 'LT Panel'),
    ('mfm_lt_094', 'PDB-5 Post Laminator Line-02', 'LT Panel'),

    ('mfm_ups_019', 'UPS Supply Laminator-3.1', 'UPS'),
    ('mfm_ups_020', 'UPS Supply Laminator-1.2', 'UPS'),
    ('mfm_ups_021', 'UPS Supply Laminator-2.2', 'UPS'),
    ('mfm_ups_022', 'UPS Supply Laminator-2.1', 'UPS'),
    ('mfm_ups_023', 'UPS Supply Laminator-3.2', 'UPS'),
    ('mfm_ups_024', 'UPS Supply Laminator-1.1', 'UPS'),
    ('mfm_ups_025', 'UPS Supply Laminator-4.1', 'UPS'),
    ('mfm_ups_026', 'UPS Supply Laminator-4.2', 'UPS'),
    ('mfm_ups_027', 'UPS Supply Laminator-5.1', 'UPS'),
    ('mfm_ups_028', 'UPS Supply Laminator-5.2', 'UPS'),
    ('mfm_ups_029', 'UPS Supply Laminator-6.1', 'UPS'),
    ('mfm_ups_030', 'UPS Supply Laminator-6.2', 'UPS'),

    ('mfm_lt_095', 'P38', 'LT Panel'),
    ('mfm_lt_096', 'Spare-05', 'LT Panel'),
    ('mfm_lt_097', 'PDB-06 Pre Laminator Line-03', 'LT Panel'),
    ('mfm_lt_098', 'PDB-08 Pre Laminator Line-03', 'LT Panel'),
    ('mfm_lt_099', 'PDB-07 Pre Laminator Line-04', 'LT Panel'),
    ('mfm_lt_100', 'PDB-09 Pre Laminator Line-04', 'LT Panel'),

    ('mfm_ups_031', 'UPS Supply Laminator-7.1', 'UPS'),
    ('mfm_ups_032', 'UPS Supply Laminator-7.2', 'UPS'),
    ('mfm_ups_033', 'UPS Supply Laminator-8.1', 'UPS'),
    ('mfm_ups_034', 'UPS Supply Laminator-8.2', 'UPS'),
    ('mfm_ups_035', 'UPS Supply Laminator-9.1', 'UPS'),
    ('mfm_ups_036', 'UPS Supply Laminator-9.2', 'UPS'),
    ('mfm_ups_037', 'UPS Supply Laminator-10.1', 'UPS'),
    ('mfm_ups_038', 'UPS Supply Laminator-10.2', 'UPS'),
    ('mfm_ups_039', 'UPS Supply Laminator-11.1', 'UPS'),
    ('mfm_ups_040', 'UPS Supply Laminator-11.2', 'UPS'),
    ('mfm_ups_041', 'UPS Supply Laminator-12.1', 'UPS'),
    ('mfm_ups_042', 'UPS Supply Laminator-12.2', 'UPS'),

    ('mfm_lt_101', 'Spare-03', 'LT Panel'),
    ('mfm_lt_102', 'Spare-09', 'LT Panel'),
    ('mfm_lt_103', 'Spare-28', 'LT Panel'),
    ('mfm_lt_104', 'PDB-1 Pre Lamination Line-01', 'LT Panel'),
    ('mfm_lt_105', 'PDB-2 Pre Lamination Line-02', 'LT Panel'),
    ('mfm_lt_106', 'PDB-3 Packaging-01', 'LT Panel'),
    ('mfm_lt_107', 'PDB-4 Post Lamination Line-01', 'LT Panel'),
    ('mfm_lt_108', 'PDB-5 Post Lamination Line-02', 'LT Panel'),
    ('mfm_lt_109', 'PDB-6 Pre Lamination Line-03', 'LT Panel'),
    ('mfm_lt_110', 'PDB-7 Pre Lamination Line-04', 'LT Panel'),
    ('mfm_lt_111', 'PDB-8 Post Lamination Line-03', 'LT Panel'),
    ('mfm_lt_112', 'PDB-9 Post Lamination Line-04', 'LT Panel'),
    ('mfm_lt_113', 'PDB-10 Packaging-02', 'LT Panel'),
    ('mfm_lt_114', 'PDB For FG', 'LT Panel'),

    ('mfm_apfc_01', 'APFC Panel-1', 'APFC'),
    ('mfm_apfc_02', 'APFC Panel-2', 'APFC'),
    ('mfm_apfc_03', 'APFC Panel-3', 'APFC'),
    ('mfm_apfc_04', 'APFC Panel-4', 'APFC'),

    ('mfm_lt_115', 'PCC Panel 1', 'LT Panel'),
    ('mfm_lt_116', 'PCC Panel 2', 'LT Panel'),
    ('mfm_lt_117', 'PCC Panel 3', 'LT Panel'),
    ('mfm_lt_118', 'PCC Panel 4', 'LT Panel'),

    ('mfm_lt_122', 'AW-EX-Panel-01',              'LT Panel'),
    ('mfm_lt_123', 'AW-EX-Panel-02',              'LT Panel'),
    ('mfm_lt_124', 'AW-EX-Panel-03',              'LT Panel'),
    ('mfm_lt_125', 'MELDB Panel',                 'LT Panel'),
    ('mfm_lt_126', 'MUPSDB Panel',                'LT Panel'),
    ('mfm_lt_127', 'PID, QC Lab, Store ofc(FG)',  'LT Panel'),
    ('mfm_lt_128', 'Utility Panel-02',            'LT Panel'),
    ('mfm_lt_129', 'Aux HSD Panel',               'LT Panel'),

    ('mfm_dg_01', 'Diesel Generator-01', 'DG'),
    ('mfm_dg_02', 'Diesel Generator-02', 'DG'),
    ('mfm_dg_03', 'Diesel Generator-03', 'DG'),
    ('mfm_dg_04', 'Diesel Generator-04', 'DG'),
    ('mfm_dg_05', 'Diesel Generator-05', 'DG'),
    ('mfm_dg_06', 'Diesel Generator-06', 'DG'),
    ('mfm_dg_07', 'Diesel Generator-07', 'DG'),
    ('mfm_dg_08', 'Diesel Generator-08', 'DG'),

    ('mfm_ht_01', 'HT Panel M1', 'HT Panel'),
    ('mfm_ht_02', 'HT Panel M2', 'HT Panel'),
    ('mfm_ht_03', 'Main HT Panel', 'HT Panel'),
]


def derive_panel_id(table_name: str) -> str:
    """mfm_tf_01 -> MFM-TF-01"""
    return table_name.upper().replace('_', '-')


class Command(BaseCommand):
    help = 'Seed all 179 MFMs from the simulator schema.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--wipe',
            action='store_true',
            help='Delete existing MFM rows (and their M2M connections) before seeding.',
        )

    def handle(self, *args, **opts):
        if opts['wipe']:
            n, _ = MFM.objects.all().delete()
            self.stdout.write(f'Wiped {n} existing MFM rows.')

        # Make sure all referenced MFMTypes exist
        for code in set(CATEGORY_TO_TYPE_CODE.values()):
            if not MFMType.objects.filter(code=code).exists():
                self.stderr.write(self.style.ERROR(
                    f'MFMType "{code}" is missing — run `python manage.py seed_parameters` first.'
                ))
                return

        type_by_code = {mt.code: mt for mt in MFMType.objects.all()}
        by_type_count = {code: 0 for code in CATEGORY_TO_TYPE_CODE.values()}
        created, updated = 0, 0

        for table_name, name, category in MFMS:
            code = CATEGORY_TO_TYPE_CODE[category]
            mt = type_by_code[code]
            panel_id = derive_panel_id(table_name)
            _, was_created = MFM.objects.update_or_create(
                table_name=table_name,
                defaults={
                    'name': name,
                    'mfm_type': mt,
                    'panel_id': panel_id,
                },
            )
            if was_created:
                created += 1
            else:
                updated += 1
            by_type_count[code] += 1

        self.stdout.write(self.style.SUCCESS(
            f'Seeded {len(MFMS)} MFMs ({created} new, {updated} updated). Per type:'
        ))
        for code, count in by_type_count.items():
            self.stdout.write(f'  {code:12s} : {count}')
