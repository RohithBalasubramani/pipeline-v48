"""validate/config_defaults_check.py — every configured DEFAULT KEY must resolve to a catalog row (ONE concern).

The audit's asset_3d config defect [2026-07-14, 14 F3]: viewer.default_asset_3d_key='pcc1a-v1' pointed at a key
with no lt_asset_3d row, so the honest tier-4 fallback silently died for ~189 records — a config-catalog
inconsistency nothing validated. This module is the permanence net: an extensible table of (knob, resolver)
pairs; check() returns a list of human-readable issues (empty = healthy). Wired fail-open at host boot
(WARN, never fatal) + tests/test_config_defaults_check.py. Add a new default-key knob → register one row here."""


def _asset_3d_default_resolves():
    """viewer.default_asset_3d_key → exactly one neuract.lt_asset_3d row."""
    from config.viewer_policy import default_asset_3d_key
    from data.db_client import q
    from config.databases import DATA_DB, DATA_SCHEMA
    key = default_asset_3d_key()
    if not key:
        return None                                   # no default configured = nothing to resolve (honest)
    rows = q(DATA_DB, f"SELECT id FROM {DATA_SCHEMA}.lt_asset_3d WHERE key=$a${key}$a$")
    if not rows:
        return (f"viewer.default_asset_3d_key={key!r} resolves to NO lt_asset_3d row — the tier-4 3D fallback "
                f"silently dies; run scripts/seed_pcc1a_asset3d.py or repoint the knob")
    return None


_CHECKS = (
    ("viewer.default_asset_3d_key", _asset_3d_default_resolves),
)


def check():
    """[issue strings]; empty = every configured default resolves. An unreachable DB SKIPS that check silently
    (a drift check must not report drift it cannot verify — same contract as data/registry/drift.py)."""
    issues = []
    for knob, fn in _CHECKS:
        try:
            issue = fn()
            if issue:
                issues.append(issue)
        except Exception:
            pass
    return issues
