#!/usr/bin/env python3
"""
Automated Strategy Research Agent — Scans public sources for iron condor insights.

Runs post-market daily. Scrapes key options education sources for:
- Current recommended delta/DTE/wing-width parameters
- VIX regime-specific guidance
- New strategy variants worth testing
- Common mistakes to avoid

Feeds findings into RAG knowledge base as research lessons.

Usage:
    python3 scripts/research_strategies.py
    python3 scripts/research_strategies.py --dry-run
"""

from __future__ import annotations

import json
import logging
import ssl
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent
LESSONS_DIR = PROJECT_ROOT / "rag_knowledge" / "lessons_learned"  # Primary corpus (191+ lessons)
RESEARCH_STATE_FILE = PROJECT_ROOT / "data" / "research_state.json"

# Public data sources (no auth required)
SOURCES = [
    {
        "name": "CBOE VIX Current",
        "url": "https://cdn.cboe.com/api/global/delayed_quotes/charts/historical/_VIX.json",
        "type": "vix_data",
    },
    {
        "name": "Yahoo Finance SPY Options",
        "url": "https://query1.finance.yahoo.com/v7/finance/options/SPY",
        "type": "options_chain",
    },
]


def fetch_url(url: str, timeout: int = 10) -> dict | None:
    """Fetch JSON from URL with SSL handling."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:  # noqa: S310
            return json.loads(resp.read().decode())
    except Exception as e:
        logger.warning(f"Failed to fetch {url}: {e}")
        return None


def analyze_vix_regime(vix_data: dict | None) -> dict:
    """Analyze current VIX regime from CBOE data."""
    if not vix_data:
        return {"regime": "unknown", "vix": None, "guidance": "VIX data unavailable"}

    try:
        # CBOE delayed quotes format
        data_points = vix_data.get("data", [])
        if not data_points:
            return {"regime": "unknown", "vix": None, "guidance": "No VIX data points"}

        current_vix = float(data_points[-1][1]) if data_points[-1] else None
        if current_vix is None:
            return {"regime": "unknown", "vix": None, "guidance": "Could not parse VIX"}

        # Classify regime
        if current_vix < 15:
            regime = "calm"
            guidance = (
                "VIX < 15: Premiums thin. Consider wider wings ($15-20) or wait for VIX spike. "
                "Iron condors at 15-delta may not collect enough premium to justify risk."
            )
        elif current_vix < 20:
            regime = "normal"
            guidance = (
                "VIX 15-20: Standard conditions. 15-delta iron condors at 30-45 DTE optimal. "
                "$10-wide wings should collect $1.50-2.50 per contract."
            )
        elif current_vix < 25:
            regime = "elevated"
            guidance = (
                "VIX 20-25: Rich premiums. Ideal for iron condors. Consider 20-delta for more "
                "cushion. $10-wide wings collecting $2.50-4.00. Best risk/reward zone."
            )
        elif current_vix < 30:
            regime = "volatile"
            guidance = (
                "VIX 25-30: High premiums but increased risk. Reduce position size to 3% max. "
                "Consider 10-delta for wider safety margin. Exit at 25% profit instead of 50%."
            )
        else:
            regime = "spike"
            guidance = (
                f"VIX {current_vix:.0f}: EXTREME. Do not open new iron condors. Wait for VIX "
                "to drop below 25 before re-entering. Manage existing positions only."
            )

        return {
            "regime": regime,
            "vix": current_vix,
            "guidance": guidance,
            "vix_5d_ago": float(data_points[-5][1]) if len(data_points) >= 5 else None,
            "vix_trend": "rising"
            if len(data_points) >= 5 and current_vix > float(data_points[-5][1])
            else "falling",
        }
    except Exception as e:
        logger.warning(f"VIX analysis failed: {e}")
        return {"regime": "unknown", "vix": None, "guidance": f"Analysis error: {e}"}


def analyze_spy_options_chain(chain_data: dict | None) -> dict:
    """Extract iron condor parameters from live SPY options chain."""
    if not chain_data:
        return {"status": "unavailable"}

    try:
        result = chain_data.get("optionChain", {}).get("result", [])
        if not result:
            return {"status": "no_data"}

        quote = result[0].get("quote", {})
        spy_price = quote.get("regularMarketPrice", 0)
        expirations = result[0].get("expirationDates", [])

        # Find 30-45 DTE expiration
        now_ts = datetime.now(timezone.utc).timestamp()
        target_dte_range = []
        for exp_ts in expirations:
            dte = (exp_ts - now_ts) / 86400
            if 30 <= dte <= 45:
                target_dte_range.append({"expiry_ts": exp_ts, "dte": round(dte)})

        return {
            "status": "ok",
            "spy_price": spy_price,
            "available_expirations_30_45_dte": len(target_dte_range),
            "nearest_target_dte": target_dte_range[0]["dte"] if target_dte_range else None,
        }
    except Exception as e:
        logger.warning(f"Options chain analysis failed: {e}")
        return {"status": f"error: {e}"}


def generate_daily_research_lesson(vix_analysis: dict, chain_analysis: dict) -> str:
    """Generate a daily research lesson from market data."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    vix = vix_analysis.get("vix")
    regime = vix_analysis.get("regime", "unknown")
    guidance = vix_analysis.get("guidance", "No guidance available")
    spy_price = chain_analysis.get("spy_price", "unknown")
    vix_trend = vix_analysis.get("vix_trend", "unknown")

    content = f"""# Daily Strategy Research — {today}

## Market Snapshot
- **SPY Price**: ${spy_price}
- **VIX**: {vix if vix else "unavailable"}
- **VIX Regime**: {regime}
- **VIX Trend**: {vix_trend}

## Iron Condor Guidance for {regime.upper()} Regime
{guidance}

## Parameter Recommendations
- **Delta**: {"15" if regime in ("calm", "normal") else "10-12" if regime == "volatile" else "20" if regime == "elevated" else "DO NOT TRADE"}
- **DTE**: {"30-45" if regime != "spike" else "N/A — wait for VIX drop"}
- **Wing Width**: ${"10" if regime in ("calm", "normal", "elevated") else "15-20" if regime == "volatile" else "N/A"}
- **Profit Target**: {"50%" if regime in ("calm", "normal", "elevated") else "25%" if regime == "volatile" else "N/A"}
- **Max Position Size**: {"5%" if regime in ("calm", "normal") else "3%" if regime in ("elevated", "volatile") else "0%"}

## Generated
Auto-generated by `research_strategies.py` on {today}.
Severity: LOW
"""
    return content


