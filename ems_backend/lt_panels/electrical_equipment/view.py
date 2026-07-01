"""
REST view for the electrical-equipment sidebar tree.

Serves the static tree (`tree_data.ELECTRICAL_EQUIPMENT_TREE`) with `mfm_id`
baked in per node (via `mfm_binding`) so the frontend can open WebSockets
directly (`ws/mfm/{mfm_id}/...`) straight from a tree click.
"""

from rest_framework.decorators import api_view
from rest_framework.response import Response

from .tree_data import ELECTRICAL_EQUIPMENT_TREE
from .mfm_binding import (
    _attach_mfm_ids,
    _build_name_to_mfm_id,
    _count_leaves,
    _count_matched,
)


@api_view(['GET'])
def electrical_equipment(request):
    """Return the Equipment sidebar tree (HT/Transformers/PCC/UPS/Production/PQ).

    Each node whose label matches an MFM in the DB carries `mfm_id`; the
    frontend uses this to open WebSockets directly (`ws/mfm/{mfm_id}/...`).
    Group container nodes (Incoming/Outgoing/Spare/Bus Coupler) and
    descriptive labels with no DB row stay without `mfm_id`.
    """
    name_to_id = _build_name_to_mfm_id()
    tree = _attach_mfm_ids(ELECTRICAL_EQUIPMENT_TREE, name_to_id)
    return Response({
        'count': len(tree),
        'leaf_count': _count_leaves(tree),
        'matched_mfm_count': _count_matched(tree),
        'tree': tree,
    })
