from __future__ import annotations

from scripts.publish_twitter import (
    POST_MAX_LENGTH,
    generate_twitter_post,
    missing_credential_names,
    resolve_credentials,
)


def test_resolve_credentials_prefers_twitter_namespace() -> None:
    env = {
        "TWITTER_API_KEY": "tw-key",
        "TWITTER_API_SECRET": "tw-secret",
        "TWITTER_ACCESS_TOKEN": "tw-access",
        "TWITTER_ACCESS_TOKEN_SECRET": "tw-access-secret",
        "X_API_KEY": "x-key",
        "X_API_SECRET": "x-secret",
        "X_ACCESS_TOKEN": "x-access",
        "X_ACCESS_TOKEN_SECRET": "x-access-secret",
    }
    creds = resolve_credentials(env)
    assert creds["api_key"] == "tw-key"
    assert creds["api_secret"] == "tw-secret"
    assert creds["access_token"] == "tw-access"
    assert creds["access_token_secret"] == "tw-access-secret"


def test_resolve_credentials_falls_back_to_x_namespace() -> None:
    env = {
        "X_API_KEY": "x-key",
        "X_API_SECRET": "x-secret",
        "X_ACCESS_TOKEN": "x-access",
        "X_ACCESS_TOKEN_SECRET": "x-access-secret",
    }
    creds = resolve_credentials(env)
    assert creds["api_key"] == "x-key"
    assert creds["api_secret"] == "x-secret"
    assert creds["access_token"] == "x-access"
    assert creds["access_token_secret"] == "x-access-secret"


def test_missing_credential_names_lists_required_inputs() -> None:
    missing = missing_credential_names({"api_key": "k", "api_secret": "", "access_token": ""})
    assert "TWITTER_API_SECRET/X_API_SECRET" in missing
    assert "TWITTER_ACCESS_TOKEN/X_ACCESS_TOKEN" in missing
    assert "TWITTER_ACCESS_TOKEN_SECRET/X_ACCESS_TOKEN_SECRET" in missing


def test_generate_twitter_post_is_within_character_limit() -> None:
    post = generate_twitter_post("positive", "A" * 180, "https://example.com/" + "x" * 200)
    assert len(post) <= POST_MAX_LENGTH
