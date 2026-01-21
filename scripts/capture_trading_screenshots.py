#!/usr/bin/env python3
"""
Automated Screenshot Capture for Trading Dashboards.

This script captures screenshots of:
1. Alpaca Paper Trading Dashboard
2. Alpaca Live Trading Dashboard
3. Progress Dashboard (GitHub Pages)

Screenshots are saved to data/screenshots/ with timestamps for:
- Cowork analysis (Claude Desktop)
- DialogFlow webhook analysis
- Historical tracking

Usage:
    python3 scripts/capture_trading_screenshots.py
    python3 scripts/capture_trading_screenshots.py --dashboard alpaca
    python3 scripts/capture_trading_screenshots.py --dashboard progress
    python3 scripts/capture_trading_screenshots.py --all

Requirements:
    playwright install chromium  # Run once to install browser
"""

import argparse
import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("❌ Playwright not installed. Run: pip install playwright && playwright install chromium")
    sys.exit(1)


class TradingScreenshotCapture:
    """Capture screenshots of trading dashboards."""

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

        # Get credentials from environment
        self.alpaca_key = os.environ.get("ALPACA_PAPER_TRADING_5K_API_KEY", "")
        self.alpaca_secret = os.environ.get("ALPACA_PAPER_TRADING_5K_API_SECRET", "")

    async def capture_alpaca_dashboard(self, account_type: str = "paper") -> Path | None:
        """
        Capture Alpaca dashboard screenshot.

        Args:
            account_type: "paper" or "live"

        Returns:
            Path to saved screenshot or None if failed
        """
        if not self.alpaca_key or not self.alpaca_secret:
            print(f"⚠️  Alpaca credentials not found - skipping {account_type} dashboard")
            return None

        print(f"📸 Capturing Alpaca {account_type} dashboard...")

        try:
            async with async_playwright() as p:
                # Launch browser in headless mode
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    viewport={"width": 1920, "height": 1080},
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                )
                page = await context.new_page()

                # Navigate to Alpaca login
                url = "https://app.alpaca.markets/login"
                await page.goto(url, wait_until="networkidle", timeout=30000)

                # NOTE: Alpaca uses OAuth login - manual login required first time
                # For automation, you would need to:
                # 1. Use Alpaca API to generate dashboard links
                # 2. OR pre-authenticate and save session cookies
                # 3. OR use API-based portfolio visualization

                # For now, capture the portfolio summary from API instead
                print("⚠️  Direct dashboard login requires OAuth - using API-based capture instead")

                # Alternative: Capture public progress dashboard or use Alpaca API visualization
                await browser.close()

                # Use API to generate a simple HTML dashboard and screenshot that
                return await self._capture_api_dashboard(account_type)

        except Exception as e:
            print(f"❌ Failed to capture Alpaca {account_type} dashboard: {e}")
            return None

    async def _capture_api_dashboard(self, account_type: str) -> Path | None:
        """Generate and capture API-based dashboard visualization."""
        import json
        import ssl
        import urllib.request

        try:
            # Query Alpaca API
            account_url = "https://paper-api.alpaca.markets/v2/account"
            positions_url = "https://paper-api.alpaca.markets/v2/positions"

            headers = {
                "accept": "application/json",
                "APCA-API-KEY-ID": self.alpaca_key,
                "APCA-API-SECRET-KEY": self.alpaca_secret,
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
        initial_capital = 5000 if account_type == "paper" else 100
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

        # Capture progress dashboard
        results["progress"] = await self.capture_progress_dashboard()

        return results

    async def create_daily_summary(self, screenshots: dict[str, Path | None]) -> Path | None:
        """Create a daily summary screenshot combining all dashboards."""
        print("📸 Creating daily summary...")

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
    args = parser.parse_args()

    capturer = TradingScreenshotCapture(output_dir=args.output_dir)

    print("🚀 Starting screenshot capture...")
    print(f"📁 Output directory: {capturer.output_dir}")

    screenshots = {}

    if args.dashboard == "alpaca" or args.dashboard == "all":
        screenshots["alpaca_paper"] = await capturer.capture_alpaca_dashboard("paper")

    if args.dashboard == "progress" or args.dashboard == "all":
        screenshots["progress"] = await capturer.capture_progress_dashboard()

    # Create daily summary if capturing all
    if args.dashboard == "all":
        await capturer.create_daily_summary(screenshots)

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
    print("\n💡 To query via DialogFlow:")
    print("1. Screenshots are saved with timestamps")
    print("2. Ask: 'What's in my latest dashboard screenshot?'")
    print("3. Or: 'Compare today's vs yesterday's portfolio'")


if __name__ == "__main__":
    asyncio.run(main())
