import React from "react";
// Card 80 — Recent Tap Changes (page transformer-asset-dashboard/tap-rtcc, CMD V2 TapRtccTab). RecentTapChangesCard
// fed its OWN Layer-2 payload's `changes` slice: today's tap-change log (Time · Previous Position · Changed To).
//
// host-served is RETIRED → the payload IS the render source. DOMAIN slot (the OLTC tap-change log has no neuract column
// today) → HONEST-BLANK: when the payload carries no usable changes slice, `tapChangesVM` yields the tab's OWN empty
// chrome (rows []), so the DataTable renders its OWN "No tap changes today" empty state with the real column headers — a
// drawn card, never a blank/null card and never a fabricated/seed row. This card carries no header period control → no
// onDateChange.
import { RecentTapChangesCard } from "@cmd-v2/pages/assets/transformer/tabs/tap-rtcc/RecentTapChangesCard";
import { tapChangesVM } from "./view-model";

function RecentTapChangesFill({ payload }: { payload: any }) {
  return <RecentTapChangesCard vm={tapChangesVM(payload)} />;
}

export const card80 = (p: any): React.ReactNode => <RecentTapChangesFill payload={p} />;
