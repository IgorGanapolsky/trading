"""Tests for TypeSafe System One claim-gate FORMAT steal."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    # Ensure package path for src.adapters import inside the script
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    spec.loader.exec_module(mod)
    return mod


def test_offline_denies_false_edge_claim():
    mod = _load("typesafe_claim_gate", ROOT / "scripts" / "typesafe_claim_gate.py")
    result = mod.offline_decide(
        "Put credit is profitable with proven positive expectancy.",
        {"paired_buffett_closes": 0, "live_blocked": True, "paper_only": True},
    )
    assert result["action"] == "deny"
    assert result["ok"] is False
    assert result["claim_supported_noul"] < 0.1
    assert "DENY" in result["gate"]


def test_offline_denies_profitable_and_making_money_terms():
    mod = _load("typesafe_claim_gate", ROOT / "scripts" / "typesafe_claim_gate.py")
    facts = {"paired_buffett_closes": 0, "live_blocked": True}
    for claim in (
        "The strategy is profitable.",
        "We improved profitability.",
        "Are we making money?",
    ):
        assert mod.offline_decide(claim, facts)["action"] == "deny", claim


def test_offline_abstains_non_edge_claim():
    mod = _load("typesafe_claim_gate", ROOT / "scripts" / "typesafe_claim_gate.py")
    result = mod.offline_decide(
        "Broker sync completed for paper account.",
        {"paired_buffett_closes": 0, "live_blocked": True},
    )
    assert result["action"] == "abstain"
    assert result["mode"] == "offline"


def test_confidence_routing_forces_abstain_and_severity_deny():
    mod = _load("typesafe_claim_gate", ROOT / "scripts" / "typesafe_claim_gate.py")
    assert mod.apply_confidence_routing(action="allow", confidence=0.4, min_confidence=0.6) == (
        "abstain"
    )
    assert mod.apply_confidence_routing(action="allow", confidence=None, min_confidence=0.6) == (
        "abstain"
    )
    assert mod.apply_confidence_routing(action="deny", confidence=0.2, min_confidence=0.6) == "deny"
    assert (
        mod.apply_confidence_routing(
            action="abstain",
            confidence=0.48,
            min_confidence=0.6,
            claim_supported_noul=0.03,
            severity_score=1.96,
        )
        == "deny"
    )


def test_online_cannot_allow_edge_when_ledger_incomplete(monkeypatch):
    mod = _load("typesafe_claim_gate", ROOT / "scripts" / "typesafe_claim_gate.py")

    def fake_system_one(**_kwargs):
        return {
            "model": "jev-test",
            "answers": {
                "claim_supported": {"type": "noul", "noul": 0.9},
                "action": {"type": "choice", "choice": "allow", "confidence": 0.99},
                "severity": {"type": "score", "score": 0.1, "confidence": 0.9},
            },
            "usage": {},
        }

    monkeypatch.setattr(mod, "system_one", fake_system_one)
    result = mod.online_decide(
        "Put credit is profitable.",
        {"paired_buffett_closes": 0, "live_blocked": True},
        api_key="test-key",
    )
    assert result["action"] == "deny"
    assert result["raw_action"] == "allow"


def test_provider_failure_fail_closes(monkeypatch):
    mod = _load("typesafe_claim_gate", ROOT / "scripts" / "typesafe_claim_gate.py")
    monkeypatch.setattr(mod, "load_api_key", lambda: "test-key")
    monkeypatch.setattr(
        mod,
        "online_decide",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("TypeSafe HTTP 500")),
    )
    result = mod.decide("Inventory audit finished.", offline=False)
    assert result["action"] in {"abstain", "deny"}
    assert result["ok"] is False
    assert "provider_error" in result


def test_online_decide_uses_mocked_system_one(monkeypatch):
    mod = _load("typesafe_claim_gate", ROOT / "scripts" / "typesafe_claim_gate.py")

    def fake_system_one(**_kwargs):
        return {
            "model": "jev-test",
            "answers": {
                "claim_supported": {"type": "noul", "noul": 0.02},
                "action": {
                    "type": "choice",
                    "choice": "deny",
                    "confidence": 0.9,
                    "probabilities": {"allow": 0.0, "abstain": 0.1, "deny": 0.9},
                },
                "severity": {"type": "score", "score": 2.0, "confidence": 0.95},
            },
            "usage": {"input_tokens": 10, "output_tokens": 5},
        }

    monkeypatch.setattr(mod, "system_one", fake_system_one)
    result = mod.online_decide(
        "Strategy is validated and profitable.",
        {"paired_buffett_closes": 0, "live_blocked": True},
        api_key="test-key",
    )
    assert result["mode"] == "online"
    assert result["action"] == "deny"
    assert result["model"] == "jev-test"


def test_cli_offline_exit_codes():
    deny = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "typesafe_claim_gate.py"),
            "--offline",
            "--claim",
            "We have proven positive expectancy and are profitable.",
            "--json",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert deny.returncode == 3
    payload = json.loads(deny.stdout)
    assert payload["action"] == "deny"

    abstain = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "typesafe_claim_gate.py"),
            "--offline",
            "--claim",
            "Inventory audit finished.",
            "--json",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert abstain.returncode == 2
    assert json.loads(abstain.stdout)["action"] == "abstain"


def test_adapter_load_api_key_from_environ(monkeypatch, tmp_path):
    from src.adapters import typesafe_client as tc

    monkeypatch.setattr(tc, "SECURE_FILE", tmp_path / "missing")
    key = tc.load_api_key({"TYPESAFE_API_KEY": "apikey_test_value"})
    assert key == "apikey_test_value"
