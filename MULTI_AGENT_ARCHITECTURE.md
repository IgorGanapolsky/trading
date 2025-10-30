# Multi-Agent AI Trading System Architecture

**Version:** 1.0.0
**Date:** 2025-10-30
**Status:** Architecture Design Document

---

## Executive Summary

This document outlines a comprehensive multi-agent AI trading system architecture designed to orchestrate specialized agents for research, signal generation, risk management, execution, and supervision. The system leverages cutting-edge communication protocols (MCP, A2A), reinforcement learning for signal generation, and human-in-the-loop validation for critical decisions.

**Key Features:**
- 5 specialized agents with clear separation of concerns
- Hierarchical orchestrator-worker pattern using Claude Agents SDK
- Multi-protocol communication (MCP, message queues, direct calls)
- RL-based signal generation with ensemble learning
- Comprehensive risk management with circuit breakers
- Human-in-the-loop validation for anomalies and high-risk trades
- Real-time monitoring and performance tracking

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Architecture Diagram](#architecture-diagram)
3. [Agent Specifications](#agent-specifications)
4. [Communication Architecture](#communication-architecture)
5. [Agent Communication Flows](#agent-communication-flows)
6. [Implementation with Claude Agents SDK](#implementation-with-claude-agents-sdk)
7. [Code Structure Proposal](#code-structure-proposal)
8. [Human-in-the-Loop Integration](#human-in-the-loop-integration)
9. [Anomaly Detection & Circuit Breakers](#anomaly-detection--circuit-breakers)
10. [Deployment Architecture](#deployment-architecture)
11. [Security & Compliance](#security--compliance)
12. [Performance Metrics](#performance-metrics)
13. [Implementation Roadmap](#implementation-roadmap)

---

## System Overview

### Design Philosophy

The system follows a **hierarchical multi-agent architecture** where a Supervisor Agent orchestrates multiple specialized agents, each responsible for a specific domain in the trading pipeline. This design enables:

- **Modularity:** Each agent can be developed, tested, and scaled independently
- **Resilience:** Failure in one agent doesn't cascade to others
- **Specialization:** Deep expertise in each domain (research, signals, risk, execution)
- **Parallel Processing:** Multiple agents can work simultaneously
- **Context Isolation:** Agents maintain separate contexts, reducing token costs

### Core Principles

1. **Single Responsibility:** Each agent has one clear purpose
2. **Deny-All Security:** Agents have minimal permissions by default
3. **Confirmations for Sensitive Actions:** Human validation for high-risk operations
4. **Observability First:** Comprehensive logging and metrics
5. **Fail-Safe Defaults:** Circuit breakers and anomaly detection protect capital

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         MULTI-AGENT TRADING SYSTEM                           │
│                         (Orchestrator-Worker Pattern)                        │
└─────────────────────────────────────────────────────────────────────────────┘

                    ┌───────────────────────────────────┐
                    │      SUPERVISOR AGENT             │
                    │  (Claude Opus 4 - Orchestrator)   │
                    │                                   │
                    │  • Task Decomposition             │
                    │  • Agent Coordination             │
                    │  • Performance Tracking           │
                    │  • Logging & Audit Trail          │
                    │  • Human Escalation               │
                    └─────────────┬─────────────────────┘
                                  │
            ┌─────────────────────┼─────────────────────┐
            │                     │                     │
            │                     │                     │
    ┌───────▼─────────┐  ┌───────▼─────────┐  ┌───────▼─────────┐
    │  RESEARCH AGENT │  │  SIGNAL AGENT   │  │ RISK MANAGER    │
    │  (Claude Sonnet)│  │  (RL + Claude)  │  │     AGENT       │
    │                 │  │                 │  │ (Claude Sonnet) │
    │  • Market Data  │  │  • RL Signals   │  │                 │
    │  • News/Sent.   │  │  • Entry/Exit   │  │  • Position Size│
    │  • Fundamentals │  │  • Multi-Model  │  │  • Stop-Loss    │
    │  • Technical    │  │    Ensemble     │  │  • Drawdown Mon.│
    └─────────┬───────┘  └────────┬────────┘  │  • Circuit Break│
              │                   │            └────────┬────────┘
              │                   │                     │
              │    MCP Protocol   │   Message Queue     │  Direct Call
              │    (Resources)    │     (Redis)         │   (Validation)
              │                   │                     │
              └───────────────────┴─────────────────────┘
                                  │
                                  │
                    ┌─────────────▼─────────────┐
                    │    EXECUTION AGENT        │
                    │    (Claude Sonnet)        │
                    │                           │
                    │  • Order Routing          │
                    │  • Fill Optimization      │
                    │  • Slippage Minimization  │
                    │  • Broker Integration     │
                    └─────────┬─────────────────┘
                              │
                              │ REST API / WebSocket
                              │
            ┌─────────────────┴──────────────────┐
            │                                    │
    ┌───────▼────────┐              ┌───────────▼────────┐
    │  ALPACA API    │              │  MARKET DATA       │
    │  (Execution)   │              │  (Real-time)       │
    └────────────────┘              └────────────────────┘


┌─────────────────────────────────────────────────────────────────────────────┐
│                        CROSS-CUTTING CONCERNS                                │
└─────────────────────────────────────────────────────────────────────────────┘

    ┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
    │  HUMAN-IN-LOOP   │     │  ANOMALY DETECT. │     │   MONITORING     │
    │                  │     │                  │     │                  │
    │  • High-Risk Val.│     │  • Pattern Det.  │     │  • Metrics       │
    │  • Confidence    │     │  • Fraud Det.    │     │  • Dashboards    │
    │  • Manual Override     │  • Deviation Mon.│     │  • Alerts        │
    └──────────────────┘     └──────────────────┘     └──────────────────┘

    ┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
    │  STATE MGMT      │     │  MESSAGE QUEUE   │     │   DATA STORE     │
    │  (Redis)         │     │  (Redis/Kafka)   │     │  (PostgreSQL)    │
    └──────────────────┘     └──────────────────┘     └──────────────────┘
```

---

## Agent Specifications

### 1. Research Agent

**Role:** Market intelligence gathering and analysis

**Responsibilities:**
- Fetch and process market data (prices, volume, indicators)
- Analyze news sentiment using multi-LLM ensemble
- Evaluate fundamentals (earnings, growth, valuation)
- Perform technical analysis (RSI, MACD, momentum)
- Generate market outlook reports

**Tools & Resources:**
- **MCP Resources:** Real-time market data feeds
- **MCP Tools:** News APIs, financial data APIs
- **Data Sources:** Yahoo Finance, Alpha Vantage, NewsAPI
- **LLMs:** Claude 3.5 Sonnet, GPT-4o, Gemini 2.0 Flash

**Inputs:**
- Symbol(s) to analyze
- Analysis depth (quick scan vs. deep dive)
- Timeframe (intraday, daily, weekly)

**Outputs:**
- Market sentiment score (-1.0 to 1.0)
- News summary and key events
- Technical indicator values
- Fundamental metrics
- Confidence score (0.0 to 1.0)

**Implementation:**
```python
class ResearchAgent:
    def __init__(self, llm_client, data_sources):
        self.llm_client = llm_client
        self.data_sources = data_sources
        self.cache = {}

    async def analyze_market(self, symbol: str) -> ResearchReport:
        # Multi-source data gathering
        market_data = await self._fetch_market_data(symbol)
        news = await self._fetch_news(symbol)
        fundamentals = await self._fetch_fundamentals(symbol)

        # Multi-LLM ensemble analysis
        sentiment = await self.llm_client.get_ensemble_sentiment(
            market_data, news
        )

        return ResearchReport(
            symbol=symbol,
            sentiment=sentiment,
            technical_indicators=market_data['indicators'],
            fundamentals=fundamentals,
            key_events=news[:5],
            confidence=self._calculate_confidence(sentiment)
        )
```

**Communication Protocol:**
- **Outbound:** Publishes research reports to `research.reports` topic (Redis Pub/Sub)
- **MCP:** Exposes market data as MCP Resources
- **Inbound:** Receives analysis requests from Supervisor

---

### 2. Signal Agent

**Role:** RL-based trading signal generation

**Responsibilities:**
- Generate entry/exit signals using reinforcement learning
- Ensemble multiple RL models (DQN, PPO, A2C)
- Combine RL signals with sentiment analysis
- Provide confidence scores for each signal
- Adapt to market conditions

**Architecture:**
```python
class SignalAgent:
    def __init__(self):
        # Multi-agent RL ensemble
        self.rl_models = {
            'dqn': DQNAgent(state_dim=50, action_dim=3),  # Buy/Hold/Sell
            'ppo': PPOAgent(state_dim=50, action_dim=3),
            'a2c': A2CAgent(state_dim=50, action_dim=3)
        }
        self.ensemble_weights = {'dqn': 0.4, 'ppo': 0.35, 'a2c': 0.25}
        self.signal_buffer = deque(maxlen=100)

    async def generate_signal(self, state: MarketState) -> TradingSignal:
        # Get signals from all RL models
        signals = {}
        for name, model in self.rl_models.items():
            action, confidence = model.predict(state.to_array())
            signals[name] = (action, confidence)

        # Ensemble voting with confidence weighting
        ensemble_action = self._weighted_ensemble(signals)

        # Validate with sentiment
        sentiment_check = await self._validate_with_sentiment(
            ensemble_action, state.symbol
        )

        return TradingSignal(
            symbol=state.symbol,
            action=ensemble_action,  # BUY/SELL/HOLD
            confidence=self._calculate_confidence(signals),
            reasoning=self._generate_reasoning(signals),
            timestamp=datetime.now()
        )
```

**RL Model Architecture:**
```
State Space (50 dimensions):
├─ Technical Indicators (20): RSI, MACD, BB, ATR, etc.
├─ Price Features (10): Returns, volatility, volume ratios
├─ Sentiment Features (10): News sentiment, social sentiment
├─ Market Features (10): VIX, sector rotation, correlation
└─ Position Features (5): Current position, P&L, exposure

Action Space (3):
├─ BUY: Enter long position
├─ SELL: Exit position or enter short
└─ HOLD: Maintain current position

Reward Function:
R(t) = α * returns(t) - β * risk(t) - γ * transaction_costs(t)
where α=1.0, β=0.5, γ=0.1
```

**Training Strategy:**
- **Online Learning:** Continuous training with recent market data
- **Experience Replay:** Store last 10,000 transitions
- **Multi-Timeframe:** Train on 5min, 15min, 1hour, 1day data
- **Backtesting:** Validate on historical data before deployment
- **Safety:** Paper trading for 30 days before live deployment

**Communication Protocol:**
- **Inbound:** Subscribes to `research.reports` topic
- **Outbound:** Publishes signals to `signals.trading` topic
- **State Storage:** Redis for model checkpoints

---

### 3. Risk Manager Agent

**Role:** Position sizing, stop-loss, and drawdown monitoring

**Responsibilities:**
- Validate all trades before execution
- Calculate position sizes based on risk parameters
- Monitor portfolio drawdown in real-time
- Implement circuit breakers
- Track consecutive losses
- Generate risk alerts

**Architecture:**
```python
class RiskManagerAgent:
    def __init__(self):
        self.max_daily_loss_pct = 2.0
        self.max_position_size_pct = 10.0
        self.max_drawdown_pct = 10.0
        self.max_consecutive_losses = 3

        self.circuit_breaker_active = False
        self.daily_pl = 0.0
        self.peak_equity = 0.0
        self.consecutive_losses = 0

    async def validate_trade(self, signal: TradingSignal,
                            account: AccountInfo) -> TradeValidation:
        # Check circuit breakers
        if self.circuit_breaker_active:
            return TradeValidation(
                approved=False,
                reason="Circuit breaker active",
                requires_human_review=True
            )

        # Check daily loss limit
        daily_loss_pct = (self.daily_pl / account.equity) * 100
        if daily_loss_pct < -self.max_daily_loss_pct:
            self._trigger_circuit_breaker("Daily loss limit exceeded")
            return TradeValidation(approved=False, reason="Daily loss limit")

        # Check drawdown
        current_drawdown = ((self.peak_equity - account.equity) /
                           self.peak_equity) * 100
        if current_drawdown > self.max_drawdown_pct:
            self._trigger_circuit_breaker("Max drawdown exceeded")
            return TradeValidation(approved=False, reason="Max drawdown")

        # Calculate position size
        position_size = self._calculate_position_size(
            account.equity,
            risk_per_trade=1.0,
            signal.confidence
        )

        # Check position size limit
        position_pct = (position_size / account.equity) * 100
        if position_pct > self.max_position_size_pct:
            return TradeValidation(
                approved=False,
                reason="Position size exceeds limit"
            )

        # Calculate stop-loss
        stop_loss_price = self._calculate_stop_loss(
            signal.action,
            signal.entry_price,
            atr=signal.market_state.atr
        )

        return TradeValidation(
            approved=True,
            position_size=position_size,
            stop_loss=stop_loss_price,
            take_profit=self._calculate_take_profit(signal),
            confidence=signal.confidence,
            warnings=self._generate_warnings(signal, account)
        )
```

**Circuit Breaker Logic:**
```
┌─────────────────────────────────────────────────────────┐
│              CIRCUIT BREAKER STATE MACHINE              │
└─────────────────────────────────────────────────────────┘

          ┌──────────┐
          │  CLOSED  │ ◄──── Normal trading
          │ (Active) │
          └────┬─────┘
               │
               │ Trigger: Daily loss > 2%
               │      OR Drawdown > 10%
               │      OR Consecutive losses >= 3
               │
          ┌────▼─────┐
          │   OPEN   │ ◄──── Trading suspended
          │ (Tripped)│
          └────┬─────┘
               │
               │ Reset: Next trading day
               │     OR Manual override with approval
               │
          ┌────▼─────┐
          │ HALF-OPEN│ ◄──── Testing recovery
          │ (Testing)│        (1 small test trade)
          └────┬─────┘
               │
               ├─ Success ──────► CLOSED
               │
               └─ Failure ──────► OPEN
```

**Risk Metrics Dashboard:**
- Daily P&L and limit usage
- Current drawdown vs. peak
- Position concentration (% in single position)
- Consecutive loss streak
- Sharpe ratio (rolling 30-day)
- Win rate and profit factor

**Communication Protocol:**
- **Inbound:** Direct synchronous calls from Execution Agent
- **Outbound:** Publishes alerts to `risk.alerts` topic
- **State:** Stores metrics in Redis with TTL

---

### 4. Execution Agent

**Role:** Order routing and fill optimization

**Responsibilities:**
- Route orders to broker (Alpaca)
- Optimize order execution (limit vs. market)
- Minimize slippage
- Handle partial fills
- Manage open orders
- Monitor fill prices

**Architecture:**
```python
class ExecutionAgent:
    def __init__(self, broker_client, risk_manager):
        self.broker = broker_client
        self.risk_manager = risk_manager
        self.active_orders = {}
        self.execution_log = []

    async def execute_trade(self, signal: TradingSignal) -> ExecutionResult:
        # Step 1: Get account info
        account = await self.broker.get_account_info()

        # Step 2: Risk validation
        validation = await self.risk_manager.validate_trade(signal, account)

        if not validation.approved:
            if validation.requires_human_review:
                # Escalate to human
                await self._escalate_to_human(signal, validation)
            return ExecutionResult(
                success=False,
                reason=validation.reason
            )

        # Step 3: Choose order type
        order_type = self._determine_order_type(signal, account)

        # Step 4: Submit order
        try:
            if order_type == 'market':
                order = await self.broker.submit_market_order(
                    symbol=signal.symbol,
                    side=signal.action,
                    notional=validation.position_size
                )
            else:  # limit order
                limit_price = self._calculate_limit_price(signal)
                order = await self.broker.submit_limit_order(
                    symbol=signal.symbol,
                    side=signal.action,
                    notional=validation.position_size,
                    limit_price=limit_price
                )

            # Step 5: Submit stop-loss
            if validation.stop_loss:
                await self.broker.submit_stop_loss(
                    symbol=signal.symbol,
                    stop_price=validation.stop_loss,
                    qty=order.filled_qty
                )

            # Step 6: Log execution
            self._log_execution(order, validation)

            return ExecutionResult(
                success=True,
                order_id=order.id,
                filled_price=order.filled_avg_price,
                filled_qty=order.filled_qty,
                slippage=self._calculate_slippage(signal, order)
            )

        except Exception as e:
            logger.error(f"Order execution failed: {e}")
            await self._handle_execution_failure(signal, e)
            return ExecutionResult(success=False, error=str(e))
```

**Order Execution Strategy:**

```
┌─────────────────────────────────────────────────────┐
│         ORDER TYPE DECISION TREE                    │
└─────────────────────────────────────────────────────┘

Signal Confidence > 0.8?
├─ YES → Spread < 0.1%?
│        ├─ YES → MARKET ORDER (fast execution)
│        └─ NO  → LIMIT ORDER (mid-point)
│
└─ NO  → Time Urgency?
         ├─ HIGH → LIMIT ORDER (aggressive, near ask/bid)
         └─ LOW  → LIMIT ORDER (passive, mid-point)

Slippage Minimization:
├─ Check volume: Order size < 1% of avg daily volume
├─ Time of day: Avoid first/last 15 minutes
├─ Limit order timeout: 5 minutes, then market order
└─ Partial fills: Accept if > 90% filled
```

**Communication Protocol:**
- **Inbound:** Subscribes to `signals.trading` topic
- **Direct Calls:** Synchronous calls to Risk Manager
- **Outbound:** Publishes execution results to `execution.results`
- **Broker API:** REST + WebSocket to Alpaca

---

### 5. Supervisor Agent

**Role:** Orchestration, logging, and performance tracking

**Responsibilities:**
- Decompose high-level trading goals into subtasks
- Coordinate agent workflows
- Monitor agent health and performance
- Aggregate results from sub-agents
- Maintain audit trail
- Escalate to human when needed
- Generate performance reports

**Architecture:**
```python
class SupervisorAgent:
    def __init__(self):
        self.agents = {
            'research': ResearchAgent(),
            'signal': SignalAgent(),
            'risk': RiskManagerAgent(),
            'execution': ExecutionAgent()
        }
        self.performance_tracker = PerformanceTracker()
        self.audit_log = AuditLog()

    async def execute_daily_routine(self):
        """Main orchestration loop for daily trading."""

        # Step 1: Get list of symbols to analyze
        symbols = await self._get_symbols_universe()

        # Step 2: Parallel research on all symbols
        research_tasks = [
            self.agents['research'].analyze_market(symbol)
            for symbol in symbols
        ]
        research_reports = await asyncio.gather(*research_tasks)

        # Step 3: Filter candidates based on sentiment
        candidates = [
            report for report in research_reports
            if report.sentiment > 0.3 and report.confidence > 0.6
        ]

        # Step 4: Generate signals for candidates
        signal_tasks = [
            self.agents['signal'].generate_signal(report.to_market_state())
            for report in candidates
        ]
        signals = await asyncio.gather(*signal_tasks)

        # Step 5: Rank signals by confidence * sentiment
        ranked_signals = sorted(
            signals,
            key=lambda s: s.confidence * s.sentiment_alignment,
            reverse=True
        )

        # Step 6: Execute top N signals
        execution_tasks = []
        for signal in ranked_signals[:5]:  # Top 5 signals
            # Risk check happens inside execution agent
            execution_tasks.append(
                self.agents['execution'].execute_trade(signal)
            )

        results = await asyncio.gather(*execution_tasks)

        # Step 7: Update performance metrics
        await self.performance_tracker.update(results)

        # Step 8: Log to audit trail
        await self.audit_log.record_daily_execution(
            symbols, research_reports, signals, results
        )

        # Step 9: Generate daily report
        daily_report = await self._generate_daily_report(results)

        # Step 10: Check if human review needed
        if self._requires_human_review(daily_report):
            await self._notify_human(daily_report)

        return daily_report
```

**Performance Tracking:**
```python
class PerformanceTracker:
    def __init__(self):
        self.metrics = {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'total_pnl': 0.0,
            'win_rate': 0.0,
            'sharpe_ratio': 0.0,
            'max_drawdown': 0.0,
            'agent_performance': {}
        }

    async def update(self, execution_results: List[ExecutionResult]):
        for result in execution_results:
            if result.success:
                self.metrics['total_trades'] += 1
                pnl = result.realized_pnl
                self.metrics['total_pnl'] += pnl

                if pnl > 0:
                    self.metrics['winning_trades'] += 1
                else:
                    self.metrics['losing_trades'] += 1

        # Update derived metrics
        self._update_win_rate()
        self._update_sharpe_ratio()
        self._update_max_drawdown()

        # Track per-agent performance
        self._update_agent_metrics(execution_results)
```

**Communication Protocol:**
- **Orchestration:** Direct async calls to sub-agents
- **Monitoring:** Subscribes to all topics for observability
- **Outbound:** Publishes daily reports to `supervisor.reports`
- **Human Interface:** REST API for manual queries and overrides

---

## Communication Architecture

### Multi-Protocol Approach

The system uses different communication protocols based on use case:

```
┌─────────────────────────────────────────────────────────────────┐
│                  COMMUNICATION PROTOCOL MATRIX                   │
└─────────────────────────────────────────────────────────────────┘

Use Case                    Protocol        Why?
───────────────────────────────────────────────────────────────────
Market Data Access          MCP Resources   Standardized, real-time
Tool Invocations           MCP Tools       LLM-friendly interface
Async Agent Messages       Redis Pub/Sub   Fast, lightweight
State Management           Redis           Low-latency cache
Risk Validation            Direct Calls    Synchronous, immediate
Order Execution            REST API        Broker integration
Real-time Market Feed      WebSocket       Streaming data
Performance Analytics      PostgreSQL      Persistent storage
Human Interface            FastAPI         REST endpoints
```

### 1. Model Context Protocol (MCP)

**Purpose:** Standardized access to market data and tools

**Implementation:**
```python
# MCP Server for Market Data
class MarketDataMCPServer:
    def __init__(self):
        self.server = MCPServer("market-data")

    @self.server.resource("market/{symbol}/price")
    async def get_price(self, symbol: str):
        """Expose current price as MCP resource."""
        price_data = await self._fetch_current_price(symbol)
        return {
            "uri": f"market://{symbol}/price",
            "mimeType": "application/json",
            "data": price_data
        }

    @self.server.tool("technical_analysis")
    async def technical_analysis(self, symbol: str, indicators: List[str]):
        """MCP tool for technical analysis."""
        results = {}
        for indicator in indicators:
            results[indicator] = await self._calculate_indicator(
                symbol, indicator
            )
        return results
```

**Resources Exposed:**
- `market://{symbol}/price` - Current price
- `market://{symbol}/volume` - Trading volume
- `market://{symbol}/indicators` - Technical indicators
- `news://{symbol}/recent` - Recent news
- `sentiment://{symbol}/score` - Sentiment score

**Tools Exposed:**
- `technical_analysis` - Calculate indicators
- `fundamental_analysis` - Fetch fundamentals
- `sentiment_analysis` - Analyze sentiment
- `backtest` - Run backtests

### 2. Message Queue (Redis Pub/Sub)

**Purpose:** Asynchronous agent-to-agent communication

**Topics:**
```
research.reports       → Research Agent publishes analysis
signals.trading        → Signal Agent publishes trading signals
execution.results      → Execution Agent publishes trade results
risk.alerts            → Risk Manager publishes alerts
supervisor.reports     → Supervisor publishes daily reports
system.health          → All agents publish health checks
```

**Implementation:**
```python
class MessageBus:
    def __init__(self, redis_client):
        self.redis = redis_client
        self.pubsub = redis_client.pubsub()

    async def publish(self, topic: str, message: dict):
        """Publish message to topic."""
        await self.redis.publish(
            topic,
            json.dumps(message, default=str)
        )

    async def subscribe(self, topic: str, handler: Callable):
        """Subscribe to topic with handler."""
        await self.pubsub.subscribe(topic)

        async for message in self.pubsub.listen():
            if message['type'] == 'message':
                data = json.loads(message['data'])
                await handler(data)
```

### 3. Direct Synchronous Calls

**Purpose:** Immediate validation and critical decisions

**Use Cases:**
- Risk validation before order execution
- Circuit breaker checks
- Human-in-the-loop confirmations

**Implementation:**
```python
class DirectCallManager:
    async def call_with_timeout(self,
                                 agent: Agent,
                                 method: str,
                                 timeout: float = 5.0,
                                 **kwargs):
        """Call agent method with timeout."""
        try:
            return await asyncio.wait_for(
                getattr(agent, method)(**kwargs),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            logger.error(f"Timeout calling {agent}.{method}")
            raise
```

### 4. State Management (Redis)

**Purpose:** Shared state across agents

**Keys:**
```
agent:{agent_id}:state         → Agent state
portfolio:positions            → Current positions
portfolio:orders               → Open orders
risk:circuit_breaker           → Circuit breaker status
risk:daily_pl                  → Daily P&L
performance:metrics            → Performance metrics
rl_models:{model_name}:weights → RL model checkpoints
```

---

## Agent Communication Flows

### Flow 1: Daily Trading Execution

```
┌──────────────────────────────────────────────────────────────────┐
│               DAILY TRADING EXECUTION FLOW                        │
└──────────────────────────────────────────────────────────────────┘

1. SUPERVISOR → Get symbols from universe
                ↓
2. SUPERVISOR → RESEARCH (parallel)
                ├─ Analyze AAPL
                ├─ Analyze MSFT
                ├─ Analyze GOOGL
                └─ Analyze NVDA
                ↓
3. RESEARCH → Publish reports to "research.reports"
                ↓
4. SIGNAL → Subscribe to "research.reports"
            → Generate signals for high-confidence reports
            → Publish to "signals.trading"
                ↓
5. EXECUTION → Subscribe to "signals.trading"
               → For each signal:
                  ├─ Direct call → RISK MANAGER (validate)
                  ├─ If approved → Submit order to Alpaca
                  ├─ If rejected → Log and skip
                  └─ Publish result to "execution.results"
                ↓
6. SUPERVISOR → Subscribe to "execution.results"
                → Aggregate results
                → Update performance metrics
                → Generate daily report
                → If anomalies detected → Escalate to human
```

### Flow 2: Anomaly Detection & Human Escalation

```
┌──────────────────────────────────────────────────────────────────┐
│           ANOMALY DETECTION & ESCALATION FLOW                     │
└──────────────────────────────────────────────────────────────────┘

1. RISK MANAGER detects anomaly:
   ├─ Consecutive losses >= 3
   ├─ Daily loss approaching limit
   ├─ Unusual slippage pattern
   └─ Model confidence drops below 0.4
   ↓
2. RISK MANAGER → Publish to "risk.alerts"
                  ↓
3. SUPERVISOR → Subscribe to "risk.alerts"
                → Analyze severity
                → Confidence score < threshold?
                   ├─ YES → Trigger human review
                   └─ NO  → Log and continue
                ↓
4. HUMAN-IN-LOOP SYSTEM:
   ├─ Send notification (email/Slack)
   ├─ Display context:
   │  ├─ Recent trades
   │  ├─ Risk metrics
   │  ├─ Agent confidence scores
   │  └─ Market conditions
   ├─ Present options:
   │  ├─ Approve continuation
   │  ├─ Pause trading (circuit breaker)
   │  ├─ Adjust risk parameters
   │  └─ Manual override
   └─ Wait for human decision (timeout: 15 minutes)
   ↓
5. Human decision → Update system state
   ├─ Pause → Set circuit_breaker = True
   ├─ Continue → Log approval, continue
   └─ Adjust → Update risk parameters, continue
```

### Flow 3: RL Model Update

```
┌──────────────────────────────────────────────────────────────────┐
│              RL MODEL TRAINING & UPDATE FLOW                      │
└──────────────────────────────────────────────────────────────────┘

1. SIGNAL AGENT (Background Thread):
   ├─ Every 1 hour:
   │  ├─ Fetch recent trades and outcomes
   │  ├─ Calculate rewards
   │  ├─ Store in experience replay buffer
   │  └─ If buffer size > 1000:
   │     └─ Trigger training
   ↓
2. Training Process:
   ├─ Sample batch from replay buffer
   ├─ Train each RL model (DQN, PPO, A2C)
   ├─ Validate on validation set
   ├─ Calculate performance metrics:
   │  ├─ Average reward
   │  ├─ Win rate
   │  └─ Sharpe ratio
   └─ If metrics improved:
      ├─ Save new model checkpoint to Redis
      ├─ Update ensemble weights
      └─ Publish "model.updated" event
   ↓
3. SUPERVISOR → Subscribe to "model.updated"
                → Log model version
                → Track A/B test performance
                → If new model underperforms:
                   └─ Rollback to previous version
```

### Flow 4: Real-time Market Data Processing

```
┌──────────────────────────────────────────────────────────────────┐
│          REAL-TIME MARKET DATA PROCESSING FLOW                    │
└──────────────────────────────────────────────────────────────────┘

1. WebSocket Connection → Alpaca Market Data
   ↓
2. Stream Handler:
   ├─ Receive tick data (price, volume, timestamp)
   ├─ Update Redis cache (market:{symbol}:latest)
   ├─ Calculate streaming indicators:
   │  ├─ VWAP
   │  ├─ RSI (rolling)
   │  └─ Volume profile
   └─ Publish to "market.data.realtime"
   ↓
3. SIGNAL AGENT → Subscribe to "market.data.realtime"
                  → Update internal state
                  → If significant change:
                     └─ Re-evaluate open positions
   ↓
4. RISK MANAGER → Subscribe to "market.data.realtime"
                  → Monitor stop-loss levels
                  → If stop-loss triggered:
                     └─ Send immediate exit signal
```

---

## Implementation with Claude Agents SDK

### Architecture Pattern: Orchestrator-Worker

The system uses Claude Agents SDK's **orchestrator-worker pattern**:
- **Orchestrator:** Supervisor Agent (Claude Opus 4)
- **Workers:** Specialized agents (Claude Sonnet 4)

### SDK Setup

```python
from claude_agents import Agent, Orchestrator, Subagent
from claude_agents.tools import Tool, MCPTool
from claude_agents.protocols import MCP, MessageQueue

# 1. Define MCP Tools
market_data_tool = MCPTool(
    name="market_data",
    description="Access real-time market data",
    server_url="http://localhost:8000/mcp"
)

# 2. Create Specialized Agents
research_agent = Subagent(
    name="research_agent",
    model="claude-sonnet-4-20250514",
    system_prompt="""You are a financial research analyst specializing in
    market data analysis, sentiment analysis, and technical analysis.

    Your responsibilities:
    - Gather and analyze market data
    - Evaluate news sentiment
    - Calculate technical indicators
    - Provide confidence-scored research reports

    Always provide structured JSON output with clear reasoning.""",
    tools=[
        market_data_tool,
        Tool(name="fetch_news", function=fetch_news_api),
        Tool(name="calculate_indicators", function=calculate_indicators)
    ],
    max_context=50000
)

signal_agent = Subagent(
    name="signal_agent",
    model="claude-sonnet-4-20250514",
    system_prompt="""You are a trading signal generator combining RL models
    with sentiment analysis.

    Your responsibilities:
    - Interpret RL model outputs
    - Validate signals with sentiment
    - Provide confidence scores
    - Generate clear reasoning for each signal

    Always explain your signal decisions.""",
    tools=[
        Tool(name="rl_ensemble", function=rl_ensemble_predict),
        Tool(name="sentiment_check", function=check_sentiment_alignment)
    ],
    max_context=30000
)

risk_manager_agent = Subagent(
    name="risk_manager_agent",
    model="claude-sonnet-4-20250514",
    system_prompt="""You are a risk management specialist focused on
    capital preservation.

    Your responsibilities:
    - Validate all trades against risk limits
    - Calculate position sizes
    - Monitor circuit breakers
    - Escalate high-risk situations to humans

    Be conservative and prioritize capital preservation.""",
    tools=[
        Tool(name="calculate_position_size", function=calc_position_size),
        Tool(name="check_circuit_breaker", function=check_circuit_breaker),
        Tool(name="get_risk_metrics", function=get_risk_metrics)
    ],
    max_context=20000
)

execution_agent = Subagent(
    name="execution_agent",
    model="claude-sonnet-4-20250514",
    system_prompt="""You are an order execution specialist focused on
    optimal trade execution.

    Your responsibilities:
    - Choose optimal order type (market vs. limit)
    - Minimize slippage
    - Handle partial fills
    - Monitor order status

    Optimize for best execution prices.""",
    tools=[
        Tool(name="submit_order", function=submit_order_to_broker),
        Tool(name="get_order_status", function=get_order_status),
        Tool(name="calculate_slippage", function=calculate_slippage)
    ],
    max_context=15000
)

# 3. Create Orchestrator (Supervisor)
supervisor = Orchestrator(
    name="trading_supervisor",
    model="claude-opus-4-20250514",
    system_prompt="""You are the supervisor of a multi-agent trading system.

    Your responsibilities:
    - Decompose trading goals into subtasks
    - Coordinate specialized agents
    - Aggregate and synthesize agent outputs
    - Make final trading decisions
    - Escalate to humans when confidence is low or anomalies detected
    - Track performance metrics

    Agents under your supervision:
    - research_agent: Market research and analysis
    - signal_agent: Trading signal generation (RL + sentiment)
    - risk_manager_agent: Risk validation and position sizing
    - execution_agent: Order execution and optimization

    Work systematically through the trading pipeline and ensure all
    risk checks are passed before executing trades.""",
    subagents=[
        research_agent,
        signal_agent,
        risk_manager_agent,
        execution_agent
    ],
    max_context=100000,  # Large context for orchestration
    parallelization=True  # Enable parallel subagent execution
)

# 4. Run Daily Trading Routine
async def run_daily_trading():
    result = await supervisor.run(
        task="""Execute today's trading routine:

        1. Analyze our universe of stocks (AAPL, MSFT, GOOGL, NVDA, TSLA)
        2. For each stock, gather research and generate trading signals
        3. Rank signals by confidence and sentiment
        4. Execute the top 3 signals that pass risk validation
        5. Provide a daily summary report

        Use parallel processing where possible to speed up analysis.
        Escalate to human if:
        - Any risk limits are breached
        - Signal confidence < 0.6
        - Unusual market conditions detected
        """,
        context={
            'date': datetime.now().isoformat(),
            'account_balance': 100000.0,
            'daily_allocation': 10.0
        }
    )

    return result
```

### Subagent Communication Patterns

**1. Parallel Research:**
```python
# Supervisor spawns multiple research subagents in parallel
research_tasks = []
for symbol in ['AAPL', 'MSFT', 'GOOGL', 'NVDA']:
    task = supervisor.spawn_subagent(
        agent=research_agent,
        task=f"Analyze {symbol} and provide research report",
        context={'symbol': symbol}
    )
    research_tasks.append(task)

# Wait for all research to complete
research_results = await asyncio.gather(*research_tasks)
```

**2. Sequential Pipeline:**
```python
# Research → Signal → Risk → Execution (sequential)
research_result = await supervisor.call_subagent(
    agent=research_agent,
    task="Analyze AAPL"
)

signal_result = await supervisor.call_subagent(
    agent=signal_agent,
    task="Generate signal for AAPL",
    context={'research': research_result}
)

risk_validation = await supervisor.call_subagent(
    agent=risk_manager_agent,
    task="Validate trade",
    context={'signal': signal_result}
)

if risk_validation['approved']:
    execution_result = await supervisor.call_subagent(
        agent=execution_agent,
        task="Execute trade",
        context={'signal': signal_result, 'validation': risk_validation}
    )
```

**3. Conditional Execution:**
```python
# Only execute if confidence is high
if signal_result['confidence'] > 0.7:
    # High confidence → proceed
    execution_result = await supervisor.call_subagent(...)
else:
    # Low confidence → escalate to human
    human_decision = await supervisor.escalate_to_human(
        reason="Signal confidence below threshold",
        context={'signal': signal_result}
    )
```

### Context Management

**Isolate context per subagent:**
```python
# Each subagent gets only what it needs
research_context = {
    'symbol': 'AAPL',
    'timeframe': '1D',
    'indicators': ['RSI', 'MACD', 'BB']
}

signal_context = {
    'research_report': research_result,  # Only relevant data
    'current_positions': get_current_positions()
}

# Supervisor maintains full context
supervisor_context = {
    'research_reports': all_research_results,
    'signals': all_signals,
    'risk_metrics': current_risk_metrics,
    'performance_history': performance_data
}
```

### Error Handling

```python
class AgentErrorHandler:
    async def handle_subagent_error(self,
                                    agent: Subagent,
                                    error: Exception,
                                    context: dict):
        """Handle subagent failures gracefully."""

        # Log error
        logger.error(f"Subagent {agent.name} failed: {error}")

        # Retry logic
        if isinstance(error, TimeoutError):
            return await self._retry_with_backoff(agent, context)

        # Fallback logic
        if agent == signal_agent:
            # Fallback to rules-based signal
            return self._fallback_signal_generation(context)

        # Escalate to supervisor
        return await supervisor.handle_failure(agent, error, context)
```

---

## Code Structure Proposal

```
trading/
├── README.md
├── MULTI_AGENT_ARCHITECTURE.md (this file)
├── requirements.txt
├── .env.example
├── docker-compose.yml
│
├── src/
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── base.py                      # Base agent class
│   │   ├── research_agent.py            # Research Agent
│   │   ├── signal_agent.py              # Signal Agent (RL + Claude)
│   │   ├── risk_manager_agent.py        # Risk Manager Agent
│   │   ├── execution_agent.py           # Execution Agent
│   │   └── supervisor_agent.py          # Supervisor Agent
│   │
│   ├── rl_models/
│   │   ├── __init__.py
│   │   ├── base_model.py                # Base RL model class
│   │   ├── dqn_agent.py                 # Deep Q-Network
│   │   ├── ppo_agent.py                 # Proximal Policy Optimization
│   │   ├── a2c_agent.py                 # Advantage Actor-Critic
│   │   ├── ensemble.py                  # Ensemble manager
│   │   └── training.py                  # Training pipeline
│   │
│   ├── communication/
│   │   ├── __init__.py
│   │   ├── mcp_server.py                # MCP server for market data
│   │   ├── mcp_client.py                # MCP client for agents
│   │   ├── message_bus.py               # Redis Pub/Sub wrapper
│   │   ├── direct_calls.py              # Synchronous call manager
│   │   └── protocols.py                 # Protocol definitions
│   │
│   ├── risk/
│   │   ├── __init__.py
│   │   ├── risk_manager.py              # Risk management (existing)
│   │   ├── circuit_breakers.py          # Circuit breaker logic
│   │   ├── position_sizing.py           # Position size calculator
│   │   └── anomaly_detection.py         # Anomaly detection
│   │
│   ├── execution/
│   │   ├── __init__.py
│   │   ├── alpaca_trader.py             # Alpaca integration (existing)
│   │   ├── order_router.py              # Order routing logic
│   │   ├── slippage_optimizer.py        # Slippage minimization
│   │   └── fill_manager.py              # Fill monitoring
│   │
│   ├── data/
│   │   ├── __init__.py
│   │   ├── market_data.py               # Market data fetching
│   │   ├── news_scraper.py              # News scraping
│   │   ├── fundamental_data.py          # Fundamental data
│   │   └── technical_indicators.py      # Technical indicators
│   │
│   ├── human_in_loop/
│   │   ├── __init__.py
│   │   ├── notification.py              # Notification system
│   │   ├── decision_interface.py        # Human decision UI/API
│   │   └── approval_manager.py          # Approval workflow
│   │
│   ├── monitoring/
│   │   ├── __init__.py
│   │   ├── metrics.py                   # Performance metrics
│   │   ├── logging_config.py            # Logging setup
│   │   ├── alerts.py                    # Alert system
│   │   └── health_check.py              # Agent health checks
│   │
│   └── utils/
│       ├── __init__.py
│       ├── state_manager.py             # Redis state management
│       ├── performance_tracker.py       # Performance tracking
│       └── config.py                    # Configuration management
│
├── tests/
│   ├── agents/
│   │   ├── test_research_agent.py
│   │   ├── test_signal_agent.py
│   │   ├── test_risk_manager_agent.py
│   │   └── test_execution_agent.py
│   ├── rl_models/
│   │   ├── test_dqn.py
│   │   ├── test_ppo.py
│   │   └── test_ensemble.py
│   └── integration/
│       ├── test_full_pipeline.py
│       └── test_communication.py
│
├── scripts/
│   ├── train_rl_models.py               # Train RL models
│   ├── backtest_strategy.py             # Backtest signals
│   ├── deploy_agents.py                 # Deploy agents
│   └── emergency_stop.py                # Emergency shutdown
│
├── notebooks/
│   ├── rl_model_analysis.ipynb          # RL model performance
│   ├── signal_analysis.ipynb            # Signal quality analysis
│   └── risk_analysis.ipynb              # Risk metrics analysis
│
├── config/
│   ├── agents.yaml                      # Agent configurations
│   ├── rl_models.yaml                   # RL model hyperparameters
│   ├── risk_limits.yaml                 # Risk parameters
│   └── symbols.yaml                     # Trading universe
│
├── data/
│   ├── rl_checkpoints/                  # RL model checkpoints
│   ├── experience_replay/               # Experience replay buffers
│   ├── trade_history/                   # Trade history
│   └── performance_logs/                # Performance logs
│
├── docker/
│   ├── Dockerfile.supervisor            # Supervisor container
│   ├── Dockerfile.agents                # Agents container
│   ├── Dockerfile.rl_training           # RL training container
│   └── Dockerfile.mcp_server            # MCP server container
│
└── deployment/
    ├── kubernetes/
    │   ├── supervisor.yaml
    │   ├── agents.yaml
    │   └── redis.yaml
    └── docker-compose.yml

```

---

## Human-in-the-Loop Integration

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│              HUMAN-IN-THE-LOOP ARCHITECTURE                      │
└─────────────────────────────────────────────────────────────────┘

Confidence Scoring:
├─ High (> 0.8): Auto-execute
├─ Medium (0.6 - 0.8): Log and execute, notify human
├─ Low (0.4 - 0.6): Require human approval
└─ Very Low (< 0.4): Block execution, require manual override

Anomaly Detection:
├─ Pattern deviation > 3 sigma → Human review
├─ Model confidence drop > 20% → Human review
├─ Unusual slippage (> 2x historical) → Human review
└─ Circuit breaker triggered → Human decision

Notification Channels:
├─ Email (high priority alerts)
├─ Slack/Discord (real-time notifications)
├─ SMS (critical circuit breakers)
└─ Web dashboard (always available)
```

### Implementation

```python
class HumanInLoopManager:
    def __init__(self):
        self.notification_service = NotificationService()
        self.decision_queue = asyncio.Queue()
        self.pending_decisions = {}

    async def request_human_approval(self,
                                     decision_type: str,
                                     context: dict,
                                     timeout: int = 900) -> HumanDecision:
        """
        Request human approval for a decision.

        Args:
            decision_type: Type of decision (trade, risk_override, etc.)
            context: Context for the decision
            timeout: Timeout in seconds (default: 15 minutes)

        Returns:
            HumanDecision object with approval status and reasoning
        """
        decision_id = str(uuid.uuid4())

        # Create decision request
        request = HumanDecisionRequest(
            id=decision_id,
            type=decision_type,
            context=context,
            timestamp=datetime.now(),
            timeout=timeout
        )

        # Store in pending decisions
        self.pending_decisions[decision_id] = request

        # Send notifications
        await self._send_notifications(request)

        # Wait for human decision with timeout
        try:
            decision = await asyncio.wait_for(
                self._wait_for_decision(decision_id),
                timeout=timeout
            )
            return decision
        except asyncio.TimeoutError:
            # Default to safe action on timeout
            logger.warning(f"Human decision timeout for {decision_id}")
            return HumanDecision(
                approved=False,
                reason="Timeout - defaulting to safe action",
                timestamp=datetime.now()
            )

    async def _send_notifications(self, request: HumanDecisionRequest):
        """Send multi-channel notifications."""

        # Format context for human
        formatted_context = self._format_context(request.context)

        # Email notification
        await self.notification_service.send_email(
            to=os.getenv('ALERT_EMAIL'),
            subject=f"Trading Decision Required: {request.type}",
            body=formatted_context,
            priority='high'
        )

        # Slack notification
        await self.notification_service.send_slack(
            channel='#trading-alerts',
            message=formatted_context,
            blocks=self._create_slack_blocks(request)
        )

        # Dashboard notification
        await self.notification_service.update_dashboard(
            decision_id=request.id,
            status='pending',
            context=formatted_context
        )

    def _format_context(self, context: dict) -> str:
        """Format context for human readability."""

        formatted = f"""
        DECISION CONTEXT
        ================

        Symbol: {context.get('symbol', 'N/A')}
        Action: {context.get('action', 'N/A')}
        Position Size: ${context.get('position_size', 0):,.2f}

        SIGNAL DETAILS:
        - Confidence: {context.get('signal_confidence', 0):.2%}
        - RL Models Agreement: {context.get('rl_agreement', 0):.2%}
        - Sentiment Score: {context.get('sentiment', 0):.2f}

        RISK METRICS:
        - Daily P&L: ${context.get('daily_pl', 0):,.2f}
        - Current Drawdown: {context.get('drawdown', 0):.2%}
        - Position Concentration: {context.get('concentration', 0):.2%}

        ANOMALY DETECTION:
        {self._format_anomalies(context.get('anomalies', []))}

        RECOMMENDATION:
        {context.get('recommendation', 'N/A')}

        Please approve or reject this decision within 15 minutes.
        """

        return formatted

    async def _wait_for_decision(self, decision_id: str) -> HumanDecision:
        """Wait for human decision from queue."""
        while True:
            decision = await self.decision_queue.get()
            if decision.id == decision_id:
                return decision
```

### Decision Interface (FastAPI)

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

class ApprovalRequest(BaseModel):
    decision_id: str
    approved: bool
    reasoning: str

@app.get("/pending_decisions")
async def get_pending_decisions():
    """Get all pending decisions requiring human approval."""
    return {
        'decisions': list(human_loop_manager.pending_decisions.values())
    }

@app.get("/decision/{decision_id}")
async def get_decision_details(decision_id: str):
    """Get detailed context for a specific decision."""
    if decision_id not in human_loop_manager.pending_decisions:
        raise HTTPException(status_code=404, detail="Decision not found")

    request = human_loop_manager.pending_decisions[decision_id]
    return {
        'id': request.id,
        'type': request.type,
        'context': request.context,
        'timestamp': request.timestamp,
        'time_remaining': request.timeout - (datetime.now() - request.timestamp).seconds
    }

@app.post("/decision/{decision_id}/approve")
async def approve_decision(decision_id: str, approval: ApprovalRequest):
    """Approve or reject a decision."""
    if decision_id not in human_loop_manager.pending_decisions:
        raise HTTPException(status_code=404, detail="Decision not found")

    decision = HumanDecision(
        id=decision_id,
        approved=approval.approved,
        reason=approval.reasoning,
        timestamp=datetime.now()
    )

    # Add to decision queue
    await human_loop_manager.decision_queue.put(decision)

    # Remove from pending
    del human_loop_manager.pending_decisions[decision_id]

    return {'status': 'success', 'decision': decision}
```

### Web Dashboard (React + Streamlit)

```python
import streamlit as st
import requests

st.set_page_config(page_title="Trading Decisions", layout="wide")

# Fetch pending decisions
response = requests.get("http://localhost:8000/pending_decisions")
pending = response.json()['decisions']

st.title("Pending Trading Decisions")
st.write(f"{len(pending)} decisions require your approval")

for decision in pending:
    with st.expander(f"{decision['type']} - {decision['id'][:8]}"):
        st.json(decision['context'])

        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("Approve", key=f"approve_{decision['id']}"):
                reasoning = st.text_input("Reasoning:")
                requests.post(
                    f"http://localhost:8000/decision/{decision['id']}/approve",
                    json={'decision_id': decision['id'], 'approved': True, 'reasoning': reasoning}
                )
                st.success("Approved!")

        with col2:
            if st.button("Reject", key=f"reject_{decision['id']}"):
                reasoning = st.text_input("Reasoning:")
                requests.post(
                    f"http://localhost:8000/decision/{decision['id']}/approve",
                    json={'decision_id': decision['id'], 'approved': False, 'reasoning': reasoning}
                )
                st.warning("Rejected!")

        with col3:
            time_remaining = decision['timeout'] - (datetime.now() - decision['timestamp']).seconds
            st.metric("Time Remaining", f"{time_remaining // 60}m {time_remaining % 60}s")
```

---

## Anomaly Detection & Circuit Breakers

### Anomaly Detection Architecture

```python
class AnomalyDetector:
    def __init__(self):
        self.historical_data = deque(maxlen=1000)
        self.anomaly_threshold = 3.0  # 3 sigma
        self.models = {
            'isolation_forest': IsolationForest(contamination=0.1),
            'autoencoder': AnomalyAutoencoder(),
            'statistical': StatisticalAnomalyDetector()
        }

    async def detect_anomalies(self,
                               signal: TradingSignal,
                               execution_result: ExecutionResult) -> List[Anomaly]:
        """
        Detect anomalies in signal and execution.

        Returns:
            List of detected anomalies with severity scores
        """
        anomalies = []

        # 1. Signal Confidence Anomaly
        if len(self.historical_data) > 100:
            avg_confidence = np.mean([d['confidence'] for d in self.historical_data])
            std_confidence = np.std([d['confidence'] for d in self.historical_data])

            if abs(signal.confidence - avg_confidence) > self.anomaly_threshold * std_confidence:
                anomalies.append(Anomaly(
                    type='signal_confidence_deviation',
                    severity='medium',
                    description=f"Signal confidence {signal.confidence:.2f} deviates from historical average {avg_confidence:.2f}",
                    z_score=abs(signal.confidence - avg_confidence) / std_confidence
                ))

        # 2. Slippage Anomaly
        if execution_result and execution_result.slippage:
            avg_slippage = np.mean([d['slippage'] for d in self.historical_data if 'slippage' in d])

            if execution_result.slippage > 2 * avg_slippage:
                anomalies.append(Anomaly(
                    type='excessive_slippage',
                    severity='high',
                    description=f"Slippage {execution_result.slippage:.4f} is {execution_result.slippage/avg_slippage:.1f}x higher than average",
                    value=execution_result.slippage
                ))

        # 3. Volume Anomaly
        if signal.market_state.volume < 0.5 * signal.market_state.avg_volume:
            anomalies.append(Anomaly(
                type='low_volume',
                severity='medium',
                description=f"Trading volume {signal.market_state.volume:,} is significantly below average",
                value=signal.market_state.volume / signal.market_state.avg_volume
            ))

        # 4. Model Disagreement Anomaly
        if signal.rl_models_agreement < 0.5:
            anomalies.append(Anomaly(
                type='model_disagreement',
                severity='high',
                description=f"RL models show low agreement: {signal.rl_models_agreement:.2%}",
                value=signal.rl_models_agreement
            ))

        # 5. Market Condition Anomaly (VIX spike)
        if signal.market_state.vix > 30:
            anomalies.append(Anomaly(
                type='high_volatility',
                severity='high',
                description=f"VIX is elevated at {signal.market_state.vix:.2f}, indicating high market stress",
                value=signal.market_state.vix
            ))

        # 6. Time-Series Anomaly (Autoencoder)
        recent_sequence = np.array([self._extract_features(d) for d in list(self.historical_data)[-50:]])
        if len(recent_sequence) == 50:
            reconstruction_error = self.models['autoencoder'].detect(recent_sequence)

            if reconstruction_error > self.anomaly_threshold:
                anomalies.append(Anomaly(
                    type='time_series_pattern_anomaly',
                    severity='high',
                    description="Recent trading patterns deviate significantly from normal",
                    value=reconstruction_error
                ))

        # Store current data point
        self.historical_data.append({
            'timestamp': datetime.now(),
            'confidence': signal.confidence,
            'slippage': execution_result.slippage if execution_result else None,
            'volume': signal.market_state.volume
        })

        return anomalies
```

### Circuit Breaker System

```python
class CircuitBreakerSystem:
    def __init__(self):
        self.breakers = {
            'daily_loss': CircuitBreaker(name='daily_loss', threshold=2.0),
            'drawdown': CircuitBreaker(name='drawdown', threshold=10.0),
            'consecutive_losses': CircuitBreaker(name='consecutive_losses', threshold=3),
            'volatility': CircuitBreaker(name='volatility', threshold=30.0),
            'anomaly_score': CircuitBreaker(name='anomaly_score', threshold=5.0)
        }
        self.state = CircuitBreakerState.CLOSED
        self.trip_history = []

    async def check_all_breakers(self,
                                 account: AccountInfo,
                                 risk_metrics: RiskMetrics,
                                 anomalies: List[Anomaly]) -> CircuitBreakerStatus:
        """
        Check all circuit breakers and return status.

        Returns:
            CircuitBreakerStatus with overall state and triggered breakers
        """
        triggered = []

        # 1. Daily Loss Breaker
        daily_loss_pct = (risk_metrics.daily_pl / account.equity) * 100
        if daily_loss_pct < -self.breakers['daily_loss'].threshold:
            triggered.append('daily_loss')
            self.breakers['daily_loss'].trip()

        # 2. Drawdown Breaker
        drawdown_pct = ((risk_metrics.peak_equity - account.equity) /
                       risk_metrics.peak_equity) * 100
        if drawdown_pct > self.breakers['drawdown'].threshold:
            triggered.append('drawdown')
            self.breakers['drawdown'].trip()

        # 3. Consecutive Losses Breaker
        if risk_metrics.consecutive_losses >= self.breakers['consecutive_losses'].threshold:
            triggered.append('consecutive_losses')
            self.breakers['consecutive_losses'].trip()

        # 4. Volatility Breaker (VIX)
        current_vix = await self._fetch_vix()
        if current_vix > self.breakers['volatility'].threshold:
            triggered.append('volatility')
            self.breakers['volatility'].trip()

        # 5. Anomaly Score Breaker
        anomaly_score = sum(a.severity_score() for a in anomalies)
        if anomaly_score > self.breakers['anomaly_score'].threshold:
            triggered.append('anomaly_score')
            self.breakers['anomaly_score'].trip()

        # Update overall state
        if triggered:
            self.state = CircuitBreakerState.OPEN
            self.trip_history.append({
                'timestamp': datetime.now(),
                'triggered_breakers': triggered,
                'metrics': {
                    'daily_loss_pct': daily_loss_pct,
                    'drawdown_pct': drawdown_pct,
                    'consecutive_losses': risk_metrics.consecutive_losses,
                    'vix': current_vix,
                    'anomaly_score': anomaly_score
                }
            })

        return CircuitBreakerStatus(
            state=self.state,
            triggered_breakers=triggered,
            trading_allowed=(self.state == CircuitBreakerState.CLOSED),
            reason=self._format_trip_reason(triggered) if triggered else None
        )

    async def reset(self, manual_override: bool = False):
        """Reset circuit breakers (automatic or manual)."""
        if manual_override:
            # Require human approval for manual reset
            approval = await human_loop_manager.request_human_approval(
                decision_type='circuit_breaker_reset',
                context={
                    'current_state': self.state,
                    'trip_history': self.trip_history[-5:],
                    'reason': 'Manual reset requested'
                }
            )

            if not approval.approved:
                logger.warning("Circuit breaker reset denied by human")
                return False

        # Reset all breakers
        for breaker in self.breakers.values():
            breaker.reset()

        self.state = CircuitBreakerState.CLOSED
        logger.info("Circuit breakers reset")
        return True

    def _format_trip_reason(self, triggered: List[str]) -> str:
        """Format human-readable reason for circuit breaker trip."""
        reasons = {
            'daily_loss': "Daily loss limit exceeded",
            'drawdown': "Maximum drawdown exceeded",
            'consecutive_losses': "Too many consecutive losses",
            'volatility': "Market volatility too high (VIX spike)",
            'anomaly_score': "Multiple anomalies detected"
        }

        return " | ".join([reasons[b] for b in triggered])
```

### Fraud Detection (Deep Learning)

```python
class FraudDetectionModel:
    """
    Transformer-based autoencoder for detecting fraudulent/anomalous trading patterns.
    Based on research in high-frequency trading surveillance.
    """
    def __init__(self):
        self.model = TransformerAutoencoder(
            input_dim=50,
            hidden_dim=128,
            num_layers=4,
            num_heads=8
        )
        self.threshold = 0.95  # 95th percentile of reconstruction error

    def detect_fraud(self, trade_sequence: np.ndarray) -> FraudScore:
        """
        Detect fraudulent patterns in trade sequence.

        Args:
            trade_sequence: Array of shape (seq_len, features)

        Returns:
            FraudScore with probability and details
        """
        # Encode and reconstruct
        encoded = self.model.encode(trade_sequence)
        reconstructed = self.model.decode(encoded)

        # Calculate reconstruction error
        reconstruction_error = np.mean((trade_sequence - reconstructed) ** 2)

        # Calculate fraud probability
        fraud_probability = 1 / (1 + np.exp(-5 * (reconstruction_error - self.threshold)))

        # Identify anomalous features
        feature_errors = np.mean((trade_sequence - reconstructed) ** 2, axis=0)
        anomalous_features = np.where(feature_errors > np.percentile(feature_errors, 95))[0]

        return FraudScore(
            probability=fraud_probability,
            reconstruction_error=reconstruction_error,
            anomalous_features=anomalous_features.tolist(),
            severity='high' if fraud_probability > 0.8 else 'medium' if fraud_probability > 0.5 else 'low'
        )
```

---

## Deployment Architecture

### Infrastructure

```yaml
# docker-compose.yml
version: '3.8'

services:
  # Message Queue & State Management
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes

  # Database for persistent storage
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: trading
      POSTGRES_USER: trader
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  # MCP Server for market data
  mcp-server:
    build:
      context: .
      dockerfile: docker/Dockerfile.mcp_server
    environment:
      - REDIS_URL=redis://redis:6379
      - ALPACA_API_KEY=${ALPACA_API_KEY}
      - ALPACA_SECRET_KEY=${ALPACA_SECRET_KEY}
    ports:
      - "8000:8000"
    depends_on:
      - redis

  # Supervisor Agent (Orchestrator)
  supervisor:
    build:
      context: .
      dockerfile: docker/Dockerfile.supervisor
    environment:
      - OPENROUTER_API_KEY=${OPENROUTER_API_KEY}
      - REDIS_URL=redis://redis:6379
      - POSTGRES_URL=postgresql://trader:${DB_PASSWORD}@postgres:5432/trading
      - MCP_SERVER_URL=http://mcp-server:8000
    depends_on:
      - redis
      - postgres
      - mcp-server
    restart: unless-stopped

  # Research Agent
  research-agent:
    build:
      context: .
      dockerfile: docker/Dockerfile.agents
    command: python -m src.agents.research_agent
    environment:
      - OPENROUTER_API_KEY=${OPENROUTER_API_KEY}
      - REDIS_URL=redis://redis:6379
      - MCP_SERVER_URL=http://mcp-server:8000
    depends_on:
      - redis
      - mcp-server
    restart: unless-stopped

  # Signal Agent (RL + LLM)
  signal-agent:
    build:
      context: .
      dockerfile: docker/Dockerfile.agents
    command: python -m src.agents.signal_agent
    environment:
      - OPENROUTER_API_KEY=${OPENROUTER_API_KEY}
      - REDIS_URL=redis://redis:6379
    volumes:
      - rl_checkpoints:/app/data/rl_checkpoints
    depends_on:
      - redis
    restart: unless-stopped

  # Risk Manager Agent
  risk-manager:
    build:
      context: .
      dockerfile: docker/Dockerfile.agents
    command: python -m src.agents.risk_manager_agent
    environment:
      - REDIS_URL=redis://redis:6379
      - POSTGRES_URL=postgresql://trader:${DB_PASSWORD}@postgres:5432/trading
    depends_on:
      - redis
      - postgres
    restart: unless-stopped

  # Execution Agent
  execution-agent:
    build:
      context: .
      dockerfile: docker/Dockerfile.agents
    command: python -m src.agents.execution_agent
    environment:
      - ALPACA_API_KEY=${ALPACA_API_KEY}
      - ALPACA_SECRET_KEY=${ALPACA_SECRET_KEY}
      - REDIS_URL=redis://redis:6379
    depends_on:
      - redis
    restart: unless-stopped

  # RL Model Training (runs periodically)
  rl-training:
    build:
      context: .
      dockerfile: docker/Dockerfile.rl_training
    command: python scripts/train_rl_models.py
    environment:
      - REDIS_URL=redis://redis:6379
      - POSTGRES_URL=postgresql://trader:${DB_PASSWORD}@postgres:5432/trading
    volumes:
      - rl_checkpoints:/app/data/rl_checkpoints
      - experience_replay:/app/data/experience_replay
    depends_on:
      - redis
      - postgres
    profiles: ["training"]  # Only run when explicitly requested

  # Human-in-Loop API
  hitl-api:
    build:
      context: .
      dockerfile: docker/Dockerfile.agents
    command: uvicorn src.human_in_loop.decision_interface:app --host 0.0.0.0 --port 8001
    environment:
      - REDIS_URL=redis://redis:6379
    ports:
      - "8001:8001"
    depends_on:
      - redis
    restart: unless-stopped

  # Monitoring Dashboard
  dashboard:
    build:
      context: .
      dockerfile: docker/Dockerfile.agents
    command: streamlit run src/monitoring/dashboard.py --server.port 8501
    environment:
      - REDIS_URL=redis://redis:6379
      - POSTGRES_URL=postgresql://trader:${DB_PASSWORD}@postgres:5432/trading
    ports:
      - "8501:8501"
    depends_on:
      - redis
      - postgres
    restart: unless-stopped

volumes:
  redis_data:
  postgres_data:
  rl_checkpoints:
  experience_replay:
```

### Kubernetes Deployment (Production)

```yaml
# kubernetes/supervisor.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: trading-supervisor
  labels:
    app: trading
    component: supervisor
spec:
  replicas: 1  # Single supervisor instance
  selector:
    matchLabels:
      app: trading
      component: supervisor
  template:
    metadata:
      labels:
        app: trading
        component: supervisor
    spec:
      containers:
      - name: supervisor
        image: trading-system/supervisor:latest
        env:
        - name: OPENROUTER_API_KEY
          valueFrom:
            secretKeyRef:
              name: trading-secrets
              key: openrouter-api-key
        - name: REDIS_URL
          value: redis://redis-service:6379
        - name: POSTGRES_URL
          valueFrom:
            secretKeyRef:
              name: trading-secrets
              key: postgres-url
        resources:
          requests:
            memory: "2Gi"
            cpu: "1000m"
          limits:
            memory: "4Gi"
            cpu: "2000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8080
          initialDelaySeconds: 10
          periodSeconds: 5

---
# kubernetes/agents.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: trading-agents
  labels:
    app: trading
    component: agents
spec:
  replicas: 3  # Multiple agent instances for parallelization
  selector:
    matchLabels:
      app: trading
      component: agents
  template:
    metadata:
      labels:
        app: trading
        component: agents
    spec:
      containers:
      - name: research-agent
        image: trading-system/agents:latest
        command: ["python", "-m", "src.agents.research_agent"]
        env:
        - name: OPENROUTER_API_KEY
          valueFrom:
            secretKeyRef:
              name: trading-secrets
              key: openrouter-api-key
        - name: REDIS_URL
          value: redis://redis-service:6379
        resources:
          requests:
            memory: "1Gi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "1000m"

      - name: signal-agent
        image: trading-system/agents:latest
        command: ["python", "-m", "src.agents.signal_agent"]
        env:
        - name: REDIS_URL
          value: redis://redis-service:6379
        volumeMounts:
        - name: rl-checkpoints
          mountPath: /app/data/rl_checkpoints
        resources:
          requests:
            memory: "2Gi"
            cpu: "1000m"
          limits:
            memory: "4Gi"
            cpu: "2000m"

      - name: risk-manager
        image: trading-system/agents:latest
        command: ["python", "-m", "src.agents.risk_manager_agent"]
        env:
        - name: REDIS_URL
          value: redis://redis-service:6379
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "500m"

      - name: execution-agent
        image: trading-system/agents:latest
        command: ["python", "-m", "src.agents.execution_agent"]
        env:
        - name: ALPACA_API_KEY
          valueFrom:
            secretKeyRef:
              name: trading-secrets
              key: alpaca-api-key
        - name: ALPACA_SECRET_KEY
          valueFrom:
            secretKeyRef:
              name: trading-secrets
              key: alpaca-secret-key
        - name: REDIS_URL
          value: redis://redis-service:6379
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "500m"

      volumes:
      - name: rl-checkpoints
        persistentVolumeClaim:
          claimName: rl-checkpoints-pvc

---
# kubernetes/redis.yaml
apiVersion: v1
kind: Service
metadata:
  name: redis-service
spec:
  selector:
    app: redis
  ports:
  - port: 6379
    targetPort: 6379
---
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: redis
spec:
  serviceName: redis-service
  replicas: 1
  selector:
    matchLabels:
      app: redis
  template:
    metadata:
      labels:
        app: redis
    spec:
      containers:
      - name: redis
        image: redis:7-alpine
        ports:
        - containerPort: 6379
        volumeMounts:
        - name: redis-data
          mountPath: /data
        command:
        - redis-server
        - --appendonly
        - "yes"
  volumeClaimTemplates:
  - metadata:
      name: redis-data
    spec:
      accessModes: ["ReadWriteOnce"]
      resources:
        requests:
          storage: 10Gi
```

---

## Security & Compliance

### Security Best Practices

```python
class SecurityManager:
    """
    Manages security controls for the multi-agent system.
    """

    def __init__(self):
        self.permission_matrix = self._load_permission_matrix()
        self.audit_logger = AuditLogger()

    def _load_permission_matrix(self):
        """
        Define permissions for each agent.
        Deny-all by default, explicit allowlist.
        """
        return {
            'research_agent': {
                'allowed_tools': [
                    'fetch_market_data',
                    'fetch_news',
                    'calculate_indicators'
                ],
                'allowed_resources': [
                    'market://*',
                    'news://*'
                ],
                'denied_actions': [
                    'execute_order',
                    'modify_risk_limits'
                ]
            },
            'signal_agent': {
                'allowed_tools': [
                    'rl_ensemble',
                    'sentiment_check'
                ],
                'allowed_resources': [
                    'rl_models://*'
                ],
                'denied_actions': [
                    'execute_order',
                    'modify_risk_limits'
                ]
            },
            'risk_manager_agent': {
                'allowed_tools': [
                    'calculate_position_size',
                    'check_circuit_breaker',
                    'get_risk_metrics'
                ],
                'allowed_resources': [
                    'risk://*',
                    'portfolio://*'
                ],
                'allowed_actions': [
                    'reject_trade',
                    'trigger_circuit_breaker'
                ],
                'denied_actions': [
                    'execute_order'
                ]
            },
            'execution_agent': {
                'allowed_tools': [
                    'submit_order',
                    'get_order_status',
                    'calculate_slippage'
                ],
                'allowed_resources': [
                    'broker://*'
                ],
                'allowed_actions': [
                    'submit_market_order',
                    'submit_limit_order',
                    'cancel_order'
                ],
                'denied_actions': [
                    'modify_risk_limits',
                    'reset_circuit_breaker'
                ],
                'requires_confirmation': [
                    'submit_market_order'  # Requires risk validation
                ]
            },
            'supervisor_agent': {
                'allowed_tools': ['*'],  # Supervisor has broad permissions
                'allowed_resources': ['*'],
                'allowed_actions': ['*'],
                'requires_confirmation': [
                    'reset_circuit_breaker',
                    'modify_risk_limits',
                    'manual_trade_override'
                ]
            }
        }

    async def validate_action(self,
                             agent_name: str,
                             action: str,
                             context: dict) -> ValidationResult:
        """Validate if agent is allowed to perform action."""

        permissions = self.permission_matrix.get(agent_name, {})

        # Check denied actions
        if action in permissions.get('denied_actions', []):
            self.audit_logger.log_security_violation(
                agent=agent_name,
                action=action,
                reason='Action explicitly denied'
            )
            return ValidationResult(
                allowed=False,
                reason=f"Agent {agent_name} is not permitted to perform {action}"
            )

        # Check if confirmation required
        if action in permissions.get('requires_confirmation', []):
            # Require human approval
            approval = await human_loop_manager.request_human_approval(
                decision_type='security_confirmation',
                context={
                    'agent': agent_name,
                    'action': action,
                    'context': context
                }
            )

            if not approval.approved:
                return ValidationResult(
                    allowed=False,
                    reason='Human approval denied'
                )

        # Log successful validation
        self.audit_logger.log_action(
            agent=agent_name,
            action=action,
            context=context,
            timestamp=datetime.now()
        )

        return ValidationResult(allowed=True)
```

### Secrets Management

```python
class SecretsManager:
    """
    Manages API keys and sensitive data.
    Short-lived credentials, never in agent context.
    """

    def __init__(self):
        self.vault = VaultClient()  # HashiCorp Vault
        self.rotation_schedule = {}

    async def get_api_key(self, service: str) -> str:
        """
        Retrieve API key from vault.
        Returns short-lived token (1 hour TTL).
        """
        # Check cache first
        cached_key = await self._get_cached_key(service)
        if cached_key and not self._is_expired(cached_key):
            return cached_key['value']

        # Fetch from vault
        key_data = await self.vault.read_secret(f"trading/{service}/api_key")

        # Create short-lived token
        token = self._create_token(key_data, ttl=3600)

        # Cache with TTL
        await self._cache_key(service, token)

        return token

    async def rotate_credentials(self):
        """
        Rotate API credentials periodically.
        Called by background job every 24 hours.
        """
        services = ['alpaca', 'openrouter']

        for service in services:
            try:
                # Generate new key
                new_key = await self._generate_new_key(service)

                # Update vault
                await self.vault.write_secret(
                    f"trading/{service}/api_key",
                    {'value': new_key, 'created_at': datetime.now()}
                )

                # Invalidate cached keys
                await self._invalidate_cache(service)

                logger.info(f"Rotated credentials for {service}")

            except Exception as e:
                logger.error(f"Failed to rotate {service} credentials: {e}")
                # Alert security team
                await self._send_security_alert(service, e)
```

---

## Performance Metrics

### Key Metrics to Track

```python
class PerformanceMetrics:
    """
    Comprehensive performance tracking for multi-agent system.
    """

    def __init__(self):
        self.metrics = {
            # Trading Performance
            'sharpe_ratio': RollingMetric(window=30),
            'sortino_ratio': RollingMetric(window=30),
            'max_drawdown': MaxDrawdownTracker(),
            'win_rate': WinRateTracker(),
            'profit_factor': ProfitFactorTracker(),
            'avg_trade_duration': AverageMetric(),

            # Agent Performance
            'research_agent_latency': LatencyTracker(),
            'signal_agent_accuracy': AccuracyTracker(),
            'risk_manager_rejections': CounterMetric(),
            'execution_agent_slippage': AverageMetric(),

            # System Performance
            'message_queue_latency': LatencyTracker(),
            'mcp_response_time': LatencyTracker(),
            'agent_cpu_usage': GaugeMetric(),
            'agent_memory_usage': GaugeMetric(),

            # RL Model Performance
            'rl_model_confidence': AverageMetric(),
            'rl_model_agreement': AverageMetric(),
            'training_loss': RollingMetric(window=100),

            # Risk Metrics
            'daily_pl': DailyPLTracker(),
            'position_concentration': GaugeMetric(),
            'leverage_ratio': GaugeMetric(),
            'circuit_breaker_trips': CounterMetric(),

            # Human-in-Loop Metrics
            'human_approvals': CounterMetric(),
            'human_rejections': CounterMetric(),
            'avg_approval_time': AverageMetric()
        }

    def export_prometheus(self):
        """Export metrics in Prometheus format."""
        prometheus_metrics = []

        for name, metric in self.metrics.items():
            prometheus_metrics.append(
                f"# HELP trading_{name} {metric.description}\n"
                f"# TYPE trading_{name} {metric.type}\n"
                f"trading_{name} {metric.value}\n"
            )

        return "\n".join(prometheus_metrics)
```

### Monitoring Dashboard

```python
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

def render_performance_dashboard():
    st.set_page_config(page_title="Multi-Agent Trading Dashboard", layout="wide")

    st.title("Multi-Agent Trading System Dashboard")

    # Metrics Summary
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Sharpe Ratio", "1.85", "+0.12")

    with col2:
        st.metric("Win Rate", "58.3%", "+2.1%")

    with col3:
        st.metric("Total P&L", "$12,450", "+$890")

    with col4:
        st.metric("Circuit Breakers", "0", "0")

    # Performance Chart
    st.subheader("Equity Curve")

    fig = make_subplots(
        rows=2, cols=1,
        subplot_titles=("Portfolio Equity", "Daily P&L"),
        row_heights=[0.7, 0.3]
    )

    # Add traces
    fig.add_trace(
        go.Scatter(x=equity_data['date'], y=equity_data['value'], name="Equity"),
        row=1, col=1
    )

    fig.add_trace(
        go.Bar(x=daily_pl_data['date'], y=daily_pl_data['value'], name="Daily P&L"),
        row=2, col=1
    )

    st.plotly_chart(fig, use_container_width=True)

    # Agent Performance
    st.subheader("Agent Performance Metrics")

    col1, col2 = st.columns(2)

    with col1:
        st.metric("Research Agent Latency", "1.2s", "-0.3s")
        st.metric("Signal Agent Accuracy", "76.5%", "+3.2%")

    with col2:
        st.metric("Execution Slippage", "0.08%", "-0.02%")
        st.metric("Risk Rejections", "12", "+2")

    # Recent Trades
    st.subheader("Recent Trades")
    st.dataframe(recent_trades_df)

    # Alerts
    st.subheader("Active Alerts")
    if len(active_alerts) > 0:
        for alert in active_alerts:
            st.warning(f"{alert['timestamp']}: {alert['message']}")
    else:
        st.success("No active alerts")
```

---

## Implementation Roadmap

### Phase 1: Foundation (Weeks 1-2)

**Objectives:**
- Set up core infrastructure
- Implement basic agent framework
- Establish communication protocols

**Tasks:**
1. Set up Redis for message queue and state management
2. Implement MCP server for market data
3. Create base agent class with Claude Agents SDK
4. Implement Research Agent (basic version)
5. Set up PostgreSQL for persistent storage
6. Create logging and monitoring infrastructure

**Deliverables:**
- Working MCP server exposing market data
- Research Agent capable of basic market analysis
- Message bus for agent communication
- Docker containers for all services

### Phase 2: Signal Generation (Weeks 3-4)

**Objectives:**
- Implement RL models
- Create Signal Agent
- Integrate with Research Agent

**Tasks:**
1. Implement DQN, PPO, and A2C models
2. Create training pipeline for RL models
3. Implement ensemble mechanism
4. Create Signal Agent integrating RL + LLM
5. Backtest signals on historical data
6. Optimize hyperparameters

**Deliverables:**
- Trained RL models with >55% win rate
- Signal Agent generating reliable signals
- Backtesting framework
- Model checkpointing system

### Phase 3: Risk & Execution (Weeks 5-6)

**Objectives:**
- Implement Risk Manager Agent
- Create Execution Agent
- Integrate with Alpaca API

**Tasks:**
1. Port existing risk management to agent framework
2. Implement circuit breaker system
3. Create Execution Agent with order routing
4. Implement slippage optimization
5. Add stop-loss and take-profit logic
6. Test full pipeline with paper trading

**Deliverables:**
- Risk Manager Agent with circuit breakers
- Execution Agent with order optimization
- Full pipeline: Research → Signal → Risk → Execution
- Paper trading validation

### Phase 4: Orchestration (Weeks 7-8)

**Objectives:**
- Implement Supervisor Agent
- Coordinate multi-agent workflows
- Performance tracking

**Tasks:**
1. Create Supervisor Agent using Claude Opus 4
2. Implement task decomposition logic
3. Add parallel agent execution
4. Create performance tracking system
5. Implement daily routine orchestration
6. Add error handling and recovery

**Deliverables:**
- Supervisor Agent orchestrating all agents
- Parallel execution of research tasks
- Performance metrics dashboard
- Automated daily trading routine

### Phase 5: Human-in-Loop (Weeks 9-10)

**Objectives:**
- Implement human approval system
- Create anomaly detection
- Build decision interface

**Tasks:**
1. Implement confidence scoring
2. Create anomaly detection system
3. Build human approval workflow
4. Create decision API (FastAPI)
5. Build web dashboard (Streamlit)
6. Implement multi-channel notifications

**Deliverables:**
- Anomaly detection system
- Human approval workflow
- Decision interface (web + API)
- Notification system (email/Slack)

### Phase 6: Testing & Validation (Weeks 11-12)

**Objectives:**
- Comprehensive testing
- Paper trading validation
- Performance optimization

**Tasks:**
1. Unit tests for all agents
2. Integration tests for full pipeline
3. Load testing for message queue
4. Paper trading for 30 days
5. Performance profiling and optimization
6. Security audit

**Deliverables:**
- Test coverage >80%
- 30 days of paper trading data
- Performance benchmarks
- Security audit report

### Phase 7: Production Deployment (Weeks 13-14)

**Objectives:**
- Deploy to production
- Monitor and iterate
- Documentation

**Tasks:**
1. Deploy to Kubernetes cluster
2. Set up monitoring (Prometheus/Grafana)
3. Configure alerts and on-call
4. Create runbooks for operations
5. Write comprehensive documentation
6. Train team on system operations

**Deliverables:**
- Production deployment
- Monitoring dashboards
- Runbooks and documentation
- Trained operations team

### Phase 8: Optimization & Iteration (Ongoing)

**Objectives:**
- Continuous improvement
- Model retraining
- Feature additions

**Tasks:**
1. Monitor performance metrics
2. Retrain RL models monthly
3. A/B test new strategies
4. Add new data sources
5. Optimize agent performance
6. Incorporate user feedback

---

## Conclusion

This multi-agent AI trading system architecture provides a comprehensive, production-ready design for building sophisticated trading systems. Key benefits include:

**Scalability:**
- Agents can be scaled independently
- Parallel processing for research and analysis
- Message queue handles high throughput

**Reliability:**
- Circuit breakers protect capital
- Anomaly detection prevents fraud
- Human-in-loop for critical decisions

**Modularity:**
- Each agent has single responsibility
- Easy to add/remove agents
- Clear interfaces between components

**Observability:**
- Comprehensive logging and metrics
- Performance tracking at all levels
- Real-time monitoring dashboards

**Security:**
- Deny-all permission model
- Short-lived credentials
- Audit logging for all actions

**Next Steps:**
1. Review and validate architecture with team
2. Set up development environment
3. Begin Phase 1 implementation
4. Regular architecture reviews and updates

---

**Document Version:** 1.0.0
**Last Updated:** 2025-10-30
**Authors:** Claude Code Research Team
**Status:** Ready for Implementation
