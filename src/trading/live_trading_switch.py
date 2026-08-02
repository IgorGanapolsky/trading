"""Live Real Money Trading Switch & Readiness Verifier.

Monitors live Alpaca account balance and API credentials. Reports readiness
honestly: API connectivity, cash/options level, AND policy gates (kill switch).

``live_trading_active`` means the system is allowed to place *live* risk —
not merely that a funded live account exists. Cash alone never implies
"LIVE REAL MONEY TRADING ACTIVE" while paper_only / live_blocked is on.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass
from pathlib import Path

import requests
from dotenv import dotenv_values

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
LIVE_READINESS_FILE = ROOT / "data" / "audit" / "live_trading_readiness.json"
KILL_SWITCH_FILE = ROOT / "data" / "runtime" / "strategy_kill_switch.json"


@dataclass
class LiveReadinessReport:
    live_credentials_present: bool
    live_api_valid: bool
    live_cash_balance: float
    live_buying_power: float
    options_approved_level: int
    live_trading_active: bool
    status_message: str
    # Explicit policy / funding decomposition (optional for older readers)
    account_funded: bool = False
    policy_live_blocked: bool = True
    policy_block_reason: str = ""


def _load_policy_live_block() -> tuple[bool, str]:
    """Return (blocked, reason) from kill switch. Default blocked if missing/unreadable."""
    if not KILL_SWITCH_FILE.exists():
        return True, "kill_switch_missing (default deny live)"
    try:
        payload = json.loads(KILL_SWITCH_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return True, "kill_switch_unreadable (default deny live)"
    if not isinstance(payload, dict):
        return True, "kill_switch_invalid (default deny live)"

    paper_only = bool(payload.get("paper_only", True))
    live_blocked = bool(payload.get("live_blocked", True))
    if paper_only or live_blocked:
        reasons = []
        if paper_only:
            reasons.append("paper_only=true")
        if live_blocked:
            reasons.append("live_blocked=true")
        reason_txt = payload.get("reason")
        if reason_txt:
            reasons.append(str(reason_txt)[:160])
        return True, "; ".join(reasons)
    return False, ""


class LiveTradingSwitch:
    """Verifies live Alpaca brokerage readiness under policy gates."""

    def __init__(self, env_path: Path | None = None):
        self.env_path = env_path or (ROOT / ".env")

    def inspect_live_readiness(self) -> LiveReadinessReport:
        vals = {}
        if self.env_path.exists():
            vals = dotenv_values(self.env_path)

        key = (
            vals.get("ALPACA_LIVE_API_KEY")
            or vals.get("ALPACA_BROKERAGE_TRADING_API_KEY")
            or os.environ.get("ALPACA_LIVE_API_KEY")
            or os.environ.get("ALPACA_BROKERAGE_TRADING_API_KEY")
        )
        secret = (
            vals.get("ALPACA_LIVE_API_SECRET")
            or vals.get("ALPACA_BROKERAGE_TRADING_API_SECRET")
            or os.environ.get("ALPACA_LIVE_API_SECRET")
            or os.environ.get("ALPACA_BROKERAGE_TRADING_API_SECRET")
        )

        policy_blocked, policy_reason = _load_policy_live_block()

        if not key or not secret:
            report = LiveReadinessReport(
                live_credentials_present=False,
                live_api_valid=False,
                live_cash_balance=0.0,
                live_buying_power=0.0,
                options_approved_level=0,
                live_trading_active=False,
                status_message="Live Alpaca API key/secret missing in .env (ALPACA_LIVE_API_KEY)",
                account_funded=False,
                policy_live_blocked=policy_blocked,
                policy_block_reason=policy_reason,
            )
            self._save_report(report)
            return report

        # Test live API endpoint
        url = "https://api.alpaca.markets/v2/account"
        headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}

        try:
            r = requests.get(url, headers=headers, timeout=10.0)
            if r.status_code != 200:
                body = (r.text or "")[:200]
                report = LiveReadinessReport(
                    live_credentials_present=True,
                    live_api_valid=False,
                    live_cash_balance=0.0,
                    live_buying_power=0.0,
                    options_approved_level=0,
                    live_trading_active=False,
                    status_message=f"Live API returned HTTP {r.status_code}: {body}",
                    account_funded=False,
                    policy_live_blocked=policy_blocked,
                    policy_block_reason=policy_reason,
                )
                self._save_report(report)
                return report

            data = r.json()
            cash = float(data.get("cash", 0.0) or 0.0)
            bp = float(data.get("buying_power", 0.0) or 0.0)
            opt_lvl = int(data.get("options_approved_level", 0) or 0)

            account_funded = (cash > 0.0) and (opt_lvl >= 2)
            # Active only when funded AND policy allows live risk.
            live_active = account_funded and (not policy_blocked)

            if live_active:
                msg = f"LIVE REAL MONEY TRADING ACTIVE (cash=${cash:,.2f}, options_level={opt_lvl})"
            elif policy_blocked and account_funded:
                msg = (
                    f"Live account funded (cash=${cash:,.2f}, options_level={opt_lvl}) "
                    f"but LIVE RISK BLOCKED by policy: {policy_reason}"
                )
            elif policy_blocked:
                msg = (
                    f"Live API valid (cash=${cash:,.2f}) but LIVE RISK BLOCKED by policy: "
                    f"{policy_reason}"
                )
            else:
                msg = (
                    f"Live account connected but not funded for options trading "
                    f"(cash=${cash:,.2f}, options_level={opt_lvl})."
                )

            report = LiveReadinessReport(
                live_credentials_present=True,
                live_api_valid=True,
                live_cash_balance=cash,
                live_buying_power=bp,
                options_approved_level=opt_lvl,
                live_trading_active=live_active,
                status_message=msg,
                account_funded=account_funded,
                policy_live_blocked=policy_blocked,
                policy_block_reason=policy_reason,
            )
            self._save_report(report)
            return report

        except Exception as e:
            report = LiveReadinessReport(
                live_credentials_present=True,
                live_api_valid=False,
                live_cash_balance=0.0,
                live_buying_power=0.0,
                options_approved_level=0,
                live_trading_active=False,
                status_message=f"Live API connection error: {e}",
                account_funded=False,
                policy_live_blocked=policy_blocked,
                policy_block_reason=policy_reason,
            )
            self._save_report(report)
            return report

    def _save_report(self, report: LiveReadinessReport) -> None:
        LIVE_READINESS_FILE.parent.mkdir(parents=True, exist_ok=True)
        try:
            with LIVE_READINESS_FILE.open("w", encoding="utf-8") as h:
                json.dump(asdict(report), h, indent=2)
        except Exception as e:
            logger.warning("Failed to save live readiness report: %s", e)
