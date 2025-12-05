# AI Training Materials Syllabus

> Curated materials for improving RAG retrieval and ML pipeline for algorithmic trading.

---

## How to Use This Syllabus

1. **Ingest** each resource into your RAG system with proper metadata tags
2. **Chunk** by section/heading boundaries (not arbitrary token counts)
3. **Tag** with `domain`, `asset_class`, `difficulty`, `source_type`
4. **Eval** - create Q&A pairs from each resource to test retrieval quality

---

## 1. Algorithmic Trading Foundations

### Books (High Priority - Full Ingestion)

| Title | Author | Why It Matters | RAG Tags |
|-------|--------|----------------|----------|
| **Quantitative Trading** | Ernest Chan | End-to-end quant workflow: idea → backtest → deploy | `domain=quant`, `phase=design` |
| **Algorithmic Trading: Winning Strategies** | Ernest Chan | Practical edges, mean reversion, momentum | `domain=quant`, `strategy=momentum` |
| **Building Winning Algorithmic Trading Systems** | Kevin Davey | Overfitting avoidance, walk-forward testing | `domain=quant`, `phase=backtest` |
| **Trading and Exchanges** | Larry Harris | Market microstructure, order types, execution | `domain=execution`, `phase=live` |
| **Advances in Financial ML** | Marcos Lopez de Prado | ML-specific: triple barrier, metalabeling, purged CV | `domain=ml`, `difficulty=advanced` |

### Papers (Chunk into RAG)

| Paper | Source | Key Concepts | RAG Tags |
|-------|--------|--------------|----------|
| "A Survey of Deep Learning for Quantitative Trading" | arXiv | RL for trading, feature engineering | `domain=ml`, `model=rl` |
| "Deep Reinforcement Learning for Trading" | Zhengyao Jiang et al. | Policy gradient for portfolio management | `domain=ml`, `model=rl` |
| "Momentum Strategies in Commodity Futures" | AQR | Cross-sectional momentum, time-series momentum | `strategy=momentum`, `asset=futures` |

### YouTube (Transcribe → Ingest)

| Channel/Video | Content | RAG Tags |
|---------------|---------|----------|
| Coding Jesus - "Algorithmic Trading Python" series | Full backtest implementations | `domain=quant`, `code=python` |
| QuantPy - "Building Trading Systems" | Data pipelines, vectorized backtesting | `domain=quant`, `phase=backtest` |
| Sentdex - "Python for Finance" | Practical Python for markets | `domain=quant`, `code=python` |

---

## 2. Options Trading & Volatility

### Books

| Title | Author | Why It Matters | RAG Tags |
|-------|--------|----------------|----------|
| **Volatility Trading** | Euan Sinclair | Vol surfaces, variance premium, practical edges | `asset=options`, `concept=volatility` |
| **Option Volatility and Pricing** | Sheldon Natenberg | Greeks, spreads, risk management | `asset=options`, `difficulty=intermediate` |
| **The Volatility Smile** | Emanuel Derman | Smile dynamics, local vol, stochastic vol | `asset=options`, `difficulty=advanced` |

### Key Concepts to Extract

```
Greeks: delta, gamma, theta, vega, rho
Strategies: covered calls, iron condors, straddles, strangles, spreads
Vol concepts: implied vs realized, VIX, term structure, skew
Risk: max loss, margin requirements, assignment risk
```

### Online Resources

| Source | Content | RAG Tags |
|--------|---------|----------|
| tastytrade.com/learn | Options mechanics, strategy videos | `asset=options`, `source=video` |
| CBOE options education | Official exchange materials | `asset=options`, `source=official` |
| r/thetagang wiki | Income strategies, wheel strategy | `asset=options`, `strategy=income` |

---

## 3. Dividend Investing & Income

### Books

| Title | Author | Why It Matters | RAG Tags |
|-------|--------|----------------|----------|
| **The Single Best Investment** | Lowell Miller | Dividend growth investing fundamentals | `strategy=dividend`, `income=true` |
| **Get Rich with Dividends** | Marc Lichtenfeld | 10-11-12 system, dividend safety | `strategy=dividend`, `income=true` |

### Key Metrics to Train On

```
Payout Ratio: dividends / earnings (< 60% generally safe)
Dividend Growth Rate: 5-year CAGR
Dividend Yield: annual dividend / price
Dividend Safety Score: coverage, debt levels, earnings stability
Dividend Aristocrats: 25+ years consecutive increases
```

