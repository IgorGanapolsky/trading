#!/bin/bash

# Mercury API Token Cleanup Script
# This script handles Mercury API token security and cleanup procedures

set -e  # Exit on any error

echo "Starting Mercury API Token Security Check..."

# Function to check for Mercury token references in codebase
check_mercury_tokens() {
    echo "Checking for Mercury API token references in codebase..."
    
    MERCURY_REFERENCES=$(grep -r "MERCURY_API_TOKEN\|mercury" . --exclude-dir=.git --exclude-dir=.venv --exclude="*.pyc" 2>/dev/null || true)
    
    if [ -n "$MERCURY_REFERENCES" ]; then
        echo "Found Mercury references in codebase:"
        echo "$MERCURY_REFERENCES"
        
        # Check if Mercury functionality is enabled
        if grep -q "MERCURY_LIVE_TRANSFERS_ENABLED=1" .env* 2>/dev/null; then
            echo "⚠️  WARNING: Mercury live transfers appear to be enabled!"
            echo "Verify that this is intentional before proceeding."
        else
            echo "✓ Mercury live transfers are correctly disabled (MERCURY_LIVE_TRANSFERS_ENABLED != 1)"
        fi
    else
        echo "No Mercury references found in codebase."
    fi
}

# Function to verify environment configuration
check_environment() {
    echo "Checking environment configuration..."
    
    if [ -f ".env" ]; then
        if grep -q "MERCURY_API_TOKEN=" .env && [ -n "$(grep "MERCURY_API_TOKEN=.*[^=]$" .env)" ]; then
            echo "⚠️  WARNING: MERCURY_API_TOKEN is set in .env file!"
            echo "Ensure this token is valid and necessary."
        else
            echo "✓ MERCURY_API_TOKEN is not set in .env (recommended for security)"
        fi
    else
        echo "✓ No .env file found (using environment variables)"
    fi
}

# Function to recommend token cleanup
recommend_cleanup() {
    echo ""
    echo "Mercury API Token Security Recommendations:"
    echo ""
    echo "1. If the Mercury token named 'trading' is no longer needed:"
    echo "   - Allow it to expire as notified by Mercury (7 days)"
    echo "   - Ensure Mercury functionality remains disabled in configuration"
    echo "   - Consider removing Mercury-related code if not in use"
    echo ""
    echo "2. If Mercury functionality is still required:"
    echo "   - Generate a new API token with minimal required permissions"
    echo "   - Store it securely in environment variables or Keychain"
    echo "   - Never hardcode the token in source code"
    echo "   - Implement proper token rotation procedures"
    echo ""
    echo "Current configuration shows Mercury transfers are disabled by default,"
    echo "which is the secure approach for unused functionality."
}

# Main execution
main() {
    echo "Mercury API Token Security Check"
    echo "================================="
    echo ""
    
    check_mercury_tokens
    echo ""
    check_environment
    echo ""
    recommend_cleanup
    
    echo ""
    echo "Security check complete. Review recommendations carefully."
}

# Run the main function
main "$@"