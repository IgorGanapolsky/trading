#!/bin/bash
#
# TRADING ACTIVITY MONITOR
#
# Checks if trading system is active by verifying:
# 1. Trade file exists for today
# 2. Trades logged in last 24 hours
# 3. system_state.json last_updated timestamp is fresh
# 4. Only alerts on market days (Mon-Fri)
#
# Exit Codes:
#   0 = Trading activity detected (OK)
#   1 = No trading activity in 24h on a market day (WARNING)
#   2 = Critical error or stale data >48h (ERROR)
#
# Usage:
#   ./check_trading_activity.sh
#
# Cron example (run at 11 AM ET on weekdays):
#   0 11 * * 1-5 /home/user/trading/scripts/check_trading_activity.sh || echo "ALERT: Trading stale"

set -euo pipefail

# Configuration
TRADING_DIR="/home/user/trading"
DATA_DIR="${TRADING_DIR}/data"
SYSTEM_STATE="${DATA_DIR}/system_state.json"
TRADE_FILE_PATTERN="${DATA_DIR}/trades_*.json"

# Colors for output
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $*"
}

log_success() {
    echo -e "${GREEN}[OK]${NC} $*"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*"
}

print_header() {
    echo "================================================================"
    echo "  TRADING ACTIVITY MONITOR"
    echo "  $(date '+%Y-%m-%d %H:%M:%S %Z')"
    echo "================================================================"
    echo ""
}

# Check if today is a market day (Mon-Fri, US holidays not considered)
is_market_day() {
    local day_of_week
    day_of_week=$(date +%u)  # 1=Monday, 7=Sunday

    if [ "$day_of_week" -ge 1 ] && [ "$day_of_week" -le 5 ]; then
        return 0  # True - it's a weekday
    else
        return 1  # False - it's weekend
    fi
}

# Check if today's trade file exists
check_todays_trade_file() {
    local today_file="${DATA_DIR}/trades_$(date +%Y-%m-%d).json"

    log_info "Checking for today's trade file: $(basename "$today_file")"

    if [ -f "$today_file" ]; then
        local trade_count
        trade_count=$(jq 'length' "$today_file" 2>/dev/null || echo "0")
        log_success "Found today's trade file with $trade_count trade(s)"
        return 0
    else
        log_warning "No trade file found for today ($(date +%Y-%m-%d))"
        return 1
    fi
}

# Check for any trade files in last 24 hours
check_recent_trade_files() {
    local cutoff_time
    cutoff_time=$(date -d '24 hours ago' +%s 2>/dev/null || date -v-24H +%s 2>/dev/null || echo "0")

    log_info "Checking for trade files modified in last 24 hours..."

    local recent_files=()
    for trade_file in ${DATA_DIR}/trades_*.json; do
        if [ -f "$trade_file" ]; then
            local file_mtime
            file_mtime=$(stat -c %Y "$trade_file" 2>/dev/null || stat -f %m "$trade_file" 2>/dev/null || echo "0")

            if [ "$file_mtime" -gt "$cutoff_time" ]; then
                recent_files+=("$(basename "$trade_file")")
            fi
        fi
    done

    if [ ${#recent_files[@]} -gt 0 ]; then
        log_success "Found ${#recent_files[@]} trade file(s) modified in last 24h: ${recent_files[*]}"
        return 0
    else
        log_warning "No trade files modified in last 24 hours"
        return 1
    fi
}

# Check system_state.json last_updated timestamp
check_system_state_freshness() {
    log_info "Checking system_state.json freshness..."

    if [ ! -f "$SYSTEM_STATE" ]; then
        log_error "system_state.json not found at $SYSTEM_STATE"
        return 2
    fi

    # Extract last_updated timestamp
    local last_updated
    last_updated=$(jq -r '.meta.last_updated // empty' "$SYSTEM_STATE" 2>/dev/null)

    if [ -z "$last_updated" ]; then
        log_error "Could not read last_updated from system_state.json"
        return 2
    fi

    # Convert timestamp to epoch (handle both formats: with/without timezone)
    local last_updated_epoch
    last_updated_epoch=$(date -d "$last_updated" +%s 2>/dev/null || date -j -f "%Y-%m-%dT%H:%M:%S" "${last_updated%%.*}" +%s 2>/dev/null || echo "0")

    local current_epoch
    current_epoch=$(date +%s)

    local hours_ago=$(( (current_epoch - last_updated_epoch) / 3600 ))

    log_info "System state last updated: $last_updated ($hours_ago hours ago)"

    if [ "$hours_ago" -lt 24 ]; then
        log_success "System state is fresh (< 24 hours old)"
        return 0
    elif [ "$hours_ago" -lt 48 ]; then
        log_warning "System state is getting stale (${hours_ago}h old, >24h)"
        return 1
    else
        log_error "System state is STALE (${hours_ago}h old, >48h) - critical issue!"
        return 2
    fi
}

# Main monitoring logic
main() {
    local exit_code=0
    local warnings=0
    local errors=0

    print_header

    # Check if it's a market day
    if is_market_day; then
        log_info "Today is a MARKET DAY ($(date +%A))"
        echo ""
    else
        log_info "Today is a WEEKEND ($(date +%A)) - markets closed"
        echo ""
        log_success "No trading expected on weekends - all checks skipped"
        exit 0
    fi

    # Run all checks
    echo "Running activity checks..."
    echo ""

    # Check 1: Today's trade file
    if ! check_todays_trade_file; then
        ((warnings++))
    fi
    echo ""

    # Check 2: Recent trade files (24h)
    if ! check_recent_trade_files; then
        ((warnings++))
    fi
    echo ""

    # Check 3: System state freshness
    check_result=0
    check_system_state_freshness || check_result=$?
    if [ "$check_result" -eq 2 ]; then
        ((errors++))
    elif [ "$check_result" -eq 1 ]; then
        ((warnings++))
    fi
    echo ""

    # Determine final status
    echo "================================================================"
    echo "  SUMMARY"
    echo "================================================================"

    if [ "$errors" -gt 0 ]; then
        log_error "CRITICAL: $errors error(s) detected - trading system may be broken!"
        log_error "Action required: Investigate system_state.json and trading automation"
        exit_code=2
    elif [ "$warnings" -gt 0 ]; then
        log_warning "WARNING: $warnings warning(s) detected - no trading activity in 24h"

        # Check if it's past market open (9:30 AM ET = 14:30 UTC, approximately)
        local current_hour
        current_hour=$(date +%H)

        if [ "$current_hour" -ge 15 ]; then
            log_warning "Market should be open - this indicates a potential issue"
            log_warning "Action: Check GitHub Actions workflow status and trading logs"
        else
            log_info "Markets may not have opened yet - check again after 10 AM ET"
        fi
        exit_code=1
    else
        log_success "All checks passed - trading system is ACTIVE"
        exit_code=0
    fi

    echo ""
    echo "Exit code: $exit_code"

    return $exit_code
}

# Run main and exit with its code
main
exit $?
