// guards.ts — RE-EXPORT SHIM (split F12, 2026-07-12): the 16 rule families + the ordered walk live in
// cmd/guards/ (one file per family; walk.ts owns the execution order). This path stays byte-stable for
// scripts/tier_audit.tsx and cmd/registry.tsx.
export { guardPayload, aiHeadlineOf } from "./guards/index";
