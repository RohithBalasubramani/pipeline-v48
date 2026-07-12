"""layer2/gates — DETERMINISTIC Layer-2 emit gates, one single-purpose module per gate (atomic rule):
  metadata.py           exact_metadata byte-identity gate + enforce + no-default scrub [META-02, load-bearing]
  basket.py             the shared basket predicates (_bindable / _col_issue / _nameplate_missing)
  walls.py              the per-field HONEST-BLANK wall predicates (SEAM 2)
  honest_blank.py       enforce_honest_blank — the pass sequencing the walls
  data_instructions.py  gate_data_instructions — the fields[] structural gate
  roster.py             gate_roster — recipe-authoritative roster validation
This __init__ re-exports the original layer2/gates.py surface byte-compatibly (tests + tools import from here).
[PROMPTS §L2 gates 2/3; contract POST: ENFORCING byte-identity gate (revert non-conforming to default)]"""
from layer2.gates.metadata import (                                     # noqa: F401
    gate_exact_metadata, enforce_exact_metadata, enforce_free_metadata, _is_chrome, _chrome_markers, _CHROME_DEFAULT)
from layer2.gates.basket import _bindable, _col_issue, _nameplate_missing   # noqa: F401
from layer2.gates.walls import (                                        # noqa: F401
    _is_series_anchor, _blankable_field, _reuse_signature, _slot_parent_chrome, _slot_parent_unit, _snake,
    _slot_leaf_token, _quantity_mismatch, _const_without_source, _axis_chrome_const_segs, _axis_slot_suffixes,
    _axis_dir_tokens, _axis_direction_ok, _axis_source_mismatch, _expectation_tokens, _expectation_direct_bind,
    _topology_boundary_proxy, _time_axis_label_bind, _live_claim_without_source)
from layer2.gates.honest_blank import enforce_honest_blank              # noqa: F401
from layer2.gates.data_instructions import gate_data_instructions      # noqa: F401
from layer2.gates.roster import gate_roster                            # noqa: F401