### Data Sources for RAG

| Source | What to Ingest | RAG Tags |
|--------|----------------|----------|
| Dividend.com | Dividend history, safety scores | `strategy=dividend`, `data=fundamentals` |
| Seeking Alpha dividend articles | Analysis, coverage ratios | `strategy=dividend`, `source=analysis` |
| S&P Dividend Aristocrats list | Annual updates, criteria | `strategy=dividend`, `universe=aristocrats` |

---

## 4. REITs (Real Estate Investment Trusts)

### Key Metrics to Train On

```
FFO (Funds From Operations): net income + depreciation - gains on sales
AFFO (Adjusted FFO): FFO - recurring capex
NAV (Net Asset Value): property value - liabilities
Cap Rate: NOI / property value
Dividend Yield: vs sector average
Debt/EBITDA: leverage ratio
Occupancy Rate: % leased
```

### REIT Sectors

```
Residential: apartments, single-family rentals
Retail: malls, shopping centers, net lease
Office: urban, suburban, medical office
Industrial: warehouses, logistics, data centers
Healthcare: hospitals, senior housing, skilled nursing
Specialty: cell towers, timber, prisons, casinos
```

### Resources

| Source | Content | RAG Tags |
|--------|---------|----------|
| Nareit.com | REIT fundamentals, sector reports | `asset=reit`, `source=official` |
| The Motley Fool REIT guides | Beginner-friendly REIT analysis | `asset=reit`, `difficulty=beginner` |
| Brad Thomas (iREIT) | Detailed REIT coverage | `asset=reit`, `source=analysis` |

---

## 5. Bonds & Treasuries

### Key Concepts to Train On

```
Duration: price sensitivity to interest rate changes
Convexity: curvature of price/yield relationship
Yield Curve: term structure (normal, inverted, flat)
Credit Spread: yield above risk-free rate
YTM (Yield to Maturity): total expected return
Current Yield: annual coupon / price
```

### Treasury Products

```
T-Bills: < 1 year, zero coupon, discount
T-Notes: 2-10 years, semi-annual coupon
T-Bonds: 20-30 years, semi-annual coupon
TIPS: inflation-protected, real yield
I-Bonds: inflation-indexed savings bonds
```

### Resources

| Source | Content | RAG Tags |
|--------|---------|----------|
| TreasuryDirect.gov | Official Treasury info | `asset=bonds`, `source=official` |
| PIMCO bond basics | Institutional-quality bond education | `asset=bonds`, `difficulty=intermediate` |
| Bogleheads bond forum | Practical bond allocation discussions | `asset=bonds`, `source=community` |

---

## 6. Crypto & Digital Assets

### Key Concepts

```
Market Structure: CEX vs DEX, order books, AMMs
Yield Sources: staking, lending, liquidity provision
Risks: smart contract, counterparty, regulatory, impermanent loss
Metrics: TVL, trading volume, gas fees, funding rates
```

### Resources (Curate Carefully - High Noise)

| Source | Content | RAG Tags |
|--------|---------|----------|
| Messari research | Institutional-grade crypto research | `asset=crypto`, `source=research` |
| The Block research | Data-driven crypto analysis | `asset=crypto`, `source=research` |
| Bankless newsletter | DeFi strategies, yield farming | `asset=crypto`, `strategy=defi` |
| CoinSnacks newsletter | Weekly crypto digest (already integrated) | `asset=crypto`, `source=newsletter` |

### Warning: Filter Aggressively

- Avoid: hype pieces, moon predictions, influencer content
- Keep: research reports, protocol documentation, risk analyses

---

## 7. RAG & ML Pipeline Improvement

### Papers for RAG Architecture

| Paper | Key Takeaway | Implementation |
|-------|--------------|----------------|
| "Retrieval-Augmented Generation for Knowledge-Intensive NLP" | RAG fundamentals | Baseline architecture |
| "ColBERT: Efficient and Effective Passage Search" | Late interaction retrieval | Better retrieval quality |
| "HyDE: Precise Zero-Shot Dense Retrieval" | Hypothetical document embeddings | Query expansion |
| "Self-RAG: Learning to Retrieve, Generate, and Critique" | Self-reflective retrieval | Quality control |

### Financial NLP Resources

