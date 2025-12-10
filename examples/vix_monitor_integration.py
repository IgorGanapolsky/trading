"""
VIX Monitor Integration Example

Demonstrates how to integrate VIX monitoring with the options trading system.

This example shows:
1. Daily VIX regime check before trading
2. VIX-based strategy selection
3. Position sizing adjustments based on volatility
4. Integration with OptionsExecutor
5. State export to system_state.json

Author: Claude (CTO)
Created: 2025-12-10
"""

import json
import logging
from datetime import datetime
from pathlib import Path

from src.options.vix_monitor import VIXMonitor, VIXSignals, VolatilityRegime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class VIXIntegratedTrading:
    """
    Trading system with VIX-based regime detection and strategy selection.
    """

    def __init__(self, paper: bool = True):
        """
        Initialize VIX-integrated trading system.

        Args:
            paper: If True, use paper trading
        """
        self.paper = paper
        self.monitor = VIXMonitor(use_alpaca=True)
        self.signals = VIXSignals(self.monitor)

        logger.info(f"VIX-Integrated Trading System initialized (Paper: {paper})")

    def run_daily_vix_check(self) -> dict:
        """
        Run daily VIX analysis before trading.

        Returns:
            Dict with VIX metrics and trading recommendations
        """
        logger.info("=== DAILY VIX CHECK ===")

        # 1. Get current VIX metrics
        try:
            current_vix = self.monitor.get_current_vix()
            regime = self.monitor.get_volatility_regime(current_vix)
            percentile = self.monitor.get_vix_percentile()
            term_state = self.monitor.get_term_structure_state()

            logger.info(f"Current VIX: {current_vix:.2f}")
            logger.info(f"Volatility Regime: {regime.value.upper()}")
            logger.info(f"VIX Percentile: {percentile:.1f}%")
            logger.info(f"Term Structure: {term_state.value.upper()}")

        except Exception as e:
            logger.error(f"Failed to fetch VIX data: {e}")
            return {
                "success": False,
                "error": str(e),
                "recommendation": "WAIT - Unable to assess VIX regime"
            }

        # 2. Check for VIX spikes (danger zone)
        spike_info = self.monitor.detect_vix_spike()
        if spike_info["is_spike"]:
            logger.warning(
                f"⚠️ VIX SPIKE DETECTED! "
                f"Severity: {spike_info['severity'].upper()}, "
                f"Z-Score: {spike_info['z_score']:.2f}"
            )

            # During spikes, recommend caution
            if spike_info["severity"] in ["severe", "extreme"]:
                logger.warning("🛑 SEVERE VIX SPIKE - HALT TRADING")
                return {
                    "success": True,
                    "vix": current_vix,
                    "regime": regime.value,
                    "spike_detected": True,
                    "recommendation": "HALT - Wait for VIX stabilization",
                    "action": "WAIT"
                }

        # 3. Get trading signals
        sell_signal = self.signals.should_sell_premium()
        buy_signal = self.signals.should_buy_premium()
        position_size = self.signals.get_position_size_multiplier()
        recommendation = self.signals.get_strategy_recommendation()

        # 4. Build trading plan
        trading_plan = {
            "success": True,
            "timestamp": datetime.now().isoformat(),
            "vix_metrics": {
                "current_vix": current_vix,
                "regime": regime.value,
                "percentile": percentile,
                "term_structure": term_state.value,
            },
            "spike_detected": spike_info["is_spike"],
            "spike_severity": spike_info["severity"],
            "primary_action": recommendation["primary_action"],
            "position_size_multiplier": position_size["multiplier"],
            "risk_level": recommendation["risk_level"],
            "signals": {
                "sell_premium": sell_signal["should_sell_premium"],
                "sell_confidence": sell_signal["confidence"],
                "buy_premium": buy_signal["should_buy_premium"],
                "buy_confidence": buy_signal["confidence"],
            },
            "recommended_strategies": recommendation["recommended_strategies"],
            "entry_rules": recommendation["entry_rules"],
            "exit_rules": recommendation["exit_rules"],
        }

        # 5. Log recommendations
        self._log_recommendations(trading_plan)

        return trading_plan

    def _log_recommendations(self, plan: dict) -> None:
        """Log trading recommendations"""
        logger.info("\n" + "="*80)
        logger.info("TRADING RECOMMENDATIONS")
        logger.info("="*80)

        logger.info(f"Primary Action: {plan['primary_action']}")
        logger.info(f"Risk Level: {plan['risk_level']}")
        logger.info(f"Position Size: {plan['position_size_multiplier']:.2f}x normal")

        if plan['spike_detected']:
            logger.warning(f"⚠️ VIX Spike Detected: {plan['spike_severity'].upper()}")

        logger.info("\nRecommended Strategies:")
        for strat in plan['recommended_strategies']:
            logger.info(
                f"  [{strat['priority']}] {strat['action']}: {strat['strategy']}"
            )

        logger.info("\nEntry Rules:")
        for rule in plan['entry_rules']:
            logger.info(f"  - {rule}")

        logger.info("\nExit Rules:")
        for rule in plan['exit_rules']:
            logger.info(f"  - {rule}")

        logger.info("="*80 + "\n")

    def execute_vix_based_strategy(self, ticker: str = "SPY") -> dict:
        """
        Execute options strategy based on current VIX regime.

        Args:
            ticker: Underlying symbol to trade

        Returns:
            Dict with execution results
        """
        # Get VIX-based trading plan
        plan = self.run_daily_vix_check()

        if not plan["success"]:
            return plan

        if plan["primary_action"] == "WAIT":
            logger.info("⏸️ Waiting for better VIX conditions")
            return plan

        # Import executor only when needed (may not be available in all environments)
        try:
            from src.trading.options_executor import OptionsExecutor
            executor = OptionsExecutor(paper=self.paper)
        except ImportError:
            logger.warning("OptionsExecutor not available - simulation mode")
            return {
                **plan,
                "execution_status": "SIMULATED",
                "message": "OptionsExecutor not available"
            }

        # Execute based on primary action
        execution_results = []

        try:
            if plan["primary_action"] == "SELL_PREMIUM":
                logger.info("Executing PREMIUM SELLING strategy...")

                # Adjust parameters based on VIX regime
                regime = plan["vix_metrics"]["regime"]

                if regime in ["high", "extreme"]:
                    # High VIX: Tighter stops, further OTM, shorter DTE
                    width = 5.0
                    target_delta = 0.16  # ~84% P.OTM
                    dte = 30

                elif regime == "elevated":
                    # Elevated VIX: Standard parameters
                    width = 5.0
                    target_delta = 0.20  # ~80% P.OTM
                    dte = 35

                else:
                    # Normal/Low VIX: Can be more aggressive
                    width = 5.0
                    target_delta = 0.25  # ~75% P.OTM
                    dte = 45

                # Execute iron condor (best premium selling strategy)
                result = executor.execute_iron_condor(
                    ticker=ticker,
                    width=width,
                    target_delta=target_delta,
                    dte=dte
                )

                execution_results.append({
                    "strategy": "iron_condor",
                    "result": result
                })

            elif plan["primary_action"] == "BUY_PREMIUM":
                logger.info("Executing PREMIUM BUYING strategy...")

                # Low VIX: Buy debit spreads or long options
                result = executor.execute_credit_spread(
                    ticker=ticker,
                    spread_type="bull_put",  # Structured as debit
                    width=10.0,  # Wider spreads for better R/R
                    target_delta=0.40,  # More ITM for vol expansion
                    dte=60  # Longer time for vol to expand
                )

                execution_results.append({
                    "strategy": "bull_put_spread",
                    "result": result
                })

            return {
                **plan,
                "execution_status": "SUCCESS",
                "executions": execution_results
            }

        except Exception as e:
            logger.error(f"Execution failed: {e}")
            return {
                **plan,
                "execution_status": "FAILED",
                "error": str(e)
            }

    def export_vix_state_to_system(self) -> None:
        """
        Export VIX state to system_state.json for integration with main trading system.
        """
        try:
            # Get VIX state
            vix_state = self.monitor.export_state()

            # Load system state
            system_state_file = Path("data/system_state.json")

            if system_state_file.exists():
                with open(system_state_file, 'r') as f:
                    system_state = json.load(f)
            else:
                system_state = {}

            # Update with VIX state
            system_state["vix_monitor"] = vix_state

            # Save
            with open(system_state_file, 'w') as f:
                json.dump(system_state, f, indent=2)

            logger.info(f"✅ VIX state exported to {system_state_file}")

        except Exception as e:
            logger.error(f"Failed to export VIX state: {e}")


