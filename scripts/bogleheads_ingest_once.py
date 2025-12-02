#!/usr/bin/env python3
"""
Ingest a single Bogleheads forum snapshot into the Sentiment RAG store.

Prefers the BogleheadsLearner (from .claude skills). Falls back to BogleHeadsAgent
if the learner is unavailable.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.rag.sentiment_store import SentimentDocument, SentimentRAGStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("bogleheads_ingest")


def _try_learner() -> dict:
    try:
        # Try to import from .claude/skills first, fall back to direct path
        try:
            from claude.skills.bogleheads_learner.scripts.bogleheads_learner import (
                BogleheadsLearner,
            )
        except ModuleNotFoundError:
            # In CI/CD environment, use absolute path
            skills_path = project_root / ".claude" / "skills" / "bogleheads_learner" / "scripts"
            sys.path.insert(0, str(skills_path))
            from bogleheads_learner import BogleheadsLearner

        learner = BogleheadsLearner()
        return learner.monitor_bogleheads_forum(
            topics=["Personal Investments", "Investing - Theory, News & General"],
            keywords=["rebalancing", "risk", "volatility", "index funds", "ETF"],
            max_posts=30,
            min_replies=3,
        )
    except Exception as e:
        logger.info(f"Learner unavailable or failed: {e}")
        return {}


def _fallback_agent() -> dict:
    try:
        from src.agents.bogleheads_agent import BogleHeadsAgent

        agent = BogleHeadsAgent()
        result = agent.analyze({"symbol": None})
        return {
            "posts_analyzed": 0,
            "sentiment_summary": result.get("bogleheads_sentiment", "Unknown"),
            "decision": result.get("signal", "HOLD"),
            "confidence": result.get("confidence", 0.5),
            "reasoning": result.get("reasoning", ""),
            "raw": result,
        }
    except Exception as e:
        logger.warning(f"BogleHeadsAgent fallback failed: {e}")
        return {}


def main() -> None:
    # Collect forum snapshot
    snapshot = _try_learner() or _fallback_agent()
    if not snapshot:
        logger.warning("No Bogleheads snapshot collected; exiting")
        return

    # Build RAG document
    now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    doc_id = f"bogleheads_{now}"
    text = json.dumps(snapshot, ensure_ascii=False)
    metadata = {
        "ticker": "MARKET",
        "published_date": now,
        "sentiment_score": 0.0,
        "confidence": snapshot.get("confidence", "medium"),
        "market_regime": snapshot.get("regime", "unknown"),
        "source_list": "bogleheads_forum",
        "freshness": "live",
        "days_old": 0,
    }

    try:
        store = SentimentRAGStore()
        count = store.upsert_documents(
            [SentimentDocument(document_id=doc_id, text=text, metadata=metadata)]
        )
        logger.info("Upserted %d Bogleheads snapshot into RAG", count)
    except Exception as e:
        logger.warning(f"RAG upsert failed (will write JSON fallback): {e}")
        try:
            fallback_dir = Path("data/rag")
            fallback_dir.mkdir(parents=True, exist_ok=True)
            (fallback_dir / "bogleheads_latest.json").write_text(
                json.dumps({"snapshot": snapshot, "metadata": metadata}, indent=2),
                encoding="utf-8",
            )
            logger.info("Wrote fallback snapshot to data/rag/bogleheads_latest.json")
        except Exception as e2:
            logger.error(f"Failed to write fallback JSON: {e2}")


if __name__ == "__main__":
    main()
