#!/usr/bin/env python3
"""
Bond Data Ingester

Fetches and caches daily bond data for the trading system.
Supports Treasuries, Corporate bonds (IG/HY), and Municipal bonds via ETF proxies.

Bond ETF Universe:
- Treasuries: TLT (20+ year), IEF (7-10 year), SHY (1-3 year), BND (Total Bond)
- Corporate: LQD (Investment Grade), JNK/HYG (High Yield)
- Municipal: MUB (National Muni), VTEB (Tax-Exempt)
- TIPS: TIP (Inflation Protected)

Data stored in: data/bonds/

Author: Trading System
Created: 2025-12-03
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv

load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Bond ETF universe with metadata
BOND_ETFS = {
    # Treasury ETFs (Government-backed, lowest risk)
    "SHY": {
        "name": "iShares 1-3 Year Treasury Bond ETF",
        "category": "treasury",
        "duration": "short",
        "duration_years": 1.9,
        "yield_approx": 4.5,
        "credit_quality": "AAA",
        "expense_ratio": 0.15,
    },
    "IEF": {
        "name": "iShares 7-10 Year Treasury Bond ETF",
        "category": "treasury",
        "duration": "intermediate",
        "duration_years": 7.5,
        "yield_approx": 4.3,
        "credit_quality": "AAA",
        "expense_ratio": 0.15,
    },
    "TLT": {
        "name": "iShares 20+ Year Treasury Bond ETF",
        "category": "treasury",
        "duration": "long",
        "duration_years": 16.5,
        "yield_approx": 4.4,
        "credit_quality": "AAA",
        "expense_ratio": 0.15,
    },
    "BND": {
        "name": "Vanguard Total Bond Market ETF",
        "category": "aggregate",
        "duration": "intermediate",
        "duration_years": 6.1,
        "yield_approx": 4.8,
        "credit_quality": "AA",
        "expense_ratio": 0.03,
    },
    "AGG": {
        "name": "iShares Core U.S. Aggregate Bond ETF",
        "category": "aggregate",
        "duration": "intermediate",
        "duration_years": 6.2,
        "yield_approx": 4.9,
        "credit_quality": "AA",
        "expense_ratio": 0.03,
    },
    # Corporate Bond ETFs
    "LQD": {
        "name": "iShares iBoxx $ Investment Grade Corporate Bond ETF",
        "category": "corporate_ig",
        "duration": "intermediate",
        "duration_years": 8.5,
        "yield_approx": 5.5,
        "credit_quality": "A",
        "expense_ratio": 0.14,
    },
    "VCIT": {
        "name": "Vanguard Intermediate-Term Corporate Bond ETF",
        "category": "corporate_ig",
        "duration": "intermediate",
        "duration_years": 6.3,
        "yield_approx": 5.2,
        "credit_quality": "A",
        "expense_ratio": 0.04,
    },
    "JNK": {
        "name": "SPDR Bloomberg High Yield Bond ETF",
        "category": "corporate_hy",
        "duration": "short",
        "duration_years": 3.8,
        "yield_approx": 7.5,
        "credit_quality": "BB",
        "expense_ratio": 0.40,
    },
    "HYG": {
        "name": "iShares iBoxx $ High Yield Corporate Bond ETF",
        "category": "corporate_hy",
        "duration": "short",
        "duration_years": 3.9,
        "yield_approx": 7.3,
        "credit_quality": "BB",
        "expense_ratio": 0.48,
    },
    # Municipal Bond ETFs (Tax-advantaged)
    "MUB": {
        "name": "iShares National Muni Bond ETF",
        "category": "municipal",
        "duration": "intermediate",
        "duration_years": 6.3,
        "yield_approx": 3.5,
        "tax_equivalent_yield": 5.5,  # Assuming 37% tax bracket
        "credit_quality": "AA",
        "expense_ratio": 0.07,
    },
    "VTEB": {
        "name": "Vanguard Tax-Exempt Bond ETF",
        "category": "municipal",
        "duration": "intermediate",
        "duration_years": 5.6,
        "yield_approx": 3.4,
        "tax_equivalent_yield": 5.4,
        "credit_quality": "AA",
        "expense_ratio": 0.05,
    },
    # TIPS (Inflation Protected)
    "TIP": {
        "name": "iShares TIPS Bond ETF",
        "category": "tips",
        "duration": "intermediate",
        "duration_years": 6.5,
        "yield_approx": 2.2,  # Real yield
        "credit_quality": "AAA",
        "expense_ratio": 0.19,
    },
    "SCHP": {
        "name": "Schwab U.S. TIPS ETF",
        "category": "tips",
        "duration": "intermediate",
        "duration_years": 6.8,
        "yield_approx": 2.1,
        "credit_quality": "AAA",
        "expense_ratio": 0.03,
    },
}

# Data directory
DATA_DIR = Path("data/bonds")


def ensure_data_dir() -> Path:
    """Ensure data directory exists."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR


