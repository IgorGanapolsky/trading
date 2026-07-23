"""Unified search index for all trading data sources.

Indexes lessons learned, trades, session decisions, and market signals into a
single searchable index with weighted hybrid BM25 + metadata ranking.
"""

from __future__ import annotations

import glob as glob_mod
import json
import logging
import math
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from src.analytics.trade_evidence import build_trade_evidence

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
LESSONS_DIR = PROJECT_ROOT / "rag_knowledge" / "lessons_learned"

KNOWN_TICKERS = {
    "SPY",
    "IWM",
    "QQQ",
    "SOFI",
    "VOO",
    "AAPL",
    "MSFT",
    "TSLA",
    "NVDA",
    "AMD",
    "AMZN",
    "META",
    "GOOG",
}

_STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "that",
    "this",
    "into",
    "over",
    "your",
    "you",
    "our",
    "are",
    "was",
    "were",
    "why",
    "how",
    "what",
    "when",
    "where",
    "who",
    "which",
    "about",
    "after",
    "before",
    "they",
    "them",
    "their",
    "then",
    "than",
    "but",
    "not",
    "can",
    "could",
    "should",
    "would",
    "will",
    "just",
    "does",
    "did",
    "had",
    "has",
    "have",
    "it",
    "its",
    "be",
    "as",
    "at",
    "by",
    "or",
    "if",
    "in",
    "on",
    "to",
    "of",
}

_SEVERITY_MULTIPLIERS = {
    "CRITICAL": 1.35,
    "HIGH": 1.2,
    "MEDIUM": 1.0,
    "LOW": 0.9,
}

_MONTH_MAP = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}


@dataclass
class SearchDocument:
    """A document in the unified search index."""

    id: str
    source_type: str
    title: str
    content: str
    date: datetime | None = None
    severity: str = "MEDIUM"
    tags: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass
class SearchResult:
    """A ranked search result."""

    id: str
    source_type: str
    title: str
    score: float
    snippet: str
    keyword_score: float
    metadata_score: float
    metadata: dict = field(default_factory=dict)


