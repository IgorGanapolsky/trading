#!/bin/bash
# Test Trading System Deployment Configuration

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

TRADING_DIR="/home/user/trading"
PASSED=0
FAILED=0

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Trading System Deployment Test${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

test_check() {
    local name="$1"
    local result="$2"
    local message="$3"

    if [ "$result" -eq 0 ]; then
        echo -e "${GREEN}✓${NC} $name"
        ((PASSED++))
    else
        echo -e "${RED}✗${NC} $name: $message"
        ((FAILED++))
    fi
}

# Test 1: Check directory structure
test_check "Trading directory exists" \
    $([ -d "$TRADING_DIR" ] && echo 0 || echo 1) \
    "Directory not found"

# Test 2: Check .env file
test_check ".env file exists" \
    $([ -f "$TRADING_DIR/.env" ] && echo 0 || echo 1) \
    "Run: cp .env.example .env"

# Test 3: Check .env permissions
if [ -f "$TRADING_DIR/.env" ]; then
    PERMS=$(stat -c "%a" "$TRADING_DIR/.env")
    test_check ".env file permissions (600)" \
        $([ "$PERMS" = "600" ] && echo 0 || echo 1) \
        "Run: chmod 600 .env (current: $PERMS)"
fi

# Test 4: Check Python
test_check "Python3 installed" \
    $(command -v python3 > /dev/null && echo 0 || echo 1) \
    "Python3 not found"

# Test 5: Check main.py
test_check "main.py exists" \
    $([ -f "$TRADING_DIR/src/main.py" ] && echo 0 || echo 1) \
    "Main script not found"

# Test 6: Check management scripts
for script in start-trading-system.sh stop-trading-system.sh status-trading-system.sh; do
    test_check "$script exists and executable" \
        $([ -x "$TRADING_DIR/$script" ] && echo 0 || echo 1) \
        "Run: chmod +x $script"
done

# Test 7: Check systemd service file
test_check "systemd service file exists" \
    $([ -f "$TRADING_DIR/trading-system.service" ] && echo 0 || echo 1) \
    "Service file not found"

# Test 8: Check systemd installation
if [ -f "/etc/systemd/system/trading-system.service" ]; then
    test_check "systemd service installed" 0 ""
    test_check "systemd service enabled" \
        $([ -L "/etc/systemd/system/multi-user.target.wants/trading-system.service" ] && echo 0 || echo 1) \
        "Run: sudo systemctl enable trading-system"
else
    echo -e "${YELLOW}⚠${NC} systemd service not installed (optional)"
fi

# Test 9: Check log directory
test_check "logs directory exists" \
    $([ -d "$TRADING_DIR/logs" ] && echo 0 || echo 1) \
    "Will be created on first run"

# Test 10: Check data directory
test_check "data directory exists" \
    $([ -d "$TRADING_DIR/data" ] && echo 0 || echo 1) \
    "Will be created on first run"

# Test 11: Check reports directory
test_check "reports directory exists" \
    $([ -d "$TRADING_DIR/reports" ] && echo 0 || echo 1) \
    "Will be created on first run"

# Test 12: Validate Python syntax
if command -v python3 > /dev/null && [ -f "$TRADING_DIR/src/main.py" ]; then
    python3 -m py_compile "$TRADING_DIR/src/main.py" 2>/dev/null
    test_check "main.py syntax valid" $? "Python syntax error"
fi

# Test 13: Check required dependencies
if command -v pip3 > /dev/null && [ -f "$TRADING_DIR/requirements.txt" ]; then
    # Just check a few critical ones
    for pkg in alpaca-py openai schedule pytz; do
        pip3 show "$pkg" > /dev/null 2>&1
        test_check "Python package: $pkg" $? "Run: pip3 install -r requirements.txt"
    done
fi

# Summary
echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "Results: ${GREEN}$PASSED passed${NC}, ${RED}$FAILED failed${NC}"
echo -e "${BLUE}========================================${NC}"

if [ $FAILED -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✓ All tests passed!${NC}"
    echo ""
    echo "Next steps:"
    echo "1. Configure API keys in .env file"
    echo "2. Run: ./start-trading-system.sh"
    echo "3. Check status: ./status-trading-system.sh"
    echo "4. View logs: tail -f logs/trading_system.log"
    echo ""
    exit 0
else
    echo ""
    echo -e "${YELLOW}⚠ Some tests failed. Fix issues above before deploying.${NC}"
    echo ""
    exit 1
fi
