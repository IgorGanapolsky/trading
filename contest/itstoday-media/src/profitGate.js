const CHANNEL_PROFILES = {
  meta: {
    label: "Meta",
    hookStyle: "identity-led",
    landingAsset: "quiz",
    proof: "before/after proof, comments, creator proof",
  },
  google: {
    label: "Google",
    hookStyle: "intent-led",
    landingAsset: "comparison page",
    proof: "search intent match, clear offer math, objection FAQ",
  },
  tiktok: {
    label: "TikTok",
    hookStyle: "pattern-interrupt",
    landingAsset: "short-form explainer",
    proof: "creator demonstration, rapid payoff, social proof",
  },
  taboola: {
    label: "Taboola",
    hookStyle: "curiosity-led",
    landingAsset: "advertorial",
    proof: "credible story arc, native headline fit, compliance review",
  },
};

const DEFAULT_CHANNELS = ["meta", "google", "tiktok", "taboola"];

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

function rate(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return 0;
  return n > 1 ? n / 100 : n;
}

function money(value) {
  const n = Number(value);
  return Number.isFinite(n) ? n : 0;
}

function round(value, digits = 2) {
  const factor = 10 ** digits;
  return Math.round((value + Number.EPSILON) * factor) / factor;
}

export function calculateEconomics(input) {
  const payout = money(input.payout);
  const cpc = Math.max(money(input.cpc), 0.01);
  const dailyBudget = Math.max(money(input.dailyBudget), 0);
  const testDays = Math.max(money(input.testDays), 1);
  const landingPageCvr = rate(input.landingPageCvr);
  const leadToSale = rate(input.leadToSale);
  const grossMargin = rate(input.grossMargin);
  const refundRate = rate(input.refundRate);

  const realizedPayout = payout * grossMargin * (1 - refundRate);
  const saleRatePerClick = landingPageCvr * leadToSale;
  const revenuePerClick = realizedPayout * saleRatePerClick;
  const contributionPerClick = revenuePerClick - cpc;
  const breakevenCpc = revenuePerClick;
  const totalBudget = dailyBudget * testDays;
  const expectedClicks = totalBudget / cpc;
  const expectedSales = expectedClicks * saleRatePerClick;
  const expectedRevenue = expectedSales * realizedPayout;
  const expectedProfit = expectedRevenue - totalBudget;
  const roi = totalBudget > 0 ? expectedProfit / totalBudget : 0;
  const roas = totalBudget > 0 ? expectedRevenue / totalBudget : 0;
  const maxTestBudget = Math.max(
    50,
    Math.min(totalBudget, realizedPayout * 1.5),
  );
  const stopLossBudget =
    contributionPerClick < 0
      ? Math.min(totalBudget, maxTestBudget)
      : totalBudget;
  const scaleBudget =
    contributionPerClick > 0 ? dailyBudget * clamp(1 + roi, 1.15, 2.5) : 0;

  return {
    payout: round(payout),
    realizedPayout: round(realizedPayout),
    cpc: round(cpc),
    landingPageCvr: round(landingPageCvr, 4),
    leadToSale: round(leadToSale, 4),
    grossMargin: round(grossMargin, 4),
    refundRate: round(refundRate, 4),
    saleRatePerClick: round(saleRatePerClick, 5),
    revenuePerClick: round(revenuePerClick, 4),
    contributionPerClick: round(contributionPerClick, 4),
    breakevenCpc: round(breakevenCpc, 4),
    totalBudget: round(totalBudget),
    expectedClicks: Math.round(expectedClicks),
    expectedSales: round(expectedSales, 2),
    expectedRevenue: round(expectedRevenue),
    expectedProfit: round(expectedProfit),
    roi: round(roi, 4),
    roas: round(roas, 3),
    stopLossBudget: round(stopLossBudget),
    scaleBudget: round(scaleBudget),
  };
}

