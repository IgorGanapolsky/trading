"""Official SuperMemory HTTP contract.

Source of truth: https://supermemory.ai/docs (Bearer auth, POST /v3/documents,
POST /v4/search with singular containerTag). Local ledgers remain edge truth.
This is not a clone of the SuperMemory console UI.
"""

from __future__ import annotations

import re

API_BASE = "https://api.supermemory.ai"
DOCUMENTS_PATH = "/v3/documents"
SEARCH_PATH = "/v4/search"
PROFILE_PATH = "/v4/profile"
DOCUMENT_GET_PATH = "/v3/documents/{id}"

DEFAULT_CONTAINER_TAG = "trading-lab"
# Live console (Max Smith KDP LLC, Free) currently also has `secure-yolo`.
# Trading never searches or writes that tenant.
FOREIGN_CONTAINER_TAGS = frozenset({"secure-yolo"})

CONTAINER_TAG_PATTERN = re.compile(r"^[a-zA-Z0-9_:-]{1,100}$")
CUSTOM_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,100}$")

SEARCH_MODES = frozenset({"memories", "documents", "hybrid"})
DEFAULT_SEARCH_MODE = "hybrid"
TASK_TYPES = frozenset({"memory", "superrag"})
DEFAULT_INGEST_TASK_TYPE = "superrag"
DREAMING_MODES = frozenset({"dynamic", "instant"})

API_KEY_ENV = "SUPERMEMORY_API_KEY"
OFFICIAL_SDK_IMPORT = "from supermemory import Supermemory"
OFFICIAL_CONSOLE = "https://console.supermemory.ai"
OFFICIAL_DOCS = "https://supermemory.ai/docs"

WRONG_SDK_IMPORTS = (
    "from supermemory import Client",
    "client.memories.create",
    "client.memories.search",
)
FORBIDDEN_AUTH_HEADERS = (
    "x-supermemory-api-key",
    "x-api-key",
    "x-sm-user-id",
)
FORBIDDEN_PATHS = (
    "/v1/",
    "/v3/memories",
    "/v3/search",
)
LOOKALIKE_SNIPPETS = (
    *WRONG_SDK_IMPORTS,
    *FORBIDDEN_AUTH_HEADERS,
    "datetime.utcnow()",
    "financial_graph.sqlite",
)

_EDGE_RE = re.compile(
    r"expectanc|profit factor|\bp/?l\b|\bpnl\b|win rate|equity|fill|paired trade|"
    r"closed trade|cohort|drawdown",
    re.I,
)
_MEMORY_RE = re.compile(
    r"\bprefer|\bremember\b|last session|operator fact|profile\b",
    re.I,
)


def validate_container_tag(tag: str) -> list[str]:
    """Return errors for a containerTag string."""
    if not isinstance(tag, str) or not tag:
        return ["containerTag must be a non-empty string"]
    errors: list[str] = []
    if not CONTAINER_TAG_PATTERN.fullmatch(tag):
        errors.append("containerTag must match ^[a-zA-Z0-9_:-]{1,100}$ (singular JSON field)")
    if tag in FOREIGN_CONTAINER_TAGS:
        errors.append(
            f"containerTag {tag!r} is a foreign tenant; trading uses {DEFAULT_CONTAINER_TAG!r}"
        )
    return errors


def validate_custom_id(custom_id: str) -> list[str]:
    if not isinstance(custom_id, str) or not CUSTOM_ID_PATTERN.fullmatch(custom_id):
        return ["customId must match ^[a-zA-Z0-9_-]{1,100}$"]
    return []


def validate_search_mode(mode: str) -> list[str]:
    if mode not in SEARCH_MODES:
        return [f"searchMode must be one of {sorted(SEARCH_MODES)}"]
    return []


def slug_custom_id(name: str) -> str:
    """Turn a lesson filename into a SuperMemory customId."""
    stem = name.rsplit("/", 1)[-1]
    if "." in stem:
        stem = stem.rsplit(".", 1)[0]
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "-", stem).strip("-_")
    return cleaned[:100] or "lesson"


def route_query(query: str) -> str:
    """Memory vs RAG routing. Edge numbers never come from SuperMemory."""
    text = query or ""
    if _EDGE_RE.search(text):
        return "local_ledger"
    if _MEMORY_RE.search(text):
        return "memory"
    return "hybrid"


def validate_v4_search_body(body: object) -> list[str]:
    """Official /v4/search body: q + singular containerTag."""
    if not isinstance(body, dict):
        return ["search body must be a JSON object"]
    errors: list[str] = []
    if not str(body.get("q") or "").strip():
        errors.append("q is required")
    if "containerTags" in body:
        errors.append("v4 search uses singular containerTag, not containerTags")
    tag = body.get("containerTag")
    if tag is not None:
        errors.extend(validate_container_tag(str(tag)))
    mode = body.get("searchMode")
    if mode is not None:
        errors.extend(validate_search_mode(str(mode)))
    return errors


def validate_v3_document_body(body: object) -> list[str]:
    if not isinstance(body, dict):
        return ["document body must be a JSON object"]
    errors: list[str] = []
    if not str(body.get("content") or "").strip():
        errors.append("content is required")
    if "containerTags" in body:
        errors.append("new writes use singular containerTag, not containerTags")
    tag = body.get("containerTag")
    if tag is not None:
        errors.extend(validate_container_tag(str(tag)))
    custom_id = body.get("customId")
    if custom_id is not None:
        errors.extend(validate_custom_id(str(custom_id)))
    task_type = body.get("taskType")
    if task_type is not None and task_type not in TASK_TYPES:
        errors.append(f"taskType must be one of {sorted(TASK_TYPES)}")
    return errors


def validate_auth_headers(headers: dict[str, str]) -> list[str]:
    lowered = {str(k).lower(): str(v) for k, v in headers.items()}
    errors: list[str] = []
    auth = lowered.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        errors.append("Authorization must be Bearer SUPERMEMORY_API_KEY")
    for forbidden in FORBIDDEN_AUTH_HEADERS:
        if forbidden in lowered:
            errors.append(f"forbidden auth header {forbidden}")
    return errors


def lookalike_hits(blob: str) -> list[str]:
    """Return forbidden lookalike snippets present in source."""
    lowered = blob
    return [snippet for snippet in LOOKALIKE_SNIPPETS if snippet in lowered]


def redact_secret(value: str | None) -> str:
    if not value:
        return ""
    return f"set:len={len(value)}"
