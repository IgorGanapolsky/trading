#!/usr/bin/env python3
"""
ADVANCED AUTONOMOUS TRADER - 2025 Standard Multi-Agent System

Architecture:
- MetaAgent: Hierarchical coordinator (Hi-DARTS inspired)
- ResearchAgent: Fundamental + news analysis (P1GPT inspired)
- SignalAgent: Technical + LLM reasoning (Trading-R1 inspired)
- RiskAgent: Portfolio risk + Kelly sizing
- ExecutionAgent: Order execution + timing
- RL Layer: Adaptive policy learning (AlphaQuanter inspired)

This is a 2025-standard AI trading system built with CANI principle.
"""

import json
import logging
import os
import sys
from datetime import date, datetime
from pathlib import Path

# Add parent to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import alpaca_trade_api as tradeapi
from src.agents.execution_agent import ExecutionAgent
from src.agents.meta_agent import MetaAgent
from src.agents.reinforcement_learning import RLPolicyLearner
from src.agents.reinforcement_learning_optimized import OptimizedRLPolicyLearner
from src.agents.research_agent import ResearchAgent
from src.agents.risk_agent import RiskAgent
from src.agents.signal_agent import SignalAgent
from src.utils.error_monitoring import init_sentry

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("logs/advanced_trading.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# Configuration
ALPACA_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET = os.getenv("ALPACA_SECRET_KEY")

if not ALPACA_KEY or not ALPACA_SECRET:
    raise ValueError("ALPACA_API_KEY and ALPACA_SECRET_KEY environment variables must be set")

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

# Initialize Alpaca API
os.environ["APCA_API_KEY_ID"] = ALPACA_KEY
os.environ["APCA_API_SECRET_KEY"] = ALPACA_SECRET
api = tradeapi.REST(ALPACA_KEY, ALPACA_SECRET, "https://paper-api.alpaca.markets")


def get_market_data(symbol: str) -> dict:
    """
    Fetch comprehensive market data for a symbol.

    Returns dict with:
    - price_history: OHLCV data
    - fundamentals: P/E, growth, etc.
    - news: Recent news items
    - market_context: Sector, trend, volatility
    """
    try:
        # Get price history from Alpaca
        bars = api.get_bars(symbol, "1Day", limit=200).df

        if bars.empty:
            logger.warning(f"No data for {symbol}")
            return {}

        # Calculate volatility
        returns = bars["close"].pct_change()
        volatility = returns.std() * (252**0.5)  # Annualized

        # Trend strength (simple momentum)
        if len(bars) >= 50:
            ma_20 = bars["close"].rolling(20).mean().iloc[-1]
            ma_50 = bars["close"].rolling(50).mean().iloc[-1]
            trend_strength = abs(ma_20 - ma_50) / ma_50
        else:
            trend_strength = 0.1

        return {
            "symbol": symbol,
            "price": bars["close"].iloc[-1],
            "price_history": bars,
            "volatility": volatility,
            "trend_strength": trend_strength,
            "fundamentals": {
                # These would come from a fundamentals API
                "pe_ratio": "N/A",
                "growth_rate": "N/A",
                "profit_margin": "N/A",
                "market_cap": "N/A",
            },
            "news": [
                # Would come from news API
            ],
            "market_context": {
                "sector": ("Technology" if symbol in ["NVDA", "GOOGL", "AMZN"] else "ETF"),
                "market_trend": "NEUTRAL",
                "volatility": volatility,
            },
        }
    except Exception as e:
        logger.error(f"Error fetching data for {symbol}: {e}")
        return {}


def main():
    """Main execution loop for advanced multi-agent trading system."""

    init_sentry()

    print("\n" + "=" * 80)
    print("🤖 ADVANCED MULTI-AGENT TRADING SYSTEM (2025 Standard)")
    print(f"📅 Date: {datetime.now().strftime('%Y-%m-%d %I:%M %p')}")
    print("=" * 80)

    # Initialize agents
    logger.info("Initializing multi-agent system...")

    meta_agent = MetaAgent()
    research_agent = ResearchAgent()
    signal_agent = SignalAgent()
    risk_agent = RiskAgent()
    execution_agent = ExecutionAgent(alpaca_api=api)
    # Use optimized RL learner if enabled (default: True)
    use_optimized_rl = os.getenv("USE_OPTIMIZED_RL", "true").lower() == "true"
    if use_optimized_rl:
        rl_learner = OptimizedRLPolicyLearner(
            enable_replay=True,
            enable_adaptive_lr=True,
            initial_exploration_rate=0.3,
        )
        logger.info("Using OptimizedRLPolicyLearner with experience replay enabled")
    else:
        rl_learner = RLPolicyLearner()
        logger.info("Using standard RLPolicyLearner")

    # Register agents with meta-agent
    meta_agent.register_agent(research_agent)
    meta_agent.register_agent(signal_agent)
    meta_agent.register_agent(risk_agent)
    meta_agent.register_agent(execution_agent)

    logger.info("✅ All agents initialized")

    # Get portfolio state
    account = api.get_account()
    portfolio_value = float(account.equity)

    print(f"\n💰 Portfolio Value: ${portfolio_value:,.2f}")
    print("📊 System: Multi-Agent (Meta + Research + Signal + Risk + Execution + RL)")

    # Trading symbols
    symbols = ["SPY", "GOOGL"]  # Start with 2 symbols

    print(f"\n🎯 Analyzing {len(symbols)} symbols...")
    print("=" * 80)

    decisions_made = []

    for symbol in symbols:
        print(f"\n📈 Analyzing {symbol}...")

        # Get market data
        market_data = get_market_data(symbol)

        if not market_data:
            print(f"❌ {symbol}: No data available")
            continue

        # Meta-agent coordinates all agents
        coordinated_decision = meta_agent.analyze(market_data)

        final_decision = coordinated_decision.get("coordinated_decision", {})
        action = final_decision.get("action", "HOLD")
        confidence = final_decision.get("confidence", 0)

        print(f"\n🧠 Meta-Agent Decision for {symbol}:")
        print(f"   Market Regime: {coordinated_decision.get('market_regime')}")
        print(f"   Coordinated Action: {action}")
        print(f"   Confidence: {confidence:.2f}")

        # If BUY, proceed with risk and execution
        if action == "BUY":
            # Risk assessment
            risk_data = {
                "portfolio_value": portfolio_value,
                "proposed_action": action,
                "symbol": symbol,
                "confidence": confidence,
                "volatility": market_data.get("volatility", 0.20),
                "historical_win_rate": 0.60,  # From backtest
            }

            risk_assessment = risk_agent.analyze(risk_data)

            if risk_assessment.get("action") == "APPROVE":
                position_size = risk_assessment.get("position_size", 0)

                print("\n✅ Risk Agent APPROVED")
                print(f"   Position Size: ${position_size:.2f}")
                print(f"   Stop-Loss: {risk_assessment.get('stop_loss', 0):.2%}")

                # Use RL to potentially override
                # Enhanced market state for OptimizedRLPolicyLearner
                price_history = market_data.get("price_history", {})
                market_state = {
                    "market_regime": coordinated_decision.get("market_regime", "UNKNOWN"),
                    "rsi": price_history.get("rsi", 50),
                    "macd_histogram": price_history.get("macd_histogram", 0.0),
                    "trend": price_history.get("trend", "SIDEWAYS"),
                    "trend_strength": price_history.get("trend_strength", 0.5),
                    "volatility": market_data.get("volatility", 0.2),
                }

                rl_action = rl_learner.select_action(market_state, action)
                print(f"\n🎓 RL Policy: {rl_action}")

                if rl_action == "BUY":
                    # Execute
                    execution_data = {
                        "action": "BUY",
                        "symbol": symbol,
                        "position_size": position_size,
                        "market_conditions": {
                            "spread": "N/A",
                            "volume": market_data.get("price_history", {}).get("volume", 0),
                            "volatility": market_data.get("volatility", 0),
                        },
                    }

                    execution_result = execution_agent.analyze(execution_data)

                    print("\n🚀 Execution Result:")
                    exec_res = execution_result.get("execution_result", {})
                    print(f"   Status: {exec_res.get('status')}")
                    if exec_res.get("status") == "SUCCESS":
                        print(f"   Order ID: {exec_res.get('order_id')}")

                        decisions_made.append(
                            {
                                "symbol": symbol,
                                "action": "BUY",
                                "position_size": position_size,
                                "order_id": exec_res.get("order_id"),
                                "timestamp": datetime.now().isoformat(),
                            }
                        )
                else:
                    print(f"   RL overrode to {rl_action} - SKIPPING trade")
            else:
                print("\n❌ Risk Agent REJECTED")
                print(f"   Reason: {risk_assessment.get('risks', 'N/A')}")
        else:
            print(f"   Action is {action} - no execution needed")

    # Summary
    print("\n" + "=" * 80)
    print("📊 SESSION SUMMARY")
    print("=" * 80)
    print(f"Symbols Analyzed: {len(symbols)}")
    print(f"Trades Executed: {len(decisions_made)}")
    print("\nRL Policy Stats:")
    rl_stats = rl_learner.get_policy_stats()
    print(f"   States Learned: {rl_stats['total_states_learned']}")
    print(f"   Action Distribution: {rl_stats['action_distribution']}")
    print("=" * 80)

    # Save decisions
    if decisions_made:
        decisions_file = DATA_DIR / f"trades_{date.today().isoformat()}.json"
        with open(decisions_file, "w") as f:
            json.dump(decisions_made, f, indent=2)
        print(f"\n📁 Decisions saved to: {decisions_file}")


if __name__ == "__main__":
    main()
