"""Options strategy coordination extracted from TradingOrchestrator.

The active repo mandate is a narrow SPY options path. Legacy Rule One and
multi-ticker IV-driven execution remain de-scoped from active operation.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.execution.alpaca_executor import AlpacaExecutor
    from src.orchestrator.telemetry import OrchestratorTelemetry
    from src.risk.options_risk_monitor import OptionsRiskMonitor

logger = logging.getLogger(__name__)


class OptionsStrategyCoordinator:
    """Coordinates options strategy execution and risk management.

    Responsibilities:
    - Run Phil Town Rule #1 options (CSPs, covered calls)
    - Run IV-aware options execution pipeline
    - Monitor options positions for risk (stop-losses, delta)

    This class is injected into TradingOrchestrator to reduce its complexity.
    """

    def __init__(
        self,
        *,
        executor: AlpacaExecutor,
        options_risk_monitor: OptionsRiskMonitor,
        telemetry: OrchestratorTelemetry,
        paper: bool = True,
    ) -> None:
        self.executor = executor
        self.options_risk_monitor = options_risk_monitor
        self.telemetry = telemetry
        self.paper = paper

    def run_options_risk_check(self, option_prices: dict | None = None) -> dict:
        """Run options position risk check (stop-losses and delta management).

        McMillan Rules Applied:
        - Credit spreads/iron condors: Exit at 1.0x credit loss threshold
        - Long options: Exit at 50% loss
        - Delta: Rebalance if |net delta| > 60

        Args:
            option_prices: Dict mapping option symbols to current prices.
                          If None, will attempt to fetch from executor.

        Returns:
            Risk check results with any actions taken.
        """
        logger.info("--- Running Options Risk Check ---")

        if option_prices is None:
            option_prices = {}

        try:
            results = self.options_risk_monitor.run_risk_check(
                current_prices=option_prices, executor=self.executor
            )

            self.telemetry.record(
                event_type="options.risk_check",
                ticker="PORTFOLIO",
                status="completed",
                payload={
                    "positions_checked": results.get("positions_checked", 0),
                    "stop_loss_exits": len(results.get("stop_loss_exits", [])),
                    "rebalance_needed": results.get("delta_analysis", {}).get(
                        "rebalance_needed", False
                    ),
                },
            )

            return results

        except Exception as e:
            logger.error("Options risk check failed: %s", e)
            return {"error": str(e)}

    def run_options_strategy(self) -> dict:
        """Legacy Rule One gate kept as an explicit no-op."""
        results = {
            "action": "archived",
            "reason": "Rule One / cash-secured-put path removed from active operating scope.",
            "active_path": "scripts/iron_condor_trader.py",
        }
        logger.info("--- Gate 6 archived: Rule One options path disabled ---")
        self.telemetry.record(
            event_type="gate.options",
            ticker="PORTFOLIO",
            status="archived",
            payload=results,
        )
        return results

    def run_iv_options_execution(self) -> dict:
        """Legacy multi-ticker IV path kept as an explicit no-op."""
        results = {
            "action": "archived",
            "reason": "IV-aware multi-ticker execution removed from active operating scope.",
            "active_path": "scripts/iron_condor_trader.py",
        }
        logger.info("--- Gate 7 archived: multi-ticker IV execution disabled ---")
        self.telemetry.record(
            event_type="gate.iv_options",
            ticker="PORTFOLIO",
            status="archived",
            payload=results,
        )
        return results
