import logging
from typing import Any

from src.agents.base_agent import BaseAgent
from src.orchestration.elite_orchestrator import EliteOrchestrator
from src.safety.chaos_monkey import chaos_monkey

logger = logging.getLogger(__name__)


class ChaosOrchestratorAgent(BaseAgent):
    """
    Chaos Orchestrator Agent: Autonomous Resilience Testing.

    Responsibilities:
    - Schedule and execute Chaos Drills
    - Determine drill parameters (latency, error rates) based on system stability
    - Analyze drill results and adjust future tests
    """

    def __init__(self):
        super().__init__(
            name="ChaosOrchestratorAgent",
            role="Resilience testing and chaos engineering orchestration",
        )

    def analyze(self, data: dict[str, Any] = None) -> dict[str, Any]:
        """
        Decide whether to run a chaos drill.

        Args:
            data: System health data (optional)

        Returns:
            Drill decision and results
        """
        logger.info("🔥 Chaos Orchestrator: Evaluating drill conditions...")

        # 1. Decide on Drill Parameters using LLM
        # In a real system, this would look at recent stability.
        # For now, we randomize slightly but ask LLM for "approval" to simulate reasoning.

        # Goldilocks Prompt: Principle-based chaos engineering with examples
        prompt = """Decide: Run chaos drill now? Balance resilience testing against production stability.

SYSTEM: STABLE | Last Drill: Unknown | Market Hours: Active

INTENSITIES:
- LOW: 10% failures, 100-500ms latency (safe for market hours)
- MEDIUM: 30% failures, 500-2000ms latency (after-hours preferred)
- HIGH: 50% failures, 1-5s latency (maintenance windows only)

PRINCIPLES (Netflix Chaos Engineering):
- Systems that aren't tested will fail unexpectedly (test proactively)
- Never drill during critical trading windows (9:30-10:00 AM, 3:30-4:00 PM)
- Increase intensity gradually - earn confidence before HIGH drills
- If last drill failed, run LOW to verify fixes before escalating

EXAMPLES:
Example 1 - Run LOW Drill:
DECISION: YES
INTENSITY: LOW
REASONING: System stable for 7 days, no recent drills. LOW intensity safe during light trading. Validates basic resilience.

Example 2 - Skip Drill:
DECISION: NO
INTENSITY: N/A
REASONING: Market opening in 15 minutes. Never drill near market transitions. Schedule for after 10:30 AM.

Example 3 - Run MEDIUM:
DECISION: YES
INTENSITY: MEDIUM
REASONING: After-hours, 3 consecutive successful LOW drills. Time to stress-test with higher intensity.

NOW DECIDE:
DECISION: [YES/NO]
INTENSITY: [LOW/MEDIUM/HIGH or N/A]
REASONING: [Why this decision maintains anti-fragility]"""

        response = self.reason_with_llm(prompt)
        reasoning = response.get("reasoning", "").upper()

        if "NO" in reasoning and "YES" not in reasoning:
            return {"action": "SKIP_DRILL", "reasoning": reasoning}

        # Parse intensity
        intensity = "LOW"
        if "HIGH" in reasoning:
            intensity = "HIGH"
        elif "MEDIUM" in reasoning:
            intensity = "MEDIUM"

        # 2. Configure Chaos Monkey
        config = self._get_config_for_intensity(intensity)
        chaos_monkey.enabled = True
        chaos_monkey.probability = config["probability"]

        self.log_decision({"action": "START_DRILL", "intensity": intensity, "config": config})

        # 3. Execute Drill (Run a trading cycle under chaos)
        logger.info(f"🚀 STARTING {intensity} INTENSITY CHAOS DRILL")
        orchestrator = EliteOrchestrator(paper=True)

        drill_results = {}
        try:
            # We inject latency/errors into this specific run via the global chaos_monkey we just configured
            drill_results = orchestrator.run_trading_cycle(symbols=["SPY", "QQQ"])
            drill_results["status"] = "SURVIVED"
        except Exception as e:
            logger.error(f"❌ System FAILED Chaos Drill: {e}")
            drill_results["status"] = "FAILED"
            drill_results["error"] = str(e)
        finally:
            # Reset Chaos Monkey
            chaos_monkey.enabled = False

        # 4. Report
        return {
            "action": "DRILL_COMPLETE",
            "intensity": intensity,
            "result": drill_results["status"],
            "details": drill_results,
        }

    def _get_config_for_intensity(self, intensity: str) -> dict[str, Any]:
        if intensity == "HIGH":
            return {"probability": 0.5, "min_ms": 1000, "max_ms": 5000}
        elif intensity == "MEDIUM":
            return {"probability": 0.3, "min_ms": 500, "max_ms": 2000}
        else:
            return {"probability": 0.1, "min_ms": 100, "max_ms": 500}
