# Multi-stage Docker build for Trading Bot
# Stage 1: Base image with common dependencies
FROM python:3.11-slim as base

# Set working directory
WORKDIR /app

# Install system dependencies required for Python packages
# - gcc, g++: Required for compiling C extensions
# - curl: For health checks
# - chromium and chromedriver: For Selenium web scraping
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    chromium \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/*

# Set environment variables for Python
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Stage 2: Dependencies installation
FROM base as dependencies

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
# Using --no-cache-dir to reduce image size
RUN pip install --no-cache-dir -r requirements.txt

# Stage 3: Final production image
FROM base as production

# Copy installed dependencies from dependencies stage
COPY --from=dependencies /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=dependencies /usr/local/bin /usr/local/bin

# Create non-root user for security
RUN useradd -m -u 1000 trader && \
    mkdir -p /app/data /app/logs && \
    chown -R trader:trader /app

# Copy application source code
COPY --chown=trader:trader src/ /app/src/
COPY --chown=trader:trader dashboard/ /app/dashboard/

# Create volume mount points for persistent data
# - data/: Trading data, positions, history
# - logs/: Application logs
VOLUME ["/app/data", "/app/logs"]

# Switch to non-root user
USER trader

# Set environment variables for Selenium (headless Chrome)
ENV CHROME_BIN=/usr/bin/chromium \
    CHROMEDRIVER_PATH=/usr/bin/chromedriver \
    DISPLAY=:99

# Expose ports
# 8501: Streamlit dashboard (if running in same container)
EXPOSE 8501

# Health check to ensure the application is running
# Checks if main process is alive
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD pgrep -f "python.*main.py" || exit 1

# Default entrypoint - run the trading bot
# Can be overridden in docker-compose for different services
ENTRYPOINT ["python", "-u"]
CMD ["src/main.py"]
