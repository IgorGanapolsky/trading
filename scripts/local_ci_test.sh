#!/bin/bash
# Local CI testing script using ACT
# Run this before pushing to catch issues early

set -e

echo "🧪 LOCAL CI TESTING WITH ACT"
echo "================================="

# Check if act is installed
if ! command -v act &> /dev/null; then
    echo "❌ ACT is not installed. Install it first:"
    echo "   brew install act"
    echo "   or visit: https://github.com/nektos/act"
    exit 1
fi

# Validate secrets exist (dry run)
echo "🔑 Validating secrets locally..."
python3 scripts/validate_secrets.py || {
    echo "⚠️  Secrets validation failed - some features may not work in CI"
    echo "   Set required environment variables for full testing"
}

# Run pre-commit hooks
echo "🔧 Running pre-commit hooks..."
if command -v pre-commit &> /dev/null; then
    pre-commit run --all-files || {
        echo "❌ Pre-commit hooks failed - fix issues before pushing"
        exit 1
    }
else
    echo "⚠️  pre-commit not installed - skipping hooks check"
fi

# Run smoke tests
echo "🧪 Running smoke tests..."
python3 tests/test_smoke.py || {
    echo "❌ Smoke tests failed - fix critical issues before pushing"
    exit 1
}

# Test workflow with ACT (just validation job)
echo "🎬 Testing GitHub Actions workflow with ACT..."
echo "   Running validation-and-test job..."

# Create minimal secrets for ACT
cat > .secrets <<EOF
ALPACA_API_KEY=test_key_pk123456789
ALPACA_SECRET_KEY=test_secret_123456789012345678901234567890
GITHUB_TOKEN=test_token
EOF

# Run ACT for the validation job only
if act workflow_dispatch \
    --job validate-and-test \
    --secret-file .secrets \
    --reuse \
    --quiet; then
    echo "✅ ACT validation job passed"
else
    echo "❌ ACT validation job failed - check workflow issues"
    rm -f .secrets
    exit 1
fi

# Clean up
rm -f .secrets

echo ""
echo "✅ ALL LOCAL CI TESTS PASSED"
echo "================================="
echo "Safe to push to GitHub! 🚀"
echo ""
echo "Next steps:"
echo "1. git add ."
echo "2. git commit -m 'your message'"
echo "3. git push"
