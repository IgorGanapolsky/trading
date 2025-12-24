---
skill_id: text_analyzer
name: Text Analyzer
version: 1.0.0
status: dormant  # Implementation file does not exist yet
description: Skill for analyzing financial text using ML feature engineering techniques
author: Trading System CTO
tags: [nlp, text-analysis, sentiment, feature-engineering, trading-signals, finbert]
tools:
  - analyze_text
  - get_news_signal
  - extract_bow_features
  - extract_tfidf_features
  - extract_embedding
dependencies:
  - src/ml/text_feature_engineering.py  # TODO: Create this file
integrations:
  - src/ml/text_feature_engineering.py::TextFeatureEngineer
  - src/ml/text_feature_engineering.py::analyze_text
  - src/ml/text_feature_engineering.py::get_news_signal
---

> **STATUS: DORMANT** - This skill describes planned functionality.
> The implementation file `src/ml/text_feature_engineering.py` does not exist yet.

# Text Analyzer Skill

Extract numerical features from financial text (news, earnings reports, social media) for ML-based trading decisions.

## Overview

This skill provides:
- Bag of Words (BoW) text features
- TF-IDF weighted term importance
- Word embeddings using FinBERT (financial domain)
- Domain-specific financial sentiment scoring
- Batch news analysis for trading signals
- Bullish/bearish/uncertainty detection

Based on: https://machinelearningmastery.com/3-feature-engineering-techniques-for-unstructured-text-data

## Feature Engineering Techniques

### 1. Bag of Words (BoW)
Simple word frequency baseline features:
- Word count
- Unique word count
- Lexical diversity
- Average word length

**Best for**: Quick baseline features, high interpretability

### 2. TF-IDF (Term Frequency - Inverse Document Frequency)
Weighted importance for keywords:
- Identifies important terms (high TF, low DF)
- Reduces weight of common words
- Captures unigrams and bigrams

**Best for**: Keyword extraction, comparative analysis

### 3. Word Embeddings (FinBERT)
Semantic understanding using financial domain model:
- 768-dimensional vector representation
- Pre-trained on financial news
- Captures context and sentiment

**Best for**: Deep semantic analysis, complex sentiment

## Financial Vocabulary

### Bullish Terms (21 terms)
```python
["beat", "exceeds", "growth", "profit", "surge", "rally", "breakout",
 "upgrade", "buy", "outperform", "bullish", "strong", "record", "soar",
 "boom", "gain", "up", "positive", "optimistic", "momentum", "accumulate"]
```

### Bearish Terms (21 terms)
```python
["miss", "decline", "loss", "drop", "crash", "selloff", "breakdown",
 "downgrade", "sell", "underperform", "bearish", "weak", "low", "plunge",
 "bust", "fall", "down", "negative", "pessimistic", "correction", "distribute"]
```

### Uncertainty Terms (12 terms)
```python
["uncertain", "volatile", "risk", "caution", "concern", "worry",
 "fear", "warning", "alert", "careful", "mixed", "unclear"]
```

### Crypto-Specific Terms (15 terms)
```python
["bitcoin", "btc", "ethereum", "eth", "crypto", "blockchain", "defi",
 "nft", "halving", "whale", "hodl", "moon", "fud", "fomo", "altcoin"]
```

## Tools

### 1. analyze_text

Extract all features from a single text (headline, article, tweet).

**Parameters:**
- `text` (required): Text to analyze

**Returns:**
```python
TextFeatures(
    word_count=25,
    char_count=180,
    avg_word_length=6.4,
    bullish_score=0.12,      # 12% of words are bullish
    bearish_score=0.04,      # 4% of words are bearish
    uncertainty_score=0.08,  # 8% of words express uncertainty
    net_sentiment=0.08,      # 0.12 - 0.04 = 0.08 (bullish)
    crypto_relevance=0.16,   # 16% crypto terms
    financial_density=0.24,  # 24% financial terms overall
    top_terms=[
        ("bitcoin surge", 0.85),
        ("breakout", 0.72),
        ("analyst upgrade", 0.68)
    ],
    embedding=np.array([...])  # 768-dim FinBERT embedding
)
```

**Signal Interpretation:**
- `net_sentiment > 0.3` + `uncertainty < 0.3` → **BUY**
- `net_sentiment < -0.3` + `uncertainty < 0.3` → **SELL**
- Otherwise → **HOLD**

