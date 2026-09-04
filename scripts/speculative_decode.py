#!/usr/bin/env python3
"""N-gram speculative decode doctor. Always JSON. Never NVIDIA speedup claims."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.llm.speculative.ngram import ngram_draft, tokenize  # noqa: E402
from src.llm.speculative.policy import (  # noqa: E402
    DraftMeasurement,
    choose_D,
    estimated_speedup,
)
from src.llm.speculative.verify import verify_draft  # noqa: E402


class _JsonArgParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:  # type: ignore[override]
        print(
            json.dumps(
                {"ok": False, "status": "UNAVAILABLE", "error": message},
                indent=2,
                sort_keys=True,
            )
        )
        self.exit(2)


def _parser() -> argparse.ArgumentParser:
    parser = _JsonArgParser(description=__doc__)
    parser.add_argument("--prefix", default="")
    parser.add_argument("--corpus", default="")
    parser.add_argument("--corpus-file", type=Path)
    parser.add_argument("--target", default="", help="Ground-truth continuation to verify against")
    parser.add_argument("--D", dest="draft_len", type=int, default=7)
    parser.add_argument("--n", type=int, default=3)
    parser.add_argument("--choose-d", action="store_true")
    parser.add_argument("--max-d", type=int, default=16)
    return parser


def _emit_error(message: str, *, code: int = 2) -> int:
    print(
        json.dumps(
            {"ok": False, "status": "UNAVAILABLE", "error": message},
            indent=2,
            sort_keys=True,
        )
    )
    return code


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
        corpus = args.corpus
        if args.corpus_file:
            try:
                corpus = args.corpus_file.read_text(encoding="utf-8")
            except OSError as exc:
                return _emit_error(f"corpus file unreadable: {exc}")
            except UnicodeDecodeError as exc:
                return _emit_error(f"corpus file not utf-8: {exc}")

        if args.choose_d:
            measurements: list[DraftMeasurement] = []
            target_toks = tokenize(args.target)
            for d in range(0, max(0, args.max_d) + 1):
                proposal = ngram_draft(args.prefix, corpus, D=d, n=args.n)
                verified = verify_draft(proposal.tokens, target_toks, mechanism=proposal.mechanism)
                measurements.append(
                    DraftMeasurement(
                        D=d, AL=float(verified.AL), draft_overhead=proposal.draft_overhead
                    )
                )
            picked = choose_D(measurements, max_D=args.max_d)
            payload = {
                "ok": True,
                "picked_D": picked,
                "measurements": [
                    {
                        "D": row.D,
                        "AL": row.AL,
                        "draft_overhead": row.draft_overhead,
                        "estimated_speedup": estimated_speedup(row.AL, row.D, row.draft_overhead),
                    }
                    for row in measurements
                ],
                "nvidia_speedup_is_not_ours": True,
                "mechanism": "suffix_ngram",
            }
            print(json.dumps(payload, indent=2, sort_keys=True))
            return 0

        proposal = ngram_draft(args.prefix, corpus, D=args.draft_len, n=args.n)
        verified = verify_draft(
            proposal.tokens, tokenize(args.target), mechanism=proposal.mechanism
        )
        speedup = estimated_speedup(float(verified.AL), verified.D, proposal.draft_overhead)
        payload = {
            "ok": True,
            "draft": proposal.tokens,
            "D": proposal.D,
            "n": proposal.n,
            "mechanism": proposal.mechanism,
            "draft_overhead": proposal.draft_overhead,
            "verify": verified.as_dict(),
            "AL": verified.AL,
            "estimated_speedup": speedup,
            "nvidia_speedup_is_not_ours": True,
            "lossless": verified.lossless,
            "paper_only": True,
            "does_not_override_risk_engine": True,
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    except SystemExit as exc:
        # argparse already emitted JSON via _JsonArgParser.error
        code = exc.code
        return int(code) if isinstance(code, int) else 2
    except Exception as exc:  # noqa: BLE001 — CLI must stay JSON
        return _emit_error(f"{type(exc).__name__}: {exc}")


if __name__ == "__main__":
    raise SystemExit(main())
