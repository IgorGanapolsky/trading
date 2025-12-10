#!/bin/bash
set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}🚀 Starting Local CI Pipeline...${NC}"

# Check requirements
if ! command -v pre-commit &> /dev/null; then
    echo -e "${RED}❌ pre-commit is not installed.${NC}"
    echo "Run: pip install pre-commit"
    exit 1
fi

if ! command -v act &> /dev/null; then
    echo -e "${RED}❌ act is not installed.${NC}"
    echo "Run: brew install act"
    exit 1
fi

# 1. Worktree hygiene (non-destructive)
echo -e "\n${YELLOW}1️⃣  Checking worktree hygiene...${NC}"
scripts/worktree_hygiene.sh || true

# Optional strict gate: fail if detached worktrees exist
if [[ "${STRICT_HYGIENE:-0}" == "1" ]]; then
    if git worktree list --porcelain | grep -q '^detached'; then
        echo -e "${RED}❌ Detached worktrees detected. Run scripts/worktree_hygiene.sh --remove-detached or set STRICT_HYGIENE=0 to bypass.${NC}"
        exit 1
    fi
fi

# 2. Run Pre-commit hooks
echo -e "\n${YELLOW}2️⃣  Running Pre-commit Hooks...${NC}"
pre-commit run --all-files || {
    echo -e "${RED}❌ Pre-commit hooks failed! Fix the issues above.${NC}"
    exit 1
}
echo -e "${GREEN}✅ Pre-commit hooks passed!${NC}"

# 3. Run Critical CI Workflows with ACT
echo -e "\n${YELLOW}3️⃣  Running GitHub Actions (Local via ACT)...${NC}"

# Run Security Scan
echo -e "\n${YELLOW}🛡️  Running Security Scan...${NC}"
act -j security-scan --reuse || {
    echo -e "${RED}❌ Security Scan failed!${NC}"
    exit 1
}

# Run ADK CI (Tests)
echo -e "\n${YELLOW}🧪 Running ADK CI (Tests)...${NC}"
# We use --reuse to speed up subsequent runs
act -j build -W .github/workflows/adk-ci.yml --reuse || {
    echo -e "${RED}❌ ADK CI failed!${NC}"
    exit 1
}

echo -e "\n${GREEN}🎉 All Local CI checks passed! You are safe to push.${NC}"
