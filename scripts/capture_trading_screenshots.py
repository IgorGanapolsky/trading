#!/usr/bin/env python3
"""
Automated Screenshot Capture for Trading Dashboards.

This script captures screenshots of:
1. Alpaca Paper Trading Dashboard
2. Alpaca Live Trading Dashboard
3. Progress Dashboard (GitHub Pages)

Screenshots are saved to data/screenshots/ with timestamps for:
- Cowork analysis (Claude Desktop)
- RAG Webhook analysis
- Historical tracking

Usage:
    python3 scripts/capture_trading_screenshots.py
    python3 scripts/capture_trading_screenshots.py --dashboard alpaca
    python3 scripts/capture_trading_screenshots.py --dashboard progress
    python3 scripts/capture_trading_screenshots.py --all

Requirements:
    playwright install chromium  # Run once to install browser
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from playwright.async_api import async_playwright
except ImportError:
    async_playwright = None


def resolve_account_credentials(
    account_type: str,
    env: Mapping[str, str],
) -> tuple[str, str]:
    """Resolve account credentials from supported env var aliases."""
    if account_type == "paper":
        key_candidates = [
            "ALPACA_PAPER_TRADING_API_KEY",
            "ALPACA_PAPER_TRADING_5K_API_KEY",
            "ALPACA_API_KEY",
        ]
        secret_candidates = [
            "ALPACA_PAPER_TRADING_API_SECRET",
            "ALPACA_PAPER_TRADING_5K_API_SECRET",
            "ALPACA_SECRET_KEY",
        ]
    else:
        key_candidates = [
            "ALPACA_BROKERAGE_TRADING_API_KEY",
            "ALPACA_LIVE_TRADING_API_KEY",
            "ALPACA_API_KEY",
        ]
        secret_candidates = [
            "ALPACA_BROKERAGE_TRADING_API_SECRET",
            "ALPACA_LIVE_TRADING_API_SECRET",
            "ALPACA_SECRET_KEY",
        ]

    key = next(
        (str(env.get(k, "")).strip() for k in key_candidates if str(env.get(k, "")).strip()), ""
    )
    secret = next(
        (str(env.get(k, "")).strip() for k in secret_candidates if str(env.get(k, "")).strip()),
        "",
    )
    return key, secret


def _ensure_playwright_installed() -> None:
    if async_playwright is None:
        raise RuntimeError(
            "Playwright not installed. Run: pip install playwright && playwright install chromium"
        )


class TradingScreenshotCapture:
    """Capture screenshots of trading dashboards."""

    MANIFEST_PATH = project_root / "docs" / "data" / "alpaca_snapshots.json"
    PAGES_SNAPSHOT_DIR = project_root / "docs" / "assets" / "snapshots"

    def __init__(self, output_dir: Path = None):
        """Initialize screenshot capture.

        Args:
            output_dir: Directory to save screenshots (default: data/screenshots)
        """
        self.output_dir = output_dir or project_root / "data" / "screenshots"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Create subdirectories
        (self.output_dir / "alpaca").mkdir(exist_ok=True)
        (self.output_dir / "dashboard").mkdir(exist_ok=True)
        (self.output_dir / "daily").mkdir(exist_ok=True)
        self.PAGES_SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
        self.MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)

        # Resolve credentials from all supported environment variable names.
        self.paper_key, self.paper_secret = resolve_account_credentials("paper", os.environ)
        self.live_key, self.live_secret = resolve_account_credentials("live", os.environ)

    @staticmethod
    def _get_base_url(account_type: str) -> str:
        return (
            "https://paper-api.alpaca.markets"
            if account_type == "paper"
            else "https://api.alpaca.markets"
        )

    @staticmethod
    def _manifest_snapshot_url(filename: str) -> str:
        return f"/trading/assets/snapshots/{filename}"

    @staticmethod
    def _read_manifest(path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _publish_snapshot(
        self, key: str, source_path: Path, captured_at_utc: str
    ) -> dict[str, str]:
        timestamp = datetime.strptime(captured_at_utc, "%Y-%m-%dT%H:%M:%SZ").strftime(
            "%Y%m%d_%H%M%S"
        )
        versioned_name = f"{key}_{timestamp}.png"
        latest_name = f"{key}_latest.png"
        versioned_path = self.PAGES_SNAPSHOT_DIR / versioned_name
        latest_path = self.PAGES_SNAPSHOT_DIR / latest_name
        shutil.copy2(source_path, versioned_path)
        shutil.copy2(source_path, latest_path)
        return {
            "file": latest_name,
            "versioned_file": versioned_name,
            "url": self._manifest_snapshot_url(latest_name),
            "versioned_url": self._manifest_snapshot_url(versioned_name),
            "captured_at_utc": captured_at_utc,
        }

    @staticmethod
    def _as_float(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def _build_account_metrics(
        self,
        account: dict[str, Any],
        state: dict[str, Any],
    ) -> dict[str, Any]:
        equity = self._as_float(account.get("current_equity", account.get("equity")))
        starting = self._as_float(account.get("starting_balance"))
        last_equity = self._as_float(account.get("last_equity"))
        daily_change = self._as_float(account.get("daily_change"))
        total_pl = self._as_float(account.get("total_pl", equity - starting if starting else 0.0))
        total_pl_pct = self._as_float(account.get("total_pl_pct", 0.0))
        buying_power = self._as_float(account.get("buying_power"))
        cash = self._as_float(account.get("cash"))
        win_rate = self._as_float(account.get("win_rate"))
        sample_size = int(account.get("win_rate_sample_size", 0) or 0)
        positions_count = int(account.get("positions_count", 0) or 0)
        north_star = state.get("north_star", {}) if isinstance(state, dict) else {}
        gate = str(north_star.get("probability_label", "unknown")).upper()

        bp_usage = 0.0
        if buying_power > 0 and equity > 0:
            bp_usage = max(0.0, min(100.0, (1.0 - (buying_power / max(equity * 2.0, 1.0))) * 100.0))

        daily_bps = 0.0
        if last_equity > 0:
            daily_bps = (daily_change / last_equity) * 10_000.0

        return {
            "equity": equity,
            "starting_balance": starting,
            "last_equity": last_equity,
            "daily_change": daily_change,
            "daily_bps": daily_bps,
            "total_pl": total_pl,
            "total_pl_pct": total_pl_pct,
            "buying_power": buying_power,
            "cash": cash,
            "buying_power_utilization_pct": bp_usage,
            "win_rate": win_rate,
            "win_rate_sample_size": sample_size,
            "positions_count": positions_count,
            "north_star_gate": gate,
        }

    @staticmethod
    def _build_financial_technical_summary(
        account_label: str,
        metrics: dict[str, Any],
    ) -> str:
        daily_change = float(metrics.get("daily_change", 0.0) or 0.0)
        daily_bps = float(metrics.get("daily_bps", 0.0) or 0.0)
        total_pl = float(metrics.get("total_pl", 0.0) or 0.0)
        total_pl_pct = float(metrics.get("total_pl_pct", 0.0) or 0.0)
        equity = float(metrics.get("equity", 0.0) or 0.0)
        bp_usage = float(metrics.get("buying_power_utilization_pct", 0.0) or 0.0)
        cash = float(metrics.get("cash", 0.0) or 0.0)
        gate = str(metrics.get("north_star_gate", "UNKNOWN")).upper()
        positions_count = int(metrics.get("positions_count", 0) or 0)
        win_rate = float(metrics.get("win_rate", 0.0) or 0.0)
        sample_size = int(metrics.get("win_rate_sample_size", 0) or 0)

        day_regime = (
            "flat premium-decay session"
            if abs(daily_change) < 1.0
            else ("positive drift session" if daily_change > 0 else "negative drift session")
        )
        deployment = (
            "low capital deployment"
            if bp_usage < 10.0
            else ("moderate capital deployment" if bp_usage < 35.0 else "high capital deployment")
        )

        return (
            f"{account_label}: net liquidation value ${equity:,.2f}; "
            f"daily P/L {daily_change:+,.2f} ({daily_bps:+.1f} bps) indicating a {day_regime}; "
            f"cumulative P/L {total_pl:+,.2f} ({total_pl_pct:+.2f}%); "
            f"{deployment} at {bp_usage:.1f}% utilization with cash ${cash:,.2f}; "
            f"open position proxy {positions_count}; win-rate estimate {win_rate:.1f}% (n={sample_size}); "
            f"North Star gate {gate}."
        )

    def _build_paperbanana_svg(
        self,
        account_label: str,
        metrics: dict[str, Any],
        captured_at_utc: str,
    ) -> str:
        equity = self._as_float(metrics.get("equity"))
        daily_change = self._as_float(metrics.get("daily_change"))
        daily_bps = self._as_float(metrics.get("daily_bps"))
        total_pl = self._as_float(metrics.get("total_pl"))
        total_pl_pct = self._as_float(metrics.get("total_pl_pct"))
        cash = self._as_float(metrics.get("cash"))
        win_rate = self._as_float(metrics.get("win_rate"))
        sample_size = int(metrics.get("win_rate_sample_size", 0) or 0)
        bp_usage = self._as_float(metrics.get("buying_power_utilization_pct"))
        positions_count = int(metrics.get("positions_count", 0) or 0)
        gate = str(metrics.get("north_star_gate", "unknown")).upper()

        trend_msg = (
            "Range-bound day; premium decay dominated."
            if abs(daily_change) < 1.0
            else (
                "Positive convexity day; favorable realized drift."
                if daily_change > 0
                else "Adverse drift day; downside variance dominated."
            )
        )

        return f"""<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#0B1F34"/>
      <stop offset="100%" stop-color="#1E3D5B"/>
    </linearGradient>
  </defs>
  <rect width="1280" height="720" fill="url(#bg)"/>
  <text x="56" y="76" fill="#F5F9FF" font-size="42" font-family="Avenir Next, Segoe UI, Arial">PaperBanana Diagram • {account_label}</text>
  <text x="56" y="112" fill="#BFD4EA" font-size="20" font-family="Avenir Next, Segoe UI, Arial">Metrics + dataflow decomposition from Alpaca sync</text>

  <rect x="52" y="150" width="1176" height="238" rx="18" fill="#102A42" stroke="#2C567E"/>
  <text x="82" y="198" fill="#F5F9FF" font-size="28" font-family="Avenir Next, Segoe UI, Arial">Net Liquidation Value</text>
  <text x="82" y="242" fill="#8CE5A9" font-size="44" font-family="Avenir Next, Segoe UI, Arial">${equity:,.2f}</text>
  <text x="82" y="284" fill="#BFD4EA" font-size="22" font-family="Avenir Next, Segoe UI, Arial">MTD P/L: {total_pl:+,.2f} ({total_pl_pct:+.2f}%)</text>
  <text x="82" y="322" fill="#BFD4EA" font-size="22" font-family="Avenir Next, Segoe UI, Arial">Daily return: {daily_change:+,.2f} ({daily_bps:+.1f} bps)</text>
  <text x="82" y="360" fill="#BFD4EA" font-size="22" font-family="Avenir Next, Segoe UI, Arial">Buying power utilization: {bp_usage:.1f}% (cash {cash:,.2f})</text>

  <rect x="52" y="418" width="572" height="238" rx="18" fill="#102A42" stroke="#2C567E"/>
  <text x="82" y="466" fill="#F5F9FF" font-size="28" font-family="Avenir Next, Segoe UI, Arial">Execution State</text>
  <text x="82" y="510" fill="#BFD4EA" font-size="22" font-family="Avenir Next, Segoe UI, Arial">Open structures/legs proxy: {positions_count}</text>
  <text x="82" y="548" fill="#BFD4EA" font-size="22" font-family="Avenir Next, Segoe UI, Arial">Win-rate estimate: {win_rate:.1f}% (n={sample_size})</text>
  <text x="82" y="586" fill="#BFD4EA" font-size="22" font-family="Avenir Next, Segoe UI, Arial">North Star gate regime: {gate}</text>

  <rect x="656" y="418" width="572" height="238" rx="18" fill="#102A42" stroke="#2C567E"/>
  <text x="686" y="466" fill="#F5F9FF" font-size="28" font-family="Avenir Next, Segoe UI, Arial">PaperBanana Flow</text>

  <rect x="686" y="488" width="122" height="56" rx="10" fill="#173955" stroke="#3A6A96"/>
  <text x="747" y="523" text-anchor="middle" fill="#DCEBFA" font-size="16" font-family="Avenir Next, Segoe UI, Arial">Alpaca</text>
  <rect x="838" y="488" width="122" height="56" rx="10" fill="#173955" stroke="#3A6A96"/>
  <text x="899" y="523" text-anchor="middle" fill="#DCEBFA" font-size="16" font-family="Avenir Next, Segoe UI, Arial">State Sync</text>
  <rect x="990" y="488" width="122" height="56" rx="10" fill="#173955" stroke="#3A6A96"/>
  <text x="1051" y="523" text-anchor="middle" fill="#DCEBFA" font-size="16" font-family="Avenir Next, Segoe UI, Arial">Risk Gate</text>

  <line x1="808" y1="516" x2="838" y2="516" stroke="#FF9E52" stroke-width="3"/>
  <polygon points="836,510 848,516 836,522" fill="#FF9E52"/>
  <line x1="960" y1="516" x2="990" y2="516" stroke="#FF9E52" stroke-width="3"/>
  <polygon points="988,510 1000,516 988,522" fill="#FF9E52"/>

  <rect x="762" y="566" width="359" height="72" rx="10" fill="#0E2539" stroke="#2C567E"/>
  <text x="780" y="593" fill="#BFD4EA" font-size="20" font-family="Avenir Next, Segoe UI, Arial">{trend_msg}</text>
  <text x="780" y="621" fill="#BFD4EA" font-size="18" font-family="Avenir Next, Segoe UI, Arial">Snapshot: {captured_at_utc}</text>
