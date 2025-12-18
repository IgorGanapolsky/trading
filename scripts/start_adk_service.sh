#!/usr/bin/env bash
###############################################################################
# ADK Trading Service Startup Script
#
# Purpose: Automatically launch the Go ADK multi-agent service before trading
# Requirements:
#   - GOOGLE_API_KEY environment variable must be set
#   - Builds and runs Go ADK server on port 8080
#   - Runs in background with proper logging
#   - Idempotent: won't start if already running
#
# Usage:
#   ./scripts/start_adk_service.sh
#
# Environment Variables:
#   GOOGLE_API_KEY (required)  - Google API key for ADK orchestrator
#   ADK_PORT (optional)        - Port to run on (default: 8080)
#   ADK_WEBUI_ORIGIN (optional)- WebUI origin (default: localhost:8080)
#   ADK_HEALTH_ADDR (optional) - Health check address (default: :8091)
###############################################################################

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Determine project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
GO_DIR="${ROOT_DIR}/go/adk_trading"
LOG_DIR="${ROOT_DIR}/logs"
LOG_PATH="${LOG_DIR}/adk_orchestrator.jsonl"
PID_FILE="${LOG_DIR}/adk_service.pid"

# Configuration
PORT="${ADK_PORT:-8080}"
WEBUI_ORIGIN="${ADK_WEBUI_ORIGIN:-localhost:8080}"
HEALTH_ADDR="${ADK_HEALTH_ADDR:-:8091}"

###############################################################################
# Helper Functions
###############################################################################

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

###############################################################################
# Pre-flight Checks
###############################################################################

check_google_api_key() {
    if [[ -z "${GOOGLE_API_KEY:-}" ]]; then
        log_error "GOOGLE_API_KEY environment variable is not set"
        log_error "Please set it before starting the ADK service:"
        log_error "  export GOOGLE_API_KEY='your-api-key-here'"
        exit 1
    fi
    log_info "GOOGLE_API_KEY is set ✓"
}

check_if_running() {
    # Check if PID file exists and process is running
    if [[ -f "${PID_FILE}" ]]; then
        local pid
        pid=$(cat "${PID_FILE}")
        if ps -p "${pid}" > /dev/null 2>&1; then
            log_warn "ADK service is already running (PID: ${pid})"
            log_info "Service is available at http://localhost:${PORT}"
            log_info "To restart, kill the process first: kill ${pid}"
            exit 0
        else
            log_warn "Stale PID file found. Removing..."
            rm -f "${PID_FILE}"
        fi
    fi

    # Check if port is already in use
    if lsof -Pi :${PORT} -sTCP:LISTEN -t >/dev/null 2>&1; then
        local port_pid
        port_pid=$(lsof -Pi :${PORT} -sTCP:LISTEN -t)
        log_error "Port ${PORT} is already in use by process ${port_pid}"
        log_error "Please stop the existing process or use a different port:"
        log_error "  ADK_PORT=8081 ./scripts/start_adk_service.sh"
        exit 1
    fi
}

check_go_installation() {
    if ! command -v go &> /dev/null; then
        log_error "Go is not installed or not in PATH"
        log_error "Please install Go 1.24+ from https://go.dev/dl/"
        exit 1
    fi
    local go_version
    go_version=$(go version | awk '{print $3}')
    log_info "Go ${go_version} detected ✓"
}

check_go_directory() {
    if [[ ! -d "${GO_DIR}" ]]; then
        log_error "Go ADK directory not found: ${GO_DIR}"
        exit 1
    fi

    if [[ ! -f "${GO_DIR}/go.mod" ]]; then
        log_error "go.mod not found in ${GO_DIR}"
        exit 1
    fi
    log_info "Go ADK directory found ✓"
}

###############################################################################
# Build & Start
###############################################################################

build_adk_service() {
    log_info "Building ADK service..."

    cd "${GO_DIR}"

    # Download dependencies if needed
    if [[ ! -d "${GO_DIR}/vendor" ]] && [[ ! -f "${GO_DIR}/go.sum" ]]; then
        log_info "Downloading Go dependencies..."
        go mod download
    fi

    # Build the binary
    log_info "Compiling trading_orchestrator..."
    if go build -o trading_orchestrator ./cmd/trading_orchestrator; then
        log_info "Build successful ✓"
    else
        log_error "Build failed"
        exit 1
    fi
}

start_adk_service() {
    log_info "Starting ADK service on port ${PORT}..."

    # Create logs directory
    mkdir -p "${LOG_DIR}"

    # Export required environment variables
    export GOOGLE_API_KEY
    export ADK_HEALTH_ADDR="${HEALTH_ADDR}"

    cd "${GO_DIR}"

    # Start the service in background
    nohup ./trading_orchestrator \
        --data_dir "${ROOT_DIR}/data" \
        --log_path "${LOG_PATH}" \
        --app "trading_orchestrator" \
        web --port "${PORT}" api --webui_address "${WEBUI_ORIGIN}" \
        >> "${LOG_DIR}/adk_stdout.log" 2>> "${LOG_DIR}/adk_stderr.log" &

    local pid=$!
    echo "${pid}" > "${PID_FILE}"

    # Wait a moment and verify it's still running
    sleep 2
    if ps -p "${pid}" > /dev/null 2>&1; then
        log_info "ADK service started successfully ✓"
        log_info "  PID: ${pid}"
        log_info "  Port: ${PORT}"
        log_info "  Health endpoint: http://localhost${HEALTH_ADDR}/health"
        log_info "  Logs: ${LOG_PATH}"
        log_info "  Stdout: ${LOG_DIR}/adk_stdout.log"
        log_info "  Stderr: ${LOG_DIR}/adk_stderr.log"

        # Test health endpoint after a brief delay
        sleep 3
        if curl -s "http://localhost${HEALTH_ADDR}/health" > /dev/null 2>&1; then
            log_info "Health check passed ✓"
        else
            log_warn "Health check endpoint not responding yet (may take a moment to initialize)"
        fi

        return 0
    else
        log_error "Service failed to start"
        log_error "Check logs at ${LOG_DIR}/adk_stderr.log for details"
        rm -f "${PID_FILE}"
        exit 1
    fi
}

###############################################################################
# Main
###############################################################################

main() {
    log_info "ADK Trading Service Startup Script"
    log_info "==================================="

    # Run all checks
    check_google_api_key
    check_if_running
    check_go_installation
    check_go_directory

    # Build and start
    build_adk_service
    start_adk_service

    log_info ""
    log_info "ADK service is ready for trading sessions!"
    log_info "To stop: kill \$(cat ${PID_FILE})"
}

main "$@"
