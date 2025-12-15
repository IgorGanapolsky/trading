#!/bin/bash
# Quick test to verify backtest script is properly structured

echo "🔍 Testing backtest_crypto_strategy.py..."
echo ""

# Test 1: Check file exists and is executable
if [ -x "scripts/backtest_crypto_strategy.py" ]; then
    echo "✅ File exists and is executable"
else
    echo "❌ File not found or not executable"
    exit 1
fi

# Test 2: Check Python syntax
if python3 -m py_compile scripts/backtest_crypto_strategy.py 2>/dev/null; then
    echo "✅ Python syntax is valid"
else
    echo "❌ Syntax errors found"
    exit 1
fi

# Test 3: Check required imports (will fail if packages not installed)
echo ""
echo "📦 Checking dependencies..."
python3 -c "import numpy, pandas, yfinance, requests" 2>/dev/null
if [ $? -eq 0 ]; then
    echo "✅ All dependencies installed"
    echo ""
    echo "🚀 Running backtest..."
    python3 scripts/backtest_crypto_strategy.py
else
    echo "⚠️  Dependencies not installed. Install with:"
    echo "   pip install numpy pandas yfinance requests"
    echo ""
    echo "Script structure:"
    grep -E "^(class |def )" scripts/backtest_crypto_strategy.py | head -20
fi
