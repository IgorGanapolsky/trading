"""
Macro Risk Guard - Tier 0 Safety Gate
Monitors macro-economic and geopolitical indicators (Oil, Treasury Yields)
to prevent trading during 'Black Swan' regime shifts.
Inspired by CNBC/PwC: 'Investors becoming more cautious on U.S. allocations'.
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class MacroRiskGuard:
    """
    Tier 0 Safety Gate that halts trading if macro-geopolitical risk spikes.
    """

    # Thresholds for 'Black Swan' alerts
    CRUDE_OIL_SPIKE_THRESHOLD: float = 0.08  # 8% move
    TREASURY_YIELD_SPIKE_THRESHOLD: float = 0.05  # 5% move in TNX
    OIL_CRISIS_PRICE: float = 100.0

    def __init__(
        self,
        data_client: Optional[Any] = None,
        *,
        intel_path: Path | str | None = None,
        intel_max_age_minutes: int = 240,
    ):
        """
        Args:
            data_client: Alpaca StockHistoricalDataClient instance
        """
        self.data_client = data_client
        self.intel_path = (
            Path(intel_path)
            if intel_path is not None
            else Path(__file__).resolve().parents[2]
            / "data"
            / "analysis"
            / "perplexity"
            / "trading_intel_latest.json"
        )
        self.intel_max_age_minutes = intel_max_age_minutes

    def check_macro_vitals(self, macro_data: dict[str, Any]) -> tuple[bool, str]:
        """
        Evaluates macro vitals. Returns (True, "") if safe, (False, reason) if blocked.
        """
        # 1. Check Geopolitical Oil Shock (CNBC/PwC takeaway #4)
        oil_change = macro_data.get("oil_change", 0.0)
        oil_price = macro_data.get("oil_price", 0.0)

        if abs(oil_change) > self.CRUDE_OIL_SPIKE_THRESHOLD or oil_price >= self.OIL_CRISIS_PRICE:
            reason = f"GEOPOLITICAL HALT: Oil volatility ({oil_change * 100:+.1f}%) or price (${oil_price:.2f})."
            logger.critical(f"🚨 {reason}")
            return False, reason

        # 2. Check Fiscal Deficit / Treasury Yields (CNBC/PwC takeaway #1)
        yield_change = macro_data.get("yield_change", 0.0)
        if abs(yield_change) > self.TREASURY_YIELD_SPIKE_THRESHOLD:
            reason = f"FISCAL RISK HALT: Treasury Yield volatility ({yield_change * 100:+.1f}%)."
            logger.critical(f"🚨 {reason}")
            return False, reason

        # 3. Check fresh Perplexity event/regime intelligence.
        intel_safe, intel_reason = self.check_perplexity_event_risk()
        if not intel_safe:
            logger.critical("Perplexity event risk halt: %s", intel_reason)
            return False, intel_reason

        logger.info("✅ Macro vitals within normal parameters.")
        return True, ""

    def check_perplexity_event_risk(self) -> tuple[bool, str]:
        """Block only when a fresh Perplexity artifact explicitly flags high event risk."""

        try:
            payload = json.loads(self.intel_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return True, ""
        except Exception as exc:
            logger.warning("Failed to read Perplexity trading intel: %s", exc)
            return True, ""

        generated_raw = payload.get("generated_at_utc")
        if not generated_raw:
            return True, ""

        try:
            generated_at = datetime.fromisoformat(str(generated_raw).replace("Z", "+00:00"))
        except ValueError:
            logger.warning("Invalid Perplexity intel timestamp: %s", generated_raw)
            return True, ""

        age_minutes = (datetime.now(timezone.utc) - generated_at).total_seconds() / 60
        if age_minutes > self.intel_max_age_minutes:
            logger.info("Ignoring stale Perplexity intel age %.1f minutes", age_minutes)
            return True, ""

        recommendation = str(payload.get("recommendation") or "").upper()
        risk_score = float(payload.get("risk_score") or 0.0)
        gate_contract = payload.get("gate_contract")
        gate_contract = gate_contract if isinstance(gate_contract, dict) else {}
        blocks = bool(gate_contract.get("blocks_new_iron_condors"))
        if blocks or recommendation == "BLOCK_NEW_IC" or risk_score >= 0.70:
            reason = gate_contract.get("reason") or (
                f"Perplexity event/regime risk score {risk_score:.2f} blocks new entries."
            )
            return False, f"PERPLEXITY EVENT RISK HALT: {reason}"

        return True, ""

    def get_macro_snapshot(self) -> dict[str, Any]:
        """
        Autonomously fetches real-time USO and TNX data if client is available.
        Otherwise falls back to conservative defaults.
        """
        if not self.data_client:
            logger.warning("No data client provided to MacroRiskGuard - using baseline vitals.")
            return {"oil_price": 75.0, "oil_change": 0.0, "yield_change": 0.0}

        try:
            from alpaca.data.requests import StockBarsRequest
            from alpaca.data.timeframe import TimeFrame

            # USO acts as our Crude Oil proxy for the Alpha Engine
            # TNX acts as our 10-Year Treasury Yield proxy
            symbols = ["USO", "TNX"]

            # Fetch latest bars to calculate change
            end = datetime.now(timezone.utc)
            start = end - timedelta(days=2)

            request_params = StockBarsRequest(
                symbol_or_symbols=symbols, timeframe=TimeFrame.Day, start=start
            )

            bars = self.data_client.get_stock_bars(request_params)

            snapshot = {"oil_price": 0.0, "oil_change": 0.0, "yield_change": 0.0}

            if "USO" in bars.data and len(bars.data["USO"]) >= 2:
                b = bars.data["USO"]
                current = b[-1].close
                prev = b[-2].close
                snapshot["oil_price"] = current
                snapshot["oil_change"] = (current - prev) / prev

            if "TNX" in bars.data and len(bars.data["TNX"]) >= 2:
                b = bars.data["TNX"]
                snapshot["yield_change"] = (b[-1].close - b[-2].close) / b[-2].close

            return snapshot

        except Exception as e:
            logger.error(f"Failed to fetch autonomous macro snapshot: {e}")
            return {"oil_price": 0.0, "oil_change": 0.0, "yield_change": 0.0}
