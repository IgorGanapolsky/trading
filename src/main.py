"""
Trading System Orchestrator - Legacy Entry Point (DEPRECATED)

DEPRECATION NOTICE:
- This scheduler-based orchestrator is deprecated.
- Canonical entry point is `scripts/autonomous_trader.py`, which boots the
  new hybrid funnel orchestrator in `src/orchestrator/main.py` and writes
  structured telemetry to `data/audit_trail/hybrid_funnel_runs.jsonl`.

This module remains for backward compatibility and will be removed after the
R&D phase. Please migrate any invocations to the canonical entry.

The legacy orchestrator manages:
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

import logging as _logging  # Added for deprecation warning on import

_logging.getLogger(__name__).warning(
    "src/main.py is deprecated. Use scripts/autonomous_trader.py (hybrid funnel)."
)

import argparse
import logging
import os
import signal
import sys
import time
from datetime import date, datetime, timedelta
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

import pytz
import schedule
from dotenv import load_dotenv

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agent_framework import RunContext  # noqa: E402
from src.core.alpaca_trader import AlpacaTrader  # noqa: E402
from src.core.risk_manager import RiskManager  # noqa: E402
from src.core.skills_integration import get_skills  # noqa: E402
from src.deepagents_integration.adapter import (
    create_analysis_agent_adapter,
)  # noqa: E402
from src.orchestration.adk_integration import (
    ADKTradeAdapter,
    summarize_adk_decision,
)  # noqa: E402
from src.orchestration.elite_orchestrator import EliteOrchestrator  # noqa: E402
from src.strategies.core_strategy import CoreStrategy  # noqa: E402
from src.strategies.growth_strategy import GrowthStrategy  # noqa: E402
from src.strategies.ipo_strategy import IPOStrategy  # noqa: E402
from src.strategies.options_strategy import OptionsStrategy  # noqa: E402


# Helper function to save trades to daily trade files
def save_trade_to_daily_file(trade_data: dict[str, Any], data_dir: Path = Path("data")) -> None:
    """
    Save trade to daily trade file (trades_YYYY-MM-DD.json).

    Args:
        trade_data: Dictionary containing trade information
        data_dir: Data directory path (default: data/)
    """
    import json

    today = date.today().isoformat()
    trade_file = data_dir / f"trades_{today}.json"

    # Load existing trades for today
    trades = []
    if trade_file.exists():
        try:
            with open(trade_file) as f:
                trades = json.load(f)
                if not isinstance(trades, list):
                    trades = [trades] if trades else []
        except Exception:
            trades = []

    # Add new trade
    trades.append(trade_data)

    # Save updated trades
    try:
        with open(trade_file, "w") as f:
            json.dump(trades, f, indent=2, default=str)
    except Exception as e:
        logging.getLogger(__name__).error(f"Failed to save trade to daily file: {e}")


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
        options_strategy: OptionsStrategy instance (Yield Generation)
        alpaca_trader: AlpacaTrader instance for order execution
        risk_manager: RiskManager instance for risk controls
        timezone: Timezone for scheduling (Eastern Time)
        running: Flag indicating if orchestrator is running
        last_execution: Dictionary tracking last execution times
        health_status: Dictionary containing health check information
    """

    def __init__(self, mode: str = "paper", config: dict[str, Any] | None = None):
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
        self.logger.info(f"Initializing Trading Orchestrator in {self.mode.upper()} mode")
        self.logger.info("=" * 80)

        # Load configuration
        self.config = config or self._load_config()
        self._validate_config()

        # Initialize timezone (Eastern Time for market hours)
        self.timezone = pytz.timezone("America/New_York")

        # Initialize components
        self.adk_adapter: ADKTradeAdapter | None = None
        self.deepagents_adapter: Any | None = None
        self.skills = get_skills()  # Initialize Claude Skills

        # Elite Orchestrator (planning-first multi-agent system)
        # ENABLED BY DEFAULT per CEO directive Nov 24, 2025
        elite_enabled = os.getenv("ELITE_ORCHESTRATOR_ENABLED", "true").lower() == "true"
        self.elite_orchestrator: EliteOrchestrator | None = None

        # Autonomous Meta-Agents
        self.trace_analysis_agent = None
        self.chaos_orchestrator_agent = None

        if elite_enabled:
            try:
                self.elite_orchestrator = EliteOrchestrator(
                    paper=self.mode == "paper" or self.config["paper_trading"],
                    enable_planning=True,
                )
                self.logger.info("✅ Elite Orchestrator initialized")

                # Initialize Meta-Agents
                from src.agents.chaos_orchestrator_agent import ChaosOrchestratorAgent
                from src.agents.trace_analysis_agent import TraceAnalysisAgent

                self.trace_analysis_agent = TraceAnalysisAgent()
                self.chaos_orchestrator_agent = ChaosOrchestratorAgent()
                self.logger.info(
                    "✅ Autonomous Meta-Agents initialized (TraceAnalysis, ChaosOrchestrator)"
                )

            except Exception as e:
                self.logger.warning(f"⚠️ Elite Orchestrator/Agents unavailable: {e}")
                self.logger.warning("⚠️ Falling back to individual agent systems")

        # Initialize RL Inference (MLPredictor) - Load independently if Elite Orchestrator disabled
        self.ml_predictor = None
        if not elite_enabled:
            try:
                from src.ml.inference import MLPredictor

                self.ml_predictor = MLPredictor()
                self.logger.info("✅ RL Inference (MLPredictor) initialized independently")
            except Exception as e:
                self.logger.warning(f"⚠️ RL Inference unavailable: {e}")

        # Initialize Workflow Agent (for end-of-day reporting)
        self.workflow_agent = None
        try:
            from src.agents.workflow_agent import WorkflowAgent

            self.workflow_agent = WorkflowAgent()
            self.logger.info("✅ WorkflowAgent initialized")
        except Exception as e:
            self.logger.warning(f"⚠️ WorkflowAgent unavailable: {e}")

        # Initialize Notification Agent (for trade alerts)
        self.notification_agent = None
        try:
            from src.agents.notification_agent import NotificationAgent

            self.notification_agent = NotificationAgent()
            self.logger.info("✅ NotificationAgent initialized")
        except Exception as e:
            self.logger.warning(f"⚠️ NotificationAgent unavailable: {e}")

        # Initialize Approval Agent (for high-value trades)
        self.approval_agent = None
        try:
            from src.agents.approval_agent import ApprovalAgent

            self.approval_agent = ApprovalAgent()
            self.logger.info("✅ ApprovalAgent initialized")
        except Exception as e:
            self.logger.warning(f"⚠️ ApprovalAgent unavailable: {e}")

        self._initialize_components()

        # Orchestrator state
        self.running = False
        self.last_execution: dict[str, datetime | None] = {
            "core_strategy": None,
            "growth_strategy": None,
            "ipo_strategy": None,
            "options_strategy": None,
            "options_accumulation": None,
        }
        self.health_status: dict[str, Any] = {
            "status": "initialized",
            "last_check": datetime.now().isoformat(),
            "errors": [],
        }

        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

        self.logger.info("Trading Orchestrator initialized successfully")
        self.logger.info(f"Daily investment allocation: ${self.config['daily_investment']:.2f}")
        self.logger.info(
            f"Risk limits: Daily loss {self.config['max_daily_loss_pct']}%, "
            f"Drawdown {self.config['max_drawdown_pct']}%"
        )

    def _load_config(self) -> dict[str, Any]:
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
            "daily_investment": float(
                os.getenv("DAILY_INVESTMENT", "10.0")
            ),  # Aligned with config.py default
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
            raise ValueError(f"Missing required configuration: {', '.join(missing_keys)}")

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

            # Use Portfolio Risk Assessment skill for enhanced health checks
            if self.skills.portfolio_risk_assessor:
                self.logger.info("✅ Using Portfolio Risk Assessment skill")
            else:
                self.logger.warning(
                    "⚠️ Portfolio Risk Assessment skill not available, using RiskManager only"
                )

            # Calculate strategy allocations
            daily_investment = self.config["daily_investment"]
            tier1_daily = daily_investment * self.config["tier1_allocation"]  # 60% -> $6
            tier2_weekly = (daily_investment * 5) * self.config[
                "tier2_allocation"
            ]  # 20% of weekly -> $10
            tier3_daily = daily_investment * self.config["tier3_allocation"]  # 10% -> $1

            # Initialize CoreStrategy (Tier 1)
            # VCA Configuration
            use_vca = os.getenv("USE_VCA", "false").lower() == "true"
            vca_target_growth_rate = (
                float(os.getenv("VCA_TARGET_GROWTH_RATE", "0.10"))
                if os.getenv("VCA_TARGET_GROWTH_RATE")
                else None
            )
            vca_max_adjustment = (
                float(os.getenv("VCA_MAX_ADJUSTMENT", "2.0"))
                if os.getenv("VCA_MAX_ADJUSTMENT")
                else None
            )
            vca_min_adjustment = (
                float(os.getenv("VCA_MIN_ADJUSTMENT", "0.3"))
                if os.getenv("VCA_MIN_ADJUSTMENT")
                else None
            )

            self.core_strategy = CoreStrategy(
                daily_allocation=tier1_daily,
                stop_loss_pct=self.config["stop_loss_pct"] / 100,
                use_sentiment=True,
                use_vca=use_vca,
                vca_target_growth_rate=vca_target_growth_rate,
                vca_max_adjustment=vca_max_adjustment,
                vca_min_adjustment=vca_min_adjustment,
            )
            allocation_mode = "VCA" if use_vca else "DCA"
            self.logger.info(
                f"Core strategy initialized ({allocation_mode} mode, daily allocation: ${tier1_daily:.2f})"
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
            self.logger.info(f"IPO strategy initialized (daily deposit: ${tier3_daily:.2f})")

            # Initialize OptionsStrategy (Yield Generation)
            self.options_strategy = OptionsStrategy(paper=use_paper)
            self.logger.info("Options strategy initialized (Covered Calls)")

            # Initialize Options Accumulation Strategy (NVDA focus)
            try:
                from src.strategies.options_accumulation_strategy import OptionsAccumulationStrategy

                self.options_accumulation_strategy = OptionsAccumulationStrategy(paper=use_paper)
                self.logger.info("Options accumulation strategy initialized (NVDA focus)")
            except Exception as e:
                self.logger.warning(f"Failed to initialize options accumulation strategy: {e}")
                self.options_accumulation_strategy = None

            # Initialize ADK orchestrator adapter
            adk_enabled_env = os.getenv("ADK_ENABLED", "1").lower()
            adk_enabled = adk_enabled_env not in {"0", "false", "off", "no"}
            self.adk_adapter = ADKTradeAdapter(
                enabled=adk_enabled,
                base_url=os.getenv("ADK_BASE_URL"),
                app_name=os.getenv("ADK_APP_NAME"),
                root_agent_name=os.getenv("ADK_ROOT_AGENT"),
                user_id=os.getenv("ADK_USER_ID"),
            )
            if self.adk_adapter.enabled:
                self.logger.info(
                    "ADK orchestrator client initialized (base_url=%s)",
                    self.adk_adapter.client.config.base_url,
                )  # type: ignore[union-attr]
            else:
                self.logger.info("ADK orchestrator integration disabled via ADK_ENABLED=0")

            # Initialize DeepAgents adapter
            # ENABLED BY DEFAULT per CEO directive Nov 24, 2025
            deepagents_enabled_env = os.getenv("DEEPAGENTS_ENABLED", "true").lower()
            deepagents_enabled = deepagents_enabled_env not in {
                "0",
                "false",
                "off",
                "no",
            }
            if deepagents_enabled:
                try:
                    self.deepagents_adapter = create_analysis_agent_adapter(
                        agent_name="deepagents-market-analysis"
                    )
                    self.logger.info("DeepAgents market analysis adapter initialized")
                except Exception as e:
                    self.logger.warning(
                        f"Failed to initialize DeepAgents (will fall back to core strategy): {e}"
                    )
                    self.deepagents_adapter = None
            else:
                self.logger.info("DeepAgents integration disabled via DEEPAGENTS_ENABLED=false")

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

        self.logger.warning(f"Received {signal_name} signal - initiating graceful shutdown")
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

        # Core Strategy: Daily at 10:00 AM ET (30 min after open - lower volatility)
        schedule.every().day.at("10:00").do(self._execute_core_strategy).tag("core_strategy")
        self.logger.info("Scheduled: Core strategy - Daily at 10:00 AM ET")

        # Growth Strategy: Weekly on Mondays at 9:35 AM ET
        schedule.every().monday.at("09:35").do(self._execute_growth_strategy).tag("growth_strategy")
        self.logger.info("Scheduled: Growth strategy - Mondays at 9:35 AM ET")

        # IPO Strategy: Daily deposit at 10:00 AM ET
        schedule.every().day.at("10:00").do(self._execute_ipo_deposit).tag("ipo_deposit")
        self.logger.info("Scheduled: IPO deposit tracking - Daily at 10:00 AM ET")

        # IPO Strategy: Weekly check on Wednesdays at 10:00 AM ET
        schedule.every().wednesday.at("10:00").do(self._check_ipo_opportunities).tag("ipo_check")
        self.logger.info("Scheduled: IPO opportunity check - Wednesdays at 10:00 AM ET")

        # Options Accumulation Strategy: Daily at 9:40 AM ET (before options strategy)
        if self.options_accumulation_strategy:
            schedule.every().day.at("09:40").do(self._execute_options_accumulation).tag(
                "options_accumulation"
            )
            self.logger.info("Scheduled: Options accumulation strategy - Daily at 9:40 AM ET")

        # Options Strategy: Daily at 10:30 AM ET
        schedule.every().day.at("10:30").do(self._execute_options_strategy).tag("options_strategy")
        self.logger.info("Scheduled: Options strategy - Daily at 10:30 AM ET")

        # Health check: Every hour
        schedule.every().hour.do(self._update_health_status).tag("health_check")

        # Daily performance monitoring using Performance Monitor skill
        schedule.every().day.at("16:00").do(self._daily_performance_monitoring).tag(
            "performance_monitoring"
        )

        # End-of-day workflow (daily reporting)
        if self.workflow_agent:
            schedule.every().day.at("16:30").do(self._execute_end_of_day_workflow).tag(
                "end_of_day_workflow"
            )
            self.logger.info("Scheduled: End-of-Day Workflow - Daily at 4:30 PM ET")

        # Autonomous Meta-Agents Schedule
        if self.trace_analysis_agent:
            # Analyze traces daily after market close
            schedule.every().day.at("17:00").do(self.trace_analysis_agent.analyze).tag(
                "trace_analysis"
            )
            self.logger.info("Scheduled: Trace Analysis - Daily at 5:00 PM ET")

        if self.chaos_orchestrator_agent:
            # Evaluate chaos drills weekly on Fridays
            schedule.every().friday.at("14:00").do(self.chaos_orchestrator_agent.analyze).tag(
                "chaos_orchestration"
            )
            self.logger.info("Scheduled: Chaos Orchestration - Fridays at 2:00 PM ET")

        self.logger.info("Scheduled: Health check - Every hour")

        self.logger.info("Schedule setup complete")

    def _reset_daily_risk(self) -> None:
        """Reset daily risk counters."""
        try:
            self.logger.info("Resetting daily risk counters")
            self.risk_manager.reset_daily_counters()
            self.logger.info("Daily risk counters reset successfully")
        except Exception as e:
            self.logger.error(f"Error resetting daily risk counters: {e}", exc_info=True)
            self._send_alert("Risk Reset Error", str(e), severity="ERROR")

    def _execute_core_strategy_with_deepagents(self, account_info: dict[str, Any]) -> bool:
        """
        Attempt to execute the core strategy via DeepAgents planning-based agent.

        Returns True when the decision loop is fully handled by DeepAgents (either
        trade executed or intentionally skipped). Returning False indicates the
        caller should fall back to the legacy Python strategy.
        """
        if not self.deepagents_adapter:
            return False

        try:
            # Prepare context for DeepAgents
            symbols_str = ", ".join(self.core_strategy.etf_universe)
            query = f"""Analyze the following ETFs for today's trading opportunity: {symbols_str}

Account Context:
- Portfolio Value: ${account_info.get("portfolio_value", 0):.2f}
- Available Cash: ${account_info.get("cash", 0):.2f}
- Buying Power: ${account_info.get("buying_power", 0):.2f}
- Daily Allocation: ${self.core_strategy.daily_allocation:.2f}

Risk Limits:
- Max Daily Loss: {self.config["max_daily_loss_pct"]}%
- Max Position Size: {self.config["max_position_size_pct"]}%
- Max Drawdown: {self.config["max_drawdown_pct"]}%
- Stop Loss: {self.config["stop_loss_pct"]}%

Instructions:
1. Fetch market data and technical indicators for each ETF
2. Analyze sentiment if available
3. Identify the best trading opportunity (or recommend HOLD if none)
4. Provide a structured trade recommendation with:
   - Symbol and action (BUY/SELL/HOLD)
   - Position size recommendation (not exceeding daily allocation)
   - Entry price target
   - Stop loss and take profit levels
   - Conviction score (0-1)
   - Risk assessment
   - Supporting reasoning

Output your recommendation in JSON format for easy parsing."""

            # Build context for agent framework
            context = RunContext(
                config={
                    "query": query,
                    "symbols": self.core_strategy.etf_universe,
                    "mode": self.mode,
                    "account": account_info,
                    "risk_limits": {
                        "max_daily_loss_pct": self.config["max_daily_loss_pct"],
                        "max_position_size_pct": self.config["max_position_size_pct"],
                        "max_drawdown_pct": self.config["max_drawdown_pct"],
                        "stop_loss_pct": self.config["stop_loss_pct"],
                    },
                    "daily_allocation": self.core_strategy.daily_allocation,
                },
                state={},
            )

            # Execute DeepAgents analysis
            self.logger.info("Executing DeepAgents market analysis for core strategy")
            result = self.deepagents_adapter.execute(context)

            if not result.succeeded:
                self.logger.error(f"DeepAgents analysis failed: {result.error}")
                return False

            # Parse the recommendation from DeepAgents response
            response = result.payload.get("response", {})
            self.logger.info(f"DeepAgents analysis complete: {response}")

            # For now, log the recommendation but don't execute
            # In a future iteration, we can parse the JSON response and execute the trade
            # This allows the system to validate DeepAgents output before trusting it with real trades
            self.logger.info(
                "DeepAgents provided analysis (execution not yet implemented - falling back to core strategy)"
            )
            self.health_status["last_deepagents_analysis"] = datetime.now().isoformat()
            self.health_status["deepagents_response"] = str(response)[:500]  # Store first 500 chars

            # Return False to fall back to core strategy for actual execution
            # This ensures DeepAgents is running and providing insights without risking execution bugs
            return False

        except Exception as exc:
            self.logger.error("DeepAgents evaluation failed: %s", exc, exc_info=True)
            return False

    def _execute_core_strategy_with_adk(self, account_info: dict[str, Any]) -> bool:
        """
        Attempt to execute the core strategy via the Go ADK orchestrator.

        Returns True when the decision loop is fully handled by ADK (either
        trade executed or intentionally skipped). Returning False indicates the
        caller should fall back to the legacy Python strategy.
        """
        if not self.adk_adapter or not self.adk_adapter.enabled:
            return False

        try:
            context = {
                "mode": self.mode,
                "account": {
                    "portfolio_value": account_info.get("portfolio_value"),
                    "cash": account_info.get("cash"),
                    "buying_power": account_info.get("buying_power"),
                },
                "risk_limits": {
                    "max_daily_loss_pct": self.config["max_daily_loss_pct"],
                    "max_position_size_pct": self.config["max_position_size_pct"],
                    "max_drawdown_pct": self.config["max_drawdown_pct"],
                    "stop_loss_pct": self.config["stop_loss_pct"],
                },
                "daily_allocation": self.core_strategy.daily_allocation,
            }
            decision = self.adk_adapter.evaluate(
                symbols=self.core_strategy.etf_universe,
                context=context,
            )
        except Exception as exc:
            self.logger.error("ADK evaluation failed: %s", exc, exc_info=True)
            return False

        if not decision:
            return False

        if decision.risk.get("decision", "").upper() == "REVIEW":
            self.logger.warning(
                "ADK risk agent requested review for %s; deferring to legacy strategy",
                decision.symbol,
            )
            return False

        trade_amount = decision.position_size or self.core_strategy.daily_allocation
        if trade_amount <= 0:
            trade_amount = self.core_strategy.daily_allocation
        trade_amount = min(trade_amount, self.core_strategy.daily_allocation * 3)

        side = "buy" if decision.action == "BUY" else "sell"
        try:
            executed = self.alpaca_trader.execute_order(
                symbol=decision.symbol,
                amount_usd=trade_amount,
                side=side,
                tier="T1_CORE_ADK",
            )
            summary = summarize_adk_decision(decision)
            self.logger.info(
                "ADK %s order executed id=%s amount=$%.2f summary=%s",
                side.upper(),
                executed.get("id"),
                trade_amount,
                summary,
            )
            self.health_status["last_core_execution"] = datetime.now().isoformat()
            self.health_status["adk_summary"] = summary
            self.last_execution["core_strategy"] = datetime.now()

            # Save trade to daily file
            try:
                trade_data = {
                    "symbol": decision.symbol,
                    "side": side,
                    "amount": trade_amount,
                    "order_id": executed.get("id"),
                    "tier": "T1_CORE_ADK",
                    "timestamp": datetime.now().isoformat(),
                    "filled_at": executed.get("filled_at"),
                    "filled_avg_price": executed.get("filled_avg_price"),
                    "filled_qty": executed.get("filled_qty"),
                    "status": executed.get("status"),
                }
                save_trade_to_daily_file(trade_data)
            except Exception as e:
                self.logger.warning(f"Failed to save ADK trade to daily file: {e}")

            return True
        except Exception as exc:
            self.logger.error("ADK order execution failed: %s", exc, exc_info=True)
            self._send_alert(
                "ADK Execution Error",
                f"{decision.symbol} {decision.action}: {exc}",
                severity="ERROR",
            )
            return False

    def _check_trade_staleness(self) -> None:
        """Check for stale trades - detects silent automation failures."""
        try:
            # Import StateManager
            sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
            from state_manager import StateManager

            state_mgr = StateManager()
            staleness = state_mgr.check_trade_staleness()

            if staleness["status"] == "ERROR":
                self.logger.error(f"TRADE STALENESS ERROR: {staleness['message']}")
                if staleness["recommended_action"]:
                    self.logger.error(f"ACTION REQUIRED: {staleness['recommended_action']}")
                self._send_alert(
                    "Trade Staleness Alert",
                    f"{staleness['message']}\n\nAction: {staleness['recommended_action']}",
                    severity="CRITICAL",
                )
            elif staleness["status"] == "WARNING":
                self.logger.warning(f"TRADE STALENESS WARNING: {staleness['message']}")
                if staleness["recommended_action"]:
                    self.logger.warning(f"RECOMMENDED: {staleness['recommended_action']}")
            else:
                self.logger.info(f"Trade staleness check: {staleness['message']}")

        except Exception as e:
            self.logger.error(f"Error checking trade staleness: {e}", exc_info=True)

    def _execute_core_strategy(self) -> None:
        """Execute Core Strategy (Tier 1) - Daily momentum index investing."""
        self.logger.info("=" * 80)
        self.logger.info("EXECUTING CORE STRATEGY (TIER 1)")
        self.logger.info("=" * 80)

        try:
            # FIRST: Check for stale trades (detects silent failures)
            self._check_trade_staleness()

            # Check if trading is allowed
            account_info = self.alpaca_trader.get_account_info()
            account_value = account_info["portfolio_value"]
            daily_pl = account_value - account_info.get("last_equity", account_value)

            # Use Portfolio Risk Assessment skill for enhanced health check
            if self.skills.portfolio_risk_assessor:
                health_result = self.skills.assess_portfolio_health()
                if (
                    health_result.get("success")
                    and health_result.get("data", {}).get("overall_status") == "HALTED"
                ):
                    self.logger.warning("Trading halted by Portfolio Risk Assessment skill")
                    self._send_alert(
                        "Trading Halted",
                        "Portfolio health check failed - trading halted",
                        severity="CRITICAL",
                    )
                    return

            if not self.risk_manager.can_trade(account_value, daily_pl, account_info):
                self.logger.warning(
                    "Trading blocked by risk manager - skipping Core Strategy execution"
                )
                self._send_alert(
                    "Trading Blocked",
                    "Core Strategy execution skipped due to risk limits",
                    severity="WARNING",
                )
                return

            # Try Elite Orchestrator first (planning-first multi-agent system)
            if self.elite_orchestrator:
                try:
                    elite_result = self.elite_orchestrator.run_trading_cycle(
                        symbols=["SPY", "QQQ", "VOO"]
                    )
                    if elite_result.get("final_decision") == "TRADE_EXECUTED":
                        self.logger.info("Core Strategy satisfied via Elite Orchestrator")
                        self.last_execution["core_strategy"] = datetime.now()
                        return
                except Exception as e:
                    self.logger.warning(f"Elite Orchestrator execution failed: {e}")

            # Try DeepAgents first (planning-based agent with sub-agent delegation)
            if self._execute_core_strategy_with_deepagents(account_info):
                self.logger.info("Core Strategy satisfied via DeepAgents")
                return

            # Try ADK orchestrator next
            if self._execute_core_strategy_with_adk(account_info):
                self.logger.info("Core Strategy satisfied via ADK orchestrator")
                return

            # Use RL inference (MLPredictor) if available and Elite Orchestrator not enabled
            if self.ml_predictor and not self.elite_orchestrator:
                try:
                    # Get RL signal for each symbol in ETF universe
                    rl_signals = {}
                    for symbol in self.core_strategy.etf_universe:
                        try:
                            signal = self.ml_predictor.get_signal(symbol)
                            rl_signals[symbol] = signal
                            self.logger.debug(
                                f"RL signal for {symbol}: {signal.get('action')} (confidence: {signal.get('confidence', 0):.2f})"
                            )
                        except Exception as e:
                            self.logger.warning(f"Failed to get RL signal for {symbol}: {e}")

                    # Filter symbols by RL confidence (only consider BUY signals with confidence > 0.6)
                    high_confidence_symbols = [
                        sym
                        for sym, sig in rl_signals.items()
                        if sig.get("action") == "BUY" and sig.get("confidence", 0) > 0.6
                    ]

                    if high_confidence_symbols:
                        self.logger.info(
                            f"RL inference identified {len(high_confidence_symbols)} high-confidence opportunities: {high_confidence_symbols}"
                        )
                        # Note: RL signal is advisory - still use core strategy for execution
                except Exception as e:
                    self.logger.warning(f"RL inference failed: {e}")

            # Execute strategy
            order = self.core_strategy.execute_daily()

            if order:
                self.logger.info(
                    f"Core Strategy order executed: {order.symbol} - ${order.amount:.2f}"
                )
                self.last_execution["core_strategy"] = datetime.now()

                # Save trade to daily file
                try:
                    trade_data = {
                        "symbol": order.symbol,
                        "side": "buy",
                        "amount": order.amount,
                        "tier": "T1_CORE",
                        "timestamp": datetime.now().isoformat(),
                        "price": getattr(order, "fill_price", None),
                        "quantity": getattr(order, "quantity", None),
                    }
                    save_trade_to_daily_file(trade_data)
                except Exception as e:
                    self.logger.warning(f"Failed to save trade to daily file: {e}")

                # Send trade notification
                if self.notification_agent:
                    try:
                        trade_data = {
                            "symbol": order.symbol,
                            "side": (
                                "buy"
                                if hasattr(order, "action") and order.action == "BUY"
                                else "buy"
                            ),
                            "quantity": getattr(
                                order,
                                "quantity",
                                order.amount / getattr(order, "fill_price", order.amount),
                            ),
                            "price": getattr(order, "fill_price", order.amount),
                            "amount": order.amount,
                            "tier": "T1_CORE",
                            "timestamp": datetime.now().isoformat(),
                        }
                        self.notification_agent.send_trade_alert(trade_data)
                    except Exception as e:
                        self.logger.warning(f"Failed to send trade notification: {e}")

                # Check if approval needed for high-value trades
                if self.approval_agent and order.amount >= self.approval_agent.high_value_threshold:
                    try:
                        approval_result = self.approval_agent._request_approval(
                            {
                                "approval_type": "trade",
                                "context": {
                                    "symbol": order.symbol,
                                    "trade_value": order.amount,
                                    "side": "buy",
                                    "tier": "T1_CORE",
                                },
                                "priority": ("high" if order.amount >= 5000 else "medium"),
                            }
                        )
                        if approval_result.get("approval_required"):
                            self.logger.info(
                                f"High-value trade approval requested: {approval_result.get('approval_id')}"
                            )
                    except Exception as e:
                        self.logger.warning(f"Failed to request approval: {e}")

                # Use Anomaly Detector skill to monitor execution quality
                if (
                    self.skills.anomaly_detector
                    and hasattr(order, "fill_price")
                    and order.fill_price
                ):
                    anomaly_result = self.skills.detect_execution_anomalies(
                        order_id=str(order.id) if hasattr(order, "id") else "unknown",
                        expected_price=(
                            order.price if hasattr(order, "price") else order.fill_price
                        ),
                        actual_fill_price=order.fill_price,
                        quantity=(
                            order.quantity
                            if hasattr(order, "quantity")
                            else order.amount / order.fill_price
                        ),
                        order_type="market",
                        timestamp=datetime.now().isoformat(),
                    )
                    if anomaly_result.get("success"):
                        analysis = anomaly_result.get("analysis", {})
                        if analysis.get("anomalies_detected"):
                            self.logger.warning(
                                f"Execution anomalies detected: {analysis.get('warnings', [])}"
                            )
                            self._send_alert(
                                "Execution Anomaly",
                                f"Anomalies detected in order execution: {analysis.get('warnings', [])}",
                                severity="WARNING",
                            )
                        else:
                            self.logger.info(
                                f"Execution quality: {analysis.get('execution_quality', {}).get('grade', 'N/A')}"
                            )
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

            # Send error notification
            if self.notification_agent:
                try:
                    self.notification_agent.send_risk_alert(
                        {
                            "alert_type": "strategy_error",
                            "message": f"Core Strategy execution failed: {str(e)}",
                            "severity": "critical",
                            "strategy": "core",
                        }
                    )
                except Exception as e2:
                    self.logger.warning(f"Failed to send error notification: {e2}")

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

            # Use Portfolio Risk Assessment skill for enhanced health check
            if self.skills.portfolio_risk_assessor:
                health_result = self.skills.assess_portfolio_health()
                if (
                    health_result.get("success")
                    and health_result.get("data", {}).get("overall_status") == "HALTED"
                ):
                    self.logger.warning("Trading halted by Portfolio Risk Assessment skill")
                    self._send_alert(
                        "Trading Halted",
                        "Portfolio health check failed - trading halted",
                        severity="CRITICAL",
                    )
                    return

            if not self.risk_manager.can_trade(account_value, daily_pl, account_info):
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
                    self.logger.info(f"  {order.action.upper()} {order.symbol} x{order.quantity}")
                    # Save trade to daily file
                    try:
                        trade_data = {
                            "symbol": order.symbol,
                            "side": (order.action.lower() if hasattr(order, "action") else "buy"),
                            "amount": getattr(
                                order,
                                "amount",
                                getattr(order, "quantity", 0) * getattr(order, "price", 0),
                            ),
                            "tier": "T2_GROWTH",
                            "timestamp": datetime.now().isoformat(),
                            "price": getattr(order, "price", None),
                            "quantity": getattr(order, "quantity", None),
                        }
                        save_trade_to_daily_file(trade_data)
                    except Exception as e:
                        self.logger.warning(f"Failed to save growth trade to daily file: {e}")
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

    def _execute_options_accumulation(self) -> None:
        """Execute Options Accumulation Strategy (NVDA focus)."""
        self.logger.info("=" * 80)
        self.logger.info("EXECUTING OPTIONS ACCUMULATION STRATEGY")
        self.logger.info("=" * 80)

        if not self.options_accumulation_strategy:
            self.logger.warning("Options accumulation strategy not initialized")
            return

        try:
            result = self.options_accumulation_strategy.execute_daily()

            if result:
                action = result.get("action")
                if action == "purchased":
                    self.logger.info(
                        f"✅ Options accumulation: Purchased {result.get('shares_purchased', 0):.4f} shares"
                    )
                    status_after = result.get("status_after", {})
                    self.logger.info(
                        f"Progress: {status_after.get('progress_pct', 0):.1f}% "
                        f"({status_after.get('current_shares', 0):.2f}/{status_after.get('target_shares', 50)} shares)"
                    )
                elif action == "complete":
                    self.logger.info("✅ Options accumulation target reached!")
                    self.logger.info("Covered calls can now be activated")
                elif action in ["failed", "error"]:
                    self.logger.warning(
                        f"Options accumulation {action}: {result.get('error', 'Unknown error')}"
                    )

            self.last_execution["options_accumulation"] = datetime.now()
            self.health_status["last_options_accumulation"] = datetime.now().isoformat()

        except Exception as e:
            self.logger.error(f"Error executing Options Accumulation Strategy: {e}", exc_info=True)
            self.health_status["errors"].append(
                {
                    "timestamp": datetime.now().isoformat(),
                    "strategy": "options_accumulation",
                    "error": str(e),
                }
            )

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
            self.logger.info(f"Projected 30 days: ${balance_info['projected_30_days']:.2f}")

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

    def _execute_end_of_day_workflow(self) -> None:
        """Execute end-of-day workflow for daily reporting."""
        self.logger.info("=" * 80)
        self.logger.info("EXECUTING END-OF-DAY WORKFLOW")
        self.logger.info("=" * 80)

        if not self.workflow_agent:
            self.logger.warning("WorkflowAgent not available - skipping end-of-day workflow")
            return

        try:
            # Get account info
            account_info = self.alpaca_trader.get_account_info()

            # Get performance metrics
            perf_data = {}
            if self.skills.performance_monitor:
                try:
                    end_date = datetime.now().strftime("%Y-%m-%d")
                    start_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
                    perf_result = self.skills.get_performance_metrics(
                        start_date=start_date, end_date=end_date
                    )
                    if perf_result.get("success"):
                        perf_data = perf_result
                except Exception as e:
                    self.logger.warning(f"Failed to get performance metrics: {e}")

            # Generate daily report workflow
            workflow_result = self.workflow_agent.analyze(
                {
                    "type": "report_generation",
                    "report_type": "daily",
                    "recipients": (
                        [self.config.get("alert_email")] if self.config.get("alert_email") else []
                    ),
                    "context": {
                        "account_value": account_info.get("portfolio_value", 0),
                        "daily_pl": account_info.get("portfolio_value", 0)
                        - account_info.get("last_equity", account_info.get("portfolio_value", 0)),
                        "cash": account_info.get("cash", 0),
                        "buying_power": account_info.get("buying_power", 0),
                        "performance_metrics": perf_data,
                        "last_executions": {
                            "core_strategy": (
                                self.last_execution.get("core_strategy").isoformat()
                                if self.last_execution.get("core_strategy")
                                else None
                            ),
                            "growth_strategy": (
                                self.last_execution.get("growth_strategy").isoformat()
                                if self.last_execution.get("growth_strategy")
                                else None
                            ),
                            "ipo_strategy": (
                                self.last_execution.get("ipo_strategy").isoformat()
                                if self.last_execution.get("ipo_strategy")
                                else None
                            ),
                        },
                        "health_status": self.health_status,
                    },
                }
            )

            if workflow_result.get("success"):
                self.logger.info(
                    f"✅ End-of-day workflow completed: {workflow_result.get('result')}"
                )
                if workflow_result.get("report_path"):
                    self.logger.info(f"   Report saved to: {workflow_result.get('report_path')}")
            else:
                self.logger.warning(f"⚠️ End-of-day workflow failed: {workflow_result.get('error')}")

        except Exception as e:
            self.logger.error(f"Error executing end-of-day workflow: {e}", exc_info=True)

        finally:
            self.logger.info("=" * 80)

    def _update_health_status(self) -> None:
        """Update health status with current system state."""
        try:
            # Get account info
            account_info = self.alpaca_trader.get_account_info()

            # Use Portfolio Risk Assessment skill if available
            if self.skills.portfolio_risk_assessor:
                health_result = self.skills.assess_portfolio_health()
                if health_result.get("success"):
                    health_data = health_result.get("data", {})
                    self.health_status.update(
                        {
                            "status": health_data.get("overall_status", "unknown").lower(),
                            "last_check": datetime.now().isoformat(),
                            "account_value": health_data.get(
                                "account_equity", account_info["portfolio_value"]
                            ),
                            "buying_power": health_data.get(
                                "buying_power", account_info["buying_power"]
                            ),
                            "daily_pl": health_data.get("daily_pl", 0),
                            "circuit_breaker": health_data.get("circuit_breakers", {}).get(
                                "should_halt_trading", False
                            ),
                            "risk_score": health_data.get("risk_score", 0),
                        }
                    )
                    self.logger.debug(f"Health check (via skill): {self.health_status['status']}")
                    return

            # Fallback to RiskManager if skill not available
            risk_metrics = self.risk_manager.get_risk_metrics()

            # Update health status
            self.health_status.update(
                {
                    "status": (
                        "healthy"
                        if not risk_metrics["account_metrics"]["circuit_breaker_triggered"]
                        else "degraded"
                    ),
                    "last_check": datetime.now().isoformat(),
                    "account_value": account_info["portfolio_value"],
                    "buying_power": account_info["buying_power"],
                    "daily_pl": risk_metrics["daily_metrics"]["daily_pl"],
                    "circuit_breaker": risk_metrics["account_metrics"]["circuit_breaker_triggered"],
                }
            )

            self.logger.debug(f"Health check: {self.health_status['status']}")

        except Exception as e:
            self.logger.error(f"Error updating health status: {e}", exc_info=True)
            self.health_status["status"] = "unhealthy"
            self.health_status["last_error"] = str(e)

    def _daily_performance_monitoring(self) -> None:
        """Daily performance monitoring using Performance Monitor skill."""
        self.logger.info("=" * 80)
        self.logger.info("DAILY PERFORMANCE MONITORING")
        self.logger.info("=" * 80)

        try:
            if not self.skills.performance_monitor:
                self.logger.warning("Performance Monitor skill not available")
                return

            # Calculate performance metrics for last 30 days
            end_date = datetime.now().strftime("%Y-%m-%d")
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

            perf_result = self.skills.get_performance_metrics(
                start_date=start_date, end_date=end_date, benchmark_symbol="SPY"
            )

            if perf_result.get("success"):
                metrics = perf_result
                returns = metrics.get("returns", {})
                risk_metrics = metrics.get("risk_metrics", {})
                trade_stats = metrics.get("trade_statistics", {})

                self.logger.info("Performance Metrics (30 days):")
                self.logger.info(f"  Total Return: {returns.get('total_return_pct', 0):.2f}%")
                self.logger.info(f"  Sharpe Ratio: {risk_metrics.get('sharpe_ratio', 0):.2f}")
                self.logger.info(
                    f"  Max Drawdown: {risk_metrics.get('max_drawdown', 0) * 100:.2f}%"
                )
                self.logger.info(f"  Win Rate: {trade_stats.get('win_rate', 0) * 100:.1f}%")
                self.logger.info(f"  Total Trades: {trade_stats.get('total_trades', 0)}")

                # Store in health status
                self.health_status["performance_metrics"] = {
                    "last_update": datetime.now().isoformat(),
                    "sharpe_ratio": risk_metrics.get("sharpe_ratio", 0),
                    "win_rate": trade_stats.get("win_rate", 0),
                    "total_return_pct": returns.get("total_return_pct", 0),
                }

                # Alert if performance is below targets
                if risk_metrics.get("sharpe_ratio", 0) < 1.5:
                    self._send_alert(
                        "Performance Below Target",
                        f"Sharpe ratio {risk_metrics.get('sharpe_ratio', 0):.2f} below target of 1.5",
                        severity="WARNING",
                    )

            else:
                self.logger.warning(
                    f"Performance monitoring failed: {perf_result.get('error', 'Unknown error')}"
                )

        except Exception as e:
            self.logger.error(f"Error in daily performance monitoring: {e}", exc_info=True)

        finally:
            self.logger.info("=" * 80)

    def _send_alert(self, title: str, message: str, severity: str = "INFO") -> None:
        """
        Send alert via configured channels.

        Args:
            title: Alert title
            message: Alert message
            severity: Alert severity (INFO, WARNING, ERROR, CRITICAL)
        """
        alert_msg = f"[{severity}] {title}: {message}"

        # Log the alert
        log_method = getattr(self.logger, severity.lower(), self.logger.info)
        log_method(alert_msg)

        # Send via NotificationAgent if available
        if self.notification_agent:
            try:
                priority_map = {
                    "INFO": "low",
                    "WARNING": "medium",
                    "ERROR": "high",
                    "CRITICAL": "critical",
                }
                self.notification_agent.analyze(
                    {
                        "message": f"{title}: {message}",
                        "channels": ["email", "dashboard", "log"],
                        "priority": priority_map.get(severity, "medium"),
                        "type": "alert",
                        "context": {"title": title, "severity": severity},
                    }
                )
            except Exception as e:
                self.logger.warning(f"Failed to send alert via NotificationAgent: {e}")

        # TODO: Implement email alerts if configured
        # if self.config.get('alert_email'):
        #     send_email_alert(self.config['alert_email'], title, message, severity)

        # TODO: Implement webhook alerts if configured
        # if self.config.get('alert_webhook_url'):
        #     send_webhook_alert(self.config['alert_webhook_url'], title, message, severity)

    def get_health_status(self) -> dict[str, Any]:
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

    def run_once(self, strategy: str | None = None) -> None:
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

    def _execute_options_strategy(self) -> None:
        """Execute Options Strategy (Yield Generation) - Covered Calls."""
        self.logger.info("=" * 80)
        self.logger.info("EXECUTING OPTIONS STRATEGY (YIELD GENERATION)")
        self.logger.info("=" * 80)

        try:
            # Execute strategy
            results = self.options_strategy.execute_daily()

            if results:
                self.logger.info(f"Options Strategy found {len(results)} opportunities")
                for res in results:
                    self.logger.info(
                        f"Proposed: Sell {res['contracts']}x {res['option_symbol']} "
                        f"(Strike: ${res['strike']:.2f}, Premium: ${res['premium']:.2f})"
                    )
                    # Note: Auto-execution is currently disabled in the strategy for safety.
                    # In the future, we can enable it here or via an approval gate.
            else:
                self.logger.info("Options Strategy: No opportunities found")

            self.last_execution["options_strategy"] = datetime.now()
            self.health_status["last_options_execution"] = datetime.now().isoformat()

        except Exception as e:
            self.logger.error(f"Error executing Options Strategy: {e}", exc_info=True)
            self.health_status["errors"].append(
                {
                    "timestamp": datetime.now().isoformat(),
                    "strategy": "options",
                    "error": str(e),
                }
            )
