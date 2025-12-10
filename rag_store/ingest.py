from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from .sqlite_store import SentimentSQLiteStore
from .vector_store import SentimentVectorStore

sqlite_store = SentimentSQLiteStore()
vector_store = SentimentVectorStore()


def _build_reddit_summary(ticker: str, payload: dict) -> str:
    top_posts = payload.get("top_posts", [])
    top_snippet = ""
    if top_posts:
        post = top_posts[0]
        top_snippet = (
            f"Top post: {post.get('title', '')[:200]} "
            f"(upvotes={post.get('score')}, comments={post.get('comments')})."
        )

    return (
        f"Reddit sentiment for {ticker}: score={payload.get('score')}, "
        f"mentions={payload.get('mentions')}, "
        f"confidence={payload.get('confidence')}. "
        f"Bullish keywords={payload.get('bullish_keywords')}, "
        f"bearish keywords={payload.get('bearish_keywords')}. "
        f"{top_snippet}"
    )


def _build_news_summary(ticker: str, payload: dict) -> str:
    sources = payload.get("sources", {})
    yahoo = sources.get("yahoo", {})
    stocktwits = sources.get("stocktwits", {})
    av = sources.get("alphavantage", {})

    return (
        f"News sentiment for {ticker}: score={payload.get('score')}, "
        f"confidence={payload.get('confidence')}. "
        f"Yahoo articles={yahoo.get('articles', 0)}, "
        f"Stocktwits messages={stocktwits.get('messages', 0)}, "
        f"AlphaVantage articles={av.get('articles', 0)}."
    )


def _prepare_docs(
    source: str,
    snapshot_date: str,
    entries: Iterable[dict],
    summary_builder,
) -> Iterable[dict]:
    for ticker, payload in entries:
        doc_id = f"{source}-{ticker}-{snapshot_date}"
        summary = summary_builder(ticker, payload)
        metadata = {
            "source": source,
            "ticker": ticker,
            "snapshot_date": snapshot_date,
            "score": payload.get("score"),
            "confidence": payload.get("confidence"),
        }
        yield {
            "id": doc_id,
            "text": summary,
            "metadata": metadata,
            "summary": summary,
        }


def ingest_reddit_snapshot(snapshot: dict) -> None:
    """Persist Reddit sentiment snapshot into the RAG store."""
    date_str = snapshot.get("meta", {}).get("date") or datetime.now().strftime("%Y-%m-%d")
    created_at = snapshot.get("meta", {}).get("timestamp", datetime.utcnow().isoformat())
    sentiments = snapshot.get("sentiment_by_ticker", {})

    if not sentiments:
        return

    sqlite_entries = []
    docs = []

    for doc in _prepare_docs(
        "reddit",
        date_str,
        sentiments.items(),
        _build_reddit_summary,
    ):
        sqlite_entries.append(
            {
                "source": "reddit",
                "ticker": doc["metadata"]["ticker"],
                "snapshot_date": date_str,
                "score": doc["metadata"]["score"],
                "confidence": doc["metadata"]["confidence"],
                "market_regime": None,
                "summary": doc["summary"],
                "metadata": sentiments[doc["metadata"]["ticker"]],
                "created_at": created_at,
            }
        )
        doc["metadata"]["created_at"] = created_at
        docs.append(doc)

    sqlite_store.bulk_upsert(sqlite_entries)
    vector_store.upsert_documents(docs)


def ingest_news_snapshot(report: dict) -> None:
    """Persist news sentiment report into the RAG store."""
    date_str = report.get("meta", {}).get("date") or datetime.now().strftime("%Y-%m-%d")
    created_at = report.get("meta", {}).get("timestamp", datetime.utcnow().isoformat())
    sentiments = report.get("sentiment_by_ticker", {})

    if not sentiments:
        return

    sqlite_entries = []
    docs = []

    for doc in _prepare_docs(
        "news",
        date_str,
        sentiments.items(),
        _build_news_summary,
    ):
        ticker = doc["metadata"]["ticker"]
        sqlite_entries.append(
            {
                "source": "news",
                "ticker": ticker,
                "snapshot_date": date_str,
                "score": doc["metadata"]["score"],
                "confidence": doc["metadata"]["confidence"],
                "market_regime": None,
                "summary": doc["summary"],
                "metadata": sentiments[ticker],
                "created_at": created_at,
            }
        )
        doc["metadata"]["created_at"] = created_at
        docs.append(doc)

    sqlite_store.bulk_upsert(sqlite_entries)
    vector_store.upsert_documents(docs)
