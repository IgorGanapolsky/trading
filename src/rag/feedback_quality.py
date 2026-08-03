"""Trading-native feedback quality gate for lesson promotion.

capture 👎 → normalize → quality-gate → (only then) store into FTS5/markdown.
Does not depend on ThumbGate.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Optional

GENERIC_NEGATIVE = re.compile(
    r"^(thumbs?\s*down|👎|bad|wrong|failed|broken|fix this)$",
    re.IGNORECASE,
)
GENERIC_POSITIVE = re.compile(
    r"^(thumbs?\s*up|👍|good|lgtm|perfect|approved|nice work|good job)$",
    re.IGNORECASE,
)
LOW_SPEC = re.compile(
    r"^(be better|do better|try harder|fix it|fix this|improve|be careful|"
    r"don'?t do that|never again|make it work|handle it)$",
    re.IGNORECASE,
)
SIGNAL_DOWN = re.compile(
    r"^(?:👎|thumbs?\s*down)\b|thumbs?\s*down|👎",
    re.IGNORECASE,
)
SIGNAL_UP = re.compile(
    r"^(?:👍|thumbs?\s*up)\b|thumbs?\s*up|👍",
    re.IGNORECASE,
)


def normalize_text(value: str, *, limit: int = 4000) -> str:
    compact = re.sub(r"\s+", " ", (value or "")).strip()
    return compact[:limit]


def normalize_signal(signal: str) -> str:
    s = normalize_text(signal).lower()
    if s in {"down", "negative", "thumbs down", "thumbs_down", "bad"}:
        return "negative"
    if s in {"up", "positive", "thumbs up", "thumbs_up", "good"}:
        return "positive"
    if SIGNAL_DOWN.search(s):
        return "negative"
    if SIGNAL_UP.search(s):
        return "positive"
    return "negative" if "down" in s or "fail" in s else "positive"


def detect_feedback_signal(message: str) -> Optional[str]:
    text = normalize_text(message)
    if not text:
        return None
    if SIGNAL_DOWN.search(text) or GENERIC_NEGATIVE.match(text):
        return "negative"
    if SIGNAL_UP.search(text) or GENERIC_POSITIVE.match(text):
        return "positive"
    lowered = text.lower()
    if any(k in lowered for k in ("that's wrong", "that failed", "broken", "undo", "revert")):
        return "negative"
    if any(k in lowered for k in ("ship it", "lgtm", "that works", "merge it")):
        return "positive"
    return None


def is_generic(text: str, signal: str) -> bool:
    n = normalize_text(text)
    if not n:
        return True
    if signal == "negative":
        return bool(GENERIC_NEGATIVE.match(n))
    return bool(GENERIC_POSITIVE.match(n))


def is_low_specificity(text: str) -> bool:
    n = normalize_text(text)
    if not n:
        return True
    if LOW_SPEC.match(n):
        return True
    words = n.split()
    if len(n) < 18 or len(words) < 4:
        return True
    return False


@dataclass(frozen=True)
class PromotionDecision:
    promotable: bool
    signal: str
    quality_gate: str
    reason: str
    source_field: str | None = None


def assess_promotion_quality(
    *,
    signal: str,
    context: str = "",
    what_went_wrong: str = "",
    what_to_change: str = "",
    what_worked: str = "",
) -> PromotionDecision:
    sig = normalize_signal(signal)
    if sig == "positive":
        candidates = [
            ("what_worked", what_worked),
            ("context", context),
        ]
    else:
        candidates = [
            ("what_to_change", what_to_change),
            ("what_went_wrong", what_went_wrong),
            ("context", context),
        ]

    usable = [
        (name, val)
        for name, val in candidates
        if normalize_text(val) and not is_generic(val, sig) and not is_low_specificity(val)
    ]
    if not usable:
        # Bare thumbs or all low-spec
        if not any(normalize_text(v) for _, v in candidates):
            return PromotionDecision(
                False,
                sig,
                "actionability",
                "Feedback lacks specific context and cannot be promoted",
            )
        return PromotionDecision(
            False,
            sig,
            "specificity",
            "Feedback is not specific enough — name the concrete failure and change",
        )

    name, _ = usable[0]
    return PromotionDecision(True, sig, "passed", "ok", source_field=name)


def build_lesson_payload(
    *,
    signal: str,
    context: str = "",
    what_went_wrong: str = "",
    what_to_change: str = "",
    what_worked: str = "",
    tags: Optional[list[str]] = None,
) -> dict[str, Any] | None:
    decision = assess_promotion_quality(
        signal=signal,
        context=context,
        what_went_wrong=what_went_wrong,
        what_to_change=what_to_change,
        what_worked=what_worked,
    )
    if not decision.promotable:
        return None

    if decision.signal == "negative":
        title = f"MISTAKE: {normalize_text(what_went_wrong or context)[:120]}"
        body_parts = [
            f"Context: {normalize_text(context)}" if context else "",
            f"What went wrong: {normalize_text(what_went_wrong)}" if what_went_wrong else "",
            f"How to avoid: {normalize_text(what_to_change)}" if what_to_change else "",
        ]
        content = "\n".join(p for p in body_parts if p)
        prevention = normalize_text(what_to_change) or "Investigate and prevent recurrence"
        severity = "HIGH"
        tag_list = list(tags or []) + ["feedback", "negative"]
    else:
        title = f"SUCCESS: {normalize_text(what_worked or context)[:120]}"
        body_parts = [
            f"Context: {normalize_text(context)}" if context else "",
            f"What worked: {normalize_text(what_worked)}" if what_worked else "",
        ]
        content = "\n".join(p for p in body_parts if p)
        prevention = normalize_text(what_worked)
        severity = "MEDIUM"
        tag_list = list(tags or []) + ["feedback", "positive"]

    return {
        "title": title,
        "content": content,
        "severity": severity,
        "prevention": prevention,
        "tags": sorted(set(tag_list)),
        "signal": decision.signal,
        "quality_gate": decision.quality_gate,
    }
