// honest-blank (structured-empty) slices for the diesel-generator voltage-current fill cards.
// ONE shared implementation now lives in ../shared/vc-empty (cached; pure) — this module re-exports it so the
// folder's existing importers keep their path.
export { unavailableHistory, unavailableHealth } from "../shared/vc-empty";
