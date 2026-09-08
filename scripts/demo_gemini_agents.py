#!/usr/bin/env python3
"""
Demo script for Google Gemini AI Agent Integration

This script demonstrates how Gemini agents can enhance our trading system
while maintaining our disciplined risk management approach.
"""

import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ai.gemini_agent import (
    AgentConfig, 
    RegimeDetectionAgent, 
    RiskManagementAgent, 
    get_gemini_agent_status
)
from config.gemini_agent_config import (
    GEMINI_AGENT_CONFIG, 
    REGIME_DETECTION_SETTINGS, 
    RISK_MANAGEMENT_SETTINGS,
    validate_config
)


def demo_regime_detection():
    """Demonstrate the regime detection capabilities"""
    print("="*60)
    print("DEMO: Regime Detection Agent")
    print("="*60)
    
    # Initialize agent
    config = AgentConfig()
    agent = RegimeDetectionAgent(config)
    
    # Simulate current market data (similar to our actual system)
    current_market_data = {
        "price": 767.78,
        "iv_rank": 13.2,  # Below our 30% threshold
        "vix": 15.30,
        "spy_above_200dma": True,
        "regime_conditions": "LOW_VOLATILITY"
    }
    
    print(f"Current market conditions:")
    print(f"  - Price: ${current_market_data['price']:.2f}")
    print(f"  - IV Rank: {current_market_data['iv_rank']:.1f}% (threshold: {REGIME_DETECTION_SETTINGS['required_iv_rank_threshold']}%)")
    print(f"  - VIX: {current_market_data['vix']:.2f}")
    print(f"  - SPY above 200 DMA: {current_market_data['spy_above_200dma']}")
    print()
    
    # Perform regime analysis
    if config.api_key:
        result = agent.analyze_regime(current_market_data)
        
        if "error" not in result:
            print("Gemini Agent Analysis:")
            print(result["analysis"])
        else:
            print(f"Agent analysis failed: {result['error']}")
            print("\nNOTE: This is expected if GOOGLE_API_KEY is not set.")
    else:
        print("Google API key not set - showing example analysis...")
        print("\nExample Gemini Analysis:")
        print("""
Based on the current market conditions:

1. REGIME SUITABILITY: NOT SUITABLE
   - IV Rank (13.2%) is significantly below the required threshold (30%)
   - This represents a low volatility environment where selling premium would be risky
   - Current regime is not favorable for put credit strategies

2. SPECIFIC RISKS:
   - Risk of volatility expansion that could trigger stop losses
   - Limited premium collection in low volatility environment
   - Higher probability of adverse moves without compensation

3. RECOMMENDATION: DO NOT ENTER TRADES
   - Wait for IV Rank to rise above 30% before considering entries
   - Current conditions do not meet system requirements
   - Preserving capital is more important than forcing trades

4. SUPPORTING METRICS:
   - IV Rank percentile: Very low
   - Volatility environment: Unfavorable for premium selling
   - Risk/Reward: Poor due to limited premium available
        """)
    
    print("\nThis aligns with our current system's regime gate that blocks entries when IV rank is below 30%.")
    print("The AI agent reinforces our disciplined approach to risk management.")


def demo_risk_management():
    """Demonstrate the risk management capabilities"""
    print("\n" + "="*60)
    print("DEMO: Risk Management Agent")
    print("="*60)
    
    # Initialize agent
    config = AgentConfig()
    agent = RiskManagementAgent(config)
    
    # Simulate portfolio and market data
    portfolio_data = {
        "positions": [
            {
                "symbol": "SPY",
                "strategy": "bull_put_credit",
                "entry_date": "2026-09-04",
                "strike_short": 742,
                "strike_long": 737,
                "quantity": 1,
                "credit_received": 0.61,
                "current_value": 0.45,
                "unrealized_pnl": 16.00
            }
        ],
        "total_equity": 50000,
        "cash_balance": 48000,
        "total_exposure": 2000,
        "daily_pnl": 150.00,
        "unrealized_pnl": 16.00
    }
    
    market_data = {
        "price": 767.78,
        "iv_rank": 13.2,
        "vix": 15.30,
        "market_regime": "low_volatility_consolidation"
    }
    
    print("Current portfolio snapshot:")
    print(f"  - Total Equity: ${portfolio_data['total_equity']:,}")
    print(f"  - Cash Balance: ${portfolio_data['cash_balance']:,}")
    print(f"  - Total Exposure: ${portfolio_data['total_exposure']:,}")
    print(f"  - Daily P&L: ${portfolio_data['daily_pnl']:.2f}")
    print(f"  - Unrealized P&L: ${portfolio_data['unrealized_pnl']:.2f}")
    print()
    
    if config.api_key:
        result = agent.assess_portfolio_risk(portfolio_data, market_data)
        
        if "error" not in result:
            print("Gemini Agent Risk Assessment:")
            print(result["risk_assessment"])
        else:
            print(f"Risk assessment failed: {result['error']}")
            print("\nNOTE: This is expected if GOOGLE_API_KEY is not set.")
    else:
        print("Google API key not set - showing example risk assessment...")
        print("\nExample Gemini Risk Assessment:")
        print("""
PORTFOLIO RISK ASSESSMENT:

1. CURRENT RISK EXPOSURE: LOW TO MODERATE
   - Single position with defined risk parameters
   - Well-capitalized account with 96% cash allocation
   - Current position represents only 4% of total equity

2. POTENTIAL STRESS SCENARIOS:
   - Volatility expansion: Limited downside due to defined risk position
   - Market gap down: Protected by long put strike at 737
   - Liquidity concerns: SPY highly liquid with tight spreads

3. CORRELATION RISKS: LOW
   - Single equity position in broad market index
   - No concentration in sector or individual stocks
   - Diversification maintained through cash allocation

4. RECOMMENDATIONS:
   - Current position acceptable within overall portfolio context
   - Maintain discipline and avoid adding to position in low volatility
   - Consider profit taking if credit reduces to 25% of initial value
   - Continue monitoring IV rank for future entry opportunities

5. COMPLIANCE CHECK:
   - Portfolio respects paper-only validation mode
   - Position size appropriate for validation phase
   - Risk management protocols properly implemented
        """)
    
    print("\nThe AI agent reinforces our disciplined approach to risk management and validates our current position sizing.")


