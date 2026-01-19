#!/usr/bin/env python3
"""
Validate GitHub workflow secrets - Zero Tolerance Policy.

Ensures all workflows using secrets reference properly configured secrets.
Prevents CI failures from missing secret references.
"""

import re
import sys
from pathlib import Path

# Known configured secrets (from GITHUB_SECRETS_REMINDER hook)
# Note: Optional notification secrets are included but may not be configured
CONFIGURED_SECRETS = {
    # Core Alpaca (REQUIRED)
    "ALPACA_PAPER_TRADING_5K_API_KEY",
    "ALPACA_PAPER_TRADING_5K_API_SECRET",
    "ALPACA_BROKERAGE_TRADING_API_KEY",
    "ALPACA_BROKERAGE_TRADING_API_SECRET",
    "ALPACA_API_KEY",
    "ALPACA_API_SECRET",
    "ALPACA_PAPER_TRADING_API_KEY",
    "ALPACA_PAPER_TRADING_API_SECRET",
    # Google Cloud (REQUIRED)
    "GCP_SA_KEY",
    "GOOGLE_API_KEY",
    # GitHub (REQUIRED)
    "GH_PAT",
    "GITHUB_TOKEN",  # Built-in
    "CI_WRITE_TOKEN",
    # Content APIs (REQUIRED)
    "YOUTUBE_API_KEY",
    "DEVTO_API_KEY",
    # AI/LLM APIs (OPTIONAL - may not be configured)
    "ANTHROPIC_API_KEY",
    "OPENROUTER_API_KEY",
    "HELICONE_API_KEY",
    # Market Data APIs (OPTIONAL)
    "ALPHA_VANTAGE_API_KEY",
    "POLYGON_API_KEY",
    "FINNHUB_API_KEY",
    "FRED_API_KEY",
    # Notifications (OPTIONAL - gracefully degrade if missing)
    "SLACK_WEBHOOK_URL",
    "DISCORD_WEBHOOK_URL",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
    "SENDGRID_API_KEY",
    "CEO_EMAIL",
    # Feature flags
    "PAPER_TRADING",
}

# Pattern to find secret references
SECRET_PATTERN = re.compile(r"\$\{\{\s*secrets\.(\w+)\s*\}\}")


def validate_workflow(filepath: Path) -> list[str]:
    """Validate a single workflow file for secret references."""
    errors = []
    content = filepath.read_text()

    for match in SECRET_PATTERN.finditer(content):
        secret_name = match.group(1)
        if secret_name not in CONFIGURED_SECRETS:
            line_num = content[: match.start()].count("\n") + 1
            errors.append(f"{filepath}:{line_num}: Unknown secret '{secret_name}'")

    return errors


def main() -> int:
    """Validate all workflow files."""
    workflows_dir = Path(".github/workflows")

    if not workflows_dir.exists():
        print("✅ No workflows directory found")
        return 0

    all_errors = []

    for workflow_file in workflows_dir.glob("*.yml"):
        errors = validate_workflow(workflow_file)
        all_errors.extend(errors)

    for workflow_file in workflows_dir.glob("*.yaml"):
        errors = validate_workflow(workflow_file)
        all_errors.extend(errors)

    if all_errors:
        print("❌ Workflow secret validation failed:")
        for error in all_errors:
            print(f"  {error}")
        print(f"\n❌ Found {len(all_errors)} unknown secret references")
        print("💡 Add missing secrets to GitHub repo settings or update CONFIGURED_SECRETS")
        return 1

    print("✅ All workflow secrets are valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
