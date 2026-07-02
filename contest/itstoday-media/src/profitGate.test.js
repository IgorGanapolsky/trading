import { describe, expect, it } from "vitest";

import {
  buildCampaignBrief,
  calculateEconomics,
  decideGate,
  generateAngles,
} from "./profitGate.js";

describe("media buying profit gate", () => {
  it("holds campaigns when CPC is above break-even economics", () => {
    const economics = calculateEconomics({
      payout: 80,
      grossMargin: 70,
      refundRate: 5,
      landingPageCvr: 4,
      leadToSale: 10,
      cpc: 4,
      dailyBudget: 250,
      testDays: 3,
    });

    const gate = decideGate(economics, {
      trackingReady: true,
      complianceReady: true,
    });

    expect(economics.breakevenCpc).toBeLessThan(1);
    expect(gate.status).toBe("hold");
    expect(gate.blockers[0]).toContain("above break-even");
  });

  it("marks strong economics as a scale candidate", () => {
    const brief = buildCampaignBrief({
      offer: "AI lead qualification for insurance buyers",
      audience: "independent insurance agents",
      pain: "unqualified quote requests",
      payout: 240,
      grossMargin: 80,
      refundRate: 3,
      landingPageCvr: 18,
      leadToSale: 22,
      cpc: 3.5,
      dailyBudget: 500,
      testDays: 3,
      trackingReady: true,
      complianceReady: true,
      channels: ["google", "meta"],
    });

    expect(brief.economics.roas).toBeGreaterThan(1.5);
    expect(brief.gate.status).toBe("scale");
    expect(brief.angles).toHaveLength(2);
    expect(brief.mediaBuyerChecklist).toHaveLength(4);
  });

  it("generates channel-specific angle briefs", () => {
    const angles = generateAngles({
      offer: "career coaching",
      audience: "busy operators",
      pain: "stalled job search",
      channels: ["taboola", "tiktok"],
    });

    expect(angles[0].channel).toBe("Taboola");
    expect(angles[0].landingPage).toContain("advertorial");
    expect(angles[1].channel).toBe("TikTok");
    expect(angles[1].hook).toContain("busy operators");
  });
});
