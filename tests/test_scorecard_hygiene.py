"""Scorecard hygiene gate: token permissions, hashed installs, no Issue spam."""

from __future__ import annotations

from pathlib import Path

from scripts.scorecard_hygiene import scan


REPO = Path(__file__).resolve().parents[1]


def test_live_repo_passes_scorecard_hygiene() -> None:
    payload = scan(REPO)
    assert payload["ok"] is True, payload["findings"]
    assert payload["workflow_count"] >= 20
    assert payload["never_opens_github_issues"] is True


def test_missing_top_level_permissions_fails(tmp_path: Path) -> None:
    wf = tmp_path / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "x.yml").write_text(
        "name: x\non: push\njobs:\n  a:\n    runs-on: ubuntu-latest\n", encoding="utf-8"
    )
    (tmp_path / "go" / "adk_trading").mkdir(parents=True)
    (tmp_path / "tests" / "evals" / "harbor_configs" / "environment").mkdir(parents=True)
    payload = scan(tmp_path)
    assert payload["ok"] is False
    assert any("missing top-level permissions" in item for item in payload["findings"])


def test_top_level_write_fails_job_level_write_ok(tmp_path: Path) -> None:
    wf = tmp_path / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "good.yml").write_text(
        "name: g\non: push\npermissions: read-all\njobs:\n"
        "  a:\n    runs-on: ubuntu-latest\n    permissions:\n      contents: write\n",
        encoding="utf-8",
    )
    (wf / "bad.yml").write_text(
        "name: b\non: push\npermissions:\n  contents: write\njobs:\n  a:\n    runs-on: ubuntu-latest\n",
        encoding="utf-8",
    )
    (tmp_path / "go" / "adk_trading").mkdir(parents=True)
    (tmp_path / "tests" / "evals" / "harbor_configs" / "environment").mkdir(parents=True)
    payload = scan(tmp_path)
    assert payload["ok"] is False
    joined = "\n".join(payload["findings"])
    assert "bad.yml" in joined
    assert "good.yml" not in joined


def test_unhashed_pip_fails_hashed_ok(tmp_path: Path) -> None:
    wf = tmp_path / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "pip.yml").write_text(
        "name: p\non: push\npermissions: read-all\njobs:\n  a:\n    runs-on: ubuntu-latest\n"
        "    steps:\n      - run: pip install alpaca-py\n",
        encoding="utf-8",
    )
    (tmp_path / "go" / "adk_trading").mkdir(parents=True)
    (tmp_path / "tests" / "evals" / "harbor_configs" / "environment").mkdir(parents=True)
    payload = scan(tmp_path)
    assert payload["ok"] is False
    assert any("unhashed pip install" in item for item in payload["findings"])


def test_unpinned_from_fails(tmp_path: Path) -> None:
    wf = tmp_path / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "ok.yml").write_text(
        "name: o\non: push\npermissions: read-all\njobs: {}\n", encoding="utf-8"
    )
    docker = tmp_path / "go" / "adk_trading"
    docker.mkdir(parents=True)
    (docker / "Dockerfile").write_text("FROM alpine:latest\n", encoding="utf-8")
    (tmp_path / "tests" / "evals" / "harbor_configs" / "environment").mkdir(parents=True)
    payload = scan(tmp_path)
    assert payload["ok"] is False
    assert any("unpinned FROM" in item for item in payload["findings"])
