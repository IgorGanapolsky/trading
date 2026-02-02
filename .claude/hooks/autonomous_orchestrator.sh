#!/bin/bash
#
# Autonomous Orchestrator - SessionStart Hook
#
# This hook auto-detects the current time and triggers appropriate swarm mode:
# - Market hours (9:30 AM - 4 PM ET weekdays): Trading mode
# - After hours (4 PM - 9:30 AM ET weekdays): Maintenance mode
# - Weekends: Research/learning mode
#
# Also checks for required tools and installs if missing.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
ORCHESTRATION_DIR="$PROJECT_DIR/.claude/scripts/orchestration"
STATE_FILE="$PROJECT_DIR/.claude/orchestrator_state.json"

# ============================================================================
# TOOL INSTALLATION CHECK
# ============================================================================

check_and_install_tools() {
    local tools_installed=true

    # Check oh-my-claudecode
    if ! command -v oh-my-claudecode &>/dev/null; then
        if npm list -g oh-my-claudecode &>/dev/null 2>&1; then
            : # Already installed globally
        else
            echo "[Orchestrator] Installing oh-my-claudecode..." >&2
            npm install -g oh-my-claudecode 2>/dev/null || {
                echo "[Orchestrator] WARN: oh-my-claudecode install failed (non-critical)" >&2
                tools_installed=false
            }
        fi
    fi

    # Check ralphex (if available)
    if ! command -v ralphex &>/dev/null; then
        if npm list -g ralphex &>/dev/null 2>&1; then
            : # Already installed globally
        else
            echo "[Orchestrator] Checking ralphex..." >&2
            # ralphex may not be public, skip gracefully
            npm install -g ralphex 2>/dev/null || true
        fi
    fi

    # Verify swarm orchestration skill exists
    if [[ ! -f "$PROJECT_DIR/.claude/skills/swarm-orchestration/SKILL.md" ]]; then
        echo "[Orchestrator] WARN: Swarm orchestration skill not found" >&2
        tools_installed=false
    fi

    echo "$tools_installed"
}

# ============================================================================
# TIME-BASED MODE DETECTION
# ============================================================================

get_current_mode() {
    # Get current time in ET
    local hour minute day_of_week
    hour=$(TZ="America/New_York" date +%H)
    minute=$(TZ="America/New_York" date +%M)
    day_of_week=$(TZ="America/New_York" date +%u)  # 1=Monday, 7=Sunday

    local current_minutes=$((10#$hour * 60 + 10#$minute))

    # Define market hours (9:30 AM = 570 min, 4:00 PM = 960 min)
    local market_open=570   # 9:30 AM
    local market_close=960  # 4:00 PM

    # Weekend check (Saturday=6, Sunday=7)
    if [[ $day_of_week -ge 6 ]]; then
        echo "research"
        return
    fi

    # Market hours check
    if [[ $current_minutes -ge $market_open && $current_minutes -lt $market_close ]]; then
        echo "trading"
        return
    fi

    # Before market (5:00 AM - 9:30 AM) = pre-market prep
    if [[ $current_minutes -ge 300 && $current_minutes -lt $market_open ]]; then
        echo "premarket"
        return
    fi

    # After hours = maintenance
    echo "maintenance"
}

# ============================================================================
# SCHEDULED TASK CHECK
# ============================================================================

check_scheduled_tasks() {
    local hour minute
    hour=$(TZ="America/New_York" date +%H)
    minute=$(TZ="America/New_York" date +%M)

    # Check for specific scheduled times
    case "${hour}:${minute}" in
        "09:25")
            echo "SWARM_TRIGGER: Pre-market analysis swarm starting..."
            echo "analysis"
            ;;
        "09:35")
            echo "SWARM_TRIGGER: Trading execution check..."
            echo "trade"
            ;;
        "15:45")
            echo "SWARM_TRIGGER: EOD position review..."
            echo "eod_review"
            ;;
        "20:00")
            echo "SWARM_TRIGGER: Daily cleanup swarm..."
            echo "cleanup"
            ;;
        *)
            echo "none"
            ;;
    esac
}

