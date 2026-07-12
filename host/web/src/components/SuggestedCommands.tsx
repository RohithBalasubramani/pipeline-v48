// Empty-state workspace: a short roster of suggested commands, fetched live from the copilot
// (/copilot/starters) so they are grounded in REAL v48 assets. Clicking one SEEDS the prompt bar
// (fills + focuses, does not auto-run) — the operator reviews then presses ↵.
// Tags are mono micro-codes (RT/ENR/V·I/PQ/ALM); text is the readable command.
import { useEffect, useState } from "react";
import { copilotStarters, type StarterChip as Chip } from "../api";

// shown only until the copilot's grounded roster arrives (or if it's unreachable)
const FALLBACK: Chip[] = [
  { tag: "RT", text: "real time monitoring for PCC Panel 1A" },
  { tag: "ENR", text: "energy and power trends for Transformer 1 today" },
  { tag: "V·I", text: "voltage and current unbalance on PCC Panel 1A" },
  { tag: "PQ", text: "power quality and harmonics on PCC Panel 1A" },
  { tag: "ALM", text: "active alarms across the site" },
];

export function SuggestedCommands({ onPick }: { onPick: (query: string) => void }) {
  const [chips, setChips] = useState<Chip[]>(FALLBACK);

  useEffect(() => {
    let alive = true;
    copilotStarters()
      .then((starters) => { if (alive && starters.length) setChips(starters); })
      .catch(() => { /* keep fallback */ });
    return () => { alive = false; };
  }, []);

  return (
    <>
      <div className="cc-work-label">Suggested commands</div>
      <div className="cc-chips">
        {chips.map((c, i) => (
          <button key={i} className="cc-chip" onClick={() => onPick(c.text)}>
            <span className="cc-chip-tag">{c.tag}</span>
            <span>{c.text}</span>
          </button>
        ))}
      </div>
    </>
  );
}
