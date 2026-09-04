"""Stdlib SuperMemory HTTP client. Optional; never required for local RAG."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Callable
from urllib.parse import urlparse

from src.rag.supermemory.contract import (
    API_BASE,
    API_KEY_ENV,
    DEFAULT_CONTAINER_TAG,
    DEFAULT_INGEST_TASK_TYPE,
    DEFAULT_SEARCH_MODE,
    DOCUMENT_GET_PATH,
    DOCUMENTS_PATH,
    PROFILE_PATH,
    SEARCH_PATH,
    redact_secret,
    validate_auth_headers,
    validate_container_tag,
    validate_v3_document_body,
    validate_v4_search_body,
)

Transport = Callable[[str, str, dict[str, str], bytes | None], tuple[int, dict[str, str], str]]


class SuperMemoryError(RuntimeError):
    """Provider or contract failure. Does not disable local RAG."""


def load_api_key(environ: dict[str, str] | None = None) -> str | None:
    """Read SUPERMEMORY_API_KEY from env. Never print the value."""
    env = environ if environ is not None else os.environ
    raw = env.get(API_KEY_ENV, "").strip()
    return raw or None


def build_auth_headers(api_key: str) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    errors = validate_auth_headers(headers)
    if errors:
        raise SuperMemoryError("; ".join(errors))
    return headers


def build_search_body(
    query: str,
    *,
    container_tag: str = DEFAULT_CONTAINER_TAG,
    search_mode: str = DEFAULT_SEARCH_MODE,
    limit: int = 8,
    include_related: bool = False,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "q": query,
        "containerTag": container_tag,
        "searchMode": search_mode,
        "limit": int(limit),
    }
    if include_related:
        body["include"] = {"relatedMemories": True}
    errors = validate_v4_search_body(body)
    if errors:
        raise SuperMemoryError("; ".join(errors))
    return body


def build_document_body(
    content: str,
    *,
    container_tag: str = DEFAULT_CONTAINER_TAG,
    custom_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    task_type: str = DEFAULT_INGEST_TASK_TYPE,
    dreaming: str = "dynamic",
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "content": content,
        "containerTag": container_tag,
        "taskType": task_type,
        "dreaming": dreaming,
    }
    if custom_id:
        body["customId"] = custom_id
    if metadata:
        body["metadata"] = metadata
    errors = validate_v3_document_body(body)
    if errors:
        raise SuperMemoryError("; ".join(errors))
    return body


def _assert_http_url(url: str) -> None:
    scheme = urlparse(url).scheme.lower()
    if scheme not in {"https", "http"}:
        raise SuperMemoryError(f"refusing non-http SuperMemory URL scheme {scheme!r}")


def _stdlib_transport(
    method: str, url: str, headers: dict[str, str], body: bytes | None
) -> tuple[int, dict[str, str], str]:
    _assert_http_url(url)
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:  # nosec B310
            payload = response.read().decode("utf-8")
            return int(response.status), dict(response.headers.items()), payload
    except urllib.error.HTTPError as exc:
        payload = exc.read().decode("utf-8", errors="replace")
        return int(exc.code), dict(exc.headers.items()), payload


class SuperMemoryClient:
    """Lazy HTTP wrapper. Missing key degrades; it does not crash callers."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str = API_BASE,
        transport: Transport | None = None,
        container_tag: str = DEFAULT_CONTAINER_TAG,
    ) -> None:
        tag_errors = validate_container_tag(container_tag)
        if tag_errors:
            raise SuperMemoryError("; ".join(tag_errors))
        self.api_key = api_key if api_key is not None else load_api_key()
        self.base_url = base_url.rstrip("/")
        self.transport = transport or _stdlib_transport
        self.container_tag = container_tag

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def status(self) -> dict[str, Any]:
        return {
            "configured": self.configured,
            "api_key": redact_secret(self.api_key),
            "base_url": self.base_url,
            "container_tag": self.container_tag,
            "documents_path": DOCUMENTS_PATH,
            "search_path": SEARCH_PATH,
            "profile_path": PROFILE_PATH,
            "auth": "Bearer",
            "edge_truth": "local_ledgers",
        }

    def _call(self, method: str, path: str, body: dict[str, Any] | None) -> dict[str, Any]:
        if not self.api_key:
            raise SuperMemoryError(f"{API_KEY_ENV} is not set")
        headers = build_auth_headers(self.api_key)
        payload = json.dumps(body).encode("utf-8") if body is not None else None
        url = f"{self.base_url}{path}"
        status, _headers, text = self.transport(method, url, headers, payload)
        try:
            parsed: Any = json.loads(text) if text else {}
        except json.JSONDecodeError as exc:
            raise SuperMemoryError(f"non-JSON SuperMemory response ({status})") from exc
        if status >= 400:
            detail = parsed.get("error") if isinstance(parsed, dict) else text[:200]
            raise SuperMemoryError(f"SuperMemory HTTP {status}: {detail}")
        if not isinstance(parsed, dict):
            raise SuperMemoryError("SuperMemory JSON must be an object")
        return parsed

    def add_document(self, body: dict[str, Any]) -> dict[str, Any]:
        errors = validate_v3_document_body(body)
        if errors:
            raise SuperMemoryError("; ".join(errors))
        return self._call("POST", DOCUMENTS_PATH, body)

    def search(self, body: dict[str, Any]) -> dict[str, Any]:
        errors = validate_v4_search_body(body)
        if errors:
            raise SuperMemoryError("; ".join(errors))
        return self._call("POST", SEARCH_PATH, body)

    def profile(self, container_tag: str | None = None) -> dict[str, Any]:
        tag = container_tag or self.container_tag
        errors = validate_container_tag(tag)
        if errors:
            raise SuperMemoryError("; ".join(errors))
        return self._call("POST", PROFILE_PATH, {"containerTag": tag})

    def get_document(self, doc_id: str) -> dict[str, Any]:
        path = DOCUMENT_GET_PATH.format(id=doc_id)
        return self._call("GET", path, None)
