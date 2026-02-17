/**
 * RAG Chat Cloudflare Worker
 * Proxies requests to Claude API with embedded trading lessons context
 * Supports conversation history for follow-up questions
 */

const DEFAULT_RAG_SEARCH_URL = "";
const DEFAULT_RAG_WEBHOOK_URL = "";
const LESSONS_INDEX_URL =
  "https://raw.githubusercontent.com/IgorGanapolsky/trading/main/data/rag/lessons_query.json";
const LESSONS_INDEX_FALLBACK_URL =
  "https://igorganapolsky.github.io/trading/data/rag/lessons_query.json";
const LESSONS_CACHE_TTL_MS = 5 * 60 * 1000;
let lessonsCache = { data: null, fetchedAt: 0 };

const SYSTEM_PREFIX = [
  "You are a trading knowledge assistant for Igor's AI Trading System.",
  "Answer questions using ONLY the lessons below.",
  "If the answer isn't in the lessons, say \"I don't have a lesson about that.\"",
].join("\n");

const GITHUB_RAW_URL =
  "https://raw.githubusercontent.com/IgorGanapolsky/trading/main/data/system_state.json";
const GITHUB_COMMITS_API_URL =
  "https://api.github.com/repos/IgorGanapolsky/trading/commits";

/**
 * Fetch live portfolio data from GitHub raw (public repo, no auth).
 * Returns parsed JSON or null on failure.
 */