# ============================================================================
# HEALTH CHECK
# ============================================================================

run_health_checks() {
    local health_status="OK"
    local issues=""

    # Check Python environment
    if ! command -v python3 &>/dev/null; then
        issues="${issues}Python3 not found; "
        health_status="DEGRADED"
    fi

    # Check system_state.json
    if [[ ! -f "$PROJECT_DIR/data/system_state.json" ]]; then
        issues="${issues}system_state.json missing; "
        health_status="DEGRADED"
    fi

    # Check LanceDB
    if [[ ! -d "$PROJECT_DIR/.claude/memory/lancedb" ]]; then
        issues="${issues}LanceDB not initialized; "
        health_status="DEGRADED"
    fi

    # Check Alpaca credentials
    if [[ -z "${ALPACA_PAPER_TRADING_API_KEY:-}" ]]; then
        # Try to load from .env
        if [[ -f "$PROJECT_DIR/.env" ]]; then
            source "$PROJECT_DIR/.env" 2>/dev/null || true
        fi
        if [[ -z "${ALPACA_PAPER_TRADING_API_KEY:-}" ]]; then
            issues="${issues}Alpaca API key not set; "
            health_status="DEGRADED"
        fi
    fi

    echo "$health_status|$issues"
}

# ============================================================================
# MAIN ORCHESTRATION
# ============================================================================

main() {
    local tools_ok mode scheduled_task health_result health_status health_issues

    # Run tool checks
    tools_ok=$(check_and_install_tools)

    # Get current mode based on time
    mode=$(get_current_mode)

    # Check for scheduled tasks
    scheduled_task=$(check_scheduled_tasks)

    # Run health checks
    health_result=$(run_health_checks)
    health_status="${health_result%%|*}"
    health_issues="${health_result#*|}"

    # Update state file
    cat > "$STATE_FILE" <<EOF
{
  "last_check": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "mode": "$mode",
  "scheduled_task": "$scheduled_task",
  "health_status": "$health_status",
  "health_issues": "${health_issues:-none}",
  "tools_ok": $tools_ok
}
EOF

    # Output orchestration context
    cat >&2 <<EOF

================================================================================
AUTONOMOUS ORCHESTRATOR - SESSION START
================================================================================
Mode: $(echo "$mode" | tr '[:lower:]' '[:upper:]')
Time: $(TZ="America/New_York" date "+%Y-%m-%d %H:%M:%S ET")
Health: $health_status
EOF

    if [[ -n "$health_issues" && "$health_issues" != "none" ]]; then
        echo "Issues: $health_issues" >&2
    fi

    if [[ "$scheduled_task" != "none" ]]; then
        echo "Scheduled: $scheduled_task" >&2
    fi

    # Mode-specific guidance
    case "$mode" in
        trading)
            cat >&2 <<EOF
--------------------------------------------------------------------------------
TRADING MODE ACTIVE
- Market is OPEN
- Ready to execute iron condor trades
- Position monitoring active
- Use /swarm trade to execute
================================================================================
EOF
            ;;
        premarket)
            cat >&2 <<EOF
--------------------------------------------------------------------------------
PRE-MARKET MODE
- Market opens soon
- Run /swarm analysis for pre-market analysis
- 5 agents: sentiment, technicals, risk, options-chain, news
================================================================================
EOF
            ;;
        maintenance)
            cat >&2 <<EOF
--------------------------------------------------------------------------------
MAINTENANCE MODE
- Market is CLOSED
- Run /swarm cleanup for daily maintenance
- Tasks: tests, dead code scan, RAG reindex
================================================================================
EOF
            ;;
        research)
            cat >&2 <<EOF
--------------------------------------------------------------------------------
RESEARCH MODE (WEEKEND)
- No trading allowed
- Run /swarm research for weekend learning
- Tasks: Phil Town content, backtesting, strategy review
================================================================================
EOF
            ;;
    esac

    # Return mode for potential programmatic use
    echo "$mode"
}

# Run main
main "$@"
