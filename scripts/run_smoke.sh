#!/usr/bin/env bash
set -euo pipefail
# Smoke test - validates core trading imports and dependencies
# Updated: Dec 19, 2025 - Removed backtest (was stub from PR #782)

# Resolve absolute paths
REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

echo "Running smoke test..."

# Ensure python path includes repo root
export PYTHONPATH="${PYTHONPATH:-}:$(pwd)"

python3 - <<'PY'
import sys

print("🔍 Checking core imports...")

try:
    from src.orchestrator.main import TradingOrchestrator
    print("  ✅ TradingOrchestrator")
except ImportError as e:
    print(f"  ❌ TradingOrchestrator: {e}")
    sys.exit(1)

try:
    from src.strategies.core_strategy import CoreStrategy
    print("  ✅ CoreStrategy")
except ImportError as e:
    print(f"  ❌ CoreStrategy: {e}")
    sys.exit(1)

try:
    from src.risk.vix_circuit_breaker import VIXCircuitBreaker
    print("  ✅ VIXCircuitBreaker")
except ImportError as e:
    print(f"  ❌ VIXCircuitBreaker: {e}")
    sys.exit(1)

try:
    from src.risk.risk_manager import RiskManager
    print("  ✅ RiskManager")
except ImportError as e:
    print(f"  ❌ RiskManager: {e}")
    sys.exit(1)

print("\n✅ Smoke test passed - core modules load correctly")
print("📝 Note: Paper trading validates strategies with real market data")
PY
