"""N-gram speculative decode: lossless verify, measured AL, no NVIDIA claims."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.llm.speculative.ngram import ngram_draft, tokenize
from src.llm.speculative.policy import (
    DraftMeasurement,
    choose_D,
    estimated_speedup,
    lookalike_hits,
)
from src.llm.speculative.verify import verify_draft

REPO = Path(__file__).resolve().parents[1]
OPS = REPO / "scripts/speculative_decode.py"
ADAPTER = REPO / "src/llm/speculative"


def test_ngram_drafts_from_repeated_suffix() -> None:
    corpus = "paper spy put credit skip live paper spy put credit skip live"
    proposal = ngram_draft("paper spy put", corpus, D=3, n=3)
    assert proposal.mechanism == "suffix_ngram"
    assert proposal.tokens == ["credit", "skip", "live"]
    # Corpus comparisons must be billed into draft_overhead (not hard-coded 0).
    assert proposal.draft_overhead > 0.0


def test_verify_is_lossless_until_first_mismatch() -> None:
    result = verify_draft(["a", "b", "X"], ["a", "b", "c", "d"])
    assert result.accepted == ["a", "b"]
    assert result.rejected_at == 2
    assert result.bonus == "c"
    assert result.AL == 3  # 2 accepted + 1 target bonus
    assert result.lossless is True
    assert result.D == 3


def test_full_accept_adds_bonus_token() -> None:
    result = verify_draft(["a", "b"], ["a", "b", "c"])
    assert result.accepted == ["a", "b"]
    assert result.rejected_at is None
    assert result.bonus == "c"
    assert result.AL == 3


def test_speedup_is_none_without_al() -> None:
    assert estimated_speedup(AL=0, D=7, draft_overhead=0.0) is None
    score = estimated_speedup(AL=4, D=7, draft_overhead=0.0)
    assert score == 4.0


def test_choose_d_stops_when_al_gain_does_not_pay() -> None:
    rows = [
        DraftMeasurement(D=1, AL=2, draft_overhead=0.0),
        DraftMeasurement(D=3, AL=4, draft_overhead=0.0),
        DraftMeasurement(D=9, AL=4, draft_overhead=0.0),  # plateau
        DraftMeasurement(D=21, AL=4.2, draft_overhead=5.0),  # expensive
    ]
    assert choose_D(rows, max_D=21) == 3


def test_cli_json_and_choose_d() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(OPS),
            "--prefix",
            "paper spy put",
            "--corpus",
            "paper spy put credit skip live paper spy put credit skip live",
            "--target",
            "credit skip live blocked",
            "--D",
            "3",
        ],
        check=False,
        capture_output=True,
        text=True,
        cwd=str(REPO),
    )
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["ok"] is True
    assert payload["nvidia_speedup_is_not_ours"] is True
    assert payload["does_not_override_risk_engine"] is True
    assert payload["draft"] == ["credit", "skip", "live"]
    assert payload["AL"] >= 3
    assert payload["lossless"] is True

    choose = subprocess.run(
        [
            sys.executable,
            str(OPS),
            "--choose-d",
            "--max-d",
            "5",
            "--prefix",
            "paper spy put",
            "--corpus",
            "paper spy put credit skip live paper spy put credit skip live",
            "--target",
            "credit skip live blocked",
        ],
        check=False,
        capture_output=True,
        text=True,
        cwd=str(REPO),
    )
    assert choose.returncode == 0, choose.stderr
    chosen = json.loads(choose.stdout)
    assert chosen["picked_D"] >= 1
    assert chosen["nvidia_speedup_is_not_ours"] is True


def test_cli_invalid_flag_is_json() -> None:
    completed = subprocess.run(
        [sys.executable, str(OPS), "--not-a-flag"],
        check=False,
        capture_output=True,
        text=True,
        cwd=str(REPO),
    )
    assert completed.returncode == 2
    payload = json.loads(completed.stdout)
    assert payload["ok"] is False
    assert payload["status"] == "UNAVAILABLE"
    assert "error" in payload


def test_sources_are_not_tensorrt_or_eagle_training() -> None:
    blobs = [OPS.read_text(encoding="utf-8")]
    for path in ADAPTER.glob("*.py"):
        if path.name == "policy.py":
            continue
        blobs.append(path.read_text(encoding="utf-8"))
    joined = "\n".join(blobs)
    assert lookalike_hits(joined) == []
    assert tokenize("a b") == ["a", "b"]
