// KnowledgeAnswer — the SEPARATE knowledge pipeline's render (2026-07-06). Per the user, it reuses the EMS
// "AI Summary" CARD DESIGN (voltage-current AiSummaryCard: BodyCard chrome "✦ AI Summary" + a brown small-caps
// "AI" label + the AiSummary primitive body with its diamond marker). We mount the REAL CMD_V2 primitives directly
// (import-only, CMD_V2 untouched) — no bespoke panel. A refusal uses the same card with an "OUT OF SCOPE" label.
import { AiSummary } from "@cmd-v2/components/charts/primitives/AiSummary";
import { BodyCard } from "@cmd-v2/components/charts/primitives/BodyCard";
import { TYPOGRAPHY } from "@cmd-v2/components/charts/primitives/typography";

export function KnowledgeAnswer({ prompt, answer, refused }: { prompt: string; answer: string; refused?: boolean }) {
  return (
    <div style={{ maxWidth: 620, margin: "48px auto 0", padding: "0 24px" }}>
      <BodyCard title={<span className="flex items-center gap-2"><span>✦</span> <span>AI Summary</span></span>}>
        <div className="space-y-2 overflow-hidden text-[12px] leading-5 text-[#44403c]">
          {prompt ? <div style={{ opacity: 0.6, fontSize: 12 }}>{prompt}</div> : null}
          <div>
            <div style={TYPOGRAPHY.aiLabel}>{refused ? "OUT OF SCOPE" : "AI"}</div>
            <AiSummary text={answer} className="mt-1" density="regular" />
          </div>
        </div>
      </BodyCard>
    </div>
  );
}
