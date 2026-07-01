"""
Tree helpers that bake MFM ids into the static electrical-equipment tree.

Walk the static tree (`tree_data.ELECTRICAL_EQUIPMENT_TREE`) and bake in
`mfm_id` wherever a node's `label` (or explicit `mfm_name`) case-insensitively
matches an MFM in the database. The frontend uses these IDs to open WebSockets
(`ws/mfm/{mfm_id}/...`) without a second lookup. Group containers
(Incoming/Outgoing/Spare/Bus Coupler) and descriptive labels with no DB row
stay without `mfm_id`.
"""

from ..models import MFM

from .constants import GROUP_SLUGS


def _count_leaves(nodes):
    """Recursively count leaf nodes (no children) in the tree."""
    n = 0
    for node in nodes:
        kids = node.get('children')
        if kids:
            n += _count_leaves(kids)
        else:
            n += 1
    return n


def _build_name_to_mfm_id() -> dict[str, int]:
    """Map MFM.name (lowercased) → MFM.id. Used to bake `mfm_id` into tree
    nodes so the frontend can open WebSockets straight from a tree click
    without a second lookup. On name collisions the lowest id wins (deterministic).
    """
    out: dict[str, int] = {}
    for mid, name in MFM.objects.values_list('id', 'name').order_by('id'):
        if not name:
            continue
        key = name.strip().lower()
        out.setdefault(key, mid)
    return out


def _attach_mfm_ids(nodes, name_to_id):
    """Walk the tree and return new dicts with `mfm_id` added where the
    node matches an MFM by name (case-insensitive). Match key is the
    explicit `mfm_name` field if present, else falls back to `label` —
    this lets tree labels stay user-friendly while pointing at the actual
    MFM name in the DB. Group containers (Incoming, Outgoing, Spare,
    Bus Coupler) and unmatched descriptive labels stay without `mfm_id`."""
    out = []
    for node in nodes:
        new_node = dict(node)
        match_key = (node.get('mfm_name') or node.get('label') or '').strip().lower()
        slug = node.get('slug') or ''
        if match_key and slug not in GROUP_SLUGS and match_key in name_to_id:
            new_node['mfm_id'] = name_to_id[match_key]
        kids = node.get('children')
        if kids:
            new_node['children'] = _attach_mfm_ids(kids, name_to_id)
        out.append(new_node)
    return out


def _count_matched(nodes):
    """Count nodes that successfully picked up an mfm_id (for diagnostics)."""
    n = 0
    for node in nodes:
        if 'mfm_id' in node:
            n += 1
        if node.get('children'):
            n += _count_matched(node['children'])
    return n