export function decideGate(economics, input = {}) {
  const blockers = [];
  const warnings = [];
  const wins = [];

  if (economics.contributionPerClick < 0) {
    blockers.push(
      `Projected CPC is $${economics.cpc}, above break-even $${economics.breakevenCpc}.`,
    );
  } else {
    wins.push(
      `Contribution is $${economics.contributionPerClick} per click before overhead.`,
    );
  }

  if (economics.expectedSales < 10) {
    warnings.push(
      "Sample is too thin for a confident read; extend the test or raise budget.",
    );
  }

  if (economics.roas < 1.15 && economics.contributionPerClick >= 0) {
    warnings.push(
      "ROAS clears spend but leaves little room for tracking error or payout volatility.",
    );
  }

  if (!input.trackingReady) {
    blockers.push("Tracking is not marked ready.");
  }

  if (!input.complianceReady) {
    warnings.push("Compliance review is not marked ready.");
  }

  if (economics.roi >= 0.5 && blockers.length === 0 && warnings.length <= 1) {
    return {
      status: "scale",
      label: "Scale Candidate",
      score: clamp(
        Math.round(70 + economics.roi * 25 - warnings.length * 8),
        70,
        98,
      ),
      blockers,
      warnings,
      wins,
      nextAction: `Launch with a daily cap near $${economics.scaleBudget} and cut if spend reaches $${economics.stopLossBudget} without signal.`,
    };
  }

  if (blockers.length === 0) {
    return {
      status: "test",
      label: "Controlled Test",
      score: clamp(
        Math.round(55 + economics.roi * 25 - warnings.length * 7),
        42,
        82,
      ),
      blockers,
      warnings,
      wins,
      nextAction: `Run a capped test at $${economics.totalBudget} total spend; require sales or qualified-lead proof before scaling.`,
    };
  }

  return {
    status: "hold",
    label: "Hold",
    score: clamp(
      Math.round(38 + economics.roi * 20 - blockers.length * 12),
      5,
      48,
    ),
    blockers,
    warnings,
    wins,
    nextAction: `Do not launch paid traffic yet. Fix the blockers or lower CPC below $${economics.breakevenCpc}.`,
  };
}

function splitWords(text) {
  return String(text || "")
    .toLowerCase()
    .replace(/[^a-z0-9\s-]/g, " ")
    .split(/\s+/)
    .filter(Boolean);
}

function pickValueProp(offer, pain) {
  const words = new Set([...splitWords(offer), ...splitWords(pain)]);
  if (words.has("debt") || words.has("credit"))
    return "faster financial relief";
  if (words.has("health") || words.has("wellness"))
    return "a simpler daily health win";
  if (words.has("insurance")) return "lower-friction quote intent";
  if (words.has("career") || words.has("job"))
    return "a clearer path to the next opportunity";
  if (words.has("trading") || words.has("investing"))
    return "a risk-first decision checkpoint";
  return "a measurable shortcut to the desired outcome";
}

function makeAngle(profile, input, index) {
  const offer = input.offer || "the offer";
  const audience = input.audience || "qualified buyers";
  const pain = input.pain || "wasted time and poor fit";
  const valueProp = pickValueProp(offer, pain);
  const urgency =
    index % 2 === 0
      ? "before spending another dollar"
      : "before the next decision";

  return {
    channel: profile.label,
    angle: `${profile.hookStyle}: ${valueProp}`,
    hook: `${audience} want ${valueProp}, not another vague promise. Show them the tradeoff ${urgency}.`,
    landingPage: `${profile.landingAsset} that names the pain, quantifies the payoff, and asks one qualifying question before the opt-in.`,
    proofNeeded: profile.proof,
    riskControl:
      "Kill the angle if CTR, CVR, or payout quality misses the gate after the capped test.",
  };
}

export function generateAngles(input) {
  const selected =
    Array.isArray(input.channels) && input.channels.length > 0
      ? input.channels
      : DEFAULT_CHANNELS;

  return selected
    .map((channel, index) => {
      const key = String(channel).toLowerCase();
      return makeAngle(
        CHANNEL_PROFILES[key] || CHANNEL_PROFILES.meta,
        input,
        index,
      );
    })
    .slice(0, 6);
}

export function buildCampaignBrief(input) {
  const economics = calculateEconomics(input);
  const gate = decideGate(economics, input);
  const angles = generateAngles(input);

  return {
    generatedAt: new Date().toISOString(),
    offer: input.offer || "",
    audience: input.audience || "",
    pain: input.pain || "",
    economics,
    gate,
    angles,
    mediaBuyerChecklist: [
      "Pixel, postback, and payout tracking are verified before launch.",
      "Daily spend cap is lower than the predeclared stop-loss budget.",
      "Creative test has one variable changed at a time.",
      "Scale only after economics and lead quality clear the gate.",
    ],
  };
}
