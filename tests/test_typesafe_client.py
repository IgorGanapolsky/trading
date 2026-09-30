import json
import logging
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.adapters.typesafe_client import load_api_key, system_one


def test_load_api_key_from_env():
    # Provide env dictionary directly
    assert load_api_key({"TYPESAFE_API_KEY": "env_key"}) == "env_key"
    assert load_api_key({"TYPESAFE_API_KEY": "  env_key_spaces  "}) == "env_key_spaces"


@patch("src.adapters.typesafe_client.os.name", "posix")
@patch("src.adapters.typesafe_client.Path.exists", return_value=True)
@patch("subprocess.run")
def test_load_api_key_from_keychain_success(mock_run, mock_exists):
    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.stdout = "keychain_key\n"
    mock_run.return_value = mock_proc

    with patch("src.adapters.typesafe_client.SECURE_FILE", Path("/does/not/exist")):
        key = load_api_key({})
        assert key == "keychain_key"
        mock_run.assert_called_once()


@patch("src.adapters.typesafe_client.os.name", "posix")
@patch("src.adapters.typesafe_client.Path.exists", return_value=True)
@patch("subprocess.run")
def test_load_api_key_from_keychain_empty(mock_run, mock_exists):
    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.stdout = " \n "
    mock_run.return_value = mock_proc

    with patch("src.adapters.typesafe_client.SECURE_FILE", Path("/does/not/exist")):
        key = load_api_key({})
        assert key is None
        mock_run.assert_called_once()


@patch("src.adapters.typesafe_client.os.name", "posix")
@patch("src.adapters.typesafe_client.Path.exists", return_value=True)
@patch("subprocess.run")
def test_load_api_key_from_keychain_fails(mock_run, mock_exists):
    mock_proc = MagicMock()
    mock_proc.returncode = 1
    mock_proc.stdout = ""
    mock_run.return_value = mock_proc

    with patch("src.adapters.typesafe_client.SECURE_FILE", Path("/does/not/exist")):
        key = load_api_key({})
        assert key is None
        mock_run.assert_called_once()


@patch("src.adapters.typesafe_client.os.name", "posix")
@patch("src.adapters.typesafe_client.Path.exists", return_value=True)
@patch("subprocess.run")
def test_load_api_key_keychain_exception(mock_run, mock_exists, caplog):
    caplog.set_level(logging.DEBUG)
    mock_run.side_effect = Exception("Keychain timeout")

    with patch("src.adapters.typesafe_client.SECURE_FILE", Path("/does/not/exist")):
        key = load_api_key({})
        assert key is None
        assert "TypeSafe Keychain read failed: Keychain timeout" in caplog.text


def test_load_api_key_from_secure_file(tmp_path):
    secure_file = tmp_path / "TYPESAFE_API_KEY"
    secure_file.write_text("file_key\n")

    with patch("src.adapters.typesafe_client.SECURE_FILE", secure_file):
        with patch("src.adapters.typesafe_client.os.name", "nt"):  # Skip keychain
            key = load_api_key({})
            assert key == "file_key"


def test_load_api_key_from_secure_file_empty(tmp_path):
    secure_file = tmp_path / "TYPESAFE_API_KEY"
    secure_file.write_text(" \n ")

    with patch("src.adapters.typesafe_client.SECURE_FILE", secure_file):
        with patch("src.adapters.typesafe_client.os.name", "nt"):  # Skip keychain
            key = load_api_key({})
            assert key is None


def test_load_api_key_secure_file_oserror(tmp_path, caplog):
    caplog.set_level(logging.DEBUG)
    secure_file = tmp_path / "TYPESAFE_API_KEY"
    secure_file.touch()

    def mock_read_text(*args, **kwargs):
        raise OSError("Permission denied")

    with patch("src.adapters.typesafe_client.SECURE_FILE", secure_file):
        with patch("src.adapters.typesafe_client.os.name", "nt"):  # Skip keychain
            with patch.object(Path, "read_text", side_effect=mock_read_text):
                key = load_api_key({})
                assert key is None
                assert "TypeSafe secure-file read failed: Permission denied" in caplog.text


def test_load_api_key_none(tmp_path):
    secure_file = tmp_path / "TYPESAFE_API_KEY"
    # File does not exist

    with patch("src.adapters.typesafe_client.SECURE_FILE", secure_file):
        with patch("src.adapters.typesafe_client.os.name", "nt"):  # Skip keychain
            key = load_api_key({})
            assert key is None


@patch("urllib.request.urlopen")
def test_system_one_success(mock_urlopen):
    mock_resp = MagicMock()
    mock_resp.read.return_value = b'{"result": "success"}'
    mock_resp.__enter__.return_value = mock_resp
    mock_urlopen.return_value = mock_resp

    res = system_one(state={"context": "test"}, questions={"q1": "test?"}, api_key="test_key")

    assert res == {"result": "success"}

    # Check request call
    req = mock_urlopen.call_args[0][0]
    assert req.headers["Authorization"] == "Bearer test_key"
    assert req.headers["Content-type"] == "application/json"

    data = json.loads(req.data.decode("utf-8"))
    assert data["state"] == {"context": "test"}
    assert data["questions"] == {"q1": "test?"}
    assert data["model"] == "jev-latest"


@patch("urllib.request.urlopen")
def test_system_one_http_error(mock_urlopen):
    mock_err = urllib.error.HTTPError(
        url="http://test", code=400, msg="Bad Request", hdrs={}, fp=None
    )
    mock_err.read = MagicMock(return_value=b"Invalid request format")
    mock_urlopen.side_effect = mock_err

    with pytest.raises(RuntimeError, match="TypeSafe HTTP 400: Invalid request format"):
        system_one(state={}, questions={}, api_key="test_key")


@patch("urllib.request.urlopen")
def test_system_one_http_error_read_fails(mock_urlopen):
    mock_err = urllib.error.HTTPError(
        url="http://test", code=500, msg="Internal Server Error", hdrs={}, fp=None
    )
    # The source code handles `exc.read()` throwing an exception by catching it,
    # and falling back to `str(exc)`.
    # `str(exc)` for HTTPError is "HTTP Error <code: <msg>"
    mock_err.read = MagicMock(side_effect=Exception("Cannot read body"))
    mock_urlopen.side_effect = mock_err

    with pytest.raises(
        RuntimeError, match="TypeSafe HTTP 500: HTTP Error 500: Internal Server Error"
    ):
        system_one(state={}, questions={}, api_key="test_key")