| Resource | Content | Use Case |
|----------|---------|----------|
| FinBERT model | Pre-trained financial sentiment | Sentiment classification |
| SEC-BERT | 10-K/10-Q understanding | Document parsing |
| BloombergGPT paper | Finance-specific LLM design | Architecture ideas |

### Chunking Strategies for Financial Docs

```python
# Recommended chunking approach for financial documents
CHUNK_STRATEGIES = {
    "10-K filings": {
        "method": "section_aware",
        "boundaries": ["Item 1", "Item 7", "Item 8"],
        "overlap": 100
    },
    "research_papers": {
        "method": "heading_based",
        "min_chunk": 200,
        "max_chunk": 1000
    },
    "earnings_transcripts": {
        "method": "speaker_turns",
        "include_context": True
    },
    "news_articles": {
        "method": "paragraph",
        "max_chunk": 500
    }
}
```

---

## 8. Evaluation Framework

### Create These Eval Sets from Your Materials

| Domain | Sample Questions | Expected Behavior |
|--------|------------------|-------------------|
| Quant | "What's the difference between walk-forward and k-fold CV for backtesting?" | Explain purged cross-validation, lookahead bias |
| Options | "Calculate the max loss on a 100/105 call spread" | Show calculation, explain defined risk |
| Dividends | "Is a 90% payout ratio sustainable?" | Discuss earnings coverage, sector norms |
| REITs | "Why is FFO more important than net income for REITs?" | Explain depreciation treatment |
| Bonds | "What happens to bond prices when rates rise?" | Explain inverse relationship, duration |
| Crypto | "What's impermanent loss in an AMM?" | Explain LP mechanics, when IL occurs |

### Retrieval Quality Metrics

```python
# Track these metrics after each RAG update
EVAL_METRICS = {
    "recall@5": "% of relevant docs in top 5",
    "precision@5": "% of top 5 that are relevant",
    "mrr": "mean reciprocal rank of first relevant doc",
    "answer_relevance": "LLM-judged answer quality 1-5",
    "hallucination_rate": "% of claims not grounded in retrieved docs"
}
```

---

## 9. Ingestion Priority Order

### Phase 1: Core (Week 1)
1. Ernest Chan - Quantitative Trading (full book)
2. Marcos Lopez de Prado - key chapters on ML for finance
3. FinBERT model + financial NLP papers

### Phase 2: Asset Classes (Week 2-3)
4. Options: Natenberg basics + tastytrade videos
5. Dividends: Key metrics + Dividend.com data
6. REITs: Nareit guides + sector primers
7. Bonds: Treasury basics + duration concepts

### Phase 3: Advanced (Week 4+)
8. Advanced ML papers (Self-RAG, ColBERT)
9. Crypto research (Messari, The Block)
10. Earnings transcripts and 10-K filings

---

## 10. Metadata Schema for RAG

```json
{
  "document_id": "uuid",
  "title": "string",
  "source_type": "book|paper|video|article|filing|newsletter",
  "domain": "quant|options|dividend|reit|bonds|crypto|ml",
  "asset_class": "equity|options|reit|bond|treasury|crypto|etf",
  "strategy": "momentum|mean_reversion|income|growth|arbitrage",
  "difficulty": "beginner|intermediate|advanced",
  "phase": "research|design|backtest|live|risk",
  "date_published": "YYYY-MM-DD",
  "date_ingested": "YYYY-MM-DD",
  "chunk_method": "section|heading|paragraph|fixed",
  "quality_score": 1-5
}
```

---

## Summary

| Domain | Top 3 Resources | Priority |
|--------|-----------------|----------|
| **Algo Trading** | Chan books, Lopez de Prado, Davey | HIGH |
| **Options** | Natenberg, Sinclair, tastytrade | HIGH |
| **Dividends** | Lichtenfeld, Dividend.com, Aristocrats list | MEDIUM |
| **REITs** | Nareit, Brad Thomas, REIT primers | MEDIUM |
| **Bonds** | TreasuryDirect, PIMCO basics, Bogleheads | MEDIUM |
| **Crypto** | Messari, The Block, CoinSnacks | LOW (high noise) |
| **RAG/ML** | FinBERT, RAG papers, ColBERT | HIGH |

---

*Last Updated: 2025-12-04*
*Next Review: After Phase 1 ingestion complete*
