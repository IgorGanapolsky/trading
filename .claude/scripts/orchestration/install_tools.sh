#!/bin/bash
#
# Tool Installer for Trading System Autonomous Orchestration
#
# This script checks for and installs required tools:
# - oh-my-claudecode (npm package)
# - ralphex (npm package, optional)
# - launchd scheduler (macOS)
#
# Usage:
#   ./install_tools.sh           # Check and install all
#   ./install_tools.sh --check   # Check only, no install
#   ./install_tools.sh --launchd # Install launchd scheduler

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../../../" && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# ============================================================================
# TOOL CHECKS
# ============================================================================

check_node() {
    if command -v node &>/dev/null; then
        log_info "Node.js: $(node --version)"
        return 0
    else
        log_error "Node.js not found"
        return 1
    fi
}

check_npm() {
    if command -v npm &>/dev/null; then
        log_info "npm: $(npm --version)"
        return 0
    else
        log_error "npm not found"
        return 1
    fi
}

check_python() {
    if command -v python3 &>/dev/null; then
        log_info "Python: $(python3 --version)"
        return 0
    else
        log_error "Python3 not found"
        return 1
    fi
}

check_oh_my_claudecode() {
    if npm list -g oh-my-claudecode &>/dev/null 2>&1; then
        local version
        version=$(npm list -g oh-my-claudecode 2>/dev/null | grep oh-my-claudecode | awk -F@ '{print $2}')
        log_info "oh-my-claudecode: $version"
        return 0
    else
        log_warn "oh-my-claudecode not installed"
        return 1
    fi
}

check_ralphex() {
    if npm list -g ralphex &>/dev/null 2>&1; then
        local version
        version=$(npm list -g ralphex 2>/dev/null | grep ralphex | awk -F@ '{print $2}')
        log_info "ralphex: $version"
        return 0
    else
        log_warn "ralphex not installed (optional)"
        return 1
    fi
}

check_launchd() {
    if launchctl list 2>/dev/null | grep -q "com.trading.autonomous"; then
        log_info "launchd scheduler: Running"
        return 0
    else
        log_warn "launchd scheduler: Not running"
        return 1
    fi
}

check_swarm_skill() {
    if [[ -f "$PROJECT_DIR/.claude/skills/swarm-orchestration/SKILL.md" ]]; then
        log_info "Swarm orchestration skill: Present"
        return 0
    else
        log_error "Swarm orchestration skill: Missing"
        return 1
    fi
}

# ============================================================================
# INSTALLERS
# ============================================================================

install_oh_my_claudecode() {
    log_info "Installing oh-my-claudecode..."
    if npm install -g oh-my-claudecode; then
        log_info "oh-my-claudecode installed successfully"
        return 0
    else
        log_error "Failed to install oh-my-claudecode"
        return 1
    fi
}

install_ralphex() {
    log_info "Attempting to install ralphex..."
    if npm install -g ralphex 2>/dev/null; then
        log_info "ralphex installed successfully"
        return 0
    else
        log_warn "ralphex not available (this is okay, it's optional)"
        return 0  # Don't fail, it's optional
    fi
}

install_launchd() {
    local plist_src="$SCRIPT_DIR/com.trading.autonomous.plist"
    local plist_dst="$HOME/Library/LaunchAgents/com.trading.autonomous.plist"

    if [[ ! -f "$plist_src" ]]; then
        log_error "Plist template not found: $plist_src"
        return 1
    fi

    # Create LaunchAgents directory if needed
    mkdir -p "$HOME/Library/LaunchAgents"

    # Update plist with actual project path
    sed "s|REPLACE_WITH_PROJECT_PATH|$PROJECT_DIR|g" "$plist_src" > "$plist_dst"

    # Load the agent
    launchctl unload "$plist_dst" 2>/dev/null || true
    if launchctl load "$plist_dst"; then
        log_info "launchd scheduler installed and running"
        log_info "Logs: /tmp/trading_scheduler.log"
        return 0
    else
        log_error "Failed to load launchd agent"
        return 1
    fi
}

uninstall_launchd() {
    local plist_dst="$HOME/Library/LaunchAgents/com.trading.autonomous.plist"

    if [[ -f "$plist_dst" ]]; then
        launchctl unload "$plist_dst" 2>/dev/null || true
        rm -f "$plist_dst"
        log_info "launchd scheduler uninstalled"
    else
        log_warn "launchd scheduler not installed"
    fi
}

# ============================================================================
# MAIN
# ============================================================================

run_checks() {
    echo "============================================"
    echo "Trading System Tool Check"
    echo "============================================"
    echo ""

    local all_ok=true

    check_node || all_ok=false
    check_npm || all_ok=false
    check_python || all_ok=false
    check_oh_my_claudecode || all_ok=false
    check_ralphex || true  # Optional, don't fail
    check_launchd || true  # Optional, just report
    check_swarm_skill || all_ok=false

    echo ""
    if $all_ok; then
        log_info "All required tools present"
        return 0
    else
        log_warn "Some tools missing - run without --check to install"
        return 1
    fi
}

run_install() {
    echo "============================================"
    echo "Trading System Tool Installation"
    echo "============================================"
    echo ""

    # Prerequisites
    check_node || {
        log_error "Node.js required. Install via: brew install node"
        exit 1
    }

    check_npm || {
        log_error "npm required"
        exit 1
    }

    check_python || {
        log_error "Python3 required. Install via: brew install python"
        exit 1
    }

    # Install npm packages
    check_oh_my_claudecode || install_oh_my_claudecode
    check_ralphex || install_ralphex

    # Verify swarm skill
    check_swarm_skill || {
        log_error "Swarm skill missing. This should be created by the orchestration system."
        exit 1
    }

    echo ""
    log_info "Tool installation complete"
    echo ""
    echo "To enable automatic scheduling, run:"
    echo "  $0 --launchd"
}

show_help() {
    echo "Trading System Tool Installer"
    echo ""
    echo "Usage: $0 [option]"
    echo ""
    echo "Options:"
    echo "  (no option)   Check and install missing tools"
    echo "  --check       Check tool status only"
    echo "  --launchd     Install and start launchd scheduler"
    echo "  --uninstall   Remove launchd scheduler"
    echo "  --help        Show this help"
}

main() {
    case "${1:-}" in
        --check)
            run_checks
            ;;
        --launchd)
            install_launchd
            ;;
        --uninstall)
            uninstall_launchd
            ;;
        --help|-h)
            show_help
            ;;
        *)
            run_install
            ;;
    esac
}

main "$@"
