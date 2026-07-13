"""layer1b/how.py — the ONE declaration of the 1b resolution `how` vocabulary.

The enum was re-declared as inline set literals in layer1b/schema.py (twice, different subsets),
layer1b/compare/resolve_names.py and run/harness.py — `collision_gate_fullname` had to be hand-threaded through every
copy when it landed (the comments still show the seams). Plain str constants (these values serialize into responses,
logs and the FE), grouped into the frozensets each consumer means.

  AI                       — the resolver LLM pinned one asset
  user-choice              — the operator picked from the AssetPicker
  collision_gate_fullname  — deterministic full-name pin (user spelled a colliding row out in full)
  no_data                  — pinned by name but its neuract table is dark (resolved, NOT fillable)
  ambiguous                — >1 candidate → picker opens
  empty                    — nothing matched → picker opens on the full registry
"""

HOW_AI = "AI"
HOW_USER_CHOICE = "user-choice"
HOW_COLLISION_GATE = "collision_gate_fullname"
HOW_ALIAS_DICTIONARY = "alias-dictionary"   # a deterministic pcc_panel_alias dictionary pin (sections rescue) — CONFIDENT
HOW_NO_DATA = "no_data"
HOW_AMBIGUOUS = "ambiguous"
HOW_EMPTY = "empty"

#: every legal `how` value (schema validation).
ALL = frozenset({HOW_AI, HOW_USER_CHOICE, HOW_COLLISION_GATE, HOW_ALIAS_DICTIONARY,
                 HOW_NO_DATA, HOW_AMBIGUOUS, HOW_EMPTY})

#: pinned to ONE asset that also has data — the basket/no-picker safety checks apply.
RESOLVED_WITH_DATA = frozenset({HOW_AI, HOW_USER_CHOICE, HOW_COLLISION_GATE, HOW_ALIAS_DICTIONARY})

#: a confident single resolution — an asset was pinned by NAME (or named-but-dark no_data) with NO open picker.
RESOLVED_ANY = RESOLVED_WITH_DATA | {HOW_NO_DATA}
