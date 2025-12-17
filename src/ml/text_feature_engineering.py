"""
Text Feature Engineering for Trading Signals
Based on: machinelearningmastery.com/3-feature-engineering-techniques-for-unstructured-text-data

Converts financial news, earnings reports, and social media into
numerical features for ML trading models.

Techniques:
1. Bag of Words (BoW) - Word frequency baseline
2. TF-IDF - Weighted importance for keywords
3. Word Embeddings - Semantic understanding (FinBERT for finance)
"""

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Optional

import numpy as np

logger = logging.getLogger(__name__)

# Financial vocabulary for domain-specific features
BULLISH_TERMS = [
    "beat",
    "exceeds",
    "growth",
    "profit",
    "surge",
    "rally",
    "breakout",
    "upgrade",
    "buy",
    "outperform",
    "bullish",
    "strong",
    "record",
    "soar",
    "boom",
    "gain",
    "up",
    "positive",
    "optimistic",
    "momentum",
    "accumulate",
]

BEARISH_TERMS = [
    "miss",
    "decline",
    "loss",
    "drop",
    "crash",
    "selloff",
    "breakdown",
    "downgrade",
    "sell",
    "underperform",
    "bearish",
    "weak",
    "low",
    "plunge",
    "bust",
    "fall",
    "down",
    "negative",
    "pessimistic",
    "correction",
    "distribute",
]

UNCERTAINTY_TERMS = [
    "uncertain",
    "volatile",
    "risk",
    "caution",
    "concern",
    "worry",
    "fear",
    "warning",
    "alert",
    "careful",
    "mixed",
    "unclear",
]


@dataclass
class TextFeatures:
    """Extracted features from text"""

    # Basic stats
    word_count: int
    char_count: int
    avg_word_length: float

    # Sentiment scores
    bullish_score: float
    bearish_score: float
    uncertainty_score: float
    net_sentiment: float  # bullish - bearish

    # Domain-specific
    financial_density: float  # % of financial terms

    # TF-IDF top terms
    top_terms: list[tuple[str, float]]

    # Embedding (if available)
    embedding: Optional[np.ndarray] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "word_count": self.word_count,
            "char_count": self.char_count,
            "avg_word_length": self.avg_word_length,
            "bullish_score": self.bullish_score,
            "bearish_score": self.bearish_score,
            "uncertainty_score": self.uncertainty_score,
            "net_sentiment": self.net_sentiment,
            "financial_density": self.financial_density,
            "top_terms": self.top_terms,
        }

    def get_signal(self) -> str:
        """Convert features to trading signal"""
        if self.net_sentiment > 0.3 and self.uncertainty_score < 0.3:
            return "BUY"
        elif self.net_sentiment < -0.3 and self.uncertainty_score < 0.3:
            return "SELL"
        else:
            return "HOLD"


