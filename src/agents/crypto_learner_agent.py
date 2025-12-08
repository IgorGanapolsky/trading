"""
Crypto Learner Agent

Specialized agent that uses RAG to learn profitable crypto strategies
and optimize the existing CryptoStrategy.
"""

import logging
from typing import Any

from src.agents.base_agent import BaseAgent
from src.rag.vector_db.retriever import get_retriever

logger = logging.getLogger(__name__)


class CryptoLearnerAgent(BaseAgent):
    """
    Agent dedicated to learning crypto alpha from RAG.
    """

    def __init__(self):
        super().__init__(name="CryptoLearner", role="Crypto Strategy Optimizer")
        try:
            self.retriever = get_retriever()
        except Exception:
            self.retriever = None
            logger.warning("RAG Retriever not available - learning disabled")

    def research_strategy(self, topic: str = "profitable crypto trading strategies") -> str:
        """
        Query RAG for crypto alpha.
        """
        if not self.retriever:
            return "RAG unavailable."

        logger.info(f"Researching: {topic}")
        results = self.retriever.retrieve(topic, n_results=5, use_hyde=True)

        knowledge = []
        if results.get("documents"):
            knowledge = results["documents"][0]

        summary = "\n\n".join(knowledge)
        return summary

    def optimize_parameters(self, current_params: dict[str, Any]) -> dict[str, Any]:
        """
        Suggest parameter optimizations based on learned alpha.
        (Placeholder for future logic connecting RAG insights to config)
        """
        # Example: If RAG says "RSI 30 is too low in bull runs", adjust to 40
        research = self.research_strategy("RSI settings for crypto bull market")

        # Simple rule-based adjustment based on keywords (mock logic)
        new_params = current_params.copy()
        if "trend following" in research.lower():
            new_params["rsi_buy_threshold"] = 45  # looser entry

        return new_params
