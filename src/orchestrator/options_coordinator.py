"""Options strategy coordination extracted from TradingOrchestrator.

This module handles:
- Gate 6: Phil Town Rule #1 Options Strategy
- Gate 7: IV-Aware Options Execution
- Options risk monitoring and stop-loss management

Extracted Jan 10, 2026 per ArjanCodes clean architecture principles.
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any

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
        - Credit spreads/iron condors: Exit at 2.2x credit received
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
        """Gate 6: Phil Town Rule #1 Options Strategy.

        Implements both Rule #1 options strategies:
        1. "Getting Paid to Wait" - Cash-secured puts at MOS price
           - Uses CASH to secure puts (no shares needed)
           - If assigned: Own stock at 50% discount to fair value
           - If not: Keep premium as profit

        2. "Getting Paid to Sell" - Covered calls at Sticker Price
           - Requires 100+ shares (skipped if not available)

        Returns:
            Dict with options strategy execution results.
        """
        from src.strategies.rule_one_options import RuleOneOptionsStrategy

        logger.info("--- Gate 6: Phil Town Rule #1 Options Strategy ---")

        # Check if theta automation is enabled
        theta_enabled = os.getenv("ENABLE_THETA_AUTOMATION", "true").lower() in (
            "true",
            "1",
            "yes",
        )

        if not theta_enabled:
            logger.info("Gate 6: Options disabled (set ENABLE_THETA_AUTOMATION=true to enable)")
            return {"action": "disabled", "reason": "ENABLE_THETA_AUTOMATION not set"}

        logger.info("Gate 6: Theta automation ENABLED - executing options strategy")

        # FIXED Jan 9, 2026: Renamed counters to be HONEST
        # This function LOGS signals; actual EXECUTION happens in rule_one_trader.py
        results: dict[str, Any] = {
            "put_signals": 0,
            "call_signals": 0,
            "puts_logged": 0,
            "calls_logged": 0,
            "est_total_premium": 0.0,
            "errors": [],
            "note": "Signals logged here; execution in rule_one_trader.py",
        }

        try:
            options_strategy = RuleOneOptionsStrategy(paper=True)
            signals = options_strategy.generate_daily_signals()
            put_signals = signals.get("puts", [])
            call_signals = signals.get("calls", [])

            results["put_signals"] = len(put_signals)
            results["call_signals"] = len(call_signals)

            logger.info(
                "Gate 6: Found %d put opportunities, %d call opportunities",
                len(put_signals),
                len(call_signals),
            )

            for signal in put_signals[:3]:
                logger.info(
                    "Gate 6 PUT SIGNAL: %s - Strike $%.2f, Premium $%.2f, "
                    "Annualized %.1f%%, Contracts %d",
                    signal.symbol,
                    signal.strike,
                    signal.premium,
                    signal.annualized_return * 100,
                    signal.contracts,
                )
                self.telemetry.record(
                    event_type="gate.options",
                    ticker=signal.symbol,
                    status="put_signal",
                    payload={
                        "strategy": "cash_secured_put",
                        "strike": signal.strike,
                        "premium": signal.premium,
                        "expiration": signal.expiration,
                        "annualized_return": signal.annualized_return,
                        "contracts": signal.contracts,
                        "total_premium": signal.total_premium,
                        "rationale": signal.rationale,
                    },
                )
                results["puts_logged"] = results.get("puts_logged", 0) + 1
                results["est_total_premium"] = (
                    results.get("est_total_premium", 0) + signal.total_premium
                )

            for signal in call_signals[:3]:
                logger.info(
                    "Gate 6 CALL SIGNAL: %s - Strike $%.2f, Premium $%.2f, "
                    "Annualized %.1f%%, Contracts %d",
                    signal.symbol,
                    signal.strike,
                    signal.premium,
                    signal.annualized_return * 100,
                    signal.contracts,
                )
                self.telemetry.record(
                    event_type="gate.options",
                    ticker=signal.symbol,
                    status="call_signal",
                    payload={
                        "strategy": "covered_call",
                        "strike": signal.strike,
                        "premium": signal.premium,
                        "expiration": signal.expiration,
                        "annualized_return": signal.annualized_return,
                        "contracts": signal.contracts,
                    },
                )
                results["calls_logged"] = results.get("calls_logged", 0) + 1
                results["est_total_premium"] = (
                    results.get("est_total_premium", 0) + signal.total_premium
                )

            logger.info(
                "Gate 6 Summary: %d puts, %d calls LOGGED (execution in rule_one_trader.py). "
                "Est. Premium: $%.2f",
                results.get("puts_logged", 0),
                results.get("calls_logged", 0),
                results.get("est_total_premium", 0),
            )

            self.telemetry.record(
                event_type="gate.options",
                ticker="PORTFOLIO",
                status="completed",
                payload=results,
            )

            return results

        except Exception as e:
            logger.error("Gate 6: Options strategy failed: %s", e)
            self.telemetry.record(
                event_type="gate.options",
                ticker="PORTFOLIO",
                status="error",
                payload={"error": str(e)},
            )
            return {"action": "error", "error": str(e)}

    def run_iv_options_execution(self) -> dict:
        """Gate 7: IV-Aware Options Execution Pipeline.

        Integrates:
        - OptionsIVSignalGenerator - generates IV-aware signals
        - OptionsExecutor - executes covered calls, iron condors, spreads

        Returns:
            Dict with execution results including trades placed.
        """
        from src.data.iv_data_provider import IVDataProvider

        logger.info("--- Gate 7: IV-Aware Options Execution Pipeline ---")

        iv_options_enabled = os.getenv("ENABLE_IV_OPTIONS", "true").lower() in (
            "true",
            "1",
            "yes",
        )

        if not iv_options_enabled:
            logger.info("Gate 7: IV Options disabled (set ENABLE_IV_OPTIONS=true to enable)")
            return {"action": "disabled", "reason": "ENABLE_IV_OPTIONS not set"}

        results: dict[str, Any] = {
            "signals_generated": 0,
            "trades_executed": 0,
            "total_premium": 0.0,
            "strategies": [],
            "errors": [],
        }

        try:
            from src.signals.options_iv_signal_generator import OptionsIVSignalGenerator

            signal_generator = OptionsIVSignalGenerator()
            logger.info("Gate 7: OptionsIVSignalGenerator initialized")

            from src.trading.options_executor import OptionsExecutor

            _options_executor = OptionsExecutor(paper=self.paper)  # noqa: F841
            logger.info("Gate 7: OptionsExecutor initialized (paper=%s)", self.paper)

            account_equity = self.executor.account_equity
            options_tickers = os.getenv("OPTIONS_TICKERS", "SPY,QQQ,AAPL,MSFT").split(",")
            iv_provider = IVDataProvider()

            for ticker in options_tickers:
                try:
                    ticker = ticker.strip()

                    iv_metrics = iv_provider.get_current_iv(ticker)
                    if iv_metrics:
                        iv_rank = iv_metrics.iv_rank
                        iv_percentile = iv_metrics.iv_percentile
                    else:
                        iv_rank = 50.0
                        iv_percentile = 50.0
                        logger.warning(f"IV data unavailable for {ticker}, using neutral defaults")

                    # Fetch current stock price from market data
                    stock_price = 100.0  # Default fallback
                    try:
                        from src.utils.market_data import MarketDataFetcher

                        fetcher = MarketDataFetcher()
                        res = fetcher.get_daily_bars(symbol=ticker, lookback_days=5)
                        if res.data is not None and not res.data.empty:
                            stock_price = float(res.data["Close"].iloc[-1])
                    except Exception as price_err:
                        logger.warning(f"Failed to fetch price for {ticker}: {price_err}")

                    signal = signal_generator.generate_trade_signal(
                        ticker=ticker,
                        iv_rank=iv_rank,
                        iv_percentile=iv_percentile,
                        stock_price=stock_price,
                        market_outlook="neutral",
                        portfolio_value=account_equity,
                    )

                    if signal:
                        results["signals_generated"] += 1
                        logger.info(
                            "Gate 7 SIGNAL: %s - %s (IV Rank: %.1f%%, IV Regime: %s)",
                            signal.ticker,
                            signal.strategy,
                            signal.iv_rank,
                            signal.iv_regime,
                        )

                        self.telemetry.record(
                            event_type="gate.iv_options",
                            ticker=ticker,
                            status="signal_generated",
                            payload={
                                "strategy": signal.strategy,
                                "iv_rank": signal.iv_rank,
                                "iv_regime": signal.iv_regime,
                                "expected_profit": signal.expected_profit,
                                "max_risk": signal.max_risk,
                                "probability_profit": signal.probability_profit,
                            },
                        )

                        results["strategies"].append(
                            {
                                "ticker": signal.ticker,
                                "strategy": signal.strategy,
                                "iv_regime": signal.iv_regime,
                            }
                        )

                        logger.info(
                            "Gate 7: Signal logged for %s - %s "
                            "(execution requires options approval)",
                            signal.ticker,
                            signal.strategy,
                        )

                except Exception as ticker_exc:
                    logger.warning("Gate 7: Failed to process %s: %s", ticker, ticker_exc)
                    results["errors"].append(f"{ticker}: {str(ticker_exc)}")
                    continue

            logger.info(
                "Gate 7 Summary: %d signals generated, %d executed",
                results["signals_generated"],
                results["trades_executed"],
            )

            self.telemetry.record(
                event_type="gate.iv_options",
                ticker="PORTFOLIO",
                status="completed",
                payload=results,
            )

            return results

        except ImportError as ie:
            logger.warning("Gate 7: Import failed - %s", ie)
            return {"action": "import_error", "error": str(ie)}

        except Exception as e:
            logger.error("Gate 7: IV Options execution failed: %s", e)
            self.telemetry.record(
                event_type="gate.iv_options",
                ticker="PORTFOLIO",
                status="error",
                payload={"error": str(e)},
            )
            return {"action": "error", "error": str(e)}
