"""
ADK-Go orchestrator client.

This module provides a thin HTTP client for the Go-based ADK service located in
`go/adk_trading`. It allows the Python trading stack to delegate research loops
to the Go multi-agent orchestrator without duplicating the coordination logic.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

import requests

logger = logging.getLogger(__name__)


DEFAULT_BASE_URL = "http://127.0.0.1:8080/api"
DEFAULT_APP_NAME = "trading_orchestrator"
DEFAULT_ROOT_AGENT = "trading_orchestrator_root_agent"
DEFAULT_USER_ID = "python-stack"


@dataclass(slots=True)
class ADKClientConfig:
    base_url: str = DEFAULT_BASE_URL
    app_name: str = DEFAULT_APP_NAME
    root_agent_name: str = DEFAULT_ROOT_AGENT
    user_id: str = DEFAULT_USER_ID
    request_timeout: float = 60.0
    ensure_session: bool = True


@dataclass(slots=True)
class OrchestratorResult:
    session_id: str
    events: list[dict[str, Any]] = field(default_factory=list)
    final_text: str | None = None
    root_event: dict[str, Any] | None = None

    def as_structured(self) -> dict[str, Any] | None:
        """
        Parse the final orchestrator response as JSON if possible.

        Returns:
            Parsed dictionary when the response is valid JSON, otherwise None.
        """
        if not self.final_text:
            return None
        try:
            return json.loads(self.final_text)
        except json.JSONDecodeError as exc:
            logger.warning("Failed to parse orchestrator response: %s", exc)
            return None


class ADKOrchestratorClient:
    """
    Minimal HTTP client for the ADK REST API.

    Usage:
        client = ADKOrchestratorClient()
        result = client.run("NVDA", context={"mode": "paper"})
    """

    def __init__(self, config: ADKClientConfig | None = None) -> None:
        self.config = config or ADKClientConfig()
        self._http = requests.Session()
        self._http.headers.update({"Content-Type": "application/json"})

    def run(
        self,
        symbol: str,
        context: dict[str, Any] | None = None,
        *,
        session_id: str | None = None,
        streaming: bool = False,
    ) -> OrchestratorResult:
        session_id = session_id or self._generate_session_id(symbol)
        if self.config.ensure_session:
            self._ensure_session(session_id)

        payload = self._build_run_payload(
            symbol=symbol,
            context=context or {},
            session_id=session_id,
            streaming=streaming,
        )

        url = f"{self.config.base_url.rstrip('/')}/run"
        logger.debug("POST %s payload=%s", url, payload)
        response = self._http.post(
            url,
            data=json.dumps(payload),
            timeout=self.config.request_timeout,
        )
        response.raise_for_status()
        events: list[dict[str, Any]] = response.json()
        root_event = self._select_root_event(events)
        final_text = _extract_text(root_event)
        logger.info("ADK run complete for %s session=%s", symbol, session_id)
        return OrchestratorResult(
            session_id=session_id,
            events=events,
            final_text=final_text,
            root_event=root_event,
        )

    def run_structured(
        self,
        symbol: str,
        context: dict[str, Any] | None = None,
        *,
        session_id: str | None = None,
        streaming: bool = False,
        require_json: bool = True,
    ) -> dict[str, Any]:
        """
        Execute the orchestrator and return the parsed JSON payload.

        Args:
            symbol: Target symbol to analyze.
            context: Optional auxiliary context dict to embed in the prompt.
            session_id: Override the session identifier.
            streaming: Enable SSE streaming if True.
            require_json: If True, raise ValueError when the response is not JSON.

        Returns:
            Parsed dictionary produced by the root ADK agent.
        """
        result = self.run(
            symbol,
            context=context,
            session_id=session_id,
            streaming=streaming,
        )
        parsed = result.as_structured()
        if parsed is None:
            if require_json:
                raise ValueError("ADK orchestrator did not return valid JSON payload")
            return {}
        return parsed

    # --------------------------------------------------------------------- #
    # Internal helpers
    # --------------------------------------------------------------------- #

    def _ensure_session(self, session_id: str) -> None:
        url = (
            f"{self.config.base_url.rstrip('/')}/apps/"
            f"{self.config.app_name}/users/{self.config.user_id}/sessions/{session_id}"
        )
        logger.debug("Ensuring ADK session %s", url)
        response = self._http.post(
            url,
            data=json.dumps({"state": {}}),
            timeout=self.config.request_timeout,
        )
        if response.status_code >= 400:
            logger.error(
                "Failed to ensure ADK session %s: %s %s",
                session_id,
                response.status_code,
                response.text,
            )
            response.raise_for_status()

    def _build_run_payload(
        self,
        *,
        symbol: str,
        context: dict[str, Any],
        session_id: str,
        streaming: bool,
    ) -> dict[str, Any]:
        message = self._build_prompt(symbol, context)
        new_message = {
            "role": "user",
            "parts": [{"text": message}],
        }
        return {
            "appName": self.config.app_name,
            "userId": self.config.user_id,
            "sessionId": session_id,
            "newMessage": new_message,
            "streaming": streaming,
        }

    def _build_prompt(self, symbol: str, context: dict[str, Any]) -> str:
        serialized_context = json.dumps(context, indent=2, sort_keys=True)
        return (
            f"Run the ADK trading orchestrator end-to-end for symbol {symbol.upper()}.\n"
            f"Context JSON:\n{serialized_context}\n"
            "Return the final JSON summary produced by the orchestrator."
        )

    def _select_root_event(self, events: Iterable[dict[str, Any]]) -> dict[str, Any] | None:
        root_name = self.config.root_agent_name
        for event in reversed(list(events)):
            if event.get("author") == root_name and not event.get("partial", False):
                return event
        return None

    def _generate_session_id(self, symbol: str) -> str:
        suffix = uuid.uuid4().hex[:8]
        timestamp = int(time.time())
        return f"{symbol.lower()}-{timestamp}-{suffix}"


def _extract_text(event: dict[str, Any] | None) -> str | None:
    if not event:
        return None
    content = event.get("content") or {}
    parts = content.get("parts") or []
    texts = [part.get("text", "") for part in parts if isinstance(part, dict)]
    combined = "\n".join(filter(None, texts)).strip()
    return combined or None
