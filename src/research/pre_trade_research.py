"""Pre-trade research via Perplexity API.

Queries Perplexity for real-time market context before each iron condor entry.
Advisory only — does not block trades, but logs findings to RAG.

Usage:
    from src.research.pre_trade_research import get_pre_trade_research
    research = get_pre_trade_research(spy_price=660.0, vix=19.5)
"""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

PERPLEXITY_API_URL = "https://api.perplexity.ai/chat/completions"
CACHE_FILE = Path(__file__).parent.parent.parent / "data" / "perplexity_pre_trade_cache.json"


def get_pre_trade_research(
    spy_price: float = 0.0,
    vix: float = 0.0,
    regime: str = "unknown",
) -> dict:
    """Query Perplexity for pre-trade market context.

    Returns dict with 'summary', 'risks', 'recommendation', 'source'.
    Non-blocking: returns empty result on any failure.
    """
    api_key = os.environ.get("PERPLEXITY_API_KEY", "")
    if not api_key:
        logger.debug("PERPLEXITY_API_KEY not set — skipping pre-trade research")
        return {"skipped": True, "reason": "no_api_key"}

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Check cache (1 query per day max — respect rate limits)
    cache = _load_cache()
    if cache.get("date") == today and cache.get("result"):
        logger.info(f"Pre-trade research (cached): {cache['result'].get('summary', '')[:80]}")
        return cache["result"]

    query = (
        f"Today is {today}. SPY is at ${spy_price:.0f}, VIX is {vix:.1f}. "
        f"Market regime appears {regime}. "
        f"I'm considering selling a SPY iron condor (15-delta, 30-45 DTE). "
        f"What are the key risks today? Any scheduled events (earnings, FOMC, "
        f"economic data)? Is this a good day to sell premium? "
        f"Answer in 3-4 sentences max."
    )

    try:
        resp = requests.post(
            PERPLEXITY_API_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "sonar",
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are a concise options market analyst. "
                            "Answer in 3-4 sentences. Focus on actionable risks "
                            "for iron condor sellers. No disclaimers."
                        ),
                    },
                    {"role": "user", "content": query},
                ],
                "max_tokens": 200,
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

        answer = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        citations = data.get("citations", [])

        result = {
            "summary": answer.strip(),
            "citations": citations[:3],
            "spy_price": spy_price,
            "vix": vix,
            "regime": regime,
            "queried_at": datetime.now(timezone.utc).isoformat(),
            "model": "sonar",
        }

        # Cache for the day
        _save_cache({"date": today, "result": result})

        logger.info(f"Pre-trade research: {answer[:100]}")
        return result

    except Exception as e:
        logger.warning(f"Pre-trade research failed: {e}")
        return {"skipped": True, "reason": str(e)}


def _load_cache() -> dict:
    try:
        if CACHE_FILE.exists():
            return json.loads(CACHE_FILE.read_text())
    except Exception:
        pass
    return {}


def _save_cache(data: dict):
    try:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        CACHE_FILE.write_text(json.dumps(data, indent=2))
    except Exception:
        pass