def fetch_bond_data(
    symbol: str,
    period: str = "6mo",
    interval: str = "1d",
) -> pd.DataFrame | None:
    """
    Fetch bond ETF historical data using yfinance.

    Args:
        symbol: Bond ETF ticker symbol
        period: Data period (1mo, 3mo, 6mo, 1y, 2y, 5y)
        interval: Data interval (1d, 1wk, 1mo)

    Returns:
        DataFrame with OHLCV data or None if error
    """
    try:
        import yfinance as yf

        ticker = yf.Ticker(symbol)
        hist = ticker.history(period=period, interval=interval)

        if hist.empty:
            logger.warning(f"No data returned for {symbol}")
            return None

        # Add computed columns
        hist["Returns"] = hist["Close"].pct_change()
        hist["Volatility_20d"] = hist["Returns"].rolling(window=20).std() * (252**0.5)
        hist["SMA_20"] = hist["Close"].rolling(window=20).mean()
        hist["SMA_50"] = hist["Close"].rolling(window=50).mean()

        # Momentum indicator
        hist["Momentum_Gate"] = hist["SMA_20"] >= hist["SMA_50"]

        logger.info(f"Fetched {len(hist)} records for {symbol}")
        return hist

    except ImportError:
        logger.error("yfinance not installed. Run: pip install yfinance")
        return None
    except Exception as e:
        logger.error(f"Error fetching {symbol}: {e}")
        return None


def calculate_bond_metrics(df: pd.DataFrame, metadata: dict) -> dict[str, Any]:
    """
    Calculate bond-specific metrics from price data.

    Args:
        df: DataFrame with OHLCV data
        metadata: Bond ETF metadata from BOND_ETFS

    Returns:
        Dictionary of calculated metrics
    """
    if df is None or df.empty:
        return {}

    try:
        current_price = float(df["Close"].iloc[-1])
        sma_20 = float(df["SMA_20"].iloc[-1]) if "SMA_20" in df.columns else current_price
        sma_50 = float(df["SMA_50"].iloc[-1]) if "SMA_50" in df.columns else current_price

        # Returns
        returns_1d = float(df["Returns"].iloc[-1]) if "Returns" in df.columns else 0
        returns_1m = ((df["Close"].iloc[-1] / df["Close"].iloc[-21]) - 1) if len(df) >= 21 else 0
        returns_3m = ((df["Close"].iloc[-1] / df["Close"].iloc[-63]) - 1) if len(df) >= 63 else 0

        # Volatility
        volatility_20d = (
            float(df["Volatility_20d"].iloc[-1]) if "Volatility_20d" in df.columns else 0
        )

        # Momentum
        momentum_gate = sma_20 >= sma_50

        # Duration-adjusted return (approximation)
        duration_years = metadata.get("duration_years", 5.0)
        duration_adjusted_vol = (
            volatility_20d / duration_years if duration_years > 0 else volatility_20d
        )

        return {
            "current_price": round(current_price, 2),
            "sma_20": round(sma_20, 2),
            "sma_50": round(sma_50, 2),
            "momentum_gate_open": momentum_gate,
            "returns_1d_pct": round(returns_1d * 100, 4),
            "returns_1m_pct": round(float(returns_1m) * 100, 2),
            "returns_3m_pct": round(float(returns_3m) * 100, 2),
            "volatility_20d_ann": round(volatility_20d * 100, 2),
            "duration_adjusted_vol": round(duration_adjusted_vol * 100, 2),
            "duration_years": duration_years,
            "yield_approx": metadata.get("yield_approx", 0),
            "credit_quality": metadata.get("credit_quality", "N/A"),
        }

    except Exception as e:
        logger.error(f"Error calculating metrics: {e}")
        return {}


