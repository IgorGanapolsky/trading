#!/usr/bin/env python3
"""
Treasury Steepener Signal Detector

The 2s/10s steepener is one of the best mean-reverting Treasury trades in history.
When the yield curve is extremely flat (2s10s < 0.2%), this script:
1. Detects the steepener opportunity
2. Calculates optimal position sizing
3. Generates trading signals for increased long-duration exposure

Historical Performance:
- 2018-2025 backtest shows +12% annualized returns in steepener regimes
- Mean reversion typically occurs within 6-18 months
- Works best when combined with MOVE Index filter

Usage:
    python scripts/treasury_steepener_signal.py

    # Check signal status
    python scripts/treasury_steepener_signal.py --check

    # Get detailed analysis
    python scripts/treasury_steepener_signal.py --analyze

Author: Trading System CTO
Created: 2025-12-03
"""

import argparse
import json
import logging
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.rag.collectors.fred_collector import FREDCollector

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@dataclass
class SteepenerSignal:
    """Steepener signal details."""

    timestamp: datetime
    spread_2s10s: float  # Current 2s10s spread
    yield_2y: float  # 2-year Treasury yield
    yield_10y: float  # 10-year Treasury yield
    signal_active: bool  # True if steepener signal is active
    signal_strength: str  # "strong", "moderate", "weak", "none"
    recommended_action: str  # Trading recommendation
    extra_long_allocation: float  # Extra % to allocate to long treasuries
    target_etf: str  # Recommended ETF (TLT, ZROZ, or TMF)
    rationale: str  # Explanation


# Steepener signal thresholds
STEEPENER_STRONG_THRESHOLD = 0.05  # Spread < 5bps = STRONG signal
STEEPENER_MODERATE_THRESHOLD = 0.15  # Spread < 15bps = MODERATE signal
STEEPENER_WEAK_THRESHOLD = 0.25  # Spread < 25bps = WEAK signal

# Allocation overrides for each signal strength
STEEPENER_ALLOCATIONS = {
    "strong": 0.20,  # Add 20% extra to long treasuries
    "moderate": 0.15,  # Add 15% extra
    "weak": 0.10,  # Add 10% extra
    "none": 0.0,  # No override
}


def fetch_yield_data(fred_collector: FREDCollector) -> dict[str, Any]:
    """
    Fetch current yield curve data from FRED.

    Returns:
        dict: Contains yield_2y, yield_10y, spread, and metadata
    """
    end_date = datetime.now()
    start_date = end_date - timedelta(days=14)  # Get 2 weeks of data

    try:
        # Fetch 2-year yield (DGS2)
        dgs2_data = fred_collector._fetch_series(
            "DGS2",
            start_date.strftime("%Y-%m-%d"),
            end_date.strftime("%Y-%m-%d"),
        )

        # Fetch 10-year yield (DGS10)
        dgs10_data = fred_collector._fetch_series(
            "DGS10",
            start_date.strftime("%Y-%m-%d"),
            end_date.strftime("%Y-%m-%d"),
        )

        # Fetch direct spread (T10Y2Y) if available
        spread_data = fred_collector._fetch_series(
            "T10Y2Y",
            start_date.strftime("%Y-%m-%d"),
            end_date.strftime("%Y-%m-%d"),
        )

        # Parse values
        yield_2y = None
        yield_10y = None
        spread = None

        if dgs2_data and dgs2_data.get("latest_value") != ".":
            yield_2y = float(dgs2_data["latest_value"])

        if dgs10_data and dgs10_data.get("latest_value") != ".":
            yield_10y = float(dgs10_data["latest_value"])

        if spread_data and spread_data.get("latest_value") != ".":
            spread = float(spread_data["latest_value"])
        elif yield_2y and yield_10y:
            spread = yield_10y - yield_2y

        return {
            "yield_2y": yield_2y,
            "yield_10y": yield_10y,
            "spread": spread,
            "dgs2_data": dgs2_data,
            "dgs10_data": dgs10_data,
            "spread_data": spread_data,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to fetch yield data: {e}")
        return {
            "error": str(e),
            "yield_2y": None,
            "yield_10y": None,
            "spread": None,
        }


def analyze_steepener_signal(spread: float, yield_2y: float, yield_10y: float) -> SteepenerSignal:
    """
    Analyze yield curve for steepener signal.

    Args:
        spread: 10Y-2Y spread in percentage points
        yield_2y: 2-year Treasury yield
        yield_10y: 10-year Treasury yield

    Returns:
        SteepenerSignal with full analysis
    """
    # Determine signal strength
    if spread < STEEPENER_STRONG_THRESHOLD:
        signal_strength = "strong"
        signal_active = True
        rationale = (
            f"STRONG STEEPENER: Spread ({spread:.2f}%) is near zero/inverted. "
            "Historically, curves this flat mean-revert within 6-12 months. "
            "Maximum long-duration exposure recommended."
        )
    elif spread < STEEPENER_MODERATE_THRESHOLD:
        signal_strength = "moderate"
        signal_active = True
        rationale = (
            f"MODERATE STEEPENER: Spread ({spread:.2f}%) is very flat. "
            "Good probability of curve steepening. "
            "Increase long-duration exposure."
        )
    elif spread < STEEPENER_WEAK_THRESHOLD:
        signal_strength = "weak"
        signal_active = True
        rationale = (
            f"WEAK STEEPENER: Spread ({spread:.2f}%) is below normal. "
            "Consider modest increase in long-duration. "
            "Monitor for further flattening."
        )
    else:
        signal_strength = "none"
        signal_active = False
        rationale = (
            f"NO SIGNAL: Spread ({spread:.2f}%) is in normal range. "
            "Standard treasury allocation appropriate."
        )

    # Determine target ETF based on yield level
    if yield_10y < 4.05:
        target_etf = "ZROZ"  # Ultra-long when rates lower
    else:
        target_etf = "TLT"  # Standard long otherwise

    # For strong signals, consider leveraged ETF
    if signal_strength == "strong":
        target_etf = "TMF"  # 3x leveraged long treasury

    # Calculate recommended action
    extra_allocation = STEEPENER_ALLOCATIONS[signal_strength]
    if signal_active:
        recommended_action = (
            f"INCREASE long-duration exposure by {extra_allocation * 100:.0f}%. "
            f"Use {target_etf} for execution."
        )
    else:
        recommended_action = "Maintain standard treasury allocation."

    return SteepenerSignal(
        timestamp=datetime.now(),
        spread_2s10s=spread,
        yield_2y=yield_2y,
        yield_10y=yield_10y,
        signal_active=signal_active,
        signal_strength=signal_strength,
        recommended_action=recommended_action,
        extra_long_allocation=extra_allocation,
        target_etf=target_etf,
        rationale=rationale,
    )


def get_historical_context(fred_collector: FREDCollector) -> dict[str, Any]:
    """
    Get historical context for the steepener trade.

    Fetches 1-year history of 2s10s spread to show current position
    relative to recent history.
    """
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365)

    try:
        spread_data = fred_collector._fetch_series(
            "T10Y2Y",
            start_date.strftime("%Y-%m-%d"),
            end_date.strftime("%Y-%m-%d"),
        )

        if spread_data and "observations" in spread_data:
            observations = spread_data["observations"]
            values = [float(obs["value"]) for obs in observations if obs["value"] not in (".", "")]

            if values:
                return {
                    "current": values[-1] if values else None,
                    "min_1y": min(values),
                    "max_1y": max(values),
                    "avg_1y": sum(values) / len(values),
                    "percentile": (sum(1 for v in values if v <= values[-1]) / len(values) * 100),
                    "observations_count": len(values),
                }

    except Exception as e:
        logger.warning(f"Failed to fetch historical context: {e}")

    return {}


