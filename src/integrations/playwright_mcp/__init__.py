"""Playwright MCP Integration for browser-based sentiment scraping and trade verification.

This module provides:
- PlaywrightMCPClient: Core browser automation using accessibility snapshots
- SentimentScraper: Dynamic scraping from Reddit, YouTube, Bogleheads
- TradeVerifier: Screenshot-based trade verification for audit trails

Usage:
    from src.integrations.playwright_mcp import PlaywrightMCPClient, SentimentScraper, TradeVerifier

    # For sentiment scraping
    scraper = SentimentScraper()
    sentiment = await scraper.scrape_reddit("wallstreetbets", ["SPY", "QQQ"])

    # For trade verification
    verifier = TradeVerifier()
    await verifier.capture_positions_screenshot()
"""

from src.integrations.playwright_mcp.client import PlaywrightMCPClient
from src.integrations.playwright_mcp.scraper import SentimentScraper
from src.integrations.playwright_mcp.verifier import TradeVerifier

__all__ = ["PlaywrightMCPClient", "SentimentScraper", "TradeVerifier"]