async function fetchLiveData() {
  try {
    const res = await fetch(GITHUB_RAW_URL, {
      headers: { "User-Agent": "rag-chat-worker" },
      cf: { cacheTtl: 300 },
    });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

async function fetchSystemStateAtCommit(sha) {
  if (!sha) return null;
  const url = `https://raw.githubusercontent.com/IgorGanapolsky/trading/${sha}/data/system_state.json`;
  try {
    const res = await fetch(url, {
      headers: { "User-Agent": "rag-chat-worker" },
      cf: { cacheTtl: 60 },
    });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

async function fetchSystemStateCommitAtOrBefore(untilIso) {
  if (!untilIso) return null;
  try {
    const url = new URL(GITHUB_COMMITS_API_URL);
    url.searchParams.set("path", "data/system_state.json");
    url.searchParams.set("per_page", "1");
    url.searchParams.set("until", untilIso);

    const res = await fetch(url.toString(), {
      headers: { "User-Agent": "rag-chat-worker" },
      cf: { cacheTtl: 60 },
    });
    if (!res.ok) return null;
    const data = await res.json();
    const first = Array.isArray(data) ? data[0] : null;
    if (!first) return null;

    const sha = first.sha;
    const commitDate =
      (first.commit &&
        first.commit.author &&
        first.commit.author.date) ||
      null;
    return { sha, commitDate };
  } catch {
    return null;
  }
}

/**
 * Decode OCC option symbol like SPY260220C00720000 into human-readable parts.
 */
function parseOccSymbol(symbol) {
  const match = symbol.match(/^([A-Z]+)(\d{2})(\d{2})(\d{2})([CP])(\d{8})$/);
  if (!match) return null;
  const [, ticker, yy, mm, dd, type, strikeRaw] = match;
  return {
    ticker,
    expiry: `20${yy}-${mm}-${dd}`,
    type: type === "C" ? "call" : "put",
    strike: parseInt(strikeRaw, 10) / 1000,
  };
}

function asNumber(value, fallback = 0) {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
}

function formatCurrency(value) {
  const n = asNumber(value, 0);
  return n.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function extractEquity(state) {
  if (!state) return 0;
  const portfolio = state.portfolio || {};
  const paper = state.paper_account || {};
  return asNumber(portfolio.equity ?? paper.equity, 0);
}

function extractAsOf(state) {
  if (!state) return null;
  const meta = state.meta || {};
  return (
    meta.last_updated ||
    meta.last_sync ||
    state.last_updated ||
    state.last_sync ||
    null
  );
}

function parseTimestamp(value) {
  if (!value) return null;
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? null : d;
}

function pickLatestTimestamp(candidates) {
  const parsed = candidates
    .map((v) => parseTimestamp(v))
    .filter((d) => d !== null)
    .sort((a, b) => b.getTime() - a.getTime());
  return parsed.length > 0 ? parsed[0] : null;
}

function computeNorthStarSnapshot(liveData) {
  const paper = (liveData && liveData.paper_account) || {};
  const paperTrading = (liveData && liveData.paper_trading) || {};
  const portfolio = (liveData && liveData.portfolio) || {};
  const risk = (liveData && liveData.risk) || {};
  const meta = (liveData && liveData.meta) || {};
  const syncHealth = (liveData && liveData.sync_health) || {};

  const winRate = asNumber(paper.win_rate, 0);
  const sampleSize = asNumber(paper.win_rate_sample_size, 0);
  const targetWinRate =
    asNumber(paperTrading.target_win_rate, 0.8) > 1
      ? asNumber(paperTrading.target_win_rate, 80)
      : asNumber(paperTrading.target_win_rate, 0.8) * 100;
  const day = asNumber(paperTrading.current_day, 0);
  const targetDays = asNumber(paperTrading.target_duration_days, 90);
  const equity = asNumber(portfolio.equity ?? paper.equity, 0);
  const dailyChange = asNumber(paper.daily_change, 0);
  const unrealized = asNumber(risk.unrealized_pl, 0);
  const baseline = 100000;
  const cumulativePl = equity - baseline;
  const winRateGap = winRate - targetWinRate;

  let status = "VALIDATING";
  let gate = "ACTIVE";
  if (sampleSize >= 30 && day >= targetDays) {
    if (winRate >= targetWinRate) {
      status = "ON_TRACK_TO_SCALE";
      gate = "PASS";
    } else {
      status = "OFF_TRACK_WIN_RATE";
      gate = "ACTIVE";
    }
  } else if (sampleSize >= 30 && winRate < targetWinRate) {
    status = "OFF_TRACK_WIN_RATE";
    gate = "ACTIVE";
  }

  const asOf = pickLatestTimestamp([
    meta.last_updated,
    meta.last_sync,
    syncHealth.last_successful_sync,
  ]);

  return {
    status,
    gate,
    winRate,
    targetWinRate,
    winRateGap,
    sampleSize,
    day,
    targetDays,
    equity,
    cumulativePl,
    dailyChange,
    unrealized,
    asOf: asOf ? asOf.toISOString() : null,
  };
}

function isNorthStarQuestion(message) {
  const q = String(message || "").toLowerCase();
  return /north star|rule\s*#?\s*1|80%|win rate|on track|off track|reach/.test(q);
}

function getPnlTimeframe(message) {
  const q = String(message || "").toLowerCase();
  const asksMoney =
    /\b(p\/?l|pnl|profit|loss|make|made|earn|earned|earnings)\b/.test(q) ||
    /how much money/.test(q);
  if (!asksMoney) return null;

  if (/\btoday\b/.test(q)) return "today";
  if (/\bthis week\b/.test(q)) return "this_week";
  if (/\blast week\b/.test(q)) return "last_week";
  return null;
}

function isAnalyticalFollowup(message) {
  const q = String(message || "").toLowerCase();
  return /\b(why|explain|reason|how come|what happened|analyze|analysis)\b/.test(q);
}

function buildDeterministicWhyContext(liveData, dailyChange) {
  const lines = [];
  const trades = (liveData && liveData.trades) || {};
  const risk = (liveData && liveData.risk) || {};
  const positions = Array.isArray(liveData && liveData.positions) ? liveData.positions : [];

  const tradesToday = asNumber(trades.today_trades ?? trades.total_trades_today, 0);
  const lastTradeDate = trades.last_trade_date || "unknown";
  const unrealized = asNumber(risk.unrealized_pl, 0);

  lines.push("");
  lines.push("Why:");
  if (tradesToday === 0) {
    lines.push("- No fills were recorded today (`trades.today_trades = 0`).");
  } else {
    lines.push(`- ${tradesToday} fill(s) were recorded today.`);
  }
  lines.push(`- Open positions: ${positions.length}.`);
  lines.push(`- Unrealized P/L: ${unrealized >= 0 ? "+" : "-"}$${formatCurrency(Math.abs(unrealized))}.`);
  lines.push(`- Last recorded trade date: ${lastTradeDate}.`);

  if (dailyChange === 0 && tradesToday === 0) {
    lines.push("- Daily P/L is flat because no positions were opened/closed today.");
  }

  return lines.join("\n");
}

async function buildDeterministicPnlReply(message, liveData) {
  const timeframe = getPnlTimeframe(message);
  if (!timeframe) return null;

  if (!liveData) {
    return [
      "P/L unavailable: live portfolio data could not be fetched.",
      "Action: retry when `data/system_state.json` is reachable and fresh.",
    ].join("\n");
  }

  const equityNow = extractEquity(liveData);
  const asOfNowRaw = extractAsOf(liveData);
  const asOfNow = parseTimestamp(asOfNowRaw) || new Date();

  if (timeframe === "today") {
    const paper = liveData.paper_account || {};
    const dailyChange = asNumber(paper.daily_change, 0);
    const lines = [
      `Today P/L (daily change): ${dailyChange >= 0 ? "+" : "-"}$${formatCurrency(Math.abs(dailyChange))}`,
      `Equity: $${formatCurrency(equityNow)}`,
      `Data as of: ${asOfNow.toISOString()}`,
    ];
    if (isAnalyticalFollowup(message)) {
      lines.push(buildDeterministicWhyContext(liveData, dailyChange));
    }
    return lines.join("\n");
  }

  let start = null;
  let end = asOfNow;
  let label = "";
  const day = asOfNow.getUTCDay(); // 0=Sun..6=Sat
  const daysSinceMonday = (day + 6) % 7;
  const currentWeekStart = new Date(
    Date.UTC(
      asOfNow.getUTCFullYear(),
      asOfNow.getUTCMonth(),
      asOfNow.getUTCDate() - daysSinceMonday,
      0,
      0,
      0,
    ),
  );

  if (timeframe === "this_week") {
    // Week boundary uses UTC Monday 00:00 for determinism.
    start = currentWeekStart;
    label = `This week (since ${start.toISOString().slice(0, 10)} UTC)`;
  } else if (timeframe === "last_week") {
    // Previous full trading week window (Mon-Fri), measured from Monday 00:00 UTC
    // of prior week to Saturday 00:00 UTC (exclusive), so weekend snapshots are excluded.
    start = new Date(currentWeekStart.getTime() - 7 * 24 * 60 * 60 * 1000);
    end = new Date(start.getTime() + 5 * 24 * 60 * 60 * 1000);
    const friday = new Date(start.getTime() + 4 * 24 * 60 * 60 * 1000);
    label = `Previous trading week (Mon-Fri ${start.toISOString().slice(0, 10)} to ${friday.toISOString().slice(0, 10)})`;
  }

  if (!start) return null;

  const startCommit = await fetchSystemStateCommitAtOrBefore(start.toISOString());
  if (!startCommit || !startCommit.sha) {
    return [
      `${label} P/L unavailable: could not find a historical snapshot.`,
      `Current equity: $${formatCurrency(equityNow)} (as of ${asOfNow.toISOString()})`,
    ].join("\n");
  }

  const startState = await fetchSystemStateAtCommit(startCommit.sha);
  if (!startState) {
    return [
      `${label} P/L unavailable: could not load historical snapshot.`,
      `Current equity: $${formatCurrency(equityNow)} (as of ${asOfNow.toISOString()})`,
    ].join("\n");
  }

  const equityStart = extractEquity(startState);
  const asOfStartRaw = extractAsOf(startState);
  const asOfStart = parseTimestamp(asOfStartRaw);

  let equityEnd = equityNow;
  let asOfEnd = asOfNow;
  let endCommit = null;

  if (timeframe === "last_week") {
    endCommit = await fetchSystemStateCommitAtOrBefore(end.toISOString());
    if (!endCommit || !endCommit.sha) {
      return [
        `${label} P/L unavailable: could not find end-of-week snapshot.`,
        `Start equity: $${formatCurrency(equityStart)} (as of ${asOfStart ? asOfStart.toISOString() : "unknown"})`,
      ].join("\n");
    }

    const endState = await fetchSystemStateAtCommit(endCommit.sha);
    if (!endState) {
      return [
        `${label} P/L unavailable: could not load end-of-week snapshot.`,
        `Start equity: $${formatCurrency(equityStart)} (as of ${asOfStart ? asOfStart.toISOString() : "unknown"})`,
      ].join("\n");
    }

    equityEnd = extractEquity(endState);
    asOfEnd = parseTimestamp(extractAsOf(endState)) || end;
  }

  const pnl = equityEnd - equityStart;
  const pct = equityStart > 0 ? (pnl / equityStart) * 100 : 0;

  const lines = [];
  lines.push(
    `${label} P/L: ${pnl >= 0 ? "+" : "-"}$${formatCurrency(Math.abs(pnl))} (${pct >= 0 ? "+" : ""}${pct.toFixed(2)}%)`,
  );
  lines.push(
    `Equity: $${formatCurrency(equityEnd)} (start: $${formatCurrency(equityStart)})`,
  );
  if (asOfStart) lines.push(`Start snapshot as of: ${asOfStart.toISOString()}`);
  lines.push(`End snapshot as of: ${asOfEnd.toISOString()}`);
  if (startCommit.commitDate) {
    lines.push(
      `Baseline source: data/system_state.json @ ${String(startCommit.sha).slice(0, 7)} (${startCommit.commitDate})`,
    );
  } else {
    lines.push(
      `Baseline source: data/system_state.json @ ${String(startCommit.sha).slice(0, 7)}`,
    );
  }
  if (endCommit && endCommit.sha) {
    lines.push(
      `End source: data/system_state.json @ ${String(endCommit.sha).slice(0, 7)}${endCommit.commitDate ? ` (${endCommit.commitDate})` : ""}`,
    );
  }
  return lines.join("\n");
}

function buildNorthStarDeterministicReply(liveData) {
  if (!liveData) {
    return [
      "North Star status unavailable: live portfolio data could not be fetched.",
      "Action: retry when `data/system_state.json` is reachable and fresh.",
    ].join("\n");
  }

  const s = computeNorthStarSnapshot(liveData);
  const direction = s.winRateGap >= 0 ? "+" : "";

  const lines = [
    `North Star Status: ${s.status}`,
    `Rule #1 Gate: ${s.gate}`,
    "",
    "Live evidence:",
    `- Win rate: ${s.winRate.toFixed(1)}% vs target ${s.targetWinRate.toFixed(1)}% (${direction}${s.winRateGap.toFixed(1)} pp)`,
    `- Sample size: ${s.sampleSize} trades (min 30)`,
    `- Paper phase: day ${s.day}/${s.targetDays}`,
    `- Equity: $${formatCurrency(s.equity)} (vs $100,000 baseline: ${s.cumulativePl >= 0 ? "+" : "-"}$${formatCurrency(Math.abs(s.cumulativePl))})`,
    `- Daily P/L: ${s.dailyChange >= 0 ? "+" : "-"}$${formatCurrency(Math.abs(s.dailyChange))}; Unrealized P/L: ${s.unrealized >= 0 ? "+" : "-"}$${formatCurrency(Math.abs(s.unrealized))}`,
    s.asOf ? `- Data as of: ${s.asOf}` : "- Data as of: unknown",
    "",
  ];

  if (s.status === "ON_TRACK_TO_SCALE") {
    lines.push("Execution focus:");
    lines.push("1) Keep Rule #1 limits unchanged during scale-up.");
    lines.push("2) Increase size only in predefined increments.");
    lines.push("3) Continue publishing daily evidence and gate checks.");
  } else {
    lines.push("Execution focus:");
    lines.push("1) Do not scale size until win rate is >= target on validated samples.");
    lines.push("2) Enforce exits mechanically: 50% take-profit, 7 DTE close, 200% max loss.");
    lines.push("3) Run post-trade root-cause on each loss and adjust entry filters before adding risk.");
  }

  return lines.join("\n");
}

function truncate(text, maxLen) {
  if (!text) return "";
  if (text.length <= maxLen) return text;
  return text.slice(0, maxLen).trimEnd() + "...";
}

function normalizeLesson(raw) {
  const id = raw.id || raw.lesson_id || raw.slug || "unknown";
  const title = raw.title || raw.name || id;
  const severity = raw.severity || "MEDIUM";
  const summarySource =
    raw.summary || raw.snippet || raw.content || raw.text || "";
  const summary = truncate(summarySource.replace(/\s+/g, " "), 240);
  const contentSource = raw.content || raw.snippet || raw.summary || "";
  const content = truncate(contentSource.replace(/\s+/g, " "), 2000);

  return {
    id,
    title,
    summary,
    content,
    severity,
    category: raw.category || "Lesson",
    tags: Array.isArray(raw.tags) ? raw.tags : [],
    date: raw.date || raw.created_at || "",
    file: raw.file || raw.source || "",
  };
}

function buildLessonsContext(lessons, source) {
  const header = `KEY LESSONS (${source || "unknown"}):`;
  if (!Array.isArray(lessons) || lessons.length === 0) {
    return `${header}\n- No lessons available for this query.`;
  }

  const lines = lessons.map((lesson) => {
    const l = normalizeLesson(lesson);
    return `- ${l.id}: ${l.title} (${l.severity}) - ${l.summary}`;
  });

  return [header, ...lines].join("\n");
}

async function fetchLessonsIndex() {
  const now = Date.now();
  if (
    lessonsCache.data &&
    now - lessonsCache.fetchedAt < LESSONS_CACHE_TTL_MS
  ) {
    return lessonsCache.data;
  }

  const sources = [LESSONS_INDEX_URL, LESSONS_INDEX_FALLBACK_URL];
  for (const url of sources) {
    try {
      const res = await fetch(url, { cf: { cacheTtl: 300 } });
      if (!res.ok) continue;
      const data = await res.json();
      if (Array.isArray(data)) {
        lessonsCache = { data, fetchedAt: now };
        return data;
      }
    } catch {
      // try next source
    }
  }

  return null;
}

function keywordSearch(lessons, query, topK) {
  const q = query.toLowerCase();
  return lessons
    .map((lesson) => {
      const normalized = normalizeLesson(lesson);
      const searchable = [
        normalized.title,
        normalized.summary,
        normalized.content,
        normalized.category,
        normalized.tags.join(" "),
      ]
        .join(" ")
        .toLowerCase();
      const score = searchable.includes(q) ? 1 : 0;
      return { lesson: normalized, score };
    })
    .filter((item) => item.score > 0)
    .slice(0, topK)
    .map((item) => item.lesson);
}

function resolveRagSearchUrl(env) {
  const raw =
    (env && (env.RAG_SEARCH_URL || env.RAG_WEBHOOK_URL)) ||
    DEFAULT_RAG_SEARCH_URL ||
    DEFAULT_RAG_WEBHOOK_URL;
  if (!raw) return "";
  if (raw.includes("/rag-search")) {
    return raw;
  }
  return `${raw.replace(/\/$/, "")}/rag-search`;
}

async function fetchRagSearch(query, topK, env) {
  const ragSearchUrl = resolveRagSearchUrl(env);
  if (!ragSearchUrl) return null;
  try {
    const res = await fetch(ragSearchUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, top_k: topK }),
    });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

async function getLessonsForQuery(query, topK, env) {
  const rag = await fetchRagSearch(query, topK, env);
  if (rag && Array.isArray(rag.results) && rag.results.length > 0) {
    return {
      results: rag.results.map(normalizeLesson),
      source: rag.source || "lancedb",
    };
  }

  const index = await fetchLessonsIndex();
  if (Array.isArray(index)) {
    return {
      results: keywordSearch(index, query, topK),
      source: "keyword_index",
    };
  }

  return { results: [], source: "none" };
}

/**
 * Build a dynamic system prompt with live position data + lesson context.
 */
function buildSystemPrompt(liveData, lessons, source) {
  const now = new Date();
  const lines = [];

  lines.push(SYSTEM_PREFIX);
  lines.push("");
  lines.push(buildLessonsContext(lessons, source));
  lines.push("");
  lines.push("CRITICAL RESPONSE PROTOCOL:");
  lines.push("- Report North Star status as a hard gate (PASS/ACTIVE), not a vibe.");
  lines.push("- Always include exact metrics: win rate, target win rate, sample size, paper day/target day.");
  lines.push("- If target is not met, provide only concrete corrective actions.");
  lines.push("- Never claim North Star progress without citing live numbers.");
  lines.push("");

  if (!liveData) {
    return lines.join("\n");
  }

  lines.push(
    "You also have access to LIVE portfolio data below. Use both lessons and live data to give actionable, position-specific advice.\n",
  );

  // Portfolio overview
  const port = liveData.portfolio || {};
  const paper = liveData.paper_account || {};
  const risk = liveData.risk || {};
  lines.push("=== LIVE PORTFOLIO STATUS ===");
  lines.push(`Equity: $${(port.equity || 0).toLocaleString()}`);
  lines.push(`Cash: $${(port.cash || 0).toLocaleString()}`);
  lines.push(`Daily Change: $${paper.daily_change || 0}`);
  lines.push(`Unrealized P/L: $${risk.unrealized_pl || 0}`);
  lines.push(`Total P/L: $${(risk.total_pl || 0).toLocaleString()}`);
  lines.push(
    `Win Rate: ${paper.win_rate || "N/A"}% (${paper.win_rate_sample_size || 0} trades)`,
  );
  lines.push("");

  const northStar = computeNorthStarSnapshot(liveData);
  lines.push("=== NORTH STAR GATE ===");
  lines.push(`Status: ${northStar.status}`);
  lines.push(`Gate: ${northStar.gate}`);
  lines.push(
    `Win Rate Gap: ${northStar.winRateGap >= 0 ? "+" : ""}${northStar.winRateGap.toFixed(1)} pp`,
  );
  lines.push(
    `Validation: ${northStar.sampleSize} trades, day ${northStar.day}/${northStar.targetDays}`,
  );
  if (northStar.asOf) {
    lines.push(`Data As Of: ${northStar.asOf}`);
  }
  lines.push("");

  // Paper trading progress
  const pt = liveData.paper_trading || {};
  if (pt.start_date) {
    const startDate = new Date(pt.start_date);
    const dayNum = Math.floor((now - startDate) / 86400000);
    lines.push("=== PAPER TRADING PROGRESS ===");
    lines.push(
      `Day ${dayNum} of ${pt.target_duration_days || 90} (target: ${(pt.target_win_rate || 0.8) * 100}% win rate)`,
    );
    lines.push("");
  }

  // Positions with decoded symbols and iron condor detection
  const positions = liveData.positions || [];
  if (positions.length > 0) {
    lines.push("=== OPEN POSITIONS ===");

    // Group by expiry to detect iron condors
    const byExpiry = {};
    for (const pos of positions) {
      const parsed = parseOccSymbol(pos.symbol);
      if (!parsed) continue;
      if (!byExpiry[parsed.expiry]) byExpiry[parsed.expiry] = [];
      byExpiry[parsed.expiry].push({ ...pos, parsed });
    }

    for (const [expiry, legs] of Object.entries(byExpiry)) {
      const expiryDate = new Date(expiry + "T16:00:00Z");
      const dte = Math.max(0, Math.ceil((expiryDate - now) / 86400000));

      // Check if this is an iron condor (4 legs: short put, long put, short call, long call)
      const puts = legs.filter((l) => l.parsed.type === "put");
      const calls = legs.filter((l) => l.parsed.type === "call");
      const isIronCondor = puts.length === 2 && calls.length === 2;

      if (isIronCondor) {
        const shortPut = puts.find((l) => l.qty < 0);
        const longPut = puts.find((l) => l.qty > 0);
        const shortCall = calls.find((l) => l.qty < 0);
        const longCall = calls.find((l) => l.qty > 0);

        const netPnl = legs.reduce((sum, l) => sum + (l.pnl || 0), 0);
        const netValue = legs.reduce((sum, l) => sum + (l.value || 0), 0);

        lines.push(
          `IRON CONDOR - ${legs[0].parsed.ticker} exp ${expiry} (${dte} DTE)`,
        );
        if (shortPut && longPut) {
          lines.push(
            `  Put spread: -${shortPut.parsed.strike}/${longPut.parsed.strike} (P/L: $${shortPut.pnl + longPut.pnl})`,
          );
        }
        if (shortCall && longCall) {
          lines.push(
            `  Call spread: -${shortCall.parsed.strike}/${longCall.parsed.strike} (P/L: $${shortCall.pnl + longCall.pnl})`,
          );
        }
        lines.push(`  Net P/L: $${netPnl} | Net value: $${netValue}`);

        // Exit rule triggers
        const triggers = [];
        if (dte <= 7) triggers.push("7 DTE EXIT RULE TRIGGERED (LL-268)");
        if (dte <= 14) triggers.push("Approaching 7 DTE - monitor closely");
        if (triggers.length > 0) {
          lines.push(`  EXIT ALERTS: ${triggers.join("; ")}`);
        }
      } else {
        for (const leg of legs) {
          const dir = leg.qty > 0 ? "long" : "short";
          lines.push(
            `${leg.parsed.ticker} ${expiry} ${leg.parsed.strike} ${leg.parsed.type} (${dir}) | P/L: $${leg.pnl} | ${dte} DTE`,
          );
        }
      }
      lines.push("");
    }
  }

  // Trade history with weekly aggregation
  const trades = liveData.trade_history || [];
  if (trades.length > 0) {
    lines.push("=== TRADE HISTORY (recent) ===");

    // Group trades by week (ISO week starting Monday)
    const byWeek = {};
    for (const trade of trades) {
      if (!trade.filled_at) continue;
      const d = new Date(trade.filled_at);
      if (Number.isNaN(d.getTime())) continue;
      // Get Monday of that week
      const day = d.getUTCDay();
      const monday = new Date(d);
      monday.setUTCDate(d.getUTCDate() - ((day + 6) % 7));
      const weekKey = monday.toISOString().slice(0, 10);
      if (!byWeek[weekKey]) byWeek[weekKey] = [];
      byWeek[weekKey].push(trade);
    }

    // Sort weeks descending and show last 4 weeks
    const sortedWeeks = Object.keys(byWeek).sort().reverse().slice(0, 4);
    for (const weekStart of sortedWeeks) {
      const weekTrades = byWeek[weekStart];
      const weekEnd = new Date(weekStart);
      weekEnd.setUTCDate(weekEnd.getUTCDate() + 6);
      const weekEndStr = weekEnd.toISOString().slice(0, 10);
      lines.push(`Week of ${weekStart} to ${weekEndStr}: ${weekTrades.length} fills`);
      for (const t of weekTrades.slice(0, 8)) {
        const sym = t.symbol ? parseOccSymbol(t.symbol) : null;
        const symStr = sym
          ? `${sym.ticker} ${sym.strike} ${sym.type} ${sym.expiry}`
          : (t.symbol || "multi-leg close");
        const side = String(t.side || "").replace("OrderSide.", "");
        lines.push(`  ${t.filled_at.slice(0, 10)} ${side} ${symStr} @ $${t.price}`);
      }
      if (weekTrades.length > 8) {
        lines.push(`  ... and ${weekTrades.length - 8} more fills`);
      }
    }
    lines.push("");

    // Equity snapshots for weekly P/L calculation
    const history = (liveData.sync_health || {}).history || [];
    if (history.length > 0) {
      lines.push("=== EQUITY SNAPSHOTS ===");
      // Show first and last equity per day for P/L calculation
      const byDay = {};
      for (const h of history) {
        const day = (h.timestamp || "").slice(0, 10);
        if (!day || !h.equity) continue;
        if (!byDay[day]) byDay[day] = { first: h.equity, last: h.equity };
        byDay[day].last = h.equity;
      }
      const days = Object.keys(byDay).sort().reverse().slice(0, 7);
      for (const day of days) {
        const { first, last } = byDay[day];
        const change = last - first;
        lines.push(`  ${day}: $${formatCurrency(last)} (intraday: ${change >= 0 ? "+" : ""}$${formatCurrency(change)})`);
      }
      lines.push(`  Baseline: $100,000 (started Jan 30, 2026)`);
      lines.push("");
    }
  }

  return lines.join("\n");
}

function classifyAnthropicFailureReason(errorText) {
  if (!errorText) return null;

  const text = String(errorText).toLowerCase();
  if (text.includes("credit balance is too low") || text.includes("insufficient")) {
    return "Anthropic credits exhausted";
  }
  if (text.includes("invalid x-api-key") || text.includes("authentication_error")) {
    return "Anthropic API key invalid/misconfigured";
  }
  if (text.includes("rate limit") || text.includes("too many requests")) {
    return "Anthropic rate limited";
  }
  if (text.includes("overloaded")) {
    return "Anthropic overloaded";
  }

  return "Anthropic API error";
}

function buildFallbackReply(query, lessons, source, reason) {
  const reasonSuffix = reason ? ` (${reason})` : "";
  const header = `AI chat is temporarily unavailable${reasonSuffix}. Here are the most relevant lessons I can find:`;
  const context = buildLessonsContext(lessons, source);
  return [header, "", `Query: ${query}`, "", context].join("\n");
}

export default {
  async fetch(request, env) {
    // Handle CORS preflight
    if (request.method === "OPTIONS") {
      return new Response(null, {
        headers: {
          "Access-Control-Allow-Origin": "*",
          "Access-Control-Allow-Methods": "POST, OPTIONS",
          "Access-Control-Allow-Headers": "Content-Type",
        },
      });
    }

    if (request.method !== "POST") {
      return new Response("Method not allowed", { status: 405 });
    }

    try {
      const payload = await request.json();
      const mode = payload.mode || "chat";

      if (mode === "search") {
        const query = (payload.query || payload.message || "").trim();
        if (!query) {
          return new Response(JSON.stringify({ error: "Query required" }), {
            status: 400,
            headers: {
              "Content-Type": "application/json",
              "Access-Control-Allow-Origin": "*",
            },
          });
        }

        const topK = Number(payload.top_k || 5);
        const { results, source } = await getLessonsForQuery(query, topK, env);

        return new Response(JSON.stringify({ results, source }), {
          headers: {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
          },
        });
      }

      const { message, history } = payload;

      if (!message || typeof message !== "string") {
        return new Response(JSON.stringify({ error: "Message required" }), {
          status: 400,
          headers: {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
          },
        });
      }

      // Build messages array with history for context
      const messages = [];

      // Add conversation history if provided (last 10 messages max)
      if (Array.isArray(history)) {
        const recentHistory = history.slice(-10);
        for (const msg of recentHistory) {
          if (msg.role && msg.content) {
            messages.push({ role: msg.role, content: msg.content });
          }
        }
      }

      // Add current message
      messages.push({ role: "user", content: message });

      // Fetch live portfolio data.
      const liveData = await fetchLiveData();

      if (isNorthStarQuestion(message)) {
        const deterministicReply = buildNorthStarDeterministicReply(liveData);
        return new Response(JSON.stringify({ reply: deterministicReply }), {
          headers: {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
          },
        });
      }

      // Deterministic P/L answers (avoid hallucinated performance numbers).
      const pnlReply = await buildDeterministicPnlReply(message, liveData);
      if (pnlReply) {
        return new Response(
          JSON.stringify({ reply: pnlReply, deterministic: true }),
          {
            headers: {
              "Content-Type": "application/json",
              "Access-Control-Allow-Origin": "*",
            },
          },
        );
      }

      // Lessons for RAG context (LanceDB-first with fallback).
      const { results: lessons, source } = await getLessonsForQuery(
        message,
        8,
        env,
      );

      const systemPrompt = buildSystemPrompt(liveData, lessons, source);

      let reply = null;
      let failureReason = null;
      try {
        const response = await fetch("https://api.anthropic.com/v1/messages", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "x-api-key": env.ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
          },
          body: JSON.stringify({
            model: "claude-3-5-haiku-20241022",
            max_tokens: 1024,
            system: systemPrompt,
            messages: messages,
          }),
        });

        if (!response.ok) {
          const error = await response.text();
          console.error("Claude API error:", error);
          failureReason = classifyAnthropicFailureReason(error);
        } else {
          const data = await response.json();
          reply = data.content[0]?.text || "No response";
        }
      } catch (error) {
        console.error("Claude API fetch failed:", error);
        failureReason = "Anthropic request failed";
      }

      if (!reply) {
        const fallbackReply = buildFallbackReply(
          message,
          lessons,
          source,
          failureReason,
        );
        return new Response(
          JSON.stringify({ reply: fallbackReply, fallback: true }),
          {
            headers: {
              "Content-Type": "application/json",
              "Access-Control-Allow-Origin": "*",
            },
          },
        );
      }

      return new Response(JSON.stringify({ reply }), {
        headers: {
          "Content-Type": "application/json",
          "Access-Control-Allow-Origin": "*",
        },
      });
    } catch (error) {
      console.error("Worker error:", error);
      return new Response(JSON.stringify({ error: error.message }), {
        status: 500,
        headers: {
          "Content-Type": "application/json",
          "Access-Control-Allow-Origin": "*",
        },
      });
    }
  },
};
