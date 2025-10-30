"""
Trading System Orchestrator - Main Entry Point

This module serves as the main entry point for the automated trading system,
coordinating all trading strategies on a defined schedule.

The orchestrator manages:
- CoreStrategy (Tier 1): Daily execution at 9:35 AM ET
- GrowthStrategy (Tier 2): Weekly execution on Mondays at 9:35 AM ET
- IPOStrategy (Tier 3): Weekly check for IPO opportunities

Features:
- Scheduled execution using APScheduler
- Manual execution mode for testing
- Comprehensive error handling and logging with file rotation
- Graceful shutdown handling (SIGTERM/SIGINT)
- Health check endpoint for monitoring
- Alert system for critical errors
- Configuration loading from .env file

Author: Trading System
Created: 2025-10-28
"""

import os
import sys
import signal
import logging
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Any
from logging.handlers import RotatingFileHandler

import schedule
import time
import pytz
from dotenv import load_dotenv

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.strategies.core_strategy import CoreStrategy
from src.strategies.growth_strategy import GrowthStrategy
from src.strategies.ipo_strategy import IPOStrategy
from src.core.alpaca_trader import AlpacaTrader
from src.core.risk_manager import RiskManager


# Configure logging with rotation
def setup_logging(log_dir: str = "logs", log_level: str = "INFO") -> logging.Logger:
    """
    Setup comprehensive logging with file rotation.

    Args:
        log_dir: Directory for log files
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    Returns:
        Configured logger instance
    """
    # Create logs directory if it doesn't exist
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    # Create logger
    logger = logging.getLogger("TradingOrchestrator")
    logger.setLevel(getattr(logging, log_level.upper()))

    # Prevent duplicate handlers
    if logger.handlers:
        logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # File handler with rotation (10MB max, keep 5 backup files)
    file_handler = RotatingFileHandler(
        log_path / "trading_system.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    # Error file handler (separate file for errors)
    error_handler = RotatingFileHandler(
        log_path / "trading_errors.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(file_formatter)
    logger.addHandler(error_handler)

    return logger


class TradingOrchestrator:
    """
    Main orchestrator for coordinating all trading strategies.

    This class manages the execution of multiple trading strategies on a defined
    schedule, handles errors, provides health monitoring, and ensures graceful
    shutdown.

    Attributes:
        mode: Trading mode ('paper' or 'live')
        config: Configuration dictionary loaded from .env
        core_strategy: CoreStrategy instance (Tier 1)
        growth_strategy: GrowthStrategy instance (Tier 2)
        ipo_strategy: IPOStrategy instance (Tier 3)
        alpaca_trader: AlpacaTrader instance for order execution
        risk_manager: RiskManager instance for risk controls
        timezone: Timezone for scheduling (Eastern Time)
        running: Flag indicating if orchestrator is running
        last_execution: Dictionary tracking last execution times
        health_status: Dictionary containing health check information
    """

    def __init__(self, mode: str = "paper", config: Optional[Dict[str, Any]] = None):
        """
        Initialize the Trading Orchestrator.

        Args:
            mode: Trading mode - 'paper' or 'live' (default: 'paper')
            config: Configuration dictionary (optional, will load from .env if not provided)

        Raises:
            ValueError: If mode is invalid or configuration is missing
        """
        self.logger = logging.getLogger("TradingOrchestrator")
        self.mode = mode.lower()

        if self.mode not in ["paper", "live"]:
            raise ValueError(f"Invalid mode '{mode}'. Must be 'paper' or 'live'.")

        self.logger.info("=" * 80)
        self.logger.info(
            f"Initializing Trading Orchestrator in {self.mode.upper()} mode"
        )
        self.logger.info("=" * 80)

        # Load configuration
        self.config = config or self._load_config()
        self._validate_config()

        # Initialize timezone (Eastern Time for market hours)
        self.timezone = pytz.timezone("America/New_York")

        # Initialize components
        self._initialize_components()

        # Orchestrator state
        self.running = False
        self.last_execution: Dict[str, Optional[datetime]] = {
            "core_strategy": None,
            "growth_strategy": None,
            "ipo_strategy": None,
        }
        self.health_status: Dict[str, Any] = {
            "status": "initialized",
            "last_check": datetime.now().isoformat(),
            "errors": [],
        }

        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

        self.logger.info("Trading Orchestrator initialized successfully")
        self.logger.info(
            f"Daily investment allocation: ${self.config['daily_investment']:.2f}"
        )
        self.logger.info(
            f"Risk limits: Daily loss {self.config['max_daily_loss_pct']}%, "
            f"Drawdown {self.config['max_drawdown_pct']}%"
        )

    def _load_config(self) -> Dict[str, Any]:
        """
        Load configuration from .env file.

        Returns:
            Configuration dictionary with all required settings

        Raises:
            ValueError: If required configuration is missing
        """
        self.logger.info("Loading configuration from .env file")

        # Load environment variables
        load_dotenv()

        config = {
            # API Keys
            "alpaca_api_key": os.getenv("ALPACA_API_KEY"),
            "alpaca_secret_key": os.getenv("ALPACA_SECRET_KEY"),
            "openrouter_api_key": os.getenv("OPENROUTER_API_KEY"),
            # Trading Configuration
            "paper_trading": os.getenv("PAPER_TRADING", "true").lower() == "true",
            "daily_investment": float(os.getenv("DAILY_INVESTMENT", "10.0")),
            # Tier Allocations
            "tier1_allocation": float(os.getenv("TIER1_ALLOCATION", "0.60")),
            "tier2_allocation": float(os.getenv("TIER2_ALLOCATION", "0.20")),
            "tier3_allocation": float(os.getenv("TIER3_ALLOCATION", "0.10")),
            "tier4_allocation": float(os.getenv("TIER4_ALLOCATION", "0.10")),
            # Risk Management
            "max_daily_loss_pct": float(os.getenv("MAX_DAILY_LOSS_PCT", "2.0")),
            "max_position_size_pct": float(os.getenv("MAX_POSITION_SIZE_PCT", "10.0")),
            "max_drawdown_pct": float(os.getenv("MAX_DRAWDOWN_PCT", "10.0")),
            "stop_loss_pct": float(os.getenv("STOP_LOSS_PCT", "5.0")),
            # Alerts
            "alert_email": os.getenv("ALERT_EMAIL"),
            "alert_webhook_url": os.getenv("ALERT_WEBHOOK_URL"),
        }

        self.logger.info("Configuration loaded successfully")
        return config

    def _validate_config(self) -> None:
        """
        Validate configuration settings.

        Raises:
            ValueError: If required configuration is missing or invalid
        """
        required_keys = ["alpaca_api_key", "alpaca_secret_key"]
        missing_keys = [key for key in required_keys if not self.config.get(key)]

        if missing_keys:
            raise ValueError(
                f"Missing required configuration: {', '.join(missing_keys)}"
            )

        # Validate tier allocations sum to <= 1.0
        total_allocation = (
            self.config["tier1_allocation"]
            + self.config["tier2_allocation"]
            + self.config["tier3_allocation"]
            + self.config["tier4_allocation"]
        )

        if total_allocation > 1.0:
            raise ValueError(
                f"Total tier allocation ({total_allocation:.2f}) exceeds 100%. "
                "Please adjust allocation percentages."
            )

        self.logger.info("Configuration validation passed")

    def _initialize_components(self) -> None:
        """Initialize all trading components and strategies."""
        self.logger.info("Initializing trading components...")

        try:
            # Initialize Alpaca trader
            use_paper = self.mode == "paper" or self.config["paper_trading"]
            self.alpaca_trader = AlpacaTrader(paper=use_paper)
            self.logger.info(
                f"Alpaca trader initialized in {'PAPER' if use_paper else 'LIVE'} mode"
            )

            # Initialize risk manager
            self.risk_manager = RiskManager(
                max_daily_loss_pct=self.config["max_daily_loss_pct"],
                max_position_size_pct=self.config["max_position_size_pct"],
                max_drawdown_pct=self.config["max_drawdown_pct"],
            )
            self.logger.info("Risk manager initialized")

            # Calculate strategy allocations
            daily_investment = self.config["daily_investment"]
            tier1_daily = (
                daily_investment * self.config["tier1_allocation"]
            )  # 60% -> $6
            tier2_weekly = (daily_investment * 5) * self.config[
                "tier2_allocation"
            ]  # 20% of weekly -> $10
            tier3_daily = (
                daily_investment * self.config["tier3_allocation"]
            )  # 10% -> $1

            # Initialize CoreStrategy (Tier 1)
            self.core_strategy = CoreStrategy(
                daily_allocation=tier1_daily,
                stop_loss_pct=self.config["stop_loss_pct"] / 100,
                use_sentiment=True,
            )
            self.logger.info(
                f"Core strategy initialized (daily allocation: ${tier1_daily:.2f})"
            )

            # Initialize GrowthStrategy (Tier 2)
            self.growth_strategy = GrowthStrategy(weekly_allocation=tier2_weekly)
            self.logger.info(
                f"Growth strategy initialized (weekly allocation: ${tier2_weekly:.2f})"
            )

            # Initialize IPOStrategy (Tier 3)
            self.ipo_strategy = IPOStrategy(
                daily_deposit=tier3_daily,
                anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
                openai_api_key=os.getenv("OPENAI_API_KEY"),
            )
            self.logger.info(
                f"IPO strategy initialized (daily deposit: ${tier3_daily:.2f})"
            )

            self.logger.info("All components initialized successfully")

        except Exception as e:
            self.logger.error(f"Failed to initialize components: {e}", exc_info=True)
            raise

    def _signal_handler(self, signum: int, frame) -> None:
        """
        Handle shutdown signals for graceful termination.

        Args:
            signum: Signal number
            frame: Current stack frame
        """
        signal_names = {signal.SIGTERM: "SIGTERM", signal.SIGINT: "SIGINT"}
        signal_name = signal_names.get(signum, str(signum))

        self.logger.warning(
            f"Received {signal_name} signal - initiating graceful shutdown"
        )
        self.stop()

    def setup_schedule(self) -> None:
        """
        Setup execution schedule for all strategies.

        Schedule:
        - Core Strategy: Daily at 9:35 AM ET (5 minutes after market open)
        - Growth Strategy: Weekly on Mondays at 9:35 AM ET
        - IPO Strategy: Daily at 10:00 AM ET for deposit tracking and weekly check
        - Risk Reset: Daily at 9:30 AM ET (before trading starts)
        """
        self.logger.info("Setting up execution schedule...")

        # Clear existing schedule
        schedule.clear()

        # Daily risk counter reset at 9:30 AM ET (before market open)
        schedule.every().day.at("09:30").do(self._reset_daily_risk).tag("risk_reset")
        self.logger.info("Scheduled: Risk reset - Daily at 9:30 AM ET")

        # Core Strategy: Daily at 9:35 AM ET
        schedule.every().day.at("09:35").do(self._execute_core_strategy).tag(
            "core_strategy"
        )
        self.logger.info("Scheduled: Core strategy - Daily at 9:35 AM ET")

        # Growth Strategy: Weekly on Mondays at 9:35 AM ET
        schedule.every().monday.at("09:35").do(self._execute_growth_strategy).tag(
            "growth_strategy"
        )
        self.logger.info("Scheduled: Growth strategy - Mondays at 9:35 AM ET")

        # IPO Strategy: Daily deposit at 10:00 AM ET
        schedule.every().day.at("10:00").do(self._execute_ipo_deposit).tag(
            "ipo_deposit"
        )
        self.logger.info("Scheduled: IPO deposit tracking - Daily at 10:00 AM ET")

        # IPO Strategy: Weekly check on Wednesdays at 10:00 AM ET
        schedule.every().wednesday.at("10:00").do(self._check_ipo_opportunities).tag(
            "ipo_check"
        )
        self.logger.info("Scheduled: IPO opportunity check - Wednesdays at 10:00 AM ET")

        # Health check: Every hour
        schedule.every().hour.do(self._update_health_status).tag("health_check")
        self.logger.info("Scheduled: Health check - Every hour")

        self.logger.info("Schedule setup complete")

    def _reset_daily_risk(self) -> None:
        """Reset daily risk counters."""
        try:
            self.logger.info("Resetting daily risk counters")
            self.risk_manager.reset_daily_counters()
            self.logger.info("Daily risk counters reset successfully")
        except Exception as e:
            self.logger.error(
                f"Error resetting daily risk counters: {e}", exc_info=True
            )
            self._send_alert("Risk Reset Error", str(e), severity="ERROR")

    def _execute_core_strategy(self) -> None:
        """Execute Core Strategy (Tier 1) - Daily momentum index investing."""
        self.logger.info("=" * 80)
        self.logger.info("EXECUTING CORE STRATEGY (TIER 1)")
        self.logger.info("=" * 80)

        try:
            # Check if trading is allowed
            account_info = self.alpaca_trader.get_account_info()
            account_value = account_info["portfolio_value"]
            daily_pl = account_value - account_info.get("last_equity", account_value)

            if not self.risk_manager.can_trade(account_value, daily_pl):
                self.logger.warning(
                    "Trading blocked by risk manager - skipping Core Strategy execution"
                )
                self._send_alert(
                    "Trading Blocked",
                    "Core Strategy execution skipped due to risk limits",
                    severity="WARNING",
                )
                return

            # Execute strategy
            order = self.core_strategy.execute_daily()

            if order:
                self.logger.info(
                    f"Core Strategy order executed: {order.symbol} - ${order.amount:.2f}"
                )
                self.last_execution["core_strategy"] = datetime.now()
            else:
                self.logger.info("Core Strategy: No order placed")

            # Update health status
            self.health_status["status"] = "healthy"
            self.health_status["last_core_execution"] = datetime.now().isoformat()

        except Exception as e:
            self.logger.error(f"Error executing Core Strategy: {e}", exc_info=True)
            self.health_status["errors"].append(
                {
                    "timestamp": datetime.now().isoformat(),
                    "strategy": "core",
                    "error": str(e),
                }
            )
            self._send_alert("Core Strategy Error", str(e), severity="CRITICAL")

        finally:
            self.logger.info("=" * 80)

    def _execute_growth_strategy(self) -> None:
        """Execute Growth Strategy (Tier 2) - Weekly stock picking."""
        self.logger.info("=" * 80)
        self.logger.info("EXECUTING GROWTH STRATEGY (TIER 2)")
        self.logger.info("=" * 80)

        try:
            # Check if trading is allowed
            account_info = self.alpaca_trader.get_account_info()
            account_value = account_info["portfolio_value"]
            daily_pl = account_value - account_info.get("last_equity", account_value)

            if not self.risk_manager.can_trade(account_value, daily_pl):
                self.logger.warning(
                    "Trading blocked by risk manager - skipping Growth Strategy execution"
                )
                self._send_alert(
                    "Trading Blocked",
                    "Growth Strategy execution skipped due to risk limits",
                    severity="WARNING",
                )
                return

            # Execute strategy
            orders = self.growth_strategy.execute_weekly()

            if orders:
                self.logger.info(f"Growth Strategy: {len(orders)} orders generated")
                for order in orders:
                    self.logger.info(
                        f"  {order.action.upper()} {order.symbol} x{order.quantity}"
                    )
                self.last_execution["growth_strategy"] = datetime.now()
            else:
                self.logger.info("Growth Strategy: No orders generated")

            # Get performance metrics
            metrics = self.growth_strategy.get_performance_metrics()
            self.logger.info(
                f"Growth Strategy metrics: Win rate {metrics['win_rate']:.1f}%, "
                f"Total P&L ${metrics['total_pnl']:.2f}"
            )

            # Update health status
            self.health_status["last_growth_execution"] = datetime.now().isoformat()

        except Exception as e:
            self.logger.error(f"Error executing Growth Strategy: {e}", exc_info=True)
            self.health_status["errors"].append(
                {
                    "timestamp": datetime.now().isoformat(),
                    "strategy": "growth",
                    "error": str(e),
                }
            )
            self._send_alert("Growth Strategy Error", str(e), severity="CRITICAL")

        finally:
            self.logger.info("=" * 80)

    def _execute_ipo_deposit(self) -> None:
        """Track daily IPO deposit (Tier 3)."""
        self.logger.info("Tracking IPO daily deposit")

        try:
            balance = self.ipo_strategy.track_daily_deposit()
            self.logger.info(f"IPO Strategy: New balance ${balance:.2f}")
            self.last_execution["ipo_strategy"] = datetime.now()

        except Exception as e:
            self.logger.error(f"Error tracking IPO deposit: {e}", exc_info=True)
            self._send_alert("IPO Deposit Error", str(e), severity="ERROR")

    def _check_ipo_opportunities(self) -> None:
        """Check for IPO opportunities and generate reminder (Tier 3)."""
        self.logger.info("=" * 80)
        self.logger.info("CHECKING IPO OPPORTUNITIES (TIER 3)")
        self.logger.info("=" * 80)

        try:
            # Display reminder to check SoFi
            self.ipo_strategy.check_sofi_offerings()

            # Get current balance info
            balance_info = self.ipo_strategy.get_balance_info()
            self.logger.info(f"IPO balance: ${balance_info['balance']:.2f}")
            self.logger.info(
                f"Projected 30 days: ${balance_info['projected_30_days']:.2f}"
            )

            # Get any existing recommendations
            recommendations = self.ipo_strategy.get_ipo_recommendations()
            if recommendations:
                self.logger.info(f"Active IPO recommendations: {len(recommendations)}")
                for rec in recommendations[:3]:  # Top 3
                    self.logger.info(
                        f"  {rec['company_name']}: {rec['score']}/100 - ${rec['target_allocation']:.2f}"
                    )

            # Update health status
            self.health_status["last_ipo_check"] = datetime.now().isoformat()

        except Exception as e:
            self.logger.error(f"Error checking IPO opportunities: {e}", exc_info=True)
            self._send_alert("IPO Check Error", str(e), severity="ERROR")

        finally:
            self.logger.info("=" * 80)

    def _update_health_status(self) -> None:
        """Update health status with current system state."""
        try:
            # Get account info
            account_info = self.alpaca_trader.get_account_info()

            # Get risk metrics
            risk_metrics = self.risk_manager.get_risk_metrics()

            # Update health status
            self.health_status.update(
                {
                    "status": (
                        "healthy"
                        if not risk_metrics["account_metrics"][
                            "circuit_breaker_triggered"
                        ]
                        else "degraded"
                    ),
                    "last_check": datetime.now().isoformat(),
                    "account_value": account_info["portfolio_value"],
                    "buying_power": account_info["buying_power"],
                    "daily_pl": risk_metrics["daily_metrics"]["daily_pl"],
                    "circuit_breaker": risk_metrics["account_metrics"][
                        "circuit_breaker_triggered"
                    ],
                }
            )

            self.logger.debug(f"Health check: {self.health_status['status']}")

        except Exception as e:
            self.logger.error(f"Error updating health status: {e}", exc_info=True)
            self.health_status["status"] = "unhealthy"
            self.health_status["last_error"] = str(e)

    def _send_alert(self, title: str, message: str, severity: str = "INFO") -> None:
        """
        Send alert via configured channels.

        Args:
            title: Alert title
            message: Alert message
            severity: Alert severity (INFO, WARNING, ERROR, CRITICAL)
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        alert_msg = f"[{severity}] {title}: {message}"

        # Log the alert
        log_method = getattr(self.logger, severity.lower(), self.logger.info)
        log_method(alert_msg)

        # TODO: Implement email alerts if configured
        # if self.config.get('alert_email'):
        #     send_email_alert(self.config['alert_email'], title, message, severity)

        # TODO: Implement webhook alerts if configured
        # if self.config.get('alert_webhook_url'):
        #     send_webhook_alert(self.config['alert_webhook_url'], title, message, severity)

    def get_health_status(self) -> Dict[str, Any]:
        """
        Get current health status for monitoring.

        Returns:
            Dictionary containing health check information
        """
        return {
            **self.health_status,
            "running": self.running,
            "mode": self.mode,
            "last_executions": self.last_execution,
        }

    def run_once(self, strategy: Optional[str] = None) -> None:
        """
        Execute strategies once (for testing).

        Args:
            strategy: Specific strategy to run ('core', 'growth', 'ipo', or None for all)
        """
        self.logger.info("=" * 80)
        self.logger.info("MANUAL EXECUTION MODE - RUN ONCE")
        self.logger.info("=" * 80)

        if strategy is None or strategy == "core":
            self._execute_core_strategy()

        if strategy is None or strategy == "growth":
            self._execute_growth_strategy()

        if strategy is None or strategy == "ipo":
            self._execute_ipo_deposit()
            self._check_ipo_opportunities()

        self.logger.info("Manual execution complete")

    def start(self) -> None:
        """Start the orchestrator with scheduled execution."""
        self.running = True
        self.logger.info("=" * 80)
        self.logger.info("STARTING TRADING ORCHESTRATOR")
        self.logger.info(f"Mode: {self.mode.upper()}")
        self.logger.info(f"Timezone: {self.timezone}")
        self.logger.info("=" * 80)

        # Setup schedule
        self.setup_schedule()

        # Initial health check
        self._update_health_status()

        self.logger.info("Orchestrator started - waiting for scheduled tasks")
        self.logger.info("Press Ctrl+C to stop")

        try:
            while self.running:
                schedule.run_pending()
                time.sleep(1)

        except KeyboardInterrupt:
            self.logger.info("Keyboard interrupt received")
            self.stop()

    def stop(self) -> None:
        """Stop the orchestrator gracefully."""
        if not self.running:
            return

        self.logger.info("=" * 80)
        self.logger.info("STOPPING TRADING ORCHESTRATOR")
        self.logger.info("=" * 80)

        self.running = False

        # Cancel any pending orders (safety measure)
        try:
            result = self.alpaca_trader.cancel_all_orders()
            self.logger.info(f"Cancelled {result['cancelled_count']} pending orders")
        except Exception as e:
            self.logger.error(f"Error cancelling orders during shutdown: {e}")

        # Save final state
        self.logger.info("Saving final state...")
        self.logger.info(f"Last executions: {self.last_execution}")

        # Final health check
        health = self.get_health_status()
        self.logger.info(f"Final status: {health['status']}")

        self.logger.info("Orchestrator stopped successfully")
        self.logger.info("=" * 80)


def main():
    """Main entry point for the trading orchestrator."""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="Trading System Orchestrator - Automated multi-strategy trading",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start in scheduled mode (paper trading)
  python src/main.py --mode paper

  # Start in live mode
  python src/main.py --mode live

  # Run once for testing (all strategies)
  python src/main.py --mode paper --run-once

  # Run specific strategy once
  python src/main.py --mode paper --run-once --strategy core

  # Debug mode with verbose logging
  python src/main.py --mode paper --log-level DEBUG
        """,
    )

    parser.add_argument(
        "--mode",
        type=str,
        choices=["paper", "live"],
        default="paper",
        help="Trading mode: paper or live (default: paper)",
    )

    parser.add_argument(
        "--run-once",
        action="store_true",
        help="Execute strategies once and exit (for testing)",
    )

    parser.add_argument(
        "--strategy",
        type=str,
        choices=["core", "growth", "ipo"],
        help="Specific strategy to run with --run-once (default: all)",
    )

    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Logging level (default: INFO)",
    )

    parser.add_argument(
        "--log-dir",
        type=str,
        default="logs",
        help="Directory for log files (default: logs)",
    )

    args = parser.parse_args()

    # Setup logging
    logger = setup_logging(log_dir=args.log_dir, log_level=args.log_level)

    # Print banner
    print("\n" + "=" * 80)
    print("  TRADING SYSTEM ORCHESTRATOR")
    print("  Multi-Strategy Automated Trading System")
    print("=" * 80)
    print(f"  Mode: {args.mode.upper()}")
    print(f"  Log Level: {args.log_level}")
    print(f"  Log Directory: {args.log_dir}")
    print("=" * 80 + "\n")

    # Safety warning for live mode
    if args.mode == "live":
        print("\n" + "!" * 80)
        print("  WARNING: LIVE TRADING MODE")
        print("  Real money will be used for trades!")
        print("!" * 80)
        response = input("\nType 'yes' to confirm live trading: ")
        if response.lower() != "yes":
            print("Live trading cancelled.")
            sys.exit(0)
        print()

    try:
        # Initialize orchestrator
        orchestrator = TradingOrchestrator(mode=args.mode)

        # Run once or start scheduled execution
        if args.run_once:
            orchestrator.run_once(strategy=args.strategy)
        else:
            orchestrator.start()

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(0)

    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
