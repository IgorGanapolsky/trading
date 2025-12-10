# RAG & ML Knowledge Expansion (Dec 2025)

## Objective
Document the curated external materials that will enrich the trading system's RAG + ML pipeline: algorithmic trading, options/volatility, income investing (dividends/REITs/bonds), crypto, and retrieval-augmented generation design itself. Each resource is paired with ingestion guidance so the agent can turn it into new knowledge chunks and keep the vector store healthy.

## How to ingest
1. Save the raw text (PDF, blog post, transcript, etc.) under `rag_knowledge/raw/` and name it using the pattern `YYYYMMDD_source.slug.txt`.
2. Run `python3.11 scripts/ingest_rag_knowledge.py --sync` (use `TMPDIR=$(pwd)/tmp` on macOS if ONNXRuntime tries to write to `/private/var/…`).
3. Confirm the new chunk is present in `data/rag/chroma_db` and `data/rag/in_memory_store.json` if fallback is used.

### PDF ingestion automation
- Run `python3 scripts/download_pdf_sources.py --date 20251208` after adding new sources to the `PDF_SOURCES` list. The script downloads the public PDFs, converts them to plain text under `rag_knowledge/raw/20251208_<slug>.txt`, and can be re-run with `--force` when the upstream material refreshes.
- The new curated PDFs feed the RAG pipeline with up-to-date reference material covering:
  - Options foundations/hedge construction (`Options Trading for Beginners`, OptionsTrading.org, 2025).
  - REIT qualification and dividend rules (`Investor Bulletin: REITs`, SEC, 2023) so the agents can explain payout coverage and leverage limits when evaluating income candidates.
  - The agentic crypto playbook (`An Adaptive Multi-Agent Bitcoin Trading System`, ArXiv 2025) and the neural execution stack (`Neural Network-Based Algorithmic Trading Systems`, ArXiv 2025) so the RAG layer stays current with AI-driven trade automation.
  - Macro/liquidity context for the Treasury term structure (`International Banking and Nonbank Financial Intermediation`, New York Fed Staff Report 1091, 2024), giving the knowledge store the right vocabulary for duration/term premium narratives.
- After the script runs, add the new chunk file (`rag_knowledge/chunks/investment_playbooks_2025.json`) and update `rag_knowledge/knowledge_index.json` so the collector exposes the new strategies to the thesis generator.

> The ingestion script already loads every JSON file from `rag_knowledge/chunks/`. When adding a new chunk, mirror the format in existing files (source_type, content, topics, citation) so the metadata remains consistent.

## Source matrix
Each entry includes what to give the AI, why it matters, and how to capture it for ingestion.

### 1. Algorithmic & systematic trading
- **Book**: *Advances in Financial Machine Learning* by Marcos López de Prado (Wiley 2018). Focus on regime detection, combinatorial optimization, and backtest overfitting controls that the pipeline can translate into quantitative rules. Provide chapter-by-chapter notes or clipped PDFs (Chapters 2, 4, 5 especially).
- **Paper**: “Universal Portfolio Management” (Cover, 1991) and its modern reinterpretations (e.g., “Portfolio confiance” variants). These concise derivations of online portfolio selection help the ML agent understand regret minimization. Capture the formulae and conclusions as text.
- **Newsletter/Blog**: *Quantocracy* curated weekly best posts plus targeted articles from *QuantInsti Lab* covering statistical arbitrage and execution slippage. Export each post as markdown or plain text, include publication date and author for citation.

### 2. Options & volatility trading
- **Book**: *Options as a Strategic Investment* by Lawrence McMillan (Revised editions 2020+). The strategy tables for verticals, calendars, condors, and hedges help the model reason about real-world payoff shapes. Slice the PDF by strategy sections and annotate keywords (e.g., “debit spread: risk capped”).
- **Research report**: CBOE's monthly *Volatility Risk Premium* and *VIX futures term structure* notes. They contain metrics (roll yield, carry) that should be stored as numerical metadata. Include tables in CSV along with textual explanations.
- **Video transcript**: Clips from *Tastytrade* or *The Options Industry Council* webinars that demonstrate trade construction and volatility surface interpretation. Use the YouTube ingestion pipeline to capture transcripts, highlight greeks/vol mentions, and treat them as chunked evidence.

