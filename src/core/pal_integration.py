"""
PAL (Provider Abstraction Layer) Integration for Trading Decisions

This module integrates PAL MCP Server's Challenge and Debug tools to prevent
errors in trading decisions through adversarial validation and systematic debugging.

Key tools:
- Challenge: Forces devil's advocate examination of council recommendations
- Debug: Systematic hypothesis-driven debugging for performance investigations

Reference: https://github.com/BeehiveInnovations/pal-mcp-server
"""

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ChallengeResult:
    """Result from PAL Challenge tool."""

    risk_score: float  # 0-1, higher = more risk identified
    concerns: list[str]  # Specific risks identified
    counter_arguments: list[str]  # Arguments against the proposal
    should_proceed: bool  # Overall recommendation
    confidence: float  # Confidence in the challenge assessment
    raw_response: str  # Full response text


@dataclass
class DebugResult:
    """Result from PAL Debug tool."""

    root_cause: str
    confidence: str  # "exploring" | "low" | "medium" | "high" | "certain"
    hypotheses: list[dict[str, Any]]  # Tracked hypotheses with status
    evidence: list[str]  # Evidence gathered
    recommendations: list[str]  # Suggested fixes
    raw_response: str


@dataclass
class CouncilDecisionAudit:
    """Audit record for a council decision."""

    timestamp: str
    symbol: str
    action: str  # BUY, SELL, HOLD
    council_decision: str  # APPROVED, REJECTED
    council_confidence: float
    individual_votes: dict[str, str]  # model -> vote
    challenge_performed: bool = False
    challenge_risk_score: float | None = None
    challenge_concerns: list[str] = field(default_factory=list)
    final_decision: str = ""  # After challenge
    entry_price: float | None = None
    exit_price: float | None = None
    actual_outcome: str = "PENDING"  # PENDING, WIN, LOSS
    pl: float | None = None
    pl_pct: float | None = None


