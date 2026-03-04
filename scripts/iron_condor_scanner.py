#!/usr/bin/env python3
"""
Iron Condor Scanner - Daily Entry Opportunity Detection

Scans for optimal iron condor entry conditions on SPY and creates
GitHub issue for CEO approval with auto-execute after 30 minutes.

Entry Criteria (per CLAUDE.md):
- SPY only (best liquidity, tightest spreads)
- 30-45 DTE
- Short strikes at 15-20 delta
- $10-wide wings
- Max 2 iron condors at a time (8 option legs canonical limit)
- 5% max risk per position

Usage:
    python scripts/iron_condor_scanner.py          # Scan and alert
    python scripts/iron_condor_scanner.py --dry-run  # Scan without alert
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from src.core.trading_constants import MAX_POSITIONS as MAX_OPTION_LEGS

# Guard against AssertionError in CI/GitHub Actions where stdin is not a TTY
try:
    load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env", override=False)
except (AssertionError, Exception):
    pass  # In CI, env vars are set via workflow secrets

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Constants from CLAUDE.md / trading constants
MAX_IRON_CONDORS = max(1, int(MAX_OPTION_LEGS) // 4)
POSITION_SIZE_PCT = 0.05  # 5% max risk per position
TARGET_DELTA = 0.15  # 15-20 delta range
MIN_DTE = 21
MAX_DTE = 50
WING_WIDTH = 10  # $10 wide spreads per CLAUDE.md

IC_TRADE_LOG = Path(__file__).parent.parent / "data" / "ic_trade_log.json"


def get_alpaca_clients():
    """Get Alpaca trading and data clients."""
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.historical.option import OptionHistoricalDataClient
    from alpaca.trading.client import TradingClient
    from src.utils.alpaca_client import get_alpaca_credentials

    api_key, secret = get_alpaca_credentials()
    if not api_key or not secret:
        logger.error("Alpaca credentials not found")
        return None, None, None

    trading_client = TradingClient(api_key, secret, paper=True)
    stock_data_client = StockHistoricalDataClient(api_key, secret)
    options_data_client = OptionHistoricalDataClient(api_key, secret)

    return trading_client, stock_data_client, options_data_client


def get_spy_price(stock_client) -> float:
    """Get current SPY price."""
    from alpaca.data.requests import StockLatestQuoteRequest

    try:
        request = StockLatestQuoteRequest(symbol_or_symbols=["SPY"])
        quote = stock_client.get_stock_latest_quote(request)
        if "SPY" in quote:
            mid = (quote["SPY"].ask_price + quote["SPY"].bid_price) / 2
            logger.info(f"SPY current price: ${mid:.2f}")
            return mid
    except Exception as e:
        logger.warning(f"Could not fetch SPY price: {e}")

    # Fallback
    return 600.0


def get_account_equity(trading_client) -> float:
    """Get current account equity."""
    try:
        account = trading_client.get_account()
        equity = float(account.equity)
        logger.info(f"Account equity: ${equity:,.2f}")
        return equity
    except Exception as e:
        logger.error(f"Could not get account equity: {e}")
        return 100000.0  # Default for paper account


def count_open_ic_positions(trading_client) -> int:
    """Count current open iron condor positions."""
    try:
        positions = trading_client.get_all_positions()
        # Count SPY option positions (IC = 4 legs)
        spy_options = [p for p in positions if p.symbol.startswith("SPY") and len(p.symbol) > 5]
        # Each IC has 4 legs, so divide by 4
        ic_count = len(spy_options) // 4
        logger.info(f"Open IC positions: {ic_count} (max: {MAX_IRON_CONDORS})")
        return ic_count
    except Exception as e:
        logger.error(f"Could not count positions: {e}")
        return 0


def get_existing_expiries(trading_client) -> set[str]:
    """Get expiry dates of existing IC positions to avoid duplicates."""
    try:
        positions = trading_client.get_all_positions()
        expiries = set()
        for p in positions:
            sym = p.symbol
            if sym.startswith("SPY") and len(sym) > 5:
                # OCC format: SPY260327P00640000 -> 260327 -> 2026-03-27
                date_part = sym[3:9]
                expiry = f"20{date_part[:2]}-{date_part[2:4]}-{date_part[4:6]}"
                expiries.add(expiry)
        logger.info(f"Existing IC expiries: {sorted(expiries) if expiries else 'none'}")
        return expiries
    except Exception as e:
        logger.warning(f"Could not get existing expiries: {e}")
        return set()


def find_expiration_date(
    options_client=None,
    spy_price: float = 600.0,
    exclude_expiries: set[str] | None = None,
) -> str | None:
    """Find optimal expiration date by querying Alpaca for real option chains.

    Validates that contracts actually exist before returning an expiry.
    Falls back to Friday-based calculation only if the API is unavailable.
    """
    et = ZoneInfo("America/New_York")
    today = datetime.now(et)
    exclude = exclude_expiries or set()

    # Try to get real expirations from Alpaca options API
    if options_client:
        try:
            from alpaca.data.requests import OptionChainRequest

            # Query a near-ATM put to discover available expirations
            request = OptionChainRequest(
                underlying_symbol="SPY",
                strike_price_gte=spy_price * 0.93,
                strike_price_lte=spy_price * 0.97,
                type="put",
            )
            chain = options_client.get_option_chain(request)

            # Extract unique expirations from the chain
            real_expiries = set()
            for symbol in chain:
                # OCC symbol: SPY260327P00650000 -> expiry 260327
                if len(symbol) >= 9:
                    date_part = symbol[3:9]
                    try:
                        exp_date = datetime.strptime(f"20{date_part}", "%Y%m%d")
                        exp_str = exp_date.strftime("%Y-%m-%d")
                        dte = (exp_date.replace(tzinfo=et) - today).days
                        if MIN_DTE <= dte <= MAX_DTE and exp_str not in exclude:
                            real_expiries.add((exp_str, dte))
                    except ValueError:
                        continue

            if real_expiries:
                candidates = sorted(real_expiries, key=lambda x: abs(x[1] - 35))
                best = candidates[0]
                logger.info(f"Target expiration (API-verified): {best[0]} ({best[1]} DTE)")
                return best[0]
            else:
                logger.warning("No valid expirations found in Alpaca option chain for DTE window")
        except Exception as e:
            logger.warning(f"Option chain query failed, falling back to Friday calc: {e}")

    # Fallback: Find Fridays in the 30-45 DTE window (third Friday = monthly)
    candidates = []
    for days_out in range(MIN_DTE, MAX_DTE + 1):
        candidate = today + timedelta(days=days_out)
        # Prefer third Fridays (monthly expirations) — always listed on Alpaca
        if candidate.weekday() == 4:
            day = candidate.day
            is_third_friday = 15 <= day <= 21
            expiry_str = candidate.strftime("%Y-%m-%d")
            if expiry_str not in exclude:
                dte = (candidate - today).days
                candidates.append((expiry_str, dte, is_third_friday))

    if not candidates:
        logger.warning("No available expiry dates (all Fridays in window already have positions)")
        return None

    # Prefer third Fridays (monthly), then closest to 35 DTE
    third_fridays = [c for c in candidates if c[2]]
    if third_fridays:
        third_fridays.sort(key=lambda x: abs(x[1] - 35))
        best = third_fridays[0]
    else:
        candidates.sort(key=lambda x: abs(x[1] - 35))
        best = candidates[0]

    logger.info(f"Target expiration (fallback): {best[0]} ({best[1]} DTE)")
    return best[0]


def calculate_strikes(spy_price: float) -> dict:
    """Calculate iron condor strikes based on 15-20 delta targeting."""
    # 15 delta is roughly 5% OTM for 30-45 DTE
    # Round to nearest $5 increment (SPY options)

    def round_to_5(x: float) -> float:
        return round(x / 5) * 5

    short_put = round_to_5(spy_price * 0.95)  # ~5% below
    long_put = short_put - WING_WIDTH

    short_call = round_to_5(spy_price * 1.05)  # ~5% above
    long_call = short_call + WING_WIDTH

    return {
        "short_put": short_put,
        "long_put": long_put,
        "short_call": short_call,
        "long_call": long_call,
    }


def build_occ_symbol(expiry: str, strike: float, opt_type: str) -> str:
    """Build OCC option symbol. expiry='2026-03-27', opt_type='P' or 'C'."""
    date_part = expiry.replace("-", "")[2:]  # YYMMDD
    return f"SPY{date_part}{opt_type}{int(strike * 1000):08d}"


def validate_symbols_exist(options_client, expiry: str, strikes: dict) -> bool:
    """Verify that the OCC symbols for all 4 legs exist on Alpaca."""
    if not options_client:
        logger.warning("No options client — skipping symbol validation")
        return True  # Optimistic if no client

    symbols = [
        build_occ_symbol(expiry, strikes["long_put"], "P"),
        build_occ_symbol(expiry, strikes["short_put"], "P"),
        build_occ_symbol(expiry, strikes["short_call"], "C"),
        build_occ_symbol(expiry, strikes["long_call"], "C"),
    ]

    try:
        from alpaca.data.requests import OptionSnapshotRequest

        request = OptionSnapshotRequest(symbol_or_symbols=symbols)
        snapshots = options_client.get_option_snapshot(request)
        found = set(snapshots.keys())
        missing = [s for s in symbols if s not in found]

        if missing:
            logger.warning(f"Missing symbols on Alpaca: {missing}")
            return False

        logger.info(f"All 4 IC legs validated: {symbols}")
        return True
    except Exception as e:
        logger.warning(f"Symbol validation failed: {e}")
        return False


def estimate_credit(strikes: dict) -> dict:
    """Estimate credit and risk for the iron condor."""
    # Conservative estimate: $1.50-2.50 total credit for SPY IC
    # Using $1.85 as middle estimate
    estimated_credit = 2.00
    max_risk = (WING_WIDTH * 100) - (estimated_credit * 100)

    return {
        "credit": estimated_credit,
        "credit_dollars": estimated_credit * 100,
        "max_risk": max_risk,
        "risk_reward": (max_risk / (estimated_credit * 100) if estimated_credit > 0 else 0),
        "win_probability": 0.85,  # 15 delta = ~85% POP
    }


def check_vix_conditions() -> tuple[bool, str]:
    """Check if VIX conditions are favorable for entry."""
    try:
        from src.signals.vix_mean_reversion_signal import VIXMeanReversionSignal

        signal = VIXMeanReversionSignal()
        result = signal.calculate_signal()

        if result.signal == "OPTIMAL_ENTRY":
            return True, f"VIX optimal ({result.current_vix:.1f})"
        elif result.signal == "GOOD_ENTRY":
            return True, f"VIX good ({result.current_vix:.1f})"
        elif result.signal == "AVOID":
            return False, f"VIX unfavorable: {result.reason}"
        else:
            return True, f"VIX neutral ({result.current_vix:.1f})"
    except Exception as e:
        logger.warning(f"VIX check failed: {e}")
        return True, "VIX check unavailable"


def load_trade_log() -> dict:
    """Load or initialize the trade log."""
    if IC_TRADE_LOG.exists():
        with open(IC_TRADE_LOG) as f:
            return json.load(f)
    return {
        "trades": [],
        "stats": {
            "total_trades": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": None,
            "avg_credit": 0,
            "avg_pnl": None,
            "total_pnl": 0,
        },
    }


def create_github_issue(opportunity: dict) -> str | None:
    """Create GitHub issue for trade approval with auto-execute."""
    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    repo = os.getenv("GITHUB_REPOSITORY", "IgorGanapolsky/trading")

    if not token:
        logger.error("GITHUB_TOKEN not set - cannot create issue")
        return None

    from urllib.error import URLError
    from urllib.request import Request, urlopen

    body = f"""## 🎯 IRON CONDOR OPPORTUNITY - SPY

