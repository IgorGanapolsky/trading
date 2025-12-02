from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

try:
    from langsmith import Client
except ImportError:  # pragma: no cover - langsmith is optional for open-source forks
    Client = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


@dataclass
class _DatasetHandle:
    id: str
    name: str


class LangSmithAgentBridge:
    """
    Small helper that mirrors LangSmith Agent Builder concepts.

    * `record_version` writes the current agent specification into a LangSmith
      dataset so we have a version history for prompts/tools.
    * `record_run` streams ad-hoc agent executions into LangSmith if requested.
    * `run_dataset_evaluation` exposes the CI-style dataset regression harness
      mentioned in the LangSmith agent-builder launch blog.
    """

    def __init__(self, agent_name: str) -> None:
        self.agent_name = agent_name
        self.registry_dataset_name = os.getenv(
            "LANGSMITH_AGENT_REGISTRY_DATASET", f"{agent_name}-versions"
        )
        self.run_dataset_name = os.getenv("LANGSMITH_AGENT_RUN_DATASET")
        self.eval_dataset_name = os.getenv("LANGSMITH_AGENT_EVAL_DATASET")
        self.eval_project_name = os.getenv(
            "LANGSMITH_AGENT_EVAL_PROJECT", f"{agent_name}-regression"
        )
        self.eval_concurrency = int(os.getenv("LANGSMITH_AGENT_EVAL_CONCURRENCY", "5"))
        self._client = self._maybe_build_client()
        self._dataset_cache: dict[str, _DatasetHandle] = {}

    def _maybe_build_client(self):
        should_init = os.getenv("LANGCHAIN_API_KEY") and (
            self.registry_dataset_name or self.run_dataset_name or self.eval_dataset_name
        )
        if not should_init or Client is None:
            return None
        try:
            return Client()
        except Exception as exc:  # pragma: no cover - network/env issues
            logger.warning("LangSmith client unavailable: %s", exc)
            return None

    def _get_or_create_dataset(self, name: str, description: str) -> _DatasetHandle:
        if name in self._dataset_cache:
            return self._dataset_cache[name]
        if not self._client:
            raise RuntimeError("LangSmith client not initialised.")
        try:
            dataset = self._client.read_dataset(dataset_name=name)
        except Exception:
            dataset = self._client.create_dataset(name=name, description=description)
        handle = _DatasetHandle(id=str(dataset.id), name=dataset.name)
        self._dataset_cache[name] = handle
        return handle

    @staticmethod
    @lru_cache(maxsize=64)
    def _hash_spec(spec: dict[str, Any]) -> str:
        payload = json.dumps(spec, sort_keys=True).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def record_version(self, spec: dict[str, Any]) -> None:
        if not self._client or not self.registry_dataset_name:
            return
        dataset = self._get_or_create_dataset(
            self.registry_dataset_name,
            description="Versioned LangChain agent specifications synced from code.",
        )
        version_hash = self._hash_spec(spec)
        existing = list(
            self._client.list_examples(
                dataset_id=dataset.id,
                metadata={"version_hash": version_hash},
                limit=1,
            )
        )
        if existing:
            return
        logger.info(
            "Recording new LangSmith agent spec version (%s) -> %s",
            dataset.name,
            version_hash[:8],
        )
        self._client.create_example(
            dataset_id=dataset.id,
            inputs={"spec": spec},
            outputs={"version_hash": version_hash},
            metadata={"version_hash": version_hash},
        )

    def record_run(
        self,
        *,
        prompt: str,
        response: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if not self._client or not self.run_dataset_name:
            return
        dataset = self._get_or_create_dataset(
            self.run_dataset_name,
            description="Ad-hoc LangChain agent transcripts synced from production runs.",
        )
        self._client.create_example(
            dataset_id=dataset.id,
            inputs={"prompt": prompt},
            outputs={"response": response, "metadata": metadata or {}},
            metadata={"source": "runtime"},
        )

    def run_dataset_evaluation(self, agent_factory):
        """
        Kick off a LangSmith dataset evaluation for CI/regression testing.
        """
        if not self._client or not self.eval_dataset_name:
            raise RuntimeError(
                "LangSmith evaluation dataset is not configured via "
                "`LANGSMITH_AGENT_EVAL_DATASET`."
            )

        logger.info(
            "Running LangSmith dataset regression: dataset=%s project=%s",
            self.eval_dataset_name,
            self.eval_project_name,
        )

        return self._client.run_on_dataset(
            dataset_name=self.eval_dataset_name,
            llm_or_chain_factory=lambda: agent_factory,
            concurrency_level=self.eval_concurrency,
            project_name=self.eval_project_name,
            verbose=True,
        )
