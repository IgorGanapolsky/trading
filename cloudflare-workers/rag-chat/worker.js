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

  return lines.join("\n");
}

function buildFallbackReply(query, lessons, source) {
  const header =
    "AI chat is temporarily unavailable. Here are the most relevant lessons I can find:";
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

      // Fetch live portfolio data + lessons (LanceDB-first with fallback)
      const liveData = await fetchLiveData();
      const { results: lessons, source } = await getLessonsForQuery(
        message,
        8,
        env,
      );
      const systemPrompt = buildSystemPrompt(liveData, lessons, source);

      let reply = null;
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
        } else {
          const data = await response.json();
          reply = data.content[0]?.text || "No response";
        }
      } catch (error) {
        console.error("Claude API fetch failed:", error);
      }

      if (!reply) {
        const fallbackReply = buildFallbackReply(message, lessons, source);
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