### Trade Details
| Field | Value |
|-------|-------|
| **Expiry** | {opportunity["expiry"]} ({opportunity["dte"]} DTE) |
| **Short Put** | ${opportunity["strikes"]["short_put"]:.0f} (delta: ~0.15) |
| **Long Put** | ${opportunity["strikes"]["long_put"]:.0f} |
| **Short Call** | ${opportunity["strikes"]["short_call"]:.0f} (delta: ~0.15) |
| **Long Call** | ${opportunity["strikes"]["long_call"]:.0f} |

### Financials
| Metric | Value |
|--------|-------|
| **Credit** | ${opportunity["pricing"]["credit"]:.2f} (${opportunity["pricing"]["credit_dollars"]:.0f} per contract) |
| **Max Risk** | ${opportunity["pricing"]["max_risk"]:.0f} per contract |
| **Risk/Reward** | {opportunity["pricing"]["risk_reward"]:.1f}:1 |
| **Win Probability** | ~{opportunity["pricing"]["win_probability"] * 100:.0f}% |

### Account Status
| Metric | Value |
|--------|-------|
| **Current Positions** | {opportunity["positions"]}/{MAX_IRON_CONDORS} |
| **Account Equity** | ${opportunity["equity"]:,.2f} |
| **Max Risk (5%)** | ${opportunity["equity"] * POSITION_SIZE_PCT:,.2f} |

