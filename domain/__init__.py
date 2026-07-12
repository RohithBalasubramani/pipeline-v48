"""domain/ — the EMS DOMAIN KERNEL: vocabulary + resolvers shared by MORE THAN ONE layer.

The rule that earns a module a home here: two-plus layers (layer1a/1b/2, ems_exec, grounding) need the SAME concept,
and parking it inside one layer forces the others to import across (or into a cycle — this package exists because
quantity_class trapped in layer2 forced ems_exec→layer2 back-imports, and swap-affinity trapped in layer2/swap forced
grounding→layer2). domain/ imports ONLY downward (config/, data/, lib/, stdlib) — NEVER a layer, run/, host/ or
grounding/. Layers import domain/; domain/ never imports back. [cycle-kill 2026-07-12]

Concerns:
    quantity_class   — the physical-quantity class vocabulary + compatibility test + const-source resolver
    metric_affinity  — the generic metric-token affinity vocabulary/score (swap pool ranking + settle re-rank)
    asset_3d         — the 4-tier neuract 3D model resolver + viewer-preset merge (emit metadata ∧ renderer shared)

Old import paths keep working: layer2/quantity_class.py, layer2/swap/candidates._metric_tokens/_affinity and
layer2/emit/metadata/asset_3d.py re-export from here (facade pattern, same as the 2026-07-12 refactor campaign).
One atomic file per concern (house rule)."""