class PALIntegration:
    """
    Integration layer for PAL MCP Server tools.

    Provides adversarial validation (Challenge) and systematic debugging (Debug)
    to prevent errors in trading decisions.
    """

    def __init__(
        self,
        enabled: bool = True,
        challenge_threshold: float = 0.7,  # Block if risk_score > threshold
        audit_path: Path | None = None,
    ):
        """
        Initialize PAL integration.

        Args:
            enabled: Whether PAL integration is active
            challenge_threshold: Risk score threshold to block trades (0-1)
            audit_path: Path for decision audit logs
        """
        self.enabled = enabled and os.getenv("PAL_ENABLED", "true").lower() == "true"
        self.challenge_threshold = challenge_threshold
        self.audit_path = audit_path or Path("data/council_decisions.json")
        self._decisions: list[CouncilDecisionAudit] = []
        self._load_audit_history()

        if self.enabled:
            logger.info(f"PAL Integration enabled (challenge_threshold={challenge_threshold})")
        else:
            logger.info("PAL Integration disabled")

    def _load_audit_history(self) -> None:
        """Load existing decision audit history."""
        if self.audit_path.exists():
            try:
                with open(self.audit_path) as f:
                    data = json.load(f)
                    self._decisions = [CouncilDecisionAudit(**d) for d in data.get("decisions", [])]
                logger.info(f"Loaded {len(self._decisions)} historical decisions")
            except Exception as e:
                logger.warning(f"Could not load audit history: {e}")
                self._decisions = []

    def _save_audit(self) -> None:
        """Persist decision audit to disk."""
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)

        # Calculate metrics
        total = len(self._decisions)
        approved = sum(1 for d in self._decisions if d.council_decision == "APPROVED")
        challenged = sum(1 for d in self._decisions if d.challenge_performed)
        blocked = sum(
            1 for d in self._decisions if d.challenge_performed and d.final_decision == "BLOCKED"
        )
        wins = sum(1 for d in self._decisions if d.actual_outcome == "WIN")
        losses = sum(1 for d in self._decisions if d.actual_outcome == "LOSS")

        data = {
            "last_updated": datetime.now().isoformat(),
            "metrics": {
                "total_decisions": total,
                "approved": approved,
                "rejected": total - approved,
                "challenged": challenged,
                "blocked_by_challenge": blocked,
                "wins": wins,
                "losses": losses,
                "win_rate": wins / (wins + losses) if (wins + losses) > 0 else 0.0,
                "challenge_block_rate": blocked / challenged if challenged > 0 else 0.0,
            },
            "decisions": [
                {
                    "timestamp": d.timestamp,
                    "symbol": d.symbol,
                    "action": d.action,
                    "council_decision": d.council_decision,
                    "council_confidence": d.council_confidence,
                    "individual_votes": d.individual_votes,
                    "challenge_performed": d.challenge_performed,
                    "challenge_risk_score": d.challenge_risk_score,
                    "challenge_concerns": d.challenge_concerns,
                    "final_decision": d.final_decision,
                    "entry_price": d.entry_price,
                    "exit_price": d.exit_price,
                    "actual_outcome": d.actual_outcome,
                    "pl": d.pl,
                    "pl_pct": d.pl_pct,
                }
                for d in self._decisions
            ],
        }

        with open(self.audit_path, "w") as f:
            json.dump(data, f, indent=2)

        logger.debug(f"Saved {total} decisions to {self.audit_path}")

    async def challenge_recommendation(
        self,
        symbol: str,
        action: str,
        council_reasoning: str,
        market_data: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> ChallengeResult:
        """
        Challenge a council recommendation using devil's advocate analysis.

        Forces examination of risks and counter-arguments that the council
        may have overlooked due to groupthink or confirmation bias.

        Args:
            symbol: Stock symbol
            action: Proposed action (BUY/SELL/HOLD)
            council_reasoning: Council's reasoning for the recommendation
            market_data: Market data (price, indicators, etc.)
            context: Additional context

        Returns:
            ChallengeResult with risk assessment and counter-arguments
        """
        if not self.enabled:
            return ChallengeResult(
                risk_score=0.0,
                concerns=[],
                counter_arguments=[],
                should_proceed=True,
                confidence=0.0,
                raw_response="PAL disabled",
            )

        try:
            # Build challenge prompt
            challenge_prompt = f"""You are playing devil's advocate for a trading decision.

The LLM Council has recommended: {action} {symbol}

Council's Reasoning:
{council_reasoning}

Market Data:
{json.dumps(market_data, indent=2)}

Your task is to CHALLENGE this recommendation:

1. What are the strongest arguments AGAINST this trade?
2. What risks is the council overlooking?
3. What would need to change for you to reject this trade?
4. Rate the overall risk (0.0 = safe, 1.0 = very risky)

Be thorough and skeptical. Your job is to find problems, not agree.

Format your response as:
RISK_SCORE: [0.0-1.0]
CONCERNS:
- [concern 1]
- [concern 2]
COUNTER_ARGUMENTS:
- [argument 1]
- [argument 2]
SHOULD_PROCEED: [YES/NO]
CONFIDENCE: [0.0-1.0]
"""

            # In production, this would call PAL MCP server
            # For now, we use our existing multi-LLM infrastructure
            from src.core.multi_llm_analysis import MultiLLMAnalyzer

            analyzer = MultiLLMAnalyzer()
            response = await analyzer.analyze(
                query=challenge_prompt,
                system_prompt=(
                    "You are a critical risk analyst. Your job is to find problems "
                    "with trading recommendations, not to agree with them. "
                    "Be skeptical and thorough."
                ),
            )

            # Parse response
            result = self._parse_challenge_response(response.content)
            logger.info(
                f"Challenge for {action} {symbol}: "
                f"risk_score={result.risk_score:.2f}, proceed={result.should_proceed}"
            )
            return result

        except Exception as e:
            logger.error(f"Challenge failed: {e}", exc_info=True)
            return ChallengeResult(
                risk_score=0.5,
                concerns=[f"Challenge error: {str(e)}"],
                counter_arguments=[],
                should_proceed=True,  # Fail-open
                confidence=0.0,
                raw_response=str(e),
            )

    def _parse_challenge_response(self, response: str) -> ChallengeResult:
        """Parse challenge response into structured result."""
        lines = response.strip().split("\n")

        risk_score = 0.5
        concerns = []
        counter_arguments = []
        should_proceed = True
        confidence = 0.5

        current_section = None

        for line in lines:
            line = line.strip()
            if not line:
                continue

            if line.startswith("RISK_SCORE:"):
                try:
                    risk_score = float(line.split(":")[1].strip())
                except (IndexError, ValueError):
                    pass
            elif line.startswith("CONCERNS:"):
                current_section = "concerns"
            elif line.startswith("COUNTER_ARGUMENTS:"):
                current_section = "counter_arguments"
            elif line.startswith("SHOULD_PROCEED:"):
                val = line.split(":")[1].strip().upper()
                should_proceed = val in ("YES", "TRUE", "1")
            elif line.startswith("CONFIDENCE:"):
                try:
                    confidence = float(line.split(":")[1].strip())
                except (IndexError, ValueError):
                    pass
            elif line.startswith("- "):
                item = line[2:].strip()
                if current_section == "concerns":
                    concerns.append(item)
                elif current_section == "counter_arguments":
                    counter_arguments.append(item)

        return ChallengeResult(
            risk_score=min(max(risk_score, 0.0), 1.0),
            concerns=concerns,
            counter_arguments=counter_arguments,
            should_proceed=should_proceed,
            confidence=min(max(confidence, 0.0), 1.0),
            raw_response=response,
        )

    async def debug_performance_issue(
        self,
        problem: str,
        context: dict[str, Any],
    ) -> DebugResult:
        """
        Systematically debug a performance issue with hypothesis tracking.

        Uses structured reasoning to identify root causes with confidence levels.

        Args:
            problem: Description of the issue (e.g., "Win rate dropped from 60% to 45%")
            context: System state, recent trades, market conditions

        Returns:
            DebugResult with root cause analysis and recommendations
        """
        if not self.enabled:
            return DebugResult(
                root_cause="PAL disabled",
                confidence="low",
                hypotheses=[],
                evidence=[],
                recommendations=["Enable PAL for debugging"],
                raw_response="PAL disabled",
            )

        try:
            debug_prompt = f"""You are systematically debugging a trading system issue.

PROBLEM: {problem}

CONTEXT:
{json.dumps(context, indent=2)}

Perform hypothesis-driven debugging:

1. Generate 3-5 hypotheses for what might be causing this problem
2. For each hypothesis, identify what evidence would confirm or refute it
3. Based on available context, rate confidence in each hypothesis
4. Identify the most likely root cause
5. Provide specific recommendations to fix it

Format your response as:
ROOT_CAUSE: [most likely cause]
CONFIDENCE: [exploring|low|medium|high|certain]

HYPOTHESES:
H1: [hypothesis] | Confidence: [level] | Evidence: [what supports/refutes]
H2: [hypothesis] | Confidence: [level] | Evidence: [what supports/refutes]
...

EVIDENCE:
- [evidence 1]
- [evidence 2]

RECOMMENDATIONS:
- [action 1]
- [action 2]
"""

            from src.core.multi_llm_analysis import MultiLLMAnalyzer

            analyzer = MultiLLMAnalyzer()
            response = await analyzer.analyze(
                query=debug_prompt,
                system_prompt=(
                    "You are a systematic debugger. Use hypothesis-driven reasoning "
                    "to identify root causes. Be thorough and evidence-based."
                ),
            )

            result = self._parse_debug_response(response.analysis)
            logger.info(
                f"Debug result: root_cause='{result.root_cause[:50]}...', "
                f"confidence={result.confidence}"
            )
            return result

        except Exception as e:
            logger.error(f"Debug failed: {e}", exc_info=True)
            return DebugResult(
                root_cause=f"Debug error: {str(e)}",
                confidence="low",
                hypotheses=[],
                evidence=[],
                recommendations=["Fix debugging infrastructure"],
                raw_response=str(e),
            )

    def _parse_debug_response(self, response: str) -> DebugResult:
        """Parse debug response into structured result."""
        lines = response.strip().split("\n")

        root_cause = "Unknown"
        confidence = "low"
        hypotheses = []
        evidence = []
        recommendations = []
        current_section = None

        for line in lines:
            line = line.strip()
            if not line:
                continue

            if line.startswith("ROOT_CAUSE:"):
                root_cause = line.split(":", 1)[1].strip()
            elif line.startswith("CONFIDENCE:"):
                conf = line.split(":")[1].strip().lower()
                if conf in ("exploring", "low", "medium", "high", "certain"):
                    confidence = conf
            elif line.startswith("HYPOTHESES:"):
                current_section = "hypotheses"
            elif line.startswith("EVIDENCE:"):
                current_section = "evidence"
            elif line.startswith("RECOMMENDATIONS:"):
                current_section = "recommendations"
            elif line.startswith("H") and current_section == "hypotheses":
                # Parse hypothesis line: H1: [hypothesis] | Confidence: [level] | Evidence: [...]
                parts = line.split("|")
                if len(parts) >= 1:
                    hyp_text = (
                        parts[0].split(":", 1)[-1].strip() if ":" in parts[0] else parts[0].strip()
                    )
                    hyp_conf = "low"
                    hyp_evidence = ""
                    for part in parts[1:]:
                        if "Confidence:" in part:
                            hyp_conf = part.split(":")[1].strip().lower()
                        elif "Evidence:" in part:
                            hyp_evidence = part.split(":", 1)[1].strip()
                    hypotheses.append(
                        {"hypothesis": hyp_text, "confidence": hyp_conf, "evidence": hyp_evidence}
                    )
            elif line.startswith("- "):
                item = line[2:].strip()
                if current_section == "evidence":
                    evidence.append(item)
                elif current_section == "recommendations":
                    recommendations.append(item)

        return DebugResult(
            root_cause=root_cause,
            confidence=confidence,
            hypotheses=hypotheses,
            evidence=evidence,
            recommendations=recommendations,
            raw_response=response,
        )

    def record_decision(
        self,
        symbol: str,
        action: str,
        council_decision: str,
        council_confidence: float,
        individual_votes: dict[str, str],
        challenge_result: ChallengeResult | None = None,
        final_decision: str = "",
        entry_price: float | None = None,
    ) -> None:
        """
        Record a council decision for audit purposes.

        Args:
            symbol: Stock symbol
            action: Proposed action
            council_decision: APPROVED or REJECTED
            council_confidence: Council's confidence (0-1)
            individual_votes: How each model voted
            challenge_result: Result from challenge (if performed)
            final_decision: Final decision after challenge
            entry_price: Entry price if trade executed
        """
        decision = CouncilDecisionAudit(
            timestamp=datetime.now().isoformat(),
            symbol=symbol,
            action=action,
            council_decision=council_decision,
            council_confidence=council_confidence,
            individual_votes=individual_votes,
            challenge_performed=challenge_result is not None,
            challenge_risk_score=challenge_result.risk_score if challenge_result else None,
            challenge_concerns=challenge_result.concerns if challenge_result else [],
            final_decision=final_decision or council_decision,
            entry_price=entry_price,
        )

        self._decisions.append(decision)
        self._save_audit()

        logger.info(
            f"Recorded decision: {action} {symbol} -> {final_decision} "
            f"(council={council_decision}, conf={council_confidence:.2%})"
        )

    def update_outcome(
        self,
        symbol: str,
        exit_price: float,
        pl: float,
        pl_pct: float,
    ) -> None:
        """
        Update a decision with actual outcome after trade closes.

        Args:
            symbol: Stock symbol to update
            exit_price: Exit price
            pl: Profit/loss amount
            pl_pct: Profit/loss percentage
        """
        # Find most recent pending decision for this symbol
        for decision in reversed(self._decisions):
            if decision.symbol == symbol and decision.actual_outcome == "PENDING":
                decision.exit_price = exit_price
                decision.pl = pl
                decision.pl_pct = pl_pct
                decision.actual_outcome = "WIN" if pl > 0 else "LOSS"
                self._save_audit()
                logger.info(
                    f"Updated outcome for {symbol}: {decision.actual_outcome} "
                    f"(P/L: ${pl:.2f}, {pl_pct:.2%})"
                )
                return

        logger.warning(f"No pending decision found for {symbol}")

    def get_metrics(self) -> dict[str, Any]:
        """Get current decision metrics."""
        total = len(self._decisions)
        if total == 0:
            return {"total": 0, "message": "No decisions recorded yet"}

        approved = sum(1 for d in self._decisions if d.council_decision == "APPROVED")
        challenged = sum(1 for d in self._decisions if d.challenge_performed)
        blocked = sum(
            1 for d in self._decisions if d.challenge_performed and d.final_decision == "BLOCKED"
        )
        wins = sum(1 for d in self._decisions if d.actual_outcome == "WIN")
        losses = sum(1 for d in self._decisions if d.actual_outcome == "LOSS")
        pending = sum(1 for d in self._decisions if d.actual_outcome == "PENDING")

        # Confidence calibration: Are high-confidence decisions more accurate?
        high_conf_decisions = [d for d in self._decisions if d.council_confidence >= 0.7]
        high_conf_wins = sum(1 for d in high_conf_decisions if d.actual_outcome == "WIN")
        high_conf_total = sum(1 for d in high_conf_decisions if d.actual_outcome in ("WIN", "LOSS"))

        return {
            "total_decisions": total,
            "approved": approved,
            "rejected": total - approved,
            "approval_rate": approved / total,
            "challenged": challenged,
            "blocked_by_challenge": blocked,
            "challenge_block_rate": blocked / challenged if challenged > 0 else 0.0,
            "wins": wins,
            "losses": losses,
            "pending": pending,
            "win_rate": wins / (wins + losses) if (wins + losses) > 0 else None,
            "high_confidence_win_rate": (
                high_conf_wins / high_conf_total if high_conf_total > 0 else None
            ),
            "average_confidence": (sum(d.council_confidence for d in self._decisions) / total),
        }


# Singleton instance for easy access
_pal_instance: PALIntegration | None = None


def get_pal() -> PALIntegration:
    """Get or create PAL integration instance."""
    global _pal_instance
    if _pal_instance is None:
        _pal_instance = PALIntegration()
    return _pal_instance
