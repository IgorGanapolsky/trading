"""Validation paper account identity pin (AGENT-590)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from src.core.paper_account_identity import (
    VALIDATION_PAPER_ACCOUNT_NUMBER,
    PaperAccountIdentityError,
    assert_broker_is_validation_paper,
    paper_identity_block_reason,
)
from src.risk.trade_gateway import RejectionReason, TradeGateway, TradeRequest


def test_assert_accepts_validation_account() -> None:
    assert (
        assert_broker_is_validation_paper("pa3c5ag0cecq", equity=94181.95)
        == VALIDATION_PAPER_ACCOUNT_NUMBER
    )


@pytest.mark.parametrize(
    "number",
    ["PA3PYE08C9MN", "PA36N5ZP8S40", "979807421", "PAUNKNOWN"],
)
def test_assert_rejects_non_validation_accounts(number: str) -> None:
    with pytest.raises(PaperAccountIdentityError, match="WRONG_PAPER_ACCOUNT"):
        assert_broker_is_validation_paper(number, equity=30055.2)


def test_assert_rejects_missing_account_number() -> None:
    with pytest.raises(PaperAccountIdentityError, match="identity missing"):
        assert_broker_is_validation_paper(None, equity=94181.95)


def test_block_reason_none_when_unspecified() -> None:
    assert paper_identity_block_reason() is None
    assert paper_identity_block_reason(state={}) is None
    assert paper_identity_block_reason(state={"paper_account": {"equity": 94181.95}}) is None


def test_block_reason_30k_equity_fingerprint() -> None:
    reason = paper_identity_block_reason(state={"paper_account": {"equity": 30055.2}})
    assert reason is not None
    assert "30k" in reason


def test_block_reason_broker_number_wins_over_ledger() -> None:
    reason = paper_identity_block_reason(
        broker_account_number="PA3PYE08C9MN",
        state={"paper_account": {"account_number": "PA3C5AG0CECQ", "equity": 94181.95}},
    )
    assert reason is not None
    assert "PA3PYE08C9MN" in reason


def test_sync_from_alpaca_refuses_30k_broker_book(monkeypatch) -> None:
    import sys
    import types
    from pathlib import Path

    scripts_dir = Path(__file__).resolve().parents[1] / "scripts"
    sys.path.insert(0, str(scripts_dir))
    import sync_alpaca_state

    monkeypatch.setattr(
        "src.utils.alpaca_client.get_alpaca_credentials",
        lambda: ("paper_key", "paper_secret"),
    )
    monkeypatch.delenv("ALPACA_BROKERAGE_TRADING_API_KEY", raising=False)
    monkeypatch.delenv("ALPACA_BROKERAGE_TRADING_API_SECRET", raising=False)

    class _Executor:
        def __init__(self, paper=True, allow_simulator=False):  # noqa: ARG002
            self.trader = None
            self.account_snapshot = {
                "cash": 30147.2,
                "buying_power": 120000.0,
                "last_equity": 30060.0,
                "account_number": "PA3PYE08C9MN",
            }
            self.account_equity = 30055.2

        def sync_portfolio_state(self) -> None:
            return None

        def get_positions(self):
            return []

    fake_executor_mod = types.ModuleType("src.execution.alpaca_executor")
    fake_executor_mod.AlpacaExecutor = _Executor
    monkeypatch.setitem(sys.modules, "src.execution.alpaca_executor", fake_executor_mod)

    with pytest.raises(sync_alpaca_state.AlpacaSyncError, match="PA3PYE08C9MN"):
        sync_alpaca_state.sync_from_alpaca()


def test_sync_refuses_to_apply_30k_book(tmp_path, monkeypatch) -> None:
    import sys
    from pathlib import Path

    scripts_dir = Path(__file__).resolve().parents[1] / "scripts"
    sys.path.insert(0, str(scripts_dir))
    import sync_alpaca_state

    monkeypatch.setattr(sync_alpaca_state, "SYSTEM_STATE_FILE", tmp_path / "system_state.json")
    (tmp_path / "system_state.json").write_text("{}", encoding="utf-8")

    with pytest.raises(sync_alpaca_state.AlpacaSyncError, match="WRONG_PAPER_ACCOUNT"):
        sync_alpaca_state.update_system_state(
            {
                "paper": {
                    "mode": "paper",
                    "account_number": "PA3PYE08C9MN",
                    "equity": 30055.2,
                    "cash": 30147.2,
                    "positions_count": 4,
                }
            }
        )


class _Executor:
    def __init__(self, equity: float = 100_000, snapshot: dict | None = None) -> None:
        self.account_equity = equity
        self.account_snapshot = snapshot or {}
        self._positions: list[dict] = []

    def get_positions(self) -> list[dict]:
        return self._positions


def _option_request() -> TradeRequest:
    return TradeRequest(
        symbol="SPY261016P00742000",
        side="sell",
        quantity=1,
        source="test",
        is_option=True,
        strategy_type="put_credit",
        bid_price=5.00,
        ask_price=5.10,
        stop_price=10.0,
        is_spread=True,
        max_loss=200.0,
        dte=35,
    )


def test_gateway_rejects_30k_broker_snapshot(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.rag.retrieve_for_trade.retrieve_for_trade",
        lambda *args, **kwargs: MagicMock(lessons=[], meta={}),
    )
    gateway = TradeGateway(executor=None, paper=True)
    gateway.executor = _Executor(
        equity=30055.2,
        snapshot={"account_number": "PA3PYE08C9MN", "equity": 30055.2},
    )
    gateway._get_total_pl = lambda: 100.0  # type: ignore[method-assign]
    gateway._get_drawdown = lambda: 0.0  # type: ignore[method-assign]
    decision = gateway.evaluate(_option_request())
    assert not decision.approved
    assert RejectionReason.WRONG_PAPER_ACCOUNT in decision.rejection_reasons


def test_gateway_allows_unspecified_identity_for_unit_tests(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "src.rag.retrieve_for_trade.retrieve_for_trade",
        lambda *args, **kwargs: MagicMock(lessons=[], meta={}),
    )
    gateway = TradeGateway(executor=None, paper=True)
    gateway.executor = _Executor(equity=100_000)
    gateway._get_total_pl = lambda: 100.0  # type: ignore[method-assign]
    gateway._get_drawdown = lambda: 0.0  # type: ignore[method-assign]
    decision = gateway.evaluate(_option_request())
    assert RejectionReason.WRONG_PAPER_ACCOUNT not in decision.rejection_reasons


def test_gateway_rejects_30k_ledger_fingerprint(tmp_path, monkeypatch) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "system_state.json").write_text(
        json.dumps({"paper_account": {"equity": 30055.2, "cash": 30147.2}}),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "src.rag.retrieve_for_trade.retrieve_for_trade",
        lambda *args, **kwargs: MagicMock(lessons=[], meta={}),
    )
    gateway = TradeGateway(executor=None, paper=True)
    gateway.executor = _Executor(equity=100_000)
    gateway._get_total_pl = lambda: 100.0  # type: ignore[method-assign]
    gateway._get_drawdown = lambda: 0.0  # type: ignore[method-assign]
    decision = gateway.evaluate(_option_request())
    assert not decision.approved
    assert RejectionReason.WRONG_PAPER_ACCOUNT in decision.rejection_reasons
