// KnowledgeAnswer — the SEPARATE knowledge pipeline's render (2026-07-06). Per the user, it reuses the EMS
// "AI Summary" CARD DESIGN (BodyCard chrome + a brown small-caps "AI" label + the AiSummary primitive body with its
// diamond marker), titled "AI Brainstorm". We mount the REAL CMD_V2 primitives directly (import-only, CMD_V2 untouched)
// — no bespoke panel. It renders the whole CONVERSATION THREAD so follow-up questions read in context; a refusal turn
// uses the same card body with an "OUT OF SCOPE" label.
//
// Layout (per the user): TOP-ANCHORED + FULL-WIDTH. The card is a plain width:100% block at the top of .cc-work (which
// sits below the fixed header via its 84px top padding and stretches full-width). We do NOT use `zoom` — with a
// percentage width `zoom` renders at the literal (un-scaled) percentage, so the card never spanned. AiSummary hard-codes
// its font (TYPOGRAPHY.insightText inline), so a plain wrapper font-size can't grow it; the scoped `.kb-answer` CSS
// override below bumps the AiSummary body/label/prompt for readability WITHOUT touching width. No 100vh/spacers → no scroll.
import { AiSummary } from "@cmd-v2/components/charts/primitives/AiSummary";
import { BodyCard } from "@cmd-v2/components/charts/primitives/BodyCard";
import { TYPOGRAPHY } from "@cmd-v2/components/charts/primitives/typography";

export type KnowledgeTurn = { prompt: string; answer: string; refused?: boolean };

// Scoped readability bump: AiSummary's <p> carries an inline font-size, which beats class cascade — so target it with
// `!important`. Also enlarges the ✦ marker, the "AI"/"OUT OF SCOPE" label, and the echoed prompt. Width is untouched.
const STYLE = `
.kb-answer .kb-prompt { font-size: 15px !important; }
.kb-answer [style*="insightText"], .kb-answer p { font-size: 17px !important; line-height: 1.6 !important; }
.kb-answer span[aria-hidden="true"] { font-size: 19px !important; }
.kb-answer .kb-ailabel { font-size: 13px !important; letter-spacing: 0.14em; }
`;

export function KnowledgeAnswer({ turns }: { turns: KnowledgeTurn[] }) {
  return (
    <div className="kb-answer" style={{ width: "100%" }}>
      <style>{STYLE}</style>
      <BodyCard title={<span className="flex items-center gap-2"><span>✦</span> <span>AI Brainstorm</span></span>}>
        <div className="space-y-4 overflow-hidden text-[#44403c]">
          {turns.map((t, i) => (
            <div key={i} className="space-y-2">
              {t.prompt ? <div className="kb-prompt" style={{ opacity: 0.6 }}>{t.prompt}</div> : null}
              <div>
                <div className="kb-ailabel" style={TYPOGRAPHY.aiLabel}>{t.refused ? "OUT OF SCOPE" : "AI"}</div>
                <AiSummary text={t.answer} className="mt-1" density="regular" />
              </div>
            </div>
          ))}
        </div>
      </BodyCard>
    </div>
  );
}