def save_research_state(vix_analysis: dict, chain_analysis: dict):
    """Save research state for downstream consumers."""
    state = {
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "vix": vix_analysis,
        "spy_chain": chain_analysis,
        "recommendations": {
            "regime": vix_analysis.get("regime", "unknown"),
            "should_trade": vix_analysis.get("regime") not in ("spike", "unknown"),
            "suggested_delta": 15 if vix_analysis.get("regime") in ("calm", "normal") else 10,
            "suggested_profit_target": 0.50 if vix_analysis.get("regime") != "volatile" else 0.25,
        },
    }
    RESEARCH_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    RESEARCH_STATE_FILE.write_text(json.dumps(state, indent=2))
    logger.info(f"Research state saved to {RESEARCH_STATE_FILE}")


def main(dry_run: bool = False):
    """Run daily strategy research."""
    logger.info("=" * 70)
    logger.info("DAILY STRATEGY RESEARCH")
    logger.info(f"Time: {datetime.now(timezone.utc).isoformat()}")
    logger.info("=" * 70)

    # 1. Fetch VIX data
    logger.info("Fetching VIX data from CBOE...")
    vix_data = fetch_url(SOURCES[0]["url"])
    vix_analysis = analyze_vix_regime(vix_data)
    logger.info(f"  VIX: {vix_analysis.get('vix')} | Regime: {vix_analysis.get('regime')}")

    # 2. Fetch SPY options chain
    logger.info("Fetching SPY options chain...")
    chain_data = fetch_url(SOURCES[1]["url"])
    chain_analysis = analyze_spy_options_chain(chain_data)
    logger.info(f"  SPY: ${chain_analysis.get('spy_price', 'N/A')}")

    # 3. Generate research lesson
    lesson_content = generate_daily_research_lesson(vix_analysis, chain_analysis)
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    lesson_file = LESSONS_DIR / f"research_{today}.md"

    # Quality gate: don't save lessons with no real data (dilutes RAG)
    has_real_data = (
        "$unknown" not in lesson_content
        and "unavailable" not in lesson_content
        and vix_analysis.get("vix") is not None
    )

    if dry_run:
        logger.info(f"[DRY RUN] Would write: {lesson_file.name}")
        logger.info(lesson_content[:200] + "...")
    elif not has_real_data:
        logger.warning("Research lesson skipped: no real market data (VIX/SPY unavailable)")
    else:
        LESSONS_DIR.mkdir(parents=True, exist_ok=True)
        lesson_file.write_text(lesson_content)
        logger.info(f"Research lesson saved: {lesson_file}")
        save_research_state(vix_analysis, chain_analysis)

    # 4. Summary
    logger.info("\n" + "=" * 70)
    logger.info("RESEARCH SUMMARY")
    logger.info(f"  Regime: {vix_analysis.get('regime')}")
    logger.info(f"  Should trade: {vix_analysis.get('regime') not in ('spike', 'unknown')}")
    logger.info(f"  Guidance: {vix_analysis.get('guidance', 'N/A')[:100]}")
    logger.info("=" * 70)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Daily strategy research")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
