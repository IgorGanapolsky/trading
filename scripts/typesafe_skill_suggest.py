#!/usr/bin/env python3
"""TypeSafe skill-suggestion FORMAT (not a TypeSafe product clone).

Two-pass progressive disclosure for large skill rosters:
  1) Cheap shortlist (token overlap / optional TypeSafe Choice over a capped set)
  2) Rerank top-K with fuller SKILL.md excerpts + per-candidate Noul fits

Offline mode works without TYPESAFE_API_KEY (CI / fail-closed).
Online mode uses System One when a key is available.

Stolen from: docs.typesafe.ai/cookbooks/skill_suggestion
Playground evidence: console.typesafe.ai/playground helpdesk triage Choice@200 opts.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.adapters.typesafe_client import load_api_key, system_one  # noqa: E402

TOKEN_RE = re.compile(r"[a-z0-9]{2,}")
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.S)
YAML_DESC_RE = re.compile(r"^description:\s*[>|]?\s*(.*?)(?=\n[a-zA-Z_]+:|\Z)", re.S | re.M)

SHORTLIST = 3
PREFILTER = 40
GATE_THRESHOLD = 0.30
FITS_THRESHOLD = 0.30
EXCERPT_CHARS = 700
DESC_INDEX_CHARS = 60

GATE_QUESTIONS = {
    "acts_on_user_system": (
        "Is the assistant being asked to act on the user's files, accounts, devices, "
        "or online services, rather than only to explain or advise?"
    ),
    "would_follow_documented_procedure": (
        "Would a careful expert answering this consult a specific documented procedure "
        "or set of commands, rather than answering from general understanding?"
    ),
    "prose_suffices": (
        "Could a knowledgeable generalist fully satisfy this request in prose, with "
        "no tools, no documentation, and no access to the user's files or accounts?"
    ),
}
INVERTED = {"prose_suffices"}


@dataclass(frozen=True)
class SkillCard:
    name: str
    path: str
    description: str
    description_full: str
    body: str
    category: str


def _tokens(text: str) -> set[str]:
    return set(TOKEN_RE.findall(text.lower()))


def _parse_skill_md(path: Path) -> SkillCard | None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    name = path.parent.name
    body = text
    description_full = ""
    m = FRONTMATTER_RE.match(text)
    if m:
        fm, body = m.group(1), m.group(2)
        dm = YAML_DESC_RE.search(fm)
        if dm:
            description_full = " ".join(dm.group(1).split())
    if not description_full:
        # first non-empty non-heading line
        for line in body.splitlines():
            line = line.strip()
            if line and not line.startswith("#") and not line.startswith("```"):
                description_full = line
                break
    description = (description_full or name)[:DESC_INDEX_CHARS]
    category = path.parent.parent.name if path.parent.parent else "skills"
    return SkillCard(
        name=name,
        path=str(path),
        description=description,
        description_full=description_full or name,
        body=body[:1600],
        category=category,
    )


def default_skill_roots() -> list[Path]:
    return [
        Path.home() / ".grok" / "skills",
        Path.home() / ".agents" / "skills",
        ROOT / "skills",
    ]


def load_roster(roots: Iterable[Path] | None = None) -> list[SkillCard]:
    seen: set[str] = set()
    out: list[SkillCard] = []
    for root in roots or default_skill_roots():
        if not root.exists():
            continue
        for skill_md in sorted(root.glob("*/SKILL.md")):
            card = _parse_skill_md(skill_md)
            if card is None or card.name in seen:
                continue
            # skip upstream typesafe API skill from suggestion noise for trading turns
            seen.add(card.name)
            out.append(card)
    return out


def offline_gate(request: str) -> float:
    """Cheap 0..1 stand-in for the three cookbook gate nouls."""
    toks = _tokens(request)
    act = bool(
        toks
        & {
            "run",
            "fix",
            "install",
            "send",
            "deploy",
            "merge",
            "commit",
            "trade",
            "dial",
            "call",
            "write",
            "edit",
            "open",
            "close",
            "sync",
            "push",
            "pr",
            "test",
            "heal",
            "login",
            "wire",
        }
    )
    procedure = bool(
        toks
        & {
            "skill",
            "playbook",
            "runbook",
            "workflow",
            "gate",
            "checklist",
            "protocol",
            "script",
            "cli",
            "make",
        }
    )
    prose = bool(toks & {"explain", "what", "why", "define", "meaning", "theory"}) and not act
    oriented = [
        1.0 if act else 0.2,
        1.0 if procedure else 0.25,
        0.2 if prose else 0.8,  # inverted prose_suffices
    ]
    return sum(oriented) / len(oriented)


def offline_rank(
    request: str, roster: list[SkillCard], limit: int = PREFILTER
) -> list[tuple[str, float]]:
    q = _tokens(request)
    scored: list[tuple[str, float]] = []
    for card in roster:
        hay = _tokens(
            card.name.replace("-", " ") + " " + card.description_full + " " + card.body[:400]
        )
        if not hay:
            continue
        inter = len(q & hay)
        if inter == 0:
            continue
        score = inter / math.sqrt(len(hay))
        # slight boost for exact name token hits
        name_toks = _tokens(card.name.replace("-", " "))
        score += 0.5 * len(q & name_toks)
        scored.append((card.name, score))
    scored.sort(key=lambda kv: -kv[1])
    if not scored:
        return []
    top = scored[0][1] or 1.0
    return [(n, s / top) for n, s in scored[:limit]]


def suggestion_block(names: tuple[str, ...]) -> str:
    body = (
        f"Relevant to the current request: {', '.join(names)}. Ignore this if it does not "
        "fit what the user actually asked for."
        if names
        else "No skill in the roster appears relevant to this request."
    )
    return f"\n\n<skill_relevance>\n{body}\n</skill_relevance>"


def offline_suggest(request: str, roster: list[SkillCard]) -> dict[str, Any]:
    gate = offline_gate(request)
    ranked = offline_rank(request, roster, limit=max(PREFILTER, SHORTLIST))
    if gate < GATE_THRESHOLD or not ranked:
        names: tuple[str, ...] = ()
        reason = "gate_below_threshold" if gate < GATE_THRESHOLD else "no_token_overlap"
    else:
        names = tuple(n for n, _ in ranked[:SHORTLIST][:1])  # at most one, cookbook style
        # require the top score not tiny
        if ranked[0][1] < 0.15:
            names = ()
            reason = "top_score_too_low"
        else:
            reason = "offline_token_rank"
    return {
        "ok": True,
        "mode": "offline",
        "stolen_format": "typesafe skill_suggestion progressive disclosure (not a clone)",
        "request": request,
        "gate": gate,
        "gate_threshold": GATE_THRESHOLD,
        "suggested": list(names),
        "ranked_preview": ranked[:8],
        "roster_size": len(roster),
        "suggestion_block": suggestion_block(names),
        "reason": reason,
        "evaluated_at": datetime.now(UTC).isoformat(),
    }


def _by_name(roster: list[SkillCard]) -> dict[str, SkillCard]:
    return {c.name: c for c in roster}


def online_suggest(
    request: str,
    roster: list[SkillCard],
    *,
    api_key: str,
    model: str = "jev-latest",
) -> dict[str, Any]:
    """Shortlist offline, then TypeSafe Choice+Noul over the shortlist, then fits Nouls."""
    pre = offline_rank(request, roster, limit=PREFILTER)
    if not pre:
        out = offline_suggest(request, roster)
        out["mode"] = "online_empty_prefilter"
        return out

    short_names = [n for n, _ in pre[: min(PREFILTER, 40)]]
    by = _by_name(roster)
    criteria = {n: by[n].description for n in short_names if n in by}
    questions: dict[str, Any] = {
        "which": {
            "type": "choice",
            "instructions": (
                "Which of these skills, if any, is the right one to load to help with the "
                "user's latest request?"
            ),
            "criteria": criteria,
        }
    }
    for key, text in GATE_QUESTIONS.items():
        questions[f"gate::{key}"] = {"type": "noul", "instructions": text}

    wide = system_one(
        state={"request": request, "recent_context": ""},
        questions=questions,
        api_key=api_key,
        model=model,
        timeout=120.0,
    )
    answers = wide.get("answers") or {}
    which = answers.get("which") or {}
    probs = which.get("probabilities") or {}
    ranked = sorted(probs.items(), key=lambda kv: -float(kv[1]))
    gate_vals = {
        k.removeprefix("gate::"): float((answers.get(k) or {}).get("noul") or 0.0)
        for k in answers
        if k.startswith("gate::")
    }
    oriented = [(1.0 - v) if k in INVERTED else v for k, v in gate_vals.items()] or [0.0]
    gate = sum(oriented) / len(oriented)
    if gate < GATE_THRESHOLD or not ranked:
        names: tuple[str, ...] = ()
        fits: dict[str, float] = {}
        winner = None
    else:
        top3 = tuple(n for n, _ in ranked[:SHORTLIST] if n in by)
        # second pass fits
        fit_q: dict[str, Any] = {
            "which": {
                "type": "choice",
                "instructions": (
                    "Exactly one of these skills is the right one to load for the user's "
                    "latest request. Which one? Read what each actually does, not just its name."
                ),
                "criteria": {
                    n: f"{by[n].description_full} — {by[n].body[:EXCERPT_CHARS]}" for n in top3
                },
            }
        }
        for n in top3:
            fit_q[f"fits::{n}"] = {
                "type": "noul",
                "instructions": (
                    f"Does the skill '{n}' do the specific thing the user's request asks for? "
                    f"It is described as: {by[n].description_full}"
                ),
            }
        rerank = system_one(
            state={"request": request, "recent_context": ""},
            questions=fit_q,
            api_key=api_key,
            model=model,
            timeout=120.0,
        )
        r_answers = rerank.get("answers") or {}
        winner = (r_answers.get("which") or {}).get("choice")
        fits = {
            k.removeprefix("fits::"): float((r_answers.get(k) or {}).get("noul") or 0.0)
            for k in r_answers
            if k.startswith("fits::")
        }
        best_fit = max(fits.values()) if fits else 0.0
        if winner and best_fit >= FITS_THRESHOLD and winner in by:
            names = (str(winner),)
        else:
            names = ()
            winner = None

    return {
        "ok": True,
        "mode": "online",
        "stolen_format": "typesafe skill_suggestion progressive disclosure (not a clone)",
        "model": wide.get("model") or model,
        "request": request,
        "gate": gate,
        "gate_values": gate_vals,
        "gate_threshold": GATE_THRESHOLD,
        "fits_threshold": FITS_THRESHOLD,
        "prefilter": pre[:12],
        "wide_ranked": ranked[:12],
        "winner": winner,
        "fits": fits if "fits" in locals() else {},
        "suggested": list(names),
        "roster_size": len(roster),
        "shortlist_size": len(short_names),
        "suggestion_block": suggestion_block(names),
        "usage_wide": wide.get("usage"),
        "evaluated_at": datetime.now(UTC).isoformat(),
    }


def suggest(
    request: str,
    *,
    offline: bool = False,
    roots: list[Path] | None = None,
    api_key: str | None = None,
    model: str = "jev-latest",
) -> dict[str, Any]:
    roster = load_roster(roots)
    key = api_key if api_key is not None else load_api_key()
    if offline or not key:
        result = offline_suggest(request, roster)
        if not key and not offline:
            result["note"] = "TYPESAFE_API_KEY missing; used offline shortlist"
        return result
    try:
        return online_suggest(request, roster, api_key=key, model=model)
    except Exception as exc:  # noqa: BLE001 — fail closed
        result = offline_suggest(request, roster)
        result["mode"] = "online_fallback_offline"
        result["provider_error"] = f"{type(exc).__name__}: {exc}"[:300]
        result["note"] = "TypeSafe provider failure; fail-closed offline shortlist"
        return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", required=True, help="User/agent turn text")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--model", default="jev-latest")
    parser.add_argument(
        "--roots",
        nargs="*",
        default=None,
        help="Skill roots (default: ~/.grok/skills ~/.agents/skills trading/skills)",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    roots = [Path(p) for p in args.roots] if args.roots else None
    result = suggest(args.request, offline=args.offline, roots=roots, model=args.model)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
