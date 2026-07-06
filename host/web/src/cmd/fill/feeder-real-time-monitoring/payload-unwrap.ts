// payload unwrap (story args → panel props) for the feeder real-time-monitoring cards.
//
// Every RTM story renders <Panel data={data} freshness={freshness} />, so the seed
// payload is { data, freshness, variant }. These readers pull the byte-faithful
// default slices Layer 2 copied from card_payloads — the HONEST-DEGRADE fallback
// when the live frame is missing/unmappable, so the panel still DRAWS its structure.
import type {
  PowerEnergyViewModel,
  PhaseMonitorViewModel,
  RealTimeFreshnessViewModel,
} from "@cmd-v2/pages/electrical/tabs/real-time-monitoring/types";

/** Seed `data` slice (PowerEnergyViewModel-shaped for card 36). */
export function powerEnergyDefault(payload: any): PowerEnergyViewModel | undefined {
  return payload?.data as PowerEnergyViewModel | undefined;
}

/** Seed `data` slice (PhaseMonitorViewModel-shaped for cards 37 & 38). */
export function phaseMonitorDefault(payload: any): PhaseMonitorViewModel | undefined {
  return payload?.data as PhaseMonitorViewModel | undefined;
}

/** Seed `freshness` slice — shared by all three panels. */
export function freshnessDefault(payload: any): RealTimeFreshnessViewModel | undefined {
  return payload?.freshness as RealTimeFreshnessViewModel | undefined;
}