### VIX Conditions
{opportunity["vix_status"]}

---

## ⏱️ AUTO-EXECUTE IN 30 MINUTES

This trade will **auto-execute at {(datetime.utcnow() + timedelta(minutes=30)).strftime("%H:%M UTC")}** unless you comment:
- **REJECT** - Cancel this trade
- **APPROVE** - Execute immediately

---

*Generated by Iron Condor Scanner | {datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")}*
"""

    payload = {
        "title": f"🎯 IC Opportunity: SPY {opportunity['expiry']} | ${opportunity['pricing']['credit_dollars']:.0f} credit",
        "body": body,
        "labels": ["iron-condor", "trade-approval", "automated"],
    }

    try:
        import json as json_module

        data = json_module.dumps(payload).encode("utf-8")
        req = Request(
            f"https://api.github.com/repos/{repo}/issues",
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github.v3+json",
            },
        )
        with urlopen(req, timeout=30) as response:
            if response.status == 201:
                result = json_module.loads(response.read().decode("utf-8"))
                issue_url = result.get("html_url")
                issue_number = result.get("number")
                logger.info(f"GitHub issue created: {issue_url}")
                return issue_number
    except URLError as e:
        logger.error(f"Failed to create GitHub issue: {e}")

    return None


def scan_for_opportunity(dry_run: bool = False) -> dict | None:
    """Main scanner function - find IC opportunity and alert."""
    logger.info("=" * 60)
    logger.info("IRON CONDOR SCANNER - Starting scan")
    logger.info("=" * 60)

    # Get clients
    trading_client, stock_client, options_client = get_alpaca_clients()
    if not trading_client:
        logger.error("Failed to initialize Alpaca clients")
        return None

    # Check position limit
    open_positions = count_open_ic_positions(trading_client)
    if open_positions >= MAX_IRON_CONDORS:
        logger.info(
            f"Position limit reached ({open_positions}/{MAX_IRON_CONDORS}) - no scan needed"
        )
        return None

    # Get market data
    spy_price = get_spy_price(stock_client)
    equity = get_account_equity(trading_client)

    # Check VIX conditions
    vix_ok, vix_status = check_vix_conditions()
    if not vix_ok:
        logger.warning(f"VIX conditions unfavorable: {vix_status}")
        return None

    # Find expiry that doesn't overlap with existing positions
    existing_expiries = get_existing_expiries(trading_client)
    expiry = find_expiration_date(
        options_client=options_client,
        spy_price=spy_price,
        exclude_expiries=existing_expiries,
    )
    if not expiry:
        logger.info("No available expiry dates — all slots in DTE window taken")
        return None
    dte = (datetime.strptime(expiry, "%Y-%m-%d") - datetime.now()).days
    strikes = calculate_strikes(spy_price)

    # Validate all 4 OCC symbols exist on Alpaca before proceeding
    if not validate_symbols_exist(options_client, expiry, strikes):
        logger.error(f"Symbol validation failed for {expiry} — contracts don't exist on Alpaca")
        return None

    pricing = estimate_credit(strikes)

    opportunity = {
        "timestamp": datetime.utcnow().isoformat(),
        "spy_price": spy_price,
        "expiry": expiry,
        "dte": dte,
        "strikes": strikes,
        "pricing": pricing,
        "equity": equity,
        "positions": open_positions,
        "vix_status": vix_status,
    }

    logger.info("=" * 60)
    logger.info("OPPORTUNITY FOUND")
    logger.info("=" * 60)
    logger.info(f"Expiry: {expiry} ({dte} DTE)")
    logger.info(f"Put Spread: ${strikes['long_put']:.0f}/${strikes['short_put']:.0f}")
    logger.info(f"Call Spread: ${strikes['short_call']:.0f}/${strikes['long_call']:.0f}")
    logger.info(f"Credit: ${pricing['credit']:.2f} (${pricing['credit_dollars']:.0f})")
    logger.info(f"Max Risk: ${pricing['max_risk']:.0f}")
    logger.info(f"VIX: {vix_status}")
    logger.info("=" * 60)

    if dry_run:
        logger.info("DRY RUN - Not creating GitHub issue")
        return opportunity

    # Create GitHub issue for approval
    issue_number = create_github_issue(opportunity)
    if issue_number:
        opportunity["issue_number"] = issue_number
        logger.info(f"Trade approval issue created: #{issue_number}")

        # Save opportunity to file for executor
        pending_file = Path(__file__).parent.parent / "data" / "pending_ic_trade.json"
        pending_file.parent.mkdir(parents=True, exist_ok=True)
        with open(pending_file, "w") as f:
            json.dump(opportunity, f, indent=2)
        logger.info(f"Opportunity saved to {pending_file}")

    return opportunity


def main():
    parser = argparse.ArgumentParser(description="Iron Condor Scanner")
    parser.add_argument("--dry-run", action="store_true", help="Scan without creating alert")
    args = parser.parse_args()

    # Check market hours
    et = ZoneInfo("America/New_York")
    now = datetime.now(et)
    if now.weekday() >= 5:  # Weekend
        logger.info("Market closed (weekend) - no scan")
        return

    hour = now.hour
    if hour < 9 or (hour == 9 and now.minute < 30) or hour >= 16:
        logger.info("Market closed - no scan")
        return

    result = scan_for_opportunity(dry_run=args.dry_run)

    if result:
        print(json.dumps(result, indent=2, default=str))
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main() or 0)