</svg>
"""

    def _publish_paperbanana_diagram(
        self,
        key: str,
        account_label: str,
        account: dict[str, Any],
        state: dict[str, Any],
        captured_at_utc: str,
    ) -> dict[str, str]:
        timestamp = datetime.strptime(captured_at_utc, "%Y-%m-%dT%H:%M:%SZ").strftime(
            "%Y%m%d_%H%M%S"
        )
        short = "paper" if key == "alpaca_paper" else "live"
        versioned_name = f"paperbanana_{short}_{timestamp}.svg"
        latest_name = f"paperbanana_{short}_latest.svg"
        versioned_path = self.PAGES_SNAPSHOT_DIR / versioned_name
        latest_path = self.PAGES_SNAPSHOT_DIR / latest_name
        metrics = self._build_account_metrics(account=account, state=state)
        technical_explainer = self._build_financial_technical_summary(account_label, metrics)
        svg = self._build_paperbanana_svg(account_label, metrics, captured_at_utc)
        versioned_path.write_text(svg, encoding="utf-8")
        latest_path.write_text(svg, encoding="utf-8")
        return {
            "diagram_file": latest_name,
            "diagram_versioned_file": versioned_name,
            "diagram_url": self._manifest_snapshot_url(latest_name),
            "diagram_versioned_url": self._manifest_snapshot_url(versioned_name),
            "technical_explainer": technical_explainer,
            "metrics": metrics,
        }

    def publish_to_pages(self, screenshots: dict[str, Path | None]) -> Path:
        captured_at_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        manifest = self._read_manifest(self.MANIFEST_PATH)
        latest: dict[str, Any] = (
            manifest.get("latest", {}) if isinstance(manifest.get("latest"), dict) else {}
        )
        history: list[dict[str, Any]] = (
            manifest.get("history", []) if isinstance(manifest.get("history"), list) else []
        )

        published_entries: dict[str, dict[str, str]] = {}
        for key, path in screenshots.items():
            if path is None:
                continue
            published_entries[key] = self._publish_snapshot(key, path, captured_at_utc)

        if not published_entries:
            return self.MANIFEST_PATH

        latest.update(published_entries)

        state_path = project_root / "data" / "system_state.json"
        state = {}
        if state_path.exists():
            try:
                state = json.loads(state_path.read_text(encoding="utf-8"))
            except Exception:
                state = {}
        paper = state.get("paper_account", {}) if isinstance(state, dict) else {}
        live = state.get("live_account", {}) if isinstance(state, dict) else {}

        if "alpaca_paper" in published_entries:
            published_entries["alpaca_paper"].update(
                self._publish_paperbanana_diagram(
                    key="alpaca_paper",
                    account_label="Paper Account",
                    account=paper if isinstance(paper, dict) else {},
                    state=state if isinstance(state, dict) else {},
                    captured_at_utc=captured_at_utc,
                )
            )
        if "alpaca_live" in published_entries:
            published_entries["alpaca_live"].update(
                self._publish_paperbanana_diagram(
                    key="alpaca_live",
                    account_label="Brokerage Account",
                    account=live if isinstance(live, dict) else {},
                    state=state if isinstance(state, dict) else {},
                    captured_at_utc=captured_at_utc,
                )
            )
        state_summary = {
            "paper_trade_count": int(state.get("trades_loaded", 0) or 0),
            "paper_equity": float(paper.get("current_equity", paper.get("equity", 0.0)) or 0.0),
            "live_equity": float(live.get("current_equity", live.get("equity", 0.0)) or 0.0),
            "date_utc": captured_at_utc[:10],
        }

        history.append(
            {
                "captured_at_utc": captured_at_utc,
                "entries": published_entries,
                "state": state_summary,
            }
        )
        history = history[-30:]

        new_manifest = {
            "updated_at_utc": captured_at_utc,
            "latest": latest,
            "history": history,
            "state": state_summary,
        }
        self.MANIFEST_PATH.write_text(json.dumps(new_manifest, indent=2), encoding="utf-8")
        print(f"✅ Published snapshots manifest: {self.MANIFEST_PATH}")
        return self.MANIFEST_PATH

    async def capture_alpaca_dashboard(self, account_type: str = "paper") -> Path | None:
        """
        Capture Alpaca dashboard screenshot.

        Args:
            account_type: "paper" or "live"

        Returns:
            Path to saved screenshot or None if failed
        """
        key = self.paper_key if account_type == "paper" else self.live_key
        secret = self.paper_secret if account_type == "paper" else self.live_secret
        if not key or not secret:
            print(f"⚠️  Alpaca credentials not found - skipping {account_type} dashboard")
            return None

        print(f"📸 Capturing Alpaca {account_type} dashboard...")

        try:
            # OAuth UI automation is brittle; generate visual snapshot from authenticated API data.
            return await self._capture_api_dashboard(
                account_type=account_type,
                api_key=key,
                api_secret=secret,
                base_url=self._get_base_url(account_type),
            )

        except Exception as e:
            print(f"❌ Failed to capture Alpaca {account_type} dashboard: {e}")
            return None

    async def _capture_api_dashboard(
        self,
        account_type: str,
        api_key: str,
        api_secret: str,
        base_url: str,
    ) -> Path | None:
        """Generate and capture API-based dashboard visualization."""
        import ssl
        import urllib.request

        _ensure_playwright_installed()

        try:
            # Query Alpaca API
            account_url = f"{base_url}/v2/account"
            positions_url = f"{base_url}/v2/positions"

            headers = {
                "accept": "application/json",
                "APCA-API-KEY-ID": api_key,
                "APCA-API-SECRET-KEY": api_secret,
            }

            # Get account data
            req = urllib.request.Request(account_url, headers=headers)
            ssl_context = ssl.create_default_context()
            with urllib.request.urlopen(req, timeout=10, context=ssl_context) as response:
                account = json.loads(response.read().decode("utf-8"))

            # Get positions
            req = urllib.request.Request(positions_url, headers=headers)
            with urllib.request.urlopen(req, timeout=10, context=ssl_context) as response:
                positions = json.loads(response.read().decode("utf-8"))

            # Generate HTML dashboard
            html = self._generate_dashboard_html(account, positions, account_type)

            # Save HTML temporarily
            temp_html = self.output_dir / "temp_dashboard.html"
            with open(temp_html, "w") as f:
                f.write(html)

            # Screenshot the HTML
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page(viewport={"width": 1920, "height": 1080})
                await page.goto(f"file://{temp_html.absolute()}")

                # Save screenshot
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                screenshot_path = (
                    self.output_dir / "alpaca" / f"{account_type}_dashboard_{timestamp}.png"
                )
                await page.screenshot(path=str(screenshot_path), full_page=True)

                await browser.close()

            # Cleanup temp file
            temp_html.unlink()

            print(f"✅ Saved {account_type} dashboard: {screenshot_path}")
            return screenshot_path

        except Exception as e:
            print(f"❌ API dashboard capture failed: {e}")
            return None

    def _generate_dashboard_html(self, account: dict, positions: list, account_type: str) -> str:
        """Generate HTML dashboard from Alpaca API data."""
        equity = float(account.get("equity", 0))
        cash = float(account.get("cash", 0))
        buying_power = float(account.get("buying_power", 0))
        last_equity = float(account.get("last_equity", 0))
        daily_change = equity - last_equity
        daily_pct = (daily_change / last_equity * 100) if last_equity > 0 else 0

        # Calculate total P/L from initial capital
        if account_type == "paper":
            initial_capital = 100000
        else:
            initial_capital = last_equity if last_equity > 0 else 200
        total_pl = equity - initial_capital
        total_pl_pct = total_pl / initial_capital * 100

        positions_html = ""
        for pos in positions:
            symbol = pos.get("symbol", "")
            qty = pos.get("qty", 0)
            current_price = float(pos.get("current_price", 0))
            unrealized_pl = float(pos.get("unrealized_pl", 0))
            unrealized_plpc = float(pos.get("unrealized_plpc", 0)) * 100

            pl_color = "green" if unrealized_pl >= 0 else "red"
            positions_html += f"""
            <tr>
                <td>{symbol}</td>
                <td>{qty}</td>
                <td>${current_price:.2f}</td>
                <td style="color: {pl_color};">${unrealized_pl:.2f} ({unrealized_plpc:.2f}%)</td>
            </tr>
            """

        change_color = "green" if daily_change >= 0 else "red"
        pl_color = "green" if total_pl >= 0 else "red"

        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Alpaca {account_type.title()} Dashboard</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            margin: 0;
            padding: 40px;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 20px;
            padding: 40px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        }}
        h1 {{
            margin: 0 0 10px 0;
            color: #1a202c;
            font-size: 36px;
        }}
        .subtitle {{
            color: #718096;
            font-size: 18px;
            margin-bottom: 30px;
        }}
        .metrics {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }}
        .metric {{
            background: #f7fafc;
            padding: 25px;
            border-radius: 12px;
            border-left: 4px solid #667eea;
        }}
        .metric-label {{
            font-size: 14px;
            color: #718096;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 8px;
        }}
        .metric-value {{
            font-size: 28px;
            font-weight: bold;
            color: #1a202c;
        }}
        .metric-change {{
            font-size: 16px;
            margin-top: 5px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }}
        th {{
            background: #f7fafc;
            padding: 15px;
            text-align: left;
            font-weight: 600;
            color: #1a202c;
            border-bottom: 2px solid #e2e8f0;
        }}
        td {{
            padding: 15px;
            border-bottom: 1px solid #e2e8f0;
        }}
        .timestamp {{
            text-align: center;
            color: #a0aec0;
            font-size: 14px;
            margin-top: 30px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 Alpaca {account_type.title()} Trading Account</h1>
        <div class="subtitle">Real-time snapshot from Alpaca API</div>

        <div class="metrics">
            <div class="metric">
                <div class="metric-label">Portfolio Value</div>
                <div class="metric-value">${equity:,.2f}</div>
                <div class="metric-change" style="color: {change_color};">
                    {"+" if daily_change >= 0 else ""}{daily_change:.2f} ({daily_pct:+.2f}%) today
                </div>
            </div>

            <div class="metric">
                <div class="metric-label">Total P/L</div>
                <div class="metric-value" style="color: {pl_color};">${total_pl:,.2f}</div>
                <div class="metric-change" style="color: {pl_color};">
                    {total_pl_pct:+.2f}% from ${initial_capital:,.0f}
                </div>
            </div>

            <div class="metric">
                <div class="metric-label">Cash Available</div>
                <div class="metric-value">${cash:,.2f}</div>
            </div>

            <div class="metric">
                <div class="metric-label">Buying Power</div>
                <div class="metric-value">${buying_power:,.2f}</div>
            </div>
        </div>

        <h2>Open Positions ({len(positions)})</h2>
        <table>
            <thead>
                <tr>
                    <th>Symbol</th>
                    <th>Quantity</th>
                    <th>Current Price</th>
                    <th>Unrealized P/L</th>
                </tr>
            </thead>
            <tbody>
                {positions_html if positions else '<tr><td colspan="4" style="text-align: center; color: #a0aec0;">No open positions</td></tr>'}
            </tbody>
        </table>

        <div class="timestamp">
            Generated: {datetime.now().strftime("%Y-%m-%d %I:%M:%S %p ET")}
        </div>
    </div>
</body>
</html>
        """

    async def capture_progress_dashboard(self) -> Path | None:
        """Capture Progress Dashboard screenshot from GitHub Pages."""
        print("📸 Capturing Progress Dashboard...")
        _ensure_playwright_installed()

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page(viewport={"width": 1920, "height": 1080})

                # Navigate to GitHub Pages dashboard
                url = "https://igorganapolsky.github.io/trading/"
                await page.goto(url, wait_until="networkidle", timeout=30000)

                # Wait for dashboard to load
                await page.wait_for_timeout(2000)

                # Save screenshot
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                screenshot_path = (
                    self.output_dir / "dashboard" / f"progress_dashboard_{timestamp}.png"
                )
                await page.screenshot(path=str(screenshot_path), full_page=True)

                await browser.close()

                print(f"✅ Saved progress dashboard: {screenshot_path}")
                return screenshot_path

        except Exception as e:
            print(f"❌ Failed to capture progress dashboard: {e}")
            return None

    async def capture_all_dashboards(self) -> dict[str, Path | None]:
        """Capture all trading dashboards."""
        results = {}

        # Capture Alpaca dashboards
        results["alpaca_paper"] = await self.capture_alpaca_dashboard("paper")
        results["alpaca_live"] = await self.capture_alpaca_dashboard("live")

        # Capture progress dashboard
        results["progress"] = await self.capture_progress_dashboard()

        return results

    async def create_daily_summary(self, screenshots: dict[str, Path | None]) -> Path | None:
        """Create a daily summary screenshot combining all dashboards."""
        print("📸 Creating daily summary...")
        _ensure_playwright_installed()

        # Filter out None values
        valid_screenshots = {k: v for k, v in screenshots.items() if v is not None}

        if not valid_screenshots:
            print("⚠️  No screenshots to combine")
            return None

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page(viewport={"width": 1920, "height": 1080})

                # Generate summary HTML
                html = self._generate_summary_html(valid_screenshots)
                temp_html = self.output_dir / "temp_summary.html"
                with open(temp_html, "w") as f:
                    f.write(html)

                await page.goto(f"file://{temp_html.absolute()}")
                await page.wait_for_timeout(1000)

                # Save screenshot
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                screenshot_path = self.output_dir / "daily" / f"daily_summary_{timestamp}.png"
                await page.screenshot(path=str(screenshot_path), full_page=True)

                await browser.close()
                temp_html.unlink()

                print(f"✅ Saved daily summary: {screenshot_path}")
                return screenshot_path

        except Exception as e:
            print(f"❌ Failed to create daily summary: {e}")
            return None

    def _generate_summary_html(self, screenshots: dict[str, Path]) -> str:
        """Generate HTML for daily summary."""
        images_html = ""
        for name, path in screenshots.items():
            title = name.replace("_", " ").title()
            images_html += f"""
            <div class="screenshot">
                <h2>{title}</h2>
                <img src="{path.absolute()}" alt="{title}">
            </div>
            """

        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Daily Trading Summary</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: #f7fafc;
            margin: 0;
            padding: 40px;
        }}
        h1 {{
            text-align: center;
            color: #1a202c;
        }}
        .timestamp {{
            text-align: center;
            color: #718096;
            margin-bottom: 40px;
        }}
        .screenshot {{
            background: white;
            padding: 20px;
            margin-bottom: 30px;
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }}
        .screenshot h2 {{
            margin-top: 0;
            color: #2d3748;
        }}
        .screenshot img {{
            width: 100%;
            border-radius: 8px;
        }}
    </style>
