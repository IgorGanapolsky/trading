#!/usr/bin/env python3
"""Exact-match LLM *response* cache (TNS FORMAT — not prompt-cache / Redis SaaS).

Source: https://thenewstack.io/llm-response-caching-costs/
Abhilash Rao Mesala — fingerprint inputs; skip the model call when unchanged.

Native provider prompt caching ≠ this. Prompt cache cheapens prefix tokens;
response cache returns a stored answer and skips inference entirely.

Key = SHA-256(normalize(query + context + model + settings + source_version + scope))
TTL by category. Never cache realtime market/personal/creative without override.

EXIT 0 always for report CLIs. EXIT 2 with --strict on invalid ops.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DIR = ROOT / "data" / "runtime" / "llm_response_cache"

# Category → TTL seconds (judgment of acceptable staleness — TNS).
CATEGORY_TTL = {
    "policy": 14 * 24 * 3600,  # HR/policy-like: weeks
    "docs": 7 * 24 * 3600,
    "code_boilerplate": 24 * 3600,
    "rag_stable": 6 * 3600,
    "news": 3600,
    "market": 0,  # do not cache live prices / inventory
    "creative": 0,
    "personal": 0,
    "default": 3600,
}

SKIP_CATEGORIES = frozenset({"market", "creative", "personal"})


def normalize_request(
    query: str,
    *,
    context: str = "",
    model: str = "",
    settings: dict | None = None,
    source_version: str = "",
    scope: str = "default",
) -> str:
    """Canonical string for fingerprinting — order and whitespace stable."""
    settings = settings or {}
    q = re.sub(r"\s+", " ", (query or "").strip().lower())
    ctx = re.sub(r"\s+", " ", (context or "").strip())
    settings_s = json.dumps(settings, sort_keys=True, separators=(",", ":"))
    parts = [
        f"q={q}",
        f"ctx={ctx}",
        f"model={(model or '').strip()}",
        f"settings={settings_s}",
        f"src={(source_version or '').strip()}",
        f"scope={(scope or 'default').strip()}",
    ]
    return "\n".join(parts)


def fingerprint(*args: Any, **kwargs: Any) -> str:
    payload = normalize_request(*args, **kwargs) if args or "query" in kwargs else ""
    if not payload and kwargs:
        payload = normalize_request(
            str(kwargs.get("query", "")), **{k: v for k, v in kwargs.items() if k != "query"}
        )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def categorize(query: str, category: str | None = None) -> str:
    if category:
        return category if category in CATEGORY_TTL else "default"
    q = (query or "").lower()
    if any(w in q for w in ("price", "quote", "spy", "bid", "ask", "equity", "pnl")):
        return "market"
    if any(w in q for w in ("poem", "story", "joke", "brainstorm", "creative")):
        return "creative"
    if any(w in q for w in ("my account", "ssn", "password", "api key", "secret")):
        return "personal"
    if any(w in q for w in ("policy", "handbook", "guideline")):
        return "policy"
    return "default"


@dataclass
class CacheEntry:
    key: str
    response: str
    category: str
    created_at: float
    expires_at: float
    meta: dict

    def fresh(self, now: float | None = None) -> bool:
        now = time.time() if now is None else now
        return self.expires_at > now and bool(self.response)


class ResponseCache:
    """File-backed exact-match response cache (one JSON file per key)."""

    def __init__(self, root: Path | None = None, *, shadow: bool = False):
        self.root = root or DEFAULT_DIR
        self.root.mkdir(parents=True, exist_ok=True)
        self.shadow = shadow
        self.stats_path = self.root / "_stats.json"
        self._stats = self._load_stats()

    def _load_stats(self) -> dict:
        if self.stats_path.exists():
            try:
                return json.loads(self.stats_path.read_text())
            except (OSError, json.JSONDecodeError):
                pass
        return {"hits": 0, "misses": 0, "skips": 0, "writes": 0, "shadow_hits": 0}

    def _save_stats(self) -> None:
        self.stats_path.write_text(json.dumps(self._stats, indent=2, sort_keys=True))

    def _path(self, key: str) -> Path:
        return self.root / f"{key}.json"

    def get(
        self,
        query: str,
        *,
        context: str = "",
        model: str = "",
        settings: dict | None = None,
        source_version: str = "",
        scope: str = "default",
        category: str | None = None,
    ) -> dict | None:
        cat = categorize(query, category)
        if cat in SKIP_CATEGORIES or CATEGORY_TTL.get(cat, 0) == 0:
            self._stats["skips"] += 1
            self._save_stats()
            return {
                "hit": False,
                "skipped": True,
                "category": cat,
                "why": "category not cacheable (realtime/personal/creative)",
            }
        key = fingerprint(
            query,
            context=context,
            model=model,
            settings=settings,
            source_version=source_version,
            scope=scope,
        )
        path = self._path(key)
        if not path.exists():
            self._stats["misses"] += 1
            self._save_stats()
            return {"hit": False, "key": key, "category": cat}
        try:
            raw = json.loads(path.read_text())
            entry = CacheEntry(**raw)
        except (OSError, json.JSONDecodeError, TypeError):
            self._stats["misses"] += 1
            self._save_stats()
            return {"hit": False, "key": key, "category": cat, "corrupt": True}
        if not entry.fresh():
            path.unlink(missing_ok=True)
            self._stats["misses"] += 1
            self._save_stats()
            return {"hit": False, "key": key, "category": cat, "expired": True}
        if self.shadow:
            self._stats["shadow_hits"] += 1
            self._save_stats()
            return {
                "hit": False,
                "shadow_hit": True,
                "key": key,
                "category": cat,
                "would_return": entry.response,
                "why": "shadow mode — log only, still call model",
            }
        self._stats["hits"] += 1
        self._save_stats()
        return {
            "hit": True,
            "key": key,
            "category": cat,
            "response": entry.response,
            "meta": entry.meta,
            "expires_at": entry.expires_at,
        }

    def set(
        self,
        query: str,
        response: str,
        *,
        context: str = "",
        model: str = "",
        settings: dict | None = None,
        source_version: str = "",
        scope: str = "default",
        category: str | None = None,
        meta: dict | None = None,
    ) -> dict:
        cat = categorize(query, category)
        ttl = CATEGORY_TTL.get(cat, CATEGORY_TTL["default"])
        if cat in SKIP_CATEGORIES or ttl <= 0:
            return {"written": False, "skipped": True, "category": cat}
        if not is_valid_response(response):
            return {"written": False, "invalid": True, "why": "refuse to poison cache"}
        key = fingerprint(
            query,
            context=context,
            model=model,
            settings=settings,
            source_version=source_version,
            scope=scope,
        )
        now = time.time()
        entry = CacheEntry(
            key=key,
            response=response,
            category=cat,
            created_at=now,
            expires_at=now + ttl,
            meta=meta or {},
        )
        self._path(key).write_text(json.dumps(asdict(entry), indent=2, sort_keys=True))
        self._stats["writes"] += 1
        self._save_stats()
        return {"written": True, "key": key, "category": cat, "ttl": ttl}

    def stats(self) -> dict:
        s = dict(self._stats)
        total = s["hits"] + s["misses"]
        s["hit_rate"] = round(s["hits"] / total, 4) if total else None
        s["note"] = (
            "Measure hit_rate before projecting savings (TNS). "
            "Response cache ≠ provider prompt cache."
        )
        return s


def is_valid_response(response: str) -> bool:
    if response is None:
        return False
    text = str(response).strip()
    if not text:
        return False
    return text.lower() not in {"error", "null", "{}", "[]"}


def cached_completion(
    query: str,
    call_model,
    *,
    context: str = "",
    model: str = "",
    settings: dict | None = None,
    source_version: str = "",
    scope: str = "default",
    category: str | None = None,
    cache: ResponseCache | None = None,
) -> dict:
    """Tier-1 exact match then call_model on miss (call_model: () -> str)."""
    cache = cache or ResponseCache()
    hit = cache.get(
        query,
        context=context,
        model=model,
        settings=settings,
        source_version=source_version,
        scope=scope,
        category=category,
    )
    if hit and hit.get("hit"):
        return {"from_cache": True, "response": hit["response"], "cache": hit}
    resp = call_model()
    write = cache.set(
        query,
        resp,
        context=context,
        model=model,
        settings=settings,
        source_version=source_version,
        scope=scope,
        category=category,
    )
    return {"from_cache": False, "response": resp, "cache_write": write, "lookup": hit}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("get", help="lookup exact-match cache")
    g.add_argument("--query", required=True)
    g.add_argument("--context", default="")
    g.add_argument("--model", default="")
    g.add_argument("--scope", default="default")
    g.add_argument("--category", default=None)
    g.add_argument("--source-version", default="")
    g.add_argument("--shadow", action="store_true")
    s = sub.add_parser("set", help="store a validated response")
    s.add_argument("--query", required=True)
    s.add_argument("--response", required=True)
    s.add_argument("--context", default="")
    s.add_argument("--model", default="")
    s.add_argument("--scope", default="default")
    s.add_argument("--category", default=None)
    s.add_argument("--source-version", default="")
    st = sub.add_parser("stats", help="hit/miss/skip counters")
    st.add_argument("--shadow", action="store_true")
    demo = sub.add_parser("demo", help="two identical calls; second should hit")
    demo.add_argument(
        "--query",
        default="",
        help="defaults to a unique demo query so prior cache entries cannot poison the proof",
    )
    args = p.parse_args(argv)

    if args.cmd == "stats":
        cache = ResponseCache(shadow=args.shadow)
        print(
            json.dumps(
                {
                    "framework": "llm_response_cache",
                    "stats": cache.stats(),
                    "ts": datetime.now(UTC).isoformat(),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    cache = ResponseCache(shadow=getattr(args, "shadow", False))
    if args.cmd == "get":
        out = cache.get(
            args.query,
            context=args.context,
            model=args.model,
            scope=args.scope,
            category=args.category,
            source_version=args.source_version,
        )
        print(json.dumps(out, indent=2, sort_keys=True))
        return 0
    if args.cmd == "set":
        out = cache.set(
            args.query,
            args.response,
            context=args.context,
            model=args.model,
            scope=args.scope,
            category=args.category,
            source_version=args.source_version,
        )
        print(json.dumps(out, indent=2, sort_keys=True))
        return 0
    if args.cmd == "demo":
        calls = {"n": 0}
        q = args.query or f"demo put-credit rules {datetime.now(UTC).isoformat()}"

        def model():
            calls["n"] += 1
            return "paper-only 1-lot SPY bull put; live blocked until n>=30"

        # Isolated dir so demo never depends on leftover runtime cache
        demo_cache = ResponseCache(root=ROOT / "data" / "runtime" / "llm_response_cache_demo")
        a = cached_completion(q, model, model="demo-model", category="docs", cache=demo_cache)
        b = cached_completion(q, model, model="demo-model", category="docs", cache=demo_cache)
        print(
            json.dumps(
                {
                    "framework": "llm_response_cache",
                    "stolen_format": "TNS LLM response caching — exact-match fingerprint + TTL",
                    "first_from_cache": a["from_cache"],
                    "second_from_cache": b["from_cache"],
                    "model_calls": calls["n"],
                    "stats": demo_cache.stats(),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0 if b["from_cache"] and calls["n"] == 1 else 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
