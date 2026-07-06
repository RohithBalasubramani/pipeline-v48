import React from "react";
// Card 63 — Fuel Tank Anatomy (page diesel-generator-asset-dashboard/fuel-efficiency). The REAL 3D FuelTankAnatomy
// (its own three.js Canvas, from dg-overview) rendered DIRECTLY from the Layer-2 payload {snapshot, display} — the
// payload IS the props.
//
// FRAMES=PAYLOADS [architecture]: ems_backend is RETIRED (the host emits frames={} EMPTY), so there is no live-frame /
// mapper path — the Layer-2 payload is the only data source. DOMAIN GAP: fuel level / rate / temp are DG telemetry
// neuract does NOT carry, so Layer-2 honest-blanks those leaves. FuelTankAnatomy reads snapshot.fuelLevel/fuelRate/
// fuelTemp PLAINLY with `.toFixed(0)` (no null guard) and drives the 3D fill from `snapshot.fuelLevel`, so tankSnapshot
// finitizes every field (an honest-blank '—' → 0): the blank case draws an EMPTY (0%) tank + 0 channels — a correct
// blank tile, never NaN, never a crash, never the seed 60% mock. `display` is the payload prose (title/subtitle/
// channel-detail/AI-summary — real or honest-blank); undefined lets the card fall back to its OWN byte-identical
// defaults. FuelTankAnatomy renders an instantaneous snapshot with NO date/range control — so it carries no onDateChange.
import { FuelTankAnatomy } from "@cmd-v2/pages/electrical/lt-pcc/tabs/dg-overview/FuelTankAnatomy";
import { tankDisplay, tankSnapshot } from "./view-model";

function FuelTankFill({ payload }: { payload: any }) {
  // SSR GUARD [family H]: FuelTankAnatomy mounts a three.js Canvas (@react-three/fiber) which needs a DOM/WebGL host —
  // server-side rendering (the ssr_repro harness / any future SSR) crashes inside fiber's useBridge. Render an empty
  // shell server-side; the browser always takes the real 3D path (typeof window is defined there).
  if (typeof window === "undefined") {
    return <div style={{ height: "100%", minHeight: 0 }} aria-label="3D fuel tank (client-only)" />;
  }
  // tankSnapshot is ALWAYS a fully-numeric FuelSnapshot (finitized real telemetry, else 0-valued honest blank);
  // tankDisplay is the payload prose or undefined (→ the card's own defaults). Neither can be null.
  return <FuelTankAnatomy snapshot={tankSnapshot(payload)} display={tankDisplay(payload)} />;
}

export const card63 = (p: any): React.ReactNode => <FuelTankFill payload={p} />;
