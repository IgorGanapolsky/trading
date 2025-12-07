#!/usr/bin/env python3
"""
TLT Momentum Gate Monitor

Monitors TLT (Treasuries) momentum gate status and alerts when gate opens/closes.
This helps track when Treasuries trading will resume.

The momentum gate is OPEN when SMA20 >= SMA50 (uptrend).
The momentum gate is CLOSED when SMA20 < SMA50 (downtrend).
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv

load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# State file to track gate status changes
STATE_FILE = Path("data") / "tlt_gate_state.json"


def get_tlt_momentum_status() -> tuple[bool, dict]:
    """
    Check TLT momentum gate status.

    Returns:
        Tuple of (gate_is_open: bool, status_dict: Dict)
    """
    try:
        import yfinance as yf

        tlt = yf.Ticker("TLT")
        hist = tlt.history(period="6mo")

        if hist.empty or "Close" not in hist.columns:
            logger.warning("TLT historical data unavailable")
            return False, {"error": "Insufficient data"}

        current_price = float(hist["Close"].iloc[-1])
        sma20 = float(hist["Close"].rolling(20).mean().iloc[-1])
        sma50 = float(hist["Close"].rolling(50).mean().iloc[-1])
        gate_open = sma20 >= sma50

        # Calculate 3-month return if enough data
        ret3m = None
        if len(hist) >= 63:
            ret3m = ((current_price / float(hist["Close"].iloc[-63])) - 1.0) * 100.0

        status = {
            "symbol": "TLT",
            "current_price": current_price,
            "sma20": sma20,
            "sma50": sma50,
            "gate_open": gate_open,
            "gate_status": "OPEN" if gate_open else "CLOSED",
            "ret3m_pct": ret3m,
            "timestamp": datetime.now().isoformat(),
        }

        return gate_open, status

    except ImportError:
        logger.error("yfinance not installed")
        return False, {"error": "yfinance not available"}
    except Exception as e:
        logger.error(f"Error checking TLT momentum: {e}", exc_info=True)
        return False, {"error": str(e)}


def load_gate_state() -> dict:
    """Load previous gate state from file."""
    if not STATE_FILE.exists():
        return {}

    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Error loading gate state: {e}")
        return {}


def save_gate_state(state: dict) -> None:
    """Save gate state to file."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving gate state: {e}")


def check_tlt_gate_change() -> dict | None:
    """
    Check if TLT gate status has changed and return alert info if so.

    Returns:
        Alert dict if status changed, None otherwise
    """
    gate_open, current_status = get_tlt_momentum_status()

    if "error" in current_status:
        logger.warning(f"Could not check TLT status: {current_status['error']}")
        return None

    previous_state = load_gate_state()
    previous_gate_open = previous_state.get("gate_open")

    # First run - just save state
    if previous_gate_open is None:
        save_gate_state(current_status)
        logger.info(
            f"TLT gate status initialized: {current_status['gate_status']} "
            f"(SMA20=${current_status['sma20']:.2f}, SMA50=${current_status['sma50']:.2f})"
        )
        return None

    # Check if status changed
    if previous_gate_open != gate_open:
        save_gate_state(current_status)

        alert = {
            "type": "gate_status_change",
            "previous_status": "OPEN" if previous_gate_open else "CLOSED",
            "current_status": current_status["gate_status"],
            "gate_opened": gate_open,
            "details": current_status,
            "timestamp": datetime.now().isoformat(),
        }

        logger.info(
            f"🚨 TLT GATE STATUS CHANGED: {alert['previous_status']} → {alert['current_status']}"
        )
        return alert

    # Status unchanged - update timestamp
    current_status["last_check"] = datetime.now().isoformat()
    save_gate_state(current_status)

    return None


def get_tlt_status_report() -> str:
    """
    Generate a formatted status report for TLT momentum gate.

    Returns:
        Formatted report string
    """
    gate_open, status = get_tlt_momentum_status()

    if "error" in status:
        return f"❌ TLT Status Check Failed: {status['error']}"

    emoji = "🟢" if gate_open else "🔴"
    gate_text = "OPEN" if gate_open else "CLOSED"
    action_text = "✅ Will execute $90/day" if gate_open else "⏸️  Trading paused"

    report = f"""
{emoji} *TLT Momentum Gate: {gate_text}*

*Current Status:*
• Price: ${status["current_price"]:.2f}
• SMA20: ${status["sma20"]:.2f}
• SMA50: ${status["sma50"]:.2f}
• Gate: {gate_text} (SMA20 {">=" if gate_open else "<"} SMA50)

*Allocation:*
• Daily Investment: $1,500
• Tier 1 (60%): $900
• Treasury Allocation (10%): $90/day
• Threshold: $0.50 ✅

*Action:* {action_text}

*Performance:*
• 3-Month Return: {status["ret3m_pct"]:.2f}%{" ✅" if status["ret3m_pct"] and status["ret3m_pct"] > 0 else "" if status["ret3m_pct"] else " (N/A)"}

*Last Check:* {datetime.now().strftime("%Y-%m-%d %H:%M:%S ET")}
"""

    return report.strip()


def main():
    """Main monitoring function."""
    print("=" * 80)
    print("TLT MOMENTUM GATE MONITOR")
    print(f"Check Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S ET')}")
    print("=" * 80)
    print()

    # Check for status change
    alert = check_tlt_gate_change()

    # Generate status report
    report = get_tlt_status_report()
    print(report)
    print()

    # If status changed, send alert
    if alert:
        print("🚨 GATE STATUS CHANGE DETECTED!")
        print(f"   Previous: {alert['previous_status']}")
        print(f"   Current:  {alert['current_status']}")
        print()

        # Try to send Telegram alert
        try:
            from src.alerts.telegram_alerter import TelegramAlerter

            alerter = TelegramAlerter()
            if alerter.enabled:
                message = f"""
*TLT MOMENTUM GATE {"OPENED" if alert["gate_opened"] else "CLOSED"}*

Treasuries trading is now {"ENABLED" if alert["gate_opened"] else "PAUSED"}.

*Details:*
• Previous Status: {alert["previous_status"]}
• Current Status: {alert["current_status"]}
• Current Price: ${alert["details"]["current_price"]:.2f}
• SMA20: ${alert["details"]["sma20"]:.2f}
• SMA50: ${alert["details"]["sma50"]:.2f}

*Impact:*
{"✅ System will now allocate $90/day to TLT" if alert["gate_opened"] else "⏸️  System will skip TLT orders until gate opens"}

*Next Check:* Daily at market open
"""
                alerter.send_alert(
                    message.strip(),
                    level="INFO" if alert["gate_opened"] else "WARNING",
                )
                print("✅ Telegram alert sent")
            else:
                print("⚠️  Telegram alerts not configured")
        except Exception as e:
            logger.warning(f"Could not send Telegram alert: {e}")

    print("=" * 80)

    # Return exit code based on gate status
    gate_open, _ = get_tlt_momentum_status()
    return 0 if gate_open else 1  # Exit 0 = gate open, 1 = gate closed


if __name__ == "__main__":
    sys.exit(main())