def main():
    """
    Example usage of VIX-integrated trading system.
    """
    print("\n" + "="*80)
    print("VIX-INTEGRATED OPTIONS TRADING SYSTEM")
    print("="*80 + "\n")

    # Initialize system
    trading_system = VIXIntegratedTrading(paper=True)

    # 1. Run daily VIX check
    print("\n--- Daily VIX Check ---\n")
    plan = trading_system.run_daily_vix_check()

    if plan["success"]:
        print(f"\n✅ VIX Analysis Complete")
        print(f"Recommendation: {plan['primary_action']}")
        print(f"Position Size: {plan['position_size_multiplier']:.2f}x")
    else:
        print(f"\n❌ VIX Analysis Failed: {plan.get('error')}")
        return

    # 2. Execute strategy (if appropriate)
    if plan["primary_action"] != "WAIT":
        print("\n--- Executing VIX-Based Strategy ---\n")
        result = trading_system.execute_vix_based_strategy(ticker="SPY")

        if result.get("execution_status") == "SUCCESS":
            print("\n✅ Strategy Executed Successfully")
            for execution in result.get("executions", []):
                print(f"  - {execution['strategy']}: {execution['result']['status']}")
        else:
            print(f"\n⚠️ Execution Status: {result.get('execution_status')}")

    # 3. Export state
    print("\n--- Exporting VIX State ---\n")
    trading_system.export_vix_state_to_system()

    print("\n" + "="*80)
    print("VIX-INTEGRATED TRADING COMPLETE")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()
