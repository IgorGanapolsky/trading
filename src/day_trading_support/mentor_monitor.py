"""MentorMonitorAgent converts coaching metadata into actionable schedules."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List, Optional

from zoneinfo import ZoneInfo

from .models import CoachSession, CoachingProgram, SessionTemplate


class MentorMonitorAgent:
    """Turns static program metadata into concrete coaching sessions."""

    def __init__(self, programs: List[CoachingProgram]) -> None:
        self.programs = programs

    def build_schedule(
        self,
        *,
        reference_time: Optional[datetime] = None,
        per_program: int = 2,
    ) -> List[CoachSession]:
        """Build next actionable sessions for each program."""

        now = reference_time or datetime.now(timezone.utc)
        sessions: List[CoachSession] = []
        for program in self.programs:
            tz = self._resolve_timezone(program.timezone)
            for template in program.session_templates[:per_program]:
                slot = self._next_occurrence(template, tz=tz, reference=now)
                if slot is None:
                    continue
                sessions.append(
                    CoachSession(
                        program=program.name,
                        session_name=template.name,
                        scheduled_for=slot,
                        format=template.format,
                        focus=list(template.focus),
                        duration_minutes=template.duration_minutes,
                        accountability_prompt=(
                            program.accountability_prompts[0]
                            if program.accountability_prompts
                            else None
                        ),
                        url=program.url,
                    )
                )
        sessions.sort(key=lambda s: s.scheduled_for)
        return sessions

    @staticmethod
    def _resolve_timezone(identifier: str) -> ZoneInfo:
        try:
            return ZoneInfo(identifier)
        except Exception:  # pragma: no cover - fall back to ET
            return ZoneInfo("America/New_York")

    def _next_occurrence(
        self,
        template: SessionTemplate,
        *,
        tz: ZoneInfo,
        reference: datetime,
    ) -> Optional[datetime]:
        cadence = template.cadence.lower()
        local_now = reference.astimezone(tz)
        start_hour, start_minute = self._parse_time(template.start_time)
        candidate = local_now.replace(
            hour=start_hour, minute=start_minute, second=0, microsecond=0
        )

        if cadence == "weekly":
            weekday = self._weekday_index(template.day_of_week)
            if weekday is None:
                weekday = 0
            delta_days = (weekday - local_now.weekday()) % 7
            candidate = candidate + timedelta(days=delta_days)
            if candidate <= local_now:
                candidate += timedelta(days=7)
        elif cadence in {"weekdays", "business"}:
            if local_now.weekday() >= 5:
                days_ahead = (7 - local_now.weekday()) % 7 or 1
                candidate = candidate + timedelta(days=days_ahead)
            if candidate <= local_now:
                candidate += timedelta(days=1)
        elif cadence == "adhoc":
            return None
        else:  # daily fallback
            if candidate <= local_now:
                candidate += timedelta(days=1)

        return candidate

    @staticmethod
    def _weekday_index(name: Optional[str]) -> Optional[int]:
        if not name:
            return None
        lookup = {
            "monday": 0,
            "tuesday": 1,
            "wednesday": 2,
            "thursday": 3,
            "friday": 4,
            "saturday": 5,
            "sunday": 6,
        }
        return lookup.get(name.lower())

    @staticmethod
    def _parse_time(value: str) -> tuple[int, int]:
        hour, minute = value.split(":", maxsplit=1)
        return int(hour), int(minute)
