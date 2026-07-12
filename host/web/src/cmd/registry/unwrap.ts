// registry/unwrap.ts — the single-object-prop payload unwrap (split F11, 2026-07-12).
import { aiHeadlineOf } from "../guards";

// "OPEN THE BOX" — the completed payload wraps the real props one level down under a SINGLE key (+ a throwaway
// `variant`), e.g. {variant, batteryHealth} / {variant, rail} / {variant, thermalLife}. The card's CMD V2 component
// reads that inner object under a prop name that VARIES per card — the Storybook `render` renames it: `railVM` reads it
// as-is, but most read it as `data` (BatteryHealthCard, HealthSummaryPanel, …), `vm` (ThermalLifeCard, tap cards, …) or
// `view` (LiveOpsCard, UpsCapacityCard, …). Since a card reads exactly ONE of these, we make the inner object available
// under ALL of them (data/vm/view) PLUS its own key PLUS spread its fields — so every prop shape is satisfied and the
// extras React harmlessly ignores. Multi-key payloads ({data,freshness} / {snapshot,display}) fall to the spread branch,
// which is already the correct multi-prop shape.
const SINGLE_OBJECT_PROP_ALIASES = ["data", "vm", "view"] as const;
// (exported for scripts/tier_audit.tsx — the FILL-vs-COMPONENTS tier comparison harness renders the direct-spread
// path with the exact same unwrap/forceBlank preprocessing renderCmd applies.)
// Keys that are NOT component props: the Storybook `variant` probe, and the narrative_ai envelope keys the host grafts
// onto a props-shaped payload (`widgets.ai_summary` + a mirrored top-level `ai_summary`). Ignoring them when we find the
// single spreadable prop keeps a props-card (19/25 AiSummary) single-key even after its ai_summary widget is attached.
// `loading` is also non-prop for key-shape detection (guards g16 sets it on the ROOT beside the vm key — it must not
// break the single-spreadable-prop unwrap) but IS forwarded as a real prop below (the CMD_V2 socket-loading seam).
const NON_PROP_KEYS = new Set(["variant", "widgets", "ai_summary", "loading"]);
export function unwrap(payload: any): any {
  if (!payload || typeof payload !== "object") return payload;
  // BACKEND-PARAGRAPH PROP [family H, cards 19/25 class]: a card that carries its REAL generated ai_summary text also
  // exposes it under the CMD_V2-designed `backendAiSummary` prop name (PqAiSummaryCard takes it as a prop and then
  // SKIPS its local compose — which is unguarded against honest-blank stats). Real text only; harmless extra prop for
  // every component that doesn't declare it.
  const aiText = aiHeadlineOf(payload);
  const withAi = (out: any) => {
    if (aiText && out && typeof out === "object" && out.backendAiSummary == null) out.backendAiSummary = aiText;
    // g16 seam: the guards mark a fully-unmeasured zero-row plot with root `loading` — forward it as the component's
    // own socket-loading prop (skeleton chrome) without disturbing key-shape detection above. Never clobbers.
    if (payload.loading === true && out && typeof out === "object" && out.loading == null) out.loading = true;
    return out;
  };
  const keys = Object.keys(payload).filter((k) => !NON_PROP_KEYS.has(k));
  if (keys.length === 1) {
    const key = keys[0];
    const inner = payload[key];
    if (inner && typeof inner === "object" && !Array.isArray(inner)) {
      const out: any = { ...inner, [key]: inner };
      // Alias the inner object to the common single-object prop names — but NEVER clobber a real field the inner
      // already carries (a spread-consumer might read it) or the payload's own key.
      for (const alias of SINGLE_OBJECT_PROP_ALIASES) {
        if (alias !== key && !(alias in out)) out[alias] = inner;
      }
      return withAi(out);
    }
  }
  const { variant, ...rest } = payload;
  const out: any = rest;
  // INNER-ALIAS HOIST [family H, card 12 class]: a MULTI-key payload ({kpi, rail}) spreads as-is, but the component may
  // read a single-object prop (`vm`) that lives ONE level down inside one of those keys (rail.vm — the Storybook story
  // rendered the subcard from it). Surface each top-level dict's data/vm/view member under that name when the spread
  // itself doesn't carry it — never clobbering an existing prop. Generic (key-shape driven, no card ids).
  for (const v of Object.values(out)) {
    if (v && typeof v === "object" && !Array.isArray(v)) {
      for (const alias of SINGLE_OBJECT_PROP_ALIASES) {
        if (!(alias in out) && alias in (v as any)) out[alias] = (v as any)[alias];
      }
    }
  }
  return withAi(out);
}
