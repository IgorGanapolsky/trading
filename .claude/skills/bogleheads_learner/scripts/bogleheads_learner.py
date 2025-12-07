#!/usr/bin/env python3
"""
Bogleheads Forum Learner

Continuously monitors and learns from Bogleheads.org forum to extract
investing wisdom and integrate insights into RL trading engine.
"""

import json
import logging
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    import requests
    from bs4 import BeautifulSoup

    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    requests = None
    BeautifulSoup = None

try:
    from anthropic import Anthropic
except ImportError:
    print("⚠️  Missing anthropic: pip install anthropic")
    Anthropic = None

try:
    from langchain.embeddings import OpenAIEmbeddings
    from langchain.text_splitter import RecursiveCharacterTextSplitter
    from langchain.vectorstores import FAISS
except ImportError:
    print("⚠️  Missing langchain: pip install langchain faiss-cpu")
    OpenAIEmbeddings = None
    FAISS = None

logger = logging.getLogger(__name__)


@dataclass
class ForumPost:
    """Forum post data structure"""

    title: str
    content: str
    author: str
    replies: int
    views: int
    date: str
    url: str
    topic: str


@dataclass
class InvestingInsight:
    """Extracted investing insight"""

    insight_type: str  # market_regime, risk_management, strategy, sentiment
    insight_text: str
    confidence: float
    relevance_score: float
    actionable: bool
    source_post: str
    extracted_at: str


