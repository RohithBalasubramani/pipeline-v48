"""
Shared constants for the electrical-equipment tree.

Kept in one small module so the tree helpers (`mfm_binding`) can import it
without pulling in the large static tree data or the REST view — avoids any
import cycle between the sub-modules.
"""

# Slugs that mark group-container nodes (Incoming/Outgoing/Spare/Bus Coupler).
# Nodes with these slugs never get an `mfm_id` baked in even if their label
# happens to match an MFM name.
GROUP_SLUGS = {'incoming', 'outgoing', 'spare', 'bus-coupler'}
