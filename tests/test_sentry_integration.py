import sys
import types

import pytest
from src.utils import error_monitoring


class DummyScope:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def set_tag(self, *args, **kwargs):
        pass

    def set_level(self, *args, **kwargs):
        pass

    def set_context(self, *args, **kwargs):
        pass


class DummySDK:
    def __init__(self):
        self.init_called = False

    def init(self, **kwargs):
        self.init_called = True

    def push_scope(self):
        return DummyScope()


@pytest.fixture(autouse=True)
def reset_sentry_state(monkeypatch):
    error_monitoring._sentry_initialized = False
    monkeypatch.delenv("SENTRY_DSN", raising=False)


def test_init_sentry_with_stub(monkeypatch):
    dummy_sdk = DummySDK()
    logging_module = types.SimpleNamespace(LoggingIntegration=lambda **kwargs: ("logging", kwargs))
    requests_module = types.SimpleNamespace(RequestsIntegration=lambda: object())

    monkeypatch.setitem(sys.modules, "sentry_sdk", dummy_sdk)
    monkeypatch.setitem(sys.modules, "sentry_sdk.integrations.logging", logging_module)
    monkeypatch.setitem(sys.modules, "sentry_sdk.integrations.requests", requests_module)

    monkeypatch.setenv("SENTRY_DSN", "http://example.com/123")

    assert error_monitoring.init_sentry() is True
    assert dummy_sdk.init_called is True

    # smoke-test capture helpers
    error_monitoring.capture_workflow_failure("test", {"foo": "bar"})
    error_monitoring.capture_api_failure("alpaca", Exception("boom"))
    error_monitoring.capture_data_source_failure("alpaca", "SPY", "timeout")
