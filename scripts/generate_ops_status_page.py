#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
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
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def parse_metrics(path: Path) -> list[tuple[str, str, str, str]]:
    rows: list[tuple[str, str, str, str]] = []
    for line in read_text(path).splitlines():
        m = METRIC_RE.match(line.strip())
        if m:
            rows.append((m.group(1), m.group(2), m.group(3), m.group(4)))
    return rows


def status_chip(status: str) -> str:
    s = status.upper().strip()
    if s == "PASS":
        return '<span class="chip pass">PASS</span>'
    if s == "WARN":
        return '<span class="chip warn">WARN</span>'
    return '<span class="chip unknown">UNKNOWN</span>'


def _normalize_metric_rows(
    metrics: list[tuple[str, str, str, str]],
    latency_ms: str,
    cost_usd: str,
    win_rate: float,
    sample_size: int,
) -> str:
    rows: list[tuple[str, str, str]] = []
    present: set[str] = set()

    for name, value, status, _note in metrics[:20]:
        key = name.lower().strip()
        if key.startswith("gateway latency"):
            value = f"{latency_ms} ms"
        elif key.startswith("gateway cost"):
            value = f"${cost_usd}"
        elif key.startswith("win rate"):
            value = f"{win_rate:.2f}% (sample_size={sample_size})"
        rows.append((name, value, status))
        present.add(key)

    if "gateway latency" not in present:
        rows.append(("Gateway Latency", f"{latency_ms} ms", "PASS"))
    if "gateway cost (smoke call)" not in present:
        rows.append(("Gateway Cost (smoke call)", f"${cost_usd}", "PASS"))
    if "win rate" not in present:
        rows.append(("Win Rate", f"{win_rate:.2f}% (sample_size={sample_size})", "WARN"))

    rendered = "\n".join(
        f"<tr><td>{name}</td><td>{value}</td><td>{status_chip(status)}</td></tr>"
        for name, value, status in rows[:16]
    )
    return rendered or '<tr><td colspan="3">No metrics available yet.</td></tr>'


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate public ops status page.")
    parser.add_argument("--repo-root", default=".", help="Repository root")
    parser.add_argument("--out", default="docs/lessons/ops-status.html", help="Output HTML")
    args = parser.parse_args()

    root = Path(args.repo_root).resolve()
    out = Path(args.out).resolve() if Path(args.out).is_absolute() else (root / args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    scorecard = root / "artifacts/devloop/profit_readiness_scorecard.md"
    tars_smoke = parse_kv(root / "artifacts/tars/smoke_metrics.txt")
    resilience = parse_kv(root / "artifacts/tars/resilience_report.txt")
    loop_status = parse_kv(root / "artifacts/devloop/status.txt")
    runtime = read_text(root / "artifacts/devloop/task_runtime_report.md")
    metrics = parse_metrics(scorecard)
    state = read_json(root / "data/system_state.json")

    paper = state.get("paper_account", {}) if isinstance(state, dict) else {}
    equity = float(paper.get("current_equity", paper.get("equity", 0.0)) or 0.0)
    total_pl = float(paper.get("total_pl", 0.0) or 0.0)
    total_pl_pct = float(paper.get("total_pl_pct", 0.0) or 0.0)
    paper_win_rate = float(paper.get("win_rate", 0.0) or 0.0)
    paper_samples = int(paper.get("win_rate_sample_size", 0) or 0)

    cycle = loop_status.get("cycle", "n/a")
    profile = loop_status.get("profile", "n/a")
    latency = tars_smoke.get("latency_ms", "n/a")
    cost = tars_smoke.get("estimated_total_cost_usd", "n/a").lstrip("$")
    metric_rows = _normalize_metric_rows(metrics, latency, cost, paper_win_rate, paper_samples)
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    has_error = resilience.get("has_error_field", "false").lower() == "true"
    err_type = resilience.get("error_type", "none")
    err_msg = resilience.get("error_message", "none")
    resilience_status = (
        '<span class="chip warn">ERROR</span>'
        if has_error
        else '<span class="chip pass">PASS</span>'
    )
    repo_blob = "https://github.com/IgorGanapolsky/trading/blob/main"

    runtime_block = (
        "<pre class='runtime'>"
        + runtime.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        + "</pre>"
        if runtime.strip()
        else "<p>No runtime report available yet.</p>"
    )

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Ops Diagnostic (Internal)</title>
  <meta name="robots" content="noindex, nofollow">
  <style>
    :root {{
      --bg: #081625;
      --panel: #112a43;
      --panel2: #1a3a5c;
      --line: #315b86;
      --text: #edf6ff;
      --muted: #b9d0e9;
      --accent: #ff9e55;
      --pass: #5cd38f;
      --warn: #f4c542;
      --unk: #8fa3b8;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: radial-gradient(circle at 15% 0%, #244a75 0, var(--bg) 55%); color: var(--text); font-family: "Avenir Next", "Segoe UI", sans-serif; }}
    .wrap {{ max-width: 1180px; margin: 0 auto; padding: 18px 14px 28px; }}
    .hero {{ border: 1px solid var(--line); border-radius: 14px; background: linear-gradient(140deg, var(--panel), var(--panel2)); padding: 16px; }}
    .title {{ margin: 0; font-size: 1.6rem; }}
    .sub {{ margin-top: 6px; color: var(--muted); font-size: 0.9rem; }}
    .nav {{ margin-top: 10px; display: flex; flex-wrap: wrap; gap: 8px; }}
    .nav a {{ color: #d2eaff; text-decoration: none; border: 1px solid var(--line); border-radius: 999px; padding: 6px 10px; font-size: 0.8rem; }}
    .grid {{ display: grid; grid-template-columns: repeat(12,1fr); gap: 10px; margin-top: 10px; }}
    .card {{ border: 1px solid var(--line); border-radius: 12px; background: var(--panel); padding: 10px; }}
    .span3 {{ grid-column: span 3; }} .span4 {{ grid-column: span 4; }} .span6 {{ grid-column: span 6; }} .span8 {{ grid-column: span 8; }} .span12 {{ grid-column: span 12; }}
    .k {{ font-size: 0.75rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.3px; }}
    .v {{ font-size: 1.05rem; font-weight: 700; margin-top: 3px; }}
    .table {{ width: 100%; border-collapse: collapse; }}
    .table td {{ font-size: 0.84rem; border-bottom: 1px solid rgba(255,255,255,0.08); padding: 7px 6px; }}
    .chip {{ border-radius: 999px; padding: 3px 8px; font-size: 0.7rem; font-weight: 700; }}
    .pass {{ background: var(--pass); color: #06331d; }} .warn {{ background: var(--warn); color: #3a2b00; }} .unknown {{ background: var(--unk); color: #102330; }}
    .runtime {{ margin: 0; white-space: pre-wrap; font-size: 0.78rem; color: #d8e9fb; line-height: 1.35; }}
    .flow {{ display: grid; grid-template-columns: repeat(5,1fr); gap: 8px; margin-top: 8px; }}
    .node {{ border: 1px solid var(--line); border-radius: 9px; background: rgba(255,255,255,0.03); min-height: 50px; display: flex; align-items: center; justify-content: center; text-align: center; font-size: 0.76rem; padding: 6px; }}
    .arr {{ color: var(--accent); text-align: center; font-weight: 800; }}
    @media (max-width: 900px) {{ .span3,.span4,.span6,.span8 {{ grid-column: span 12; }} .flow {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body>
  <div class="wrap">
    <section class="hero">
      <h1 class="title">Ops Diagnostic (Internal)</h1>
      <p class="sub">Internal diagnostic page generated from source artifacts. For judge flow, use <a style="color:#d2eaff" href="/trading/lessons/judge-demo.html">judge-demo.html</a>.</p>
      <div class="nav">
        <a href="/trading/lessons/judge-demo.html">Judge Demo</a>
        <a href="/trading/lessons/">Lessons Index</a>
        <a href="https://github.com/IgorGanapolsky/trading/wiki">Project Wiki</a>
        <a href="https://github.com/IgorGanapolsky/trading/wiki/Development-Engine-and-Evidence">Wiki: Dev Evidence</a>
      </div>
    </section>
    <section class="grid">
      <article class="card span3"><div class="k">Loop Cycle / Profile</div><div class="v">{cycle} / {profile}</div></article>
      <article class="card span3"><div class="k">Gateway Latency</div><div class="v">{latency} ms</div></article>
      <article class="card span3"><div class="k">Gateway Cost</div><div class="v">${cost}</div></article>
      <article class="card span3"><div class="k">Paper P/L</div><div class="v">${total_pl:,.2f} ({total_pl_pct:.2f}%)</div></article>
      <article class="card span6"><div class="k">Resilience Check</div><div class="v">{resilience_status}</div><div class="k">type={err_type}</div><div class="k">message={err_msg}</div></article>
      <article class="card span6"><div class="k">Win Rate Context</div><div class="v">{paper_win_rate:.2f}%</div><div class="k">sample_size={paper_samples} (must reach 30 for projection quality)</div><div class="k">Generated: {generated_at}</div></article>

      <article class="card span8">
        <div class="k">Readiness Metrics</div>
        <table class="table">{metric_rows}</table>
      </article>
      <article class="card span4">
        <div class="k">Current Equity</div>
        <div class="v">${equity:,.2f}</div>
        <div class="k" style="margin-top:8px">Evidence Files</div>
        <table class="table">
          <tr><td><a href="{repo_blob}/artifacts/tars/smoke_metrics.txt">smoke_metrics.txt</a></td></tr>
          <tr><td><a href="{repo_blob}/artifacts/tars/smoke_response.json">smoke_response.json</a></td></tr>
          <tr><td><a href="{repo_blob}/artifacts/tars/resilience_report.txt">resilience_report.txt</a></td></tr>
          <tr><td><a href="{repo_blob}/artifacts/devloop/profit_readiness_scorecard.md">profit_readiness_scorecard.md</a></td></tr>
          <tr><td><a href="{repo_blob}/docs/_reports/hackathon-system-explainer.md">system explainer</a></td></tr>
        </table>
      </article>

      <article class="card span6">
        <div class="k">Tetrate Evidence Pipeline</div>
        <div class="flow">
          <div class="node">1. Routed Call</div><div class="arr">-></div><div class="node">2. Smoke Metrics</div><div class="arr">-></div><div class="node">3. Resilience Check</div>
        </div>
        <div class="flow">
          <div class="node">4. RAG Ingest</div><div class="arr">-></div><div class="node">5. Scorecard</div><div class="arr">-></div><div class="node">6. Judge Proof</div>
        </div>
      </article>

      <article class="card span6">
        <div class="k">Active Runtime Report</div>
        {runtime_block}
      </article>
    </section>
  </div>
</body>
</html>
"""

    out.write_text(html, encoding="utf-8")
    print(f"ok: ops status page generated -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
