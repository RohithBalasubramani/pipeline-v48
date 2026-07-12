/**
 * SHARED (payload derivation + honest-empty concern) — panel-overview-harmonics-pq.
 *
 * PAYLOAD-DIRECT (host-served RETIRED — the host emits frames={} EMPTY): the ONLY data
 * source is the Layer-2 completed `payload`. The old snapshot-derived helpers
 * (presentation(snap) / liveTablePeriod(snap,...) that read a mapped aggregate snapshot)
 * are dead code now and were DELETED, along with snapshot.ts.
 *
 * What remains is the small pure period selector plus the HONEST-EMPTY builders every
 * card falls back to when the payload elided its periods — an empty period / zeroed stats
 * carrying ZERO fabricated harmonic values (NEVER buildPQPeriods(), whose synthetic
 * iThd/vThd waves are a seed leak). The card always DRAWS honest '—' chrome, never a mock.
 */
import type {
  PQPanelState,
  PQPeriod,
  PQStats,
} from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/harmonics-pq/types";

/** The last (most recent) period in a list — the tab's default-selected bucket. */
export const lastPeriod = (periods: PQPeriod[]): PQPeriod | undefined =>
  periods[periods.length - 1];

/** A blank feeder row — all metrics 0, id/labels dashed. Used to satisfy the required
 *  PQStats.worst* pointer shape AND SignatureCard's mock branch (which reads a `selected`
 *  panel's h3/h5/… UNGUARDED — an undefined selected crashes it) on the honest-empty path;
 *  it is NOT a fabricated measurement — every value is 0 and shows '—'/flat-at-zero. */
export function blankPanel(): PQPanelState {
  return {
    id: "",
    panel: "—",
    table: "—",
    kw: 0,
    pf: 0,
    iThd: 0,
    vThd: 0,
    iThdPk: 0,
    h3: 0,
    h5: 0,
    h7: 0,
    kFactor: 0,
    truePf: 0,
    pfGap: 0,
    neutralA: 0,
    status: "success",
    driverKey: "OK",
    driver: "—",
  };
}

/** An HONEST-EMPTY period — a labelled bucket with NO feeder rows. The components .map()
 *  the empty panels to an empty (honest-blank) table/radar; ZERO fabricated data. */
export function emptyPeriod(): PQPeriod {
  return { label: "—", panels: [] };
}

/** HONEST-EMPTY period carrying ONE blank ('—'/zero) feeder row. SignatureCard's mock
 *  branch reads `period.panels.find(...) ?? period.panels[0]` and then that row's h3/h5/…
 *  UNGUARDED, so it needs at least one row to avoid a crash — the blank row draws a
 *  flat-at-zero radar (honest '—'), never a fabricated signature. */
export function emptyPeriodWithRow(): PQPeriod {
  return { label: "—", panels: [blankPanel()] };
}

/** HONEST-EMPTY rollup — zero issue counts + blank worst-of pointers. Keeps the required
 *  PQStats shape so PqTopStrip/PqAiSummaryCard read `worst*.iThd` safely (→ 0/'—'), never
 *  a crash and never a fabricated worst feeder. */
export function emptyStats(): PQStats {
  const b = blankPanel();
  return { iThd: 0, vThd: 0, pfGap: 0, neutral: 0, total: 0, worstIThd: b, worstVThd: b, worst: b };
}
