"""
Lightweight Market Scanner Agent
Works without Stirrup dependency - uses OpenRouter directly.

Purpose:
- Autonomous market scanning using OpenRouter multi-LLM
- Generates UDM-validated trading signals
- Designed for 24/7 background operation

Usage:
    python -m src.agents.market_scanner --symbol BTCUSD --mode quick
    python -m src.agents.market_scanner --symbols "BTCUSD,AAPL" --continuous
"""

import asyncio
import json
import os
import aiohttp
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict
from enum import Enum
import sys

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from src.core.unified_domain_model import (
    Symbol, Signal, TradeAction, SignalStrength, AssetClass,
    DomainValidator, factory
)


# =============================================================================
# CONFIGURATION
# =============================================================================

class ScanMode(str, Enum):
    QUICK = "quick"       # Fast scan - headlines only
    STANDARD = "standard" # Normal - news + sentiment
    DEEP = "deep"         # Comprehensive research


@dataclass
class ScannerConfig:
    symbols: List[str]
    mode: ScanMode = ScanMode.STANDARD
    model: str = "anthropic/claude-sonnet-4"
    min_confidence: float = 0.6
    output_dir: str = "./data/scanner_output"


# =============================================================================
# OPENROUTER CLIENT
# =============================================================================

class OpenRouterClient:
    """Simple async OpenRouter client"""

    BASE_URL = "https://openrouter.ai/api/v1/chat/completions"

    def __init__(self, api_key: str = None, model: str = "anthropic/claude-sonnet-4"):
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY")
        self.model = model

        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY not set")

    async def chat(self, messages: List[Dict], temperature: float = 0.7) -> str:
        """Send chat completion request"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/trading-system",
        }

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(self.BASE_URL, headers=headers, json=payload) as resp:
                if resp.status != 200:
                    error = await resp.text()
                    raise Exception(f"OpenRouter error {resp.status}: {error}")

                data = await resp.json()
                return data["choices"][0]["message"]["content"]


# =============================================================================
# WEB SEARCH (using DuckDuckGo - no API key needed)
# =============================================================================

async def search_news(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    """Search for news using DuckDuckGo HTML (no API needed)"""
    try:
        from duckduckgo_search import DDGS

        with DDGS() as ddgs:
            results = list(ddgs.news(query, max_results=max_results))
            return [
                {
                    "title": r.get("title", ""),
                    "body": r.get("body", ""),
                    "url": r.get("url", ""),
                    "date": r.get("date", ""),
                }
                for r in results
            ]
    except ImportError:
        print("  [news] duckduckgo-search not installed")
        return []
    except Exception as e:
        # Handle network restrictions gracefully
        if "Connect" in str(e) or "tunnel" in str(e):
            print("  [news] Network restricted - using analysis without news")
        else:
            print(f"  [news] Search error: {type(e).__name__}")
        return []


# =============================================================================
# MARKET SCANNER
# =============================================================================

class MarketScanner:
    """Lightweight autonomous market scanner"""

    def __init__(self, config: ScannerConfig):
        self.config = config
        self.client = OpenRouterClient(model=config.model)

    def _get_scan_prompt(self, symbol: str, news: List[Dict]) -> str:
        """Build analysis prompt"""
        news_text = "\n".join([
            f"- {n['title']}: {n['body'][:200]}..."
            for n in news[:5]
        ]) if news else "No recent news found."

        mode_depth = {
            ScanMode.QUICK: "Brief analysis based on headlines.",
            ScanMode.STANDARD: "Moderate analysis with sentiment assessment.",
            ScanMode.DEEP: "Comprehensive analysis with multiple factors.",
        }

        return f"""
Analyze {symbol} and provide a trading signal.

## Recent News
{news_text}

## Analysis Depth
{mode_depth[self.config.mode]}

## Required Output Format (JSON)
{{
    "symbol": "{symbol}",
    "action": "BUY" | "SELL" | "HOLD",
    "confidence": 0.0-1.0,
    "reasoning": "Brief explanation",
    "sentiment": "bullish" | "bearish" | "neutral",
    "timeframe": "day" | "swing" | "position"
}}

Minimum actionable confidence: {self.config.min_confidence}
If uncertain, output HOLD.

