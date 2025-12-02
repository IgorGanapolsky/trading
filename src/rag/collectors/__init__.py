"""News collectors package."""

from src.rag.collectors.alphavantage_collector import AlphaVantageCollector
from src.rag.collectors.berkshire_collector import BerkshireLettersCollector
from src.rag.collectors.bogleheads_collector import BogleheadsCollector
from src.rag.collectors.linkedin_collector import LinkedInCollector
from src.rag.collectors.mcmillan_options_collector import McMillanOptionsKnowledgeBase
from src.rag.collectors.orchestrator import NewsOrchestrator, get_orchestrator
from src.rag.collectors.reddit_collector import RedditCollector
from src.rag.collectors.seekingalpha_collector import SeekingAlphaCollector
from src.rag.collectors.stocktwits_collector import StockTwitsCollector
from src.rag.collectors.tiktok_collector import TikTokCollector
from src.rag.collectors.yahoo_collector import YahooFinanceCollector

__all__ = [
    "get_orchestrator",
    "NewsOrchestrator",
    "YahooFinanceCollector",
    "RedditCollector",
    "AlphaVantageCollector",
    "TikTokCollector",
    "LinkedInCollector",
    "SeekingAlphaCollector",
    "BerkshireLettersCollector",
    "StockTwitsCollector",
    "BogleheadsCollector",
    "McMillanOptionsKnowledgeBase",
]