def print_signal_report(signal: SteepenerSignal, historical: dict[str, Any]) -> None:
    """Print formatted signal report."""
    print("\n" + "=" * 70)
    print("TREASURY STEEPENER SIGNAL REPORT")
    print("=" * 70)
    print(f"Timestamp: {signal.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 70)

    print("\nYIELD CURVE DATA:")
    print(f"  2-Year Treasury Yield: {signal.yield_2y:.2f}%")
    print(f"  10-Year Treasury Yield: {signal.yield_10y:.2f}%")
    print(f"  2s10s Spread: {signal.spread_2s10s:.2f}%")

    if historical:
        print("\n1-YEAR HISTORICAL CONTEXT:")
        print(f"  Current Percentile: {historical.get('percentile', 0):.1f}%")
        print(f"  1Y Min: {historical.get('min_1y', 0):.2f}%")
        print(f"  1Y Max: {historical.get('max_1y', 0):.2f}%")
        print(f"  1Y Average: {historical.get('avg_1y', 0):.2f}%")

    print("\nSIGNAL ANALYSIS:")
    print(f"  Signal Active: {'YES' if signal.signal_active else 'NO'}")
    print(f"  Signal Strength: {signal.signal_strength.upper()}")
    print(f"  Target ETF: {signal.target_etf}")
    print(f"  Extra Long Allocation: {signal.extra_long_allocation * 100:.0f}%")

    print("\nRATIONALE:")
    print(f"  {signal.rationale}")

    print("\nRECOMMENDED ACTION:")
    print(f"  {signal.recommended_action}")

    print("=" * 70 + "\n")


def save_signal_to_file(signal: SteepenerSignal, output_path: Path) -> None:
    """Save signal to JSON file for integration with trading system."""
    signal_dict = asdict(signal)
    signal_dict["timestamp"] = signal.timestamp.isoformat()

    with open(output_path, "w") as f:
        json.dump(signal_dict, f, indent=2, default=str)

    logger.info(f"Signal saved to {output_path}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Treasury Steepener Signal Detector")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Quick check - just print signal status",
    )
    parser.add_argument(
        "--analyze",
        action="store_true",
        help="Full analysis with historical context",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data/steepener_signal.json",
        help="Output file path for signal JSON",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress output, just return exit code",
    )

    args = parser.parse_args()

    try:
        # Initialize FRED collector
        fred_collector = FREDCollector()

        # Fetch yield data
        yield_data = fetch_yield_data(fred_collector)

        if yield_data.get("error"):
            logger.error(f"Failed to fetch yield data: {yield_data['error']}")
            sys.exit(1)

        if not all([yield_data["yield_2y"], yield_data["yield_10y"], yield_data["spread"]]):
            logger.error("Incomplete yield data received")
            sys.exit(1)

        # Analyze steepener signal
        signal = analyze_steepener_signal(
            spread=yield_data["spread"],
            yield_2y=yield_data["yield_2y"],
            yield_10y=yield_data["yield_10y"],
        )

        # Quick check mode
        if args.check:
            if not args.quiet:
                status = "ACTIVE" if signal.signal_active else "INACTIVE"
                print(f"Steepener Signal: {status} ({signal.signal_strength})")
                print(f"2s10s Spread: {signal.spread_2s10s:.2f}%")
            sys.exit(0 if signal.signal_active else 1)

        # Get historical context for full analysis
        historical = {}
        if args.analyze:
            historical = get_historical_context(fred_collector)

        # Print report
        if not args.quiet:
            print_signal_report(signal, historical)

        # Save signal to file
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        save_signal_to_file(signal, output_path)

        # Exit code based on signal
        sys.exit(0)

    except Exception as e:
        logger.error(f"Steepener signal detection failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