class UnifiedSearch:
    """Unified hybrid BM25 + metadata search across all trading data sources."""

    def __init__(self, keyword_weight: float = 0.55, metadata_weight: float = 0.45):
        self._keyword_weight = keyword_weight
        self._metadata_weight = metadata_weight
        self._documents: list[SearchDocument] = []
        self._idf: dict[str, float] = {}
        self._avgdl: float = 0.0
        self._source_weights: dict[str, float] = {}
        self._last_trade_evidence: dict = {}

    def build_index(self) -> dict:
        """Load all data sources and build the BM25 index."""
        self._documents = []

        lessons = self._load_lessons()
        trades = self._load_trades()
        session_decisions = self._load_session_decisions()
        market_signals = self._load_market_signals()

        self._documents = lessons + trades + session_decisions + market_signals
        self._build_idf()

        stats = {
            "lessons": len(lessons),
            "trades": len(trades),
            "session_decisions": len(session_decisions),
            "market_signals": len(market_signals),
            "bm25_vocabulary": len(self._idf),
            "avg_doc_length": round(self._avgdl, 1),
            "trade_evidence": dict(self._last_trade_evidence),
        }
        logger.info("Unified search index built: %s", stats)
        return stats

    def search(
        self,
        query: str,
        top_k: int = 10,
        source_types: list[str] | None = None,
        ticker: str | None = None,
        severity_filter: str | None = None,
    ) -> list[dict]:
        """Search across all indexed documents."""
        query_terms = self._tokenize(query)
        if not query_terms:
            return []

        query_tickers = {t for t in query.upper().split() if t in KNOWN_TICKERS}
        if ticker:
            query_tickers.add(ticker.upper())

        results: list[SearchResult] = []
        raw_bm25_scores: list[tuple[SearchDocument, float]] = []

        candidates = self._documents
        if source_types:
            candidates = [d for d in candidates if d.source_type in source_types]
        if severity_filter:
            candidates = [d for d in candidates if d.severity == severity_filter.upper()]

        for doc in candidates:
            bm25 = self._bm25_score(query_terms, doc.content)
            raw_bm25_scores.append((doc, bm25))

        max_bm25 = max((s for _, s in raw_bm25_scores), default=0.0)
        if max_bm25 == 0.0:
            return []

        for doc, bm25 in raw_bm25_scores:
            norm_bm25 = bm25 / max_bm25
            meta_score = self._metadata_score(doc, query_tickers)
            combined = (self._keyword_weight * norm_bm25) + (self._metadata_weight * meta_score)

            results.append(
                SearchResult(
                    id=doc.id,
                    source_type=doc.source_type,
                    title=doc.title,
                    score=round(combined, 4),
                    snippet=doc.content[:500],
                    keyword_score=round(norm_bm25, 4),
                    metadata_score=round(meta_score, 4),
                    metadata=doc.metadata,
                )
            )

        results.sort(key=lambda r: r.score, reverse=True)
        top = results[:top_k]

        return [
            {
                "id": r.id,
                "type": r.source_type,
                "title": r.title,
                "score": r.score,
                "snippet": r.snippet,
                "keyword_score": r.keyword_score,
                "metadata_score": r.metadata_score,
                "metadata": r.metadata,
            }
            for r in top
        ]

    # ------------------------------------------------------------------
    # BM25
    # ------------------------------------------------------------------

    def _build_idf(self) -> None:
        """Build IDF table and compute average document length."""
        doc_freq: dict[str, int] = {}
        total_len = 0
        n = len(self._documents)

        for doc in self._documents:
            tokens = self._tokenize(doc.content)
            total_len += len(tokens)
            seen: set[str] = set()
            for tok in tokens:
                if tok not in seen:
                    doc_freq[tok] = doc_freq.get(tok, 0) + 1
                    seen.add(tok)

        self._avgdl = total_len / n if n > 0 else 1.0
        self._idf = {}
        for term, df in doc_freq.items():
            self._idf[term] = math.log((n - df + 0.5) / (df + 0.5) + 1.0)

    def _bm25_score(
        self, query_terms: list[str], doc_content: str, k1: float = 1.2, b: float = 0.75
    ) -> float:
        """Compute BM25 score for a document against query terms."""
        tokens = self._tokenize(doc_content)
        dl = len(tokens)
        tf_map: dict[str, int] = {}
        for tok in tokens:
            tf_map[tok] = tf_map.get(tok, 0) + 1

        score = 0.0
        for term in query_terms:
            if term not in self._idf:
                continue
            tf = tf_map.get(term, 0)
            idf = self._idf[term]
            numerator = tf * (k1 + 1)
            denominator = tf + k1 * (1 - b + b * dl / self._avgdl)
            score += idf * (numerator / denominator)

        return score

    # ------------------------------------------------------------------
    # Metadata scoring
    # ------------------------------------------------------------------

    def _metadata_score(self, doc: SearchDocument, query_tickers: set[str]) -> float:
        """Compute metadata-based score with ticker, severity, and recency bonuses."""
        score = 0.0

        # Ticker match bonus
        doc_tickers = set()
        for tag in doc.tags:
            if tag.upper() in KNOWN_TICKERS:
                doc_tickers.add(tag.upper())
        doc_symbol = doc.metadata.get("symbol", "").upper()
        if doc_symbol in KNOWN_TICKERS:
            doc_tickers.add(doc_symbol)
        if query_tickers and doc_tickers & query_tickers:
            score += 0.15

        # Recency bonus
        if doc.date:
            now = datetime.now()
            days_ago = (now - doc.date).days
            if days_ago <= 7:
                score += 0.12
            elif days_ago <= 30:
                score += 0.08
            elif days_ago <= 90:
                score += 0.05

        # Base before severity multiplier
        base = max(score, 0.01)

        # Severity multiplier
        multiplier = _SEVERITY_MULTIPLIERS.get(doc.severity, 1.0)
        score = base * multiplier

        # Source weight
        src_weight = self._source_weights.get(doc.source_type, 1.0)
        score *= src_weight

        return score

    # ------------------------------------------------------------------
    # Tokenizer
    # ------------------------------------------------------------------

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """Tokenize text: lowercase, split on non-alphanumeric, filter stopwords and short tokens."""
        tokens = re.split(r"[^a-zA-Z0-9]+", text.lower())
        return [t for t in tokens if t and len(t) > 2 and t not in _STOPWORDS]

    # ------------------------------------------------------------------
    # Data loaders
    # ------------------------------------------------------------------

    def _load_lessons(self) -> list[SearchDocument]:
        """Load lessons learned from markdown files."""
        docs: list[SearchDocument] = []
        if not LESSONS_DIR.exists():
            logger.warning("Lessons directory not found: %s", LESSONS_DIR)
            return docs

        for path in sorted(LESSONS_DIR.glob("*.md")):
            try:
                content = path.read_text(encoding="utf-8")
                title = self._extract_md_title(content) or path.stem
                severity = self._extract_severity(content)
                date = self._extract_date_from_filename(path.name)
                tags = self._extract_tickers_from_text(content)

                docs.append(
                    SearchDocument(
                        id=f"lesson:{path.stem}",
                        source_type="lesson",
                        title=title,
                        content=content,
                        date=date,
                        severity=severity,
                        tags=tags,
                        metadata={"file": str(path.name)},
                    )
                )
            except Exception as exc:
                logger.warning("Failed to load lesson %s: %s", path.name, exc)

        return docs

    def _load_trades(self) -> list[SearchDocument]:
        """Load only verified paired closed trades.

        Raw fills and legacy spread summaries are useful diagnostics, but they
        are not ground-truth outcomes and must not be retrieved by an agent as
        if they were completed trades.
        """
        docs: list[SearchDocument] = []

        # trades.json
        trades_path = DATA_DIR / "trades.json"
        if trades_path.exists():
            try:
                data = json.loads(trades_path.read_text(encoding="utf-8"))
                evidence = build_trade_evidence(data)
                self._last_trade_evidence = evidence.to_dict()
                rows = [] if evidence.issues else evidence.rows
                for trade in rows:
                    tid = trade.get("id", "unknown")
                    symbol = trade.get("symbol", "")
                    strategy = trade.get("strategy", "")
                    entry_date = trade.get("entry_date", "")
                    exit_date = trade.get("exit_date", "")
                    credit = trade.get("entry_credit", 0)
                    debit = trade.get("exit_debit", 0)
                    pnl = trade.get("realized_pnl", 0)
                    outcome = trade.get("outcome", "")
                    legs = trade.get("legs", {})
                    put_strikes = legs.get("put_strikes", [])
                    call_strikes = legs.get("call_strikes", [])

                    parts = [
                        f"{symbol} {strategy}",
                        f"entry:{entry_date} exit:{exit_date}",
                        f"credit:${credit} debit:${debit} PnL:${pnl}",
                        f"outcome:{outcome}",
                    ]
                    if put_strikes:
                        parts.append(f"put_strikes:{'-'.join(str(int(s)) for s in put_strikes)}")
                    if call_strikes:
                        parts.append(f"call_strikes:{'-'.join(str(int(s)) for s in call_strikes)}")
                    content = " ".join(parts)
                    title = f"{symbol} {strategy} {entry_date}"

                    date = None
                    if entry_date:
                        try:
                            date = datetime.strptime(entry_date, "%Y-%m-%d")
                        except ValueError:
                            pass

                    docs.append(
                        SearchDocument(
                            id=f"trade:{tid}",
                            source_type="trade",
                            title=title,
                            content=content,
                            date=date,
                            severity="MEDIUM",
                            tags=[symbol] if symbol else [],
                            metadata={
                                "symbol": symbol,
                                "strategy": strategy,
                                "pnl": pnl,
                                "outcome": outcome,
                                "evidence_status": trade["evidence_status"],
                                "dataset_sha256": evidence.dataset_sha256,
                            },
                        )
                    )
            except Exception as exc:
                logger.warning("Failed to load trades.json: %s", exc)

        # Legacy spread summaries are indexed only when a producer explicitly
        # marks each row as broker-paired and verified.  Existing unlabelled
        # rows remain available on disk for diagnostics, not agent grounding.
        spread_path = DATA_DIR / "spread_performance.json"
        if spread_path.exists():
            try:
                data = json.loads(spread_path.read_text(encoding="utf-8"))
                for trade in data.get("trades", []):
                    if trade.get("evidence_status") != "verified_paired_closed_trade":
                        continue
                    date_str = trade.get("date", "")
                    symbol = trade.get("symbol", "")
                    premium = trade.get("premium", 0)
                    pnl = trade.get("pnl", 0)
                    is_win = trade.get("is_win", False)
                    trade_num = trade.get("trade_num", 0)

                    content = (
                        f"{symbol} spread date:{date_str} "
                        f"premium:${premium} PnL:${pnl} "
                        f"outcome:{'win' if is_win else 'loss'}"
                    )
                    title = f"Spread {symbol} {date_str}"

                    date = None
                    if date_str:
                        try:
                            date = datetime.strptime(date_str, "%Y-%m-%d")
                        except ValueError:
                            pass

                    # Extract base ticker from OCC symbol
                    ticker_match = re.match(r"([A-Z]+)\d", symbol)
                    base_ticker = ticker_match.group(1) if ticker_match else symbol

                    docs.append(
                        SearchDocument(
                            id=f"spread:{trade_num}:{symbol}",
                            source_type="trade",
                            title=title,
                            content=content,
                            date=date,
                            severity="MEDIUM",
                            tags=[base_ticker] if base_ticker else [],
                            metadata={
                                "symbol": base_ticker,
                                "premium": premium,
                                "pnl": pnl,
                                "is_win": is_win,
                                "evidence_status": trade["evidence_status"],
                            },
                        )
                    )
            except Exception as exc:
                logger.warning("Failed to load spread_performance.json: %s", exc)

        return docs

    def _load_session_decisions(self) -> list[SearchDocument]:
        """Load session decisions from data/session_decisions_*.json."""
        docs: list[SearchDocument] = []
        pattern = str(DATA_DIR / "session_decisions_*.json")

        for path_str in sorted(glob_mod.glob(pattern)):
            path = Path(path_str)
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                session = data.get("session", {})
                session_date = session.get("date", "")

                for decision in data.get("decisions", []):
                    ticker = decision.get("ticker", "")
                    dec = decision.get("decision", "")
                    reason = decision.get("rejection_reason", "")
                    gate = decision.get("gate_reached", 0)
                    indicators = decision.get("indicators", {})

                    macd = indicators.get("macd", "")
                    rsi = indicators.get("rsi", "")
                    adx = indicators.get("adx", "")
                    price = indicators.get("current_price", "")

                    content = (
                        f"{session_date} {ticker} {dec} gate:{gate} "
                        f"reason:{reason} MACD:{macd} RSI:{rsi} ADX:{adx} price:${price}"
                    )
                    title = f"{session_date} {ticker} {dec}"

                    date = None
                    if session_date:
                        try:
                            date = datetime.strptime(session_date, "%Y-%m-%d")
                        except ValueError:
                            pass

                    docs.append(
                        SearchDocument(
                            id=f"decision:{session_date}:{ticker}",
                            source_type="session_decision",
                            title=title,
                            content=content,
                            date=date,
                            severity="MEDIUM",
                            tags=[ticker] if ticker else [],
                            metadata={
                                "symbol": ticker,
                                "decision": dec,
                                "gate": gate,
                                "indicators": indicators,
                            },
                        )
                    )
            except Exception as exc:
                logger.warning("Failed to load session decisions %s: %s", path.name, exc)

        return docs

    def _load_market_signals(self) -> list[SearchDocument]:
        """Load market signals from data/market_signals/*.json and data/trend_snapshot.json."""
        docs: list[SearchDocument] = []

        # market_signals directory
        signals_dir = DATA_DIR / "market_signals"
        if signals_dir.exists():
            for path in sorted(signals_dir.glob("*.json")):
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                    signal_name = data.get("signal", path.stem)
                    status = data.get("status", "unknown")
                    severity_score = data.get("severity_score", 0)
                    reasons = data.get("reasons", [])

                    content = (
                        f"Market signal: {signal_name} status:{status} "
                        f"severity_score:{severity_score} reasons:{'; '.join(reasons)}"
                    )
                    title = f"Signal: {signal_name}"

                    date = None
                    updated = data.get("updated_at", "")
                    if updated:
                        try:
                            date = datetime.fromisoformat(updated.replace("Z", "+00:00")).replace(
                                tzinfo=None
                            )
                        except (ValueError, TypeError):
                            pass

                    severity = (
                        "HIGH"
                        if severity_score > 0.7
                        else "MEDIUM"
                        if severity_score > 0.3
                        else "LOW"
                    )

                    docs.append(
                        SearchDocument(
                            id=f"signal:{path.stem}",
                            source_type="market_signal",
                            title=title,
                            content=content,
                            date=date,
                            severity=severity,
                            tags=[],
                            metadata=data,
                        )
                    )
                except Exception as exc:
                    logger.warning("Failed to load market signal %s: %s", path.name, exc)

        # trend_snapshot.json
        trend_path = DATA_DIR / "trend_snapshot.json"
        if trend_path.exists():
            try:
                data = json.loads(trend_path.read_text(encoding="utf-8"))
                symbols = data.get("symbols", {})
                generated = data.get("generated_at", "")

                date = None
                if generated:
                    try:
                        date = datetime.fromisoformat(generated)
                    except (ValueError, TypeError):
                        pass

                for sym, info in symbols.items():
                    regime = info.get("regime_bias", "")
                    price = info.get("price", 0)
                    gate_open = info.get("gate_open", False)

                    content = (
                        f"Trend snapshot {sym} regime:{regime} price:${price} "
                        f"gate_open:{gate_open} sma20:{info.get('sma20', '')} "
                        f"sma50:{info.get('sma50', '')} sma200:{info.get('sma200', '')}"
                    )
                    title = f"Trend: {sym} {regime}"

                    docs.append(
                        SearchDocument(
                            id=f"trend:{sym}",
                            source_type="market_signal",
                            title=title,
                            content=content,
                            date=date,
                            severity="MEDIUM",
                            tags=[sym],
                            metadata={"symbol": sym, **info},
                        )
                    )
            except Exception as exc:
                logger.warning("Failed to load trend_snapshot.json: %s", exc)

        return docs

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_md_title(content: str) -> str | None:
        """Extract title from first markdown heading."""
        match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        return match.group(1).strip() if match else None

    @staticmethod
    def _extract_severity(content: str) -> str:
        """Extract severity from markdown content."""
        match = re.search(r"\*\*Severity\*\*:\s*(\w+)", content, re.IGNORECASE)
        if match:
            val = match.group(1).upper()
            if val in _SEVERITY_MULTIPLIERS:
                return val
        return "MEDIUM"

    @staticmethod
    def _extract_date_from_filename(filename: str) -> datetime | None:
        """Extract date from lesson filename."""
        # Pattern: month + day (e.g., jan12, feb08)
        match = re.search(
            r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)(\d{1,2})",
            filename.lower(),
        )
        if match:
            month_str, day_str = match.groups()
            month = _MONTH_MAP[month_str]
            day = int(day_str)
            year = datetime.now().year
            try:
                date = datetime(year, month, day)
                if date > datetime.now():
                    date = datetime(year - 1, month, day)
                return date
            except ValueError:
                return None

        # Pattern: YYYYMMDD
        match = re.search(r"(\d{8})", filename)
        if match:
            try:
                return datetime.strptime(match.group(1), "%Y%m%d")
            except ValueError:
                return None

        return None

    @staticmethod
    def _extract_tickers_from_text(text: str) -> list[str]:
        """Extract known ticker symbols from text."""
        words = set(re.findall(r"\b[A-Z]{2,5}\b", text))
        return sorted(words & KNOWN_TICKERS)


# ------------------------------------------------------------------
# Singleton
# ------------------------------------------------------------------

_instance: UnifiedSearch | None = None


def get_unified_search() -> UnifiedSearch:
    """Return singleton UnifiedSearch instance."""
    global _instance
    if _instance is None:
        _instance = UnifiedSearch()
    return _instance


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    search = get_unified_search()
    stats = search.build_index()
    print("\n=== Unified Search Index Stats ===")
    for key, val in stats.items():
        print(f"  {key}: {val}")

    query = "iron condor risk"
    print(f"\n=== Search: '{query}' ===")
    results = search.search(query, top_k=10)
    print(f"Found {len(results)} results:")
    for r in results:
        print(
            f"  [{r['type']}] {r['id'][:60]} score={r['score']:.3f} kw={r['keyword_score']:.3f} meta={r['metadata_score']:.3f}"
        )
        print(f"    Title: {r['title'][:80]}")