Return ONLY the JSON, no other text.
"""

    async def scan_symbol(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Scan a single symbol"""
        print(f"  Scanning {symbol}...")

        # 1. Search for news
        news = await search_news(f"{symbol} stock crypto market news today")

        # 2. Get LLM analysis
        prompt = self._get_scan_prompt(symbol, news)
        messages = [{"role": "user", "content": prompt}]

        try:
            response = await self.client.chat(messages, temperature=0.3)

            # Parse JSON from response
            # Handle markdown code blocks
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                response = response.split("```")[1].split("```")[0]

            analysis = json.loads(response.strip())

            # 3. Create UDM signal if actionable
            if analysis.get("confidence", 0) >= self.config.min_confidence:
                signal = self._create_signal(symbol, analysis)
                if signal:
                    self._save_signal(signal, analysis)
                    return {"symbol": symbol, "signal": signal.to_dict(), "analysis": analysis}

            return {"symbol": symbol, "signal": None, "analysis": analysis}

        except json.JSONDecodeError as e:
            print(f"  Failed to parse response for {symbol}: {e}")
            return {"symbol": symbol, "error": str(e)}
        except Exception as e:
            print(f"  Error scanning {symbol}: {e}")
            return {"symbol": symbol, "error": str(e)}

    def _create_signal(self, symbol: str, analysis: Dict) -> Optional[Signal]:
        """Create UDM-validated signal"""
        try:
            # Determine asset class
            is_crypto = any(c in symbol.upper() for c in ["BTC", "ETH", "USD", "DOGE", "SOL"])

            if is_crypto:
                sym = factory.create_crypto_symbol(symbol.upper())
            else:
                sym = factory.create_equity_symbol(symbol.upper())

            action_map = {"BUY": TradeAction.BUY, "SELL": TradeAction.SELL, "HOLD": TradeAction.HOLD}
            action = action_map.get(analysis.get("action", "HOLD").upper(), TradeAction.HOLD)

            signal = factory.create_signal(
                symbol=sym,
                action=action,
                confidence=analysis.get("confidence", 0.5),
                source="market_scanner"
            )

            signal.metadata = {
                "reasoning": analysis.get("reasoning", ""),
                "sentiment": analysis.get("sentiment", "neutral"),
                "timeframe": analysis.get("timeframe", "day"),
                "scanned_at": datetime.utcnow().isoformat(),
            }

            # Validate
            if DomainValidator.is_valid(signal):
                return signal
            else:
                print(f"  Signal validation failed for {symbol}")
                return None

        except Exception as e:
            print(f"  Error creating signal: {e}")
            return None

    def _save_signal(self, signal: Signal, analysis: Dict):
        """Save signal to disk"""
        signals_dir = Path("./data/scanner_signals")
        signals_dir.mkdir(parents=True, exist_ok=True)

        filename = f"signal_{signal.symbol.ticker}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = signals_dir / filename

        data = {
            "signal": signal.to_dict(),
            "analysis": analysis,
            "generated_at": datetime.utcnow().isoformat(),
        }

        filepath.write_text(json.dumps(data, indent=2))
        print(f"  Signal saved: {filepath}")

    async def scan_all(self) -> List[Dict]:
        """Scan all configured symbols"""
        results = []
        for symbol in self.config.symbols:
            result = await self.scan_symbol(symbol)
            if result:
                results.append(result)
            await asyncio.sleep(1)  # Rate limiting
        return results


# =============================================================================
# CONTINUOUS MONITORING
# =============================================================================

async def run_continuous(symbols: List[str], interval_minutes: int = 60, mode: ScanMode = ScanMode.STANDARD):
    """Run scanner continuously"""
    config = ScannerConfig(symbols=symbols, mode=mode)
    scanner = MarketScanner(config)

    print(f"Starting continuous scanner")
    print(f"  Symbols: {symbols}")
    print(f"  Interval: {interval_minutes} min")
    print(f"  Mode: {mode.value}")
    print()

    while True:
        print(f"{'='*50}")
        print(f"Scan at {datetime.utcnow().isoformat()}")
        print(f"{'='*50}")

        results = await scanner.scan_all()

        actionable = [r for r in results if r.get("signal")]
        print(f"\nResults: {len(results)} scanned, {len(actionable)} actionable signals")

        for r in actionable:
            s = r["signal"]
            print(f"  {s['action']} {s['symbol']} @ {s['confidence']:.0%}")

        print(f"\nNext scan in {interval_minutes} minutes...")
        await asyncio.sleep(interval_minutes * 60)


# =============================================================================
# CLI
# =============================================================================

async def main():
    import argparse

    parser = argparse.ArgumentParser(description="Market Scanner")
    parser.add_argument("--symbol", "-s", default="BTCUSD", help="Symbol to scan")
    parser.add_argument("--symbols", help="Comma-separated symbols")
    parser.add_argument("--mode", "-m", default="quick", choices=["quick", "standard", "deep"])
    parser.add_argument("--continuous", "-c", action="store_true", help="Run continuously")
    parser.add_argument("--interval", "-i", type=int, default=60, help="Interval in minutes")

    args = parser.parse_args()

    symbols = [s.strip().upper() for s in args.symbols.split(",")] if args.symbols else [args.symbol.upper()]
    mode = ScanMode(args.mode)

    if args.continuous:
        await run_continuous(symbols, args.interval, mode)
    else:
        config = ScannerConfig(symbols=symbols, mode=mode)
        scanner = MarketScanner(config)

        print(f"Scanning {symbols} in {mode.value} mode...")
        results = await scanner.scan_all()

        print(f"\n{'='*50}")
        print("SCAN RESULTS")
        print(f"{'='*50}")
        for r in results:
            if "error" in r:
                print(f"  {r['symbol']}: ERROR - {r['error']}")
            elif r.get("signal"):
                s = r["signal"]
                print(f"  {r['symbol']}: {s['action']} @ {s['confidence']:.0%} - {r['analysis'].get('reasoning', '')[:50]}")
            else:
                a = r.get("analysis", {})
                print(f"  {r['symbol']}: {a.get('action', 'N/A')} @ {a.get('confidence', 0):.0%} (below threshold)")


if __name__ == "__main__":
    asyncio.run(main())
