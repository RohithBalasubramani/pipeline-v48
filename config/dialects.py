"""config/dialects.py — the DATA-fill target shapes (the surviving 'dialects'). Add/remove here. [frames/]"""
# The shape the worker fills INTO (mapper input). NOT a Layer-2 output.
DATA_FILL_SHAPES = ["flat_asset", "widgets_envelope", "column_row", "shared_context"]

# Resolver inputs: how (render_shell, backend_strategy, handling_class) maps to a dialect
# lives in frames/resolver.py; this is the closed vocabulary it may emit.  # open_items/column_row_dialect.md
