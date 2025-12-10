from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from src.orchestrator.main import TradingOrchestrator
from src.orchestrator.smart_dca import SmartDCAAllocator


class DummyConfig:
    def __init__(self, allocations: dict[str, float]) -> None:
        self._allocations = allocations

    def get_tier_allocations(self) -> dict[str, float]:
        return dict(self._allocations)


def test_reallocate_all_to_bucket_focuses_budget() -> None:
    config = DummyConfig({"core_etfs": 4.0, "growth_stocks": 3.0, "crypto": 1.0})
    allocator = SmartDCAAllocator(config=config)

    expected_total = round(sum(config.get_tier_allocations().values()), 2)
    reallocated = allocator.reallocate_all_to_bucket("crypto")

    assert reallocated == expected_total
    assert allocator._bucket_targets["crypto"] == expected_total  # type: ignore[attr-defined]
    for bucket, value in allocator._bucket_targets.items():  # type: ignore[attr-defined]
        if bucket != "crypto":
            assert value == 0.0


def test_reallocate_all_to_bucket_adds_missing_bucket() -> None:
    config = DummyConfig({"tier1_core": 10.0})
    allocator = SmartDCAAllocator(config=config)

    allocator.reallocate_all_to_bucket("crypto")

    assert "crypto" in allocator._bucket_targets  # type: ignore[attr-defined]
    assert allocator._bucket_targets["crypto"] == 10.0  # type: ignore[attr-defined]


def test_orchestrator_weekend_reallocation(monkeypatch: pytest.MonkeyPatch) -> None:
    orchestrator = object.__new__(TradingOrchestrator)
    smart = MagicMock()
    smart.reallocate_all_to_bucket.return_value = 10.0
    orchestrator.smart_dca = smart  # type: ignore[attr-defined]

    events: list[dict] = []

    class _Telemetry:
        def record(self, **kwargs):  # noqa: ANN001
            events.append(kwargs)

    orchestrator.telemetry = _Telemetry()  # type: ignore[attr-defined]

    monkeypatch.setenv("WEEKEND_PROXY_REALLOCATE", "true")
    monkeypatch.delenv("WEEKEND_PROXY_BUCKET", raising=False)

    orchestrator._maybe_reallocate_for_weekend({"session_type": "off_hours_crypto_proxy"})  # type: ignore[attr-defined]

    smart.reallocate_all_to_bucket.assert_called_once_with("crypto")
    assert events
    assert events[0]["payload"]["reallocated_budget"] == 10.0


def test_orchestrator_weekend_reallocation_respects_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    orchestrator = object.__new__(TradingOrchestrator)
    orchestrator.smart_dca = MagicMock()  # type: ignore[attr-defined]
    orchestrator.telemetry = SimpleNamespace(
        record=lambda **kwargs: None  # noqa: ARG005
    )  # type: ignore[attr-defined]

    monkeypatch.setenv("WEEKEND_PROXY_REALLOCATE", "false")

    orchestrator._maybe_reallocate_for_weekend({"session_type": "off_hours_crypto_proxy"})  # type: ignore[attr-defined]

    orchestrator.smart_dca.reallocate_all_to_bucket.assert_not_called()  # type: ignore[attr-defined]
