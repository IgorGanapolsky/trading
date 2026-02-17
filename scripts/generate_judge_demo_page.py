#!/usr/bin/env python3
# ruff: noqa: S608
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

METRIC_RE = re.compile(r"^- ([^:]+): (.+) \[([A-Z]+)\] \((.*)\)$")


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def parse_kv(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in read_text(path).splitlines():
        for m in re.finditer(r"([A-Za-z0-9_]+)=(\S+)", line):
            out[m.group(1)] = m.group(2)
    return out


def as_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except Exception:
        return default


def maybe_float(value: object) -> float | None:
    try:
        return float(value)  # type: ignore[arg-type]
    except Exception:
        return None


def parse_smoke_response(smoke_response: dict) -> dict[str, object]:
    model = str(smoke_response.get("model", "unknown"))
    service_tier = str(smoke_response.get("service_tier", "unknown"))
    request_id = str(smoke_response.get("id", "n/a"))
    usage = smoke_response.get("usage", {}) if isinstance(smoke_response, dict) else {}
    prompt_tokens = int(usage.get("prompt_tokens", 0) or 0)
    completion_tokens = int(usage.get("completion_tokens", 0) or 0)
    total_tokens = int(usage.get("total_tokens", 0) or 0)

    candidates: list[str] = []
    choices_payload = smoke_response.get("choices") if isinstance(smoke_response, dict) else None
    if isinstance(choices_payload, list):
        for choice in choices_payload:
            if not isinstance(choice, dict):
                continue
            message = choice.get("message", {})
            if isinstance(message, dict) and isinstance(message.get("content"), str):
                candidates.append(message["content"])
    elif isinstance(choices_payload, str):
        candidates.append(choices_payload)

    router_check = False
    for content in candidates:
        fenced_match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", content, re.IGNORECASE)
        json_candidate = fenced_match.group(1) if fenced_match else None
        if not json_candidate:
            block_match = re.search(r"\{[\s\S]*\}", content)
            json_candidate = block_match.group(0) if block_match else None
        if not json_candidate:
            continue
        try:
            payload = json.loads(json_candidate)
            if isinstance(payload, dict) and "router_check" in payload:
                router_check = bool(payload.get("router_check"))
                break
        except Exception:
            continue

    return {
        "model": model,
        "service_tier": service_tier,
        "request_id": request_id,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "router_check": router_check,
    }


def checklist_progress(path: Path) -> tuple[int, int]:
    done = 0
    total = 0
    for line in read_text(path).splitlines():
        if line.startswith("- [x] ") or line.startswith("- [ ] "):
            total += 1
            if line.startswith("- [x] "):
                done += 1
    return done, total


def parse_scorecard_metrics(path: Path) -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    for line in read_text(path).splitlines():
        m = METRIC_RE.match(line.strip())
        if m:
            rows.append((m.group(1), m.group(2), m.group(3)))
    return rows


def derive_loop_status(loop_status: dict[str, str]) -> tuple[str, str]:
    cycle = loop_status.get("cycle")
    profile = loop_status.get("profile")

    iteration = loop_status.get("iteration")
    if not cycle and iteration:
        cycle = f"iteration {iteration}"

    if not profile:
        ruff_exit = loop_status.get("ruff_exit")
        pytest_exit = loop_status.get("pytest_exit")
        if ruff_exit is not None and pytest_exit is not None:
            profile = "healthy" if ruff_exit == "0" and pytest_exit == "0" else "degraded"

    return cycle or "unknown", profile or "unknown"


def status_chip(status: str) -> str:
    if status == "PASS":
        return '<span class="chip pass">PASS</span>'
    if status == "WARN":
        return '<span class="chip warn">WARN</span>'
    return '<span class="chip unknown">UNKNOWN</span>'


def _snapshot_html(manifest: dict) -> str:
    latest = manifest.get("latest", {}) if isinstance(manifest, dict) else {}
    if not isinstance(latest, dict):
        latest = {}
    progress = latest.get("progress", {}) if isinstance(latest.get("progress"), dict) else {}
    progress_time = progress.get("captured_at_utc", "unknown")

    # Keep this focused for judges: one compact screenshot with Tetrate gateway evidence.
    tetrate_snapshot_url = "/trading/assets/snapshots/judge_tetrate_metrics_latest.png"
    dashboard_url = "/trading/lessons/ops-status.html"

    return f"""
      <article class="card span12">
        <div class="k">Most Important Screenshot (Tetrate Evidence)</div>
        <a href="{dashboard_url}">Open full evidence page</a>
        <a href="{dashboard_url}"><img class="snap" src="{tetrate_snapshot_url}" alt="Tetrate metrics and evidence pipeline snapshot"></a>
        <div class="k">Captured: {progress_time}</div>
      </article>
    """


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate polished judge demo page from artifacts."
    )
    parser.add_argument("--repo-root", default=".", help="Repository root")
    parser.add_argument("--out", default="docs/lessons/judge-demo.html", help="Output HTML path")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    out = Path(args.out).resolve() if Path(args.out).is_absolute() else (repo_root / args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    checklist = repo_root / "artifacts/tars/judge_demo_checklist.md"
    scorecard = repo_root / "artifacts/devloop/profit_readiness_scorecard.md"
    smoke = parse_kv(repo_root / "artifacts/tars/smoke_metrics.txt")
    smoke_response = read_json(repo_root / "artifacts/tars/smoke_response.json")
    exec_daily = read_json(repo_root / "artifacts/tars/execution_quality_daily.json")
    loop_status = parse_kv(repo_root / "artifacts/devloop/status.txt")
    system_state = read_json(repo_root / "data/system_state.json")
    snapshot_manifest = read_json(repo_root / "docs/data/alpaca_snapshots.json")

    done, total = checklist_progress(checklist)
    metrics = parse_scorecard_metrics(scorecard)
    loop_cycle, loop_profile = derive_loop_status(loop_status)
    latency = smoke.get("latency_ms", "n/a")
    est_cost = smoke.get("estimated_total_cost_usd", "n/a")
    gateway_host = smoke.get("gateway_base_url_host", "unknown")
    gateway_key_source = smoke.get("gateway_key_source", "unknown")
    cost_basis = smoke.get("cost_estimate_basis", "unknown")
    smoke_meta = parse_smoke_response(smoke_response)
    smoke_model = str(smoke_meta["model"])
    smoke_service_tier = str(smoke_meta["service_tier"])
    smoke_request_id = str(smoke_meta["request_id"])
    prompt_tokens = int(smoke_meta["prompt_tokens"])
    completion_tokens = int(smoke_meta["completion_tokens"])
    total_tokens = int(smoke_meta["total_tokens"])
    router_check = bool(smoke_meta["router_check"])

    has_exec_daily = all(
        key in exec_daily
        for key in (
            "success_rate",
            "actionable_rate",
            "run_count",
            "p95_latency_ms",
            "generated_at_utc",
        )
    )
    if has_exec_daily:
        exec_success = exec_daily.get("success_rate")
        exec_actionable = exec_daily.get("actionable_rate")
        exec_runs = exec_daily.get("run_count")
        exec_p95 = exec_daily.get("p95_latency_ms")
        generated_at = exec_daily.get("generated_at_utc")
        smoke_model = str(exec_daily.get("model") or smoke_model)
        prompt_tokens = int(exec_daily.get("prompt_tokens") or prompt_tokens)
        completion_tokens = int(exec_daily.get("completion_tokens") or completion_tokens)
        total_tokens = int(exec_daily.get("total_tokens") or total_tokens)
        router_check = bool(exec_daily.get("router_check", router_check))
    else:
        has_smoke_result = bool(smoke_response.get("choices")) or bool(smoke_response.get("id"))
        exec_runs = 1 if has_smoke_result else 0
        exec_success = 100.0 if has_smoke_result else 0.0
        exec_actionable = 0.0
        exec_p95 = smoke.get("latency_ms", "n/a")
        generated_at = smoke.get("timestamp_utc", "n/a")
    fallback_probe_ok_count = exec_daily.get("fallback_probe_ok_count", 0) if has_exec_daily else 0
    est_cost_value = maybe_float(est_cost) or 0.0
    est_cost_display = f"{est_cost_value:.8f}"
    cost_per_1k = (est_cost_value / total_tokens) * 1000.0 if total_tokens > 0 else 0.0
    smoke_probe_ok = bool(smoke_response.get("id")) and not bool(smoke_response.get("error"))
    smoke_probe_text = "PASS" if smoke_probe_ok else "WARN"
    smoke_probe_chip = status_chip("PASS" if smoke_probe_ok else "WARN")

    paper = system_state.get("paper_account", {}) if isinstance(system_state, dict) else {}
    north_star = system_state.get("north_star", {}) if isinstance(system_state, dict) else {}
    starting_balance = float(paper.get("starting_balance", 0.0) or 0.0)
    current_equity = float(paper.get("current_equity", paper.get("equity", 0.0)) or 0.0)
    total_pl = float(paper.get("total_pl", current_equity - starting_balance) or 0.0)
    total_pl_pct = float(paper.get("total_pl_pct", 0.0) or 0.0)
    paper_win_rate = float(paper.get("win_rate", 0.0) or 0.0)
    paper_win_samples = int(paper.get("win_rate_sample_size", 0) or 0)
    north_star_prob = north_star.get("probability_label", "unknown")
    repo_blob = "https://github.com/IgorGanapolsky/trading/blob/main"

    metric_rows = (
        "\n".join(
            f"<tr><td>{name}</td><td>{value}</td><td>{status_chip(status)}</td></tr>"
            for name, value, status in metrics[:12]
        )
        or '<tr><td colspan="3">No scorecard metrics found yet.</td></tr>'
    )
    snapshot_section = _snapshot_html(snapshot_manifest)
    router_check_text = "PASS" if router_check else "UNKNOWN"
    router_check_chip = status_chip("PASS" if router_check else "UNKNOWN")

    html = (  # noqa: S608 - static HTML template, not SQL
        f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Judge Demo Evidence</title>
  <style>
    :root {{
      --bg: #061321;
      --panel: #10263e;
      --panel2: #163557;
      --text: #eef6ff;
      --muted: #b7cbe4;
      --line: #2b4f78;
      --accent: #ff8f42;
      --pass: #2ecc71;
      --warn: #f4c542;
      --unk: #95a5a6;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: radial-gradient(circle at 20% 0%, #1d3d66 0%, var(--bg) 50%);
      color: var(--text);
      font-family: "Avenir Next", "Segoe UI", sans-serif;
    }}
    .wrap {{ max-width: 1120px; margin: 0 auto; padding: 22px 16px 34px; }}
    .hero {{
      border: 1px solid var(--line);
      background: linear-gradient(135deg, var(--panel), var(--panel2));
      border-radius: 16px;
      padding: 22px;
    }}
    .nav {{
      margin-top: 10px;
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }}
    .nav a {{
      color: #d1e8ff;
      text-decoration: none;
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 5px 10px;
      font-size: 0.76rem;
    }}
    h1 {{ margin: 0 0 6px; font-size: clamp(1.3rem, 2.2vw, 1.8rem); }}
    p {{ margin: 0; color: var(--muted); line-height: 1.45; font-size: 0.92rem; }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(12, 1fr);
      gap: 12px;
      margin-top: 12px;
    }}
    .card {{
      border: 1px solid var(--line);
      background: var(--panel);
      border-radius: 12px;
      padding: 12px;
    }}
    .span4 {{ grid-column: span 4; }}
    .span6 {{ grid-column: span 6; }}
    .span8 {{ grid-column: span 8; }}
    .span12 {{ grid-column: span 12; }}
    .k {{
      color: var(--muted);
      font-size: 0.78rem;
      text-transform: uppercase;
      letter-spacing: 0.3px;
    }}
    .v {{ font-size: 1.12rem; font-weight: 700; margin-top: 3px; }}
    .table {{ width: 100%; border-collapse: collapse; }}
    .table td {{
      border-bottom: 1px solid rgba(255,255,255,0.08);
      padding: 8px 6px;
      vertical-align: top;
      font-size: 0.86rem;
    }}
    .chip {{
      border-radius: 999px;
      padding: 4px 10px;
      font-size: 0.74rem;
      font-weight: 700;
      display: inline-block;
    }}
    .pass {{ background: var(--pass); color: #092414; }}
    .warn {{ background: var(--warn); color: #312500; }}
    .unknown {{ background: var(--unk); color: #102026; }}
    .flow {{
      display: grid;
      grid-template-columns: repeat(5, 1fr);
      gap: 10px;
    }}
    .node {{
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.03);
      border-radius: 10px;
      min-height: 52px;
      display: flex;
      align-items: center;
      justify-content: center;
      text-align: center;
      padding: 8px;
      font-size: 0.8rem;
    }}
    .arr {{ text-align: center; color: var(--accent); font-weight: 800; }}
    .links a {{ color: #9ed0ff; text-decoration: none; }}
    .links li {{ margin: 6px 0; color: var(--muted); }}
    .snap {{
      width: 100%;
      margin-top: 10px;
      border: 1px solid var(--line);
      border-radius: 10px;
      display: block;
    }}
    .pair {{
      margin-top: 10px;
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
    }}
    .mono {{
      font-family: "JetBrains Mono", "SFMono-Regular", Menlo, Consolas, monospace;
      font-size: 0.78rem;
      background: rgba(255,255,255,0.05);
      border: 1px solid rgba(255,255,255,0.08);
      padding: 1px 6px;
      border-radius: 6px;
      overflow-wrap: anywhere;
    }}
    .note {{
      margin-top: 8px;
      font-size: 0.82rem;
      color: var(--muted);
      line-height: 1.35;
    }}
    .stat-help {{
      margin-top: 8px;
      font-size: 0.78rem;
      color: var(--muted);
      line-height: 1.35;
    }}
    .diagram {{
      margin-top: 10px;
      border: 1px solid var(--line);
      border-radius: 10px;
      background: rgba(255,255,255,0.02);
      padding: 10px;
      overflow-x: auto;
    }}
    .legend {{
      margin-top: 8px;
      color: var(--muted);
      font-size: 0.8rem;
      line-height: 1.35;
    }}
    @media (max-width: 920px) {{
      .span4, .span6, .span8 {{ grid-column: span 12; }}
      .flow {{ grid-template-columns: 1fr; }}
      .arr {{ transform: rotate(90deg); }}
      .pair {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <section class="hero">
      <h1>Judge Demo Evidence Hub</h1>
      <p>This page translates complex AI product behavior into clear proof.
      Audience mode: simple enough for non-technical viewers, concrete enough for technical judges.</p>
      <div class="nav">
        <a href="/trading/lessons/">Lessons Index</a>
        <a href="https://github.com/IgorGanapolsky/trading/wiki">Project Wiki</a>
        <a href="https://github.com/IgorGanapolsky/trading/wiki/Development-Engine-and-Evidence">Wiki: Dev Evidence</a>
      </div>
    </section>

    <section class="grid">
      <article class="card span4">
        <div class="k">Checklist Progress</div>
        <div class="v">{done}/{total}</div>
        <div class="stat-help">How many required judge-proof sections passed in <a href="{repo_blob}/artifacts/tars/judge_demo_checklist.md">judge_demo_checklist.md</a>. This is structural completeness, not model quality.</div>
      </article>
      <article class="card span4">
        <div class="k">System Status</div>
        <div class="v">{loop_cycle} / {loop_profile}</div>
        <div class="stat-help">Current autonomous loop cycle + runtime health profile from smoke, lint, and test gates. <span class="mono">healthy</span> means the latest guardrails are green.</div>
      </article>
      <article class="card span4">
        <div class="k">Smoke Latency / Cost</div>
        <div class="v">{latency} ms / ${est_cost_display}</div>
        <div class="stat-help">Single Tetrate-routed smoke call telemetry from <a href="{repo_blob}/artifacts/tars/smoke_metrics.txt">smoke_metrics.txt</a>: end-to-end response time and estimated token spend per run.</div>
      </article>

      <article class="card span6">
        <div class="k">Execution Quality Daily</div>
        <table class="table">
          <tr><td>Gateway Router</td><td>Tetrate TARS</td></tr>
          <tr><td>Gateway Host</td><td><span class="mono">{gateway_host}</span></td></tr>
          <tr><td>Gateway Key Source</td><td><span class="mono">{gateway_key_source}</span></td></tr>
          <tr><td>Routed Model</td><td>{smoke_model}</td></tr>
          <tr><td>Service Tier</td><td>{smoke_service_tier}</td></tr>
          <tr><td>Request ID</td><td><span class="mono">{smoke_request_id}</span></td></tr>
          <tr><td>Runs</td><td>{exec_runs}</td></tr>
          <tr><td>Latest Smoke Probe</td><td>{smoke_probe_text} {smoke_probe_chip}</td></tr>
          <tr><td>Success Rate</td><td>{exec_success}%</td></tr>
          <tr><td>Actionable Rate</td><td>{exec_actionable}%</td></tr>
          <tr><td>P95 Latency</td><td>{exec_p95} ms</td></tr>
          <tr><td>Token Envelope</td><td>{prompt_tokens} prompt / {completion_tokens} completion / {total_tokens} total</td></tr>
          <tr><td>Token Economics</td><td>${est_cost_display} ({cost_per_1k:.6f} / 1K tokens)</td></tr>
          <tr><td>Schema Gate (router_check)</td><td>{router_check_text} {router_check_chip}</td></tr>
          <tr><td>Fallback Probe OK</td><td>{fallback_probe_ok_count}</td></tr>
          <tr><td>Estimated Cost / Smoke Run</td><td>${est_cost_display}</td></tr>
          <tr><td>Cost Basis</td><td><span class="mono">{cost_basis}</span></td></tr>
          <tr><td>Generated</td><td>{generated_at}</td></tr>
        </table>
        <p class="note">Interpretation: this card reports the Tetrate-routed inference path health, not trading profitability. Actionable rate reflects whether responses passed the downstream actionability parser.</p>
      </article>

      <article class="card span6">
        <div class="k">How Tetrate Is Used (Concrete Flow)</div>
        <table class="table" style="margin-top:10px">
          <tr><td>Entry Contract</td><td>Orchestrator sends <span class="mono">POST /v1/chat/completions</span> request through TARS.</td></tr>
          <tr><td>Route Decision</td><td>TARS applies provider/model policy and returns normalized OpenAI-compatible response payload.</td></tr>
          <tr><td>Runtime Proof</td><td>Observed model <span class="mono">{smoke_model}</span>, tier <span class="mono">{smoke_service_tier}</span>, request <span class="mono">{smoke_request_id}</span>.</td></tr>
          <tr><td>Schema Gate</td><td>Response must parse into structured trade intent; malformed payloads are rejected.</td></tr>
          <tr><td>Risk/Policy Gate</td><td>Whitelist, max positions, loss limits, and cadence controls can veto execution.</td></tr>
          <tr><td>Fallback Path</td><td>Fallback probes validate alternate provider path; status is tracked in daily quality artifacts.</td></tr>
          <tr><td>Telemetry</td><td>Latency, token counts, and estimated costs are persisted for ongoing quality/cost monitoring.</td></tr>
          <tr><td>Judge Evidence</td><td>Raw artifact files are published for independent verification of each stage.</td></tr>
        </table>
        <div class="k" style="margin-top:10px">Tetrate Request Flow Diagram</div>
        <div class="diagram">
          <svg viewBox="0 0 920 250" width="100%" role="img" aria-label="Tetrate request and validation flow diagram">
            <defs>
              <marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto" markerUnits="strokeWidth">
                <path d="M0,0 L0,6 L9,3 z" fill="#ff8f42"></path>
              </marker>
            </defs>
            <rect x="20" y="40" width="150" height="58" rx="8" fill="#173656" stroke="#2b4f78"></rect>
            <text x="95" y="65" text-anchor="middle" fill="#eef6ff" font-size="13">Signal + Context</text>
            <text x="95" y="82" text-anchor="middle" fill="#b7cbe4" font-size="11">orchestrator inputs</text>

            <rect x="210" y="40" width="170" height="58" rx="8" fill="#173656" stroke="#2b4f78"></rect>
            <text x="295" y="65" text-anchor="middle" fill="#eef6ff" font-size="13">Tetrate TARS</text>
            <text x="295" y="82" text-anchor="middle" fill="#b7cbe4" font-size="11">policy + provider routing</text>

            <rect x="420" y="40" width="180" height="58" rx="8" fill="#173656" stroke="#2b4f78"></rect>
            <text x="510" y="65" text-anchor="middle" fill="#eef6ff" font-size="13">Primary LLM Call</text>
            <text x="510" y="82" text-anchor="middle" fill="#b7cbe4" font-size="11">{smoke_model}</text>

            <rect x="640" y="40" width="130" height="58" rx="8" fill="#173656" stroke="#2b4f78"></rect>
            <text x="705" y="65" text-anchor="middle" fill="#eef6ff" font-size="13">JSON Gate</text>
            <text x="705" y="82" text-anchor="middle" fill="#b7cbe4" font-size="11">schema check</text>

            <rect x="790" y="40" width="110" height="58" rx="8" fill="#173656" stroke="#2b4f78"></rect>
            <text x="845" y="65" text-anchor="middle" fill="#eef6ff" font-size="13">Actionable</text>
            <text x="845" y="82" text-anchor="middle" fill="#b7cbe4" font-size="11">pass/fail</text>

            <rect x="640" y="155" width="260" height="58" rx="8" fill="#173656" stroke="#2b4f78"></rect>
            <text x="770" y="178" text-anchor="middle" fill="#eef6ff" font-size="13">Artifacts + KPIs</text>
            <text x="770" y="196" text-anchor="middle" fill="#b7cbe4" font-size="11">smoke_metrics, scorecard, readiness gates</text>

            <line x1="170" y1="69" x2="210" y2="69" stroke="#ff8f42" stroke-width="2.2" marker-end="url(#arrow)"></line>
            <line x1="380" y1="69" x2="420" y2="69" stroke="#ff8f42" stroke-width="2.2" marker-end="url(#arrow)"></line>
            <line x1="600" y1="69" x2="640" y2="69" stroke="#ff8f42" stroke-width="2.2" marker-end="url(#arrow)"></line>
            <line x1="770" y1="69" x2="790" y2="69" stroke="#ff8f42" stroke-width="2.2" marker-end="url(#arrow)"></line>
            <line x1="845" y1="98" x2="845" y2="155" stroke="#ff8f42" stroke-width="2.2" marker-end="url(#arrow)"></line>

            <path d="M510 98 C 510 130, 350 130, 350 155" stroke="#95a5a6" stroke-width="2" fill="none" stroke-dasharray="6 5" marker-end="url(#arrow)"></path>
            <text x="355" y="178" fill="#b7cbe4" font-size="11">fallback provider route on health or timeout failure</text>
          </svg>
        </div>
        <div class="legend">
          Flow semantics: solid arrows are primary execution path; dashed arrow is Tetrate fallback route. Output is only considered usable after schema + actionability gates.
        </div>
        <div class="note">
          Verify now:
          <a href="{repo_blob}/artifacts/tars/smoke_metrics.txt">smoke_metrics.txt</a>,
          <a href="{repo_blob}/artifacts/tars/smoke_response.json">smoke_response.json</a>,
          <a href="{repo_blob}/artifacts/tars/resilience_report.txt">resilience_report.txt</a>,
          <a href="/trading/lessons/ops-status.html">ops-status</a>,
          <a href="https://router.tetrate.ai">router.tetrate.ai</a>.
        </div>
      </article>

      <article class="card span6">
        <div class="k">What Is A Judge?</div>
        <p style="margin-top:10px">In this hackathon, a judge is the reviewer scoring whether the product is real, useful, safe, and measurable.
        This page is built to help judges verify outcomes quickly from evidence, not promises.</p>
      </article>

      <article class="card span6">
        <div class="k">How Much Money Made (Paper) + Why</div>
        <table class="table">
          <tr><td>Starting balance</td><td>${starting_balance:,.2f}</td></tr>
          <tr><td>Current equity</td><td>${current_equity:,.2f}</td></tr>
          <tr><td>Net P/L</td><td>${total_pl:,.2f} ({total_pl_pct:.2f}%)</td></tr>
          <tr><td>Why (current drivers)</td><td>Win rate {paper_win_rate:.1f}% over {paper_win_samples} samples, strategy gate status: {north_star_prob.upper()}</td></tr>
        </table>
      </article>

      <article class="card span8">
        <div class="k">Readiness Metrics</div>
        <table class="table">{metric_rows}</table>
      </article>

      <article class="card span4 links">
        <div class="k">Evidence Files</div>
        <ul>
          <li><a href="{repo_blob}/artifacts/tars/submission_summary.md">submission_summary.md</a></li>
          <li><a href="{repo_blob}/artifacts/tars/judge_demo_checklist.md">judge_demo_checklist.md</a></li>
          <li><a href="{repo_blob}/artifacts/tars/smoke_response.json">smoke_response.json</a></li>
          <li><a href="{repo_blob}/artifacts/tars/trade_opinion_smoke.json">trade_opinion_smoke.json</a></li>
          <li><a href="{repo_blob}/artifacts/tars/smoke_metrics.txt">smoke_metrics.txt</a></li>
          <li><a href="{repo_blob}/artifacts/tars/execution_quality_daily.json">execution_quality_daily.json</a></li>
          <li><a href="{repo_blob}/artifacts/tars/env_status.txt">env_status.txt</a></li>
          <li><a href="{repo_blob}/artifacts/tars/resilience_report.txt">resilience_report.txt</a></li>
          <li><a href="{repo_blob}/artifacts/tars/retrieval_report.txt">retrieval_report.txt</a></li>
          <li><a href="{repo_blob}/artifacts/devloop/profit_readiness_scorecard.md">profit_readiness_scorecard.md</a></li>
          <li><a href="{repo_blob}/docs/_reports/hackathon-system-explainer.md">system explainer</a></li>
        </ul>
      </article>
{snapshot_section}
    </section>
  </div>
</body>
</html>
"""
    )

    out.write_text(html, encoding="utf-8")
    print(f"ok: judge demo page generated -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
