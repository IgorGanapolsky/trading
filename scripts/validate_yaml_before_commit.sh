#!/bin/bash
# Strict YAML validation for workflow files
# Pre-commit hook to catch YAML syntax errors before they break CI

set -e

YAML_FILES=$(find .github/workflows -name "*.yml" -o -name "*.yaml" 2>/dev/null || true)

if [ -z "$YAML_FILES" ]; then
    echo "✅ No YAML files to validate"
    exit 0
fi

ERRORS=0

for file in $YAML_FILES; do
    if ! python3 -c "import yaml; yaml.safe_load(open('$file'))" 2>/dev/null; then
        echo "❌ Invalid YAML: $file"
        ERRORS=$((ERRORS + 1))
    fi
done

if [ $ERRORS -gt 0 ]; then
    echo "❌ Found $ERRORS YAML validation errors"
    exit 1
fi

echo "✅ All YAML files are valid"
exit 0
