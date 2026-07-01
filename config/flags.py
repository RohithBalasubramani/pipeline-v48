"""config/flags.py — feature flags / open-decision toggles. Flip here as decisions land or pages ship."""
from config.app_config import cfg

# Partition: detect page-wise-shared interdependency (implicit shared-snapshot, no explicit links).
# OFF until the FE interdependency settles (open_items/partition_page_wise_shared.md).
PAGE_WISE_SHARED_DETECTION = cfg("flags.page_wise_shared_detection", False)

# Layer-2 group atom $ctx source form (open_items/ctx_source_form.md). "dotted" => "$ctx.<buffer>".
CTX_SOURCE_FORM = cfg("flags.ctx_source_form", "dotted")

# Acceptance gate: require the LIVE Storybook sentinel (fe_contract/acceptance_sentinel.md) for "done".
REQUIRE_LIVE_SENTINEL = cfg("flags.require_live_sentinel", True)
