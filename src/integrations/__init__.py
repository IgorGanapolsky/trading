"""Integrations module - external integrations for the trading system."""

from src.integrations.playwright_mcp import SentimentResult, SentimentScraper, TradeVerifier

__all__ = ["SentimentResult", "SentimentScraper", "TradeVerifier"]
