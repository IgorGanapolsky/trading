from src.core.pal_integration import PALIntegration


def test_pal_initialization():
    pal = PALIntegration()
    assert pal is not None
    assert pal.challenge_threshold == 0.7


def test_pal_disabled_by_default_if_env_false(monkeypatch):
    monkeypatch.setenv("PAL_ENABLED", "false")
    pal = PALIntegration(enabled=True)
    assert pal.enabled is False
