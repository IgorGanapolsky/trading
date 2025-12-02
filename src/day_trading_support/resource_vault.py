"""Persistence + reporting helpers for the support orchestrator."""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

from .models import DailySupportPlan
from .vector_store import ResourceVectorStore


class ResourceVault:
    """Writes plan artifacts (JSON, Markdown, embeddings)."""

    def __init__(
        self,
        *,
        storage_dir: Path | str = Path("data/day_trading_resources"),
        report_dir: Path | str = Path("reports"),
        vector_store: ResourceVectorStore | None = None,
    ) -> None:
        self.storage_dir = Path(storage_dir)
        self.report_dir = Path(report_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.report_dir.mkdir(parents=True, exist_ok=True)
        self.state_path = self.storage_dir / "resource_state.json"
        self.vector_store = vector_store or ResourceVectorStore()

    def persist_plan(self, plan: DailySupportPlan) -> dict[str, Path]:
        payload = plan.to_dict()
        with open(self.state_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)

        date_suffix = plan.generated_at.strftime("%Y-%m-%d")
        dated_state = self.storage_dir / f"resource_state_{date_suffix}.json"
        with open(dated_state, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)

        markdown_path = self.report_dir / f"day_trading_support_{date_suffix}.md"
        markdown_path.write_text(self._build_markdown(plan), encoding="utf-8")

        self.vector_store.upsert_documents(self._build_vector_docs(plan))

        return {
            "state": self.state_path,
            "dated_state": dated_state,
            "report": markdown_path,
        }

    def _build_markdown(self, plan: DailySupportPlan) -> str:
        lines = [
            f"# Day-Trading Support Plan ({plan.generated_at.date()})",
            "",
            "## Focus Areas",
            "- " + "\n- ".join(plan.focus_areas) if plan.focus_areas else "- General prep",
            "",
            "## Coaching",
        ]
        if plan.coaching:
            for session in plan.coaching:
                timestamp = session.scheduled_for.isoformat()
                focus = ", ".join(session.focus)
                lines.append(
                    f"- **{session.program} · {session.session_name}** ({timestamp}) — {focus}"
                )
        else:
            lines.append("- No sessions scheduled")
        lines.append("\n## Reading Assignments")
        if plan.reading:
            for assignment in plan.reading:
                lines.append(
                    f"- **{assignment.book}** — {assignment.task} ({assignment.minutes} min)"
                )
        else:
            lines.append("- Add study block")
        lines.append("\n## Newsletter Highlights")
        if plan.newsletters:
            for insight in plan.newsletters[:5]:
                tickers = ", ".join(insight.tickers) or "No tickers"
                lines.append(f"- **{insight.source}**: {insight.headline} ({tickers})")
        else:
            lines.append("- No fresh newsletter items")
        return "\n".join(lines)

    def _build_vector_docs(self, plan: DailySupportPlan) -> Iterable[dict]:
        generated = plan.generated_at.strftime("%Y%m%dT%H%M")
        docs: list[dict] = []
        for idx, session in enumerate(plan.coaching):
            text = (
                f"Coaching session {session.session_name} from {session.program}"
                f" focusing on {', '.join(session.focus)} at {session.scheduled_for.isoformat()}"
            )
            docs.append(
                {
                    "id": f"coach-{generated}-{idx}",
                    "text": text,
                    "metadata": {
                        "type": "coaching",
                        "program": session.program,
                        "focus": session.focus,
                    },
                }
            )
        for idx, assignment in enumerate(plan.reading):
            docs.append(
                {
                    "id": f"reading-{generated}-{idx}",
                    "text": f"Study {assignment.book}: {assignment.task}",
                    "metadata": {
                        "type": "reading",
                        "book": assignment.book,
                        "tags": assignment.tags,
                    },
                }
            )
        for idx, insight in enumerate(plan.newsletters):
            docs.append(
                {
                    "id": f"newsletter-{generated}-{idx}",
                    "text": f"{insight.source}: {insight.headline} {insight.summary}",
                    "metadata": {
                        "type": "newsletter",
                        "source": insight.source,
                        "tickers": insight.tickers,
                    },
                }
            )
        return docs
