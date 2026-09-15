#!/usr/bin/env python3
"""Multi-teacher distillation cache (LinkedIn Job Search infra FORMAT).

Sources:
- https://www.infoq.com/news/2026/09/linkedin-ai-multi-teacher/
- https://www.linkedin.com/blog/engineering/infrastructure/the-training-infrastructure-behind-ai-powered-job-search-eight-x-faster-multi-teacher-distillation

Steal (not Ray/FSDP/H200/SGLang):
  - Pluggable specialized teachers (relevance, engagement, embedding-ish signals)
  - Offline cache keyed by teacher_id + teacher_version + data_fingerprint
  - Per-shard (per-example) cache — update data without full re-infer
  - Online vs offline is a *per-teacher* decision in one run
  - Student iterates cheaply from cached soft labels (no teacher GPUs)
  - Measure teacher_calls vs cache_hits → estimated speedup

Lab mapping: teachers are deterministic/local probes (search grades, eval
precision, hydrafusion cost, fanout pressure), not billion-param LLMs.

EXIT 0 always for report. EXIT 2 with --strict if required teachers miss.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
CACHE_ROOT = ROOT / "data" / "runtime" / "teacher_cache"


def data_fingerprint(examples: list[dict]) -> str:
    h = hashlib.sha256()
    for ex in examples:
        h.update(json.dumps(ex, sort_keys=True, separators=(",", ":")).encode())
        h.update(b"\n")
    return h.hexdigest()[:16]


def example_id(ex: dict) -> str:
    if "id" in ex:
        return str(ex["id"])
    return hashlib.sha256(
        json.dumps(ex, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()[:16]


def example_fingerprint(ex: dict) -> str:
    """Per-example cache key — batch edits must not invalidate unrelated shards."""
    return data_fingerprint([ex])


@dataclass
class Teacher:
    teacher_id: str
    version: str
    infer: Callable[[dict], dict]  # -> soft labels / embedding-ish vector

    def cache_dir(self) -> Path:
        return CACHE_ROOT / self.teacher_id / self.version


def _load_shard(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def _save_shard(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True))


def run_teacher(
    teacher: Teacher,
    examples: list[dict],
    *,
    mode: str = "auto",  # auto | online | offline
) -> dict:
    """Infer or load cache. auto = fill missing shards; online = re-infer all."""
    batch_fp = data_fingerprint(examples)
    tdir = teacher.cache_dir()
    teacher_calls = 0
    cache_hits = 0
    outputs: dict[str, dict] = {}
    missing: list[dict] = []

    for ex in examples:
        eid = example_id(ex)
        efp = example_fingerprint(ex)
        shard = tdir / f"{efp}_{eid}.json"
        cached = _load_shard(shard)
        if mode != "online" and cached and cached.get("data_fp") == efp:
            outputs[eid] = cached["soft"]
            cache_hits += 1
        else:
            missing.append(ex)

    if mode == "offline" and missing:
        return {
            "ok": False,
            "teacher_id": teacher.teacher_id,
            "error": "offline_cache_incomplete",
            "missing": len(missing),
            "cache_hits": cache_hits,
            "teacher_calls": 0,
        }

    to_infer = examples if mode == "online" else missing
    if mode == "online":
        outputs = {}
        cache_hits = 0

    for ex in to_infer:
        eid = example_id(ex)
        efp = example_fingerprint(ex)
        soft = teacher.infer(ex)
        teacher_calls += 1
        outputs[eid] = soft
        shard = tdir / f"{efp}_{eid}.json"
        _save_shard(
            shard,
            {
                "teacher_id": teacher.teacher_id,
                "version": teacher.version,
                "data_fp": efp,
                "batch_fp": batch_fp,
                "example_id": eid,
                "soft": soft,
                "ts": datetime.now(UTC).isoformat(),
            },
        )

    return {
        "ok": True,
        "teacher_id": teacher.teacher_id,
        "version": teacher.version,
        "data_fp": batch_fp,
        "mode_used": "online" if teacher_calls else "offline",
        "teacher_calls": teacher_calls,
        "cache_hits": cache_hits,
        "n": len(examples),
        "outputs": outputs,
    }


def collector_merge(
    teacher_softs: dict[str, dict],
    *,
    strategy: str = "average",
    learned_weights: dict[str, float] | None = None,
) -> dict:
    """InfoQ/LinkedIn collector: merge teacher soft labels (average or learned weights)."""
    if not teacher_softs:
        return {"score": 0.0, "p_yes": 0.0, "p_no": 1.0, "strategy": strategy}
    if strategy == "learned" and learned_weights:
        wsum = 0.0
        acc = 0.0
        for tid, soft in teacher_softs.items():
            w = float(learned_weights.get(tid, 1.0))
            s = float(soft.get("score", soft.get("p_yes", 0.0)))
            acc += w * s
            wsum += w
        score = acc / wsum if wsum else 0.0
    else:
        vals = [float(s.get("score", s.get("p_yes", 0.0))) for s in teacher_softs.values()]
        score = sum(vals) / len(vals)
        strategy = "average"
    return {
        "score": round(score, 6),
        "p_yes": round(score, 6),
        "p_no": round(1.0 - score, 6),
        "strategy": strategy,
    }


def learn_weights_from_teachers(
    examples: list[dict],
    teacher_outputs: dict[str, dict[str, dict]],
) -> dict[str, float]:
    """Cheap learned weighting: weight ∝ mean soft-score magnitude (stabilize high-signal teachers)."""
    weights: dict[str, float] = {}
    for tid, outs in teacher_outputs.items():
        scores = [float((outs.get(example_id(ex)) or {}).get("score", 0.0)) for ex in examples]
        weights[tid] = max(0.1, sum(scores) / max(len(scores), 1))
    # normalize
    s = sum(weights.values()) or 1.0
    return {k: round(v / s, 4) for k, v in weights.items()}


def fuse_student(
    examples: list[dict],
    teacher_outputs: dict[str, dict[str, dict]],
    *,
    weights: dict[str, float] | None = None,
) -> list[dict]:
    """Compact student: weighted average of teacher soft scores (no GPU)."""
    weights = weights or {}
    results = []
    for ex in examples:
        eid = example_id(ex)
        softs = {tid: (outs.get(eid) or {}) for tid, outs in teacher_outputs.items()}
        strategy = "learned" if weights else "average"
        merged = collector_merge(softs, strategy=strategy, learned_weights=weights)
        detail = {
            tid: {
                "score": float(s.get("score", s.get("p_yes", 0.0))),
                "weight": float((weights or {}).get(tid, 1.0)),
            }
            for tid, s in softs.items()
        }
        student = float(merged["score"])
        results.append(
            {
                "example_id": eid,
                "student_score": round(student, 6),
                "teachers": detail,
                "example": ex,
            }
        )
    results.sort(key=lambda r: -r["student_score"])
    return results


# --- Built-in lab teachers (pluggable) ---


def relevance_teacher(ex: dict) -> dict:
    """Soft relevance from query/path/snippet overlap (ties to search_stack grades)."""
    q = (ex.get("query") or "").lower()
    blob = f"{ex.get('path', '')} {ex.get('snippet', '')} {ex.get('text', '')}".lower()
    toks = [t for t in q.split() if len(t) >= 3]
    if not toks:
        return {"score": 0.0, "p_yes": 0.0, "p_no": 1.0}
    hit = sum(1 for t in toks if t in blob)
    p = hit / len(toks)
    return {"score": p, "p_yes": p, "p_no": 1.0 - p, "task": "relevance"}


def engagement_teacher(ex: dict) -> dict:
    """Multi-task-ish engagement proxy: ops workflows preferred."""
    path = (ex.get("path") or "").lower()
    title = (ex.get("title") or ex.get("query") or "").lower()
    score = 0.2
    if any(x in path for x in ("scripts/", "docs/", "rag_knowledge/")):
        score += 0.3
    if any(x in title for x in ("kill", "cash", "dial", "ci", "pr")):
        score += 0.3
    if ex.get("severity") in {"critical", "high"}:
        score += 0.2
    score = min(1.0, score)
    return {
        "score": score,
        "p_yes": score,
        "p_no": 1.0 - score,
        "tasks": {"view": score, "apply": score * 0.8},
    }


def embedding_teacher(ex: dict) -> dict:
    """Dense-ish bag fingerprint as fixed vector (no neural net)."""
    text = f"{ex.get('query', '')} {ex.get('path', '')} {ex.get('snippet', '')}".lower()
    dims = 16
    vec = [0.0] * dims
    for i, ch in enumerate(text[:256]):
        vec[i % dims] += (ord(ch) % 31) / 31.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    vec = [round(v / norm, 6) for v in vec]
    # Convert to a score via first component magnitude for fusion
    score = min(1.0, abs(vec[0]))
    return {"score": score, "embedding": vec, "p_yes": score, "p_no": 1.0 - score}


DEFAULT_TEACHERS = {
    "relevance": Teacher("relevance", "v1", relevance_teacher),
    "engagement": Teacher("engagement", "v1", engagement_teacher),
    "embedding": Teacher("embedding", "v1", embedding_teacher),
}


def distill(
    examples: list[dict],
    *,
    teacher_ids: list[str] | None = None,
    mode: str = "auto",
    weights: dict[str, float] | None = None,
) -> dict:
    t0 = time.monotonic()
    ids = teacher_ids or list(DEFAULT_TEACHERS.keys())
    teacher_outputs: dict[str, dict[str, dict]] = {}
    accounting = []
    for tid in ids:
        teacher = DEFAULT_TEACHERS[tid]
        result = run_teacher(teacher, examples, mode=mode)
        accounting.append(
            {
                "teacher_id": tid,
                "mode_used": result.get("mode_used"),
                "teacher_calls": result.get("teacher_calls"),
                "cache_hits": result.get("cache_hits"),
                "ok": result.get("ok"),
            }
        )
        if not result.get("ok"):
            return {
                "ok": False,
                "error": result.get("error"),
                "accounting": accounting,
                "framework": "multi_teacher_distill",
            }
        teacher_outputs[tid] = result["outputs"]

    if weights is None:
        weights = learn_weights_from_teachers(examples, teacher_outputs)
    student = fuse_student(examples, teacher_outputs, weights=weights)
    # InfoQ: online early → offline as teachers stabilize (convergence toward cached)
    modes = [a.get("mode_used") for a in accounting]
    convergence = {
        "all_offline": all(m == "offline" for m in modes),
        "modes": modes,
        "note": "Query online while teachers change; switch to offline cache once stable",
    }
    calls = sum(a.get("teacher_calls") or 0 for a in accounting)
    hits = sum(a.get("cache_hits") or 0 for a in accounting)
    # LinkedIn: avoid re-paying teacher inference when only student changes
    naive_calls = len(ids) * len(examples)  # every teacher every example every run
    speedup = (naive_calls / calls) if calls else float(len(ids) * max(len(examples), 1))
    return {
        "ok": True,
        "framework": "multi_teacher_distill",
        "stolen_format": (
            "LinkedIn multi-teacher distillation infra FORMAT — pluggable teachers, "
            "per-shard offline cache, per-teacher online/offline, student from cache "
            "(not Ray/FSDP/H200 clone); ~8x narrative = eliminate redundant teacher GPU"
        ),
        "source": {
            "infoq": "https://www.infoq.com/news/2026/09/linkedin-ai-multi-teacher/",
            "linkedin_engineering": (
                "https://www.linkedin.com/blog/engineering/infrastructure/"
                "the-training-infrastructure-behind-ai-powered-job-search-"
                "eight-x-faster-multi-teacher-distillation"
            ),
        },
        "n_examples": len(examples),
        "teachers": ids,
        "accounting": accounting,
        "teacher_calls": calls,
        "cache_hits": hits,
        "naive_teacher_calls": naive_calls,
        "estimated_speedup_vs_naive": round(speedup, 3),
        "elapsed_s": round(time.monotonic() - t0, 4),
        "student_ranking": student,
        "collector_weights": weights,
        "convergence": convergence,
        "ts": datetime.now(UTC).isoformat(),
    }


def demo_examples() -> list[dict]:
    return [
        {
            "id": "ex1",
            "query": "put credit kill switch",
            "path": "scripts/spy_put_credit.py",
            "snippet": "kill switch blocks new iron condor",
            "severity": "high",
        },
        {
            "id": "ex2",
            "query": "cash fee yes dial",
            "path": "outreach/DIAL_CARD_NOW.md",
            "snippet": "TOP_5 research packet dials",
            "severity": "critical",
        },
        {
            "id": "ex3",
            "query": "random blog post",
            "path": "wiki/archive/old.md",
            "snippet": "unrelated marketing notes",
            "severity": "info",
        },
    ]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--mode", choices=["auto", "online", "offline"], default="auto")
    p.add_argument("--demo", action="store_true", help="run built-in lab examples")
    p.add_argument("--examples-json", default="", help="path to JSON list of examples")
    p.add_argument("--strict", action="store_true")
    args = p.parse_args(argv)
    if args.examples_json:
        examples = json.loads(Path(args.examples_json).read_text())
    else:
        examples = demo_examples()
    # First pass honors --mode (offline must not fall through to online fill).
    out1 = distill(examples, mode=args.mode)
    if args.mode == "offline" or not out1.get("ok"):
        out = {
            **out1,
            "first_pass_teacher_calls": out1.get("teacher_calls"),
            "cache_amortization": {
                "first_calls": out1.get("teacher_calls"),
                "note": "offline/cold path — no auto refill",
                "status": "skipped_amortization",
            },
        }
        print(json.dumps(out, indent=2, sort_keys=True))
        if args.strict and not out.get("ok"):
            return 2
        return 0
    # Warm-cache amortization pass (auto/online only after a successful first pass)
    out2 = distill(examples, mode="auto")
    out = {
        **out2,
        "first_pass_teacher_calls": out1.get("teacher_calls"),
        "second_pass_teacher_calls": out2.get("teacher_calls"),
        "cache_amortization": {
            "first_calls": out1.get("teacher_calls"),
            "second_calls": out2.get("teacher_calls"),
            "note": "Student iteration after warm cache should approach 0 teacher calls",
        },
    }
    print(json.dumps(out, indent=2, sort_keys=True))
    if args.strict and not out.get("ok"):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
