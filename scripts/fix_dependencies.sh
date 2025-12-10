#!/bin/bash
# Dependency Installation Fix Script
# Resolves pandas/numpy/yfinance/alpaca-trade-api installation issues
# Created: 2025-11-06
# Environment: Linux 4.4.0, Python 3.11

set -e  # Exit on error

echo "========================================"
echo "Trading System Dependency Installer"
echo "========================================"
echo ""

# Step 1: Install numpy and pandas with binary wheels only (fast)
echo "Step 1: Installing numpy and pandas from binary wheels..."
pip install --no-cache-dir --only-binary :all: numpy pandas
echo "✅ numpy and pandas installed"
echo ""

# Step 2: Install yfinance with stdlib distutils (fixes install_layout error)
echo "Step 2: Installing yfinance..."
SETUPTOOLS_USE_DISTUTILS=stdlib pip install --no-cache-dir yfinance
echo "✅ yfinance installed"
echo ""

# Step 3: Install alpaca-trade-api with stdlib distutils
echo "Step 3: Installing alpaca-trade-api..."
SETUPTOOLS_USE_DISTUTILS=stdlib pip install --no-cache-dir alpaca-trade-api
echo "✅ alpaca-trade-api installed"
echo ""

# Step 4: Upgrade websockets to fix version conflicts
echo "Step 4: Fixing websockets version conflict..."
SETUPTOOLS_USE_DISTUTILS=stdlib pip install --no-cache-dir 'websockets>=13.0'
echo "✅ websockets upgraded"
echo ""

# Step 5: Install remaining requirements (ignoring already installed debian packages)
echo "Step 5: Installing remaining requirements..."
SETUPTOOLS_USE_DISTUTILS=stdlib pip install --no-cache-dir --ignore-installed -r /home/user/trading/requirements.txt
echo "✅ All requirements installed"
echo ""

# Step 6: Verify imports
echo "Step 6: Verifying all imports work..."
python3 << 'PYEOF'
import pandas as pd
import numpy as np
import yfinance as yf
from alpaca_trade_api import REST

print(f"✅ pandas: {pd.__version__}")
print(f"✅ numpy: {np.__version__}")
print(f"✅ yfinance: {yf.__version__}")
print("✅ alpaca-trade-api: imported successfully")
PYEOF

echo ""
echo "========================================"
echo "✅ INSTALLATION COMPLETE!"
echo "========================================"
echo ""
echo "Key solution: Use SETUPTOOLS_USE_DISTUTILS=stdlib environment variable"
echo "This fixes the AttributeError: install_layout error with older packages"
echo ""
