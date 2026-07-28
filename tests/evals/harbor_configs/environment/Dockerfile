# Harbor Eval Environment: Trade Execution Evals
FROM python:3.11-slim as base

WORKDIR /app

# Install minimal dependencies for evals
RUN pip install --no-cache-dir \
    pytest==8.3.4 \
    pytest-cov==5.0.0 \
    requests==2.32.3 \
    httpx==0.27.2 \
    openai==1.58.1 \
    tiktoken==0.8.0

# Copy eval code with golden fixtures
COPY requirements-ci.txt .
RUN pip install --no-cache-dir -r requirements-ci.txt 2>/dev/null || true

# Build stage
FROM base as build
WORKDIR /build
COPY . .
RUN pip install --no-cache-dir -e . >/dev/null 2>&1 || \
    pip install pytest decimal numpy >/dev/null 2>&1 || true

# Runtime stage  
FROM base
WORKDIR /evals
COPY --from=build /app/dist /evals/dist
COPY tests/evals/harbor_configs/. .

# Set Python path for eval discovery
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONHASHSEED=0 \
    PATH="/evals/dist:$PATH"

ENTRYPOINT ["python", "-m", "pytest"]