def demo_trade_validation():
    """Demonstrate the trade validation capabilities"""
    print("\n" + "="*60)
    print("DEMO: Trade Validation Agent")
    print("="*60)
    
    # Initialize agent
    config = AgentConfig()
    agent = RiskManagementAgent(config)  # Reusing for trade validation
    
    # Simulate a potential trade idea
    trade_idea = {
        "strategy": "bull_put_credit",
        "underlying": "SPY",
        "quantity": 1,
        "short_strike": 742,
        "long_strike": 737,
        "credit_received": 0.61,
        "dte": 35,
        "short_delta": 0.16,
        "probability_of_profit": 0.84
    }
    
    market_data = {
        "price": 767.78,
        "iv_rank": 13.2,  # Below threshold
        "vix": 15.30,
        "spy_above_200dma": True
    }
    
    print("Potential trade idea:")
    print(f"  - Strategy: {trade_idea['strategy']}")
    print(f"  - Underlying: {trade_idea['underlying']}")
    print(f"  - Quantity: {trade_idea['quantity']}")
    print(f"  - Strikes: {trade_idea['long_strike']}/{trade_idea['short_strike']} ({trade_idea['short_strike']}-{trade_idea['long_strike']} wide)")
    print(f"  - Credit: ${trade_idea['credit_received']:.2f}")
    print(f"  - DTE: {trade_idea['dte']}")
    print(f"  - Short Delta: {trade_idea['short_delta']}")
    print()
    
    print(f"Current market conditions:")
    print(f"  - IV Rank: {market_data['iv_rank']:.1f}% (threshold: {REGIME_DETECTION_SETTINGS['required_iv_rank_threshold']}%)")
    print(f"  - VIX: {market_data['vix']:.2f}")
    print()
    
    if config.api_key:
        result = agent.validate_trade_idea(trade_idea, market_data)
        
        if "error" not in result:
            print("Gemini Agent Trade Validation:")
            print(result["validation"])
        else:
            print(f"Trade validation failed: {result['error']}")
            print("\nNOTE: This is expected if GOOGLE_API_KEY is not set.")
    else:
        print("Google API key not set - showing example validation...")
        print("\nExample Gemini Trade Validation:")
        print("""
TRADE VALIDATION ANALYSIS:

1. RISK-REWARD ASSESSMENT: POOR
   - Credit received ($0.61) is limited in low volatility environment
   - Risk of volatility expansion outweighs limited premium
   - Current market conditions do not justify entry

2. ALIGNMENT WITH CURRENT REGIME: POOR
   - IV Rank (13.2%) significantly below required threshold (30%)
   - System regime gate correctly prevents entries in low volatility
   - Forcing trades would violate disciplined risk management

3. POSITION SIZING APPROPRIATENESS: NOT APPLICABLE
   - Position should not be entered given regime conditions
   - Maintaining current position is acceptable, but no new entries

4. POTENTIAL ISSUES:
   - Violates established regime gate (IV Rank < 30%)
   - Premium collection limited in current environment
   - Higher risk of adverse move without adequate compensation

5. RECOMMENDATION: DO NOT PROCEED
   - Respect the system's regime gate and wait for favorable conditions
   - Current discipline is correct and protects capital
   - Entry opportunities will arise when IV Rank increases above threshold
        """)
    
    print("\nThis demonstrates how the AI agent reinforces our disciplined regime gate approach.")


def main():
    """Main demo function"""
    print("Google Gemini AI Agent Integration Demo")
    print("Maintaining disciplined risk management while enhancing capabilities")
    print()
    
    # Validate configuration
    config_valid = validate_config()
    print("Configuration Validation:")
    for key, value in config_valid.items():
        status = "✓" if value else "✗"
        print(f"  {status} {key}: {value}")
    print()
    
    # Show agent status
    status = get_gemini_agent_status()
    print(f"Gemini Agent Status:")
    print(f"  - Enabled: {status['gemini_integration_enabled']}")
    print(f"  - API Key Available: {status['api_key_available']}")
    print(f"  - Available Models: {status['models_available']}")
    print()
    
    if not status['api_key_available']:
        print("NOTE: To use the actual Gemini agents, set your GOOGLE_API_KEY environment variable.")
        print("The demo will show example outputs instead.")
        print()
    
    # Run demos
    demo_regime_detection()
    demo_risk_management()
    demo_trade_validation()
    
    print("\n" + "="*60)
    print("DEMO SUMMARY")
    print("="*60)
    print("The Gemini AI agents enhance our trading system by:")
    print("• Providing intelligent regime detection while respecting our thresholds")
    print("• Offering advanced risk management analysis")
    print("• Validating trade ideas against our disciplined criteria")
    print("• Maintaining our paper-only validation approach until proven")
    print("• Supporting our kill switch and risk management protocols")
    print()
    print("All AI recommendations reinforce our disciplined approach to risk management,")
    print("ensuring we maintain proper validation before considering live trading.")


if __name__ == "__main__":
    main()