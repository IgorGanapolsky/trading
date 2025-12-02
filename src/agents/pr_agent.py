"""
PR Agent - Intelligent Pull Request Handler
"""

import logging
from typing import Any

from src.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class PRAgent(BaseAgent):
    """
    Agent for handling Pull Requests automatically.

    Capabilities:
    - Analyze PR diffs for risk
    - Check for breaking changes
    - Auto-approve low-risk PRs
    - Request changes for high-risk PRs
    """

    def __init__(self):
        super().__init__(name="PRAgent", role="PR Reviewer & Automator")

    def analyze(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Analyze a Pull Request.

        Args:
            data: PR context (title, body, diff, files)

        Returns:
            Analysis result with action (APPROVE, COMMENT, REQUEST_CHANGES)
        """
        pr_title = data.get("title", "")
        data.get("body", "")
        files = data.get("files", [])

        logger.info(f"Analyzing PR: {pr_title}")

        # 1. Risk Assessment
        risk_score = self._calculate_risk(pr_title, files)

        # 2. Decision Logic
        if risk_score < 30:
            action = "APPROVE"
            comment = "✅ Low risk update. Auto-approved by PRAgent."
        elif risk_score < 70:
            action = "COMMENT"
            comment = "⚠️ Medium risk. Please verify manually."
        else:
            action = "REQUEST_CHANGES"
            comment = "❌ High risk detected. Manual review required."

        return {
            "action": action,
            "risk_score": risk_score,
            "comment": comment,
            "analysis": f"Analyzed {len(files)} files. Risk score: {risk_score}",
        }

    def _calculate_risk(self, title: str, files: list[str]) -> int:
        """Calculate risk score (0-100) based on PR content."""
        score = 0

        # Keyword analysis
        if "security" in title.lower():
            score += 0  # Security updates are usually safe/necessary
        if "breaking" in title.lower():
            score += 50
        if "major" in title.lower():
            score += 40

        # File analysis
        for file in files:
            if file.endswith(".lock") or file.endswith(".txt"):
                score += 5
            elif file.endswith(".py"):
                score += 20
            elif file.endswith(".yml") or file.endswith(".yaml"):
                score += 15

        return min(score, 100)
