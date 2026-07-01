"""Single source of truth for per-MFM-type detail sections served by the
`details` action on `MFMViewSet` (`/api/mfm/{id}/details/`).

Mirrors `page_registry.py` — each section has a dispatcher with a
STRATEGIES dict keyed by mfm_type code. Each strategy implements
``build(mfm) -> dict | None``; ``None`` means pending (placeholder card).
A populated payload looks like::

    {
        'title':    'PCC Panel 1A',
        'subtitle': 'LT-PCC-001A - one-line ...',
        'groups':   [{'name': 'Rating & Identity', 'fields': [...]}, ...],
    }

Adding a new section = add a dispatcher class + a row in `_DETAILS`.
Adding type support to an existing section = add the type code to that
dispatcher's STRATEGIES dict.
"""
import re

from .consumers._dispatch import resolve_category


class _Stub:
    """Placeholder strategy — section advertised but content not yet defined.

    Frontend treats a `None` build result as a pending placeholder card.
    """
    @staticmethod
    def build(mfm):
        return None


class DetailDispatcher:
    """Base class; subclasses register per-type strategies in STRATEGIES.

    Each strategy must expose ``build(mfm) -> dict | None``. Return ``None``
    to advertise the section as pending; return a dict with
    ``{title, subtitle, groups}`` to populate it.
    """
    STRATEGIES: dict = {}


# ─────────────────────────────────────────────────────────────────────────────
# Concrete strategies
# ─────────────────────────────────────────────────────────────────────────────

# Match MFM names like "PCC Panel 1", "PCC Panel 4 A", etc. The general
# Nameplate strategy for lt_panel is PCC-only; other LT panels (BPDB, PDB,
# AHU meters, etc.) get their own strategies later — for now they stay
# pending. Word boundary keeps "PCC Panel" from matching "PCC Panel Bus".
_PCC_PANEL_NAME_RE = re.compile(r'^PCC Panel(\s|$)', re.IGNORECASE)


class PCCPanelNameplate:
    """Nameplate for PCC panels (LT-panel MFMs whose name starts with 'PCC Panel').

    Mixes static schema text (system, frequency, fault level, protection
    schemes) with values derived from the MFM row (asset tag from
    panel_id, source mix from `incoming` M2M, outgoing-bay count from
    `outgoing` M2M). Live values (live load, PF, operating state) are
    returned as ``None`` — wire them to `fetch_live` when ready.
    """
    @staticmethod
    def build(mfm):
        if not _PCC_PANEL_NAME_RE.match((mfm.name or '').strip()):
            return None  # not a PCC panel — section stays pending

        panel_id = mfm.panel_id or ''
        # MFM-LT-115 → LT-PCC-115. Falls back to upper(table_name) if pattern doesn't match.
        if panel_id.startswith('MFM-LT-'):
            asset_tag = panel_id.replace('MFM-LT-', 'LT-PCC-', 1)
        else:
            asset_tag = (mfm.table_name or '').upper()

        incoming_names = [m.name for m in mfm.incoming.all()]
        outgoing_count = mfm.outgoing.count()

        return {
            'title': mfm.name,
            'subtitle': f'{asset_tag} - one-line asset identity, rating, source, '
                        f'protection, and metering summary.',
            'groups': [
                {'name': 'Rating & Identity', 'fields': [
                    {'key': 'asset_tag',       'label': 'Asset Tag',        'value': asset_tag},
                    {'key': 'service',         'label': 'Service',          'value': f'{mfm.name} main LT distribution panel'},
                    {'key': 'system',          'label': 'System',           'value': '415 V AC, 3 phase, 4 wire'},
                    {'key': 'frequency',       'label': 'Frequency',        'value': '50 Hz'},
                    {'key': 'bus_arrangement', 'label': 'Bus Arrangement',  'value': None},
                    {'key': 'fault_level',     'label': 'Fault Level',      'value': '50 kA'},
                ]},
                {'name': 'Source & Metering', 'fields': [
                    {'key': 'incomers',             'label': 'Incomers',             'value': f'{len(incoming_names)} sources' if incoming_names else None},
                    {'key': 'source_mix',           'label': 'Source Mix',           'value': ', '.join(incoming_names) or None},
                    {'key': 'main_metering',        'label': 'Main Metering',        'value': None},
                    {'key': 'incoming_live_load',   'label': 'Incoming Live Load',   'value': None},
                    {'key': 'outgoing_mapped_bays', 'label': 'Outgoing Mapped Bays', 'value': f'{outgoing_count}/{outgoing_count}' if outgoing_count else None},
                    {'key': 'outgoing_live_load',   'label': 'Outgoing Live Load',   'value': None},
                ]},
                {'name': 'Protection & Operating Summary', 'fields': [
                    {'key': 'incoming_protection', 'label': 'Incoming Protection', 'value': 'ACB, metering, relay 50/51'},
                    {'key': 'outgoing_protection', 'label': 'Outgoing Protection', 'value': 'MCCB, MFM, relay 50/51 per feeder bay'},
                    {'key': 'feeder_families',     'label': 'Feeder Families',     'value': None},
                    {'key': 'average_pf',          'label': 'Average PF',          'value': None},
                    {'key': 'drawing_reference',   'label': 'Drawing Reference',   'value': None},
                    {'key': 'operating_state',     'label': 'Operating State',     'value': 'Live monitored panel'},
                ]},
            ],
        }


