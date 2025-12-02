#!/usr/bin/env bash
# Strict YAML validation before commit
# This ensures all YAML files are valid before they're committed

set -e

echo "🔍 Validating YAML files before commit..."

FAILED=0

# Check all staged YAML files
for file in $(git diff --cached --name-only --diff-filter=ACM | grep -E '\.(yaml|yml)$'); do
    if [ -f "$file" ]; then
        echo "  Checking: $file"

        # Use Python's yaml module for strict validation
        if ! python3 -c "
import yaml
import sys
try:
    with open('$file', 'r') as f:
        yaml.safe_load(f)
    print('    ✅ Valid')
except yaml.YAMLError as e:
    print(f'    ❌ YAML Error: {e}')
    sys.exit(1)
except Exception as e:
    print(f'    ❌ Error reading file: {e}')
    sys.exit(1)
"; then
            echo "    ❌ FAILED: $file has YAML syntax errors"
            FAILED=1
        fi
    fi
done

# Special check for GitHub Actions workflows
for file in $(git diff --cached --name-only --diff-filter=ACM | grep '\.github/workflows/.*\.yml$'); do
    if [ -f "$file" ]; then
        echo "  Validating GitHub Actions workflow: $file"

        # Check for common workflow syntax issues
        if grep -q '<<EOF' "$file" || grep -q '<<-EOF' "$file"; then
            # Check if heredoc is properly closed
            if ! python3 -c "
import re
with open('$file') as f:
    content = f.read()
    # Count heredoc starts and ends
    starts = len(re.findall(r'<<-?EOF', content))
    ends = len(re.findall(r'^EOF', content, re.MULTILINE))
    if starts != ends:
        print(f'    ❌ Heredoc mismatch: {starts} starts, {ends} ends')
        exit(1)
"; then
                echo "    ❌ FAILED: $file has heredoc syntax issues"
                FAILED=1
            fi
        fi

        # Check for duplicate step IDs in GitHub Actions workflows
        if ! python3 -c "
import yaml
import sys
from collections import Counter

with open('$file') as f:
    content = yaml.safe_load(f)

if not content or 'jobs' not in content:
    sys.exit(0)

errors = []
for job_name, job_config in content.get('jobs', {}).items():
    if not isinstance(job_config, dict):
        continue
    steps = job_config.get('steps', [])
    if not steps:
        continue

    # Collect all step IDs
    step_ids = [s.get('id') for s in steps if isinstance(s, dict) and s.get('id')]
    duplicates = [id for id, count in Counter(step_ids).items() if count > 1]

    if duplicates:
        errors.append(f'Job \"{job_name}\" has duplicate step IDs: {duplicates}')

if errors:
    for err in errors:
        print(f'    ❌ {err}')
    sys.exit(1)
print('    ✅ No duplicate step IDs')
"; then
            echo "    ❌ FAILED: $file has duplicate step IDs"
            FAILED=1
        fi
    fi
done

if [ $FAILED -eq 1 ]; then
    echo ""
    echo "❌ YAML validation failed!"
    echo "   Fix the errors above before committing."
    exit 1
fi

echo "✅ All YAML files are valid"
exit 0
