"""
Options Book Retriever - RAG Interface for Options Trading Knowledge

Provides high-level retrieval API for options book content:
1. Query options strategies by market conditions
2. Get McMillan's rules for specific setups
3. Cross-reference IV/Greeks with book knowledge
4. Support trading decisions with authoritative citations

Integrates with:
- OptionsBookCollector (PDF ingestion)
- McMillanOptionsKnowledgeBase (structured knowledge)
- IVAnalyzer (volatility metrics)
- Trading signal generation
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from src.rag.collectors.options_book_collector import get_options_book_collector
from src.rag.collectors.mcmillan_options_collector import McMillanOptionsKnowledgeBase
from src.rag.vector_db.chroma_client import get_rag_db
from src.rag.vector_db.embedder import get_embedder

logger = logging.getLogger(__name__)


class OptionsBookRetriever:
    """
    High-level retrieval interface for options book knowledge.

    Combines:
    - PDF book content (via OptionsBookCollector)
    - Structured knowledge (via McMillanOptionsKnowledgeBase)
    - Vector search (via ChromaDB)

    Usage:
        retriever = OptionsBookRetriever()

        # Get strategy guidance
        guidance = retriever.get_strategy_for_conditions(
            iv_rank=65,
            market_outlook="neutral",
            days_to_expiration=30
        )

        # Get expected move cross-check
        cross_check = retriever.cross_check_expected_move(
            ticker="SPY",
            sentiment_signal="overbought",
            current_iv=0.18,
            dte=7
        )

        # Search book for topic
        results = retriever.search_options_knowledge(
            "iron condor entry timing"
        )
    """

    # Collection name for options books in ChromaDB
    COLLECTION_NAME = "options_books"

    def __init__(self):
        """Initialize retriever with all knowledge sources."""
        self.book_collector = get_options_book_collector()
        self.mcmillan_kb = McMillanOptionsKnowledgeBase()
        self.db = get_rag_db()
        self.embedder = get_embedder()

        logger.info("Options Book Retriever initialized")

    def search_options_knowledge(
        self,
        query: str,
        top_k: int = 5,
        content_types: Optional[List[str]] = None,
        include_structured: bool = True
    ) -> Dict[str, Any]:
        """
        Search all options knowledge sources for query.

        Args:
            query: Natural language query
            top_k: Number of results per source
            content_types: Filter by content types (strategy, example, etc.)
            include_structured: Also search McMillan knowledge base

        Returns:
            Dict with results from all sources:
            {
                "query": str,
                "book_results": [...],
                "structured_results": [...],
                "combined_answer": str
            }
        """
        logger.info(f"Searching options knowledge for: '{query}'")

        results = {
            "query": query,
            "book_results": [],
            "structured_results": [],
            "combined_answer": "",
            "timestamp": datetime.now().isoformat()
        }

        # Search PDF books
        book_search = self.book_collector.search(
            query=query,
            top_k=top_k,
            content_types=content_types
        )
        results["book_results"] = book_search.get("results", [])

        # Search structured knowledge base
        if include_structured:
            kb_results = self.mcmillan_kb.search_knowledge(query)
            results["structured_results"] = kb_results

        # Combine into answer
        results["combined_answer"] = self._synthesize_answer(query, results)

        return results

    def get_strategy_for_conditions(
        self,
        iv_rank: float,
        market_outlook: str = "neutral",
        days_to_expiration: int = 30,
        risk_tolerance: str = "moderate"
    ) -> Dict[str, Any]:
        """
        Get recommended options strategy based on current conditions.

        Args:
            iv_rank: Current IV Rank (0-100)
            market_outlook: 'bullish', 'neutral', 'bearish'
            days_to_expiration: Target DTE
            risk_tolerance: 'conservative', 'moderate', 'aggressive'

        Returns:
            Strategy recommendation with reasoning and book references
        """
        logger.info(
            f"Getting strategy for: IV Rank={iv_rank}, Outlook={market_outlook}, "
            f"DTE={days_to_expiration}"
        )

        # Get IV-based recommendation from structured KB
        iv_rec = self.mcmillan_kb.get_iv_recommendation(
            iv_rank=iv_rank,
            iv_percentile=iv_rank  # Use same if percentile not available
        )

        # Map outlook to strategy categories
        outlook_strategies = {
            "bullish": ["long_call", "covered_call", "cash_secured_put", "bull_spread"],
            "neutral": ["iron_condor", "covered_call", "calendar_spread", "butterfly"],
            "bearish": ["long_put", "bear_spread", "protective_put"]
        }

        suitable_strategies = outlook_strategies.get(market_outlook.lower(), [])

        # Filter by IV recommendation
        if "SELL" in iv_rec["recommendation"]:
            # High IV - prefer short premium strategies
            preferred = ["iron_condor", "covered_call", "cash_secured_put", "credit_spread"]
        else:
            # Low IV - prefer long premium strategies
            preferred = ["long_call", "long_put", "debit_spread", "calendar_spread"]

        # Find overlap
        recommended = [s for s in suitable_strategies if s in preferred]
        if not recommended:
            recommended = suitable_strategies[:2]  # Fall back to outlook strategies

        # Get detailed rules for top strategy
        primary_strategy = recommended[0] if recommended else "covered_call"
        strategy_rules = self.mcmillan_kb.get_strategy_rules(primary_strategy)

        # Search books for additional context
        book_context = self.book_collector.search(
            query=f"{primary_strategy} setup {market_outlook}",
            top_k=3
        )

        return {
            "recommended_strategy": primary_strategy,
            "alternative_strategies": recommended[1:] if len(recommended) > 1 else [],
            "iv_recommendation": iv_rec["recommendation"],
            "iv_reasoning": iv_rec["reasoning"],
            "strategy_rules": strategy_rules,
            "book_references": book_context.get("results", []),
            "conditions": {
                "iv_rank": iv_rank,
                "market_outlook": market_outlook,
                "dte": days_to_expiration,
                "risk_tolerance": risk_tolerance
            }
        }

    def cross_check_expected_move(
        self,
        ticker: str,
        sentiment_signal: str,
        current_iv: float,
        dte: int,
        stock_price: float = None
    ) -> Dict[str, Any]:
        """
        Cross-check sentiment signal against McMillan's expected move calculation.

        This is the KEY integration for: "whenever sentiment says overbought,
        cross-check McMillan's expected move calc before slapping on a call."

        Args:
            ticker: Stock symbol
            sentiment_signal: 'overbought', 'oversold', 'bullish', 'bearish', 'neutral'
            current_iv: Current implied volatility (as decimal, e.g., 0.30)
            dte: Days to expiration
            stock_price: Current stock price (optional, can fetch if not provided)

        Returns:
            Cross-check result with:
            - Expected move range
            - Whether sentiment aligns with IV expectation
            - Recommended action
            - McMillan's guidance
        """
        logger.info(
            f"Cross-checking sentiment '{sentiment_signal}' for {ticker} "
            f"(IV={current_iv:.2%}, DTE={dte})"
        )

        # Use provided price or fetch (simplified - would use yfinance in production)
        if stock_price is None:
            stock_price = 100.0  # Placeholder - real implementation fetches live price
            logger.warning(f"Using placeholder price ${stock_price} for {ticker}")

        # Calculate expected move using McMillan's formula
        expected_move = self.mcmillan_kb.calculate_expected_move(
            stock_price=stock_price,
            implied_volatility=current_iv,
            days_to_expiration=dte,
            confidence_level=1.0  # 1 std dev (68% probability)
        )

        # Also calculate 2 std dev for more context
        expected_move_2std = self.mcmillan_kb.calculate_expected_move(
            stock_price=stock_price,
            implied_volatility=current_iv,
            days_to_expiration=dte,
            confidence_level=2.0  # 2 std dev (95% probability)
        )

        # Get IV recommendation
        iv_rank_approx = min(100, current_iv * 300)  # Rough approximation
        iv_rec = self.mcmillan_kb.get_iv_recommendation(
            iv_rank=iv_rank_approx,
            iv_percentile=iv_rank_approx
        )

        # Determine if sentiment aligns with expected move
        alignment_analysis = self._analyze_sentiment_alignment(
            sentiment_signal=sentiment_signal,
            expected_move=expected_move,
            iv_recommendation=iv_rec
        )

        # Get relevant book passages
        book_search = self.book_collector.search(
            query=f"expected move {sentiment_signal} IV {current_iv*100:.0f}%",
            top_k=3,
            content_types=["strategy", "rule"]
        )

        return {
            "ticker": ticker,
            "sentiment_signal": sentiment_signal,
            "expected_move": expected_move,
            "expected_move_2std": expected_move_2std,
            "iv_analysis": {
                "current_iv": current_iv,
                "iv_rank_approx": iv_rank_approx,
                "recommendation": iv_rec["recommendation"],
                "strategies": iv_rec["strategies"]
            },
            "alignment": alignment_analysis,
            "book_references": book_search.get("results", []),
            "final_recommendation": self._generate_recommendation(
                sentiment_signal,
                expected_move,
                iv_rec,
                alignment_analysis
            )
        }

    def get_20_delta_weekly_guidance(
        self,
        iv_rank: float,
        iv_percentile: float,
        stock_price: float = 100.0
    ) -> Dict[str, Any]:
        """
        Get guidance for auto-selling 20-delta weeklies when IV is 2σ cheap.

        Per user spec: "auto-selling 20-delta weeklies only when IV is
        two-standard-devs cheap"

        Args:
            iv_rank: Current IV Rank (0-100)
            iv_percentile: Current IV Percentile (0-100)
            stock_price: Current stock price

        Returns:
            Guidance on whether to auto-sell 20-delta weeklies
        """
        # McMillan's rule: IV < (mean - 2σ) = exceptionally cheap
        # This translates to roughly IV Rank < 5 or IV Percentile < 5
        is_2std_cheap = iv_rank < 5 or iv_percentile < 5

        # Get strategy rules for covered calls (20-delta is a covered call strike)
        strategy_rules = self.mcmillan_kb.get_strategy_rules("covered_call")

        # Position sizing for this setup
        position_sizing = self.mcmillan_kb.get_position_size(
            portfolio_value=10000,  # Example
            option_premium=0.50,    # Typical weekly premium for 20-delta
            max_risk_pct=0.02
        )

        return {
            "should_auto_sell": is_2std_cheap,
            "iv_rank": iv_rank,
            "iv_percentile": iv_percentile,
            "is_2std_cheap": is_2std_cheap,
            "reasoning": (
                "IV is 2 standard deviations below mean - exceptionally cheap. "
                "McMillan suggests this is optimal for selling premium via 20-delta weeklies."
                if is_2std_cheap else
                "IV is not at 2σ cheap level. Wait for better entry or use standard criteria."
            ),
            "strategy_rules": strategy_rules,
            "position_sizing": position_sizing,
            "delta_target": 0.20,
            "dte_target": 7,  # Weekly
            "reference": "McMillan's Options as a Strategic Investment, Ch. 22: Volatility"
        }

    def get_collar_or_butterfly_guidance(
        self,
        position_type: str,
        iv_rank: float,
        stock_price: float,
        shares_owned: int = 100
    ) -> Dict[str, Any]:
        """
        Quick retrieval for collar or butterfly setups.

        Per user spec: "short, cheat-sheet style, perfect for quick retrieval
        when the system wants a collar or butterfly"

        Args:
            position_type: 'collar' or 'butterfly'
            iv_rank: Current IV Rank
            stock_price: Current stock price
            shares_owned: Shares owned (for collar)

        Returns:
            Cheat-sheet style guidance
        """
        logger.info(f"Getting {position_type} guidance (IV Rank: {iv_rank})")

        if position_type.lower() == "collar":
            return {
                "strategy": "Collar (Protective Put + Covered Call)",
                "when_to_use": "Own shares, want downside protection while generating income",
                "setup": {
                    "step_1": f"Own {shares_owned} shares",
                    "step_2": "Buy OTM put (10-15 delta) for protection",
                    "step_3": "Sell OTM call (15-30 delta) to offset put cost",
                    "net_cost": "Usually zero or small credit"
                },
                "optimal_iv": "IV Rank 30-50 (balanced put cost vs call premium)",
                "current_iv_rank": iv_rank,
                "iv_assessment": (
                    "Good entry - balanced costs" if 30 <= iv_rank <= 50 else
                    "Put may be expensive - consider narrower width" if iv_rank > 50 else
                    "Put is cheap - wider protection available"
                ),
                "quick_rules": [
                    "Put strike: 8-10% below current price",
                    "Call strike: 5-10% above current price",
                    "Same expiration for both",
                    "DTE: 30-60 days typical",
                    "Roll before expiration, not at"
                ],
                "risk_profile": "Limited downside (to put strike), capped upside (at call strike)",
                "mcmillan_reference": "Chapter 19: Put and Call Combination Strategies"
            }

        elif position_type.lower() == "butterfly":
            return {
                "strategy": "Butterfly Spread (Long Call Butterfly or Put Butterfly)",
                "when_to_use": "Expect stock to stay near current price at expiration",
                "setup": {
                    "step_1": "Buy 1 ITM call (lower strike)",
                    "step_2": "Sell 2 ATM calls (middle strike)",
                    "step_3": "Buy 1 OTM call (higher strike)",
                    "strikes": "Equal distance between strikes"
                },
                "optimal_iv": "IV Rank > 30 (more premium to collect)",
                "current_iv_rank": iv_rank,
                "iv_assessment": (
                    "Good entry - elevated premiums" if iv_rank > 30 else
                    "Low IV - butterfly may be too cheap"
                ),
                "quick_rules": [
                    "Wings: 5-10 points apart typically",
                    "Max profit: At middle strike at expiration",
                    "Max loss: Net debit paid",
                    "DTE: 30-45 days optimal",
                    "Close at 50% profit or 21 DTE"
                ],
                "risk_profile": "Limited risk (net debit), limited reward (width - debit)",
                "example": {
                    "stock_price": stock_price,
                    "lower_strike": stock_price - 5,
                    "middle_strike": stock_price,
                    "upper_strike": stock_price + 5,
                    "typical_cost": "$1.50-2.50 for $5 wide",
                    "max_profit": "$5 - cost = $2.50-3.50"
                },
                "mcmillan_reference": "Chapter 10: Butterfly Spreads"
            }

        else:
            return {
                "error": f"Unknown position type: {position_type}",
                "supported": ["collar", "butterfly"]
            }

    def _analyze_sentiment_alignment(
        self,
        sentiment_signal: str,
        expected_move: Dict,
        iv_recommendation: Dict
    ) -> Dict[str, Any]:
        """Analyze if sentiment aligns with expected move."""

        move_pct = expected_move["move_percentage"]

        # Define what "significant move" means per McMillan
        is_large_expected_move = move_pct > 5  # >5% expected move is significant

        # Sentiment implies direction; expected move implies magnitude
        if sentiment_signal in ["overbought", "bearish"]:
            # Expecting downside
            if is_large_expected_move:
                alignment = "ALIGNED"
                note = "High IV supports potential for significant move in expected direction"
            else:
                alignment = "CAUTION"
                note = "Sentiment is bearish but expected move is small - may be overpriced put"

        elif sentiment_signal in ["oversold", "bullish"]:
            # Expecting upside
            if is_large_expected_move:
                alignment = "ALIGNED"
                note = "High IV supports potential for significant move in expected direction"
            else:
                alignment = "CAUTION"
                note = "Sentiment is bullish but expected move is small - may be overpriced call"

        else:  # neutral
            if is_large_expected_move:
                alignment = "CAUTION"
                note = "Neutral sentiment but high expected move - consider straddle/strangle"
            else:
                alignment = "ALIGNED"
                note = "Neutral sentiment and low expected move - good for iron condor"

        return {
            "status": alignment,
            "note": note,
            "expected_move_pct": move_pct,
            "is_significant_move": is_large_expected_move,
            "sentiment_direction": sentiment_signal
        }

    def _generate_recommendation(
        self,
        sentiment_signal: str,
        expected_move: Dict,
        iv_recommendation: Dict,
        alignment: Dict
    ) -> str:
        """Generate final recommendation based on all inputs."""

        if alignment["status"] == "ALIGNED":
            if sentiment_signal in ["overbought", "bearish"]:
                return (
                    f"PROCEED: Buy protective put or bearish spread. "
                    f"Expected move: ±{expected_move['move_percentage']:.1f}%. "
                    f"Target strike: ${expected_move['lower_bound']:.2f} (1σ) or "
                    f"${expected_move['lower_bound'] - expected_move['expected_move']:.2f} (2σ)."
                )
            elif sentiment_signal in ["oversold", "bullish"]:
                return (
                    f"PROCEED: Buy call or bullish spread. "
                    f"Expected move: ±{expected_move['move_percentage']:.1f}%. "
                    f"Target strike: ${expected_move['upper_bound']:.2f} (1σ)."
                )
            else:  # neutral
                return (
                    f"PROCEED: Iron condor or butterfly. "
                    f"Expected range: ${expected_move['lower_bound']:.2f} - "
                    f"${expected_move['upper_bound']:.2f} (68% probability)."
                )
        else:  # CAUTION
            return (
                f"WAIT: Sentiment ({sentiment_signal}) may not be supported by IV. "
                f"Expected move only ±{expected_move['move_percentage']:.1f}%. "
                f"Consider waiting for better setup or use defined-risk spread."
            )

    def _synthesize_answer(self, query: str, results: Dict) -> str:
        """Synthesize answer from all results."""
        parts = []

        if results["structured_results"]:
            for result in results["structured_results"][:2]:
                parts.append(f"[{result['type'].upper()}] {result['name']}")

        if results["book_results"]:
            for result in results["book_results"][:2]:
                chapter = result.get("chapter", "Unknown")
                excerpt = result.get("excerpt", "")[:200]
                parts.append(f"[Book: {chapter}] {excerpt}...")

        if parts:
            return "\n\n".join(parts)
        return "No relevant information found in options knowledge base."

    def ingest_options_books_to_vector_store(self) -> Dict[str, Any]:
        """
        Ingest all options book chunks into the vector store for semantic search.

        This enables semantic search across book content.
        """
        logger.info("Ingesting options books to vector store...")

        chunks = self.book_collector.get_chunks_for_rag()

        if not chunks:
            return {
                "status": "no_chunks",
                "message": "No book chunks to ingest. Use book_collector.ingest_pdf() first."
            }

        # Prepare for ChromaDB
        documents = []
        metadatas = []
        ids = []

        for chunk in chunks:
            documents.append(chunk["content"])
            metadatas.append(chunk["metadata"])
            ids.append(chunk["id"])

        # Add to database
        result = self.db.add_documents(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )

        return {
            "status": result["status"],
            "chunks_ingested": len(chunks),
            "message": result.get("message", "")
        }


# Singleton instance
_retriever_instance = None


def get_options_book_retriever() -> OptionsBookRetriever:
    """Get or create OptionsBookRetriever instance (singleton)."""
    global _retriever_instance

    if _retriever_instance is None:
        _retriever_instance = OptionsBookRetriever()

    return _retriever_instance


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    retriever = OptionsBookRetriever()

    # Example: Get strategy for conditions
    print("\n=== Strategy for Current Conditions ===")
    strategy = retriever.get_strategy_for_conditions(
        iv_rank=65,
        market_outlook="neutral",
        days_to_expiration=30
    )
    print(f"Recommended: {strategy['recommended_strategy']}")
    print(f"IV Reasoning: {strategy['iv_reasoning']}")

    # Example: Cross-check expected move
    print("\n=== Expected Move Cross-Check ===")
    cross_check = retriever.cross_check_expected_move(
        ticker="SPY",
        sentiment_signal="overbought",
        current_iv=0.18,
        dte=7,
        stock_price=450.0
    )
    print(f"Expected Move: ±{cross_check['expected_move']['move_percentage']:.1f}%")
    print(f"Alignment: {cross_check['alignment']['status']}")
    print(f"Recommendation: {cross_check['final_recommendation']}")

    # Example: Collar guidance
    print("\n=== Collar Cheat Sheet ===")
    collar = retriever.get_collar_or_butterfly_guidance(
        position_type="collar",
        iv_rank=45,
        stock_price=150.0
    )
    print(f"When to use: {collar['when_to_use']}")
    print(f"IV Assessment: {collar['iv_assessment']}")
