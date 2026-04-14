---
layout: null
title: SPY Options Validation Platform
permalink: /
---

<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <title>SPY Options Validation Platform</title>
    <meta
      name="description"
      content="Broker-backed SPY options validation platform with hard risk gates, paired-trade accounting, and live operator surfaces."
    >
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
      :root {
        --ink: #102131;
        --muted: #5e6c78;
        --accent: #0d63ff;
        --accent-2: #ec7a1c;
        --bg: #f4f0e8;
        --panel: rgba(255, 255, 255, 0.82);
        --border: rgba(16, 33, 49, 0.12);
        --good: #1f8f4e;
        --bad: #b43b29;
        --shadow: 0 24px 60px rgba(16, 33, 49, 0.12);
      }

      * {
        box-sizing: border-box;
      }

      body {
        margin: 0;
        color: var(--ink);
        background:
          radial-gradient(circle at top left, rgba(13, 99, 255, 0.11), transparent 36%),
          radial-gradient(circle at bottom right, rgba(236, 122, 28, 0.14), transparent 32%),
          linear-gradient(180deg, #f8f5ee 0%, #efe8db 100%);
        font-family: "Avenir Next", "Segoe UI", sans-serif;
      }

      .shell {
        max-width: 1180px;
        margin: 0 auto;
        padding: 28px 20px 80px;
      }

      .topbar {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 16px;
        margin-bottom: 28px;
        font-size: 14px;
      }

      .brand {
        display: flex;
        align-items: center;
        gap: 10px;
        font-weight: 700;
        letter-spacing: 0.02em;
      }

      .brand-mark {
        width: 12px;
        height: 12px;
        border-radius: 999px;
        background: linear-gradient(135deg, var(--accent), var(--accent-2));
      }

      .nav {
        display: flex;
        flex-wrap: wrap;
        gap: 12px;
      }

      .nav a,
      .cta,
      .ghost {
        text-decoration: none;
        color: var(--ink);
        border: 1px solid var(--border);
        background: rgba(255, 255, 255, 0.68);
        padding: 11px 14px;
        border-radius: 999px;
        font-weight: 600;
      }

      .cta {
        background: linear-gradient(135deg, var(--accent), #4c8eff);
        border-color: transparent;
        color: #fff;
      }

      .hero {
        display: grid;
        grid-template-columns: minmax(0, 1.3fr) minmax(340px, 0.9fr);
        gap: 24px;
        align-items: stretch;
      }

      .panel {
        background: var(--panel);
        border: 1px solid var(--border);
        border-radius: 28px;
        box-shadow: var(--shadow);
        backdrop-filter: blur(12px);
      }

      .hero-copy {
        padding: 38px;
      }

      .eyebrow {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 8px 12px;
        border-radius: 999px;
        background: rgba(13, 99, 255, 0.08);
        color: var(--accent);
        font-size: 12px;
        letter-spacing: 0.08em;
        font-weight: 800;
        text-transform: uppercase;
      }

      h1 {
        margin: 18px 0 12px;
        font-family: "Iowan Old Style", "Palatino Linotype", Georgia, serif;
        font-size: clamp(44px, 8vw, 72px);
        line-height: 0.94;
        letter-spacing: -0.04em;
      }

      .hero-copy p {
        margin: 0;
        max-width: 54ch;
        font-size: 18px;
        line-height: 1.65;
        color: var(--muted);
      }

      .hero-actions {
        display: flex;
        flex-wrap: wrap;
        gap: 12px;
        margin-top: 26px;
      }

      .hero-status {
        padding: 32px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
      }

      .status-label {
        font-size: 12px;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: var(--muted);
        font-weight: 800;
      }

      .status-pill {
        margin-top: 12px;
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 10px 14px;
        border-radius: 999px;
        font-weight: 800;
        text-transform: capitalize;
      }

      .status-halted {
        background: rgba(180, 59, 41, 0.12);
        color: var(--bad);
      }

      .status-active,
      .status-defensive {
        background: rgba(13, 99, 255, 0.1);
        color: var(--accent);
      }

      .status-ok {
        background: rgba(31, 143, 78, 0.12);
        color: var(--good);
      }

      .metric-grid {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 16px;
        margin-top: 24px;
      }

      .metric {
        padding: 22px;
      }

      .metric h2 {
        margin: 0;
        font-size: 15px;
        color: var(--muted);
        font-weight: 700;
      }

      .metric strong {
        display: block;
        margin-top: 10px;
        font-size: clamp(24px, 3vw, 34px);
        line-height: 1.05;
      }

      .metric small {
        display: block;
        margin-top: 8px;
        color: var(--muted);
        line-height: 1.5;
      }

      .section-grid {
        display: grid;
        grid-template-columns: minmax(0, 1.05fr) minmax(0, 0.95fr);
        gap: 18px;
        margin-top: 18px;
      }

      .section {
        padding: 28px;
      }

      .section h3 {
        margin: 0 0 14px;
        font-size: 14px;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: var(--muted);
      }

      .section p,
      .section li {
        color: var(--muted);
        line-height: 1.7;
      }

      .section ul {
        margin: 0;
        padding-left: 18px;
      }

      .timestamp {
        margin-top: 18px;
        color: var(--muted);
        font-size: 14px;
      }

      .blocker {
        font-weight: 700;
        color: var(--ink);
      }

      @media (max-width: 960px) {
        .hero,
        .section-grid,
        .metric-grid {
          grid-template-columns: 1fr;
        }
      }
    </style>

  </head>
  <body>
    <main class="shell">
      <div class="topbar">
        <div class="brand">
          <span class="brand-mark"></span>
          <span>SPY Options Validation Platform</span>
        </div>
        <nav class="nav">
          <a href="https://github.com/IgorGanapolsky/trading/wiki/Progress-Dashboard">Operator Dashboard</a>
          <a href="{{ '/blog.html' | relative_url }}">Research</a>
          <a href="https://github.com/IgorGanapolsky/trading/wiki">Wiki</a>
          <a href="https://github.com/IgorGanapolsky/trading">GitHub</a>
        </nav>
      </div>

      <section class="hero">
        <article class="panel hero-copy">
          <div class="eyebrow">Live Public Surface</div>
          <h1>Current truth, not frozen marketing.</h1>
          <p>
            This system should be judged by broker-backed scorecards, paired-trade accounting, and active gate state.
            This page renders from a generated public-status bundle so investor-facing copy stays congruent with the ledgers.
          </p>
          <div class="hero-actions">
            <a class="cta" href="https://github.com/IgorGanapolsky/trading/wiki/Progress-Dashboard">Open operator dashboard</a>
            <a class="ghost" href="https://github.com/IgorGanapolsky/trading">View repository</a>
          </div>
          <div class="timestamp" id="generated-at">Loading current public status…</div>
        </article>

        <aside class="panel hero-status">
          <div>
            <div class="status-label">Current Operating Status</div>
            <div class="status-pill status-active" id="public-status-pill">Loading…</div>
          </div>
          <div>
            <div class="status-label">Exact Blocker</div>
            <p class="blocker" id="blocker-text">Fetching canonical gate state…</p>
          </div>
        </aside>
      </section>

      <section class="metric-grid">
        <article class="panel metric">
          <h2>Paper Equity</h2>
          <strong id="paper-equity">—</strong>
          <small>Directly derived from the current public-status bundle.</small>
        </article>
        <article class="panel metric">
          <h2>Today P/L</h2>
          <strong id="paper-pnl">—</strong>
          <small id="paper-pnl-detail">Detailed decomposition is sourced from the operator scorecard.</small>
        </article>
        <article class="panel metric">
          <h2>Closed Trades</h2>
          <strong id="closed-trades">—</strong>
          <small id="win-rate">—</small>
        </article>
        <article class="panel metric">
          <h2>Gate Mode</h2>
          <strong id="gate-mode">—</strong>
          <small id="gate-detail">—</small>
        </article>
      </section>

      <section class="section-grid">
        <article class="panel section">
          <h3>Why This Exists</h3>
          <p id="summary-text">
            Loading broker-backed daily summary…
          </p>
          <p>
            The platform’s value is operational discipline: hard risk gates, paired-trade accounting, current public status,
            and a clean line between live facts and aspirational strategy.
          </p>
        </article>
        <article class="panel section">
          <h3>Current Constraints</h3>
          <ul id="constraints-list">
            <li>Loading current constraints…</li>
          </ul>
        </article>
      </section>
    </main>

    <script>
      const STATUS_URL = "{{ '/data/public_status.json' | relative_url }}";

      function formatMoney(value) {
        if (typeof value !== "number") return "n/a";
        return new Intl.NumberFormat("en-US", {
          style: "currency",
          currency: "USD",
          maximumFractionDigits: 2
        }).format(value);
      }

      function formatPct(value) {
        if (typeof value !== "number") return "n/a";
        return `${value.toFixed(2)}%`;
      }

      function statusClass(value) {
        if (value === "halted") return "status-halted";
        if (value === "defensive") return "status-defensive";
        return "status-ok";
      }

      function render(status) {
        const paper = status.paper || {};
        const ledger = status.ledger || {};
        const gate = status.gate || {};
        const narrative = status.narrative || {};

        document.getElementById("generated-at").textContent =
          `Generated from canonical public status at ${status.generated_at_et}.`;

        const pill = document.getElementById("public-status-pill");
        pill.textContent = status.system?.public_status || "unknown";
        pill.className = `status-pill ${statusClass(status.system?.public_status)}`;

        document.getElementById("blocker-text").textContent =
          gate.blocker_reason || "No blocker reported.";

        document.getElementById("paper-equity").textContent = formatMoney(paper.equity);
        document.getElementById("paper-pnl").textContent = formatMoney(paper.total_pnl_today);
        if (
          typeof paper.realized_pnl_today === "number" ||
          typeof paper.unrealized_pnl_today === "number" ||
          paper.fills_today_count !== null && paper.fills_today_count !== undefined
        ) {
          document.getElementById("paper-pnl-detail").textContent =
            `Realized ${formatMoney(paper.realized_pnl_today)} | Unrealized ${formatMoney(paper.unrealized_pnl_today)} | Fills ${paper.fills_today_count ?? "n/a"}`;
        } else {
          document.getElementById("paper-pnl-detail").textContent =
            "Detailed realized/unrealized decomposition is available in the operator scorecard.";
        }

        document.getElementById("closed-trades").textContent = `${ledger.closed_trades_total ?? "n/a"}`;
        document.getElementById("win-rate").textContent =
          `Win rate ${formatPct(ledger.win_rate_pct)} | Profit factor ${ledger.profit_factor ?? "n/a"}`;

        document.getElementById("gate-mode").textContent = gate.mode || "unknown";
        document.getElementById("gate-detail").textContent =
          `Scale allowed: ${gate.scale_allowed} | Max position pct: ${gate.recommended_max_position_pct ?? "n/a"}`;

        document.getElementById("summary-text").textContent =
          narrative.summary || "No summary available.";

        const constraints = [
          `Current gate mode: ${gate.mode || "unknown"}`,
          `Block new positions: ${gate.block_new_positions}`,
          `Qualified setups this week: ${gate.qualified_setups_this_week ?? "n/a"}`,
          `Closed trades this week: ${gate.closed_trades_this_week ?? "n/a"}`,
          `Scaling gate: ${gate.scaling_gate_closed_trades_observed ?? "n/a"} / ${gate.scaling_gate_min_closed_trades ?? "n/a"}`
        ];
        const list = document.getElementById("constraints-list");
        list.innerHTML = constraints.map((item) => `<li>${item}</li>`).join("");
      }

      fetch(STATUS_URL, { cache: "no-store" })
        .then((response) => {
          if (!response.ok) throw new Error(`HTTP ${response.status}`);
          return response.json();
        })
        .then(render)
        .catch((error) => {
          document.getElementById("generated-at").textContent =
            `Public status fetch failed: ${error.message}. Use the operator dashboard for canonical status.`;
          document.getElementById("public-status-pill").textContent = "fetch-failed";
          document.getElementById("public-status-pill").className = "status-pill status-halted";
          document.getElementById("blocker-text").textContent =
            "The current public-status bundle could not be loaded. This is itself a public-surface failure.";
        });
    </script>

  </body>
</html>
