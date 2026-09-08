"""
Configuration for Google Gemini AI Agent Integration

This configuration maintains our disciplined approach while enabling 
AI-enhanced capabilities for regime detection and risk management.
"""

import os
from typing import Dict, Any

# Gemini Agent Configuration
GEMINI_AGENT_CONFIG = {
    # Model settings
    "model_name": os.getenv("GEMINI_MODEL_NAME", "gemini-1.5-pro"),
    "temperature": 0.1,  # Low temperature for consistent analytical responses
    "max_tokens": 2048,
    
    # Safety settings appropriate for financial applications
    "safety_settings": {
        "harassment": "BLOCK_MEDIUM_AND_ABOVE",
        "hate_speech": "BLOCK_MEDIUM_AND_ABOVE", 
        "sexually_explicit": "BLOCK_MEDIUM_AND_ABOVE",
        "dangerous_content": "BLOCK_MEDIUM_AND_ABOVE"
    },
    
    # Feature flags for different agent capabilities
    "features": {
        "regime_detection": True,
        "trade_validation": True, 
        "risk_management": True,
        "research_analysis": True
    },
    
    # API settings
    "api_key": os.getenv("GOOGLE_API_KEY", ""),
    
    # Rate limiting to prevent excessive API calls
    "rate_limiting": {
        "max_calls_per_minute": 10,
        "max_daily_calls": 1000
    },
    
    # Integration with existing systems
    "integration": {
        "respect_kill_switch": True,  # Always respect the paper-only mode
        "log_all_interactions": True,  # Maintain audit trail
        "require_confirmation": True,  # Human confirmation for critical decisions
        "fallback_to_deterministic": True  # Fall back to rules-based if API unavailable
    }
}

# Regime Detection Settings
REGIME_DETECTION_SETTINGS = {
    "required_iv_rank_threshold": 30.0,  # Our current regime gate
    "vix_upper_threshold": 30.0,  # Upper limit for safe trading
    "historical_lookback_days": 30,  # Days of historical data to analyze
    "confidence_threshold": 0.7,  # Minimum confidence for regime change detection
    "analysis_frequency_minutes": 60  # How often to perform regime analysis
}

# Risk Management Settings  
RISK_MANAGEMENT_SETTINGS = {
    "max_position_size_percentage": 2.0,  # Maximum 2% of account per position
    "max_daily_loss_threshold": 5.0,  # Stop trading if daily loss exceeds 5%
    "max_concurrent_positions": 5,  # Limit number of simultaneous positions
    "portfolio_correlation_limit": 0.7,  # Maximum correlation between positions
    "stress_test_scenarios": ["volatility_spike", "liquidity_crunch", "trend_reversal"]
}

# Validation Settings
TRADE_VALIDATION_SETTINGS = {
    "min_risk_reward_ratio": 1.5,  # Minimum 1.5:1 risk-reward
    "max_position_size": 1,  # Maximum position size (contracts/shares)
    "max_duration_days": 45,  # Maximum trade duration
    "validation_confidence_threshold": 0.8,  # Minimum confidence to proceed
    "paper_only_enforcement": True  # Ensure no live trading occurs during validation
}

def validate_config() -> Dict[str, Any]:
    """
    Validate the Gemini agent configuration
    
    Returns:
        Dictionary with validation results
    """
    results = {
        "api_key_set": bool(GEMINI_AGENT_CONFIG["api_key"]),
        "model_name_valid": GEMINI_AGENT_CONFIG["model_name"] in ["gemini-1.5-pro", "gemini-1.5-flash", "gemini-pro"],
        "temperature_valid": 0.0 <= GEMINI_AGENT_CONFIG["temperature"] <= 1.0,
        "safety_settings_valid": isinstance(GEMINI_AGENT_CONFIG["safety_settings"], dict),
        "integration_settings_valid": GEMINI_AGENT_CONFIG["integration"]["respect_kill_switch"] is True
    }
    
    results["all_valid"] = all(results.values())
    
    return results