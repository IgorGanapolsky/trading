"""
Execution Agent: Order execution and timing optimization

Responsibilities:
- Execute orders via Alpaca API
- Optimize execution timing
- Handle order failures
- Track execution quality

Ensures best execution
"""

import logging
from typing import Dict, Any, Optional
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
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

    def __init__(self, alpaca_api: Optional[TradingClient] = None):
        super().__init__(
            name="ExecutionAgent", role="Order execution and timing optimization"
        )
        self.alpaca_api = alpaca_api
        self.execution_history: list = []

    def analyze(self, data: Dict[str, Any]) -> Dict[str, Any]:
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

        # Build execution analysis prompt
        memory_context = self.get_memory_context(limit=3)

        # Goldilocks Prompt: Focused execution with timing examples
        prompt = f"""Execute {action} ${position_size:,.0f} on {symbol}. Minimize slippage, maximize fill quality.

ORDER: {action} {symbol} ${position_size:,.0f} (Market) | Status: {market_status['status']}
CONDITIONS: Spread {market_conditions.get('spread', 'N/A')} | Vol {market_conditions.get('volume', 'N/A')} | Volatility {market_conditions.get('volatility', 'N/A')}

{memory_context}

PRINCIPLES:
- Wide spread (>0.1%) = wait for better liquidity or use limit order
- Low volume (<50% avg) = expect higher slippage, consider splitting
- First/last 15 min of day = higher volatility, avoid if not urgent
- Market closed = queue for open (unless overnight risk is acceptable)

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

    def _check_market_status(self) -> Dict[str, Any]:
        """Check if market is open and ready for trading."""
        if not self.alpaca_api:
            return {"status": "UNKNOWN", "is_open": False}

        try:
            clock = self.alpaca_api.get_clock()
            return {
                "status": "OPEN" if clock.is_open else "CLOSED",
                "is_open": clock.is_open,
                "next_open": (
                    str(clock.next_open) if hasattr(clock, "next_open") else None
                ),
                "next_close": (
                    str(clock.next_close) if hasattr(clock, "next_close") else None
                ),
            }
        except Exception as e:
            logger.error(f"Error checking market status: {e}")
            return {"status": "ERROR", "is_open": False, "error": str(e)}

    def _execute_order(
        self, symbol: str, action: str, position_size: float
    ) -> Dict[str, Any]:
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
            logger.info(
                f"Order executed: {order.id} - {symbol} {action} ${position_size}"
            )

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

    def _parse_execution_response(self, reasoning: str) -> Dict[str, Any]:
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
                except:
                    pass
            elif line.startswith("CONFIDENCE:"):
                try:
                    analysis["confidence"] = float(line.split(":")[1].strip())
                except:
                    pass
            elif line.startswith("RECOMMENDATION:"):
                rec = line.split(":")[1].strip().upper()
                if rec in ["EXECUTE", "DELAY", "CANCEL"]:
                    analysis["action"] = rec

        return analysis
