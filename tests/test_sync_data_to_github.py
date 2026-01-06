"""Tests for GitHub API-based data sync utility."""

import base64
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.sync_data_to_github import (
    GITHUB_API,
    REPO_NAME,
    REPO_OWNER,
    api_request,
    get_file_sha,
    get_github_token,
    sync_file,
)


class TestGetGithubToken:
    """Tests for get_github_token function."""

    def test_returns_github_token(self, monkeypatch):
        """Should return GITHUB_TOKEN when set."""
        monkeypatch.setenv("GITHUB_TOKEN", "test-token-123")
        monkeypatch.delenv("GH_TOKEN", raising=False)
        assert get_github_token() == "test-token-123"

    def test_returns_gh_token_fallback(self, monkeypatch):
        """Should return GH_TOKEN when GITHUB_TOKEN not set."""
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.setenv("GH_TOKEN", "gh-token-456")
        assert get_github_token() == "gh-token-456"

    def test_github_token_priority(self, monkeypatch):
        """GITHUB_TOKEN should take priority over GH_TOKEN."""
        monkeypatch.setenv("GITHUB_TOKEN", "github-token")
        monkeypatch.setenv("GH_TOKEN", "gh-token")
        assert get_github_token() == "github-token"

    def test_exits_when_no_token(self, monkeypatch):
        """Should exit with code 1 when no token available."""
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.delenv("GH_TOKEN", raising=False)
        with pytest.raises(SystemExit) as exc_info:
            get_github_token()
        assert exc_info.value.code == 1


class TestApiRequest:
    """Tests for api_request function."""

    @patch("scripts.sync_data_to_github.urllib.request.urlopen")
    def test_successful_get_request(self, mock_urlopen):
        """Should return status and data for successful GET."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = b'{"sha": "abc123"}'
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        status, data = api_request("GET", "/repos/test/test/contents/file.json", "token")

        assert status == 200
        assert data == {"sha": "abc123"}

    @patch("scripts.sync_data_to_github.urllib.request.urlopen")
    def test_successful_put_request(self, mock_urlopen):
        """Should return status and data for successful PUT."""
        mock_response = MagicMock()
        mock_response.status = 201
        mock_response.read.return_value = b'{"commit": {"sha": "def456"}}'
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        status, data = api_request(
            "PUT",
            "/repos/test/test/contents/file.json",
            "token",
            {"content": "test", "message": "test commit"},
        )

        assert status == 201
        assert data["commit"]["sha"] == "def456"


class TestGetFileSha:
    """Tests for get_file_sha function."""

    @patch("scripts.sync_data_to_github.api_request")
    def test_returns_sha_when_file_exists(self, mock_api_request):
        """Should return SHA when file exists on GitHub."""
        mock_api_request.return_value = (200, {"sha": "abc123def456"})

        sha = get_file_sha("data/test.json", "token")

        assert sha == "abc123def456"
        mock_api_request.assert_called_once()

    @patch("scripts.sync_data_to_github.api_request")
    def test_returns_none_when_file_not_found(self, mock_api_request):
        """Should return None when file doesn't exist (404)."""
        mock_api_request.return_value = (404, {"message": "Not Found"})

        sha = get_file_sha("data/new-file.json", "token")

        assert sha is None

    @patch("scripts.sync_data_to_github.api_request")
    def test_returns_none_on_error(self, mock_api_request):
        """Should return None on API errors."""
        mock_api_request.return_value = (500, {"message": "Server Error"})

        sha = get_file_sha("data/test.json", "token")

        assert sha is None


class TestSyncFile:
    """Tests for sync_file function."""

    @patch("scripts.sync_data_to_github.api_request")
    @patch("scripts.sync_data_to_github.get_file_sha")
    def test_creates_new_file(self, mock_get_sha, mock_api_request):
        """Should create new file when it doesn't exist on GitHub."""
        mock_get_sha.return_value = None  # File doesn't exist
        mock_api_request.return_value = (201, {"commit": {"sha": "newcommit"}})

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"test": "data"}, f)
            f.flush()

            result = sync_file(f.name, "token", "Test commit")

            assert result is True
            # Verify PUT was called without SHA
            call_args = mock_api_request.call_args
            assert "sha" not in call_args[0][3]  # data dict

            os.unlink(f.name)

    @patch("scripts.sync_data_to_github.api_request")
    @patch("scripts.sync_data_to_github.get_file_sha")
    def test_updates_existing_file(self, mock_get_sha, mock_api_request):
        """Should update file when it exists on GitHub."""
        mock_get_sha.return_value = "existing-sha-123"
        mock_api_request.return_value = (200, {"commit": {"sha": "updated"}})

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"updated": "data"}, f)
            f.flush()

            result = sync_file(f.name, "token")

            assert result is True
            # Verify PUT was called with SHA
            call_args = mock_api_request.call_args
            assert call_args[0][3]["sha"] == "existing-sha-123"

            os.unlink(f.name)

    def test_returns_false_for_missing_file(self):
        """Should return False when local file doesn't exist."""
        result = sync_file("/nonexistent/path/file.json", "token")
        assert result is False

    @patch("scripts.sync_data_to_github.api_request")
    @patch("scripts.sync_data_to_github.get_file_sha")
    def test_handles_conflict_with_retry(self, mock_get_sha, mock_api_request):
        """Should retry with fresh SHA on 409 conflict."""
        # First call: conflict, second call: fresh SHA, third call: success
        mock_get_sha.side_effect = [None, "fresh-sha-456"]
        mock_api_request.side_effect = [
            (409, {"message": "conflict"}),
            (200, {"commit": {"sha": "resolved"}}),
        ]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"conflict": "test"}, f)
            f.flush()

            result = sync_file(f.name, "token")

            assert result is True
            assert mock_api_request.call_count == 2

            os.unlink(f.name)

    @patch("scripts.sync_data_to_github.api_request")
    @patch("scripts.sync_data_to_github.get_file_sha")
    def test_returns_false_on_api_failure(self, mock_get_sha, mock_api_request):
        """Should return False on API failure."""
        mock_get_sha.return_value = None
        mock_api_request.return_value = (500, {"message": "Server Error"})

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"test": "data"}, f)
            f.flush()

            result = sync_file(f.name, "token")

            assert result is False

            os.unlink(f.name)


class TestBase64Encoding:
    """Tests for base64 encoding of file content."""

    @patch("scripts.sync_data_to_github.api_request")
    @patch("scripts.sync_data_to_github.get_file_sha")
    def test_content_is_base64_encoded(self, mock_get_sha, mock_api_request):
        """Should base64 encode file content in API request."""
        mock_get_sha.return_value = None
        mock_api_request.return_value = (201, {"commit": {"sha": "new"}})

        test_content = {"key": "value", "number": 123}

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(test_content, f)
            f.flush()

            sync_file(f.name, "token")

            # Get the content that was sent to API
            call_args = mock_api_request.call_args
            sent_content = call_args[0][3]["content"]

            # Decode and verify
            decoded = base64.b64decode(sent_content).decode("utf-8")
            assert json.loads(decoded) == test_content

            os.unlink(f.name)


class TestIntegrationConfig:
    """Tests for module configuration."""

    def test_repo_config(self):
        """Verify repo configuration is correct."""
        assert REPO_OWNER == "IgorGanapolsky"
        assert REPO_NAME == "trading"
        assert GITHUB_API == "https://api.github.com"
