"""
MINIMAL VIABLE TRADING SYSTEM

Created: Dec 11, 2025
Purpose: Strip away all complexity and prove we can make money

This system has ONLY:
1. Simple SMA momentum (20/50 crossover)
2. Fixed position sizing (2% of portfolio per trade)
3. Simple stop-loss (-3%) and take-profit (+5%)
4. Basic daily loss limit (-2% circuit breaker)

NO:
- Agent frameworks (LangChain, DeepAgents, ADK, DiscoRL, SB3)
- RL filters
- LLM sentiment analysis
- Multiple sequential gates
- Complex risk management layers
- Mental toughness coaching
- Macro context adjustments

PHILOSOPHY:
- Trade more, learn faster
- Simple rules > complex ML
- Prove edge first, add complexity later
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from src.core.alpaca_trader import AlpacaTrader

logger = logging.getLogger(__name__)


@dataclass
class TradeSignal:
    """Simple trade signal."""

    symbol: str
    action: str  # "BUY", "SELL", "HOLD"
    confidence: float  # 0-1
    reason: str
    price: float
    sma_20: float
    sma_50: float


@dataclass
class TradeResult:
    """Trade execution result."""

    success: bool
    symbol: str
    action: str
    amount: float
    price: float
    order_id: str | None
    error: str | None


class MinimalTrader:
    """
    Minimal viable trading system with stripped-down logic.

    Entry Rules:
    - BUY when SMA(20) crosses above SMA(50)
    - Price > SMA(20) (momentum confirmation)

    Exit Rules:
    - SELL when price drops 3% (stop-loss)
    - SELL when price rises 5% (take-profit)
    - SELL when SMA(20) crosses below SMA(50)

    Position Sizing:
    - Fixed 2% of portfolio per trade
    - Max 5 positions at once

    Risk Management:
    - Daily loss limit: 2% (circuit breaker)
    - That's it. No other gates.
    """

    # Simple configuration
    SMA_SHORT = 20
    SMA_LONG = 50
    POSITION_SIZE_PCT = 0.02  # 2% of portfolio per trade
    MAX_POSITIONS = 5
    STOP_LOSS_PCT = -0.03  # -3%
    TAKE_PROFIT_PCT = 0.05  # +5%
    DAILY_LOSS_LIMIT = -0.02  # -2% circuit breaker

    # Universe: Just the basics
    UNIVERSE = ["SPY", "QQQ", "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META"]

    def __init__(self, paper: bool = True, daily_budget: float = 10.0):
        """Initialize minimal trader."""
        self.paper = paper
        self.daily_budget = daily_budget
        self.trader = AlpacaTrader(paper=paper)
        self.daily_pnl = 0.0
        self.trades_today = 0
        self.circuit_breaker_tripped = False

        logger.info(f"MinimalTrader initialized: paper={paper}, budget=${daily_budget}")

    def get_sma(self, symbol: str, period: int) -> float | None:
        """Calculate simple moving average."""
        try:
            bars = self.trader.get_bars(symbol, timeframe="1Day", limit=period + 5)
            if not bars or len(bars) < period:
                return None
            closes = [float(bar["c"]) for bar in bars[-period:]]
            return sum(closes) / len(closes)
        except Exception as e:
            logger.error(f"Failed to get SMA for {symbol}: {e}")
            return None

    def get_current_price(self, symbol: str) -> float | None:
        """Get current price."""
        try:
            quote = self.trader.get_quote(symbol)
            if quote:
                return float(quote.get("ask_price") or quote.get("last_price", 0))
            return None
        except Exception as e:
            logger.error(f"Failed to get price for {symbol}: {e}")
            return None

    def generate_signal(self, symbol: str) -> TradeSignal | None:
        """
        Generate simple momentum signal.

        BUY when:
        - SMA(20) > SMA(50) (golden cross or uptrend)
        - Price > SMA(20) (momentum confirmation)

        SELL when:
        - SMA(20) < SMA(50) (death cross or downtrend)
        """
        sma_20 = self.get_sma(symbol, self.SMA_SHORT)
        sma_50 = self.get_sma(symbol, self.SMA_LONG)
        price = self.get_current_price(symbol)

        if not all([sma_20, sma_50, price]):
            logger.warning(f"Insufficient data for {symbol}")
            return None

        # Simple momentum logic
        if sma_20 > sma_50 and price > sma_20:
            action = "BUY"
            confidence = min((sma_20 - sma_50) / sma_50 * 10, 1.0)  # Scale to 0-1
            reason = (
                f"Uptrend: SMA20 ({sma_20:.2f}) > SMA50 ({sma_50:.2f}), Price ({price:.2f}) > SMA20"
            )
        elif sma_20 < sma_50:
            action = "SELL"
            confidence = min((sma_50 - sma_20) / sma_50 * 10, 1.0)
            reason = f"Downtrend: SMA20 ({sma_20:.2f}) < SMA50 ({sma_50:.2f})"
        else:
            action = "HOLD"
            confidence = 0.5
            reason = "No clear signal"

        return TradeSignal(
            symbol=symbol,
            action=action,
            confidence=confidence,
            reason=reason,
            price=price,
            sma_20=sma_20,
            sma_50=sma_50,
        )

    def check_circuit_breaker(self) -> bool:
        """Check if circuit breaker should trip."""
        if self.circuit_breaker_tripped:
            return True

        try:
            account = self.trader.get_account_summary()
            equity = float(account.get("equity", 0))
            last_equity = float(account.get("last_equity", equity))

            if last_equity > 0:
                daily_return = (equity - last_equity) / last_equity
                if daily_return < self.DAILY_LOSS_LIMIT:
                    logger.warning(
                        f"CIRCUIT BREAKER TRIPPED: Daily loss {daily_return:.2%} "
                        f"exceeds limit {self.DAILY_LOSS_LIMIT:.2%}"
                    )
                    self.circuit_breaker_tripped = True
                    return True
        except Exception as e:
            logger.error(f"Circuit breaker check failed: {e}")

        return False

    def get_position_size(self) -> float:
        """Calculate position size (2% of portfolio)."""
        try:
            account = self.trader.get_account_summary()
            equity = float(account.get("equity", 100000))
            return equity * self.POSITION_SIZE_PCT
        except Exception as e:
            logger.error(f"Failed to get position size: {e}")
            return 100.0  # Fallback to $100

    def count_positions(self) -> int:
        """Count current open positions."""
        try:
            positions = self.trader.get_positions()
            return len([p for p in positions if p["symbol"] in self.UNIVERSE])
        except Exception as e:
            logger.error(f"Failed to count positions: {e}")
            return 0

    def check_exit_conditions(self, symbol: str) -> tuple[bool, str]:
        """
        Check if position should be exited.

        Returns: (should_exit, reason)
        """
        try:
            positions = self.trader.get_positions()
            position = next((p for p in positions if p["symbol"] == symbol), None)

            if not position:
                return False, ""

            unrealized_plpc = float(position.get("unrealized_plpc", 0))

            # Stop-loss
            if unrealized_plpc <= self.STOP_LOSS_PCT:
                return True, f"STOP-LOSS: {unrealized_plpc:.2%} <= {self.STOP_LOSS_PCT:.2%}"

            # Take-profit
            if unrealized_plpc >= self.TAKE_PROFIT_PCT:
                return True, f"TAKE-PROFIT: {unrealized_plpc:.2%} >= {self.TAKE_PROFIT_PCT:.2%}"

            # Momentum reversal (check SMA cross)
            signal = self.generate_signal(symbol)
            if signal and signal.action == "SELL":
                return True, f"MOMENTUM REVERSAL: {signal.reason}"

            return False, ""

        except Exception as e:
            logger.error(f"Exit check failed for {symbol}: {e}")
            return False, ""

    def execute_trade(self, signal: TradeSignal) -> TradeResult:
        """Execute a trade based on signal."""
        try:
            if signal.action == "BUY":
                amount = min(self.get_position_size(), self.daily_budget)
                order = self.trader.execute_order(
                    symbol=signal.symbol,
                    amount_usd=amount,
                    side="buy",
                    tier="MINIMAL",
                )
                return TradeResult(
                    success=True,
                    symbol=signal.symbol,
                    action="BUY",
                    amount=amount,
                    price=signal.price,
                    order_id=order.get("id"),
                    error=None,
                )
            elif signal.action == "SELL":
                # Close position
                positions = self.trader.get_positions()
                position = next((p for p in positions if p["symbol"] == signal.symbol), None)

                if position:
                    qty = float(position["qty"])
                    order = self.trader.close_position(signal.symbol)
                    return TradeResult(
                        success=True,
                        symbol=signal.symbol,
                        action="SELL",
                        amount=qty * signal.price,
                        price=signal.price,
                        order_id=order.get("id") if order else None,
                        error=None,
                    )

            return TradeResult(
                success=False,
                symbol=signal.symbol,
                action=signal.action,
                amount=0,
                price=signal.price,
                order_id=None,
                error="No action taken",
            )

        except Exception as e:
            logger.error(f"Trade execution failed: {e}")
            return TradeResult(
                success=False,
                symbol=signal.symbol,
                action=signal.action,
                amount=0,
                price=signal.price,
                order_id=None,
                error=str(e),
            )

    def run_daily(self) -> dict[str, Any]:
        """
        Run daily trading cycle.

        Simple flow:
        1. Check circuit breaker
        2. Check existing positions for exits
        3. Scan universe for entry signals
        4. Execute trades
        """
        logger.info("=" * 60)
        logger.info("MINIMAL TRADER - Daily Run")
        logger.info(f"Time: {datetime.now()}")
        logger.info("=" * 60)

        results = {
            "timestamp": datetime.now().isoformat(),
            "circuit_breaker": False,
            "exits": [],
            "entries": [],
            "errors": [],
        }

        # Step 1: Circuit breaker check
        if self.check_circuit_breaker():
            logger.warning("Circuit breaker active - no trading")
            results["circuit_breaker"] = True
            return results

        # Step 2: Check exits for existing positions
        logger.info("\n--- CHECKING EXITS ---")
        try:
            positions = self.trader.get_positions()
            for pos in positions:
                symbol = pos["symbol"]
                if symbol not in self.UNIVERSE:
                    continue

                should_exit, reason = self.check_exit_conditions(symbol)
                if should_exit:
                    logger.info(f"EXIT SIGNAL: {symbol} - {reason}")
                    signal = TradeSignal(
                        symbol=symbol,
                        action="SELL",
                        confidence=1.0,
                        reason=reason,
                        price=float(pos.get("current_price", 0)),
                        sma_20=0,
                        sma_50=0,
                    )
                    result = self.execute_trade(signal)
                    results["exits"].append(
                        {"symbol": symbol, "reason": reason, "success": result.success}
                    )
        except Exception as e:
            logger.error(f"Exit check failed: {e}")
            results["errors"].append(f"Exit check: {e}")

        # Step 3: Scan for entry signals
        logger.info("\n--- SCANNING FOR ENTRIES ---")
        current_positions = self.count_positions()

        if current_positions >= self.MAX_POSITIONS:
            logger.info(f"Max positions ({self.MAX_POSITIONS}) reached - no new entries")
        else:
            for symbol in self.UNIVERSE:
                # Skip if already have position
                try:
                    positions = self.trader.get_positions()
                    if any(p["symbol"] == symbol for p in positions):
                        continue
                except Exception:
                    pass

                signal = self.generate_signal(symbol)
                if signal and signal.action == "BUY" and signal.confidence > 0.3:
                    logger.info(f"ENTRY SIGNAL: {symbol} - {signal.reason}")
                    result = self.execute_trade(signal)
                    results["entries"].append(
                        {
                            "symbol": symbol,
                            "confidence": signal.confidence,
                            "success": result.success,
                            "amount": result.amount,
                        }
                    )

                    current_positions += 1
                    if current_positions >= self.MAX_POSITIONS:
                        break

        # Summary
        logger.info("\n" + "=" * 60)
        logger.info("DAILY SUMMARY")
        logger.info(f"  Exits: {len(results['exits'])}")
        logger.info(f"  Entries: {len(results['entries'])}")
        logger.info(f"  Errors: {len(results['errors'])}")
        logger.info("=" * 60)

        return results


def main():
    """Run minimal trader."""
    import sys

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    paper = "--live" not in sys.argv
    trader = MinimalTrader(paper=paper, daily_budget=10.0)
    results = trader.run_daily()

    print("\n" + "=" * 60)
    print("MINIMAL TRADER RESULTS")
    print("=" * 60)
    print(f"Circuit Breaker: {'TRIPPED' if results['circuit_breaker'] else 'OK'}")
    print(f"Exits: {len(results['exits'])}")
    print(f"Entries: {len(results['entries'])}")
    print(f"Errors: {len(results['errors'])}")
    print("=" * 60)


if __name__ == "__main__":
    main()
