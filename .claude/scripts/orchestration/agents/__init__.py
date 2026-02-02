"""
Swarm Agent Modules

This package contains specialized agents for the trading swarm:
- sentiment: Market sentiment analysis
- technicals: Technical indicator analysis
- risk: Risk assessment (Phil Town Rule #1)
- options_chain: Options chain analysis
- news: Breaking news and events
- cleanup: System maintenance
- research: Weekend learning
- backtest: Strategy backtesting
"""

from .base import BaseAgent
from .sentiment import SentimentAgent
from .technicals import TechnicalsAgent
from .risk import RiskAgent
from .options_chain import OptionsChainAgent
from .news import NewsAgent

__all__ = [
    "BaseAgent",
    "SentimentAgent",
    "TechnicalsAgent",
    "RiskAgent",
    "OptionsChainAgent",
    "NewsAgent",
]