# ─────────────────────────────────────────────────────────────────────────────
# Section dispatchers — register supported types in STRATEGIES.
# ─────────────────────────────────────────────────────────────────────────────

class NameplateDispatcher(DetailDispatcher):
    """Manufacturer / model / serial / nominal ratings — universal."""
    STRATEGIES = {
        'transformer': _Stub,
        'ups':         _Stub,
        'lt_panel':    PCCPanelNameplate,  # populated for PCC; others stay pending
        'ht_panel':    _Stub,
        'apfc':        _Stub,
        'dg':          _Stub,
    }


class SpecificationsDispatcher(DetailDispatcher):
    """Detailed technical specifications — universal, fields differ per type."""
    STRATEGIES = {code: _Stub for code in (
        'transformer', 'ups', 'lt_panel', 'ht_panel', 'apfc', 'dg',
    )}


class TapChangerDispatcher(DetailDispatcher):
    """Tap changer position, OLTC range — transformer only."""
    STRATEGIES = {'transformer': _Stub}


class BatteryBankDispatcher(DetailDispatcher):
    """Battery type, runtime, age, charger state — UPS only."""
    STRATEGIES = {'ups': _Stub}


class FuelSystemDispatcher(DetailDispatcher):
    """Fuel tank level, engine specs, run-hours — DG only."""
    STRATEGIES = {'dg': _Stub}


class CapacitorBanksDispatcher(DetailDispatcher):
    """Stage configuration, step ratings, contactor state — APFC only."""
    STRATEGIES = {'apfc': _Stub}


# ─────────────────────────────────────────────────────────────────────────────
# Section list — single source of truth, in display order.
# `pages_for_mfm` walks this and filters by STRATEGIES on each dispatcher.
# ─────────────────────────────────────────────────────────────────────────────

_DETAILS = [
    {'code': 'nameplate',       'name': 'Nameplate',
     'description': 'Manufacturer, model, serial number, nominal ratings.',
     'dispatcher': NameplateDispatcher},
    {'code': 'specifications',  'name': 'Specifications',
     'description': 'Type-specific technical specifications and limits.',
     'dispatcher': SpecificationsDispatcher},
    {'code': 'tap-changer',     'name': 'Tap Changer',
     'description': 'OLTC tap position, range, and switching mode.',
     'dispatcher': TapChangerDispatcher},
    {'code': 'battery-bank',    'name': 'Battery Bank',
     'description': 'Battery configuration, capacity, runtime, age.',
     'dispatcher': BatteryBankDispatcher},
    {'code': 'fuel-system',     'name': 'Fuel System',
     'description': 'Fuel tank, engine specs, run-hours.',
     'dispatcher': FuelSystemDispatcher},
    {'code': 'capacitor-banks', 'name': 'Capacitor Banks',
     'description': 'Capacitor stage configuration and step ratings.',
     'dispatcher': CapacitorBanksDispatcher},
]


def details_for_mfm(mfm):
    """Build the detail-section list for an MFM, filtered by which sections
    have a strategy registered for the MFM's type.

    Each output entry has::

        {code, name, order, description, pending, title, subtitle, groups}

    A section is included only if its dispatcher has a strategy for the
    MFM's type (category-resolved code first, then `mfm_type.code` as
    fallback). ``pending=True`` means the strategy returned ``None`` —
    frontend renders a placeholder card. When populated, ``groups`` is a
    list of ``{name, fields}``; each field is
    ``{key, label, value, unit?}``.

    Public function (no underscore) — imported by `views.MFMViewSet.details`.
    """
    type_code = resolve_category(mfm)
    fallback_code = mfm.mfm_type.code

    out = []
    for i, d in enumerate(_DETAILS):
        strategies = getattr(d['dispatcher'], 'STRATEGIES', {})
        strategy = strategies.get(type_code) or strategies.get(fallback_code)
        if strategy is None:
            continue
        payload = strategy.build(mfm) if hasattr(strategy, 'build') else None
        if payload is None:
            entry = {
                'code': d['code'],
                'name': d['name'],
                'order': i + 1,
                'description': d.get('description', ''),
                'pending': True,
                'title': None,
                'subtitle': None,
                'groups': [],
            }
        else:
            entry = {
                'code': d['code'],
                'name': d['name'],
                'order': i + 1,
                'description': d.get('description', ''),
                'pending': False,
                'title': payload.get('title'),
                'subtitle': payload.get('subtitle'),
                'groups': payload.get('groups', []),
            }
        out.append(entry)
    return out
