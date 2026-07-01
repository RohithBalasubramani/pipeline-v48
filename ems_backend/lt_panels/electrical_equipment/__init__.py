"""
Electrical Equipment package — the sidebar tree for the "Equipment" section
of the CMD frontend, plus the REST view that serves it with `mfm_id` baked
into each matching node.

Atomised from the former single-file `electrical_equipment.py`. This barrel
re-exports every public name the old module exposed so existing imports keep
working unchanged:

    from .electrical_equipment import electrical_equipment            # urls.py
    from .electrical_equipment import (                               # views.py
        _build_name_to_mfm_id, _attach_mfm_ids,
        _count_leaves, _count_matched,
    )

Concerns are split into single-purpose sub-modules:
    tree_data.py    ELECTRICAL_EQUIPMENT_TREE — the static hierarchy
    constants.py    GROUP_SLUGS — shared container-slug set
    mfm_binding.py  tree helpers that bake MFM ids into the tree
    view.py         the `electrical_equipment` REST endpoint
"""

from .constants import GROUP_SLUGS
from .tree_data import ELECTRICAL_EQUIPMENT_TREE
from .mfm_binding import (
    _attach_mfm_ids,
    _build_name_to_mfm_id,
    _count_leaves,
    _count_matched,
)
from .view import electrical_equipment

__all__ = [
    'GROUP_SLUGS',
    'ELECTRICAL_EQUIPMENT_TREE',
    '_attach_mfm_ids',
    '_build_name_to_mfm_id',
    '_count_leaves',
    '_count_matched',
    'electrical_equipment',
]