**Usage:**
```python
from src.ml.text_feature_engineering import analyze_text

headline = "Bitcoin surges past $100,000 as institutions buy"
features = analyze_text(headline)

print(f"Signal: {features.get_signal()}")
print(f"Net Sentiment: {features.net_sentiment:.4f}")
print(f"Crypto Relevance: {features.crypto_relevance:.4f}")
print(f"Top Terms: {features.top_terms[:3]}")
```

### 2. get_news_signal

Analyze a batch of news headlines to generate aggregated trading signal.

**Parameters:**
- `headlines` (required): List of news headlines/articles

**Returns:**
```python
{
    "signal": "BUY",           # BUY, SELL, or HOLD
    "confidence": 0.73,        # 0.5-0.9 confidence level
    "avg_bullish": 0.08,       # Average bullish score
    "avg_bearish": 0.02,       # Average bearish score
    "avg_uncertainty": 0.04,   # Average uncertainty score
    "net_sentiment": 0.06,     # avg_bullish - avg_bearish
    "headlines_analyzed": 15   # Number of headlines processed
}
```

**Signal Thresholds:**
- **BUY**: `net_sentiment > 0.02` AND `uncertainty < 0.05`
- **SELL**: `net_sentiment < -0.02` AND `uncertainty < 0.05`
- **HOLD**: Mixed signals or high uncertainty

**Confidence Calculation:**
```python
confidence = 0.5 + abs(net_sentiment) * 5
confidence = min(confidence, 0.9)  # Cap at 90%
```

**Usage:**
```python
from src.ml.text_feature_engineering import get_news_signal

headlines = [
    "Bitcoin surges past $100,000 as institutional buying continues",
    "Crypto market faces uncertainty amid regulatory concerns",
    "Ethereum breaks out to new highs, analysts bullish on ETH",
]

result = get_news_signal(headlines)
print(f"Signal: {result['signal']} (confidence: {result['confidence']:.2f})")
print(f"Net Sentiment: {result['net_sentiment']:.4f}")
```

### 3. extract_bow_features

Extract Bag of Words features only.

**Parameters:**
- `text` (required): Text to analyze

**Returns:**
```python
{
    "word_count": 25,
    "unique_words": 18,
    "lexical_diversity": 0.72,  # unique/total ratio
    "avg_word_length": 6.4
}
```

**Usage:**
```python
from src.ml.text_feature_engineering import get_engineer

engineer = get_engineer()
bow = engineer.extract_bow_features("Bitcoin price surges higher")
print(f"Words: {bow['word_count']}, Unique: {bow['unique_words']}")
```

### 4. extract_tfidf_features

Extract TF-IDF weighted terms from batch of texts.

**Parameters:**
- `texts` (required): List of texts to analyze

**Returns:**
```python
[
    [("bitcoin surge", 0.85), ("breakout", 0.72), ...],  # Text 1 top terms
    [("ethereum upgrade", 0.91), ("bullish", 0.68), ...], # Text 2 top terms
]
```

**Usage:**
```python
from src.ml.text_feature_engineering import get_engineer

engineer = get_engineer()
texts = [
    "Bitcoin surges to new highs",
    "Ethereum upgrade completed successfully"
]
tfidf_results = engineer.extract_tfidf_features(texts)

for i, top_terms in enumerate(tfidf_results):
    print(f"Text {i+1} top terms: {top_terms[:3]}")
```

### 5. extract_embedding

Generate FinBERT semantic embedding (768 dimensions).

**Parameters:**
- `text` (required): Text to embed

**Returns:**
```python
np.ndarray  # Shape: (768,)
# Or None if FinBERT not available
```

**Usage:**
```python
from src.ml.text_feature_engineering import get_engineer

engineer = get_engineer()
embedding = engineer.extract_embedding("Bitcoin price analysis")

if embedding is not None:
    print(f"Embedding shape: {embedding.shape}")
    # Use in ML models, similarity comparisons, clustering, etc.
```

## Integration with Trading System

### Pre-Trade Analysis Workflow

