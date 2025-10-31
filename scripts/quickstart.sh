#!/bin/bash
#
# Quick Start Script for Trading System Orchestrator
# This script helps set up and run the trading system
#

set -e

echo ""
echo "=========================================="
echo "Trading System Orchestrator - Quick Start"
echo "=========================================="
echo ""

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check Python
if ! command_exists python3; then
    echo "Error: Python 3 is required but not installed."
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
echo "Found Python $PYTHON_VERSION"

# Check if .env exists
if [ ! -f .env ]; then
    echo ""
    echo "Step 1: Creating .env file from .env.example..."
    if [ -f .env.example ]; then
        cp .env.example .env
        echo "✓ .env file created"
        echo ""
        echo "⚠️  IMPORTANT: Edit .env and add your API keys:"
        echo "   - ALPACA_API_KEY"
        echo "   - ALPACA_SECRET_KEY"
        echo "   - OPENROUTER_API_KEY (optional)"
        echo ""
        read -p "Press Enter after you've configured .env..."
    else
        echo "Error: .env.example not found"
        exit 1
    fi
else
    echo "✓ .env file already exists"
fi

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo ""
    echo "Step 2: Creating virtual environment..."
    python3 -m venv venv
    echo "✓ Virtual environment created"
fi

# Activate virtual environment
echo ""
echo "Step 3: Activating virtual environment..."
source venv/bin/activate
echo "✓ Virtual environment activated"

# Install dependencies
echo ""
echo "Step 4: Installing dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt
echo "✓ Dependencies installed"

# Run tests
echo ""
echo "Step 5: Running tests..."
python tests/test_main.py
TEST_RESULT=$?

if [ $TEST_RESULT -eq 0 ]; then
    echo ""
    echo "=========================================="
    echo "Setup Complete!"
    echo "=========================================="
    echo ""
    echo "The trading system is ready to run."
    echo ""
    echo "Available commands:"
    echo ""
    echo "  # Test run (execute once and exit)"
    echo "  python src/main.py --mode paper --run-once"
    echo ""
    echo "  # Start scheduled execution"
    echo "  python src/main.py --mode paper"
    echo ""
    echo "  # Debug mode"
    echo "  python src/main.py --mode paper --log-level DEBUG"
    echo ""
    echo "  # View help"
    echo "  python src/main.py --help"
    echo ""
    echo "For more information, see ORCHESTRATOR_README.md"
    echo ""

    # Ask if user wants to run test
    read -p "Would you like to run a test execution now? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo ""
        echo "Running test execution..."
        python src/main.py --mode paper --run-once
    fi
else
    echo ""
    echo "=========================================="
    echo "Setup Failed"
    echo "=========================================="
    echo ""
    echo "Please check the error messages above and:"
    echo "  1. Verify all dependencies are installed"
    echo "  2. Check that .env is configured correctly"
    echo "  3. Ensure API keys are valid"
    echo ""
    exit 1
fi
