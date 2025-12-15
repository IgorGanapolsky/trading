"""News collectors package."""

from .alphavantage_collector import AlphaVantageCollector
from .berkshire_collector import BerkshireLettersCollector
from .bogleheads_collector import BogleheadsCollector
from .earnings_whisper_collector import EarningsWhisperCollector
from .finviz_collector import FinvizCollector
from .fred_collector import FREDCollector as FredCollector
from .mcmillan_options_collector import McMillanOptionsKnowledgeBase
from .options_flow_collector import OptionsFlowCollector
from .orchestrator import NewsOrchestrator, get_orchestrator
from .reddit_collector import RedditCollector
from .seekingalpha_collector import SeekingAlphaCollector
from .stocktwits_collector import StockTwitsCollector
from .tradingview_collector import TradingViewCollector
from .yahoo_collector import YahooFinanceCollector

__all__ = [
    "get_orchestrator",
    "NewsOrchestrator",
    "YahooFinanceCollector",
    "RedditCollector",
    "AlphaVantageCollector",
    "SeekingAlphaCollector",
    "BerkshireLettersCollector",
    "StockTwitsCollector",
    "BogleheadsCollector",
    "McMillanOptionsKnowledgeBase",
    "OptionsFlowCollector",
    "FinvizCollector",
    "TradingViewCollector",
    "EarningsWhisperCollector",
    "FREDCollector",
    "FredCollector",
]

# Backwards-compatible aliases
FREDCollector = FredCollector