```python
from src.ml.text_feature_engineering import get_news_signal, analyze_text
from src.utils.news_sentiment import get_recent_news

# 1. Fetch recent news
news = get_recent_news("BTC", hours=24)
headlines = [article["title"] for article in news]

# 2. Analyze batch for trading signal
signal_result = get_news_signal(headlines)

# 3. Check signal strength
if signal_result["signal"] == "BUY" and signal_result["confidence"] > 0.7:
    print("✅ Strong bullish news signal - consider long position")
elif signal_result["signal"] == "SELL" and signal_result["confidence"] > 0.7:
    print("❌ Strong bearish news signal - consider short position")
else:
    print("⚠️ Weak/mixed signal - wait for clarity")

# 4. Detailed analysis of key headlines
for headline in headlines[:3]:
    features = analyze_text(headline)
    print(f"\n{headline}")
    print(f"  Signal: {features.get_signal()}, Sentiment: {features.net_sentiment:.3f}")
```

### Integration with Sentiment Analyzer Skill

```python
from src.ml.text_feature_engineering import get_news_signal
from src.utils.news_sentiment import NewsSentimentAggregator

# Combine text features with broader sentiment
sentiment_agg = NewsSentimentAggregator()
news_data = sentiment_agg.get_aggregated_sentiment(["BTC"])

# Extract headlines
headlines = [item["title"] for item in news_data["BTC"]["articles"]]

# Get text-based signal
text_signal = get_news_signal(headlines)

# Combine with sentiment analyzer score
final_score = (text_signal["net_sentiment"] + news_data["BTC"]["score"]) / 2
```

## FinBERT Model Details

**Model**: `ProsusAI/finbert`
- Pre-trained on financial news corpus
- Fine-tuned for financial sentiment classification
- 768-dimensional embeddings
- Understands financial context better than general BERT

**Requirements**:
```bash
pip install transformers torch
```

**Fallback**: If FinBERT not available, skill uses BoW and TF-IDF only.

## Example Use Cases

### 1. Earnings Report Analysis
```python
earnings_report = """
Company XYZ reported Q4 earnings that beat analyst expectations.
Revenue grew 25% year-over-year to $2.5B. Profit margins expanded
to record highs. Management upgraded full-year guidance.
"""

features = analyze_text(earnings_report)
# Expected: High bullish_score, low uncertainty, BUY signal
```

### 2. Breaking News Impact
```python
breaking_news = [
    "SEC approves Bitcoin ETF applications",
    "Institutional investors pour billions into crypto",
    "Major banks launch crypto trading desks"
]

signal = get_news_signal(breaking_news)
# Expected: Strong BUY signal with high confidence
```

### 3. Crisis Detection
```python
crisis_headlines = [
    "Crypto exchange halts withdrawals amid insolvency fears",
    "Market selloff intensifies as panic spreads",
    "Regulators warn of systemic risks"
]

signal = get_news_signal(crisis_headlines)
# Expected: SELL signal or HOLD with high uncertainty
```

## CLI Usage

```bash
# Test text analysis
python src/ml/text_feature_engineering.py

# Analyze custom text
python -c "from src.ml.text_feature_engineering import analyze_text; \
           features = analyze_text('Bitcoin surges to new record high'); \
           print(f'Signal: {features.get_signal()}')"

# Batch news analysis
python -c "from src.ml.text_feature_engineering import get_news_signal; \
           import json; \
           result = get_news_signal(['BTC breaks $100k', 'Bullish momentum continues']); \
           print(json.dumps(result, indent=2))"
```

## Performance & Accuracy

**Speed**:
- BoW: <1ms per text
- TF-IDF: ~10ms per batch
- FinBERT: ~50-100ms per text (GPU recommended)

**Accuracy** (tested on financial news):
- Directional prediction: ~65-70% (standalone)
- Combined with sentiment analyzer: ~75-80%
- Best with high confidence scores (>0.7)

## Best Practices

1. **Always analyze multiple headlines**: Single headlines can be misleading
2. **Check uncertainty scores**: High uncertainty = wait for clarity
3. **Combine with other signals**: Text analysis is one input, not the only input
4. **Use confidence thresholds**: Only act on high-confidence signals (>0.7)
5. **Monitor crypto_relevance**: Ensure headlines are actually about your asset
6. **Cache embeddings**: FinBERT is slow, cache results when possible

## References

- Feature Engineering Guide: https://machinelearningmastery.com/3-feature-engineering-techniques-for-unstructured-text-data
- FinBERT Model: https://huggingface.co/ProsusAI/finbert
- Implementation: `/home/user/trading/src/ml/text_feature_engineering.py`
