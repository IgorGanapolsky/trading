"""
Gemini Deep Research Integration for Trading
Uses Google's new Interactions API for autonomous market research.

Enhanced (Dec 2025): Supports visual outputs (charts, diagrams) when available.
Visual outputs require Google AI Ultra subscription ($249.99/mo).
Falls back gracefully to text-only research when visuals unavailable.
"""

import base64
import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Check if google-genai is available
try:
    from google import genai

    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    logger.warning("google-genai not installed. Run: pip install google-genai")


@dataclass
class ResearchOutput:
    """Structured output from Gemini Deep Research."""

    research_name: str
    timestamp: str
    text_content: dict[str, Any]
    visual_outputs: list[dict[str, Any]] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    status: str = "completed"
    error: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "research_name": self.research_name,
            "timestamp": self.timestamp,
            "text_content": self.text_content,
            "visual_outputs": [
                {"type": v["type"], "path": v.get("path"), "mime_type": v.get("mime_type")}
                for v in self.visual_outputs
            ],
            "sources": self.sources,
            "status": self.status,
            "error": self.error,
        }

    @property
    def has_visuals(self) -> bool:
        """Check if research includes visual outputs."""
        return len(self.visual_outputs) > 0


class GeminiDeepResearch:
    """
    Autonomous market research using Gemini Deep Research agent.
    Analyzes financials, news, sentiment before trading decisions.

    Enhanced Features:
    - Visual output capture (charts, diagrams) when available
    - Structured ResearchOutput dataclass for consistent access
    - Automatic storage to data/research_outputs/
    - Graceful fallback when visuals unavailable
    """

    # Storage directory for research outputs
    RESEARCH_DIR = Path("data/research_outputs")

    def __init__(self, output_dir: Optional[Path] = None):
        """
        Initialize Gemini Deep Research client.

        Args:
            output_dir: Custom output directory (default: data/research_outputs/)
        """
        self.client = None
        self.output_dir = output_dir or self.RESEARCH_DIR
        self._ensure_output_dirs()

        if GEMINI_AVAILABLE:
            api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
            if api_key:
                self.client = genai.Client(api_key=api_key)
                logger.info("✅ Gemini Deep Research initialized")
            else:
                logger.warning("⚠️ No GOOGLE_API_KEY found")

    def _ensure_output_dirs(self) -> None:
        """Create output directories if they don't exist."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        (self.output_dir / "visuals").mkdir(exist_ok=True)
        (self.output_dir / "json").mkdir(exist_ok=True)

    def research_crypto_market(self, symbol: str = "BTC") -> Optional[dict[str, Any]]:
        """
        Deep research on crypto market conditions before trading.
        Returns sentiment, key news, and trading recommendation.
        """
        if not self.client:
            return None

        query = f"""
        Research current {symbol} cryptocurrency market conditions for trading:

        1. Latest news and developments (last 24-48 hours)
        2. Market sentiment from social media and news
        3. Key support/resistance levels
        4. Any upcoming events (ETF decisions, halvings, regulations)
        5. Fear & Greed index analysis
        6. Whale wallet movements if available

        Provide a trading recommendation: BUY, SELL, or HOLD with confidence level.
        Format as JSON with keys: sentiment, news_summary, recommendation, confidence, key_levels
        """

        return self._run_research(query, f"{symbol}_market_research")

    def research_stock(self, symbol: str) -> Optional[dict[str, Any]]:
        """
        Deep research on a stock before trading.
        """
        if not self.client:
            return None

        query = f"""
        Research {symbol} stock for trading decision:

        1. Recent earnings and financial health
        2. Latest news and analyst ratings
        3. Technical analysis (RSI, MACD, moving averages)
        4. Institutional ownership changes
        5. Upcoming catalysts (earnings dates, FDA approvals, etc.)
        6. Sector performance comparison

        Provide a trading recommendation: BUY, SELL, or HOLD with confidence level.
        Format as JSON with keys: fundamentals, technicals, sentiment, recommendation, confidence, target_price
        """

        return self._run_research(query, f"{symbol}_stock_research")

    def research_market_conditions(self) -> Optional[dict[str, Any]]:
        """
        Research overall market conditions for risk management.
        """
        if not self.client:
            return None

        query = """
        Research current overall market conditions:

        1. S&P 500 and major indices trend
        2. VIX (volatility index) analysis
        3. Fed policy and interest rate outlook
        4. Geopolitical risks
        5. Sector rotation trends
        6. Risk-on vs Risk-off sentiment

        Recommend portfolio allocation: % stocks, % crypto, % cash
        Format as JSON with keys: market_regime, vix_analysis, allocation, risk_level, key_risks
        """

        return self._run_research(query, "market_conditions")

    def _run_research(
        self, query: str, research_name: str, timeout: int = 300
    ) -> Optional[dict[str, Any]]:
        """
        Execute deep research query and wait for results.

        Args:
            query: Research query to execute
            research_name: Identifier for this research (used in filenames)
            timeout: Maximum wait time in seconds (default: 300)

        Returns:
            Dictionary with research results, or None on failure
        """
        try:
            logger.info(f"🔍 Starting deep research: {research_name}")

            interaction = self.client.interactions.create(
                input=query, agent="deep-research-pro-preview-12-2025", background=True
            )

            logger.info(f"Research ID: {interaction.id}")

            start_time = time.time()
            while time.time() - start_time < timeout:
                interaction = self.client.interactions.get(interaction.id)

                if interaction.status == "completed":
                    # Process all outputs (text and visual)
                    research_output = self._process_outputs(interaction, research_name)

                    # Save to storage
                    self._save_research(research_output)

                    logger.info(
                        f"✅ Research completed: {research_name} "
                        f"(visuals: {len(research_output.visual_outputs)})"
                    )

                    # Return text content for backward compatibility
                    result = research_output.text_content.copy()
                    result["_research_output"] = research_output.to_dict()
                    return result

                elif interaction.status == "failed":
                    error_msg = getattr(interaction, "error", "Unknown error")
                    logger.error(f"❌ Research failed: {error_msg}")
                    return None

                time.sleep(10)

            logger.warning(f"⚠️ Research timeout: {research_name}")
            return None

        except Exception as e:
            logger.error(f"Research error: {e}")
            return None

    def _process_outputs(self, interaction: Any, research_name: str) -> ResearchOutput:
        """
        Process all outputs from a completed interaction.

        Handles:
        - Text outputs: Parsed as JSON or stored as raw text
        - Image outputs: Decoded from base64 and saved to disk
        """
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        text_content: dict[str, Any] = {}
        visual_outputs: list[dict[str, Any]] = []
        sources: list[str] = []

        for idx, output in enumerate(interaction.outputs):
            output_type = getattr(output, "type", "text")

            if output_type == "text" or hasattr(output, "text"):
                # Process text output
                result_text = getattr(output, "text", str(output))
                text_content = self._parse_text_output(result_text, research_name)

                # Extract sources if present
                if "sources" in text_content:
                    sources = text_content.get("sources", [])

            elif output_type == "image":
                # Process visual output (requires Google AI Ultra)
                visual_info = self._save_visual_output(
                    output, research_name, timestamp, idx
                )
                if visual_info:
                    visual_outputs.append(visual_info)
                    logger.info(f"📊 Saved visual output: {visual_info['path']}")

        return ResearchOutput(
            research_name=research_name,
            timestamp=timestamp,
            text_content=text_content,
            visual_outputs=visual_outputs,
            sources=sources,
        )

    def _parse_text_output(
        self, result_text: str, research_name: str
    ) -> dict[str, Any]:
        """Parse text output, attempting JSON extraction."""
        try:
            # Find JSON in response
            json_match = re.search(r"\{.*\}", result_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except (json.JSONDecodeError, AttributeError):
            pass

        # Return raw text if JSON parse fails
        return {"raw_research": result_text, "research_name": research_name}

    def _save_visual_output(
        self, output: Any, research_name: str, timestamp: str, idx: int
    ) -> Optional[dict[str, Any]]:
        """
        Save a visual output (image) to disk.

        Returns metadata about the saved visual, or None if save failed.
        """
        try:
            mime_type = getattr(output, "mime_type", "image/png")
            data = getattr(output, "data", None)

            if not data:
                logger.warning(f"Visual output {idx} has no data")
                return None

            # Determine file extension from mime type
            ext = mime_type.split("/")[-1] if "/" in mime_type else "png"
            filename = f"{research_name}_{timestamp}_{idx}.{ext}"
            filepath = self.output_dir / "visuals" / filename

            # Decode and save
            image_data = base64.b64decode(data)
            filepath.write_bytes(image_data)

            return {
                "type": "image",
                "mime_type": mime_type,
                "path": str(filepath),
                "filename": filename,
                "size_bytes": len(image_data),
            }

        except Exception as e:
            logger.error(f"Failed to save visual output {idx}: {e}")
            return None

    def _save_research(self, research_output: ResearchOutput) -> Path:
        """Save research output to JSON file."""
        filename = f"{research_output.research_name}_{research_output.timestamp}.json"
        filepath = self.output_dir / "json" / filename

        with open(filepath, "w") as f:
            json.dump(research_output.to_dict(), f, indent=2)

        return filepath

    def get_latest_research(self, research_name: str) -> Optional[ResearchOutput]:
        """
        Get the most recent research output for a given name.

        Useful for caching - avoid redundant API calls.
        """
        json_dir = self.output_dir / "json"
        if not json_dir.exists():
            return None

        # Find matching files
        pattern = f"{research_name}_*.json"
        matching_files = sorted(json_dir.glob(pattern), reverse=True)

        if not matching_files:
            return None

        # Load most recent
        with open(matching_files[0]) as f:
            data = json.load(f)

        return ResearchOutput(
            research_name=data["research_name"],
            timestamp=data["timestamp"],
            text_content=data["text_content"],
            visual_outputs=data.get("visual_outputs", []),
            sources=data.get("sources", []),
            status=data.get("status", "completed"),
        )

    def get_pre_trade_analysis(self, symbol: str, asset_type: str = "crypto") -> dict[str, Any]:
        """
        Get comprehensive pre-trade analysis before executing a trade.
        """
        result = {
            "symbol": symbol,
            "timestamp": datetime.utcnow().isoformat(),
            "analysis_available": False,
            "recommendation": "HOLD",
            "confidence": 0.5,
        }

        if not self.client:
            logger.warning("Gemini not available, using default analysis")
            return result

        if asset_type == "crypto":
            research = self.research_crypto_market(symbol.replace("USD", "").replace("/", ""))
        else:
            research = self.research_stock(symbol)

        if research:
            result["analysis_available"] = True
            result["research"] = research
            result["recommendation"] = research.get("recommendation", "HOLD")
            result["confidence"] = research.get("confidence", 0.5)

        return result


# Singleton instance
_researcher = None


def get_researcher() -> GeminiDeepResearch:
    global _researcher
    if _researcher is None:
        _researcher = GeminiDeepResearch()
    return _researcher


if __name__ == "__main__":
    # Test the integration
    logging.basicConfig(level=logging.INFO)
    researcher = get_researcher()

    print("Testing Gemini Deep Research for Trading...")
    result = researcher.research_crypto_market("BTC")
    print(json.dumps(result, indent=2) if result else "No result (API key needed)")
