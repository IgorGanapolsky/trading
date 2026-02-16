from __future__ import annotations

import re

MAX_LINKEDIN_CHARS = 2800
DEFAULT_HASHTAGS = ("#AIEngineering", "#AIDiscovery", "#TradingSystems", "#BuildInPublic")

_CODE_BLOCK_RE = re.compile(r"```.*?```", re.DOTALL)
_INLINE_CODE_RE = re.compile(r"`([^`]+)`")
_MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]+\)")
_HEADING_RE = re.compile(r"^#{1,6}\s+", re.MULTILINE)
_MULTISPACE_RE = re.compile(r"\s+")
_NUMERIC_SIGNAL_RE = re.compile(
    r"(\$[\d,.]+|\b\d+(?:\.\d+)?%\b|\b\d+(?:\.\d+)?x\b|\b\d+(?:,\d{3})+\b)", re.IGNORECASE
)


def _clean_markdown(text: str) -> str:
    cleaned = _CODE_BLOCK_RE.sub(" ", text or "")
    cleaned = _INLINE_CODE_RE.sub(r"\1", cleaned)
    cleaned = _MARKDOWN_LINK_RE.sub(r"\1", cleaned)
    cleaned = _HEADING_RE.sub("", cleaned)
    cleaned = cleaned.replace("*", " ").replace("_", " ")
    cleaned = _MULTISPACE_RE.sub(" ", cleaned).strip()
    return cleaned


def _split_sentences(text: str) -> list[str]:
    cleaned = _clean_markdown(text)
    if not cleaned:
        return []
    parts = re.split(r"(?<=[.!?])\s+", cleaned)
    return [part.strip() for part in parts if part.strip()]


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    clipped = text[: limit + 1]
    clipped = clipped.rsplit(" ", 1)[0].rstrip(" ,;:-")
    if not clipped:
        clipped = text[:limit].rstrip(" ,;:-")
    return f"{clipped}..."


def _first_sentence(text: str, fallback: str) -> str:
    sentences = _split_sentences(text)
    if sentences:
        return sentences[0]
    return fallback.strip()


def _find_method_sentence(text: str, fallback: str) -> str:
    for sentence in _split_sentences(text):
        lower = sentence.lower()
        if any(token in lower for token in ("we ", "using ", "via ", "through ", "built ")):
            return sentence
    return fallback


def _find_result_sentence(text: str, fallback: str) -> str:
    for sentence in _split_sentences(text):
        if _NUMERIC_SIGNAL_RE.search(sentence):
            return sentence
    return fallback


def _build_hashtags(tags: list[str] | None = None) -> str:
    normalized: list[str] = []
    for tag in tags or []:
        cleaned = re.sub(r"[^a-zA-Z0-9]+", "", str(tag or ""))
        if not cleaned:
            continue
        hashtag = f"#{cleaned[:24]}"
        if hashtag.lower() not in {t.lower() for t in normalized}:
            normalized.append(hashtag)
        if len(normalized) >= 4:
            break

    if not normalized:
        normalized = list(DEFAULT_HASHTAGS)

    return " ".join(normalized[:4])


def build_answer_first_linkedin_post(
    *,
    title: str,
    body_markdown: str,
    canonical_url: str,
    tags: list[str] | None = None,
    question_cluster: str | None = None,
    result_summary: str | None = None,
    max_chars: int = MAX_LINKEDIN_CHARS,
) -> str:
    """
    Build a deterministic, answer-first LinkedIn post.

    Format:
    - First two lines provide direct answer + outcome.
    - Then Problem / Method / Result / Evidence sections for AI snippet extraction.
    - Canonical URL is always included.
    """
    clean_body = _clean_markdown(body_markdown)
    direct_answer = _truncate(
        _first_sentence(clean_body, fallback=title),
        220,
    )
    problem = _truncate(
        _first_sentence(clean_body, fallback=f"{title} addresses a real-world implementation gap."),
        260,
    )
    method = _truncate(
        _find_method_sentence(
            clean_body,
            fallback="We implemented an automated pipeline with enforced quality checks and canonical linking.",
        ),
        280,
    )
    result = _truncate(
        (result_summary or "").strip()
        or _find_result_sentence(
            clean_body,
            fallback="Improved discoverability by standardizing answer-first structure and metadata signals.",
        ),
        260,
    )
    hashtags = _build_hashtags(tags)

    lines: list[str] = [
        title.strip(),
        f"Direct answer: {direct_answer}",
        "",
        f"Problem: {problem}",
        f"Method: {method}",
        f"Result: {result}",
    ]
    if question_cluster:
        lines.append(f"Question cluster: {_truncate(question_cluster.strip(), 180)}")
    lines.extend(
        [
            f"Evidence: {canonical_url.strip()}",
            "",
            hashtags,
        ]
    )
    post = "\n".join(line for line in lines if line is not None).strip()
    if len(post) <= max_chars:
        return post

    # Shrink method/result first, preserving structure and canonical link.
    method = _truncate(method, 180)
    result = _truncate(result, 180)
    compact_lines = [
        title.strip(),
        f"Direct answer: {direct_answer}",
        "",
        f"Problem: {problem}",
        f"Method: {method}",
        f"Result: {result}",
    ]
    if question_cluster:
        compact_lines.append(f"Question cluster: {_truncate(question_cluster.strip(), 120)}")
    compact_lines.extend([f"Evidence: {canonical_url.strip()}", "", hashtags])
    compact_post = "\n".join(compact_lines).strip()
    return compact_post[:max_chars].rstrip()
