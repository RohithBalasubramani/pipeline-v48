/* ── Shared sampling chrome (the real tab defaults — same as the story) ──── */
import {
  createDefaultPowerQualitySampling,
  powerQualityResolutionOptionsForPreset,
} from "@cmd-v2/pages/electrical/tabs/power-quality/powerQualitySampling";

export const SAMPLING = createDefaultPowerQualitySampling();
export const SAMPLING_RESOLUTION_OPTIONS = powerQualityResolutionOptionsForPreset(SAMPLING.preset);
