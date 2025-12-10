#!/usr/bin/env python3
"""
Demonstration of Multi-Broker Failover in AlpacaExecutor

This example shows how to enable automatic broker failover
in the execution layer. When ENABLE_BROKER_FAILOVER=true,
orders automatically fail over from Alpaca → IBKR → Tradier
if any broker becomes unavailable.

Usage:
    # Enable failover (recommended for production)
    export ENABLE_BROKER_FAILOVER=true
    python3 examples/broker_failover_demo.py

    # Disable failover (default, backward compatible)
    export ENABLE_BROKER_FAILOVER=false
    python3 examples/broker_failover_demo.py
"""

import logging
import os

from src.execution.alpaca_executor import AlpacaExecutor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


def demo_basic_order():
    """Demonstrate basic order placement with failover."""
    logger.info("=" * 80)
    logger.info("DEMO: Basic Order Placement with Failover")
    logger.info("=" * 80)

    # Initialize executor
    # If ENABLE_BROKER_FAILOVER=true, it will use multi-broker failover
    # Otherwise, it uses standard Alpaca-only execution
    executor = AlpacaExecutor(paper=True, allow_simulator=True)

    failover_status = "ENABLED" if executor.enable_failover else "DISABLED"
    logger.info(f"Failover Status: {failover_status}")

    if executor.enable_failover:
        logger.info("Orders will automatically fail over: Alpaca → IBKR → Tradier")
    else:
        logger.info("Using standard Alpaca-only execution (backward compatible)")

    # Sync portfolio state
    executor.sync_portfolio_state()
    logger.info(f"Account Equity: ${executor.account_equity:,.2f}")

    # Example: Place a buy order
    # This will automatically fail over to backup brokers if Alpaca is unavailable
    try:
        logger.info("\nPlacing order for AAPL...")
        order = executor.place_order(
            symbol="AAPL",
            notional=100.0,  # $100 worth of AAPL
            side="buy"
        )

        logger.info("✅ Order placed successfully!")
        logger.info(f"  Order ID: {order.get('id')}")
        logger.info(f"  Symbol: {order.get('symbol')}")
        logger.info(f"  Side: {order.get('side')}")
        logger.info(f"  Status: {order.get('status')}")

        if "broker" in order:
            logger.info(f"  Broker Used: {order['broker']} (via failover)")
        else:
            logger.info("  Broker Used: Alpaca (direct)")

    except Exception as e:
        logger.error(f"❌ Order failed: {e}")


def demo_order_with_stop_loss():
    """Demonstrate order placement with automatic stop-loss."""
    logger.info("\n" + "=" * 80)
    logger.info("DEMO: Order with Stop-Loss and Failover")
    logger.info("=" * 80)

    executor = AlpacaExecutor(paper=True, allow_simulator=True)

    failover_status = "ENABLED" if executor.enable_failover else "DISABLED"
    logger.info(f"Failover Status: {failover_status}")

    try:
        logger.info("\nPlacing order for TSLA with 5% stop-loss...")
        result = executor.place_order_with_stop_loss(
            symbol="TSLA",
            notional=200.0,  # $200 worth of TSLA
            side="buy",
            stop_loss_pct=0.05,  # 5% stop-loss
        )

        logger.info("✅ Order with stop-loss placed successfully!")

        if result["order"]:
            logger.info(f"  Main Order ID: {result['order'].get('id')}")
            logger.info(f"  Status: {result['order'].get('status')}")

            if "broker" in result["order"]:
                logger.info(f"  Broker Used: {result['order']['broker']} (via failover)")

        if result["stop_loss"]:
            logger.info(f"  Stop-Loss Order ID: {result['stop_loss'].get('id')}")
            logger.info(f"  Stop Price: ${result['stop_loss_price']:.2f}")
            logger.info(f"  Stop Percentage: {result['stop_loss_pct'] * 100:.1f}%")

        if result.get("error"):
            logger.warning(f"  ⚠️  Warning: {result['error']}")

    except Exception as e:
        logger.error(f"❌ Order with stop-loss failed: {e}")


def demo_health_check():
    """Demonstrate multi-broker health check."""
    logger.info("\n" + "=" * 80)
    logger.info("DEMO: Multi-Broker Health Check")
    logger.info("=" * 80)

    executor = AlpacaExecutor(paper=True, allow_simulator=True)

    if not executor.enable_failover:
        logger.info("Failover is disabled. Enable with ENABLE_BROKER_FAILOVER=true")
        return

    if executor.multi_broker:
        logger.info("Checking health of all brokers...")
        health = executor.multi_broker.health_check()

        for broker_name, status in health.items():
            logger.info(f"\n{broker_name.upper()}:")
            logger.info(f"  Status: {status.get('status', 'unknown')}")

            if status.get("status") == "healthy":
                logger.info("  ✅ Available for trading")
                if "equity" in status:
                    logger.info(f"  Equity: ${status['equity']:,.2f}")
            elif status.get("status") == "not_configured":
                logger.info("  ⚠️  Not configured (credentials missing)")
            else:
                logger.info("  ❌ Unhealthy")
                if "error" in status:
                    logger.info(f"  Error: {status['error']}")

            if "circuit_breaker" in status:
                logger.info(f"  Circuit Breaker: {status['circuit_breaker']}")


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("MULTI-BROKER FAILOVER DEMONSTRATION")
    print("=" * 80)
    print()
    print("Environment Configuration:")
    print(f"  ENABLE_BROKER_FAILOVER: {os.getenv('ENABLE_BROKER_FAILOVER', 'false')}")
    print(f"  ALPACA_SIMULATED: {os.getenv('ALPACA_SIMULATED', 'false')}")
    print()

    # Run demos
    demo_basic_order()
    demo_order_with_stop_loss()
    demo_health_check()

    print("\n" + "=" * 80)
    print("DEMO COMPLETE")
    print("=" * 80)
    print()
    print("To enable failover in production:")
    print("  export ENABLE_BROKER_FAILOVER=true")
    print()
    print("To disable failover (backward compatible):")
    print("  export ENABLE_BROKER_FAILOVER=false")
    print()
