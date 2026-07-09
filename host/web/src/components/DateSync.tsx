import React from "react";
import type { DateWindow } from "../types";

// host/web/src/components/DateSync.tsx — ATOMIC: PAGE-LEVEL date synchronisation across the cards of one run.
//
// A dashboard PAGE has ONE time context (the CMD_V2 app drives every card from a single page-level date filter). The
// per-card re-fetch seam is real, but a user changing a date control expects EVERY date-navigable card on the page to
// move, not just the one card that owns the control. This shared context is that page window: any card's date control
// calls `setWindow`, and every is_history CmdCard re-fetches its OWN payload when the shared window changes. The
// provider is keyed per run in App, so a new prompt starts a fresh window (no stale carry-over).

type Ctx = { window: DateWindow | null; setWindow: (w: DateWindow) => void };
const DateSyncContext = React.createContext<Ctx>({ window: null, setWindow: () => {} });

export function DateSyncProvider({ children }: { children: React.ReactNode }) {
  const [window, setWindow] = React.useState<DateWindow | null>(null);
  return <DateSyncContext.Provider value={{ window, setWindow }}>{children}</DateSyncContext.Provider>;
}

export const useDateSync = () => React.useContext(DateSyncContext);
