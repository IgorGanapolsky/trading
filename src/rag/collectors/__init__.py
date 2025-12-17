"""News collectors package.

Collectors may have optional dependencies (bs4, etc).
Import errors are caught to allow partial functionality.
"""

import logging

logger = logging.getLogger(__name__)

# Core collectors (no optional deps)
from .fred_collector import FREDCollector as FredCollector
from .orchestrator import NewsOrchestrator, get_orchestrator

# Optional collectors - may require bs4 or other packages
_optional_collectors = {}

try:
    from .alphavantage_collector import AlphaVantageCollector
    _optional_collectors["AlphaVantageCollector"] = AlphaVantageCollector
except ImportError as e:
    logger.debug(f"AlphaVantageCollector unavailable: {e}")

try:
    from .berkshire_collector import BerkshireLettersCollector
    _optional_collectors["BerkshireLettersCollector"] = BerkshireLettersCollector
except ImportError as e:
    logger.debug(f"BerkshireLettersCollector unavailable: {e}")

try:
    from .bogleheads_collector import BogleheadsCollector
    _optional_collectors["BogleheadsCollector"] = BogleheadsCollector
except ImportError as e:
    logger.debug(f"BogleheadsCollector unavailable: {e}")

try:
    from .earnings_whisper_collector import EarningsWhisperCollector
    _optional_collectors["EarningsWhisperCollector"] = EarningsWhisperCollector
except ImportError as e:
    logger.debug(f"EarningsWhisperCollector unavailable: {e}")

try:
    from .finviz_collector import FinvizCollector
    _optional_collectors["FinvizCollector"] = FinvizCollector
except ImportError as e:
    logger.debug(f"FinvizCollector unavailable: {e}")

try:
    from .mcmillan_options_collector import McMillanOptionsKnowledgeBase
    _optional_collectors["McMillanOptionsKnowledgeBase"] = McMillanOptionsKnowledgeBase
except ImportError as e:
    logger.debug(f"McMillanOptionsKnowledgeBase unavailable: {e}")

try:
    from .options_flow_collector import OptionsFlowCollector
    _optional_collectors["OptionsFlowCollector"] = OptionsFlowCollector
except ImportError as e:
    logger.debug(f"OptionsFlowCollector unavailable: {e}")

try:
    from .reddit_collector import RedditCollector
    _optional_collectors["RedditCollector"] = RedditCollector
except ImportError as e:
    logger.debug(f"RedditCollector unavailable: {e}")

try:
    from .seekingalpha_collector import SeekingAlphaCollector
    _optional_collectors["SeekingAlphaCollector"] = SeekingAlphaCollector
except ImportError as e:
    logger.debug(f"SeekingAlphaCollector unavailable: {e}")

try:
    from .stocktwits_collector import StockTwitsCollector
    _optional_collectors["StockTwitsCollector"] = StockTwitsCollector
except ImportError as e:
    logger.debug(f"StockTwitsCollector unavailable: {e}")

try:
    from .tradingview_collector import TradingViewCollector
    _optional_collectors["TradingViewCollector"] = TradingViewCollector
except ImportError as e:
    logger.debug(f"TradingViewCollector unavailable: {e}")

try:
    from .yahoo_collector import YahooFinanceCollector
    _optional_collectors["YahooFinanceCollector"] = YahooFinanceCollector
except ImportError as e:
    logger.debug(f"YahooFinanceCollector unavailable: {e}")

# Export available collectors to module namespace
locals().update(_optional_collectors)

__all__ = [
    "get_orchestrator",
    "NewsOrchestrator",
    "FREDCollector",
    "FredCollector",
] + list(_optional_collectors.keys())

# Backwards-compatible aliases
FREDCollector = FredCollector