### 3. Dividend growth, REITs, and bonds Treasuries
- **Book**: *The Single Best Investment* by Lowell Miller (Dividend Growth). Summaries of the ranking system (dividend track record, payout ratio, valuation thresholds) become features for RAG reasoning. Convert the book’s dividend ranking criteria into structured chunks.
- **Regulatory report**: SEC/FINRA releases on REIT risk disclosures (e.g., 2024 Form 10-K commentary on leverage/capital adequacy). Provide relevant paragraphs plus bullet lists of key ratios.
- **Research paper**: NY Fed or FRED working papers on U.S. Treasury term structure control (e.g., “The Term Premium in U.S. Treasuries”). Extract definitions of “term premium,” “duration targeting,” etc., and add them as `topics`: [`treasury_yield`, `duration`, `term_premium`].
- **Behavioral finance companion**: *Money: Master the Game* by Tony Robbins (7-step audiobook). Capture the action plan for deciding to become an investor, constructing diversified buckets, building lifetime income, starting immediately, and using wealth as a force for gratitude and giving back. These chapters reinforce the mindset/values bucket that complements the quantitative income-tracking content above.
- **High-yield dividend playbook**: *High-Yield Dividend Strategies: Navigating Risk for Maximum Reward* by J. R. Glenn. Document the risk controls (sector diversification, payout ratio ceilings, debt/interest coverage limits), the actionable screening filters, and how to pair them with scenario stress tests. These rules help the RAG agent recommend when to prioritize high-yield vs growth/dividend/allocation buckets.
- **AI-assisted REIT playbook**: *How to Invest in REITs Using Free AI* by Ron Pekman. Extract the blueprint for using AI-based data gathering (public feeds, scraping REIT filings, projecting occupancy/capex), mapping those signals to dividend stability, and prioritizing low-cost automation for screening REITs. This shows the RAG agents how to link automation with REIT fundamentals, reinforcing the “AI + REIT” combo the trading desk runs daily.
- **Operational wealth playbook**: *Wealth Can’t Wait* by David Osborn and Paul Morris. It frames financial freedom as avoiding “seven wealth traps,” implementing seven business pillars (clarity, systems, marketing, operations, people, leverage, and giving), and running continuous life audits to keep cash flow aligned with values. Capture the trap/pillar lists plus the audit checkpoints so the RAG layer can surface them when we need behavioral-/process-oriented prompts.

### 4. Crypto & digital asset intelligence
- **Research**: Chainalysis *Crypto Crime Report* and *DeFi Adoption Reports* (2025). Tables/graphs explaining on-chain flows and compliance risk become evidence for sentiment signals. Convert to JSON summary with `source_type: report` and `topics: ["crypto_risk", "on_chain", "defi"]`.
- **Developer docs**: Ethereum/L2 Upgrade notes (Shanghai, Dencun, EigenLayer). Provide changelog text and highlight gas/consensus implications; these show the pipeline how protocol changes affect execution risk.
- **Podcast transcript**: *Unchained* interviews with macro/crypto investors about regulation and stablecoins. Use existing YouTube pipeline to capture transcripts so they automatically become ingestion source text.
- **Crypto acceleration dossier**: Bring in the freely available guides (Investopedia’s “Cryptocurrency Investment Guide,” “10 Rules of Investing in Crypto,” and “How to Invest in Crypto With Just $100”) plus the *Cryptocurrency Investing Guide* eBook (2019 Wiley) and the new AI-focused work-by principle coverage from Medien. Extract the trading rules, risk controls, data automation recipes, and beginner checklists so the RAG agents can recommend precise crypto entry/exit prompts. Save each cleaned PDF/text under `rag_knowledge/raw/` with the `YYYYMMDD_slug.txt` format before ingestion.
- **AI-first crypto playbook**: Add the curated summary at `rag_knowledge/raw/20251208_crypto_ai_investing.txt` plus the chunk file `rag_knowledge/chunks/crypto_ai_2025.json`. It bundles the actionable steps from *How to Invest in Crypto Using Free AI*, the beginner safeguards from Investopedia/Forbes, GPT-4 risk intelligence ideas, and the discipline principles from *The Only Crypto Investing Book You’ll Ever Need*. This new material keeps the vector store aware of free AI tooling (Pionex, Kryll, 3Commas, Stoic, Coinrule), the defensive guardrails (wallet hygiene, tax compliance, DCA, low leverage), and the multi-bucket strategy matrix, so the retrieval agent can push crypto as a high-priority, AI-augmented focus.

### 5. RAG / ML pipeline insights
- **Paper**: “PipeRAG: Fast retrieval-augmented generation via adaptive pipeline parallelism” (KDD 2025). Already in the chunks, but add follow-up reports or GitHub release notes describing your pipeline’s best practices (Chroma + SentenceTransformers + BM25). Capture them as `source_type: paper` or `source_type: doc` with `topics: ["rag_performance", "hybrid_search"]`.
- **Blog**: LangChain/Chroma/REST API best practices posts from late 2025 (look for “LLM Orchestration Patterns” or “Chroma 0.6 release notes”). Download the HTML or copy the cleaned text into `rag_knowledge/raw/` for ingestion.
- **Internal doc**: Document how `src/utils/pydantic_compat.py` should load before Chroma to avoid the BaseSettings guard. Convert the explanation into narrative and cite it in the new chunk so the RAG system knows to patch Pydantic before import.

## Execution support
1. Once your new documents (PDFs, markdown, transcripts) land in `rag_knowledge/raw/`, run the ingestion command shown earlier; it will parse every chunk and sync the Chroma store.
2. If chroma compilation tries to write to `/private/var/…`, always override `TMPDIR` to a workspace-local `tmp/` directory before running ingestion on macOS.
3. Re-run `python3.11 -m pip check` after adding any new dependency to ensure the December 2025 stack remains healthy.

Let me know if you want me to pull specific URLs next; otherwise, I’ll continue curating the new chunk described below and sync the store again.
