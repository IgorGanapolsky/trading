# Advanced AI Training Syllabus (2025 Era)

> **Addendum to Standard Syllabus**
> Focus: Transformers for Time-Series, Agentic RAG, and Structured Alpha

---

## 1. Advanced Machine Learning (State-of-the-Art)

The industry has moved from LSTM/GRU to **Transformers** and **Foundation Models** for time-series.

### Architecture Upgrades
*   **TimeMixer:** Decomposable Multiscale Mixing. Essential for handling tick data + daily bars simultaneously.
    *   *Action:* Replace standard MLP forecasters with a TimeMixer implementation.
*   **MOMENT:** The "GPT-4 of Time Series".
    *   *Action:* Fine-tune a pre-trained open-source Time-Series Foundation Model instead of training from scratch.
*   **Generative Data Augmentation (Fin-GAN):**
    *   *Action:* Use GANs to generate "synthetic crashes" to stress-test your RL agent (training on only history is insufficient).

### Resources to Ingest
| Title | Type | Key Concept | Priority |
|-------|------|-------------|----------|
| "TimeMixer: Decomposable Multiscale Mixing" | Paper (ICLR 2024) | Multi-scale forecasting | HIGH |
| "MOMENT: Open Time-series Foundation Models" | Paper (ICML 2024) | Foundation models | HIGH |
| "Deep Hedging" (JP Morgan) | Paper | RL for Options Risk | HIGH |

---

## 2. Agentic RAG (Next-Gen Retrieval)

Standard RAG retrieves text. **Agentic RAG** retrieves *tools* and *logic*.

### New Components
*   **Multi-HyDE (Hypothetical Document Embeddings):**
    *   *Logic:* Agent generates a *fake* ideal financial report, then searches vector DB for the closest *real* match. drastic improvement over keyword search.
*   **Self-RAG:**
    *   *Logic:* The model critiques its own retrieved documents *before* answering. "Is this document actually relevant to the user's question about bond duration?"

### Data Schemas (The "Missing Link")
Ingest these **technical docs** so the agent understands its own tools:
1.  **OpenBB Platform Docs:** The manual for your data pipeline.
2.  **DeFiLlama API Schemas:** For crypto TVL/Yield analysis.
3.  **IBKR Flex Query Reference:** For understanding trade execution reports.

---

## 3. Domain-Specific "Alpha" Knowledge

### Options & Volatility (Advanced)
*   **"Physics-informed Convolutional Transformer for Volatility"** (2024): Moves beyond Black-Scholes.
*   **Nansen "Smart Money" Labels:** Learn to classify wallet behaviors (e.g., "Whale", "Fund", "Bot").

### Macro & Bonds
*   **Fed Reserve "FEDS Notes":** High-signal technical notes (better than news).
*   **ISDA Master Agreement Definitions:** For complex derivatives structure.

### Crypto Alpha (New Dec 2025)
*   **Master The Crypto - Trading Guide:** Comprehensive guide on market cycles and technicals.
*   **Strategy Videos (Transcripts):**
    *   "How to trade crypto in 2025" (Video ID: _OqVDO99YVM)
    *   "Advanced Altcoin Flipping" (Video ID: hlvf6TXAFfo)

---

## Implementation Checklist

- [ ] **Scrape** OpenBB & DeFiLlama API docs -> `rag_knowledge/docs/`
- [ ] **Download** TimeMixer & MOMENT papers -> `rag_knowledge/papers/`
- [ ] **Upgrade** `rag_store/retriever.py` to support **Multi-HyDE** query expansion.
- [ ] **Prototype** a `src/ml/models/time_mixer.py` to replace the NumPy MLP.

*Created: 2025-12-07*
