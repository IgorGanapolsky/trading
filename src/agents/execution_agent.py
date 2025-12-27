from __future__ import annotations

"""
Execution Agent: Order execution and timing optimization

Responsibilities:
- Execute orders via Alpaca API
- Optimize execution timing
- Handle order failures
- Track execution quality

Ensures best execution
"""

import builtins
import contextlib
import logging
from typing import Any

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.requests import MarketOrderRequest

try:
    from src.core.options_client import AlpacaOptionsClient
except Exception:  # pragma: no cover - optional dependency in lightweight test envs
    AlpacaOptionsClient = None  # type: ignore[misc,assignment]

from src.utils.market_data import MarketDataProvider
from src.utils.technical_indicators import calculate_macd, calculate_rsi

from .base_agent import BaseAgent

logger = logging.getLogger(__name__)


class ExecutionAgent(BaseAgent):
    """
    Agent responsible for executing trades efficiently.

    Responsibilities:
    - Execute orders with minimal slippage
    - Monitor order status
    - Handle partial fills
    - Track execution quality (slippage, fill rate)
    """

    def __init__(
        self,
        alpaca_api: TradingClient | None = None,
        *,
        paper: bool = True,
        options_client: AlpacaOptionsClient | None = None,
    ):
        super().__init__(name="ExecutionAgent", role="Order execution and timing optimization")
        self.alpaca_api = alpaca_api
        self.paper = paper
        self.options_client = options_client
        self.execution_history: list = []
        # Lazily instantiated options client (False sentinel == permanently unavailable)
        self._options_client: AlpacaOptionsClient | None | bool = options_client
        self.data_provider = MarketDataProvider()

    def analyze(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Analyze execution timing and prepare order.

        Args:
            data: Contains action, symbol, position_size, market conditions

        Returns:
            Execution plan with timing recommendation
        """
        action = data.get("action", "HOLD")
        symbol = data.get("symbol", "UNKNOWN")
        position_size = data.get("position_size", 0)
        market_conditions = data.get("market_conditions", {})

        if action == "HOLD":
            return {
                "action": "NO_EXECUTION",
                "reasoning": "HOLD recommendation - no order needed",
            }

        # Check market status
        market_status = self._check_market_status()

        # Fetch historical data and calculate technicals
        macd_hist = 0.0
        rsi = 50.0
        try:
            # Fetch 60 days of data to ensure enough for MACD/RSI
            hist_result = self.data_provider.get_daily_bars(symbol, lookback_days=60)
            if not hist_result.data.empty:
                prices = hist_result.data["Close"]
                _, _, macd_hist = calculate_macd(prices)
                rsi = calculate_rsi(prices)
        except Exception as e:
            logger.warning(f"Failed to calculate technicals for {symbol}: {e}")

        # Build execution analysis prompt
        memory_context = self.get_memory_context(limit=3)

        # Goldilocks Prompt: Focused execution with timing examples
        prompt = f"""Execute {action} ${position_size:,.0f} on {symbol}. Minimize slippage, maximize fill quality.

ORDER: {action} {symbol} ${position_size:,.0f} (Market) | Status: {market_status["status"]}
CONDITIONS: Spread {market_conditions.get("spread", "N/A")} | Vol {market_conditions.get("volume", "N/A")} | Volatility {market_conditions.get("volatility", "N/A")}
TECHNICALS: MACD Hist {macd_hist:.3f} | RSI {rsi:.1f}

{memory_context}

REASONING PROTOCOL:
Think step-by-step before deciding:
1. Check market status and timing constraints
2. Evaluate liquidity conditions (spread, volume)
3. Assess technical momentum (RSI, MACD)
4. Estimate slippage risk based on conditions
5. Critique your assessment - what execution risk are you underestimating?

PRINCIPLES:
- Wide spread (>0.1%) = wait for better liquidity or use limit order
- Low volume (<50% avg) = expect higher slippage, consider splitting
- First/last 15 min of day = higher volatility, avoid if not urgent
- Market closed = queue for open (unless overnight risk is acceptable)
- RSI > 70 = Overbought, be cautious with BUYs (consider DELAY)
- RSI < 30 = Oversold, potential bounce (good for BUYs)
- MACD Hist < 0 = Bearish momentum (be cautious with BUYs)
- MACD Hist > 0 = Bullish momentum

EXAMPLES:
Example 1 - Execute Now:
TIMING: IMMEDIATE
SLIPPAGE: 0.05%
CONFIDENCE: 0.92
RECOMMENDATION: EXECUTE
(Good liquidity, tight spread, mid-day execution)

Example 2 - Wait for Open:
TIMING: WAIT_OPEN
SLIPPAGE: 0.15%
CONFIDENCE: 0.75
RECOMMENDATION: DELAY
(Market closed, queue order for 9:35 AM to avoid opening volatility)

Example 3 - Cancel:
TIMING: N/A
SLIPPAGE: N/A
CONFIDENCE: 0.30
RECOMMENDATION: CANCEL
(Spread 0.8% too wide, volume dried up, wait for better conditions)

NOW DECIDE FOR {symbol} {action}:
TIMING: [IMMEDIATE/WAIT_5MIN/WAIT_OPEN]
SLIPPAGE: [expected %]
CONFIDENCE: [0-1]
RECOMMENDATION: [EXECUTE/DELAY/CANCEL]"""

        # Get LLM analysis
        response = self.reason_with_llm(prompt)

        # Parse response
        analysis = self._parse_execution_response(response["reasoning"])
        analysis["market_status"] = market_status
        analysis["full_reasoning"] = response["reasoning"]

        # Execute if recommended
        if analysis["action"] == "EXECUTE" and self.alpaca_api:
            execution_result = self._execute_order(symbol, action, position_size)
            analysis["execution_result"] = execution_result
        else:
            analysis["execution_result"] = {
                "status": "NOT_EXECUTED",
                "reason": analysis["action"],
            }

        # Log decision
        self.log_decision(analysis)

        return analysis

    # ------------------------------------------------------------------ #
    # Options execution helpers
    # ------------------------------------------------------------------ #
    def _get_options_client(self) -> AlpacaOptionsClient | None:
        """
        Lazily resolve an Alpaca options client if credentials are available.

        Returns:
            AlpacaOptionsClient or None when unavailable (missing creds / package)
        """

        if self._options_client is False:
            return None

        if self._options_client is not None:
            return self._options_client

        if AlpacaOptionsClient is None:
            logger.warning("AlpacaOptionsClient not available in current environment.")
            self._options_client = False
            return None

        try:
            self._options_client = AlpacaOptionsClient(paper=self.paper)
            return self._options_client
        except Exception as exc:  # pragma: no cover - depends on external creds
            logger.warning("Failed to initialize AlpacaOptionsClient: %s", exc)
            self._options_client = False
            return None

    def submit_option_order(
        self,
        *,
        option_symbol: str,
        qty: int,
        side: str = "sell_to_open",
        order_type: str = "limit",
        limit_price: float | None = None,
        paper: bool | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Submit an option order using Alpaca's options API (with simulation fallback).

        Args:
            option_symbol: OCC option symbol (e.g., SPY240216C00420000)
            qty: Number of contracts to trade
            side: Order side (sell_to_open, buy_to_close, etc.)
            order_type: "market" or "limit"
            limit_price: Limit price per contract when using limit orders
            paper: Override for paper/live flag (defaults to agent setting)
            metadata: Additional context to persist alongside execution history

        Returns:
            Dict containing submission metadata (or simulation) plus execution status.
        """

        if qty <= 0:
            raise ValueError("qty must be positive when submitting option orders.")

        payload_meta = metadata.copy() if metadata else {}
        payload_meta["option_symbol"] = option_symbol
        payload_meta["side"] = side
        payload_meta["order_type"] = order_type
        payload_meta["limit_price"] = limit_price

        client = self._get_options_client()
        final_paper = self.paper if paper is None else paper
        result: dict[str, Any]

        if client:
            try:
                order = client.submit_option_order(
                    option_symbol=option_symbol,
                    qty=qty,
                    side=side,
                    order_type=order_type,
                    limit_price=limit_price,
                )
                result = {
                    "status": "SUBMITTED",
                    "order": order,
                    "metadata": payload_meta,
                    "paper": final_paper,
                }
                logger.info(
                    "Options order submitted via Alpaca: %s x%d (%s)",
                    option_symbol,
                    qty,
                    side,
                )
            except Exception as exc:  # pragma: no cover - network/credential failures
                logger.error("Option order submission failed: %s", exc)
                result = {
                    "status": "ERROR",
                    "error": str(exc),
                    "option_symbol": option_symbol,
                    "qty": qty,
                    "side": side,
                    "metadata": payload_meta,
                }
        else:
            # Simulation fallback when options trading isn't enabled in this environment.
            result = {
                "status": "SIMULATED",
                "option_symbol": option_symbol,
                "qty": qty,
                "side": side,
                "order_type": order_type,
                "limit_price": limit_price,
                "metadata": payload_meta,
                "paper": final_paper,
            }
            logger.info(
                "Simulated options order: %s x%d (%s) @ %s",
                option_symbol,
                qty,
                side,
                limit_price if limit_price is not None else "MKT",
            )

        self.execution_history.append(result)
        return result

    def _check_market_status(self) -> dict[str, Any]:
        """Check if market is open and ready for trading."""
        if not self.alpaca_api:
            return {"status": "UNKNOWN", "is_open": False}

        try:
            clock = self.alpaca_api.get_clock()
            return {
                "status": "OPEN" if clock.is_open else "CLOSED",
                "is_open": clock.is_open,
                "next_open": (str(clock.next_open) if hasattr(clock, "next_open") else None),
                "next_close": (str(clock.next_close) if hasattr(clock, "next_close") else None),
            }
        except Exception as e:
            logger.error(f"Error checking market status: {e}")
            return {"status": "ERROR", "is_open": False, "error": str(e)}

    def _execute_order(self, symbol: str, action: str, position_size: float) -> dict[str, Any]:
        """
        Execute order via Alpaca API.

        Args:
            symbol: Stock symbol
            action: BUY or SELL
            position_size: Dollar amount

        Returns:
            Execution result
        """
        try:
            if action == "BUY":
                req = MarketOrderRequest(
                    symbol=symbol,
                    notional=position_size,
                    side=OrderSide.BUY,
                    time_in_force=TimeInForce.DAY,
                )
                order = self.alpaca_api.submit_order(req)
            elif action == "SELL":
                # For sell, we'd need to know the quantity (not implemented yet)
                return {"status": "ERROR", "message": "SELL not yet implemented"}
            else:
                return {"status": "ERROR", "message": f"Unknown action: {action}"}

            result = {
                "status": "SUCCESS",
                "order_id": order.id,
                "symbol": symbol,
                "action": action,
                "amount": position_size,
                "order_status": order.status,
            }

            # Track execution
            self.execution_history.append(result)
            logger.info(f"Order executed: {order.id} - {symbol} {action} ${position_size}")

            return result

        except Exception as e:
            logger.error(f"Order execution error: {e}")
            return {
                "status": "ERROR",
                "error": str(e),
                "symbol": symbol,
                "action": action,
                "amount": position_size,
            }

    def _parse_execution_response(self, reasoning: str) -> dict[str, Any]:
        """Parse LLM response into structured execution plan."""
        lines = reasoning.split("\n")
        analysis = {
            "timing": "IMMEDIATE",
            "slippage": 0.001,
            "confidence": 0.8,
            "action": "EXECUTE",
        }

        for line in lines:
            line = line.strip()
            if line.startswith("TIMING:"):
                timing = line.split(":")[1].strip().upper()
                if timing in ["IMMEDIATE", "WAIT_5MIN", "WAIT_OPEN"]:
                    analysis["timing"] = timing
            elif line.startswith("SLIPPAGE:"):
                try:
                    slippage_str = line.split(":")[1].strip().replace("%", "")
                    analysis["slippage"] = float(slippage_str) / 100
                except Exception:
                    pass
            elif line.startswith("CONFIDENCE:"):
                with contextlib.suppress(builtins.BaseException):
                    analysis["confidence"] = float(line.split(":")[1].strip())
            elif line.startswith("RECOMMENDATION:"):
                rec = line.split(":")[1].strip().upper()
                if rec in ["EXECUTE", "DELAY", "CANCEL"]:
                    analysis["action"] = rec

        return analysis

    # ------------------------------------------------------------------ #
    # Options execution helpers (Theta automation, etc.)
    # ------------------------------------------------------------------ #
    def execute_option_trade(
        self,
        *,
        option_symbol: str,
        side: str,
        qty: int,
        order_type: str = "limit",
        limit_price: float | None = None,
    ) -> dict[str, Any]:
        """
        Submit an options order via the Alpaca options client.

        Args:
            option_symbol: OCC-formatted option ticker (e.g., SPY250117C00450000)
            side: One of sell_to_open, buy_to_close, buy_to_open, sell_to_close
            qty: Number of contracts
            order_type: limit or market
            limit_price: Required for limit orders (per contract)
        """
        if not self.options_client:
            raise RuntimeError("Options client not configured for ExecutionAgent")

        result = self.options_client.submit_option_order(
            option_symbol=option_symbol,
            qty=qty,
            side=side,
            order_type=order_type,
            limit_price=limit_price,
        )
        self.execution_history.append(
            {
                "type": "options",
                "symbol": option_symbol,
                "side": side,
                "qty": qty,
                "order_type": order_type,
                "limit_price": limit_price,
                "result": result,
            }
        )
        logger.info(
            "Options order submitted via ExecutionAgent: %s %s x%d @ %s (status=%s)",
            side,
            option_symbol,
            qty,
            f"${limit_price:.2f}" if limit_price else "mkt",
            result.get("status"),
        )
        return result