class TextFeatureEngineer:
    """
    Extracts numerical features from financial text for ML models.
    """

    def __init__(self):
        self.tfidf_vectorizer = None
        self.embedding_model = None
        self._init_tfidf()
        self._init_embeddings()

    def _init_tfidf(self):
        """Initialize TF-IDF vectorizer"""
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer

            self.tfidf_vectorizer = TfidfVectorizer(
                max_features=1000,
                stop_words="english",
                ngram_range=(1, 2),  # Unigrams and bigrams
                min_df=1,
                max_df=0.95,
            )
            logger.info("✅ TF-IDF vectorizer initialized")
        except ImportError:
            logger.warning("⚠️ sklearn not available for TF-IDF")

    def _init_embeddings(self):
        """Initialize embedding model (FinBERT for financial text)"""
        try:
            import torch  # noqa: F401 - required by transformers
            from transformers import AutoModel, AutoTokenizer

            # Use FinBERT for financial sentiment
            model_name = "ProsusAI/finbert"
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            self.embedding_model = AutoModel.from_pretrained(model_name)
            self.embedding_model.eval()
            logger.info("✅ FinBERT embedding model loaded")
        except ImportError:
            logger.warning("⚠️ transformers not available for embeddings")
        except Exception as e:
            logger.warning(f"⚠️ Could not load FinBERT: {e}")

    def preprocess(self, text: str) -> str:
        """Clean and normalize text"""
        # Lowercase
        text = text.lower()
        # Remove URLs
        text = re.sub(r"http\S+|www\S+", "", text)
        # Remove special characters but keep financial symbols
        text = re.sub(r"[^\w\s$%.]", " ", text)
        # Remove extra whitespace
        text = " ".join(text.split())
        return text

    def _count_terms(self, words: list[str], term_list: list[str]) -> int:
        """Count occurrences of terms from a list"""
        return sum(1 for word in words if word in term_list)

    def extract_bow_features(self, text: str) -> dict[str, float]:
        """
        Technique 1: Bag of Words
        Simple word frequency features
        """
        text = self.preprocess(text)
        words = text.split()
        word_count = len(words)

        if word_count == 0:
            return {"word_count": 0, "unique_words": 0, "lexical_diversity": 0}

        unique_words = len(set(words))

        return {
            "word_count": word_count,
            "unique_words": unique_words,
            "lexical_diversity": unique_words / word_count,
            "avg_word_length": sum(len(w) for w in words) / word_count,
        }

    def extract_tfidf_features(self, texts: list[str]) -> list[list[tuple[str, float]]]:
        """
        Technique 2: TF-IDF
        Weighted term importance
        """
        if not self.tfidf_vectorizer or not texts:
            return [[] for _ in texts]

        try:
            # Fit and transform
            processed = [self.preprocess(t) for t in texts]
            tfidf_matrix = self.tfidf_vectorizer.fit_transform(processed)
            feature_names = self.tfidf_vectorizer.get_feature_names_out()

            results = []
            for i in range(tfidf_matrix.shape[0]):
                row = tfidf_matrix[i].toarray().flatten()
                # Get top 10 terms
                top_indices = row.argsort()[-10:][::-1]
                top_terms = [(feature_names[j], float(row[j])) for j in top_indices if row[j] > 0]
                results.append(top_terms)

            return results
        except Exception as e:
            logger.error(f"TF-IDF error: {e}")
            return [[] for _ in texts]

    def extract_embedding(self, text: str) -> Optional[np.ndarray]:
        """
        Technique 3: Word Embeddings (FinBERT)
        Semantic understanding of financial text
        """
        if not self.embedding_model:
            return None

        try:
            import torch

            # Tokenize
            inputs = self.tokenizer(
                text[:512],  # FinBERT max length
                return_tensors="pt",
                truncation=True,
                padding=True,
            )

            # Get embeddings
            with torch.no_grad():
                outputs = self.embedding_model(**inputs)
                # Use [CLS] token embedding
                embedding = outputs.last_hidden_state[:, 0, :].numpy().flatten()

            return embedding
        except Exception as e:
            logger.error(f"Embedding error: {e}")
            return None

    def extract_financial_features(self, text: str) -> dict[str, float]:
        """Extract domain-specific financial features"""
        text = self.preprocess(text)
        words = text.split()
        word_count = max(len(words), 1)

        bullish_count = self._count_terms(words, BULLISH_TERMS)
        bearish_count = self._count_terms(words, BEARISH_TERMS)
        uncertainty_count = self._count_terms(words, UNCERTAINTY_TERMS)

        total_financial = bullish_count + bearish_count + uncertainty_count

        return {
            "bullish_score": bullish_count / word_count,
            "bearish_score": bearish_count / word_count,
            "uncertainty_score": uncertainty_count / word_count,
            "net_sentiment": (bullish_count - bearish_count) / max(word_count, 1),
            "financial_density": total_financial / word_count,
        }

    def extract_all_features(self, text: str) -> TextFeatures:
        """Extract all features from text"""
        bow = self.extract_bow_features(text)
        financial = self.extract_financial_features(text)
        tfidf = self.extract_tfidf_features([text])[0] if text else []
        embedding = self.extract_embedding(text)

        return TextFeatures(
            word_count=bow["word_count"],
            char_count=len(text),
            avg_word_length=bow.get("avg_word_length", 0),
            bullish_score=financial["bullish_score"],
            bearish_score=financial["bearish_score"],
            uncertainty_score=financial["uncertainty_score"],
            net_sentiment=financial["net_sentiment"],
            financial_density=financial["financial_density"],
            top_terms=tfidf[:5],
            embedding=embedding,
        )

    def analyze_news_batch(self, headlines: list[str]) -> dict[str, Any]:
        """
        Analyze a batch of news headlines for trading signal.
        """
        if not headlines:
            return {"signal": "HOLD", "confidence": 0.5, "reason": "No headlines"}

        # Extract features from all headlines
        all_features = [self.extract_all_features(h) for h in headlines]

        # Aggregate sentiment
        avg_bullish = np.mean([f.bullish_score for f in all_features])
        avg_bearish = np.mean([f.bearish_score for f in all_features])
        avg_uncertainty = np.mean([f.uncertainty_score for f in all_features])
        net_sentiment = avg_bullish - avg_bearish

        # Determine signal
        if net_sentiment > 0.02 and avg_uncertainty < 0.05:
            signal = "BUY"
            confidence = min(0.5 + net_sentiment * 5, 0.9)
        elif net_sentiment < -0.02 and avg_uncertainty < 0.05:
            signal = "SELL"
            confidence = min(0.5 + abs(net_sentiment) * 5, 0.9)
        else:
            signal = "HOLD"
            confidence = 0.5

        return {
            "signal": signal,
            "confidence": confidence,
            "avg_bullish": avg_bullish,
            "avg_bearish": avg_bearish,
            "avg_uncertainty": avg_uncertainty,
            "net_sentiment": net_sentiment,
            "headlines_analyzed": len(headlines),
        }


# Singleton
_engineer = None


def get_engineer() -> TextFeatureEngineer:
    global _engineer
    if _engineer is None:
        _engineer = TextFeatureEngineer()
    return _engineer


def analyze_text(text: str) -> TextFeatures:
    """Quick function to analyze text"""
    return get_engineer().extract_all_features(text)


def get_news_signal(headlines: list[str]) -> dict[str, Any]:
    """Get trading signal from news headlines"""
    return get_engineer().analyze_news_batch(headlines)


if __name__ == "__main__":
    # Test the feature engineering
    logging.basicConfig(level=logging.INFO)

    test_headlines = [
        "Stock market breaks out to new highs, analysts bullish",
        "Market selloff continues as fear grips investors",
    ]

    engineer = get_engineer()

    print("=== Individual Analysis ===")
    for headline in test_headlines:
        features = engineer.extract_all_features(headline)
        print(f"\n'{headline[:50]}...'")
        print(f"  Signal: {features.get_signal()}")
        print(f"  Net Sentiment: {features.net_sentiment:.4f}")

    print("\n=== Batch Analysis ===")
    result = engineer.analyze_news_batch(test_headlines)
    print(json.dumps(result, indent=2))
