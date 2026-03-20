"""Tests for the MCP server tools."""

import time
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

import pytest

from claude_colab.mcp_server import (
    _check_session_age,
    _ensure_healthy,
    colab_download,
    colab_exec,
    colab_python,
    colab_status,
    colab_upload,
)


@pytest.fixture
def mock_config():
    return {
        "url": "https://test.trycloudflare.com",
        "token": "tok",
        "encryption_key": "key",
        "connected_at": datetime.now(timezone.utc).isoformat(),
    }


@pytest.fixture
def mock_client():
    client = MagicMock()
    client.health.return_value = {
        "status": "ok",
        "version": "0.1.0",
        "gpu_name": "Tesla T4",
        "vram_total": 15.0,
        "vram_used": 1.2,
    }
    return client


class TestColabStatus:
    @patch("claude_colab.mcp_server._get_client_and_config")
    def test_returns_health(self, mock_get, mock_client, mock_config):
        mock_get.return_value = (mock_client, mock_config)
        result = colab_status()
        assert "Tesla T4" in str(result)

    @patch("claude_colab.mcp_server._get_client_and_config")
    def test_not_connected(self, mock_get):
        mock_get.return_value = (None, None)
        result = colab_status()
        assert "Not connected" in str(result)


class TestColabExec:
    @patch("claude_colab.mcp_server._get_client_and_config")
    def test_runs_command(self, mock_get, mock_client, mock_config):
        mock_client.exec.return_value = {
            "stdout": "hello\n", "stderr": "", "exit_code": 0, "duration": 0.1,
        }
        mock_get.return_value = (mock_client, mock_config)
        result = colab_exec("echo hello")
        assert result["stdout"] == "hello\n"


class TestColabPython:
    @patch("claude_colab.mcp_server._get_client_and_config")
    def test_runs_code(self, mock_get, mock_client, mock_config):
        mock_client.python.return_value = {
            "output": "42\n", "error": None, "return_value": 42, "duration": 0.1,
        }
        mock_get.return_value = (mock_client, mock_config)
        result = colab_python("print(42)")
        assert result["return_value"] == 42


class TestColabUpload:
    @patch("claude_colab.mcp_server._get_client_and_config")
    def test_uploads_file(self, mock_get, mock_client, mock_config):
        mock_client.upload.return_value = {"ok": True, "path": "/content/x.py", "size_bytes": 100}
        mock_get.return_value = (mock_client, mock_config)
        result = colab_upload("/local/x.py", "/content/x.py")
        assert result["ok"] is True


class TestColabDownload:
    @patch("claude_colab.mcp_server._get_client_and_config")
    def test_downloads_file(self, mock_get, mock_client, mock_config):
        mock_client.download.return_value = {"content_b64": "aGVsbG8=", "path": "/content/x", "size_bytes": 5}
        mock_get.return_value = (mock_client, mock_config)
        result = colab_download("/content/x", "/local/x")
        assert result["size_bytes"] == 5


class TestSessionAge:
    def test_fresh_session_no_warning(self):
        now_iso = datetime.now(timezone.utc).isoformat()
        warning = _check_session_age(now_iso)
        assert warning is None

    def test_old_session_warns(self):
        old = (datetime.now(timezone.utc) - timedelta(hours=11)).isoformat()
        warning = _check_session_age(old)
        assert "expire soon" in warning

    def test_invalid_date_no_crash(self):
        warning = _check_session_age("not-a-date")
        assert warning is None


class TestHealthCheck:
    def test_lazy_check_on_stale(self, mock_client):
        _ensure_healthy(mock_client, last_check=0)
        mock_client.health.assert_called_once()

    def test_skip_check_on_fresh(self, mock_client):
        _ensure_healthy(mock_client, last_check=time.time())
        mock_client.health.assert_not_called()