def save_bond_data(symbol: str, df: pd.DataFrame, metrics: dict) -> Path:
    """
    Save bond data to Parquet file and metrics to JSON.

    Args:
        symbol: Bond ETF ticker
        df: DataFrame with price data
        metrics: Calculated metrics

    Returns:
        Path to saved Parquet file
    """
    ensure_data_dir()

    # Save price data as Parquet (efficient for time series)
    parquet_path = DATA_DIR / f"{symbol}_daily.parquet"
    df.to_parquet(parquet_path)
    logger.info(f"Saved price data to {parquet_path}")

    # Save metrics as JSON
    metrics_path = DATA_DIR / f"{symbol}_metrics.json"
    metrics["symbol"] = symbol
    metrics["last_updated"] = datetime.now().isoformat()
    metrics["data_points"] = len(df)

    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)
    logger.info(f"Saved metrics to {metrics_path}")

    return parquet_path


def load_bond_data(symbol: str) -> tuple[pd.DataFrame | None, dict | None]:
    """
    Load cached bond data.

    Args:
        symbol: Bond ETF ticker

    Returns:
        Tuple of (DataFrame, metrics_dict) or (None, None) if not cached
    """
    parquet_path = DATA_DIR / f"{symbol}_daily.parquet"
    metrics_path = DATA_DIR / f"{symbol}_metrics.json"

    df = None
    metrics = None

    if parquet_path.exists():
        try:
            df = pd.read_parquet(parquet_path)
        except Exception as e:
            logger.warning(f"Error loading {parquet_path}: {e}")

    if metrics_path.exists():
        try:
            with open(metrics_path) as f:
                metrics = json.load(f)
        except Exception as e:
            logger.warning(f"Error loading {metrics_path}: {e}")

    return df, metrics


def ingest_all_bonds(force_refresh: bool = False) -> dict[str, dict]:
    """
    Ingest data for all bond ETFs in the universe.

    Args:
        force_refresh: If True, fetch fresh data even if cached data exists

    Returns:
        Dictionary of symbol -> metrics
    """
    logger.info("=" * 80)
    logger.info("BOND DATA INGESTION")
    logger.info(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 80)

    results = {}
    success_count = 0
    error_count = 0

    for symbol, metadata in BOND_ETFS.items():
        logger.info(f"\nProcessing {symbol} ({metadata['name']})...")

        # Check if cached data is fresh (< 24 hours old)
        _, cached_metrics = load_bond_data(symbol)
        if cached_metrics and not force_refresh:
            last_updated = cached_metrics.get("last_updated")
            if last_updated:
                last_dt = datetime.fromisoformat(last_updated)
                age_hours = (datetime.now() - last_dt).total_seconds() / 3600
                if age_hours < 24:
                    logger.info(f"  Using cached data ({age_hours:.1f} hours old)")
                    results[symbol] = cached_metrics
                    success_count += 1
                    continue

        # Fetch fresh data
        df = fetch_bond_data(symbol)
        if df is not None:
            metrics = calculate_bond_metrics(df, metadata)
            metrics.update(metadata)  # Add static metadata
            save_bond_data(symbol, df, metrics)
            results[symbol] = metrics
            success_count += 1
        else:
            error_count += 1
            results[symbol] = {"error": "Failed to fetch data"}

    logger.info("\n" + "=" * 80)
    logger.info(f"INGESTION COMPLETE: {success_count} success, {error_count} errors")
    logger.info("=" * 80)

    # Save summary
    summary_path = DATA_DIR / "bond_universe_summary.json"
    summary = {
        "last_updated": datetime.now().isoformat(),
        "total_etfs": len(BOND_ETFS),
        "success_count": success_count,
        "error_count": error_count,
        "bonds": results,
    }
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    logger.info(f"Summary saved to {summary_path}")

    return results


