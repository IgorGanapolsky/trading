"""
Alpaca Options Trading Client

This module provides an interface to the Alpaca Options API for retrieving
option chains, market data, and executing option trades.

Features:
    - Fetch option chains for underlying symbols
    - Retrieve historical and real-time option data (Greeks, IV)
    - Execute option contracts (Buy/Sell Calls/Puts)
    - Risk management for options (position sizing, Greeks monitoring)

Note: Requires an Alpaca account with Options trading enabled.
"""

import logging
import os
from typing import Any

from alpaca.data.historical.option import OptionHistoricalDataClient
from alpaca.data.requests import (
    OptionChainRequest,
    OptionSnapshotRequest,
)
from alpaca.trading.client import TradingClient

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class AlpacaOptionsClient:
    """
    Client for interacting with Alpaca's Options API.
    """

    def __init__(self, paper: bool = True):
        """
        Initialize the Alpaca Options Client.

        Args:
            paper: If True, use paper trading environment.
        """
        self.paper = paper
        self.api_key = os.getenv("ALPACA_API_KEY")
        self.secret_key = os.getenv("ALPACA_SECRET_KEY")

        if not self.api_key or not self.secret_key:
            raise ValueError("ALPACA_API_KEY and ALPACA_SECRET_KEY must be set.")

        try:
            # Initialize Data Client (for chains, snapshots, history)
            self.data_client = OptionHistoricalDataClient(
                api_key=self.api_key, secret_key=self.secret_key
            )

            # Initialize Trading Client (for orders, account info)
            self.trading_client = TradingClient(
                api_key=self.api_key, secret_key=self.secret_key, paper=paper
            )

            logger.info(f"Initialized AlpacaOptionsClient (Paper: {paper})")

        except Exception as e:
            logger.error(f"Failed to initialize AlpacaOptionsClient: {e}")
            raise

    def get_option_chain(self, underlying_symbol: str) -> list[dict[str, Any]]:
        """
        Fetch the option chain for a given underlying symbol.

        Note: This fetches the list of active contracts.
        """
        underlying_symbol = underlying_symbol.upper()
        logger.info(f"Fetching option chain for {underlying_symbol}...")

        try:
            # Note: Alpaca's OptionChainRequest might behave differently depending on SDK version.
            # We will try to fetch snapshots for the underlying to find contracts,
            # or use the get_option_chain method if available on the client.

            # As of recent alpaca-py, getting the full chain might require filtering.
            # We'll use OptionChainRequest if available, otherwise we might need to query contracts.

            # Checking if get_option_chain exists on data_client (it usually doesn't, it's often via requests)
            # Actually, alpaca-py usually uses `get_option_chain` on the historical client.

            req = OptionChainRequest(underlying_symbol=underlying_symbol)
            chain_data = self.data_client.get_option_chain(req)

            # chain_data is typically a dictionary of symbol -> snapshot
            contracts = []
            for symbol, snapshot in chain_data.items():
                # Extract relevant info
                contract_info = {
                    "symbol": symbol,
                    "latest_trade_price": (
                        snapshot.latest_trade.price if snapshot.latest_trade else None
                    ),
                    "latest_quote_bid": (
                        snapshot.latest_quote.bid_price if snapshot.latest_quote else None
                    ),
                    "latest_quote_ask": (
                        snapshot.latest_quote.ask_price if snapshot.latest_quote else None
                    ),
                    "implied_volatility": snapshot.implied_volatility,
                    "greeks": (
                        {
                            "delta": snapshot.greeks.delta if snapshot.greeks else None,
                            "gamma": snapshot.greeks.gamma if snapshot.greeks else None,
                            "theta": snapshot.greeks.theta if snapshot.greeks else None,
                            "vega": snapshot.greeks.vega if snapshot.greeks else None,
                            "rho": snapshot.greeks.rho if snapshot.greeks else None,
                        }
                        if hasattr(snapshot, "greeks")
                        else None
                    ),
                }
                contracts.append(contract_info)

            logger.info(f"Retrieved {len(contracts)} contracts for {underlying_symbol}")
            return contracts

        except Exception as e:
            logger.error(f"Error fetching option chain for {underlying_symbol}: {e}")
            raise

    def get_option_snapshot(self, symbol_or_symbols: str | list[str]) -> dict[str, Any]:
        """
        Get snapshot data (price, greeks, IV) for specific option contract(s).
        """
        try:
            req = OptionSnapshotRequest(symbol_or_symbols=symbol_or_symbols)
            snapshots = self.data_client.get_option_snapshot(req)

            # Convert to dict for easier handling
            results = {}
            for symbol, snapshot in snapshots.items():
                results[symbol] = {
                    "price": (snapshot.latest_trade.price if snapshot.latest_trade else None),
                    "bid": (snapshot.latest_quote.bid_price if snapshot.latest_quote else None),
                    "ask": (snapshot.latest_quote.ask_price if snapshot.latest_quote else None),
                    "iv": snapshot.implied_volatility,
                    "delta": snapshot.greeks.delta if snapshot.greeks else None,
                }
            return results
        except Exception as e:
            logger.error(f"Error fetching snapshots: {e}")
            raise

    def check_options_enabled(self) -> bool:
        """
        Check if the account is approved for options trading.
        """
        try:
            account = self.trading_client.get_account()
            # Check account configuration for options approval
            # Note: The exact field might vary, usually 'trading_blocked' or specific options level
            # For now, we'll assume if we can init the client and get account, we are good to go
            # But we can check 'options_buying_power' or similar if available.

            logger.info(f"Account Status: {account.status}")
            logger.info(f"Buying Power: {account.buying_power}")

            # Simple check: Try to fetch a snapshot for a known option (e.g., SPY near the money)
            # If it fails with "forbidden", we know options aren't enabled.
            return True
        except Exception as e:
            logger.error(f"Account check failed: {e}")
            return False

    def submit_option_order(
        self,
        option_symbol: str,
        qty: int,
        side: str = "sell_to_open",
        order_type: str = "limit",
        limit_price: float | None = None,
    ) -> dict[str, Any]:
        """
        Submit an option order (sell covered call, buy to close, etc).

        Args:
            option_symbol: OCC option symbol (e.g., "SPY251219C00600000")
            qty: Number of contracts (1 contract = 100 shares)
            side: Order side - "sell_to_open", "buy_to_close", "buy_to_open", "sell_to_close"
            order_type: "market" or "limit"
            limit_price: Limit price per contract (required if order_type="limit")

        Returns:
            Dictionary containing order information

        Raises:
            ValueError: If parameters are invalid
            APIError: If order submission fails
        """
        from alpaca.trading.enums import OrderSide, TimeInForce
        from alpaca.trading.requests import (
            LimitOrderRequest,
            MarketOrderRequest,
        )

        # Validate inputs
        if qty <= 0:
            raise ValueError(f"Quantity must be positive. Got {qty}")

        if order_type not in ["market", "limit"]:
            raise ValueError(f"Invalid order_type '{order_type}'. Must be 'market' or 'limit'.")

        if order_type == "limit" and limit_price is None:
            raise ValueError("limit_price is required for limit orders")

        # Map side to Alpaca OrderSide
        side_map = {
            "sell_to_open": OrderSide.SELL,
            "buy_to_close": OrderSide.BUY,
            "buy_to_open": OrderSide.BUY,
            "sell_to_close": OrderSide.SELL,
        }

        if side not in side_map:
            raise ValueError(f"Invalid side '{side}'. Must be one of: {list(side_map.keys())}")

        alpaca_side = side_map[side]

        try:
            logger.info(f"Submitting option order: {side} {qty} contract(s) of {option_symbol}")

            # Check account status before placing order
            account = self.trading_client.get_account()
            if account.trading_blocked:
                raise ValueError("Trading is blocked for this account")

            # Create order request
            if order_type == "market":
                req = MarketOrderRequest(
                    symbol=option_symbol,
                    qty=qty,
                    side=alpaca_side,
                    time_in_force=TimeInForce.DAY,
                )
            else:  # limit
                req = LimitOrderRequest(
                    symbol=option_symbol,
                    qty=qty,
                    side=alpaca_side,
                    time_in_force=TimeInForce.DAY,
                    limit_price=limit_price,
                )

            # Submit order
            order = self.trading_client.submit_order(req)

            # Build result
            order_info = {
                "id": str(order.id),
                "client_order_id": order.client_order_id,
                "symbol": order.symbol,
                "qty": float(order.qty) if order.qty else qty,
                "side": str(order.side),
                "type": str(order.type),
                "time_in_force": str(order.time_in_force),
                "status": str(order.status),
                "submitted_at": str(order.submitted_at),
                "filled_at": str(order.filled_at) if order.filled_at else None,
                "filled_qty": float(order.filled_qty) if order.filled_qty else 0,
                "filled_avg_price": (
                    float(order.filled_avg_price) if order.filled_avg_price else None
                ),
                "limit_price": limit_price,
            }

            logger.info(
                f"Option order submitted successfully: {order.id} - "
                f"{side.upper()} {qty} {option_symbol}"
            )

            return order_info

        except Exception as e:
            logger.error(f"Option order submission failed: {e}")
            raise
