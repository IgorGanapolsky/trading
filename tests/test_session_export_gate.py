"""Bolt Forge FORMAT: default DENY, seed-secret strip, operator lane blocked."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load():
    path = ROOT / "scripts" / "session_export_gate.py"
    spec = importlib.util.spec_from_file_location("session_export_gate", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_default_deny_without_opt_in(tmp_path: Path):
    mod = _load()
    with pytest.raises(PermissionError, match="default DENY"):
        mod.export_session(
            "hello",
            lane="research",
            dest=tmp_path / "out.txt",
            log=tmp_path / "log.jsonl",
            opt_in=False,
            understand_irreversible=True,
            allow_operator=False,
        )


def test_operator_lane_blocked_even_with_opt_in(tmp_path: Path):
    mod = _load()
    with pytest.raises(PermissionError, match="operator lane"):
        mod.export_session(
            "plan",
            lane="spy_put_credit",
            dest=tmp_path / "out.txt",
            log=tmp_path / "log.jsonl",
            opt_in=True,
            understand_irreversible=True,
            allow_operator=False,
        )


def test_seed_secret_stripped(tmp_path: Path):
    mod = _load()
    dest = tmp_path / "out.txt"
    raw = f"key={mod.SEED_SECRET} Bearer abc.def"
    report = mod.export_session(
        raw,
        lane="research",
        dest=dest,
        log=tmp_path / "log.jsonl",
        opt_in=True,
        understand_irreversible=True,
        allow_operator=False,
    )
    body = dest.read_text(encoding="utf-8")
    assert mod.SEED_SECRET not in body
    assert "PKLIVE_FAKE_VALUE" not in body
    assert "abc.def" not in body
    assert "[REDACTED]" in body
    assert report["remote_upload"] is False
    assert report["irreversible"] is True


def test_cli_deny_exit_2(tmp_path: Path):
    src = tmp_path / "in.txt"
    src.write_text("nope", encoding="utf-8")
    dest = tmp_path / "out.txt"
    r = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "session_export_gate.py"),
            "export",
            "--input",
            str(src),
            "--dest",
            str(dest),
            "--lane",
            "research",
            "--log",
            str(tmp_path / "log.jsonl"),
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert r.returncode == 2
    data = json.loads(r.stdout)
    assert data["ok"] is False
    assert not dest.exists()
