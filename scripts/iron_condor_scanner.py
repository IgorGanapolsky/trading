#!/usr/bin/env python3
"""
Iron Condor Scanner - Daily Entry Opportunity Detection

Scans for optimal iron condor entry conditions on SPY and creates
GitHub issue for CEO approval with auto-execute after 30 minutes.

Entry Criteria (baseline):
- SPY only (best liquidity, tightest spreads)
- 30-45 DTE
- Short strikes at 15-20 delta
- $10-wide wings
- Max 5 positions at a time
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

# Guard against AssertionError in CI/GitHub Actions where stdin is not a TTY
try:
    load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env", override=False)
except (AssertionError, Exception):
    pass  # In CI, env vars are set via workflow secrets

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Baseline constants
MAX_POSITIONS = 5
POSITION_SIZE_PCT = 0.05  # 5% max risk per position
BASE_TARGET_DELTA = 0.15  # 15 delta baseline
BASE_MIN_DTE = 30
BASE_MAX_DTE = 45
ADAPTIVE_TARGET_DELTA = 0.18  # Slightly closer strikes when cadence is low
ADAPTIVE_MIN_DTE = 21
TARGET_DTE = 35
WING_WIDTH = 10  # $10 wide spreads per CLAUDE.md

IC_TRADE_LOG = Path(__file__).parent.parent / "data" / "ic_trade_log.json"
SYSTEM_STATE_PATH = Path(__file__).parent.parent / "data" / "system_state.json"


def _load_json_dict(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def load_scan_profile(state_path: Path = SYSTEM_STATE_PATH) -> dict:
    """Resolve scanner thresholds from North Star cadence state.

    Adaptive mode is enabled only when cadence throughput is low and
    hard-risk blockers (risk caps or AI credit stress) are not active.
    """
    base = {
        "mode": "baseline",
        "target_delta": BASE_TARGET_DELTA,
        "min_dte": BASE_MIN_DTE,
        "max_dte": BASE_MAX_DTE,
        "target_dte": TARGET_DTE,
        "allow_vix_override": False,
        "reason": "Cadence healthy or hard-risk blockers active; baseline scan profile.",
    }
    state = _load_json_dict(state_path)
    if not state:
        return base

    weekly_gate = state.get("north_star_weekly_gate", {})
    if not isinstance(weekly_gate, dict):
        return base

    cadence = weekly_gate.get("cadence_kpi", {})
    if not isinstance(cadence, dict):
        cadence = {}
    enforcement = weekly_gate.get("cadence_enforcement", {})
    if not isinstance(enforcement, dict):
        enforcement = {}
    diagnostic = weekly_gate.get("no_trade_diagnostic", {})
    if not isinstance(diagnostic, dict):
        diagnostic = {}

    blocked_categories = diagnostic.get("blocked_categories", [])
    if not isinstance(blocked_categories, list):
        blocked_categories = []
    blocked_set = {str(item) for item in blocked_categories}
    hard_blockers = {"risk_caps", "ai_credit_stress"}

    cadence_passed = bool(cadence.get("passed"))
    setup_missed = not bool(cadence.get("meets_qualified_setups", True))
    setups_observed = int(cadence.get("qualified_setups_observed", 0))
    et_now = datetime.now(ZoneInfo("America/New_York"))
    midweek_no_setups = et_now.weekday() >= 2 and setups_observed <= 0
    adaptive_requested = bool(enforcement.get("adaptive_scan_required"))

    if (
        adaptive_requested or (not cadence_passed and setup_missed) or midweek_no_setups
    ) and blocked_set.isdisjoint(hard_blockers):
        adaptive_profile = enforcement.get("adaptive_scan_profile", {})
        if not isinstance(adaptive_profile, dict):
            adaptive_profile = {}
        target_delta = float(adaptive_profile.get("target_delta", ADAPTIVE_TARGET_DELTA))
        min_dte = int(adaptive_profile.get("min_dte", ADAPTIVE_MIN_DTE))
        max_dte = int(adaptive_profile.get("max_dte", BASE_MAX_DTE))
        allow_vix_override = bool(adaptive_profile.get("allow_vix_override", True))
        reason = str(
            adaptive_profile.get("reason")
            or "Cadence miss with no hard-risk blocker; enabling adaptive scan profile."
        )
        if midweek_no_setups:
            reason = (
                f"{reason} Midweek no-setup fallback active (weekday={et_now.weekday()}, "
                f"qualified_setups={setups_observed})."
            )
        return {
            "mode": "adaptive",
            "target_delta": target_delta,
            "min_dte": min_dte,
            "max_dte": max_dte,
            "target_dte": TARGET_DTE,
            "allow_vix_override": allow_vix_override,
            "reason": reason,
        }

    return base


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
        logger.info(f"Open IC positions: {ic_count} (max: {MAX_POSITIONS})")
        return ic_count
    except Exception as e:
        logger.error(f"Could not count positions: {e}")
        return 0


def find_expiration_date(
    *, min_dte: int = BASE_MIN_DTE, max_dte: int = BASE_MAX_DTE, target_dte: int = TARGET_DTE
) -> str:
    """Find optimal expiration date in a target DTE band, anchored to Friday."""
    et = ZoneInfo("America/New_York")
    today = datetime.now(et)

    target_date = today + timedelta(days=target_dte)

    # Find next Friday
    days_until_friday = (4 - target_date.weekday()) % 7
    if days_until_friday == 0 and target_date.weekday() != 4:
        days_until_friday = 7

    expiry = target_date + timedelta(days=days_until_friday)
    dte = (expiry - today).days

    # Ensure DTE stays inside configured bounds
    if dte < min_dte:
        expiry += timedelta(days=7)
        dte = (expiry - today).days
    elif dte > max_dte:
        expiry -= timedelta(days=7)
        dte = (expiry - today).days

    expiry_str = expiry.strftime("%Y-%m-%d")
    logger.info(f"Target expiration: {expiry_str} ({dte} DTE)")
    return expiry_str


def _delta_to_otm_pct(target_delta: float) -> float:
    # Approximation for selecting OTM distance: lower delta -> wider distance.
    if target_delta <= 0.16:
        return 0.05
    if target_delta <= 0.18:
        return 0.045
    return 0.04


def calculate_strikes(spy_price: float, *, target_delta: float = BASE_TARGET_DELTA) -> dict:
    """Calculate iron condor strikes based on target delta approximation."""
    # Round to nearest $5 increment (SPY options)

    def round_to_5(x: float) -> float:
        return round(x / 5) * 5

    otm_pct = _delta_to_otm_pct(target_delta)

    short_put = round_to_5(spy_price * (1.0 - otm_pct))
    long_put = short_put - WING_WIDTH

    short_call = round_to_5(spy_price * (1.0 + otm_pct))
    long_call = short_call + WING_WIDTH

    return {
        "short_put": short_put,
        "long_put": long_put,
        "short_call": short_call,
        "long_call": long_call,
    }


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
| **Current Positions** | {opportunity["positions"]}/{MAX_POSITIONS} |
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


def scan_for_opportunity(dry_run: bool = False, adaptive: bool | None = None) -> dict | None:
    """Main scanner function - find IC opportunity and alert."""
    logger.info("=" * 60)
    logger.info("IRON CONDOR SCANNER - Starting scan")
    logger.info("=" * 60)

    if adaptive is None:
        scan_profile = load_scan_profile()
    elif adaptive:
        scan_profile = {
            "mode": "adaptive",
            "target_delta": ADAPTIVE_TARGET_DELTA,
            "min_dte": ADAPTIVE_MIN_DTE,
            "max_dte": BASE_MAX_DTE,
            "target_dte": TARGET_DTE,
            "allow_vix_override": True,
            "reason": "Forced adaptive scan mode.",
        }
    else:
        scan_profile = {
            "mode": "baseline",
            "target_delta": BASE_TARGET_DELTA,
            "min_dte": BASE_MIN_DTE,
            "max_dte": BASE_MAX_DTE,
            "target_dte": TARGET_DTE,
            "allow_vix_override": False,
            "reason": "Forced baseline scan mode.",
        }

    logger.info(
        "Scan profile: %s | delta=%.2f | dte=%s-%s | vix_override=%s",
        scan_profile["mode"],
        float(scan_profile["target_delta"]),
        int(scan_profile["min_dte"]),
        int(scan_profile["max_dte"]),
        bool(scan_profile["allow_vix_override"]),
    )
    logger.info("Scan profile reason: %s", scan_profile["reason"])

    # Get clients
    trading_client, stock_client, options_client = get_alpaca_clients()
    if not trading_client:
        logger.error("Failed to initialize Alpaca clients")
        return None

    # Check position limit
    open_positions = count_open_ic_positions(trading_client)
    if open_positions >= MAX_POSITIONS:
        logger.info(f"Position limit reached ({open_positions}/{MAX_POSITIONS}) - no scan needed")
        return None

    # Get market data
    spy_price = get_spy_price(stock_client)
    equity = get_account_equity(trading_client)

    # Check VIX conditions
    vix_ok, vix_status = check_vix_conditions()
    vix_override_applied = False
    if not vix_ok:
        if scan_profile["allow_vix_override"]:
            vix_override_applied = True
            logger.warning("VIX conditions unfavorable, but override enabled: %s", vix_status)
        else:
            logger.warning(f"VIX conditions unfavorable: {vix_status}")
            return None

    # Calculate opportunity
    expiry = find_expiration_date(
        min_dte=int(scan_profile["min_dte"]),
        max_dte=int(scan_profile["max_dte"]),
        target_dte=int(scan_profile["target_dte"]),
    )
    dte = (datetime.strptime(expiry, "%Y-%m-%d") - datetime.now()).days
    strikes = calculate_strikes(spy_price, target_delta=float(scan_profile["target_delta"]))
    pricing = estimate_credit(strikes)
    max_risk_allowed = equity * POSITION_SIZE_PCT
    if pricing["max_risk"] > max_risk_allowed:
        logger.warning(
            "Rejected by risk cap: max risk %.2f exceeds allowed %.2f (5%% of equity).",
            pricing["max_risk"],
            max_risk_allowed,
        )
        return None

    opportunity = {
        "timestamp": datetime.utcnow().isoformat(),
        "spy_price": spy_price,
        "expiry": expiry,
        "dte": dte,
        "strikes": strikes,
        "pricing": pricing,
        "equity": equity,
        "positions": open_positions,
        "vix_status": (
            f"{vix_status} (override for cadence recovery)" if vix_override_applied else vix_status
        ),
        "scan_profile": scan_profile,
        "risk_guard": {
            "max_risk_allowed": max_risk_allowed,
            "max_risk_ok": pricing["max_risk"] <= max_risk_allowed,
        },
        "adaptive_applied": scan_profile["mode"] == "adaptive",
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
    parser.add_argument(
        "--adaptive",
        action="store_true",
        help="Force adaptive scan profile (relaxed non-critical filters).",
    )
    parser.add_argument(
        "--no-adaptive",
        action="store_true",
        help="Force baseline scan profile.",
    )
    args = parser.parse_args()

    adaptive: bool | None = None
    if args.adaptive and args.no_adaptive:
        parser.error("Use either --adaptive or --no-adaptive, not both.")
    if args.adaptive:
        adaptive = True
    elif args.no_adaptive:
        adaptive = False

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

    result = scan_for_opportunity(dry_run=args.dry_run, adaptive=adaptive)

    if result:
        print(json.dumps(result, indent=2, default=str))
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main() or 0)
