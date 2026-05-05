#!/usr/bin/env python3
"""Generate Alpaca Portfolio Snapshots.

Fetches portfolio data from both paper and brokerage Alpaca accounts
and generates PNG chart images for embedding in judge-demo.html.

Usage:
    python scripts/generate_alpaca_snapshot.py

Output:
    docs/assets/snapshots/paper_YYYYMMDD.png
    docs/assets/snapshots/brokerage_YYYYMMDD.png
    docs/assets/snapshots/latest.json
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

# Output directory
SNAPSHOTS_DIR = Path("docs/assets/snapshots")

# Account starting values
PAPER_STARTING = 100_000.0
BROKERAGE_STARTING = 5_000.0

# Chart theme (matches judge-demo.html)
CHART_BG = "#061321"
CHART_PANEL = "#10263e"
CHART_TEXT = "#eef6ff"
CHART_MUTED = "#b7cbe4"
CHART_ACCENT = "#ff8f42"
CHART_PASS = "#2ecc71"
CHART_LINE = "#2b4f78"


def fetch_paper_account() -> dict | None:
    """Fetch paper trading account data via Alpaca API."""
    try:
        from alpaca.trading.client import TradingClient
        from src.utils.alpaca_client import get_alpaca_credentials

        api_key, secret_key = get_alpaca_credentials()
        if not api_key or not secret_key:
            logger.warning("Paper trading credentials not found")
            return None

        client = TradingClient(api_key, secret_key, paper=True)
        account = client.get_account()
        positions = client.get_all_positions()

        return {
            "account_type": "paper",
            "equity": float(account.equity),
            "cash": float(account.cash),
            "buying_power": float(account.buying_power),
            "starting_capital": PAPER_STARTING,
            "position_count": len(positions),
            "positions": [
                {
                    "symbol": p.symbol,
                    "qty": float(p.qty),
                    "market_value": float(p.market_value),
                    "unrealized_pl": float(p.unrealized_pl),
                }
                for p in positions
            ],
        }
    except Exception as e:
        logger.error(f"Failed to fetch paper account: {e}")
        return None


def fetch_brokerage_account() -> dict | None:
    """Fetch brokerage (live) account data via Alpaca API."""
    try:
        from alpaca.trading.client import TradingClient
        from src.utils.alpaca_client import get_brokerage_credentials

        api_key, secret_key = get_brokerage_credentials()
        if not api_key or not secret_key:
            logger.warning("Brokerage credentials not found")
            return None

        client = TradingClient(api_key, secret_key, paper=False)
        account = client.get_account()

        return {
            "account_type": "brokerage",
            "equity": float(account.equity),
            "cash": float(account.cash),
            "buying_power": float(account.buying_power),
            "starting_capital": BROKERAGE_STARTING,
            "position_count": 0,
            "positions": [],
        }
    except Exception as e:
        logger.error(f"Failed to fetch brokerage account: {e}")
        return None


def generate_chart(account_data: dict, output_path: Path) -> bool:
    """Generate a portfolio snapshot chart as PNG.

    Args:
        account_data: Account data dict from fetch functions.
        output_path: Path to save the PNG file.

    Returns:
        True if chart was generated successfully.
    """
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.patches import FancyBboxPatch
    except ImportError:
        logger.error("matplotlib not installed")
        return False

    equity = account_data["equity"]
    starting = account_data["starting_capital"]
    change = equity - starting
    change_pct = (change / starting) * 100 if starting > 0 else 0
    acct_type = account_data["account_type"].upper()
    pos_count = account_data["position_count"]

    fig, ax = plt.subplots(figsize=(6, 3.2))
    fig.patch.set_facecolor(CHART_BG)
    ax.set_facecolor(CHART_BG)
    ax.axis("off")

    # Title
    title_label = "📝 PAPER" if acct_type == "PAPER" else "🔴 BROKERAGE"
    ax.text(
        0.5,
        0.92,
        title_label,
        transform=ax.transAxes,
        fontsize=16,
        fontweight="bold",
        color=CHART_TEXT,
        ha="center",
        va="top",
    )

    # Equity value
    ax.text(
        0.5,
        0.68,
        f"${equity:,.2f}",
        transform=ax.transAxes,
        fontsize=28,
        fontweight="bold",
        color=CHART_ACCENT,
        ha="center",
        va="top",
    )

    # Change
    change_color = CHART_PASS if change >= 0 else "#ff6b6b"
    change_sign = "+" if change >= 0 else ""
    ax.text(
        0.5,
        0.44,
        f"{change_sign}${change:,.2f} ({change_sign}{change_pct:.2f}%)",
        transform=ax.transAxes,
        fontsize=14,
        fontweight="bold",
        color=change_color,
        ha="center",
        va="top",
    )

    # Stats line
    stats_text = f"Positions: {pos_count} | Starting: ${starting:,.0f}"
    ax.text(
        0.5,
        0.22,
        stats_text,
        transform=ax.transAxes,
        fontsize=10,
        color=CHART_MUTED,
        ha="center",
        va="top",
    )

    # Timestamp
    et = ZoneInfo("America/New_York")
    now = datetime.now(et)
    ax.text(
        0.5,
        0.06,
        now.strftime("Updated %Y-%m-%d %H:%M ET"),
        transform=ax.transAxes,
        fontsize=8,
        color=CHART_LINE,
        ha="center",
        va="top",
    )

    # Border
    border = FancyBboxPatch(
        (0.02, 0.02),
        0.96,
        0.96,
        transform=ax.transAxes,
        boxstyle="round,pad=0.02",
        linewidth=1.5,
        edgecolor=CHART_LINE,
        facecolor="none",
    )
    ax.add_patch(border)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150, bbox_inches="tight", facecolor=CHART_BG)
    plt.close(fig)
    logger.info(f"Chart saved: {output_path}")
    return True


def write_manifest(manifest: dict, output_path: Path) -> None:
    """Write the snapshot manifest with stable JSON formatting."""
    output_path.write_text(json.dumps(manifest, indent=2, default=str) + "\n", encoding="utf-8")


def main():
    """Main entry point."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    et = ZoneInfo("America/New_York")
    now = datetime.now(et)
    date_str = now.strftime("%Y%m%d")

    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)

    manifest = {
        "generated_at": now.isoformat(),
        "accounts": [],
    }

    # Paper account
    paper = fetch_paper_account()
    if paper:
        paper_path = SNAPSHOTS_DIR / f"paper_{date_str}.png"
        if generate_chart(paper, paper_path):
            paper["chart"] = str(paper_path)
            manifest["accounts"].append(paper)
            # Also save as latest
            latest_paper = SNAPSHOTS_DIR / "paper_latest.png"
            import shutil

            shutil.copy2(paper_path, latest_paper)
            logger.info(f"Paper snapshot: ${paper['equity']:,.2f}")

    # Brokerage account
    brokerage = fetch_brokerage_account()
    if brokerage:
        brokerage_path = SNAPSHOTS_DIR / f"brokerage_{date_str}.png"
        if generate_chart(brokerage, brokerage_path):
            brokerage["chart"] = str(brokerage_path)
            manifest["accounts"].append(brokerage)
            latest_brokerage = SNAPSHOTS_DIR / "brokerage_latest.png"
            import shutil

            shutil.copy2(brokerage_path, latest_brokerage)
            logger.info(f"Brokerage snapshot: ${brokerage['equity']:,.2f}")

    # Write manifest
    manifest_path = SNAPSHOTS_DIR / "latest.json"
    write_manifest(manifest, manifest_path)
    logger.info(f"Manifest written: {manifest_path}")

    # Summary
    print(f"\n{'=' * 50}")
    print("ALPACA PORTFOLIO SNAPSHOT")
    print(f"{'=' * 50}")
    for acct in manifest["accounts"]:
        change = acct["equity"] - acct["starting_capital"]
        print(f"  {acct['account_type'].upper()}: ${acct['equity']:,.2f} ({change:+,.2f})")
    print(f"Generated: {now.strftime('%Y-%m-%d %H:%M ET')}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
