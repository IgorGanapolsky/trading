"""Top-level orchestrator that coordinates all support agents."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, List, Optional, Sequence

from .config_loader import DayTradingResourceConfig, load_resource_config
from .mentor_monitor import MentorMonitorAgent
from .models import DailySupportPlan, NewsletterInsight, ReadingAssignment
from .newsletter_harvester import MarketPrepAgent
from .reading_ingestor import StudyGuideAgent
from .resource_vault import ResourceVault


class DayTradeSupportOrchestrator:
    """Coordinates coaching, reading, and newsletter flows."""

    def __init__(
        self,
        *,
        config: Optional[DayTradingResourceConfig] = None,
        mentor_agent: Optional[MentorMonitorAgent] = None,
        study_agent: Optional[StudyGuideAgent] = None,
        market_agent: Optional[MarketPrepAgent] = None,
        vault: Optional[ResourceVault] = None,
    ) -> None:
        self.config = config or load_resource_config()
        self.mentor = mentor_agent or MentorMonitorAgent(self.config.coaching_programs)
        self.study = study_agent or StudyGuideAgent(self.config.books)
        self.market = market_agent or MarketPrepAgent(self.config.newsletters)
        self.vault = vault or ResourceVault()

    def run(
        self,
        *,
        focus_tags: Optional[Iterable[str]] = None,
        study_minutes: int = 45,
    ) -> DailySupportPlan:
        focus_list = list(focus_tags or [])
        coaching_sessions = self.mentor.build_schedule()
        reading_assignments = self.study.generate_assignments(
            focus_tags=focus_list, minutes=study_minutes
        )
        newsletter_insights = self.market.harvest()
        plan = DailySupportPlan(
            generated_at=datetime.now(timezone.utc),
            focus_areas=focus_list or ["psychology", "trade execution", "market prep"],
            coaching=coaching_sessions,
            reading=reading_assignments,
            newsletters=newsletter_insights,
        )
        self.vault.persist_plan(plan)
        return plan

    def summarize(self, plan: DailySupportPlan) -> str:
        lines = [
            f"Support plan generated at {plan.generated_at.isoformat()}",
            f"Focus areas: {', '.join(plan.focus_areas)}",
            f"Coaching sessions: {len(plan.coaching)}",
            f"Reading tasks: {len(plan.reading)}",
            f"Newsletter highlights: {len(plan.newsletters)}",
        ]
        return "\n".join(lines)
