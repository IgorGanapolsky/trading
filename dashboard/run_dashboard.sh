#!/bin/bash

# Trading System Dashboard Launcher
# This script launches the Streamlit dashboard

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Trading System Dashboard${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

# Change to project root
cd "$PROJECT_ROOT"

echo -e "${GREEN}Project Root:${NC} $PROJECT_ROOT"
echo -e "${GREEN}Dashboard:${NC} $SCRIPT_DIR/dashboard.py"
echo ""

# Check if streamlit is installed
if ! command -v streamlit &> /dev/null
then
    echo "Error: Streamlit is not installed."
    echo "Please install it with: pip install streamlit"
    exit 1
fi

# Check if data directory exists
if [ ! -d "$PROJECT_ROOT/data" ]; then
    echo "Creating data directory..."
    mkdir -p "$PROJECT_ROOT/data"
fi

echo -e "${GREEN}Starting dashboard...${NC}"
echo "The dashboard will open in your default browser."
echo "Press Ctrl+C to stop the dashboard."
echo ""

# Launch the dashboard
streamlit run "$SCRIPT_DIR/dashboard.py"