</head>
<body>
    <h1>📊 Daily Trading Dashboard Summary</h1>
    <div class="timestamp">{datetime.now().strftime("%Y-%m-%d %I:%M:%S %p ET")}</div>
    {images_html}
</body>
</html>
        """


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Capture trading dashboard screenshots")
    parser.add_argument(
        "--dashboard",
        choices=["alpaca", "progress", "all"],
        default="all",
        help="Which dashboard to capture (default: all)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Output directory for screenshots (default: data/screenshots)",
    )
    parser.add_argument(
        "--publish-pages",
        action="store_true",
        help="Publish latest snapshots + manifest into docs/assets and docs/data",
    )
    args = parser.parse_args()

    capturer = TradingScreenshotCapture(output_dir=args.output_dir)

    print("🚀 Starting screenshot capture...")
    print(f"📁 Output directory: {capturer.output_dir}")

    screenshots = {}

    if args.dashboard == "alpaca" or args.dashboard == "all":
        screenshots["alpaca_paper"] = await capturer.capture_alpaca_dashboard("paper")
        screenshots["alpaca_live"] = await capturer.capture_alpaca_dashboard("live")

    if args.dashboard == "progress" or args.dashboard == "all":
        screenshots["progress"] = await capturer.capture_progress_dashboard()

    # Create daily summary if capturing all
    if args.dashboard == "all":
        screenshots["daily_summary"] = await capturer.create_daily_summary(screenshots)

    if args.publish_pages:
        capturer.publish_to_pages(screenshots)

    # Print summary
    print("\n" + "=" * 60)
    print("📸 Screenshot Capture Summary")
    print("=" * 60)
    for name, path in screenshots.items():
        if path:
            print(f"✅ {name}: {path}")
        else:
            print(f"❌ {name}: Failed")
    print("=" * 60)

    # Cowork integration instructions
    print("\n💡 To use with Anthropic Cowork:")
    print("1. Install Claude Desktop with Claude Max subscription")
    print(f"2. Point Cowork to: {capturer.output_dir.absolute()}")
    print("3. Ask Claude: 'Analyze my latest trading screenshots'")
    print("\n💡 To query via RAG Webhook:")
    print("1. Screenshots are saved with timestamps")
    print("2. Ask: 'What's in my latest dashboard screenshot?'")
    print("3. Or: 'Compare today's vs yesterday's portfolio'")


if __name__ == "__main__":
    asyncio.run(main())
