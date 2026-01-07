"""
Centralized constants for the trading system.

Technical Debt Fix - Jan 2026

This module consolidates hardcoded values that were scattered across 37+ files.
All timeout values, retry parameters, and other magic numbers should be defined here.

Usage:
    from src.utils.constants import TIMEOUT_DEFAULT, MAX_RETRIES
"""

from __future__ import annotations

# =============================================================================
# TIMEOUT CONSTANTS (was hardcoded in 15+ files)
# =============================================================================

# HTTP request timeouts (seconds)
TIMEOUT_DEFAULT = 10  # Default for most HTTP requests
TIMEOUT_SHORT = 5  # Quick health checks
TIMEOUT_MEDIUM = 15  # API calls with potential latency
TIMEOUT_LONG = 30  # Browser automation, large downloads
TIMEOUT_VERY_LONG = 60  # Heavy operations

# =============================================================================
# RETRY CONSTANTS (was inconsistent across files)
# =============================================================================

MAX_RETRIES_DEFAULT = 3
MAX_RETRIES_CRITICAL = 5  # For critical operations like order execution
INITIAL_BACKOFF_SECONDS = 1.0
BACKOFF_MULTIPLIER = 2.0  # Exponential backoff factor

# =============================================================================
# CACHE CONSTANTS (was duplicated in 4 sentiment classes)
# =============================================================================

CACHE_HOURS_DEFAULT = 24  # Default cache TTL
CACHE_HOURS_SHORT = 1  # For rapidly changing data
CACHE_HOURS_LONG = 168  # Weekly cache (7 * 24)

# =============================================================================
# API RATE LIMITS
# =============================================================================

# Alpaca
ALPACA_RATE_LIMIT_PER_MINUTE = 200
ALPACA_RATE_LIMIT_BURST = 50

# OpenRouter
OPENROUTER_RATE_LIMIT_PER_MINUTE = 60

# =============================================================================
# TRADING CONSTANTS
# =============================================================================

# Position sizing
MAX_POSITION_PCT = 10.0  # Max 10% of portfolio per position
MAX_TOTAL_EXPOSURE_PCT = 80.0  # Max 80% total market exposure
MIN_BUYING_POWER_RESERVE_PCT = 20.0  # Keep 20% cash reserve

# Risk management
MAX_DAILY_LOSS_PCT = 2.0  # Stop trading if down 2% in a day
MAX_DRAWDOWN_PCT = 10.0  # Max acceptable drawdown
DEFAULT_STOP_LOSS_PCT = 5.0  # Default stop loss percentage

# Phil Town Rule #1 specific
PHIL_TOWN_MOS_PCT = 50.0  # Margin of Safety - buy at 50% of intrinsic value
PHIL_TOWN_DELTA_MIN = 0.20  # Min delta for CSPs
PHIL_TOWN_DELTA_MAX = 0.30  # Max delta for CSPs
PHIL_TOWN_DTE_MIN = 30  # Min days to expiration
PHIL_TOWN_DTE_MAX = 45  # Max days to expiration

# =============================================================================
# MODEL CONSTANTS
# =============================================================================

# Budget (monthly)
LLM_MONTHLY_BUDGET_DEFAULT = 25.0  # $25/month target
LLM_DAILY_BUDGET_DEFAULT = 0.83  # $25/30 days

# Token estimates
ESTIMATED_TOKENS_SIMPLE = 1000
ESTIMATED_TOKENS_MEDIUM = 2000
ESTIMATED_TOKENS_COMPLEX = 4000

# =============================================================================
# MARKET HOURS (US Eastern)
# =============================================================================

MARKET_OPEN_HOUR = 9
MARKET_OPEN_MINUTE = 30
MARKET_CLOSE_HOUR = 16
MARKET_CLOSE_MINUTE = 0

# Pre/post market
PREMARKET_OPEN_HOUR = 4
AFTERMARKET_CLOSE_HOUR = 20

# =============================================================================
# DATA PROVIDER CONSTANTS
# =============================================================================

# Alpha Vantage
ALPHA_VANTAGE_RATE_LIMIT = 5  # 5 calls per minute (free tier)

# Yahoo Finance
YFINANCE_MAX_PERIOD = "5y"
YFINANCE_DEFAULT_INTERVAL = "1d"

# =============================================================================
# SENTINEL VALUES
# =============================================================================

NO_DATA_SENTINEL = -999.99
CONFIDENCE_THRESHOLD_LOW = 0.3
CONFIDENCE_THRESHOLD_MEDIUM = 0.5
CONFIDENCE_THRESHOLD_HIGH = 0.7
