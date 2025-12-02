import json
from pathlib import Path

import numpy as np
from src.rag.sentiment_store import SentimentRAGStore


class DummyEmbedder:
    """Lightweight embedder used for testing without heavy ML dependencies."""

    def __init__(self, dimension: int = 4):
        self.dimension = dimension

    def embed_single(self, text: str) -> np.ndarray:
        seed = hash(text) % 1000
        rng = np.random.default_rng(seed)
        vec = rng.random(self.dimension)
        return vec / np.linalg.norm(vec)

    def embed_batch(self, texts):
        return np.vstack([self.embed_single(text) for text in texts])


def _write_sentiment_file(target_dir: Path, date: str = "2025-11-09") -> None:
    payload = {
        "meta": {
            "date": date,
            "timestamp": f"{date}T08:00:00",
            "sources": ["reddit", "news"],
            "freshness": "fresh",
            "days_old": 0,
        },
        "sentiment_by_ticker": {
            "SPY": {
                "score": 65.0,
                "confidence": "high",
                "market_regime": "risk_on",
                "sources": {
                    "reddit": {
                        "normalized_score": 70.0,
                        "mentions": 40,
                        "confidence": "high",
                    },
                    "news": {
                        "normalized_score": 60.0,
                        "confidence": "medium",
                    },
                },
            },
            "NVDA": {
                "score": 55.0,
                "confidence": "medium",
                "market_regime": "neutral",
                "sources": {
                    "reddit": {
                        "normalized_score": 58.0,
                        "mentions": 25,
                        "confidence": "medium",
                    }
                },
            },
        },
    }

    (target_dir).mkdir(parents=True, exist_ok=True)
    with open(target_dir / f"reddit_{date}.json", "w") as handle:
        json.dump(payload, handle)
    with open(target_dir / f"news_{date}.json", "w") as handle:
        json.dump(payload, handle)


def test_ingest_and_history(tmp_path):
    sentiment_dir = tmp_path / "sentiment"
    _write_sentiment_file(sentiment_dir)

    store = SentimentRAGStore(
        db_path=tmp_path / "sentiment.db",
        embedder=DummyEmbedder(),
        sentiment_dir=sentiment_dir,
    )

    written = store.ingest_from_cache(days=3)
    assert written == 4  # 2 tickers * 2 files (reddit/news)

    history = store.get_ticker_history("SPY", limit=3)
    assert history, "Expected SPY sentiment history entries"
    assert history[0]["metadata"]["ticker"] == "SPY"
    assert history[0]["metadata"]["confidence"] == "high"


def test_semantic_query_returns_results(tmp_path):
    sentiment_dir = tmp_path / "sentiment"
    _write_sentiment_file(sentiment_dir, date="2025-11-10")

    store = SentimentRAGStore(
        db_path=tmp_path / "sentiment.db",
        embedder=DummyEmbedder(),
        sentiment_dir=sentiment_dir,
    )
    store.ingest_from_cache()

    results = store.query(query="SPY market outlook", ticker="SPY", top_k=2)
    assert len(results) > 0
    assert results[0]["metadata"]["ticker"] == "SPY"
