# Dockerfile for RAG Webhook with LanceDB RAG
# Includes LanceDB for local semantic search
FROM python:3.11-slim

# Cache bust to force fresh build on deploy
ARG CACHE_BUST=1

WORKDIR /app

# Install webhook dependencies INCLUDING LanceDB for semantic search
# Build time ~3-4 min but enables real RAG answers
RUN pip install --no-cache-dir \
    fastapi==0.128.0 \
    uvicorn==0.40.0 \
    requests==2.32.5 \
    lancedb>=0.4.0 \
    sentence-transformers==3.4.1 \
    pyarrow>=14.0.0 \
    rank_bm25==0.2.2

# Create required package structure
RUN mkdir -p src/agents src/rag src/memory rag_knowledge/lessons_learned data

# Create empty __init__.py files for Python packages
RUN touch src/__init__.py src/agents/__init__.py src/rag/__init__.py src/memory/__init__.py

# Copy RAG files for semantic search
COPY src/agents/rag_webhook.py src/agents/
COPY src/rag/lessons_learned_rag.py src/rag/
COPY src/rag/lessons_search.py src/rag/
COPY src/memory/document_aware_rag.py src/memory/
COPY rag_knowledge/lessons_learned/ rag_knowledge/lessons_learned/

# Copy system state for portfolio data (fallback to GitHub raw if stale)
COPY data/system_state.json data/

# Expose port
EXPOSE 8080

# Run webhook
CMD ["python", "-m", "uvicorn", "src.agents.rag_webhook:app", "--host", "0.0.0.0", "--port", "8080"]
