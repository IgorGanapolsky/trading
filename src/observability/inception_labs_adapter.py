"""Inception Labs Mercury 2 Model Adapter.

Integrates Inception Labs high-speed Mercury 2 model API (https://platform.inceptionlabs.ai/)
for 100M free token high-throughput RAG search, tool calling, and subagent loops.
"""

from __future__ import annotations

import json
import logging
import os
import requests
from dataclasses import dataclass
from pathlib import Path
from dotenv import dotenv_values

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
INCEPTION_BASE_URL = "https://api.inceptionlabs.ai/v1"


@dataclass
class InceptionResponse:
    content: str
    model: str
    tokens_used: int
    success: bool
    status_code: int


class InceptionLabsMercuryAdapter:
    """Manages Inception Labs Mercury 2 model inference & 100M free token routing."""

    def __init__(self, api_key: str | None = None, env_path: Path | None = None):
        self.env_path = env_path or (ROOT / ".env")
        self.api_key = api_key or self._resolve_api_key()

    def _resolve_api_key(self) -> str | None:
        if self.env_path.exists():
            vals = dotenv_values(self.env_path)
            if "INCEPTION_LABS_API_KEY" in vals:
                return vals["INCEPTION_LABS_API_KEY"]
            if "MERCURY_2_API_KEY" in vals:
                return vals["MERCURY_2_API_KEY"]
        return os.environ.get("INCEPTION_LABS_API_KEY") or os.environ.get("MERCURY_2_API_KEY")

    def completion(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.2,
    ) -> InceptionResponse:
        if not self.api_key:
            return InceptionResponse(
                content="",
                model="mercury-2",
                tokens_used=0,
                success=False,
                status_code=401,
            )

        url = f"{INCEPTION_BASE_URL}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": "mercury-2",
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        try:
            r = requests.post(url, headers=headers, json=payload, timeout=15.0)
            if r.status_code == 200:
                data = r.json()
                content = data["choices"][0]["message"]["content"]
                tokens = data.get("usage", {}).get("total_tokens", 0)
                return InceptionResponse(
                    content=content,
                    model="mercury-2",
                    tokens_used=tokens,
                    success=True,
                    status_code=200,
                )
            else:
                return InceptionResponse(
                    content="",
                    model="mercury-2",
                    tokens_used=0,
                    success=False,
                    status_code=r.status_code,
                )
        except Exception as e:
            logger.warning("Inception Labs API request error: %s", e)
            return InceptionResponse(
                content="",
                model="mercury-2",
                tokens_used=0,
                success=False,
                status_code=500,
            )
