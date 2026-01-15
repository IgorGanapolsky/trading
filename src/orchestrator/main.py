"""Hybrid funnel orchestrator (Momentum → RL → LLM → Risk)."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from src.agents.macro_agent import MacroeconomicAgent
from src.agents.momentum_agent import MomentumAgent
from src.agents.rl_agent import RLFilter
from src.analyst.bias_store import BiasProvider, BiasSnapshot, BiasStore
from src.execution.alpaca_executor import AlpacaExecutor
from src.integrations.playwright_mcp import SentimentScraper, TradeVerifier
from src.learning.trade_memory import TradeMemory

# LLM sentiment handled by Gate 3 with BiasProvider
from src.orchestrator.anomaly_monitor import AnomalyMonitor
from src.orchestrator.budget import BudgetController
from src.orchestrator.failure_isolation import FailureIsolationManager
from src.orchestrator.gates import (
    Gate0Psychology,
    Gate1Momentum,
    Gate2RLFilter,
    Gate3Sentiment,
    Gate4Risk,
    Gate5Execution,
    Gate15Debate,
    Gate35Introspection,
    GateMemory,
    GateSecurity,
    RAGPreTradeQuery,
    TradeMemoryQuery,
    TradingGatePipeline,
)
from src.orchestrator.options_coordinator import OptionsStrategyCoordinator
from src.orchestrator.parallel_processor import (
    ParallelProcessingResult,
    ParallelTickerProcessor,
    TickerOutcome,
    create_thread_safe_wrapper,
)
from src.orchestrator.session_manager import SessionManager
from src.orchestrator.smart_dca import SmartDCAAllocator
from src.orchestrator.telemetry import OrchestratorTelemetry
from src.risk.capital_efficiency import get_capital_calculator
from src.risk.options_risk_monitor import OptionsRiskMonitor
from src.risk.position_manager import ExitConditions, PositionManager
from src.risk.risk_manager import RiskManager
from src.risk.trade_gateway import RejectionReason, TradeGateway, TradeRequest
from src.signals.microstructure_features import MicrostructureFeatureExtractor
from src.utils.heartbeat import record_heartbeat
from src.utils.regime_detector import RegimeDetector
from src.utils.staleness_guard import check_data_staleness

# Bull/Bear Debate Agents - Multi-perspective analysis (Dec 2025)
# Based on UCLA/MIT TradingAgents research showing 42% CAGR improvement
try:
    from src.agents.debate_agents import DebateModerator

    DEBATE_AVAILABLE = True
except ImportError:
    DEBATE_AVAILABLE = False

# RAG Retriever - Historical context for trading decisions (Dec 2025)
try:
    from src.rag.vector_db.retriever import get_retriever

    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False

# Lessons Learned RAG - Learn from past mistakes (Dec 2025)
# Query lessons before trading to avoid repeating errors
try:
    from src.rag.lessons_learned_rag import LessonsLearnedRAG

    LESSONS_RAG_AVAILABLE = True
except ImportError:
    LESSONS_RAG_AVAILABLE = False

# Introspective awareness imports (Dec 2025)
try:
    # NOTE: Keep optional import pattern without triggering ruff F401.
    # We intentionally avoid importing unused callables just to test availability.
    import importlib.util

    from src.core.introspective_council import IntrospectiveCouncil

    INTROSPECTION_AVAILABLE = True
except ImportError:
    INTROSPECTION_AVAILABLE = False

if INTROSPECTION_AVAILABLE:
    # Optional module presence check (keeps behavior without unused imports).
    _UNCERTAINTY_TRACKER_AVAILABLE = (
        importlib.util.find_spec("src.core.uncertainty_tracker") is not None
    )

# Observability: Vertex AI RAG + Local logs (Jan 9, 2026)

# Go ADK Multi-Agent Trading Orchestrator (Dec 2025)
# Provides Gemini-powered research/signal/risk/execution agents
# See: go/adk_trading/ for the Go implementation
try:
    from src.orchestration.adk_integration import ADKTradeAdapter, summarize_adk_decision

    ADK_AVAILABLE = True
except ImportError:
    ADK_AVAILABLE = False

logger = logging.getLogger(__name__)

# is_us_market_day imported from session_manager


class TradingOrchestrator:
    """
    Implements the four-gate funnel:

        Gate 1 - Momentum (math, free)
        Gate 2 - RL filter (local inference)
        Gate 3 - LLM analyst (budgeted)
        Gate 4 - Risk sizing (hard rules)
    """

    def __init__(self, tickers: list[str], paper: bool = True) -> None:
        self.tickers = [ticker.strip().upper() for ticker in tickers if ticker.strip()]
        if not self.tickers:
            raise ValueError("At least one ticker symbol is required.")

        # Persist execution mode; some gates/logging reference self.paper.
        self.paper = paper

        import os as _os

        self.macro_agent = MacroeconomicAgent()
        self.momentum_agent = MomentumAgent(
            min_score=float(_os.getenv("MOMENTUM_MIN_SCORE", "0.0"))
        )

        # Jan 10, 2026: DISABLED RL FILTER (CEO directive - reduce complexity)
        # Evidence: 1,601 lines of RL code, 0 trades using it
        # With $30 portfolio, RL has nothing to learn from
        # Re-enable when: portfolio >= $500 AND trades being executed
        self.rl_filter_enabled = _os.getenv("RL_FILTER_ENABLED", "false").lower() in {
            "1",
            "true",
            "yes",
        }
        self.llm_sentiment_enabled = _os.getenv("LLM_SENTIMENT_ENABLED", "true").lower() in {
            "1",
            "true",
            "yes",
        }

        # Dec 2025: Parallel ticker processing (ADK Fan-Out/Gather pattern)
        # Reduces latency from O(n) to O(1) for n tickers
        self.parallel_processing_enabled = _os.getenv(
            "PARALLEL_TICKER_PROCESSING", "true"
        ).lower() in {"1", "true", "yes"}
        self.parallel_max_workers = int(_os.getenv("PARALLEL_MAX_WORKERS", "5"))
        self.parallel_processor: ParallelTickerProcessor | None = None  # Lazy init

        # Only initialize if enabled (saves memory and API costs)
        if self.rl_filter_enabled:
            self.rl_filter = RLFilter()
            logger.info("Gate 2: RLFilter ENABLED")
        else:
            self.rl_filter = None
            logger.info("Gate 2: RLFilter DISABLED (simplification mode)")

        # LangChain agent removed - was stub returning hardcoded neutral sentiment
        # LLM sentiment now uses BiasProvider with real data
        self.llm_agent = None
        if self.llm_sentiment_enabled:
            logger.info("Gate 3: LLM Sentiment via BiasProvider (LangChain stub removed)")
        else:
            logger.info("Gate 3: LLM Sentiment DISABLED (simplification mode)")
        # Playwright MCP for dynamic sentiment scraping and trade verification
        self.playwright_scraper = SentimentScraper()
        self.trade_verifier = TradeVerifier(paper_trading=paper)
        self.budget_controller = BudgetController()
        self.risk_manager = RiskManager()
        self.executor = AlpacaExecutor(paper=paper)
        self.executor.sync_portfolio_state()
        self.telemetry = OrchestratorTelemetry()
        self.anomaly_monitor = AnomalyMonitor(
            telemetry=self.telemetry,
            window=int(os.getenv("ANOMALY_WINDOW", "40")),
            rejection_threshold=float(os.getenv("ANOMALY_REJECTION_THRESHOLD", "0.8")),
            confidence_floor=float(os.getenv("ANOMALY_CONFIDENCE_FLOOR", "0.45")),
        )
        self.failure_manager = FailureIsolationManager(self.telemetry)
        self.options_risk_monitor = OptionsRiskMonitor()
        # CRITICAL: All trades must go through the gateway - no direct executor calls
        self.trade_gateway = TradeGateway(executor=self.executor, paper=paper)
        # Capital efficiency calculator - determines what strategies are viable
        self.capital_calculator = get_capital_calculator(daily_deposit_rate=10.0)
        self.session_profile: dict[str, Any] | None = None
        # Mental coach disabled - class not implemented (Jan 15, 2026 fix)
        self.mental_coach = None

        # Jan 10, 2026: Extracted classes for cleaner architecture
        # OptionsStrategyCoordinator handles Gate 6/7 (options strategies)
        self.options_coordinator = OptionsStrategyCoordinator(
            executor=self.executor,
            options_risk_monitor=self.options_risk_monitor,
            telemetry=self.telemetry,
            paper=paper,
        )
        # SessionManager handles session profiles and market day detection
        self.session_manager = SessionManager(
            default_tickers=self.tickers,
            weekend_proxy_symbols=os.getenv("WEEKEND_PROXY_SYMBOLS", "BITO,RWCR"),
        )
        self.microstructure = MicrostructureFeatureExtractor()
        self.regime_detector = RegimeDetector()
        self.smart_dca = SmartDCAAllocator()

        # Gate 0.5: Bull/Bear Debate - Multi-perspective analysis (Dec 2025)
        # Based on UCLA/MIT TradingAgents research showing 42% CAGR improvement
        self.debate_moderator: DebateModerator | None = None
        enable_debate = os.getenv("ENABLE_BULL_BEAR_DEBATE", "true").lower() in {
            "1",
            "true",
            "yes",
        }
        if enable_debate and DEBATE_AVAILABLE:
            try:
                self.debate_moderator = DebateModerator()
                logger.info(
                    "Gate 0.5: Bull/Bear DebateModerator initialized (reduces confirmation bias)"
                )
            except Exception as e:
                logger.warning(f"DebateModerator init failed: {e}")

        # RAG Retriever - Historical context for trading decisions (Dec 2025)
        self.rag_retriever = None
        enable_rag = os.getenv("ENABLE_RAG_CONTEXT", "true").lower() in {
            "1",
            "true",
            "yes",
        }
        if enable_rag and RAG_AVAILABLE:
            try:
                self.rag_retriever = get_retriever()
                logger.info("RAG Retriever initialized (historical context for trading decisions)")
            except Exception as e:
                logger.warning(f"RAG Retriever init failed: {e}")

        # Lessons Learned RAG - Query past mistakes before trading (Dec 2025)
        self.lessons_rag: LessonsLearnedRAG | None = None
        enable_lessons = os.getenv("ENABLE_LESSONS_RAG", "true").lower() in {
            "1",
            "true",
            "yes",
        }
        if enable_lessons and LESSONS_RAG_AVAILABLE:
            try:
                self.lessons_rag = LessonsLearnedRAG()
                logger.info(
                    "Lessons Learned RAG initialized (%d lessons loaded)",
                    len(self.lessons_rag.lessons) if self.lessons_rag.lessons else 0,
                )
                # Connect anomaly monitor to RAG for feedback loop
                # Anomalies → Lessons → RAG → Future Trade Decisions
                self.anomaly_monitor.lessons_rag = self.lessons_rag
                logger.info("Anomaly→Lesson feedback loop connected")
            except Exception as e:
                logger.warning(f"Lessons Learned RAG init failed: {e}")

        bias_dir = os.getenv("BIAS_DATA_DIR", "data/bias")
        self.bias_store = BiasStore(bias_dir)
        # Position manager for active exit management (Updated Dec 17, 2025)
        # Research: 5% targets too tight, positions closed before trends developed
        self.position_manager = PositionManager(
            conditions=ExitConditions(
                take_profit_pct=float(os.getenv("TAKE_PROFIT_PCT", "0.15")),  # 15% (was 5%)
                stop_loss_pct=float(os.getenv("STOP_LOSS_PCT", "0.08")),  # 8% (was 5%)
                max_holding_days=int(os.getenv("MAX_HOLDING_DAYS", "30")),  # 30 days (was 14)
                enable_momentum_exit=os.getenv("ENABLE_MOMENTUM_EXIT", "false").lower()
                in {"1", "true"},  # DISABLED: MACD reversal causes false exits in sideways markets
                enable_atr_stop=os.getenv("ENABLE_ATR_STOP", "true").lower() in {"1", "true"},
                atr_multiplier=float(os.getenv("ATR_MULTIPLIER", "2.5")),  # 2.5x ATR (was 2.0)
            )
        )
        self.bias_fresh_minutes = int(os.getenv("BIAS_FRESHNESS_MINUTES", "90"))
        self.bias_snapshot_ttl_minutes = int(
            os.getenv("BIAS_TTL_MINUTES", str(max(self.bias_fresh_minutes, 360)))
        )
        enable_async_analyst = os.getenv("ENABLE_ASYNC_ANALYST", "true").lower() in {
            "1",
            "true",
            "yes",
        }
        self.bias_provider: BiasProvider | None = None
        if enable_async_analyst:
            self.bias_provider = BiasProvider(
                self.bias_store,
                freshness=timedelta(minutes=self.bias_fresh_minutes),
            )

        # Gate 3.5: Introspective Awareness (Dec 2025 - Anthropic research)
        # NOTE: Disabled - MultiLLMAnalyzer removed in favor of other analysis methods
        self.introspective_council: IntrospectiveCouncil | None = None
        self.uncertainty_tracker = None
        logger.info("Gate 3.5: IntrospectiveCouncil disabled (MultiLLMAnalyzer removed)")

        # Go ADK Multi-Agent Adapter (Dec 2025)
        # Provides Gemini-powered multi-agent analysis: research → signal → risk → execution
        # Uses google.golang.org/adk with 4 specialized sub-agents
        self.adk_adapter: ADKTradeAdapter | None = None
        enable_adk = os.getenv("ENABLE_ADK_AGENTS", "true").lower() in {"1", "true", "yes"}
        if enable_adk and ADK_AVAILABLE:
            try:
                self.adk_adapter = ADKTradeAdapter(enabled=True)
                logger.info(
                    "Go ADK Multi-Agent Adapter initialized (research/signal/risk/execution)"
                )
            except Exception as e:
                logger.warning(f"Go ADK adapter init failed (will use Python-only pipeline): {e}")

        # Gate 0: Mental Toughness Coach (CEO FIX Jan 15, 2026)
        # Mental coach feature not yet implemented - set to None to skip Gate0Psychology checks
        # Gate0Psychology.evaluate() gracefully handles None mental_coach
        self.mental_coach = None
        logger.info("Gate 0: Mental coach disabled (feature not implemented)")

        # Initialize LLM-friendly gate pipeline (Dec 2025 refactor)
        # Each gate is <150 lines, independently testable
        self._init_gate_pipeline()

    def _init_gate_pipeline(self) -> None:
        """Initialize the decomposed trading gate pipeline."""
        # Gate S: Security validation - MUST run first (Dec 24, 2025)
        # Protects against prompt injection in external data
        self.gate_security = GateSecurity(
            telemetry=self.telemetry,
            strict_mode=True,  # Block on MEDIUM+ threats
        )
        logger.info("Gate S: Security validation initialized (prompt injection defense)")

        # Gate M: Memory feedback loop - query before, record after (Dec 24, 2025)
        # Closes the learning loop from past trades
        self.gate_memory = GateMemory(
            telemetry=self.telemetry,
            db_path="data/trade_memory.db",
        )
        logger.info("Gate M: Memory feedback loop initialized (SQLite)")

        self.gate0 = Gate0Psychology(
            mental_coach=self.mental_coach,
            telemetry=self.telemetry,
        )
        self.gate1 = Gate1Momentum(
            momentum_agent=self.momentum_agent,
            failure_manager=self.failure_manager,
            telemetry=self.telemetry,
        )
        self.gate15 = Gate15Debate(
            debate_moderator=self.debate_moderator,
            telemetry=self.telemetry,
            debate_available=DEBATE_AVAILABLE,
        )
        self.gate2 = Gate2RLFilter(
            rl_filter=self.rl_filter,
            failure_manager=self.failure_manager,
            telemetry=self.telemetry,
            rl_filter_enabled=self.rl_filter_enabled,
        )
        self.gate3 = Gate3Sentiment(
            llm_agent=self.llm_agent,
            bias_provider=self.bias_provider,
            budget_controller=self.budget_controller,
            playwright_scraper=self.playwright_scraper,
            failure_manager=self.failure_manager,
            telemetry=self.telemetry,
            llm_sentiment_enabled=self.llm_sentiment_enabled,
        )
        self.gate35 = Gate35Introspection(
            introspective_council=self.introspective_council,
            uncertainty_tracker=self.uncertainty_tracker,
            telemetry=self.telemetry,
            introspection_available=INTROSPECTION_AVAILABLE,
        )
        self.gate4 = Gate4Risk(
            risk_manager=self.risk_manager,
            executor=self.executor,
            failure_manager=self.failure_manager,
            telemetry=self.telemetry,
        )
        self.gate5 = Gate5Execution(
            trade_gateway=self.trade_gateway,
            smart_dca=self.smart_dca,
            executor=self.executor,
            risk_manager=self.risk_manager,
            position_manager=self.position_manager,
            trade_verifier=self.trade_verifier,
            failure_manager=self.failure_manager,
            telemetry=self.telemetry,
        )
        self.gate_pipeline = TradingGatePipeline(
            gate0=self.gate0,
            gate1=self.gate1,
            gate15=self.gate15,
            gate2=self.gate2,
            gate3=self.gate3,
            gate35=self.gate35,
            gate4=self.gate4,
        )
        # RAG pre-trade query - queries lessons before each trade decision
        self.rag_query = RAGPreTradeQuery(
            lessons_rag=self.lessons_rag,
            telemetry=self.telemetry,
        )

        # TradeMemory pre-trade query - queries historical pattern performance
        # THE KEY INSIGHT: Most systems write to journals but never READ before trading
        self.trade_memory = TradeMemory(db_path="data/trade_memory.db")
        self.trade_memory_query = TradeMemoryQuery(
            trade_memory=self.trade_memory,
            telemetry=self.telemetry,
        )
        logger.info("TradeMemory pre-trade query initialized")

        logger.info("Gate pipeline initialized (866→~50 lines per method)")

    def run(self) -> None:
        # GATE -1: Staleness Guard - Block trading on stale data
        # Prevents the "Dec 23 lying incident" where stale local data
        # caused system to claim "no trades" while 9 live orders existed
        session_profile = self._build_session_profile()
        is_market_day = session_profile.get("is_market_day", True)

        staleness = check_data_staleness(is_market_day=is_market_day)
        if staleness.is_stale and staleness.blocking:
            logger.error(
                "⛔ STALENESS GUARD: Trading blocked - %s (last update: %s)",
                staleness.reason,
                staleness.last_updated or "unknown",
            )
            self.telemetry.record(
                event_type="staleness.blocked",
                ticker="SYSTEM",
                status="blocked",
                payload={
                    "reason": staleness.reason,
                    "hours_old": staleness.hours_old,
                    "last_updated": staleness.last_updated,
                },
            )
            raise RuntimeError(
                f"Trading blocked: {staleness.reason}. "
                "Run 'python scripts/sync_alpaca_state.py' to refresh data."
            )
        elif staleness.is_stale:
            logger.warning("⚠️ STALENESS WARNING: %s", staleness.reason)
        else:
            logger.info("✅ Data freshness verified: %.1fh old", staleness.hours_old)

        active_tickers = session_profile["tickers"]
        self.session_profile = session_profile
        self.smart_dca.reset_session(active_tickers)

        # Gate 0: Mental Toughness Coach - Start session and check readiness
        coaching_intervention = None
        if self.mental_coach:
            try:
                coaching_intervention = self.mental_coach.start_session()
                state_summary = self.mental_coach.get_state_summary()

                self.telemetry.record(
                    event_type="coaching.session_start",
                    ticker="SYSTEM",
                    status="info",
                    payload={
                        "intervention": coaching_intervention.headline,
                        "zone": state_summary["zone"],
                        "readiness_score": state_summary["readiness_score"],
                        "mental_energy": state_summary["mental_energy"],
                        "active_biases": state_summary["active_biases"],
                    },
                )

                logger.info(
                    "Gate 0: Session started - Zone: %s, Readiness: %s, Energy: %s",
                    state_summary["zone"],
                    state_summary["readiness_score"],
                    state_summary["mental_energy"],
                )

                # Check if ready to trade at all
                ready, blocking_intervention = self.mental_coach.is_ready_to_trade()
                if not ready:
                    logger.warning(
                        "Gate 0: BLOCKED - Not psychologically ready: %s",
                        blocking_intervention.headline if blocking_intervention else "Unknown",
                    )
                    self.telemetry.record(
                        event_type="coaching.session_blocked",
                        ticker="SYSTEM",
                        status="blocked",
                        payload={
                            "reason": blocking_intervention.headline
                            if blocking_intervention
                            else "Tilt/Danger zone",
                            "message": blocking_intervention.message
                            if blocking_intervention
                            else "",
                            "zone": state_summary["zone"],
                        },
                    )
                    # In strict mode, abort the session entirely
                    if os.getenv("COACHING_STRICT_MODE", "false").lower() in {"1", "true"}:
                        logger.error("Gate 0: STRICT MODE - Session aborted due to mental state")
                        return
            except Exception as e:
                logger.warning(f"Gate 0: Coaching check failed, continuing: {e}")

        # Determine the macro context for this session
        macro_context = self.macro_agent.get_macro_context()
        session_profile["macro_context"] = macro_context

        self.momentum_agent.configure_regime(session_profile.get("momentum_overrides"))

        self.telemetry.record(
            event_type="session.profile",
            ticker="SYSTEM",
            status="info",
            payload={
                "session_type": session_profile["session_type"],
                "market_day": session_profile["is_market_day"],
                "tickers": active_tickers,
                "rl_threshold": session_profile["rl_threshold"],
                "macro_context": macro_context,
            },
        )

        logger.info(
            "Running hybrid funnel (%s) for tickers: %s",
            session_profile["session_type"],
            ", ".join(active_tickers),
        )

        # CRITICAL: Manage existing positions FIRST (exits before entries)
        # This ensures win/loss tracking works properly
        self._manage_open_positions()

        # Query lessons learned RAG to avoid repeating past mistakes
        self._query_lessons_learned(context="options momentum trading")

        # Go ADK Multi-Agent Analysis (Dec 2025)
        # Get Gemini-powered signals from research/signal/risk/execution agents
        adk_decision = None
        if self.adk_adapter:
            try:
                adk_decision = self.adk_adapter.evaluate(
                    symbols=active_tickers[:5],  # Limit to reduce latency
                    context={
                        "macro_context": macro_context,
                        "session_type": session_profile["session_type"],
                        "portfolio_value": self.executor.get_account_info().get("equity", 100000),
                    },
                )
                if adk_decision:
                    adk_summary = summarize_adk_decision(adk_decision)
                    self.telemetry.record(
                        event_type="adk.decision",
                        ticker=adk_decision.symbol,
                        status="info",
                        payload=adk_summary,
                    )
                    logger.info(
                        "ADK agents recommend: %s %s (confidence=%.1f%%, size=%.2f)",
                        adk_decision.action,
                        adk_decision.symbol,
                        adk_decision.confidence * 100,
                        adk_decision.position_size,
                    )
            except Exception as e:
                logger.debug(f"ADK evaluation skipped: {e}")

        # =================================================================
        # OPTIONS FIRST (Dec 12, 2025): Theta decay is proven profit maker
        # Evidence: +$327 profit today from AMD/SPY short puts
        # Running options FIRST ensures they get capital before momentum
        # See: ll_019, deep research "options-primary-strategy"
        # =================================================================
        # Gate 6: Phil Town Rule #1 Options Strategy (MOVED UP - was last)
        self.run_options_strategy()

        # Gate 7: IV-Aware Options Execution (MOVED UP - was last)
        # Integrates OptionsIVSignalGenerator + OptionsExecutor
        self.run_iv_options_execution()

        # THEN run momentum trading (30% of budget per config)
        # Dec 2025: ADK Parallel Fan-Out/Gather pattern for reduced latency
        if self.parallel_processing_enabled and len(active_tickers) > 1:
            parallel_result = self._process_tickers_parallel(
                active_tickers, rl_threshold=session_profile["rl_threshold"]
            )
            logger.info(
                "Parallel processing: %d passed, %d rejected, %d errors in %.0fms",
                parallel_result.passed,
                parallel_result.rejected,
                parallel_result.errors,
                parallel_result.total_time_ms,
            )
        else:
            # Sequential fallback (single ticker or parallel disabled)
            for ticker in active_tickers:
                self._process_ticker(ticker, rl_threshold=session_profile["rl_threshold"])

        # Allocate any unused DCA budget into the safety bucket
        self._deploy_safe_reserve()

        # Run portfolio-level strategies
        self._run_portfolio_strategies()

        # Gate 5: Post-execution delta rebalancing
        self.run_delta_rebalancing()

        # Gate 0: Mental Toughness Coach - End session with review
        if self.mental_coach:
            try:
                end_intervention = self.mental_coach.end_session()
                state_summary = self.mental_coach.get_state_summary()

                self.telemetry.record(
                    event_type="coaching.session_end",
                    ticker="SYSTEM",
                    status="completed",
                    payload={
                        "intervention": end_intervention.headline,
                        "final_zone": state_summary["zone"],
                        "final_readiness": state_summary["readiness_score"],
                        "trades_today": state_summary["trades_today"],
                        "consecutive_wins": state_summary["consecutive_wins"],
                        "consecutive_losses": state_summary["consecutive_losses"],
                        "active_biases": state_summary["active_biases"],
                    },
                )

                logger.info(
                    "Gate 0: Session ended - Zone: %s, Readiness: %s, Trades: %d",
                    state_summary["zone"],
                    state_summary["readiness_score"],
                    state_summary["trades_today"],
                )
            except Exception as e:
                logger.warning(f"Gate 0: Session end coaching failed: {e}")

        # Save and print session summary (always, even with 0 trades)
        self.telemetry.save_session_decisions(self.session_profile)
        self.telemetry.print_session_summary()

        # Record heartbeat to indicate system is alive (Dec 28, 2025)
        # Prevents the "Dec 11-12 incident" where trading was dead for 2 days unnoticed
        try:
            record_heartbeat(
                workflow_name="trading_session",
                status="success",
                details={
                    "tickers_processed": len(active_tickers),
                    "session_type": self.session_profile.get("session_type", "unknown"),
                },
            )
        except Exception as e:
            logger.warning(f"Failed to record heartbeat: {e}")

    def _query_lessons_learned(self, context: str = "trading session") -> None:
        """
        Query lessons learned RAG before trading to avoid repeating mistakes.

        Logs warnings for any relevant lessons found based on current context.
        """
        if not self.lessons_rag:
            return

        try:
            # Query for relevant lessons
            results = self.lessons_rag.search(
                query=f"trading {context} mistakes errors filters thresholds",
                top_k=3,
            )

            if results:
                logger.info("=" * 60)
                logger.info("📚 LESSONS LEARNED (from RAG - don't repeat mistakes!):")
                for lesson, score in results:
                    if score > 0.1:  # Only show relevant matches
                        logger.warning(
                            "  ⚠️  [%s] %s: %s",
                            lesson.severity.upper(),
                            lesson.title,
                            lesson.prevention[:100] + "..."
                            if len(lesson.prevention) > 100
                            else lesson.prevention,
                        )

                # Log to telemetry
                self.telemetry.record(
                    event_type="lessons.queried",
                    ticker="SYSTEM",
                    status="info",
                    payload={
                        "lessons_found": len(results),
                        "top_lesson": results[0][0].title
                        if results and len(results) > 0 and len(results[0]) > 0
                        else None,
                    },
                )
                logger.info("=" * 60)

        except Exception as e:
            logger.debug(f"Lessons RAG query failed (non-fatal): {e}")

    def _format_momentum_rejection(self, indicators: dict) -> str:
        """Format a human-readable rejection reason from momentum indicators."""
        reasons = []
        adx = indicators.get("adx", 0)
        macd = indicators.get("macd_hist", indicators.get("macd", 0))
        rsi = indicators.get("rsi", 50)
        vol = indicators.get("volume_ratio", 1.0)

        if adx < 10:
            reasons.append(f"ADX={adx:.1f} (weak trend)")
        if macd < 0:
            reasons.append(f"MACD={macd:.2f} (bearish)")
        if rsi > 70:
            reasons.append(f"RSI={rsi:.1f} (overbought)")
        if vol < 0.6:
            reasons.append(f"Vol={vol:.1f}x (low)")

        return "; ".join(reasons) if reasons else "Score below threshold"

    def _run_portfolio_strategies(self) -> None:
        """Run strategies that operate on the portfolio level."""
        logger.info("--- Running Portfolio-Level Strategies ---")
        if not self.session_profile:
            logger.warning("Session profile not available, skipping portfolio strategies.")
            return

        # --- REIT Smart Income Strategy ---
        try:
            from src.strategies.reit_strategy import ReitStrategy

            reit_strategy = ReitStrategy(trader=self.executor.trader)

            reit_alloc_pct = float(os.getenv("REIT_ALLOCATION_PCT", "0.15"))
            daily_investment = float(os.getenv("DAILY_INVESTMENT", "50.0"))
            reit_amount = daily_investment * reit_alloc_pct

            if reit_amount >= 1.0:
                logger.info(f"Executing REIT Strategy with ${reit_amount:.2f}...")
                reit_strategy.execute_daily(amount=reit_amount)
            else:
                logger.info("Skipping REIT Strategy: allocation amount is too small.")
        except Exception as e:
            logger.error(f"Failed to run REIT Strategy: {e}", exc_info=True)

    def _manage_open_positions(self) -> dict[str, Any]:
        """
        CRITICAL: Manage existing positions - check for exits and record closed trades.

        This method solves the core problem of positions never being closed (0% win rate).
        It evaluates all open positions against exit conditions and executes sells when
        triggered, recording closed trades for proper win/loss tracking.

        Returns:
            Dict with management results: positions checked, exits executed, trades recorded
        """
        logger.info("=" * 80)
        logger.info("POSITION MANAGEMENT - ACTIVE EXIT EVALUATION")
        logger.info("=" * 80)

        results = {
            "positions_checked": 0,
            "exits_executed": 0,
            "trades_recorded": 0,
            "errors": [],
        }

        try:
            # Get current positions from Alpaca
            positions = self.executor.get_positions()
            results["positions_checked"] = len(positions)

            if not positions:
                logger.info("No open positions to manage.")
                return results

            logger.info(f"Found {len(positions)} open positions to evaluate.")

            # Evaluate positions for exits
            exits_to_execute = self.position_manager.manage_all_positions(positions)

            if not exits_to_execute:
                logger.info("No positions flagged for exit.")
                return results

            logger.info(f"Processing {len(exits_to_execute)} exit signals...")

            # Execute exits and record closed trades
            for exit_info in exits_to_execute:
                try:
                    symbol = exit_info["symbol"]
                    position = exit_info["position"]
                    reason = exit_info["reason"]

                    logger.info(f"Executing exit for {symbol}: {reason}")

                    # Create CLOSE request through trade gateway.
                    #
                    # IMPORTANT:
                    # - Alpaca positions can include options with negative qty for short legs.
                    # - Closing a SHORT position requires a BUY (buy-to-close semantics).
                    # - Closing a LONG position requires a SELL.
                    #
                    # If we always use SELL here, a short option "close" can be interpreted as
                    # sell-to-open, which requires new collateral/options buying power and fails.
                    close_side = "buy" if position.quantity < 0 else "sell"
                    trade_request = TradeRequest(
                        symbol=symbol,
                        side=close_side,
                        quantity=abs(position.quantity),
                        source=f"position_manager.{reason}",
                    )

                    decision = self.trade_gateway.evaluate(trade_request)

                    if not decision.approved:
                        logger.warning(
                            f"Exit rejected by gateway for {symbol}: {[r.value for r in decision.rejection_reasons]}"
                        )
                        results["errors"].append(f"{symbol}: gateway rejection")
                        continue

                    # Execute the close order
                    order = self.trade_gateway.execute(decision)
                    if not order:
                        logger.warning(
                            "Exit execution returned no order for %s (%s). Not recording as closed.",
                            symbol,
                            reason,
                        )
                        results["errors"].append(f"{symbol}: execution returned no order")
                        continue

                    results["exits_executed"] += 1

                    # Record the closed trade for win/loss tracking
                    self._record_closed_trade(
                        symbol=symbol,
                        entry_price=position.entry_price,
                        exit_price=position.current_price,
                        quantity=position.quantity,
                        entry_date=position.entry_date.isoformat() if position.entry_date else None,
                        exit_reason=reason,
                    )
                    results["trades_recorded"] += 1

                    # A2 Adaptation: Calculate actual return and prediction correctness
                    actual_return_pct = position.unrealized_plpc * 100
                    prediction_correct = actual_return_pct > 0  # True if profitable exit

                    # Log telemetry with prediction outcome tracking
                    self.telemetry.record(
                        event_type="position.exit",
                        ticker=symbol,
                        status="executed",
                        payload={
                            "reason": reason,
                            "entry_price": position.entry_price,
                            "exit_price": position.current_price,
                            "pl_pct": actual_return_pct,
                            "order": order,
                            # Prediction outcome tracking for A2 adaptation mode
                            "actual_return": actual_return_pct,
                            "prediction_correct": prediction_correct,
                            "outcome_timestamp": datetime.now(timezone.utc).isoformat(),
                        },
                    )

                    # =================================================================
                    # FEEDBACK LOOP: Record outcome to TradeMemory (GateMemory)
                    # This completes the learning cycle for pattern-based decisions
                    # =================================================================
                    try:
                        pending = getattr(self, "_pending_trade_outcomes", {})
                        entry_record = pending.pop(symbol, None)
                        if entry_record:
                            won = actual_return_pct > 0
                            pnl = position.unrealized_pl or 0
                            lesson = (
                                f"{'Win' if won else 'Loss'} on {symbol}: "
                                f"{actual_return_pct:.2f}% ({reason})"
                            )
                            self.gate_memory.record_outcome(
                                ticker=symbol,
                                strategy=entry_record.get("strategy", "momentum"),
                                entry_reason=entry_record.get("entry_reason", "technical"),
                                won=won,
                                pnl=pnl,
                                lesson=lesson,
                            )
                            logger.info(
                                "📊 Feedback recorded: %s %s (%.2f%% / $%.2f)",
                                symbol,
                                "WON" if won else "LOST",
                                actual_return_pct,
                                pnl,
                            )
                    except Exception as mem_err:
                        logger.warning("Failed to record feedback for %s: %s", symbol, mem_err)

                    # DiscoRL online learning: Record trade outcome for continuous improvement
                    if hasattr(self.rl_filter, "record_trade_outcome"):
                        try:
                            # Get entry features stored when position was opened
                            entry_features = self.position_manager.get_entry_features(symbol)

                            if entry_features:
                                # Fetch current market features for exit state
                                exit_features = {}
                                try:
                                    momentum_exit = self.momentum_agent.analyze(symbol)
                                    if momentum_exit:
                                        exit_features = momentum_exit.indicators
                                except Exception as fetch_err:
                                    logger.debug(
                                        f"Could not fetch exit features for {symbol}: {fetch_err}"
                                    )
                                    exit_features = entry_features  # Fallback to entry features

                                # Calculate reward (P/L percentage)
                                reward = (
                                    position.unrealized_plpc
                                )  # Already a percentage (e.g., 0.03 for 3%)

                                # Record the trade outcome for DiscoRL learning
                                training_metrics = self.rl_filter.record_trade_outcome(
                                    entry_state=entry_features,
                                    action=1,  # 1 = BUY (long position)
                                    exit_state=exit_features,
                                    reward=reward,
                                    done=True,
                                )

                                if training_metrics:
                                    logger.info(
                                        f"DiscoRL learned from {symbol} trade: "
                                        f"reward={reward:.4f}, loss={training_metrics.get('total_loss', 0):.4f}"
                                    )
                                    self.telemetry.record(
                                        event_type="rl.online_learning",
                                        ticker=symbol,
                                        status="trained",
                                        payload={
                                            "reward": reward,
                                            "metrics": training_metrics,
                                            "buffer_size": training_metrics.get("buffer_size", 0),
                                        },
                                    )
                            else:
                                logger.debug(
                                    f"No entry features found for {symbol}, skipping DiscoRL learning"
                                )

                        except Exception as rl_err:
                            logger.warning(f"DiscoRL online learning failed for {symbol}: {rl_err}")

                    # Clear entry tracking (after DiscoRL uses the features)
                    self.position_manager.clear_entry(symbol)

                    logger.info(
                        f"✅ Closed {symbol}: {reason} (P/L: {position.unrealized_plpc * 100:.2f}%)"
                    )

                except Exception as e:
                    logger.error(f"Error executing exit for {exit_info.get('symbol')}: {e}")
                    results["errors"].append(f"{exit_info.get('symbol')}: {str(e)}")
                    continue

        except Exception as e:
            logger.error(f"Position management failed: {e}", exc_info=True)
            results["errors"].append(f"Overall failure: {str(e)}")

        logger.info("=" * 80)
        logger.info(
            f"POSITION MANAGEMENT COMPLETE: {results['exits_executed']} exits, "
            f"{results['trades_recorded']} trades recorded"
        )
        logger.info("=" * 80)

        return results

    def _record_closed_trade(
        self,
        symbol: str,
        entry_price: float,
        exit_price: float,
        quantity: float,
        entry_date: str | None,
        exit_reason: str,
    ) -> None:
        """
        Record a closed trade to system state for win/loss tracking.

        This updates the performance metrics that feed the win rate calculation.
        Also feeds the Mental Toughness Coach for psychological state updates.
        """
        try:
            from scripts.state_manager import StateManager

            state_manager = StateManager()

            # Calculate P/L
            pl = (exit_price - entry_price) * quantity
            is_winner = pl > 0

            # Record via state manager
            state_manager.record_closed_trade(
                symbol=symbol,
                entry_price=entry_price,
                exit_price=exit_price,
                quantity=quantity,
                entry_date=entry_date or datetime.now().isoformat(),
            )

            # Update win/loss counts
            if is_winner:
                state_manager.state["performance"]["winning_trades"] = (
                    state_manager.state["performance"].get("winning_trades", 0) + 1
                )
            else:
                state_manager.state["performance"]["losing_trades"] = (
                    state_manager.state["performance"].get("losing_trades", 0) + 1
                )

            # Recalculate win rate
            total_closed = len(state_manager.state["performance"].get("closed_trades", []))
            winning = state_manager.state["performance"].get("winning_trades", 0)
            if total_closed > 0:
                state_manager.state["performance"]["win_rate"] = (winning / total_closed) * 100

            state_manager.save_state()

            logger.info(
                f"Recorded closed trade: {symbol} {'WIN' if is_winner else 'LOSS'} "
                f"(${pl:.2f}, {((exit_price - entry_price) / entry_price) * 100:.2f}%)"
            )

            # Gate 2 RL Training: Record trade outcome for DiscoRL/DQN learning
            # Dec 10, 2025: CEO mandate - no dead code, RL must learn from real trades!
            try:
                # Get entry features stored when position was opened
                entry_features = self.position_manager.get_entry_features(symbol)

                if entry_features:
                    # Fetch current market features for exit state
                    exit_features = {}
                    try:
                        momentum_exit = self.momentum_agent.analyze(symbol)
                        if momentum_exit:
                            exit_features = momentum_exit.indicators
                    except Exception as fetch_err:
                        logger.debug(f"Could not fetch exit features for {symbol}: {fetch_err}")
                        exit_features = entry_features  # Fallback to entry features

                    pl_pct = (exit_price - entry_price) / entry_price if entry_price > 0 else 0
                    # Scale reward: +-10% maps to +-1.0 reward
                    reward = pl_pct * 10.0
                    # Action: 1=BUY (we bought), outcome determines if it was good
                    action = 1  # BUY action that led to this trade

                    # Record to RL filter for online learning with proper market states
                    rl_result = self.rl_filter.record_trade_outcome(
                        entry_state=entry_features,
                        action=action,
                        exit_state=exit_features,
                        reward=reward,
                        done=True,
                    )
                    if rl_result:
                        logger.info(
                            f"Gate 2 RL: Recorded trade outcome for {symbol} "
                            f"(reward={reward:.3f}, action={action})"
                        )
                else:
                    logger.debug(f"No entry features stored for {symbol}, skipping RL training")
            except Exception as rl_exc:
                logger.debug(f"Gate 2 RL training update failed (non-critical): {rl_exc}")

            # Gate 0: Mental Toughness Coach - Process trade result for psychological state
            if self.mental_coach:
                try:
                    coaching_interventions = self.mental_coach.process_trade_result(
                        is_win=is_winner,
                        pnl=pl,
                        ticker=symbol,
                        trade_reason=exit_reason,
                    )

                    state_summary = self.mental_coach.get_state_summary()

                    # Log coaching feedback
                    for intervention in coaching_interventions:
                        logger.info(
                            "Gate 0 Coaching: %s - %s",
                            intervention.headline,
                            intervention.message[:100] + "..."
                            if len(intervention.message) > 100
                            else intervention.message,
                        )
                        self.telemetry.record(
                            event_type="coaching.intervention",
                            ticker=symbol,
                            status="triggered",
                            payload={
                                "intervention_type": intervention.intervention_type.value,
                                "headline": intervention.headline,
                                "severity": intervention.severity,
                                "action_items": intervention.action_items,
                                "zone": state_summary["zone"],
                                "consecutive_wins": state_summary["consecutive_wins"],
                                "consecutive_losses": state_summary["consecutive_losses"],
                            },
                        )

                    # Check if we should stop trading due to psychological state
                    ready, blocking_intervention = self.mental_coach.is_ready_to_trade()
                    if not ready:
                        logger.warning(
                            "Gate 0: CIRCUIT BREAKER - Mental state degraded: %s",
                            blocking_intervention.headline
                            if blocking_intervention
                            else "Tilt detected",
                        )
                        self.telemetry.record(
                            event_type="coaching.circuit_breaker",
                            ticker=symbol,
                            status="triggered",
                            payload={
                                "reason": blocking_intervention.headline
                                if blocking_intervention
                                else "Mental state",
                                "zone": state_summary["zone"],
                                "readiness_score": state_summary["readiness_score"],
                            },
                        )

                except Exception as coach_err:
                    logger.warning(f"Gate 0: Coaching feedback failed: {coach_err}")

        except Exception as e:
            logger.error(f"Failed to record closed trade for {symbol}: {e}")

    def _build_session_profile(self) -> dict[str, Any]:
        """Build session profile - delegates to SessionManager.

        Jan 10, 2026: Extracted to SessionManager for cleaner architecture.
        """
        return self.session_manager.build_session_profile()

    def _estimate_execution_costs(self, notional: float) -> dict[str, float]:
        sec_fee_rate = float(os.getenv("SEC_FEE_RATE", "0.000018"))
        broker_fee_rate = float(os.getenv("BROKER_FEE_RATE", "0.0005"))
        slip_bps = float(os.getenv("EXECUTION_SLIPPAGE_BPS", "25.0"))

        slippage_cost = (slip_bps / 10_000.0) * notional
        fee_cost = (sec_fee_rate + broker_fee_rate) * notional
        total_cost = slippage_cost + fee_cost

        return {
            "slippage_cost": round(slippage_cost, 4),
            "fees": round(fee_cost, 4),
            "total_cost": round(total_cost, 4),
            "slippage_bps": slip_bps,
            "fee_rate": sec_fee_rate + broker_fee_rate,
        }

    def _track_gate_event(
        self,
        *,
        gate: str,
        ticker: str,
        status: str,
        metrics: dict[str, Any] | None = None,
    ) -> None:
        try:
            self.anomaly_monitor.track(
                gate=gate,
                ticker=ticker,
                status=status,
                metrics=metrics or {},
            )
        except Exception as exc:  # pragma: no cover - non-critical
            logger.debug("Anomaly monitor tracking failed for %s: %s", gate, exc)

    def _process_tickers_parallel(
        self, tickers: list[str], rl_threshold: float
    ) -> ParallelProcessingResult:
        """Process multiple tickers in parallel using ADK Fan-Out/Gather pattern.

        This reduces latency from O(n*T) to O(T) where n is number of tickers
        and T is time per ticker.

        Args:
            tickers: List of ticker symbols to process
            rl_threshold: RL confidence threshold for gate 2

        Returns:
            ParallelProcessingResult with aggregated stats
        """
        # Lazy initialization of parallel processor
        if self.parallel_processor is None:
            # Create thread-safe wrapper around _process_ticker
            safe_fn = create_thread_safe_wrapper(
                telemetry=self.telemetry,
                process_ticker_fn=self._process_ticker,
            )
            self.parallel_processor = ParallelTickerProcessor(
                process_fn=safe_fn,
                max_workers=self.parallel_max_workers,
                timeout_seconds=30.0,
            )
            logger.info(
                "Initialized ParallelTickerProcessor with %d workers",
                self.parallel_max_workers,
            )

        # Process all tickers in parallel
        result = self.parallel_processor.process_tickers(tickers, rl_threshold)

        # Log any errors for debugging
        for ticker, ticker_result in result.results.items():
            if ticker_result.outcome == TickerOutcome.ERROR:
                logger.error(
                    "Parallel processing error for %s: %s",
                    ticker,
                    ticker_result.error_message,
                )

        return result

    def _process_ticker(self, ticker: str, rl_threshold: float) -> None:
        # Dec 2025: Use v2 pipeline if enabled (LLM-friendly, ~100 lines vs 866)
        use_v2 = os.getenv("USE_PIPELINE_V2", "false").lower() in {"1", "true", "yes"}
        if use_v2:
            return self._process_ticker_v2(ticker, rl_threshold)

        logger.info("--- Processing %s ---", ticker)

        # Initialize decision tracking for this ticker
        self.telemetry.start_ticker_decision(ticker)

        # Gate 0: Pre-trade psychological readiness check
        if self.mental_coach:
            try:
                pre_trade_intervention = self.mental_coach.pre_trade_check(ticker)
                if pre_trade_intervention:
                    logger.info(
                        "Gate 0 (%s): Pre-trade coaching - %s",
                        ticker,
                        pre_trade_intervention.headline,
                    )
                    self.telemetry.record(
                        event_type="coaching.pre_trade",
                        ticker=ticker,
                        status="intervention",
                        payload={
                            "headline": pre_trade_intervention.headline,
                            "severity": pre_trade_intervention.severity,
                            "action_items": pre_trade_intervention.action_items,
                        },
                    )

                # Check if still ready to trade (may have degraded during session)
                ready, blocking_intervention = self.mental_coach.is_ready_to_trade()
                if not ready:
                    logger.warning(
                        "Gate 0 (%s): SKIPPED - Not ready to trade: %s",
                        ticker,
                        blocking_intervention.headline if blocking_intervention else "Tilt/Danger",
                    )
                    self.telemetry.gate_reject(
                        "coaching",
                        ticker,
                        {
                            "reason": blocking_intervention.headline
                            if blocking_intervention
                            else "Mental state",
                            "severity": blocking_intervention.severity
                            if blocking_intervention
                            else "critical",
                        },
                    )
                    return
            except Exception as e:
                logger.warning(f"Gate 0 (%s): Pre-trade check failed, continuing: {e}", ticker)

        # Gate 1: deterministic momentum
        momentum_outcome = self.failure_manager.run(
            gate="momentum",
            ticker=ticker,
            operation=lambda: self.momentum_agent.analyze(ticker),
        )
        if not momentum_outcome.ok:
            logger.error(
                "Gate 1 (%s): momentum analysis failed: %s",
                ticker,
                momentum_outcome.failure.error,
            )
            return

        momentum_signal = momentum_outcome.result
        if not momentum_signal.is_buy:
            logger.info("Gate 1 (%s): REJECTED by momentum filter.", ticker)
            # Track rejection with indicator details
            ind = momentum_signal.indicators
            rejection_reason = self._format_momentum_rejection(ind)
            self.telemetry.update_ticker_decision(
                ticker,
                gate=1,
                status="REJECT",
                indicators=ind,
                rejection_reason=rejection_reason,
            )
            self.telemetry.gate_reject(
                "momentum",
                ticker,
                {
                    "strength": momentum_signal.strength,
                    "indicators": momentum_signal.indicators,
                },
            )
            self._track_gate_event(
                gate="momentum",
                ticker=ticker,
                status="reject",
                metrics={"confidence": momentum_signal.strength},
            )
            return
        logger.info("Gate 1 (%s): PASSED (strength=%.2f)", ticker, momentum_signal.strength)
        self.telemetry.gate_pass(
            "momentum",
            ticker,
            {
                "strength": momentum_signal.strength,
                "indicators": momentum_signal.indicators,
            },
        )
        self._track_gate_event(
            gate="momentum",
            ticker=ticker,
            status="pass",
            metrics={"confidence": momentum_signal.strength},
        )

        # Gate 1.5: Bull/Bear Debate - Multi-perspective analysis (Dec 2025)
        # Based on UCLA/MIT TradingAgents research showing 42% CAGR improvement
        debate_outcome = None
        if self.debate_moderator and DEBATE_AVAILABLE:
            try:
                # Build market data for debate
                debate_market_data = {
                    "price": momentum_signal.indicators.get("close", 0),
                    "rsi": momentum_signal.indicators.get("rsi", 50),
                    "macd_histogram": momentum_signal.indicators.get("macd_histogram", 0),
                    "volume_ratio": momentum_signal.indicators.get("volume_ratio", 1.0),
                    "trend": "BULLISH" if momentum_signal.is_buy else "BEARISH",
                    "ma_50": momentum_signal.indicators.get("sma_20", 0),  # Approximate
                    "ma_200": momentum_signal.indicators.get("sma_50", 0),  # Approximate
                }

                debate_outcome = self.debate_moderator.conduct_debate(ticker, debate_market_data)

                logger.info(
                    "Gate 1.5 (%s): Bull/Bear Debate - Winner: %s, Rec: %s, Confidence: %.2f",
                    ticker,
                    debate_outcome.winner,
                    debate_outcome.final_recommendation,
                    debate_outcome.confidence,
                )

                self.telemetry.record(
                    event_type="debate.outcome",
                    ticker=ticker,
                    status="completed",
                    payload={
                        "winner": debate_outcome.winner,
                        "recommendation": debate_outcome.final_recommendation,
                        "confidence": debate_outcome.confidence,
                        "bull_conviction": debate_outcome.bull_position.conviction,
                        "bear_conviction": debate_outcome.bear_position.conviction,
                        "position_size_modifier": debate_outcome.position_size_modifier,
                        "key_factors": debate_outcome.key_factors,
                        "dissenting_view": debate_outcome.dissenting_view,
                    },
                )

                # If debate strongly recommends against, reject the trade
                if debate_outcome.winner == "BEAR" and debate_outcome.confidence > 0.7:
                    logger.info(
                        "Gate 1.5 (%s): REJECTED by Bear - %s",
                        ticker,
                        debate_outcome.dissenting_view,
                    )
                    self.telemetry.gate_reject(
                        "debate",
                        ticker,
                        {
                            "winner": "BEAR",
                            "confidence": debate_outcome.confidence,
                            "key_factors": debate_outcome.key_factors,
                        },
                    )
                    return

            except Exception as debate_err:
                logger.warning(f"Gate 1.5 (%s): Debate failed, continuing: {debate_err}", ticker)

        # Gate 2: RL inference (SKIPPED if disabled - simplification mode)
        if not self.rl_filter_enabled or self.rl_filter is None:
            logger.info(
                "Gate 2 (%s): SKIPPED - RL filter disabled (simplification mode)",
                ticker,
            )
            rl_decision = {"action": "BUY", "confidence": 1.0, "skipped": True}
            self.telemetry.gate_pass(
                "rl_filter", ticker, {"skipped": True, "reason": "simplification_mode"}
            )
        else:
            rl_outcome = self.failure_manager.run(
                gate="rl_filter",
                ticker=ticker,
                operation=lambda: self.rl_filter.predict(momentum_signal.indicators),
            )
            if not rl_outcome.ok:
                logger.error(
                    "Gate 2 (%s): RL filter failed: %s",
                    ticker,
                    rl_outcome.failure.error,
                )
                self._track_gate_event(
                    gate="rl_filter",
                    ticker=ticker,
                    status="error",
                    metrics={"confidence": 0.0},
                )
                return

            rl_decision = rl_outcome.result
            if rl_decision.get("confidence", 0.0) < rl_threshold:
                logger.info(
                    "Gate 2 (%s): REJECTED by RL filter (confidence=%.2f).",
                    ticker,
                    rl_decision.get("confidence", 0.0),
                )
                self.telemetry.gate_reject(
                    "rl_filter",
                    ticker,
                    rl_decision,
                )
                self._track_gate_event(
                    gate="rl_filter",
                    ticker=ticker,
                    status="reject",
                    metrics={"confidence": rl_decision.get("confidence", 0.0)},
                )
                return
            logger.info(
                "Gate 2 (%s): PASSED (action=%s, confidence=%.2f).",
                ticker,
                rl_decision.get("action"),
                rl_decision.get("confidence", 0.0),
            )
            self.telemetry.gate_pass("rl_filter", ticker, rl_decision)
        self.telemetry.explainability_event(
            gate="rl_filter",
            ticker=ticker,
            contributions=rl_decision.get("explainability", {}),
            metadata={"sources": rl_decision.get("sources")},
        )
        self._track_gate_event(
            gate="rl_filter",
            ticker=ticker,
            status="pass",
            metrics={"confidence": rl_decision.get("confidence", 0.0)},
        )

        pre_plan = self.smart_dca.plan_allocation(
            ticker=ticker,
            momentum_strength=momentum_signal.strength,
            rl_confidence=rl_decision.get("confidence", 0.0),
            sentiment_score=0.0,
        )
        if pre_plan.cap <= 0:
            logger.info(
                "Smart DCA: bucket %s exhausted before LLM budget, skipping %s",
                pre_plan.bucket,
                ticker,
            )
            self.telemetry.record(
                event_type="dca.skip",
                ticker=ticker,
                status="exhausted",
                payload={
                    "bucket": pre_plan.bucket,
                    "remaining": self.smart_dca.remaining_budget().get(pre_plan.bucket, 0.0),
                },
            )
            return

        micro_features = {}
        regime_snapshot = {"label": "unknown", "confidence": 0.0}
        try:
            micro_features = self.microstructure.extract(ticker)
            if "microstructure_error" not in micro_features:
                momentum_signal.indicators.update(micro_features)
                regime_snapshot = self.regime_detector.detect(micro_features)
                self.telemetry.record(
                    event_type="microstructure",
                    ticker=ticker,
                    status="ok",
                    payload={**micro_features, **regime_snapshot},
                )
            else:
                self.telemetry.record(
                    event_type="microstructure",
                    ticker=ticker,
                    status="error",
                    payload=micro_features,
                )
        except Exception as exc:  # pragma: no cover - diagnostics only
            self.telemetry.record(
                event_type="microstructure",
                ticker=ticker,
                status="exception",
                payload={"error": str(exc)},
            )

        # Gate 2.5: Multi-source sentiment analysis (before Gate 3)
        # Integrates news, social media, and market sentiment
        sentiment_skill_score = 0.0
        try:
            import sys

            sentiment_script = os.path.join(
                os.path.dirname(__file__),
                "../../.claude/skills/sentiment_analyzer/scripts/sentiment_analyzer.py",
            )
            if os.path.exists(sentiment_script):
                sys.path.insert(0, os.path.dirname(sentiment_script))
                from sentiment_analyzer import SentimentAnalyzer

                analyzer = SentimentAnalyzer()
                composite_result = analyzer.get_composite_sentiment(
                    symbols=[ticker], include_market_sentiment=True
                )

                if composite_result.get("success") and ticker in composite_result.get(
                    "composite_sentiment", {}
                ):
                    sentiment_data = composite_result["composite_sentiment"][ticker]
                    sentiment_skill_score = sentiment_data.get("score", 0.0)
                    logger.info(
                        "Gate 2.5 (%s): Sentiment Analyzer score=%.2f, label=%s, confidence=%.2f",
                        ticker,
                        sentiment_skill_score,
                        sentiment_data.get("label", "unknown"),
                        sentiment_data.get("confidence", 0.0),
                    )
                    self.telemetry.record(
                        event_type="gate.sentiment_analyzer",
                        ticker=ticker,
                        status="analyzed",
                        payload={
                            "score": sentiment_skill_score,
                            "label": sentiment_data.get("label"),
                            "confidence": sentiment_data.get("confidence"),
                            "recommendation": sentiment_data.get("recommendation"),
                        },
                    )
        except Exception as sentiment_exc:
            logger.warning("Gate 2.5 (%s): Sentiment analyzer failed: %s", ticker, sentiment_exc)
            self.telemetry.record(
                event_type="gate.sentiment_analyzer",
                ticker=ticker,
                status="error",
                payload={"error": str(sentiment_exc)},
            )

        # Gate 3: LLM sentiment (budget-aware, bias-cache first)
        # Enhanced with Playwright MCP for dynamic web scraping
        # Dec 10, 2025: Can be SKIPPED in simplification mode
        sentiment_score = 0.0
        playwright_score = 0.0
        # Initialize variables that may be used later (Jan 15, 2026 fix - prevent NameError)
        llm_model = None
        bias_snapshot: BiasSnapshot | None = None
        neg_threshold = float(os.getenv("LLM_NEGATIVE_SENTIMENT_THRESHOLD", "-0.2"))
        playwright_weight = float(os.getenv("PLAYWRIGHT_SENTIMENT_WEIGHT", "0.3"))

        if not self.llm_sentiment_enabled or self.llm_agent is None:
            logger.info(
                "Gate 3 (%s): SKIPPED - LLM sentiment disabled (simplification mode)",
                ticker,
            )
            self.telemetry.gate_pass(
                "llm_sentiment", ticker, {"skipped": True, "reason": "simplification_mode"}
            )
            # Skip directly to Gate 4 (Risk)
        else:
            # Original Gate 3 logic (only runs if LLM sentiment enabled)
            llm_model = getattr(self.llm_agent, "model_name", None)
            neg_threshold = float(os.getenv("LLM_NEGATIVE_SENTIMENT_THRESHOLD", "-0.2"))
            session_type = (self.session_profile or {}).get("session_type")
            if session_type == "weekend":
                neg_threshold = float(os.getenv("WEEKEND_SENTIMENT_FLOOR", "-0.1"))
            bias_snapshot: BiasSnapshot | None = None

            # Playwright MCP sentiment enhancement (async, non-blocking)
            playwright_weight = float(os.getenv("PLAYWRIGHT_SENTIMENT_WEIGHT", "0.3"))
        try:
            import asyncio

            playwright_result = asyncio.get_event_loop().run_until_complete(
                self.playwright_scraper.scrape_all([ticker])
            )
            if ticker in playwright_result and playwright_result[ticker].total_mentions > 0:
                playwright_score = playwright_result[ticker].weighted_score
                logger.info(
                    "Gate 3 (%s): Playwright sentiment=%.2f (mentions=%d, bull=%d, bear=%d)",
                    ticker,
                    playwright_score,
                    playwright_result[ticker].total_mentions,
                    playwright_result[ticker].bullish_count,
                    playwright_result[ticker].bearish_count,
                )
                self.telemetry.record(
                    event_type="gate.playwright",
                    ticker=ticker,
                    status="scraped",
                    payload={
                        "score": playwright_score,
                        "mentions": playwright_result[ticker].total_mentions,
                        "sources": [s.value for s in playwright_result[ticker].sources],
                    },
                )
        except Exception as pw_exc:
            logger.warning("Gate 3 (%s): Playwright scraping failed: %s", ticker, pw_exc)
            self.telemetry.record(
                event_type="gate.playwright",
                ticker=ticker,
                status="error",
                payload={"error": str(pw_exc)},
            )

        if self.bias_provider:
            bias_snapshot = self.bias_provider.get_bias(ticker)

        if bias_snapshot:
            sentiment_score = bias_snapshot.score
            payload = bias_snapshot.to_dict()
            payload["source"] = "bias_store"
            if sentiment_score < neg_threshold:
                logger.info(
                    "Gate 3 (%s): REJECTED by bias store (score=%.2f, reason=%s).",
                    ticker,
                    sentiment_score,
                    bias_snapshot.reason,
                )
                self.telemetry.gate_reject(
                    "llm",
                    ticker,
                    {**payload, "trigger": "negative_sentiment"},
                )
                return
            logger.info(
                "Gate 3 (%s): PASSED via bias store (sentiment=%.2f).",
                ticker,
                sentiment_score,
            )
            self.telemetry.gate_pass("llm", ticker, payload)
        elif self.budget_controller.can_afford_execution(model=llm_model):
            llm_outcome = self.failure_manager.run(
                gate="llm",
                ticker=ticker,
                operation=lambda: self.llm_agent.analyze_news(ticker, momentum_signal.indicators),
                retry=2,
            )
            if llm_outcome.ok:
                llm_result = llm_outcome.result
                llm_score = llm_result.get("score", 0.0)
                # Blend LLM and Playwright sentiment scores
                if playwright_score != 0.0:
                    sentiment_score = (
                        llm_score * (1 - playwright_weight) + playwright_score * playwright_weight
                    )
                    logger.info(
                        "Gate 3 (%s): Blended sentiment=%.2f (LLM=%.2f, Playwright=%.2f, weight=%.1f)",
                        ticker,
                        sentiment_score,
                        llm_score,
                        playwright_score,
                        playwright_weight,
                    )
                else:
                    sentiment_score = llm_score
                self.budget_controller.log_spend(llm_result.get("cost", 0.0))
                if sentiment_score < neg_threshold:
                    logger.info(
                        "Gate 3 (%s): REJECTED by LLM (score=%.2f, reason=%s).",
                        ticker,
                        sentiment_score,
                        llm_result.get("reason", "N/A"),
                    )
                    self.telemetry.gate_reject(
                        "llm",
                        ticker,
                        {**llm_result, "trigger": "negative_sentiment"},
                    )
                    self._track_gate_event(
                        gate="llm",
                        ticker=ticker,
                        status="reject",
                        metrics={"confidence": sentiment_score},
                    )
                    return
                logger.info("Gate 3 (%s): PASSED (sentiment=%.2f).", ticker, sentiment_score)
                self.telemetry.gate_pass("llm", ticker, llm_result)
                self._track_gate_event(
                    gate="llm",
                    ticker=ticker,
                    status="pass",
                    metrics={"confidence": sentiment_score},
                )
                self._persist_bias_from_llm(ticker, llm_result)
            else:
                logger.warning(
                    "Gate 3 (%s): Error calling LLM (%s). Falling back to RL output.",
                    ticker,
                    llm_outcome.failure.error,
                )
                self.telemetry.gate_reject(
                    "llm",
                    ticker,
                    {
                        "error": llm_outcome.failure.error,
                        "reason": "exception",
                        "attempts": llm_outcome.failure.metadata.get("attempts"),
                    },
                )
                self._track_gate_event(
                    gate="llm",
                    ticker=ticker,
                    status="error",
                    metrics={"confidence": sentiment_score},
                )
        else:
            logger.info("Gate 3 (%s): Skipped to protect budget.", ticker)
            self.telemetry.record(
                event_type="gate.llm",
                ticker=ticker,
                status="skipped",
                payload={
                    "remaining_budget": self.budget_controller.remaining_budget,
                    "model": llm_model,
                },
            )
            self._track_gate_event(
                gate="llm",
                ticker=ticker,
                status="skipped",
                metrics={"confidence": sentiment_score},
            )

        # Gate 3.5: Introspective Awareness (Dec 2025 - Anthropic research)
        # Combines self-consistency, epistemic uncertainty, and self-critique
        introspection_multiplier = 1.0
        if self.introspective_council:
            try:
                import asyncio

                # Prepare market data for introspection
                market_data = {
                    "symbol": ticker,
                    "momentum_strength": momentum_signal.strength,
                    "rl_confidence": rl_decision.get("confidence", 0.0),
                    "sentiment_score": sentiment_score,
                    "indicators": momentum_signal.indicators,
                }

                # Run introspective analysis
                introspection_result = asyncio.get_event_loop().run_until_complete(
                    self.introspective_council.analyze_trade(
                        symbol=ticker,
                        market_data=market_data,
                    )
                )

                # Log introspection metrics
                self.telemetry.record(
                    event_type="gate.introspection",
                    ticker=ticker,
                    status="pass" if introspection_result.execute else "reject",
                    payload={
                        "combined_confidence": introspection_result.combined_confidence,
                        "epistemic_uncertainty": introspection_result.epistemic_uncertainty,
                        "aleatoric_uncertainty": introspection_result.aleatoric_uncertainty,
                        "introspection_state": introspection_result.introspection_state.value,
                        "position_multiplier": introspection_result.position_multiplier,
                        "recommendation": introspection_result.recommendation,
                    },
                )

                # Track uncertainty for calibration analysis
                if self.uncertainty_tracker:
                    self.uncertainty_tracker.record(
                        symbol=ticker,
                        decision=introspection_result.action,
                        epistemic_score=introspection_result.epistemic_uncertainty,
                        aleatoric_score=introspection_result.aleatoric_uncertainty,
                        aggregate_confidence=introspection_result.combined_confidence,
                        consistency_score=introspection_result.introspective_confidence,
                        vote_breakdown={},
                        introspection_state=introspection_result.introspection_state.value,
                        knowledge_gaps=introspection_result.knowledge_gaps,
                        trade_executed=introspection_result.execute,
                    )

                # Apply position multiplier or reject
                if not introspection_result.execute:
                    logger.info(
                        "Gate 3.5 (%s): REJECTED by introspection (confidence=%.2f, state=%s)",
                        ticker,
                        introspection_result.combined_confidence,
                        introspection_result.introspection_state.value,
                    )
                    return

                introspection_multiplier = introspection_result.position_multiplier
                logger.info(
                    "Gate 3.5 (%s): PASSED (confidence=%.2f, multiplier=%.2f)",
                    ticker,
                    introspection_result.combined_confidence,
                    introspection_multiplier,
                )

            except Exception as e:
                logger.warning("Gate 3.5 (%s): Introspection failed, continuing: %s", ticker, e)

        # RAG Context - Query historical knowledge for this ticker (Dec 2025)
        rag_sentiment = None
        if self.rag_retriever:
            try:
                # Get recent news and sentiment from RAG
                rag_sentiment = self.rag_retriever.get_market_sentiment(
                    ticker=ticker,
                    days_back=7,
                )
                self.rag_retriever.get_ticker_context(
                    ticker=ticker,
                    n_results=5,
                    days_back=7,
                )
                if rag_sentiment.get("article_count", 0) > 0:
                    logger.info(
                        "RAG Context (%s): Found %d articles, sentiment=%.2f",
                        ticker,
                        rag_sentiment.get("article_count", 0),
                        rag_sentiment.get("sentiment_score", 0.0),
                    )
                    self.telemetry.record(
                        event_type="rag.context",
                        ticker=ticker,
                        status="success",
                        payload={
                            "article_count": rag_sentiment.get("article_count", 0),
                            "sentiment_score": rag_sentiment.get("sentiment_score", 0.0),
                            "sources": rag_sentiment.get("sources", []),
                        },
                    )
                    # Adjust sentiment score based on RAG if we have articles
                    if rag_sentiment.get("sentiment_score") is not None:
                        rag_weight = 0.3  # 30% weight to RAG sentiment
                        sentiment_score = (
                            sentiment_score * (1 - rag_weight)
                            + rag_sentiment["sentiment_score"] * rag_weight
                        )
                        logger.info(
                            "RAG Context (%s): Adjusted sentiment to %.2f (RAG weight=%.0f%%)",
                            ticker,
                            sentiment_score,
                            rag_weight * 100,
                        )
            except Exception as e:
                logger.debug("RAG context query failed for %s: %s", ticker, e)

        allocation_plan = self.smart_dca.plan_allocation(
            ticker=ticker,
            momentum_strength=momentum_signal.strength,
            rl_confidence=rl_decision.get("confidence", 0.0),
            sentiment_score=sentiment_score,
        )
        if allocation_plan.cap <= 0:
            logger.info(
                "Smart DCA: sentiment reduced allocation for %s (bucket=%s). Redirecting to safety.",
                ticker,
                allocation_plan.bucket,
            )
            self.telemetry.record(
                event_type="dca.skip",
                ticker=ticker,
                status="negative_sentiment",
                payload={
                    "bucket": allocation_plan.bucket,
                    "confidence": allocation_plan.confidence,
                    "remaining": self.smart_dca.remaining_budget().get(allocation_plan.bucket, 0.0),
                },
            )
            return

        # Apply introspection multiplier to position sizing (Gate 3.5)
        original_cap = allocation_plan.cap
        allocation_plan.cap *= introspection_multiplier
        if introspection_multiplier < 1.0:
            logger.info(
                "Gate 3.5 (%s): Position reduced %.0f%% ($%.2f -> $%.2f) due to uncertainty",
                ticker,
                (1 - introspection_multiplier) * 100,
                original_cap,
                allocation_plan.cap,
            )

        # Gather recent history for ATR-based sizing and stops
        hist = None
        current_price = momentum_signal.indicators.get("last_price")
        atr_pct = None
        try:
            from src.utils.market_data import MarketDataFetcher
            from src.utils.technical_indicators import calculate_atr

            fetcher = MarketDataFetcher()
            res = fetcher.get_daily_bars(symbol=ticker, lookback_days=60)
            hist = res.data
            if current_price is None and hist is not None and not hist.empty:
                current_price = float(hist["Close"].iloc[-1])
            if hist is not None and current_price:
                atr_val = float(calculate_atr(hist))
                if atr_val and current_price:
                    atr_pct = atr_val / float(current_price)
        except Exception as exc:  # pragma: no cover - fail-open
            logger.debug("History fetch failed for %s: %s", ticker, exc)

        # Gate 4: Risk sizing and execution
        risk_outcome = self.failure_manager.run(
            gate="risk",
            ticker=ticker,
            operation=lambda: self.risk_manager.calculate_size(
                ticker=ticker,
                account_equity=self.executor.account_equity,
                signal_strength=momentum_signal.strength,
                rl_confidence=rl_decision.get("confidence", 0.0),
                sentiment_score=sentiment_score,
                multiplier=rl_decision.get("suggested_multiplier", 1.0),
                current_price=current_price,
                hist=hist,
                market_regime=regime_snapshot.get("label"),
                allocation_cap=allocation_plan.cap,
            ),
            event_type="gate.risk",
        )
        if not risk_outcome.ok:
            logger.error(
                "Gate 4 (%s): Risk sizing failed: %s",
                ticker,
                risk_outcome.failure.error,
            )
            self._track_gate_event(
                gate="risk",
                ticker=ticker,
                status="error",
                metrics={"confidence": rl_decision.get("confidence", 0.0)},
            )
            return

        order_size = risk_outcome.result

        if order_size <= 0:
            logger.info("Gate 4 (%s): REJECTED (position size calculated as 0).", ticker)
            self.telemetry.gate_reject(
                "risk",
                ticker,
                {
                    "order_size": order_size,
                    "account_equity": self.executor.account_equity,
                },
            )
            self._track_gate_event(
                gate="risk",
                ticker=ticker,
                status="reject",
                metrics={"confidence": rl_decision.get("confidence", 0.0)},
            )
            return

        self.smart_dca.reserve(allocation_plan.bucket, order_size)
        logger.info("Executing BUY %s for $%.2f", ticker, order_size)

        # CRITICAL: All trades go through the mandatory gateway
        trade_request = TradeRequest(
            symbol=ticker, side="buy", notional=order_size, source="orchestrator"
        )
        gateway_decision = self.trade_gateway.evaluate(trade_request)

        if not gateway_decision.approved:
            if RejectionReason.MINIMUM_BATCH_NOT_MET not in gateway_decision.rejection_reasons:
                self.smart_dca.release(allocation_plan.bucket, order_size)
            logger.warning(
                "Gate GATEWAY (%s): REJECTED by Trade Gateway - %s",
                ticker,
                [r.value for r in gateway_decision.rejection_reasons],
            )
            self.telemetry.gate_reject(
                "gateway",
                ticker,
                {
                    "rejection_reasons": [r.value for r in gateway_decision.rejection_reasons],
                    "risk_score": gateway_decision.risk_score,
                },
            )
            return

        order_outcome = self.failure_manager.run(
            gate="execution.order",
            ticker=ticker,
            operation=lambda: self.trade_gateway.execute(gateway_decision),
            event_type="execution.order",
        )
        if not order_outcome.ok:
            self.smart_dca.release(allocation_plan.bucket, order_size)
            logger.error("Execution failed for %s: %s", ticker, order_outcome.failure.error)
            return
        order = order_outcome.result
        self.telemetry.gate_pass(
            "risk",
            ticker,
            {"order_size": order_size, "account_equity": self.executor.account_equity},
        )
        self._track_gate_event(
            gate="risk",
            ticker=ticker,
            status="pass",
            metrics={"confidence": rl_decision.get("confidence", 0.0)},
        )
        cost_estimate = self._estimate_execution_costs(order_size)

        # A2 Adaptation: Track RL prediction for future confidence calibration
        prediction_timestamp = datetime.now(timezone.utc).isoformat()
        self.telemetry.order_event(
            ticker,
            {
                "order": order,
                "rl": rl_decision,
                "cost_estimate": cost_estimate,
                "session_type": (self.session_profile or {}).get("session_type"),
                # Prediction tracking for A2 adaptation mode
                "predicted_confidence": rl_decision.get("confidence", 0.0),
                "predicted_action": rl_decision.get("action", "unknown"),
                "prediction_timestamp": prediction_timestamp,
            },
        )
        self.telemetry.record(
            event_type="dca.allocate",
            ticker=ticker,
            status="allocated",
            payload={
                "bucket": allocation_plan.bucket,
                "notional": order_size,
                "cap": allocation_plan.cap,
                "remaining_bucket": self.smart_dca.remaining_budget().get(
                    allocation_plan.bucket, 0.0
                ),
            },
        )

        # Place ATR-based stop-loss if possible
        try:
            if current_price and current_price > 0:
                stop_price = self.risk_manager.calculate_stop_loss(
                    ticker=ticker, entry_price=float(current_price), direction="long", hist=hist
                )
                # Approximate quantity from notional if fill qty unavailable
                qty = order.get("filled_qty") or (order_size / float(current_price))
                stop_order = self.executor.set_stop_loss(ticker, float(qty), float(stop_price))
                self.telemetry.record(
                    event_type="execution.stop",
                    ticker=ticker,
                    status="submitted",
                    payload={
                        "stop": stop_order,
                        "atr_pct": atr_pct,
                        "atr_multiplier": float(os.getenv("ATR_STOP_MULTIPLIER", "2.0")),
                    },
                )
        except Exception as exc:  # pragma: no cover - non-fatal
            logger.info("Stop-loss placement skipped for %s: %s", ticker, exc)

        # Track position entry with features for DiscoRL online learning
        try:
            self.position_manager.track_entry(
                symbol=ticker,
                entry_date=datetime.now(),
                entry_features=momentum_signal.indicators,
            )
            logger.debug(f"Tracked entry for {ticker} with features for DiscoRL online learning")
        except Exception as exc:
            logger.warning(f"Failed to track entry for {ticker}: {exc}")

        # Playwright MCP: Trade verification with screenshot audit trail
        verify_trades = os.getenv("ENABLE_TRADE_VERIFICATION", "true").lower() in {
            "1",
            "true",
            "yes",
        }
        if verify_trades and order.get("id"):
            try:
                import asyncio

                order_id = order.get("id", "")
                order_qty = (
                    order.get("filled_qty")
                    or order.get("qty")
                    or (order_size / float(current_price or 1))
                )
                verification = asyncio.get_event_loop().run_until_complete(
                    self.trade_verifier.verify_order_execution(
                        order_id=str(order_id),
                        expected_symbol=ticker,
                        expected_qty=float(order_qty),
                        expected_side="buy",
                        api_response=order,
                    )
                )
                self.telemetry.record(
                    event_type="execution.verification",
                    ticker=ticker,
                    status="verified" if verification.verified else "unverified",
                    payload={
                        "order_id": order_id,
                        "verified": verification.verified,
                        "screenshot": str(verification.screenshot_path)
                        if verification.screenshot_path
                        else None,
                        "errors": verification.errors,
                    },
                )
                if verification.verified:
                    logger.info("Trade verification PASSED for %s (order=%s)", ticker, order_id)
                else:
                    logger.warning(
                        "Trade verification FAILED for %s (order=%s): %s",
                        ticker,
                        order_id,
                        verification.errors,
                    )
            except Exception as verify_exc:
                logger.warning("Trade verification skipped for %s: %s", ticker, verify_exc)

    def _process_ticker_v2(self, ticker: str, rl_threshold: float) -> None:
        """
        LLM-friendly ticker processing using the gate pipeline.

        This is the refactored version (Dec 2025) that replaces the 866-line
        monolithic method with a ~100-line orchestrator calling modular gates.

        Each gate is <150 lines and independently testable.
        """
        logger.info("--- Processing %s (v2 pipeline) ---", ticker)
        self.telemetry.start_ticker_decision(ticker)

        # =======================================================================
        # SECURITY GATE (runs FIRST, before any LLM processing)
        # Validates ticker against injection patterns and blocklists
        # =======================================================================
        security_result = self.gate_security.evaluate(
            ticker=ticker,
            external_data={},  # Will be populated with news/sentiment later
            trade_signal={"symbol": ticker, "action": "ANALYZE"},
        )
        if not security_result.passed:
            logger.warning(
                "🛡️  Security Gate BLOCKED %s: %s",
                ticker,
                security_result.reason,
            )
            self.telemetry.record(
                event_type="security.block",
                ticker=ticker,
                status="blocked",
                payload=security_result.data,
            )
            return

        # =======================================================================
        # MEMORY GATE (query historical pattern performance)
        # Provides context on how similar trades performed in the past
        # =======================================================================
        memory_result = self.gate_memory.evaluate(
            ticker=ticker,
            strategy="momentum",  # Will be updated based on actual strategy
            entry_reason="technical_signal",
            min_win_rate=0.35,  # Low threshold - we're gathering data, not filtering
        )
        memory_context = memory_result.data or {}
        if memory_result.data and memory_result.data.get("pattern_history"):
            logger.info(
                "📊 Memory: %s has %d prior trades (%.1f%% win rate)",
                ticker,
                memory_result.data.get("trade_count", 0),
                memory_result.data.get("win_rate", 0) * 100,
            )

        # Pre-flight: Get allocation plan
        pre_plan = self.smart_dca.plan_allocation(
            ticker=ticker,
            momentum_strength=0.0,  # Will update after Gate 1
            rl_confidence=0.0,
            sentiment_score=0.0,
        )

        if pre_plan.cap <= 0:
            logger.info("Smart DCA: bucket %s exhausted, skipping %s", pre_plan.bucket, ticker)
            self.telemetry.record(
                event_type="dca.skip",
                ticker=ticker,
                status="exhausted",
                payload={"bucket": pre_plan.bucket},
            )
            return

        # Run the gate pipeline (Gates 0-4)
        success, ctx, gate_results = self.gate_pipeline.run(
            ticker=ticker,
            rl_threshold=rl_threshold,
            session_profile=self.session_profile,
            allocation_cap=pre_plan.cap,
        )

        # Log all gate results for observability
        for result in gate_results:
            self._track_gate_event(
                gate=result.gate_name,
                ticker=ticker,
                status="pass" if result.passed else "reject",
                metrics={"confidence": result.confidence},
            )

        if not success:
            last_result = gate_results[-1] if gate_results else None
            logger.info(
                "Pipeline rejected %s at gate %s: %s",
                ticker,
                last_result.gate_name if last_result else "unknown",
                last_result.reason if last_result else "no results",
            )
            return

        # Re-plan allocation with actual momentum/RL data
        allocation_plan = self.smart_dca.plan_allocation(
            ticker=ticker,
            momentum_strength=ctx.momentum_strength,
            rl_confidence=ctx.rl_decision.get("confidence", 0.0),
            sentiment_score=ctx.sentiment_score,
        )
        ctx.allocation_plan = allocation_plan

        if allocation_plan.cap <= 0:
            logger.info("Smart DCA: allocation exhausted post-gates for %s", ticker)
            return

        # ========================================================================
        # RULE DISCOVERY ENFORCEMENT (Dec 2025)
        # Both RAG and TradeMemory are now ENFORCED, not just logged
        # ========================================================================

        # 1. RAG pre-trade query: Get relevant lessons BEFORE execution
        rag_result = self.rag_query.query(ticker, ctx)
        ctx.rag_context = rag_result
        if rag_result.get("warnings"):
            logger.warning("⚠️  RAG Warnings for %s:", ticker)
            for warning in rag_result["warnings"]:
                logger.warning("    %s", warning)

        # ENFORCE RAG blocking
        if rag_result.get("should_block"):
            logger.warning(
                "🚫 RAG BLOCK (%s): Trade blocked by lessons learned - %s",
                ticker,
                rag_result.get("block_reason"),
            )
            self.telemetry.gate_reject(
                "rag_enforcement",
                ticker,
                {
                    "block_reason": rag_result.get("block_reason"),
                    "lessons": [lesson.get("title") for lesson in rag_result.get("lessons", [])],
                },
            )
            return

        # 2. TradeMemory pre-trade query: Check historical pattern performance
        # Derive strategy and entry_reason from context
        strategy = "momentum_long"  # Default strategy
        if ctx.momentum_signal:
            strength = ctx.momentum_strength
            if strength >= 0.8:
                entry_reason = "strong_momentum"
            elif strength >= 0.6:
                entry_reason = "moderate_momentum"
            else:
                entry_reason = "weak_momentum"
        else:
            entry_reason = "unknown"

        memory_result = self.trade_memory_query.query(ticker, strategy, entry_reason)

        # ENFORCE TradeMemory blocking
        if memory_result.get("should_block"):
            logger.warning(
                "🚫 TradeMemory BLOCK (%s): Trade blocked by historical pattern - %s",
                ticker,
                memory_result.get("block_reason"),
            )
            self.telemetry.gate_reject(
                "trade_memory_enforcement",
                ticker,
                {
                    "block_reason": memory_result.get("block_reason"),
                    "pattern": memory_result.get("pattern"),
                    "win_rate": memory_result.get("win_rate"),
                    "sample_size": memory_result.get("sample_size"),
                },
            )
            return

        # Log memory recommendation if found (for learning)
        if memory_result.get("found"):
            logger.info(
                "📚 TradeMemory (%s): Pattern '%s' → %s (%.0f%% win rate, %d trades)",
                ticker,
                memory_result.get("pattern"),
                memory_result.get("recommendation"),
                memory_result.get("win_rate", 0) * 100,
                memory_result.get("sample_size", 0),
            )

        # ========================================================================

        # Fetch price and history for risk calculation
        try:
            price_data = self.executor.get_current_price(ticker)
            ctx.current_price = price_data.get("price")
            ctx.hist = self.momentum_agent._fetch_history(ticker)
            if ctx.hist is not None and len(ctx.hist) >= 14:
                atr = self.risk_manager._calculate_atr(ctx.hist, period=14)
                ctx.atr_pct = (atr / ctx.current_price * 100) if ctx.current_price else None
        except Exception as e:
            logger.warning("Failed to fetch price/history for %s: %s", ticker, e)

        # Microstructure features and regime detection
        try:
            micro_features = self.microstructure.extract(ticker)
            if "microstructure_error" not in micro_features:
                if ctx.momentum_signal:
                    ctx.momentum_signal.indicators.update(micro_features)
                ctx.regime_snapshot = self.regime_detector.detect(micro_features)
        except Exception as e:
            logger.debug("Microstructure extraction failed for %s: %s", ticker, e)

        # Gate 4: Risk sizing (using pipeline result)
        risk_result = self.gate4.evaluate(ticker, ctx, allocation_plan.cap)
        if not risk_result.passed:
            logger.info("Gate 4 (%s): REJECTED - %s", ticker, risk_result.reason)
            return

        order_size = risk_result.data.get("order_size", 0.0)
        if order_size <= 0:
            logger.info("Gate 4 (%s): Order size is 0, skipping", ticker)
            return

        ctx.order_size = order_size

        # Gate 5: Execution
        exec_result = self.gate5.execute(ticker, ctx, order_size)
        if not exec_result.passed:
            logger.warning("Gate 5 (%s): Execution failed - %s", ticker, exec_result.reason)
            return

        # Record successful execution
        order = exec_result.data.get("order", {})
        self.telemetry.order_event(
            ticker,
            {
                "order": order,
                "rl": ctx.rl_decision,
                "session_type": (self.session_profile or {}).get("session_type"),
                "predicted_confidence": ctx.rl_decision.get("confidence", 0.0),
            },
        )
        self.telemetry.record(
            event_type="dca.allocate",
            ticker=ticker,
            status="allocated",
            payload={
                "bucket": allocation_plan.bucket,
                "notional": order_size,
                "cap": allocation_plan.cap,
            },
        )

        # Gate 5.5: Execution quality monitoring (anomaly detection)
        # Analyzes slippage, execution price, and identifies anomalies
        try:
            import sys
            from datetime import datetime as dt

            anomaly_script = os.path.join(
                os.path.dirname(__file__),
                "../../.claude/skills/anomaly_detector/scripts/anomaly_detector.py",
            )
            if os.path.exists(anomaly_script):
                sys.path.insert(0, os.path.dirname(anomaly_script))
                from anomaly_detector import AnomalyDetector

                detector = AnomalyDetector()

                # Extract order details for anomaly detection
                filled_price = (
                    order.get("filled_avg_price") if isinstance(order, dict) else ctx.current_price
                )
                if filled_price is None:
                    filled_price = ctx.current_price

                execution_analysis = detector.detect_execution_anomalies(
                    order_id=str(order.get("id", "unknown"))
                    if isinstance(order, dict)
                    else "unknown",
                    expected_price=ctx.current_price,
                    actual_fill_price=float(filled_price),
                    quantity=abs(order_size / ctx.current_price) if ctx.current_price > 0 else 0,
                    order_type=order.get("type", "market") if isinstance(order, dict) else "market",
                    timestamp=dt.now().isoformat(),
                )

                if execution_analysis.get("success"):
                    analysis = execution_analysis.get("analysis", {})
                    slippage = analysis.get("slippage", {})
                    quality = analysis.get("execution_quality", {})

                    logger.info(
                        "Gate 5.5 (%s): Execution quality - slippage=%.3f%%, grade=%s, score=%.1f",
                        ticker,
                        slippage.get("percentage", 0.0),
                        quality.get("grade", "N/A"),
                        quality.get("score", 0.0),
                    )

                    if analysis.get("anomalies_detected"):
                        logger.warning(
                            "Gate 5.5 (%s): ANOMALY DETECTED - warnings: %s",
                            ticker,
                            analysis.get("warnings", []),
                        )

                    self.telemetry.record(
                        event_type="gate.anomaly_detector",
                        ticker=ticker,
                        status="analyzed",
                        payload={
                            "slippage_pct": slippage.get("percentage"),
                            "slippage_severity": slippage.get("severity"),
                            "execution_grade": quality.get("grade"),
                            "execution_score": quality.get("score"),
                            "anomalies_detected": analysis.get("anomalies_detected"),
                            "warnings": analysis.get("warnings", []),
                        },
                    )
        except Exception as anomaly_exc:
            logger.warning("Gate 5.5 (%s): Anomaly detection failed: %s", ticker, anomaly_exc)
            self.telemetry.record(
                event_type="gate.anomaly_detector",
                ticker=ticker,
                status="error",
                payload={"error": str(anomaly_exc)},
            )

        logger.info("✅ %s processed successfully via v2 pipeline", ticker)

        # =======================================================================
        # FEEDBACK LOOP: Store trade entry for outcome tracking
        # When this position is closed, we'll call gate_memory.record_outcome()
        # to complete the learning cycle
        # =======================================================================
        try:
            entry_record = {
                "ticker": ticker,
                "strategy": strategy,  # Using actual strategy from line 2465
                "entry_reason": entry_reason,  # Using actual entry_reason from lines 2469-2475
                "order_id": order.get("id") if isinstance(order, dict) else None,
                "entry_time": order.get("created_at") if isinstance(order, dict) else None,
                "entry_price": ctx.current_price,
                "order_size": order_size,
                "memory_context": memory_context,
            }
            # Store in pending_outcomes for later matching when position closes
            if not hasattr(self, "_pending_trade_outcomes"):
                self._pending_trade_outcomes = {}
            self._pending_trade_outcomes[ticker] = entry_record
            logger.debug("📝 Trade entry recorded for feedback loop: %s", ticker)
        except Exception as e:
            logger.warning("Failed to record trade entry for feedback: %s", e)

    def _deploy_safe_reserve(self) -> None:
        sweep = self.smart_dca.drain_to_safe()
        if not sweep or sweep.amount <= 0:
            return

        self.telemetry.record(
            event_type="dca.safe_sweep",
            ticker=sweep.symbol,
            status="pending",
            payload={
                "amount": sweep.amount,
                "buckets": sweep.buckets,
            },
        )

        trade_request = TradeRequest(
            symbol=sweep.symbol,
            side="buy",
            notional=sweep.amount,
            source="smart_dca.safe",
        )
        decision = self.trade_gateway.evaluate(trade_request)

        if not decision.approved:
            level = logging.INFO
            if RejectionReason.MINIMUM_BATCH_NOT_MET not in decision.rejection_reasons:
                level = logging.WARNING
            logger.log(
                level,
                "Smart DCA sweep rejected for %s: %s",
                sweep.symbol,
                [r.value for r in decision.rejection_reasons],
            )
            self.telemetry.record(
                event_type="dca.safe_sweep",
                ticker=sweep.symbol,
                status="rejected",
                payload={
                    "amount": sweep.amount,
                    "reasons": [r.value for r in decision.rejection_reasons],
                },
            )
            return

        order_outcome = self.failure_manager.run(
            gate="execution.safe_dca",
            ticker=sweep.symbol,
            operation=lambda: self.trade_gateway.execute(decision),
            event_type="execution.safe_dca",
        )
        if not order_outcome.ok:
            logger.error(
                "Smart DCA sweep execution failed for %s: %s",
                sweep.symbol,
                order_outcome.failure.error,
            )
            return

        self.telemetry.record(
            event_type="dca.safe_sweep",
            ticker=sweep.symbol,
            status="executed",
            payload={
                "amount": sweep.amount,
                "buckets": sweep.buckets,
                "order": order_outcome.result,
            },
        )

    def _persist_bias_from_llm(self, ticker: str, llm_payload: dict) -> None:
        try:
            score = float(llm_payload.get("score", 0.0))
            now = datetime.now(timezone.utc)
            snapshot = BiasSnapshot(
                symbol=ticker,
                score=score,
                direction=self._score_to_direction(score),
                conviction=min(1.0, max(0.0, abs(score))),
                reason=llm_payload.get("reason", "llm sentiment"),
                created_at=now,
                expires_at=now + timedelta(minutes=self.bias_snapshot_ttl_minutes),
                model=llm_payload.get("model"),
                sources=llm_payload.get("sources", []),
                metadata={"source": "orchestrator.llm", "raw": llm_payload},
            )
            self.bias_store.persist(snapshot)
        except Exception as exc:  # pragma: no cover - analytics only
            logger.debug("Failed to persist bias snapshot for %s: %s", ticker, exc)

    @staticmethod
    def _score_to_direction(score: float) -> str:
        if score >= 0.2:
            return "bullish"
        if score <= -0.2:
            return "bearish"
        return "neutral"

    def run_delta_rebalancing(self) -> dict:
        """
        Gate 5: Delta-Neutral Rebalancing (Post-Execution)

        McMillan Rule: If |net delta| > 60, buy/sell SPY shares to bring it under 25.

        This should be called after all ticker processing to ensure the overall
        portfolio delta exposure remains within acceptable bounds.

        CAPITAL GUARD: Delta hedging requires $50k+ to be efficient.
        For smaller accounts, frequent adjustments destroy alpha through fees.

        Returns:
            Dict with rebalancing results
        """
        logger.info("--- Gate 5: Delta-Neutral Rebalancing Check ---")

        # CRITICAL: Capital efficiency guard - disable delta hedging for small accounts
        account_equity = self.executor.account_equity
        delta_hedge_check = self.capital_calculator.should_enable_delta_hedging(account_equity)

        if not delta_hedge_check["enabled"]:
            logger.warning("Gate 5: Delta hedging DISABLED - %s", delta_hedge_check["reason"])
            self.telemetry.record(
                event_type="gate.delta_rebalance",
                ticker="PORTFOLIO",
                status="disabled",
                payload={
                    "reason": delta_hedge_check["reason"],
                    "account_equity": account_equity,
                    "capital_gap": delta_hedge_check.get("capital_gap", 0),
                    "days_to_enable": delta_hedge_check.get("days_to_enable", 0),
                },
            )
            return {
                "action": "disabled",
                "reason": delta_hedge_check["reason"],
                "recommendation": delta_hedge_check.get(
                    "recommendation", "Use defined-risk strategies"
                ),
            }

        try:
            # Calculate current delta exposure
            delta_analysis = self.options_risk_monitor.calculate_net_delta()

            self.telemetry.record(
                event_type="gate.delta_rebalance",
                ticker="PORTFOLIO",
                status="checking",
                payload={
                    "net_delta": delta_analysis["net_delta"],
                    "max_allowed": delta_analysis["max_allowed"],
                    "rebalance_needed": delta_analysis["rebalance_needed"],
                },
            )

            if not delta_analysis["rebalance_needed"]:
                logger.info(
                    "Gate 5: Delta exposure acceptable (net delta: %.1f, max: %.1f)",
                    delta_analysis["net_delta"],
                    delta_analysis["max_allowed"],
                )
                return {"action": "none", "delta_analysis": delta_analysis}

            # Calculate hedge trade
            hedge = self.options_risk_monitor.calculate_delta_hedge(delta_analysis["net_delta"])

            if hedge["action"] == "NONE":
                return {"action": "none", "delta_analysis": delta_analysis}

            logger.warning(
                "Gate 5: Delta rebalancing triggered - %s %d %s",
                hedge["action"],
                hedge["quantity"],
                hedge["symbol"],
            )

            # Execute the hedge through the gateway
            try:
                hedge_request = TradeRequest(
                    symbol=hedge["symbol"],
                    side=hedge["action"].lower(),
                    quantity=hedge["quantity"],
                    source="delta_hedge",
                )
                hedge_decision = self.trade_gateway.evaluate(hedge_request)

                if not hedge_decision.approved:
                    logger.warning(
                        "Delta hedge rejected by gateway: %s",
                        [r.value for r in hedge_decision.rejection_reasons],
                    )
                    return {
                        "action": "rejected",
                        "reasons": [r.value for r in hedge_decision.rejection_reasons],
                    }

                order = self.trade_gateway.execute(hedge_decision)

                self.telemetry.record(
                    event_type="gate.delta_rebalance",
                    ticker=hedge["symbol"],
                    status="executed",
                    payload={
                        "hedge": hedge,
                        "order": order,
                        "pre_rebalance_delta": delta_analysis["net_delta"],
                        "target_delta": hedge.get("target_delta"),
                    },
                )

                logger.info(
                    "✅ Delta hedge executed: %s %d %s (Order ID: %s)",
                    hedge["action"],
                    hedge["quantity"],
                    hedge["symbol"],
                    order.get("id", "N/A"),
                )

                return {
                    "action": "hedged",
                    "hedge": hedge,
                    "order": order,
                    "delta_analysis": delta_analysis,
                }

            except Exception as e:
                logger.error("Failed to execute delta hedge: %s", e)
                self.telemetry.record(
                    event_type="gate.delta_rebalance",
                    ticker=hedge["symbol"],
                    status="failed",
                    payload={"error": str(e), "hedge": hedge},
                )
                return {"action": "failed", "error": str(e), "hedge": hedge}

        except Exception as e:
            logger.error("Delta rebalancing check failed: %s", e)
            return {"action": "error", "error": str(e)}

    def run_options_risk_check(self, option_prices: dict = None) -> dict:
        """Run options risk check - delegates to OptionsStrategyCoordinator.

        Jan 10, 2026: Extracted to OptionsStrategyCoordinator for cleaner architecture.
        """
        return self.options_coordinator.run_options_risk_check(option_prices)

    def run_options_strategy(self) -> dict:
        """Run options strategy - delegates to OptionsStrategyCoordinator.

        Jan 10, 2026: Extracted to OptionsStrategyCoordinator for cleaner architecture.
        """
        return self.options_coordinator.run_options_strategy()

    def run_iv_options_execution(self) -> dict:
        """Run IV options execution - delegates to OptionsStrategyCoordinator.

        Jan 10, 2026: Extracted to OptionsStrategyCoordinator for cleaner architecture.
        """
        return self.options_coordinator.run_iv_options_execution()

    def _maybe_reallocate_for_weekend(self, session: dict | None = None) -> None:
        """Reallocate for weekend - delegates to SessionManager.

        Jan 10, 2026: Extracted to SessionManager for cleaner architecture.
        """
        self.session_manager.maybe_reallocate_for_weekend(self.smart_dca, self.telemetry)