def get_bond_allocation_signals() -> dict[str, Any]:
    """
    Generate bond allocation signals based on current market conditions.

    Returns:
        Dictionary with allocation recommendations
    """
    try:
        from src.rag.collectors.fred_collector import FREDCollector

        fred = FREDCollector()
        macro_regime = fred.get_macro_regime()
    except Exception as e:
        logger.warning(f"Could not get macro regime: {e}")
        macro_regime = {"regime": "unknown"}

    # Load bond metrics
    _, summary = load_bond_data("bond_universe_summary")
    if not summary:
        summary = ingest_all_bonds()

    # Generate allocation based on regime
    regime = macro_regime.get("regime", "unknown")

    # Default allocation (balanced)
    allocation = {
        "SHY": 0.20,  # Short-term treasuries
        "IEF": 0.20,  # Intermediate treasuries
        "TLT": 0.15,  # Long-term treasuries
        "LQD": 0.20,  # Investment grade corporate
        "JNK": 0.10,  # High yield (careful)
        "TIP": 0.15,  # Inflation protection
    }

    rationale = "Balanced bond allocation"

    if regime == "risk_off":
        # Flight to quality - favor treasuries
        allocation = {
            "SHY": 0.35,
            "IEF": 0.30,
            "TLT": 0.20,
            "LQD": 0.10,
            "JNK": 0.00,  # Avoid high yield in stress
            "TIP": 0.05,
        }
        rationale = "Risk-off: Heavy treasury allocation for safety"

    elif regime == "cautious":
        # Reduce risk slightly
        allocation = {
            "SHY": 0.30,
            "IEF": 0.25,
            "TLT": 0.15,
            "LQD": 0.15,
            "JNK": 0.05,
            "TIP": 0.10,
        }
        rationale = "Cautious: Favor short duration and quality"

    elif regime == "risk_on":
        # Can take more credit risk
        allocation = {
            "SHY": 0.10,
            "IEF": 0.15,
            "TLT": 0.15,
            "LQD": 0.30,
            "JNK": 0.15,
            "TIP": 0.15,
        }
        rationale = "Risk-on: Favor corporate bonds for yield"

    return {
        "regime": regime,
        "allocation": allocation,
        "rationale": rationale,
        "macro_data": macro_regime,
        "timestamp": datetime.now().isoformat(),
    }


def print_bond_summary():
    """Print a formatted summary of bond universe status."""
    results = ingest_all_bonds()

    print("\n" + "=" * 100)
    print("BOND UNIVERSE STATUS")
    print("=" * 100)
    print(f"{'Symbol':<8} {'Name':<45} {'Price':>8} {'1M%':>8} {'3M%':>8} {'Vol%':>8} {'Gate':>6}")
    print("-" * 100)

    for symbol, metrics in sorted(results.items()):
        if "error" in metrics:
            print(f"{symbol:<8} ERROR: {metrics['error']}")
            continue

        name = metrics.get("name", "")[:44]
        price = metrics.get("current_price", 0)
        ret_1m = metrics.get("returns_1m_pct", 0)
        ret_3m = metrics.get("returns_3m_pct", 0)
        vol = metrics.get("volatility_20d_ann", 0)
        gate = "OPEN" if metrics.get("momentum_gate_open", False) else "CLOSED"

        print(
            f"{symbol:<8} {name:<45} ${price:>6.2f} {ret_1m:>+7.2f}% {ret_3m:>+7.2f}% {vol:>7.1f}% {gate:>6}"
        )

    print("=" * 100)

    # Print allocation signals
    signals = get_bond_allocation_signals()
    print(f"\nMACRO REGIME: {signals['regime'].upper()}")
    print(f"RATIONALE: {signals['rationale']}")
    print("\nRECOMMENDED ALLOCATION:")
    for symbol, pct in signals["allocation"].items():
        if pct > 0:
            print(f"  {symbol}: {pct * 100:.0f}%")
    print()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Bond Data Ingester")
    parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Force refresh all data even if cached",
    )
    parser.add_argument(
        "--symbol",
        type=str,
        help="Fetch single symbol only",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Print formatted summary",
    )
    args = parser.parse_args()

    if args.summary:
        print_bond_summary()
    elif args.symbol:
        symbol = args.symbol.upper()
        if symbol in BOND_ETFS:
            df = fetch_bond_data(symbol)
            if df is not None:
                metrics = calculate_bond_metrics(df, BOND_ETFS[symbol])
                save_bond_data(symbol, df, metrics)
                print(f"\n{symbol} Metrics:")
                for k, v in metrics.items():
                    print(f"  {k}: {v}")
        else:
            print(f"Unknown symbol: {symbol}")
            print(f"Available: {', '.join(BOND_ETFS.keys())}")
    else:
        ingest_all_bonds(force_refresh=args.force_refresh)