class BogleheadsLearner:
    """
    Bogleheads Forum Learner

    Monitors forum, extracts insights, stores in RAG, integrates with RL.
    """

    def __init__(self):
        self.forum_url = "https://www.bogleheads.org/forum"
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
        self.openai_api_key = os.getenv("OPENAI_API_KEY")

        self.anthropic_client = None
        if self.anthropic_api_key and Anthropic:
            self.anthropic_client = Anthropic(api_key=self.anthropic_api_key)

        # RAG storage
        self.rag_dir = project_root / "data" / "rag" / "bogleheads"
        self.rag_dir.mkdir(parents=True, exist_ok=True)

        self.vectorstore = None
        self._initialize_rag()

        # Rate limiting
        self.last_request_time = 0
        self.min_request_interval = 2.0  # 2 seconds between requests

    def _initialize_rag(self):
        """Initialize RAG vector store"""
        if not OpenAIEmbeddings or not FAISS:
            logger.warning("RAG not available - insights will not be stored")
            return

        try:
            if self.openai_api_key:
                embeddings = OpenAIEmbeddings(openai_api_key=self.openai_api_key)
                rag_path = self.rag_dir / "vectorstore"

                if rag_path.exists():
                    self.vectorstore = FAISS.load_local(str(rag_path), embeddings)
                    logger.info("✅ Loaded existing Bogleheads RAG store")
                else:
                    # Create empty vectorstore
                    from langchain.docstore.document import Document

                    self.vectorstore = FAISS.from_documents(
                        [Document(page_content="Initial Bogleheads insights")],
                        embeddings,
                    )
                    logger.info("✅ Created new Bogleheads RAG store")
        except Exception as e:
            logger.warning(f"⚠️  Could not initialize RAG: {e}")

    def _rate_limit(self):
        """Rate limit requests to forum"""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_request_interval:
            time.sleep(self.min_request_interval - elapsed)
        self.last_request_time = time.time()

    def monitor_bogleheads_forum(
        self,
        topics: list[str] | None = None,
        keywords: list[str] | None = None,
        max_posts: int = 50,
        min_replies: int = 5,
    ) -> dict[str, Any]:
        """
        Monitor Bogleheads forum for new discussions.

        Args:
            topics: Topics to monitor
            keywords: Keywords to filter for
            max_posts: Maximum posts to analyze
            min_replies: Minimum replies required

        Returns:
            Dict with monitoring results
        """
        if not REQUESTS_AVAILABLE:
            return {
                "success": False,
                "error": "Missing dependencies: requests, beautifulsoup4",
            }

        topics = topics or [
            "Personal Investments",
            "Investing - Theory, News & General",
        ]
        keywords = keywords or [
            "market timing",
            "rebalancing",
            "risk",
            "volatility",
            "bear market",
            "bull market",
            "diversification",
            "allocation",
        ]

        logger.info(f"🔍 Monitoring Bogleheads forum for topics: {topics}")

        posts_analyzed = 0
        insights_extracted = 0

        try:
            # Check robots.txt first
            robots_url = f"{self.forum_url}/robots.txt"
            try:
                self._rate_limit()
                robots_resp = requests.get(robots_url, timeout=5)
                if robots_resp.status_code == 200:
                    logger.info("✅ Checked robots.txt")
            except:
                logger.debug("Could not check robots.txt")

            # Try RSS feed first (cleaner, preferred)
            rss_urls = [
                f"{self.forum_url}/feed.php",
                f"{self.forum_url}/rss.php",
            ]

            posts_found = []

            # Try RSS feeds
            for rss_url in rss_urls:
                try:
                    self._rate_limit()
                    rss_resp = requests.get(
                        rss_url, headers={"User-Agent": "TradingBot/1.0"}, timeout=10
                    )
                    if rss_resp.status_code == 200:
                        # Parse RSS
                        soup = BeautifulSoup(rss_resp.content, "xml")
                        items = soup.find_all("item")

                        for item in items[:max_posts]:
                            title = item.find("title")
                            description = item.find("description")
                            link = item.find("link")

                            if title and description:
                                title_text = title.get_text()
                                desc_text = description.get_text()

                                # Check if matches keywords
                                content_lower = (title_text + " " + desc_text).lower()
                                if any(kw.lower() in content_lower for kw in keywords):
                                    posts_found.append(
                                        {
                                            "title": title_text,
                                            "content": desc_text[:1000],  # Limit content
                                            "url": link.get_text() if link else "",
                                            "date": (
                                                item.find("pubDate").get_text()
                                                if item.find("pubDate")
                                                else ""
                                            ),
                                        }
                                    )

                        if posts_found:
                            logger.info(f"✅ Found {len(posts_found)} posts via RSS")
                            break
                except Exception as e:
                    logger.debug(f"RSS feed {rss_url} failed: {e}")
                    continue

            # Fallback: HTML scraping (if RSS not available)
            if not posts_found:
                try:
                    self._rate_limit()
                    resp = requests.get(
                        self.forum_url,
                        headers={"User-Agent": "TradingBot/1.0"},
                        timeout=10,
                    )
                    resp.raise_for_status()

                    soup = BeautifulSoup(resp.text, "html.parser")

                    # Find topic links (phpBB structure)
                    topic_links = soup.find_all("a", class_=["topictitle", "forumtitle"], href=True)

                    for link in topic_links[:max_posts]:
                        title = link.get_text(strip=True)
                        href = link.get("href", "")

                        # Check if matches keywords
                        if any(kw.lower() in title.lower() for kw in keywords):
                            # Get full post content
                            try:
                                self._rate_limit()
                                post_url = (
                                    href if href.startswith("http") else f"{self.forum_url}/{href}"
                                )
                                post_resp = requests.get(
                                    post_url,
                                    headers={"User-Agent": "TradingBot/1.0"},
                                    timeout=5,
                                )

                                if post_resp.status_code == 200:
                                    post_soup = BeautifulSoup(post_resp.text, "html.parser")
                                    content_div = post_soup.find("div", class_="content")
                                    content = (
                                        content_div.get_text(strip=True) if content_div else ""
                                    )

                                    if len(content) > 100:  # Only if substantial content
                                        posts_found.append(
                                            {
                                                "title": title,
                                                "content": content[:1000],
                                                "url": post_url,
                                                "date": "",
                                            }
                                        )
                            except:
                                continue  # Skip if can't fetch post

                            if len(posts_found) >= max_posts:
                                break

                    if posts_found:
                        logger.info(f"✅ Found {len(posts_found)} posts via HTML scraping")
                except Exception as e:
                    logger.warning(f"HTML scraping failed: {e}")

            posts_analyzed = len(posts_found)

            # Extract insights from posts
            if posts_found:
                all_insights = []
                for post in posts_found:
                    insights = self.extract_investing_insights(
                        post["content"],
                        {
                            "title": post["title"],
                            "url": post["url"],
                            "date": post.get("date", ""),
                            "replies": 0,  # Would need to parse from HTML
                        },
                    )
                    all_insights.extend(insights)

                insights_extracted = len(all_insights)

                # Store insights in RAG
                if all_insights:
                    store_result = self.store_insights_to_rag(all_insights)
                    logger.info(f"✅ Stored {store_result.get('stored_count', 0)} insights to RAG")

            return {
                "success": True,
                "posts_analyzed": posts_analyzed,
                "insights_extracted": insights_extracted,
                "topics_found": [p["title"] for p in posts_found[:10]],
                "posts": posts_found[:5],  # Return sample posts
            }

        except Exception as e:
            logger.error(f"Error monitoring forum: {e}")
            return {"success": False, "error": str(e)}

    def extract_investing_insights(
        self, post_content: str, post_metadata: dict[str, Any]
    ) -> list[InvestingInsight]:
        """
        Extract investing insights from forum post using Claude.

        Args:
            post_content: Forum post content
            post_metadata: Post metadata

        Returns:
            List of InvestingInsight objects
        """
        if not self.anthropic_client:
            logger.warning("Anthropic client not available")
            return []

        prompt = f"""Analyze this Bogleheads forum post and extract investing insights.

POST TITLE: {post_metadata.get("title", "N/A")}
AUTHOR: {post_metadata.get("author", "N/A")}
REPLIES: {post_metadata.get("replies", 0)}
DATE: {post_metadata.get("date", "N/A")}

POST CONTENT:
{post_content[:2000]}  # Limit to 2000 chars

Extract insights that could inform trading decisions. Look for:
1. Market regime discussions (bull/bear/choppy)
2. Risk management wisdom
3. Strategy recommendations
4. Sentiment indicators
5. Contrarian signals

Return JSON array of insights:
[
  {{
    "insight_type": "market_regime|risk_management|strategy|sentiment",
    "insight_text": "Extracted insight",
    "confidence": 0.0-1.0,
    "relevance_score": 0.0-1.0,
    "actionable": true/false
  }}
]
"""

        try:
            response = self.anthropic_client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}],
            )

            # Parse JSON from response
            content = response.content[0].text
            json_match = re.search(r"\[.*\]", content, re.DOTALL)

            if json_match:
                insights_data = json.loads(json_match.group())
                insights = []

                for insight_data in insights_data:
                    insights.append(
                        InvestingInsight(
                            insight_type=insight_data.get("insight_type", "unknown"),
                            insight_text=insight_data.get("insight_text", ""),
                            confidence=insight_data.get("confidence", 0.5),
                            relevance_score=insight_data.get("relevance_score", 0.5),
                            actionable=insight_data.get("actionable", False),
                            source_post=post_metadata.get("url", ""),
                            extracted_at=datetime.now().isoformat(),
                        )
                    )

                return insights
            else:
                logger.warning("Could not parse insights from Claude response")
                return []

        except Exception as e:
            logger.error(f"Error extracting insights: {e}")
            return []

    def store_insights_to_rag(
        self,
        insights: list[InvestingInsight],
        embedding_model: str = "text-embedding-3-small",
    ) -> dict[str, Any]:
        """
        Store insights in RAG vector store.

        Args:
            insights: List of insights to store
            embedding_model: Embedding model to use

        Returns:
            Dict with storage results
        """
        if not self.vectorstore:
            logger.warning("RAG vectorstore not available")
            return {"stored_count": 0, "error": "RAG not initialized"}

        try:
            from langchain.docstore.document import Document

            documents = []
            for insight in insights:
                doc_content = f"""
Type: {insight.insight_type}
Insight: {insight.insight_text}
Confidence: {insight.confidence}
Relevance: {insight.relevance_score}
Actionable: {insight.actionable}
Source: {insight.source_post}
Extracted: {insight.extracted_at}
"""
                documents.append(
                    Document(
                        page_content=doc_content,
                        metadata={
                            "type": insight.insight_type,
                            "confidence": insight.confidence,
                            "relevance": insight.relevance_score,
                            "actionable": insight.actionable,
                            "source": insight.source_post,
                            "extracted_at": insight.extracted_at,
                        },
                    )
                )

            # Add to vectorstore
            self.vectorstore.add_documents(documents)

            # Save vectorstore
            rag_path = self.rag_dir / "vectorstore"
            self.vectorstore.save_local(str(rag_path))

            logger.info(f"✅ Stored {len(insights)} insights to RAG")

            return {"stored_count": len(insights), "rag_path": str(rag_path)}

        except Exception as e:
            logger.error(f"Error storing insights: {e}")
            return {"stored_count": 0, "error": str(e)}

    def get_bogleheads_signal(
        self, symbol: str, market_context: dict[str, Any], query: str | None = None
    ) -> dict[str, Any]:
        """
        Get trading signal based on Bogleheads forum wisdom.

        Args:
            symbol: Symbol to analyze
            market_context: Current market context
            query: Specific query

        Returns:
            Dict with signal and reasoning
        """
        if not self.vectorstore:
            return {
                "signal": "HOLD",
                "confidence": 0.0,
                "reasoning": "RAG not available",
                "insights_used": [],
            }

        try:
            # Build query
            if not query:
                query = f"What do Bogleheads recommend for {symbol} given: {market_context}"

            # Search RAG
            docs = self.vectorstore.similarity_search(query, k=5)

            if not docs:
                return {
                    "signal": "HOLD",
                    "confidence": 0.0,
                    "reasoning": "No relevant Bogleheads insights found",
                    "insights_used": [],
                }

            # Analyze insights with Claude
            insights_text = "\n\n".join([doc.page_content for doc in docs])

            if self.anthropic_client:
                prompt = f"""Based on these Bogleheads forum insights, provide a trading signal for {symbol}.

MARKET CONTEXT:
{json.dumps(market_context, indent=2)}

BOGLEHEADS INSIGHTS:
{insights_text}

Provide:
1. Signal: BUY, SELL, or HOLD
2. Confidence: 0.0-1.0
3. Reasoning: Why this signal based on Bogleheads wisdom
4. Key insights: Which insights informed this decision

Return JSON:
{{
    "signal": "BUY|SELL|HOLD",
    "confidence": 0.0-1.0,
    "reasoning": "...",
    "key_insights": ["insight1", "insight2"]
}}
"""

                response = self.anthropic_client.messages.create(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=1000,
                    messages=[{"role": "user", "content": prompt}],
                )

                content = response.content[0].text
                json_match = re.search(r"\{.*\}", content, re.DOTALL)

                if json_match:
                    signal_data = json.loads(json_match.group())
                    return {
                        "signal": signal_data.get("signal", "HOLD"),
                        "confidence": signal_data.get("confidence", 0.5),
                        "reasoning": signal_data.get("reasoning", ""),
                        "insights_used": signal_data.get("key_insights", []),
                    }

            # Fallback: Simple analysis
            return {
                "signal": "HOLD",
                "confidence": 0.5,
                "reasoning": f"Found {len(docs)} relevant insights, but analysis unavailable",
                "insights_used": [doc.page_content[:100] for doc in docs],
            }

        except Exception as e:
            logger.error(f"Error getting Bogleheads signal: {e}")
            return {
                "signal": "HOLD",
                "confidence": 0.0,
                "reasoning": f"Error: {str(e)}",
                "insights_used": [],
            }

    def analyze_market_regime_bogleheads(self, timeframe: str = "30d") -> dict[str, Any]:
        """
        Analyze market regime based on Bogleheads discussions.

        Args:
            timeframe: Timeframe to analyze

        Returns:
            Dict with regime analysis
        """
        if not self.vectorstore:
            return {
                "regime": "unknown",
                "sentiment": "neutral",
                "key_themes": [],
                "risk_level": "medium",
            }

        try:
            # Search for recent regime discussions
            query = f"market regime bull bear choppy volatility {timeframe}"
            docs = self.vectorstore.similarity_search(query, k=10)

            if not docs:
                return {
                    "regime": "unknown",
                    "sentiment": "neutral",
                    "key_themes": [],
                    "risk_level": "medium",
                }

            # Analyze with Claude
            if self.anthropic_client:
                insights_text = "\n\n".join([doc.page_content for doc in docs])

                prompt = f"""Analyze these Bogleheads forum discussions to determine current market regime.

INSIGHTS:
{insights_text}

Determine:
1. Market regime: bull, bear, choppy, uncertain
2. Overall sentiment: bullish, bearish, neutral
3. Key themes: List 3-5 main themes discussed
4. Risk level: low, medium, high

Return JSON:
{{
    "regime": "bull|bear|choppy|uncertain",
    "sentiment": "bullish|bearish|neutral",
    "key_themes": ["theme1", "theme2"],
    "risk_level": "low|medium|high"
}}
"""

                response = self.anthropic_client.messages.create(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=1000,
                    messages=[{"role": "user", "content": prompt}],
                )

                content = response.content[0].text
                json_match = re.search(r"\{.*\}", content, re.DOTALL)

                if json_match:
                    return json.loads(json_match.group())

            # Fallback
            return {
                "regime": "uncertain",
                "sentiment": "neutral",
                "key_themes": ["Found insights but analysis unavailable"],
                "risk_level": "medium",
            }

        except Exception as e:
            logger.error(f"Error analyzing regime: {e}")
            return {
                "regime": "unknown",
                "sentiment": "neutral",
                "key_themes": [],
                "risk_level": "medium",
            }


def main():
    """Test Bogleheads learner"""
    learner = BogleheadsLearner()

    print("🔍 Testing Bogleheads Forum Learner...")

    # Test monitoring
    result = learner.monitor_bogleheads_forum(max_posts=10)
    print(f"Monitoring result: {result}")

    # Test signal generation
    signal = learner.get_bogleheads_signal(
        symbol="SPY", market_context={"volatility": "high", "trend": "bullish"}
    )
    print(f"Signal: {signal}")

    # Test regime analysis
    regime = learner.analyze_market_regime_bogleheads()
    print(f"Regime: {regime}")


if __name__ == "__main__":
    main()
# ruff: noqa: UP045
