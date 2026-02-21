"""Read-only local ops snapshot for Perplexity Local MCP command connectors."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SYSTEM_STATE_PATH = Path("data/system_state.json")
VERIFICATION_REPORTS_PATH = Path("data/verification_reports.json")
RAG_INDEX_PATH = Path("data/rag/lessons_query.json")
PUBLICATION_HISTORY_PATH = Path("data/analytics/publication-status-history.jsonl")
LESSONS_PATH = Path("rag_knowledge/lessons_learned")


def build_local_ops_snapshot(repo_root: Path, *, now: datetime | None = None) -> dict[str, Any]:
    """Build an immutable status payload for local AI assistants."""
    now_utc = (now or datetime.now(UTC)).astimezone(UTC)

    system_state_file = repo_root / SYSTEM_STATE_PATH
    verification_file = repo_root / VERIFICATION_REPORTS_PATH
    rag_index_file = repo_root / RAG_INDEX_PATH
    publication_file = repo_root / PUBLICATION_HISTORY_PATH
    lessons_dir = repo_root / LESSONS_PATH

    system_state = _read_json(system_state_file)
    verification_reports = _read_json(verification_file)
    latest_verification = _latest_verification_row(verification_reports)
    latest_publication = _latest_jsonl_row(publication_file)

    system_last_updated = _parse_dt(system_state.get("last_updated"))
    rag_index_updated = _file_mtime_utc(rag_index_file)
    lessons_count = len(list(lessons_dir.glob("*.md"))) if lessons_dir.exists() else 0

    paper_account = system_state.get("paper_account", {})
    positions = system_state.get("positions", [])

    trading = {
        "equity": _pick_first_number(
            paper_account.get("equity"),
            system_state.get("account", {}).get("current_equity"),
            system_state.get("portfolio", {}).get("equity"),
        ),
        "cash": _pick_first_number(
            paper_account.get("cash"),
            system_state.get("account", {}).get("cash"),
            system_state.get("portfolio", {}).get("cash"),
        ),
        "daily_pnl": _pick_first_number(
            paper_account.get("daily_change"),
            latest_verification.get("daily_pnl"),
        ),
        "positions_count": int(len(positions)) if isinstance(positions, list) else 0,
        "system_last_updated_utc": _to_iso(system_last_updated),
        "system_state_age_minutes": _age_minutes(system_last_updated, now_utc),
    }

    verification = {
        "latest_date": latest_verification.get("date"),
        "traded": latest_verification.get("traded"),
        "orders": latest_verification.get("orders"),
        "fills": latest_verification.get("fills"),
        "positions": latest_verification.get("positions"),
        "equity": latest_verification.get("equity"),
        "daily_pnl": latest_verification.get("daily_pnl"),
        "total_pnl": latest_verification.get("total_pnl"),
    }

    publishing = {
        "latest_date": latest_publication.get("date"),
        "latest_generated_at_utc": latest_publication.get("generated_at_utc"),
        "latest_generated_at_et": latest_publication.get("generated_at_et"),
        "platforms": latest_publication.get("platforms", {}),
    }

    rag = {
        "lessons_count": lessons_count,
        "query_index_updated_utc": _to_iso(rag_index_updated),
        "query_index_age_minutes": _age_minutes(rag_index_updated, now_utc),
    }

    health_flags = {
        "system_state_stale": bool(
            trading["system_state_age_minutes"] is None or trading["system_state_age_minutes"] > 180
        ),
        "rag_index_stale": bool(
            rag["query_index_age_minutes"] is None or rag["query_index_age_minutes"] > 1440
        ),
        "verification_missing": not bool(verification.get("latest_date")),
        "publishing_missing": not bool(publishing.get("latest_date")),
    }

    return {
        "generated_at_utc": _to_iso(now_utc),
        "repo_root": str(repo_root),
        "trading": trading,
        "verification": verification,
        "rag": rag,
        "publishing": publishing,
        "health_flags": health_flags,
        "sources": {
            "system_state": _source_meta(system_state_file),
            "verification_reports": _source_meta(verification_file),
            "rag_index": _source_meta(rag_index_file),
            "publication_history": _source_meta(publication_file),
        },
    }


def render_local_ops_markdown(snapshot: dict[str, Any]) -> str:
    """Render a compact markdown status block for chat assistants."""
    trading = snapshot.get("trading", {})
    verification = snapshot.get("verification", {})
    rag = snapshot.get("rag", {})
    publishing = snapshot.get("publishing", {})
    health_flags = snapshot.get("health_flags", {})

    lines = [
        "# Local Ops Snapshot",
        "",
        f"- Generated (UTC): `{snapshot.get('generated_at_utc', 'N/A')}`",
        "",
        "## Trading",
        f"- Equity: `{trading.get('equity')}`",
        f"- Cash: `{trading.get('cash')}`",
        f"- Daily P/L: `{trading.get('daily_pnl')}`",
        f"- Positions: `{trading.get('positions_count')}`",
        f"- System last updated (UTC): `{trading.get('system_last_updated_utc')}`",
        f"- System age (minutes): `{trading.get('system_state_age_minutes')}`",
        "",
        "## Verification",
        f"- Latest report date: `{verification.get('latest_date')}`",
        f"- Traded: `{verification.get('traded')}`",
        f"- Orders/Fills: `{verification.get('orders')}` / `{verification.get('fills')}`",
        f"- Verification daily P/L: `{verification.get('daily_pnl')}`",
        "",
        "## RAG",
        f"- Lessons count: `{rag.get('lessons_count')}`",
        f"- Query index updated (UTC): `{rag.get('query_index_updated_utc')}`",
        f"- Query index age (minutes): `{rag.get('query_index_age_minutes')}`",
        "",
        "## Publishing",
        f"- Latest publication date: `{publishing.get('latest_date')}`",
        f"- Latest generated (UTC): `{publishing.get('latest_generated_at_utc')}`",
        "",
        "## Health Flags",
        f"- system_state_stale: `{health_flags.get('system_state_stale')}`",
        f"- rag_index_stale: `{health_flags.get('rag_index_stale')}`",
        f"- verification_missing: `{health_flags.get('verification_missing')}`",
        f"- publishing_missing: `{health_flags.get('publishing_missing')}`",
    ]
    return "\n".join(lines) + "\n"


def _read_json(path: Path) -> dict[str, Any] | list[Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, (dict, list)):
            return payload
        return {}
    except Exception:
        return {}


def _latest_verification_row(payload: dict[str, Any] | list[Any]) -> dict[str, Any]:
    if isinstance(payload, list):
        rows = [row for row in payload if isinstance(row, dict)]
        if not rows:
            return {}
        return rows[-1]
    if isinstance(payload, dict):
        return payload
    return {}


def _latest_jsonl_row(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    latest: dict[str, Any] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            latest = payload
    return latest


def _source_meta(path: Path) -> dict[str, Any]:
    mtime = _file_mtime_utc(path)
    return {
        "exists": path.exists(),
        "mtime_utc": _to_iso(mtime),
    }


def _parse_dt(value: Any) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        text = value.replace("Z", "+00:00")
        return datetime.fromisoformat(text).astimezone(UTC)
    except ValueError:
        return None


def _file_mtime_utc(path: Path) -> datetime | None:
    if not path.exists():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)


def _to_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _age_minutes(value: datetime | None, now_utc: datetime) -> float | None:
    if value is None:
        return None
    return round((now_utc - value).total_seconds() / 60.0, 3)


def _pick_first_number(*values: Any) -> float | None:
    for value in values:
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None
